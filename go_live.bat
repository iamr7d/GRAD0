@echo off
rem Double-click to put Prime Earth News live on the web: starts the newsroom, then streams the channel
rem to a public watch page. The public link is printed below (your own domain if you ran
rem python -m channel.setup_domain, otherwise a random https://....trycloudflare.com/watch).
rem Keep both windows open. Ctrl+C in this window ends the stream.
cd /d "%~dp0"
git pull
start "Newsroom" cmd /k "set FFMPEG=ffmpeg&& set FFPROBE=ffprobe&& python -m channel.run --no-llm"
python -m channel.live --public %*
pause
