import json
import math
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

STUB = """
const binom = (n, p) => { let k = 0; for (let i = 0; i < n; i++) if (Math.random() < p) k++; return k; };
const app = { measure: { callPromising: async (b, th, beta, mode) => {
  await new Promise((r) => setTimeout(r, 150));
  const n = 4000, c = Math.cos(th);
  const pc = mode === 'usd' ? [1 - c, 1 - c] : [(1 + Math.cos(beta - th)) / 2, (1 - Math.cos(beta + th)) / 2];
  const tally = pc.map((q) => { const k = binom(n, q); return mode === 'usd' ? [k, 0, n - k] : [k, n - k, 0]; });
  return JSON.stringify({ tally, shots: n, qubits: mode === 'usd' ? 4 : 2, depth: 6, cx: mode === 'usd' ? 4 : 0, backend: 'preview (sampled from exact probabilities)', ionq: false, seconds: 0.15, drawing: '(circuit drawing appears on Qollab)' });
} } };
const backend = { name: 'preview' };
"""


def main(out):
    js = open(os.path.join(ROOT, "main.js")).read().replace("import * as app from 'hl.app';", STUB)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lockpick (preview)</title>
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
