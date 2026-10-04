"""
Snake arena: three new decision models on ONE shared board, 3 rounds.

  Amazon Strands Decider 2B   (local server, STRANDS_URL)
  Cloudflare Clef-flash        (Workers AI, CF_ACCOUNT_ID + CF_API_TOKEN)
  Perplexity pplx-decider      (Decisions API, PPLX_KEY + PPLX_URL [+ PPLX_MODEL])

Every tick all three models are asked at the same time (in parallel). Each one sees only its own
situation, described in words: where the nearest apple is, and what is next to its head
(wall / its own body / another snake / free). Then all moves happen together.
A snake dies if it hits a wall, its own body or another snake. Head-on crashes kill both.
A round ends when only one snake is left alive (it wins) or after MAX_TICKS (most apples wins).
Start corners rotate every round, so each model starts from each corner once.
Every call is logged with its full raw answer and latency, so the video is rebuilt from the log.

Run:  python3 snake_arena.py
Writes snake_arena_log.json next to this file.
"""
import json, os, random, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

W = H = 14
ROUNDS = int(os.environ.get("ROUNDS", "3"))
MAX_TICKS = int(os.environ.get("MAX_TICKS", "150"))
N_APPLES = 2
OUT = Path(__file__).resolve().parent
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPP = {"up": "down", "down": "up", "left": "right", "right": "left"}
STARTS = [([(3, 3), (2, 3), (1, 3)], "right"),        # top-left, heading right
          ([(10, 10), (11, 10), (12, 10)], "left"),    # bottom-right, heading left
          ([(10, 3), (10, 2), (10, 1)], "down")]       # top-right, heading down

def models():
    out = []
    surl = os.environ.get("STRANDS_URL", "").strip()
    if surl: out.append(dict(name="Amazon Strands Decider 2B", url=surl, headers={}, model=None))
    acc, tok = os.environ.get("CF_ACCOUNT_ID", "").strip(), os.environ.get("CF_API_TOKEN", "").strip()
    if acc and tok:
        out.append(dict(name="Cloudflare Clef-flash", headers={"Authorization": f"Bearer {tok}"}, model=None,
                        url=f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/@cf/cloudflare/clef-flash"))
    pk, purl = os.environ.get("PPLX_KEY", "").strip(), os.environ.get("PPLX_URL", "").strip()
    if pk and purl:
        out.append(dict(name="Perplexity pplx-decider", url=purl, headers={"Authorization": f"Bearer {pk}"},
                        model=os.environ.get("PPLX_MODEL", "pplx-decider-v1-27b")))
    return out

def find_answer(obj, legal):
    """Returns (choice, probabilities) from any response shape."""
    if isinstance(obj, dict):
        mv = obj.get("move")
        if isinstance(mv, dict) and isinstance(mv.get("choice"), str) and mv["choice"] in legal:
            return mv["choice"], mv.get("probabilities") or {}
        for v in obj.values():
            r = find_answer(v, legal)
            if r: return r
    return None

def describe(me, snakes, apples):
    s = snakes[me]; body = s["body"]; hx, hy = body[0]; direction = s["dir"]
    ax, ay = min(apples, key=lambda a: abs(a[0] - hx) + abs(a[1] - hy))
    own = set(body[:-1])
    others = set()
    for k, o in snakes.items():
        if k != me and o["alive"]: others |= set(o["body"])
    def what(d):
        dx, dy = DIRS[d]; nx, ny = hx + dx, hy + dy
        if not (0 <= nx < W and 0 <= ny < H): return "wall"
        if (nx, ny) in own: return "your own body"
        if (nx, ny) in others: return "another snake"
        return "free"
    horiz = f"{abs(ax - hx)} cells to the {'right' if ax > hx else 'left'}" if ax != hx else "in your column"
    vert = f"{abs(ay - hy)} cells {'down' if ay > hy else 'up'}" if ay != hy else "in your row"
    lines = [f"You are a snake on a {W}x{H} board with two other snakes. Your length is {len(body)}. You are moving {direction}.",
             f"The nearest apple is {horiz} and {vert}.", "What is next to your head:"]
    legal = [d for d in DIRS if d != OPP[direction]]
    for d in legal: lines.append(f"- {d}: {what(d)}")
    lines.append("Eat apples. Never move into a wall, your own body or another snake.")
    return "\n".join(lines), legal

def ask(m, sess, state, legal):
    q = {"move": {"type": "choice", "instructions": "Which way should the snake move now?",
                  "criteria": {d: f"move {d}" for d in legal}}}
    body = {"state": state, "questions": q}
    if m["model"]: body["model"] = m["model"]
    t0 = time.perf_counter(); r = sess.post(m["url"], json=body, timeout=30); ms = (time.perf_counter() - t0) * 1000
    if r.status_code != 200: raise RuntimeError(f"{m['name']} HTTP {r.status_code}: {r.text[:300]}")
    raw = r.json(); ans = find_answer(raw, legal)
    if not ans: raise RuntimeError(f"{m['name']} no legal move in answer: {json.dumps(raw)[:300]}")
    return ans[0], ans[1], round(ms, 2), raw

def play_round(rnd, ms, sessions):
    rng = random.Random(100 + rnd)
    snakes = {}
    for i, m in enumerate(ms):
        body, d = STARTS[(i + rnd) % 3]
        snakes[m["name"]] = {"body": [tuple(p) for p in body], "dir": d, "alive": True, "apples": 0, "death": None, "died_tick": None}
    occupied = lambda: {p for s in snakes.values() if s["alive"] for p in s["body"]}
    def new_apple(apples):
        while True:
            a = (rng.randrange(W), rng.randrange(H))
            if a not in occupied() and a not in apples: return a
    apples = []
    for _ in range(N_APPLES): apples.append(new_apple(apples))
    ticks = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for t in range(MAX_TICKS):
            alive = [m for m in ms if snakes[m["name"]]["alive"]]
            if len(alive) <= 1: break
            before = {n: {"body": list(s["body"]), "dir": s["dir"], "alive": s["alive"]} for n, s in snakes.items()}
            apples_before = [list(a) for a in apples]
            jobs = {}
            for m in alive:
                state, legal = describe(m["name"], snakes, apples)
                jobs[m["name"]] = (state, legal, pool.submit(ask, m, sessions[m["name"]], state, legal))
            moves = {}
            for n, (state, legal, fut) in jobs.items():
                try:
                    ch, probs, msv, raw = fut.result()
                    moves[n] = {"state": state, "legal": legal, "choice": ch, "p": probs, "ms": msv, "raw": raw}
                except Exception as e:   # an API failure counts as a crash for that snake, the round goes on
                    print("   !!", e)
                    moves[n] = {"state": state, "legal": legal, "choice": snakes[n]["dir"], "p": {}, "ms": None, "raw": None, "error": str(e)}
            # move everyone at once
            new = {}
            for n, mv in moves.items():
                s = snakes[n]; dx, dy = DIRS[mv["choice"]]; head = (s["body"][0][0] + dx, s["body"][0][1] + dy)
                ate = head in apples
                new[n] = ([head] + (s["body"] if ate else s["body"][:-1]), ate)
            dead = {n: "API error" for n, mv in moves.items() if mv.get("error")}
            for n, (nb, ate) in new.items():
                if n in dead: continue
                h = nb[0]
                if not (0 <= h[0] < W and 0 <= h[1] < H): dead[n] = "wall"; continue
                if h in nb[1:]: dead[n] = "own body"; continue
                for k, (ob, _) in new.items():
                    if k == n: continue
                    if h == ob[0]: dead[n] = "head-on crash"; break
                    if h in ob[1:]: dead[n] = "another snake"; break
            eaten = []
            for n, (nb, ate) in new.items():
                s = snakes[n]; moves[n]["ate"] = ate and n not in dead; moves[n]["death"] = dead.get(n)
                if n in dead:
                    s["alive"] = False; s["death"] = dead[n]; s["died_tick"] = t
                else:
                    s["body"] = nb; s["dir"] = moves[n]["choice"]
                    if ate: s["apples"] += 1; eaten.append(nb[0])
            for a in eaten:
                if a in apples: apples.remove(a)
            while len(apples) < N_APPLES: apples.append(new_apple(apples))
            ticks.append({"tick": t, "before": before, "apples_before": apples_before, "moves": moves,
                          "apples_after": [list(a) for a in apples]})
            if (t + 1) % 20 == 0: print(f"   tick {t + 1}: " + ", ".join(f"{n.split()[0]} {s['apples']}{'' if s['alive'] else ' X'}" for n, s in snakes.items()))
    alive = [n for n, s in snakes.items() if s["alive"]]
    if len(alive) == 1: winner, how = alive[0], "last snake alive"
    else:
        winner = max(snakes, key=lambda n: (snakes[n]["apples"], snakes[n]["died_tick"] or 10**6)); how = "most apples"
    return {"round": rnd + 1, "winner": winner, "how": how, "ticks": len(ticks),
            "result": {n: {"apples": s["apples"], "death": s["death"], "died_tick": s["died_tick"], "alive": s["alive"]} for n, s in snakes.items()},
            "start_apples": None, "log": ticks}

def main():
    ms = models()
    if len(ms) < 2: sys.exit("need at least 2 models configured")
    sessions = {}
    for m in ms:
        s = requests.Session(); s.headers.update({**m["headers"], "Content-Type": "application/json"}); sessions[m["name"]] = s
    # one warm-up call each so the first move is not a cold start
    for m in ms:
        try: ask(m, sessions[m["name"]], "warm up", ["up", "down"])
        except Exception as e: print("warm-up", m["name"], e)
    log = {"board": [W, H], "models": [m["name"] for m in ms], "when": time.strftime("%Y-%m-%d %H:%M %Z"), "rounds": []}
    for r in range(ROUNDS):
        print(f"\n=== ROUND {r + 1} ===")
        res = play_round(r, ms, sessions)
        # record starting apples for replay
        log["rounds"].append(res)
        print(f"winner: {res['winner']} ({res['how']}) after {res['ticks']} ticks")
        for n, v in res["result"].items(): print(f"   {n:<28} apples {v['apples']:>2}  {'ALIVE' if v['alive'] else 'out: ' + str(v['death']) + ' at tick ' + str(v['died_tick'])}")
    wins = {m["name"]: sum(1 for r in log["rounds"] if r["winner"] == m["name"]) for m in ms}
    log["wins"] = wins
    (OUT / "snake_arena_log.json").write_text(json.dumps(log, indent=1, default=list))
    print("\n=== ARENA RESULT ===")
    for n, w in sorted(wins.items(), key=lambda x: -x[1]): print(f"{n:<28} {w} round wins")
    print("saved: snake_arena_log.json")

if __name__ == "__main__":
    main()
