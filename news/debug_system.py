import os
import time
import requests
from duckduckgo_search import DDGS
from langchain_openai import ChatOpenAI
from config import TRENDING_LLM_CONFIG

print("--- 🔍 SYSTEM DIAGNOSTIC TOOL ---")

# 1. TEST FILE SYSTEM
print("\n[1] Testing File Write Permissions...")
try:
    test_path = "/home/rahulraj/pen_stream/bucket/news/anchor_script/write_test.txt"
    with open(test_path, "w") as f:
        f.write("Write Access OK")
    os.remove(test_path)
    print("✅ File System: OK")
except Exception as e:
    print(f"❌ File System Error: {e}")

# 2. TEST SEARCH ENGINE (The likely culprit)
print("\n[2] Testing DuckDuckGo Search...")
try:
    print("   Querying 'test' (max_results=5)...")
    start = time.time()
    # Set a strict timeout logic if possible, or just simplistic call
    results = DDGS().news(keywords="technology", max_results=5)
    duration = time.time() - start
    
    if results:
        print(f"✅ Search: OK ({len(results)} results in {duration:.2f}s)")
    else:
        print("❌ Search: Returned Empty List (SOFT BLOCK ACTIVE)")
except Exception as e:
    print(f"❌ Search Error: {e}")

# 3. TEST OLLAMA (GPU 1)
print("\n[3] Testing Local AI (GPU 1 / Port 11435)...")
try:
    llm = ChatOpenAI(**TRENDING_LLM_CONFIG)
    print("   Sending 'Hello' to Mistral...")
    response = llm.invoke("Reply with just the word: 'Online'.")
    print(f"✅ LLM Response: {response.content}")
except Exception as e:
    print(f"❌ LLM Error: {e}")
    print("   (Check if 'ollama serve' is running on port 11435)")

print("\n--- DIAGNOSTIC COMPLETE ---")