"""Demo: synthesize SSML using Google Cloud Text-to-Speech (Vertex) and play it.

This script calls the project's `synthesize_texts_to_mp3` helper with `ssml=True`.
It requires Google Cloud credentials available via the environment (ADC) or
`GOOGLE_APPLICATION_CREDENTIALS` pointing at a service account JSON.

Run: python3 backend/demo_vertex_ssml_play.py
"""
import os
import sys
from pathlib import Path
import subprocess

# Make repo root importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.vertex_tts import segments_to_ssml, synthesize_texts_to_mp3


def main():
    out_dir = Path("runs")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "vertex_demo_tts.mp3"

    segments = [
        {"translated": "Hola amigo, esta es una prueba usando SSML.", "language": "es-ES"},
        {"translated": "Esto debería respetar las pausas y la voz.", "language": "es-ES"},
    ]

    ssml = segments_to_ssml(segments, global_lang="es-ES", pause_between=0.25)
    print("Using SSML:\n", ssml)

    try:
        synthesize_texts_to_mp3([ssml], out_path, ssml=True, voice={"language_code": "es-ES"})
        print(f"Wrote TTS MP3 to {out_path}")
        # Try to play (macOS)
        try:
            subprocess.run(["afplay", str(out_path)], check=True)
        except Exception:
            print("Could not play audio with afplay. Play the file manually:", out_path)
    except Exception as e:
        print("Failed to synthesize SSML via Google Cloud Text-to-Speech:")
        print(repr(e))
        print()
        print("If this is an authentication error, ensure you have set up Application Default Credentials or set the environment variable:")
        print("  export GOOGLE_APPLICATION_CREDENTIALS=\"/path/to/service-account.json\"")
        print("Create a service account in Google Cloud, grant it the Text-to-Speech role, and download the JSON key.")


if __name__ == "__main__":
    main()
