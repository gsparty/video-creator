# test_tts_try_voices.py
from google.cloud import texttospeech
import sys, time

def main():
    client = texttospeech.TextToSpeechClient()
    voices = client.list_voices().voices
    en_voices = [v for v in voices if any("en-US" in lang for lang in v.language_codes)]
    try_list = en_voices if en_voices else voices

    for v in try_list:
        name = v.name
        lang = v.language_codes[0] if v.language_codes else "en-US"
        print("Trying voice:", name, "langs=", v.language_codes)
        try:
            synthesis_input = texttospeech.SynthesisInput(text="Hello — testing voice " + name)
            voice = texttospeech.VoiceSelectionParams(language_code=lang, name=name)
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.LINEAR16)
            resp = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
            out = "tts_test.wav"
            with open(out, "wb") as f:
                f.write(resp.audio_content)
            print("Success! wrote:", out, "using voice", name)
            return 0
        except Exception as e:
            print("Failed for", name, "->", repr(e))
            time.sleep(0.2)
            continue

    print("No voice succeeded. Check credentials/permissions or try ADC.")
    return 1

if __name__ == "__main__":
    sys.exit(main())
