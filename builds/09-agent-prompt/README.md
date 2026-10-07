# 09 · Find leaked keys with your own agent

A prompt you paste into Claude Code (or any coding agent) to audit a repo for leaked secrets, including keys you already deleted.

```
Scan this repo for leaked secrets, including the git history.
1. Check every file and every commit on every branch (git log -p --all) for API keys, tokens and passwords.
2. Never print a full secret. Show only the first 6 characters.
3. For each one tell me: the file, the commit, what kind of key it is, and whether it's still in the code or only in history.
4. Don't change anything. Give me the list and what to rotate first.
```

Want the same without an agent, in one command? [keyspider](../06-keyspider).

`card.py` draws the prompt card (1080×1350).
