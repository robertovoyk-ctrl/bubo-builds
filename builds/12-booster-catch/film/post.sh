#!/bin/bash
# render frames (any size) + hud overlay + film.wav -> 1080x1920 mp4. Bloom on the picture only, text stays crisp.
#   ./post.sh <frames dir> <out.mp4>
set -e
cd "$(dirname "$0")"
FR=${1:-full}; OUT=${2:-booster_film.mp4}
[ -d hud ] && [ $(ls hud | wc -l) -ge $(ls $FR | wc -l) ] || python3 hud.py hud
[ -f film.wav ] || python3 audio.py
"${FFMPEG:-ffmpeg}" -v error -y -framerate 24 -i $FR/f%04d.png -framerate 24 -i hud/h%04d.png -i film.wav -filter_complex \
"[0:v]scale=1080:1920:flags=lanczos,split[a][b];[b]curves=all='0/0 0.62/0 1/1',gblur=sigma=26[g];[a][g]blend=all_mode=screen:all_opacity=0.5,eq=contrast=1.04:saturation=1.1,vignette=PI/5,noise=alls=3:allf=t,format=rgba[p];\
[p][1:v]overlay=0:0:format=auto,format=yuv420p[v]" \
 -map "[v]" -map 2:a -shortest -c:v libx264 -preset slow -crf 17 -profile:v high -c:a aac -b:a 192k \
 -map_metadata -1 -metadata:s:v encoder= -metadata:s:a encoder= -fflags +bitexact -flags:v +bitexact -flags:a +bitexact \
 -movflags +faststart "$OUT"
echo "-> $OUT"
