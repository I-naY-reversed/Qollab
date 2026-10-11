import inspect as _inspect
import json
import math
import time

from qiskit import QuantumCircuit, transpile

SHOTS = 4000


async def _maybe(v):
    return await v if _inspect.isawaitable(v) else v


def _is_ionq(backend):
    return "ionq" in str(getattr(backend, "name", "")).lower()


def helstrom(theta, p):

    return 0.5 * (1 + math.sqrt(1 - 4 * p * (1 - p) * math.cos(theta) ** 2))


def p_success(theta, p, beta):

    return p * (1 + math.cos(beta - theta)) / 2 + (1 - p) * (1 - math.cos(beta + theta)) / 2


def circuit(theta, beta, mode):

    usd = mode == "usd"
    qc = QuantumCircuit(4 if usd else 2, 4 if usd else 2)
    qc.ry(theta, 0)
    qc.ry(-theta, 1)
    if usd:
        g = math.acos(min(1.0, math.tan(theta / 2)))
        for s, a in ((0, 2), (1, 3)):
            qc.x(s)
            qc.cry(2 * g, s, a)
            qc.x(s)
            qc.h(s)
        qc.measure([0, 1, 2, 3], [0, 1, 2, 3])
    else:
        qc.ry(-beta, 0)
        qc.ry(-beta, 1)
        qc.measure([0, 1], [0, 1])
    return qc


def tally(counts, mode):

    out = [[0, 0, 0], [0, 0, 0]]
    for key, n in counts.items():
        b = key.replace(" ", "")[::-1]
        for s in (0, 1):
            if mode == "usd" and b[2 + s] == "1":
                out[s][2] += n
            else:
                guess_plus = b[s] == "0"
                out[s][0 if guess_plus == (s == 0) else 1] += n
    return out


async def measure(backend, theta, beta, mode):
    t0 = time.perf_counter()
    theta, beta = float(theta), float(beta)
    qc = circuit(theta, beta, str(mode))
    try:
        tc = transpile(qc, backend=backend, optimization_level=1, num_processes=1)
    except Exception:
        tc = transpile(qc, basis_gates=["rz", "sx", "x", "cx"], optimization_level=1, num_processes=1)
    job = await _maybe(backend.run(tc, shots=SHOTS))
    result = await _maybe(job.result())
    t = tally(result.get_counts(), str(mode))
    ops = tc.count_ops()
    return json.dumps(dict(tally=t, shots=SHOTS, qubits=qc.num_qubits, depth=tc.depth(), cx=int(tc.num_nonlocal_gates()),
                           backend=str(getattr(backend, "name", backend)), ionq=_is_ionq(backend),
                           seconds=time.perf_counter() - t0, drawing=str(qc.draw(output="text", fold=-1))))
