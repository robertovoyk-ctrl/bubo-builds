# Text overlay for every frame (1080x1920 RGBA): labels, live telemetry from the sim, Grok's own words, stamps, cards.
#   python3 hud.py [outdir] [a:b:step]
import os, sys, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import shots
W, H = 1080, 1920
FD = os.path.join(HERE, 'fonts')                     # put DejaVu here (Colab has none); falls back to the system copy
if not os.path.isdir(FD): FD = '/usr/share/fonts/truetype/dejavu'
SANS_B, SANS = os.path.join(FD, 'DejaVuSans-Bold.ttf'), os.path.join(FD, 'DejaVuSans.ttf')
MONO, MONO_B = os.path.join(FD, 'DejaVuSansMono.ttf'), os.path.join(FD, 'DejaVuSansMono-Bold.ttf')
_f = {}
def font(p, s):
    if (p, s) not in _f: _f[(p, s)] = ImageFont.truetype(p, s)
    return _f[(p, s)]
WHITE, DIM, RED, GREEN, AMBER, BLUE = (245, 245, 240), (175, 178, 180), (255, 60, 60), (60, 235, 120), (255, 176, 40), (120, 190, 255)

def smooth(x): x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)

def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ''
    for w_ in words:
        t = (cur + ' ' + w_).strip()
        if d.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w_
    if cur: lines.append(cur)
    return lines

def shade(im, box, alpha=150, r=22):
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); ImageDraw.Draw(ov).rounded_rectangle(box, r, fill=(0, 0, 0, alpha))
    im.alpha_composite(ov)

def band(im, y0, y1, alpha=190, top=True):
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    for y in range(y0, y1):
        u = (y - y0) / max(1, y1 - y0); a = alpha * ((1 - u) if top else u) ** 1.2
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(a)))
    im.alpha_composite(ov)

def chip(im, d, label, title, x=60, y=120):
    f1, f2 = font(SANS_B, 40), font(SANS_B, 52)
    w1 = d.textlength(label, font=f1)
    d.rounded_rectangle([x, y, x + w1 + 36, y + 62], 12, fill=(255, 255, 255, 235))
    d.text((x + 18, y + 9), label, font=f1, fill=(10, 10, 12))
    if title:
        for i, ln in enumerate(wrap(d, title, f2, 560)):
            d.text((x, y + 86 + i * 64), ln, font=f2, fill=WHITE)

def telemetry(d, st, x=W - 60, y=124, extra=None):
    f, fl = font(MONO_B, 44), font(MONO, 26)
    vz = st['vz']
    rows = [('ALT', f"{max(0, st['z']):,.0f} m"),
            ('SPEED', f"{abs(vz):,.0f} m/s {'up' if vz > 1 else 'down'}"),
            ('TO TOWER', f"{abs(st['x']):,.0f} m"),
            ('ENGINES', f"{int(st['lit'])}")]
    for i, (k, v) in enumerate(rows):
        yy = y + i * 78
        d.text((x, yy), k, font=fl, fill=DIM, anchor='ra')
        col = AMBER if (k == 'ENGINES' and int(st['lit']) > 0) else (RED if (k == 'SPEED' and vz > 1) else WHITE)
        d.text((x, yy + 28), v, font=f, fill=col, anchor='ra')

def say_box(im, d, who, text, y_bottom=1700, accent=BLUE, alpha=1.0, sub=None):
    if alpha <= 0: return
    f1, f2, f3 = font(SANS_B, 30), font(SANS_B, 50), font(MONO, 30)
    lines = wrap(d, text, f2, W - 180)
    h = 70 + len(lines) * 64 + (50 if sub else 0)
    y0 = y_bottom - h
    shade(im, [50, y0, W - 50, y_bottom], int(165 * alpha))
    d.rectangle([50, y0 + 18, 58, y_bottom - 18], fill=(*accent, int(255 * alpha)))
    d.text((90, y0 + 22), who, font=f1, fill=(*accent, int(255 * alpha)))
    for i, ln in enumerate(lines):
        d.text((90, y0 + 62 + i * 64), ln, font=f2, fill=(*WHITE, int(255 * alpha)))
    if sub: d.text((90, y0 + 70 + len(lines) * 64), sub, font=f3, fill=(*AMBER, int(255 * alpha)))

def stamp(im, d, word, sub, color, u, cy=820):
    if u <= 0: return
    s = 1.0 + 0.25 * (1 - smooth(u / 0.25))
    f = font(SANS_B, int(150 * s))
    wdt = d.textlength(word, font=f)
    cx = W // 2
    pad = 34
    a = int(255 * smooth(u / 0.12))
    box = [cx - wdt / 2 - pad, cy - 95 * s, cx + wdt / 2 + pad, cy + 95 * s]
    d.rounded_rectangle(box, 18, fill=(*color, int(a * 0.92)))
    d.text((cx, cy), word, font=f, fill=(255, 255, 255, a), anchor='mm')
    if sub:
        fs = font(SANS_B, 52)
        for i, ln in enumerate(wrap(d, sub, fs, W - 140)):
            tw = d.textlength(ln, font=fs)
            shade(im, [cx - tw / 2 - 22, cy + 120 + i * 72, cx + tw / 2 + 22, cy + 186 + i * 72], int(a * 0.7), 14)
            d.text((cx, cy + 153 + i * 72), ln, font=fs, fill=(255, 255, 255, a), anchor='mm')

def card(im, d, lines, a, big_first=True, y=None):
    ov = Image.new('RGBA', im.size, (0, 0, 0, int(200 * a))); im.alpha_composite(ov)
    y = y or 700
    for i, ln in enumerate(lines):
        f = font(SANS_B, 84 if (i == 0 and big_first) else 70)
        col = WHITE if i < len(lines) - 1 else GREEN
        if big_first and i == 0 and ln.startswith('TRY'): col = AMBER
        for part in wrap(d, ln, f, W - 140):
            d.text((70, y), part, font=f, fill=(*col, int(255 * a)))
            y += 92
        y += 28 if i == 0 else 4

def thoughts(s, ts):
    """Grok's last applied decision line, and whether it is still thinking about the next one (realtime)."""
    dec = shots.flight(s['flight'])['decisions']
    said = [e for e in dec if e['applies_at'] <= ts + 1e-6]
    pending = [e for e in dec if e['t'] <= ts + 1e-6 < e['applies_at']]
    return (said[-1] if said else None), (pending[0] if pending else None)

def metric(d, label, value, col=WHITE, x=W - 60, y=128):
    d.text((x, y), label, font=font(SANS_B, 30), fill=DIM, anchor='ra')
    d.text((x, y + 40), value, font=font(SANS_B, 84), fill=col, anchor='ra')

def inset(im, d, s, ts, x0=716, y0=700, w=320, h=600):
    """Side view of the real path from the sim: tower at 0, booster track, current position."""
    xmin, xmax, zmax = s['inset']
    shade(im, [x0, y0, x0 + w, y0 + h], 150, 18)
    pad = 24; gx0, gx1, gy0, gy1 = x0 + pad, x0 + w - pad, y0 + pad + 30, y0 + h - pad - 34
    X = lambda x: gx0 + (x - xmin) / (xmax - xmin) * (gx1 - gx0)
    Z = lambda z: gy1 - min(max(z + shots.ARM_Z, 0), zmax) / zmax * (gy1 - gy0)
    d.text((x0 + pad, y0 + 16), 'SIDE VIEW', font=font(SANS_B, 24), fill=DIM)
    d.line([(gx0, gy1), (gx1, gy1)], fill=(150, 150, 150, 255), width=3)
    tx = X(0); d.rectangle([tx - 5, Z(146 - shots.ARM_Z), tx + 5, gy1], fill=(200, 200, 200, 255))
    d.text((tx, gy1 + 8), 'TOWER', font=font(SANS_B, 22), fill=DIM, anchor='ma')
    st = shots.flight(s['flight'])['states']
    pts = [(X(r[1]), Z(r[2])) for r in st if r[0] <= ts][::5]
    if len(pts) > 1: d.line(pts, fill=(255, 176, 40, 255), width=5)
    cur = shots.state(s['flight'], ts); cx, cz = X(cur['x']), Z(cur['z'])
    d.ellipse([cx - 11, cz - 11, cx + 11, cz + 11], fill=(255, 255, 255, 255))

def draw(fr):
    info = shots.frame_info(fr); s = info['shot']; tl = info['tl']
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    sid = s['id']
    if sid == 'hook':                                             # frame 0: full strength, no fade
        band(im, 0, 720, 235)
        l1, l2 = shots.HOOKS[shots.HOOK]
        f = font(SANS_B, 112)
        for i, (ln, col) in enumerate(((l1, WHITE), (l2, AMBER))):
            for j, part in enumerate(wrap(d, ln, f, W - 130)):
                d.text((64, 130 + i * 136 + j * 124), part, font=f, fill=col)
        return im
    if s.get('card') and not s.get('flight'):
        card(im, d, s['card'], 1.0); return im
    if sid == 'close':
        return im
    st = dict(info['st']); ts = info['ts']
    if sid == 'end':
        card(im, d, s['card'], smooth(tl / 0.3), big_first=False, y=640); return im
    band(im, 0, 640, 170)
    if sid.startswith('v'):
        chip(im, d, 'TRY 2', None)
        d.text((60, 205), sid, font=font(SANS_B, 150), fill=WHITE)
    else:
        chip(im, d, s['label'], s['title'])
    if s.get('metric') == 'speed' and not (st['end'] and st['result'] == 'CAUGHT' and tl > s['stamp'][0] + 0.4):
        metric(d, 'SPEED', f"{abs(st['vz']):,.0f} m/s", RED if abs(st['vz']) > 3 and st['z'] < 30 else WHITE)
    if s.get('inset'):
        inset(im, d, s, ts)
    if s.get('thoughts'):
        last, pend = thoughts(s, ts)
        if pend is not None and pend['why'] in s.get('lines', []) and tl < s['stamp'][0]:
            metric(d, 'GROK THINKING', f"{ts - pend['t']:.1f} s", AMBER)
        else:
            metric(d, 'ALTITUDE', f"{max(0, st['z']):,.0f} m", RED if st['vz'] > 1 else WHITE)
        keep = [e for e in shots.flight(s['flight'])['decisions'] if e['why'] in s.get('lines', []) and e['applies_at'] <= ts + 1e-6]
        if keep:
            say_box(im, d, 'GROK', keep[-1]['why'])
    if s.get('quote'):
        qa = smooth(tl / 0.2) * (1 - smooth((tl - (s['stamp'][0] - 0.4)) / 0.3))
        say_box(im, d, f'GROK, after v{shots.QUOTE_AFTER[int(sid[1:])]} failed', s['quote'], alpha=qa)
    if s.get('stamp'):
        at, word, sub = s['stamp']
        color = {'ABORT': (230, 140, 20), 'CRASH': (225, 40, 40), 'TOO FAST': (225, 40, 40), 'CAUGHT': (30, 175, 85)}[word]
        stamp(im, d, word, sub, color, tl - at, cy=560)
    return im

if __name__ == '__main__':
    outd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'hud')
    spec = sys.argv[2] if len(sys.argv) > 2 else f'0:{shots.NFRAMES}:1'
    os.makedirs(outd, exist_ok=True)
    if ':' in spec:
        a_, b_, c_ = (int(x) for x in spec.split(':')); frames = range(a_, min(b_, shots.NFRAMES), c_)
    else: frames = [int(x) for x in spec.split(',')]
    for fr in frames:
        draw(fr).save(os.path.join(outd, f'h{fr:04d}.png'), compress_level=1)
    print('hud frames', len(frames))
