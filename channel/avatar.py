"""Realistic AI anchor: turn one presenter photo + each story's voice into a talking-head video.

Uses SadTalker (open source, runs on an NVIDIA GPU; about 1-2 minutes per story on an RTX 3050)
in its own folder and Python environment. For every story in the run of show that has a voice
but no anchor video yet (newest first), it writes bucket/media/anchor/<voice id>.mp4 and stores
its address as extra_data.anchor_url. The broadcast page plays it in the anchor box in sync
with the voice; stories without one fall back to the illustrated anchor.

    python -m channel.avatar --watch      # keep making anchor clips as stories arrive (own window)
    python -m channel.avatar --once       # do what's waiting, then stop

Settings in .env (paths on this PC):
    PEN_SADTALKER_DIR=C:\\Users\\rahul\\SadTalker            # the SadTalker checkout (with checkpoints/)
    PEN_SADTALKER_PYTHON=C:\\Users\\rahul\\SadTalker\\venv\\Scripts\\python.exe
    PEN_ANCHOR_IMAGE=bucket/media/anchor/anchor.png         # front-facing presenter photo (default)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .config import FFMPEG, MEDIA, QUEUE_FILE, ROOT, media_url

ANCHOR_DIR = MEDIA / "anchor"
ANCHOR_DIR.mkdir(parents=True, exist_ok=True)


def _settings():
    st = Path(os.getenv("PEN_SADTALKER_DIR", ""))
    py = os.getenv("PEN_SADTALKER_PYTHON") or str(st / "venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python"))
    img = Path(os.getenv("PEN_ANCHOR_IMAGE", "")) if os.getenv("PEN_ANCHOR_IMAGE") else None
    if img and not img.is_absolute():
        img = ROOT / img
    if not img:
        img = next((p for p in (ANCHOR_DIR / n for n in ("anchor.png", "anchor.jpg", "anchor.jpeg")) if p.exists()), ANCHOR_DIR / "anchor.png")
    return st, Path(py), img


def check():
    st, py, img = _settings()
    problems = []
    if not (st / "inference.py").exists():
        problems.append(f"SadTalker not found: set PEN_SADTALKER_DIR in .env (now '{st}')")
    if not py.exists():
        problems.append(f"SadTalker's Python not found: set PEN_SADTALKER_PYTHON in .env (now '{py}')")
    if not img.exists():
        problems.append(f"No presenter photo: put a front-facing portrait at {img}")
    return problems


def _voice_file(audio_url):
    return ROOT / audio_url.lstrip("/")


def render(voice: Path, out: Path, max_seconds=0):
    """Run SadTalker for one voice track; writes `out` (H.264 MP4 with the voice as its audio).
    max_seconds > 0 animates only the start of the voice (the 3-minute reel plays ~17 s per story);
    the page shows the illustrated anchor once a short clip runs out."""
    st, py, img = _settings()
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "voice.wav"
        cut = ["-t", str(max_seconds)] if max_seconds else []
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(voice), *cut, "-ac", "1", "-ar", "16000", str(wav)], check=True)
        cmd = [str(py), "inference.py", "--driven_audio", str(wav), "--source_image", str(img),
               "--result_dir", tmp, "--preprocess", "full", "--still", "--size", "256", "--expression_scale", "1.0"]
        if os.getenv("PEN_ANCHOR_ENHANCE", "1") != "0":
            cmd += ["--enhancer", "gfpgan"]   # sharper face; set PEN_ANCHOR_ENHANCE=0 if it's too slow
        subprocess.run(cmd, cwd=st, check=True)
        made = sorted(Path(tmp).rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
        if not made:
            raise RuntimeError("SadTalker made no video")
        part = out.with_suffix(".part.mp4")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(made[-1]), "-c:v", "libx264", "-crf", "20",
                        "-preset", "medium", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                        "-movflags", "+faststart", str(part)], check=True)
        part.replace(out)


def _save(item_id, url):
    latest = json.loads(QUEUE_FILE.read_text())
    for q in latest:
        if q.get("id") == item_id:
            q.setdefault("extra_data", {})["anchor_url"] = url
    tmp = QUEUE_FILE.with_suffix(".avatar.tmp")
    tmp.write_text(json.dumps(latest, indent=2))
    tmp.replace(QUEUE_FILE)


def run_once(limit=None, max_seconds=0, ready_only=False):
    try:
        queue = json.loads(QUEUE_FILE.read_text())
    except (OSError, ValueError):
        return 0
    voiced = [q for q in queue if (q.get("extra_data") or {}).get("audio_url")]
    if ready_only:   # the first `limit` stories with footage, in run-of-show order: the ones a reel plays
        voiced = [q for q in voiced if q["extra_data"].get("video_url") or q["extra_data"].get("photo_url")][:limit]
    else:
        voiced.sort(key=lambda q: -(q.get("timestamp") or 0))     # newest stories first
    todo = [q for q in voiced if not q["extra_data"].get("anchor_url")]
    done = 0
    for item in todo[:limit]:
        voice = _voice_file(item["extra_data"]["audio_url"])
        if not voice.exists():
            continue
        out = ANCHOR_DIR / f"{voice.stem}.mp4"
        try:
            if not out.exists():
                t0 = time.time()
                print(f"Anchor clip for: {item.get('main_heading', '')[:70]}")
                render(voice, out, max_seconds)
                print(f"  done in {time.time() - t0:.0f} s")
            _save(item["id"], media_url(out))
            done += 1
        except Exception as e:
            print(f"  failed: {e}")
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--watch", action="store_true", help="keep going as new stories arrive")
    ap.add_argument("--once", action="store_true", help="make what's waiting, then stop")
    ap.add_argument("--limit", type=int, default=None, help="at most this many clips per pass (newest first)")
    ap.add_argument("--max-seconds", type=float, default=float(os.getenv("PEN_ANCHOR_MAX_SECONDS", "0")),
                    help="animate only the first N seconds of each voice (e.g. 18 for the 3-minute reel)")
    a = ap.parse_args()
    problems = check()
    if problems:
        sys.exit("Realistic anchor isn't set up yet:\n  - " + "\n  - ".join(problems))
    if not shutil.which(FFMPEG) and not Path(FFMPEG).exists():
        sys.exit("ffmpeg not found")
    while True:
        n = run_once(a.limit, a.max_seconds, ready_only=bool(a.limit))
        if not a.watch:
            print(f"Made {n} anchor clips.")
            break
        if not n:
            time.sleep(30)


if __name__ == "__main__":
    main()
