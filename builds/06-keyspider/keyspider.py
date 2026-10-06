#!/usr/bin/env python3
"""keyspider: finds API keys, tokens and passwords in a git repo, including ones you already deleted.

Scans every file in the working tree and every line ever added in the git history.
Prints findings masked (never the full secret) and can write a JSON report.

usage:
  python3 keyspider.py <path-or-git-url> [--json report.json] [--no-history] [--verify]

--verify asks each provider, with one read-only request, whether the key still works.
That sends the key to its own provider, nowhere else. Scan only repositories you own
or are allowed to audit, and use --verify only on keys that are yours.
"""
import argparse, base64, json, math, os, re, subprocess, sys, tempfile, urllib.error, urllib.request

PATTERNS = [  # (kind, regex). Specific providers first, generic last.
    ('Anthropic API key', r'sk-ant-[A-Za-z0-9_\-]{20,}'),
    ('OpenAI API key', r'sk-(?:proj-|svcacct-)?[A-Za-z0-9_\-]{32,}'),
    ('Perplexity API key', r'pplx-[A-Za-z0-9]{32,}'),
    ('AWS access key', r'(?:AKIA|ASIA|A3T[A-Z0-9])[A-Z0-9]{16}'),
    ('GitHub token', r'gh[pousr]_[A-Za-z0-9]{36,}'),
    ('GitHub fine-grained token', r'github_pat_[A-Za-z0-9_]{60,}'),
    ('Stripe live key', r'(?:sk|rk)_live_[A-Za-z0-9]{20,}'),
    ('Slack token', r'xox[baprs]-[A-Za-z0-9\-]{10,}'),
    ('Google API key', r'AIza[0-9A-Za-z_\-]{35}'),
    ('Telegram bot token', r'\b\d{8,10}:[A-Za-z0-9_\-]{35}\b'),
    ('Private key', r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY(?: BLOCK)?-----'),
    ('JSON Web Token', r'eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}'),
]
GENERIC = re.compile(r'''(?i)\b([A-Za-z0-9_\-]*?(?:password|passwd|pwd|secret|token|api[_\-]?key|access[_\-]?key|auth))["']?\s*[:=]\s*["']([^"'\s]{8,})["']''')
PLACEHOLDER = re.compile(r'(?i)(x{4,}|\*{3,}|your[_\-]|example|changeme|placeholder|dummy|<[^>]+>|\$\{|\{\{|process\.env|os\.environ|getenv|test|sample|redacted)')
SKIP_DIRS = {'.git', 'node_modules', '.venv', 'venv', '__pycache__', 'dist', 'build', '.next'}
SKIP_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.mov', '.wav', '.mp3', '.zip', '.gz', '.pdf', '.ttf', '.otf', '.woff', '.woff2', '.ico', '.blend'}
COMPILED = [(k, re.compile(p)) for k, p in PATTERNS]

def entropy(s):
    if not s: return 0.0
    n = len(s); counts = {c: s.count(c) for c in set(s)}
    return -sum(v / n * math.log2(v / n) for v in counts.values())

LOW_PATH = re.compile(r'(?i)(^|/)(tests?|spec|fixtures?|examples?|samples?|docs?|testdata|mocks?)(/|$)|\.(md|rst|txt)$')
def low(f):
    """tests, fixtures and docs usually hold fake keys on purpose; ALL_CAPS values are templates"""
    return bool(LOW_PATH.search(f['file'] or '')) or bool(re.fullmatch(r'[A-Z0-9_]+', f['secret']))

def mask(s):
    s = s.strip()
    return s[:6] + '…' + f'[{len(s)} chars]' if len(s) > 10 else s[:2] + '…'

# --verify: one read-only request per key to the provider that issued it.
# 2xx means the key works, 401/403 means it is dead, anything else is unknown.
def _req(url, headers=None, data=None):
    r = urllib.request.Request(url, headers={'User-Agent': 'keyspider', **(headers or {})}, data=data)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, resp.read(4096)
    except urllib.error.HTTPError as e:
        return e.code, b''
    except Exception:
        return None, b''

def _bearer(url):
    return lambda k: _req(url, {'Authorization': f'Bearer {k}'})

CHECKS = {
    'OpenAI API key': _bearer('https://api.openai.com/v1/models'),
    'Anthropic API key': lambda k: _req('https://api.anthropic.com/v1/models', {'x-api-key': k, 'anthropic-version': '2023-06-01'}),
    'GitHub token': lambda k: _req('https://api.github.com/user', {'Authorization': f'token {k}'}),
    'GitHub fine-grained token': lambda k: _req('https://api.github.com/user', {'Authorization': f'token {k}'}),
    'Stripe live key': lambda k: _req('https://api.stripe.com/v1/balance', {'Authorization': 'Basic ' + base64.b64encode(f'{k}:'.encode()).decode()}),
    'Google API key': lambda k: _req(f'https://generativelanguage.googleapis.com/v1beta/models?key={k}'),
    'Telegram bot token': lambda k: _req(f'https://api.telegram.org/bot{k}/getMe'),
    'Slack token': lambda k: _req('https://slack.com/api/auth.test', {'Authorization': f'Bearer {k}'}, data=b''),
}

def verify(kind, secret):
    """'works', 'dead', 'unknown' or 'not checked' (no safe check for this kind)"""
    check = CHECKS.get(kind)
    if not check: return 'not checked'
    status, body = check(secret.strip())
    if status is None: return 'unknown'
    if kind == 'Slack token':          # Slack answers 200 with ok:false for bad tokens
        return 'works' if b'"ok":true' in body else 'dead'
    if 200 <= status < 300: return 'works'
    if status in (401, 403): return 'dead'
    if status in (400, 404) and kind in ('Google API key', 'Telegram bot token'): return 'dead'
    return 'unknown'

def scan_line(line):
    hits, spans = [], []
    for kind, rx in COMPILED:
        for m in rx.finditer(line):
            if any(a <= m.start() < b for a, b in spans): continue
            spans.append((m.start(), m.end())); hits.append((kind, m.group(0)))
    for m in GENERIC.finditer(line):
        val = m.group(2)
        if any(a <= m.start(2) < b for a, b in spans): continue
        if PLACEHOLDER.search(val) or entropy(val) < 3.0: continue
        hits.append((f'Hardcoded {m.group(1).lower()}', val))
    return hits

def scan_tree(root):
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        for f in files:
            p = os.path.join(d, f)
            if os.path.splitext(f)[1].lower() in SKIP_EXT or os.path.getsize(p) > 2_000_000: continue
            try:
                with open(p, encoding='utf-8', errors='strict') as fh:
                    for i, line in enumerate(fh, 1):
                        for kind, val in scan_line(line):
                            out.append(dict(where='file', file=os.path.relpath(p, root), line=i, kind=kind, secret=val, text=line.rstrip('\n')))
            except (UnicodeDecodeError, OSError):
                continue
    return out

def scan_history(root):
    try:
        log = subprocess.run(['git', '-C', root, 'log', '-p', '--all', '--no-color', '--format=@@commit %H %as'],
                             capture_output=True, text=True, errors='replace', check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    out, commit, date, file = [], None, None, None
    for line in log.splitlines():
        if line.startswith('@@commit '): _, commit, date = line.split(' ', 2); continue
        if line.startswith('+++ b/'): file = line[6:]; continue
        if line.startswith('+') and not line.startswith('+++'):
            if file and os.path.splitext(file)[1].lower() in SKIP_EXT: continue
            for kind, val in scan_line(line[1:]):
                out.append(dict(where='history', file=file, commit=commit[:10], date=date, kind=kind, secret=val, text=line[1:]))
    return out

def main():
    ap = argparse.ArgumentParser(description='find keys, tokens and passwords in a git repo, including deleted ones')
    ap.add_argument('target', help='local path or git URL')
    ap.add_argument('--json', help='write a JSON report (secrets masked)')
    ap.add_argument('--no-history', action='store_true', help='skip the git history')
    ap.add_argument('--verify', action='store_true', help='ask each provider (one read-only request) whether the key still works')
    a = ap.parse_args()
    root, tmp = a.target, None
    if re.match(r'^(https?://|git@)', a.target):
        tmp = tempfile.mkdtemp(prefix='keyspider_'); root = os.path.join(tmp, 'repo')
        subprocess.run(['git', 'clone', '--quiet', '--no-single-branch', a.target, root], check=True)
    files = scan_tree(root)
    hist = [] if a.no_history else scan_history(root)
    live = {(f['kind'], f['secret']) for f in files}
    ghosts, seen = [], set()
    for h in hist:                      # secrets that are gone from the files but still sit in history
        k = (h['kind'], h['secret'])
        if k in live or k in seen: continue
        seen.add(k); ghosts.append(h)
    R, Y, D, B, Z = '\033[91m', '\033[93m', '\033[2m', '\033[1m', '\033[0m'
    if not sys.stdout.isatty(): R = Y = D = B = Z = ''
    for f in files + ghosts: f['level'] = 'low' if low(f) else 'high'
    hi_f = [f for f in files if f['level'] == 'high']; hi_g = [g for g in ghosts if g['level'] == 'high']
    lows = [f for f in files + ghosts if f['level'] == 'low']
    if a.verify:                        # one request per distinct key, never for low findings
        cache = {}
        for f in hi_f + hi_g:
            k = (f['kind'], f['secret'])
            if k not in cache: cache[k] = verify(*k)
            f['works'] = cache[k]
    tag = {'works': f'  {R}{B}KEY WORKS{Z}', 'dead': f'  {D}key is dead{Z}', 'unknown': f'  {D}could not check{Z}', 'not checked': f'  {D}no safe check for this kind{Z}'}
    print(f'{B}keyspider{Z}  {a.target}')
    for f in hi_f:
        print(f'{R}LIVE{Z}     {f["file"]}:{f["line"]}  {f["kind"]}  {mask(f["secret"])}' + tag.get(f.get('works'), ''))
    for g in hi_g:
        print(f'{Y}DELETED{Z}  {g["file"]}  commit {g["commit"]} ({g["date"]})  {g["kind"]}  {mask(g["secret"])}  {D}still in git history{Z}' + tag.get(g.get('works'), ''))
    for f in lows:
        where = f'{f["file"]}:{f["line"]}' if f['where'] == 'file' else f'{f["file"]}  commit {f["commit"]}'
        print(f'{D}low      {where}  {f["kind"]}  {mask(f["secret"])}  (tests/docs/template){Z}')
    total = len(hi_f) + len(hi_g)
    print(f'\n{B}{len(hi_f)} live, {len(hi_g)} deleted but still in history{Z}  {D}+{len(lows)} low{Z}' if total or lows else f'\n{B}clean: nothing found{Z}')
    if a.verify and total:
        c = lambda s: sum(1 for f in hi_f + hi_g if f.get('works') == s)
        n, d, u = c('works'), c('dead'), c('unknown') + c('not checked')
        print((f'{R}{B}{n} still {"works" if n == 1 else "work"} right now.{Z} ' if n else '') + f'{D}{d} dead, {u} not confirmed either way.{Z}')
    if hi_g:
        print(f'{D}deleting a key from a file does not remove it from git. rotate it.{Z}')
    if a.json:
        rep = [dict(f, secret=mask(f['secret']), text=f['text'].replace(f['secret'], mask(f['secret']))) for f in files + ghosts]
        with open(a.json, 'w') as fh: json.dump(rep, fh, indent=1)
    sys.exit(1 if total else 0)

if __name__ == '__main__':
    main()
