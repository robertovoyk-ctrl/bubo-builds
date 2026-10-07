# bubo-builds

Every frame is code.

These are the builds behind the videos on [@bubosees](https://x.com/bubosees).
No video model touched any of them: scenes are written in code, rendered frame by frame,
and the sound is synthesized or played from open samples.

| # | Build | What it is | Stack |
|---|-------|------------|-------|
| 01 | [Fly on Note G](builds/01-fly-note-g) | A fruit fly walks Ada Lovelace's Note G (1843) and lights up the words it touches | Canvas, Playwright, numpy audio |
| 02 | [Fly plays Für Elise](builds/02-fly-fur-elise) | A fly on a grand piano, rendered in Blender Cycles | Blender (bpy), ffmpeg |
| 03 | [Snake arena](builds/03-snake-arena) | Three decision models play Snake on one board. Every move is a real API call, every answer is logged | Python, Canvas, ffmpeg |
| 04 | [Fly under the UFO](builds/04-fly-ufo) | A giant fruit fly in a UFO beam; the head opens and the brain lights up | Blender (bpy), numpy audio |
| 05 | [Code scanner](builds/05-spider-code) | A spider crawls down a wall of code and turns it red | Blender (bpy), numpy audio |
| 06 | [keyspider](builds/06-keyspider) | Finds API keys and passwords in a git repo, including deleted ones still in history | Python, git |
| 07 | [keyspider film](builds/07-keyspider-film) | The spider walks down real code and lights up the secrets keyspider found in it | Blender (bpy), Python, numpy audio |
| 08 | [keyspider guard](builds/08-keyspider-guard) | The spider stops a commit with two secrets in it, they move to env, the commit goes through | Blender (bpy), Python, numpy audio |
| 09 | [agent prompt](builds/09-agent-prompt) | A prompt that makes your coding agent audit a repo for leaked keys, deleted ones included | prompt, Python (PIL) card |
| 10 | [agent film](builds/10-agent-film) | The spider walks down Claude Code's real answer and lights up every leaked key it found | Blender (bpy), Python, numpy audio |

## How every build works

1. The scene is one deterministic function of time: same `t`, same frame, every render.
2. Frames are rendered headless (Playwright Chromium or Blender) to PNG.
3. Events (steps, hits, deaths) are logged with timestamps, and the audio is built from that log.
4. ffmpeg stitches frames and audio into an H.264 MP4.

## License

Code: MIT. Videos, images and audio: CC BY-NC 4.0. See [LICENSE](LICENSE) and [LICENSE-MEDIA.md](LICENSE-MEDIA.md).
