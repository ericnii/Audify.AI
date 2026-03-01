import numpy as np

def estimate_median_f0(f0: np.ndarray) -> float:
    voiced = f0[f0 > 1.0]
    if len(voiced) == 0:
        return 0.0
    return float(np.median(voiced))

def semitone_shift(src_hz: float, tgt_hz: float) -> float:
    if src_hz <= 0 or tgt_hz <= 0:
        return 0.0
    return 12.0 * np.log2(tgt_hz / src_hz)