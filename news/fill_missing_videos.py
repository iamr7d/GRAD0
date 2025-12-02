#!/usr/bin/env python3
"""Fill missing extra_data.video_url in run_of_show.json using the Pexels helper."""
import os
import json
import time
import sys

# Ensure repo root on path so we can import the project's modules
sys.path.insert(0, '/home/rahulraj/pen_stream')

from news.tools.video_finder import get_relevant_video
from news.config import PATH_QUEUE

QFILE = os.path.join(PATH_QUEUE, 'run_of_show.json')

def backup(qfile):
    bak = qfile + f'.bak.{int(time.time())}'
    try:
        if os.path.exists(qfile):
            with open(qfile, 'r') as f:
                data = f.read()
            with open(bak, 'w') as f:
                f.write(data)
            print('Backup written to', bak)
    except Exception as e:
        print('Backup failed:', e)

def fill():
    if not os.path.exists(QFILE):
        print('Queue file not found:', QFILE)
        return
    with open(QFILE, 'r') as f:
        try:
            queue = json.load(f)
        except Exception as e:
            print('Failed to load JSON:', e)
            return

    changed = False
    for item in queue:
        try:
            extra = item.get('extra_data') or {}
            video = extra.get('video_url')
            if not video:
                heading = item.get('main_heading') or item.get('content_text') or 'news background'
                print('Searching for video for:', heading)
                v = get_relevant_video(heading)
                if v:
                    extra['video_url'] = v
                    item['extra_data'] = extra
                    changed = True
                    print(' -> Found:', v)
                else:
                    print(' -> No video found, skipping')
                # be kind to API rate limits
                time.sleep(1.0)
        except Exception as e:
            print('Error processing item', item.get('id'), e)

    if changed:
        backup(QFILE)
        with open(QFILE, 'w') as f:
            json.dump(queue, f, indent=2)
        print('Queue updated.')
    else:
        print('No changes needed.')

if __name__ == '__main__':
    fill()
