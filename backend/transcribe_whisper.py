from faster_whisper import WhisperModel

from pathlib import Path


_model = None

def _get_model():
    global _model
    if _model is None:
        _model = WhisperModel("medium", compute_type="int8")
    return _model

def transcribe_with_whisper(audio_path):
    audio_path = str(Path(audio_path).resolve())
    model = _get_model()

    segments, _ = model.transcribe(audio_path)

    results = []
    for s in segments:
        text = s.text.strip()
        if not text:
            continue
        results.append({
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            "text": text
        })
    return results