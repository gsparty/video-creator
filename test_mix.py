# test_mix.py
# Generates a short test tone and attempts to mix an optional whoosh SFX using audio_mixer_ffmpeg.duck_and_mix

import wave, struct, math, os
from audio_mixer_ffmpeg import duck_and_mix

# Generate 1.5s test tone tts file
tts_file = "sample_tts.wav"
framerate = 44100
duration = 1.5
amplitude = 8000
freq = 440.0

with wave.open(tts_file, "w") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(framerate)
    for i in range(int(framerate * duration)):
        val = int(amplitude * math.sin(2 * math.pi * freq * (i / framerate)))
        w.writeframes(struct.pack("<h", val))

sfx_list = []
if os.path.exists("assets/sounds/whoosh.wav"):
    sfx_list.append(("assets/sounds/whoosh.wav", 0.05))
elif os.path.exists("assets/sounds/whoosh.mp3"):
    sfx_list.append(("assets/sounds/whoosh.mp3", 0.05))

print("Mixing", tts_file, "with", sfx_list)
out = duck_and_mix(tts_file, sfx_list, out_path="test_mix.wav")
print("Wrote", out)
