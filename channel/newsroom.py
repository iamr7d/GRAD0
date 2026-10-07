"""Real-time newsroom: pull the latest stories from RSS feeds into the run of show.

Only real reporting goes on air. Each item keeps the publisher, link and published time;
headline and summary come from the feed itself. If a local Ollama model is running, it
rewrites the summary into a short anchor script and picks a stock-footage search term,
but it is told to use only facts from the feed text.

Run once:   python -m channel.newsroom
Keep going: python -m channel.run   (newsroom + media/voice production every few minutes)
"""
import hashlib
import html
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

import feedparser
import requests

from .config import QUEUE_FILE

FEEDS = {
    "World": ["https://feeds.bbci.co.uk/news/world/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml",
              "https://feeds.npr.org/1004/rss.xml"],
    "Business": ["https://feeds.bbci.co.uk/news/business/rss.xml"],
    "Tech": ["https://feeds.bbci.co.uk/news/technology/rss.xml", "https://www.theverge.com/rss/index.xml"],
    "Science": ["https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"],
    "India": ["https://feeds.feedburner.com/ndtvnews-top-stories", "https://www.thehindu.com/news/national/feeder/default.rss"],
}
MAX_AGE_H = 12          # ignore older stories
MAX_QUEUE = 40          # stories kept in the run of show
OLLAMA = "http://127.0.0.1:11435/api/chat"
OLLAMA_MODEL = "mistral:latest"


def _clean(text):
    text = re.sub(r"<[^>]+>", " ", html.unescape(text or ""))
    return re.sub(r"\s+", " ", text).strip()


def _fetch(url, category):
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent": "PrimeEarthNews/1.0"})
        feed = feedparser.parse(r.content)
    except Exception as e:
        print(f"Feed failed {url}: {e}")
        return []
    out = []
    for e in feed.entries[:10]:
        try:
            ts = int(parsedate_to_datetime(e.get("published") or e.get("updated")).timestamp())
        except Exception:
            ts = int(time.time())
        if time.time() - ts > MAX_AGE_H * 3600:
            continue
        title = _clean(e.get("title"))
        if not title:
            continue
        out.append({"title": title, "summary": _clean(e.get("summary"))[:600], "link": e.get("link", ""),
                    "source": _clean(feed.feed.get("title", "")) or url, "published": ts, "category": category})
    return out


def fetch_all():
    jobs = [(u, c) for c, urls in FEEDS.items() for u in urls]
    with ThreadPoolExecutor(8) as ex:
        stories = [s for batch in ex.map(lambda a: _fetch(*a), jobs) for s in batch]
    stories.sort(key=lambda s: -s["published"])
    for s in stories:
        s["source"] = _short_source(s["source"])
    # drop near-duplicates (same first words from different outlets)
    seen, unique = set(), []
    for s in stories:
        key = " ".join(re.findall(r"[a-z]+", s["title"].lower())[:5])
        if key not in seen:
            seen.add(key); unique.append(s)
    # interleave outlets so one fast-posting site can't fill every slot
    by_src = {}
    for s in unique:
        by_src.setdefault(s["source"], []).append(s)
    mixed = []
    while any(by_src.values()):
        for src in list(by_src):
            if by_src[src]:
                mixed.append(by_src[src].pop(0))
    return mixed


SOURCE_NAMES = {"bbc": "BBC News", "al jazeera": "Al Jazeera", "npr": "NPR", "verge": "The Verge",
                "ndtv": "NDTV", "the hindu": "The Hindu"}


def _short_source(name):
    low = name.lower()
    return next((v for k, v in SOURCE_NAMES.items() if k in low), name.split("|")[0].split(" – ")[0].strip())


def _ollama_script(story):
    """Ask the local LLM for an anchor script grounded in the feed text. Returns dict or None."""
    prompt = (
        "You write for a TV news anchor. Use ONLY facts in the text below; do not add names, numbers or claims.\n"
        f"HEADLINE: {story['title']}\nTEXT: {story['summary']}\nSOURCE: {story['source']}\n\n"
        'Reply with JSON only: {"anchor_script": "2-3 sentences, attribute to the source", '
        '"bullets": ["2-3 short on-screen points"], "visual_keyword": "2-4 word literal stock video search"}'
    )
    try:
        r = requests.post(OLLAMA, json={"model": OLLAMA_MODEL, "messages": [{"role": "user", "content": prompt}],
                                        "stream": False, "format": "json"}, timeout=90)
        data = json.loads(r.json()["message"]["content"])
        if data.get("anchor_script"):
            return data
    except Exception as e:
        print(f"Ollama unavailable, using feed text ({e.__class__.__name__})")
    return None


def to_item(story, use_llm=True):
    sid = hashlib.sha1(story["link"].encode() or story["title"].encode()).hexdigest()[:8]
    llm = _ollama_script(story) if use_llm else None
    script = (llm or {}).get("anchor_script") or f"{story['title']}. {story['summary']} That's according to {story['source']}."
    words = [w for w in re.findall(r"[A-Za-z]+", story["title"]) if len(w) > 3][:4]
    return {
        "id": sid, "type": "headline",
        "main_heading": story["title"],
        "content_text": story["summary"][:220],
        "headlines": (llm or {}).get("bullets", [])[:3],
        "display_duration": 20,
        "timestamp": story["published"],
        "extra_data": {
            "category": story["category"], "source": story["source"], "link": story["link"],
            "anchor_script": script,
            "visual_keyword": (llm or {}).get("visual_keyword") or " ".join(words) or story["category"],
        },
    }


SEEN_FILE = QUEUE_FILE.parent / "seen_stories.json"


def update_queue(use_llm=True):
    stories = fetch_all()
    queue = json.loads(QUEUE_FILE.read_text()) if QUEUE_FILE.exists() else []
    queue = [q for q in queue if (q.get("extra_data") or {}).get("link")]   # drop old synthetic/test items
    try:
        seen = set(json.loads(SEEN_FILE.read_text()))
    except Exception:
        seen = set()
    seen |= {q["id"] for q in queue}
    new = []
    for s in stories:
        item_id = hashlib.sha1(s["link"].encode() or s["title"].encode()).hexdigest()[:8]
        if item_id in seen:          # already aired or already queued
            continue
        seen.add(item_id)
        new.append(to_item(s, use_llm))
        if len(new) >= 8:            # cap per cycle so voice/footage production keeps up
            break
    # newest stories first; when full, the oldest ones drop off the end
    queue = (new + queue)[:MAX_QUEUE]
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(queue, indent=2))
    tmp.replace(QUEUE_FILE)
    SEEN_FILE.write_text(json.dumps(sorted(seen)[-5000:]))
    print(f"Newsroom: {len(new)} new, {len(queue)} in run of show.")
    return new


if __name__ == "__main__":
    import sys
    update_queue(use_llm="--no-llm" not in sys.argv)
