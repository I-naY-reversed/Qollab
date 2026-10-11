import sys; sys.path.insert(0, "..")
"""Measurement audit (offline). For each geometry and ansatz:
  bias      = E_VQE - E_exact (same active-space Hamiltonian; deterministic, from statevectors)
  target    = total RMSE sqrt(bias^2 + SE^2) <= 1.6 mHa  (chemical accuracy, defined before any budget)
  N_equal   = G * sum(sigma_g^2) / SE^2      equal shots per measurement group      (exact sigma: reference)
  N_oracle  = (sum sigma_g)^2 / SE^2         sigma-proportional allocation          (exact sigma: unattainable reference)
  Practical = pilot n0 shots per group, then remaining shots proportional to pilot sigma-hat; pilot counted.
              Evaluated by repeated simulated experiments (evidence, not the verdict)."""
import json, numpy as np
from qiskit import QuantumCircuit
from circjson import from_list
from qiskit.quantum_info import Statevector
CHEM_ACC = 1.6e-3
N0 = 200
TRIALS = 200
BUDGETS = np.unique(np.round(np.logspace(np.log10(3e4), np.log10(1e8), 15)).astype(int))
rng = np.random.default_rng(20261011)

def group_dist(state, grp):
    n = len(grp['basis']); qc = QuantumCircuit(n)
    for q, ch in enumerate(reversed(grp['basis'])):
        if ch == 'X': qc.h(q)
        elif ch == 'Y': qc.sdg(q); qc.h(q)
    p = state.evolve(qc).probabilities(); vals = np.zeros(2 ** n)
    for lab, c in zip(grp['paulis'], grp['coeffs']):
        qs = [n - 1 - i for i, ch in enumerate(lab) if ch != 'I']
        par = np.zeros(2 ** n, int)
        for q in qs: par ^= (np.arange(2 ** n) >> q) & 1
        vals += c * (1 - 2 * par)
    keep = p > 1e-15
    return vals[keep], p[keep] / p[keep].sum()

def errors(dists, mu, budget, strategy, cabs=None):

    G = len(dists); T = TRIALS
    if strategy == 'equal':
        n = budget // G; est = np.zeros(T)
        for v, p in dists: est += rng.multinomial(n, p, size=T) @ v / n
        return est - mu.sum()
    if budget <= N0 * G: return None
    pil = [rng.multinomial(N0, p, size=T) for v, p in dists]
    m = np.array([c @ v / N0 for c, (v, p) in zip(pil, dists)])
    s2 = np.array([np.maximum((c * (v[None, :] - mm[:, None]) ** 2).sum(1) / (N0 - 1), 0)
                   for c, (v, p), mm in zip(pil, dists, m)])
    sig = np.sqrt(s2)
    if strategy == 'guarded':
        sig = np.sqrt(s2 + (np.asarray(cabs)[:, None] ** 2) / N0)
    rest = budget - N0 * G
    alloc = np.floor(rest * sig / np.maximum(sig.sum(0), 1e-300)).astype(np.int64)
    est = np.zeros(T)
    for g, (v, p) in enumerate(dists):
        extra = np.array([rng.multinomial(k, p) @ v if k > 0 else 0.0 for k in alloc[g]])
        est += (m[g] * N0 + extra) / (N0 + alloc[g])
    return est - mu.sum()

if __name__ == '__main__':
    D = json.load(open('../data/geometries.json')); out = []
    for g in D['geometries']:
        row = dict(r=g['r'], exact=g['exact'], hf=g['hf'], ccsd=g['ccsd'], ansatz={})
        for name, a in g['ansatz'].items():
            st = Statevector(from_list(json.load(open('../circuits/' + a['qasm'].replace('.qasm', '.json')))))
            dists = [group_dist(st, grp) for grp in g['groups']]
            mu = np.array([v @ p for v, p in dists]); sd = np.array([np.sqrt(p @ (v - v @ p) ** 2) for v, p in dists])
            assert np.allclose(sd, a['group_std'], atol=1e-9) and abs(mu.sum() - a['e_vqe']) < 1e-8
            bias = a['e_vqe'] - g['exact']; G = len(dists)
            reachable = abs(bias) < CHEM_ACC
            se = np.sqrt(CHEM_ACC ** 2 - bias ** 2) if reachable else None
            n_eq = int(np.ceil(G * (sd ** 2).sum() / se ** 2)) if reachable else None
            n_or = int(np.ceil(sd.sum() ** 2 / se ** 2)) if reachable else None
            emp = {}
            cabs = [sum(abs(c) for lab, c in zip(grp['paulis'], grp['coeffs']) if set(lab) != {'I'}) for grp in g['groups']]

            pz = np.array([p.max() ** N0 for v, p in dists]); gapm = np.array([abs(v[np.argmax(p)] - v @ p) for v, p in dists])
            naive_floor = float(np.sqrt((pz * gapm ** 2).sum()))
            for strat in ('equal', 'pilot', 'guarded'):
                rm = []
                for B in BUDGETS:
                    errs = errors(dists, mu, int(B), strat, cabs)
                    rm.append(None if errs is None else float(np.sqrt(np.mean(errs ** 2))))
                tot = [None if x is None else float(np.sqrt(x ** 2 + bias ** 2)) for x in rm]
                hit = next((int(B) for B, t in zip(BUDGETS, tot) if t is not None and t <= CHEM_ACC), None)
                emp[strat] = dict(sampling_rmse=rm, total_rmse=tot, first_budget_meeting_target=hit)
            row['ansatz'][name] = dict(bias=bias, reachable=reachable, se_needed=se, n_equal=n_eq, n_oracle=n_or,
                                       sigma_sum=float(sd.sum()), sigma_sq_sum=float((sd ** 2).sum()), groups=G,
                                       cx=a['cx'], depth=a['depth'], naive_pilot_floor=naive_floor, empirical=emp)
            print(f"r={g['r']:.3f} {name:5s} bias={1e3*bias:8.4f} mHa reach={reachable} N_eq={n_eq} N_oracle={n_or} "
                  f"floor={1e3*naive_floor:.2f}mHa pilot_hit={emp['pilot']['first_budget_meeting_target']} guarded_hit={emp['guarded']['first_budget_meeting_target']} equal_hit={emp['equal']['first_budget_meeting_target']}", flush=True)
        out.append(row)
    json.dump(dict(chem_acc=CHEM_ACC, pilot_per_group=N0, trials=TRIALS, budgets=[int(b) for b in BUDGETS], seed=20261011,
                   target='total RMSE sqrt(bias^2 + SE^2) <= 1.6 mHa', geometries=out), open('../data/audit.json', 'w'), indent=1)
