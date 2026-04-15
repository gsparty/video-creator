# Video Creator

Automation-heavy workspace for generating short-form videos from trending topics, scripted text, stock assets, TTS, and overlays.

## What is in here

- Script generation and trend helpers (`script_generator.py`, `trends.py`, `produce_from_trends.py`)
- TTS/audio tooling (`tts_batch.py`, `mix_sfx_into_tts.py`, `make_sfx.py`)
- Video assembly/render scripts (`video_builder.py`, `assemble_video.py`, `overlay_*.py`)
- Stock/media handling utilities (`pexels_fetch.py`, `sound_fetcher.py`, `stock/`, `stock_clips/`)
- Upload/integration scripts (`youtube_uploader.py`, `upload_youtube.py`)

## Typical workflow (high level)

1. Collect or classify trend/topic input
2. Generate script/captions
3. Produce narration audio + optional effects
4. Build and render final short video
5. Export/upload output

## Notes

This repo is an active experimentation sandbox with many utility scripts and iterations.
Use it as a toolkit workspace rather than a single polished app entrypoint.
