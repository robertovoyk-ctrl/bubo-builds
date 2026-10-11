# Grade Grok's final flight computer on flights it never saw during its own testing (it only ever tested seeds 0-4).
#   python3 check_unseen.py                       -> 500 new seeds x 3 scenarios = 1,500 flights
#   python3 check_unseen.py runs/agent_grok-4.7_v3.py 5 55
# Right = CAUGHT in nominal and engine_out, 'aborted to sea' in tower_fault. No API calls.
import sys, collections
from grok_pilot import build_codegen_pilot
from sim import fly
path = sys.argv[1] if len(sys.argv) > 1 else 'runs/agent_grok-4.7_final.py'
a, b = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (100, 600)
code = open(path).read(); total = n = 0
for sc in ['nominal', 'tower_fault', 'engine_out']:
    outcomes = collections.Counter(); ok = 0
    for seed in range(a, b):
        res, _ = fly(build_codegen_pilot(code), seed=seed, scenario=sc, decide_every=0.1)
        good = res == ('aborted to sea' if sc == 'tower_fault' else 'CAUGHT'); ok += good
        outcomes[res if not good else 'right'] += 1
    print(f'{sc:12s} {ok}/{b - a}  {dict(outcomes.most_common(3))}', flush=True)
    total += ok; n += b - a
print(f'TOTAL {total}/{n} right on seeds {a}-{b - 1}')
