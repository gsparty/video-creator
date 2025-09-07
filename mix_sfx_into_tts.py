# mix_sfx_into_tts.py (fixed)
# Usage: python mix_sfx_into_tts.py <basename> <sfx_file>
# Example: python mix_sfx_into_tts.py 02_3-second-kitchen-trick sfx_click.mp3

import os
import subprocess
import sys

if len(sys.argv) < 2:
    print("Usage: python mix_sfx_into_tts.py <basename> <sfx_file (optional)>")
    sys.exit(1)

basename = sys.argv[1]
sfx = sys.argv[2] if len(sys.argv) > 2 else "sfx_click.mp3"
tts = f"{basename}.tts.mp3"
times_file = f"{basename}.caption_starts.txt"
out = f"{basename}.tts_with_sfx.mp3"

for p in (tts, times_file, sfx):
    if not os.path.exists(p):
        raise SystemExit(f"Missing required file: {p}")

with open(times_file, "r", encoding="utf-8") as f:
    times = [float(line.strip()) for line in f.readlines() if line.strip()]

# If there are no times, just copy the original tts to output
if len(times) == 0:
    import shutil
    shutil.copy(tts, out)
    print("No caption times found — copied TTS to", out)
    sys.exit(0)

# Build ffmpeg command
cmd = ["ffmpeg", "-y", "-i", tts]
# add one sfx input per time entry
for _ in times:
    cmd += ["-i", sfx]

# Build filter_complex using semicolons between adelay chains (important)
adelay_parts = []
labels = []
for i, t in enumerate(times):
    ms = int(round(t * 1000))
    label = f"s{i}"
    labels.append(label)
    # adelay arg needs one value per channel. We'll assume stereo: "ms|ms"
    adelay_parts.append(f"[{i+1}:a]adelay={ms}|{ms}[{label}]")

# join adelay parts with semicolons
adelay_part = ";".join(adelay_parts)

# Now construct the amix inputs: base audio [0:a] plus each delayed sN
mix_input_sequence = "[0:a]" + "".join(f"[{lab}]" for lab in labels)
mix_part = f"{mix_input_sequence}amix=inputs={1+len(labels)}:dropout_transition=0,volume=2[aout]"

filter_complex = f"{adelay_part};{mix_part}"

cmd += ["-filter_complex", filter_complex, "-map", "[aout]", "-c:a", "aac", "-b:a", "128k", out]

print("Running FFmpeg to mix SFX into TTS...")
# show a short human readable preview of the command (useful for debugging)
print("FFmpeg command:", " ".join(cmd))
subprocess.check_call(cmd)
print("WROTE", out)
