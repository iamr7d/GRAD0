import json
import os

# --- Path Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUEUE_FILE = os.path.join(BASE_DIR, "bucket/news/queue/run_of_show.json")

def clean_queue(file_path):
    # 1. Load the existing data
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Queue file not found at {file_path}")
        return
    except json.JSONDecodeError:
        print("Error: Could not decode JSON. File may be corrupted.")
        return

    # 2. Filter out items where main_heading contains "Test AI News"
    # This uses a list comprehension (conditional filtering) to create a new list
    cleaned_data = [
        item for item in data
        if "Test AI News" not in item.get("main_heading", "")
    ]
    
    # 3. Save the cleaned data back to the file
    with open(file_path, 'w') as f:
        json.dump(cleaned_data, f, indent=4)
        
    print(f"✅ Cleaned {len(data) - len(cleaned_data)} dummy items.")
    print(f"   {len(cleaned_data)} production items remain in queue.")


if __name__ == "__main__":
    clean_queue(QUEUE_FILE)