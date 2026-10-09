"""Broadcast server for the Prime Earth News playout page.

Serves only what the page needs:
  /                      -> channel/web/broadcast.html
  /<file>                -> other files in channel/web (glass3d.js)
  /bucket/news/...       -> run of show, ticker
  /bucket/media/...      -> footage, voice tracks, music
  POST /sync             -> records what is on air (bucket/news/queue/playout_status.json)
  /watch                 -> public watch page for the live stream (channel/web/watch.html)
  /live/...              -> the live stream's HLS playlist and segments (bucket/live, written by channel.live)
Nothing else in the repo (code, .env, keys) is reachable.
Visitors arriving through the public tunnel (python -m channel.live --public) only get the
watch page, the stream and the list of headlines; the studio page and /sync stay local.

    python -m channel.server            # http://127.0.0.1:8000/
    python -m channel.server --host 0.0.0.0 --port 8000   # reachable from OBS on another machine
Open http://127.0.0.1:8000/?autoplay=1 in an OBS browser source (1920x1080).
"""
import argparse
import json
import time

from flask import Flask, abort, jsonify, redirect, request, send_from_directory

from .config import BUCKET, MUSIC_DIR, ROOT

WEB = ROOT / "channel" / "web"
LIVE = BUCKET / "live"
PUBLIC = ("/watch", "/live/", "/hls.min.js", "/bucket/news/queue/run_of_show.json", "/favicon.ico")
STATUS = BUCKET / "news" / "queue" / "playout_status.json"
app = Flask(__name__)


@app.before_request
def public_guard():
    # Cloudflare's tunnel adds this header to every visitor's request; local OBS/Chrome requests don't have it.
    if request.headers.get("Cf-Connecting-Ip") and request.path == "/":
        return redirect("/watch")  # the bare domain opens the watch page
    if request.headers.get("Cf-Connecting-Ip") and not request.path.startswith(PUBLIC):
        abort(404)
    if request.headers.get("Cf-Connecting-Ip") and request.method != "GET":
        abort(405)


@app.after_request
def no_cache(resp):
    if request.path.endswith((".json", ".txt", ".html", ".m3u8")) or request.path in ("/", "/watch"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/watch")
def watch():
    return send_from_directory(WEB, "watch.html")


@app.get("/live/<path:name>")
def live(name):
    playlist = LIVE / "stream.m3u8"
    if name.endswith(".m3u8") and (not playlist.exists() or time.time() - playlist.stat().st_mtime > 30):
        abort(404)  # left over from a stream that has stopped: show "off air" instead of a frozen picture
    return send_from_directory(LIVE, name, conditional=True)


@app.get("/")
def index():
    return send_from_directory(WEB, "broadcast.html")


@app.get("/bucket/<area>/<path:name>")
def bucket(area, name):
    if area not in ("news", "media"):
        abort(404)
    return send_from_directory(BUCKET / area, name, conditional=True)


@app.get("/<path:name>")
def web(name):
    if name.startswith("src/"):
        abort(404)
    if name in ("audio/bed.m4a", "audio/sting.m4a"):
        # your own music wins: bucket/media/music/news_bed.mp3 (or .m4a) and news_sting.mp3, kept out of git
        stem = "news_bed" if name.endswith("bed.m4a") else "news_sting"
        for f in sorted(MUSIC_DIR.glob(stem + ".*")):
            return send_from_directory(MUSIC_DIR, f.name, conditional=True)
    return send_from_directory(WEB, name)


@app.post("/sync")
def sync():
    data = request.get_json(silent=True) or {}
    status = {"current_id": str(data.get("current_id", ""))[:32], "heading": str(data.get("heading", ""))[:300],
              "timestamp": data.get("timestamp"), "server_time": time.time()}
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(status, indent=2))
    return jsonify(ok=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    print(f"Prime Earth News on http://{a.host}:{a.port}/  (OBS: add ?autoplay=1)")
    app.run(host=a.host, port=a.port, threaded=True)
