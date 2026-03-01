from __future__ import annotations
import os
from pathlib import Path
import html
from typing import List, Optional, Dict, Any
import numpy as np

try:
    import librosa
except ImportError:
    librosa = None  # type: ignore

try:
    from google.cloud import texttospeech
except Exception as e:
    # Defer import error until function call so the rest of the backend can start
    texttospeech = None  # type: ignore
import base64
import requests


def _ensure_client() -> "texttospeech.TextToSpeechClient":
    if texttospeech is None:
        raise RuntimeError(
            "google-cloud-texttospeech is not installed. Install it or add it to requirements.txt"
        )

    # The client will pick up credentials from the environment via
    # GOOGLE_APPLICATION_CREDENTIALS or from ADC if running on GCP.
    return texttospeech.TextToSpeechClient()


def synthesize_texts_to_mp3(
    texts: List[str],
    out_path: Path,
    *,
    ssml: bool = False,
    voice: Optional[Dict[str, Any]] = None,
    speaking_rate: float = 1.0,
    pitch: float = 0.0,
) -> None:
    """
    Synthesize a list of texts (or SSML fragments) into a single MP3 file using
    Google Cloud Text-to-Speech (Vertex/Cloud TTS).

    Args:
        texts: List of text strings or SSML fragments.
        out_path: Path to write resulting MP3 to.
        ssml: If True, treat the provided strings as SSML fragments and wrap
              them inside a single <speak> element. If False, synthesize as
              plain text.
        voice: Optional dict to control voice selection. Recognized keys:
               - language_code (str) default 'en-US'
               - name (str) voice name
               - ssml_gender (str) one of 'MALE','FEMALE','NEUTRAL'
        speaking_rate: Speaking rate multiplier (1.0 is default)
        pitch: Pitch adjustment in semitones (0.0 is default)

    Raises:
        RuntimeError if the TTS client library is not available or credentials
        are not configured.
    """
    client = _ensure_client()

    # Build input: either SSML wrapped or plain text joined with newlines
    if ssml:
        # If fragments already contain <speak>, don't double-wrap
        body = "\n".join(texts)
        if "<speak" not in body:
            ssml_text = f"<speak>{body}</speak>"
        else:
            ssml_text = body
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml_text)
    else:
        combined = "\n".join(texts)
        synthesis_input = texttospeech.SynthesisInput(text=combined)

    # Voice selection
    vc = voice or {}
    language_code = vc.get("language_code", "en-US")
    name = vc.get("name")
    ssml_gender_str = (vc.get("ssml_gender") or "NEUTRAL").upper()
    ssml_gender = getattr(texttospeech.SsmlVoiceGender, ssml_gender_str, texttospeech.SsmlVoiceGender.NEUTRAL)

    voice_params = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=name,
        ssml_gender=ssml_gender,
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speaking_rate,
        pitch=pitch,
    )

    response = client.synthesize_speech(
        input=synthesis_input, voice=voice_params, audio_config=audio_config
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(response.audio_content)


def segments_to_ssml(
    segments,
    *,
    global_lang: str = "en-US",
    pause_between: List[float] | None = None,
) -> str:
    """
    Convert translated segments into a single SSML string.

    pause_between: list of pause durations (seconds) between segments.
                   Length should be len(segments) - 1.
    """

    parts = []

    # Ensure pause list exists
    if pause_between is None:
        pause_between = []

    for i, seg in enumerate(segments):
        text = seg.get("translated") or seg.get("text") or ""
        if not text:
            continue

        # Proper XML escaping
        safe = html.escape(text)

        lang = seg.get("language") or global_lang
        # Apply language-specific speaking rate adjustment for better pacing
        # Spanish is naturally faster, so slow it down more than English
        prosody_rate = "0.6"
        parts.append(f'<prosody rate="{prosody_rate}"><voice xml:lang="{lang}">{safe}</voice></prosody>')

        # Add pause AFTER this segment if one exists
        if i < len(pause_between):
            pause = pause_between[i]
            parts.append(f'<break time="{pause}s"/>')

    body = "".join(parts)
    return f"<speak>{body}</speak>"


def synthesize_texts_to_mp3_api_key(
    api_key: str,
    texts: List[str],
    out_path: Path,
    *,
    ssml: bool = False,
    voice: Optional[Dict[str, Any]] = None,
    speaking_rate: float = 1.0,
    pitch: float = 0.0,
) -> None:
    """
    Synthesize speech via the Google Cloud Text-to-Speech REST API using an API key.

    This is an alternative for environments where application-default credentials
    or service-account JSON are not available. Note: API keys have different
    quota/permission characteristics and should be protected.

    Args:
        api_key: Your Google Cloud API key string.
        texts: List of texts or SSML fragments. If ssml=True, pass a single
               SSML string in the list (or fragments will be concatenated).
        out_path: Path to write MP3 to.
        ssml: If True, send SSML payload to the API.
        voice: Dict with optional keys 'language_code' and 'name'.
        speaking_rate: float speaking rate.
        pitch: float pitch.

    Raises:
        RuntimeError on API errors.
    """
    if not api_key:
        raise RuntimeError("API key required for synthesize_texts_to_mp3_api_key")

    if ssml:
        body = "\n".join(texts)
        if "<speak" not in body:
            input_payload = {"ssml": f"<speak>{body}</speak>"}
        else:
            input_payload = {"ssml": body}
    else:
        input_payload = {"text": "\n".join(texts)}

    vc = voice or {}
    language_code = vc.get("language_code", "en-US")
    name = vc.get("name")

    payload = {
        "input": input_payload,
        "voice": {"languageCode": language_code},
        "audioConfig": {"audioEncoding": "MP3", "speakingRate": speaking_rate, "pitch": pitch},
    }
    if name:
        payload["voice"]["name"] = name

    url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"

    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"TTS API error {resp.status_code}: {resp.text}")

    data = resp.json()
    audio_content = data.get("audioContent")
    if not audio_content:
        raise RuntimeError(f"No audioContent in TTS response: {data}")

    audio_bytes = base64.b64decode(audio_content)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(audio_bytes)


def combine_audio_files(
    tts_path: Path,
    instrumental_path: Path,
    out_path: Path,
    segments: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Combine TTS (translated speech) and instrumental audio files.
    Aligns TTS with instrumental timing based on segment start times.
    
    Args:
        tts_path: Path to TTS MP3 file
        instrumental_path: Path to instrumental WAV file
        out_path: Path to save combined audio
        segments: Optional list of segments with 'start' times to align TTS
    """
    if librosa is None:
        raise RuntimeError("librosa is required to combine audio files")
    
    # Load both audio files
    tts_audio, tts_sr = librosa.load(str(tts_path), sr=None)
    instrumental_audio, inst_sr = librosa.load(str(instrumental_path), sr=None)
    
    # Resample to same sample rate if different
    if tts_sr != inst_sr:
        instrumental_audio = librosa.resample(instrumental_audio, orig_sr=inst_sr, target_sr=tts_sr)
    
    # Get the start time of the first segment to align TTS
    tts_start_time = 0.0
    if segments and len(segments) > 0:
        tts_start_time = float(segments[0].get("start", 0.0))
    
    # Calculate padding (silence) needed at the start of TTS
    tts_sr_int = int(tts_sr)
    padding_samples = int(tts_start_time * tts_sr_int)
    
    # Pad TTS with silence at the beginning
    if padding_samples > 0:
        silence_pad = np.zeros(padding_samples)
        tts_audio_padded = np.concatenate([silence_pad, tts_audio])
    else:
        tts_audio_padded = tts_audio
    
    # Match lengths - pad or trim to instrumental length
    inst_len = len(instrumental_audio)
    if len(tts_audio_padded) < inst_len:
        # Pad TTS with silence at the end
        silence_pad = np.zeros(inst_len - len(tts_audio_padded))
        tts_audio_padded = np.concatenate([tts_audio_padded, silence_pad])
    elif len(tts_audio_padded) > inst_len:
        # Trim TTS to match instrumental length
        tts_audio_padded = tts_audio_padded[:inst_len]
    
    # Mix: reduce instrumental volume a bit so TTS is prominent
    # 70% TTS + 30% instrumental for balance
    combined = 0.7 * tts_audio_padded + 0.3 * instrumental_audio
    
    # Normalize to prevent clipping
    max_val = np.max(np.abs(combined))
    if max_val > 1.0:
        combined = combined / max_val
    
    # Save as WAV using soundfile
    import soundfile as sf
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), combined, tts_sr_int)
