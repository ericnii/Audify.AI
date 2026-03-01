from __future__ import annotations
import logging
import os
import shutil
import threading 
import uuid 
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import numpy as np
import subprocess

from apply_f0_world import apply_f0_world
from audio_ops import time_stretch_to_duration, resample_wav
from f0_extract import extract_f0_pyworld
from tts_local import tts_to_wav, LANG_CODE_MAP, warmup_tts_model
from svc_infer import get_available_speakers, run_voice_conversion
from mixdown import mix_vocals_instrumental
from audio_stems import seperate_stems_demucs
from text_cleanup import clean_for_tts
from timbre_match import select_closest_speaker
from transcribe_whisper import transcribe_with_whisper
from translate_marianmt import translate_segments

app = FastAPI()
LOGGER = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS = Path("runs")
RUNS.mkdir(exist_ok=True)

app.mount("/files", StaticFiles(directory=str(RUNS)), name="files")

JOBS: Dict[str, Dict[str, Any]] = {}
SUPPORTED_LANGUAGES = sorted(LANG_CODE_MAP.keys())
PROXY_TTS_PROGRESS_START = 75
PROXY_TTS_PROGRESS_END = 87


def _proxy_tts_progress(done: int, total: int) -> int:
    if total <= 0:
        return PROXY_TTS_PROGRESS_END
    ratio = max(0.0, min(1.0, done / total))
    return int(
        round(
            PROXY_TTS_PROGRESS_START
            + ratio * (PROXY_TTS_PROGRESS_END - PROXY_TTS_PROGRESS_START)
        )
    )


@app.on_event("startup")
def _startup_prewarm_models() -> None:
    if os.getenv("TTS_PREWARM", "1").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    try:
        device = warmup_tts_model()
        LOGGER.info("TTS warmup complete on device: %s", device)
    except Exception:
        # Keep API available even if TTS warmup fails; first request will retry load.
        LOGGER.exception("TTS warmup failed during startup.")

def _slice_f0_window(f0: np.ndarray, t: np.ndarray, start_s: float, end_s: float):
    i0 = int(np.searchsorted(t, start_s, side="left"))
    i1 = int(np.searchsorted(t, end_s, side="left"))
    f0_seg = f0[i0:i1]
    t_seg = t[i0:i1] - start_s
    return f0_seg, t_seg

def _stitch_segments_ffmpeg(rendered: list[tuple[float, Path]], out_wav: Path, sr: int = 16000):
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    if not rendered:
        subprocess.run(
            ["ffmpeg","-y","-f","lavfi","-i",f"anullsrc=r={sr}:cl=mono","-t","1",str(out_wav)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return

    inputs = []
    filters = []
    amix_inputs = []
    for i, (start_s, wav) in enumerate(rendered):
        inputs += ["-i", str(wav)]
        delay_ms = int(max(0.0, start_s) * 1000)
        filters.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
        amix_inputs.append(f"[a{i}]")

    filter_complex = ";".join(filters) + ";" + "".join(amix_inputs) + f"amix=inputs={len(rendered)}:normalize=0[out]"
    subprocess.run(
        ["ffmpeg","-y", *inputs, "-filter_complex", filter_complex, "-map","[out]", str(out_wav)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

def job_worker(job_id: str, 
               input_path: Path, 
               start_time: Optional[float],
               end_time: Optional[float],
               target_language: str,
               ) -> None:
    """
    Take a song and add it to JOBS (local dictionary for now, would be database or 
    redis for production) for the React app to poll.
    """
    job_dir = RUNS / job_id
    try:
        JOBS[job_id]["status"] = "separating"
        stems = seperate_stems_demucs(
            input_path, 
            job_dir / "stems",
            start_time=start_time,
            end_time=end_time
            )
        JOBS[job_id].update({"stage": "transcribing", "progress": 35})

        # Copy to stable names
        vocals_out = job_dir / "vocals.wav"
        inst_out = job_dir / "instrumental.wav"
        shutil.copy(stems["vocals"], vocals_out)
        shutil.copy(stems["instrumental"], inst_out)

        JOBS[job_id].update({"status": "transcribing", "stage": "transcribing", "progress": 50})
        segments = transcribe_with_whisper(vocals_out)

        JOBS[job_id].update({"status": "translating", "stage": "translating", "progress": 60})
        segments = translate_segments(segments, vocals_out, target_language=target_language)

        # New: extract F0 once
        f0_data = extract_f0_pyworld(vocals_out, sr=16000, hop_ms=10.0)
        f0_global = f0_data["f0"]
        t_global  = f0_data["t"]
        sr        = f0_data["sr"]
        hop_ms    = 10.0
        # Save f0 if you want cache: np.save(job_dir/"f0.npy", f0)

        # New: generate proxy TTS per segment (stub)
        JOBS[job_id].update({"status": "proxy_tts", "stage": "proxy_tts", "progress": 75})
        proxy_dir = job_dir / "proxy_segments"
        proxy_dir.mkdir(exist_ok=True)

        # For MVP: just create per-segment wavs and later stitch.
        # You will: (1) TTS -> (2) time-stretch to segment duration -> (3) (optional) pitch shaping
        rendered = []
        total_segments = len(segments)
        JOBS[job_id].update(
            {
                "status": "proxy_tts",
                "stage": f"proxy_tts (0/{total_segments})",
                "progress": _proxy_tts_progress(0, total_segments),
                "proxy_segments_done": 0,
                "proxy_segments_total": total_segments,
            }
        )
        
        # segment loop
        for i, seg in enumerate(segments, start=1):
            start = float(seg["start"])
            end = float(seg["end"])
            dur = max(0.05, end - start)

            text = (seg.get("translated") or "").strip()
            if text:
                seg_dir = proxy_dir / f"{i-1:04d}"
                seg_dir.mkdir(parents=True, exist_ok=True)

                tts_raw = seg_dir / "tts.wav"
                tts_stretch = seg_dir / "tts_stretch.wav"
                tts_pitched = seg_dir / "tts_pitched.wav"

                # 0) clean up the text for tts
                text = clean_for_tts(seg.get("translated", ""))
                if text:
                    # 1) TTS proxy
                    tts_to_wav(text, tts_raw, language=seg["language"])  # keep your signature

                    # 2) Stretch to match original segment duration
                    time_stretch_to_duration(tts_raw, tts_stretch, target_dur_s=dur)

                    # 3) Slice original F0 for this segment
                    f0_seg, t_seg = _slice_f0_window(f0_global, t_global, start, end)

                    # 4) Impose original melody onto stretched proxy
                    if (f0_seg > 0).sum() < 3:
                        # no voiced pitch to impose, just use stretched
                        tts_pitched.write_bytes(tts_stretch.read_bytes())
                    else:
                        apply_f0_world(
                            in_wav=tts_stretch,
                            out_wav=tts_pitched,
                            f0_target=f0_seg,
                            t_target=t_seg,
                            sr=sr,
                            hop_ms=hop_ms,
                        )

                    rendered.append((start, tts_pitched))
            JOBS[job_id].update(
                {
                    "status": "proxy_tts",
                    "stage": f"proxy_tts ({i}/{total_segments})",
                    "progress": _proxy_tts_progress(i, total_segments),
                    "proxy_segments_done": i,
                    "proxy_segments_total": total_segments,
                    "proxy_rendered_segments": len(rendered),
                }
            )

        # stitch proxy segments -> proxy_full.wav
        proxy_full = job_dir / "proxy_full.wav"
        _stitch_segments_ffmpeg(rendered, proxy_full, sr=sr)

        # resample wav to 32k
        resample_wav(proxy_full, proxy_full, sr=32000, channels=1)
        # Implement with ffmpeg concat once you have segments normalized SR/channels.

        # New: so-vits-svc inference
        JOBS[job_id].update({"status": "svc", "stage": "svc", "progress": 88})
        v_vocals = job_dir / "v_translated_vocals.wav"
        available_speakers = get_available_speakers()
        selected_voice = select_closest_speaker(proxy_full, available_speakers)
        JOBS[job_id].update({"selected_voice": selected_voice})
        run_voice_conversion(proxy_full, v_vocals, spk_name=selected_voice)

        # New: mix
        JOBS[job_id].update({"status": "mixing", "stage": "mixing", "progress": 95})
        final_mix = job_dir / "final_mix.wav"
        mix_vocals_instrumental(v_vocals, inst_out, final_mix)
        words = [w for seg in segments for w in seg.get("words", [])] if segments else []

        JOBS[job_id].update({
            "status": "done",
            "stage": "done",
            "progress": 100,
            "vocals_url": f"/files/{job_id}/v_translated_vocals.wav",
            "instrumental_url": f"/files/{job_id}/instrumental.wav",
            "mix_url": f"/files/{job_id}/final_mix.wav",
            "target_language": target_language,
            "segments": segments,
            "selected_voice": selected_voice,
            "words": words,  # Add word-level timing data
        })

    except Exception as e:
        JOBS[job_id].update({"status": "error", "stage": "error", "error": repr(e)})

@app.post("/jobs")
async def create_job(
    file: UploadFile = File(...),
    start_time: Optional[float] = Form(None),
    end_time: Optional[float] = Form(None),
    language: str = Form("Spanish"),
) -> Dict[str, str]:
    """
    Create a job and add it to JOBS.
    """
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{language}'. Supported: {', '.join(SUPPORTED_LANGUAGES)}",
        )

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "queued",
        "stage": "queued",
        "progress": 0,
        "target_language": language,
    }

    job_dir = RUNS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    input_path = job_dir / file.filename
    input_path.write_bytes(await file.read())

    t = threading.Thread(
        target=job_worker, 
        args=(job_id, input_path, start_time, end_time, language),
        daemon=True,
    )
    t.start()

    return {"job_id": job_id}

@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    """
    Return the job associated with job_id.
    """
    return JOBS.get(job_id, {"status": "not_found"})
