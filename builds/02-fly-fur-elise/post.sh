#!/bin/bash
# $1 = output mp4, $2 = number of frames (optional)
N=${2:-468}
ffmpeg -v error -y -framerate 24 -i full/f%04d.png -i fur_elise_own.wav -filter_complex \
"[0:v]trim=end_frame=$N,scale=1080:1080:flags=lanczos,split[a][b];[b]curves=all='0/0 0.72/0 1/1',gblur=sigma=22[g];[a][g]blend=all_mode=screen:all_opacity=0.3,unsharp=5:5:0.55:5:5:0,colorbalance=rs=0.04:gs=0.01:bs=-0.04:rh=0.02:bh=-0.03,eq=contrast=1.04:saturation=1.03,vignette=PI/5.5,noise=alls=2.5:allf=t,format=yuv420p[v]" \
 -map "[v]" -map 1:a -c:v libx264 -preset slow -crf 15 -profile:v high -c:a aac -b:a 192k -shortest \
 -map_metadata -1 -metadata:s:v encoder= -metadata:s:a encoder= -metadata:s:v handler_name= -metadata:s:a handler_name= \
 -fflags +bitexact -flags:v +bitexact -flags:a +bitexact -bsf:v filter_units=remove_types=6 -movflags +faststart "$1"
