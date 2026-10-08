"""Mouth movement for the on-screen anchor: a loudness curve per voice track.

For bucket/media/voice/<id>.mp3 it writes <id>.lip.json = {"fps": 25, "v": "0012579..."}:
one digit (0 = closed, 9 = wide open) per 40 ms. The broadcast page reads it next to the voice
and moves the anchor's mouth in time with the speech. New voices get one automatically (tts.py);
for voices made before this existed:

    python -m channel.lipsync
"""
import json
import subprocess
from pathlib import Path

import numpy as np

from .config import FFMPEG, VOICE_DIR

FPS = 25
RATE = 8000


def lip_path(voice: Path) -> Path:
    return voice.with_suffix(".lip.json")


def write(voice: Path) -> Path:
    raw = subprocess.run([FFMPEG, "-loglevel", "error", "-i", str(voice), "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768
    step = RATE // FPS
    n = len(pcm) // step
    rms = np.sqrt(np.mean(pcm[: n * step].reshape(n, step) ** 2, axis=1) + 1e-9) if n else np.zeros(0)
    db = 20 * np.log10(rms)
    level = np.clip((db + 45) / 30, 0, 1)                          # -45 dBFS closed .. -15 dBFS wide open
    level = np.convolve(level, [0.25, 0.5, 0.25], mode="same")     # soften frame-to-frame jitter
    out = lip_path(voice)
    out.write_text(json.dumps({"fps": FPS, "v": "".join(str(int(round(x * 9))) for x in level)}))
    return out


def backfill():
    made = 0
    for f in sorted(VOICE_DIR.glob("*.mp3")):
        if not lip_path(f).exists():
            try:
                write(f)
                made += 1
            except subprocess.CalledProcessError as e:
                print(f"Skipped {f.name}: {e}")
    print(f"Made lip-sync data for {made} voice tracks.")


if __name__ == "__main__":
    backfill()
