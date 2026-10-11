import * as app from 'hl.app';

const $ = (id) => document.getElementById(id);
const D = Math.PI / 180;
const S = { s: 0.5, p: 0.5, mode: 'min', beta: 0, pts: [], last: { min: null, usd: null }, busy: false, ranOnce: false, ionq: false, ready: false };
const theta = () => Math.acos(S.s);
const Pb = (b) => S.p * (1 + Math.cos(b - theta())) / 2 + (1 - S.p) * (1 - Math.cos(b + theta())) / 2;
const PH = () => 0.5 * (1 + Math.sqrt(1 - 4 * S.p * (1 - S.p) * S.s * S.s));
const guess = () => Math.max(S.p, 1 - S.p);
function optBeta() {
  let best = 0, bv = -1;
  for (let i = 0; i <= 1800; i++) { const v = Pb(i * 0.1 * D); if (v > bv) { bv = v; best = i * 0.1; } }
  return best;
}
const f3 = (x) => x.toFixed(3);
const NS = 'http://www.w3.org/2000/svg';
function el(tag, attrs, parent, text) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}
const C = { q: '#7aa2f7', c: '#e0b24a', ref: '#c77dba', ink: '#eeeeee', ink2: '#b4b6bb', ink3: '#9e9ea1', rule: '#2c3e4c', err: '#f08a7e' };
const setStatus = (t, bad = false) => { $('status').textContent = t; $('status').classList.toggle('err', bad); };

const R = 120;
const xy = (phi, r = R) => [r * Math.sin(phi), -r * Math.cos(phi)];
function drawBloch() {
  const g = $('bloch');
  g.replaceChildren();
  el('circle', { cx: 0, cy: 0, r: R, fill: 'none', stroke: C.rule, 'stroke-width': 1.5 }, g);
  el('line', { x1: 0, y1: -R - 8, x2: 0, y2: R + 8, stroke: C.rule }, g);
  el('line', { x1: -R - 8, y1: 0, x2: R + 8, y2: 0, stroke: C.rule }, g);
  el('text', { x: 4, y: -R - 12 }, g, '|0>');
  el('text', { x: 4, y: R + 22 }, g, '|1>');
  el('text', { x: R + 6, y: -4 }, g, '|+>');
  el('text', { x: -R - 30, y: -4 }, g, '|->');
  if ($('showOpt').checked && S.mode === 'min') {
    const o = optBeta() * D, [a, b] = xy(o);
    el('line', { x1: -a, y1: -b, x2: a, y2: b, stroke: C.ref, 'stroke-width': 2, 'stroke-dasharray': '6 4' }, g);
  }
  if (S.mode === 'min') {
    const [a, b] = xy(S.beta * D);
    el('line', { x1: -a, y1: -b, x2: a, y2: b, stroke: C.q, 'stroke-width': 2.5 }, g);
    el('circle', { cx: a, cy: b, r: 7, fill: C.q }, g);
    el('text', { x: a * 1.17 - 4, y: b * 1.17 + 4, fill: C.q, style: `fill:${C.q}` }, g, '+');
    el('text', { x: -a * 1.17 - 4, y: -b * 1.17 + 4, style: `fill:${C.q}` }, g, '-');
  }
  for (const [sgn, name] of [[1, 'ψ+'], [-1, 'ψ−']]) {
    const [a, b] = xy(sgn * theta());
    el('line', { x1: 0, y1: 0, x2: a, y2: b, stroke: C.ink, 'stroke-width': 2 }, g);
    el('circle', { cx: a, cy: b, r: 4.5, fill: C.ink }, g);
    el('text', { x: a + (sgn > 0 ? 8 : -30), y: b - 6, class: 'lbl' }, g, name);
  }

  const [a1, b1] = xy(theta(), 34), [a2, b2] = xy(-theta(), 34);
  el('path', { d: `M ${a2} ${b2} A 34 34 0 0 1 ${a1} ${b1}`, fill: 'none', stroke: C.ink3 }, g);
  el('text', { x: -16, y: -40 }, g, `2θ=${Math.round(2 * theta() / D)}`);
}
function bindDrag() {
  const svg = $('bloch');
  const set = (ev) => {
    if (S.mode !== 'min') return;
    const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());

    const b = Math.atan2(p.x, -p.y) / D;
    S.beta = Math.round(b < 0 ? b + 180 : b) % 181;
    sync();
  };
  let down = false;
  svg.addEventListener('pointerdown', (e) => { e.preventDefault(); down = true; svg.setPointerCapture(e.pointerId); set(e); });
  svg.addEventListener('pointermove', (e) => { if (down) set(e); });
  svg.addEventListener('pointerup', () => { down = false; });
}

const PW = 440, PHt = 280, M = { l: 56, r: 12, t: 12, b: 36 };
const X = (deg) => M.l + (deg / 180) * (PW - M.l - M.r);
const Y = (v) => M.t + (1 - v) * (PHt - M.t - M.b);
function drawPlot() {
  const g = $('pplot');
  g.replaceChildren();
  for (const v of [0, 0.25, 0.5, 0.75, 1]) {
    el('line', { x1: M.l, x2: PW - M.r, y1: Y(v), y2: Y(v), stroke: C.rule }, g);
    el('text', { x: M.l - 6, y: Y(v) + 4, 'text-anchor': 'end' }, g, v.toFixed(2));
  }
  for (const d of [0, 45, 90, 135, 180]) el('text', { x: X(d), y: PHt - M.b + 16, 'text-anchor': 'middle' }, g, String(d));
  el('text', { x: (M.l + PW - M.r) / 2, y: PHt - 4, 'text-anchor': 'middle' }, g, 'beta (deg)');
  el('text', { x: 10, y: Y(0.5), 'text-anchor': 'middle', transform: `rotate(-90 10 ${Y(0.5)})` }, g, 'P');
  if (S.mode === 'usd') {
    el('line', { x1: M.l, x2: PW - M.r, y1: Y(1 - S.s), y2: Y(1 - S.s), stroke: C.q, 'stroke-width': 2, 'stroke-dasharray': '8 3' }, g);
    el('text', { x: PW - M.r - 4, y: Y(1 - S.s) + 16, 'text-anchor': 'end', style: `fill:${C.q}` }, g, 'unambiguous: 1 - s, no errors');
  }
  el('line', { x1: M.l, x2: PW - M.r, y1: Y(guess()), y2: Y(guess()), stroke: C.c, 'stroke-width': 2, 'stroke-dasharray': '1.5 3' }, g);
  el('line', { x1: M.l, x2: PW - M.r, y1: Y(PH()), y2: Y(PH()), stroke: C.ref, 'stroke-width': 2, 'stroke-dasharray': '5 3' }, g);
  let d = '';
  for (let i = 0; i <= 180; i++) d += `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(Pb(i * D)).toFixed(1)}`;
  el('path', { d, fill: 'none', stroke: C.q, 'stroke-width': 2, opacity: S.mode === 'min' ? 1 : 0.35 }, g);
  if (S.mode === 'min') el('line', { x1: X(S.beta), x2: X(S.beta), y1: M.t, y2: PHt - M.b, stroke: C.ink3, 'stroke-dasharray': '2 3' }, g);
  for (const q of S.pts.filter((q) => q.s === S.s && q.p === S.p)) {
    el('line', { x1: X(q.beta), x2: X(q.beta), y1: Y(q.P + q.se), y2: Y(q.P - q.se), stroke: C.q, 'stroke-width': 1.5 }, g);
    el('circle', { cx: X(q.beta), cy: Y(q.P), r: 3.5, fill: C.q }, g);
  }
}

function bar(parent, frac, ticks) {
  const svg = el('svg', { viewBox: '0 0 300 22', preserveAspectRatio: 'none' }, parent);
  let x = 0;
  frac.forEach((f, i) => { el('rect', { x: x * 300, y: 3, width: f * 300, height: 16, fill: [C.q, C.err, '#5d6670'][i] }, svg); x += f; });
  for (const t of ticks) el('line', { x1: t * 300, x2: t * 300, y1: 0, y2: 22, stroke: C.ink, 'stroke-width': 2 }, svg);
}
function drawBars() {
  const box = $('bars');
  box.replaceChildren();
  const any = S.last.min || S.last.usd;
  if (!any) { box.innerHTML = '<p class="note">No measurement yet.</p>'; return; }
  for (const k of ['min', 'usd']) {
    const r = S.last[k];
    if (!r) continue;
    const row = document.createElement('div'); row.className = 'barrow';
    const lab = document.createElement('span');
    lab.textContent = k === 'min' ? `Minimum-error, beta = ${r.beta} deg` : 'Unambiguous (IDP)';
    row.appendChild(lab);
    const pred = k === 'min' ? [r.pred] : [1 - r.s];
    bar(row, r.frac, pred);
    box.appendChild(row);
    const note = document.createElement('p'); note.className = 'note';
    note.textContent = `s = ${r.s.toFixed(2)}, p = ${r.p.toFixed(2)}: P_corr = ${f3(r.frac[0])}, P_err = ${f3(r.frac[1])}, P_? = ${f3(r.frac[2])}.`;
    box.appendChild(note);
  }
}

function drawTiles() {
  const r = S.last[S.mode];
  const cur = r && r.s === S.s && r.p === S.p && (S.mode === 'usd' || r.beta === S.beta);
  $('sP').textContent = cur ? f3(r.frac[0]) : '-';
  $('sPn').textContent = cur ? `+- ${f3(r.se)} (1 sigma); P_err = ${f3(r.frac[1])}` : 'not measured at this setting';
  $('sE').textContent = S.mode === 'min' ? f3(Pb(S.beta * D)) : f3(1 - S.s);
  $('sEn').textContent = S.mode === 'min' ? `beta = ${S.beta} deg` : 'Eq. (4), P_err = 0';
  $('sH').textContent = f3(PH());
  $('sHn').textContent = `at beta = ${optBeta().toFixed(1)} deg`;
  $('sG').textContent = f3(guess());
}

function sync() {
  $('beta').value = S.beta;
  $('betaOut').textContent = `${S.beta} deg`;
  $('beta').disabled = S.mode !== 'min';
  if (S.vmode && S.vmode !== S.mode) $('verdict').textContent = '';
  drawBloch(); drawPlot(); drawTiles(); drawBars();
}

async function measure() {
  if (S.busy || !S.ready) return;
  if (S.ionq && S.ranOnce) { setStatus('This backend allows one job per run. Stop and Run to measure again.', true); return; }
  S.busy = true; $('measure').disabled = true;
  setStatus('Running the circuit...');
  try {
    const r = JSON.parse(String(await app.measure.callPromising(backend, theta(), S.beta * D, S.mode)));
    S.ranOnce = true; S.ionq = r.ionq;
    const n = r.shots, w = [S.p, 1 - S.p];
    const frac = [0, 1, 2].map((j) => w[0] * r.tally[0][j] / n + w[1] * r.tally[1][j] / n);
    const q = r.tally.map((t) => t[0] / n);
    const se = Math.sqrt((w[0] ** 2 * q[0] * (1 - q[0]) + w[1] ** 2 * q[1] * (1 - q[1])) / n);
    const pred = S.mode === 'min' ? Pb(S.beta * D) : 1 - S.s;
    S.last[S.mode] = { s: S.s, p: S.p, beta: S.beta, frac, se, pred };
    if (S.mode === 'min') S.pts.push({ s: S.s, p: S.p, beta: S.beta, P: frac[0], se });
    $('circuit').textContent = r.drawing;
    $('circNote').textContent = `${r.qubits} qubits, depth ${r.depth}, ${r.cx} two-qubit gates after transpiling, ${n} shots per state on ${r.backend}, ${r.seconds.toFixed(2)} s.`;
    S.vmode = S.mode;
    const z = se > 0 ? Math.abs(frac[0] - pred) / se : 0;
    if (S.mode === 'min') {
      const gap = PH() - frac[0];
      $('verdict').textContent = `P_corr = ${f3(frac[0])} +- ${f3(se)} at beta = ${S.beta} deg (Eq. 2: ${f3(pred)}, ${z.toFixed(1)} sigma). Helstrom bound ${f3(PH())}${gap < 0 ? ` (exceeded by ${f3(-gap)}, ${(-gap / se).toFixed(1)} sigma)` : `; gap ${f3(gap)}`}. Guessing ${f3(guess())}.`;
    } else {
      $('verdict').textContent = `IDP: P_corr = ${f3(frac[0])}, P_err = ${f3(frac[1])}, P_? = ${f3(frac[2])} (Eq. 4: ${f3(1 - S.s)}, 0, ${f3(S.s)}). Helstrom: P_corr = ${f3(PH())}, P_err = ${f3(1 - PH())}.`;
    }
    setStatus(S.ionq ? 'Done. This backend allows one job per run; Stop and Run to measure again.' : 'Done.');
  } catch (e) {
    console.log('measure error: ' + e);
    setStatus('The circuit did not run: ' + e, true);
  }
  S.busy = false;
  $('measure').disabled = S.ionq && S.ranOnce;
  sync();
}

document.querySelectorAll('#app input[name=s]').forEach((r) => r.addEventListener('change', () => { S.s = +r.value; sync(); }));
document.querySelectorAll('#app input[name=p]').forEach((r) => r.addEventListener('change', () => { S.p = +r.value; sync(); }));
document.querySelectorAll('#app input[name=mode]').forEach((r) => r.addEventListener('change', () => { S.mode = r.value; sync(); }));
$('beta').addEventListener('input', () => { S.beta = +$('beta').value; sync(); });
$('showOpt').addEventListener('change', sync);
$('measure').addEventListener('click', measure);
function pick(name, i) {
  const rs = [...document.querySelectorAll(`#app input[name=${name}]`)];
  const r = rs[(i + rs.length) % rs.length]; r.checked = true; r.dispatchEvent(new Event('change'));
}
document.addEventListener('keydown', (e) => {
  if (e.target.closest && e.target.closest('input[type=range]')) { if (e.key === 'Enter') measure(); return; }
  if (e.altKey || e.ctrlKey || e.metaKey) return;
  const idx = (name) => [...document.querySelectorAll(`#app input[name=${name}]`)].findIndex((r) => r.checked);
  if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
    if (S.mode !== 'min') return;
    S.beta = Math.min(180, Math.max(0, S.beta + (e.key === 'ArrowRight' ? 1 : -1) * (e.shiftKey ? 10 : 1)));
    sync(); e.preventDefault();
  } else if (e.key === 'Enter' && !(e.target.tagName === 'BUTTON')) { measure(); }
  else if (['1', '2', '3'].includes(e.key)) pick('s', +e.key - 1);
  else if (e.key === 'p' || e.key === 'P') pick('p', idx('p') + 1);
  else if (e.key === 'u' || e.key === 'U') pick('mode', idx('mode') + 1);
  else if (e.key === 'o' || e.key === 'O') { $('showOpt').checked = !$('showOpt').checked; sync(); }
});

import('https://cdn.jsdelivr.net/npm/katex@0.16.11/+esm').then(({ default: katex }) => {
  document.querySelectorAll('#app .eq[data-tex]').forEach((x) => {
    try { katex.render(x.dataset.tex, x.firstElementChild, { displayMode: true, throwOnError: false, output: 'html' }); } catch (e) {  }
  });
  document.querySelectorAll('#app .m[data-tex]').forEach((x) => {
    try { katex.render(x.dataset.tex, x, { displayMode: false, throwOnError: false, output: 'html' }); } catch (e) {  }
  });
}).catch(() => {});

bindDrag();
sync();
S.ready = true;
$('measure').disabled = false;
setStatus(`Ready. Backend: ${backend?.name ?? backend}.`);
console.log(`Lockpick ready. Backend: ${backend?.name ?? backend}`);
