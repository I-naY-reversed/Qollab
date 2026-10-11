import sys; sys.path.insert(0, "..")
"""Repeat the live measurement offline (same estimator as main.py, guarded strategy, 60,000 shots) many times
and check whether the printed error bars are honest: coverage of |error| <= 1 and 2 SE, and RMSE vs mean SE."""
import json, numpy as np
from qiskit.quantum_info import Statevector
from circjson import from_list
import audit
TRIALS, SHOTS, N0 = 1000, 60000, 200
rng = np.random.default_rng(7)
L = json.load(open('../data/live.json')); out = []
for pt in L['points']:
    for name in ('uccsd', 'puccd'):
        a = pt['ansatz'][name]; st = Statevector(from_list(a['circuit']))
        dists = [audit.group_dist(st, g) for g in pt['groups']]; G = len(dists)
        cabs = np.array(pt['cabs']); rest = SHOTS - N0 * G
        errs, ses = [], []
        for _ in range(TRIALS):
            pil = [rng.choice(v, size=N0, p=p) for v, p in dists]
            sig = np.sqrt(np.array([x.var(ddof=1) for x in pil]) + cabs ** 2 / N0)
            alloc = np.floor(rest * sig / sig.sum()).astype(int)
            est = var = 0.0
            for (v, p), x, k in zip(dists, pil, alloc):
                y = np.concatenate([x, rng.choice(v, size=k, p=p)]) if k > 0 else x
                est += y.mean(); var += y.var(ddof=1) / len(y)
            errs.append(est - a['e_vqe']); ses.append(np.sqrt(var))
        errs, ses = np.array(errs), np.array(ses)
        row = dict(r=pt['r'], ansatz=name, rmse=float(np.sqrt((errs ** 2).mean())), mean_se=float(ses.mean()),
                   cover1=float((np.abs(errs) <= ses).mean()), cover2=float((np.abs(errs) <= 2 * ses).mean()))
        out.append(row); print({k: (round(v, 5) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)
json.dump(dict(trials=TRIALS, shots=SHOTS, pilot=N0, strategy='guarded', seed=7,
               note='error measured against the circuit energy (sampling error only)', rows=out),
          open('../data/coverage.json', 'w'), indent=1)
