# Score for the UFO + fly film, synthesised with numpy (no samples).
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve
SR = 48000; DUR = 28.0; N = int(SR * DUR); rng = np.random.RandomState(5)
t = np.arange(N) / SR; mix = np.zeros((N, 2))
def ss(a, b, x): u = np.clip((x - a) / (b - a), 0, 1); return u * u * (3 - 2 * u)
def put(sig, at, pan=0.0, g=1.0):
    i = int(at * SR); j = min(N, i + len(sig))
    if j <= i: return
    s = sig[:j - i] * g; mix[i:j, 0] += s * (1 - pan) * .7; mix[i:j, 1] += s * (1 + pan) * .7
def bp(x, lo, hi, o=2): return sosfilt(butter(o, [lo, hi], 'band', fs=SR, output='sos'), x)
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
OPEN0, OPEN1, CLOSE0, CLOSE1 = 15.0, 17.6, 22.6, 25.0
# night wind
w = bp(rng.normal(0, 1, N), 120, 900) * (0.05 + 0.03 * np.sin(t * 0.37)) * (1 - 0.7 * ss(10, 14, t))
mix[:, 0] += w; mix[:, 1] += np.roll(w, 4000)
# saucer hum: low detuned tones + slow beating, louder as we get under it
hum = sum(np.sin(2 * np.pi * f * t + p) for f, p in ((41.2, 0), (41.9, 1), (82.4, 2), (123.5, .5))) / 4
hum *= (0.12 + 0.28 * ss(1, 10, t)) * (1 - 0.6 * ss(12, 15, t)) * (1 + 0.25 * np.sin(2 * np.pi * 0.7 * t))
mix += hum[:, None] * 0.8
# shimmer pad (the beam)
pad = sum(np.sin(2 * np.pi * f * t) * (0.6 + 0.4 * np.sin(t * (0.3 + k * 0.11)))
          for k, f in enumerate((329.6, 392.0, 493.9, 587.3))) / 4
pad *= 0.05 * ss(2.5, 7, t) * (1 - ss(13, 15, t))
mix[:, 0] += pad; mix[:, 1] += np.roll(pad, 1200)
# camera push whoosh 9-14 s
n = int(5 * SR); wh = bp(rng.normal(0, 1, n), 200, 3000) * np.sin(np.linspace(0, np.pi, n)) ** 2
put(wh, 9.0, 0, 0.18)
# tension riser before opening
n = int(3 * SR); tt = np.arange(n) / SR
riser = np.sin(2 * np.pi * np.cumsum(80 + 160 * (tt / tt[-1]) ** 2) / SR) * (tt / tt[-1]) ** 2
put(riser, 12.2, 0, 0.12)
# panels: mechanical clicks + servo whine, staggered
for k in range(12):
    at = OPEN0 + 0.08 + k * 0.17 + rng.uniform(0, .05)
    n = int(.06 * SR); c = bp(rng.normal(0, 1, n), 1800, 7000) * np.exp(-np.arange(n) / SR * 90)
    put(c, at, rng.uniform(-.6, .6), 0.35)
n = int(2.6 * SR); tt = np.arange(n) / SR
servo = np.sin(2 * np.pi * np.cumsum(420 + 260 * np.sin(tt * 2.4)) / SR) * np.sin(np.pi * tt / tt[-1]) * 0.08
put(servo, OPEN0, 0, 1)
# brain: crackle + soft pulses
seg = (t > OPEN0 + .4) & (t < CLOSE0 + .8)
cr = (rng.uniform(size=N) > 0.9993).astype(float) * rng.uniform(.3, 1, N)
cr = bp(np.convolve(cr, np.exp(-np.arange(300) / 40), 'same'), 2000, 9000) * seg * 0.5
mix[:, 0] += cr; mix[:, 1] += np.roll(cr, 300)
for k in range(9):
    at = OPEN0 + 1.0 + k * 0.72
    n = int(1.4 * SR); tt = np.arange(n) / SR
    tone = sum(np.sin(2 * np.pi * f * tt) for f in (523.3 * 2 ** ([0, 3, 7, 10, 12][k % 5] / 12),)) * np.exp(-tt * 3)
    put(tone, at, (-.4, .4)[k % 2], 0.07)
drone = sum(np.sin(2 * np.pi * f * t) for f in (55, 82.4, 110.2)) / 3 * 0.18 * ss(OPEN0, OPEN1, t) * (1 - ss(CLOSE0, CLOSE1, t))
mix += drone[:, None]
# closing: reverse servo + thud
put(servo[::-1], CLOSE0, 0, 1)
n = int(.6 * SR); tt = np.arange(n) / SR; thud = np.sin(2 * np.pi * np.cumsum(90 * np.exp(-tt * 6) + 38) / SR) * np.exp(-tt * 7)
put(thud, CLOSE1 - 0.15, 0, 0.6)
# eye flare sting
n = int(3 * SR); tt = np.arange(n) / SR
sting = sum(np.sin(2 * np.pi * f * tt) * np.exp(-tt * 1.2) for f in (220, 277.2, 329.6, 440)) / 4
put(sting, 24.6, 0, 0.22); put(lp(rng.normal(0, 1, n), 400) * np.exp(-tt * 2) * 0.3, 24.6, 0, 1)
# room
L = int(1.4 * SR); ir = rng.normal(0, 1, (L, 2)) * np.exp(-np.arange(L) / SR * 3.5)[:, None]; ir /= np.abs(ir).sum(0) / 3
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix * 0.8 + wet * 0.25
out[:int(.3 * SR)] *= np.linspace(0, 1, int(.3 * SR))[:, None]; f = int(1.2 * SR); out[-f:] *= np.linspace(1, 0, f)[:, None]
out /= np.abs(out).max() * 1.12
sf.write('ufo.wav', out.astype(np.float32), SR); print('ok')
