# 11 · Paste this into your agent (prompt film)

The leaked-keys prompt from [09](../09-agent-prompt), written on a wall of code. The spider crawls down beside it and every sentence lights up as it reaches it. At the end the whole prompt is on screen, big enough to read on a phone.

Built in code: Blender (bpy, Cycles) for the spider and the wall, numpy for the sound.

- `panelgen.py` – `panel.png`, the prompt split into its five sentences
- `film.py` – the scene (12 s)
- `audio_soft.py` – the score, `film.wav`
- `card.py` – end card and the opening title
- `colab_render.sh` – one-shot GPU render on Colab, then `post.sh` makes the 14 s 1080×1920 mp4
