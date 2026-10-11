import base64
import inspect as _inspect
import json
import time

import numpy as np
from qiskit import QuantumCircuit, transpile

from . import qae


def _load_sgra():
    return (np.concatenate((np.load("data/sgra/lum4_sums_0.npy"), np.load("data/sgra/lum4_sums_1.npy")), axis=0),
            np.load("data/sgra/source_variance.npy"))


def _load_charged():
    return (np.concatenate((np.load("data/charged/lum4_sums_0.npy"), np.load("data/charged/lum4_sums_1.npy")), axis=0),
            np.load("data/charged/source_variance.npy"))


def _load_cinematic():
    return (np.concatenate((np.load("data/cinematic/lum4_sums_0.npy"), np.load("data/cinematic/lum4_sums_1.npy")), axis=0),
            np.load("data/cinematic/source_variance.npy"))


LOADERS = {"sgra": _load_sgra, "charged": _load_charged, "cinematic": _load_cinematic}
BLOCK = 64 * 255
KS = [0, 1, 2, 4, 8, 16]
KS_IONQ = [0, 1, 2, 4, 8]
SHOTS = 32
_lum4 = {}


_b64 = {}


def _url(raw, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def _read_sgra():
    return dict(truth=_url(open("data/sgra/truth.png", "rb").read()),
                c=_url(open("data/sgra/c.png", "rb").read()),
                h=_url(open("data/sgra/h.png", "rb").read()),
                q=_url(open("data/sgra/q.png", "rb").read()),
                ec=_url(open("data/sgra/ec.png", "rb").read()),
                eh=_url(open("data/sgra/eh.png", "rb").read()),
                eq=_url(open("data/sgra/eq.png", "rb").read()),
                adv=_url(open("data/sgra/adv.png", "rb").read()),
                curves=json.load(open("data/sgra/curves.json")))


def _read_charged():
    return dict(truth=_url(open("data/charged/truth.png", "rb").read()),
                c=_url(open("data/charged/c.png", "rb").read()),
                h=_url(open("data/charged/h.png", "rb").read()),
                q=_url(open("data/charged/q.png", "rb").read()),
                ec=_url(open("data/charged/ec.png", "rb").read()),
                eh=_url(open("data/charged/eh.png", "rb").read()),
                eq=_url(open("data/charged/eq.png", "rb").read()),
                adv=_url(open("data/charged/adv.png", "rb").read()),
                curves=json.load(open("data/charged/curves.json")))


def _read_cinematic():
    return dict(truth=_url(open("data/cinematic/truth.png", "rb").read()),
                c=_url(open("data/cinematic/c.png", "rb").read()),
                h=_url(open("data/cinematic/h.png", "rb").read()),
                q=_url(open("data/cinematic/q.png", "rb").read()),
                ec=_url(open("data/cinematic/ec.png", "rb").read()),
                eh=_url(open("data/cinematic/eh.png", "rb").read()),
                eq=_url(open("data/cinematic/eq.png", "rb").read()),
                adv=_url(open("data/cinematic/adv.png", "rb").read()),
                curves=json.load(open("data/cinematic/curves.json")))


READERS = {"sgra": _read_sgra, "charged": _read_charged, "cinematic": _read_cinematic}
_files = {}


def _lum(name):

    if name not in _lum4:
        sums, var = LOADERS[name]()
        _lum4[name] = (sums.astype(np.float64) / BLOCK, var.astype(np.float64))
    return _lum4[name]


def load_preset(name):

    if name not in _files:
        _files[name] = READERS[name]()
    if "eht" not in _files:
        _files["eht"] = _url(open("data/eht_sgra.jpg", "rb").read(), "image/jpeg")
    var = _lum(name)[1]
    y, x = np.unravel_index(int(np.argmax(var)), var.shape)
    return json.dumps(dict(_files[name], eht=_files["eht"], default_pixel=[int(x), int(y)]))


def _bit(key, i):

    if isinstance(key, int):
        return (key >> i) & 1
    key = str(key).replace(" ", "")
    if key.startswith("0x"):
        return (int(key, 16) >> i) & 1
    return len(key) > i and key[-1 - i] == "1"


async def _maybe(v):
    return await v if _inspect.isawaitable(v) else v


def _is_ionq(backend):
    return "ionq" in str(getattr(backend, "name", "")).lower()


def _packed(f, ks):

    blocks = qae.mlae_circuits(f, ks)
    w = blocks[0].num_qubits
    out = QuantumCircuit(w * len(ks), len(ks))
    for i, b in enumerate(blocks):
        out.compose(b.remove_final_measurements(inplace=False), qubits=range(i * w, (i + 1) * w), inplace=True)
        out.measure(i * w, i)
    return out


async def inspect(backend, name, x, y):

    t0 = time.perf_counter()
    blocks, svar = _lum(name)
    f = blocks[int(y), int(x)].copy()
    mu = float(f.mean())
    source_var = float(svar[int(y), int(x)])
    ionq = _is_ionq(backend)
    ks = KS_IONQ if ionq else KS
    if ionq:
        f = f.reshape(-1, 2).mean(1)
        circs = [_packed(f, ks)]
    else:
        circs = qae.mlae_circuits(f, ks)
    try:
        tc = transpile(circs, backend=backend, optimization_level=1)
    except Exception:
        tc = transpile(circs, basis_gates=["rz", "sx", "x", "cx"], optimization_level=1)
    t1 = time.perf_counter()
    job = await _maybe(backend.run(tc, shots=SHOTS))
    result = await _maybe(job.result())
    t2 = time.perf_counter()
    if ionq:
        counts = result.get_counts()
        hits = [int(sum(v for k, v in counts.items() if _bit(k, i))) for i in range(len(ks))]
    else:
        hits = [int(sum(v for k, v in result.get_counts(i).items() if _bit(k, 0))) for i in range(len(tc))]
    est = qae.mlae_estimate(ks, hits, SHOTS)
    theta = float(np.arcsin(np.sqrt(mu)))
    ops = tc[-1].count_ops()
    return json.dumps(dict(
        x=int(x), y=int(y), mu=mu, estimate=est, error=abs(est - mu), ks=ks, shots=SHOTS, hits=hits,
        ideal=[float(np.sin((2 * k + 1) * theta) ** 2) for k in ks], queries=qae.queries(ks, SHOTS),
        iid_error=float(np.sqrt(source_var / qae.queries(ks, SHOTS))),
        mlae_rmse=qae.mlae_rmse(mu, ks, SHOTS), mlae_trials=400,
        encoded_iid_error=float(np.sqrt(np.var(f, ddof=0) / qae.queries(ks, SHOTS))),
        exact_classical_mean=mu, encoded_values=int(len(f)), subrays=1024,
        qubits=tc[-1].num_qubits, index_qubits=int(np.log2(len(f))), packed=ionq,
        depth_max=tc[-1].depth(), cx_max=int(ops.get("cx", 0)),
        backend=str(getattr(backend, "name", backend)), t_transpile=t1 - t0, t_run=t2 - t1,
    ))
