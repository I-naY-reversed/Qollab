import * as app from 'bh.app';

let SIZE = 256;
const PRESETS = ['cinematic', 'sgra', 'charged'];
const MARKER = 'rgb(199, 125, 186)';
const $ = (id) => document.getElementById(id);

const S = { preset: 'cinematic', pass: 9, data: null, img: {}, timer: null, busy: false, loading: false, generation: 0, pending: null, px: null, ranOnce: false };

const loadImg = (src) => new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = src; });

const sci = (x) => (x === 0 ? '0' : x >= 0.01 ? x.toFixed(3) : x.toExponential(1));
const thin = (n) => n.toLocaleString('en-US');
const abbr = (t, title) => `<abbr title="${title}">${t}</abbr>`;
const screens = () => document.querySelectorAll('#app .screen');
const radio = (name) => document.querySelector(`#app input[name="${name}"]:checked`).value;
const setRadio = (name, v) => { document.querySelector(`#app input[name="${name}"][value="${v}"]`).checked = true; draw(); };

function tipify() {
  const seen = new Set();
  document.querySelectorAll('#app abbr').forEach((el) => {
    const tip = el.dataset.tipText || el.getAttribute('title') || '';
    el.dataset.tipText = tip;
    el.removeAttribute('title');
    const key = el.textContent.trim();
    const first = tip && !seen.has(key);
    seen.add(key);
    el.classList.toggle('tip', Boolean(first));
    if (first) { el.dataset.tip = tip; el.tabIndex = 0; el.setAttribute('aria-label', `${key}: ${tip}`); }
    else { delete el.dataset.tip; el.removeAttribute('tabindex'); el.removeAttribute('aria-label'); }
  });
}

async function loadPreset(name) {
  const generation = ++S.generation;
  S.loading = true;
  S.pending = null;
  try {
    S.preset = name;
    document.querySelectorAll('#app .preset').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.preset === name)));
    screens().forEach((el) => el.classList.add('loading'));
    $('inspStatus').textContent = 'Loading precomputed passes...';
    const d = JSON.parse(String(await app.load_preset.callPromising(name)));
    if (generation !== S.generation) return;
    const [truth, c, h, q, ec, eh, eq, adv] = await Promise.all([d.truth, d.c, d.h, d.q, d.ec, d.eh, d.eq, d.adv].map(loadImg));
    if (generation !== S.generation) return;
    S.data = d;
    SIZE = d.curves.render.size;
    S.img = { truth, c, h, q, ec, eh, eq, adv };
    S.px = d.default_pixel;
    if (!$('eht').src) $('eht').src = d.eht;
    const cv = d.curves;
    $('pA').textContent = cv.a;
    $('pQ').textContent = cv.Q;
    $('pI').textContent = `${cv.inc} deg`;
    $('pR').textContent = `${cv.r_in.toFixed(2)} M`;
    $('ticks').innerHTML = cv.queries.map((n) => `<span>${n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + 'k' : n}</span>`).join('');
    $('edgeFrac').textContent = `${(100 * cv.edge_frac).toFixed(1)}%`;
    $('renderNote').textContent = `Render: ${cv.render.subrays} rays per pixel, ${(100 * cv.render.interpolated_cells).toFixed(0)}% of cells interpolated.`;
    screens().forEach((el) => el.classList.remove('loading'));
    S.loading = false;
    draw();
    await inspect(S.px[0], S.px[1]);
  } catch (e) {
    if (generation !== S.generation) return;
    S.data = null;
    S.pending = null;
    console.log('preset error: ' + e);
    $('inspStatus').textContent = 'Could not load this preset: ' + e;
  } finally {
    if (generation === S.generation) {
      S.loading = false;
      screens().forEach((el) => el.classList.remove('loading'));
    }
  }
}

function drawPanel(canvas, img, frame) {
  const ctx = canvas.getContext('2d');
  ctx.imageSmoothingEnabled = false;
  const k = canvas.width / SIZE;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(img, frame === null ? 0 : (frame - 1) * SIZE, 0, SIZE, SIZE, 0, 0, canvas.width, canvas.height);

  ctx.strokeStyle = 'rgba(238, 238, 238, 0.35)';
  ctx.fillStyle = 'rgba(238, 238, 238, 0.55)';
  ctx.lineWidth = 1;
  ctx.font = '10px "IBM Plex Mono", monospace';
  for (let v = 32; v < SIZE; v += 32) {
    const p = v * k, len = v % 64 ? 4 : 8;
    ctx.beginPath();
    ctx.moveTo(p, 0); ctx.lineTo(p, len); ctx.moveTo(0, p); ctx.lineTo(len, p);
    ctx.stroke();
    if (v % 64 === 0) { ctx.fillText(String(v), p + 3, 18); ctx.fillText(String(v), 11, p + 3); }
  }
  if (S.px) {
    ctx.strokeStyle = MARKER;
    ctx.lineWidth = 2;
    ctx.strokeRect((S.px[0] - 3) * k, (S.px[1] - 3) * k, 7 * k, 7 * k);
  }
}

function draw() {
  if (!S.data) return;
  const disp = radio('display');
  const ref = disp === 'ref', err = disp === 'error', adv = disp === 'adv';
  const pure = radio('method') === 'qae';
  const cv = S.data.curves;
  const i = S.pass - 1;
  const left = adv ? S.img.adv : ref ? S.img.truth : err ? S.img.ec : S.img.c;
  const right = adv || ref ? S.img.truth : err ? (pure ? S.img.eq : S.img.eh) : (pure ? S.img.q : S.img.h);
  drawPanel($('cvC'), left, ref || adv ? null : S.pass);
  drawPanel($('cvQ'), right, ref || adv ? null : S.pass);
  $('cbar').hidden = !err;
  $('abar').hidden = !adv;
  $('labC').innerHTML = adv ? 'Advantage map' : 'IID ' + abbr('MC', 'Monte Carlo: average of independently drawn rays');
  $('passLabel').textContent = S.pass;
  $('pass').value = S.pass;
  $('queryLabel').textContent = thin(cv.queries[i]);
  $('capQ').innerHTML = adv ? 'Reference' : pure ? abbr('MLAE', 'Maximum-likelihood amplitude estimation') + ' only' : 'IID MC + ' + abbr('MLAE', 'Maximum-likelihood amplitude estimation');
  $('rmseC').innerHTML = adv ? '-' : ref ? '0' : sci(cv.rmse_mc[i]);
  $('rmseQ').innerHTML = adv || ref ? '0' : sci(pure ? cv.rmse_qae[i] : cv.rmse_hybrid[i]);
  const qf = cv.quantum_pixel_frac[i];
  const share = qf === 0 ? 'no pixel is flagged at this budget'
    : `${qf < 1e-4 ? 'under 0.01' : (100 * qf).toFixed(qf < 0.01 ? 2 : 1)}% of pixels are flagged`;
  $('cap1').innerHTML = adv
    ? `Advantage map: pixels where amplitude estimation overtakes independent sampling within the schedule (${(100 * cv.advantage_any).toFixed(1)}% of the image), coloured by the crossover budget <i>N</i>*, Eq. (9); bright: early. They are the photon ring, the disk edges and the stars, where the ray values vary most. Elsewhere independent sampling is more accurate at every budget shown. Right: reference.`
    : ref
    ? `Reference: mean of all ${cv.render.subrays} rays per pixel.`
    : `${err ? 'Per-pixel log<sub>10</sub> of the absolute luminance error against the reference' : 'Progressive render'}, pass ${S.pass} of 9 at a budget of <i>N</i> = ${thin(cv.queries[i])} queries per pixel. Left: IID Monte Carlo. ` +
      (pure ? 'Right: ideal MLAE on every pixel.' : `Right: hybrid; a 32-ray pilot flags high-variance pixels, which spend the remaining <i>N</i> &minus; 32 queries on MLAE; ${share}.`) +
      ' Full-image passes sample the exact noiseless output law of each circuit; only Fig. 3 runs circuits. Marker: pixel shown in Fig. 3.';
  document.querySelectorAll('#ticks span').forEach((el, j) => el.classList.toggle('on', j === i));
  plot();
  tipify();
}

function plot() {
  const cv = S.data.curves;
  const W = 440, H = 290, L = 50, R = 10, T = 10, B = 34;
  const xs = cv.queries;
  const series = [
    ['rmse_mc_edge', 'var(--classical)', '', 'IID MC, high-variance'],
    ['rmse_qae_edge', 'var(--quantum)', '', 'MLAE, high-variance'],
    ['rmse_mc', 'var(--classical)', '5 4', 'IID MC, whole image'],
    ['rmse_hybrid', 'var(--quantum)', '5 4', 'IID MC + MLAE, whole image'],
    ['rmse_finite', 'var(--third)', '1 3', 'Finite table, whole image'],
  ];
  const all = series.flatMap(([k]) => cv[k]).filter((v) => v > 0);
  const y0 = Math.log10(Math.min(...all)) - 0.1, y1 = Math.log10(Math.max(...all)) + 0.1;
  const x0 = Math.log10(xs[0]) - 0.05, x1 = Math.log10(xs[xs.length - 1]) + 0.05;
  const X = (v) => L + (Math.log10(v) - x0) / (x1 - x0) * (W - L - R);
  const Y = (v) => T + (y1 - Math.log10(v)) / (y1 - y0) * (H - T - B);
  const pow = (e) => `1e${e}`;
  let s = '';
  for (let e = Math.ceil(x0); e <= x1; e++) s += `<line x1="${X(10 ** e)}" x2="${X(10 ** e)}" y1="${T}" y2="${H - B}" style="stroke:var(--rule)"/><text x="${X(10 ** e)}" y="${H - B + 15}" text-anchor="middle">${pow(e)}</text>`;
  for (let e = Math.ceil(y0); e <= y1; e++) s += `<line x1="${L}" x2="${W - R}" y1="${Y(10 ** e)}" y2="${Y(10 ** e)}" style="stroke:var(--rule)"/><text x="${L - 6}" y="${Y(10 ** e) + 4}" text-anchor="end">${pow(e)}</text>`;
  s += `<text x="${(L + W - R) / 2}" y="${H - 2}" text-anchor="middle">N (oracle queries per pixel)</text>`;
  s += `<text x="11" y="${(T + H - B) / 2}" transform="rotate(-90 11 ${(T + H - B) / 2})" text-anchor="middle">RMSE</text>`;
  const xq = xs[S.pass - 1];
  s += `<line x1="${X(xq)}" x2="${X(xq)}" y1="${T}" y2="${H - B}" style="stroke:var(--ink-3)" stroke-dasharray="2 3"/>`;
  series.forEach(([k, col, dash]) => {

    const idx = xs.map((x, j) => j).filter((j) => cv[k][j] > 0);
    const pts = idx.map((j) => `${X(xs[j]).toFixed(1)},${Y(cv[k][j]).toFixed(1)}`).join(' ');
    s += `<polyline points="${pts}" fill="none" style="stroke:${col}" stroke-width="2" stroke-dasharray="${dash}"/>`;
    if (cv[k][S.pass - 1] > 0) s += `<circle cx="${X(xq)}" cy="${Y(cv[k][S.pass - 1])}" r="3.5" style="fill:${col}"/>`;
    if (idx.length < xs.length) {
      const j = idx[idx.length - 1];
      s += `<text x="${X(xs[j]) - 4}" y="${Y(cv[k][j]) + 18}" text-anchor="middle" style="fill:${col}">exact from N = ${thin(cv.subrays)}</text>`;
    }
  });
  $('plot').innerHTML = s;
  $('legend').innerHTML = series.map(([, col, dash, label]) =>
    `<li><svg width="28" height="8" aria-hidden="true"><line x1="0" x2="28" y1="4" y2="4" style="stroke:${col}" stroke-width="2.5" stroke-dasharray="${dash}"/></svg>${label}</li>`).join('');
  const head = '<tr><th><i>N</i></th>' + series.map(([, , , l]) => `<th>${l}</th>`).join('') + '</tr>';
  const body = xs.map((x, j) => `<tr><td>${thin(x)}</td>` + series.map(([k]) => `<td>${cv[k][j] > 0 ? sci(cv[k][j]) : '0 (exact)'}</td>`).join('') + '</tr>').join('');
  $('plotTable').innerHTML = `<table>${head}${body}</table>`;
}

async function inspect(x, y) {
  if (S.loading || !S.data) return;
  const request = { x, y, preset: S.preset, generation: S.generation };
  if (S.busy) { S.pending = request; return; }
  S.busy = true;
  S.px = [x, y];
  $('px').value = x;
  $('py').value = y;
  draw();
  $('inspStatus').textContent = `Running pixel (${x}, ${y})...`;
  $('inspCard').setAttribute('aria-busy', 'true');
  try {
    const r = JSON.parse(String(await app.inspect.callPromising(backend, request.preset, x, y)));
    if (request.generation !== S.generation) return;
    S.ranOnce = true;
    const BX = (v) => (4 + 132 * v).toFixed(1);
    const scale = `<svg class="barsvg" viewBox="0 0 140 18" aria-hidden="true">${[0, 0.5, 1].map((v) =>
      `<text x="${BX(v)}" y="12" text-anchor="middle">${v}</text>`).join('')}</svg>`;
    const rows = r.ks.map((k, i) => {
      const m = r.hits[i] / r.shots, p = r.ideal[i];
      const sd = Math.sqrt(Math.max(m * (1 - m), 1 / r.shots) / r.shots);
      const lo = Math.max(0, m - sd), hi = Math.min(1, m + sd);
      const bar = `<svg class="barsvg" viewBox="0 0 140 18" role="img" aria-label="measured ${m.toFixed(2)} plus or minus ${sd.toFixed(2)}, predicted ${p.toFixed(2)}">` +
        `<line x1="${BX(0)}" x2="${BX(1)}" y1="9" y2="9" style="stroke:var(--rule)" stroke-width="6"/>` +
        [0, 0.5, 1].map((v) => `<line x1="${BX(v)}" x2="${BX(v)}" y1="4" y2="14" style="stroke:var(--ink-3)" stroke-width="1"/>`).join('') +
        `<line x1="${BX(0)}" x2="${BX(m)}" y1="9" y2="9" style="stroke:var(--quantum)" stroke-width="6"/>` +
        `<line x1="${BX(lo)}" x2="${BX(hi)}" y1="9" y2="9" style="stroke:var(--ink)" stroke-width="1.5"/>` +
        `<line x1="${BX(lo)}" x2="${BX(lo)}" y1="6" y2="12" style="stroke:var(--ink)" stroke-width="1.5"/><line x1="${BX(hi)}" x2="${BX(hi)}" y1="6" y2="12" style="stroke:var(--ink)" stroke-width="1.5"/>` +
        `<line x1="${BX(p)}" x2="${BX(p)}" y1="1" y2="17" style="stroke:var(--third)" stroke-width="2"/></svg>`;
      return `<tr><td>${k}</td><td>${r.hits[i]}/${r.shots}</td><td>${m.toFixed(2)}</td><td>${p.toFixed(2)}</td><td class="barcell">${bar}</td></tr>`;
    }).join('');
    const circ = r.packed
      ? `One ${r.qubits}-qubit circuit with ${r.ks.length} blocks side by side (IonQ runs one circuit per job)`
      : `${r.ks.length} circuits of ${r.qubits} qubits`;
    $('insp').innerHTML = `
      <table class="est">
        <tr><th>&mu;<sub>${abbr('ref', 'Reference: mean of the pixel\'s ' + r.subrays + ' stored sub-ray values')}</sub></th><td>${r.mu.toFixed(4)}</td><td class="note">mean of ${r.subrays} sub-rays; the classical mean of the ${r.encoded_values}-value oracle table equals it exactly after ${r.encoded_values} reads</td></tr>
        <tr class="q"><th>&mu;<sub>MLAE</sub></th><td>${r.estimate.toFixed(4)}</td><td class="note">error ${sci(r.error)} in this run; <i>N</i> = ${thin(r.queries)} queries</td></tr>
        <tr class="q"><th>&epsilon;<sub>MLAE</sub></th><td>${r.mlae_rmse.toFixed(4)}</td><td class="note">RMSE over ${r.mlae_trials} trials of the ideal output law, Eq. (6), at the same <i>N</i></td></tr>
        <tr class="c"><th>&epsilon;<sub>IID</sub></th><td>${r.iid_error.toFixed(4)}</td><td class="note">expected error of ${thin(r.queries)} independent sub-ray samples, Eq. (4) (continuous-integrand model)</td></tr>
      </table>
      <div class="tablewrap"><table>
        <tr><th>${abbr('<i>k</i>', 'Number of Grover iterations Q applied after A')}</th><th>hits</th><th>measured</th><th>Eq. (6)</th><th class="barcell">${scale}</th></tr>${rows}
      </table></div>
      <p class="note">Bars: measured hit rate with binomial 1-sigma whiskers; plum tick: Eq. (6).</p>
      <p class="circ">${circ}; ${r.index_qubits} index qubits + 1 ancilla per block over the pixel's sub-rays averaged to ${2 ** r.index_qubits} block means (exact). Deepest: ${r.depth_max} layers, ${r.cx_max} ${abbr('CX', 'Controlled-NOT gates after transpiling')}. ${r.shots} shots per circuit. Backend ${r.backend}, ${(r.t_transpile + r.t_run).toFixed(1)} s.</p>`;
    $('inspStatus').textContent = 'Done. Click a plate or enter coordinates to run another pixel. On IonQ backends press Stop, then Run, first (one job per run).';
    tipify();
  } catch (e) {
    if (request.generation !== S.generation) return;
    console.log('inspector error: ' + e);
    $('inspStatus').textContent = 'Inspector circuit failed: ' + e;
  } finally {
    S.busy = false;
    $('inspCard').removeAttribute('aria-busy');
    const next = S.pending;
    S.pending = null;
    if (next && next.generation === S.generation && next.preset === S.preset && !S.loading) inspect(next.x, next.y);
  }
}

function setPass(p) { S.pass = Math.min(9, Math.max(1, p)); draw(); }

function setPlayLabel(playing) { $('play').textContent = playing ? 'Pause' : 'Play'; }

function togglePlay() {
  if (S.timer) { clearInterval(S.timer); S.timer = null; setPlayLabel(false); return; }
  if (S.pass >= 9) setPass(1);
  setPlayLabel(true);
  S.timer = setInterval(() => { if (S.pass >= 9) togglePlay(); else setPass(S.pass + 1); }, 900);
}

const clampPx = (v) => Math.min(SIZE - 1, Math.max(0, Math.round(+v) || 0));

function onCanvasClick(ev) {
  const rect = ev.target.getBoundingClientRect();
  inspect(clampPx((ev.clientX - rect.left) / rect.width * SIZE - 0.5), clampPx((ev.clientY - rect.top) / rect.height * SIZE - 0.5));
}

document.querySelectorAll('#app .preset').forEach((b) => b.addEventListener('click', () => loadPreset(b.dataset.preset)));
$('pass').addEventListener('input', (e) => setPass(+e.target.value));
$('play').addEventListener('click', togglePlay);
document.querySelectorAll('#app input[name="method"], #app input[name="display"]').forEach((el) => el.addEventListener('change', draw));
$('cvC').addEventListener('click', onCanvasClick);
$('cvQ').addEventListener('click', onCanvasClick);
$('runPx').addEventListener('click', () => inspect(clampPx($('px').value), clampPx($('py').value)));
document.addEventListener('keydown', (e) => {
  if (['SELECT', 'INPUT', 'SUMMARY'].includes(e.target.tagName)) return;
  if (e.shiftKey && e.key.startsWith('Arrow')) {
    e.preventDefault();
    const d = { ArrowLeft: [-4, 0], ArrowRight: [4, 0], ArrowUp: [0, -4], ArrowDown: [0, 4] }[e.key];
    S.px = [clampPx(S.px[0] + d[0]), clampPx(S.px[1] + d[1])];
    $('px').value = S.px[0];
    $('py').value = S.px[1];
    draw();
  } else if (e.key === 'Enter' && e.target.tagName !== 'BUTTON') inspect(S.px[0], S.px[1]);
  else if (e.key === ' ') { e.preventDefault(); togglePlay(); }
  else if (e.key === 'ArrowRight') setPass(S.pass + 1);
  else if (e.key === 'ArrowLeft') setPass(S.pass - 1);
  else if (e.key === 'q' || e.key === 'Q') setRadio('method', radio('method') === 'qae' ? 'hybrid' : 'qae');
  else if (e.key === 'e' || e.key === 'E') setRadio('display', radio('display') === 'error' ? 'image' : 'error');
  else if (e.key === 't' || e.key === 'T') setRadio('display', radio('display') === 'ref' ? 'image' : 'ref');
  else if (e.key === 'a' || e.key === 'A') setRadio('display', radio('display') === 'adv' ? 'image' : 'adv');
  else if (['1', '2', '3'].includes(e.key)) loadPreset(PRESETS[+e.key - 1]);
});

import('https://cdn.jsdelivr.net/npm/katex@0.16.11/+esm').then(({ default: katex }) => {
  document.querySelectorAll('#app .eq[data-tex]').forEach((el) => {
    const target = el.firstElementChild;
    try { katex.render(el.dataset.tex, target, { displayMode: true, throwOnError: false, output: 'html' }); } catch (e) {  }
  });
  document.querySelectorAll('#app .m[data-tex]').forEach((el) => {
    try { katex.render(el.dataset.tex, el, { displayMode: false, throwOnError: false, output: 'html' }); } catch (e) {  }
  });
}).catch(() => {});

tipify();
await loadPreset(PRESETS[0]);
console.log('Quantum supersampling ready. Press Play, or click a plate to run that pixel.');
