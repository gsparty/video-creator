# tts_utils.py
"""
Helper utilities for robust Google Cloud Text-to-Speech usage.
Provides voice-selection fallback and a simple synthesize_text() helper.
"""
from google.cloud import texttospeech
import time
from typing import Optional, List, Tuple

DEFAULT_OUTPUT = "tts_out.wav"

# Preferred voice hints in order (strings matched against voice.name)
PREFERRED_VOICE_HINTS = [
    "en-US-Casual-K",
    "en-US-Neural2",
    "en-US-Wavenet",
    "en-US-Standard",
    "en-US-Casual",
    "en-US"
]

def list_voices(client: texttospeech.TextToSpeechClient):
    return client.list_voices().voices

def choose_voice(voices, lang="en-US") -> Optional[str]:
    # prefer exactly matching known good voices first
    for hint in PREFERRED_VOICE_HINTS:
        for v in voices:
            if hint.lower() in v.name.lower() and any(lang in lc for lc in v.language_codes):
                return v.name
    # fallback: any voice that supports lang
    for v in voices:
        if any(lang in lc for lc in v.language_codes):
            return v.name
    # last resort: any voice
    return voices[0].name if voices else None

def synthesize_text(
    text: str,
    out_path: str = DEFAULT_OUTPUT,
    preferred_voice: Optional[str] = None,
    lang: str = "en-US",
    audio_encoding=texttospeech.AudioEncoding.LINEAR16,
    speaking_rate: float = 1.0,
    pitch: float = 0.0,
) -> Tuple[str, str]:
    """
    Synthesize `text` to `out_path`. Tries preferred voice first then falls back.
    Returns (out_path, voice_used)
    Raises RuntimeError if no voice succeeded.
    """
    client = texttospeech.TextToSpeechClient()
    voices = list_voices(client)
    voice_candidates: List[str] = []
    if preferred_voice:
        voice_candidates.append(preferred_voice)
    # populate candidates from list (prefer those supporting lang)
    for v in voices:
        if any(lang in lc for lc in v.language_codes):
            voice_candidates.append(v.name)
    # ensure unique while preserving order
    voice_candidates = list(dict.fromkeys(voice_candidates))
    if not voice_candidates:
        voice_candidates = [v.name for v in voices] if voices else []

    last_exc = None
    for vn in voice_candidates:
        try:
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(language_code=lang, name=vn)
            audio_config = texttospeech.AudioConfig(
                audio_encoding=audio_encoding, speaking_rate=speaking_rate, pitch=pitch
            )
            resp = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            with open(out_path, "wb") as f:
                f.write(resp.audio_content)
            return out_path, vn
        except Exception as e:
            last_exc = e
            time.sleep(0.2)
            continue
    raise RuntimeError(f"TTS: no voice succeeded. Last error: {last_exc}")
