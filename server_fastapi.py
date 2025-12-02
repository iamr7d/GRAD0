#!/usr/bin/env python3
"""
FastAPI-based broadcast server with a proxied media endpoint.

Features:
- Serves static files from project root (same as old server)
- `/proxy_video?url=...` endpoint with host whitelist, token auth, and simple caching for image responses

Run with:
  PROXY_TOKEN=yourtoken /path/to/venv/bin/uvicorn server_fastapi:app --host 0.0.0.0 --port 8000

"""
import os
import time
import hashlib
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import requests
from cachetools import TTLCache

# rate limiting and disk cache
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
from diskcache import Cache as DiskCache

ROOT = os.path.abspath(os.path.dirname(__file__))
app = FastAPI()

# Initialize rate limiter (per-IP)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: Response("Too Many Requests", status_code=429))
app.add_middleware(SlowAPIMiddleware)

# Simple in-memory cache for small image bodies: key=url -> (bytes, headers, ts)
IMAGE_CACHE = TTLCache(maxsize=512, ttl=300)
# Disk cache to persist across restarts (for larger or repeated items)
DISK_CACHE_DIR = os.path.join(ROOT, '.cache', 'proxy_cache')
os.makedirs(DISK_CACHE_DIR, exist_ok=True)
DISK_CACHE = DiskCache(DISK_CACHE_DIR)

# whitelist for proxied hosts
ALLOWED_HOSTS = ['videos.pexels.com', 'images.pexels.com', 'player.vimeo.com', 'vimeo.com']

# token for proxy usage (set PROXY_TOKEN env var)
PROXY_TOKEN = os.getenv('PROXY_TOKEN', '')


def _check_allowed(hostname: str) -> bool:
    return any(hostname.endswith(h) for h in ALLOWED_HOSTS)


@app.get('/proxy_video')
async def proxy_video(request: Request, url: str = None):
    if not url:
        raise HTTPException(status_code=400, detail="missing url")

    # require token unless localhost
    token = request.query_params.get('token') or request.headers.get('X-Proxy-Token')
    client = request.client.host if request.client else 'unknown'
    if PROXY_TOKEN:
        if client not in ('127.0.0.1', '::1') and token != PROXY_TOKEN:
            raise HTTPException(status_code=403, detail='proxy token required')

    try:
        parsed = requests.utils.urlparse(url)
        hostname = parsed.hostname or ''
    except Exception:
        raise HTTPException(status_code=400, detail='invalid url')

    if not _check_allowed(hostname):
        raise HTTPException(status_code=403, detail='forbidden host')

    # If cached in memory, return
    if url in IMAGE_CACHE:
        body, headers, ts = IMAGE_CACHE[url]
        return Response(content=body, media_type=headers.get('Content-Type', 'application/octet-stream'), headers={'X-Cache':'HIT-MEM'})

    # If cached on disk, return
    if url in DISK_CACHE:
        data, headers = DISK_CACHE[url]
        return Response(content=data, media_type=headers.get('Content-Type', 'application/octet-stream'), headers={'X-Cache':'HIT-DISK'})

    try:
        r = requests.get(url, stream=True, timeout=10)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    content_type = r.headers.get('Content-Type','application/octet-stream')
    content_length = r.headers.get('Content-Length')

    # Cache small images (<=5MB)
    try:
        cl = int(content_length) if content_length else None
    except Exception:
        cl = None

    if content_type.startswith('image') and (cl is None or cl <= 5_000_000):
        # load into memory and cache (and persist to disk)
        data = r.content
        IMAGE_CACHE[url] = (data, {'Content-Type': content_type}, time.time())
        try:
            DISK_CACHE.set(url, (data, {'Content-Type': content_type}), expire=300)
        except Exception:
            pass
        return Response(content=data, media_type=content_type, headers={'X-Cache':'MISS'})

    # stream large video directly
    def iter_chunks():
        try:
            for chunk in r.iter_content(chunk_size=64*1024):
                if chunk:
                    yield chunk
        finally:
            r.close()

    headers = {'Cache-Control': 'no-store, no-cache, must-revalidate', 'Access-Control-Allow-Origin': '*'}
    return StreamingResponse(iter_chunks(), media_type=content_type, headers=headers)


# Serve static files (project root)
app.mount('/', StaticFiles(directory=ROOT, html=True), name='static')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run('server_fastapi:app', host='0.0.0.0', port=8000, reload=False)
