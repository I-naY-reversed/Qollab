import math

import numpy as np

from kn import HORIZON, SKY, bardeen_shadow, isco, trace_screen

HF, MAXS = 0.01, 200000


def captured(nx, ny, r0, th0, a, Q):
    k = trace_screen(np.array([nx]), np.array([ny]), r0, th0, a, Q, 1e9, 1e9, max(2 * r0, 1000.0), HF, MAXS)[0]
    return k[0] == HORIZON


def edge(dirx, diry, r0, th0, a, Q, hi):

    lo = 0.0
    for _ in range(40):
        m = 0.5 * (lo + hi)
        if captured(m * dirx, m * diry, r0, th0, a, Q):
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def test_synge():
    for r0 in (10.0, 40.0, 1000.0):
        t = edge(1, 0, r0, math.pi / 2, 0.0, 0.0, 2.0)
        want = math.asin(3 * math.sqrt(3) * math.sqrt(1 - 2 / r0) / r0)
        print(f"Schwarzschild r0={r0}: shadow angle {math.atan(t):.6f} vs Synge {want:.6f}")
        assert abs(math.atan(t) - want) < 1e-4 * max(1, want * 10)


def test_bardeen():
    r0 = 1e4
    for a, Q, inc in ((0.94, 0.0, math.pi / 2), (0.6, 0.7, math.radians(45)), (0.9, 0.3, math.radians(80)), (0.9, 0.0, math.radians(30))):
        al, be = bardeen_shadow(a, Q, inc)
        worst = 0
        for ang in np.linspace(0, 2 * np.pi, 16, endpoint=False):
            dx, dy = math.cos(ang), math.sin(ang)
            t = edge(dx, dy, r0, inc, a, Q, 20 / r0) * r0

            pts = np.concatenate([np.stack([al, be], 1), np.stack([al, -be], 1)])
            ang_pts = np.arctan2(pts[:, 1], pts[:, 0])
            j = np.argmin(np.abs(np.angle(np.exp(1j * (ang_pts - ang)))))
            worst = max(worst, abs(t - np.hypot(*pts[j])))
        print(f"a={a} Q={Q} i={math.degrees(inc):.0f}: max |traced - analytic| = {worst:.4f} M")
        assert worst < 0.05


def test_isco():
    for a, Q, want in ((0.0, 0.0, 6.0), (0.94, 0.0, 2.0236), (0.9, 0.0, 2.3209)):
        got = isco(a, Q)
        print(f"ISCO a={a} Q={Q}: {got:.4f} (want {want})")
        assert abs(got - want) < 2e-3
    print(f"ISCO a=0.6 Q=0.7: {isco(0.6, 0.7):.4f}; a=0.9 Q=0.3: {isco(0.9, 0.3):.4f}")


def test_carter():
    n = np.linspace(-0.3, 0.3, 25)
    nx, ny = np.meshgrid(n, n)
    out = trace_screen(nx.ravel(), ny.ravel(), 40.0, math.radians(60), 0.9, 0.3, 1e9, 1e9, 1000.0, HF, MAXS)
    kind, drift = out[0], out[8]
    m = kind == SKY
    print(f"Carter constant drift (sky rays): max {drift[m].max():.2e}, median {np.median(drift[m]):.2e}")
    assert drift[m].max() < 1e-4


if __name__ == "__main__":
    test_isco()
    test_synge()
    test_carter()
    test_bardeen()
    print("all passed")
