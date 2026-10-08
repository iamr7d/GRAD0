"""Run the channel back end: fetch real news, then voice it and attach footage, on a loop.

    python -m channel.run              # every 5 minutes
    python -m channel.run --every 120  # every 2 minutes
    python -m channel.run --no-llm     # skip Ollama, read feed text as written
    python -m channel.run --once       # one cycle, then exit (e.g. before render_reel)
"""
import argparse
import time

from . import newsroom, produce
from .config import check_ffmpeg

ap = argparse.ArgumentParser()
ap.add_argument("--every", type=int, default=300)
ap.add_argument("--no-llm", action="store_true")
ap.add_argument("--once", action="store_true")
a = ap.parse_args()
check_ffmpeg()
while True:
    try:
        newsroom.update_queue(use_llm=not a.no_llm)
        produce.run_once()
    except Exception as e:
        print(f"Cycle failed: {e}")
    if a.once:
        break
    time.sleep(a.every)
