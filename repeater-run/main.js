import * as app from 'rr.app';

const $ = (id) => document.getElementById(id);
const QBER_LINE = 0.11;
const S = { cfg: null, n: 4, F0: 0.95, links: [], history: [], log: [], busy: false, ranOnce: false, ionqUsed: false, keyTest: null, useMeasured: false };
const plan = () => S.cfg.plans[String(S.F0)][S.n];

const f3 = (x) => x.toFixed(3);

const purifyF = (F) => { const a = (1 - F) / 3, p = (F + a) ** 2 + 4 * a * a; return (F * F + a * a) / p; };
const pct = (x) => `${(100 * x).toFixed(1)}%`;
const qberOf = (F) => (2 * (1 - F)) / 3;
const h2 = (q) => (q <= 0 || q >= 1 ? 0 : -q * Math.log2(q) - (1 - q) * Math.log2(1 - q));
const keyRate = (q) => Math.max(0, 1 - 2 * h2(q));
function dur(s) {
  if (s < 1) return `${(s * 1000).toFixed(0)} ms`;
  if (s < 120) return `${s.toFixed(1)} s`;
  if (s < 7200) return `${(s / 60).toFixed(1)} min`;
  if (s < 172800) return `${(s / 3600).toFixed(1)} h`;
  if (s < 3.15e7 * 2) return `${(s / 86400).toFixed(0)} days`;
  return `${(s / 3.156e7).toFixed(1)} years`;
}
const rate = (r, u = 'bits') => (r >= 0.1 ? `${r.toFixed(r >= 10 ? 1 : 2)} ${u}/s` : r >= 1e-4 ? `${(r * 3600).toFixed(1)} ${u}/h` : `${(r * 3.156e7).toExponential(1)} ${u}/yr`);

function bestAtF0() {
  const all = S.cfg.plans[String(S.F0)];
  let best = null;
  for (const n of Object.keys(all)) { const p = all[n].par; if (p && (!best || p.key_per_s > best.r)) best = { r: p.key_per_s, n: +n }; }
  return best;
}

const calm = () => $('app').classList.contains('still') || window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, calm() ? 0 : ms));

const travel = (t) => Math.min(9, Math.max(0.9, 0.9 + 0.8 * Math.log10(t / 0.0076)));
async function loadArt() {
  try {
    const a = JSON.parse(String(await app.art.callPromising()));
    const root = $('app');
    for (const k of ['banner', 'station', 'photon', 'purify', 'emblem']) root.style.setProperty(`--art-${k}`, `url("${a[k]}")`);
    root.classList.add('art');
  } catch (e) { console.log('art not loaded (page works without it): ' + e); }
}
const sci = (x) => (x >= 0.01 ? x.toFixed(3) : x.toExponential(1));

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

function setStatus(text, err = false) {
  $('status').textContent = text;
  $('status').classList.toggle('err', err);
}

const F_LINE = 1 - 1.5 * QBER_LINE;
function fbar(F, label) {
  const X = (v) => (2 + 136 * (Math.min(1, Math.max(0.5, v)) - 0.5) / 0.5).toFixed(1);
  return `<svg class="fbar" viewBox="0 0 140 14" preserveAspectRatio="none" role="img" aria-label="${label}">` +
    `<rect x="2" y="4" width="136" height="6" style="fill:#3d5466"/>` +
    `<rect x="2" y="4" width="${(X(F) - 2).toFixed(1)}" height="6" style="fill:var(--quantum)"/>` +
    `<line x1="${X(F_LINE)}" x2="${X(F_LINE)}" y1="0" y2="14" style="stroke:#0b1218" stroke-width="5" vector-effect="non-scaling-stroke"/>` +
    `<line x1="${X(F_LINE)}" x2="${X(F_LINE)}" y1="0" y2="14" style="stroke:var(--third)" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg>`;
}

function cityName(i) {
  if (i === 0) return 'Toronto';
  if (i === S.n) return 'Montreal';
  return `R${i}`;
}

function newRoute(n) {
  S.n = n;
  S.links = Array.from({ length: n }, (_, i) => ({ a: i, b: i + 1, F: S.F0, E: 1, D: [1] }));
  S.history = [];
  S.log = [];
  S.keyTest = null;
  document.querySelectorAll('#app .preset').forEach((b) => b.setAttribute('aria-pressed', String(+b.dataset.n === n)));
  document.querySelectorAll('#app .f0').forEach((b) => b.setAttribute('aria-pressed', String(+b.dataset.f0 === S.F0)));
  const pl = plan();
  $('pKm').textContent = `${pl.km.toFixed(0)} km`;
  $('pEta').textContent = sci(pl.eta);
  $('pT').textContent = dur(pl.pair_s);
  $('kmTicks').innerHTML = `<span><b>Toronto</b> 0 km</span><span>${n} ${n === 1 ? 'segment' : 'segments'} of ${pl.km.toFixed(0)} km</span><span><b>Montreal</b> ${S.cfg.route_km.toFixed(0)} km</span>`;
  $('circuit').textContent = 'No circuit yet.';
  $('circNote').textContent = '';
  render();
  setStatus(`${n} ${n === 1 ? 'segment' : 'segments'} of ${pl.km.toFixed(0)} km, F0 = ${S.F0.toFixed(2)}.`);
}

function snapshot() { S.history.push(JSON.stringify({ links: S.links, log: S.log })); }

function render() {
  const route = $('route');
  route.classList.remove('loading');
  const parts = [];
  S.links.forEach((l, i) => {
    const q = qberOf(l.F);
    const span = l.b - l.a;
    const tLink = Math.max(...l.D) * plan().pair_s;
    parts.push(`<div class="link${q < QBER_LINE ? ' ok' : ''}" style="--hops:${span}; --travel:${travel(tLink).toFixed(2)}s" role="group" aria-label="Link ${cityName(l.a)} to ${cityName(l.b)}">
      <span class="fibre" aria-hidden="true"><span class="ph"></span></span>
      <span class="ends">${cityName(l.a)} - ${cityName(l.b)}, ${(span * plan().km).toFixed(0)} km</span>
      <span class="lf"><i>F</i> = ${f3(l.F)}</span>
      <span class="lq">QBER ${pct(q)}, <i>M</i> = ${Math.max(...l.D).toFixed(2)}</span>
      ${fbar(l.F, `fidelity ${f3(l.F)}, limit ${f3(F_LINE)}`)}
      <button data-act="purify" data-i="${i}" ${S.busy ? 'disabled' : ''} aria-label="Purify link ${cityName(l.a)} to ${cityName(l.b)}: kept link would have F ${f3(purifyF(l.F))}">Purify</button>
      <span class="lq"${purifyF(l.F) > l.F ? ' aria-hidden="true"' : ''}>${purifyF(l.F) > l.F ? `purify: F ${f3(purifyF(l.F))}` : 'purify would lower F (needs F > 0.5): undo and purify shorter links first'}</span>
    </div>`);
    if (i < S.links.length - 1) {
      const n2 = S.links[i + 1];
      const Fs = (1 + 3 * ((4 * l.F - 1) / 3) * ((4 * n2.F - 1) / 3)) / 4;
      parts.push(`<div class="station"><span class="node" aria-hidden="true"></span><span class="sname">${cityName(l.b)}</span>
        <button data-act="swap" data-i="${i}" ${S.busy ? 'disabled' : ''} aria-label="Swap at ${cityName(l.b)}: joined link would have F ${f3(Fs)}">Swap</button>
        <span class="sname" aria-hidden="true">${f3(Fs)}</span></div>`);
    }
  });
  route.innerHTML = parts.join('');
  $('undo').disabled = S.busy || !S.history.length;
  $('reset').disabled = S.busy || !S.history.length;
  renderScore();
  renderLog();
}

function totals() {
  const pl = plan();

  const pairs = S.links.reduce((s, l) => s + l.E, 0);

  const slowest = Math.max(...S.links.flatMap((l) => l.D));
  return { pairs, M: slowest, time: slowest * pl.pair_s };
}

function renderScore() {
  const done = S.links.length === 1;
  const t = totals();
  const par = plan().par;
  const top = bestAtF0();
  $('sRatePar').textContent = (par ? `best known at ${S.n} ${S.n === 1 ? 'segment' : 'segments'}: ${rate(par.key_per_s)}` : `no strategy reaches 11% at ${S.n} segments`)
    + (top ? `; at any segment count: ${rate(top.r)} (${top.n})` : '');
  S.R = null;
  if (done) {
    const F = S.links[0].F, q = qberOf(F), r = keyRate(q);
    S.R = r / t.time;
    $('sF').textContent = f3(F);
    $('sF').className = `tval${q < QBER_LINE ? '' : ' bad'}`;
    $('qberBar').innerHTML = qberBar(q, S.keyTest);
    $('sPair').textContent = rate(1 / t.time, 'pairs');
    $('sPairs').textContent = `T = ${dur(t.time)}; M = ${t.M.toFixed(2)}; ${t.pairs.toFixed(2)} elementary pairs per delivered pair`;
    $('sRate').textContent = S.R > 0 ? rate(S.R) : '0';
    $('sRate').className = `tval${S.R > 0 ? '' : ' bad'}`;
  } else {
    $('qberBar').innerHTML = qberBar(null, null);
    for (const id of ['sF', 'sPair', 'sRate']) { $(id).textContent = '-'; $(id).className = 'tval'; }
    $('sPairs').textContent = `M = ${t.M.toFixed(2)}; ${t.pairs.toFixed(2)} elementary pairs so far`;
  }
  $('key').disabled = S.busy || !done;
  $('emblem').classList.toggle('on', done && qberOf(S.links[0].F) < QBER_LINE);
  if (!done) $('sKey').textContent = `${S.links.length} links; the result is defined once one link spans the route.`;
  else if (!S.keyTest) {
    const q = qberOf(S.links[0].F);
    $('sKey').textContent = `QBER = ${pct(q)} (Eq. 4), r = ${keyRate(q).toFixed(3)} (Eq. 5): ${q < QBER_LINE ? 'secret key possible' : 'no secret key. Each swap compounded the noise: undo, purify links before joining them, or use fewer segments'}.`;
  }
  renderRatePlot();
}

function renderRatePlot() {
  const W = 420, H = 230, x0 = 52, x1 = 404, y0 = 12, y1 = 196, NS = [1, 2, 4, 8], LO = -10, HI = 3;
  const X = (n) => x0 + (x1 - x0) * Math.log2(n) / 3;
  const Y = (r) => y1 - (y1 - y0) * (Math.min(HI, Math.max(LO, Math.log10(r))) - LO) / (HI - LO);
  let g = '';
  for (let e = LO; e <= HI; e += 2) g += `<line x1="${x0}" x2="${x1}" y1="${Y(10 ** e)}" y2="${Y(10 ** e)}" style="stroke:var(--rule)" stroke-width="1"/><text x="${x0 - 6}" y="${Y(10 ** e) + 3.5}" text-anchor="end">1e${e}</text>`;
  g += NS.map((n) => `<text x="${X(n)}" y="${y1 + 16}" text-anchor="middle">${n}</text>`).join('');
  g += `<text x="${(x0 + x1) / 2}" y="${H - 2}" text-anchor="middle">segments</text><text x="12" y="${(y0 + y1) / 2}" text-anchor="middle" transform="rotate(-90 12 ${(y0 + y1) / 2})">R (bits/s)</text>`;
  const etaTot = 10 ** (-S.cfg.loss_db_km * S.cfg.route_km / 10), plob = -Math.log2(1 - etaTot) * 1e9;
  g += `<line x1="${x0}" x2="${x1}" y1="${Y(plob)}" y2="${Y(plob)}" style="stroke:var(--ink-2)" stroke-width="1.5" stroke-dasharray="5 4"/><text x="${x0 + 6}" y="${Y(plob) - 5}">PLOB, 1 GHz</text>`;
  const f0s = S.cfg.F0_choices.slice().sort((a, b) => (a === S.F0) - (b === S.F0));
  for (const f0 of f0s) {
    const sel = f0 === S.F0;
    const pts = NS.map((n) => [n, S.cfg.plans[String(f0)][n].par]).filter(([, p]) => p && p.key_per_s > 0).map(([n, p]) => [X(n), Y(p.key_per_s)]);
    const col = sel ? 'var(--quantum)' : 'var(--ink-3)';
    g += `<polyline points="${pts.map((p) => p.map((v) => v.toFixed(1)).join(',')).join(' ')}" style="fill:none;stroke:${col}" stroke-width="${sel ? 2 : 1.2}"/>`;
    g += pts.map(([x, y]) => `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${sel ? 3 : 2}" style="fill:${col}"/>`).join('');
    const [lx, ly] = pts[pts.length - 1];
    g += `<text x="${lx + 6}" y="${ly + 3.5}" style="fill:${col}">${f0.toFixed(2)}</text>`;
  }
  if (S.R > 0) g += `<circle cx="${X(S.n).toFixed(1)}" cy="${Y(S.R).toFixed(1)}" r="5.5" style="fill:none;stroke:var(--classical)" stroke-width="2"/>`;
  $('rateplot').innerHTML = `<svg id="rplot" viewBox="0 0 ${W + 30} ${H}" role="img" aria-label="Best known key rate against segment count${S.R > 0 ? `; current route ${rate(S.R)}` : ''}">${g}</svg>`;
}

function qberBar(q, test) {
  const X = (v) => (4 + 212 * Math.min(0.25, Math.max(0, v)) / 0.25).toFixed(1);
  const lab = q === null ? 'route not joined' : `QBER ${pct(q)}${test ? `, measured ${pct((test.qber_z + test.qber_x) / 2)}` : ''}, limit 11 percent`;
  let s = `<svg class="barsvg" style="width:220px" viewBox="0 0 220 30" role="img" aria-label="${lab}">` +
    `<rect x="4" y="6" width="212" height="6" style="fill:var(--rule)"/>` +
    [0, 0.05, 0.1, 0.15, 0.2, 0.25].map((v) => `<text x="${X(v)}" y="27" text-anchor="middle">${Math.round(v * 100)}</text>`).join('') + `<text x="216" y="3" text-anchor="end">QBER (%)</text>` +
    `<line x1="${X(QBER_LINE)}" x2="${X(QBER_LINE)}" y1="0" y2="18" style="stroke:var(--third)" stroke-width="2"/>`;
  if (q !== null) s += `<rect x="4" y="6" width="${(X(q) - 4).toFixed(1)}" height="6" style="fill:${q < QBER_LINE ? 'var(--quantum)' : 'var(--err)'}"/>`;
  if (test) {
    const m = (test.qber_z + test.qber_x) / 2, sd = Math.sqrt(Math.max(m * (1 - m), 1 / test.n) / (2 * test.n));
    s += `<line x1="${X(m - sd)}" x2="${X(m + sd)}" y1="9" y2="9" style="stroke:var(--ink)" stroke-width="1.5"/>` +
      `<line x1="${X(m)}" x2="${X(m)}" y1="3" y2="15" style="stroke:var(--ink)" stroke-width="2"/>`;
  }
  return s + '</svg>';
}

function renderLog() {
  if (!S.log.length) { $('log').innerHTML = '<p class="note">No operations yet.</p>'; return; }
  const BX = (v) => (4 + 132 * (Math.min(1, Math.max(0.5, v)) - 0.5) / 0.5).toFixed(1);
  const scale = `<svg class="barsvg" viewBox="0 0 140 18" aria-hidden="true">${[0.5, 0.75, 1].map((v) =>
    `<text x="${BX(v)}" y="12" text-anchor="middle">${v}</text>`).join('')}</svg>`;
  const rows = S.log.slice().reverse().map((e) => {
    const m = e.measured;
    let bar = '', meas = '<td class="miss">not run</td>', pm = '<td class="miss">-</td>';
    if (m) {
      const n = m.kept ?? m.n;
      const sd = Math.sqrt(Math.max(m.F * (1 - m.F), 1 / n) / n);
      const lo = m.F - sd, hi = m.F + sd;
      bar = `<svg class="barsvg" viewBox="0 0 140 18" role="img" aria-label="measured ${f3(m.F)} plus or minus ${f3(sd)}, predicted ${f3(e.F)}">` +
        `<line x1="${BX(0.5)}" x2="${BX(1)}" y1="9" y2="9" style="stroke:var(--rule)" stroke-width="6"/>` +
        `<line x1="${BX(0.5)}" x2="${BX(m.F)}" y1="9" y2="9" style="stroke:var(--quantum)" stroke-width="6"/>` +
        `<line x1="${BX(lo)}" x2="${BX(hi)}" y1="9" y2="9" style="stroke:var(--ink)" stroke-width="1.5"/>` +
        `<line x1="${BX(lo)}" x2="${BX(lo)}" y1="6" y2="12" style="stroke:var(--ink)" stroke-width="1.5"/>` +
        `<line x1="${BX(hi)}" x2="${BX(hi)}" y1="6" y2="12" style="stroke:var(--ink)" stroke-width="1.5"/>` +
        `<line x1="${BX(e.F)}" x2="${BX(e.F)}" y1="1" y2="17" style="stroke:var(--third)" stroke-width="2"/></svg>`;
      meas = `<td>${f3(m.F)} &plusmn; ${f3(sd)}</td>`;
      pm = e.kind === 'purify' ? `<td>${f3(m.p)}</td>` : '<td class="miss">-</td>';
    } else if (e.pending) {
      meas = '<td class="miss">running...</td>';
    } else if (e.note) {
      meas = `<td class="miss">${e.note}</td>`;
    }
    const pe = e.kind === 'purify' ? f3(e.p) : '-';
    return `<tr><td>${e.step}</td><td class="op">${e.label}${e.applied ? ' (measured)' : ''}</td><td>${f3(e.F1)}${e.F2 !== undefined ? ', ' + f3(e.F2) : ''}</td>` +
      `<td>${f3(e.F)}</td>${meas}<td>${pe}</td>${pm}<td class="barcell">${bar}</td></tr>`;
  }).join('');
  $('log').innerHTML = `<table><tr><th>#</th><th class="op">operation</th><th>input <i>F</i></th><th><abbr title="Output fidelity from Eq. (2) or (3)">Eq. <i>F</i></abbr></th>` +
    `<th>measured <i>F</i></th><th><abbr title="Probability the purification check passes, Eq. (3)">Eq. <i>p</i></abbr></th><th>measured <i>p</i></th><th class="barcell">${scale}</th></tr>${rows}</table>`;
}

async function runCircuit(entry, kind, F1, F2) {
  if (S.ionqUsed) {
    entry.note = 'IonQ: one job per run';
    setStatus('The model was updated; no circuit was run because the IonQ job for this run was already used.');
    entry.pending = false;
    return;
  }
  entry.pending = true;
  renderLog();
  try {
    const r = JSON.parse(String(await app.measure.callPromising(backend, kind, F1, F2 ?? null)));
    entry.measured = r;
    S.ranOnce = true;
    if (r.ionq) S.ionqUsed = true;
    $('circuit').textContent = r.drawing;
    $('circNote').textContent = `${r.qubits} qubits, depth ${r.depth}, ${r.cx} CX after transpiling, ${r.shots} shots on ${r.backend}, ${r.seconds.toFixed(2)} s.`;
    $('shots').textContent = r.shots;
    console.log(`${kind}: measured ${JSON.stringify({ F: r.F, p: r.p, qber_z: r.qber_z, qber_x: r.qber_x })}`);
  } catch (e) {
    console.log('circuit error: ' + e);
    entry.error = String(e);
    entry.note = 'circuit failed';
    setStatus('Circuit failed; the link uses the formula result: ' + entry.error, true);
  } finally {
    entry.pending = false;
  }
}

async function move(kind, i) {
  if (S.busy) return;
  S.busy = true;
  S.keyTest = null;
  try {
    const L1 = S.links[i];
    const L2 = kind === 'swap' ? S.links[i + 1] : L1;
    const ex = JSON.parse(String(await app.exact.callPromising(kind, L1.F, L2.F)));

    const el = kind === 'swap' ? document.querySelectorAll('#route .station')[i] : document.querySelectorAll('#route .link')[i];
    if (el && $('app').classList.contains('art')) {
      setStatus(kind === 'swap' ? `Swapping at ${cityName(L1.b)}...` : `Purifying ${cityName(L1.a)}-${cityName(L1.b)}...`);
      el.classList.add(kind === 'swap' ? 'joining' : 'purifying');
      if (kind === 'purify') el.insertAdjacentHTML('beforeend', '<span class="fx" aria-hidden="true"></span>');
      await sleep(kind === 'swap' ? 650 : 1000);
    }
    snapshot();
    const label = kind === 'swap'
      ? `swap at ${cityName(L1.b)}`
      : `purify ${cityName(L1.a)}-${cityName(L1.b)}`;
    const entry = { step: S.log.length + 1, kind, label, F1: L1.F, F2: L2.F, F: ex.F, p: ex.p };
    S.log.push(entry);
    if (kind === 'swap') {
      S.links.splice(i, 2, { a: L1.a, b: L2.b, F: ex.F, E: L1.E + L2.E, D: L1.D.concat(L2.D) });
    } else {
      S.links.splice(i, 1, { a: L1.a, b: L1.b, F: ex.F, E: (2 * L1.E) / ex.p, D: L1.D.map((d) => (2 * d) / ex.p) });
    }
    setStatus(`${label}: F = ${f3(ex.F)}${kind === 'purify' ? `, p = ${f3(ex.p)}` : ''}. Running circuit...`);
    render();
    await runCircuit(entry, kind, L1.F, L2.F);
    if (entry.measured) {
      if (S.useMeasured && !entry.measured.ionq) {
        const idx = S.links.findIndex((l) => l.a === L1.a && l.b === (kind === 'swap' ? L2.b : L1.b));
        if (idx >= 0) {
          S.links[idx].F = entry.measured.F;
          if (kind === 'purify') { const pm = Math.max(entry.measured.p, 1e-6); S.links[idx].E = (2 * L1.E) / pm; S.links[idx].D = L1.D.map((d) => (2 * d) / pm); }
          entry.applied = true;
        }
      }
      setStatus(`${label}: F = ${f3(ex.F)} (Eq.), ${f3(entry.measured.F)} (measured${entry.applied ? ', applied' : ''}).`);
    }
  } catch (err) {
    setStatus(`Could not complete the ${kind}: ${err && err.message ? err.message : err}. Press U to undo if the route changed.`);
  } finally {
    S.busy = false;
    render();
    const target = document.querySelector(`#route button[data-act="${kind}"][data-i="${Math.min(i, S.links.length - 1 - (kind === 'swap' ? 1 : 0))}"]`)
      || document.querySelector('#route button[data-act="purify"]');
    if (target) target.focus();
    const done = S.links.length === 1 && qberOf(S.links[0].F) < QBER_LINE;
    if (done && S.log[S.log.length - 1]?.measured) setStatus(`Route joined: QBER ${pct(qberOf(S.links[0].F))}.`);
  }
}

async function testKey() {
  if (S.busy || S.links.length !== 1) return;
  S.busy = true;
  render();
  const F = S.links[0].F;
  setStatus('Measuring QBER in Z and X...');
  try {
    if (S.ionqUsed) throw new Error('one job per run');
    const r = JSON.parse(String(await app.measure.callPromising(backend, 'key', F, null)));
    if (r.ionq) S.ionqUsed = true;
    S.ranOnce = true;
    S.keyTest = r;
    $('circuit').textContent = r.drawing;
    $('circNote').textContent = `QBER: ${r.qubits} qubits, two copies of the delivered pair measured in Z and X; ${r.shots} shots on ${r.backend}.`;
    const m = (r.qber_z + r.qber_x) / 2;
    const q = qberOf(F);
    const ok = q < QBER_LINE;
    $('sKey').textContent = `Verdict from the model QBER = ${pct(q)} (Eq. 4), not the sample: ${ok ? 'secret key possible' : 'no secret key'}. Sample over ${r.shots} shots: Z ${pct(r.qber_z)}, X ${pct(r.qber_x)}; 1-sigma ${pct(Math.sqrt(q * (1 - q) / (2 * r.shots)))}.`;
    setStatus('QBER measured.');
  } catch (e) {
    console.log('key error: ' + e);
    setStatus(S.ionqUsed ? 'The IonQ job for this run was already used. Stop and Run to measure again.' : 'The QBER circuit did not run: ' + e, true);
  } finally {
    S.busy = false;
    render();
  }
}

function undo() {
  if (S.busy || !S.history.length) return;
  const prev = JSON.parse(S.history.pop());
  S.links = prev.links;
  S.log = prev.log;
  S.keyTest = null;
  $('circuit').textContent = 'No circuit yet.';
  $('circNote').textContent = '';
  render();
  setStatus('Undone.');
}

$('route').addEventListener('click', (e) => {
  const b = e.target.closest('button[data-act]');
  if (b) move(b.dataset.act, +b.dataset.i);
});
document.querySelectorAll('#app .preset').forEach((b) => b.addEventListener('click', () => { if (!S.busy && S.cfg) newRoute(+b.dataset.n); }));
document.querySelectorAll('#app .f0').forEach((b) => b.addEventListener('click', () => { if (!S.busy && S.cfg) { S.F0 = +b.dataset.f0; newRoute(S.n); } }));
$('useMeasured').addEventListener('change', (e) => { S.useMeasured = e.target.checked; setStatus(S.useMeasured ? 'Measured mode: links take F from the circuit (local simulators).' : 'Links follow Eqs. (2) and (3).'); });
$('still').addEventListener('change', (e) => { $('app').classList.toggle('still', e.target.checked); setStatus(e.target.checked ? 'Animations paused.' : 'Animations on.'); });
$('undo').addEventListener('click', undo);
$('reset').addEventListener('click', () => { if (!S.busy) newRoute(S.n); });
$('key').addEventListener('click', testKey);
document.addEventListener('keydown', (e) => {
  if (!S.cfg || e.target.closest('input, textarea') || e.metaKey || e.ctrlKey || e.altKey) return;
  const k = e.key.toLowerCase();
  if (['1', '2', '3', '4'].includes(k) && !S.busy) newRoute([1, 2, 4, 8][+k - 1]);
  else if (k === 'p') { $('still').checked = !$('still').checked; $('still').dispatchEvent(new Event('change')); }
  else if (k === 'u') undo();
  else if (k === 'f' && !S.busy) { const c = S.cfg.F0_choices; S.F0 = c[(c.indexOf(S.F0) + 1) % c.length]; newRoute(S.n); }
  else if (k === 'm' && !S.busy) { $('useMeasured').checked = !$('useMeasured').checked; $('useMeasured').dispatchEvent(new Event('change')); }
  else if (k === 'r' && !S.busy) newRoute(S.n);
  else if (k === 'k') testKey();
});

import('https://cdn.jsdelivr.net/npm/katex@0.16.11/+esm').then(({ default: katex }) => {
  document.querySelectorAll('#app .eq[data-tex]').forEach((el) => {
    try { katex.render(el.dataset.tex, el.firstElementChild, { displayMode: true, throwOnError: false, output: 'htmlAndMathml' }); } catch (e) {  }
  });
  document.querySelectorAll('#app .m[data-tex]').forEach((el) => {
    try { katex.render(el.dataset.tex, el, { displayMode: false, throwOnError: false, output: 'htmlAndMathml' }); } catch (e) {  }
  });
}).catch(() => {});

$('route').classList.add('loading');
tipify();
try {
  const t0 = performance.now();
  S.cfg = JSON.parse(String(await app.setup.callPromising()));
  console.log(`Repeater Run ready in ${((performance.now() - t0) / 1000).toFixed(1)} s. Backend: ${backend?.name ?? backend}`);
  await loadArt();
  newRoute(4);
  setStatus('Ready.');
} catch (e) {
  console.log('setup error: ' + e);
  $('route').classList.remove('loading');
  setStatus('Could not load the physics module: ' + e + '. Press Run again.', true);
}
