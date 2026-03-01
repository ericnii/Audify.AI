from pathlib import Path

# so-vits-svc inference assets (you fill these in after training)
SVC_REPO_DIR = Path("external/so-vits-svc")
SVC_MODEL_DIR = SVC_REPO_DIR / "logs" / "44k_voice1"
SVC_MODEL_PATH = SVC_MODEL_DIR / "G_latest.pth"  # Fallback logic resolves latest G_*.pth automatically.
SVC_CONFIG_PATH = SVC_MODEL_DIR / "config.json"
SVC_SPK_NAME = "voice1"
SVC_DEVICE = "cuda"
SVC_F0_PREDICTOR = "harvest"
SVC_REFERENCE_VOICES_DIR = SVC_REPO_DIR / "database_raw"

# Local TTS model choice (start simple; you can swap later)
# If you go fully local, simplest MVP is to use a CLI TTS engine you can call per segment.
# (You can later upgrade to a neural TTS library.)
TTS_VOICES = {
    "Spanish": {"lang": "es"},
    "French": {"lang": "fr"},
    "German": {"lang": "de"},
}

SAMPLE_RATE = 44100  # keep consistent through pipeline
