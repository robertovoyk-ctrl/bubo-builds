#!/bin/bash
# Render on a Mac (Apple Silicon GPU via Metal). Frames are kept in ./full, so a rerun resumes where it stopped.
# Usage: RES=720 SPP=20 bash mac_render.sh
cd "$(dirname "$0")"
fail(){ echo "FAILED: $1"; exit 1; }
B=/Applications/Blender.app/Contents/MacOS/Blender
[ -x "$B" ] || fail "Blender not found at $B (install it with: brew install --cask blender)"
command -v ffmpeg >/dev/null || fail "ffmpeg missing (brew install ffmpeg)"
python3 -c "import numpy, scipy, soundfile" 2>/dev/null || python3 -m pip install --user -q numpy scipy soundfile || fail "python packages"
python3 audio_soft.py || fail "audio"
[ -f card.png ] && [ -f title.png ] || fail "card.png or title.png missing"
mkdir -p full
BUBO_GPU=1 caffeinate -dimsu "$B" -b --python film.py -- full 0:336:1 ${RES:-720} ${SPP:-20} frames > render.log 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do sleep 30; echo "$(ls full | wc -l | tr -d ' ')/336 frames  $(grep -a -m1 '^GPU' render.log)  last: $(grep -a DONE render.log | tail -1)"; done
N=$(ls full | wc -l | tr -d ' ')
[ "$N" -ge 336 ] || { grep -a -A12 Traceback render.log | tail -30; fail "render stopped at $N/336"; }
bash post.sh "$HOME/Desktop/agent_film.mp4" || fail "ffmpeg"
echo "DONE -> ~/Desktop/agent_film.mp4"
