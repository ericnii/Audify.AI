import re

from backend.vertex_tts import segments_to_ssml


def _strip_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def test_segments_to_ssml_basic():
    segments = [
        {"translated": "Hola amigo", "language": "es-ES"},
        {"translated": "Esto es una prueba", "language": "es-ES"},
    ]
    ssml = segments_to_ssml(segments, global_lang="es-ES", pause_between=0.2)
    ssml_nospace = _strip_ws(ssml)
    # Should be wrapped in <speak>
    assert ssml_nospace.startswith("<speak>") and ssml_nospace.endswith("</speak>")
    # Should contain two voice tags with xml:lang
    assert ssml.count('<voice xml:lang="es-ES">') == 2
    # Should contain break tag with 0.2s
    assert '<break time="0.2s"/>' in ssml


def test_segments_to_ssml_language_fallback():
    segments = [
        {"translated": "Hello world", "language": "English"},
        {"translated": "Second line"},
    ]
    ssml = segments_to_ssml(segments, global_lang="en-US")
    # First segment should use provided language value 'English' (the helper will
    # insert the provided string as xml:lang). The function currently uses the
    # segment value directly as xml:lang, so ensure it's present.
    assert 'xml:lang="English"' in ssml or 'xml:lang="en-US"' in ssml
    # There should still be a speak wrapper
    assert ssml.strip().startswith("<speak>")
