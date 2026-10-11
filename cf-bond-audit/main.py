import json, math, time
import numpy as np
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit
from circjson import from_list

try:
    backend
except NameError:
    from qiskit.providers.basic_provider import BasicSimulator
    backend = BasicSimulator()

CHEM_ACC = 1.6e-3
LIVE = json.load(open("data/live.json"))
CURVE = json.load(open("data/curve.json"))
AUDIT = json.load(open("data/audit.json"))
PAIR = json.load(open("data/pairing.json"))


def basis_circuit(prep, basis):

    qc = prep.copy()
    for q, ch in enumerate(reversed(basis)):
        if ch == "X":
            qc.h(q)
        elif ch == "Y":
            qc.sdg(q)
            qc.h(q)
    qc.measure_all()
    return qc


def outcome_values(group, bitstrings):

    n = len(group["basis"])
    out = np.zeros(len(bitstrings))
    bits = np.array([[int(s[n - 1 - q]) for q in range(n)] for s in bitstrings])
    for lab, c in zip(group["paulis"], group["coeffs"]):
        qs = [n - 1 - i for i, ch in enumerate(lab) if ch != "I"]
        par = bits[:, qs].sum(1) % 2 if qs else np.zeros(len(bitstrings), int)
        out += c * (1 - 2 * par)
    return out


SEED = [0]


def run(circs, shots, memory=False):

    SEED[0] += 1
    try:
        return backend.run(circs, shots=shots, memory=memory, seed_simulator=SEED[0]).result()
    except Exception:
        return backend.run(circs, shots=shots, memory=memory).result()


def measure_energy(prep, groups, cabs, total_shots, pilot, strategy):

    G = len(groups)
    circs = [basis_circuit(prep, g["basis"]) for g in groups]
    if strategy == "equal":
        n = max(total_shots // G, 1)
        res = run(circs, n)
        est, var = 0.0, 0.0
        for i, g in enumerate(groups):
            counts = res.get_counts(i)
            keys = list(counts)
            v = outcome_values(g, keys)
            w = np.array([counts[k] for k in keys], float)
            m = float(w @ v / w.sum())
            s2 = float(w @ (v - m) ** 2 / max(w.sum() - 1, 1))
            est += m
            var += s2 / w.sum()
        assert G * n <= total_shots, "executed shots exceeded the budget"
        return est, math.sqrt(var), G * n
    if pilot < 2 or total_shots < pilot * G:
        raise ValueError(f"need pilot_shots >= 2 and shots_per_point >= {G} x pilot_shots for the {strategy} strategy")
    rest = total_shots - pilot * G
    res = run(circs, pilot, memory=True)
    vals = [outcome_values(g, res.get_memory(i)) for i, g in enumerate(groups)]
    sig = []
    for i, v in enumerate(vals):
        s2 = float(v.var(ddof=1))
        if strategy == "guarded":
            s2 += cabs[i] ** 2 / pilot
        sig.append(math.sqrt(max(s2, 0.0)))
    sig = np.array(sig)
    alloc = np.floor(rest * sig / sig.sum()).astype(int) if sig.sum() > 0 else np.zeros(G, int)
    est, var, executed = 0.0, 0.0, pilot * G
    for i, g in enumerate(groups):
        v = vals[i]
        if alloc[i] > 0:
            more = run(circs[i], int(alloc[i]), memory=True).get_memory()
            v = np.concatenate([v, outcome_values(g, more)])
            executed += int(alloc[i])
        est += float(v.mean())
        var += float(v.var(ddof=1)) / len(v)
    assert executed <= total_shots, "executed shots exceeded the budget"
    return est, math.sqrt(var), executed


def mha(x):
    return 1000.0 * x


def main(shots_per_point: int = 60000, ansatz: str = "both", strategy: str = "guarded", pilot_shots: int = 200, seed: int = 1011):

    t0 = time.time()
    SEED[0] = seed * 1000
    names = ["uccsd", "puccd"] if ansatz == "both" else [ansatz]
    print("C-F Bond Accuracy Audit: CH3F, STO-3G, CAS(4e,4o), 6 qubits, 70 measurement groups")
    print(f"Backend: {getattr(backend, 'name', backend)}. Shots per point: {shots_per_point}, strategy: {strategy}, pilot: {pilot_shots}/group, seed: {seed}")
    print("Energies in Hartree. Exact = CASCI in the same active space (the strongest classical baseline here).\n")
    live = {n: [] for n in names}
    for pt in LIVE["points"]:
        for n in names:
            a = pt["ansatz"][n]
            prep = from_list(a["circuit"])
            e, se, used = measure_energy(prep, pt["groups"], pt["cabs"], shots_per_point, pilot_shots, strategy)
            err = e - pt["exact"]
            live[n].append((pt["r"], e, se))
            ag = [g for g in AUDIT["geometries"] if abs(g["r"] - pt["r"]) < 1e-9][0]["ansatz"][n]
            if strategy == "equal":
                pred = math.sqrt(len(pt["groups"]) * ag["sigma_sq_sum"] / max(shots_per_point, 1))
            else:
                pred = ag["sigma_sum"] / math.sqrt(max(shots_per_point, 1))
            print(f"r(C-F) = {pt['r']:.3f} A  {n:5s}  measured {e:.5f} +/- {se:.5f}  (shots executed {used} of {shots_per_point})  "
                  f"exact {pt['exact']:.5f}  measured - exact = {mha(err):+.2f} mHa  "
                  f"[ansatz error {mha(a['bias']):+.3f} mHa, {a['cx']} CX; "
                  f"reference standard error for this strategy {mha(pred):.1f} mHa]")
    print(f"\nLive measurement finished in {time.time() - t0:.1f} s.\n")

    print("Verdict (deterministic, from exact statevector values shipped in data/audit.json):")
    for n in ("uccsd", "puccd"):
        rows = [g["ansatz"][n] for g in AUDIT["geometries"]]
        bad = [g["r"] for g in AUDIT["geometries"] if not g["ansatz"][n]["reachable"]]
        worst = max(abs(r["bias"]) for r in rows)
        if bad:
            print(f"  {n.upper()}: ansatz error up to {mha(worst):.2f} mHa > 1.6 mHa at {len(bad)} of {len(rows)} bond lengths. "
                  f"No number of shots can reach chemical accuracy there.")
        else:
            nmax = max(r["n_equal"] for r in rows)
            nmin = min(r["n_equal"] for r in rows)
            print(f"  {n.upper()}: ansatz error <= {mha(worst):.3f} mHa everywhere; with equal allocation it needs "
                  f"{nmin/1e6:.1f} to {nmax/1e6:.1f} million shots per energy to reach total RMSE <= 1.6 mHa.")
    gaps = [row["pair_gap"] for row in PAIR["rows"]]
    near = max(abs(row["puccd_minus_pair"]) for row in PAIR["rows"])
    print(f"  Why pUCCD misses: the best possible paired-electron state in these orbitals (DOCI, a 6x6 exact solve) is already "
          f"{mha(min(gaps)):.1f} to {mha(max(gaps)):.1f} mHa above exact at every bond length, and the pUCCD circuits sit within "
          f"{mha(near):.4f} mHa of that limit. The miss is structural, not an optimization failure.")
    eq = [g for g in AUDIT["geometries"] if abs(g["r"] - 1.383) < 1e-6][0]["ansatz"]["uccsd"]
    print(f"  Naive pilot allocation at equilibrium stops improving: its error floor is at least {mha(eq['naive_pilot_floor']):.2f} mHa "
          f"(observed about 3 mHa), which more shots do not remove (rare outcomes missed by a {AUDIT['pilot_per_group']}-shot pilot).")

    plot(live)


def plot(live):
    r = np.array([g["r"] for g in CURVE["geometries"]])
    ex = np.array([g["exact"] for g in CURVE["geometries"]])
    fig, ax = plt.subplots(1, 3, figsize=(16, 4.8))
    styles = {"hf": ("Hartree-Fock", "s", ":"), "ccsd": ("CCSD (same active space)", "^", "--"),
              "uccsd": ("UCCSD-VQE (exact expectation)", "o", "-"), "puccd": ("pUCCD-VQE (exact expectation)", "D", "-.")}
    ax[0].plot(r, ex, "k-", lw=2, label="Exact (CASCI)")
    for k in ("hf", "ccsd"):
        lab, mk, ls = styles[k]
        ax[0].plot(r, [g[k] for g in CURVE["geometries"]], ls, marker=mk, ms=4, label=lab)
    for n, pts in live.items():
        if pts:
            ax[0].errorbar([p[0] for p in pts], [p[1] for p in pts], yerr=[p[2] for p in pts], fmt=styles[n][1],
                           ms=7, capsize=3, label=f"{n.upper()} measured live")
    ax[0].set(xlabel="C-F distance (angstrom)", ylabel="Energy (Hartree)", title="C-F bond stretching, same model for every method")
    ax[0].legend(fontsize=8)
    for k in ("hf", "ccsd", "uccsd", "puccd"):
        lab, mk, ls = styles[k]
        if k in ("uccsd", "puccd"):
            err = [abs(g["ansatz"][k]["bias"]) for g in CURVE["geometries"]]
        else:
            err = [abs(g[k] - g["exact"]) for g in CURVE["geometries"]]
        ax[1].semilogy(r, 1000 * np.maximum(err, 1e-9), ls, marker=mk, ms=5, label=lab)
    ax[1].semilogy([row["r"] for row in PAIR["rows"]], [1000 * row["pair_gap"] for row in PAIR["rows"]], "k:",
                   marker="v", ms=5, label="best paired-electron state (DOCI): limit for any pUCCD")
    ax[1].axhline(1.6, color="k", lw=1)
    ax[1].text(r[0], 1.9, "chemical accuracy 1.6 mHa", fontsize=8)
    ax[1].set(xlabel="C-F distance (angstrom)", ylabel="|E - exact| (mHa, log)", title="Error vs exact (no shot noise)")
    ax[1].legend(fontsize=8)
    eq = [g for g in AUDIT["geometries"] if abs(g["r"] - 1.383) < 1e-6][0]["ansatz"]["uccsd"]["empirical"]
    B = np.array(AUDIT["budgets"])
    for k, lab, mk in (("equal", "equal shots per group", "o"), ("pilot", "naive pilot allocation", "x"), ("guarded", "guarded pilot allocation", "s")):
        y = [np.nan if v is None else 1000 * v for v in eq[k]["sampling_rmse"]]
        ax[2].loglog(B, y, marker=mk, label=lab)
    ax[2].axhline(1.6, color="k", lw=1)
    ax[2].set(xlabel="total shots per energy", ylabel="sampling RMSE (mHa)",
              title=f"UCCSD at equilibrium: {AUDIT['trials']} simulated experiments per point")
    ax[2].legend(fontsize=8)
    fig.tight_layout()
    plt.show()


main()
