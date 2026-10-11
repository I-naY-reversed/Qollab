import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
DATA = os.path.join(HERE, "..", "data")
KS = [0, 1, 2, 4, 8, 16, 32, 64, 128]
SHOTS = 32
G_COARSE = np.linspace(0, np.pi / 2, 4001)
SEED = 2026
RHO_C = 300.0
PILOT = 32
CHECK = 4.0
USE_PRIOR = False
SEEDS = [2026, 2027, 2028]


def budgets():
    return [SHOTS * sum(2 * k + 1 for k in KS[:m]) for m in range(1, len(KS) + 1)]


def mlae_batch(hits, m, shots=None, prior=None):

    ks = np.array(KS[:m])
    sh = np.full(m, SHOTS, dtype=np.float32) if shots is None else np.asarray(shots, dtype=np.float32)[:m]
    h = hits[:, :m].astype(np.float32)

    def tables(g):
        p = np.clip(np.sin(np.outer(2 * ks + 1, g)) ** 2, 1e-9, 1 - 1e-9)
        return np.log(p).astype(np.float32), np.log1p(-p).astype(np.float32)

    l1, l0 = tables(G_COARSE)
    ll = h @ l1 + (sh[None, :] - h) @ l0
    if prior is not None:
        pm, ps = (np.asarray(x, dtype=np.float32)[:, None] for x in prior)
        ll = ll - 0.5 * ((np.sin(G_COARSE).astype(np.float32)[None] ** 2 - pm) / ps) ** 2
    j = np.argmax(ll, 1)
    step = G_COARSE[1]
    off = np.linspace(-1.5 * step, 1.5 * step, 61)
    g = np.clip(G_COARSE[j][:, None] + off[None], 0, np.pi / 2)
    p = np.clip(np.sin((2 * ks + 1)[None, :, None] * g[:, None, :]) ** 2, 1e-12, 1 - 1e-12)
    ll2 = (h[:, :, None] * np.log(p) + (sh[None, :, None] - h[:, :, None]) * np.log1p(-p)).sum(1)
    if prior is not None:
        ll2 = ll2 - 0.5 * ((np.sin(g) ** 2 - pm) / ps) ** 2
    return np.sin(g[np.arange(len(g)), np.argmax(ll2, 1)]) ** 2


def simulate(lum, rng, chunk=4096):

    n, S = lum.shape
    mu = lum.mean(1, dtype=np.float64)
    B = budgets()
    P = len(B)
    mc = np.zeros((P, n))
    fin = np.zeros((P, n))
    total = np.zeros(n)
    pilot_rho = np.zeros(n)
    pilot_mean = np.zeros(n)
    pilot_var = np.zeros(n)
    uniform = np.full(S, 1.0 / S)
    for c in range(0, n, chunk):
        L = lum[c:c + chunk].astype(np.float64)
        m = len(L)

        cs = np.cumsum(rng.permuted(L, axis=1), axis=1)
        for i, b in enumerate(B):
            r = min(b, S)
            fin[i, c:c + m] = cs[:, r - 1] / r

        tot, prev = np.zeros(m), 0
        for i, b in enumerate(B):
            inc = b - prev
            if inc <= 600:
                draws = np.take_along_axis(L, rng.integers(0, S, size=(m, inc)), 1)
                if i == 0:
                    pm = draws.mean(1)
                    pv = draws.var(1, ddof=1)
                    pilot_rho[c:c + m] = pv / np.maximum(pm * (1 - pm), 1e-4)
                    pilot_mean[c:c + m], pilot_var[c:c + m] = pm, pv
                tot += draws.sum(1)
            else:
                tot += (rng.multinomial(inc, uniform, size=m) * L).sum(1)
            prev = b
            mc[i, c:c + m] = tot / b
    theta = np.arcsin(np.sqrt(np.clip(mu, 0, 1)))
    hits = np.stack([rng.binomial(SHOTS, np.sin((2 * k + 1) * theta) ** 2) for k in KS], 1)
    qae = np.zeros((P, n))
    for mm in range(1, len(KS) + 1):
        for c in range(0, n, 8192):
            qae[mm - 1, c:c + 8192] = mlae_batch(hits[c:c + 8192], mm)


    hyb = mc.copy()
    use_q = np.zeros(P)
    rejected = np.zeros(P)
    hyb_queries = [B[0]]

    pilot_se = np.sqrt(np.maximum(pilot_mean * (1 - pilot_mean), 1.0 / PILOT) / PILOT)
    for i in range(1, P):
        k_new = KS[i]
        extra = (B[i] - PILOT - B[i - 1]) // (2 * k_new + 1)
        shots = [SHOTS] * i + [extra]
        hyb_queries.append(PILOT + B[i - 1] + extra * (2 * k_new + 1))
        h_i = np.concatenate([hits[:, :i], rng.binomial(extra, np.sin((2 * k_new + 1) * theta) ** 2)[:, None]], 1)
        est = np.zeros(n)
        for c in range(0, n, 8192):
            est[c:c + 8192] = mlae_batch(h_i[c:c + 8192], i + 1, shots, (pilot_mean[c:c + 8192], pilot_se[c:c + 8192]) if USE_PRIOR else None)
        flag = pilot_rho > RHO_C / B[i]
        ok = np.abs(est - pilot_mean) <= CHECK * pilot_se
        hyb[i] = np.where(flag & ok, est, mc[i])
        use_q[i] = (flag & ok).mean()
        rejected[i] = (flag & ~ok).mean()
    return dict(mu=mu, mc=mc, fin=fin, qae=qae, hyb=hyb, use_q=use_q, rejected=rejected, hyb_queries=hyb_queries)


def colorize(est, mu, rgb):

    ratio = np.where(mu > 1e-3, est / np.maximum(mu, 1e-3), 0)[:, None]
    col = np.where(mu[:, None] > 1e-3, rgb * ratio, est[:, None])
    return np.clip(col, 0, 1)


def post(img):

    from scipy.ndimage import gaussian_filter
    hi = np.clip(img - 0.55, 0, None)
    glow = 0.6 * gaussian_filter(hi, (2, 2, 0)) + 0.5 * gaussian_filter(hi, (8, 8, 0))
    h, w, _ = img.shape
    yy, xx = np.mgrid[0:h, 0:w]
    rr = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2))
    vig = 1 - 0.18 * np.clip(rr - 0.55, 0, None) ** 2
    out = 1 - (1 - np.clip(img, 0, 1)) * (1 - np.clip(glow, 0, 1))
    return np.clip(out * vig[..., None], 0, 1)


def save_png(a, h, w, path):
    Image.fromarray((post(a.reshape(h, w, 3)) * 255 + 0.5).astype(np.uint8)).save(path, optimize=True)


ERR_LOG_RANGE = (-5.0, -1.0)


def error_rgb(err):

    from matplotlib import colormaps
    lo, hi = ERR_LOG_RANGE
    t = (np.log10(np.maximum(err, 10.0**lo)) - lo) / (hi - lo)
    return colormaps["magma"](np.clip(t, 0, 1))[..., :3]


def save_error_strip(ests, mu, h, w, path):

    from matplotlib import colormaps
    lo, hi = ERR_LOG_RANGE
    idx = [np.round(255 * np.clip((np.log10(np.maximum(np.abs(e - mu), 10.0**lo)) - lo) / (hi - lo), 0, 1)).reshape(h, w) for e in ests]
    im = Image.fromarray(np.concatenate(idx, 1).astype(np.uint8), mode="P")
    pal = (colormaps["magma"](np.linspace(0, 1, 256))[:, :3] * 255 + 0.5).astype(np.uint8)
    im.putpalette(pal.ravel().tolist())
    im.save(path, optimize=True)


def save_strip(frames, h, w, path):

    strip = np.concatenate([post(f.reshape(h, w, 3)) for f in frames], 1)
    Image.fromarray((strip * 255 + 0.5).astype(np.uint8)).save(path, optimize=True)


def crossover_index(mu, var):

    B = np.array(budgets(), dtype=np.float64)
    F = np.cumsum([SHOTS * (2 * k + 1) ** 2 for k in KS]).astype(np.float64)
    win = np.sqrt(var[:, None] / B[None]) > np.sqrt(mu[:, None] * (1 - mu[:, None]) / F[None])
    return np.where(win.any(1), win.argmax(1), -1)


ADV_RAMP = np.array([[0xee, 0xf3, 0xff], [0x7a, 0xa2, 0xf7], [0x00, 0x33, 0xa0]], dtype=np.float64) / 255


def save_advantage(idx, rgbf, h, w, path):

    gray = np.clip(rgbf @ np.array([0.2126, 0.7152, 0.0722]), 0, 1)
    img = np.repeat((0.3 * gray)[:, None], 3, 1)
    t = np.clip(idx / (len(KS) - 1), 0, 1)[:, None] * (len(ADV_RAMP) - 1)
    lo = np.floor(t).astype(int).clip(0, len(ADV_RAMP) - 2)
    col = ADV_RAMP[lo[:, 0]] + (t - lo) * (ADV_RAMP[lo[:, 0] + 1] - ADV_RAMP[lo[:, 0]])
    img = np.where((idx >= 0)[:, None], col, img)
    Image.fromarray((img.reshape(h, w, 3) * 255 + 0.5).astype(np.uint8)).save(path, optimize=True)


def rmse(est, mu, mask=None):
    m = slice(None) if mask is None else mask
    return [float(np.sqrt(np.mean((e[m] - mu[m]) ** 2))) for e in est]


def run(name):
    src = os.path.join(OUT, name)
    rgb = np.load(os.path.join(src, "rgb.npy"))
    lum8 = np.load(os.path.join(src, "lum.npy"))
    h, w, S = lum8.shape
    sub = int(round(np.sqrt(S)))
    lum = lum8.reshape(h * w, S).astype(np.float32) / 255
    runs = [simulate(lum, np.random.default_rng(seed)) for seed in SEEDS]
    r0 = runs[0]
    mu = r0["mu"]
    var = lum.var(1, dtype=np.float64)
    rgbf = rgb.reshape(h * w, 3).astype(np.float64)
    d = os.path.join(DATA, name)
    os.makedirs(d, exist_ok=True)
    save_png(np.clip(rgbf, 0, 1), h, w, os.path.join(d, "truth.png"))
    for tag, est in (("c", r0["mc"]), ("h", r0["hyb"]), ("q", r0["qae"])):
        save_strip([colorize(e, mu, rgbf) for e in est], h, w, os.path.join(d, f"{tag}.png"))
        save_error_strip(est, mu, h, w, os.path.join(d, f"e{tag}.png"))


    blk = lum8.reshape(h, w, 4, sub // 4, 4, sub // 4).astype(np.uint32).sum((3, 5)).reshape(h, w, 16).astype(np.uint16)
    np.save(os.path.join(d, "lum4_sums_0.npy"), blk[: h // 2])
    np.save(os.path.join(d, "lum4_sums_1.npy"), blk[h // 2:])
    np.save(os.path.join(d, "source_variance.npy"), var.reshape(h, w).astype(np.float32))
    old = os.path.join(d, "lum4.npy")
    if os.path.exists(old):
        os.remove(old)
    adv = crossover_index(mu, var)
    save_advantage(adv, rgbf, h, w, os.path.join(d, "adv.png"))
    stats = json.load(open(os.path.join(src, "stats.json")))
    edge = var / np.maximum(mu * (1 - mu), 1e-6) > 0.05
    B = budgets()
    ratios = [1 - rmse([r["hyb"][-1]], mu)[0] / rmse([r["mc"][-1]], mu)[0] for r in runs]
    edge_ratios = [rmse([r["mc"][-1]], mu, edge)[0] / rmse([r["qae"][-1]], mu, edge)[0] for r in runs]
    curves = dict(
        preset=name, label=stats["label"], a=stats["a"], Q=stats["Q"], inc=stats["inc"], r_in=stats["r_in"],
        ks=KS, shots=SHOTS, queries=B, hybrid_queries=r0["hyb_queries"], pilot=PILOT, rho_c=RHO_C, subrays=S,
        rmse_mc=rmse(r0["mc"], mu), rmse_mc_expected=[float(np.sqrt(var.mean() / b)) for b in B],
        rmse_finite=rmse(r0["fin"], mu), rmse_qae=rmse(r0["qae"], mu), rmse_hybrid=rmse(r0["hyb"], mu),
        rmse_mc_edge=rmse(r0["mc"], mu, edge), rmse_qae_edge=rmse(r0["qae"], mu, edge), rmse_finite_edge=rmse(r0["fin"], mu, edge),
        edge_frac=float(edge.mean()), quantum_pixel_frac=[float(x) for x in r0["use_q"]], check_rejected_frac=[float(x) for x in r0["rejected"]], check_sigma=CHECK, err_log_range=list(ERR_LOG_RANGE),
        advantage_frac=[float((adv == m).mean()) for m in range(len(KS))], advantage_any=float((adv >= 0).mean()),
        seeds=SEEDS, hybrid_gain_last=[float(x) for x in ratios], edge_qae_factor_last=[float(x) for x in edge_ratios],
        render=dict(size=h, subrays=S, interpolated_cells=stats["good_cell_frac"], exact_subrays=stats["exact_subrays"]),
    )
    json.dump(curves, open(os.path.join(d, "curves.json"), "w"), indent=1)
    print(name, "queries", B, "hybrid queries", r0["hyb_queries"])
    for key in ("rmse_mc", "rmse_mc_expected", "rmse_finite", "rmse_hybrid", "rmse_qae", "rmse_mc_edge", "rmse_qae_edge", "quantum_pixel_frac"):
        print(f"  {key:18s}", " ".join(f"{x:.1e}" for x in curves[key]))
    print("  check rejected", [f"{x:.1e}" for x in r0["rejected"]], " advantage any", f"{(adv >= 0).mean():.3f}")
    print("  hybrid gain at last pass per seed", [f"{x:.3f}" for x in ratios], " edge MC/QAE per seed", [f"{x:.2f}" for x in edge_ratios])


if __name__ == "__main__":
    for name in sys.argv[1:] or ["sgra", "charged", "cinematic"]:
        run(name)
