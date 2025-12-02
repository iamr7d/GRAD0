#!/usr/bin/env python3
import sys
import os
import json
import uuid
import time

# Ensure repo root on path so we can import the tools module
sys.path.insert(0, '/home/rahulraj/pen_stream')

from news.tools.video_finder import get_relevant_video
from news.config import PATH_QUEUE

def add_test_item(heading='Test AI News', content='Automated test item', duration=15):
    qfile = os.path.join(PATH_QUEUE, 'run_of_show.json')
    if os.path.exists(qfile):
        try:
            queue = json.load(open(qfile))
        except Exception:
            queue = []
    else:
        queue = []

    media = get_relevant_video(heading)
    video_url = media.get('url') if isinstance(media, dict) else media
    media_type = media.get('type') if isinstance(media, dict) else ('video' if str(video_url).lower().endswith(('.mp4','.webm')) else 'image')
    item = {
        'id': str(uuid.uuid4())[:8],
        'type': 'headline',
        'main_heading': heading,
        'content_text': content,
        'display_duration': duration,
        'timestamp': int(time.time()),
        'extra_data': {'video_url': video_url, 'media_url': video_url, 'media_type': media_type}
    }
    queue.append(item)
    # Cap queue length
    if len(queue) > 50:
        queue = queue[-50:]
    os.makedirs(PATH_QUEUE, exist_ok=True)
    with open(qfile, 'w') as f:
        json.dump(queue, f, indent=2)
    print('Added item:', item['id'], 'video:', video_url)

if __name__ == '__main__':
    add_test_item()
