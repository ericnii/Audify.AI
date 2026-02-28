from __future__ import annotations
import subprocess
import tempfile
from pathlib import Path

def seperate_stems_demucs(
        input_audio: str | Path,
        out_dir: str | Path,
        model: str = "htdemucs",
        start_time: float | str | None = None,
        end_time: float | str | None = None,
) -> dict[str, Path]:
    """
    Runs Demucs to separate vocals + instrument from a raw song file.
    Optional start_time/end_time trim the input with ffmpeg before separation.
    Returns paths to vocals.mp3 and instrumental.mp3 (no_vocals.mp3).
    """
    input_audio = Path(input_audio).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    demucs_input = input_audio

    if (start_time is None) != (end_time is None):
        raise ValueError("Provide both start_time and end_time, or neither.")
    if start_time is not None and end_time is not None:
        start_f = float(start_time)
        end_f = float(end_time)
        if start_f < 0:
            raise ValueError("start_time must be >= 0.")
        if end_f <= start_f:
            raise ValueError("end_time must be greater than start_time.")

        trimmed_dir = Path(tempfile.mkdtemp(prefix="audify_trim_", dir=str(out_dir)))
        trimmed_input = trimmed_dir / f"{input_audio.stem}_trimmed.wav"
        trim_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-to", str(end_time),
            "-i", str(input_audio),
            "-acodec", "pcm_s16le",
            str(trimmed_input),
        ]
        trim_proc = subprocess.run(trim_cmd, capture_output=True, text=True)
        if trim_proc.returncode != 0:
            raise RuntimeError(
                f"ffmpeg trim failed (code {trim_proc.returncode}).\n"
                f"CMD: {' '.join(trim_cmd)}\n\n"
                f"STDOUT:\n{trim_proc.stdout}\n\n"
                f"STDERR:\n{trim_proc.stderr}\n"
            )
        demucs_input = trimmed_input

    cmd_demucs = [
        "python", "-m", "demucs",
        "-n", model,
        "--two-stems", "vocals",
        "--mp3",
        "--out", str(out_dir),
        str(demucs_input)
    ]

    proc = subprocess.run(cmd_demucs, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Demucs failed (code {proc.returncode}).\n"
            f"CMD: {' '.join(cmd_demucs)}\n\n"
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
