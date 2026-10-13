# Sound for the pavilion flythrough: mountain wind against glass, a warm low pad, a few soft chimes.
import numpy as np, soundfile as sf, os
from scipy.signal import butter, sosfilt, fftconvolve
SR = 48000; DUR = 20.0; N = int(SR * DUR)
t = np.arange(N) / SR; rng = np.random.RandomState(5); mix = np.zeros((N, 2))
def ss(a, b, x): u = np.clip((x - a) / (b - a), 0, 1); return u * u * (3 - 2 * u)
def bp(x, a, b): return sosfilt(butter(2, [a, b], 'band', fs=SR, output='sos'), x)
def lp(x, f): return sosfilt(butter(2, f, 'low', fs=SR, output='sos'), x)
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
# wind: two slow gusting layers, slightly different per ear
for ch in (0, 1):
    w = bp(rng.normal(0, 1, N), 120, 900) * (0.55 + 0.45 * np.sin(2 * np.pi * (0.06 + 0.01 * ch) * t + ch))
    w += bp(rng.normal(0, 1, N), 900, 3500) * 0.25 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t + 2 + ch)) ** 2
    mix[:, ch] += w * 0.05
# glass hum: very quiet resonance of the panes
mix += (np.sin(2 * np.pi * 62 * t) * 0.004 * (0.6 + 0.4 * np.sin(2 * np.pi * 0.2 * t)))[:, None]
# warm pad, fades in and grows toward the end
pad = sum(np.sin(2 * np.pi * hz(m + d) * t + rng.uniform(0, 6)) for m in (45, 52, 57, 61, 64) for d in (-0.04, 0.04)) / 10
mix += (lp(pad, 1200) * 0.07 * ss(0.5, 6, t) * (0.7 + 0.3 * ss(10, 18, t)))[:, None]
# soft chimes
for at, m in ((3.2, 76), (7.9, 81), (12.4, 79), (16.0, 84)):
    n = int(3.0 * SR); tt = np.arange(n) / SR; i = int(at * SR); j = min(N, i + n)
    s = (np.sin(2 * np.pi * hz(m) * tt) + 0.3 * np.sin(2 * np.pi * hz(m) * 2.76 * tt)) * np.exp(-tt * 1.6) * 0.035
    pan = rng.uniform(-0.6, 0.6)
    mix[i:j, 0] += s[:j - i] * (1 - pan) * 0.7; mix[i:j, 1] += s[:j - i] * (1 + pan) * 0.7
# room reverb
ir_n = int(2.5 * SR); irt = np.arange(ir_n) / SR
ir = rng.normal(0, 1, (ir_n, 2)) * np.exp(-irt * 2.2)[:, None]
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix + wet * (np.abs(mix).max() / (np.abs(wet).max() + 1e-9)) * 0.3
out *= (ss(0, 0.8, t) * (1 - ss(DUR - 1.5, DUR, t)))[:, None]
out = np.tanh(out / np.abs(out).max() * 1.2) * 0.7
sf.write(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'film.wav'), out.astype(np.float32), SR); print('ok')
