"""Bring every existing voice track to broadcast loudness (-16 LUFS) in place.
    python -m channel.normalize_voices
"""
import subprocess

from .config import FFMPEG, VOICE_DIR
from .tts import LOUDNORM

files = sorted(VOICE_DIR.glob("*.mp3"))
for f in files:
    tmp = f.with_suffix(".norm.mp3")
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(f), "-af", LOUDNORM, "-ar", "44100", "-ac", "1", "-b:a", "128k", str(tmp)])
    if r.returncode == 0:
        tmp.replace(f)
print(f"Normalised {len(files)} voice tracks.")
