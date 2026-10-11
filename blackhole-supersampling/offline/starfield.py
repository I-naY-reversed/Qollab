import os
import sys

import numpy as np
from PIL import Image

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")


def _tint(t):

    stops = np.array([[1.0, 0.55, 0.35], [1.0, 0.85, 0.65], [1.0, 1.0, 1.0], [0.75, 0.85, 1.0]])
    x = np.clip(t, 0, 1) * (len(stops) - 1)
    i = np.minimum(x.astype(int), len(stops) - 2)
    w = (x - i)[:, None]
    return stops[i] * (1 - w) + stops[i + 1] * w


def _noise(shape, rng, octaves=5):

    h, w = shape
    acc = np.zeros(shape)
    for o in range(octaves):
        gh, gw = 4 * 2**o, 8 * 2**o
        g = rng.random((gh + 1, gw + 1))
        g[:, -1] = g[:, 0]
        y = np.linspace(0, gh, h)[:, None]
        x = np.linspace(0, gw, w)[None, :]
        y0, x0 = np.minimum(y.astype(int), gh - 1), np.minimum(x.astype(int), gw - 1)
        fy, fx = y - y0, x - x0
        fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
        v = (g[y0, x0] * (1 - fx) + g[y0, x0 + 1] * fx) * (1 - fy) + (g[y0 + 1, x0] * (1 - fx) + g[y0 + 1, x0 + 1] * fx) * fy
        acc += v / 2**o
    acc -= acc.min()
    return acc / acc.max()


def make(width=4096, n_stars=60000, seed=7):
    h, w = width // 2, width
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w, 3))
    th = (np.arange(h) + 0.5) / h * np.pi
    ph = (np.arange(w) + 0.5) / w * 2 * np.pi
    TH, PH = np.meshgrid(th, ph, indexing="ij")
    xyz = np.stack([np.sin(TH) * np.cos(PH), np.sin(TH) * np.sin(PH), np.cos(TH)], -1)


    pole = np.array([0.3, -0.5, 0.81])
    pole /= np.linalg.norm(pole)
    d = xyz @ pole
    n1, n2 = _noise((h, w), rng), _noise((h, w), rng)
    band = np.exp(-(d / 0.22) ** 2) * (0.35 + 0.65 * n1) * (0.6 + 0.4 * n2)
    dust = np.exp(-(d / 0.06) ** 2) * (n2 > 0.55)
    img += (band * (1 - 0.7 * dust))[..., None] * np.array([0.10, 0.09, 0.075])


    for c in ([0.09, 0.02, 0.05], [0.02, 0.05, 0.09], [0.07, 0.04, 0.01]):
        v = rng.normal(size=3)
        v /= np.linalg.norm(v)
        blob = np.exp(-((1 - xyz @ v) / 0.02)) * _noise((h, w), rng)
        img += blob[..., None] * np.array(c) * 2


    z = rng.uniform(-1, 1, n_stars)
    lon = rng.uniform(0, 2 * np.pi, n_stars)
    sth = np.arccos(z)
    lum = 0.04 * rng.pareto(1.6, n_stars) + 0.02
    lum = np.minimum(lum, 6.0)
    col = _tint(rng.beta(2.5, 2.0, n_stars)) * lum[:, None]
    yc, xc = sth / np.pi * h, lon / (2 * np.pi) * w
    sig = 0.8 + 0.25 * np.log1p(lum * 10)
    rad = 4
    for dy in range(-rad, rad + 1):
        for dx in range(-3 * rad, 3 * rad + 1):
            yi = np.floor(yc).astype(int) + dy
            stretch = 1 / np.maximum(np.sin(np.clip((yi + 0.5) / h * np.pi, 1e-3, np.pi - 1e-3)), 0.25)
            xi = np.floor(xc).astype(int) + dx
            ok = (yi >= 0) & (yi < h)
            ddy = yi + 0.5 - yc
            ddx = (xi + 0.5 - xc) / stretch
            wgt = np.exp(-(ddx**2 + ddy**2) / (2 * sig**2)) / (2 * np.pi * sig**2) * 4
            np.add.at(img, (yi[ok], xi[ok] % w), col[ok] * wgt[ok, None])
    return img.astype(np.float32)


if __name__ == "__main__":
    width = int(sys.argv[1]) if len(sys.argv) > 1 else 4096
    os.makedirs(OUT, exist_ok=True)
    img = make(width)
    np.save(os.path.join(OUT, "starfield.npy"), img)
    disp = 1 - np.exp(-img * 3)
    Image.fromarray((np.clip(disp, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)).save(os.path.join(OUT, "starfield.png"))
    print("saved", img.shape, "max", img.max())
