import asyncio, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from qiskit.providers.basic_provider import BasicSimulator
from qiskit.quantum_info import Statevector
from hl import app

def exact(theta, beta, mode):
    qc = app.circuit(theta, beta, mode).remove_final_measurements(inplace=False)
    pr = Statevector(qc).probabilities_dict()
    return app.tally({k: v for k, v in pr.items()}, mode)

for th in (math.acos(0.25), math.acos(0.5), math.acos(0.75)):
    for p in (0.5, 0.75, 0.9):
        for beta in (0.0, 0.7, math.pi / 2, 2.0):
            t = exact(th, beta, "min")
            P = p * t[0][0] + (1 - p) * t[1][0]
            assert abs(P - app.p_success(th, p, beta)) < 1e-12, (th, p, beta)
        b = max((i * math.pi / 2000 for i in range(2001)), key=lambda x: app.p_success(th, p, x))
        assert abs(app.p_success(th, p, b) - app.helstrom(th, p)) < 1e-6
    t = exact(th, 0, "usd")
    for s in (0, 1):
        assert abs(t[s][0] - (1 - math.cos(th))) < 1e-12 and t[s][1] < 1e-12 and abs(t[s][2] - math.cos(th)) < 1e-12
r = json.loads(asyncio.run(app.measure(BasicSimulator(), math.acos(0.5), math.pi / 2, "min")))
print("min:", r["tally"], r["cx"], "CX", f'{r["seconds"]:.2f} s')
r = json.loads(asyncio.run(app.measure(BasicSimulator(), math.acos(0.5), 0, "usd")))
print("usd:", r["tally"], r["cx"], "CX", f'{r["seconds"]:.2f} s')
print(r["drawing"])
print("all checks pass")
