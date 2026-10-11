import sys
import time

import numpy as np
from qiskit import transpile
from qiskit.primitives import StatevectorSampler

from bh.qae import classical_mc, fast_path_hits, mlae_circuits, mlae_estimate, queries

KS = [0, 1, 2, 4, 8, 16]
SHOTS = 100


def edge_pixel(n, rng):

    side = 2 ** (n // 2)
    y, x = np.mgrid[0:side, 0:side] / side
    f = 1 / (1 + np.exp(-(x + 0.6 * y - 0.8 + 0.05 * rng.standard_normal()) * 25))
    f = f.ravel()
    if len(f) < 2**n:
        f = np.resize(f, 2**n)
    return f


def run(n, rng):
    f = edge_pixel(n, rng)
    mu = f.mean()
    t0 = time.perf_counter()
    circs = mlae_circuits(f, KS)
    t_build = time.perf_counter() - t0
    t0 = time.perf_counter()
    tc = transpile(circs, basis_gates=["u", "cx"], optimization_level=1)
    t_tr = time.perf_counter() - t0
    cx = [c.count_ops().get("cx", 0) for c in tc]
    t0 = time.perf_counter()
    res = StatevectorSampler(seed=1).run(circs, shots=SHOTS).result()
    t_run = time.perf_counter() - t0
    hits = [r.data.c.get_counts().get("1", 0) for r in res]
    est = mlae_estimate(KS, hits, SHOTS)
    nq = queries(KS, SHOTS)
    print(f"n={n} qubits={n + 1} mu={mu:.5f} mlae={est:.5f} err={abs(est - mu):.2e} "
          f"queries={nq} classical_err={abs(classical_mc(f, nq, rng) - mu):.2e}")
    print(f"  build {t_build:.2f}s  transpile {t_tr:.2f}s  sample {t_run:.2f}s  cx per k {cx}")
    return mu


def error_scaling(rng, trials=200):

    print("queries  rmse_mlae  rmse_mc")
    for m in range(1, len(KS) + 1):
        ks = KS[:m]
        nq = queries(ks, SHOTS)
        e_q, e_c = [], []
        for _ in range(trials):
            mu = rng.uniform(0.05, 0.95)
            f = (rng.random(1024) < mu).astype(float)
            mu = f.mean()
            e_q.append(mlae_estimate(ks, fast_path_hits(mu, ks, SHOTS, rng), SHOTS) - mu)
            e_c.append(classical_mc(f, nq, rng) - mu)
        print(f"{nq:7d}  {np.sqrt(np.mean(np.square(e_q))):.2e}   {np.sqrt(np.mean(np.square(e_c))):.2e}")


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    for n in [int(a) for a in sys.argv[1:]] or [6, 8, 10]:
        run(n, rng)
    error_scaling(rng)
