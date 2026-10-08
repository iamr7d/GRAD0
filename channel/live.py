"""Broadcast Prime Earth News as a live stream on a website.

Plays the channel in Chrome in the background (the same page OBS shows), encodes it with
ffmpeg into an HLS live stream in bucket/live/, and the broadcast server shows it on the
watch page at http://127.0.0.1:8000/watch.

    python -m channel.live                  # stream locally: open http://127.0.0.1:8000/watch
    python -m channel.live --public         # also give it a public https address (Cloudflare tunnel)
    python -m channel.live --rtmp URL       # also push to YouTube Live / any RTMP server
    python -m channel.live --hd             # 1080p instead of 720p (needs a stronger PC and upload)

Keep the newsroom running too (python -m channel.run, or start_channel.bat) so the news stays fresh.
--public needs cloudflared once: winget install --id Cloudflare.cloudflared
The address it prints (https://<words>.trycloudflare.com/watch) changes each time it starts.
Stop with Ctrl+C.
"""
import argparse
import asyncio
import base64
import re
import shutil
import subprocess
import sys
import threading
import time

from .config import BUCKET, FFMPEG
from .render_reel import DEFAULT_BASE, FPS, H, RECORD_JS, W, check_ready, ensure_server, launch_browser

LIVE = BUCKET / "live"
RESTART_HOURS = 6  # restart Chrome now and then so a 24/7 stream doesn't slowly use up memory


def ffmpeg_cmd(hd, rtmp):
    w, h, kbps = (1920, 1080, 6000) if hd else (1280, 720, 3000)
    hls = ("hls_time=2:hls_list_size=12:hls_flags=delete_segments+independent_segments+omit_endlist"
           ":hls_start_number_source=epoch:hls_segment_filename=seg_%d.ts")
    cmd = [FFMPEG, "-loglevel", "error", "-fflags", "+genpts", "-i", "pipe:0",
           "-vf", f"fps={FPS},scale={w}:{h}:flags=bicubic,format=yuv420p",
           "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{kbps}k", "-maxrate", f"{kbps}k",
           "-bufsize", f"{kbps * 2}k", "-g", str(FPS * 2), "-keyint_min", str(FPS * 2), "-sc_threshold", "0",
           "-af", "aresample=48000:async=1", "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
           "-map", "0:v", "-map", "0:a"]
    if rtmp:  # one encode, two destinations; if YouTube drops, the website keeps going
        return cmd + ["-flags", "+global_header", "-f", "tee",
                      f"[f=hls:{hls}]stream.m3u8|[f=flv:onfail=ignore]{rtmp}"]
    return cmd + ["-f", "hls"] + [x for kv in hls.split(":") for x in ("-" + kv.split("=", 1)[0], kv.split("=", 1)[1])] + ["stream.m3u8"]


def clear_live():
    LIVE.mkdir(parents=True, exist_ok=True)
    for f in LIVE.iterdir():
        if f.suffix in (".ts", ".m3u8", ".tmp"):
            f.unlink(missing_ok=True)


async def session(base, hd, rtmp, show, hours):
    """One run of Chrome + ffmpeg. Returns normally after `hours`; raises if something breaks."""
    from playwright.async_api import async_playwright

    clear_live()
    enc = subprocess.Popen(ffmpeg_cmd(hd, rtmp), cwd=LIVE, stdin=subprocess.PIPE)
    broken = asyncio.Event()

    def chunk(b64):
        try:
            enc.stdin.write(base64.b64decode(b64))
            enc.stdin.flush()
        except OSError:
            broken.set()

    try:
        async with async_playwright() as p:
            browser = await launch_browser(p, show)
            page = await browser.new_page(viewport={"width": W, "height": H})
            page.on("crash", lambda _: broken.set())
            await page.expose_function("penChunk", chunk)
            await page.goto(base, wait_until="load")
            await page.wait_for_timeout(1500)
            await page.evaluate(RECORD_JS, {"w": W, "h": H, "fps": FPS, "slice": 500, "vbps": 8e6, "waitSting": False})
            print(f"ON AIR  ({time.strftime('%H:%M')})  watch page: {base.rstrip('/')}/watch")
            t_end = time.time() + hours * 3600
            while time.time() < t_end:
                if broken.is_set() or enc.poll() is not None:
                    raise RuntimeError("the browser or the encoder stopped")
                await asyncio.sleep(2)
            await browser.close()
    finally:
        try:
            enc.stdin.close()
        except OSError:
            pass
        try:
            enc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            enc.kill()


def start_tunnel(base):
    """Free public https address via Cloudflare's quick tunnel (no account needed)."""
    exe = shutil.which("cloudflared")
    if not exe:
        sys.exit("--public needs cloudflared. Install it once with:  winget install --id Cloudflare.cloudflared\n"
                 "then open a new PowerShell window and run this again.")
    proc = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", base.rstrip("/")],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    found = threading.Event()

    def read():
        for line in proc.stdout:  # keep draining so cloudflared never blocks on a full pipe
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not found.is_set():
                found.set()
                print(f"\nPUBLIC WATCH PAGE:  {m.group(0)}/watch\n(share this link; it changes each time you start)\n")

    threading.Thread(target=read, daemon=True).start()
    if not found.wait(30):
        print("Cloudflare tunnel hasn't given an address yet; it will print here when it does.")
    return proc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--public", action="store_true", help="publish the watch page on a public https address")
    ap.add_argument("--rtmp", help="also stream to this RTMP URL (e.g. rtmp://a.rtmp.youtube.com/live2/<stream key>)")
    ap.add_argument("--hd", action="store_true", help="1080p at 6 Mbps instead of 720p at 3 Mbps")
    ap.add_argument("--show", action="store_true", help="show the Chrome window instead of running it in the background")
    ap.add_argument("--base", default=DEFAULT_BASE, help="broadcast server address")
    a = ap.parse_args()

    check_ready()
    server = ensure_server(a.base, can_start=a.base == DEFAULT_BASE)
    tunnel = start_tunnel(a.base) if a.public else None
    try:
        while True:
            try:
                asyncio.run(session(a.base, a.hd, a.rtmp, a.show, RESTART_HOURS))
                print("Scheduled restart of the stream ...")
            except KeyboardInterrupt:
                raise
            except Exception as e:  # keep the channel on air: restart after any failure
                print(f"Stream stopped ({e}); restarting in 5 s ...")
                time.sleep(5)
    except KeyboardInterrupt:
        print("\nOff air.")
    finally:
        for proc in (tunnel, server):
            if proc:
                proc.terminate()
        clear_live()


if __name__ == "__main__":
    main()
