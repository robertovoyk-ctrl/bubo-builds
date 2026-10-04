import numpy as np
from PIL import Image, ImageDraw, ImageFilter
rng = np.random.RandomState(3)
def grad(h, w, stops):
    ys = np.linspace(0, 1, h)
    cols = np.zeros((h, 3))
    for c in range(3):
        cols[:, c] = np.interp(ys, [s[0] for s in stops], [s[1][c] for s in stops])
    return np.repeat(cols[:, None, :], w, 1)
def hills(img, layers):
    d = ImageDraw.Draw(img); w, h = img.size
    for yy, col, amp, fr, ph in layers:
        pts = [(0, h)] + [(x, h * yy + amp * np.sin(x * fr + ph) + amp * 0.4 * np.sin(x * fr * 2.7 + ph * 2)) for x in range(0, w + 8, 8)] + [(w, h)]
        d.polygon(pts, fill=col)
def painting(name, dusk):
    w, h = 768, 600
    a = grad(h, w, [(0, (45, 63, 102) if dusk else (22, 36, 61)), (0.62, (200, 140, 106) if dusk else (60, 90, 110)), (1, (44, 63, 48))])
    img = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(img)
    for i in range(50):
        x, y = rng.rand() * w, rng.rand() * h * 0.5; d.rectangle([x, y, x + 2, y + 2], fill=(255, 250, 230))
    mx, my = int(w * 0.68), int(h * 0.27)
    glow = Image.new('RGB', (w, h)); gd = ImageDraw.Draw(glow); gd.ellipse([mx - 90, my - 90, mx + 90, my + 90], fill=(120, 110, 80)); glow = glow.filter(ImageFilter.GaussianBlur(40))
    img = Image.fromarray(np.clip(np.asarray(img, float) + np.asarray(glow, float), 0, 255).astype(np.uint8)); d = ImageDraw.Draw(img)
    d.ellipse([mx - 30, my - 30, mx + 30, my + 30], fill=(255, 246, 208))
    hills(img, [(0.66, (59, 86, 64), 26, 0.012, 1), (0.75, (46, 71, 51), 22, 0.017, 3), (0.85, (34, 54, 42), 18, 0.02, 5)])
    img.filter(ImageFilter.GaussianBlur(0.8)).save(f'tex/{name}.png')
painting('paint_a', False); painting('paint_b', True)
# dusk sky for the window: deep blue top -> violet -> warm pink/orange at the horizon
w, h = 2048, 1024
sky = grad(h, w, [(0, (18, 26, 62)), (0.45, (60, 58, 120)), (0.7, (170, 100, 130)), (0.85, (240, 150, 110)), (1, (250, 190, 130))])
img = Image.fromarray(sky.astype(np.uint8)); d = ImageDraw.Draw(img)
for i in range(120):
    x, y = rng.rand() * w, rng.rand() * h * 0.45; s = rng.rand() * 1.6; d.ellipse([x, y, x + s, y + s], fill=(230, 230, 255))
img.save('tex/sky.png')
# silhouettes (alpha): far hills, then rooftops + trees
def sil(name, draw):
    im = Image.new('RGBA', (2048, 512), (0, 0, 0, 0)); draw(ImageDraw.Draw(im), im); im.save(f'tex/{name}.png')
def far(d, im):
    w, h = im.size; pts = [(0, h)] + [(x, h * 0.55 + 40 * np.sin(x * 0.004 + 1) + 18 * np.sin(x * 0.013)) for x in range(0, w + 8, 8)] + [(w, h)]
    d.polygon(pts, fill=(52, 40, 70, 255))
def near(d, im):
    w, h = im.size; x = 0
    while x < w:
        bw = 90 + rng.rand() * 160; bh = 120 + rng.rand() * 170; top = h - bh
        if rng.rand() < 0.45:   # tree
            for k in range(6):
                cx, cy, r = x + bw / 2 + (rng.rand() - 0.5) * bw * 0.6, top + rng.rand() * bh * 0.5, 40 + rng.rand() * 50
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(14, 10, 20, 255))
            d.rectangle([x + bw / 2 - 8, top + bh * 0.4, x + bw / 2 + 8, h], fill=(14, 10, 20, 255))
        else:                   # house with a pitched roof and maybe a lit window
            d.rectangle([x, top + 40, x + bw, h], fill=(14, 10, 20, 255)); d.polygon([(x - 10, top + 42), (x + bw / 2, top - 20), (x + bw + 10, top + 42)], fill=(14, 10, 20, 255))
            if rng.rand() < 0.6:
                wx = x + bw * (0.25 + rng.rand() * 0.4); wy = top + 70 + rng.rand() * 40; d.rectangle([wx, wy, wx + 16, wy + 20], fill=(255, 190, 110, 255))
        x += bw + rng.rand() * 30
sil('far', far); sil('near', near)
print('ok')
