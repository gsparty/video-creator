# pil_compat.py -- lightweight Pillow compatibility shim
# ensures older code referencing Image.ANTIALIAS works with recent Pillow versions

try:
    from PIL import Image
except Exception:
    # nothing to do if Pillow missing
    Image = None

if Image is not None:
    # Pillow 9+ moved constants to Image.Resampling
    # Provide Image.ANTIALIAS alias if missing
    try:
        _ = Image.ANTIALIAS
    except Exception:
        try:
            Image.ANTIALIAS = Image.Resampling.LANCZOS
        except Exception:
            # fallback: try to alias LANCZOS or set numeric placeholder
            if hasattr(Image, "LANCZOS"):
                Image.ANTIALIAS = Image.LANCZOS
            else:
                Image.ANTIALIAS = 1
