"""Small helper to run DiffSinger repo inference from this project.

This wrapper prepares a temporary input folder (lyrics + midi) and either prints
the command to run the repo's inference script or executes it.

It intentionally performs minimal assumptions about the target repo. Adapt the
argument names if your chosen DiffSinger fork expects different CLI flags.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
import shutil
from typing import Optional

from backend import text_phonemes


def prepare_inputs(work_dir: Path, lyrics: str, midi_path: Optional[Path]) -> tuple[Path, Optional[Path]]:
    """Write lyrics to lyrics.txt and copy midi if provided.

    Returns (lyrics_file, midi_file_or_none)
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    lyrics_file = work_dir / "lyrics.txt"
    with lyrics_file.open("w", encoding="utf8") as fh:
        fh.write(lyrics)

    midi_out = None
    if midi_path:
        midi_out = work_dir / midi_path.name
        shutil.copy2(midi_path, midi_out)

    return lyrics_file, midi_out


def build_inference_command(repo_path: Path, checkpoint: Path, lyrics_file: Path, midi_file: Optional[Path], out_wav: Path) -> list[str]:
    """Construct a reasonable command for a DiffSinger-style repo.

    This assumes the repo provides an `inference.py` script accepting --checkpoint,
    --lyrics_file, --midi and --output. Adjust flags to match your chosen fork.
    """
    inf = repo_path / "inference.py"
    if not inf.exists():
        raise FileNotFoundError(f"Inference script not found at expected path: {inf}")

    cmd = [sys.executable, str(inf), "--checkpoint", str(checkpoint), "--lyrics_file", str(lyrics_file), "--output", str(out_wav)]
    if midi_file:
        cmd += ["--midi", str(midi_file)]
    return cmd


def run_diffsinger_inference(repo_path: Path, checkpoint: Path, lyrics: str, midi_path: Optional[Path], out_wav: Path, execute: bool = False) -> Path:
    """Prepare inputs and run (or print) the DiffSinger inference command.

    If execute=False the function prints the command and returns the expected output path.
    If execute=True the function will run the command and return the produced WAV path if successful.
    """
    repo_path = Path(repo_path)
    checkpoint = Path(checkpoint)
    out_wav = Path(out_wav)

    if not repo_path.exists():
        raise FileNotFoundError(f"DiffSinger repo path not found: {repo_path}")
    if not checkpoint.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint}")

    uid = uuid.uuid4().hex[:8]
    tmp_dir = repo_path / "inputs" / f"audify_{uid}"
    lyrics_file, midi_file = prepare_inputs(tmp_dir, lyrics, Path(midi_path) if midi_path else None)

    cmd = build_inference_command(repo_path, checkpoint, lyrics_file, midi_file, out_wav)

    print("Prepared inputs:", tmp_dir)
    print("Inference command:")
    print(" ".join(cmd))

    if not execute:
        print("Dry-run (execute=False). To run inference set execute=True.")
        return out_wav

    # Execute and let stdout/stderr stream to console
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"DiffSinger inference failed (rc={proc.returncode})")

    if not out_wav.exists():
        raise FileNotFoundError(f"Inference finished but output not found at {out_wav}")

    return out_wav


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Run DiffSinger inference from this repo (minimal wrapper)")
    p.add_argument("--repo", required=True, type=Path, help="Path to local DiffSinger repo clone")
    p.add_argument("--checkpoint", required=True, type=Path, help="Path to model checkpoint file")
    p.add_argument("--lyrics", required=True, help="Lyrics text to synthesize")
    p.add_argument("--midi", type=Path, help="Optional MIDI file for melody")
    p.add_argument("--out", required=True, type=Path, help="Output WAV path")
    p.add_argument("--execute", action="store_true", help="If set, actually run the repo inference script")

    args = p.parse_args()
    try:
        run_diffsinger_inference(args.repo, args.checkpoint, args.lyrics, args.midi, args.out, execute=args.execute)
    except Exception as e:
        print("Error:", e)
        raise
