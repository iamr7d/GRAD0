"""Shared settings for the PEN News channel. Paths are relative to the repo, keys come from the environment."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUCKET = ROOT / "bucket"
QUEUE_FILE = BUCKET / "news" / "queue" / "run_of_show.json"
MEDIA = BUCKET / "media"
VIDEO_DIR = MEDIA / "video"
VOICE_DIR = MEDIA / "voice"
MUSIC_DIR = MEDIA / "music"
MODELS = ROOT / "channel" / "models"
FFMPEG = os.getenv("FFMPEG", str(ROOT / "ffmpeg-git-20240629-amd64-static" / "ffmpeg"))
FFPROBE = os.getenv("FFPROBE", str(ROOT / "ffmpeg-git-20240629-amd64-static" / "ffprobe"))

try:  # optional .env in the repo root (never committed)
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
TTS_VOICE = os.getenv("PEN_TTS_VOICE", "bm_george")          # Kokoro voice
EDGE_VOICE = os.getenv("PEN_EDGE_VOICE", "en-GB-RyanNeural")  # Edge TTS fallback voice

for d in (VIDEO_DIR, VOICE_DIR, MUSIC_DIR, MODELS):
    d.mkdir(parents=True, exist_ok=True)


def media_url(path: Path) -> str:
    """Turn a file under bucket/ into the URL the broadcast page loads it from."""
    return "/" + Path(path).resolve().relative_to(ROOT).as_posix()
