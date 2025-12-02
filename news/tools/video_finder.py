
import os
import requests
import random
import time

BASE_VIDEO_URL = "https://api.pexels.com/videos/search"
BASE_PHOTO_URL = "https://api.pexels.com/v1/search"
DEFAULT_VIDEO = "https://upload.wikimedia.org/wikipedia/commons/transcoded/c/c0/Big_Buck_Bunny_4K.webm/Big_Buck_Bunny_4K.webm.480p.vp9.webm"


def _load_api_key():
    try:
        from dotenv import load_dotenv
        load_dotenv("/home/rahulraj/pen_stream/stream/.env")
    except Exception:
        # It's fine if dotenv isn't installed or .env missing; rely on environment
        pass
    return os.getenv("PEXELS_API_KEY")


def _tokens(query):
    return [t.strip() for t in query.lower().replace('-', ' ').split() if len(t) > 2]


def _video_matches(video, tokens):
    hay = []
    # common video fields to check
    if video.get('url'):
        hay.append(video.get('url'))
    if video.get('image'):
        hay.append(video.get('image'))
    # check user/name
    user = video.get('user') or {}
    if user.get('name'):
        hay.append(user.get('name'))
    # video_files links
    for vf in video.get('video_files', []):
        if vf.get('link'):
            hay.append(vf.get('link'))

    hay_text = ' '.join([h.lower() for h in hay if h])
    # if any token appears in hay_text, it's a weak match
    matches = sum(1 for t in tokens if t in hay_text)
    return matches >= 1


def _semantic_available():
    try:
        import sentence_transformers
        return True
    except Exception:
        return False


def _semantic_score(texts, query):
    """Compute cosine similarity scores between `query` and each text in `texts` using
    sentence-transformers if available. Returns list of floats (0..1).
    If sentence-transformers is not installed, returns None.
    """
    try:
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer('all-MiniLM-L6-v2')
        q_emb = model.encode(query, convert_to_tensor=True)
        c_emb = model.encode(texts, convert_to_tensor=True)
        sims = util.cos_sim(q_emb, c_emb).cpu().numpy().reshape(-1)
        return [float(s) for s in sims]
    except Exception as e:
        # model not available or failed
        return None


def _simple_sem_score(texts, query):
    """Lightweight fallback semantic score based on token overlap and term frequency.
    Returns list of similarity scores between 0 and 1.
    """
    import math
    from collections import Counter

    def tokenize(s):
        return [t for t in ''.join([c if c.isalnum() else ' ' for c in s.lower()]).split() if len(t) > 2]

    q_tokens = tokenize(query)
    q_counts = Counter(q_tokens)
    q_norm = math.sqrt(sum(v*v for v in q_counts.values())) or 1.0

    scores = []
    for t in texts:
        t_tokens = tokenize(t or '')
        t_counts = Counter(t_tokens)
        dot = sum((q_counts[k] * t_counts.get(k,0) for k in q_counts))
        t_norm = math.sqrt(sum(v*v for v in t_counts.values())) or 1.0
        sim = dot / (q_norm * t_norm)
        scores.append(float(sim))
    return scores


def get_relevant_video(query, attempts=3):
    """Search Pexels for a video matching `query`. If videos found but none match
    the query heuristically, retry up to `attempts`. If still not found, fall back
    to searching photos and return an image URL. Always returns a URL string.
    """
    api_key = _load_api_key()
    if not api_key:
        print("⚠️ Pexels Key missing. Using default video.")
        return DEFAULT_VIDEO

    headers = {"Authorization": api_key}
    tokens = _tokens(query)

    print(f"🎥 Searching Pexels videos for: '{query}' (tokens: {tokens})...")

    # Try searching videos with a few pages/attempts
    for page in range(1, attempts + 1):
        params = {"query": query, "per_page": 6, "page": page, "orientation": "landscape"}
        try:
            resp = requests.get(BASE_VIDEO_URL, headers=headers, params=params, timeout=6)
            data = resp.json()
            videos = data.get('videos', [])
            if not videos:
                # no videos on this page
                time.sleep(0.5)
                continue

            # Prefer HD videos first
            videos_sorted = sorted(videos, key=lambda v: max((f.get('width', 0) for f in v.get('video_files', [])), default=0), reverse=True)
            # Try to find a matching video
            for video in videos_sorted:
                # Try semantic matching first if available
                try:
                    hay_samples = []
                    if video.get('url'): hay_samples.append(video.get('url'))
                    if video.get('image'): hay_samples.append(video.get('image'))
                    if video.get('user') and video.get('user').get('name'): hay_samples.append(video.get('user').get('name'))
                    for vf in video.get('video_files', []):
                        if vf.get('link'): hay_samples.append(vf.get('link'))

                    sem_scores = None
                    if _semantic_available() and hay_samples:
                        sem_scores = _semantic_score(hay_samples, query)
                except Exception:
                    sem_scores = None

                # Accept if semantic score passes threshold
                if sem_scores and max(sem_scores) >= 0.56:
                    vfiles = video.get('video_files', [])
                    if not vfiles:
                        continue
                    best = next((f for f in vfiles if f.get('width', 0) >= 1280), vfiles[0])
                    print("✅ Found semantically matching video (score=", max(sem_scores), "):", best.get('link'))
                    return {
                        "url": best.get('link'),
                        "type": "video",
                        "matched": True
                    }

                # Fallback to token heuristic
                if _video_matches(video, tokens):
                    # choose best file (>=1280 width if available)
                    vfiles = video.get('video_files', [])
                    if not vfiles:
                        continue
                    best = next((f for f in vfiles if f.get('width', 0) >= 1280), vfiles[0])
                    print("✅ Found matching video:", best.get('link'))
                    return {
                        "url": best.get('link'),
                        "type": "video",
                        "matched": True
                    }

            # If none matched heuristically, pick one candidate and retry on next page
            candidate = random.choice(videos)
            vfiles = candidate.get('video_files', [])
            if vfiles:
                best = next((f for f in vfiles if f.get('width', 0) >= 1280), vfiles[0])
                print("⚠️ No close match heuristically; keeping candidate:", best.get('link'))
                # still return candidate as a fallback for quicker UX
                return {
                    "url": best.get('link'),
                    "type": "video",
                    "matched": False
                }

        except Exception as e:
            print(f"❌ Pexels video search error: {e}")
            time.sleep(0.5)

    # If we get here, try photo search as a fallback
    print(f"🔁 Falling back to Pexels photo search for: '{query}'")
    try:
        params = {"query": query, "per_page": 6, "page": 1}
        resp = requests.get(BASE_PHOTO_URL, headers=headers, params=params, timeout=6)
        data = resp.json()
        photos = data.get('photos', [])
        if photos:
            # try to find a photo that matches tokens
            for photo in photos:
                src = photo.get('src', {})
                hay = ' '.join([photo.get('url',''), photo.get('photographer',''), src.get('original','')]).lower()
                if any(t in hay for t in tokens):
                    img = src.get('original') or src.get('large')
                    print("🖼️ Found matching photo:", img)
                    return {
                        "url": img,
                        "type": "image",
                        "matched": True
                    }

            # return first photo as last resort
            first = photos[0].get('src', {}).get('original')
            if first:
                print("🖼️ No clear match; returning first photo:", first)
                return {
                    "url": first,
                    "type": "image",
                    "matched": False
                }
    except Exception as e:
        print(f"❌ Pexels photo search error: {e}")

    print("⚠️ No suitable Pexels media found; using default video.")
    return {"url": DEFAULT_VIDEO, "type": "video", "matched": False}
