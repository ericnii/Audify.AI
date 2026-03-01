from __future__ import annotations
from pathlib import Path
import shutil
import subprocess
import uuid

from config import (
    SVC_CONFIG_PATH,
    SVC_DEVICE,
    SVC_F0_PREDICTOR,
    SVC_MODEL_PATH,
    SVC_REPO_DIR,
    SVC_SPK_NAME,
)


def run_sovits_svc_41(
    in_wav: Path,
    out_wav: Path,
    model_pth: Path = SVC_MODEL_PATH,
    config_json: Path = SVC_CONFIG_PATH,
    svc_repo_dir: Path = SVC_REPO_DIR,
    spk_name: str = SVC_SPK_NAME,
    device: str = SVC_DEVICE,          # try "mps" if supported by your torch build; otherwise cpu
    f0_predictor: str = SVC_F0_PREDICTOR # options include: crepe, pm, dio, harvest, rmvpe, fcpe
) -> None:
    """
    Runs so-vits-svc 4.1 inference_main.py (the CLI you pasted).
    It requires the wav to be in svc_repo_dir/raw and referenced by filename via -n.
    """
    svc_repo_dir = Path(svc_repo_dir)
    raw_dir = svc_repo_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    # Unique name to avoid collisions across jobs
    tmp_name = f"job_{uuid.uuid4().hex}.wav"
    tmp_in_repo = raw_dir / tmp_name

    shutil.copyfile(in_wav, tmp_in_repo)

    py = svc_repo_dir / ".venv" / "bin" / "python"

    cmd = [
        str(py),
        "inference_main.py",
        "-m", str(model_pth),
        "-c", str(config_json),
        "-n", tmp_name,             # filename in raw/
        "-s", spk_name,             # target speaker name in the model
        "-d", device,               # "cpu" or "mps" if supported
        "-f0p", f0_predictor,        # for singing: harvest/dio/pm are common; rmvpe if available
        # IMPORTANT: do NOT add "-a" for singing
    ]

    subprocess.run(cmd, cwd=str(svc_repo_dir), check=True)

    # Find output. Many forks write to "results/" or "output/"
    # We’ll search for the newest .wav produced after inference.
    candidates = []
    for folder in ["results", "result", "output", "outputs"]:
        p = svc_repo_dir / folder
        if p.exists():
            candidates.extend(p.glob("*.wav"))

    if not candidates:
        # fallback: search repo for recent wavs (costly but ok for MVP)
        candidates = list(svc_repo_dir.rglob("*.wav"))

    # pick most recently modified
    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    shutil.copyfile(newest, out_wav)

    # cleanup input
    try:
        tmp_in_repo.unlink()
    except OSError:
        pass


def run_voice_conversion(
    in_wav: Path,
    out_wav: Path,
) -> None:
    run_sovits_svc_41(in_wav, out_wav)
