from __future__ import annotations
import shutil
import threading 
import uuid 
import math
from pathlib import Path
from typing import List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from audio_stems import seperate_stems_demucs
from audio_chunk import extract_wav_chunk
from transcribe_gemini import transcribe_with_timestamps_gemini

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

def transcribe_chunked_gemini(
    job_id: str,
    vocals_wav: str | Path,
    work_dir: str | Path,
    chunk_s: float = 15.0,
    total_s: float = 30.0,      
) -> List[Dict[str, Any]]:
    """
    Transcribe a specific chunk of the 
    vocal stem and outputs a list of 
    segments.
    """
    vocals_wav = Path(vocals_wav).resolve()
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    chunks_dir = work_dir / "chunks"
    chunks_dir.mkdir(exist_ok=True)

    segments_all: List[Dict[str, Any]] = []

    t = 0.0
    n_chunks = int(math.ceil(total_s / chunk_s))

    for i in range(n_chunks):
        JOBS[job_id].update({
            "stage": f"transcribing ({i + 1}/{n_chunks})",
            "progress": 35 + int(55 * (i + 1) / n_chunks)
        })
        dur = min(chunk_s, total_s - t)
        chunk_path = chunks_dir / f"chunk_{i:03d}.wav"
        extract_wav_chunk(vocals_wav, chunk_path, start_s=t, dur_s=dur)

        segs = transcribe_with_timestamps_gemini(chunk_path)
        
        for s in segs: 
            segments_all.append({
                "start": s["start"] + t,
                "end": s["end"] + t,
                "text": s["text"],
            })

        t += dur

    return segments_all

def job_worker(job_id: str, 
               input_path: Path, 
               clip_seconds: float
               ) -> None:
    """
    Take a song and add it to JOBS (local dictionary for now, would be database or 
    redis for production) for the React app to poll.
    """
    job_dir = RUNS / job_id
    try:
        JOBS[job_id]["status"] = "separating"
        stems = seperate_stems_demucs(input_path, job_dir / "stems")
        JOBS[job_id].update({"stage": "transcribing", "progress": 35})

        # Copy to stable names
        vocals_out = job_dir / "vocals.wav"
        inst_out = job_dir / "instrumental.wav"
        shutil.copy(stems["vocals"], vocals_out)
        shutil.copy(stems["instrumental"], inst_out)

        JOBS[job_id]["status"] = "transcribing"
        segments = transcribe_chunked_gemini(job_id, vocals_out, job_dir, total_s=clip_seconds, chunk_s=min(15.0, clip_seconds))
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
    clip_seconds: float = Form(30.0),  # MVP: only process first N seconds
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

    t = threading.Thread(target=job_worker, args=(job_id, input_path, clip_seconds), daemon=True)
    t.start()

    return {"job_id": job_id}

@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    """
    Return the job associated with job_id.
    """
    return JOBS.get(job_id, {"status": "not_found"})