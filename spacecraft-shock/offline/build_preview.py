import asyncio
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from qiskit.providers.basic_provider import BasicSimulator
from ss import app

STUB = """
const SETUP = %s;
const MEAS = %s;
const app = {
  setup: { callPromising: async () => { await new Promise((r) => setTimeout(r, 300)); return JSON.stringify(SETUP); } },
  measure: { callPromising: async (b, iIso, iBat) => {
    await new Promise((r) => setTimeout(r, 600));
    return JSON.stringify(MEAS[`${iBat},${iIso}`]);
  } },
};
const backend = { name: 'basic_simulator (preview: results precomputed locally)' };
"""


def main(out):
    be = BasicSimulator()
    meas = {f'{b},{i}': json.loads(asyncio.run(app.measure(be, i, b))) for b in range(3) for i in range(5)}
    js = open(os.path.join(ROOT, "main.js")).read().replace(
        "import * as app from 'ss.app';", STUB % (app.setup(), json.dumps(meas)))
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Quantum Simulation of Pyroshock (preview)</title>
<style>{open(os.path.join(ROOT, "main.css")).read()}</style></head>
<body>
{open(os.path.join(ROOT, "index.html")).read()}
<script type="module">{js}</script>
</body></html>"""
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(html)
    print("wrote", out)


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "offline", "out", "preview.html"))
