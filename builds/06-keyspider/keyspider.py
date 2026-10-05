#!/usr/bin/env python3
"""keyspider: finds API keys, tokens and passwords in a git repo, including ones you already deleted.

Scans every file in the working tree and every line ever added in the git history.
Prints findings masked (never the full secret) and can write a JSON report.

usage:
  python3 keyspider.py <path-or-git-url> [--json report.json] [--no-history]

Scan only repositories you own or are allowed to audit.
"""
import argparse, json, math, os, re, subprocess, sys, tempfile

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
    print(f'{B}keyspider{Z}  {a.target}')
    for f in hi_f:
        print(f'{R}LIVE{Z}     {f["file"]}:{f["line"]}  {f["kind"]}  {mask(f["secret"])}')
    for g in hi_g:
        print(f'{Y}DELETED{Z}  {g["file"]}  commit {g["commit"]} ({g["date"]})  {g["kind"]}  {mask(g["secret"])}  {D}still in git history{Z}')
    for f in lows:
        where = f'{f["file"]}:{f["line"]}' if f['where'] == 'file' else f'{f["file"]}  commit {f["commit"]}'
        print(f'{D}low      {where}  {f["kind"]}  {mask(f["secret"])}  (tests/docs/template){Z}')
    total = len(hi_f) + len(hi_g)
    print(f'\n{B}{len(hi_f)} live, {len(hi_g)} deleted but still in history{Z}  {D}+{len(lows)} low{Z}' if total or lows else f'\n{B}clean: nothing found{Z}')
    if hi_g:
        print(f'{D}deleting a key from a file does not remove it from git. rotate it.{Z}')
    if a.json:
        rep = [dict(f, secret=mask(f['secret']), text=f['text'].replace(f['secret'], mask(f['secret']))) for f in files + ghosts]
        with open(a.json, 'w') as fh: json.dump(rep, fh, indent=1)
    sys.exit(1 if total else 0)

if __name__ == '__main__':
    main()
