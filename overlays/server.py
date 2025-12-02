import os
import time
import json
from flask import Flask, Response, send_from_directory, stream_with_context, request

app = Flask(__name__, static_folder='overlays')

@app.route('/sync', methods=['POST'])
def sync():
    # Placeholder for sync logic
    import http.server
    import socketserver
    import os
    import json

    # --- CONFIGURATION ---
    PORT = 8000
    DIRECTORY = "/home/rahulraj/pen_stream"
    # This file stores which story is currently "On Air"
    STATUS_FILE = os.path.join(DIRECTORY, "bucket/news/queue/playout_status.json")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=DIRECTORY, **kwargs)

        # 1. Disable Caching (So OBS sees updates instantly)
        def end_headers(self):
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Access-Control-Allow-Origin', '*') 
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            super().end_headers()

        # 2. Handle CORS Preflight
        def do_OPTIONS(self):
            self.send_response(200)
            self.end_headers()

        # 3. HANDLE THE SYNC SIGNAL (The Missing Piece)
        def do_POST(self):
            if self.path == '/sync':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                try:
                    # Save the status sent by HTML
                    data = json.loads(post_data)
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
                    with open(STATUS_FILE, 'w') as f:
                        json.dump(data, f)
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b'{"status": "ok"}')
                except Exception as e:
                    print(f"❌ Sync Error: {e}")
                    self.send_response(500)
                    self.end_headers()
            else:
                self.send_error(404)

    print(f"📡 BROADCAST SERVER ACTIVE (Port {PORT})")
    print(f"📂 Root: {DIRECTORY}")

    # Allow immediate restart if it crashes
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer Stopped.")
            httpd.server_close()