#!/bin/bash
# Render the booster film on a Mac (Apple Silicon GPU via Metal). Frames stay in ./full, so a rerun resumes.
#   TEST=1 bash mac_render.sh          -> renders 3 frames at full quality, prints seconds per frame and the total estimate
#   bash mac_render.sh                 -> full film, then ~/Desktop/booster_film.mp4
#   RES=1080 SPP=64 by default (max quality). Lower SPP (e.g. 32) halves the time.
cd "$(dirname "$0")"
fail(){ echo "FAILED: $1"; exit 1; }
B=""
for c in /Applications/Blender.app "$HOME/Applications/Blender.app"; do [ -x "$c/Contents/MacOS/Blender" ] && B="$c/Contents/MacOS/Blender"; done
[ -n "$B" ] || fail "Blender not found in /Applications or ~/Applications"
python3 -c "import numpy, scipy, soundfile, PIL, imageio_ffmpeg" 2>/dev/null || python3 -m pip install --user -q numpy scipy soundfile pillow imageio-ffmpeg || fail "python packages"
export FFMPEG=$(command -v ffmpeg || python3 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")
[ -x "$FFMPEG" ] || fail "no ffmpeg"
NF=$(python3 -c "import shots; print(shots.NFRAMES)")
RES=${RES:-1080}; SPP=${SPP:-64}
if [ -n "$TEST" ]; then
  rm -rf test_hq; S=$(date +%s)
  BUBO_GPU=1 "$B" -b --python film.py -- test_hq 0,245,372 $RES $SPP 2>&1 | grep -aE "^GPU|DONE"
  T=$(( $(date +%s) - S )); PER=$(( T / 3 ))
  echo "about $PER s per frame -> full film about $(( PER * NF / 60 )) min at RES=$RES SPP=$SPP"
  exit 0
fi
python3 audio.py || fail "audio"
python3 hud.py hud || fail "hud"
mkdir -p full
BUBO_GPU=1 caffeinate -dimsu "$B" -b --python film.py -- full 0:$NF:1 $RES $SPP > render.log 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do sleep 30; echo "$(ls full | wc -l | tr -d ' ')/$NF frames  $(grep -a -m1 '^GPU' render.log)  last: $(grep -a DONE render.log | tail -1)"; done
N=$(ls full | wc -l | tr -d ' ')
[ "$N" -ge "$NF" ] || { grep -a -A12 Traceback render.log | tail -30; fail "render stopped at $N/$NF"; }
bash post.sh full "$HOME/Desktop/booster_film.mp4" || fail "ffmpeg"
echo "DONE -> ~/Desktop/booster_film.mp4"
