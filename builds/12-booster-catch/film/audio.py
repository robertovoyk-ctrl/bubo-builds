# Sound for the booster film, driven by the same frames as the picture:
# air rush follows the booster's real speed, engine roar follows engines x throttle, booms at real impacts,
# a clank and a major chord at the catch, a low pulse that tightens through the montage.
import os, sys
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import shots
SR = 48000; DUR = shots.DUR; N = int(SR * DUR); rng = np.random.RandomState(11)
t = np.arange(N) / SR; mix = np.zeros((N, 2))
def ss(a, b, x): u = np.clip((x - a) / (b - a), 0, 1); return u * u * (3 - 2 * u)
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
def bp(x, a, b, o=2): return sosfilt(butter(o, [a, b], 'band', fs=SR, output='sos'), x)
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def put(sig, at, pan=0.0, g=1.0):
    i = int(at * SR); j = min(N, i + len(sig))
    if j <= i: return
    s = sig[:j - i] * g; mix[i:j, 0] += s * (1 - pan) * .7; mix[i:j, 1] += s * (1 + pan) * .7

# --- per-frame envelopes from the sim
F = shots.NFRAMES; spd = np.zeros(F); eng = np.zeros(F); cut = np.zeros(F)
prev = None
for fr in range(F):
    i = shots.frame_info(fr); s = i['shot']
    if s is not prev: cut[fr] = 1; prev = s
    if 'st' in i and not s.get('card'):
        st = i['st']
        frozen = fr > 0 and shots.frame_info(fr - 1).get('ts') == i['ts']
        if not st['end'] and not frozen:
            spd[fr] = min(1.0, abs(st['vz']) / 300.0)
            eng[fr] = (st['lit'] / 13.0) ** 0.6 * (0.5 + 0.5 * st['throttle']) if st['lit'] else 0.0
ft = np.arange(F) / shots.FPS
spd_s = np.interp(t, ft, spd); eng_s = np.interp(t, ft, eng)
k = int(0.05 * SR); kern = np.ones(k) / k
spd_s = np.convolve(spd_s, kern, 'same'); eng_s = np.convolve(eng_s, kern, 'same')
noise = rng.normal(0, 1, N)
air = bp(noise, 300, 2400) * (0.25 + 0.75 * spd_s) * spd_s * 0.10
brown = lp(np.cumsum(rng.normal(0, 1, N)) * 0.02 - lp(np.cumsum(rng.normal(0, 1, N)) * 0.02, 20), 180)
crackle = bp(rng.normal(0, 1, N) * (rng.random(N) < 0.02), 800, 5000)
roar = (brown / (np.abs(brown).max() + 1e-9) * 0.9 + crackle * 0.6) * eng_s * 0.55
mix += np.stack([air + roar, air * 0.9 + roar], 1)

# --- events
for s in shots.SHOTS:
    if not s.get('flight') or s['id'] == 'end': continue
    T = shots.flight(s['flight'])['T']; res = shots.flight(s['flight'])['result']
    for (a, x), (b, y) in zip(s['keys'], s['keys'][1:]):
        if y >= T - 1e-6 and x < T - 1e-6:
            at = s['start'] + a + (b - a) * (T - x) / (y - x); break
    else: continue
    if res.startswith('crashed'):
        n = int(1.6 * SR); tt = np.arange(n) / SR
        boom = np.sin(2 * np.pi * 55 * tt * (1 - 0.35 * tt)) * np.exp(-tt * 3.5) + lp(rng.normal(0, 1, n), 900) * np.exp(-tt * 4.5) * 0.8
        put(boom * 0.55, at)
    elif res == 'CAUGHT':
        n = int(1.2 * SR); tt = np.arange(n) / SR
        clank = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt * d) for f, d in ((180, 6), (431, 9), (977, 14), (1660, 20)))
        put(clank * 0.12, at); put(lp(rng.normal(0, 1, int(0.08 * SR)), 3000) * 0.3, at)
    elif res == 'aborted to sea':
        n = int(0.22 * SR); tt = np.arange(n) / SR
        for j in range(3):
            put(np.sin(2 * np.pi * (660 if j % 2 == 0 else 520) * tt) * ss(0, 0.01, tt) * (1 - ss(0.18, 0.22, tt)) * 0.06, at + j * 0.26)

# --- music: low pulse, tighter in the montage, resolves at the catch
def pad(notes, a, b, fade=1.0, g=0.05):
    out = np.zeros(N)
    for m in notes:
        for det in (-0.06, 0.0, 0.05):
            out += sum(np.sin(2 * np.pi * hz(m + det) * k_ * t + rng.uniform(0, 6)) / k_ ** 1.7 for k_ in (1, 2, 3))
    return lp(out, 1100) * g / len(notes) * ss(a, a + fade, t) * (1 - ss(b - fade, b, t))
v1 = next(s['start'] for s in shots.SHOTS if s['id'] == 'v1')
v10 = next(s for s in shots.SHOTS if s['id'] == 'v10'); catch_t = v10['start'] + v10['stamp'][0]
mix += pad([45, 52, 57, 60], 0.0, catch_t + 0.3, 1.5, 0.06)[:, None]
mix += pad([48, 55, 60, 64, 67], catch_t - 0.1, DUR, 0.6, 0.075)[:, None]
beat = 0.0
while beat < catch_t:
    bpm = 84 if beat < v1 else 112
    n = int(0.3 * SR); tt = np.arange(n) / SR
    put(np.sin(2 * np.pi * 52 * tt * (1 - 0.4 * tt)) * np.exp(-tt * 14) * 0.16, beat)
    beat += 60.0 / bpm
for j, m in enumerate((60, 64, 67, 72, 76)):
    n = int(3.0 * SR); tt = np.arange(n) / SR; f = hz(m)
    put((np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2.76 * f * tt) * np.exp(-tt * 4)) * np.exp(-tt * 1.4) * 0.05,
        catch_t + 0.12 + 0.06 * j, -0.4 + 0.2 * j)

ir_n = int(1.4 * SR); irt = np.arange(ir_n) / SR
ir = rng.normal(0, 1, (ir_n, 2)) * np.exp(-irt * 4.0)[:, None]
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix + wet * (np.abs(mix).max() / (np.abs(wet).max() + 1e-9)) * 0.25
out *= (ss(0, 0.3, t) * (1 - ss(DUR - 1.0, DUR, t)))[:, None]
out = np.tanh(out / np.abs(out).max() * 1.4) * 0.7
sf.write(os.path.join(HERE, 'film.wav'), out.astype(np.float32), SR); print('ok', out.shape, round(DUR, 2))
