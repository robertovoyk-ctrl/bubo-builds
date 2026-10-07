# Renders the panel the spider walks on: the prompt and Claude Code's real answer (agent_result.txt, secrets masked).
#   panel.png        R = text, G = row id k/8 on rows that light up, B = tag text under them
#   panel_fixed.png  same image (this film has no "after" state)
#   panel.json       rows and lit rows
# Run: python3 panelgen.py
import json, os, re, shutil
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__))
res = open(os.path.join(HERE, 'agent_result.txt')).read()
rows = re.findall(r'^\| (\d) \| (\S+) \| (\w+) "[^"]*" \| ([^|]+?) \| `([^`]+)` \| \*\*([^*]+)\*\*', res, re.M)
assert len(rows) == 3, rows

lines, marks = [], []                      # marks: (row, k, tag)
def add(t): lines.append(t)
add('$ claude -p "Scan this repo for leaked secrets,')
add('    including the git history. Never print a full')
add('    secret. Tell me what to rotate first."')
add('')
add('... scanning 4 commits on every branch')
add('')
add('Secrets found')
add('')
tags = {'Only in history': 'deleted, but still in git history', 'Still in code': 'still in the code right now'}
for i, (n, f, commit, kind, first6, status) in enumerate(rows, 1):
    add(f'#{n}  {f}   commit {commit}')
    add(f'    {kind}   {first6}…')
    marks.append((len(lines), i, '▲ ' + tags.get(status.strip(), status.strip())))
    add(f'    {status.strip().upper()}')
    add('')
    add('')
add('Rotate first')
add('  1. Stripe key: rotate immediately.')
add('  2. Database password: rotate next.')
add('  3. OpenAI key: still rotate it.')
add('')
marks.append((len(lines), 4, ''))
add('Deleting a file does not erase it from git history.')
add('')

COLS, CW, RH = 92, 22, 40
W, H = COLS * CW, len(lines) * RH
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 30)
bold = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 30)
tagf = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 26)
R = Image.new('L', (W, H), 0); G = Image.new('L', (W, H), 0); B = Image.new('L', (W, H), 0)
dr, dg, db = ImageDraw.Draw(R), ImageDraw.Draw(G), ImageDraw.Draw(B)
for row, txt in enumerate(lines):
    dim = txt.startswith('...') or txt.startswith('    including') or txt.startswith('    secret') or txt.startswith('$')
    head = txt in ('Secrets found', 'Rotate first') or txt.startswith('#') or txt.startswith('Deleting')
    dr.text((10, row * RH + 4), txt, font=bold if head else font, fill=150 if dim else 255)
for row, k, tag in marks:
    span = 2 if tag else 1
    dg.rectangle([0, row * RH, W, (row + span) * RH - 1], fill=int(k * 255 / 8))
    if tag: db.text((10 + 4 * CW, (row + 1) * RH + 6), tag, font=tagf, fill=255)
im = Image.merge('RGB', (R, G, B)); im.save(os.path.join(HERE, 'panel.png'))
shutil.copy(os.path.join(HERE, 'panel.png'), os.path.join(HERE, 'panel_fixed.png'))
json.dump(dict(rows=len(lines), cols=COLS, findings=[dict(row=r, k=k, label=t) for r, k, t in marks]), open(os.path.join(HERE, 'panel.json'), 'w'), indent=1)
print('rows', len(lines), marks)
