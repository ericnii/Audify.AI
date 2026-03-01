from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from config import (
    SVC_CONFIG_PATH,
    SVC_DEVICE,
    SVC_F0_PREDICTOR,
    SVC_MODEL_DIR,
    SVC_MODEL_PATH,
    SVC_REPO_DIR,
    SVC_SPK_NAME,
)


def _resolve_svc_python(svc_repo_dir: Path) -> Path:
    candidates = [
        svc_repo_dir / ".venv310" / "Scripts" / "python.exe",
        svc_repo_dir / ".venv" / "Scripts" / "python.exe",
        svc_repo_dir / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Unable to locate Python executable for so-vits-svc.")


def _resolve_model_path(model_pth: Path, model_dir: Path) -> Path:
    if model_pth.exists() and model_pth.is_file():
        return model_pth.resolve()

    checkpoints = list(model_dir.glob("G_*.pth"))
    if not checkpoints:
        raise FileNotFoundError(
            f"No so-vits checkpoint found. Expected {model_pth} or any G_*.pth in {model_dir}."
        )

    def _score(p: Path) -> tuple[int, float]:
        match = re.search(r"G_(\d+)\.pth$", p.name)
        step = int(match.group(1)) if match else -1
        return (step, p.stat().st_mtime)

    return max(checkpoints, key=_score).resolve()


def get_available_speakers(config_json: Path = SVC_CONFIG_PATH) -> list[str]:
    if not config_json.exists():
        return [SVC_SPK_NAME]
    try:
        data = json.loads(config_json.read_text(encoding="utf-8"))
    except Exception:
        return [SVC_SPK_NAME]

    spk = data.get("spk")
    if isinstance(spk, dict) and spk:
        return list(spk.keys())
    return [SVC_SPK_NAME]


def run_sovits_svc_41(
    in_wav: Path,
    out_wav: Path,
    model_dir: Path = SVC_MODEL_DIR,
    model_pth: Path = SVC_MODEL_PATH,
    config_json: Path = SVC_CONFIG_PATH,
    svc_repo_dir: Path = SVC_REPO_DIR,
    spk_name: str = SVC_SPK_NAME,
    device: str = SVC_DEVICE,
    f0_predictor: str = SVC_F0_PREDICTOR,
) -> str:
    """
    Runs so-vits-svc 4.1 inference_main.py.
    Input wav is copied into svc_repo_dir/raw and referenced by filename via -n.
    """
    svc_repo_dir = Path(svc_repo_dir).resolve()
    model_dir = Path(model_dir).resolve()
    config_json = Path(config_json).resolve()
    resolved_model = _resolve_model_path(Path(model_pth).resolve(), model_dir=model_dir)

    speakers = get_available_speakers(config_json=config_json)
    if spk_name not in speakers:
        spk_name = speakers[0]

    raw_dir = svc_repo_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    results_dir = svc_repo_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    tmp_name = f"job_{uuid.uuid4().hex}.wav"
    tmp_in_repo = raw_dir / tmp_name
    shutil.copyfile(in_wav, tmp_in_repo)

    py = _resolve_svc_python(svc_repo_dir)
    started_at = time.time()
    tmp_stem = Path(tmp_name).stem

    cmd = [
        str(py),
        "inference_main.py",
        "-m",
        str(resolved_model),
        "-c",
        str(config_json),
        "-n",
        tmp_name,
        "-s",
        spk_name,
        "-d",
        device,
        "-f0p",
        f0_predictor,
        "-wf",
        "wav",
    ]

    try:
        subprocess.run(cmd, cwd=str(svc_repo_dir), check=True)

        candidates: list[Path] = []
        for folder in ["results", "result", "output", "outputs"]:
            folder_path = svc_repo_dir / folder
            if not folder_path.exists():
                continue
            for audio in folder_path.glob("*"):
                if audio.suffix.lower() not in {".wav", ".flac"}:
                    continue
                if tmp_stem not in audio.stem:
                    continue
                if audio.stat().st_mtime >= (started_at - 1.0):
                    candidates.append(audio)

        if not candidates:
            raise FileNotFoundError(
                "so-vits inference completed but no output file was found for this request."
            )

        newest = max(candidates, key=lambda p: p.stat().st_mtime)
        if newest.suffix.lower() == ".wav":
            shutil.copyfile(newest, out_wav)
        else:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(newest), str(out_wav)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    finally:
        tmp_in_repo.unlink(missing_ok=True)

    return spk_name


def run_voice_conversion(
    in_wav: Path,
    out_wav: Path,
    spk_name: str | None = None,
) -> str:
    return run_sovits_svc_41(in_wav, out_wav, spk_name=spk_name or SVC_SPK_NAME)

