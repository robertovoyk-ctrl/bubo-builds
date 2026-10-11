#!/bin/bash
# One-shot GPU render on Google Colab: frames -> overlay + sound -> final 1080x1920 mp4.
# In a Colab cell (GPU runtime):  !cd /content && unzip -o -q booster_film.zip && bash booster_film/colab_render.sh
cd "$(dirname "$0")"
fail(){ echo "FAILED: $1"; exit 1; }
NF=$(python3 -c "import shots; print(shots.NFRAMES)")
if [ ! -x /content/blender/blender ]; then
  apt-get -qq install -y libxi6 libxkbcommon0 libsm6 libxrender1 libgl1 libegl1 >/dev/null 2>&1
  wget -q https://download.blender.org/release/Blender5.0/blender-5.0.1-linux-x64.tar.xz -O /tmp/b.tar.xz || fail "blender download"
  mkdir -p /content/blender && tar -xf /tmp/b.tar.xz -C /content/blender --strip-components=1 || fail "blender unpack"
fi
pip -q install soundfile >/dev/null 2>&1
# frames go to Google Drive when it is mounted, so a disconnect never loses them and a rerun resumes
if [ -d /content/drive/MyDrive ]; then
  OUT=/content/drive/MyDrive/bubo/booster-film/full; mkdir -p "$OUT"; rm -rf full; ln -sfn "$OUT" full
  echo "frames go to Google Drive: $OUT ($(ls "$OUT" | wc -l) already there)"
fi
python3 audio.py || fail "audio"
python3 hud.py hud || fail "hud"
BUBO_GPU=1 /content/blender/blender -b --python film.py -- full 0:$NF:1 ${RES:-1080} ${SPP:-64} > render.log 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do sleep 30; echo "$(ls full 2>/dev/null | wc -l)/$NF frames  $(grep -a -m1 '^GPU' render.log)  last: $(grep -a DONE render.log | tail -1)"; done
N=$(ls full 2>/dev/null | wc -l)
[ "$N" -ge "$NF" ] || { grep -a -A12 Traceback render.log | tail -30; fail "render stopped at $N/$NF"; }
./post.sh full /content/booster_film.mp4 || fail "ffmpeg"
[ -d /content/drive/MyDrive ] && cp /content/booster_film.mp4 /content/drive/MyDrive/bubo/booster_film.mp4 && echo "copied to Google Drive: MyDrive/bubo/booster_film.mp4"
echo "DONE -> /content/booster_film.mp4"
