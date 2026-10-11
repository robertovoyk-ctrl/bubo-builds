# The film's timeline, shared by film.py (3D) and hud.py (text overlay).
# Every booster position comes from flights/*.json (the simulator); nothing is animated by hand.
# A shot maps video time -> sim time with piecewise-linear keys; equal sim times = a freeze.
import json, os, bisect
HERE = os.path.dirname(os.path.abspath(__file__))
FPS = 24
ARM_Z = 100.0            # catch arms height above ground (m); sim z = 0 is the arms

def F(name):
    d = json.load(open(os.path.join(HERE, 'flights', name + '.json')))
    d['T'] = d['states'][-1][0]
    return d

# cam: 'track' = long lens on the ground following the booster, 'wide' = tower cam
# cam_cut: sim time where 'track' cuts to 'wide'
HOOKS = {   # frame-0 text variants (pick one): (line 1, line 2)
    'A': ('Grok had to', 'catch this rocket.'),
    'B': ('I gave Grok', 'a falling rocket.'),
    'C': ('Grok vs a', '71 m falling rocket.'),
}
HOOK = os.environ.get('HOOK', 'A')
SHOTS = [
    # cold open: the real v10 approach, wide, flame on, text up from frame 0
    dict(id='hook', dur=1.5, flight='agent_10_nominal', keys=[(0, 30.0), (1.5, 31.4)], cam='wide_hook'),
    # TRY 1: live. Wide follow cam keeps the tower in frame while it passes 317 m to the side and climbs away
    dict(id='live', dur=4.0, flight='realtime', keys=[(0, 15.5), (0.8, 20.2), (2.4, 24.5), (3.4, 33.3), (4.0, 33.3)],
         cam='track', inset=(-120, 480, 2600), label='TRY 1', title='Grok flies it live', thoughts=True,
         lines=['Light all engines for landing burn', 'Too far and too late to catch'],
         stamp=(3.4, 'ABORT', 'it decided 13 s too late')),
    dict(id='card2', dur=1.2, flight=None, cam='wide', card=['TRY 2', 'Give it a simulator.', 'Let it write the code.']),
    dict(id='v1', dur=1.5, flight='agent_1_nominal', keys=[(0, 21.0), (0.9, 22.74), (1.5, 22.74)], cam='track', inset=(-120, 480, 2600),
         label='v1', stamp=(1.0, 'CRASH', 'missed the tower by 249 m'), metric='speed'),
    dict(id='v3', dur=1.5, flight='agent_3_nominal', keys=[(0, 30.4), (1.0, 32.62), (1.5, 32.62)], cam='wide',
         label='v3', stamp=(1.0, 'TOO FAST', '4 m/s into the arms. limit 3'), metric='speed', hard=True),
    dict(id='v10', dur=5.3, flight='agent_10_nominal', keys=[(0, 21.0), (0.8, 25.0), (4.3, 33.7), (5.3, 33.7)],
         cam='track', cam_cut=25.0, label='v10', quote='Vertical is solved. The miss is purely sideways.',
         stamp=(4.3, 'CAUGHT', None), metric='speed'),
    dict(id='close', dur=1.5, flight='agent_10_nominal', keys=[(0, 32.6), (0.9, 33.7), (1.5, 33.7)], cam='close'),
    dict(id='end', dur=2.5, flight='agent_10_nominal', keys=[(0, 33.7), (2.5, 33.7)], cam='wide_end',
         card=['10 versions. $0.59.', '1,500 new flights.', '1,500 right.']),
]
QUOTE_AFTER = {10: 9}     # which failed version Grok was answering when it wrote the quote

_cache = {}
def flight(name):
    if name not in _cache: _cache[name] = F(name)
    return _cache[name]

t0 = 0.0
for s in SHOTS:
    s['start'] = t0; t0 += s['dur']
    if s.get('flight') and 'keys' not in s:          # montage: last `tail` video seconds play the last 2*tail sim seconds
        T = flight(s['flight'])['T']; tail = s['tail']
        s['keys'] = [(0, max(0.0, T - 2.0 * tail)), (tail, T), (s['dur'], T)]
DUR = t0
NFRAMES = int(round(DUR * FPS))

def shot_at(t):
    for s in SHOTS:
        if t < s['start'] + s['dur'] - 1e-9: return s
    return SHOTS[-1]

def sim_time(s, tl):
    k = s['keys']
    if tl <= k[0][0]: return k[0][1]
    for (a, x), (b, y) in zip(k, k[1:]):
        if tl <= b: return x + (y - x) * (tl - a) / max(b - a, 1e-9)
    return k[-1][1]

def state(name, ts):
    """Interpolated sim state at sim time ts -> dict."""
    d = flight(name); st = d['states']; times = [r[0] for r in st] if 'times' not in d else d['times']
    d['times'] = times
    i = min(max(bisect.bisect_left(times, ts), 1), len(st) - 1)
    a, b = st[i - 1], st[i]
    f = 0.0 if b[0] == a[0] else min(1.0, max(0.0, (ts - a[0]) / (b[0] - a[0])))
    r = {k: a[j] + (b[j] - a[j]) * f for j, k in enumerate(d['keys'])}
    r['lit'] = (a if f < 0.5 else b)[6]; r['tower_ok'] = (a if f < 0.5 else b)[9]
    r['end'] = ts >= d['T'] - 1e-6; r['result'] = d['result']
    return r

def frame_info(fr):
    """Everything about video frame fr that the renderer and the overlay need."""
    t = fr / FPS; s = shot_at(t); tl = t - s['start']
    out = dict(t=t, shot=s, tl=tl)
    if s.get('flight'):
        ts = sim_time(s, tl); out['ts'] = ts; out['st'] = state(s['flight'], ts)
        cam = s['cam']
        if cam == 'track' and s.get('cam_cut') is not None and ts >= s['cam_cut']: cam = 'wide'
        out['cam'] = cam
    else:
        out['cam'] = s['cam']
    return out

if __name__ == '__main__':
    for s in SHOTS:
        print(f"{s['start']:5.1f}-{s['start'] + s['dur']:5.1f}  {s['id']:7s} {s.get('flight') or '':20s} keys={s.get('keys')}")
    print('DUR', DUR, 'frames', NFRAMES)
