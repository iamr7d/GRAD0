"""Find and cache high-quality stock footage from Pexels.

Only landscape 1080p (or better, downscaled choice) MP4 files at least `min_seconds` long are accepted.
Files are cached under bucket/media/video/<id>.mp4 and reused across stories.
Pexels asks for attribution: every result carries the videographer's name and page.
"""
import json
import re
import time
from pathlib import Path

import requests

from .config import PEXELS_API_KEY, VIDEO_DIR, media_url

API = "https://api.pexels.com/videos/search"
INDEX = VIDEO_DIR / "index.json"


def _load_index():
    try:
        return json.loads(INDEX.read_text())
    except Exception:
        return {}


def _save_index(idx):
    tmp = INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(idx, indent=2))
    tmp.replace(INDEX)


def _best_file(video, min_width=1920):
    """Pick the smallest landscape MP4 that is still at least 1080p, preferring 25/30 fps."""
    files = [f for f in video.get("video_files", [])
             if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")
             and f["width"] >= min_width and f["width"] / f["height"] >= 1.7]
    if not files:
        return None
    files.sort(key=lambda f: (f["width"], abs((f.get("fps") or 30) - 30)))
    return files[0]


def _relevance(video, words):
    slug = (video.get("url") or "").lower()
    return sum(1 for w in words if w in slug)


def search(query, min_seconds=8, max_seconds=60, per_page=20):
    """Return candidate videos for `query`, best first. Each entry has the chosen file."""
    if not PEXELS_API_KEY:
        raise RuntimeError("PEXELS_API_KEY is not set (put it in .env)")
    r = requests.get(API, headers={"Authorization": PEXELS_API_KEY},
                     params={"query": query, "per_page": per_page, "orientation": "landscape", "size": "large"},
                     timeout=15)
    r.raise_for_status()
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 2]
    out = []
    for v in r.json().get("videos", []):
        if not (min_seconds <= (v.get("duration") or 0) <= max_seconds):
            continue
        f = _best_file(v)
        if f:
            out.append({"video": v, "file": f, "score": _relevance(v, words)})
    out.sort(key=lambda c: (-c["score"], -c["video"].get("duration", 0)))
    return out


def fetch(query, min_seconds=8, avoid_ids=()):
    """Download (or reuse) the best matching clip. Returns a dict for the run-of-show, or None."""
    idx = _load_index()
    for cand in search(query, min_seconds=min_seconds):
        vid = str(cand["video"]["id"])
        if vid in avoid_ids:
            continue
        path = VIDEO_DIR / f"{vid}.mp4"
        if not path.exists():
            tmp = path.with_suffix(".part")
            with requests.get(cand["file"]["link"], stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as fh:
                    for chunk in resp.iter_content(1 << 16):
                        fh.write(chunk)
            tmp.replace(path)
        user = cand["video"].get("user") or {}
        entry = {
            "id": vid, "query": query, "path": media_url(path),
            "width": cand["file"]["width"], "height": cand["file"]["height"],
            "duration": cand["video"].get("duration"),
            "credit": f"Video: {user.get('name', 'Pexels')} / Pexels", "source": cand["video"].get("url"),
            "fetched": int(time.time()),
        }
        idx[vid] = entry
        _save_index(idx)
        return entry
    return None


if __name__ == "__main__":
    import sys
    print(json.dumps(fetch(" ".join(sys.argv[1:]) or "city skyline night"), indent=2))
