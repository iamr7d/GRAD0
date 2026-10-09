"""Bring every existing voice track to broadcast loudness (-16 LUFS) in place.
    python -m channel.normalize_voices
"""
import subprocess

from .config import FFMPEG, VOICE_DIR, check_ffmpeg
from .tts import LOUDNORM

check_ffmpeg()
# skip leftovers from interrupted runs (.raw.mp3 / .norm.mp3)
files = sorted(f for f in VOICE_DIR.glob("*.mp3") if f.suffixes == [".mp3"])
done = 0
for f in files:
    tmp = f.with_suffix(".norm.mp3")
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(f), "-af", LOUDNORM, "-ar", "44100", "-ac", "1", "-b:a", "128k", str(tmp)])
    if r.returncode == 0:
        tmp.replace(f)
        done += 1
    else:
        tmp.unlink(missing_ok=True)
        print(f"Skipped {f.name}: ffmpeg could not read it")
print(f"Normalised {done} of {len(files)} voice tracks.")
