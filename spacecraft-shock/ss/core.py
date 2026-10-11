import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import UCRXGate


NAMES = ["sep. ring", "lower frame", "power deck", "battery", "upper frame", "avionics board", "isolator plate", "instrument"]
MASSES = np.array([2.0, 3.0, 4.0, 3.0, 5.0, 1.0, 3.0, 3.0])
PARENT = [-1, 0, 1, 2, 2, 4, 4, 6]
ISO, BAT, BOARD = 7, 3, 5
COMPONENTS = [(BAT, "battery", 50.0), (BOARD, "avionics board", 200.0), (ISO, "instrument", 20.0)]
N_QUBITS = 4

F_MIN = 40.0
K_STRUCT = 3.5e7
K_BOARD = 1.0e7
K_ISO_SWEEP = [3.5e7, 3.5e6, 1.0e6, 4.0e5, 2.0e5]
K_BAT_SWEEP = [3.5e7, 3.5e6, 1.0e6]
WINDOW = 3.7e-3
STEPS = 128


V0 = 1000 * 9.80665 / (2 * np.pi * 1000)


def springs(k_iso, k_bat=K_STRUCT):
    k = np.full(len(MASSES), K_STRUCT)
    k[BOARD], k[ISO], k[BAT] = K_BOARD, k_iso, k_bat
    return k


def B_matrix(m, k):

    N, E = len(m), len(k)
    B = np.zeros((N, E))
    for e in range(E):
        B[e, e] += np.sqrt(k[e] / m[e])
        if PARENT[e] >= 0:
            B[PARENT[e], e] -= np.sqrt(k[e] / m[PARENT[e]])
    return B


def hamiltonian(m, k):

    B = B_matrix(m, k)
    N, E = B.shape
    H = np.zeros((N + E, N + E))
    H[:N, N:] = -B
    H[N:, :N] = -B.T
    return H


def frequencies(m, k):

    w2 = np.linalg.eigvalsh(B_matrix(m, k) @ B_matrix(m, k).T)
    return np.sqrt(np.clip(w2, 0, None)) / (2 * np.pi)


def energy_fractions(m, k, times, j0=0):

    H = hamiltonian(m, k)
    w, V = np.linalg.eigh(H)
    p0 = np.zeros(len(H))
    p0[j0] = 1.0
    c = V.T @ p0
    amps = (V[None, :, :] * np.exp(-1j * np.outer(times, w))[:, None, :]) @ c
    return np.abs(amps) ** 2


def spring_fraction(P, e):

    return P[..., len(MASSES) + e]


def isolator_fraction(P):
    return spring_fraction(P, ISO)


G0 = 9.80665


def accel_g(p, k_e, m_c, e0=None):

    e0 = 0.5 * MASSES[0] * V0 ** 2 if e0 is None else e0
    return np.sqrt(2 * k_e * np.asarray(p) * e0) / m_c / G0


def instrument_accel_g(p_iso, k_iso, e0=None):
    return accel_g(p_iso, k_iso, MASSES[ISO], e0)


def to_model_order(p_path):

    p = np.asarray(p_path)
    return np.r_[p[1::2], p[0::2]]


def incrementer(n):
    qc = QuantumCircuit(n, name="+1")
    for t in range(n - 1, 0, -1):
        qc.mcx(list(range(t)), t)
    qc.x(0)
    return qc


def bond_angles(m, k):

    N = len(m)
    even = np.array([-2 * np.sqrt(k[e] / m[e]) for e in range(N)])
    chain = np.zeros(N)
    branch = []
    for e in range(1, N):
        w = 2 * np.sqrt(k[e] / m[PARENT[e]])
        if PARENT[e] == e - 1:
            chain[e - 1] = w
        else:
            branch.append((2 * PARENT[e] + 1, 2 * e, w))
    return even, chain, branch


def two_level_rx(n, a, b, theta):

    diff = [q for q in range(n) if (a ^ b) >> q & 1]
    d = diff[0]
    ctrl = [q for q in range(n) if q != d]
    ref = a if not (a >> d & 1) else b
    angles = [0.0] * 2 ** len(ctrl)
    angles[sum((ref >> q & 1) << i for i, q in enumerate(ctrl))] = theta
    qc = QuantumCircuit(n, name="R")
    for j in diff[1:]:
        qc.cx(d, j)
    qc.append(UCRXGate(angles), [d] + ctrl)
    for j in reversed(diff[1:]):
        qc.cx(d, j)
    return qc


class ShockCircuits:


    def __init__(self, m, k, dt):
        n = N_QUBITS
        even, chain, branch = bond_angles(m, k)
        inc = incrementer(n)

        def even_block(h):
            qc = QuantumCircuit(n)
            qc.append(UCRXGate(list(even * h)), range(n))
            return qc

        odd = QuantumCircuit(n)
        for part, h in (("R", dt / 2), ("C", dt), ("R", dt / 2)):
            if part == "C":
                odd.compose(inc.inverse(), inplace=True)
                odd.append(UCRXGate(list(chain * h)), range(n))
                odd.compose(inc, inplace=True)
            else:
                for a, b, w in branch:
                    odd.compose(two_level_rx(n, a, b, w * h), inplace=True)
        prep = QuantumCircuit(n)
        prep.x(0)

        opts = dict(basis_gates=["rz", "sx", "x", "cx"], optimization_level=1, num_processes=1)
        self.prep, self.half, self.full, self.odd = transpile(
            [prep, even_block(dt / 2), even_block(dt), odd], **opts)
        self.n, self.dt = n, dt

    def circuit(self, steps, measure=True):
        qc = QuantumCircuit(self.n)
        qc.compose(self.prep, inplace=True)
        if steps > 0:
            qc.compose(self.half, inplace=True)
            for s in range(steps):
                qc.compose(self.odd, inplace=True)
                qc.compose(self.full if s < steps - 1 else self.half, inplace=True)
        if measure:
            qc.measure_all()
        return qc


def counts_to_probs(counts, n=N_QUBITS):

    p = np.zeros(2 ** n)
    for key, c in counts.items():
        p[int(key.replace(" ", ""), 2)] += c
    return p / p.sum()
