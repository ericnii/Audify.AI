from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import librosa
import numpy as np
import soundfile as sf

from audio_stems import seperate_stems_demucs
from transcribe_whisper import transcribe_with_whisper

SUPPORTED_AUDIO_EXTS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac"}


def _merge_intervals(intervals: list[tuple[int, int]], max_gap_samples: int) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in intervals:
        if not merged:
            merged.append([start, end])
            continue
        if start - merged[-1][1] <= max_gap_samples:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def _chunk_intervals(
    intervals: list[tuple[int, int]],
    min_samples: int,
    max_samples: int,
) -> list[tuple[int, int]]:
    chunks: list[tuple[int, int]] = []
    for start, end in intervals:
        pos = start
        while pos < end:
            remain = end - pos
            if remain < min_samples:
                break
            take = min(max_samples, remain)
            chunks.append((pos, pos + take))
            pos += take
    return chunks


def _silence_intervals(
    y: np.ndarray,
    sr: int,
    silence_db: int,
    merge_gap_sec: float,
) -> list[tuple[int, int]]:
    intervals_np = librosa.effects.split(y, top_db=silence_db, frame_length=2048, hop_length=512)
    intervals = [(int(s), int(e)) for s, e in intervals_np.tolist()]
    return _merge_intervals(intervals, max_gap_samples=int(merge_gap_sec * sr))


def _whisper_intervals(
    in_audio: Path,
    sr: int,
    merge_gap_sec: float,
) -> list[tuple[int, int]]:
    segments = transcribe_with_whisper(in_audio)
    sec_intervals: list[tuple[float, float]] = []
    for seg in segments:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", 0.0))
        if end <= start:
            continue
        sec_intervals.append((start, end))

    if not sec_intervals:
        return []

    merged_secs: list[tuple[float, float]] = []
    cur_start, cur_end = sec_intervals[0]
    for start, end in sec_intervals[1:]:
        gap = start - cur_end
        if gap <= merge_gap_sec:
            cur_end = max(cur_end, end)
        else:
            merged_secs.append((cur_start, cur_end))
            cur_start, cur_end = start, end
    merged_secs.append((cur_start, cur_end))

    return [(max(0, int(s * sr)), max(0, int(e * sr))) for s, e in merged_secs]


def _iter_input_files(
    input_files: list[str] | None,
    input_dir: str | None,
) -> list[Path]:
    files: list[Path] = []
    if input_files:
        files.extend(Path(p).resolve() for p in input_files)

    if input_dir:
        root = Path(input_dir).resolve()
        if not root.exists():
            raise FileNotFoundError(f"input-dir not found: {root}")
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in SUPPORTED_AUDIO_EXTS:
                files.append(p.resolve())

    deduped: list[Path] = []
    seen: set[Path] = set()
    for p in files:
        if p in seen:
            continue
        seen.add(p)
        deduped.append(p)
    return deduped


def _prepare_vocal_sources(
    inputs: Iterable[Path],
    stems_from_songs: bool,
    stems_dir: Path,
    demucs_model: str,
) -> list[Path]:
    sources: list[Path] = []
    if not stems_from_songs:
        for p in inputs:
            if not p.exists():
                raise FileNotFoundError(f"Input audio not found: {p}")
            sources.append(p)
        return sources

    stems_dir.mkdir(parents=True, exist_ok=True)
    for idx, song_path in enumerate(inputs):
        if not song_path.exists():
            raise FileNotFoundError(f"Input song not found: {song_path}")
        out = stems_dir / f"song_{idx:03d}_{song_path.stem}"
        stems = seperate_stems_demucs(song_path, out, model=demucs_model)
        sources.append(stems["vocals"])
        print(f"[stems] {song_path.name} -> {stems['vocals']}")
    return sources


def generate_clips_from_sources(
    source_audio: list[Path],
    out_dir: Path,
    target_sr: int,
    min_sec: float,
    max_sec: float,
    target_total_min: float,
    min_rms: float,
    segmenter: str,
    silence_db: int,
    merge_gap_sec: float,
) -> tuple[int, float]:
    out_dir.mkdir(parents=True, exist_ok=True)

    min_samples = int(min_sec * target_sr)
    max_samples = int(max_sec * target_sr)
    target_total_sec = target_total_min * 60.0

    clip_idx = 0
    total_sec = 0.0

    for source in source_audio:
        y, sr = librosa.load(source, sr=target_sr, mono=True)
        if segmenter == "whisper":
            base_intervals = _whisper_intervals(source, sr=sr, merge_gap_sec=merge_gap_sec)
            if not base_intervals:
                base_intervals = _silence_intervals(y=y, sr=sr, silence_db=silence_db, merge_gap_sec=merge_gap_sec)
        else:
            base_intervals = _silence_intervals(y=y, sr=sr, silence_db=silence_db, merge_gap_sec=merge_gap_sec)

        chunked_intervals = _chunk_intervals(base_intervals, min_samples=min_samples, max_samples=max_samples)

        song_written = 0
        for start, end in chunked_intervals:
            if end > len(y):
                end = len(y)
            if end <= start:
                continue

            clip = y[start:end]
            rms = float(np.sqrt(np.mean(np.square(clip))))
            if rms < min_rms:
                continue

            out_file = out_dir / f"{clip_idx:05d}.wav"
            sf.write(out_file, clip, sr)
            clip_idx += 1
            song_written += 1
            total_sec += len(clip) / sr
            if total_sec >= target_total_sec:
                print(f"[clips] reached target at {source.name}")
                return clip_idx, total_sec

        print(f"[clips] {source.name}: wrote {song_written} clips")

    return clip_idx, total_sec


def generate_clips(
    in_wav: Path,
    out_dir: Path,
    target_sr: int,
    min_sec: float,
    max_sec: float,
    target_total_min: float,
    silence_db: int,
    merge_gap_sec: float,
    min_rms: float,
    segmenter: str = "silence",
) -> tuple[int, float]:
    return generate_clips_from_sources(
        source_audio=[in_wav],
        out_dir=out_dir,
        target_sr=target_sr,
        min_sec=min_sec,
        max_sec=max_sec,
        target_total_min=target_total_min,
        min_rms=min_rms,
        segmenter=segmenter,
        silence_db=silence_db,
        merge_gap_sec=merge_gap_sec,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Create 2-8s vocal clips for so-vits-svc training from one or many audio files. "
            "Can optionally run Demucs first to extract vocals."
        )
    )
    p.add_argument("--input", help="Single input audio path (vocals file, or full song with --stems-from-songs).")
    p.add_argument("--inputs", nargs="+", help="Multiple input audio paths.")
    p.add_argument("--input-dir", help="Directory to recursively scan for audio files.")
    p.add_argument(
        "--out-dir",
        default="external/so-vits-svc/dataset_raw/voice1",
        help="Output directory for generated clips.",
    )
    p.add_argument("--sr", type=int, default=32000, help="Target sample rate.")
    p.add_argument("--min-sec", type=float, default=2.0, help="Minimum clip length in seconds.")
    p.add_argument("--max-sec", type=float, default=8.0, help="Maximum clip length in seconds.")
    p.add_argument(
        "--target-min",
        type=float,
        default=9.0,
        help="Stop after this many minutes of total clips.",
    )
    p.add_argument(
        "--silence-db",
        type=int,
        default=30,
        help="Silence threshold for non-silent interval detection.",
    )
    p.add_argument(
        "--merge-gap-sec",
        type=float,
        default=0.25,
        help="Merge non-silent intervals separated by <= this gap.",
    )
    p.add_argument(
        "--min-rms",
        type=float,
        default=0.005,
        help="Minimum RMS needed to keep a clip.",
    )
    p.add_argument(
        "--segmenter",
        choices=["whisper", "silence"],
        default="whisper",
        help="How to choose clip boundaries from vocals.",
    )
    p.add_argument(
        "--stems-from-songs",
        action="store_true",
        help="Treat inputs as full songs and extract vocals with Demucs before slicing clips.",
    )
    p.add_argument(
        "--stems-dir",
        default="external/so-vits-svc/.tmp_stems",
        help="Directory to store generated stems when --stems-from-songs is set.",
    )
    p.add_argument(
        "--demucs-model",
        default="mdx_extra",
        help="Demucs model name used when --stems-from-songs is set.",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out_dir).resolve()
    stems_dir = Path(args.stems_dir).resolve()

    input_files: list[str] = []
    if args.input:
        input_files.append(args.input)
    if args.inputs:
        input_files.extend(args.inputs)

    candidates = _iter_input_files(input_files=input_files or None, input_dir=args.input_dir)
    if not candidates:
        raise ValueError("No input audio files found. Use --input, --inputs, or --input-dir.")
    if args.min_sec <= 0 or args.max_sec <= 0:
        raise ValueError("min-sec and max-sec must be > 0")
    if args.max_sec < args.min_sec:
        raise ValueError("max-sec must be >= min-sec")
    if args.target_min <= 0:
        raise ValueError("target-min must be > 0")

    sources = _prepare_vocal_sources(
        inputs=candidates,
        stems_from_songs=args.stems_from_songs,
        stems_dir=stems_dir,
        demucs_model=args.demucs_model,
    )

    count, total_sec = generate_clips_from_sources(
        source_audio=sources,
        out_dir=out_dir,
        target_sr=args.sr,
        min_sec=args.min_sec,
        max_sec=args.max_sec,
        target_total_min=args.target_min,
        min_rms=args.min_rms,
        segmenter=args.segmenter,
        silence_db=args.silence_db,
        merge_gap_sec=args.merge_gap_sec,
    )

    print(f"Processed sources: {len(sources)}")
    print(f"Generated {count} clips")
    print(f"Total duration: {total_sec / 60.0:.2f} minutes")
    print(f"Output directory: {out_dir}")


if __name__ == "__main__":
    main()
