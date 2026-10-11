# Grok as an engineer with a simulator: it writes its flight computer, runs test flights itself, reads the results,
# fixes the code and repeats, all in one conversation. It only gets facts back (results and telemetry), never hints.
#
#   python3 grok_agent.py --model grok-4.7 --extra '{"reasoning_effort":"low"}' --budget 1.30
#
# Tools the model can call:
#   run_tests(code)                                   15 test flights, one line per flight
#   inspect_flight(code, scenario, seed, t_from, t_to) telemetry table of one flight, every 0.5 s
#   submit(code)                                      final answer
# Everything is logged to runs/agent_*. Spend limit is checked before every call; each call is capped in tokens.
import argparse, json, os, sys, time
from grok_pilot import (PHYSICS, CODEGEN_ASK, build_codegen_pilot, post, load_env, BUDGET, charge, usage_cost,
                        check_budget, OverBudget, HERE)
from sim import fly

SCENARIOS = ['nominal', 'tower_fault', 'engine_out']
SEEDS = [0, 1, 2, 3, 4]

TASK = CODEGEN_ASK.split('Answer with the code only')[0] + """You have a simulator. Use the tools to test your code before you submit:
- run_tests(code): runs the 15 test flights (nominal, tower_fault, engine_out; seeds 0-4) and returns each outcome.
- inspect_flight(code, scenario, seed, t_from, t_to): returns the telemetry and your commands every 0.5 s in that time window.
- submit(code): your final flight computer.
Goal: every flight right (CAUGHT in nominal and engine_out, 'aborted to sea' in tower_fault).
Work like an engineer: test, look at what actually happened, fix, test again. Submit when all 15 are right or when you are confident it is your best."""

CODE = {'type': 'string', 'description': 'the full Python source with def pilot(tel)'}
TOOLS = [
    {'type': 'function', 'function': {'name': 'run_tests', 'description': 'Run the 15 test flights with this code.',
        'parameters': {'type': 'object', 'properties': {'code': CODE}, 'required': ['code']}}},
    {'type': 'function', 'function': {'name': 'inspect_flight', 'description': 'Telemetry of one test flight, every 0.5 s between t_from and t_to (seconds).',
        'parameters': {'type': 'object', 'properties': {'code': CODE, 'scenario': {'type': 'string', 'enum': SCENARIOS},
                       'seed': {'type': 'integer'}, 't_from': {'type': 'number'}, 't_to': {'type': 'number'}},
                       'required': ['code', 'scenario', 'seed', 't_from', 't_to']}}},
    {'type': 'function', 'function': {'name': 'submit', 'description': 'Submit your final flight computer.',
        'parameters': {'type': 'object', 'properties': {'code': CODE}, 'required': ['code']}}},
]

def right(sc, res): return res == ('aborted to sea' if sc == 'tower_fault' else 'CAUGHT')

def run_tests(code):
    try:
        pilot = build_codegen_pilot(code)
    except Exception as e:
        return f'code did not load: {type(e).__name__}: {e}', 0
    lines, n = [], 0
    for sc in SCENARIOS:
        for seed in SEEDS:
            log = []
            res, b = fly(pilot, seed=seed, scenario=sc, decide_every=0.1, log=log)
            ok = right(sc, res); n += ok
            ign = next((e['tel'] for e in log if e['tel']['engines_running'] > 0), None)
            extra = f" | engines first on at t={ign['t']} alt={ign['altitude_m']} m v={ign['vertical_speed_ms']} m/s" if ign else ' | engines never ran'
            lines.append(f"{sc} seed {seed}: {res}{'' if ok else '  <-- WRONG'} | ended t={b.t:.1f}s, fuel left {b.fuel:.0f} kg{extra}")
    return f'{n}/15 right\n' + '\n'.join(lines), n

def inspect_flight(code, scenario, seed, t_from, t_to):
    try:
        pilot = build_codegen_pilot(code)
    except Exception as e:
        return f'code did not load: {type(e).__name__}: {e}'
    log = []
    res, b = fly(pilot, seed=int(seed), scenario=scenario, decide_every=0.1, log=log)
    rows = [e for e in log if float(t_from) <= e['t'] <= float(t_to)][::5][:60]
    out = [f'result: {res} (flight ended at t={b.t:.1f}s)', 't | alt | v_vert | dist | v_side | tilt | engines(cmd/run) | throttle | fuel | your command']
    for e in rows:
        t, c = e['tel'], e['cmd']
        out.append(f"{t['t']} | {t['altitude_m']} | {t['vertical_speed_ms']} | {t['distance_to_tower_m']} | {t['sideways_speed_ms']} | {t['tilt_deg']} | "
                   f"{t['engines_commanded']}/{t['engines_running']} | {t['throttle']} | {t['fuel_kg']} | {json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in c.items()})}")
    return '\n'.join(out)

def call(model, messages, extra, max_tokens):
    est = sum(len(json.dumps(m)) for m in messages) / 4 * BUDGET['in'] / 1e6 + max_tokens * BUDGET['out'] / 1e6
    check_budget(reserve=est)                              # stop BEFORE a call that could cross the limit
    body = {'model': model, 'messages': messages, 'tools': TOOLS, 'max_tokens': max_tokens, **(extra or {})}
    t0 = time.time()
    out = post('https://api.x.ai/v1/chat/completions', {'Authorization': 'Bearer ' + os.environ['XAI_API_KEY']}, body, timeout=900, tries=1)
    charge(*usage_cost(out.get('usage')))
    return out['choices'][0]['message'], time.time() - t0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', default='grok-4.7')
    ap.add_argument('--extra', default='')
    ap.add_argument('--budget', type=float, default=1.30)
    ap.add_argument('--max-turns', type=int, default=30)
    ap.add_argument('--max-tokens', type=int, default=8000, help='cap per model reply (thinking included)')
    a = ap.parse_args()
    load_env()
    BUDGET.update(limit=a.budget)
    extra = json.loads(a.extra) if a.extra else None
    os.makedirs(os.path.join(HERE, 'runs'), exist_ok=True)
    tag = 'agent_' + a.model
    messages = [{'role': 'system', 'content': PHYSICS}, {'role': 'user', 'content': TASK}]
    transcript, best = [], (-1, None)
    final = None
    try:
        for turn in range(1, a.max_turns + 1):
            msg, secs = call(a.model, messages, extra, a.max_tokens)
            calls = msg.get('tool_calls') or []
            keep = {'role': 'assistant', 'content': msg.get('content') or ''}
            if calls: keep['tool_calls'] = calls
            messages.append(keep)
            say = (msg.get('content') or '').strip()
            print(f"turn {turn} ({secs:.0f}s, spent ${BUDGET['spent']:.3f}): {say[:200]}" if say else f"turn {turn} ({secs:.0f}s, spent ${BUDGET['spent']:.3f})", flush=True)
            if not calls:
                transcript.append(dict(turn=turn, said=say))
                messages.append({'role': 'user', 'content': 'Use the tools: test your code with run_tests, or submit it.'})
                continue
            for tc in calls:
                fn = tc['function']['name']
                try: args = json.loads(tc['function'].get('arguments') or '{}')
                except json.JSONDecodeError: args = {}
                code = args.get('code', '')
                if fn == 'run_tests':
                    result, n = run_tests(code)
                    v = len([t for t in transcript if t.get('tool') == 'run_tests']) + 1
                    open(os.path.join(HERE, 'runs', f'{tag}_v{v}.py'), 'w').write(code)
                    if n > best[0]: best = (n, code)
                    print(f'   run_tests v{v}: {result.splitlines()[0]}', flush=True)
                elif fn == 'inspect_flight':
                    result = inspect_flight(code, args.get('scenario', 'nominal'), args.get('seed', 0), args.get('t_from', 0), args.get('t_to', 120))
                    print(f"   inspect_flight {args.get('scenario')} seed {args.get('seed')} t={args.get('t_from')}..{args.get('t_to')}", flush=True)
                elif fn == 'submit':
                    final = code
                    result = 'submitted'
                else:
                    result = 'unknown tool'
                transcript.append(dict(turn=turn, said=say, tool=fn, args={k: v for k, v in args.items() if k != 'code'}, result=result[:3000]))
                messages.append({'role': 'tool', 'tool_call_id': tc['id'], 'content': result})
            if final is not None:
                break
    except OverBudget as e:
        print(f'\nSTOPPED: {e}')
    finally:
        json.dump(transcript, open(os.path.join(HERE, 'runs', f'{tag}_transcript.json'), 'w'), indent=1)
        code = final if final is not None else best[1]
        if code:
            open(os.path.join(HERE, 'runs', f'{tag}_final.py'), 'w').write(code)
            res, n = run_tests(code)
            print(f"\n{'SUBMITTED' if final is not None else 'BEST TESTED'} flight computer: {res.splitlines()[0]}")
            print(res)
        print(f"spent this run: about ${BUDGET['spent']:.3f} (limit ${BUDGET['limit']:.2f})")

if __name__ == '__main__':
    main()
