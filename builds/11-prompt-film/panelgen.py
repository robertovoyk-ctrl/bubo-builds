# Renders the panel the spider walks down: the leaked-keys prompt from 09, one sentence per group.
#   panel.png        R = text, G = group id k/8 on the rows of each sentence, B = unused
#   panel_fixed.png  same image (the film crossfades to it after a sentence is read)
#   panel.json       rows and sentence groups
# Run: python3 panelgen.py
import json, os, shutil
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
GROUPS = [
    ['Scan this repo for', 'leaked secrets,', 'including the git', 'history.'],
    ['1. Check every file and', '   every commit on every', '   branch (git log -p', '   --all) for API keys,', '   tokens and passwords.'],
    ['2. Never print a full', '   secret. Show only the', '   first 6 characters.'],
    ['3. For each one tell me', '   the file, the commit,', '   what kind of key it', "   is, and whether it's", '   still in the code or', '   only in history.'],
    ["4. Don't change anything.", '   Give me the list and', '   what to rotate first.'],
]
lines, groups = [], []
for k, g in enumerate(GROUPS, 1):
    if lines: lines.append('')
    groups.append(dict(k=k, first=len(lines), last=len(lines) + len(g) - 1))
    lines += g
COLS, CW, RH = 26, 22, 40
W, H = COLS * CW, len(lines) * RH
bold = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 32)
R = Image.new('L', (W, H), 0); G = Image.new('L', (W, H), 0); B = Image.new('L', (W, H), 0)
dr, dg = ImageDraw.Draw(R), ImageDraw.Draw(G)
for row, txt in enumerate(lines):
    dr.text((6, row * RH + 2), txt, font=bold, fill=255)
for g in groups:
    dg.rectangle([0, g['first'] * RH, W, (g['last'] + 1) * RH - 1], fill=int(g['k'] * 255 / 8))
Image.merge('RGB', (R, G, B)).save(os.path.join(HERE, 'panel.png'))
shutil.copy(os.path.join(HERE, 'panel.png'), os.path.join(HERE, 'panel_fixed.png'))
json.dump(dict(rows=len(lines), cols=COLS, groups=groups), open(os.path.join(HERE, 'panel.json'), 'w'), indent=1)
print('rows', len(lines), 'widest', max(len(l) for l in lines), groups)
