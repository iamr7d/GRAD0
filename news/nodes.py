import json
import time
import os
import uuid
import socket
import feedparser
import json_repair
import requests
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypedDict, List
from langchain_core.tools import Tool
from langchain_openai import ChatOpenAI
from config import *
# --- IMPORT VIDEO TOOL ---
from tools.video_finder import get_relevant_video 

# --- 0. GLOBAL SAFETY NET ---
socket.setdefaulttimeout(15)

# --- 1. HELPERS ---
def clean_json(text: str):
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1]
            if text.startswith("json"): text = text[4:]
    try:
        return json_repair.loads(text)
    except:
        return []

def save_audit_log(status, data):
    timestamp = int(time.time())
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{timestamp}_{unique_id}.json"
    folder = PATH_RAW_SELECTED if status == "selected" else PATH_RAW_REJECTED
    path = os.path.join(folder, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=4)
    return path

# --- 2. PLAYLIST MANAGER ---
class QueueManager:
    def __init__(self):
        self.filepath = os.path.join(PATH_QUEUE, "run_of_show.json")
    
    def load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, 'r') as f: return json.load(f)
            except: return []
        return []

    def save(self, queue):
        if len(queue) > 50: queue = queue[:50]
        with open(self.filepath, 'w') as f:
            json.dump(queue, f, indent=4)
        if queue:
            with open(os.path.join(PATH_QUEUE, "current_item.json"), 'w') as f:
                json.dump(queue[0], f, indent=4)
    def add_item(self, type, content, heading, duration=15, priority="normal", extra_data=None):
        queue = self.load()
        if extra_data is None:
            extra_data = {}

        # Ensure every item has a visual video URL
        video_url = get_relevant_video(heading)
        extra_data['video_url'] = video_url

        print(f"➕ Adding to Queue: {heading}")
        print(f"   ▶️ Video URL: {video_url}")

        item = {
            "id": str(uuid.uuid4())[:8],
            "type": type,
            "main_heading": heading,
            "content_text": content,
            "display_duration": duration,
            "timestamp": int(time.time()),
            "extra_data": extra_data
        }

        if priority == "high":
            print(f"🚨 INJECTING HIGH PRIORITY: {heading}")
            queue.insert(0, item)
        else:
            queue.append(item)

        self.save(queue)

# --- CRITICAL: INITIALIZE GLOBAL INSTANCE HERE ---
qm = QueueManager()

# --- 3. STATE ---
class BreakingState(TypedDict):
    search_results: str
    is_urgent: bool

class TrendingState(TypedDict):
    raw_candidates: List[dict]
    processed_candidates: List[dict]
    approved_stories: List[dict]
    final_output: dict

# --- 4. TOOLS ---
def fetch_single_feed(url):
    try:
        response = requests.get(url, timeout=5.0)
        feed = feedparser.parse(response.content)
        entries = []
        for entry in feed.entries[:2]:
            entries.append({
                "title": entry.title,
                "summary": getattr(entry, 'summary', entry.title)[:300],
                "link": getattr(entry, 'link', 'N/A'),
                "source": feed.feed.get('title', 'Unknown'),
            })
        if entries: print(".", end="", flush=True)
        return entries
    except:
        return []

def robust_fetch_news():
    print(f"\n[RSS] 🚀 Launching Parallel Fetch...")
    all_urls = []
    for category in RSS_SOURCES:
        all_urls.extend(RSS_SOURCES[category])
    
    stories = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_url = {executor.submit(fetch_single_feed, url): url for url in all_urls}
        for future in as_completed(future_to_url):
            try:
                entries = future.result()
                stories.extend(entries)
            except:
                pass
    print(f"\n✅ [RSS] Aggregated {len(stories)} articles.")
    return stories

# --- 5. BREAKING NODE (GPU 0) ---
breaking_llm = ChatOpenAI(**BREAKING_LLM_CONFIG)

async def check_wires_node(state: BreakingState):
    return {"search_results": "Scanning..."}

async def analyze_urgency_node(state: BreakingState):
    return {"is_urgent": False}

# --- 6. COLLECTOR NODE (GPU 1) ---
trending_llm = ChatOpenAI(**TRENDING_LLM_CONFIG)

async def collect_and_cluster_node(state: TrendingState):
    print(f"\n[GPU 1] 🌍 Collecting Data...")
    raw_articles = robust_fetch_news()
    if not raw_articles: return {"processed_candidates": []}

    subset = raw_articles[:60] 
    prompt = f"""
    News Aggregator. Extract 10 DISTINCT Top Stories.
    INPUT: {json.dumps(subset)}
    OUTPUT JSON LIST: [ {{"original_title": "...", "original_summary": "..."}} ]
    """
    try:
        res = await trending_llm.ainvoke(prompt)
        return {"processed_candidates": clean_json(res.content)}
    except: return {"processed_candidates": []}

# --- 7. FILTER NODE ---
async def safety_filter_node(state: TrendingState):
    cands = state.get('processed_candidates', [])
    if not cands: return {"approved_stories": []}
    
    print("[GPU 1] 🛡️  Filtering...")
    prompt = f"""
    Filter stories. Remove Fake/Abusive.
    INPUT: {json.dumps(cands)}
    OUTPUT JSON LIST (Approved): [ {{"original_title": "...", "reason": "Passed"}} ]
    """
    try:
        res = await trending_llm.ainvoke(prompt)
        approved = clean_json(res.content)
        
        final_list = []
        for item in approved:
            orig = next((x for x in cands if x['original_title'][:10] in item.get('original_title','')[:10]), {})
            final_list.append({**orig, **item})
            
        print(f"[GPU 1] Approved {len(final_list)} stories.")
        return {"approved_stories": final_list}
    except: return {"approved_stories": []}

# --- 8. EDITOR NODE (WITH VISUAL DIRECTOR) ---
async def editor_production_node(state: TrendingState):
    stories = state.get('approved_stories', [])
    if not stories: return {}
    
    print(f"[GPU 1] ✍️  Producing Content & Selecting Visuals...")
    
    prompt = f"""
    You are a TV Director. 
    INPUT: {json.dumps(stories)}
    
    REQUIREMENTS:
    1. main_heading: Short Title (3-6 words).
    2. content_text: 2 short sentences.
    3. visual_search_term: A specific 2-3 word phrase to search for stock video (e.g. "Cyber Hacker", "Wildfire Smoke", "Stock Market Graph").
    4. ticker: Uppercase headline.
    
    OUTPUT JSON: 
    {{ "segments": [ {{ "main_heading": "...", "content_text": "...", "visual_search_term": "...", "ticker": "..." }} ] }}
    """
    try:
        res = await trending_llm.ainvoke(prompt)
        data = clean_json(res.content)
        
        if data and 'segments' in data:
            for seg in data['segments']:
                
                # 1. SEARCH PEXELS (video or image)
                keyword = seg.get('visual_search_term', 'news background')
                media = get_relevant_video(keyword)

                media_url = media.get('url') if isinstance(media, dict) else media
                media_type = media.get('type') if isinstance(media, dict) else ('video' if str(media_url).lower().endswith(('.mp4','.webm')) else 'image')
                matched = media.get('matched', False) if isinstance(media, dict) else False

                # 2. ADD TO QUEUE (store both `media_url` and `video_url` for backwards compat)
                qm.add_item(
                    type="headline", 
                    heading=seg['main_heading'],
                    content=seg['content_text'],
                    duration=15,
                    extra_data={
                        "video_url": media_url,
                        "media_url": media_url,
                        "media_type": media_type,
                        "visual_keyword": keyword,
                        "visual_matched": matched
                    }
                )
                
                # Save Log
                save_audit_log("selected", seg)
                
            # Update Ticker File
            t_list = [s.get('ticker','') for s in data['segments']]
            t_text = " +++ ".join(t_list) + " +++ "
            with open(os.path.join(PATH_TICKER, "latest.txt"), "w") as f: f.write(t_text)
            
            print(f"✅ Queue Updated with {len(data['segments'])} Visual Stories.")
            
        return {"final_output": data}
    except Exception as e:
        print(f"❌ Error: {e}")
        return {}

# --- 9. TICKER NODE ---
async def generate_ticker_node(state: TrendingState):
    try:
        raw = robust_fetch_news()
        titles = [x['title'] for x in raw[:20]]
        text = " +++ ".join(titles).upper() + " +++ "
        with open(os.path.join(PATH_TICKER, "latest.txt"), "w") as f: f.write(text)
        return {"ticker_text": text}
    except: return {}

if __name__ == "__main__":
    print('Python executable:', sys.executable)
    try:
        import feedparser
        print('feedparser is installed')
    except ImportError:
        print('feedparser is NOT installed')
    from nodes import QueueManager
    qm = QueueManager()
    qm.add_item(
        type="headline",
        content="Test content for video",
        heading="Test AI News",
        duration=15
    )
    print("Test item added. Check run_of_show.json for extra_data.video_url.")