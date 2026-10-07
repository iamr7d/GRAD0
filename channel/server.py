"""Broadcast server for the Prime Earth News playout page.

Serves only what the page needs:
  /                      -> channel/web/broadcast.html
  /<file>                -> other files in channel/web (glass3d.js)
  /bucket/news/...       -> run of show, ticker
  /bucket/media/...      -> footage, voice tracks, music
  POST /sync             -> records what is on air (bucket/news/queue/playout_status.json)
Nothing else in the repo (code, .env, keys) is reachable.

    python -m channel.server            # http://127.0.0.1:8000/
    python -m channel.server --host 0.0.0.0 --port 8000   # reachable from OBS on another machine
Open http://127.0.0.1:8000/?autoplay=1 in an OBS browser source (1920x1080).
"""
import argparse
import json
import time

from flask import Flask, abort, jsonify, request, send_from_directory

from .config import BUCKET, ROOT

WEB = ROOT / "channel" / "web"
STATUS = BUCKET / "news" / "queue" / "playout_status.json"
app = Flask(__name__)


@app.after_request
def no_cache(resp):
    if request.path.endswith((".json", ".txt", ".html")) or request.path == "/":
        resp.headers["Cache-Control"] = "no-store"
    return resp


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
