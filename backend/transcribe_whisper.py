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


def transcribe_with_segments_and_words(audio_path):
    """
    Transcribe audio and return both segments and word-level timing with breaks.
    
    Returns a dict with:
    - segments: Default Whisper segments (for translation)
    - words: List of individual words with start/end times and breaks between them
    
    Example:
    {
        "segments": [
            {"start": 0.0, "end": 5.0, "text": "Hello world", "id": 0},
            {"start": 5.5, "end": 10.0, "text": "How are you", "id": 1}
        ],
        "words": [
            {"start": 0.0, "end": 0.5, "text": "Hello", "break_after": 0.3},
            {"start": 0.8, "end": 1.2, "text": "world", "break_after": 4.3},
            {"start": 5.5, "end": 6.0, "text": "How", "break_after": 0.2},
            ...
        ]
    }
    """
    audio_path = str(Path(audio_path).resolve())
    model = _get_model()

    segments_list, _ = model.transcribe(audio_path, word_timestamps=True)

    # Convert to lists to allow multiple iterations
    segments_list = list(segments_list)
    
    segments = []
    words = []
    all_words = []  # Collect all words for break calculation
    
    # First pass: collect segments and all words
    segment_id = 0
    for segment in segments_list:
        segment_text = segment.text.strip()
        if not segment_text:
            continue
        
        # Add segment for translation (default Whisper segments)
        segments.append({
            "id": segment_id,
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "text": segment_text,
            "translated": ""  # To be filled by translator
        })
        
        # Extract word-level timestamps
        if hasattr(segment, 'words') and segment.words:
            for word in segment.words:
                word_text = word.word.strip()
                if not word_text:
                    continue
                all_words.append({
                    "text": word_text,
                    "start": word.start,
                    "end": word.end,
                    "segment_id": segment_id
                })
        else:
            # Fallback: treat entire segment as one word
            all_words.append({
                "text": segment_text,
                "start": segment.start,
                "end": segment.end,
                "segment_id": segment_id
            })
        
        segment_id += 1
    
    # Second pass: calculate breaks based on word timing
    for i, word in enumerate(all_words):
        # Calculate break (silence) after this word
        if i < len(all_words) - 1:
            next_word = all_words[i + 1]
            break_after = next_word['start'] - word['end']
        else:
            # Last word - no break after
            break_after = 0
        
        words.append({
            "text": word["text"],
            "start": round(word["start"], 2),
            "end": round(word["end"], 2),
            "duration": round(word["end"] - word["start"], 3),
            "break_after": round(break_after, 3),  # Silence after this word
            "segment_id": word["segment_id"]
        })
    
    return {
        "segments": segments,
        "words": words
    }