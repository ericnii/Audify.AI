"""Demo: synthesize SSML using Google Cloud Text-to-Speech REST API with an API key.

The script reads the API key from one of these environment variables (in order):
  - GOOGLE_TTS_API_KEY
  - GOOGLE_API_KEY
  - TTS_API_KEY

It builds SSML from example segments, calls the project's
`synthesize_texts_to_mp3_api_key`, writes `runs/tts_with_key.mp3`, and tries to
play it with `afplay` on macOS.

Run locally like:
  export GOOGLE_TTS_API_KEY="YOUR_KEY"
  python3 backend/demo_tts_with_key.py
"""
import os
import sys
from pathlib import Path
import subprocess

# Ensure repo root is importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.vertex_tts import segments_to_ssml, synthesize_texts_to_mp3_api_key


def get_api_key() -> str:
    for name in ("GOOGLE_TTS_API_KEY", "GOOGLE_API_KEY", "TTS_API_KEY"):
        v = os.environ.get(name)
        if v:
            print(f"Using API key from env var: {name}")
            return v
    return ""


def main():
    api_key = get_api_key()
    if not api_key:
        print("No API key found. Set GOOGLE_TTS_API_KEY or GOOGLE_API_KEY in your environment.")
        print("Example: export GOOGLE_TTS_API_KEY=\"YOUR_KEY\"")
        sys.exit(1)

    out_dir = Path("runs")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "tts_with_key.mp3"

    segments = [
        {"translated": "Hola amiga, esto es una demostración SSML." , "language": "es-ES"},
        {"translated": "El servicio usará el API key para autenticar la petición.", "language": "es-ES"},
        {"translated": "El servicio usará el API key para autenticar la petición.", "language": "es-ES"},
    ]

    ssml = segments_to_ssml(segments, global_lang="es-ES", pause_between=[2, 0.6])
    print("SSML to synthesize:\n", ssml)

    try:
        synthesize_texts_to_mp3_api_key(api_key, [ssml], out_path, ssml=True, voice={"language_code": "es-ES"})
        print(f"Wrote MP3 to: {out_path}")
        try:
            subprocess.run(["afplay", str(out_path)], check=True)
        except Exception:
            print("Could not play audio with afplay. Play the file manually:", out_path)
    except Exception as e:
        print("Failed to synthesize via API key:")
        print(repr(e))
        print()
        print("Ensure your API key is enabled for the Text-to-Speech API and not restricted, or use a service account for ADC.")


if __name__ == "__main__":
    main()
