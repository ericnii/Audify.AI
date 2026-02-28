from __future__ import annotations
import subprocess
from pathlib import Path

def seperate_stems_demucs(
        input_audio: str | Path,
        out_dir: str | Path,
        model: str = "htdemucs"
) -> dict[str, Path]:
    """
    Runs Demucs to separate vocals + instrument from a raw song file.
    Returns paths to vocals.wav and instrumental.wav (or 'no_vocals.wav').
    """
    input_audio = Path(input_audio).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "python3", "-m", "demucs",
        "-n", model,
        "--two-stems", "vocals",
        "--mp3",
        "--out", str(out_dir),
        str(input_audio)
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Demucs failed (code {proc.returncode}).\n"
            f"CMD: {' '.join(cmd)}\n\n"
            f"STDOUT:\n{proc.stdout}\n\n"
            f"STDERR:\n{proc.stderr}\n"
        )

    model_dir = out_dir / model
    if not model_dir.exists():
        raise FileNotFoundError(f"Expected Demucs output folder missing: {model_dir}")
    
    track_dirs = [p for p in model_dir.iterdir() if p.is_dir()]
    if not track_dirs:
        raise FileNotFoundError(f"No track output found under {model_dir}")
    
    track_dir = max(track_dirs, key=lambda p: p.stat().st_mtime)

    vocals = track_dir / "vocals.mp3"
    instrumental = track_dir / "no_vocals.mp3"

    if not vocals.exists():
        raise FileNotFoundError(f"Missing vocals stem: {vocals}")
    if not instrumental.exists():
        raise FileNotFoundError(f"Missing instrumental stem: {instrumental}")

    return {"vocals": vocals, "instrumental": instrumental}
