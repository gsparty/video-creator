import sys

try:
    import moviepy
    import moviepy.editor as m
    from PIL import Image
    import requests
    import flask

    print("IMPORTS OK")
    print("moviepy version:", moviepy.__version__)
    print("PIL version:", Image.__version__)
    print("requests version:", requests.__version__)
    print("flask version:", flask.__version__)
except Exception as e:
    print("IMPORT ERROR:", type(e).__name__, str(e))
    sys.exit(1)
