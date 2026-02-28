from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any

from audio_chunk import extract_wav_chunk
from transcribe_gemini import transcribe_with_timestamps_gemini

def transcribe_chunked_gemini(
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

    segments_all: List[Dict[str, Any]] = []
    t = 0.0
    i = 0
    while t < total_s:
        dur = min(chunk_s, total_s - t)
        chunk_path = work_dir / f"chunk_{i:03d}.wav"
        extract_wav_chunk(vocals_wav, chunk_path, start_s=t, dur_s=dur)

        segs = transcribe_with_timestamps_gemini(chunk_path)
        for s in segs: 
            segments_all.append({
                "start": s["start"] + t,
                "end": s["end"] + t,
                "text": s["text"],
            })
        t += dur
        i += 1
    return segments_all