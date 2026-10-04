#!/bin/bash
# frames (720x1280) + ufo.wav -> 1080x1920 mp4 with soft bloom and grade, clean metadata
ffmpeg -v error -y -framerate 24 -i full/f%04d.png -i ufo.wav -filter_complex \
"[0:v]scale=1080:1920:flags=lanczos,split[a][b];[b]curves=all='0/0 0.7/0 1/1',gblur=sigma=26[g];[a][g]blend=all_mode=screen:all_opacity=0.35,unsharp=5:5:0.5:5:5:0,eq=contrast=1.04:saturation=1.06,vignette=PI/5,noise=alls=2:allf=t,format=yuv420p[v]" \
 -map "[v]" -map 1:a -c:v libx264 -preset slow -crf 16 -profile:v high -c:a aac -b:a 192k -shortest \
 -map_metadata -1 -metadata:s:v encoder= -metadata:s:a encoder= -metadata:s:v handler_name= -metadata:s:a handler_name= \
 -fflags +bitexact -flags:v +bitexact -flags:a +bitexact -bsf:v filter_units=remove_types=6 -movflags +faststart "$1"
