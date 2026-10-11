import asyncio
import json
import os
import sys

import numpy as np
from qiskit.providers.basic_provider import BasicSimulator

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from bh import app

GRID = 8


def record(name):

    d = json.loads(app.load_preset(name))
    pts = {tuple(d["default_pixel"])}
    size = d["curves"]["render"]["size"]
    for gx in np.linspace(size * 0.2, size * 0.8, GRID).astype(int):
        for gy in np.linspace(size * 0.2, size * 0.8, GRID).astype(int):
            pts.add((int(gx), int(gy)))
    runs = [json.loads(asyncio.run(app.inspect(BasicSimulator(), name, x, y))) for x, y in sorted(pts)]
    for r in runs:
        r["backend"] = "basic_simulator (recorded for this preview)"
    return d, runs


def main(out):
    data = {}
    for name in ("sgra", "charged", "cinematic"):
        d, runs = record(name)
        data[name] = dict(preset=d, runs=runs)
        print(name, len(runs), "recorded runs")
    stub = """
const PREVIEW = %s;
const app = {
  load_preset: { callPromising: async (n) => JSON.stringify(PREVIEW[n].preset) },
  inspect: { callPromising: async (b, n, x, y) => {
    const runs = PREVIEW[n].runs;
    let best = runs[0], dist = Infinity;
    for (const r of runs) { const dd = (r.x - x) ** 2 + (r.y - y) ** 2; if (dd < dist) { dist = dd; best = r; } }
    await new Promise((res) => setTimeout(res, 150));
    return JSON.stringify(best);
  } },
};
const backend = { name: 'preview' };
""" % json.dumps(data)
    js = open("main.js").read().replace("import * as app from 'bh.app';", stub)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quantum Supersampling</title>
<style>{open("main.css").read()}</style></head>
<body>
<p style="margin:0;padding:8px 16px;background:#1c2c38;color:#b4b6bb;font:13px/1.4 Georgia,serif">Offline preview. On Qollab the inspector runs the circuits live; here it replays runs recorded on Qiskit's BasicSimulator for the nearest of {GRID * GRID}+ sampled pixels.</p>
{open("index.html").read()}
<script type="module">{js}</script>
</body></html>"""
    with open(out, "w") as f:
        f.write(html)
    print("wrote", out, round(os.path.getsize(out) / 1e6, 1), "MB")


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "offline", "out", "preview.html"))
