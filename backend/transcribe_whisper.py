import os
from pathlib import Path

from faster_whisper import WhisperModel

from text_phonemes import text_to_phonemes


_model = None
_model_device = None
_model_compute_type = None

WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL_NAME", "medium")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")


def _is_cuda_runtime_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    markers = (
        "cublas64_12.dll",
        "cuda",
        "cudnn",
        "cannot be loaded",
        "library cublas",
    )
    return any(m in msg for m in markers)


def _build_model(device: str, compute_type: str):
    return WhisperModel(WHISPER_MODEL_NAME, device=device, compute_type=compute_type)


def _set_model(device: str, compute_type: str) -> WhisperModel:
    global _model, _model_device, _model_compute_type
    _model = _build_model(device, compute_type)
    _model_device = device
    _model_compute_type = compute_type
    return _model


def _get_model():
    global _model
    if _model is not None:
        return _model

    preferred_device = WHISPER_DEVICE
    preferred_compute_type = WHISPER_COMPUTE_TYPE
    try:
        return _set_model(preferred_device, preferred_compute_type)
    except Exception as exc:
        if preferred_device != "cpu" and _is_cuda_runtime_error(exc):
            return _set_model("cpu", "int8")
        raise

def _merge_short_segments(segments, min_duration=0.4):
    merged = []
    buffer = None

    for seg in segments:
        dur = seg["end"] - seg["start"]

        if buffer is None:
            buffer = seg.copy()
            continue

        if dur < min_duration:
            # merge into buffer
            buffer["end"] = seg["end"]
            buffer["text"] += " " + seg["text"]
        else:
            merged.append(buffer)
            buffer = seg.copy()

    if buffer:
        merged.append(buffer)

    return merged

def transcribe_with_whisper(audio_path):
    audio_path = str(Path(audio_path).resolve())
    model = _get_model()
    try:
        segments, _ = model.transcribe(audio_path, word_timestamps=True)
    except Exception as exc:
        if _model_device != "cpu" and _is_cuda_runtime_error(exc):
            model = _set_model("cpu", "int8")
            segments, _ = model.transcribe(audio_path, word_timestamps=True)
        else:
            raise

    results = []
    for s in segments:
        # Prefer phrase-level output so each segment can contain multiple words.
        if hasattr(s, 'words') and s.words:
            text = s.text.strip()
            if not text:
                continue
            start = s.words[0].start if s.words[0].start is not None else s.start
            end = s.words[-1].end if s.words[-1].end is not None else s.end
            phonemes = text_to_phonemes(text)
            results.append({
                "start": round(start, 2),
                "end": round(end, 2),
                "text": text,
                "phonemes": phonemes
            })
        else:
            # Fallback if per-word metadata is unavailable.
            text = s.text.strip()
            if not text:
                continue
            results.append({
                "start": round(s.start, 2),
                "end": round(s.end, 2),
                "text": text
            })
    
    return _merge_short_segments(results)
