import imageio
import numpy as np

from text_overlay import make_text_clip

try:
    c = make_text_clip(
        "DEBUG Overlay ✅", fontsize=140, color="white", size=(1080, 1920), duration=2
    )
    print("make_text_clip returned:", type(c))
    # grab a frame
    arr = c.get_frame(0)  # returns float or uint array
    arr = (np.clip(arr, 0, 255)).astype(np.uint8)
    imageio.imwrite("debug_txt.png", arr)
    print("Wrote debug_txt.png")
except Exception as e:
    print("ERROR make_text_clip:", repr(e))
    raise
