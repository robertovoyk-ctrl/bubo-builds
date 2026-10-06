# 08 · keyspider guard (film)

The spider sits on a commit before it happens. It walks down what the commit adds, stops on a hardcoded Stripe key and a database password, and blocks the commit. The two lines move to environment variables, and the same commit goes through clean.

The commit on screen is real: `guardatlas.py` builds a small demo project, stages it, and runs the actual [keyspider](../06-keyspider) guard (`--staged`) on it. The two blocked lines and the labels come from that run. Every key in the demo project is random and fake.

Built entirely in code: Blender (bpy, Cycles) for the spider and the code wall, numpy for the sound.

## Files

- `guardatlas.py` – demo repo, real guard run, renders `panel.png` (the commit) and `panel_fixed.png` (after the fix)
- `film.py` – the scene, `python3.11 film.py -- <outdir> <times> <width> <samples>`
- `audio.py` – the score, `film.wav`
- `card.py` – end card, `card.png`
- `colab_render.sh` – one-shot GPU render on Colab, then `post.sh` makes the 1080×1920 mp4

## Use the guard on your own repo

```bash
python3 ../06-keyspider/keyspider.py /path/to/your/repo --install-hook
```
