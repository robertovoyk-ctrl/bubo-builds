#!/bin/bash
# One-shot GPU render on Google Colab: frames -> audio -> final 1080x1920 mp4
cd "$(dirname "$0")"
fail(){ echo "FAILED: $1"; exit 1; }
if [ ! -x /content/blender/blender ]; then
  apt-get -qq install -y libxi6 libxkbcommon0 libsm6 libxrender1 libgl1 libegl1 >/dev/null 2>&1
  wget -q https://download.blender.org/release/Blender5.0/blender-5.0.1-linux-x64.tar.xz -O /tmp/b.tar.xz || fail "blender download"
  mkdir -p /content/blender && tar -xf /tmp/b.tar.xz -C /content/blender --strip-components=1 || fail "blender unpack"
fi
pip -q install soundfile >/dev/null 2>&1
python3 audio.py || fail "audio"
BUBO_GPU=1 /content/blender/blender -b --python scene.py -- full 0:672:1 ${RES:-608} ${SPP:-10} frames > render.log 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do sleep 30; echo "$(ls full 2>/dev/null | wc -l)/672 frames  $(grep -m1 '^GPU' render.log)  last: $(grep DONE render.log | tail -1)"; done
N=$(ls full 2>/dev/null | wc -l)
[ "$N" -ge 672 ] || { grep -A12 Traceback render.log | tail -30; fail "render stopped at $N/672"; }
chmod +x post.sh && ./post.sh /content/fly_ufo.mp4 || fail "ffmpeg"
echo "DONE -> /content/fly_ufo.mp4"
