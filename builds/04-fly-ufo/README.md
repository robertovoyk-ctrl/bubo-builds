# 04 · Fly under the UFO

A giant fruit fly stands in a UFO beam in a night desert. The camera pushes into its head, the head capsule opens like petals, the brain lights up, then everything closes and the eyes flare.

Everything is procedural, written in code for Blender / Cycles: terrain, rocks, saucer, fly anatomy, neurons, and a numpy-synthesised score. No samples, no assets except the wing texture.

- `scene.py` builds and renders the scene (`BUBO_GPU=1` uses OptiX/CUDA when present)
- `audio.py` writes `ufo.wav`
- `post.sh` turns frames + audio into a 1080×1920 mp4
- `colab_render.sh` runs the whole pipeline on a Colab GPU
