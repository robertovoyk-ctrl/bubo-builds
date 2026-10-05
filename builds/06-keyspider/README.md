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
./demo.sh                                         # throwaway repo with fake keys
```

Exit code is 1 when something real is found, so it can run in CI.

Python 3 and git, nothing else. Scan only repositories you own or are allowed to audit.

## If it finds something

1. Revoke the key at the provider and make a new one. This is the only real fix.
2. Move secrets to environment variables or a secrets manager.
3. Rewriting history (`git filter-repo`) hides the key from new clones, but anyone who already pulled still has it. Rotate first.
