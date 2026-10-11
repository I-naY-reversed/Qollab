import base64
import inspect as _inspect
import json
import time

from qiskit import transpile

from . import core

SHOTS = 2000


async def _maybe(v):
    return await v if _inspect.isawaitable(v) else v


def _is_ionq(backend):
    return "ionq" in str(getattr(backend, "name", "")).lower()


def setup():

    plans = {}
    for F0 in core.F0_CHOICES:
        plans[str(F0)] = {}
        for n in (1, 2, 4, 8):
            plans[str(F0)][n] = dict(core.segment(n), par=core.par(n, F0))
    return json.dumps(dict(route_km=core.ROUTE_KM, F0=core.F0, F0_choices=list(core.F0_CHOICES), qber_max=core.QBER_MAX,
                           loss_db_km=core.LOSS_DB_PER_KM, plans=plans))


def _webp(raw):
    return "data:image/webp;base64," + base64.b64encode(raw).decode()


def art():

    return json.dumps(dict(
        banner=_webp(open("assets/banner.webp", "rb").read()),
        station=_webp(open("assets/station.webp", "rb").read()),
        photon=_webp(open("assets/photon.webp", "rb").read()),
        purify=_webp(open("assets/purify.webp", "rb").read()),
        emblem=_webp(open("assets/emblem.webp", "rb").read()),
    ))


def exact(kind, F1, F2):

    if kind == "swap":
        return json.dumps(dict(F=core.swap_exact(F1, F2), p=1.0))
    if kind == "purify":
        F, p = core.purify_exact(F1, F2)
        return json.dumps(dict(F=F, p=p))
    raise ValueError(kind)


async def measure(backend, kind, F1, F2=None):

    t0 = time.perf_counter()
    qc = {"swap": lambda: core.swap_circuit(F1, F2),
          "purify": lambda: core.purify_circuit(F1, F2),
          "key": lambda: core.key_circuit(F1)}[kind]()
    drawing = str(qc.draw(output="text", fold=-1))
    try:
        tc = transpile(qc, backend=backend, optimization_level=1)
    except Exception:
        tc = transpile(qc, basis_gates=["rz", "sx", "x", "cx"], optimization_level=1)
    job = await _maybe(backend.run(tc, shots=SHOTS))
    result = await _maybe(job.result())
    counts = result.get_counts()
    out = {"swap": core.read_swap, "purify": core.read_purify, "key": core.read_key}[kind](counts)
    ops = tc.count_ops()
    out.update(kind=kind, shots=SHOTS, qubits=qc.num_qubits, depth=tc.depth(), cx=int(ops.get("cx", 0)),
               backend=str(getattr(backend, "name", backend)), ionq=_is_ionq(backend),
               seconds=time.perf_counter() - t0, drawing=drawing)
    return json.dumps(out)
