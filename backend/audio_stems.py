from __future__ import annotations
import subprocess
import sys
from pathlib import Path


def _parse_time_seconds(value: float | str | None, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number or None. Got: {value!r}") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be >= 0. Got: {parsed}")
    return parsed


def _trim_audio_ffmpeg(
    input_audio: Path,
    out_dir: Path,
    start_time: float | None,
    end_time: float | None,
) -> Path:
    if start_time is None and end_time is None:
        return input_audio

    if end_time is not None and start_time is not None and end_time <= start_time:
        raise ValueError(
            f"end_time must be greater than start_time. Got start_time={start_time}, end_time={end_time}"
        )

    trimmed_input = out_dir / f"{input_audio.stem}.trimmed.wav"
    cmd = ["ffmpeg", "-y"]

    if start_time is not None:
        cmd += ["-ss", f"{start_time:.3f}"]

    cmd += ["-i", str(input_audio)]

    if end_time is not None:
        if start_time is not None:
            cmd += ["-t", f"{(end_time - start_time):.3f}"]
        else:
            cmd += ["-to", f"{end_time:.3f}"]

    # Normalize to PCM WAV so demucs gets a stable input format.
    cmd += ["-vn", "-ac", "2", "-ar", "44100", str(trimmed_input)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg trim failed (code {proc.returncode}).\n"
            f"CMD: {' '.join(cmd)}\n\n"
            f"STDOUT:\n{proc.stdout}\n\n"
            f"STDERR:\n{proc.stderr}\n"
        )

    return trimmed_input


def seperate_stems_demucs(
        input_audio: str | Path,
        out_dir: str | Path,
        # model: str = "htdemucs",
        model: str = "mdx_extra",
        start_time: float | str | None = None,
        end_time: float | str | None = None,
) -> dict[str, Path]:
    """
    Runs Demucs to separate vocals + instrument from the full song file.
    If start_time/end_time are provided, trims input first before separation.
    Returns paths to vocals.mp3 and instrumental.mp3 (no_vocals.mp3).
    """
    input_audio = Path(input_audio).resolve()
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    start_s = _parse_time_seconds(start_time, "start_time")
    end_s = _parse_time_seconds(end_time, "end_time")
    trimmed_input = _trim_audio_ffmpeg(
        input_audio=input_audio,
        out_dir=out_dir,
        start_time=start_s,
        end_time=end_s,
    )

    def _build_cmd(model_name: str) -> list[str]:
        return [
            sys.executable, "-m", "demucs",
            "-n", model_name,
            "--two-stems", "vocals",
            "--mp3",
            "--out", str(out_dir),
            str(trimmed_input),
        ]

    try:
        attempted_models = [model]
        selected_model = model
        cmd_demucs = _build_cmd(model)
        proc = subprocess.run(cmd_demucs, capture_output=True, text=True)

        needs_diffq = "Trying to use DiffQ, but diffq is not installed" in (proc.stderr or "")
        if proc.returncode != 0 and needs_diffq and model.endswith("_q"):
            fallback_model = model[:-2]
            attempted_models.append(fallback_model)
            selected_model = fallback_model
            cmd_demucs = _build_cmd(fallback_model)
            proc = subprocess.run(cmd_demucs, capture_output=True, text=True)

        if proc.returncode != 0:
            raise RuntimeError(
                f"Demucs failed (code {proc.returncode}).\n"
                f"Tried models: {', '.join(attempted_models)}\n"
                f"CMD: {' '.join(cmd_demucs)}\n\n"
                f"STDOUT:\n{proc.stdout}\n\n"
                f"STDERR:\n{proc.stderr}\n"
            )

        model_dir = out_dir / selected_model
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
    finally:
        if trimmed_input != input_audio:
            trimmed_input.unlink(missing_ok=True)
