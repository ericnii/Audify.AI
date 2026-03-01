from faster_whisper import WhisperModel
from text_phonemes import text_to_phonemes

from pathlib import Path


_model = None

def _get_model():
    global _model
    if _model is None:
        _model = WhisperModel("medium", compute_type="int8")
    return _model

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

    segments, _ = model.transcribe(audio_path, word_timestamps=True)

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
