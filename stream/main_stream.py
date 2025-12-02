


from graphics_engine import NewsGraphics
import os
import subprocess
import time

# PATHS
BASE_DIR = "/home/rahulraj/pen_stream"
INPUT_DIR = os.path.join(BASE_DIR, "bucket/news/anchor_script")
OUTPUT_DIR = os.path.join(BASE_DIR, "stream/assets/job_queue")
PROCESSED_DIR = os.path.join(BASE_DIR, "stream/processed")

# Ensure directories exist
for p in [OUTPUT_DIR, PROCESSED_DIR]:
    os.makedirs(p, exist_ok=True)

# Initialize Engines
gfx = NewsGraphics()

INTRO_VIDEO = "/home/rahulraj/pen_stream/intro.mp4"
INTRO_INTERVAL = 360  # seconds
last_intro_time = 0

def play_intro_video():
    print("Playing intro video...")
    subprocess.Popen(["/home/rahulraj/pen_stream/ffmpeg-git-20240629-amd64-static/ffmpeg", "-re", "-i", INTRO_VIDEO, "-f", "null", "-"])

def process_news():
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith(".json")]
    if not files:
        print("No new news to process.")
        return
    for filename in files:
        json_path = os.path.join(INPUT_DIR, filename)
        try:
            print(f"\n[Director] Processing Show: {filename}")
            with open(json_path, 'r') as f:
                show_data = json.load(f)
            # Create a unique folder for this show's assets
            job_id = filename.replace("broadcast_", "").replace(".json", "")
            job_folder = os.path.join(OUTPUT_DIR, job_id)
            os.makedirs(job_folder, exist_ok=True)
            # --- PROCESS INTRO ---
            if "show_intro" in show_data:
                generate_voice_segment(show_data['show_intro'], os.path.join(job_folder, "00_intro.wav"))
            # --- PROCESS SEGMENTS ---
            segments = show_data.get('segments', [])
            for i, seg in enumerate(segments):
                # 1. Generate Audio
                audio_name = f"seg_{i+1:02d}.wav"
                generate_voice_segment(seg['tts_script'], os.path.join(job_folder, audio_name))
                # 2. Generate Graphic Overlay
                image_name = f"seg_{i+1:02d}.png"
                gfx.create_overlay(
                    main_heading=seg['main_heading'], 
                    headlines=seg['headlines'], 
                    output_path=os.path.join(job_folder, image_name)
                )
            # --- PROCESS OUTRO ---
            if "show_outro" in show_data:
                generate_voice_segment(show_data['show_outro'], os.path.join(job_folder, "99_outro.wav"))
            # Move processed JSON to archive
            shutil.move(json_path, os.path.join(PROCESSED_DIR, filename))
            print(f"✅ Job Complete! Assets ready in: {job_folder}")
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")
            time.sleep(5)


print("--- 🎬 VISUAL ASSET FACTORY ONLINE ---")
print(f"Watching: {INPUT_DIR}")

# Play intro video once at the start
play_intro_video()
time.sleep(10)  # Wait for intro to finish (adjust duration as needed)

while True:
    process_news()
    time.sleep(2)
