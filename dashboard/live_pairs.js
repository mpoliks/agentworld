/*
 * dashboard/live_pairs.js — trade tape + living grid (V2 S5).
 *
 * Two views over the per-step `pair_samples` stream. Both subscribe to
 * `applyStep(step)` calls from `live.html` and render whatever they need.
 *
 * - `createTape(host)`: vertical scrolling log of recent pairs.
 *   Capped to a fixed scrollback so it does not grow without bound.
 * - `createGrid(host)`: SVG grid with 12 sector columns; each sampled
 *   pair flashes two slots (one per sector endpoint) plus an arc between
 *   them. Colour by pair type.
 *
 * Both factories return `{ applyStep(step), reset() }`.
 */
(function () {
  'use strict';

  // Sectors are defined in `engine/core/population.py` SECTOR_NAMES.
  // Order matters: column index = sector index.
  const SECTOR_NAMES = [
    'agriculture', 'extraction', 'manufacturing', 'energy',
    'logistics', 'construction', 'retail', 'finance',
    'information', 'health', 'education', 'leisure',
  ];
  const N_SECTORS = SECTOR_NAMES.length;

  const STYLE = `
    .lp-tape { font-family: var(--mono); font-size: 11px; line-height: 1.55; color: var(--text-2); background: var(--panel); border: 1px solid var(--border); border-radius: 3px; height: 480px; overflow-y: auto; padding: 8px 10px; }
    .lp-tape-row { display: grid; grid-template-columns: 48px 60px 1fr 110px 120px; gap: 10px; padding: 2px 0; border-bottom: 1px dotted var(--border); }
    .lp-tape-row.executed { color: var(--text); }
    .lp-tape-row.executed .lp-result { color: var(--green); }
    .lp-tape-row.rejected { color: var(--text-3); }
    .lp-tape-row.rejected .lp-result { color: var(--red); }
    .lp-tape-row .lp-step { color: var(--text-3); }
    .lp-tape-row .lp-type { color: var(--accent); }
    .lp-tape-row.t-hh .lp-type { color: var(--green); }
    .lp-tape-row.t-ha .lp-type { color: var(--accent); }
    .lp-tape-row.t-aa .lp-type { color: var(--blue); }
    .lp-controls { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; font-family: var(--mono); font-size: 11px; color: var(--text-3); }
    .lp-chip { padding: 4px 10px; background: var(--panel); border: 1px solid var(--border); border-radius: 3px; cursor: pointer; color: var(--text-2); user-select: none; }
    .lp-chip.active { background: var(--accent); color: #1a1208; border-color: var(--accent); }
    .lp-status { margin-left: auto; color: var(--text-3); font-size: 10px; }

    .lp-grid-host { background: var(--panel); border: 1px solid var(--border); border-radius: 3px; padding: 12px 16px; }
    .lp-grid-svg { width: 100%; height: 460px; display: block; }
    .lp-grid-svg .col-bg { fill: var(--panel-2); stroke: var(--border); stroke-width: 1; }
    .lp-grid-svg .col-label { fill: var(--text-3); font-family: var(--mono); font-size: 9px; text-transform: uppercase; letter-spacing: 0.06em; }
    .lp-grid-svg .slot { fill: var(--text-3); }
    .lp-grid-svg .arc { fill: none; stroke-opacity: 0.4; }
    .lp-grid-legend { display: flex; gap: 16px; font-family: var(--mono); font-size: 10px; color: var(--text-3); margin-top: 8px; }
    .lp-grid-legend .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 50%; vertical-align: middle; margin-right: 4px; }
  `;

  function ensureStyle() {
    if (!document.querySelector('style[data-lp]')) {
      const s = document.createElement('style');
      s.setAttribute('data-lp', '1');
      s.textContent = STYLE;
      document.head.appendChild(s);
    }
  }

  function pairTypeKey(rec) {
    if (rec.is_a_human && rec.is_b_human) return 'hh';
    if (!rec.is_a_human && !rec.is_b_human) return 'aa';
    return 'ha';
  }
  function pairTypeGlyph(rec) {
    if (rec.is_a_human && rec.is_b_human) return 'H↔H';
    if (!rec.is_a_human && !rec.is_b_human) return 'A↔A';
    return 'H↔A';
  }
  function pairTypeColor(rec) {
    if (rec.is_a_human && rec.is_b_human) return 'var(--green)';
    if (!rec.is_a_human && !rec.is_b_human) return 'var(--blue)';
    return 'var(--accent)';
  }

  function fmt(v, d) { return (Number.isFinite(v) ? v.toFixed(d) : '—'); }

  // ---- TAPE ---------------------------------------------------------------

  function createTape(host) {
    ensureStyle();
    host.innerHTML = '';
    const wrap = document.createElement('div');
    host.appendChild(wrap);

    const controls = document.createElement('div');
    controls.className = 'lp-controls';
    const allChip = makeChip('all', true);
    const exChip = makeChip('executed only', false);
    const rejChip = makeChip('rejected only', false);
    const hhChip = makeChip('H↔H', false);
    const haChip = makeChip('H↔A', false);
    const aaChip = makeChip('A↔A', false);
    const status = document.createElement('span');
    status.className = 'lp-status';
    status.textContent = 'waiting for run…';
    controls.appendChild(allChip);
    controls.appendChild(exChip);
    controls.appendChild(rejChip);
    controls.appendChild(hhChip);
    controls.appendChild(haChip);
    controls.appendChild(aaChip);
    controls.appendChild(status);
    wrap.appendChild(controls);

    const tape = document.createElement('div');
    tape.className = 'lp-tape';
    wrap.appendChild(tape);

    const filters = {
      executed: null, // null = all
      type: null,     // null = all, otherwise 'hh' | 'ha' | 'aa'
    };

    function makeChip(label, active) {
      const c = document.createElement('span');
      c.className = 'lp-chip' + (active ? ' active' : '');
      c.textContent = label;
      return c;
    }
    function setChipState(updater) {
      [allChip, exChip, rejChip].forEach((c) => c.classList.remove('active'));
      [hhChip, haChip, aaChip].forEach((c) => c.classList.remove('active'));
      updater();
    }
    allChip.addEventListener('click', () => {
      filters.executed = null;
      setChipState(() => allChip.classList.add('active'));
      paintAll();
    });
    exChip.addEventListener('click', () => {
      filters.executed = true;
      setChipState(() => exChip.classList.add('active'));
      paintAll();
    });
    rejChip.addEventListener('click', () => {
      filters.executed = false;
      setChipState(() => rejChip.classList.add('active'));
      paintAll();
    });
    function toggleType(chip, key) {
      if (filters.type === key) {
        filters.type = null;
        chip.classList.remove('active');
      } else {
        [hhChip, haChip, aaChip].forEach((c) => c.classList.remove('active'));
        filters.type = key;
        chip.classList.add('active');
      }
      paintAll();
    }
    hhChip.addEventListener('click', () => toggleType(hhChip, 'hh'));
    haChip.addEventListener('click', () => toggleType(haChip, 'ha'));
    aaChip.addEventListener('click', () => toggleType(aaChip, 'aa'));

    const MAX_ROWS = 600;        // cap scrollback
    const recordsBuf = [];       // newest-last circular buffer

    function passesFilter(rec) {
      if (filters.executed !== null && rec.executed !== filters.executed) return false;
      if (filters.type !== null && pairTypeKey(rec) !== filters.type) return false;
      return true;
    }

    function buildRow(step, rec) {
      const row = document.createElement('div');
      const typeKey = pairTypeKey(rec);
      row.className = `lp-tape-row t-${typeKey} ${rec.executed ? 'executed' : 'rejected'}`;
      const stepEl = document.createElement('span'); stepEl.className = 'lp-step'; stepEl.textContent = `t${step}`;
      const typeEl = document.createElement('span'); typeEl.className = 'lp-type'; typeEl.textContent = pairTypeGlyph(rec);
      const secEl = document.createElement('span'); secEl.textContent = `${SECTOR_NAMES[rec.sec_a]} → ${SECTOR_NAMES[rec.sec_b]}`;
      const fricEl = document.createElement('span'); fricEl.textContent = `s=${fmt(rec.base_surplus, 3)} ƒ=${fmt(rec.friction, 3)}`;
      const resEl = document.createElement('span'); resEl.className = 'lp-result';
      if (rec.executed) {
        resEl.textContent = `+${fmt(rec.real_surplus, 3)}`;
      } else {
        resEl.textContent = `✕ ${rec.reject_reason || '?'}`;
      }
      row.appendChild(stepEl);
      row.appendChild(typeEl);
      row.appendChild(secEl);
      row.appendChild(fricEl);
      row.appendChild(resEl);
      return row;
    }

    function paintAll() {
      tape.innerHTML = '';
      // Render newest-first (reversed buffer iteration).
      for (let i = recordsBuf.length - 1; i >= 0; i -= 1) {
        const { step, rec } = recordsBuf[i];
        if (!passesFilter(rec)) continue;
        tape.appendChild(buildRow(step, rec));
      }
    }

    function applyStep(step) {
      const pairs = step.pair_samples || [];
      if (!pairs.length) return;
      // Newest pairs go to the head of the tape; we render newest-first by
      // iterating recordsBuf in reverse, so push in order here.
      for (const rec of pairs) {
        recordsBuf.push({ step: step.step, rec });
      }
      // Trim from the head when oversized.
      if (recordsBuf.length > MAX_ROWS) {
        recordsBuf.splice(0, recordsBuf.length - MAX_ROWS);
      }
      status.textContent = `step ${step.step} · ${pairs.length} new · ${recordsBuf.length}/${MAX_ROWS} buffered`;
      paintAll();
      tape.scrollTop = 0;
    }

    function reset() {
      recordsBuf.length = 0;
      tape.innerHTML = '';
      status.textContent = 'waiting for run…';
    }

    return { applyStep, reset };
  }

  // ---- GRID ---------------------------------------------------------------

  function createGrid(host) {
    ensureStyle();
    host.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'lp-grid-host';
    host.appendChild(wrap);

    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'lp-grid-svg');
    svg.setAttribute('viewBox', '0 0 960 460');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    wrap.appendChild(svg);

    const W = 960, H = 460;
    const TOP_PAD = 28;          // headroom for column labels
    const BOTTOM_PAD = 16;
    const SIDE_PAD = 12;
    const COL_W = (W - 2 * SIDE_PAD) / N_SECTORS;
    const SLOT_ROWS = 40;
    const SLOT_R = 3;
    const COL_INNER_PAD = 6;
    const slotsHost = document.createElementNS(NS, 'g');
    const arcsHost = document.createElementNS(NS, 'g');
    svg.appendChild(slotsHost);
    svg.appendChild(arcsHost);

    // Column backgrounds + labels.
    for (let s = 0; s < N_SECTORS; s += 1) {
      const x = SIDE_PAD + s * COL_W;
      const bg = document.createElementNS(NS, 'rect');
      bg.setAttribute('class', 'col-bg');
      bg.setAttribute('x', x + COL_INNER_PAD / 2);
      bg.setAttribute('y', TOP_PAD);
      bg.setAttribute('width', COL_W - COL_INNER_PAD);
      bg.setAttribute('height', H - TOP_PAD - BOTTOM_PAD);
      bg.setAttribute('rx', 2);
      svg.appendChild(bg);
      const lbl = document.createElementNS(NS, 'text');
      lbl.setAttribute('class', 'col-label');
      lbl.setAttribute('x', x + COL_W / 2);
      lbl.setAttribute('y', 18);
      lbl.setAttribute('text-anchor', 'middle');
      lbl.textContent = SECTOR_NAMES[s].slice(0, 4);
      svg.appendChild(lbl);
    }

    // Pre-place SLOT_ROWS dots per column.
    const slotEls = [];          // [sector][row] → circle element
    for (let s = 0; s < N_SECTORS; s += 1) {
      slotEls.push([]);
      const x = SIDE_PAD + s * COL_W + COL_W / 2;
      const colTop = TOP_PAD + 10;
      const colBot = H - BOTTOM_PAD - 6;
      const step = (colBot - colTop) / (SLOT_ROWS - 1);
      for (let r = 0; r < SLOT_ROWS; r += 1) {
        const c = document.createElementNS(NS, 'circle');
        c.setAttribute('class', 'slot');
        c.setAttribute('cx', x);
        c.setAttribute('cy', colTop + r * step);
        c.setAttribute('r', SLOT_R);
        slotsHost.appendChild(c);
        slotEls[s].push(c);
      }
    }

    function slotXY(sec, slotIdx) {
      const x = SIDE_PAD + sec * COL_W + COL_W / 2;
      const colTop = TOP_PAD + 10;
      const colBot = H - BOTTOM_PAD - 6;
      const stepY = (colBot - colTop) / (SLOT_ROWS - 1);
      return { x, y: colTop + slotIdx * stepY };
    }

    function colorForPair(rec) { return pairTypeColor(rec); }

    function flash(sec, slotIdx, color) {
      const el = slotEls[sec][slotIdx];
      if (!el) return;
      el.setAttribute('fill', color);
      el.setAttribute('r', SLOT_R + 2);
      // CSS-free fade: schedule an attribute reset.
      setTimeout(() => {
        if (!el.isConnected) return;
        el.setAttribute('fill', 'var(--text-3)');
        el.setAttribute('r', SLOT_R);
      }, 900);
    }

    function drawArc(sec_a, slot_a, sec_b, slot_b, color) {
      const p1 = slotXY(sec_a, slot_a);
      const p2 = slotXY(sec_b, slot_b);
      const path = document.createElementNS(NS, 'path');
      const mx = (p1.x + p2.x) / 2;
      const my = Math.min(p1.y, p2.y) - 30;
      path.setAttribute('class', 'arc');
      path.setAttribute('d', `M${p1.x},${p1.y} Q${mx},${my} ${p2.x},${p2.y}`);
      path.setAttribute('stroke', color);
      path.setAttribute('stroke-width', '1.2');
      arcsHost.appendChild(path);
      setTimeout(() => { if (path.isConnected) path.remove(); }, 1100);
    }

    function applyStep(step) {
      const pairs = step.pair_samples || [];
      for (const rec of pairs) {
        const slotA = (rec.proto_a >>> 0) % SLOT_ROWS;
        const slotB = (rec.proto_b >>> 0) % SLOT_ROWS;
        const color = colorForPair(rec);
        // Rejected pairs render dimmer (no arc) so the visual reads as
        // "this happened, but it died at the gate."
        if (rec.executed) {
          drawArc(rec.sec_a, slotA, rec.sec_b, slotB, color);
        }
        flash(rec.sec_a, slotA, color);
        flash(rec.sec_b, slotB, color);
      }
    }

    function reset() {
      while (arcsHost.firstChild) arcsHost.removeChild(arcsHost.firstChild);
      slotEls.flat().forEach((el) => {
        el.setAttribute('fill', 'var(--text-3)');
        el.setAttribute('r', SLOT_R);
      });
    }

    // Legend below the SVG.
    const legend = document.createElement('div');
    legend.className = 'lp-grid-legend';
    legend.innerHTML = `
      <span><span class="swatch" style="background: var(--green);"></span> H↔H</span>
      <span><span class="swatch" style="background: var(--accent);"></span> H↔A</span>
      <span><span class="swatch" style="background: var(--blue);"></span> A↔A</span>
      <span style="margin-left: auto; color: var(--text-3);">arc = executed · dim flash = rejected</span>
    `;
    wrap.appendChild(legend);

    return { applyStep, reset };
  }

  window.createTape = createTape;
  window.createGrid = createGrid;
  window.LP_SECTOR_NAMES = SECTOR_NAMES;
})();
