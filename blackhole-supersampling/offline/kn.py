import math

import numpy as np
from numba import njit, prange

SKY, HORIZON, LOST = 0, 2, 3


@njit(cache=True, inline="always")
def _rhs(r, th, pr, pth, a, Q2, L):
    s = math.sin(th)
    if abs(s) < 1e-9:
        s = 1e-9 if s >= 0 else -1e-9
    c = math.cos(th)
    D = r * r - 2.0 * r + a * a + Q2
    Dp = 2.0 * (r - 1.0)
    P = r * r + a * a - a * L
    T = L / s - a * s
    dr = D * pr
    dth = pth
    dph = T / s + a * P / D
    dpr = -0.5 * (Dp * pr * pr - 4.0 * r * P / D + P * P * Dp / (D * D))
    dpth = T * (L * c / (s * s) + a * c)
    return dr, dth, dph, dpr, dpth


@njit(cache=True)
def horizon(a, Q):
    return 1.0 + math.sqrt(max(1.0 - a * a - Q * Q, 0.0))


@njit(cache=True)
def camera_ray(r0, th0, nx, ny, a, Q):

    Q2 = Q * Q
    s, c = math.sin(th0), math.cos(th0)
    Sig = r0 * r0 + a * a * c * c
    D = r0 * r0 - 2.0 * r0 + a * a + Q2
    A = (r0 * r0 + a * a) ** 2 - a * a * D * s * s
    gpp = A * s * s / Sig
    omega = a * (2.0 * r0 - Q2) / A
    lapse = math.sqrt(Sig * D / A)

    n = math.sqrt(1.0 + nx * nx + ny * ny)
    vr, vph, vth = -1.0 / n, nx / n, -ny / n

    mr, mph, mth = -vr, -vph, -vth
    Eloc = 1.0
    L = math.sqrt(gpp) * mph * Eloc
    E = lapse * Eloc + omega * L
    pr = math.sqrt(Sig / D) * mr * Eloc
    pth = math.sqrt(Sig) * mth * Eloc
    return r0, th0, pr / E, pth / E, L / E


NCROSS = 3


@njit(cache=True)
def trace(r, th, pr, pth, L, a, Q, r_in, r_out, r_esc, hfac, max_steps, rc_out, pc_out):

    Q2 = Q * Q
    rh = horizon(a, Q)
    ph = 0.0
    nc = 0
    c0 = math.cos(th)
    s0 = math.sin(th)
    K0 = pth * pth + c0 * c0 * (L * L / (s0 * s0) - a * a)
    for i in range(max_steps):
        dr, dth, dph, dpr, dpth = _rhs(r, th, pr, pth, a, Q2, L)
        s = abs(math.sin(th))
        rate = abs(dr) / max(r - rh, 1e-6) + abs(dth) + abs(dph) * (1.0 if s < 0.1 else s) + abs(dpth) / (abs(pth) + 1.0) + 1e-12
        h = -hfac / rate
        k1 = (dr, dth, dph, dpr, dpth)
        y2 = _rhs(r + 0.5 * h * k1[0], th + 0.5 * h * k1[1], pr + 0.5 * h * k1[3], pth + 0.5 * h * k1[4], a, Q2, L)
        y3 = _rhs(r + 0.5 * h * y2[0], th + 0.5 * h * y2[1], pr + 0.5 * h * y2[3], pth + 0.5 * h * y2[4], a, Q2, L)
        y4 = _rhs(r + h * y3[0], th + h * y3[1], pr + h * y3[3], pth + h * y3[4], a, Q2, L)
        nr = r + h / 6.0 * (k1[0] + 2 * y2[0] + 2 * y3[0] + y4[0])
        nth = th + h / 6.0 * (k1[1] + 2 * y2[1] + 2 * y3[1] + y4[1])
        nph = ph + h / 6.0 * (k1[2] + 2 * y2[2] + 2 * y3[2] + y4[2])
        npr = pr + h / 6.0 * (k1[3] + 2 * y2[3] + 2 * y3[3] + y4[3])
        npth = pth + h / 6.0 * (k1[4] + 2 * y2[4] + 2 * y3[4] + y4[4])
        f0, f1 = math.cos(th), math.cos(nth)
        if f0 * f1 < 0.0 and nc < NCROSS:
            w = f0 / (f0 - f1)
            rc = r + w * (nr - r)
            if r_in <= rc <= r_out:
                rc_out[nc] = rc
                pc_out[nc] = ph + w * (nph - ph)
                nc += 1
        r, th, ph, pr, pth = nr, nth, nph, npr, npth
        if r < rh * 1.01:
            return HORIZON, th, ph, nc, i, 0.0
        if r > r_esc:
            c = math.cos(th)
            sn = math.sin(th)
            K = pth * pth + c * c * (L * L / (sn * sn) - a * a)
            return SKY, th, ph, nc, i, abs(K - K0) / max(abs(K0), 1.0)
    return LOST, th, ph, nc, max_steps, 0.0


@njit(parallel=True, cache=True)
def trace_screen(nx, ny, r0, th0, a, Q, r_in, r_out, r_esc, hfac, max_steps):

    n = nx.size
    kind = np.empty(n, np.int8)
    th_end = np.empty(n)
    ph_end = np.empty(n)
    ncr = np.empty(n, np.int8)
    rcr = np.zeros((n, NCROSS))
    pcr = np.zeros((n, NCROSS))
    lam = np.empty(n)
    steps = np.empty(n, np.int32)
    drift = np.empty(n)
    for i in prange(n):
        r, th, pr, pth, L = camera_ray(r0, th0, nx[i], ny[i], a, Q)
        k, t, p, nc, st, dk = trace(r, th, pr, pth, L, a, Q, r_in, r_out, r_esc, hfac, max_steps, rcr[i], pcr[i])
        kind[i] = k
        th_end[i] = t
        ph_end[i] = p
        ncr[i] = nc
        lam[i] = L
        steps[i] = st
        drift[i] = dk
    return kind, th_end, ph_end, ncr, rcr, pcr, lam, steps, drift


def kepler_omega(r, a, Q):

    w = np.sqrt(np.maximum(r - Q * Q, 0.0))
    return w / (r * r + a * w)


def _eq_metric(r, a, Q):
    q2 = Q * Q
    gtt = -(1 - (2 * r - q2) / (r * r))
    gtp = -a * (2 * r - q2) / (r * r)
    gpp = r * r + a * a + a * a * (2 * r - q2) / (r * r)
    return gtt, gtp, gpp


def redshift(r, lam, a, Q):

    om = kepler_omega(r, a, Q)
    gtt, gtp, gpp = _eq_metric(r, a, Q)
    norm = -(gtt + 2 * gtp * om + gpp * om * om)
    ut = 1 / np.sqrt(np.maximum(norm, 1e-12))
    return 1 / (ut * (1 - om * lam))


def isco(a, Q):

    def energy(r):
        om = kepler_omega(r, a, Q)
        gtt, gtp, gpp = _eq_metric(r, a, Q)
        norm = -(gtt + 2 * gtp * om + gpp * om * om)
        ut = 1 / np.sqrt(norm)
        return -(gtt + gtp * om) * ut

    rh = 1 + np.sqrt(max(1 - a * a - Q * Q, 0))
    r = np.linspace(rh * 1.001, 12, 200001)
    with np.errstate(invalid="ignore", divide="ignore"):
        e = energy(r)
    ok = np.isfinite(e) & (e > 0)
    r, e = r[ok], e[ok]
    return float(r[np.argmin(e)])


def bardeen_shadow(a, Q, inc, n=4000):

    rp = 1 + np.sqrt(1 - a * a - Q * Q)
    r = np.linspace(rp * 1.0001, 6, 400001)
    D = r * r - 2 * r + a * a + Q * Q
    Dp = 2 * (r - 1)
    xi = (r * r + a * a - 4 * r * D / Dp) / a
    eta = 16 * r * r * D / Dp**2 - (xi - a) ** 2
    s = eta + a * a * np.cos(inc) ** 2 - xi * xi / np.tan(inc) ** 2
    ok = s >= 0
    return -xi[ok] / np.sin(inc), np.sqrt(s[ok])
