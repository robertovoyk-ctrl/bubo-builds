# Builds a demo repo with FAKE random keys, stages a commit that hardcodes two of them, and runs the
# real keyspider guard (--staged) on it. Then renders the commit the spider walks down, twice:
#   panel.png        what the commit adds; finding rows carry their id, B = "BLOCKED" tags
#   panel_fixed.png  the same commit after the secrets were moved to environment variables, B = "moved" tags
#   G channel (both) = id k/8 on the rows that change: 1, 2 = the secrets, 3 = the commit result line
# Every key here is random and fake. Run: python3 guardatlas.py
import json, os, random, string, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
KEYSPIDER = os.path.join(HERE, '..', '06-keyspider', 'keyspider.py')
r = random.Random(808)
A = string.ascii_letters + string.digits
def rnd(n): return ''.join(r.choice(A) for _ in range(n))

STRIPE = f'sk_live_{rnd(32)}'
DBPASS = rnd(18)
PAY = f'''import stripe
from .models import Order

stripe.api_key = "{STRIPE}"

def charge(order: Order):
    intent = stripe.PaymentIntent.create(
        amount=order.total_cents,
        currency="usd",
        metadata={{"order": order.id}},
    )
    return intent.client_secret
'''
DB = f'''import psycopg

DB_HOST = "db.internal"
DB_USER = "app"
DB_PASSWORD = "{DBPASS}"

def connect():
    return psycopg.connect(host=DB_HOST, user=DB_USER,
                           password=DB_PASSWORD, dbname="prod")
'''
FIXED = {f'stripe.api_key = "{STRIPE}"': 'stripe.api_key = os.environ["STRIPE_KEY"]',
         f'DB_PASSWORD = "{DBPASS}"': 'DB_PASSWORD = os.environ["DB_PASSWORD"]'}

def main():
    root = os.path.join(tempfile.mkdtemp(prefix='guard_'), 'shop-api')
    os.makedirs(os.path.join(root, 'app')); os.makedirs(os.path.join(root, 'db'))
    g = lambda *a: subprocess.run(['git', '-C', root, *a], check=True, capture_output=True)
    g('init', '-q'); g('config', 'user.email', 'agent@shop'); g('config', 'user.name', 'agent')
    open(os.path.join(root, 'README.md'), 'w').write('shop api\n'); g('add', '-A'); g('commit', '-qm', 'init')
    open(os.path.join(root, 'app', 'payments.py'), 'w').write(PAY)
    open(os.path.join(root, 'db', 'connect.py'), 'w').write(DB)
    g('add', '-A')
    run = subprocess.run([sys.executable, KEYSPIDER, root, '--staged'], capture_output=True, text=True)
    print(run.stderr.strip()); assert run.returncode == 1, 'guard did not block'
    blocked = [l.split()[1] for l in run.stderr.splitlines() if l.startswith('BLOCKED')]   # file:line, in keyspider's order
    labels = {'Stripe live key': 'Stripe live key', 'Hardcoded db_password': 'database password'}
    kinds = {l.split()[1]: ' '.join(l.split()[2:-2]) for l in run.stderr.splitlines() if l.startswith('BLOCKED')}

    lines, fixed, marks = [], [], []          # marks: (row, k, blocked label, fixed label)
    def add(a, b=None): lines.append(a); fixed.append(a if b is None else b)
    add('$ git commit -m "add payments and db"')
    add('keyspider guard · checking what this commit adds')
    add('')
    k = 0
    for f, txt in (('app/payments.py', PAY), ('db/connect.py', DB)):
        add(f'── {f}  (new) ' + '─' * max(4, 40 - len(f)))
        for i, ln in enumerate(txt.splitlines(), 1):
            if f'{f}:{i}' in blocked:
                k += 1
                marks.append((len(lines), k, f'BLOCKED · {labels.get(kinds[f"{f}:{i}"], kinds[f"{f}:{i}"])}', 'moved to .env'))
                add(f'{i:>3} +{ln}', f'{i:>3} +{FIXED[ln]}'); add('')
            else:
                add(f'{i:>3} +{ln}')
        add('')
    add('')
    marks.append((len(lines), 3, '', ''))
    add(f'✗ commit blocked: {len(blocked)} secrets would have gone into git', '✓ commit clean · keys stay on your machine')
    add('')

    COLS, CW, RH = 92, 22, 40
    W, H = COLS * CW, len(lines) * RH
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 30)
    bold = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 26)
    bold30 = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf', 30)
    for name, src, tagi in (('panel.png', lines, 2), ('panel_fixed.png', fixed, 3)):
        R = Image.new('L', (W, H), 0); G = Image.new('L', (W, H), 0); B = Image.new('L', (W, H), 0)
        dr, dg, db = ImageDraw.Draw(R), ImageDraw.Draw(G), ImageDraw.Draw(B)
        for row, txt in enumerate(src):
            y = row * RH + 4
            hdr = txt.startswith('──') or txt.startswith('keyspider guard')
            dr.text((10, y), txt, font=bold30 if txt[:1] in '$✗✓' else font, fill=170 if hdr else 255)
        for row, kk, lb, lf in marks:
            span = 2 if kk < 3 else 1
            dg.rectangle([0, row * RH, W, (row + span) * RH - 1], fill=int(kk * 255 / 8))
            lab = lb if tagi == 2 else lf
            if lab: db.text((10 + 5 * CW, (row + 1) * RH + 6), ('▲ ' if tagi == 2 else '✓ ') + lab, font=bold, fill=255)
        Image.merge('RGB', (R, G, B)).save(os.path.join(HERE, name))
    meta = dict(rows=len(lines), cols=COLS, findings=[dict(row=row, k=kk, label=lb) for row, kk, lb, _ in marks])
    json.dump(meta, open(os.path.join(HERE, 'panel.json'), 'w'), indent=1)
    print('rows', len(lines), [(m[0], m[1], m[2]) for m in marks])

if __name__ == '__main__':
    main()
