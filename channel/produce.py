"""Prepare every story in the run of show for air: anchor voice + high-quality footage.

Reads bucket/news/queue/run_of_show.json, fills in for each item:
  extra_data.audio_url / audio_seconds   (TTS of the anchor script)
  extra_data.video_url / video_credit    (local Pexels clip, 1080p+)
  extra_data.clips                        (up to 3 shots [{url, credit}] the page cuts between)
  display_duration                        (voice length + a short tail)
and writes the file back atomically. Run once, or with --watch to keep up with the newsroom.
"""
import argparse
import json
import time

from . import pexels, tts, unsplash, visuals
from .config import QUEUE_FILE

CLIPS_PER_STORY = 3   # stock shots per story; the broadcast page cuts between them


def script_for(item):
    extra = item.get("extra_data") or {}
    if extra.get("anchor_script"):
        return extra["anchor_script"]
    parts = [item.get("main_heading", "").capitalize() + ".", item.get("content_text", "")]
    parts += [h if h.endswith(".") else h + "." for h in item.get("headlines", [])]
    return " ".join(p for p in parts if p.strip())


def prepare(item, used_ids):
    extra = item.setdefault("extra_data", {})
    changed = False
    if not extra.get("audio_url"):
        voice = tts.speak(script_for(item))
        if voice:
            extra["audio_url"], extra["audio_seconds"] = voice["path"], voice["seconds"]
            item["display_duration"] = max(8, round(voice["seconds"] + 1.5))
            changed = True
    clips = extra.get("clips") or ([{"url": extra["video_url"], "credit": extra.get("video_credit", "")}]
                                   if extra.get("video_local") else [])
    if len(clips) < CLIPS_PER_STORY and not extra.get("clips_tried"):
        queries = ([extra["visual_keyword"]] if extra.get("visual_source") == "llm" else []) + \
                  visuals.search_terms(item.get("main_heading", ""), item.get("content_text", ""), extra.get("category", "World"))
        errored = False
        for q in dict.fromkeys(q for q in queries if q):   # several shots per story, cut together on air
            try:
                found = pexels.fetch_many(q, CLIPS_PER_STORY - len(clips), avoid_ids=used_ids)
            except Exception as e:
                print(f"Pexels error for '{q}': {e}")
                errored = True
                continue
            for clip in found:
                used_ids.add(clip["id"])
                clips.append({"url": clip["path"], "credit": clip["credit"]})
                if not extra.get("video_local"):
                    extra.update(video_local=True, video_url=clip["path"], media_url=clip["path"], media_type="video",
                                 video_credit=clip["credit"], video_source=clip["source"])
            if len(clips) >= CLIPS_PER_STORY:
                break
        if not errored:
            extra["clips_tried"] = True    # don't search Pexels again for this story if fewer were found
            changed = True
        if clips and clips != extra.get("clips"):
            extra["clips"] = clips
            changed = True
        if not extra.get("video_local") and not extra.get("photo_url"):
            try:
                photo = unsplash.search(visuals.search_terms(item.get("main_heading", ""), item.get("content_text", ""), extra.get("category", "World"))[0])
            except Exception as e:
                print(f"Unsplash error: {e}")
                photo = None
            if photo:
                unsplash.mark_used(photo)
                extra.update(photo_url=photo["url"], media_url=photo["url"], media_type="image",
                             media_credit=photo["credit"], media_credit_html=photo["credit_html"])
                changed = True
    return changed


def _save(item):
    """Write one finished item back, re-reading first so nothing the newsroom added is lost."""
    latest = json.loads(QUEUE_FILE.read_text())
    for i, q in enumerate(latest):
        if q.get("id") == item["id"]:
            latest[i] = item
    tmp = QUEUE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(latest, indent=2))
    tmp.replace(QUEUE_FILE)


def run_once():
    if not QUEUE_FILE.exists():
        print("No run of show yet.")
        return
    queue = json.loads(QUEUE_FILE.read_text())
    used = {str((i.get("extra_data") or {}).get("video_url", "")).split("/")[-1].removesuffix(".mp4") for i in queue}
    done = 0
    for item in queue:
        if "Test AI News" in item.get("main_heading", ""):
            continue
        try:
            if prepare(item, used):
                _save(item)          # save each story as soon as it is ready
                done += 1
        except Exception as e:
            print(f"Could not prepare '{item.get('main_heading')}': {e}")
    print(f"Produced {done} stories.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true", help="keep checking for new stories")
    ap.add_argument("--every", type=int, default=30, help="seconds between checks in --watch mode")
    a = ap.parse_args()
    run_once()
    while a.watch:
        time.sleep(a.every)
        run_once()
