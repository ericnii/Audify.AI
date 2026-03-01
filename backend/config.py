from pathlib import Path

# so-vits-svc inference assets (you fill these in after training)
SVC_MODEL_PATH = Path("models/svc/G.pth")
SVC_CONFIG_PATH = Path("models/svc/config.json")
SVC_REPO_DIR = Path("external/so-vits-svc")
SVC_SPK_NAME = "voice1"
SVC_DEVICE = "mps"
SVC_F0_PREDICTOR = "harvest"

# Local TTS model choice (start simple; you can swap later)
# If you go fully local, simplest MVP is to use a CLI TTS engine you can call per segment.
# (You can later upgrade to a neural TTS library.)
TTS_VOICES = {
    "Spanish": {"lang": "es"},
    "French": {"lang": "fr"},
    "German": {"lang": "de"},
}

SAMPLE_RATE = 44100  # keep consistent through pipeline
