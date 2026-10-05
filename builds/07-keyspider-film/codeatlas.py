# Builds a small demo project with FAKE random keys (one of them committed and then "deleted"),
# scans it with keyspider, and renders the code the spider walks on:
#   panel.png  R = code text, G = finding id (k/8) on finding rows, B = finding tag text
#   panel.json rows, finding rows and labels
# Every key here is random and fake. Run: python3 codeatlas.py
import json, os, random, string, subprocess, tempfile, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
KEYSPIDER = os.path.join(HERE, '..', '06-keyspider', 'keyspider.py')
r = random.Random(1907)
A = string.ascii_letters + string.digits
def rnd(n, alpha=A): return ''.join(r.choice(alpha) for _ in range(n))

FILES_V1 = {
 'app/settings.py': f'''import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = ["api.example.app", "localhost"]

DATABASE_URL = os.getenv("DATABASE_URL")
CACHE_TTL = 300
OPENAI_KEY = "sk-proj-{rnd(48)}"
MODEL = "gpt-6.1"
MAX_TOKENS = 2048
''',
}
FILES_V2 = {
 'app/settings.py': '''import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.getenv("DEBUG", "0") == "1"
ALLOWED_HOSTS = ["api.example.app", "localhost"]

DATABASE_URL = os.getenv("DATABASE_URL")
CACHE_TTL = 300
OPENAI_KEY = os.environ["OPENAI_KEY"]
MODEL = "gpt-6.1"
MAX_TOKENS = 2048
''',
 'app/payments.py': f'''import stripe
from .models import Order

stripe.api_key = "sk_live_{rnd(32)}"

def charge(order: Order):
    intent = stripe.PaymentIntent.create(
        amount=order.total_cents,
        currency="usd",
        metadata={{"order": order.id}},
    )
    return intent.client_secret
''',
 'bot/notify.py': f'''import requests

TELEGRAM_TOKEN = "{r.randint(6000000000, 8999999999)}:{rnd(35, A + '_-')}"
CHAT_ID = -1002231

def send(text):
    url = f"https://api.telegram.org/bot{{TELEGRAM_TOKEN}}/sendMessage"
    requests.post(url, json={{"chat_id": CHAT_ID, "text": text}}, timeout=10)
''',
 'db/connect.py': f'''import psycopg

DB_HOST = "db.internal"
DB_USER = "app"
DB_PASSWORD = "{rnd(18)}"

def connect():
    return psycopg.connect(host=DB_HOST, user=DB_USER,
                           password=DB_PASSWORD, dbname="prod")
''',
}

def write(root, files):
    for p, txt in files.items():
        os.makedirs(os.path.dirname(os.path.join(root, p)), exist_ok=True)
        open(os.path.join(root, p), 'w').write(txt)

def main():
    root = os.path.join(tempfile.mkdtemp(prefix='demo_'), 'shop-api')
    os.makedirs(root)
    g = lambda *a: subprocess.run(['git', '-C', root, *a], check=True, capture_output=True)
    g('init', '-q'); g('config', 'user.email', 'dev@shop'); g('config', 'user.name', 'dev')
    write(root, FILES_V1); g('add', '-A'); g('commit', '-qm', 'settings')
    write(root, FILES_V2); g('add', '-A'); g('commit', '-qm', 'move key to env, payments, bot, db')
    rep = os.path.join(root, '..', 'report.json')
    subprocess.run([sys.executable, KEYSPIDER, root, '--json', rep])
    found = json.load(open(rep))
    old_commit = subprocess.run(['git', '-C', root, 'log', '--format=%h', '-n', '1', 'HEAD~1'], capture_output=True, text=True).stdout.strip()

    # the listing the spider walks down: files in this order, then the old commit
    order = ['app/settings.py', 'app/payments.py', 'bot/notify.py', 'db/connect.py']
    lines, marks = [], []          # marks: (row, k, label)
    labels = {'Stripe live key': 'Stripe live key', 'Telegram bot token': 'Telegram bot token',
              'OpenAI API key': 'OpenAI key', 'Hardcoded db_password': 'database password'}
    k = 0
    for f in order:
        lines.append(f'── {f} ' + '─' * max(4, 44 - len(f)))
        for i, ln in enumerate(open(os.path.join(root, f)).read().splitlines(), 1):
            hit = [x for x in found if x['where'] == 'file' and x['file'] == f and x['line'] == i]
            lines.append(f'{i:>3}  {ln}')
            if hit:
                k += 1; marks.append((len(lines) - 1, k, f'{labels.get(hit[0]["kind"], hit[0]["kind"])} · LIVE')); lines.append('')
        lines.append('')
    hist = [x for x in found if x['where'] == 'history']
    if hist:
        lines.append(f'── git log -p · commit {old_commit} ' + '─' * 18)
        lines.append('     app/settings.py')
        lines.append('     -CACHE_TTL = 300')
        for h in hist:
            k += 1
            txt = [l for l in FILES_V1['app/settings.py'].splitlines() if l.startswith('OPENAI_KEY')][0]
            marks.append((len(lines), k, f'{labels.get(h["kind"], h["kind"])} · deleted, still in git history'))
            lines.append(f'     -{txt}'); lines.append('')
        lines.append('     +OPENAI_KEY = os.environ["OPENAI_KEY"]')
    # render: one text row per line
    COLS, CW, RH = 92, 22, 40
    W, H = COLS * CW, len(lines) * RH
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 30)
    bold = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 26)
    R = Image.new('L', (W, H), 0); G = Image.new('L', (W, H), 0); B = Image.new('L', (W, H), 0)
    dr, dg, db = ImageDraw.Draw(R), ImageDraw.Draw(G), ImageDraw.Draw(B)
    for row, txt in enumerate(lines):
        y = row * RH + 4
        dr.text((10, y), txt, font=font, fill=255 if not txt.startswith('──') else 170)
    for row, kk, label in marks:            # finding row + the tag row under it light up together
        dg.rectangle([0, row * RH, W, (row + 2) * RH - 1], fill=int(kk * 255 / 8))
        db.text((10 + 5 * CW, (row + 1) * RH + 6), '▲ ' + label, font=bold, fill=255)
    Image.merge('RGB', (R, G, B)).save(os.path.join(HERE, 'panel.png'))
    meta = dict(rows=len(lines), cols=COLS, findings=[dict(row=row, k=kk, label=label) for row, kk, label in marks])
    json.dump(meta, open(os.path.join(HERE, 'panel.json'), 'w'), indent=1)
    print('rows', len(lines), 'findings', [(m[0], m[2]) for m in marks])

if __name__ == '__main__':
    main()
