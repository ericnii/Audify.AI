from __future__ import annotations

from pathlib import Path
from typing import Dict, Union

import numpy as np
import soundfile as sf


def extract_f0_pyworld(
    wav_path: Union[str, Path],
    sr: int = 16000,
    hop_ms: float = 10.0,
    f0_floor: float = 50.0,
    f0_ceil: float = 1100.0,
) -> Dict[str, np.ndarray | int | float]:
    """
    Extract F0 (fundamental frequency) from an audio file using WORLD (pyworld).

    Returns a dict:
      {
        "f0":  np.ndarray float32 shape (T,),  Hz, with 0.0 for unvoiced frames
        "t":   np.ndarray float32 shape (T,),  seconds, same length as f0
        "sr":  int,                              sample rate used for analysis
        "hop": float,                            hop size in seconds (hop_ms/1000)
      }

    Notes:
    - We resample the audio to `sr` so time steps are predictable and fast.
    - We compute frames spaced exactly `hop_ms` milliseconds apart.
    - f0_floor/f0_ceil should bracket the singer’s range:
        male-ish vocals: 50–500 Hz
        female-ish vocals: 80–800 Hz
        pop singing with falsetto can go > 1000 Hz
    """

    import pyworld as pw

    wav_path = Path(wav_path)

    # 1) Load audio
    x, file_sr = sf.read(str(wav_path), always_2d=False)

    # 2) Convert to mono
    if isinstance(x, np.ndarray) and x.ndim == 2:
        x = x.mean(axis=1)

    # 3) Convert to float32 for resampling; WORLD prefers float64 later
    x = x.astype(np.float32, copy=False)

    # 4) Resample if needed (so everything uses the same SR for downstream steps)
    if file_sr != sr:
        import librosa
        x = librosa.resample(x, orig_sr=file_sr, target_sr=sr)

    # WORLD expects float64
    x64 = x.astype(np.float64, copy=False)

    # 5) Run WORLD F0 estimator
    # frame_period is in milliseconds
    frame_period = float(hop_ms)

    # harvest gives an initial f0 estimate + time stamps (t) in seconds
    f0, t = pw.harvest(
        x64,
        fs=sr,
        f0_floor=f0_floor,
        f0_ceil=f0_ceil,
        frame_period=frame_period,
    )

    # 6) Refine f0 using stonemask (reduces gross errors)
    f0 = pw.stonemask(x64, f0, t, sr)

    # 7) Return in the format your pipeline expects
    return {
        "f0": f0.astype(np.float32),
        "t": t.astype(np.float32),
        "sr": int(sr),
        "hop": float(hop_ms) / 1000.0,
    }