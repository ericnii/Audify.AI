import subprocess
from pathlib import Path

def mix_vocals_instrumental(vocals_wav: Path, inst_wav: Path, out_wav: Path) -> None:
    out_wav.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(inst_wav),
        "-i", str(vocals_wav),
        # Simple mix. You can add loudnorm/sidechain later.
        "-filter_complex", "amix=inputs=2:duration=longest:dropout_transition=2",
        str(out_wav),
    ]
    subprocess.run(cmd, check=True)