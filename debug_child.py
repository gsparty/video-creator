# debug_child.py
import os
import sys

print("child sys.executable:", sys.executable)
print("child cwd:", os.getcwd())
print("child sys.path (first 6):", sys.path[:6])
try:
    import moviepy.editor as m
    print("child moviepy OK:", getattr(m, "__file__", None))
except Exception as e:
    print("child import ERROR:", repr(e))
