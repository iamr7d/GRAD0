"""Render the showreel straight to an MP4, no OBS needed.

Opens the broadcast page in Chrome, records the tab (picture and sound) while ?reel=SECONDS
plays, and converts the result to a LinkedIn-ready MP4 (1920x1080, 30 fps, H.264 + AAC).
Uses the broadcast server if it is running, otherwise starts one just for the render.

    python -m channel.render_reel                    # 3-minute reel -> renders/prime_earth_news_<time>.mp4
    python -m channel.render_reel --seconds 60       # 1-minute reel
    python -m channel.render_reel --show             # watch it record in a visible window

One-off setup: pip install playwright   (uses your installed Google Chrome; if you
don't have Chrome, also run: python -m playwright install chromium)
"""
import argparse
import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

from .config import FFMPEG, QUEUE_FILE, ROOT

OUT_DIR = ROOT / "renders"
W, H, FPS = 1920, 1080, 30
DEFAULT_BASE = "http://127.0.0.1:8000/"

# Runs inside the page: capture this tab, start the recorder, then start the reel.
RECORD_JS = """async ({w, h, fps}) => {
  document.getElementById("start").hidden = true;   // no click-to-start card in the recording
  document.getElementById("titles").style.visibility = "visible";   // open on the red title background
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 200))));
  const screen = await navigator.mediaDevices.getDisplayMedia({
    video: {width: w, height: h, frameRate: fps}, audio: false, preferCurrentTab: true});
  // Sound is taken straight from the page's music bed, anchor voice and sting (works without speakers).
  const ctx = new AudioContext({sampleRate: 48000}), mix = ctx.createMediaStreamDestination();
  for (const el of document.querySelectorAll("audio, video")) {
    const src = ctx.createMediaElementSource(el); src.connect(mix); src.connect(ctx.destination);
  }
  await ctx.resume();
  const stream = new MediaStream([...screen.getVideoTracks(), ...mix.stream.getAudioTracks()]);
  const types = ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm"];
  const mimeType = types.find(t => MediaRecorder.isTypeSupported(t));
  const rec = new MediaRecorder(stream, {mimeType, videoBitsPerSecond: 16e6, audioBitsPerSecond: 192e3});
  let saving = Promise.resolve();   // chunks are handed to Python one after another, in order
  rec.ondataavailable = e => {
    if (!e.data.size) return;
    saving = saving.then(async () => {
      const b = new Uint8Array(await e.data.arrayBuffer());
      let s = ""; for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode(...b.subarray(i, i + 0x8000));
      await window.penChunk(btoa(s));
    });
  };
  window.penStop = () => new Promise(r => { rec.onstop = () => r(saving); rec.stop(); });
  const t0 = performance.now();
  rec.start(1000);
  await new Promise(r => setTimeout(r, 300));
  start();
  // seconds before the reel starts (its sting begins); trimmed off when converting
  const sting = document.getElementById("sting");
  while (sting.paused) await new Promise(r => setTimeout(r, 10));
  return {mimeType, lead: Math.max(0, (performance.now() - t0) / 1000 - 0.05)};
}"""


def reachable(base):
    try:
        urllib.request.urlopen(base, timeout=5).read(1)
        return True
    except OSError:
        return False


def ensure_server(base, can_start):
    """Use the running broadcast server, or start one for the length of the render."""
    if reachable(base):
        return None
    if not can_start:
        sys.exit(f"Can't reach {base}.")
    print("Broadcast server isn't running; starting it for this render.")
    proc = subprocess.Popen([sys.executable, "-m", "channel.server"], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        time.sleep(0.5)
        if reachable(base):
            return proc
    proc.terminate()
    sys.exit(f"Couldn't start the broadcast server at {base}. Try: python -m channel.server")


def check_ready():
    try:
        q = json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        q = []
    ready = sum(1 for i in q if i.get("extra_data", {}).get("audio_url") and i.get("extra_data", {}).get("video_url"))
    print(f"Queue: {ready} of {len(q)} stories have voice and footage.")
    if not ready:
        sys.exit("Nothing ready to air yet. Leave the newsroom running until stories have voice and footage.")


async def record(url, raw, seconds, show):
    from playwright.async_api import async_playwright

    args = ["--autoplay-policy=no-user-gesture-required", "--auto-accept-this-tab-capture",
            "--auto-select-tab-capture-source-by-title=Prime", "--hide-scrollbars"]
    async with async_playwright() as p:
        exe = os.getenv("PEN_CHROME")  # optional: path to a specific Chrome/Chromium
        try:
            if exe:
                browser = await p.chromium.launch(executable_path=exe, headless=not show, args=args, ignore_default_args=["--mute-audio"])
            else:
                browser = await p.chromium.launch(channel="chrome", headless=not show, args=args, ignore_default_args=["--mute-audio"])
        except Exception:
            print("Google Chrome not found, using Playwright's Chromium (it can't play MP4 footage; install Chrome for the real look).")
            browser = await p.chromium.launch(headless=not show, args=args, ignore_default_args=["--mute-audio"])
        page = await browser.new_page(viewport={"width": W, "height": H})
        page.on("crash", lambda _: print("\nThe page crashed while recording."))
        out = open(raw, "wb")
        await page.expose_function("penChunk", lambda b64: out.write(base64.b64decode(b64)))
        await page.goto(url, wait_until="load")
        await page.wait_for_timeout(1500)  # fonts, 3D titles and first media settle
        info = await page.evaluate(RECORD_JS, {"w": W, "h": H, "fps": FPS})
        print(f"Recording ({info['mimeType']}) ...")
        t0 = time.time()
        limit = seconds + 120
        while await page.title() != "REEL DONE":
            if time.time() - t0 > limit:
                print("Reel did not finish in time; stopping anyway.")
                break
            await asyncio.sleep(1)
            print(f"\r  {int(time.time() - t0)} s", end="", flush=True)
        print()
        await page.wait_for_timeout(4500)  # hold on the end card while the music fades
        await page.evaluate("window.penStop()")
        out.close()
        await browser.close()
        return info["lead"]


def to_mp4(raw, mp4, lead=0.0):
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-ss", f"{lead:.3f}", "-i", str(raw),
           "-vf", f"fps={FPS},scale={W}:{H}:flags=lanczos,format=yuv420p,tpad=stop_mode=clone:stop_duration=3",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high",
           "-af", "aresample=48000:async=1", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-shortest", "-movflags", "+faststart", str(mp4)]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=int, default=180, help="reel length (default 180)")
    ap.add_argument("--base", default=DEFAULT_BASE, help="broadcast server address")
    ap.add_argument("--out", help="output MP4 path (default renders/prime_earth_news_<time>.mp4)")
    ap.add_argument("--show", action="store_true", help="record in a visible window instead of in the background")
    a = ap.parse_args()

    check_ready()
    server = ensure_server(a.base, can_start=a.base == DEFAULT_BASE)
    OUT_DIR.mkdir(exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M")
    mp4 = a.out or OUT_DIR / f"prime_earth_news_{stamp}.mp4"
    raw = OUT_DIR / f"raw_{stamp}.webm"
    try:
        lead = asyncio.run(record(f"{a.base.rstrip('/')}/?reel={a.seconds}", raw, a.seconds, a.show))
    finally:
        if server:
            server.terminate()
    print("Converting to MP4 ...")
    to_mp4(raw, mp4, lead)
    raw.unlink(missing_ok=True)
    print(f"Done: {mp4}")


if __name__ == "__main__":
    main()
