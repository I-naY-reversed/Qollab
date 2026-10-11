import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from rr import app

STUB = """
const CFG = %s;
const w = (F) => (4 * F - 1) / 3, Fw = (x) => (1 + 3 * x) / 4;
const binom = (n, p) => { let k = 0; for (let i = 0; i < n; i++) if (Math.random() < p) k++; return k; };
const exactJs = (kind, F1, F2) => {
  if (kind === 'swap') return { F: Fw(w(F1) * w(F2)), p: 1 };
  const a1 = (1 - F1) / 3, a2 = (1 - F2) / 3, p = (F1 + a1) * (F2 + a2) + 4 * a1 * a2;
  return { F: (F1 * F2 + a1 * a2) / p, p };
};
const app = {
  setup: { callPromising: async () => { await new Promise((r) => setTimeout(r, 400)); return JSON.stringify(CFG); } },
  exact: { callPromising: async (k, a, b) => JSON.stringify(exactJs(k, a, b)) },
  measure: { callPromising: async (b, kind, F1, F2) => {
    await new Promise((r) => setTimeout(r, 120));
    const n = 2000, base = { kind, shots: n, qubits: 8, depth: 10, cx: 7, backend: 'preview (sampled from Eqs. 2-4, no circuit)', ionq: false, seconds: 0.12, drawing: '(circuit drawing appears on Qollab)' };
    if (kind === 'key') { const q = 2 * (1 - F1) / 3; return JSON.stringify({ ...base, n, qber_z: binom(n, q) / n, qber_x: binom(n, q) / n }); }
    const e = exactJs(kind, F1, F2);
    if (kind === 'swap') return JSON.stringify({ ...base, n, F: binom(n, e.F) / n });
    const kept = binom(n, e.p); return JSON.stringify({ ...base, n, kept, p: kept / n, F: binom(kept, e.F) / kept });
  } },
};
app.art = { callPromising: async () => ART };
const backend = { name: 'preview' };
"""


def main(out):
    os.chdir(ROOT)
    js = open(os.path.join(ROOT, "main.js")).read().replace("import * as app from 'rr.app';", (STUB % app.setup()) + "\nconst ART = " + json.dumps(app.art()) + ";")
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Repeater Run (preview)</title>
<style>{open(os.path.join(ROOT, "main.css")).read()}</style></head>
<body>
<p style="margin:0;padding:8px 16px;background:#1c2c38;color:#b4b6bb;font:13px/1.4 Georgia,serif">Offline preview: measured values are sampled from the equations here. On Qollab every move runs its circuit.</p>
{open(os.path.join(ROOT, "index.html")).read()}
<script type="module">{js}</script>
</body></html>"""
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(html)
    print("wrote", out)


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "offline", "out", "preview.html"))
