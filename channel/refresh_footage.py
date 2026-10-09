"""Throw away footage choices for every story so produce.py picks again with the new rules.
    python -m channel.refresh_footage
"""
import json
from .config import QUEUE_FILE

q = json.loads(QUEUE_FILE.read_text())
for item in q:
    x = item.get("extra_data") or {}
    for k in ("video_local", "video_url", "media_url", "media_type", "video_credit", "video_source", "photo_url", "media_credit", "media_credit_html"):
        x.pop(k, None)
    if x.get("visual_source") != "llm":
        x["visual_keyword"] = ""
QUEUE_FILE.write_text(json.dumps(q, indent=2))
print(f"Cleared footage for {len(q)} stories; channel.run will fetch new clips on its next cycle.")
