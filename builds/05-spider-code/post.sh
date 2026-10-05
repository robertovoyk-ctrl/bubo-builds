#!/bin/bash
# frames + spider.wav -> 1080x1920 mp4 with neon bloom, grain and vignette, clean metadata
ffmpeg -v error -y -framerate 24 -i full/f%04d.png -i spider.wav -filter_complex \
"[0:v]scale=1080:1920:flags=lanczos,split[a][b];[b]curves=all='0/0 0.6/0 1/1',gblur=sigma=22[g];[a][g]blend=all_mode=screen:all_opacity=0.45,unsharp=5:5:0.4:5:5:0,eq=contrast=1.05:saturation=1.08,vignette=PI/5,noise=alls=3:allf=t,format=yuv420p[v]" \
 -map "[v]" -map 1:a -c:v libx264 -preset slow -crf 16 -profile:v high -c:a aac -b:a 192k -shortest \
 -map_metadata -1 -metadata:s:v encoder= -metadata:s:a encoder= -metadata:s:v handler_name= -metadata:s:a handler_name= \
 -fflags +bitexact -flags:v +bitexact -flags:a +bitexact -bsf:v filter_units=remove_types=6 -movflags +faststart "$1"
