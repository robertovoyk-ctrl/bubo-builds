#!/bin/bash
# $1 log json, $2 output mp4
set -e
rm -rf fr && python3 rend.py video "$1" fr x > /dev/null && python3 audio.py
ffmpeg -v error -y -framerate 60 -i fr/f%05d.png -i arena.wav -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -profile:v high -c:a aac -b:a 192k -shortest -map_metadata -1 -metadata:s:v encoder= -metadata:s:a encoder= -metadata:s:v handler_name= -metadata:s:a handler_name= -fflags +bitexact -flags:v +bitexact -flags:a +bitexact -bsf:v filter_units=remove_types=6 -movflags +faststart "$2"
ffprobe -v error -show_entries format=duration -of compact=p=0 "$2"
