from moviepy.editor import CompositeVideoClip, VideoFileClip

from text_overlay import make_text_clip

in_path = "stock_clips/test1.mp4"
clip = VideoFileClip(in_path)
print(
    "stock clip size/duration/fps:",
    getattr(clip, "size", None),
    clip.duration,
    clip.fps,
    flush=True,
)

# make short overlay duration that matches clip
txt = make_text_clip(
    "COMPOSITE TEST ✅",
    fontsize=120,
    color="white",
    size=clip.size,
    duration=min(3, clip.duration),
)
print("overlay type:", type(txt), "has img:", hasattr(txt, "img"), flush=True)

# position and composite
txt = txt.set_position(("center", "center"))
comp = CompositeVideoClip([clip, txt]).set_duration(min(3, clip.duration))
out = "debug_comp.mp4"
comp.write_videofile(out, fps=clip.fps or 25, codec="libx264", audio_codec="aac")
print("Wrote", out, flush=True)
