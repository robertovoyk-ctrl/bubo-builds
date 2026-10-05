#!/bin/bash
# Builds a throwaway repo with random fake keys (one committed then "deleted"), then scans it.
set -e
D=$(mktemp -d)/demo && mkdir -p "$D" && cd "$D" && git init -q && git config user.email demo@demo && git config user.name demo
r(){ python3 -c "import secrets,string;print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range($1)))"; }
echo "OPENAI_KEY = \"sk-proj-$(r 48)\"" > config.py && git add -A && git commit -qm "first version"
echo 'import os; OPENAI_KEY = os.environ["OPENAI_KEY"]' > config.py && git commit -qam "move key to env"
echo "DB_PASSWORD = \"$(r 14)\"" > bot.py && git add -A && git commit -qm "bot"
cd - >/dev/null && python3 "$(dirname "$0")/keyspider.py" "$D" || true
