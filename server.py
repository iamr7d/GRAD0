import os
import time
import json
import requests
import socket # ADDED: For port availability check
from flask import Flask, Response, request, send_from_directory, jsonify, stream_with_context

# --- CONFIGURATION ---
# Use the directory where this script is located as the base
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
# Define the directories the app needs to serve content from
BUCKET_DIR = os.path.join(BASE_DIR, 'bucket') 
OVERLAYS_DIR = os.path.join(BASE_DIR, 'overlays')

# This file stores which story is currently "On Air"
STATUS_FILE = os.path.join(BASE_DIR, "bucket/news/queue/playout_status.json")

# Ensure necessary output directory exists
os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)

# Initialize Flask App
app = Flask(__name__) 

# --- CORS PREFLIGHT SETUP (Mandatory for OBS/External access) ---
@app.before_request
def handle_options():
    """Handles CORS preflight requests by setting required headers."""
    if request.method == 'OPTIONS':
        res = Response()
        res.headers['Access-Control-Allow-Origin'] = '*'
        res.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        res.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        # Prevent caching for preflight response
        res.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        return res

# --- ADD NO-CACHE HEADERS TO ALL RESPONSES (Crucial for OBS live update) ---
@app.after_request
def add_no_cache_headers(response):
    """Applies no-cache headers to ensure OBS always gets the latest content."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response


# --- ROUTE 1: SERVE STATIC FILES (OVERLAYS AND ROOT LEVEL HTML) ---
@app.route('/')
@app.route('/<path:filename>')
def serve_static(filename='broadcast_screen.html'):
    """Serves the main HTML files and other static assets."""
    # Special handler for files located in the 'overlays' subdirectory
    if filename.startswith('overlays/'):
        return send_from_directory(BASE_DIR, filename)

    # Try to serve files from the base directory
    try:
        return send_from_directory(BASE_DIR, filename)
    except FileNotFoundError:
        # Fallback to try the 'overlays' directory for files requested at root
        # This covers cases like "http://localhost:8000/broadcast_screen.html" 
        # when the file is actually in "overlays/broadcast_screen.html"
        return send_from_directory(OVERLAYS_DIR, filename)


# --- ROUTE 2: SERVE DATA FILES (from /bucket) ---
@app.route('/bucket/<path:filename>')
def serve_bucket(filename):
    """Serves JSON and TXT data files from the /bucket directory."""
    # Ensure filename is relative to BUCKET_DIR
    return send_from_directory(BUCKET_DIR, filename)


# --- ROUTE 3: SYNC SIGNAL (POST Request from HTML) ---
@app.route('/sync', methods=['POST'])
def sync():
    """Receives the 'On Air' status from the HTML and saves it to playout_status.json."""
    try:
        data = request.json
        # Add server-side timestamp
        data['server_time'] = time.time()
        
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
            
        print(f"📡 ON AIR: {data.get('heading', 'Unknown')}")
        return jsonify({"status": "ok", "synced": True})
        
    except Exception as e:
        print(f"❌ Sync Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# --- ROUTE 4: VIDEO PROXY (to avoid CORS/hotlinking issues) ---
@app.route('/proxy_video')
def proxy_video():
    """Streams remote video/image content through this server to bypass browser restrictions."""
    video_url = request.args.get('url')
    if not video_url:
        return Response("Missing URL", status=400)

    # Whitelist check for security (from original server.py logic)
    allowed_hosts = ['videos.pexels.com', 'images.pexels.com', 'player.vimeo.com', 'vimeo.com']
    try:
        parsed = requests.utils.urlparse(video_url)
        hostname = parsed.hostname or ''
        if not any(hostname.endswith(h) for h in allowed_hosts):
            return Response("Forbidden host", status=403)
    except Exception:
        return Response("Invalid URL format", status=400)

    try:
        # Stream the remote content
        req = requests.get(video_url, stream=True, timeout=10)
        
        # Forward specific headers
        headers = {
            'Content-Type': req.headers.get('Content-Type'),
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': 'no-store, no-cache, must-revalidate'
        }
        if req.headers.get('Content-Length'):
            headers['Content-Length'] = req.headers['Content-Length']

        # Use streaming response for large files (videos)
        return Response(
            stream_with_context(req.iter_content(chunk_size=64*1024)),
            headers=headers,
            status=req.status_code
        )
    except Exception as e:
        print(f"Proxy Error: {e}")
        return Response("Proxy Error: Bad Gateway", status=502)


if __name__ == '__main__':
    
    def is_port_available(port):
        """Checks if a port is available by attempting to bind to it."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('0.0.0.0', port))
                return True
            except socket.error:
                return False

    def run_server():
        PORTS_TO_TRY = [8000, 8001, 8080]
        
        for port in PORTS_TO_TRY:
            if is_port_available(port):
                try:
                    print(f"Attempting to start server on port {port}...")
                    print(f"🚀 PEN BROADCAST SERVER ACTIVE (Flask)")
                    print(f"📂 Base Directory: {BASE_DIR}")
                    print(f"👉 Live Endpoint: http://127.0.0.1:{port}/broadcast_screen.html")
                    # Setting host='0.0.0.0' allows external access (e.g., from OBS on the network)
                    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)
                    return # Exit successfully if server starts
                except Exception as e:
                    # Catch any rare issues after the port check
                    print(f"An unexpected error occurred during startup on port {port}: {e}")
                    break
            else:
                print(f"⚠️ Port {port} is busy. Trying next port...")
                time.sleep(1)
                continue
        
        print("\n❌ FAILED TO START SERVER. All attempted ports were busy.")

    run_server()