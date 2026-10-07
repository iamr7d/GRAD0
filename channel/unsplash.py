"""Still photos from Unsplash, used when Pexels has no good video for a story.

Follows the Unsplash API guidelines:
  * hotlink: we keep the original images.unsplash.com URL (no re-hosting)
  * trigger downloads: we call the photo's download_location when a photo is put on air
  * attribution: every result carries "Photo by <name> on Unsplash" with referral links
Set UNSPLASH_ACCESS_KEY in .env. Demo apps get 50 requests/hour.
"""
import os

import requests

from .config import ROOT  # noqa: F401  (loads .env)

API = "https://api.unsplash.com"
APP = os.getenv("UNSPLASH_APP_NAME", "prime_earth_news")
KEY = os.getenv("UNSPLASH_ACCESS_KEY", "")


def _get(path, **params):
    if not KEY:
        raise RuntimeError("UNSPLASH_ACCESS_KEY is not set (put it in .env)")
    r = requests.get(API + path, params=params, timeout=15,
                     headers={"Authorization": f"Client-ID {KEY}", "Accept-Version": "v1"})
    r.raise_for_status()
    return r.json()


def _ref(url):
    return f"{url}?utm_source={APP}&utm_medium=referral"


def search(query, min_width=1920):
    """Return the best landscape photo for `query`, or None."""
    data = _get("/search/photos", query=query, orientation="landscape", per_page=10, content_filter="high")
    for p in data.get("results", []):
        if p.get("width", 0) < min_width:
            continue
        user = p.get("user") or {}
        return {
            "id": p["id"],
            # hotlinked, sized for 1080p output
            "url": p["urls"]["raw"] + "&w=1920&h=1080&fit=crop&q=85&fm=jpg",
            "download_location": p["links"]["download_location"],
            "credit": f"Photo by {user.get('name', 'Unknown')} on Unsplash",
            "credit_html": f'Photo by <a href="{_ref(user.get("links", {}).get("html", "https://unsplash.com"))}">{user.get("name", "Unknown")}</a> '
                           f'on <a href="{_ref("https://unsplash.com/")}">Unsplash</a>',
        }
    return None


def mark_used(photo):
    """Tell Unsplash the photo went on air (required by the API guidelines)."""
    try:
        requests.get(photo["download_location"], timeout=10,
                     headers={"Authorization": f"Client-ID {KEY}", "Accept-Version": "v1"})
    except Exception as e:
        print(f"Unsplash download trigger failed: {e}")


if __name__ == "__main__":
    import json, sys
    print(json.dumps(search(" ".join(sys.argv[1:]) or "city skyline"), indent=2))
