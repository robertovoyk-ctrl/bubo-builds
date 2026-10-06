# Score for the keyspider guard film, synthesised with numpy (no samples). Writes film.wav.
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve
SR = 48000; DUR = 14.0; N = int(SR * DUR); rng = np.random.RandomState(4)
t = np.arange(N) / SR; mix = np.zeros((N, 2))
TS = 0.40; JUMP0 = 13.15; END = 13.62
def ss(a, b, x): u = np.clip((x - a) / (b - a), 0, 1); return u * u * (3 - 2 * u)
def put(sig, at, pan=0.0, g=1.0):
    i = int(at * SR); j = min(N, i + len(sig))
    if j <= i or i < 0: return
    s = sig[:j - i] * g; mix[i:j, 0] += s * (1 - pan) * .7; mix[i:j, 1] += s * (1 + pan) * .7
def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, hi], 'band', fs=SR, output='sos'), x)
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
def env(n, a, d): k = np.arange(n) / SR; return np.minimum(1, k / max(a, 1e-4)) * np.exp(-k * d)

# digital bed: low hum + filtered noise, gone after the cut to black
hum = sum(np.sin(2 * np.pi * f * t + p) for f, p in ((55, 0), (55.7, 1.3), (110, .4), (164.8, 2.0))) / 4
bed = hum * 0.11 + bp(rng.normal(0, 1, N), 2500, 7000) * 0.012
bed *= ss(0.0, 1.5, t) * (1 - ss(END - 0.02, END + 0.02, t))
mix += bed[:, None]
# code switching on: a dense patter of tiny clicks, rows lighting up
for k in range(260):
    at = rng.uniform(0.15, 2.1); n = int(0.006 * SR)
    put(bp(rng.normal(0, 1, n), 3000, 9000) * env(n, 0.0005, 600), at, rng.uniform(-0.8, 0.8), 0.09 * rng.uniform(0.4, 1))
# background code chatter for the rest of the film
for k in range(420):
    at = rng.uniform(2.0, END - 0.1); n = int(0.004 * SR)
    put(bp(rng.normal(0, 1, n), 4000, 10000) * env(n, 0.0005, 900), at, rng.uniform(-0.9, 0.9), 0.035)
# entrance whoosh as the legs come in from the top
n = int(1.2 * SR); w = bp(rng.normal(0, 1, n), 300, 2400) * np.sin(np.pi * np.arange(n) / n) ** 2
put(w, 1.7, 0.0, 0.18)
# footsteps: each group of four feet lands every half cycle -> sharp dry ticks + a little glyph crackle
k = 0
while True:
    for g in (0, 1):
        land = (k + 0.5 * g + 0.5) * TS
        if 2.15 < land < 10.7:
            n = int(0.03 * SR); tick = bp(rng.normal(0, 1, n), 1800, 6500) * env(n, 0.0004, 220)
            put(tick, land, -0.35 if g else 0.35, 0.32)
            n2 = int(0.09 * SR); cr = bp(rng.normal(0, 1, n2), 5000, 11000) * env(n2, 0.001, 45) * (rng.uniform(0, 1, n2) > 0.85)
            put(cr, land + 0.005, 0.0, 0.16)
    k += 1
    if k * TS > 10: break
# detections: each found secret gets a hard digital hit (times match film.py T_DET)
DET = [4.22, 6.9, 8.56]
for i, td in enumerate(DET):
    n = int(0.6 * SR); tt = np.arange(n) / SR
    tone = sum(np.sin(2 * np.pi * f * tt) for f in (880 * 2 ** (i / 12), 1320 * 2 ** (i / 12))) * np.exp(-tt * 7)
    put(tone * 0.12, td, -0.3 + 0.2 * i)
    put(lp(np.tanh(3 * np.sin(2 * np.pi * 55 * tt)) * np.exp(-tt * 9), 400) * 0.35, td)
    n2 = int(0.25 * SR); put(bp(rng.normal(0, 1, n2), 3000, 9000) * (rng.uniform(0, 1, n2) > 0.8) * np.exp(-np.arange(n2) / SR * 14) * 0.2, td)
# the secrets move to env (two soft rising chimes), then the commit goes through (a clean major chord)
for i, tf in enumerate((10.0, 10.45)):
    n = int(0.8 * SR); tt = np.arange(n) / SR
    put(sum(np.sin(2 * np.pi * f * tt) for f in (659.3 * 2 ** (i * 5 / 12), 987.8 * 2 ** (i * 5 / 12))) * np.exp(-tt * 5) * ss(0, 0.02, tt) * 0.08, tf, 0.25 - 0.5 * i)
n = int(1.8 * SR); tt = np.arange(n) / SR
put(sum(np.sin(2 * np.pi * f * tt) for f in (523.3, 659.3, 784.0, 1046.5)) * np.exp(-tt * 1.6) * ss(0, 0.03, tt) * 0.06, 11.0)
# low drone under the wide shot of everything it found
n = int(3.0 * SR); tt = np.arange(n) / SR
put(lp(np.tanh(2 * np.sin(2 * np.pi * 41 * tt)), 600) * ss(0, 1.0, tt) * (1 - ss(2.4, 3.0, tt)) * 0.22, 9.4)
# eyes light: a thin rising tone
n = int(0.9 * SR); tt = np.arange(n) / SR
put(np.sin(2 * np.pi * (880 + 300 * tt) * tt) * ss(0, 0.6, tt) * 0.06, 12.4)
# jump: fast whoosh toward the lens, then a hit and dead silence
n = int(0.5 * SR); tt = np.arange(n) / SR
put(bp(rng.normal(0, 1, n), 500, 6000) * (tt / tt[-1]) ** 2, JUMP0, 0.0, 0.5)
n = int(0.5 * SR); tt = np.arange(n) / SR
hit = np.sin(2 * np.pi * np.cumsum(45 + 120 * np.exp(-tt * 25)) / SR) * env(n, 0.001, 9) + bp(rng.normal(0, 1, n), 800, 5000) * env(n, 0.0005, 40) * 0.6
put(hit, END - 0.03, 0.0, 0.9)

L = int(0.7 * SR); ir = rng.normal(0, 1, (L, 2)) * np.exp(-np.arange(L) / SR * 7)[:, None]; ir /= np.abs(ir).sum(0) / 4
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix * 0.85 + wet * 0.15
f0_ = int((END + 0.12) * SR); out[f0_:] *= np.linspace(1, 0, N - f0_)[:, None]
out /= np.abs(out).max() * 1.12
sf.write('film.wav', out.astype(np.float32), SR); print('ok')
