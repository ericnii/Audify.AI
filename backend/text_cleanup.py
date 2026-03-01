import re

def _shorten_if_too_long(text: str, max_chars: int = 120) -> str:
    if len(text) <= max_chars:
        return text
    # cut at last punctuation/space before max_chars
    cut = max(text.rfind(".", 0, max_chars),
            text.rfind(",", 0, max_chars),
            text.rfind(" ", 0, max_chars))
    return text[:cut].strip() if cut > 20 else text[:max_chars].strip()

def clean_for_tts(text: str) -> str:
    """
    Minimal cleanup to make TTS more stable across ES/FR/DE.
    Keeps punctuation that helps prosody, removes junk.
    """
    if not text:
        return ""

    # Normalize quotes/apostrophes
    text = (text.replace("“", '"').replace("”", '"')
                .replace("’", "'").replace("`", "'"))

    # Remove bracketed stage directions: [chorus], (laughs), etc.
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)

    # Remove weird symbols but keep basic punctuation for rhythm
    # Keep: letters, numbers, spaces, apostrophe, comma, period, question/exclamation, colon, semicolon, hyphen
    text = re.sub(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ\s'.,?!:;\-]", " ", text)

    # Collapse repeated punctuation
    text = re.sub(r"([!?.,])\1+", r"\1", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return _shorten_if_too_long(text)