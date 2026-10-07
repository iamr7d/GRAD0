@echo off
rem Double-click to render the 3-minute Prime Earth News reel to an MP4 in the renders folder (no OBS needed).
cd /d "%~dp0"
python -m channel.render_reel %*
pause
