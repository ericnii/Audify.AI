import numpy as np
from pathlib import Path
import soundfile as sf
import pyworld as pw

def _load_mono_resampled(wav_path: str | Path, target_sr: int) -> tuple[np.ndarray, int]:
    x, sr = sf.read(str(wav_path))
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != target_sr:
        import librosa
        x = librosa.resample(x.astype(np.float32), orig_sr=sr, target_sr=target_sr)
        sr = target_sr
    return x.astype(np.float64), sr

def _resample_f0_to_world_frames(f0_src: np.ndarray, t_src: np.ndarray, t_dst: np.ndarray) -> np.ndarray:
    """
    Resample an F0 curve defined at times t_src onto t_dst.
    Assumes unvoiced regions are f0==0.
    """
    f0_src = np.asarray(f0_src, dtype=np.float64)
    t_src = np.asarray(t_src, dtype=np.float64)
    t_dst = np.asarray(t_dst, dtype=np.float64)

    if len(f0_src) == 0:
        return np.zeros_like(t_dst)

    # Interpolate voiced values; keep unvoiced at 0
    voiced = f0_src > 0
    if voiced.sum() < 2:
        return np.zeros_like(t_dst)

    f0_voiced = np.interp(t_dst, t_src[voiced], f0_src[voiced], left=0.0, right=0.0)

    # A simple voiced mask based on proximity to voiced regions
    # (MVP: if interpolated > 0, treat as voiced)
    f0_out = np.where(f0_voiced > 0, f0_voiced, 0.0)
    return f0_out

def apply_f0_world(
    in_wav: str | Path,
    out_wav: str | Path,
    f0_target: np.ndarray,
    t_target: np.ndarray,
    sr: int = 16000,
    hop_ms: float = 10.0,
    f0_floor: float = 50.0,
    f0_ceil: float = 1100.0,
) -> None:
    """
    Apply an external F0 contour (f0_target at times t_target) onto in_wav using WORLD.

    - in_wav: proxy audio (TTS, time-stretched to the segment)
    - f0_target: F0 extracted from original singing
    - t_target: time stamps for f0_target (seconds)
    - sr/hop_ms must match how you extracted f0_target (recommended: sr=16000, hop=10ms)
    """

    x, _ = _load_mono_resampled(in_wav, sr)
    x = x.astype(np.float64)

    frame_period = hop_ms  # WORLD uses ms
    # WORLD analysis of the proxy audio (this gives you the "what it sounds like" parts)
    f0_proxy, t_proxy = pw.harvest(x, sr, frame_period=frame_period, f0_floor=f0_floor, f0_ceil=f0_ceil)
    sp = pw.cheaptrick(x, f0_proxy, t_proxy, sr)
    ap = pw.d4c(x, f0_proxy, t_proxy, sr)

    # Resample original F0 onto proxy frame times
    f0_new = _resample_f0_to_world_frames(f0_target, t_target, t_proxy)

    # Clamp and clean
    f0_new = np.where((f0_new >= f0_floor) & (f0_new <= f0_ceil), f0_new, 0.0)

    # Optional smoothing to reduce jitter artifacts
    # (light smoothing only on voiced frames)
    voiced = f0_new > 0
    if voiced.sum() > 5:
        kernel = np.array([0.2, 0.6, 0.2], dtype=np.float64)
        f0_sm = f0_new.copy()
        f0_sm[voiced] = np.convolve(f0_new[voiced], kernel, mode="same")
        f0_new = f0_sm

    y = pw.synthesize(f0_new, sp, ap, sr, frame_period=frame_period)

    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_wav), y.astype(np.float32), sr)