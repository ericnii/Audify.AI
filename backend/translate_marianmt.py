from pathlib import Path
from typing import Dict, List, Tuple
import re

import torch
from transformers import MarianMTModel, MarianTokenizer

MARIAN_MODELS: Dict[str, str] = {
    "Spanish": "Helsinki-NLP/opus-mt-en-es",
    "French": "Helsinki-NLP/opus-mt-en-fr",
    "German": "Helsinki-NLP/opus-mt-en-de",
    "Italian": "Helsinki-NLP/opus-mt-en-it",
    "Portuguese": "Helsinki-NLP/opus-mt-en-pt",
    "Dutch": "Helsinki-NLP/opus-mt-en-nl",
    "Russian": "Helsinki-NLP/opus-mt-en-ru",
    "Japanese": "Helsinki-NLP/opus-mt-en-jap",
    "Korean": "Helsinki-NLP/opus-mt-en-ko",
    "Chinese": "Helsinki-NLP/opus-mt-en-zh",
}

_MODEL_CACHE: Dict[str, Tuple[MarianTokenizer, MarianMTModel, torch.device]] = {}


def _get_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")

def _get_model(target_language: str) -> Tuple[MarianTokenizer, MarianMTModel, torch.device]:
    if target_language not in MARIAN_MODELS:
        raise ValueError(
            f"Unsupported target_language={target_language!r}. "
            f"Supported: {sorted(MARIAN_MODELS.keys())}"
        )

    model_name = MARIAN_MODELS[target_language]
    if model_name in _MODEL_CACHE:
        return _MODEL_CACHE[model_name]

    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)

    device = _get_device()
    model.to(device)
    model.eval()

    _MODEL_CACHE[model_name] = (tokenizer, model, device)
    return tokenizer, model, device


def translate_text(text: str, audio: Path, target_language: str = "Spanish") -> str:
    # Keeping signature the same for compatibility; 'audio' is unused by MarianMT.
    tokenizer, model, device = _get_model(target_language)

    text = (text or "").strip()
    if not text:
        return ""

    batch = tokenizer([text], return_tensors="pt", padding=True, truncation=True).to(device)
    with torch.inference_mode():
        out = model.generate(**batch, num_beams=4, max_new_tokens=256)

    return tokenizer.batch_decode(out, skip_special_tokens=True)[0].strip()


def translate_segments(segments: list, audio_path: Path, target_language: str = "Spanish") -> list:
    tokenizer, model, device = _get_model(target_language)

    texts: List[str] = [(seg.get("text") or "").strip() for seg in segments]

    # You can tune this. On CPU: 8–16. On GPU: 32–128.
    BATCH_SIZE = 16 if device.type == "mps" else 12

    translations: List[str] = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch_texts = texts[i:i + BATCH_SIZE]

        # Handle empties without sending them through the model
        empty_mask = [not t for t in batch_texts]
        to_translate = [t for t in batch_texts if t]

        if not to_translate:
            translations.extend([""] * len(batch_texts))
            continue

        batch = tokenizer(to_translate, return_tensors="pt", padding=True, truncation=True).to(device)
        with torch.inference_mode():
            out = model.generate(**batch, num_beams=4, max_new_tokens=256)
        decoded = [s.strip() for s in tokenizer.batch_decode(out, skip_special_tokens=True)]

        # Reinsert empties in correct spots
        it = iter(decoded)
        for is_empty in empty_mask:
            translations.append("" if is_empty else next(it))

    # Rebuild output in the exact same schema you had
    translated_segments = []
    for seg, tr in zip(segments, translations):
        translated_segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"],
            "phonemes": seg.get("phonemes"),
            "translated": tr,
            "language": target_language,
        })

    return translated_segments