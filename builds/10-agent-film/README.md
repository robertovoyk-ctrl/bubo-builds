# 10 · Paste this into your agent (film)

The spider walks down Claude Code's real answer to the leaked-keys prompt from [09](../09-agent-prompt) and lights up every key it reported, including the one that was deleted but is still in git history.

`agent_result.txt` is the agent's actual output on a throwaway demo repo with random fake keys (masked to 6 characters). `panelgen.py` turns it into the code panel the spider walks on.

Built in code: Blender (bpy, Cycles) for the spider and the code wall, numpy for the sound.

- `panelgen.py` – `panel.png` from `agent_result.txt`
- `film.py` – the scene
- `audio_soft.py` – the score, `film.wav`
- `card.py` – end card and the opening title
- `colab_render.sh` – one-shot GPU render on Colab, then `post.sh` makes the 1080×1920 mp4
