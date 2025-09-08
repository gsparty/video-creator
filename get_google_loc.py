try:
    import google

    print("google.__file__ ->", getattr(google, "__file__", "package (no __file__)"))
except Exception as e:
    print("Importing top-level google failed:", e)
try:
    import google.cloud

    print("google.cloud ->", getattr(google.cloud, "__file__", "package (no __file__)"))
except Exception as e:
    print("Importing google.cloud failed:", e)
