import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import UCRYGate


def state_prep(f):

    f = np.clip(np.asarray(f, dtype=float), 0.0, 1.0)
    n = int(np.log2(len(f)))
    assert 2**n == len(f), "len(f) must be a power of 2"
    qc = QuantumCircuit(n + 1, name="A")
    qc.h(range(1, n + 1))

    qc.append(UCRYGate(list(2 * np.arcsin(np.sqrt(f)))), [0] + list(range(1, n + 1)))
    return qc


def grover_op(a_circ):

    m = a_circ.num_qubits
    q = QuantumCircuit(m, name="Q")
    q.z(0)
    q.compose(a_circ.inverse(), inplace=True)
    q.x(range(m))
    q.h(m - 1)
    q.mcx(list(range(m - 1)), m - 1)
    q.h(m - 1)
    q.x(range(m))
    q.compose(a_circ, inplace=True)
    return q


def mlae_circuits(f, ks):

    a = state_prep(f)
    q = grover_op(a)
    circs = []
    for k in ks:
        c = QuantumCircuit(a.num_qubits, 1)
        c.compose(a, inplace=True)
        for _ in range(k):
            c.compose(q, inplace=True)
        c.measure(0, 0)
        circs.append(c)
    return circs


def queries(ks, shots):

    return shots * sum(2 * k + 1 for k in ks)


_GRID = np.linspace(0, np.pi / 2, 20001)


def mlae_estimate(ks, hits, shots):

    ll = np.zeros_like(_GRID)
    for k, h in zip(ks, hits):
        p = np.clip(np.sin((2 * k + 1) * _GRID) ** 2, 1e-12, 1 - 1e-12)
        ll += h * np.log(p) + (shots - h) * np.log(1 - p)
    return float(np.sin(_GRID[np.argmax(ll)]) ** 2)


def mlae_rmse(mu, ks, shots, trials=400, seed=1):

    rng = np.random.default_rng(seed)
    theta = np.arcsin(np.sqrt(mu))
    ks = np.asarray(ks)
    hits = rng.binomial(shots, np.sin((2 * ks + 1) * theta) ** 2, size=(trials, len(ks)))
    p = np.clip(np.sin(np.outer(2 * ks + 1, _GRID)) ** 2, 1e-12, 1 - 1e-12)
    ll = hits @ np.log(p) + (shots - hits) @ np.log1p(-p)
    est = np.sin(_GRID[np.argmax(ll, 1)]) ** 2
    return float(np.sqrt(np.mean((est - mu) ** 2)))


def fast_path_hits(mu, ks, shots, rng):

    theta = np.arcsin(np.sqrt(mu))
    return [int(rng.binomial(shots, np.sin((2 * k + 1) * theta) ** 2)) for k in ks]


def classical_mc(f, n_samples, rng):

    return float(np.mean(rng.choice(np.asarray(f), size=n_samples)))
