# Score for the agent film: warm pad, muted plucks for the steps, bells instead of digital hits.
# Same timing as film.py. Writes film_soft.wav (16.5 s, covers the end card too).
import numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve
SR = 48000; DUR = 16.5; N = int(SR * DUR); rng = np.random.RandomState(8)
t = np.arange(N) / SR; mix = np.zeros((N, 2))
TS = 0.40; DET = [4.72, 5.85, 7.05, 8.71]; FIXES = []; CLEAN = 10.4; JUMP0 = 13.15; END = 13.62
def ss(a, b, x): u = np.clip((x - a) / (b - a), 0, 1); return u * u * (3 - 2 * u)
def lp(x, f, o=2): return sosfilt(butter(o, f, 'low', fs=SR, output='sos'), x)
def put(sig, at, pan=0.0, g=1.0):
    i = int(at * SR); j = min(N, i + len(sig))
    if j <= i: return
    s = sig[:j - i] * g; mix[i:j, 0] += s * (1 - pan) * .7; mix[i:j, 1] += s * (1 + pan) * .7
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def pad(notes, a, b, fade=1.2, g=0.05):
    """detuned soft saw-ish pad, low-passed, between a and b seconds"""
    tt = t; out = np.zeros(N)
    for m in notes:
        for det in (-0.07, 0.0, 0.06):
            f = hz(m + det)
            out += sum(np.sin(2 * np.pi * f * k * tt + rng.uniform(0, 6)) / k ** 1.6 for k in (1, 2, 3))
    out = lp(out, 1400) * g / len(notes)
    return out * ss(a, a + fade, tt) * (1 - ss(b - fade, b, tt))
def bell(m, dur=2.2, g=0.1, bright=1.0):
    n = int(dur * SR); tt = np.arange(n) / SR; f = hz(m)
    s = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 2.2) + 0.35 * bright * np.sin(2 * np.pi * f * 2.76 * tt) * np.exp(-tt * 5) \
        + 0.15 * bright * np.sin(2 * np.pi * f * 5.4 * tt) * np.exp(-tt * 9)
    return s * ss(0, 0.004, tt) * g
def pluck(m, g=0.05):
    n = int(0.35 * SR); tt = np.arange(n) / SR; f = hz(m)
    s = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt)) * np.exp(-tt * 14)
    return lp(s * ss(0, 0.003, tt), 2500) * g

# pad: calm minor while it scans, opens to major once the commit is clean, holds under the end card
mix += pad([45, 52, 55, 59, 60], 0.0, CLEAN + 0.6, 2.0, 0.07)[:, None]          # A minor add9
mix += pad([48, 55, 59, 62, 64], CLEAN - 0.4, DUR, 1.0, 0.075)[:, None]       # C maj9
mix *= (1 - 0.65 * ss(END - 0.05, END + 0.25, t) * (1 - ss(END + 0.3, END + 1.2, t)))[:, None]   # dip at the cut to the card
# steps: muted plucks on a slow pentatonic walk instead of ticks
scale = [57, 60, 62, 64, 67, 69]
k = 0
while k * TS < 11:
    for g in (0, 1):
        land = (k + 0.5 * g + 0.5) * TS
        if 2.15 < land < 10.7:
            put(pluck(scale[(k * 2 + g) % len(scale)], 0.045), land, -0.3 if g else 0.3)
    k += 1
# found secrets: a soft low thump and a warm muted two-note swell (no bell partials)
def mellow(m, dur=1.6, g=0.08):
    n = int(dur * SR); tt = np.arange(n) / SR; f = hz(m)
    s = np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * 2 * f * tt)
    return lp(s * ss(0, 0.06, tt) * np.exp(-tt * 2.6), 900) * g
for i, td in enumerate(DET):
    n = int(0.5 * SR); tt = np.arange(n) / SR
    put(np.sin(2 * np.pi * 70 * tt * (1 - 0.3 * tt)) * np.exp(-tt * 9) * 0.2, td)
    put(mellow(57 - i, 1.6, 0.09) + mellow(60 - i, 1.6, 0.06), td, -0.15 + 0.15 * i)
# secrets move to env: two rising bells, then the clean chord blooms
for i, tf in enumerate(FIXES):
    put(bell(72 + 4 * i, 2.0, 0.07, 0.6), tf, 0.25 - 0.5 * i); put(bell(79 + 4 * i, 2.0, 0.045, 0.4), tf + 0.09, 0.25 - 0.5 * i)
for j, m in enumerate((60, 64, 67, 72, 76)):
    put(bell(m, 3.5, 0.05, 0.5), CLEAN + 0.05 * j, -0.4 + 0.2 * j)
# eyes light: a thin soft shimmer; jump: an airy swell, no hit
n = int(1.0 * SR); tt = np.arange(n) / SR
put(sum(np.sin(2 * np.pi * hz(m) * tt) for m in (84, 88, 91)) * ss(0, 0.7, tt) * np.exp(-np.maximum(tt - 0.7, 0) * 6) * 0.02, 12.4)
n = int(0.6 * SR); tt = np.arange(n) / SR
put(lp(rng.normal(0, 1, n), 1800) * ss(0, 0.45, tt) * (1 - ss(0.45, 0.6, tt)) * 0.12, JUMP0 - 0.1)
# end card: one last low bell under the text
put(bell(48, 3.0, 0.08, 0.3), END + 0.15)

# small room: soft reverb
ir_n = int(1.8 * SR); irt = np.arange(ir_n) / SR
ir = rng.normal(0, 1, (ir_n, 2)) * np.exp(-irt * 3.2)[:, None]; ir[:, 0] = lp(ir[:, 0], 5000); ir[:, 1] = lp(ir[:, 1], 5000)
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix + wet * (np.abs(mix).max() / (np.abs(wet).max() + 1e-9)) * 0.35
out *= (1 - ss(DUR - 1.2, DUR, t))[:, None]
out = out / np.abs(out).max() * 0.6
sf.write('film.wav', out.astype(np.float32), SR); print('ok', out.shape)
