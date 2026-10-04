"""Render the score with Salamander Grand Piano samples (CC BY 3.0, Alexander Holm)."""
import json, numpy as np, soundfile as sf
from scipy.signal import fftconvolve

SR = 48000
score = json.load(open('score.json'))
SAMPLES = {39: 'Ds2', 45: 'A2', 51: 'Ds3', 57: 'A3', 60: 'C4', 63: 'Ds4', 69: 'A4', 72: 'C5', 75: 'Ds5'}
cache = {}
def sample(base, layer):
    k = (base, layer)
    if k not in cache:
        x, sr = sf.read(f'samples/{SAMPLES[base]}v{layer}.flac', dtype='float32')
        if x.ndim == 1: x = np.stack([x, x], 1)
        if sr != SR:
            idx = np.arange(0, len(x) - 1, sr / SR); x = np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
        cache[k] = x
    return cache[k]

def note_audio(midi, vel, ring):
    base = min(SAMPLES, key=lambda b: abs(b - midi))
    x = sample(base, 12 if vel > 0.8 else 10)
    semis = midi - base
    n = int((ring + 0.6) * SR)
    if semis:
        ratio = 2 ** (semis / 12)
        idx = np.arange(n) * ratio; idx = idx[idx < len(x) - 1]
        y = np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
    else:
        y = x[:n].copy()
    # damper: after `ring` seconds the note is released with a short fade
    rel = int(ring * SR); fade = int(0.16 * SR)
    if rel < len(y):
        env = np.ones(len(y), np.float32)
        e = min(len(y), rel + fade)
        env[rel:e] = np.linspace(1, 0, e - rel) ** 2; env[e:] = 0
        y = y * env[:, None]
    return y * vel

end = score['end']
mix = np.zeros((int((end + 0.5) * SR), 2), np.float32)
for e in score['events']:
    y = note_audio(e['midi'], e['vel'], e['ring'])
    i = int(e['t'] * SR); j = min(len(mix), i + len(y))
    mix[i:j] += y[:j - i]
# small warm room
rng = np.random.RandomState(4)
ir_len = int(1.1 * SR); tt = np.arange(ir_len) / SR
ir = rng.normal(0, 1, (ir_len, 2)) * np.exp(-tt * 5.5)[:, None]
ir[:, 0] = np.convolve(ir[:, 0], np.ones(24) / 24, 'same'); ir[:, 1] = np.convolve(ir[:, 1], np.ones(24) / 24, 'same')
ir /= np.abs(ir).sum(0) / 6
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:len(mix)] for c in range(2)], 1)
out = mix * 0.82 + wet * 0.18
fade = int(0.8 * SR); out[-fade:] *= np.linspace(1, 0, fade)[:, None]
out /= np.abs(out).max() * 1.12
sf.write('fur_elise.wav', out, SR)
print('ok', round(len(out) / SR, 2), 's')
