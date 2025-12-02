#!/usr/bin/env bash
# Trigger script to generate a news item using the stream venv
set -e
BASE_DIR="/home/rahulraj/pen_stream"
VENV_PY="$BASE_DIR/stream/venv_stream/bin/python3"
SCRIPT="$BASE_DIR/news/add_test_item.py"
LOG="$BASE_DIR/tools/trigger_generation.log"

# Run and append timestamped output to log
echo "--- trigger run: $(date -u +'%Y-%m-%dT%H:%M:%SZ') ---" >> "$LOG"
if [ -x "$VENV_PY" ]; then
  "$VENV_PY" "$SCRIPT" >> "$LOG" 2>&1 || echo "script failed" >> "$LOG"
else
  python3 "$SCRIPT" >> "$LOG" 2>&1 || echo "script failed (system python)" >> "$LOG"
fi
