from __future__ import annotations

import threading
from pathlib import Path

import nltk
from g2p_en import G2p

_NLTK_DATA_DIR = Path(__file__).resolve().parent / ".nltk_data"
_BOOTSTRAP_DONE = False
_G2P = None
_LOCK = threading.Lock()

_RESOURCE_CANDIDATES = [
    # Newer NLTK name used by recent g2p_en stacks.
    ("taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"),
    # Backward-compatible alias for older NLTK.
    ("taggers/averaged_perceptron_tagger", "averaged_perceptron_tagger"),
    ("corpora/cmudict", "cmudict"),
    ("tokenizers/punkt", "punkt"),
    ("tokenizers/punkt_tab", "punkt_tab"),
]


def _ensure_nltk_data_path() -> None:
    _NLTK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    nltk_path = str(_NLTK_DATA_DIR)
    if nltk_path not in nltk.data.path:
        nltk.data.path.insert(0, nltk_path)


def _ensure_resource(resource_path: str, package_name: str) -> None:
    try:
        nltk.data.find(resource_path)
        return
    except LookupError:
        pass

    nltk.download(package_name, download_dir=str(_NLTK_DATA_DIR), quiet=True)
    nltk.data.find(resource_path)


def _bootstrap_nltk_resources() -> None:
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return

    _ensure_nltk_data_path()
    for resource_path, package_name in _RESOURCE_CANDIDATES:
        try:
            _ensure_resource(resource_path, package_name)
        except LookupError:
            # Some installs don't provide every optional resource package.
            # Keep going and let g2p usage decide if anything critical is still missing.
            continue
    _BOOTSTRAP_DONE = True


def _get_g2p() -> G2p:
    global _G2P
    if _G2P is not None:
        return _G2P

    with _LOCK:
        if _G2P is None:
            _bootstrap_nltk_resources()
            _G2P = G2p()
    return _G2P


def text_to_phonemes(text: str):
    g2p = _get_g2p()
    try:
        phonemes = g2p(text)
    except LookupError:
        # If runtime still reports missing NLTK assets, force one retry after bootstrap.
        with _LOCK:
            _bootstrap_nltk_resources()
        phonemes = g2p(text)
    return list(phonemes)  # Returns ["HH", "EH", "L", "O"]
