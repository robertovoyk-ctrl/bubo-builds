# Original score for "Bug found. 183 years late." — everything synthesised here, no samples.
# Clockwork engine ticks + music-box arpeggio + plucked bass, glitch blips synced to every word the fly breaks,
# a soft "check" on every verified row, a fly buzz during the flight, then silence, an error hit and a closing chord.
import json, numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000; DUR = 15.8
ev = json.load(open('events.json')); TABLE_END, LAND_T = ev['t'][2], ev['t'][3]
SWAP = [e[1] for e in ev['ev'] if e[0] == 'swap'][0]
N = int(DUR * SR); mix = np.zeros((N, 2)); rng = np.random.RandomState(4)
mf = lambda m: 440 * 2 ** ((m - 69) / 12)
def put(sig, t, pan=0.0, gain=1.0):
    i = int(t * SR); j = min(N, i + len(sig))
    if i >= N or j <= i: return
    s = sig[:j - i] * gain; mix[i:j, 0] += s * (1 - pan) * 0.5 * 2 ** 0.5; mix[i:j, 1] += s * (1 + pan) * 0.5 * 2 ** 0.5
def env(n, a, d):  # attack seconds, exponential decay rate
    t = np.arange(n) / SR; return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t * d)

def musicbox(m, dur=1.2, dec=4.5):
    n = int(dur * SR); t = np.arange(n) / SR; f = mf(m)
    s = np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t * 9) + 0.25 * np.sin(2 * np.pi * f * 5.43 * t) * np.exp(-t * 20)
    return s * env(n, 0.002, dec)
def pluck(m, dur=0.45):
    n = int(dur * SR); t = np.arange(n) / SR; f = mf(m)
    s = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.4 * np.exp(-t * (6 + 5 * k)) for k in range(1, 7))
    return s * env(n, 0.003, 5)
def tick(hi=True):
    n = int(0.035 * SR); s = rng.normal(0, 1, n) * np.exp(-np.arange(n) / SR * 260)
    return sosfilt(butter(2, [2500, 7000] if hi else [900, 2600], 'band', fs=SR, output='sos'), s) * (0.9 if hi else 1.2)
def blip(m):
    n = int(0.07 * SR); t = np.arange(n) / SR; f = mf(m) * (1 + 0.6 * np.exp(-t * 60))
    s = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * 0.5 + np.sin(2 * np.pi * np.cumsum(f * 2) / SR) * 0.3
    return sosfilt(butter(2, 6000, 'low', fs=SR, output='sos'), s * env(n, 0.001, 45))
def check():
    n = int(0.25 * SR); t = np.arange(n) / SR
    return (np.sin(2 * np.pi * mf(88) * t) + 0.4 * np.sin(2 * np.pi * mf(95) * t)) * env(n, 0.001, 18)
def kick():
    n = int(0.35 * SR); t = np.arange(n) / SR; f = 50 + 90 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 9)

BPM = 120; B = 60 / BPM; S16 = B / 4
# chords (A minor feel): Am | F | C | G, one bar each, looping
prog = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]
bass = [45, 41, 36, 43]
arp = [0, 1, 2, 1, 2, 0, 2, 1]                          # music-box pattern over chord tones, +12
end_groove = SWAP - 0.05
t = 0.0; step = 0
while t < end_groove:
    bar = int(t / (4 * B)) % 4; ch = prog[bar]
    if step % 2 == 0: put(tick(step % 8 == 0), t, pan=0.35 * ((step // 2) % 2 * 2 - 1), gain=0.10)
    if t > 0.45:
        if step % 2 == 0: put(musicbox(ch[arp[(step // 2) % 8]] + 12 + (12 if (step // 16) % 2 and step % 8 == 6 else 0)), t, pan=0.25, gain=0.20)
        if step % 4 == 0: put(pluck(bass[bar]), t, pan=-0.15, gain=0.42)
        if step % 4 == 0 and t > 2.9: put(kick(), t, gain=0.30)
        if step % 8 == 4 and t > 2.9:
            n = int(0.12 * SR); put(sosfilt(butter(2, 1800, 'high', fs=SR, output='sos'), rng.normal(0, 1, n)) * env(n, 0.001, 30), t, gain=0.10)
    t += S16; step += 1
# a little lift once the fly reaches the table: the music box doubles an octave up
t = ev['t'][1] + 0.6; k = 0
while t < TABLE_END:
    bar = int(t / (4 * B)) % 4; put(musicbox(prog[bar][(k * 2) % 3] + 24, 0.5), t, pan=-0.3, gain=0.07); t += B / 2; k += 1
# glitch blips: one per broken word, pitch from a pentatonic set
pent = [81, 84, 86, 88, 91, 93, 96]
for e in ev['ev']:
    if e[0] == 'i': put(blip(pent[rng.randint(len(pent))]), e[1], pan=rng.uniform(-0.6, 0.6), gain=0.10)
    if e[0] == 'ok': put(check(), e[1], pan=0.2, gain=0.05)
    if e[0] == 'warn':                                   # row 4: a sour two-note question
        for dt, m in ((0, 70), (0.12, 69)): put(blip(m), e[1] + dt, gain=0.22)
# the carried quote: low rising swell while the fly drags it
n = int((ev['t'][1] - ev['t'][0]) * SR); tt = np.arange(n) / SR
put(np.sin(2 * np.pi * np.cumsum(110 + 60 * tt / tt[-1]) / SR) * np.minimum(1, tt / 0.3) * np.minimum(1, (tt[-1] - tt) / 0.3), ev['t'][0], gain=0.10)
# fly buzz during the flight back to operation 4
n = int((LAND_T - TABLE_END + 0.2) * SR); tt = np.arange(n) / SR; f = 210 + 25 * np.sin(2 * np.pi * 7 * tt)
buzz = np.sign(np.sin(2 * np.pi * np.cumsum(f) / SR)) * (1 + 0.5 * np.sin(2 * np.pi * 31 * tt))
buzz = sosfilt(butter(2, [150, 3000], 'band', fs=SR, output='sos'), buzz) * np.minimum(1, tt / 0.1) * np.minimum(1, (tt[-1] - tt) / 0.15)
put(buzz, TABLE_END, pan=0.0, gain=0.10)
# the reveal: error hit (detuned low saw + noise), then a closing chord on the caption
n = int(1.2 * SR); tt = np.arange(n) / SR
err = sum(np.sign(np.sin(2 * np.pi * f * tt)) for f in (55, 58.3, 82.4)) / 3
err = sosfilt(butter(3, 900, 'low', fs=SR, output='sos'), err) * env(n, 0.002, 3.2)
put(err, SWAP, gain=0.45); put(kick(), SWAP, gain=0.6)
for k in range(3): put(blip(96 - k * 5), SWAP + 0.06 * k, gain=0.12)
cap = SWAP + 1.1
for i, m in enumerate([57, 64, 69, 72, 76]): put(musicbox(m + 12, 2.4, 1.3), cap + i * 0.09, pan=-0.3 + 0.15 * i, gain=0.20)
put(pluck(33, 2.3) * np.exp(-np.arange(int(2.3*SR))/SR*0.5)[:int(2.3*SR)], cap, gain=0.5)
# room + master
L = int(1.1 * SR); ir = rng.normal(0, 1, (L, 2)) * np.exp(-np.arange(L) / SR * 5)[:, None]
ir /= np.abs(ir).sum(0) / 4
wet = np.stack([fftconvolve(mix[:, c], ir[:, c])[:N] for c in range(2)], 1)
out = mix * 0.85 + wet * 0.18
f = int(0.6 * SR); out[-f:] *= np.linspace(1, 0, f)[:, None]
out /= np.abs(out).max() * 1.12
sf.write('music.wav', out.astype(np.float32), SR); print('ok', SWAP, cap)
