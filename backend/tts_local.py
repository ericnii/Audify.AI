from pathlib import Path
from TTS.api import TTS
import torch
import subprocess

# Lazy global model (loads once)
_TTS_MODEL = None

# Map your human-readable language to ISO
LANG_CODE_MAP = {
    "Spanish": "es",
    "French": "fr",
    "German": "de",
}


def _get_device():
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _get_tts_model():
    global _TTS_MODEL
    if _TTS_MODEL is None:
        device = _get_device()

        # XTTS v2 multilingual model
        _TTS_MODEL = TTS(
            model_name="tts_models/multilingual/multi-dataset/xtts_v2",
            progress_bar=False,
        ).to(device)

    return _TTS_MODEL


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

    tts = _get_tts_model()

    lang_code = LANG_CODE_MAP.get(language)
    if not lang_code:
        raise ValueError(f"Unsupported language: {language}")

    # XTTS needs a speaker reference OR a default
    # For proxy we can use default speaker embeddings
    # So no speaker_wav provided here

    tts.tts_to_file(
        text=text,
        file_path=str(out_wav),
        language=lang_code,
    )

    subprocess.run(
    [
        "ffmpeg",
        "-y",
        "-i", str(out_wav),
        "-ar", "16000",
        "-ac", "1",
        str(out_wav),
    ],
    check=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    )