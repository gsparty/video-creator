# overlay_test_runner.py - uses the helper to place a text overlay on stock_clips\test1.mp4
from pathlib import Path

from moviepy.editor import CompositeVideoClip, VideoFileClip

from text_overlay import make_text_clip

in_path = Path("stock_clips") / "test1.mp4"
if not in_path.exists():
    raise SystemExit("stock_clips/test1.mp4 not found")

clip = VideoFileClip(str(in_path))
txt = make_text_clip(
    "Text overlay check ✅", fontsize=80, size=clip.size, duration=min(5, clip.duration)
)
txt = txt.set_position("center").set_duration(min(5, clip.duration))
out = CompositeVideoClip([clip, txt])
out.write_videofile(
    "overlay_test.mp4", fps=clip.fps or 25, codec="libx264", audio_codec="aac"
)
print("Wrote overlay_test.mp4")
