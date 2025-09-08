# test_overlay_watch.py
import os
import sys
import time
from multiprocessing import Process, Queue

TIMEOUT = 30  # seconds


def child_make(q):
    try:
        # small, clear startup message
        print("child: start import text_overlay", flush=True)
        from text_overlay import make_text_clip

        print("child: imported make_text_clip", flush=True)

        # try to build a small overlay and save a single frame
        clip = make_text_clip(
            "DEBUG Overlay ✅", fontsize=80, color="white", size=(540, 960), duration=1
        )
        print("child: clip created, trying to save frame", flush=True)

        # try save_frame if present, else get_frame+imageio
        try:
            if hasattr(clip, "save_frame"):
                clip.save_frame("debug_child_saveframe.png", t=0)
                q.put(("OK", "save_frame"))
                return
        except Exception as e:
            print("child: save_frame failed:", repr(e), flush=True)

        try:
            arr = clip.get_frame(0)
            # lazy import imageio to write
            import imageio
            import numpy as _np

            arr = (_np.clip(arr, 0, 255)).astype(_np.uint8)
            imageio.imwrite("debug_child_getframe.png", arr)
            q.put(("OK", "get_frame"))
            return
        except Exception as e:
            print("child: get_frame failed:", repr(e), flush=True)
            q.put(("ERR", repr(e)))
            return
    except Exception as exc:
        q.put(("ERR", repr(exc)))
        return


if __name__ == "__main__":
    print("parent: start; PID", os.getpid())
    q = Queue()
    p = Process(target=child_make, args=(q,))
    p.start()
    start = time.time()
    p.join(TIMEOUT)
    if p.is_alive():
        print(f"parent: child still alive after {TIMEOUT}s — terminating", flush=True)
        p.terminate()
        p.join(5)
        print("parent: child terminated", flush=True)
        sys.exit(2)
    # child finished — read queue
    try:
        ok, msg = q.get_nowait()
        print("parent: child result:", ok, msg)
        if ok == "OK":
            print(
                "parent: debug image written (check debug_child_saveframe.png or debug_child_getframe.png)"
            )
            sys.exit(0)
        else:
            print("parent: error in child:", msg)
            sys.exit(3)
    except Exception as e:
        print("parent: child finished but returned nothing; exit", repr(e))
        sys.exit(4)
