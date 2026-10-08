#!/bin/bash
# frames + film.wav -> 1080x1920 mp4 with bloom and grain, then 2 s of the end card. Clean metadata.
set -e
DUR=$(awk -v n=$(ls full | wc -l) 'BEGIN{printf "%.4f", n/24+2.0}')
ffmpeg -v error -y -framerate 24 -i full/f%04d.png -i film.wav -filter_complex \
"[0:v]scale=1080:1920:flags=lanczos,split[a][b];[b]curves=all='0/0 0.6/0 1/1',gblur=sigma=22[g];[a][g]blend=all_mode=screen:all_opacity=0.45,unsharp=5:5:0.4:5:5:0,eq=contrast=1.05:saturation=1.08,vignette=PI/5,noise=alls=3:allf=t,format=yuv420p,fps=24[vb];movie=title.png,loop=loop=-1:size=1:start=0,fps=24,trim=duration=2.6,format=rgba,fade=out:st=2.0:d=0.5:alpha=1[ti];[vb][ti]overlay=0:0:shortest=0:eof_action=pass,format=yuv420p[v0];\
[1:a]apad=whole_dur=$DUR,atrim=0:$DUR[a];\
movie=card.png,loop=loop=-1:size=1:start=0,trim=duration=2.0,fps=24,fade=in:st=0:d=0.25,noise=alls=3:allf=t,format=yuv420p,setsar=1[c];\
[v0]setsar=1[v1];[v1][c]concat=n=2:v=1:a=0[v]" \
 -map "[v]" -map "[a]" -c:v libx264 -preset slow -crf 16 -profile:v high -c:a aac -b:a 192k \
 -map_metadata -1 -metadata:s:v encoder= -metadata:s:a encoder= -metadata:s:v handler_name= -metadata:s:a handler_name= \
 -fflags +bitexact -flags:v +bitexact -flags:a +bitexact -bsf:v filter_units=remove_types=6 -movflags +faststart "$1"
