/*
 * dashboard/live_sector_chord.js — sector chord diagram (V2 S6).
 *
 * Same per-pair stream as the tape and grid. Each sampled executed
 * pair contributes to a 12×12 matrix M[sec_a][sec_b]; the chord
 * renders sectors as arcs around a circle and ribbons whose thickness
 * encodes the matrix entry. Two modes:
 *
 *  - **per-step**: M is zeroed each step and re-filled from this step's
 *    K pairs. Ribbons pulse — fast, but the chord can be jittery.
 *  - **cumulative**: M accumulates across all steps. Ribbons grow.
 *    The structure of who-trades-with-whom emerges slowly.
 *
 * Volume metric = sum of `base_surplus × pair_weight` over executed
 * pairs in (sec_a, sec_b). Rejected pairs are excluded — the chord is
 * a *cleared trade* view, the tape and grid carry the rejected detail.
 *
 * `window.createSectorChord(host) → { applyStep(step), reset() }`.
 *
 * Uses d3 v7 (already loaded by live.html).
 */
(function () {
  'use strict';

  const SECTOR_NAMES = (window.LP_SECTOR_NAMES || [
    'agriculture', 'extraction', 'manufacturing', 'energy',
    'logistics', 'construction', 'retail', 'finance',
    'information', 'health', 'education', 'leisure',
  ]);
  const N = SECTOR_NAMES.length;

  const STYLE = `
    .lp-chord-host { background: var(--panel); border: 1px solid var(--border); border-radius: 3px; padding: 12px 16px; }
    .lp-chord-controls { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; font-family: var(--mono); font-size: 11px; color: var(--text-3); }
    .lp-chord-chip { padding: 4px 10px; background: var(--panel-2); border: 1px solid var(--border); border-radius: 3px; cursor: pointer; color: var(--text-2); user-select: none; }
    .lp-chord-chip.active { background: var(--accent); color: #1a1208; border-color: var(--accent); }
    .lp-chord-status { margin-left: auto; color: var(--text-3); font-size: 10px; }
    .lp-chord-svg { width: 100%; height: 540px; display: block; }
    .lp-chord-svg .arc-label { fill: var(--text-2); font-family: var(--mono); font-size: 10px; }
    .lp-chord-svg .arc { stroke: var(--bg); stroke-width: 1; }
    .lp-chord-svg .ribbon { fill-opacity: 0.55; stroke: var(--bg); stroke-width: 0.5; }
    .lp-chord-svg .ribbon:hover { fill-opacity: 0.95; }
  `;

  function ensureStyle() {
    if (!document.querySelector('style[data-lp-chord]')) {
      const s = document.createElement('style');
      s.setAttribute('data-lp-chord', '1');
      s.textContent = STYLE;
      document.head.appendChild(s);
    }
  }

  function sectorColor(i) {
    // d3.interpolateRainbow gives distinct hues across 12 sectors;
    // we shift the start so finance/information land on cooler hues.
    if (typeof d3 !== 'undefined' && d3.interpolateRainbow) {
      return d3.interpolateRainbow((i + 0.5) / N);
    }
    // Fallback if d3 isn't loaded for some reason.
    const palette = ['#b89a55', '#5fa572', '#c25a5a', '#5b8ec4', '#9077c2',
                     '#d99b6b', '#7caec1', '#a3a85a', '#bd6fa6', '#6cb39e',
                     '#c0795a', '#8e9aa8'];
    return palette[i % palette.length];
  }

  function createSectorChord(host) {
    ensureStyle();
    host.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'lp-chord-host';
    host.appendChild(wrap);

    const controls = document.createElement('div');
    controls.className = 'lp-chord-controls';
    // Default to per-step so first-time users see ribbons pulse with
    // step-by-step volume; cumulative is one chip-click away when the
    // user wants the slowly-growing structural pattern.
    const perStepChip = makeChip('per step', true);
    const cumulativeChip = makeChip('cumulative', false);
    const status = document.createElement('span');
    status.className = 'lp-chord-status';
    status.textContent = 'waiting for run…';
    controls.appendChild(perStepChip);
    controls.appendChild(cumulativeChip);
    controls.appendChild(status);
    wrap.appendChild(controls);

    function makeChip(label, active) {
      const c = document.createElement('span');
      c.className = 'lp-chord-chip' + (active ? ' active' : '');
      c.textContent = label;
      return c;
    }

    let mode = 'per-step';
    perStepChip.addEventListener('click', () => {
      mode = 'per-step';
      perStepChip.classList.add('active');
      cumulativeChip.classList.remove('active');
      // Don't wipe cumulative on toggle — let it sit; per-step will
      // overwrite from the next step's samples.
    });
    cumulativeChip.addEventListener('click', () => {
      mode = 'cumulative';
      cumulativeChip.classList.add('active');
      perStepChip.classList.remove('active');
    });

    if (typeof d3 === 'undefined') {
      const err = document.createElement('p');
      err.style.color = 'var(--red)';
      err.textContent = 'd3 v7 not loaded — sector chord unavailable.';
      wrap.appendChild(err);
      return { applyStep: () => {}, reset: () => {} };
    }

    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'lp-chord-svg');
    svg.setAttribute('viewBox', '0 0 600 540');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    wrap.appendChild(svg);

    const W = 600, H = 540;
    const rOut = 200;
    const rIn = rOut - 18;
    const cx = W / 2;
    const cy = H / 2 + 10;

    const root = d3.select(svg).append('g').attr('transform', `translate(${cx},${cy})`);

    // Layouts.
    const chord = d3.chord()
      .padAngle(0.04)
      .sortSubgroups(d3.descending);
    const arcGen = d3.arc().innerRadius(rIn).outerRadius(rOut);
    const ribbonGen = d3.ribbon().radius(rIn - 2);

    // Cumulative state.
    let matrix = Array.from({ length: N }, () => Array(N).fill(0));
    let totalVolume = 0;
    let stepCount = 0;

    function zeroMatrix() {
      return Array.from({ length: N }, () => Array(N).fill(0));
    }

    function applyStep(step) {
      const pairs = step.pair_samples || [];
      if (mode === 'per-step') {
        matrix = zeroMatrix();
      }
      let stepVolume = 0;
      for (const rec of pairs) {
        if (!rec.executed) continue;
        const w = (rec.base_surplus || 0) * (rec.pair_weight || 1);
        if (w <= 0) continue;
        matrix[rec.sec_a][rec.sec_b] += w;
        // Symmetric add — the chord is undirected at the sector level.
        if (rec.sec_a !== rec.sec_b) {
          matrix[rec.sec_b][rec.sec_a] += w * 0.5;
          matrix[rec.sec_a][rec.sec_b] -= 0;  // (left as-is for clarity)
        }
        stepVolume += w;
      }
      stepCount += 1;
      totalVolume += stepVolume;
      status.textContent = (
        mode === 'cumulative'
          ? `${stepCount} steps · cumulative volume ${totalVolume.toFixed(2)}`
          : `step ${step.step} · step volume ${stepVolume.toFixed(2)}`
      );
      redraw();
    }

    function redraw() {
      const chords = chord(matrix);
      // groups: one arc per sector.
      const groupSel = root.selectAll('g.group').data(chords.groups, (d) => d.index);
      groupSel.exit().remove();
      const groupEnter = groupSel.enter().append('g').attr('class', 'group');
      groupEnter.append('path').attr('class', 'arc');
      groupEnter.append('text').attr('class', 'arc-label');
      const groupMerge = groupEnter.merge(groupSel);
      groupMerge.select('path.arc')
        .attr('d', arcGen)
        .attr('fill', (d) => sectorColor(d.index));
      groupMerge.select('text.arc-label')
        .attr('transform', (d) => {
          const a = (d.startAngle + d.endAngle) / 2 - Math.PI / 2;
          const r = rOut + 12;
          return `translate(${Math.cos(a) * r}, ${Math.sin(a) * r})`;
        })
        .attr('text-anchor', (d) => {
          const a = (d.startAngle + d.endAngle) / 2;
          return a > Math.PI ? 'end' : 'start';
        })
        .text((d) => SECTOR_NAMES[d.index]);

      // ribbons.
      const ribbonSel = root.selectAll('path.ribbon').data(
        chords.filter((c) => c.source.value > 0 || c.target.value > 0),
        (d) => `${d.source.index}-${d.target.index}`,
      );
      ribbonSel.exit().remove();
      const ribbonEnter = ribbonSel.enter().append('path').attr('class', 'ribbon');
      ribbonEnter.append('title');
      ribbonEnter.merge(ribbonSel)
        .attr('d', ribbonGen)
        .attr('fill', (d) => sectorColor(d.source.index));
      ribbonEnter.merge(ribbonSel).select('title')
        .text((d) => {
          const i = d.source.index, j = d.target.index;
          return `${SECTOR_NAMES[i]} ↔ ${SECTOR_NAMES[j]}: ${(d.source.value + d.target.value).toFixed(3)}`;
        });
    }

    function reset() {
      matrix = zeroMatrix();
      totalVolume = 0;
      stepCount = 0;
      status.textContent = 'waiting for run…';
      redraw();
    }

    // Initial empty render so the SVG isn't blank before the first step.
    redraw();

    return { applyStep, reset };
  }

  window.createSectorChord = createSectorChord;
})();
