# ensure we use the same ImageMagick config you added earlier

# import helper
import text_overlay

# create a sample overlay clip
size = (1080, 1920)
headline = "DEBUG Overlay ✅"
try:
    clip = text_overlay.make_text_clip(headline, fontsize=140, color="white", size=size, duration=2)
    print("make_text_clip returned:", type(clip), flush=True)
    # try to save a single frame robustly
    saved = False
    try:
        # many moviepy clips support save_frame
        clip.save_frame("debug_txt_saveframe.png", t=0)
        print("Saved debug_txt_saveframe.png via save_frame()", flush=True)
        saved = True
    except Exception as e:
        print("save_frame failed:", e, flush=True)
    if not saved:
        # If clip has .img (ImageClip), save with Pillow
        try:
            import imageio
            import numpy as np
            import PIL.Image as Image
            if hasattr(clip, "img"):
                arr = np.array(clip.img).astype("uint8")
                Image.fromarray(arr).save("debug_txt_img.png")
                print("Saved debug_txt_img.png from clip.img", flush=True)
                saved = True
        except Exception as e:
            print("saving from .img failed:", e, flush=True)
    if not saved:
        # fallback: get a frame via get_frame(0)
        try:
            import imageio
            import numpy as _np
            arr = clip.get_frame(0)
            # ensure uint8
            arr = (_np.clip(arr, 0, 255)).astype(_np.uint8)
            imageio.imwrite("debug_txt_getframe.png", arr)
            print("Saved debug_txt_getframe.png via get_frame()", flush=True)
            saved = True
        except Exception as e:
            print("get_frame failed:", e, flush=True)
    if not saved:
        print("Failed to save any debug overlay image", flush=True)
except Exception as exc:
    print("make_text_clip raised:", repr(exc), flush=True)
    raise
