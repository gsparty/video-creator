# make_sfx.py
# Usage: python make_sfx.py sfx_click.mp3
import sys, subprocess
out = sys.argv[1] if len(sys.argv)>1 else "sfx_click.mp3"
# short sine burst as a "ping"
cmd = [
  "ffmpeg","-y",
  "-f","lavfi","-i", "sine=frequency=1200:duration=0.12",
  "-af","acompressor,volume=2",
  "-c:a","libmp3lame","-q:a","2",
  out
]
print("RUNNING:", " ".join(cmd))
subprocess.check_call(cmd)
print("WROTE", out)
