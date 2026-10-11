import inspect as _inspect
import json
import time

import numpy as np
from qiskit import QuantumCircuit

from . import core

SHOTS = 16384
TIME_POINTS = 8
IONQ_STEPS = 16


async def _maybe(v):
    return await v if _inspect.isawaitable(v) else v


def _is_ionq(backend):
    return "ionq" in str(getattr(backend, "name", "")).lower()


def _dt():
    return core.WINDOW / core.STEPS


def _snap_steps():
    return [core.STEPS * (i + 1) // TIME_POINTS for i in range(TIME_POINTS)]


def _r(a, d=6):
    return [float(round(x, d)) for x in np.ravel(a)]


def _design(i_iso, i_bat):
    return core.springs(core.K_ISO_SWEEP[i_iso], core.K_BAT_SWEEP[i_bat])


def _worst_step(k):

    P = core.energy_fractions(core.MASSES, k, _dt() * np.arange(1, core.STEPS + 1))
    u = np.max([core.accel_g(core.spring_fraction(P, c), k[c], core.MASSES[c]) / lim
                for c, _, lim in core.COMPONENTS], axis=0)
    return int(np.argmax(u)) + 1


def setup():

    m, dt = core.MASSES, _dt()
    t_fine = np.linspace(0, core.WINDOW, 241)
    snaps = [0] + _snap_steps()
    designs = []
    for i_bat in range(len(core.K_BAT_SWEEP)):
        row = []
        for i_iso in range(len(core.K_ISO_SWEEP)):
            k = _design(i_iso, i_bat)
            P = core.energy_fractions(m, k, t_fine)
            comps = []
            for c, _, _ in core.COMPONENTS:
                a = core.accel_g(core.spring_fraction(P, c), k[c], m[c])
                comps.append(dict(a_fine=_r(a, 3), a_peak=float(a.max()), t_peak=float(t_fine[a.argmax()])))
            row.append(dict(k_iso=core.K_ISO_SWEEP[i_iso], k_bat=core.K_BAT_SWEEP[i_bat], k=_r(k),
                            f1=float(core.frequencies(m, k)[0]), comps=comps,
                            snaps=[_r(p) for p in core.energy_fractions(m, k, dt * np.array(snaps))]))
        designs.append(row)
    return json.dumps(dict(
        names=core.NAMES, masses=_r(m), parent=core.PARENT, k_struct=core.K_STRUCT, k_board=core.K_BOARD,
        components=[dict(index=c, name=n, allow=lim) for c, n, lim in core.COMPONENTS],
        k_iso=core.K_ISO_SWEEP, k_bat=core.K_BAT_SWEEP, f_min=core.F_MIN, window=core.WINDOW, steps=core.STEPS,
        dt=dt, v0=core.V0, e0=0.5 * m[0] * core.V0 ** 2, g0=core.G0, qubits=core.N_QUBITS, shots=SHOTS,
        snap_steps=snaps, t_fine=_r(t_fine, 9), designs=designs))


def _step_drawing():

    n = core.N_QUBITS

    def blk(name):
        return QuantumCircuit(n, name=name).to_gate()

    inc = core.incrementer(n)
    qc = QuantumCircuit(n)
    qc.x(0)
    qc.barrier()
    qc.append(blk("E(dt/2)"), range(n))
    qc.append(blk("R(dt/2)"), range(n))
    qc.append(inc.inverse().to_gate(label="-1"), range(n))
    qc.append(blk("C(dt)"), range(n))
    qc.append(inc.to_gate(label="+1"), range(n))
    qc.append(blk("R(dt/2)"), range(n))
    qc.append(blk("E(dt/2)"), range(n))
    qc.measure_all()
    return str(qc.draw(output="text", fold=-1))


async def measure(backend, i_iso, i_bat):

    t0 = time.perf_counter()
    m, dt = core.MASSES, _dt()
    k = _design(int(i_iso), int(i_bat))
    ionq = _is_ionq(backend)
    if ionq:
        s = _worst_step(k)
        circuits = [core.ShockCircuits(m, k, s * dt / IONQ_STEPS).circuit(IONQ_STEPS)]
        steps = [s]
    else:
        sc = core.ShockCircuits(m, k, dt)
        steps = _snap_steps()
        circuits = [sc.circuit(s) for s in steps]
    job = await _maybe(backend.run(circuits if len(circuits) > 1 else circuits[0], shots=SHOTS))
    result = await _maybe(job.result())
    out = []
    for c, s in enumerate(steps):
        counts = result.get_counts(c) if len(circuits) > 1 else result.get_counts()
        out.append(dict(step=s, p=_r(core.to_model_order(core.counts_to_probs(counts)))))
    ops = [qc.count_ops() for qc in circuits]
    return json.dumps(dict(
        results=out, shots=SHOTS, qubits=core.N_QUBITS, circuits=len(circuits),
        cx_max=int(max(o.get("cx", 0) for o in ops)), depth_max=int(max(qc.depth() for qc in circuits)),
        backend=str(getattr(backend, "name", backend)), ionq=ionq, steps=IONQ_STEPS if ionq else core.STEPS,
        seconds=time.perf_counter() - t0, drawing=_step_drawing()))
