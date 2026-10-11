# Dense trajectories for the film, straight from the simulator.
#  - realtime / frozen runs: replay Grok's logged commands at their logged times (sim is deterministic)
#  - code runs: fly Grok's own code again
# Writes film/flights/<name>.json: every 0.02 s state + the decision lines (with Grok's "why" when it gave one).
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import sim
from grok_pilot import build_codegen_pilot
RUNS = os.path.join(ROOT, 'runs')
OUT = os.path.join(HERE, 'flights'); os.makedirs(OUT, exist_ok=True)

def fly_dense(pilot, seed, scenario, latency=0.0, decide_every=0.1, dt=0.02):
    b = sim.Booster(seed, scenario); queue = []; next_dec = 0.0; dec = []; states = []
    def snap():
        states.append([round(b.t, 3), round(b.x, 2), round(b.z, 2), round(b.vx, 2), round(b.vz, 2), round(b.tilt, 2),
                       b.lit() if b.fuel > 0 else 0, round(b.throttle, 2), round(b.fins, 2), int(b.tower_ok), round(b.fuel)])
    snap()
    while not b.done:
        if b.t >= next_dec - 1e-9:
            tel = b.telemetry(); cmd = pilot(tel)
            lat = latency(tel) if callable(latency) else latency
            queue.append((b.t + lat, cmd)); queue.sort(key=lambda q: q[0])
            dec.append(dict(t=round(b.t, 2), applies_at=round(b.t + lat, 2), cmd=cmd, tel=tel))
            next_dec = b.t + (decide_every(tel) if callable(decide_every) else decide_every)
        while queue and queue[0][0] <= b.t + 1e-9:
            b.apply(queue.pop(0)[1])
        b.step(dt); snap()
    return b.result, states, dec

def replay(logfile):
    d = json.load(open(os.path.join(RUNS, logfile))); steps = d['steps']; i = {'k': 0}
    def pilot(tel):
        s = steps[i['k']]; i['k'] += 1
        assert abs(s['tel']['altitude_m'] - tel['altitude_m']) < 0.2 and abs(s['tel']['distance_to_tower_m'] - tel['distance_to_tower_m']) < 0.2, (s['tel'], tel)
        return s['cmd']
    lat = lambda tel: steps[i['k'] - 1]['applies_at'] - steps[i['k'] - 1]['t']
    nxt = lambda tel: (steps[i['k']]['t'] - steps[i['k'] - 1]['t']) if i['k'] < len(steps) else 999
    res, st, dec = fly_dense(pilot, d['seed'], d['scenario'], latency=lat, decide_every=nxt)
    assert res == d['result'], (res, d['result'])
    return d['seed'], d['scenario'], res, st, dec

STATE_KEYS = ['t', 'x', 'z', 'vx', 'vz', 'tilt', 'lit', 'throttle', 'fins', 'tower_ok', 'fuel']
def save(name, seed, scenario, res, st, dec, source):
    keep = [dict(t=e['t'], applies_at=e['applies_at'], why=e['cmd'].get('why', ''), engines=e['cmd'].get('engines'),
                 abort=bool(e['cmd'].get('abort'))) for e in dec] if 'code' not in source else []
    json.dump(dict(name=name, seed=seed, scenario=scenario, result=res, source=source, keys=STATE_KEYS, states=st, decisions=keep),
              open(os.path.join(OUT, name + '.json'), 'w'))
    zmax = max(s[2] for s in st); last = st[-1]
    print(f"{name:22s} {scenario:11s} seed {seed}: {res:45s} T={last[0]:.1f}s  peak alt {zmax:.0f} m  end x={last[1]:.1f} vz={last[4]:.1f}  decisions {len(dec)}")

for name, f in [('realtime', 'grok-4.7_realtime_nominal_0.json'), ('frozen0', 'grok-4.7_frozen_nominal_0.json'),
                ('frozen1', 'grok-4.7_frozen_nominal_1.json'), ('frozen2', 'grok-4.7_frozen_nominal_2.json')]:
    seed, sc, res, st, dec = replay(f); save(name, seed, sc, res, st, dec, 'replay of ' + f)

SEED = int(os.environ.get('SEED', 1))
for v in list(range(1, 11)) + ['final']:
    code = open(os.path.join(RUNS, f'agent_grok-4.7_{v if v == "final" else "v%d" % v}.py')).read()
    for sc in (['nominal', 'engine_out', 'tower_fault'] if v == 'final' else ['nominal']):
        res, st, dec = fly_dense(build_codegen_pilot(code), SEED, sc)
        save(f'agent_{v}_{sc}', SEED, sc, res, st, dec, f'code agent v{v}')
