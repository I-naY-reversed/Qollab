import asyncio
import json
import os
import sys

from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Statevector

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rr import app, core


def probs(qc, qubits):

    p = Statevector(qc.remove_final_measurements(inplace=False)).probabilities_dict()
    out = {}
    for k, v in p.items():
        bits = k[::-1]
        key = "".join(bits[q] for q in reversed(qubits))
        out[key] = out.get(key, 0.0) + v
    return out


def main():
    cases = [(0.95, 0.95), (0.9, 0.8), (0.7, 0.6), (0.99, 0.6)]
    for F1, F2 in cases:
        m = probs(core.swap_circuit(F1, F2), [0, 3])
        assert abs(m.get("00", 0) - core.swap_exact(F1, F2)) < 1e-9, ("swap", F1, F2)
        m = probs(core.purify_circuit(F1, F2), [0, 1, 2, 3])
        p = sum(v for k, v in m.items() if k[0] == k[1])
        good = sum(v for k, v in m.items() if k[0] == k[1] and k[2:] == "00")
        Fp, pp = core.purify_exact(F1, F2)
        assert abs(p - pp) < 1e-9 and abs(good / p - Fp) < 1e-9, ("purify", F1, F2)
    for F in (0.95, 0.8):
        m = probs(core.key_circuit(F), [0, 1, 2, 3])
        ez = sum(v for k, v in m.items() if k[3] != k[2])
        ex = sum(v for k, v in m.items() if k[1] != k[0])
        assert abs(ez - core.qber(F)) < 1e-9 and abs(ex - core.qber(F)) < 1e-9, ("key", F)
    print("exact: swap, purify and key circuits match Eqs. (2) to (4) to 1e-9")

    b = BasicSimulator()
    for kind, F1, F2, ref in (("swap", 0.95, 0.95, core.swap_exact(0.95, 0.95)),
                              ("purify", 0.9, 0.8, core.purify_exact(0.9, 0.8)[0]),
                              ("key", 0.82, None, core.qber(0.82))):
        r = json.loads(asyncio.run(app.measure(b, kind, F1, F2)))
        got = r.get("F", r.get("qber_z"))
        n = r.get("kept", r["n"])
        sd = (ref * (1 - ref) / n) ** 0.5
        assert abs(got - ref) < 5 * sd, (kind, got, ref, sd)
        print(f"shots: {kind} measured {got:.4f} vs {ref:.4f} (1 sigma {sd:.4f}), {r['seconds']:.2f} s")
    s = json.loads(app.setup())
    for F0, plans in s["plans"].items():
        for n, pl in plans.items():
            best = pl["par"]
            print(f"F0 {F0}, {n} hops: {pl['km']:.0f} km, eta {pl['eta']:.2e}, {pl['pair_s']:.3g} s per pair, "
                  f"best {best['pairs']:.2f} pairs at F {best['F']:.4f}" if best else f"F0 {F0}, {n} hops: no strategy under 11%")

    F = 0.95
    Fw, _ = core.purify_exact(F, F)
    Fw2, _ = core.purify_exact(Fw, Fw)
    A, B, C, D = F, (1 - F) / 3, (1 - F) / 3, (1 - F) / 3
    for _ in range(2):
        p = (A + B) ** 2 + (C + D) ** 2
        A, B, C, D = (A * A + B * B) / p, (2 * A * B) / p, (C * C + D * D) / p, (2 * C * D) / p
    print(f"two rounds at F = {F}: with twirl {Fw2:.4f}, without twirl {A:.4f}")


if __name__ == "__main__":
    main()
