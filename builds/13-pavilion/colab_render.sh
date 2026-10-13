#!/bin/bash
# Full-quality GPU render on Google Colab (L4): 480 frames 1920x804 -> grade -> one mp4 with sound.
# In a Colab cell (GPU runtime, Drive mounted), from this folder:  !bash colab_render.sh
cd "$(dirname "$0")"
fail(){ echo "FAILED: $1"; exit 1; }
NF=480; RES=${RES:-1920}; SPP=${SPP:-128}
if [ ! -x /content/blender/blender ]; then
  apt-get -qq install -y libxi6 libxkbcommon0 libsm6 libxrender1 libgl1 libegl1 >/dev/null 2>&1
  wget -q https://download.blender.org/release/Blender5.0/blender-5.0.1-linux-x64.tar.xz -O /tmp/b.tar.xz || fail "blender download"
  mkdir -p /content/blender && tar -xf /tmp/b.tar.xz -C /content/blender --strip-components=1 || fail "blender unpack"
fi
pip -q install soundfile >/dev/null 2>&1
# frames go to Google Drive so a disconnect never loses them; a rerun skips finished frames
if [ -d /content/drive/MyDrive ]; then
  OUT=/content/drive/MyDrive/bubo/pavilion/full; mkdir -p "$OUT"; rm -rf full; ln -sfn "$OUT" full
  echo "frames go to Google Drive: $OUT ($(ls "$OUT" | wc -l) already there)"
else
  echo "WARNING: Google Drive is not mounted, frames stay in /content and are lost if the runtime disconnects"; mkdir -p full
fi
python3 audio.py || fail "audio"
HQ=1 BUBO_GPU=1 /content/blender/blender -b --python scene.py -- full 0:$NF:1 $RES $SPP > render.log 2>&1 &
PID=$!
CHECKED=0
while kill -0 $PID 2>/dev/null; do
  sleep 30
  if [ $CHECKED = 0 ] && grep -aq '^DONE' render.log; then
    grep -aq '^GPU' render.log || { kill $PID; fail "no GPU in use (Runtime > Change runtime type > L4 GPU)"; }
    CHECKED=1
  fi
  echo "$(ls full 2>/dev/null | wc -l)/$NF frames  $(grep -a -m1 '^GPU' render.log)  last: $(grep -a DONE render.log | tail -1)"
done
N=$(ls full 2>/dev/null | wc -l)
[ "$N" -ge "$NF" ] || { grep -a -A12 Traceback render.log | tail -30; fail "render stopped at $N/$NF (rerun this cell to resume)"; }
python3 post.py full graded || fail "post"
ffmpeg -v error -y -framerate 24 -i graded/f%04d.png -i film.wav -c:v libx264 -preset slow -crf 15 -pix_fmt yuv420p \
  -c:a aac -b:a 256k -shortest -movflags +faststart /content/pavilion.mp4 || fail "ffmpeg"
[ -d /content/drive/MyDrive ] && cp /content/pavilion.mp4 /content/drive/MyDrive/bubo/pavilion.mp4 && echo "copied to Google Drive: MyDrive/bubo/pavilion.mp4"
echo "DONE -> /content/pavilion.mp4"
