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
# keep frames on Google Drive when it is mounted, so a disconnect never loses them and a rerun resumes
if [ -d /content/drive/MyDrive ]; then
  OUT=/content/drive/MyDrive/bubo/11-prompt-film/full; mkdir -p "$OUT"; rm -rf full; ln -sfn "$OUT" full
  echo "frames go to Google Drive: $OUT ($(ls "$OUT" | wc -l) already there)"
fi
python3 audio_soft.py || fail "audio"
[ -f card.png ] && [ -f title.png ] || fail "card.png or title.png missing"
BUBO_GPU=1 /content/blender/blender -b --python film.py -- full 0:288:1 ${RES:-1080} ${SPP:-32} frames > render.log 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do sleep 30; echo "$(ls full 2>/dev/null | wc -l)/288 frames  $(grep -a -m1 '^GPU' render.log)  last: $(grep -a DONE render.log | tail -1)"; done
N=$(ls full 2>/dev/null | wc -l)
[ "$N" -ge 288 ] || { grep -a -A12 Traceback render.log | tail -30; fail "render stopped at $N/288"; }
chmod +x post.sh && ./post.sh /content/prompt_film.mp4 || fail "ffmpeg"
[ -d /content/drive/MyDrive ] && cp /content/prompt_film.mp4 /content/drive/MyDrive/bubo/prompt_film.mp4 && echo "copied to Google Drive: MyDrive/bubo/prompt_film.mp4"
echo "DONE -> /content/prompt_film.mp4"
