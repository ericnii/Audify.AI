from __future__ import annotations
import os
import shutil
import threading 
import uuid 
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from audio_stems import seperate_stems_demucs
from transcribe_whisper import transcribe_with_whisper, transcribe_with_segments_and_words
from translate_gemini import translate_segments
from vertex_tts import synthesize_texts_to_mp3_api_key, segments_to_ssml, combine_audio_files, reshape_for_synthesis

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
               end_time: Optional[float],
<<<<<<< HEAD
               language: str = "Spanish"
=======
               target_language: str = "Spanish"
>>>>>>> new_lang
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
        
        # Use new function that returns both segments and words with timing/breaks
        transcription = transcribe_with_segments_and_words(vocals_out)
        segments = transcription["segments"]
        words = transcription["words"]
        
        # Translate only the segments (not individual words)
<<<<<<< HEAD
        segments = translate_segments(segments, clipped_vocals, target_language=language)
=======
        segments = translate_segments(segments, vocals_out, target_language=target_language)
        
        # Reshape segments to add break timing for better rhythm syncing
        segments = reshape_for_synthesis(segments)
        
>>>>>>> new_lang
        JOBS[job_id].update({"stage": "finalizing", "progress": 80})

        # Synthesize translated segments into TTS audio using Google Cloud TTS API
        try:
            api_key = os.environ.get("GOOGLE_TTS_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                JOBS[job_id].setdefault("notes", {})["tts_error"] = "No API key found for TTS"
            else:
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
                # Use the API key version for synthesizing translated segments
                synthesize_texts_to_mp3_api_key(api_key, [ssml], tts_out, ssml=True, voice={"language_code": global_lang})
                tts_url = f"/files/{job_id}/tts.mp3"
                JOBS[job_id].update({"tts_url": tts_url})
                
                # Combine TTS with instrumental audio, aligned to segment timings
                combined_out = job_dir / "combined.wav"
                combine_audio_files(tts_out, inst_out, combined_out, segments=segments)
                combined_url = f"/files/{job_id}/combined.wav"
                JOBS[job_id].update({"combined_url": combined_url})
        except Exception as e:
            # Don't fail the whole job if TTS fails; record error for frontend
            JOBS[job_id].setdefault("notes", {})["tts_error"] = repr(e)

        JOBS[job_id].update({"stage": "finalizing", "progress": 95})

        JOBS[job_id].update({
            "status": "done",
            "vocals_url": f"/files/{job_id}/vocals.wav",
            "instrumental_url": f"/files/{job_id}/instrumental.wav",
            "segments": segments,
            "words": words,  # Add word-level timing data
        })

    except Exception as e:
        JOBS[job_id].update({"status": "error", "stage": "error", "error": repr(e)})

@app.post("/jobs")
async def create_job(
    file: UploadFile = File(...),
    start_time: Optional[float] = Form(None),
    end_time: Optional[float] = Form(None),
<<<<<<< HEAD
    language: str = Form("Spanish"),
=======
    target_language: str = Form("Spanish")
>>>>>>> new_lang
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
<<<<<<< HEAD
        target=job_worker,
        args=(job_id, input_path, start_time, end_time, language),
=======
        target=job_worker, 
        args=(job_id, input_path, start_time, end_time, target_language),
>>>>>>> new_lang
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
