"""A presenter-led segment: one presenter video (e.g. a HeyGen anchor on green) in the anchor box, with
footage and lower thirds cut to what he says. Think "the first minute of the hour": titles, the anchor
reads the top stories, end card.

    python -m channel.show tools\\show_first_minute.json      # prepare footage + clip
    python -m channel.render_reel --seconds 60 --params show=1  # render it

The spec lists the presenter video and timed cues ({t, cat, head, sub, query} or {t, query, keep: true} to
change only the footage). Footage comes from Pexels by query; the prepared show is written to
bucket/media/anchor/show.json for the page.
"""
import json
import sys
from pathlib import Path

from . import pexels
from .avatar import ANCHOR_DIR, import_presenter
from .config import ROOT


def build(spec_path: Path):
    spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))   # -sig: Notepad / PowerShell may add a BOM
    clip = Path(spec["clip"]).expanduser()
    if not clip.is_absolute():
        clip = ROOT / clip
    # "cover": [[x, y, w, h], ...] fractions of the frame painted in the screen colour (e.g. HeyGen's
    # watermark), so the green key removes them along with the background
    colour = spec.get("screen_colour", "0x089146")
    boxes = ",".join(f"drawbox=x=iw*{x}:y=ih*{y}:w=iw*{w}:h=ih*{h}:color={colour}:t=fill" for x, y, w, h in spec.get("cover", []))
    import_presenter(clip, "show", boxes)   # -> bucket/media/anchor/heygen_show.(mp4|webm), voice at -16 LUFS
    made = next(ANCHOR_DIR.glob("heygen_show.*"))
    cues, used = [], set()
    for c in spec["cues"]:
        got = pexels.fetch(c["query"], avoid_ids=tuple(used)) if c.get("query") else None
        if c.get("query") and not got:
            print(f"  no footage for '{c['query']}'")
        if got:
            used.add(got["id"])
        cues.append({**{k: v for k, v in c.items() if k != "query"},
                     "media": got["path"] if got else "", "credit": got["credit"] if got else ""})
        print(f"  {c['t']:5.1f}s  {c.get('head') or '(footage)':60.60s} {got['path'] if got else ''}")
    out = {"clip": "/bucket/media/anchor/" + made.name, "cues": cues, "title": spec.get("title", "")}
    if spec.get("ticker"):
        out["ticker"] = spec["ticker"]
    (ANCHOR_DIR / "show.json").write_text(json.dumps(out, indent=2))
    print(f"Show ready: {ANCHOR_DIR / 'show.json'}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    build(Path(sys.argv[1]))
