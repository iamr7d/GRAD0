# Prime Earth News (GRAD0) – handoff for the next assistant

Repo: https://github.com/iamr7d/GRAD0 · working branch: `r7d/zen-volta-pnyy4f`
Owner runs everything on **Windows 11** (PowerShell, Python 3.12, OBS 32) at `C:\Users\rahul\GRAD0`.
Goal right now: record a **~3 minute** news video in OBS to post on LinkedIn.

## What the system is
An automated English TV news channel branded **Prime Earth News.AI** (red block logo: PRIME / EARTH white, NEWS black, ".AI" dark red, Montserrat Black).

```
RSS feeds ──► channel/newsroom.py ──► bucket/news/queue/run_of_show.json
                  (real stories only, opening paragraphs of each article, source + link kept)
run_of_show ──► channel/produce.py ──► voice (channel/tts.py: Kokoro local TTS, Edge TTS fallback, -16 LUFS)
                                    └► footage (channel/pexels.py 1080p video; channel/unsplash.py photo fallback)
                                         search terms from channel/visuals.py (topic → literal stock query)
channel/run.py = newsroom + produce every 5 min
channel/server.py (Flask, 127.0.0.1:8000) serves ONLY channel/web/, bucket/news/, bucket/media/ + POST /sync
channel/web/broadcast.html = the on-air page (OBS browser source)
```

### On-air page (`channel/web/broadcast.html`)
- "Glass and light" design (modelled on 5 News 2026): flat frosted-glass UI, Plus Jakarta Sans text.
- Opening titles: WebGL 3D red glass logo block (`channel/web/glass3d.js`, built from `channel/web/src/glass3d.js` with esbuild; three.js bundled, no CDN).
- Top-right bug: the logo on a glassmorphic CSS 3D cube, front-facing, flips every ~6 s (logo on all faces).
- Bottom ticker: label flips LATEST → time → ● LIVE; scrolls live headlines.
- Lower third: full width, word-by-word headline, rotating second line, red progress line, footage credit bottom-right.
- Breaking (`type: "breaking"`): red glass panel takeover → red banner.
- Audio: `channel/web/audio/bed.m4a` (original synthesized music bed, -20 LUFS) ducks under the anchor voice; `sting.m4a` on titles/end card.
- URL params: `?autoplay=1` (no click needed – use in OBS), `?reel=60` or `?reel=180` (fixed showreel then ends on logo, `document.title` becomes "REEL DONE"). No `reel` = continuous loop.

### Secrets
`.env` in repo root (gitignored), never commit or paste keys:
```
PEXELS_API_KEY=...
UNSPLASH_ACCESS_KEY=...
```
The owner's Pexels and Unsplash keys were pasted in chat earlier → advise regenerating them.
The old ElevenLabs and Pexels keys that were committed in `news/main_graph.py` and `stream/.env` are removed from the code but remain in git history, so they must be revoked/rotated.

## How the owner runs it (Windows)
Always `cd C:\Users\rahul\GRAD0` first (PowerShell often opens in `C:\WINDOWS\system32`). ffmpeg must be on PATH (`winget install ffmpeg`); config finds it automatically.

Easiest: double-click `start_channel.bat` (git pull, opens "Newsroom" and "Broadcast server" windows, opens the page).

Manual, two separate windows that stay open:
```powershell
cd C:\Users\rahul\GRAD0; python -m channel.run --no-llm      # window 1 (drop --no-llm if Ollama runs on :11435)
cd C:\Users\rahul\GRAD0; python -m channel.server            # window 2
```
Useful one-offs:
```powershell
python -m channel.normalize_voices        # bring old voice files to -16 LUFS
python -m channel.refresh_footage         # forget clip choices so produce re-picks
del bucket\news\queue\run_of_show.json; del bucket\news\queue\seen_stories.json   # start the queue fresh
```

### Rendering the 3-minute video to MP4 (no OBS)
Double-click `render_reel.bat`, or:
```powershell
cd C:\Users\rahul\GRAD0; pip install playwright      # once; uses the installed Google Chrome
python -m channel.render_reel                           # 3-minute reel -> renders\prime_earth_news_<time>.mp4
python -m channel.render_reel --seconds 60 --show       # 1-minute reel, in a visible window
```
`channel/render_reel.py` opens `/?reel=180` in Chrome in the background, records the tab (picture via tab capture, sound mixed from the page's audio elements, so speakers aren't needed), stops after the logo end card and converts to 1920x1080 30 fps H.264/AAC MP4 with ffmpeg. It starts the broadcast server itself if it isn't running. Needs Google Chrome: Playwright's own Chromium can't play the MP4 footage or AAC audio. Takes about as long as the reel.

### Live stream on a website
Double-click `go_live.bat` (starts the newsroom, then the stream), or:
```powershell
winget install --id Cloudflare.cloudflared            # once, for the public link; then open a new PowerShell
cd C:\Users\rahul\GRAD0; python -m channel.live --public
```
`channel/live.py` plays the channel (`/` without `reel`, so it loops forever) in background Chrome, captures it like `render_reel`, and pipes it into ffmpeg, which writes a 720p30 3 Mbps HLS live stream to `bucket/live/` (`--hd` = 1080p 6 Mbps). `channel/server.py` serves it with the watch page at `/watch` (`channel/web/watch.html`, hls.js vendored as `channel/web/hls.min.js`; headlines list with source links from the run of show). `--public` runs a free Cloudflare quick tunnel and prints `https://<random>.trycloudflare.com/watch`; the address changes on every start. Visitors through the tunnel (requests carrying `Cf-Connecting-Ip`) can only GET `/watch`, `/live/*`, `/hls.min.js` and the run of show; the studio page, media files and `/sync` stay local. `--rtmp rtmp://a.rtmp.youtube.com/live2/<key>` also pushes the same encode to YouTube Live (key goes on the command line, never in chat or git). The stream restarts itself after a failure and every 6 hours. Permanent address on an own domain (DNS on Cloudflare): run once `python -m channel.setup_domain live.example.com` (browser login, creates tunnel `prime-earth-news`, routes DNS, writes gitignored `tunnel.json`); after that `--public`/`go_live.bat` use that address and the bare domain redirects to `/watch`. It only runs while the PC is on; 24/7 needs a cloud VM (next step).

### Recording the 3-minute video in OBS (manual alternative)
1. Queue should have ≥ 9 stories with voice + footage (check: `python -c "import json;q=json.load(open('bucket/news/queue/run_of_show.json'));print(sum(1 for i in q if i['extra_data'].get('audio_url') and i['extra_data'].get('video_url')),'ready of',len(q))"`).
2. OBS → Browser source: URL `http://127.0.0.1:8000/?autoplay=1&reel=180`, 1920×1080, tick "Control audio via OBS"; right-click → Transform → Fit to screen. Only one Browser source.
3. Audio Mixer → ⋮ → Advanced Audio Properties → Browser → "Monitor and Output" to hear it.
4. Settings → Output → recording format MP4. Refresh the source, Start Recording, stop at the logo end card (~3:05). File → Show Recordings.

## Known issues / pitfalls seen
- Commands fail with "No module named channel" when not run from `GRAD0`.
- Black OBS preview = server window closed, or wrong URL. Ctrl+C stops a program; users accidentally stopped the server by reusing its window.
- Footage is topic-matched stock (Pexels), not real event footage.
- With `--no-llm` the anchor reads the article's opening paragraphs; some paywalled sites fall back to the one-line summary.
- Development tested in a Linux sandbox that could NOT reach news sites, Pexels or Unsplash; real network runs only on the owner's PC.

## Possible next steps
- Done: `python -m channel.render_reel` burns the reel to MP4 (see above).
- Cloud VM for a 24/7 stream that doesn't need the PC on.
- Done: removed the legacy `server.py`, `server_fastapi.py`, `overlays/server.py` (exposed the whole folder incl. `.env`), `news/main_graph.py` (invented news), committed logs and caches.
- Design previews (claude.ai artifacts) are separate from the repo; the repo page is the source of truth.
