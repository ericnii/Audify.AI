from __future__ import annotations
import argparse
import shutil
import subprocess
from pathlib import Path
import sys


def check_repo_path(repo_path: Path) -> None:
    if not repo_path.exists():
        raise FileNotFoundError(f"DiffSinger repo path not found: {repo_path}")
    if not (repo_path / "README.md").exists():
        print(f"Warning: {repo_path} exists but README.md not found — repo may be different.")


def print_commands_for_finetune(repo_path: Path, data_dir: Path, out_dir: Path) -> None:
    print("\n=== DiffSinger fine-tuning (high level) ===\n")
    print("1) Create a Python env and install requirements inside the DiffSinger repo:\n")
    print(f"   python -m venv .venv && source .venv/bin/activate && pip install -r {repo_path / 'requirements.txt'}\n")

    print("2) Prepare your English singing dataset in DiffSinger format (see repo docs). Example (NUS/Open dataset):\n")
    print(f"   # put wavs and metadata under {data_dir}\n")

    print("3) Run finetuning from a provided checkpoint (example command — adapt config/checkpoint names):\n")
    print(f"   cd {repo_path} && python train.py --config configs/your_config.yaml --data_dir {data_dir} --output_dir {out_dir} --resume checkpoints/your_checkpoint.pth\n")

    print("4) After training, run inference using the repo's inference script, providing lyrics and MIDI/F0 where required. Example:\n")
    print(f"   cd {repo_path} && python inference.py --checkpoint {out_dir}/best.pth --lyrics 'Hello world' --output {out_dir}/sample.wav\n")


def print_commands_for_diffspeech(repo_path: Path, checkpoint: Path, text: str, out_wav: Path) -> None:
    print("\n=== DiffSpeech (TTS) quick inference using LJSpeech checkpoint ===\n")
    print("1) Create a Python env and install requirements (TTS/DiffSpeech may use different reqs):\n")
    print(f"   python -m venv .venv && source .venv/bin/activate && pip install -r {repo_path / 'requirements.txt'}\n")

    print("2) Run the TTS inference command (example — adapt to repo script names):\n")
    print(f"   cd {repo_path} && python inference_tts.py --checkpoint {checkpoint} --text \"{text}\" --output {out_wav}\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DiffSinger helper: prints commands for finetune/inference")
    sub = parser.add_subparsers(dest="cmd")

    p1 = sub.add_parser("finetune", help="Print fine-tuning commands for DiffSinger on English data")
    p1.add_argument("--repo", required=True, type=Path, help="Path to DiffSinger repo (local clone)")
    p1.add_argument("--data", required=True, type=Path, help="Path to prepared dataset directory")
    p1.add_argument("--out", required=True, type=Path, help="Output dir for checkpoints/logs")

    p2 = sub.add_parser("diffee", help="Print DiffSpeech/DiffSpeech-like TTS commands (LJSpeech) ")
    p2.add_argument("--repo", required=True, type=Path, help="Path to repo with DiffSpeech or DiffSinger TTS support")
    p2.add_argument("--checkpoint", required=True, type=Path, help="Path to TTS checkpoint (e.g., LJSpeech) ")
    p2.add_argument("--text", required=True, help="Text to synthesize (short)")
    p2.add_argument("--out", required=True, type=Path, help="Output wav path")

    parser.add_argument("--execute", action="store_true", help="(dangerous) actually run the example inference command")

    args = parser.parse_args(argv)
    if args.cmd == "finetune":
        try:
            check_repo_path(args.repo)
        except FileNotFoundError as e:
            print(e)
            return 2
        print_commands_for_finetune(args.repo, args.data, args.out)
        return 0

    if args.cmd == "diffee":
        try:
            check_repo_path(args.repo)
        except FileNotFoundError as e:
            print(e)
            return 2
        print_commands_for_diffspeech(args.repo, args.checkpoint, args.text, args.out)
        if args.execute:
            # Safety: do not run training here; only attempt a single-word TTS if an inference script is present
            inf_script = args.repo / "inference_tts.py"
            if not inf_script.exists():
                print(f"Inference script not found: {inf_script}. Aborting execution.")
                return 3
            cmd = [sys.executable, str(inf_script), "--checkpoint", str(args.checkpoint), "--text", args.text, "--output", str(args.out)]
            print("Running:", " ".join(cmd))
            subprocess.run(cmd)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
