import sys

from google.cloud import texttospeech_v1 as tts


def main():
    client = tts.TextToSpeechClient()
    # List voices and choose an en-US voice if available
    voices = client.list_voices().voices
    en_voices = [v for v in voices if any("en-US" in lang for lang in v.language_codes)]
    if en_voices:
        chosen = en_voices[0].name
        lang = "en-US"
    else:
        # fallback to first available voice
        chosen = voices[0].name
        lang = voices[0].language_codes[0] if voices[0].language_codes else "en-US"

    print(f"Selected voice: {chosen} (lang: {lang})")

    synthesis_input = tts.SynthesisInput(
        text="Hello from test TTS. This voice was auto-selected."
    )
    voice = tts.VoiceSelectionParams(language_code=lang, name=chosen)
    audio_config = tts.AudioConfig(audio_encoding=tts.AudioEncoding.LINEAR16)

    resp = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    out = "tts_test.wav"
    with open(out, "wb") as f:
        f.write(resp.audio_content)
    print("Wrote", out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("TTS failed:", e)
        sys.exit(1)
