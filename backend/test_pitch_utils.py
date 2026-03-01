"""Unit tests for pitch_utils.

- Tests midi_to_f0 by creating an in-memory PrettyMIDI object saved to a temp file.
- Tests audio_to_f0 by synthesizing a sine wave at 440Hz and saving to a temp wav, then
  extracting f0 and checking it's around 440Hz on voiced frames.

Run with: python -m pytest backend/test_pitch_utils.py
"""
import tempfile
import os
import numpy as np
import pytest
import soundfile as sf
import pretty_midi

from backend import pitch_utils as pu


def test_midi_to_f0_simple():
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    # add A4 from 0.0 to 1.0
    note = pretty_midi.Note(velocity=100, pitch=69, start=0.0, end=1.0)
    inst.notes.append(note)
    pm.instruments.append(inst)

    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as fh:
        pm.write(fh.name)
        fname = fh.name
    try:
        times, f0 = pu.midi_to_f0(fname, fps=100)
        voiced = ~np.isnan(f0)
        assert voiced.sum() > 0
        assert np.nanmean(f0[voiced]) == pytest.approx(440.0, rel=1e-2)
    finally:
        os.remove(fname)


def test_audio_to_f0_sine():
    sr = 22050
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * 440.0 * t)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
        sf.write(fh.name, y, sr)
        fname = fh.name
    try:
        times, f0 = pu.audio_to_f0(fname, sr=sr, hop_length=256)
        voiced = ~np.isnan(f0)
        assert voiced.sum() > 0
        mean_f0 = np.nanmean(f0[voiced])
        assert mean_f0 == pytest.approx(440.0, rel=0.02)
    finally:
        os.remove(fname)
