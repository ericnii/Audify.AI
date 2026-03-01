"""Demo: synthesize SSML-derived segments to speech locally and play it.

This script uses `segments_to_ssml` to build SSML, then naively strips tags
to plain text and uses pyttsx3 to save the spoken audio to runs/demo_tts.wav.
On macOS it then plays the file with `afplay`.

Run: python backend/demo_tts_play.py
"""
import re
from pathlib import Path
import subprocess

from vertex_tts import segments_to_ssml


def ssml_to_plain_text(ssml: str) -> str:
    # Very small sanitizer: remove SSML tags and unescape a few entities
    text = re.sub(r"<[^>]+>", " ", ssml)
    text = text.replace("&amp;", "&")
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main():
    out_dir = Path("runs")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "demo_tts.wav"

    # Example segments — replace with real translated segments if you have them.
    segments = [
        {"translated": "Hola amigo, esta es una prueba." , "language": "es-ES"},
        {"translated": "Vamos a cantar juntos.", "language": "es-ES"},
    ]

    ssml = segments_to_ssml(segments, global_lang="es-ES", pause_between=0.25)
    plain = ssml_to_plain_text(ssml)

    print("SSML:")
    print(ssml)
    print("\nPlain text sent to pyttsx3:")
    print(plain)

    try:
        import pyttsx3
    except Exception as e:
        print("pyttsx3 is not installed. Install it with: pip install pyttsx3")
        raise

    engine = pyttsx3.init()
    # Save to file and run
    engine.save_to_file(plain, str(out_path))
    engine.runAndWait()

    print(f"Wrote demo audio to {out_path}")

    # Play on macOS
    try:
        subprocess.run(["afplay", str(out_path)], check=True)
    except Exception:
        print("Unable to play audio with afplay. You can play the file at:", out_path)


if __name__ == "__main__":
    main()
