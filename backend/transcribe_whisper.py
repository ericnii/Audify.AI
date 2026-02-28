from faster_whisper import WhisperModel
from text_phonemes import text_to_phonemes

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

    segments, _ = model.transcribe(audio_path, word_timestamps=True)

    results = []
    for s in segments:
        # Extract word-level timestamps if available
        if hasattr(s, 'words') and s.words:
            for word in s.words:
                word_text = word.word.strip()
                if not word_text:
                    continue
                phonemes = text_to_phonemes(word_text)
                results.append({
                    "start": round(word.start, 2),
                    "end": round(word.end, 2),
                    "text": word_text,
                    "phonemes": phonemes
                })
        else:
            # Fallback to segment-level if no words
            text = s.text.strip()
            if not text:
                continue
            results.append({
                "start": round(s.start, 2),
                "end": round(s.end, 2),
                "text": text
            })
    return results