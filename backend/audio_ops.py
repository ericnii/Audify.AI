from pathlib import Path
import subprocess


def _get_duration_seconds(wav_path: str | Path) -> float:
    """
    Uses ffprobe to get duration in seconds.
    """
    wav_path = str(wav_path)

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            wav_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    return float(result.stdout.strip())


def time_stretch_to_duration(
    in_wav: str | Path,
    out_wav: str | Path,
    target_dur_s: float,
    min_dur: float = 0.02,
) -> None:
    """
    Time-stretch `in_wav` so its duration becomes exactly `target_dur_s`.

    Uses ffmpeg atempo filter.
    Handles chaining if ratio is outside 0.5–2.0.
    """

    in_wav = Path(in_wav)
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    target_dur_s = max(min_dur, float(target_dur_s))

    current_dur = _get_duration_seconds(in_wav)

    if current_dur <= 0:
        raise RuntimeError(f"Invalid duration for {in_wav}")

    # ratio >1 speeds up (shorter output)
    # ratio <1 slows down (longer output)
    ratio = current_dur / target_dur_s

    # If very close, just copy
    if abs(current_dur - target_dur_s) < 0.005:
        out_wav.write_bytes(in_wav.read_bytes())
        return

    filters = []

    # atempo only supports 0.5–2.0
    while ratio > 2.0:
        filters.append("atempo=2.0")
        ratio /= 2.0

    while ratio < 0.5:
        filters.append("atempo=0.5")
        ratio /= 0.5

    filters.append(f"atempo={ratio}")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", str(in_wav),
            "-filter:a", ",".join(filters),
            "-ar", "16000",      # force consistent SR
            "-ac", "1",          # mono
            str(out_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
def resample_wav(
    in_wav: str | Path,
    out_wav: str | Path,
    sr: int,
    channels: int = 1,
) -> None:
    """
    Resample audio to a target sample rate + channel count.
    Uses ffmpeg so it's fast and reliable.
    """
    in_wav = Path(in_wav)
    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", str(in_wav),
            "-ar", str(sr),
            "-ac", str(channels),
            str(out_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )