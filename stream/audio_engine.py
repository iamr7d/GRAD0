import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import save

# 1. Load the .env file
load_dotenv()

# 2. Get Config
API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "Rachel") # Default to Rachel if missing

if not API_KEY:
    print("❌ ERROR: ELEVENLABS_API_KEY not found in .env file!")

# 3. Initialize Client
client = ElevenLabs(api_key=API_KEY)

def generate_voice_segment(text, output_path):
    """Generates audio using ElevenLabs Cloud API"""
    print(f"☁️  ElevenLabs Voicing ({VOICE_ID}): {text[:30]}...")
    
    try:
        # Generate the audio
        audio = client.generate(
            text=text,
            voice=VOICE_ID,
            model="eleven_turbo_v2" 
        )
        
        # Save to file
        save(audio, output_path)
        print(f"✅ Saved: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"❌ ElevenLabs Error: {e}")
        return None