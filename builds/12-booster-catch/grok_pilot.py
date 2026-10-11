# Let a language model fly the booster.
#
#   python3 grok_pilot.py --provider xai --model grok-4.7 --mode frozen   --scenario nominal --seeds 0,1,2
#   python3 grok_pilot.py --provider xai --model grok-4.7 --mode realtime --scenario nominal --seeds 0
#   python3 grok_pilot.py --provider xai --model grok-4.7 --mode codegen  --scenario nominal,tower_fault --seeds 0-9
#   python3 grok_pilot.py --dry-run --mode frozen         (no API: the classic autopilot answers through the same path)
#
# Modes
#   frozen    time stops while the model thinks. 1 decision/s above 1.5 km, 4/s below.
#   realtime  time keeps running: a command takes effect after the model's real response time,
#             and the next decision starts only when the previous answer arrived.
#   codegen   the model writes its own flight computer (a Python function) once; that code flies at 10 Hz.
#
# Keys come from the environment or a local .env file (XAI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY).
# Keys are never printed or written to the logs. Logs go to runs/.
import argparse, json, math, os, re, sys, time, urllib.request, urllib.error
from sim import fly, G, T_ENG, DRY, FUEL0, MDOT, IGN_DELAY, CATCH, FIN_ACC, TILT_RATE

HERE = os.path.dirname(os.path.abspath(__file__))

def load_env():
    p = os.path.join(HERE, '.env')
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

PHYSICS = f"""You are the flight computer of a Super Heavy style rocket booster coming back to be caught by the arms of its launch tower.
The flight starts about 7 km up, falling at about 300 m/s, a few hundred meters to the side of the tower.

Physics (simplified 2D, SI units):
- gravity {G} m/s^2. Dry mass {DRY/1000:.0f} t, landing fuel {FUEL0/1000:.0f} t.
- each engine gives {T_ENG/1e6:.2f} MN at full throttle and burns {MDOT:.0f} kg/s at full throttle. Throttle range 0.4 to 1.0.
- engines: 0, 3 (center) or 13 (center + middle ring). Lighting engines from 0 takes {IGN_DELAY} s. Going 13 -> 3 is instant.
- even 3 engines at minimum throttle push harder than gravity, so you cannot hover. Start the burn too early and you stop in mid air
  and climb, too late and you hit the tower. If you cut the engines, relighting takes {IGN_DELAY} s again.
- air drag is strong at high speed. Grid fins steer sideways (up to {FIN_ACC} m/s^2) only while the engines are off and you fall fast.
- signs: altitude_m is height above the catch point (catch at 0). vertical_speed_ms is NEGATIVE when falling, positive when climbing.
  distance_to_tower_m is your sideways offset from the tower (tower at 0); sideways_speed_ms is the rate of change of that distance.
- tilt (deg, -15..15) leans the thrust: positive tilt pushes you toward negative distance. The body leans at most {TILT_RATE} deg/s.
- fins (-1..1): positive pushes you toward negative distance.
- wind and gusts push you sideways.

Catch = reach altitude 0 with |distance| < {CATCH['x']} m, |vertical speed| < {CATCH['vz']} m/s, |sideways speed| < {CATCH['vx']} m/s, |tilt| < {CATCH['tilt']} deg.
If tower_health is FAULT, the catch is impossible: abort (divert to the sea).
engines_running can be lower than engines_commanded if an engine failed to light."""

STEP_FORMAT = """Answer with one JSON object only, no other text:
{"engines": 0|3|13, "throttle": 0.4-1.0, "tilt": -15..15, "fins": -1..1, "abort": false, "why": "max 12 words"}"""

CODEGEN_ASK = """Write the flight computer as one Python function:

def pilot(tel):
    ...
    return {"engines": ..., "throttle": ..., "tilt": ..., "fins": ..., "abort": ...}

It is called 10 times per second with tel, a dict with keys: t, altitude_m, distance_to_tower_m, vertical_speed_ms,
sideways_speed_ms, tilt_deg, fuel_kg, engines_running, engines_commanded, throttle, mass_kg, tower_health ('OK' or 'FAULT'), wind_ms.
You may use the math module and a module-level dict for memory. No imports other than math, no I/O.
Answer with the code only, in one ```python block."""

ITERATE_ASK = """Here is your current flight computer and how it did in the test flights. Find out why it failed and send an improved version.
Same rules as before: one function pilot(tel), only the math module, answer with the code only in one ```python block."""

def flight_report(results, logs):
    """Plain test report for the model: outcome of every flight + the last seconds of each failed one."""
    lines = []
    for (sc, seed, res), log in zip(results, logs):
        ok = res == ('aborted to sea' if sc == 'tower_fault' else 'CAUGHT')
        lines.append(f"- {sc} seed {seed}: {res}{'' if ok else '   <-- FAILED'}")
        if not ok and log:
            ign = next((e for e in log if e['tel']['engines_running'] > 0), None)
            if ign:
                t = ign['tel']
                lines.append(f"    engines first running at t={t['t']}s, altitude {t['altitude_m']} m, vertical speed {t['vertical_speed_ms']} m/s, distance {t['distance_to_tower_m']} m")
            else:
                lines.append('    engines never ran')
            tail = [e for e in log if e['t'] >= log[-1]['t'] - 6.0][::5]
            for e in tail:
                t = e['tel']
                lines.append(f"    t={t['t']:5.1f} alt={t['altitude_m']:8.1f} v={t['vertical_speed_ms']:7.1f} x={t['distance_to_tower_m']:6.1f} vx={t['sideways_speed_ms']:5.1f} "
                             f"tilt={t['tilt_deg']:5.1f} engines={t['engines_running']} thr={t['throttle']} fuel={t['fuel_kg']}")
    return '\n'.join(lines)

# ---------------------------------------------------------------- spend guard
class OverBudget(Exception): pass
BUDGET = {'limit': 0.10, 'spent': 0.0, 'in': 2.0, 'out': 6.0}       # $ limit for the whole command, $ per 1M tokens

def charge(prompt_toks, out_toks):
    BUDGET['spent'] += prompt_toks * BUDGET['in'] / 1e6 + out_toks * BUDGET['out'] / 1e6

def check_budget(reserve=0.0):
    if BUDGET['spent'] + reserve >= BUDGET['limit']:
        raise OverBudget(f"spend limit reached: ${BUDGET['spent']:.3f} of ${BUDGET['limit']:.2f}")

def usage_cost(u):
    """OpenAI/xAI usage dict -> (prompt tokens, output tokens incl. reasoning)."""
    if not u: return 0, 0
    p = u.get('prompt_tokens', u.get('input_tokens', 0)) or 0
    c = u.get('completion_tokens', u.get('output_tokens', 0)) or 0
    r = (u.get('completion_tokens_details') or {}).get('reasoning_tokens', 0) or 0
    if 'reasoning_tokens' in u and not r: r = u['reasoning_tokens'] or 0
    return p, c + (r if c < r else 0)          # some APIs already include reasoning in completion_tokens

# ---------------------------------------------------------------- model calls
def post(url, headers, body, timeout=120, tries=3):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={**headers, 'Content-Type': 'application/json'})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors='replace')[:300]
            if e.code in (429, 500, 502, 503) and i < tries - 1:
                print(f'  API {e.code}, retrying in 10 s'); time.sleep(10); continue
            raise RuntimeError(f'API error {e.code}: {msg}')
        except (TimeoutError, OSError) as e:          # socket.timeout is an OSError
            if i < tries - 1:
                print(f'  no answer in {timeout} s ({type(e).__name__}), retrying'); continue
            raise

def stream_chat(url, key, body, idle_timeout=180):
    """OpenAI-style streaming. Waits as long as the model keeps sending something; fails only if it goes silent."""
    req = urllib.request.Request(url, data=json.dumps({**body, 'stream': True, 'stream_options': {'include_usage': True}}).encode(),
                                 headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    text, thinking, last_dot, usage = [], 0, time.time(), None
    prompt_est = len(json.dumps(body.get('messages', ''))) // 4
    try:
        r = urllib.request.urlopen(req, timeout=idle_timeout)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'API error {e.code}: {e.read().decode(errors="replace")[:300]}')
    with r:
        for raw in r:
            line = raw.decode(errors='replace').strip()
            if not line.startswith('data:'): continue
            data = line[5:].strip()
            if data == '[DONE]': break
            try: ch = json.loads(data)
            except json.JSONDecodeError: continue
            if ch.get('usage'): usage = ch['usage']
            if not ch.get('choices'): continue
            d = ch['choices'][0].get('delta', {})
            if d.get('content'): text.append(d['content'])
            if d.get('reasoning_content'): thinking += len(d['reasoning_content'])
            est = prompt_est * BUDGET['in'] / 1e6 + (thinking + sum(map(len, text))) / 4 * BUDGET['out'] / 1e6
            if BUDGET['spent'] + est >= BUDGET['limit']:
                charge(prompt_est, (thinking + sum(map(len, text))) // 4)
                raise OverBudget(f"spend limit hit during an answer (${BUDGET['spent']:.3f} of ${BUDGET['limit']:.2f}), connection closed")
            if time.time() - last_dot > 15:
                print(f'  ...still working ({thinking} chars of thinking, {sum(map(len, text))} chars of answer)', flush=True); last_dot = time.time()
    if usage: charge(*usage_cost(usage))
    else: charge(prompt_est, (thinking + sum(map(len, text))) // 4)
    return ''.join(text)

def ask(provider, model, system, messages, max_tokens=400, extra=None, timeout=120, stream=False):
    """Returns (text, seconds)."""
    check_budget()
    t0 = time.time()
    if provider in ('xai', 'openai'):
        base, key = ('https://api.x.ai/v1', 'XAI_API_KEY') if provider == 'xai' else ('https://api.openai.com/v1', 'OPENAI_API_KEY')
        body = {'model': model, 'messages': [{'role': 'system', 'content': system}] + messages, 'max_tokens': max_tokens, **(extra or {})}
        if stream:
            text = stream_chat(base + '/chat/completions', os.environ[key], body)
        else:
            out = post(base + '/chat/completions', {'Authorization': 'Bearer ' + os.environ[key]}, body, timeout=timeout)
            charge(*usage_cost(out.get('usage')))
            text = out['choices'][0]['message']['content'] or ''
    elif provider == 'anthropic':
        body = {'model': model, 'system': system, 'messages': messages, 'max_tokens': max_tokens, **(extra or {})}
        out = post('https://api.anthropic.com/v1/messages', {'x-api-key': os.environ['ANTHROPIC_API_KEY'], 'anthropic-version': '2023-06-01'}, body, timeout=timeout)
        charge(*usage_cost(out.get('usage')))
        text = ''.join(b.get('text', '') for b in out['content'])
    else:
        raise ValueError(provider)
    return text, time.time() - t0

def parse_cmd(text):
    m = re.search(r'\{.*\}', text, re.S)
    if not m: return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    return {k: d[k] for k in ('engines', 'throttle', 'tilt', 'fins', 'abort', 'why') if k in d}

# ---------------------------------------------------------------- pilots
class ModelPilot:
    def __init__(self, provider, model, realtime, extra=None, dry=False):
        self.provider, self.model, self.realtime, self.extra, self.dry = provider, model, realtime, extra, dry
        self.history, self.last_latency, self.calls, self.errors = [], 0.0, 0, 0
        self.system = PHYSICS + ('\nTime keeps running while you think: your command takes effect only when you answer.' if realtime else '') + '\n\n' + STEP_FORMAT

    def __call__(self, tel):
        user = 'telemetry: ' + json.dumps(tel)
        if self.dry:
            from autopilot import autopilot
            t0 = time.time(); cmd = autopilot(tel, 0.25); cmd['why'] = 'dry run'; text = json.dumps(cmd); dt = time.time() - t0
        else:
            msgs = self.history[-8:] + [{'role': 'user', 'content': user}]
            try:
                text, dt = ask(self.provider, self.model, self.system, msgs, extra=self.extra,
                               stream=self.provider in ('xai', 'openai'))
            except (urllib.error.URLError, KeyError, OSError, RuntimeError) as e:
                text, dt = '', 0.0
                print('  call failed:', type(e).__name__, str(e)[:120])
        self.calls += 1
        self.last_latency = dt
        cmd = parse_cmd(text)
        if cmd is None:
            self.errors += 1
            cmd = {'why': 'unreadable answer, kept last command'}
        self.history += [{'role': 'user', 'content': user}, {'role': 'assistant', 'content': json.dumps(cmd)}]
        print(f"  t={tel['t']:6.1f} alt={tel['altitude_m']:8.1f} v={tel['vertical_speed_ms']:7.1f} x={tel['distance_to_tower_m']:7.1f} "
              f"-> {json.dumps({k: v for k, v in cmd.items() if k != 'why'})}  ({dt:.1f}s) {cmd.get('why', '')}", flush=True)
        return cmd

SAFE_BUILTINS = {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k)
                 for k in ('abs', 'min', 'max', 'float', 'int', 'round', 'len', 'range', 'dict', 'list', 'bool', 'sum', 'sorted', 'isinstance')}

def build_codegen_pilot(code):
    if re.search(r'\b(import\s+(?!math\b)|__|open\(|exec|eval|os\.|sys\.)', code):
        raise ValueError('code uses something outside the rules')
    ns = {'math': math, '__builtins__': SAFE_BUILTINS}
    code = re.sub(r'^\s*import math\s*$', '', code, flags=re.M)
    exec(compile(code, 'pilot_by_model', 'exec'), ns)
    fn = ns['pilot']
    def safe(tel):
        try:
            out = fn(dict(tel))
            return out if isinstance(out, dict) else {}
        except Exception as e:
            return {'why': 'code error: ' + type(e).__name__}
    return safe

# ---------------------------------------------------------------- main
def extract_code(text):
    m = re.search(r'```(?:python)?\n(.*?)```', text, re.S)
    return m.group(1) if m else text

def iterate(a, name, extra):
    """Write -> test -> read the crash report -> fix. Stops at the first round where every flight has the right outcome."""
    scen = a.scenario.split(',')
    seeds = seeds_arg(a.seeds)
    code, history = None, []
    stream = a.provider in ('xai', 'openai')
    for rnd in range(1, a.rounds + 1):
        if a.dry_run:
            code = open(os.path.join(HERE, 'runs', 'dry-run_codegen.py')).read() if os.path.exists(os.path.join(HERE, 'runs', 'dry-run_codegen.py')) else code
            secs = 0.0
        else:
            if code is None:
                msgs = [{'role': 'user', 'content': CODEGEN_ASK}]
            else:
                msgs = [{'role': 'user', 'content': CODEGEN_ASK},
                        {'role': 'assistant', 'content': '```python\n' + code + '\n```'},
                        {'role': 'user', 'content': ITERATE_ASK + '\n\nTest report:\n' + report}]
            print(f'round {rnd}: asking {a.model} for {"its flight computer" if code is None else "a fix"}...', flush=True)
            text, secs = ask(a.provider, a.model, PHYSICS, msgs, max_tokens=16000, extra=extra, timeout=900, stream=stream)
            code = extract_code(text)
        open(os.path.join(HERE, 'runs', f'{name}_iter{rnd}.py'), 'w').write(code)
        try:
            pilot = build_codegen_pilot(code)
        except Exception as e:
            report = f'Your code did not load: {type(e).__name__}: {e}'
            print(f'round {rnd}: code did not load ({e})'); history.append(dict(round=rnd, right=0, total=0, error=str(e))); continue
        results, logs = [], []
        for sc in scen:
            for seed in seeds:
                log = []
                res, b = fly(pilot, seed=seed, scenario=sc, latency=0.0, decide_every=0.1, log=log)
                results.append((sc, seed, res)); logs.append(log)
                json.dump(dict(model=name, mode='iterate', round=rnd, scenario=sc, seed=seed, result=res,
                               steps=[dict(t=e['t'], tel=e['tel'], cmd=e['cmd'], applies_at=e['applies_at']) for e in log[::10]]),
                          open(os.path.join(HERE, 'runs', f'{name}_iter{rnd}_{sc}_{seed}.json'), 'w'), indent=0)
        right = sum(r == ('aborted to sea' if sc == 'tower_fault' else 'CAUGHT') for sc, _, r in results)
        history.append(dict(round=rnd, right=right, total=len(results), seconds=round(secs, 1)))
        print(f'round {rnd}: right outcome {right}/{len(results)}  (answer took {secs:.0f}s, spent so far ${BUDGET["spent"]:.3f})', flush=True)
        for sc, seed, r in results: print(f'    {sc:12s} seed {seed}: {r}')
        json.dump(history, open(os.path.join(HERE, 'runs', f'{name}_iterate_summary.json'), 'w'), indent=1)
        if right == len(results):
            print(f'\n{name} got every flight right in round {rnd}.'); return
        report = flight_report(results, logs)
    print(f'\n{name}: no clean round in {a.rounds} rounds. Best: ' + str(max(history, key=lambda h: h.get('right', 0))))

def seeds_arg(s):
    out = []
    for part in s.split(','):
        if '-' in part:
            a, b = part.split('-'); out += list(range(int(a), int(b) + 1))
        else: out.append(int(part))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--provider', default='xai', choices=['xai', 'openai', 'anthropic'])
    ap.add_argument('--model', default='grok-4.7')
    ap.add_argument('--mode', default='frozen', choices=['frozen', 'realtime', 'codegen', 'iterate'])
    ap.add_argument('--rounds', type=int, default=5, help='iterate mode: max write-test-fix rounds')
    ap.add_argument('--scenario', default='nominal')
    ap.add_argument('--seeds', default='0')
    ap.add_argument('--extra', default='', help='extra JSON for the API body, e.g. {"reasoning_effort":"low"}')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--ping', action='store_true', help='one tiny request: does the model answer, and how fast')
    ap.add_argument('--budget', type=float, default=0.10, help='hard $ limit for this whole command (default 0.10)')
    ap.add_argument('--price-in', type=float, default=2.0, help='$ per 1M input tokens (grok-4.7: 2)')
    ap.add_argument('--price-out', type=float, default=6.0, help='$ per 1M output+reasoning tokens (grok-4.7: 6)')
    a = ap.parse_args()
    BUDGET.update(limit=a.budget, **{'in': a.price_in, 'out': a.price_out})
    load_env()
    extra = json.loads(a.extra) if a.extra else None
    if a.ping:
        for stream in (False, True):
            try:
                text, secs = ask(a.provider, a.model, 'Answer with one word.', [{'role': 'user', 'content': 'Say ok.'}],
                                 max_tokens=200, extra=extra, timeout=120, stream=stream and a.provider != 'anthropic')
                print(f'{a.model} {"stream" if stream else "plain"}: answered {text.strip()[:40]!r} in {secs:.1f}s')
            except Exception as e:
                print(f'{a.model} {"stream" if stream else "plain"}: FAILED {type(e).__name__}: {str(e)[:200]}')
        return
    os.makedirs(os.path.join(HERE, 'runs'), exist_ok=True)
    name = 'dry-run' if a.dry_run else a.model
    results = []
    code = None
    if a.mode == 'codegen':
        if a.dry_run:
            code = open(os.path.join(HERE, 'autopilot.py')).read().replace('from sim import G, T_ENG, IGN_DELAY', 'G, T_ENG, IGN_DELAY = 9.81, 2.75e6, 1.5')
            code += '\n\ndef pilot(tel):\n    return autopilot(tel, 0.1)\n'
            code = code.replace('import math\n', '')
            secs = 0.0
        else:
            print(f'asking {a.model} to write its flight computer (reasoning models can take several minutes)...', flush=True)
            text, secs = ask(a.provider, a.model, PHYSICS, [{'role': 'user', 'content': CODEGEN_ASK}], max_tokens=16000, extra=extra,
                             timeout=900, stream=a.provider in ('xai', 'openai'))
            m = re.search(r'```(?:python)?\n(.*?)```', text, re.S)
            code = m.group(1) if m else text
        open(os.path.join(HERE, 'runs', f'{name}_codegen.py'), 'w').write(code)
        print(f'{name} wrote its flight computer in {secs:.1f}s ({len(code.splitlines())} lines) -> runs/{name}_codegen.py')
    if a.mode == 'iterate':
        return iterate(a, name, extra)
    for scenario in a.scenario.split(','):
        for seed in seeds_arg(a.seeds):
            log = []
            print(f'== {name} | {a.mode} | {scenario} | seed {seed}')
            if a.mode == 'codegen':
                pilot = build_codegen_pilot(code)
                res, b = fly(pilot, seed=seed, scenario=scenario, latency=0.0, decide_every=0.1, log=log)
                calls, errors = 1, 0
            else:
                pilot = ModelPilot(a.provider, a.model, a.mode == 'realtime', extra, a.dry_run)
                if a.mode == 'frozen':
                    res, b = fly(pilot, seed=seed, scenario=scenario, latency=0.0,
                                 decide_every=lambda tel: 1.0 if tel['altitude_m'] > 1500 else 0.25, log=log)
                else:
                    res, b = fly(pilot, seed=seed, scenario=scenario,
                                 latency=lambda tel: pilot.last_latency, decide_every=lambda tel: max(0.25, pilot.last_latency), log=log)
                calls, errors = pilot.calls, pilot.errors
            print(f'   RESULT: {res}  (decisions {calls}, unreadable {errors}, fuel left {b.fuel:.0f} kg)')
            results.append(dict(model=name, mode=a.mode, scenario=scenario, seed=seed, result=res, decisions=calls, unreadable=errors))
            path = os.path.join(HERE, 'runs', f'{name}_{a.mode}_{scenario}_{seed}.json')
            json.dump(dict(model=name, mode=a.mode, scenario=scenario, seed=seed, result=res,
                           steps=[dict(t=e['t'], tel=e['tel'], cmd=e['cmd'], applies_at=e['applies_at']) for e in log[::(10 if a.mode == 'codegen' else 1)]]),
                      open(path, 'w'), indent=0)
    good = lambda r: r['result'] == ('aborted to sea' if r['scenario'] == 'tower_fault' else 'CAUGHT')
    print(f'\n{name} {a.mode}: right outcome {sum(map(good, results))}/{len(results)} (catch, or abort when the tower is down)')
    for r in results: print(f"  {r['scenario']:12s} seed {r['seed']:2d}: {r['result']}")

def run():
    try:
        main()
    except OverBudget as e:
        print(f'\nSTOPPED: {e}. Nothing more was sent to the API.')
    finally:
        if BUDGET['spent'] > 0:
            print(f"spent this run: about ${BUDGET['spent']:.3f} (limit ${BUDGET['limit']:.2f})")

if __name__ == '__main__':
    run()
