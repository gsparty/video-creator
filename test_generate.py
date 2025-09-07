# test_generate.py
import traceback

from short_maker import generate_short

try:
    mp4, parts = generate_short("Alana", region="CH", voice_lang=None)
    print("SUCCESS:", mp4)
    print("PARTS:", parts)
except Exception as e:
    print("FAILED:", type(e).__name__, e)
    traceback.print_exc()
