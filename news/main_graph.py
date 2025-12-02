import asyncio
import sys
import requests
import time
import os
import json
import uuid
import random
from pathlib import Path
from elevenlabs.client import ElevenLabs 

# --- 🛠️ CRITICAL SETUP: SET WORKING DIRECTORY TO PROJECT ROOT 🛠️ ---
CURRENT_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_PROJECT_DIR = os.path.dirname(CURRENT_SCRIPT_DIR) 
os.chdir(BASE_PROJECT_DIR)
print(f"📂 Working Directory Set To: {os.getcwd()}")

from langgraph.graph import StateGraph, END

# Import existing nodes
try:
    from nodes import (
        BreakingState, TrendingState,
        check_wires_node, analyze_urgency_node,
        collect_and_cluster_node, safety_filter_node,
    )
except ImportError:
    sys.path.append(CURRENT_SCRIPT_DIR)
    from nodes import (
        BreakingState, TrendingState,
        check_wires_node, analyze_urgency_node,
        collect_and_cluster_node, safety_filter_node
    )

# --- 🔑 API CONFIGURATION (HARDCODED FOR STABILITY) ---
# ElevenLabs
ELEVENLABS_API_KEY = "sk_b9fe20f85bf9c9ad7c7eea6d492fef33d0d6890d6a41754c"
ELEVENLABS_VOICE_ID = "1SM7GgM6IMuvQlz2BwM3" # Mark ConvoAI

# Pexels
PEXELS_API_KEY = "FTCgsuQoPu4aQLnOREJ1BjhGdzC8rkKU67kN6XaOpoM5klZl8G7R5fFk"

# --- SYSTEM CONFIGURATION ---
BREAKING_INTERVAL = 300
TRENDING_INTERVAL = 300 # Reduced to 5 mins to close the gap between batches
TICKER_INTERVAL = 300

QUEUE_DIR = os.path.join(BASE_PROJECT_DIR, "bucket/news/queue")
TICKER_DIR = os.path.join(BASE_PROJECT_DIR, "bucket/news/ticker")
AUDIO_DIR = os.path.join(BASE_PROJECT_DIR, "bucket/news/audio")

# --- CUSTOM AI AGENTS ---

def ensure_directories():
    print(f"📂 Project Root Detected: {BASE_PROJECT_DIR}")
    for p in [QUEUE_DIR, TICKER_DIR, AUDIO_DIR]:
        Path(p).mkdir(parents=True, exist_ok=True)
    print(f"✅ Output Targets Verified")

async def search_pexels(query):
    """Searches Pexels for a relevant video URL."""
    if not PEXELS_API_KEY:
        return "https://videos.pexels.com/video-files/3129671/3129671-hd_1280_720_25fps.mp4"
    
    headers = {"Authorization": PEXELS_API_KEY}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=1&orientation=landscape"
    
    try:
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('videos'):
                # Get the first video, preferably HD
                video_files = data['videos'][0]['video_files']
                # Try to find 1280x720 or similar
                best_video = next((v for v in video_files if v['width'] >= 1280), video_files[0])
                return best_video['link']
    except Exception as e:
        print(f"⚠️ Pexels Search Failed for '{query}': {e}")
    
    # Fallback Video
    return "https://videos.pexels.com/video-files/3129671/3129671-hd_1280_720_25fps.mp4"

async def generate_anchor_audio(text, filename):
    """
    Generates professional anchor audio using ElevenLabs API.
    """
    filepath = os.path.join(AUDIO_DIR, filename)
    
    try:
        # Run in thread to avoid blocking
        def _run_elevenlabs():
            client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            
            # Generate audio stream
            audio_stream = client.text_to_speech.convert(
                text=text,
                voice_id=ELEVENLABS_VOICE_ID,
                model_id="eleven_multilingual_v2"
            )
            
            # Save stream to file
            with open(filepath, "wb") as f:
                for chunk in audio_stream:
                    if chunk:
                        f.write(chunk)

        await asyncio.to_thread(_run_elevenlabs)
        return f"/bucket/news/audio/{filename}" 
        
    except Exception as e:
        print(f"❌ ElevenLabs Error: {e}")
        return None

async def query_ollama_direct(port, prompt):
    url = f"http://127.0.0.1:{port}/api/chat"
    payload = {
        "model": "mistral:latest",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    try:
        response = await asyncio.to_thread(requests.post, url, json=payload, timeout=60)
        if response.status_code == 200:
            return response.json().get("message", {}).get("content", "")
        else:
            print(f"❌ Ollama Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Ollama Connection Failed: {e}")
        return None

async def custom_ticker_node(state: TrendingState):
    print("   [Ticker] 🧠 Generating detailed ticker lines...")
    
    prompt = """
    You are a professional broadcast news ticker writer.
    Generate 5 distinct news headlines based on current global trends or general knowledge.
    
    CRITICAL RULES:
    1. Each headline MUST be between 18 and 25 words long.
    2. Write in full, clear sentences. Do not use abbreviated "headline speak".
    3. Explain the 'Why' and 'Impact' in the sentence.
    4. Separate items with " +++ " (space plus plus plus space).
    5. Do not output anything else, just the text string.
    """
    
    content = ""
    try:
        from langchain_community.chat_models import ChatOllama
        from langchain_core.messages import HumanMessage
        llm = ChatOllama(model="mistral:latest", base_url="http://127.0.0.1:11435")
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content
    except (ImportError, Exception):
        content = await query_ollama_direct(11435, prompt)

    if content:
        clean_content = content.strip().replace('"', '')
        with open(os.path.join(TICKER_DIR, "latest.txt"), "w") as f:
            f.write(clean_content)
        print(f"✅ [Ticker] Updated.")
    
    return state

async def custom_editor_node(state: TrendingState):
    print("   [Editor] ✍️  Writing Scripts, Headlines & Recording Audio (ElevenLabs)...")
    
    stories = state.get('approved_stories', [])
    if not stories:
        print("   [Editor] No upstream stories found. Generating fresh synthetic news.")
        stories = ["Global AI Regulation Summit", "SpaceX Mars Timeline Update", "Ocean Cleanup Milestone"]

    production_queue = []
    
    for story_topic in stories:
        prompt = f"""
        You are Senior Reporter Michael Watson for Pen News.
        Write a broadcast news segment for the topic: "{story_topic}".
        
        CRITICAL INSTRUCTIONS:
        1. "anchor_script": Write a professional news script. Be direct. Do NOT use phrases like "Here are the key points", "In summary", or "Let's look at the details". Just report the news as a continuous narrative.
        2. "headlines": Provide 3 or 4 distinct facts as bullet points for the screen.
        
        Output valid JSON only with these fields:
        - "main_heading": A short, punchy 3-5 word title.
        - "content_text": A 1 sentence summary (approx 15 words) for the text display.
        - "anchor_script": The spoken script (2-3 sentences). Professional tone.
        - "headlines": Array of 3-4 strings (bullet points).
        - "visual_keyword": A simple search term for stock video (e.g. "Rocket Launch").
        - "scores": Object with integers 1-10 for "quality", "impact", "politics", "bias".
        
        JSON FORMAT ONLY. NO MARKDOWN.
        """
        
        content = ""
        try:
            from langchain_community.chat_models import ChatOllama
            from langchain_core.messages import HumanMessage
            llm = ChatOllama(model="mistral:latest", base_url="http://127.0.0.1:11435")
            response = llm.invoke([HumanMessage(content=prompt)])
            content = response.content
        except (ImportError, Exception):
            content = await query_ollama_direct(11435, prompt)

        if content:
            try:
                json_str = content.strip()
                if "```json" in json_str:
                    json_str = json_str.split("```json")[1].split("```")[0]
                elif "```" in json_str:
                    json_str = json_str.split("```")[1].split("```")[0]
                    
                data = json.loads(json_str)
                
                # --- PREPARE FULL SCRIPT (Direct Narrative) ---
                intro = data.get("anchor_script", data.get("content_text", "News update."))
                # Flatten the list of headlines into a single string for TTS
                headlines_text = ". ".join(data.get("headlines", []))
                
                # Combine: Intro + Headlines text directly (No "Here are the points")
                full_script = f"{intro} {headlines_text}"
                
                # Dynamic Duration Calculation
                word_count = len(full_script.split())
                est_duration = max(20, int(word_count / 2.3)) + 2
                
                # --- GENERATE ASSETS ---
                item_id = str(uuid.uuid4())[:8]
                audio_filename = f"{item_id}.mp3"
                # Use the FULL script for generation
                audio_path = await generate_anchor_audio(full_script, audio_filename)
                
                visual_key = data.get("visual_keyword", "News")
                video_url = await search_pexels(visual_key)

                item = {
                    "id": item_id,
                    "type": "headline",
                    "main_heading": data.get("main_heading", story_topic).upper(),
                    "content_text": data.get("content_text", ""),
                    "headlines": data.get("headlines", []),
                    "display_duration": est_duration,
                    "timestamp": int(time.time()),
                    "scores": data.get("scores", {"quality": 8, "impact": 7, "politics": 5, "bias": 1}),
                    "extra_data": {
                        "visual_keyword": visual_key,
                        "media_url": video_url, 
                        "media_type": "video",
                        "audio_url": audio_path
                    }
                }
                production_queue.append(item)
                print(f"   [Editor] Processed & Recorded ({est_duration}s): {item['main_heading']}")
            except Exception as e:
                print(f"   [Editor] Failed to process '{story_topic}': {e}")

    if production_queue:
        with open(os.path.join(QUEUE_DIR, "run_of_show.json"), "w") as f:
            json.dump(production_queue, f, indent=4)
        print(f"✅ [Trend] Saved {len(production_queue)} stories to queue.")
    
    return state

# --- 0. FORCE UNBUFFERED OUTPUT ---
sys.stdout.reconfigure(line_buffering=True)

def check_gpu_status(port, name):
    url = f"http://127.0.0.1:{port}/api/tags"
    try:
        print(f"   Testing {name} (Port {port})... ", end="", flush=True)
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            print("✅ ONLINE")
            return True
        else:
            print(f"❌ ERROR ({response.status_code})")
            return False
    except:
        print("❌ UNREACHABLE")
        return False

# --- GRAPH DEFINITIONS ---

workflow_break = StateGraph(BreakingState)
workflow_break.add_node("scan", check_wires_node)
workflow_break.add_node("analyze", analyze_urgency_node)
workflow_break.set_entry_point("scan")
workflow_break.add_edge("scan", "analyze")
workflow_break.add_edge("analyze", END)
app_break = workflow_break.compile()

workflow_trend = StateGraph(TrendingState)
workflow_trend.add_node("collect", collect_and_cluster_node)
workflow_trend.add_node("filter", safety_filter_node)
workflow_trend.add_node("editor", custom_editor_node)
workflow_trend.set_entry_point("collect")
workflow_trend.add_edge("collect", "filter")
workflow_trend.add_edge("filter", "editor")
workflow_trend.add_edge("editor", END)
app_trend = workflow_trend.compile()

workflow_ticker = StateGraph(TrendingState)
workflow_ticker.add_node("gen_ticker", custom_ticker_node)
workflow_ticker.set_entry_point("gen_ticker")
workflow_ticker.add_edge("gen_ticker", END)
app_ticker = workflow_ticker.compile()

# --- RUNNERS ---

async def run_breaking_loop():
    print(f">>> [GPU 0] Breaking Loop Started ({BREAKING_INTERVAL}s)")
    while True:
        try:
            await app_break.ainvoke({"search_results": "", "is_urgent": False})
            await asyncio.sleep(BREAKING_INTERVAL) 
        except Exception as e:
            print(f"❌ [GPU 0 Error] {e}")
            await asyncio.sleep(60)

async def run_trending_loop():
    print(f">>> [GPU 1] Trending Loop Started ({TRENDING_INTERVAL}s)")
    while True:
        try:
            print("   [Trend] Starting Cycle...")
            await app_trend.ainvoke({"raw_search_results": "", "candidates": [], "approved_stories": []})
            print(f"   ...Trend Sleep {TRENDING_INTERVAL}s...")
            await asyncio.sleep(TRENDING_INTERVAL) 
        except Exception as e:
            print(f"❌ [GPU 1 Error] {e}")
            await asyncio.sleep(60)

async def run_ticker_loop():
    print(f">>> [GPU 1] Ticker Loop Started ({TICKER_INTERVAL}s)")
    while True:
        try:
            await app_ticker.ainvoke({"raw_search": ""})
            await asyncio.sleep(TICKER_INTERVAL)
        except Exception as e:
            print(f"❌ [Ticker Error] {e}")
            await asyncio.sleep(60)

if __name__ == "__main__":
    print("\n=======================================")
    print("   DUAL GPU AI NEWS STATION STARTING   ")
    print("=======================================")
    ensure_directories()
    
    gpu0_ok = check_gpu_status(11436, "GPU 0")
    gpu1_ok = check_gpu_status(11435, "GPU 1")
    
    if not gpu0_ok or not gpu1_ok:
        print("\n[CRITICAL] GPU Offline. Check 'ollama serve'.")
        sys.exit(1)
        
    print("\n3. Loops Starting...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(asyncio.gather(
            run_breaking_loop(), run_trending_loop(), run_ticker_loop()
        ))
    except KeyboardInterrupt:
        print("\nShutting down...")