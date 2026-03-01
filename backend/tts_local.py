import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import torch
from TTS.api import TTS

# Lazy global model (loads once)
_TTS_MODEL = None
_TTS_DEVICE = None
_DEFAULT_SPEAKER_WAV = None
_CACHE_VERSION = "v1"
_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

# Coqui XTTS may ask for CPML confirmation interactively; backend runs non-interactively.
os.environ.setdefault("COQUI_TOS_AGREED", "1")

# Map your human-readable language to ISO
LANG_CODE_MAP = {
    "Spanish": "es",
    "French": "fr",
    "German": "de",
}


def _cache_dir() -> Path:
    return Path(__file__).resolve().parent / ".cache" / "tts"


def _cache_key(text: str, lang_code: str) -> str:
    speaker_wav = _get_default_speaker_wav()
    speaker_sig = speaker_wav.resolve().as_posix()
    payload = f"{_CACHE_VERSION}|{_MODEL_NAME}|{lang_code}|{speaker_sig}|{text}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _cache_path(text: str, lang_code: str) -> Path:
    return _cache_dir() / f"{_cache_key(text, lang_code)}.wav"


def _get_device():
    forced = os.getenv("TTS_DEVICE", "auto").strip().lower()
    if forced and forced != "auto":
        if forced == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("TTS_DEVICE=cuda requested but torch.cuda.is_available() is False.")
            return "cuda"
        if forced == "mps":
            if not torch.backends.mps.is_available():
                raise RuntimeError("TTS_DEVICE=mps requested but torch.backends.mps.is_available() is False.")
            return "mps"
        if forced == "cpu":
            return "cpu"
        raise ValueError("TTS_DEVICE must be one of: auto, cuda, mps, cpu.")

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _get_tts_model():
    global _TTS_MODEL, _TTS_DEVICE
    if _TTS_MODEL is None:
        device = _get_device()

        try:
            # XTTS v2 multilingual model
            _TTS_MODEL = TTS(model_name=_MODEL_NAME, progress_bar=False).to(device)
            _TTS_DEVICE = device
        except Exception:
            if device != "cpu":
                _TTS_MODEL = TTS(model_name=_MODEL_NAME, progress_bar=False).to("cpu")
                _TTS_DEVICE = "cpu"
            else:
                raise

    return _TTS_MODEL


def _candidate_speaker_wavs() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[1]
    candidates = []

    env_speaker = os.getenv("TTS_SPEAKER_WAV", "").strip()
    if env_speaker:
        candidates.append(Path(env_speaker))

    candidates.extend(
        [
            Path(__file__).resolve().parent / "speaker_reference.wav",
            repo_root / "external" / "so-vits-svc" / "database_raw" / "voice1" / "00000.wav",
        ]
    )

    base_dirs = [
        repo_root / "external" / "so-vits-svc" / "database_raw" / "voice1",
        repo_root / "external" / "so-vits-svc" / "dataset_raw" / "voice1",
    ]
    for base in base_dirs:
        if base.exists():
            candidates.extend(sorted(base.glob("*.wav")))
            candidates.extend(sorted(base.glob("*.flac")))
            candidates.extend(sorted(base.glob("*.mp3")))

    # De-duplicate while preserving order.
    deduped = []
    seen = set()
    for p in candidates:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped


def _get_default_speaker_wav() -> Path:
    global _DEFAULT_SPEAKER_WAV
    if _DEFAULT_SPEAKER_WAV is not None:
        return _DEFAULT_SPEAKER_WAV

    for path in _candidate_speaker_wavs():
        candidate = path.expanduser()
        if candidate.exists() and candidate.is_file():
            _DEFAULT_SPEAKER_WAV = candidate.resolve()
            return _DEFAULT_SPEAKER_WAV

    raise FileNotFoundError(
        "XTTS requires a speaker reference WAV, but none was found. "
        "Set TTS_SPEAKER_WAV to a valid audio file path."
    )


def warmup_tts_model() -> str:
    """Load XTTS once during app startup to avoid first-request latency spikes."""
    _get_tts_model()
    _get_default_speaker_wav()
    return _TTS_DEVICE or "cpu"


def tts_to_wav(text: str, out_wav: Path, language: str) -> None:
    """
    Generate speech for `text` in given language.
    language should be "Spanish" | "French" | "German"
    """

    text = text.strip()
    if not text:
        raise ValueError("Empty text passed to tts_to_wav")

    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    lang_code = LANG_CODE_MAP.get(language)
    if not lang_code:
        raise ValueError(f"Unsupported language: {language}")

    cache_file = _cache_path(text, lang_code)
    if cache_file.exists():
        shutil.copy2(cache_file, out_wav)
        return

    tts = _get_tts_model()
    speaker_wav = _get_default_speaker_wav()

    # XTTS v2 is multi-speaker; always provide a reference voice.
    raw_out = out_wav.with_suffix(".raw.wav")
    tts.tts_to_file(
        text=text,
        file_path=str(raw_out),
        language=lang_code,
        speaker_wav=str(speaker_wav),
    )

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(raw_out),
            "-ar",
            "16000",
            "-ac",
            "1",
            str(out_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    raw_out.unlink(missing_ok=True)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_wav, cache_file)
