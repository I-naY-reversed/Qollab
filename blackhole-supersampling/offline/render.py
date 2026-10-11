import argparse
import json
import math
import os
import time

import numpy as np
from PIL import Image

from kn import SKY, isco, redshift, trace_screen

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

PRESETS = {
    "sgra": dict(a=0.9, Q=0.0, inc=30.0, label="Sgr A* (EHT-motivated)"),
    "charged": dict(a=0.6, Q=0.7, inc=45.0, label="Charged what-if"),
    "cinematic": dict(a=0.9, Q=0.3, inc=80.0, label="Cinematic"),
}
R0 = 40.0
TAN_HALF = 0.55
R_OUT = 10.0
R_ESC = 1000.0
HFAC = 0.01
MAX_STEPS = 200000
CELL = 8
EXPOSURE = 1.6
SKY_GAIN = 0.6
SKY_TOL = 0.3 * 2 * math.pi / 4096


def screen_xy(gx, gy, n):

    return (gx / n * 2 - 1) * TAN_HALF, (1 - gy / n * 2) * TAN_HALF


def to_vec(th, ph):
    s = np.sin(th)
    return np.stack([s * np.cos(ph), s * np.sin(ph), np.cos(th)], -1)


def from_vec(v):
    v = v / np.linalg.norm(v, axis=-1, keepdims=True)
    return np.arccos(np.clip(v[..., 2], -1, 1)), np.arctan2(v[..., 1], v[..., 0])


BAND_POLE = np.array([0.3, -0.5, 0.81]) / np.linalg.norm([0.3, -0.5, 0.81])


def sky_rotation(inc_deg):

    th0 = math.radians(inc_deg)
    src = -np.array([math.sin(th0), 0.0, math.cos(th0)])
    dst = np.cross(BAND_POLE, [0.0, 0.0, 1.0])
    dst /= np.linalg.norm(dst)
    v, c = np.cross(src, dst), float(src @ dst)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def sample_sky(sky, th, ph, rot=None):

    v = to_vec(th, ph)
    if rot is not None:
        v = v @ rot.T
    th, ph = from_vec(v)
    h, w, _ = sky.shape
    y = th / math.pi * h - 0.5
    x = (ph % (2 * math.pi)) / (2 * math.pi) * w - 0.5
    y0 = np.clip(np.floor(y).astype(int), 0, h - 2)
    x0 = np.floor(x).astype(int)
    fy = np.clip(y - y0, 0, 1)[..., None]
    fx = (x - x0)[..., None]
    x0 %= w
    x1 = (x0 + 1) % w
    return (sky[y0, x0] * (1 - fx) + sky[y0, x1] * fx) * (1 - fy) + (sky[y0 + 1, x0] * (1 - fx) + sky[y0 + 1, x1] * fx) * fy


def blackbody_rgb(kelvin):

    t = np.clip(kelvin, 1000, 40000) / 100
    r = np.where(t <= 66, 255.0, 329.698727446 * np.power(np.maximum(t - 60, 1e-6), -0.1332047592))
    g = np.where(t <= 66, 99.4708025861 * np.log(t) - 161.1195681661, 288.1221695283 * np.power(np.maximum(t - 60, 1e-6), -0.0755148492))
    b = np.where(t >= 66, 255.0, np.where(t <= 19, 0.0, 138.5177312231 * np.log(np.maximum(t - 10, 1e-6)) - 305.0447927307))
    rgb = np.clip(np.stack([r, g, b], -1), 0, 255) / 255
    return rgb ** 2.2


_RNG = np.random.default_rng(11)
_WAVES = [(int(m), float(n), float(ph), float(amp)) for m, n, ph, amp in zip(
    _RNG.integers(1, 14, 24), _RNG.uniform(6, 45, 24), _RNG.uniform(0, 2 * np.pi, 24), _RNG.uniform(0.3, 1.0, 24))]


def disk_texture(r, phi):

    u = np.log(r)
    acc = sum(amp * np.sin(m * phi + n * u + ph) for m, n, ph, amp in _WAVES)
    acc /= np.sqrt(sum(w[3] ** 2 for w in _WAVES) / 2)
    return np.exp(0.3 * acc - 0.5 * 0.3**2)


DISK_T_PEAK = 4300.0


def shade(kind, th, ph, ncr, rcr, pcr, lam, p, sky, r_in):

    out = np.zeros(kind.shape + (3,), np.float32)
    m = kind == SKY
    out[m] = SKY_GAIN * sample_sky(sky, th[m], ph[m], sky_rotation(p["inc"])) ** 1.6
    for j in range(rcr.shape[-1]):
        d = ncr > j
        if not d.any():
            continue
        r, phh, lm = rcr[..., j][d], pcr[..., j][d], lam[d]
        g = redshift(r, lm, p["a"], p["Q"])
        x = r_in / r
        flux = x**3 * np.maximum(1 - np.sqrt(x), 0) / 0.0143
        outer = np.clip((R_OUT - r) / 3.0, 0, 1) ** 2
        bright = 0.28 * flux * g**4 * disk_texture(r, phh) * outer
        out[d] += blackbody_rgb(DISK_T_PEAK * flux**0.25 * g) * bright[:, None]
    return out


def tonemap(rgb):

    x = EXPOSURE * np.maximum(rgb, 0)
    y = (x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14)
    return np.clip(y, 0, 1) ** (1 / 2.2)


def luminance(c):
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]


AXIS_GAP = 3e-4


def trace_xy(x, y, p, r_in):
    x = np.where(np.abs(x) < AXIS_GAP, np.where(x < 0, -AXIS_GAP, AXIS_GAP), x)
    k, th, ph, ncr, rcr, pcr, lam, st, dk = trace_screen(
        x.ravel(), y.ravel(), R0, math.radians(p["inc"]), p["a"], p["Q"], r_in, R_OUT, R_ESC, HFAC, MAX_STEPS)
    return k, th, ph, ncr, rcr, pcr, lam


def _corner_err(f):

    e = np.zeros(f.shape[:2])
    d2x = np.linalg.norm(f[:, 2:] - 2 * f[:, 1:-1] + f[:, :-2], axis=-1)
    d2y = np.linalg.norm(f[2:] - 2 * f[1:-1] + f[:-2], axis=-1)
    e[:, 1:-1] += d2x
    e[1:-1] += d2y
    e[:, 0], e[:, -1], e[0], e[-1] = np.inf, np.inf, np.inf, np.inf
    return e / 8


def _cell_max(e):
    return np.maximum.reduce([e[:-1, :-1], e[:-1, 1:], e[1:, :-1], e[1:, 1:]])


def classify(ck, cncr, cvec, crcr, cpcr):

    from scipy.ndimage import maximum_filter, minimum_filter
    code = ck.astype(np.int32) * 8 + cncr
    same = maximum_filter(code, size=4, mode="nearest") == minimum_filter(code, size=4, mode="nearest")
    same = same[:-1, :-1]
    sky_err = _cell_max(_corner_err(cvec))
    ok = (ck[:-1, :-1] != SKY) | (sky_err < SKY_TOL)
    for j in range(crcr.shape[-1]):
        has = cncr[:-1, :-1] > j
        er = _cell_max(_corner_err(crcr[..., j:j + 1]))
        ep = _cell_max(_corner_err(cpcr[..., j:j + 1]))
        ok &= ~has | ((er < 0.003) & (ep < 0.003))
    return same & ok


def render(name, size, sub, sky, exact=False):
    p = PRESETS[name]
    r_in = isco(p["a"], p["Q"])
    t0 = time.time()
    n_sub = size * sub
    nc = n_sub // CELL
    gi = np.arange(nc + 1) * CELL
    GX, GY = np.meshgrid(gi, gi)
    cx, cy = screen_xy(GX, GY, n_sub)
    ck, cth, cph, cncr, crcr, cpcr, clam = trace_xy(cx, cy, p, r_in)
    shp = (nc + 1, nc + 1)
    ck, cth, cph, cncr, clam = (v.reshape(shp) for v in (ck, cth, cph, cncr, clam))
    crcr, cpcr = crcr.reshape(shp + (-1,)), cpcr.reshape(shp + (-1,))
    cvec = to_vec(cth, cph)
    t_corner = time.time() - t0
    good = classify(ck, cncr, cvec, crcr, cpcr)
    if exact:
        good[:] = False
    ncross = crcr.shape[-1]

    f = (np.arange(CELL) + 0.5) / CELL
    FY, FX = np.meshgrid(f, f, indexing="ij")
    W = [((1 - FX) * (1 - FY)), (FX * (1 - FY)), ((1 - FX) * FY), (FX * FY)]

    rgb = np.zeros((size, size, 3), np.float32)
    lum = np.zeros((size, size, sub * sub), np.uint8)
    cpp = sub // CELL
    n_exact = 0
    band = max(1, 4 // max(1, cpp // 4))
    for py0 in range(0, size, band):
        cy0, cy1 = py0 * cpp, min(size, py0 + band) * cpp
        hb = cy1 - cy0

        def interp(c):
            ex = (Ellipsis,) + (None, None)
            cs = [c[cy0:cy1, :-1], c[cy0:cy1, 1:], c[cy0 + 1:cy1 + 1, :-1], c[cy0 + 1:cy1 + 1, 1:]]
            if c.ndim == 3:
                return sum(ci[:, :, None, None, :] * w[None, None, :, :, None] for ci, w in zip(cs, W))
            return sum(ci[ex] * w[None, None] for ci, w in zip(cs, W))

        K = np.repeat(np.repeat(ck[cy0:cy1, :-1][..., None, None], CELL, 2), CELL, 3)
        NC = np.repeat(np.repeat(cncr[cy0:cy1, :-1][..., None, None], CELL, 2), CELL, 3)
        TH, PH = from_vec(interp(cvec))
        RC, PC, LAM = interp(crcr), interp(cpcr), interp(clam)
        bi, bj = np.nonzero(~good[cy0:cy1])
        if len(bi):
            gx = bj[:, None, None] * CELL + FX[None] * CELL
            gy = (cy0 + bi)[:, None, None] * CELL + FY[None] * CELL
            x, y = screen_xy(gx, gy, n_sub)
            k, th, ph, ncr, rcr, pcr, lam = trace_xy(x, y, p, r_in)
            s3 = (len(bi), CELL, CELL)
            K[bi, bj], TH[bi, bj], PH[bi, bj] = k.reshape(s3), th.reshape(s3), ph.reshape(s3)
            NC[bi, bj], LAM[bi, bj] = ncr.reshape(s3), lam.reshape(s3)
            RC[bi, bj], PC[bi, bj] = rcr.reshape(s3 + (ncross,)), pcr.reshape(s3 + (ncross,))
            n_exact += k.size
        col = tonemap(shade(K, TH, PH, NC, RC, PC, LAM, p, sky, r_in))
        hp = hb // cpp
        col = col.reshape(hp, cpp, size, cpp, CELL, CELL, 3).transpose(0, 2, 1, 4, 3, 5, 6).reshape(hp, size, sub * sub, 3)
        rgb[py0:py0 + hp] = col.mean(2)
        lum[py0:py0 + hp] = np.round(luminance(col) * 255).astype(np.uint8)
    stats = dict(preset=name, **p, r_in=r_in, size=size, sub=sub, corner_rays=int(ck.size),
                 exact_subrays=int(n_exact), total_subrays=int(n_sub * n_sub),
                 good_cell_frac=round(float(good.mean()), 4), t_corner=round(t_corner, 1), t_total=round(time.time() - t0, 1))
    return rgb, lum, stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("presets", nargs="*", default=list(PRESETS))
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--sub", type=int, default=32)
    ap.add_argument("--exact", action="store_true", help="trace every sub-ray (accuracy check)")
    args = ap.parse_args()
    sky = np.load(os.path.join(OUT, "starfield.npy"))
    for name in args.presets:
        rgb, lum, stats = render(name, args.size, args.sub, sky, args.exact)
        d = os.path.join(OUT, name + ("_exact" if args.exact else ""))
        os.makedirs(d, exist_ok=True)
        np.save(os.path.join(d, "rgb.npy"), rgb)
        np.save(os.path.join(d, "lum.npy"), lum)
        Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(d, "truth.png"))
        json.dump(stats, open(os.path.join(d, "stats.json"), "w"), indent=1)
        print(json.dumps(stats))
