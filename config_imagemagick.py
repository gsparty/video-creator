# config_imagemagick.py
import os
import moviepy.config as mpc

# Update this path if your ImageMagick install changes
MAGICK_PATH = r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"

# 1) Set environment variable
os.environ["IMAGEMAGICK_BINARY"] = MAGICK_PATH

# 2) Set moviepy config variable
mpc.IMAGEMAGICK_BINARY = MAGICK_PATH

print(f"✅ ImageMagick configured: {MAGICK_PATH}")
