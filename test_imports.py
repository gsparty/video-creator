import sys

try:
    import flask
    import moviepy
    import requests
    from PIL import Image

    print("IMPORTS OK")
    print("moviepy version:", moviepy.__version__)
    print("PIL version:", Image.__version__)
    print("requests version:", requests.__version__)
    print("flask version:", flask.__version__)
except Exception as e:
    print("IMPORT ERROR:", type(e).__name__, str(e))
    sys.exit(1)
