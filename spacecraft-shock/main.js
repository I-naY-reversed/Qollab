import * as app from 'ss.app';

const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const S = { cfg: null, iso: 0, bat: 0, t: 8, meas: {}, busy: false, ranOnce: false, playing: null, info: null };
const key = () => `${S.bat},${S.iso}`;
const D = () => S.cfg.designs[S.bat][S.iso];
const N = () => S.cfg.names.length;

const sci = (x, d = 1) => { if (x === 0) return '0'; const e = Math.floor(Math.log10(Math.abs(x))); return `${(x / 10 ** e).toFixed(d)}e${e}`; };
const ms = (t) => `${(t * 1e3).toFixed(2)} ms`;
const sigma = (q, n) => Math.sqrt(Math.max(q * (1 - q), 1 / n) / n);
const gfmt = (a) => (a >= 100 ? a.toFixed(0) : a >= 10 ? a.toFixed(1) : a >= 0.1 ? a.toFixed(2) : sci(a));
const mJ = (f) => { const v = f * S.cfg.e0 * 1e3; return v >= 10 ? v.toFixed(0) : v >= 1 ? v.toFixed(1) : v >= 0.01 ? v.toFixed(2) : sci(v); };
const dec = (e) => (e >= 0 ? String(10 ** e) : `0.${'0'.repeat(-e - 1)}1`);

const accel = (p, c, d = D()) => Math.sqrt(2 * d.k[c] * Math.max(p, 0) * S.cfg.e0) / S.cfg.masses[c] / S.cfg.g0;
const accelSigma = (p, c, n, d = D()) => { const s = sigma(p, n); return p > s ? accel(p, c, d) * s / (2 * p) : accel(s, c, d); };
const pSpring = (p, c) => p[N() + c];
const kLab = (k, rigid) => (k === S.cfg.k_struct ? rigid : `${sci(k)} N/m`);

function tFail(d, j) {
  const a = d.comps[j].a_fine, t = S.cfg.t_fine, lim = S.cfg.components[j].allow;
  for (let i = 1; i < a.length; i++) if (a[i] > lim) return t[i - 1] + (t[i] - t[i - 1]) * (lim - a[i - 1]) / (a[i] - a[i - 1]);
  return null;
}
const passes = (d) => d.f1 >= S.cfg.f_min && S.cfg.components.every((c, j) => d.comps[j].a_peak <= c.allow);

function setStatus(text, err = false) {
  $('status').textContent = text;
  $('status').classList.toggle('err', err);
}

const STOPS = [[0x1c, 0x2c, 0x38], [0x00, 0x33, 0xa0], [0x7a, 0xa2, 0xf7], [0xee, 0xf3, 0xff]];
function shade(s) {
  const u = Math.min(1, Math.max(0, (Math.log10(Math.max(s, 1e-6)) + 3) / 3)) * (STOPS.length - 1);
  const i = Math.min(STOPS.length - 2, Math.floor(u)), f = u - i;
  return `rgb(${STOPS[i].map((a, j) => Math.round(a + f * (STOPS[i + 1][j] - a))).join(',')})`;
}
const el = (tag, attrs = {}, text) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text !== undefined) e.textContent = text; return e; };

const G = { base: 532, block: 40, spring: 22, main: 105, side: 222, labX: 292, barX: 470, barW: 156 };
const blockW = (m) => 36 + 16 * m;
const barPos = (s) => G.barX + G.barW * Math.min(1, Math.max(0, (Math.log10(Math.max(s, 1e-6)) + 3) / 3));
const isSide = (j) => !S.cfg.parent.includes(j) && j !== N() - 1;

function zigzag(x0, y0, x1, y1, amp) {
  const n = 6, dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L, nx = -uy, ny = ux;
  const h = L / (n + 1);
  let d = `M${x0},${y0} L${(x0 + ux * h / 2).toFixed(1)},${(y0 + uy * h / 2).toFixed(1)}`;
  for (let i = 0; i < n; i++) { const s = h / 2 + h * (i + 0.5), o = i % 2 ? -amp : amp; d += ` L${(x0 + ux * s + nx * o).toFixed(1)},${(y0 + uy * s + ny * o).toFixed(1)}`; }
  return d + ` L${(x1 - ux * h / 2).toFixed(1)},${(y1 - uy * h / 2).toFixed(1)} L${x1},${y1}`;
}

function buildStack() {
  const svg = $('stack');
  svg.replaceChildren();
  svg.append(el('line', { x1: G.main - 95, x2: G.main + 95, y1: G.base + 1, y2: G.base + 1, class: 'base' }));
  for (let x = G.main - 91; x <= G.main + 91; x += 12) svg.append(el('line', { x1: x, x2: x - 8, y1: G.base + 3, y2: G.base + 12, class: 'hatch' }));
  svg.append(el('text', { x: G.main, y: G.base + 26, 'text-anchor': 'middle', class: 'lab-muted' }, 'launcher interface (fixed)'));
  svg.append(el('text', { x: G.barX - 10, y: 10, 'text-anchor': 'end', class: 'tick' }, 'energy (mJ)'));
  for (const v of [1e-3, 1e-2, 1e-1, 1]) {
    svg.append(el('line', { x1: barPos(v), x2: barPos(v), y1: 14, y2: G.base, class: 'gridv' }));
    svg.append(el('text', { x: barPos(v), y: 10, 'text-anchor': v === 1e-3 ? 'start' : v === 1 ? 'end' : 'middle', class: 'tick' }, mJ(v)));
  }

  const box = [];
  let y = G.base;
  for (let j = 0; j < N(); j++) {
    const ys = y - G.spring / 2;
    y -= G.spring;
    const w = blockW(S.cfg.masses[j]), x = isSide(j) ? G.side : G.main;
    box.push({ x, w, top: y - G.block, bot: y, ys });
    y -= G.block;
  }
  for (let j = 0; j < N(); j++) {
    const b = box[j], p = S.cfg.parent[j], side = isSide(j);
    const x0 = p < 0 ? G.main : (side ? box[p].x + box[p].w / 2 - 8 : box[p].x), y0 = p < 0 ? G.base : box[p].top;
    const x1 = side ? b.x - b.w / 2 + 8 : b.x;
    const comp = S.cfg.components.some((c) => c.index === j);
    svg.append(el('path', { d: zigzag(x0, y0, x1, b.bot, 8), id: `spr${j}`, class: comp ? 'spring mount' : 'spring' }));
    rowLabel(svg, b.ys, comp ? `${S.cfg.names[j]} mount` : 'structure, k = 3.5e7 N/m', `s${j}`, true, side ? b.x + b.w / 2 : G.main + 70);
    svg.append(el('rect', { x: b.x - b.w / 2, y: b.top, width: b.w, height: G.block, rx: 2, id: `blk${j}`, class: 'block' }));
    svg.append(el('text', { x: b.x, y: b.top + G.block / 2 + 4, 'text-anchor': 'middle', class: 'mlab', id: `mlab${j}` }, `${S.cfg.masses[j]} kg`));
    rowLabel(svg, b.top + G.block / 2, S.cfg.names[j], `m${j}`, false, b.x + b.w / 2);
  }
  const yRing = box[0].top + G.block / 2;
  svg.append(el('path', { d: `M18,${yRing + 12} L18,${yRing - 14} M12,${yRing - 6} L18,${yRing - 14} L24,${yRing - 6}`, class: 'impulse' }));
  svg.append(el('text', { x: 4, y: yRing - 22, class: 'lab-muted' }, 'v0 = 1.56 m/s'));
}

function rowLabel(svg, yc, name, id, small, xFrom) {
  svg.append(el('line', { x1: xFrom + 4, x2: G.labX - 6, y1: yc, y2: yc, class: 'leader' }));
  svg.append(el('text', { x: G.labX, y: yc + 4, class: small ? 'lab-muted' : 'lab' }, name));
  svg.append(el('text', { x: G.barX - 6, y: yc + 4, 'text-anchor': 'end', class: 'num', id: `v${id}` }, ''));
  svg.append(el('rect', { x: G.barX, y: yc - (small ? 2.5 : 4), width: 0, height: small ? 5 : 8, class: 'bar', id: `b${id}` }));
  svg.append(el('line', { x1: G.barX, x2: G.barX, y1: yc - 7, y2: yc + 7, class: 'tickx', id: `x${id}` }));
}

function drawStack() {
  const d = D(), n = N();
  const exact = d.snaps[S.t];
  const meas = S.t > 0 ? S.meas[key()]?.[S.t - 1] : null;
  for (let j = 0; j < n; j++) {
    for (const [id, k] of [[`m${j}`, j], [`s${j}`, n + j]]) {
      const e = exact[k], q = meas ? meas[k] : null;
      $(`x${id}`).setAttribute('x1', barPos(e)); $(`x${id}`).setAttribute('x2', barPos(e));
      $(`b${id}`).setAttribute('width', q === null ? 0 : Math.max(0, barPos(q) - G.barX));
      $(`v${id}`).textContent = q === null ? '' : mJ(q);
    }
    $(`blk${j}`).style.fill = meas ? shade(meas[j]) : 'var(--panel)';
    $(`mlab${j}`).classList.toggle('dark', Boolean(meas && meas[j] > 0.08));
    $(`spr${j}`).style.stroke = meas ? shade(meas[n + j]) : 'var(--ink-3)';
    $(`blk${j}`).classList.remove('failed');
  }
  const t = S.cfg.snap_steps[S.t] * S.cfg.dt;
  S.cfg.components.forEach((c, j) => { const tf = tFail(d, j); if (tf !== null && t >= tf) $(`blk${c.index}`).classList.add('failed'); });
  $('tLabel').textContent = `t = ${ms(t)}`;
  $('tsl').value = S.t;
  $('tsl').setAttribute('aria-valuetext', `t = ${ms(t)}`);
}

function chart(host, { xmin, xmax, ymin, ymax, xlabel, ylabel, xticks, aria }) {
  const W = 520, H = 320, L = 58, R = 14, T = 12, B = 62;
  const X = (v) => L + (W - L - R) * (v - xmin) / (xmax - xmin);
  const Y = (v) => T + (H - T - B) * (1 - (Math.log10(Math.max(v, ymin)) - Math.log10(ymin)) / (Math.log10(ymax) - Math.log10(ymin)));
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': aria, class: 'plot' });
  for (let e = Math.round(Math.log10(ymin)); e <= Math.log10(ymax) + 1e-9; e++) {
    svg.append(el('line', { x1: L, x2: W - R, y1: Y(10 ** e), y2: Y(10 ** e), class: 'grid' }));
    svg.append(el('text', { x: L - 6, y: Y(10 ** e) + 3.5, 'text-anchor': 'end' }, dec(e)));
  }
  for (const [v, t] of xticks) {
    svg.append(el('line', { x1: X(v), x2: X(v), y1: T, y2: H - B, class: 'grid' }));
    svg.append(el('text', { x: X(v), y: H - B + 15, 'text-anchor': 'middle' }, t));
  }
  svg.append(el('rect', { x: L, y: T, width: W - L - R, height: H - T - B, class: 'frame' }));
  svg.append(el('text', { x: (L + W - R) / 2, y: H - B + 34, 'text-anchor': 'middle', class: 'axl' }, xlabel));
  svg.append(el('text', { x: 14, y: (T + H - B) / 2, 'text-anchor': 'middle', transform: `rotate(-90 14 ${(T + H - B) / 2})`, class: 'axl' }, ylabel));
  host.replaceChildren(svg);
  return { svg, X, Y, L, R, T, B, W, H };
}
function curve(c, xs, ys, ymin, cls) {
  const g = el('g');
  let run = [];
  const flush = () => { if (run.length > 1) g.append(el('polyline', { points: run.join(' '), class: cls })); run = []; };
  xs.forEach((x, i) => { if (ys[i] >= ymin) run.push(`${c.X(x).toFixed(1)},${c.Y(ys[i]).toFixed(1)}`); else flush(); });
  flush();
  return g;
}
const MARK = ['square', 'triangle', 'circle'];
const STYLE = ['dashed', 'dotted', ''];
function marker(x, y, shape, open) {
  const cls = open ? 'open' : '';
  if (shape === 'square') return el('rect', { x: x - 3.5, y: y - 3.5, width: 7, height: 7, class: cls });
  if (shape === 'triangle') return el('path', { d: `M${x},${y - 4.5} L${x + 4.5},${y + 3.5} L${x - 4.5},${y + 3.5} Z`, class: cls });
  return el('circle', { cx: x, cy: y, r: 4, class: cls });
}

function drawTime() {
  const c = chart($('tplot'), { xmin: 0, xmax: S.cfg.window * 1e3, ymin: 0.01, ymax: 10, xlabel: 'time after release t (ms)', ylabel: '|a| / allowable',
    xticks: [0, 1, 2, 3].map((v) => [v, String(v)]), aria: 'Acceleration of each component relative to its allowable against time' });
  const tf = S.cfg.t_fine.map((t) => t * 1e3), d = D();
  c.svg.append(el('line', { x1: c.L, x2: c.W - c.R, y1: c.Y(1), y2: c.Y(1), class: 'limit' }));
  c.svg.append(el('text', { x: c.L + 6, y: c.Y(1) - 5, class: 'limlab' }, 'allowable'));
  const tc = S.cfg.snap_steps[S.t] * S.cfg.dt * 1e3;
  c.svg.append(el('line', { x1: c.X(tc), x2: c.X(tc), y1: c.T, y2: c.H - c.B, class: 'cursor' }));
  const m = S.meas[key()];
  S.cfg.components.forEach((comp, j) => {
    c.svg.append(curve(c, tf, d.comps[j].a_fine.map((a) => a / comp.allow), 0.01, `exact ${STYLE[j]}`));
    const tx = tFail(d, j);
    if (tx !== null) {
      const x = c.X(tx * 1e3), y = c.Y(1);
      c.svg.append(el('path', { d: `M${x - 4},${y - 4} L${x + 4},${y + 4} M${x - 4},${y + 4} L${x + 4},${y - 4}`, class: 'failmark' }));
    }
    if (m) m.forEach((p, i) => {
      const q = pSpring(p, comp.index), a = accel(q, comp.index) / comp.allow, s = accelSigma(q, comp.index, S.cfg.shots) / comp.allow;
      const x = c.X(S.cfg.snap_steps[i + 1] * S.cfg.dt * 1e3), yv = Math.max(a, 0.01);
      const g = el('g', { class: 'qpt' });
      g.append(el('line', { x1: x, x2: x, y1: c.Y(Math.max(yv - s, 1e-9)), y2: c.Y(yv + s) }));
      g.append(marker(x, c.Y(yv), MARK[j], a < 0.01));
      c.svg.append(g);
    });
  });
  S.cfg.components.forEach((comp, j) => {
    const y = c.H - 6, x = c.L + 152 * j;
    c.svg.append(el('line', { x1: x, x2: x + 22, y1: y - 4, y2: y - 4, class: `exact ${STYLE[j]}` }));
    const g = el('g', { class: 'qpt' }); g.append(marker(x + 32, y - 4, MARK[j], false)); c.svg.append(g);
    c.svg.append(el('text', { x: x + 42, y, class: 'leg' }, `${comp.name}, ${comp.allow} g`));
  });
}

function drawTable() {
  const cfg = S.cfg;
  let h = '<table class="designs"><thead><tr><th scope="col">battery mount</th>';
  cfg.k_iso.forEach((k) => { h += `<th scope="col">${kLab(k, 'no isolator')}</th>`; });
  h += '</tr></thead><tbody>';
  cfg.k_bat.forEach((kb, ib) => {
    h += `<tr><th scope="row">${kLab(kb, 'hard-mounted')}</th>`;
    cfg.k_iso.forEach((ki, ii) => {
      const d = cfg.designs[ib][ii];
      const fails = cfg.components.map((c, j) => ({ c, t: tFail(d, j) })).filter((x) => x.t !== null).sort((a, b) => a.t - b.t);
      const umax = Math.max(...cfg.components.map((c, j) => d.comps[j].a_peak / c.allow));
      let txt;
      if (d.f1 < cfg.f_min) txt = '<span class="bad">f1 &lt; 40 Hz</span>';
      else if (fails.length) txt = `<span class="bad">${fails[0].c.name}, ${ms(fails[0].t)}</span>`;
      else txt = `<span>passes, ${(100 * umax).toFixed(0)} %</span>`;
      const m = S.meas[`${ib},${ii}`];
      if (m) {
        const um = Math.max(...m.flatMap((p) => cfg.components.map((c) => accel(pSpring(p, c.index), c.index, d) / c.allow)));
        txt += `<span class="q">circuit ${(100 * um).toFixed(0)} %</span>`;
      }
      const sel = ib === S.bat && ii === S.iso;
      h += `<td><button class="cell${sel ? ' sel' : ''}" data-b="${ib}" data-i="${ii}" aria-pressed="${sel}"><span class="f">f1 = ${d.f1.toFixed(1)} Hz</span>${txt}</button></td>`;
    });
    h += '</tr>';
  });
  $('dtable').innerHTML = h + '</tbody></table>';
  $('dtable').querySelectorAll('button.cell').forEach((b) => b.addEventListener('click', () => select(+b.dataset.i, +b.dataset.b)));
}

function drawReadout() {
  const d = D();
  const m = S.t > 0 ? S.meas[key()]?.[S.t - 1] : null;
  S.cfg.components.forEach((comp, j) => {
    const c = comp.index, tf = tFail(d, j);
    $(`cv${j}`).textContent = m ? `${gfmt(accel(pSpring(m, c), c))} +/- ${gfmt(accelSigma(pSpring(m, c), c, S.cfg.shots))} g` : (S.t === 0 ? '0 g' : '-');
    $(`ce${j}`).textContent = `exact ${gfmt(accel(pSpring(d.snaps[S.t], c), c))} g; peak ${gfmt(d.comps[j].a_peak)} g`;
    $(`cf${j}`).textContent = tf === null ? `below ${comp.allow} g` : `exceeds ${comp.allow} g at ${ms(tf)}`;
    $(`cf${j}`).classList.toggle('bad', tf !== null);
  });
  const ok = d.f1 >= S.cfg.f_min;
  $('pF1').textContent = `${d.f1.toFixed(1)} Hz`;
  $('pOk').textContent = ok ? 'meets the 40 Hz requirement' : 'violates the 40 Hz requirement';
  $('pOk').classList.toggle('err', !ok);
  const good = S.cfg.designs.flat().filter(passes).length;
  $('verdict').textContent = passes(d)
    ? `Exact solution: the selected design meets 40 Hz and keeps every component below its allowable; ${good} of 15 designs do (Fig. 2).`
    : `Exact solution: the selected design fails; ${good} of 15 designs pass (Fig. 2), all with a compliant battery mount and k_iso <= 1.0e6 N/m.`;
}

function radio(host, items, current, onPick) {
  host.replaceChildren();
  items.forEach((lab, i) => {
    const b = document.createElement('button');
    b.className = 'preset';
    b.setAttribute('role', 'radio');
    b.textContent = lab;
    b.addEventListener('click', () => onPick(i));
    host.append(b);
  });
  host.onkeydown = (e) => {
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    e.preventDefault(); e.stopPropagation();
    const i = (current() + (e.key === 'ArrowRight' ? 1 : -1) + items.length) % items.length;
    onPick(i); host.children[i].focus();
  };
}
function syncRadio(host, i) { [...host.children].forEach((b, j) => { b.setAttribute('aria-checked', String(j === i)); b.tabIndex = j === i ? 0 : -1; }); }

function render() {
  syncRadio($('isoGroup'), S.iso);
  syncRadio($('batGroup'), S.bat);
  drawStack(); drawTime(); drawTable(); drawReadout();
  $('run').disabled = !S.cfg || S.busy;
  $('play').disabled = !S.cfg;
  $('tsl').disabled = !S.cfg;
}

function focusTime() {
  const d = D();
  const tfs = S.cfg.components.map((c, j) => tFail(d, j)).filter((x) => x !== null);
  const target = tfs.length ? Math.min(...tfs)
    : d.comps.map((c, j) => [c.a_peak / S.cfg.components[j].allow, c.t_peak]).sort((a, b) => b[0] - a[0])[0][1];
  const i = S.cfg.snap_steps.findIndex((s) => s * S.cfg.dt >= target - 1e-12);
  return i < 0 ? S.cfg.snap_steps.length - 1 : i;
}

function select(iIso, iBat) {
  if (S.busy || (iIso === S.iso && iBat === S.bat)) return;
  stop();
  S.iso = iIso; S.bat = iBat;
  S.t = focusTime();
  render();
  if (!S.meas[key()]) setStatus(S.info?.ionq ? 'Exact solution shown. This backend accepts one job per run.' : 'Exact solution shown. Run circuits to measure this design.');
}

async function runCircuits() {
  if (S.busy || !S.cfg) return;
  if (S.ranOnce && S.info?.ionq) { setStatus('This backend accepts one job per run. Stop and Run to measure again.', true); return; }
  stop();
  S.busy = true;
  $('stack').classList.add('loading');
  setStatus(`Running circuits on ${backend?.name ?? 'the backend'}...`);
  render();
  try {
    const r = JSON.parse(String(await app.measure.callPromising(backend, S.iso, S.bat)));
    S.ranOnce = true;
    S.info = r;
    const d = D();
    $('circuit').textContent = r.drawing;
    $('circNote').textContent = `${r.qubits} qubits; ${r.circuits} circuit${r.circuits > 1 ? 's' : ''} on ${r.backend}, ${r.shots} shots each, ${r.steps} product-formula steps; up to ${r.cx_max} CX, depth ${r.depth_max} after transpilation to rz, sx, x, cx.`;
    if (r.ionq) {
      const p = r.results[0].p;
      setStatus(`1 circuit on ${r.backend} (${r.steps} steps, 300 KB job limit) at t = ${ms(r.results[0].step * S.cfg.dt)}: ` + S.cfg.components.map((c) => `${c.name} ${gfmt(accel(pSpring(p, c.index), c.index))} g`).join(', ') + '.');
    } else {
      S.meas[key()] = r.results.map((x) => x.p);

      const z = [];
      r.results.forEach((x, i) => S.cfg.components.forEach((c) => {
        const e = pSpring(d.snaps[i + 1], c.index);
        z.push(Math.abs(pSpring(x.p, c.index) - e) / sigma(e, r.shots));
      }));
      setStatus(`${r.circuits} circuits on ${r.backend} in ${r.seconds.toFixed(1)} s. ${z.filter((v) => v <= 2).length} of ${z.length} mount-spring energy estimates within 2 sigma of the exact solution.`);
    }
  } catch (e) {
    console.log('measure error: ' + e);
    setStatus((S.ranOnce ? 'This backend accepts one job per run. Stop and Run to measure again. ' : 'The circuits did not run: ') + e, true);
  } finally {
    S.busy = false;
    $('stack').classList.remove('loading');
    render();
  }
}

function stop() { if (S.playing) { clearInterval(S.playing); S.playing = null; $('play').textContent = 'Play'; } }
function play() {
  if (S.playing) { stop(); return; }
  S.t = 0; render();
  $('play').textContent = 'Pause';
  S.playing = setInterval(() => { if (S.t >= 8) { stop(); return; } S.t += 1; render(); }, 650);
}

$('run').addEventListener('click', () => runCircuits());
$('play').addEventListener('click', play);
$('tsl').addEventListener('input', (e) => { stop(); S.t = +e.target.value; render(); });
document.addEventListener('keydown', (e) => {
  if (!S.cfg || e.target.closest('input, textarea') || e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (['1', '2', '3', '4', '5'].includes(k)) select(+k - 1, S.bat);
  else if (k === 'b') select(S.iso, (S.bat + 1) % S.cfg.k_bat.length);
  else if (k === 'arrowleft' && !e.target.closest('[role=radiogroup]')) { stop(); S.t = Math.max(0, S.t - 1); render(); }
  else if (k === 'arrowright' && !e.target.closest('[role=radiogroup]')) { stop(); S.t = Math.min(8, S.t + 1); render(); }
  else if (k === 'p') play();
  else if (k === 'r') runCircuits();
});

import('https://cdn.jsdelivr.net/npm/katex@0.16.11/+esm').then(({ default: katex }) => {
  document.querySelectorAll('#app .eq[data-tex]').forEach((n) => {
    try { katex.render(n.dataset.tex, n.firstElementChild, { displayMode: true, throwOnError: false, output: 'html' }); } catch (e) {  }
  });
  document.querySelectorAll('#app .m[data-tex]').forEach((n) => {
    try { katex.render(n.dataset.tex, n, { displayMode: false, throwOnError: false, output: 'html' }); } catch (e) {  }
  });
}).catch(() => {});

$('stack').classList.add('loading');
try {
  const t0 = performance.now();
  S.cfg = JSON.parse(String(await app.setup.callPromising()));
  console.log(`Pyroshock model ready in ${((performance.now() - t0) / 1000).toFixed(1)} s. Backend: ${backend?.name ?? backend}`);
  radio($('isoGroup'), S.cfg.k_iso.map((k) => kLab(k, 'none')), () => S.iso, (i) => select(i, S.bat));
  radio($('batGroup'), S.cfg.k_bat.map((k) => kLab(k, 'hard-mounted')), () => S.bat, (i) => select(S.iso, i));
  S.cfg.components.forEach((c, j) => { $(`cn${j}`).textContent = `${c.name[0].toUpperCase()}${c.name.slice(1)}, allowable ${c.allow} g`; });
  buildStack();
  S.t = focusTime();
  $('stack').classList.remove('loading');
  render();
  const ionq = String(backend?.name ?? '').toLowerCase().includes('ionq');
  if (ionq) setStatus('Exact solution shown. IonQ backends accept one circuit per run: Run circuits measures the selected design once.');
  else await runCircuits();
} catch (e) {
  console.log('setup error: ' + e);
  $('stack').classList.remove('loading');
  setStatus('Could not load the model: ' + e + '. Press Run again.', true);
}
