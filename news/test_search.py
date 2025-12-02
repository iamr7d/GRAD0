from duckduckgo_search import DDGS
import time

print("--- 🔍 SEARCH ENGINE DIAGNOSTIC ---")

try:
    print("Attempting to fetch 10 results...")
    # Try a simple query
    results = DDGS().news(keywords="technology", max_results=10)
    
    if results:
        print(f"✅ SUCCESS: Found {len(results)} articles.")
        print(f"   Sample: {results[0]['title']}")
    else:
        print("❌ FAILURE: Search returned 0 results. (You are Rate Limited)")

except Exception as e:
    print(f"❌ CRITICAL ERROR: {e}")