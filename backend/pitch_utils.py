"""Utilities for extracting or generating pitch contours.

Functions:
- audio_to_f0(path, sr=22050, hop_length=256, fmin='C2', fmax='C7') -> (times, f0_hz)
- midi_to_f0(path, fps=80, collapse_policy='highest') -> (times, f0_hz)
- hz_to_midi(hz), midi_to_hz(midi)

Representation:
- f0 arrays use np.nan for unvoiced frames.
- times are in seconds and match the f0 frames.

This file is deliberately dependency-light and uses librosa and pretty_midi which
are included in `backend/requirements.txt`.
"""

from typing import Tuple, Optional
import numpy as np
import librosa
import pretty_midi


def hz_to_midi(hz: float) -> float:
    return 69.0 + 12.0 * np.log2(hz / 440.0)


def midi_to_hz(midi: float) -> float:
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def audio_to_f0(path: str,
                sr: int = 22050,
                hop_length: int = 256,
                fmin: str = "C2",
                fmax: str = "C7") -> Tuple[np.ndarray, np.ndarray]:
    """Extracts an F0 contour from an audio file using librosa.pyin.

    Returns (times, f0_hz) where f0_hz contains np.nan for unvoiced frames.
    """
    y, sr = librosa.load(path, sr=sr)
    fmin_hz = librosa.note_to_hz(fmin) if isinstance(fmin, str) else float(fmin)
    fmax_hz = librosa.note_to_hz(fmax) if isinstance(fmax, str) else float(fmax)

    f0, voiced_flag, voiced_prob = librosa.pyin(
        y, fmin=fmin_hz, fmax=fmax_hz, sr=sr, hop_length=hop_length
    )
    n_frames = len(f0)
    times = librosa.frames_to_time(np.arange(n_frames), sr=sr, hop_length=hop_length)
    return times, f0


def midi_to_f0(path: str,
               fps: int = 80,
               collapse_policy: str = "highest",
               track_index: Optional[int] = None) -> Tuple[np.ndarray, np.ndarray]:
    """Converts a MIDI file into a per-frame F0 contour (Hz).

    Args:
      path: path to .mid file
      fps: frames per second for output contour (e.g., 80 -> 12.5 ms frames)
      collapse_policy: how to handle polyphony: 'highest' (default), 'lowest', 'priority' (first)
      track_index: optional instrument index to select a single MIDI track

    Returns (times, f0_hz) with np.nan for frames with no active note.
    """
    pm = pretty_midi.PrettyMIDI(path)
    end_time = pm.get_end_time()
    times = np.arange(0.0, end_time, 1.0 / fps)
    f0 = np.full_like(times, np.nan, dtype=float)

    instruments = pm.instruments
    if track_index is not None:
        instruments = [instruments[track_index]]

    # gather all notes across chosen instruments
    notes = []
    for instr in instruments:
        if instr.is_drum:
            continue
        for note in instr.notes:
            notes.append((note.start, note.end, note.pitch))

    # if no notes found, return all-nan contour
    if len(notes) == 0:
        return times, f0

    # For each frame, pick note according to policy
    for i, t in enumerate(times):
        active = [n for n in notes if n[0] <= t < n[1]]
        if len(active) == 0:
            continue
        if collapse_policy == "highest":
            chosen = max(active, key=lambda x: x[2])
        elif collapse_policy == "lowest":
            chosen = min(active, key=lambda x: x[2])
        else:  # priority
            chosen = active[0]
        f0[i] = pretty_midi.note_number_to_hz(chosen[2])

    return times, f0


# Small CLI helpers when run directly
if __name__ == "__main__":
    import argparse
    import json

    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=["audio", "midi"], help="Source type")
    p.add_argument("input", help="Path to input file")
    p.add_argument("--out-json", help="Write contour to JSON file (times,f0)")
    p.add_argument("--fps", type=int, default=80)
    p.add_argument("--hop", type=int, default=256)
    args = p.parse_args()

    if args.mode == "audio":
        times, f0 = audio_to_f0(args.input, hop_length=args.hop)
    else:
        times, f0 = midi_to_f0(args.input, fps=args.fps)

    out = {"times": times.tolist(), "f0": [None if np.isnan(x) else x for x in f0.tolist()]}
    if args.out_json:
        with open(args.out_json, "w") as fh:
            json.dump(out, fh)
    else:
        print(json.dumps(out)[:1000])
