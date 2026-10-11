import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from scipy.integrate import solve_ivp
from qiskit.quantum_info import Statevector
from qiskit.providers.basic_provider import BasicSimulator
from ss.core import *

m = MASSES
DESIGNS = [(ki, kb) for kb in K_BAT_SWEEP for ki in K_ISO_SWEEP]


def stiffness_matrix(k):
    K = np.zeros((len(m), len(m)))
    for e in range(len(k)):
        u = np.zeros(len(m)); u[e] = 1
        if PARENT[e] >= 0: u[PARENT[e]] = -1
        K += k[e] * np.outer(u, u)
    return K


def test_factorization():
    k = springs(2e5, 3.5e6); B = B_matrix(m, k); Mi = np.diag(m ** -0.5)
    assert np.allclose(B @ B.T, Mi @ stiffness_matrix(k) @ Mi, rtol=1e-12, atol=1e-6)


def test_energy_vs_newton():
    k = springs(2e5, 3.5e6); K = stiffness_matrix(k); t = np.linspace(0, WINDOW, 7)
    z0 = np.zeros(16); z0[8] = V0
    sol = solve_ivp(lambda _, z: np.r_[z[8:], -(K @ z[:8]) / m], (0, WINDOW), z0, t_eval=t, rtol=1e-11, atol=1e-13)
    x, v = sol.y[:8].T, sol.y[8:].T; E0 = 0.5 * m[0] * V0 ** 2
    ext = np.array([x[:, e] - (x[:, PARENT[e]] if PARENT[e] >= 0 else 0) for e in range(8)]).T
    ref = np.c_[0.5 * m * v ** 2, 0.5 * k * ext ** 2] / E0
    assert np.abs(ref - energy_fractions(m, k, t)).max() < 1e-8


def test_two_level_rotation():
    from qiskit.quantum_info import Operator
    from scipy.linalg import expm
    for a, b in [(5, 8), (9, 12), (1, 14)]:
        X = np.zeros((16, 16)); X[a, b] = X[b, a] = 1
        assert np.allclose(Operator(two_level_rx(4, a, b, 0.3)).data, expm(-0.15j * X))


def test_trotter_accuracy():

    dt = WINDOW / STEPS
    for ki, kb in DESIGNS:
        k = springs(ki, kb); sc = ShockCircuits(m, k, dt)
        for s in range(STEPS // 8, STEPS + 1, STEPS // 8):
            p = to_model_order(Statevector(sc.circuit(s, measure=False)).probabilities())
            pe = energy_fractions(m, k, np.array([s * dt]))[0]
            assert 0.5 * np.abs(p - pe).sum() < 0.01, (ki, kb, s)
            for c, _, _ in COMPONENTS:
                e = spring_fraction(pe, c)
                assert abs(spring_fraction(p, c) - e) < 1.6 * np.sqrt(max(e * (1 - e), 1 / 16384) / 16384), (ki, kb, s, c)


def test_shots():
    k = springs(2e5, 3.5e6); dt = WINDOW / STEPS; sc = ShockCircuits(m, k, dt); shots = 20000
    counts = BasicSimulator().run(sc.circuit(STEPS // 2), shots=shots, seed_simulator=7).result().get_counts()
    p = to_model_order(counts_to_probs(counts)); pe = energy_fractions(m, k, np.array([STEPS // 2 * dt]))[0]
    for c, _, _ in COMPONENTS:
        e = spring_fraction(pe, c)
        assert abs(spring_fraction(p, c) - e) < 4 * np.sqrt(max(e * (1 - e), 1 / shots) / shots) + 1e-4


if __name__ == "__main__":
    for name, f in list(globals().items()):
        if name.startswith("test_"):
            f(); print("ok", name)
