import argparse
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rr import core

QMAX = core.QBER_MAX
HOPS = (1, 2, 4, 8)


def h2(q):
    return 0.0 if q <= 0 or q >= 1 else -q * math.log2(q) - (1 - q) * math.log2(1 - q)


def key_bits(F):
    return max(0.0, 1 - 2 * h2(core.qber(F)))


def dur(s):
    if s < 1:
        return f"{s * 1000:.0f} ms"
    if s < 120:
        return f"{s:.1f} s"
    if s < 7200:
        return f"{s / 60:.1f} min"
    if s < 172800:
        return f"{s / 3600:.1f} h"
    if s < 6.3e7:
        return f"{s / 86400:.0f} days"
    return f"{s / 3.156e7:.1f} years"


WORDS = {
    "full": dict(
        intro=("Toronto and Montreal want a secret key over 540 km of fibre, made from shared entangled pairs. "
               "Fibre loses 0.2 dB per km, so across the whole route only about one photon in 60 billion arrives, "
               "and a quantum signal cannot be amplified. Repeater stations fix the rate, but every hop adds noise. "
               "Build the link with swaps and purification until the error rate (QBER) drops below 11%, "
               "then make the key as fast as you can (score = secret bits per second).\n"
               "Try it: 1. Pick how many hops (1, 2, 4 or 8). 2. SWAP at a station to join two links; PURIFY a link "
               "to trade two noisy copies for one better one. 3. When one link spans the route with QBER under 11%, "
               "run TEST. Then try to reach the best known key rate."),
        swap="swap", purify="purify", link="link", F="fidelity F", q="QBER",
        commands="Commands: swap N (join link N and N+1) | purify N | test | undo | reset | hops 1/2/4/8 | f0 0.9/0.95/0.99 | look",
        above="Above 11%. Each swap multiplied the noise. Is there a move that makes a link better? Undo and look.",
        below="Below 11%: a secret key is possible. Run TEST.",
        show_F=True),
    "blind": dict(
        intro=("Connect city A to city B with one link whose error rate is below 11%, using as few resources as you "
               "can. The route can be split into 1, 2, 4 or 8 segments.\n"
               "Moves: JOIN two neighbouring links into one longer link, or REFINE a link. Then run TEST."),
        swap="join", purify="refine", link="link", F=None, q="error rate",
        commands="Commands: join N (join link N and N+1) | refine N | test | undo | reset | hops 1/2/4/8 | f0 0.9/0.95/0.99 | look",
        above="Error rate above 11%: the test would fail.",
        below="Error rate below 11%. Run TEST.",
        show_F=False),
}


def fresh(n, F0):
    return [dict(a=i, b=i + 1, F=F0, E=1.0, D=[1.0]) for i in range(n)]


def load(path):
    with open(path) as f:
        return json.load(f)


def save(path, st):
    with open(path, "w") as f:
        json.dump(st, f)


def log(st, event):
    st["log"].append(event)


def name(st, i):
    if i == 0:
        return "Toronto" if st["mode"] == "full" else "A"
    if i == st["n"]:
        return "Montreal" if st["mode"] == "full" else "B"
    return f"R{i}" if st["mode"] == "full" else f"S{i}"


def screen(st, msg=""):
    W = WORDS[st["mode"]]
    seg = core.segment(st["n"])
    plan = core.par(st["n"], st["F0"])
    out = []
    if st.get("show_intro", True):
        out.append(W["intro"])
        st["show_intro"] = False
    out.append(f"\nRoute: {st['n']} hops of {seg['km']:.0f} km. Per-hop success probability {seg['eta']:.1e}, "
               f"time per elementary pair {dur(seg['pair_s'])}. Fresh pairs: {'F0 = ' + format(st['F0'], '.2f') if W['show_F'] else 'quality setting ' + format(st['F0'], '.2f')}.")
    for i, l in enumerate(st["links"]):
        q = core.qber(l["F"])
        km = (l["b"] - l["a"]) * seg["km"]
        fpart = f"F {l['F']:.3f}, " if W["show_F"] else ""
        out.append(f"  link {i}: {name(st, l['a'])} - {name(st, l['b'])}, {km:.0f} km, {fpart}{W['q']} {100 * q:.1f}%")
        if i < len(st["links"]) - 1:
            n2 = st["links"][i + 1]
            Fs = core.swap_exact(l["F"], n2["F"])
            prev = f"F {Fs:.3f}" if W["show_F"] else f"{W['q']} {100 * core.qber(Fs):.1f}%"
            out.append(f"     station {name(st, l['b'])}: {W['swap']} {i} here would give {prev}")
    pairs = sum(l["E"] for l in st["links"])
    out.append(f"Elementary pairs used: {pairs:.2f}" + (f" (fewest that reach 11%: {plan['pairs']:.2f})" if plan else ""))
    if len(st["links"]) == 1:
        F = st["links"][0]["F"]
        q = core.qber(F)
        slow = max(d for l in st["links"] for d in l["D"])
        bits = key_bits(F) / (slow * seg["pair_s"])
        def kps(n):
            pr = core.par(n, st["F0"])
            return pr["key_per_s"] if pr else 0.0
        best_n = max((1, 2, 4, 8), key=kps)
        out.append(f"End-to-end {W['q']}: {100 * q:.1f}% ({'below' if q < QMAX else 'ABOVE'} 11%). "
                   f"{'Secret key rate' if W['show_F'] else 'Score'}: {bits:.4g} bits/s (best known at this spacing {kps(st['n']):.4g}; at any spacing {kps(best_n):.4g} with {best_n} hops)"
                   + f". Time per delivered pair: {dur(slow * seg['pair_s'])}.")
        out.append(W["below"] if q < QMAX else W["above"])
    else:
        out.append("Route not joined yet.")
    if msg:
        out.append(">> " + msg)
    out.append(W["commands"])
    return "\n".join(out)


def act(st, cmd, args):
    W = WORDS[st["mode"]]
    rev = {W["swap"]: "swap", W["purify"]: "purify"}
    cmd = rev.get(cmd, cmd)
    links = st["links"]
    if cmd in ("swap", "purify"):
        if not args or not args[0].lstrip("-").isdigit():
            return "Give a link number."
        i = int(args[0])
        if cmd == "swap":
            if not 0 <= i < len(links) - 1:
                return f"No station after link {i}."
            st["history"].append(json.dumps(links))
            L1, L2 = links[i], links[i + 1]
            F = core.swap_exact(L1["F"], L2["F"])
            links[i:i + 2] = [dict(a=L1["a"], b=L2["b"], F=F, E=L1["E"] + L2["E"], D=L1["D"] + L2["D"])]
            log(st, dict(move="swap", i=i, F=F))
            return f"{W['swap']} at {name(st, L1['b'])}: new link {name(st, L1['a'])} - {name(st, L2['b'])}."
        if not 0 <= i < len(links):
            return f"No link {i}."
        st["history"].append(json.dumps(links))
        L = links[i]
        F, p = core.purify_exact(L["F"], L["F"])
        links[i] = dict(a=L["a"], b=L["b"], F=F, E=2 * L["E"] / p, D=[2 * d / p for d in L["D"]])
        log(st, dict(move="purify", i=i, F=F, p=p))
        extra = f" Check passed with probability {p:.3f}; each attempt uses two copies of this link." if W["show_F"] else ""
        return f"{W['purify']} on link {i} done.{extra}"
    if cmd == "test":
        if len(links) != 1:
            log(st, dict(move="test", ok=False, joined=False))
            return "Join the route into one link first."
        F = links[0]["F"]
        rng = random.Random(len(st["log"]))
        n = 2000
        qz = sum(rng.random() < core.qber(F) for _ in range(n)) / n
        qx = sum(rng.random() < core.qber(F) for _ in range(n)) / n
        ok = core.qber(F) < QMAX
        pairs = links[0]["E"]
        log(st, dict(move="test", ok=ok, joined=True, F=F, pairs=pairs, bits_per_s=key_bits(F) / (max(links[0]["D"]) * core.segment(st["n"])["pair_s"]), n=st["n"], F0=st["F0"]))
        return (("PASS" if ok else "FAIL") + f": model {WORDS[st['mode']]['q']} {100 * core.qber(F):.1f}% vs 11%. Sample of 2000 shots: {100 * qz:.1f}% and {100 * qx:.1f}%.")
    if cmd == "undo":
        if not st["history"]:
            return "Nothing to undo."
        st["links"] = json.loads(st["history"].pop())
        log(st, dict(move="undo"))
        return "Undone."
    if cmd == "reset":
        st["links"] = fresh(st["n"], st["F0"])
        st["history"] = []
        log(st, dict(move="reset"))
        return "Reset."
    if cmd == "hops":
        n = int(args[0]) if args and args[0].isdigit() else 0
        if n not in HOPS:
            return "hops must be 1, 2, 4 or 8."
        st["n"] = n
        st["links"] = fresh(n, st["F0"])
        st["history"] = []
        log(st, dict(move="hops", n=n))
        return f"Now {n} hops. Route reset: all moves cleared."
    if cmd == "f0":
        try:
            f = float(args[0])
        except (IndexError, ValueError):
            return "f0 must be 0.9, 0.95 or 0.99."
        if f not in core.F0_CHOICES:
            return "f0 must be 0.9, 0.95 or 0.99."
        st["F0"] = f
        st["links"] = fresh(st["n"], f)
        st["history"] = []
        log(st, dict(move="f0", F0=f))
        return f"Fresh pairs now {f}."
    if cmd == "look":
        return ""
    return "Unknown command."


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True)
    ap.add_argument("--mode", default="full", choices=["full", "blind"])
    ap.add_argument("cmd")
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    if a.cmd == "new":
        st = dict(mode=a.mode, n=4, F0=0.95, links=fresh(4, 0.95), history=[], log=[], show_intro=True)
        save(a.state, st)
        print(screen(st))
        return
    st = load(a.state)
    if len([e for e in st["log"] if e["move"] != "look"]) >= 60:
        print("Move limit (60) reached. Session over.")
        return
    msg = act(st, a.cmd.lower(), a.args)
    print(screen(st, msg))
    save(a.state, st)


if __name__ == "__main__":
    main()
