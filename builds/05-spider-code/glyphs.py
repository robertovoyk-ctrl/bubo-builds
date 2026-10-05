# Generates glyphs.png: rows of angular code glyphs (procedural, no font) for the code wall.
# Red channel = glyph mask * brightness. Run once: python3 glyphs.py
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
rng = np.random.RandomState(3)
ROWS, COLS, CW, CH = 64, 112, 34, 56
W, H = COLS * CW, ROWS * CH
im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
GX, GY = 4, 6                       # stroke grid inside a glyph
def make_glyph():
    segs = []
    for _ in range(rng.randint(2, 4)):          # 2-3 connected strokes
        x, y = rng.randint(0, GX + 1), rng.randint(0, GY + 1)
        for _ in range(rng.randint(3, 7)):
            dx, dy = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (2, 0), (0, 2)][rng.randint(8)]
            nx, ny = min(GX, max(0, x + dx)), min(GY, max(0, y + dy))
            segs.append((x, y, nx, ny)); x, y = nx, ny
    if rng.uniform() < 0.45:                    # horizontal bar, common in the reference glyphs
        yb = rng.randint(0, GY + 1); segs.append((0, yb, GX, yb))
    return segs
lib = [make_glyph() for _ in range(90)]
for r in range(ROWS):
    c = 0
    while c < COLS:
        run = rng.randint(3, 26); gap = rng.randint(1, 9)
        base = rng.uniform(0.25, 0.75)
        for k in range(run):
            if c >= COLS: break
            if rng.uniform() < 0.08: c += 1; continue
            b = min(1.0, base * rng.uniform(0.6, 1.25) + (0.35 if rng.uniform() < 0.05 else 0))
            col = int(255 * b); ox, oy = c * CW + 5, r * CH + 8
            sx, sy = (CW - 10) / GX, (CH - 16) / GY
            for (x0, y0, x1, y1) in lib[rng.randint(len(lib))]:
                d.line([(ox + x0 * sx, oy + y0 * sy), (ox + x1 * sx, oy + y1 * sy)], fill=col, width=5)
            c += 1
        c += gap
im = im.filter(ImageFilter.GaussianBlur(0.6))
im.save('glyphs.png', optimize=True); print('ok', im.size)
