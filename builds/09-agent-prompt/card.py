# Prompt card for the "paste this into your agent" post: a terminal window with the exact prompt. 1080x1350.
from PIL import Image, ImageDraw, ImageFont
import textwrap
W, H = 1080, 1350
BG = (4, 7, 6); WIN = (9, 15, 12); BAR = (16, 26, 21); GREEN = (60, 255, 140); MINT = (220, 245, 230); RASP = (255, 40, 120); DIM = (95, 120, 108)
MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'; MONOB = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'
PROMPT = [
    ('h', 'Scan this repo for leaked secrets, including the git history.'),
    ('n', '1. Check every file and every commit on every branch (git log -p --all) for API keys, tokens and passwords.'),
    ('n', '2. Never print a full secret. Show only the first 6 characters.'),
    ('n', '3. For each one tell me: the file, the commit, what kind of key it is, and whether it\'s still in the code or only in history.'),
    ('n', '4. Don\'t change anything. Give me the list and what to rotate first.'),
]
im = Image.new('RGB', (W, H), BG)
wall = Image.open('/home/claude/bubo-builds/builds/05-spider-code/glyphs.png').crop((0, 0, 2160, 2700)).resize((W, H))
im.paste(Image.merge('RGB', [wall.point(lambda v: v * 0.03), wall.point(lambda v: v * 0.12), wall.point(lambda v: v * 0.07)]))
d = ImageDraw.Draw(im)
fh = ImageFont.truetype(MONOB, 50); fb = ImageFont.truetype(MONO, 33); fbb = ImageFont.truetype(MONOB, 33); fs = ImageFont.truetype(MONO, 26)
d.text((64, 70), 'Paste this into', font=fh, fill=MINT)
d.text((64, 130), 'your agent.', font=fh, fill=GREEN)
x0, y0, x1 = 50, 260, W - 50
lines = []
for kind, txt in PROMPT:
    for i, part in enumerate(textwrap.wrap(txt, 43, subsequent_indent='   ' if kind == 'n' else '')):
        lines.append((kind, part))
    lines.append(('gap', ''))
y1 = y0 + 80 + sum(14 if k == "gap" else 46 for k, _ in lines) + 6
d.rounded_rectangle([x0, y0, x1, y1], 22, fill=WIN, outline=(40, 90, 62), width=2)
d.rounded_rectangle([x0, y0, x1, y0 + 56], 22, fill=BAR); d.rectangle([x0, y0 + 30, x1, y0 + 56], fill=BAR)
for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
    d.ellipse([x0 + 24 + i * 34, y0 + 18, x0 + 44 + i * 34, y0 + 38], fill=c)
d.text((x0 + 140, y0 + 13), 'claude  ~/your-repo', font=fs, fill=DIM)
y = y0 + 80
d.text((x0 + 34, y), '>', font=fbb, fill=GREEN)
for kind, part in lines:
    if kind == 'gap': y += 14; continue
    d.text((x0 + 70, y), part, font=fbb if kind == 'h' else fb, fill=MINT if kind == 'h' else (190, 225, 205))
    y += 46
d.text((64, y1 + 50), 'finds keys you deleted, too.', font=fs, fill=DIM)
d.text((64, y1 + 92), '@bubosees', font=ImageFont.truetype(MONOB, 28), fill=RASP)
im.save('card.png'); print('ok', y1)
