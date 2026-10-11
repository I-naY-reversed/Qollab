import math

from qiskit import QuantumCircuit


ROUTE_KM = 540.0
F0 = 0.95
F0_CHOICES = (0.90, 0.95, 0.99)
LOSS_DB_PER_KM = 0.2
C_FIBRE_KM_S = 2.0e5
QBER_MAX = 0.11


def w_of(F):
    return (4 * F - 1) / 3


def F_of(w):
    return (1 + 3 * w) / 4


def qber(F):

    return 2 * (1 - F) / 3


def key_rate(F):

    q = qber(F)
    if q <= 0:
        return 1.0
    if q >= 0.5:
        return 0.0
    h = -q * math.log2(q) - (1 - q) * math.log2(1 - q)
    return max(0.0, 1 - 2 * h)


def swap_exact(F1, F2):

    return F_of(w_of(F1) * w_of(F2))


def purify_exact(F1, F2):

    a1, a2 = (1 - F1) / 3, (1 - F2) / 3
    p = (F1 + a1) * (F2 + a2) + 4 * a1 * a2
    return (F1 * F2 + a1 * a2) / p, p


def segment(n):

    L = ROUTE_KM / n
    eta = 10 ** (-LOSS_DB_PER_KM * L / 10)
    attempt = L / C_FIBRE_KM_S
    return dict(km=L, eta=eta, attempt_s=attempt, pair_s=attempt / eta)


def _bell(qc, a, b):
    qc.h(a)
    qc.cx(a, b)


def _werner_noise(qc, F, data, a1, a0):

    w = w_of(F)
    pI, pX, pZ = (1 + 3 * w) / 4, (1 - w) / 4, (1 - w) / 4
    qc.ry(2 * math.asin(math.sqrt(2 * pX)), a1)
    qc.x(a1)
    qc.cry(2 * math.asin(math.sqrt(pZ / (pI + pZ))), a1, a0)
    qc.x(a1)
    qc.cry(math.pi / 2, a1, a0)
    qc.cx(a1, data)
    qc.cz(a0, data)


def _bell_readout(qc, a, b):

    qc.cx(a, b)
    qc.h(a)


def swap_circuit(F1, F2):

    qc = QuantumCircuit(8, 2, name="swap")
    _bell(qc, 0, 1)
    _bell(qc, 2, 3)
    _werner_noise(qc, F1, 1, 4, 5)
    _werner_noise(qc, F2, 2, 6, 7)
    qc.barrier()
    qc.cx(1, 2)
    qc.h(1)
    qc.cx(2, 3)
    qc.cz(1, 3)
    qc.barrier()
    _bell_readout(qc, 0, 3)
    qc.measure([0, 3], [0, 1])
    return qc


def purify_circuit(F1, F2):

    qc = QuantumCircuit(8, 4, name="purify")
    _bell(qc, 0, 1)
    _bell(qc, 2, 3)
    _werner_noise(qc, F1, 1, 4, 5)
    _werner_noise(qc, F2, 3, 6, 7)
    qc.barrier()
    qc.cx(0, 2)
    qc.cx(1, 3)
    qc.barrier()
    _bell_readout(qc, 0, 1)
    qc.measure([0, 1, 2, 3], [0, 1, 2, 3])
    return qc


def key_circuit(F):

    qc = QuantumCircuit(8, 4, name="key")
    _bell(qc, 0, 1)
    _bell(qc, 2, 3)
    _werner_noise(qc, F, 1, 4, 5)
    _werner_noise(qc, F, 3, 6, 7)
    qc.barrier()
    qc.h(2)
    qc.h(3)
    qc.measure([0, 1, 2, 3], [0, 1, 2, 3])
    return qc


def bit(key, i):

    if isinstance(key, int):
        return (key >> i) & 1
    key = str(key).replace(" ", "")
    if key.startswith("0x"):
        return (int(key, 16) >> i) & 1
    return 1 if len(key) > i and key[-1 - i] == "1" else 0


def read_swap(counts):
    n = sum(counts.values())
    good = sum(v for k, v in counts.items() if bit(k, 0) == 0 and bit(k, 1) == 0)
    return dict(F=good / n, n=n)


def read_purify(counts):
    n = sum(counts.values())
    kept = {k: v for k, v in counts.items() if bit(k, 2) == bit(k, 3)}
    nk = sum(kept.values())
    good = sum(v for k, v in kept.items() if bit(k, 0) == 0 and bit(k, 1) == 0)
    return dict(F=good / nk if nk else 0.0, p=nk / n, n=n, kept=nk)


def read_key(counts):
    n = sum(counts.values())
    ez = sum(v for k, v in counts.items() if bit(k, 0) != bit(k, 1))
    ex = sum(v for k, v in counts.items() if bit(k, 2) != bit(k, 3))
    return dict(qber_z=ez / n, qber_x=ex / n, n=n)


def _pareto(pts):
    pts = sorted(pts, key=lambda t: (t[1], -t[0]))
    out, best = [], -1.0
    for F, E in pts:
        if F > best + 1e-12:
            out.append((F, E))
            best = F
    return out


def par(n, F0=F0, rounds=6, keep=80):

    def pur_front(pts):
        cur = list(pts)
        for _ in range(rounds):
            new = []
            for F, E in cur:
                Fp, p = purify_exact(F, F)
                new.append((Fp, 2 * E / p))
            cur = _pareto(cur + new)
        return cur[:keep]
    front = {1: pur_front([(F0, 1.0)])}
    for m in range(2, n + 1):
        pts = [(swap_exact(F1, F2), E1 + E2)
               for k in range(1, m) for F1, E1 in front[k] for F2, E2 in front[m - k]]
        front[m] = pur_front(_pareto(pts))
    ok = [(F, E) for F, E in front[n] if qber(F) < QBER_MAX]
    if not ok:
        return None
    F, E = min(ok, key=lambda t: t[1])
    Fk, Ek = max(ok, key=lambda t: key_rate(t[0]) / t[1])


    mfront = {1: pur_front([(F0, 1.0)])}
    for m in range(2, n + 1):
        pts = [(swap_exact(F1, F2), max(M1, M2))
               for k in range(1, m) for F1, M1 in mfront[k] for F2, M2 in mfront[m - k]]
        mfront[m] = pur_front(_pareto(pts))
    okm = [(Fm, M) for Fm, M in mfront[n] if qber(Fm) < QBER_MAX]
    Fr, Mr = max(okm, key=lambda t: key_rate(t[0]) / t[1])
    seg = segment(n)
    return dict(F=F, pairs=E, key_F=Fk, key_pairs=Ek, key_per_pair=key_rate(Fk) / Ek,
                rate_F=Fr, rate_M=Mr, key_per_s=key_rate(Fr) / (Mr * seg["pair_s"]))
