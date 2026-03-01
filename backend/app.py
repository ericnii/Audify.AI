from __future__ import annotations
import shutil
import threading 
import uuid 
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from audio_stems import seperate_stems_demucs
from transcribe_whisper import transcribe_with_whisper
from translate_gemini import translate_segments
from vertex_tts import synthesize_texts_to_mp3, segments_to_ssml

app = FastAPI()

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

def job_worker(job_id: str, 
               input_path: Path, 
               start_time: Optional[float],
               end_time: Optional[float]
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
        clipped_vocals = job_dir / "vocals_clipped.wav"

        JOBS[job_id].update({"status": "transcribing", "stage": "transcribing", "progress": 50})
        segments = transcribe_with_whisper(vocals_out)
        # Translate segments to Spanish with instrumental context
        segments = translate_segments(segments, clipped_vocals, target_language="Spanish")
        JOBS[job_id].update({"stage": "finalizing", "progress": 80})

        # Synthesize translated segments into TTS audio using ElevenLabs (if configured)
        try:
            # Build SSML from translated segments so the TTS can preserve pauses,
            # language tags, and per-segment voice hints.
            # Map simple language names to SSML language codes when possible.
            def _lang_name_to_code(name: Optional[str]) -> str:
                if not name:
                    return "en-US"
                lower = name.lower()
                if "span" in lower:
                    return "es-ES"
                if "english" in lower:
                    return "en-US"
                if "french" in lower:
                    return "fr-FR"
                return "en-US"

            # Determine a global language code from the job target (segments may
            # carry a language field, but translate_segments currently writes
            # the target name like 'Spanish').
            global_lang = _lang_name_to_code(segments[0].get("language") if segments else None)
            ssml = segments_to_ssml(segments, global_lang=global_lang)
            tts_out = job_dir / "tts.mp3"
            # We pass the SSML as a single element and set ssml=True so the
            # synthesize helper treats it as SSML payload.
            synthesize_texts_to_mp3([ssml], tts_out, ssml=True, voice={"language_code": global_lang})
            tts_url = f"/files/{job_id}/tts.mp3"
            JOBS[job_id].update({"tts_url": tts_url})
        except Exception as e:
            # Don't fail the whole job if TTS fails; record error for frontend
            JOBS[job_id].setdefault("notes", {})["tts_error"] = repr(e)

        JOBS[job_id].update({"stage": "finalizing", "progress": 95})

        JOBS[job_id].update({
            "status": "done",
            "vocals_url": f"/files/{job_id}/vocals.wav",
            "instrumental_url": f"/files/{job_id}/instrumental.wav",
            "segments": segments,
        })

    except Exception as e:
        JOBS[job_id].update({"status": "error", "stage": "error", "error": repr(e)})

@app.post("/jobs")
async def create_job(
    file: UploadFile = File(...),
    start_time: Optional[float] = Form(None),
    end_time: Optional[float] = Form(None)
) -> Dict[str, str]:
    """
    Create a job and add it to JOBS.
    """
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "queued", "stage": "queued", "progress": 0}

    job_dir = RUNS / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    input_path = job_dir / file.filename
    input_path.write_bytes(await file.read())

    t = threading.Thread(
        target=job_worker, 
        args=(job_id, input_path, start_time, end_time),
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
