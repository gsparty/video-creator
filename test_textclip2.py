import os

# point to your magick.exe
magick_path = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"

# 1) environment variable (some MoviePy code reads this)
os.environ["IMAGEMAGICK_BINARY"] = magick_path

# 2) set the config variable directly (moviepy.config exists, even if change_settings doesn't)
import moviepy.config as mpc  # noqa: E402  # noqa: E402

mpc.IMAGEMAGICK_BINARY = magick_path

# Now import TextClip and create a simple TextClip image
from moviepy.editor import TextClip  # noqa: E402
txt = TextClip("hello world", fontsize=50)  # this invokes ImageMagick
print("TextClip OK, IMAGEMAGICK_BINARY=", mpc.IMAGEMAGICK_BINARY)

