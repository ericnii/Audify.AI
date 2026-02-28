from __future__ import annotations
import subprocess
from pathlib import Path

def extract_wav_chunk(
        input_wav: str | Path,
        out_wav: str | Path,
        start_s: float,
        dur_s: float
) -> None:
    """
    Return a trimmed segment starting from 
    start_s which lasts dur_s of a given input_wav.
    """
    input_wav = Path(input_wav).resolve()
    out_wav = Path(out_wav).resolve()
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_s),
        "-t", str(dur_s),
        "-i", str(input_wav),
        "-ac", "1",
        "-ar", "16000",
        str(out_wav)
    ]

    subprocess.run(cmd, 
                   check=True, 
                   stdout=subprocess.DEVNULL, 
                   stderr=subprocess.DEVNULL)
    
    