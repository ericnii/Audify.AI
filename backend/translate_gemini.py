import google.generativeai as genai
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini API
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEY not found in .env file")

genai.configure(api_key=api_key)


def translate_text(text: str, audio: Path, target_language: str = "Spanish") -> str:
    """
    Translate text to target language using Gemini API.
    
    Args:
        text: Text to translate
        target_language: Target language (default: Spanish)
    
    Returns:
        Translated text
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    prompt = f""" You are a helpful assistant that translates lyrics of songs to different languages.
    Here is the instrumentals of the song: {audio}. Make sure the translation fits the rhythm and mood of the music.
    Translate the following text to {target_language}. 
Only provide the translation, no explanations.

Text to translate:
{text}"""
    
    response = model.generate_content(prompt)
    return response.text.strip()


def translate_segments(segments: list, audio_path: Path, target_language: str = "Spanish") -> list:
    """
    Translate transcription segments to target language.
    
    Args:
        segments: List of segment dicts with "start", "end", "text" keys
        audio_path: Path to the audio file (for context)
        target_language: Target language (default: Spanish)
    
    Returns:
        List of segments with translated text
    """
    translated_segments = []
    
    for segment in segments:
        translated_text = translate_text(segment["text"], audio_path, target_language)
        translated_segments.append({
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"],  # Original text
            "translated": translated_text,  # Translated text
            "language": target_language
        })
    
    return translated_segments
