from pathlib import Path
import os
from dotenv import load_dotenv
from google import genai
from concurrent.futures import ThreadPoolExecutor
import functools
import librosa
import numpy as np

load_dotenv()

# Configure Gemini API
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env file")
client = genai.Client(api_key=api_key)


def analyze_beat_and_rhythm(audio_path: Path) -> dict:
    """
    Analyze the beat, tempo, and rhythm characteristics of the instrumental.
    
    Args:
        audio_path: Path to the instrumental audio file
    
    Returns:
        Dict with beat info: {"tempo": BPM, "time_signature": "4/4", "beat_pattern": description}
    """
    try:
        y, sr = librosa.load(str(audio_path), sr=None)
        
        # Estimate tempo
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        
        # Get onset strength for rhythm analysis
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        
        # Estimate energy distribution
        energy = np.abs(librosa.stft(y))
        energy_mean = np.mean(energy)
        
        # Simple time signature detection (assume 4/4 for most songs)
        beat_analysis = {
            "tempo": int(tempo),
            "time_signature": "4/4",
            "beat_pattern": f"~{int(tempo)} BPM in 4/4 time (standard pop/modern music)",
            "energy_level": "high" if energy_mean > 0.5 else "moderate" if energy_mean > 0.2 else "low",
            "rhythm_type": "steady beats" if tempo > 80 else "slow ballad rhythm"
        }
        return beat_analysis
    except Exception as e:
        print(f"Warning: Could not analyze beat: {e}")
        return {
            "tempo": 120,
            "time_signature": "4/4",
            "beat_pattern": "~120 BPM in 4/4 time (standard)",
            "energy_level": "moderate",
            "rhythm_type": "steady beats"
        }


def count_syllables(text: str) -> int:
    """
    Estimate syllable count of text.
    Simple approximation: count vowel groups.
    
    Args:
        text: Text to count syllables in
    
    Returns:
        Estimated syllable count
    """
    text = text.lower()
    vowels = 'aeiouy'
    syllable_count = 0
    previous_was_vowel = False
    
    for char in text:
        is_vowel = char in vowels
        if is_vowel and not previous_was_vowel:
            syllable_count += 1
        previous_was_vowel = is_vowel
    
    # Adjust for common patterns
    if text.endswith('e'):
        syllable_count -= 1
    if text.endswith('le') and len(text) > 2:
        syllable_count += 1
    
    return max(1, syllable_count)


def translate_text(text: str, audio: Path, target_language: str = "Spanish", 
                   beat_info: dict = None, original_word_count: int = None,
                   original_syllable_count: int = None) -> str:
    """
    Translate text to target language using Gemini API, considering beat and rhythm.
    
    Args:
        text: Text to translate
        audio: Path to instrumental audio
        target_language: Target language (default: Spanish)
        beat_info: Dict with beat/rhythm analysis
        original_word_count: Word count of original text
        original_syllable_count: Syllable count of original text
    
    Returns:
        Translated text that matches the rhythm and syllable count
    """
    if beat_info is None:
        beat_info = analyze_beat_and_rhythm(audio)
    
    word_count = len(text.split())
    syllable_count = sum(count_syllables(word) for word in text.split())
    
    if original_word_count is None:
        original_word_count = word_count
    if original_syllable_count is None:
        original_syllable_count = syllable_count
    
    # Build a detailed prompt considering rhythm and syllables
    prompt = f"""You are a professional music translator specializing in songs and lyrics.

SONG INSTRUMENTAL CHARACTERISTICS:
- Tempo: {beat_info.get('tempo', 120)} BPM
- Time Signature: {beat_info.get('time_signature', '4/4')}
- Beat Pattern: {beat_info.get('beat_pattern', 'standard 4/4')}
- Energy Level: {beat_info.get('energy_level', 'moderate')}
- Rhythm Type: {beat_info.get('rhythm_type', 'steady beats')}

ORIGINAL LYRICS METRICS:
- Word Count: {original_word_count} words
- Syllable Count: {original_syllable_count} syllables
- Phrase Length: roughly {original_syllable_count // max(1, original_word_count)} syllables per word

TRANSLATION REQUIREMENTS:
1. CRITICAL: Translate to {target_language} while maintaining as close to {original_word_count} words as possible (±1 word acceptable)
2. CRITICAL: Maintain syllable count close to {original_syllable_count} syllables (±2 syllables is acceptable)
3. Ensure the translation flows naturally with the {beat_info.get('tempo')} BPM rhythm
4. Keep emotional meaning and intent identical to the original
5. Make the lyrics singable and rhythmically fitting
6. Avoid awkward phrasing that breaks the musical flow

ORIGINAL TEXT TO TRANSLATE:
"{text}"

Translate this text following all requirements above. 
ONLY provide the translation without any explanation, analysis, or commentary."""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return (response.text or "").strip()


def translate_segments(segments: list, audio_path: Path, target_language: str = "Spanish") -> list:
    """
    Translate transcription segments to target language in parallel.
    Uses beat and rhythm analysis from instrumental to ensure translations fit musically.
    
    Args:
        segments: List of segment dicts with "start", "end", "text" keys
        audio_path: Path to the audio file (for beat analysis)
        target_language: Target language (default: Spanish)
    
    Returns:
        List of segments with translated text, beat-aware and syllable-matched
    """
    # Analyze beat and rhythm once from instrumental
    beat_info = analyze_beat_and_rhythm(audio_path)
    
    # Function to translate a single segment with beat awareness
    def translate_segment_with_beat(segment: dict) -> tuple:
        original_text = segment["text"]
        original_word_count = len(original_text.split())
        original_syllable_count = sum(count_syllables(word) for word in original_text.split())
        
        # Translate with beat info and syllable/word constraints
        translated_text = translate_text(
            text=original_text,
            audio=audio_path,
            target_language=target_language,
            beat_info=beat_info,
            original_word_count=original_word_count,
            original_syllable_count=original_syllable_count
        )
        
        return translated_text
    
    # Use ThreadPoolExecutor for parallel API calls
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Map segments to translation tasks
        translations = list(executor.map(
            translate_segment_with_beat,
            segments
        ))
    
    # Combine results
    translated_segments = []
    for segment, translated_text in zip(segments, translations):
        translated_segments.append({
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"],  # Original text
            "phonemes": segment.get("phonemes"),  # Preserve phonemes
            "translated": translated_text,  # Translated text
            "language": target_language
        })
    
    return translated_segments
