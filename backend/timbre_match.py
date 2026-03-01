from __future__ import annotations

import threading
from pathlib import Path
from typing import Sequence

import librosa
import numpy as np

from config import SVC_REFERENCE_VOICES_DIR, SVC_SPK_NAME

_CACHE_LOCK = threading.Lock()
_PROFILE_CACHE: dict[tuple[str, tuple[str, ...]], dict[str, np.ndarray]] = {}


def _compute_embedding(audio_path: Path) -> np.ndarray | None:
    y, sr = librosa.load(audio_path, sr=16000, mono=True)
    if y.size == 0:
        return None

    max_samples = 16000 * 12
    if y.size > max_samples:
        start = (y.size - max_samples) // 2
        y = y[start : start + max_samples]

    mfcc = librosa.feature.mfcc(y=y, sr=16000, n_mfcc=24)
    delta = librosa.feature.delta(mfcc)
    feat = np.vstack([mfcc, delta]).astype(np.float32)
    emb = np.concatenate([feat.mean(axis=1), feat.std(axis=1)]).astype(np.float32)
    norm = np.linalg.norm(emb)
    if norm <= 0:
        return None
    return emb / norm


def _build_speaker_profiles(
    reference_root: Path,
    speakers: Sequence[str],
    max_files_per_speaker: int = 48,
) -> dict[str, np.ndarray]:
    profiles: dict[str, np.ndarray] = {}
    for spk in speakers:
        spk_dir = reference_root / spk
        if not spk_dir.exists():
            continue

        embeddings: list[np.ndarray] = []
        for wav in sorted(spk_dir.glob("*.wav"))[:max_files_per_speaker]:
            emb = _compute_embedding(wav)
            if emb is not None:
                embeddings.append(emb)

        if not embeddings:
            continue

        profile = np.mean(np.vstack(embeddings), axis=0)
        norm = np.linalg.norm(profile)
        if norm <= 0:
            continue
        profiles[spk] = profile / norm

    return profiles


def select_closest_speaker(
    query_wav: Path,
    candidate_speakers: Sequence[str],
    reference_root: Path = SVC_REFERENCE_VOICES_DIR,
) -> str:
    speakers = tuple(sorted(set(candidate_speakers)))
    if not speakers:
        return SVC_SPK_NAME

    key = (str(Path(reference_root).resolve()), speakers)
    with _CACHE_LOCK:
        profiles = _PROFILE_CACHE.get(key)
        if profiles is None:
            profiles = _build_speaker_profiles(Path(reference_root), speakers)
            _PROFILE_CACHE[key] = profiles

    query_emb = _compute_embedding(Path(query_wav))
    if query_emb is None or not profiles:
        return speakers[0]

    best_spk = speakers[0]
    best_score = -np.inf
    for spk in speakers:
        profile = profiles.get(spk)
        if profile is None:
            continue
        score = float(np.dot(query_emb, profile))
        if score > best_score:
            best_score = score
            best_spk = spk
    return best_spk

