from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any, Dict, List

from google import genai
from google.genai import types

def transcribe_with_timestamps_gemini(
        audio_path: str | Path,
        model: str = "gemini-2.0-flash",
        language_hint: str | None = None
) -> List[Dict[str, Any]]:
    """
    Take a vocals only stem and identify 
    start/end timestamps where words are said.
    
    Returns:
      [{ "start": float, "end": float, "text": str }, ...]
    Timestamps are in seconds.
    """
    audio_path = Path(audio_path).resolve()
    audio_bytes = audio_path.read_bytes()

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

    schema = {
        "type": "object",
        "properties": {
            "segments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "start": {"type": "number"},
                        "end": {"type": "number"},
                        "text": {"type": "string"},
                    },
                    "required": ["start", "end", "text"],
                },
            }
        },
        "required": ["segments"],
    }
    lang_line = f"Language hint: {language_hint}." if language_hint else ""
    prompt = f"""
                Transcribe the provided vocals audio into text.
                Return JSON with an array `segments`, each containing:
                - start (seconds)
                - end (seconds)
                - text

                Segment at natural phrase boundaries (roughly 1–4 seconds each).
                {lang_line}

                Only return JSON. No extra commentary.
            """
    resp = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(prompt),
                    types.Part.from_bytes(
                        data=audio_bytes,
                        mime_type="audio/wav",
                    ),
                ],
            )
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.2,
        ),
    )
    data = json.loads(resp.text)
    segments = data["segments"]

    # basic cleanup of response
    cleaned = []
    for s in segments:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        cleaned.append({
            "start": float(s["start"]),
            "end": float(s["end"]),
            "text": text,
        })
    return cleaned
