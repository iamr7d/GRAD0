@echo off
rem Double-click to start Prime Earth News: opens the newsroom and the broadcast server in two windows.
cd /d "%~dp0"
git pull
start "Newsroom" cmd /k "set FFMPEG=ffmpeg&& set FFPROBE=ffprobe&& python -m channel.run --no-llm"
start "Broadcast server" cmd /k "python -m channel.server"
timeout /t 4 >nul
start "" "http://127.0.0.1:8000/"
