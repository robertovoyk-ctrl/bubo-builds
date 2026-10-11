# 12 · Grok catches a rocket

A falling booster, a tower with two catch arms, and Grok making the calls.

**Try 1, live.** Grok (`grok-4.7` through the xAI API) flies the booster itself, one decision at a time, while the simulation keeps running. One decision took 13 s to come back. The booster passed the tower 317 m to the side and climbed to 2.1 km before the abort landed.

**Try 2, simulator.** Grok gets three tools and writes its own flight computer (a Python function that runs at 10 Hz):

- `run_tests(code)` runs 15 test flights (nominal, tower fault, two engines out; seeds 0–4)
- `inspect_flight(code, scenario, seed, t_from, t_to)` returns telemetry and its own commands every 0.5 s
- `submit(code)`

It went from 5/15 to 15/15 in 17 steps and 10 versions. Total API cost: $0.587.
Graded afterwards on 1,500 flights it never saw (seeds 100–599, three scenarios): 1,500 right.

Every version it wrote is in `runs/`, and so is its full log (`agent_grok-4.7_transcript.json`), including the step where it works out on its own that the burn has to be one continuous hoverslam.

## The simulator

`sim.py`, about 150 lines. 2D: height above the catch arms and distance from the tower.
Gravity, drag that thins with altitude, steady wind plus gusts, grid fins that only bite when falling fast,
3 or 13 engines at 40–100 % throttle, a 1.5 s light-up delay, no hovering, 45 t of landing fuel.
A catch needs |x| < 6 m, |vz| < 3 m/s, |vx| < 2 m/s, tilt < 10° and a healthy tower.
Numbers are public ballparks, not anyone's flight software.

## Run it

```
python3 check_unseen.py                    # grade the final flight computer on 1,500 new flights, no API
python3 check_unseen.py runs/agent_grok-4.7_v3.py 5 55
XAI_API_KEY=... python3 grok_agent.py --model grok-4.7 --extra '{"reasoning_effort":"low"}' --budget 1.30
XAI_API_KEY=... python3 grok_pilot.py --provider xai --model grok-4.7 --mode realtime --scenario nominal --seeds 0 --budget 0.20
```

`--budget` is a hard stop in dollars, checked before every call.

## The film

`film/`: every booster position, tilt, engine and grid-fin state in the video comes from these flights.
`extract.py` replays Grok's logged live and frozen runs and re-flies each version of its code, `film.py` renders the scene in Blender (Cycles), `hud.py` draws the text, `audio.py` builds the sound from the same flight data.

- `colab_render.sh` – one-shot GPU render on Colab, then `post.sh` makes the 19 s 1080×1920 mp4
- `mac_render.sh` – the same on a Mac
