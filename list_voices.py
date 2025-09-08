# list_voices.py
from google.cloud import texttospeech

client = texttospeech.TextToSpeechClient()
voices = client.list_voices().voices
for v in voices:
    print(v.name, "|", v.language_codes, "| ssml_gender=", v.ssml_gender)
