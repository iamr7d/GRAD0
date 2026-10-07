"""Text to speech for the anchor voice.

Primary: Kokoro (Apache 2.0, runs locally on CPU or GPU) through the kokoro-onnx package.
Fallback: Edge TTS (Microsoft's free read-aloud voices; unofficial, so treat it as a backup).
Output is an MP3 under bucket/media/voice/.
"""
import asyncio
import hashlib
import subprocess
import wave
from pathlib import Path

import requests

from .config import EDGE_VOICE, FFMPEG, FFPROBE, MODELS, TTS_VOICE, VOICE_DIR, media_url

KOKORO_FILES = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}
_kokoro = None
# broadcast loudness for speech: -16 LUFS, peaks under -1.5 dBTP, light high-pass and compression
LOUDNORM = "highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,loudnorm=I=-16:TP=-1.5:LRA=7"


def _ensure_models():
    for name, url in KOKORO_FILES.items():
        p = MODELS / name
        if not p.exists():
            print(f"Downloading {name} ...")
            tmp = p.with_suffix(".part")
            with requests.get(url, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in r.iter_content(1 << 20):
                        fh.write(chunk)
            tmp.replace(p)


def _kokoro_say(text, wav_path):
    global _kokoro
    from kokoro_onnx import Kokoro
    import numpy as np
    if _kokoro is None:
        _ensure_models()
        _kokoro = Kokoro(str(MODELS / "kokoro-v1.0.onnx"), str(MODELS / "voices-v1.0.bin"))
    lang = "en-gb" if TTS_VOICE.startswith("b") else "en-us"
    samples, sr = _kokoro.create(text, voice=TTS_VOICE, speed=1.0, lang=lang)
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())


def _edge_say(text, mp3_path):
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, EDGE_VOICE, rate="+0%").save(str(mp3_path)))


def duration(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def speak(text):
    """Synthesize `text`; returns {"path": url, "seconds": float, "engine": name} or None."""
    key = hashlib.sha1(f"v2|{TTS_VOICE}|{text}".encode()).hexdigest()[:12]   # v2: normalised audio
    mp3 = VOICE_DIR / f"{key}.mp3"
    if not mp3.exists():
        engine = "kokoro"
        try:
            wav = mp3.with_suffix(".wav")
            _kokoro_say(text, wav)
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(wav), "-af", LOUDNORM, "-ar", "44100", "-ac", "1", "-b:a", "128k", str(mp3)], check=True)
            wav.unlink(missing_ok=True)
        except Exception as e:
            print(f"Kokoro failed ({e}); trying Edge TTS")
            engine = "edge"
            try:
                raw = mp3.with_suffix(".raw.mp3")
                _edge_say(text, raw)
                subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(raw), "-af", LOUDNORM, "-ar", "44100", "-ac", "1", "-b:a", "128k", str(mp3)], check=True)
                raw.unlink(missing_ok=True)
            except Exception as e2:
                print(f"Edge TTS failed too: {e2}")
                return None
    return {"path": media_url(mp3), "seconds": round(duration(mp3), 2)}


if __name__ == "__main__":
    import sys
    print(speak(" ".join(sys.argv[1:]) or "Good evening. This is PEN News."))
