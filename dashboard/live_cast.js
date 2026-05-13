/*
 * dashboard/live_cast.js — Live World (Cockpit Pass 2).
 *
 * Canvas-rendered persistent cast: ~150 prototypes the engine follows
 * from step 0 onward. Each cast member is a dot whose state evolves
 * visibly:
 *   - wealth → dot radius (log-scaled)
 *   - sector → fill colour (sector palette)
 *   - is_human → circle (human) vs rotated square (agent)
 *   - autonomy → outline thickness on agents
 *   - firm membership → dashed hull around co-members
 *
 * Layered on top: animated events derived from the per-pair stream
 * and the cast-snapshot deltas:
 *   - Trades between cast members → arc, colour by pair-type, ~600ms
 *   - Rejected trades on cast members → red flash + reject reason letter
 *   - Firm formation / dissolution → hull appears / fades
 *   - Pigouvian collect (when family is pigouvian) → gold ring on
 *     A2A pairs touching cast members
 *
 * Subscribes to `applyStep(step)` calls from live.html.
 * `window.createLiveCast(host) → { applyStep, reset, dispose }`.
 */
(function () {
  'use strict';

  const SECTOR_NAMES = (window.LP_SECTOR_NAMES || [
    'agriculture', 'extraction', 'manufacturing', 'energy',
    'logistics', 'construction', 'retail', 'finance',
    'information', 'health', 'education', 'leisure',
  ]);
  const N_SECTORS = SECTOR_NAMES.length;

  const STYLE = `
    .lc-host { position: relative; background: #050608; border: 1px solid var(--border); border-radius: 3px; overflow: hidden; }
    .lc-controls { display: flex; gap: 10px; align-items: center; padding: 10px 14px; font-family: var(--mono); font-size: 11px; color: var(--text-3); border-bottom: 1px solid var(--border); background: var(--panel); }
    .lc-status { margin-left: auto; }
    .lc-canvas-wrap { position: relative; height: 600px; }
    .lc-canvas { width: 100%; height: 100%; display: block; }
    .lc-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-family: var(--mono); font-size: 12px; pointer-events: none; }
    .lc-tooltip { position: absolute; background: var(--panel); border: 1px solid var(--accent); border-radius: 3px; padding: 6px 10px; font-family: var(--mono); font-size: 10px; color: var(--text); pointer-events: none; display: none; max-width: 260px; line-height: 1.4; z-index: 5; }
  `;

  function ensureStyle() {
    if (!document.querySelector('style[data-lc]')) {
      const s = document.createElement('style');
      s.setAttribute('data-lc', '1');
      s.textContent = STYLE;
      document.head.appendChild(s);
    }
  }

  function sectorColor(i) {
    if (window.d3 && window.d3.interpolateRainbow) {
      return window.d3.interpolateRainbow((i + 0.5) / N_SECTORS);
    }
    const fallback = [
      '#b89a55', '#5fa572', '#c25a5a', '#5b8ec4',
      '#9077c2', '#d99b6b', '#7caec1', '#a3a85a',
      '#bd6fa6', '#6cb39e', '#c0795a', '#8e9aa8',
    ];
    return fallback[i % fallback.length];
  }

  function pairTypeColor(rec) {
    if (rec.is_a_human && rec.is_b_human) return 'rgba(95,165,114,0.85)';
    if (!rec.is_a_human && !rec.is_b_human) return 'rgba(91,142,196,0.85)';
    return 'rgba(184,154,85,0.85)';
  }

  function rejectColor(reason) {
    if (reason === 'law') return 'rgba(194,90,90,0.9)';
    if (reason === 'permeability') return 'rgba(184,154,85,0.85)';
    if (reason === 'regulator') return 'rgba(144,119,194,0.85)';
    if (reason === 'market') return 'rgba(124,174,193,0.85)';
    if (reason === 'align') return 'rgba(189,111,166,0.85)';
    if (reason === 'cost') return 'rgba(108,179,158,0.85)';
    return 'rgba(158,162,168,0.6)';
  }
  function rejectLetter(reason) {
    return ({ law: 'L', permeability: 'P', regulator: 'R', market: 'M', align: 'N', cost: '$' })[reason] || '?';
  }

  function hashPos(n) {
    // Stable [0, 1) hash for prototype indices.
    let h = (n + 0x9e3779b9) | 0;
    h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b);
    h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35);
    h ^= h >>> 16;
    return (h >>> 0) / 0xffffffff;
  }

  function convexHull(points) {
    // Andrew's monotone chain. points: [{x,y}].
    if (points.length < 3) return points.slice();
    const sorted = points.slice().sort((a, b) => a.x - b.x || a.y - b.y);
    const cross = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
    const lower = [];
    for (const p of sorted) {
      while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
      lower.push(p);
    }
    const upper = [];
    for (let i = sorted.length - 1; i >= 0; i -= 1) {
      const p = sorted[i];
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
      upper.push(p);
    }
    lower.pop(); upper.pop();
    return lower.concat(upper);
  }

  function createLiveCast(host) {
    ensureStyle();
    host.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'lc-host';
    host.appendChild(wrap);

    const controls = document.createElement('div');
    controls.className = 'lc-controls';
    const status = document.createElement('span');
    status.className = 'lc-status';
    status.textContent = 'waiting for cast snapshot…';
    controls.appendChild(document.createTextNode('Live world · persistent cast follows ~150 prototypes from step 0'));
    controls.appendChild(status);
    wrap.appendChild(controls);

    const canvasWrap = document.createElement('div');
    canvasWrap.className = 'lc-canvas-wrap';
    const canvas = document.createElement('canvas');
    canvas.className = 'lc-canvas';
    canvasWrap.appendChild(canvas);
    const empty = document.createElement('div');
    empty.className = 'lc-empty';
    empty.textContent = 'cast appears once the run produces its first snapshot';
    canvasWrap.appendChild(empty);
    const tooltip = document.createElement('div');
    tooltip.className = 'lc-tooltip';
    canvasWrap.appendChild(tooltip);
    wrap.appendChild(canvasWrap);

    const ctx = canvas.getContext('2d');
    function resize() {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth || 960;
      const h = canvas.clientHeight || 600;
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();

    // ---- cast geometry ---------------------------------------------------
    const cast = new Map();         // proto_idx → { sector, isHuman, x, y, wealth, capability, autonomy, firmId, hashPos }
    const trades = [];              // active trade animations
    const rejects = [];             // active reject overlays
    let lastSnapshotStep = -1;
    const TRADE_LIFETIME_MS = 700;
    const REJECT_LIFETIME_MS = 900;

    function castViewport() {
      return { w: canvas.clientWidth || 960, h: canvas.clientHeight || 600 };
    }

    function buildPositions(snapshot) {
      // Sector-organized circular layout: 12 wedges, dots within each.
      const { w, h } = castViewport();
      const cx = w / 2, cy = h / 2;
      const outerR = Math.min(w, h) * 0.36;
      const innerR = outerR - 80;
      // Group cast members by sector.
      const bySector = new Map();
      for (const m of snapshot) {
        if (!bySector.has(m.sector)) bySector.set(m.sector, []);
        bySector.get(m.sector).push(m);
      }
      cast.clear();
      bySector.forEach((members, sec) => {
        // Sort members deterministically by proto_idx so positions are
        // stable across reloads.
        members.sort((a, b) => a.idx - b.idx);
        const startA = (sec / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
        const sweep = (1 / N_SECTORS) * 2 * Math.PI * 0.82;
        members.forEach((m, i) => {
          const t = members.length > 1 ? i / (members.length - 1) : 0.5;
          const r = innerR + (outerR - innerR) * (0.3 + hashPos(m.idx) * 0.65);
          const angle = startA + sweep * (t - 0.5) + (hashPos(m.idx + 1) - 0.5) * 0.05;
          cast.set(m.idx, {
            sector: m.sector,
            isHuman: m.is_human,
            x: cx + r * Math.cos(angle),
            y: cy + r * Math.sin(angle),
            wealth: m.wealth,
            wealthSmooth: m.wealth,
            capability: m.capability,
            autonomy: m.autonomy,
            firmId: m.firm_id,
            firmHullColor: null,
            stack: m.stack,
            idx: m.idx,
          });
        });
      });
    }

    function ingestSnapshot(stepIdx, snapshot) {
      if (cast.size === 0) {
        buildPositions(snapshot);
      } else {
        for (const m of snapshot) {
          const c = cast.get(m.idx);
          if (!c) continue;
          c.wealth = m.wealth;
          c.capability = m.capability;
          c.autonomy = m.autonomy;
          c.firmId = m.firm_id;
        }
      }
      lastSnapshotStep = stepIdx;
    }

    function spawnTrade(p, now) {
      const a = cast.get(p.proto_a);
      const b = cast.get(p.proto_b);
      if (!a && !b) return;
      // Both endpoints in cast = full arc. Only one = ghost arc to
      // the off-canvas sector centroid.
      const aPt = a || sectorGhost(p.sec_a);
      const bPt = b || sectorGhost(p.sec_b);
      if (!aPt || !bPt) return;
      if (p.executed) {
        trades.push({
          ax: aPt.x, ay: aPt.y, bx: bPt.x, by: bPt.y,
          color: pairTypeColor(p), width: 1.2 + Math.log10(p.pair_weight + 1) * 0.5,
          t0: now, dur: TRADE_LIFETIME_MS,
        });
      } else {
        // Rejection: red flash on the cast endpoint(s).
        const reason = p.reject_reason || 'cost';
        if (a) rejects.push({ x: a.x, y: a.y, color: rejectColor(reason), letter: rejectLetter(reason), t0: now });
        if (b) rejects.push({ x: b.x, y: b.y, color: rejectColor(reason), letter: rejectLetter(reason), t0: now });
      }
    }

    function sectorGhost(sec) {
      const { w, h } = castViewport();
      const cx = w / 2, cy = h / 2;
      const outerR = Math.min(w, h) * 0.36 + 40;
      const angle = (sec / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
      return { x: cx + outerR * Math.cos(angle), y: cy + outerR * Math.sin(angle) };
    }

    // ---- render loop ----------------------------------------------------
    let raf;
    function frame() {
      const now = performance.now();
      const { w, h } = castViewport();
      ctx.clearRect(0, 0, w, h);

      // Background: faint sector labels.
      ctx.font = '9px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const cx = w / 2, cy = h / 2;
      const labelR = Math.min(w, h) * 0.36 + 22;
      for (let s = 0; s < N_SECTORS; s += 1) {
        const a = (s / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
        ctx.fillStyle = sectorColor(s);
        ctx.globalAlpha = 0.55;
        ctx.fillText(SECTOR_NAMES[s].toUpperCase(), cx + labelR * Math.cos(a), cy + labelR * Math.sin(a));
      }
      ctx.globalAlpha = 1.0;

      // Smooth wealth lerp toward target for visible growth/shrink.
      cast.forEach((c) => {
        c.wealthSmooth += (c.wealth - c.wealthSmooth) * 0.18;
      });

      // Firm hulls (background layer).
      const firms = new Map();
      cast.forEach((c) => {
        if (c.firmId == null || c.firmId < 0) return;
        if (!firms.has(c.firmId)) firms.set(c.firmId, []);
        firms.get(c.firmId).push(c);
      });
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 3]);
      firms.forEach((members, firmId) => {
        if (members.length < 2) return;
        const hull = convexHull(members.map((m) => ({ x: m.x, y: m.y })));
        if (hull.length < 2) return;
        const col = sectorColor(firmId % N_SECTORS);
        ctx.strokeStyle = col;
        ctx.fillStyle = col + '22';
        ctx.beginPath();
        ctx.moveTo(hull[0].x, hull[0].y);
        for (let i = 1; i < hull.length; i += 1) ctx.lineTo(hull[i].x, hull[i].y);
        ctx.closePath();
        ctx.globalAlpha = 0.4;
        ctx.fill();
        ctx.globalAlpha = 0.7;
        ctx.stroke();
        ctx.globalAlpha = 1.0;
      });
      ctx.setLineDash([]);

      // Trade arcs (foreground over hulls, under dots).
      for (let i = trades.length - 1; i >= 0; i -= 1) {
        const t = trades[i];
        const u = (now - t.t0) / t.dur;
        if (u >= 1) { trades.splice(i, 1); continue; }
        const alpha = 1 - u;
        ctx.strokeStyle = t.color;
        ctx.globalAlpha = alpha;
        ctx.lineWidth = t.width;
        const midX = (t.ax + t.bx) / 2;
        const midY = (t.ay + t.by) / 2;
        // Bend toward the centre so arcs read as inter-sector flow.
        const cx2 = midX + (cx - midX) * 0.35;
        const cy2 = midY + (cy - midY) * 0.35;
        ctx.beginPath();
        ctx.moveTo(t.ax, t.ay);
        ctx.quadraticCurveTo(cx2, cy2, t.bx, t.by);
        ctx.stroke();
      }
      ctx.globalAlpha = 1.0;

      // Reject overlays.
      for (let i = rejects.length - 1; i >= 0; i -= 1) {
        const r = rejects[i];
        const u = (now - r.t0) / REJECT_LIFETIME_MS;
        if (u >= 1) { rejects.splice(i, 1); continue; }
        ctx.globalAlpha = 1 - u;
        ctx.strokeStyle = r.color;
        ctx.lineWidth = 2;
        const sz = 5 + u * 7;
        ctx.beginPath();
        ctx.moveTo(r.x - sz, r.y - sz);
        ctx.lineTo(r.x + sz, r.y + sz);
        ctx.moveTo(r.x + sz, r.y - sz);
        ctx.lineTo(r.x - sz, r.y + sz);
        ctx.stroke();
        ctx.fillStyle = r.color;
        ctx.font = 'bold 9px "JetBrains Mono", monospace';
        ctx.fillText(r.letter, r.x + sz + 6, r.y);
      }
      ctx.globalAlpha = 1.0;

      // Dots (cast).
      cast.forEach((c) => {
        const r = 3 + Math.log10(Math.max(c.wealthSmooth, 0.1)) * 1.6;
        ctx.fillStyle = sectorColor(c.sector);
        if (c.isHuman) {
          ctx.beginPath();
          ctx.arc(c.x, c.y, r, 0, 2 * Math.PI);
          ctx.fill();
          ctx.strokeStyle = 'rgba(231,232,234,0.55)';
          ctx.lineWidth = 1;
          ctx.stroke();
        } else {
          // Square (rotated 45°) for agents, sized similarly.
          const half = r * 0.95;
          ctx.save();
          ctx.translate(c.x, c.y);
          ctx.rotate(Math.PI / 4);
          ctx.fillRect(-half, -half, half * 2, half * 2);
          // Autonomy → outline opacity. Highly autonomous = sharp dark.
          ctx.strokeStyle = `rgba(12,13,16,${0.4 + 0.5 * c.autonomy})`;
          ctx.lineWidth = 1.2;
          ctx.strokeRect(-half, -half, half * 2, half * 2);
          ctx.restore();
        }
      });

      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);

    // ---- hover tooltip --------------------------------------------------
    function pickAt(mx, my) {
      let best = null, bestD = Infinity;
      cast.forEach((c) => {
        const dx = c.x - mx, dy = c.y - my;
        const d = Math.hypot(dx, dy);
        if (d < bestD && d < 14) { bestD = d; best = c; }
      });
      return best;
    }
    canvas.addEventListener('mousemove', (ev) => {
      const rect = canvas.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      const c = pickAt(mx, my);
      if (!c) { tooltip.style.display = 'none'; return; }
      tooltip.innerHTML = `
        <div style="color: ${sectorColor(c.sector)}; font-weight: 600;">${c.isHuman ? 'human' : 'agent'} · proto ${c.idx}</div>
        <div>sector: ${SECTOR_NAMES[c.sector]} · stack ${c.stack}</div>
        <div>wealth: ${c.wealth.toExponential(2)}</div>
        <div>capability: ${c.capability.toFixed(3)}</div>
        <div>autonomy: ${c.autonomy.toFixed(3)}</div>
        <div>firm: ${c.firmId >= 0 ? c.firmId : 'independent'}</div>
      `;
      tooltip.style.left = (mx + 12) + 'px';
      tooltip.style.top = (my + 12) + 'px';
      tooltip.style.display = 'block';
    });
    canvas.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });

    // ---- public API -----------------------------------------------------

    function applyStep(step) {
      if (step.cast_snapshot && step.cast_snapshot.length) {
        empty.style.display = 'none';
        ingestSnapshot(step.step, step.cast_snapshot);
      }
      const pairs = step.pair_samples || [];
      if (pairs.length && cast.size) {
        const now = performance.now();
        for (let i = 0; i < pairs.length; i += 1) {
          const p = pairs[i];
          if (cast.has(p.proto_a) || cast.has(p.proto_b)) {
            spawnTrade(p, now);
          }
        }
      }
      const inFirm = [...cast.values()].filter((c) => c.firmId >= 0).length;
      status.textContent = `step ${lastSnapshotStep} · ${cast.size} cast · ${trades.length} active trades · ${inFirm} in firms`;
    }

    function reset() {
      cast.clear();
      trades.length = 0;
      rejects.length = 0;
      lastSnapshotStep = -1;
      empty.style.display = '';
      status.textContent = 'waiting for cast snapshot…';
    }

    function dispose() {
      cancelAnimationFrame(raf);
      ro.disconnect();
    }

    return { applyStep, reset, dispose };
  }

  window.createLiveCast = createLiveCast;
})();
