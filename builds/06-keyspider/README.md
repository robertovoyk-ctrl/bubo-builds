# 06 · keyspider

Finds API keys, tokens and passwords in a git repo, including the ones you already deleted.

Deleting a key from a file does not remove it from git. Every old commit still has it, and anyone who clones the repo can read it. keyspider reads every file and every line ever added in the history, and tells you which secrets are live and which are "deleted" but still there.

```
$ python3 keyspider.py https://github.com/you/your-repo
keyspider  https://github.com/you/your-repo
LIVE     bot.py:3  Hardcoded db_password  Tr0ub4…[13 chars]
DELETED  config.py  commit c0d6f8c2f7 (2026-10-05)  OpenAI API key  sk-pro…[56 chars]  still in git history

1 live, 1 deleted but still in history  +0 low
deleting a key from a file does not remove it from git. rotate it.
```

Secrets are always printed masked, so the report itself is safe to share.

## What it looks for

Anthropic, OpenAI, Perplexity, AWS, GitHub, Stripe, Slack, Google and Telegram keys, private key files, JSON Web Tokens, and hardcoded `password` / `secret` / `token` / `api_key` values that look random enough to be real. Findings in tests, fixtures and docs, and ALL_CAPS template values, are listed as `low`.

## Use

```bash
python3 keyspider.py <path-or-git-url>            # files + full git history
python3 keyspider.py . --json report.json         # also write a masked JSON report
python3 keyspider.py . --no-history               # working tree only
python3 keyspider.py . --verify                   # also check which keys still work
./demo.sh                                         # throwaway repo with fake keys
```

Exit code is 1 when something real is found, so it can run in CI.

## Stop it before the commit

Finding a leaked key means it is already in git. The guard stops it one step earlier:

```bash
python3 keyspider.py /path/to/your/repo --install-hook
```

From then on every `git commit` in that repo is checked first, by you or by your coding agent. Only the lines the commit adds are scanned, so it takes a fraction of a second.

```
BLOCKED  app.py:4       Hardcoded db_password  8ik30q…[18 chars]
BLOCKED  payments.py:3  Stripe live key        sk_liv…[40 chars]
warning  tests/t.py:1   Hardcoded token        BJGXKd…[30 chars]

keyspider stopped this commit: 2 secrets would have gone into git.
move them to a .env file (listed in .gitignore) or an environment variable, then commit again.
```

Move the value out of the code (`stripe.api_key = os.environ["STRIPE_KEY"]`, the key itself in `.env`), commit again, and it passes. Tests, fixtures and docs only get a warning. It works in private repos and catches plain passwords too, which GitHub's push protection does not.

## Does the key still work?

With `--verify`, keyspider sends each key it found to the provider that issued it, with one read-only request (list models, read the account, `getMe`), and tags the line:

```
DELETED  config.py  commit c0d6f8c2f7  OpenAI API key  sk-pro…[56 chars]  still in git history  KEY WORKS
LIVE     bot.py:3   Telegram bot token  712345…[46 chars]  key is dead
```

Checked: OpenAI, Anthropic, GitHub, Stripe, Google, Telegram, Slack. Other kinds (AWS needs a second secret, passwords have no provider) are marked as not checked. A network error or rate limit is "could not check", never "dead". The key goes only to its own provider, and the request never changes anything there. Use `--verify` only on keys that are yours. A dead key in history is still worth cleaning up; a working one means rotate now.

Python 3 and git, nothing else. Scan only repositories you own or are allowed to audit.

## If it finds something

1. Revoke the key at the provider and make a new one. This is the only real fix.
2. Move secrets to environment variables or a secrets manager.
3. Rewriting history (`git filter-repo`) hides the key from new clones, but anyone who already pulled still has it. Rotate first.
