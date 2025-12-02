import os

# --- PATHS ---
BASE_DIR = "/home/rahulraj/pen_stream/bucket/news"
PATH_HEADLINES = os.path.join(BASE_DIR, "headlines")
PATH_BREAKING = os.path.join(BASE_DIR, "breaking_news")
PATH_SCRIPT = os.path.join(BASE_DIR, "anchor_script")
PATH_TICKER = os.path.join(BASE_DIR, "ticker")
PATH_QUEUE = os.path.join(BASE_DIR, "queue")  # <--- NEW

# Audit Logs
PATH_RAW_SELECTED = os.path.join(BASE_DIR, "Raw/selected")
PATH_RAW_REJECTED = os.path.join(BASE_DIR, "Raw/rejected")

# Ensure dirs exist
for p in [PATH_HEADLINES, PATH_BREAKING, PATH_SCRIPT, PATH_TICKER, PATH_RAW_SELECTED, PATH_RAW_REJECTED, PATH_QUEUE]:
    os.makedirs(p, exist_ok=True)

# --- DUAL GPU CONFIG (Keep existing) ---
BREAKING_LLM_CONFIG = {
    "base_url": "http://127.0.0.1:11436/v1", 
    "api_key": "ollama",
    "model": "mistral:latest",
    "temperature": 0.1
}

TRENDING_LLM_CONFIG = {
    "base_url": "http://127.0.0.1:11435/v1",
    "api_key": "ollama",
    "model": "mistral:latest", 
    "temperature": 0.3
}

# --- RSS SOURCES (Keep your existing massive list) ---
RSS_SOURCES = {
    "WORLD": ["http://feeds.bbci.co.uk/news/world/rss.xml", "https://www.aljazeera.com/xml/rss/all.xml"],
    "TECH": ["https://techcrunch.com/feed/", "https://www.theverge.com/rss/index.xml"],
    "FINANCE": ["https://feeds.bloomberg.com/markets/news.rss"],
    # ... add the rest of your list here
}