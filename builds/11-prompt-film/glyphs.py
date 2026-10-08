# Generates glyphs.png: rows of code characters (katakana, kanji, digits; some mirrored) for the code wall.
# Uses Noto Sans CJK (SIL Open Font License). Red channel = glyph mask * brightness. Run once: python3 glyphs.py
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
rng = np.random.RandomState(3)
ROWS, COLS, CELL = 64, 96, 56
W, H = COLS * CELL, ROWS * CELL
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
font = ImageFont.truetype(FONT, 44, index=0)
chars = [chr(c) for c in range(0x30A2, 0x30F6)] + list('日月火水木金土二三四五六七八九十口目田由甲申電雨') + list('0123456789') + list('ZΞ:=*+<>|')
def glyph_img(ch, mirror):
    g = Image.new('L', (CELL, CELL), 0); d = ImageDraw.Draw(g)
    bb = d.textbbox((0, 0), ch, font=font); w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((CELL - w) / 2 - bb[0], (CELL - h) / 2 - bb[1]), ch, font=font, fill=255)
    return ImageOps.mirror(g) if mirror else g
cache = {}
im = Image.new('L', (W, H), 0)
for r in range(ROWS):
    c = 0
    while c < COLS:
        run = rng.randint(3, 28); gap = rng.randint(1, 8); base = rng.uniform(0.3, 0.8)
        for k in range(run):
            if c >= COLS: break
            if rng.uniform() < 0.06: c += 1; continue
            ch = chars[rng.randint(len(chars))]; mir = rng.uniform() < 0.4
            key = (ch, mir)
            if key not in cache: cache[key] = glyph_img(ch, mir)
            b = min(1.0, base * rng.uniform(0.7, 1.2) + (0.3 if rng.uniform() < 0.05 else 0))
            g = cache[key].point(lambda v, b=b: int(v * b))
            im.paste(g, (c * CELL, r * CELL), g)
            c += 1
        c += gap
im.save('glyphs.png', optimize=True); print('ok', im.size)
