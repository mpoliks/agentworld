/*
 * dashboard/live_cast.js — Live World (Cockpit Pass 2, map rebuild).
 *
 * Spatial 2D map. The persistent cast of ~150 prototypes lives on a
 * 4×3 grid of sector regions. Each agent has a position, velocity,
 * and a small force field acting on it:
 *
 *   - **Sector pull** keeps members loosely bound to their region.
 *   - **Trade pull** during an active cast-to-cast trade accelerates
 *     the two agents toward each other; they meet, exchange (small
 *     particle burst), then dampening returns them to their region.
 *   - **Boundary force** keeps agents inside the canvas.
 *   - **Random walk** + dampening so motion stays organic, not jittery.
 *
 * Trades only animate when *both* endpoints are in the cast — the
 * other ~95% of pair samples are abstract. Rejection events that
 * touch at least one cast member produce a red ✕ overlay at the cast
 * member's position with a letter tag for the gate that killed the
 * trade.
 *
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
  const GRID_COLS = 4;
  const GRID_ROWS = 3;
  const SECTOR_PAD = 24;

  const STYLE = `
    .lc-host { position: relative; background: #06080b; border: 1px solid var(--border); border-radius: 3px; overflow: hidden; }
    .lc-controls { display: flex; gap: 10px; align-items: center; padding: 10px 14px; font-family: var(--mono); font-size: 11px; color: var(--text-3); border-bottom: 1px solid var(--border); background: var(--panel); }
    .lc-status { margin-left: auto; }
    .lc-canvas-wrap { position: relative; height: 640px; }
    .lc-canvas { width: 100%; height: 100%; display: block; }
    .lc-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-family: var(--mono); font-size: 12px; pointer-events: none; }
    .lc-tooltip { position: absolute; background: var(--panel); border: 1px solid var(--accent); border-radius: 3px; padding: 6px 10px; font-family: var(--mono); font-size: 10px; color: var(--text); pointer-events: none; display: none; max-width: 260px; line-height: 1.4; z-index: 5; }
    .lc-legend { display: flex; flex-wrap: wrap; gap: 8px 14px; padding: 6px 14px; font-family: var(--mono); font-size: 10px; color: var(--text-3); border-top: 1px solid var(--border); background: var(--panel); }
    .lc-legend-key { display: inline-flex; align-items: center; gap: 4px; }
    .lc-legend-key .glyph { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
    .lc-legend-key .glyph.sq { border-radius: 1px; transform: rotate(45deg); }
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
    if (rec.is_a_human && rec.is_b_human) return 'rgba(95,165,114,0.9)';
    if (!rec.is_a_human && !rec.is_b_human) return 'rgba(91,142,196,0.9)';
    return 'rgba(217,180,90,0.95)';
  }

  function rejectColor(reason) {
    return ({
      law: 'rgba(194,90,90,0.95)',
      permeability: 'rgba(184,154,85,0.9)',
      regulator: 'rgba(144,119,194,0.9)',
      market: 'rgba(124,174,193,0.9)',
      align: 'rgba(189,111,166,0.9)',
      cost: 'rgba(108,179,158,0.9)',
    })[reason] || 'rgba(158,162,168,0.7)';
  }
  function rejectLetter(reason) {
    return ({ law: 'L', permeability: 'P', regulator: 'R', market: 'M', align: 'N', cost: '$' })[reason] || '?';
  }

  function convexHull(points) {
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
    controls.appendChild(document.createTextNode('Live world map · agents move between sector regions and meet to trade'));
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

    const legend = document.createElement('div');
    legend.className = 'lc-legend';
    legend.innerHTML = `
      <span class="lc-legend-key"><span class="glyph" style="background:#e7e8ea;"></span>human</span>
      <span class="lc-legend-key"><span class="glyph sq" style="background:#9ea2a8;"></span>agent</span>
      <span class="lc-legend-key">size→wealth · color→sector</span>
      <span class="lc-legend-key">trade arc colour: <span style="color: var(--green);">H↔H</span> · <span style="color: var(--accent);">H↔A</span> · <span style="color: var(--blue);">A↔A</span></span>
      <span class="lc-legend-key">reject ✕ tag: L law · P permeability · R regulator · M market · N alignment · $ cost</span>
    `;
    wrap.appendChild(legend);

    const ctx = canvas.getContext('2d');
    let W = 1100, H = 640;
    function resize() {
      const dpr = window.devicePixelRatio || 1;
      W = canvas.clientWidth || 1100;
      H = canvas.clientHeight || 640;
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();

    function sectorRect(sec) {
      const col = sec % GRID_COLS;
      const row = Math.floor(sec / GRID_COLS);
      const innerW = W - 2 * SECTOR_PAD;
      const innerH = H - 2 * SECTOR_PAD;
      const cellW = innerW / GRID_COLS;
      const cellH = innerH / GRID_ROWS;
      return {
        x: SECTOR_PAD + col * cellW,
        y: SECTOR_PAD + row * cellH,
        w: cellW,
        h: cellH,
        cx: SECTOR_PAD + col * cellW + cellW / 2,
        cy: SECTOR_PAD + row * cellH + cellH / 2,
      };
    }

    // ---- state -----------------------------------------------------------
    const cast = new Map();   // proto_idx → { x, y, vx, vy, sector, isHuman, wealth, wealthSmooth, capability, autonomy, firmId, stack, idx, lastFlash }
    const trades = [];        // active cast-to-cast trade animations
    const rejects = [];       // active reject overlays on cast members
    const pulses = [];        // small wealth/exchange particle bursts
    let lastSnapshotStep = -1;
    let nIncomingPairs = 0;

    const TRADE_DURATION_MS = 700;       // total animation lifetime
    const TRADE_APPROACH_FRAC = 0.45;    // 0 → frac: agents accelerate together
    const TRADE_MEET_FRAC = 0.55;        // approach end → meet end (particle burst)
    const REJECT_DURATION_MS = 800;
    const TRADE_CAP = 80;                // max concurrent trades
    const REJECT_CAP = 60;

    function buildPositions(snapshot) {
      cast.clear();
      for (const m of snapshot) {
        const r = sectorRect(m.sector);
        // Initial position: random within the sector rect, slightly inset.
        const inset = 14;
        const rx = r.x + inset + Math.random() * (r.w - 2 * inset);
        const ry = r.y + inset + Math.random() * (r.h - 2 * inset);
        cast.set(m.idx, {
          x: rx, y: ry, vx: 0, vy: 0,
          sector: m.sector,
          isHuman: m.is_human,
          wealth: m.wealth, wealthSmooth: m.wealth,
          capability: m.capability,
          autonomy: m.autonomy,
          firmId: m.firm_id,
          stack: m.stack,
          idx: m.idx,
          lastFlash: 0,
          inTrade: 0,         // count of active trades referencing this agent
        });
      }
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
          if (c.sector !== m.sector) {
            // Sector switch (rare — population dynamics could cause this).
            c.sector = m.sector;
          }
        }
      }
      lastSnapshotStep = stepIdx;
    }

    function spawnFromPair(p, now) {
      nIncomingPairs += 1;
      const a = cast.get(p.proto_a);
      const b = cast.get(p.proto_b);
      if (!a && !b) return;
      if (!p.executed) {
        const reason = p.reject_reason || 'cost';
        if (a) {
          rejects.push({ x: a.x, y: a.y, color: rejectColor(reason), letter: rejectLetter(reason), t0: now });
          a.lastFlash = now;
        }
        if (b) {
          rejects.push({ x: b.x, y: b.y, color: rejectColor(reason), letter: rejectLetter(reason), t0: now });
          b.lastFlash = now;
        }
        if (rejects.length > REJECT_CAP) rejects.splice(0, rejects.length - REJECT_CAP);
        return;
      }
      // Cast-to-cast: agents meet at midpoint.
      // Single-cast: the cast member darts out to a ghost point at the
      // other endpoint's sector edge, flashes, and drifts back.
      // Cast-to-cast events are statistically rare (cast covers a small
      // share of weighted pairs), so most animations are single-cast
      // darts — the right "agent leaves the village, trades, comes back"
      // feel for the map.
      if (a && b) {
        if (trades.length >= TRADE_CAP) trades.shift();
        trades.push({
          kind: 'meet', a, b, t0: now, dur: TRADE_DURATION_MS,
          color: pairTypeColor(p),
          weight: Math.max(0.6, Math.min(2.8, Math.log10((p.pair_weight || 1) + 1) * 0.8 + 0.6)),
          flashed: false,
        });
        a.inTrade += 1;
        b.inTrade += 1;
      } else {
        // Sample only a fraction of single-cast events so the canvas
        // doesn't get overwhelmed at K=1500 × 100 steps/sec.
        if (Math.random() > 0.35) return;
        const me = a || b;
        const otherSector = a ? p.sec_b : p.sec_a;
        const ghost = sectorRect(otherSector);
        // Offset slightly into the other sector so darting reads as
        // "going to do business there", not "leaving the canvas."
        if (trades.length >= TRADE_CAP) trades.shift();
        trades.push({
          kind: 'dart', a: me, ghost: { x: ghost.cx, y: ghost.cy }, t0: now, dur: TRADE_DURATION_MS,
          color: pairTypeColor(p),
          weight: Math.max(0.6, Math.min(2.0, Math.log10((p.pair_weight || 1) + 1) * 0.6 + 0.6)),
          flashed: false,
        });
        me.inTrade += 1;
      }
    }

    // ---- physics ---------------------------------------------------------

    let lastFrameMs = performance.now();
    function step(now) {
      const rawDt = Math.min(48, now - lastFrameMs);   // clamp to handle tab switches
      lastFrameMs = now;
      // Convert ms to a unit where 1 == one frame at 60fps for tuning.
      const dt = rawDt / 16.67;

      // 1. Sector pull + random walk + dampening on each cast member.
      cast.forEach((c) => {
        const r = sectorRect(c.sector);
        // Pull toward sector centroid — weak so agents wander within their region.
        c.vx += (r.cx - c.x) * 0.0025 * dt;
        c.vy += (r.cy - c.y) * 0.0025 * dt;
        // Random walk for organic motion when idle.
        const wander = c.inTrade > 0 ? 0.02 : 0.18;
        c.vx += (Math.random() - 0.5) * wander * dt;
        c.vy += (Math.random() - 0.5) * wander * dt;
      });

      // 2. Trade pull: meeting (both cast) or darting (single cast).
      for (let i = trades.length - 1; i >= 0; i -= 1) {
        const t = trades[i];
        const u = (now - t.t0) / t.dur;
        if (u >= 1) {
          t.a.inTrade = Math.max(0, t.a.inTrade - 1);
          if (t.kind === 'meet') t.b.inTrade = Math.max(0, t.b.inTrade - 1);
          trades.splice(i, 1);
          continue;
        }
        if (t.kind === 'meet') {
          if (u < TRADE_APPROACH_FRAC) {
            const k = 0.045 * (1 - u / TRADE_APPROACH_FRAC) * dt;
            const dx = t.b.x - t.a.x;
            const dy = t.b.y - t.a.y;
            t.a.vx += dx * k;
            t.a.vy += dy * k;
            t.b.vx -= dx * k;
            t.b.vy -= dy * k;
          } else if (u >= TRADE_APPROACH_FRAC && u < TRADE_MEET_FRAC && !t.flashed) {
            const mx = (t.a.x + t.b.x) / 2;
            const my = (t.a.y + t.b.y) / 2;
            pulses.push({ x: mx, y: my, t0: now, color: t.color });
            t.flashed = true;
          }
        } else {
          // 'dart': single cast member moves toward the ghost point and back.
          if (u < TRADE_APPROACH_FRAC) {
            const k = 0.06 * (1 - u / TRADE_APPROACH_FRAC) * dt;
            t.a.vx += (t.ghost.x - t.a.x) * k;
            t.a.vy += (t.ghost.y - t.a.y) * k;
          } else if (u >= TRADE_APPROACH_FRAC && u < TRADE_MEET_FRAC && !t.flashed) {
            // Flash slightly in front of where the cast member currently is,
            // along the dart vector — reads as "trade landed."
            pulses.push({ x: t.a.x, y: t.a.y, t0: now, color: t.color });
            t.flashed = true;
          }
        }
      }

      // 3. Apply velocity, dampening, boundary.
      cast.forEach((c) => {
        c.vx *= Math.pow(0.86, dt);
        c.vy *= Math.pow(0.86, dt);
        // Cap velocity so trade pull doesn't fling agents through the canvas.
        const v = Math.hypot(c.vx, c.vy);
        const VMAX = c.inTrade > 0 ? 8.0 : 1.2;
        if (v > VMAX) { c.vx = c.vx / v * VMAX; c.vy = c.vy / v * VMAX; }
        c.x += c.vx * dt;
        c.y += c.vy * dt;
        // Boundary soft-bounce.
        const m = 14;
        if (c.x < m) { c.x = m; c.vx = Math.abs(c.vx) * 0.4; }
        if (c.x > W - m) { c.x = W - m; c.vx = -Math.abs(c.vx) * 0.4; }
        if (c.y < m) { c.y = m; c.vy = Math.abs(c.vy) * 0.4; }
        if (c.y > H - m) { c.y = H - m; c.vy = -Math.abs(c.vy) * 0.4; }
      });

      // 4. Lerp wealth for smooth radius growth/shrink.
      cast.forEach((c) => { c.wealthSmooth += (c.wealth - c.wealthSmooth) * 0.18 * dt; });
    }

    // ---- render loop -----------------------------------------------------
    let raf;
    function frame() {
      const now = performance.now();
      step(now);
      ctx.clearRect(0, 0, W, H);

      // Sector regions: soft fill + label.
      for (let s = 0; s < N_SECTORS; s += 1) {
        const r = sectorRect(s);
        const color = sectorColor(s);
        ctx.fillStyle = color + '11';     // very faint
        ctx.strokeStyle = color + '55';
        ctx.lineWidth = 1;
        ctx.fillRect(r.x, r.y, r.w, r.h);
        ctx.strokeRect(r.x, r.y, r.w, r.h);
        ctx.font = 'bold 11px "JetBrains Mono", monospace';
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.85;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        ctx.fillText(SECTOR_NAMES[s].toUpperCase(), r.x + 8, r.y + 6);
        ctx.globalAlpha = 1.0;
      }

      // Firm hulls (after region grid, before agents).
      const firms = new Map();
      cast.forEach((c) => {
        if (c.firmId == null || c.firmId < 0) return;
        let arr = firms.get(c.firmId);
        if (!arr) { arr = []; firms.set(c.firmId, arr); }
        arr.push(c);
      });
      ctx.lineWidth = 1.5;
      ctx.setLineDash([5, 4]);
      firms.forEach((members, firmId) => {
        if (members.length < 2) return;
        const hull = convexHull(members.map((m) => ({ x: m.x, y: m.y })));
        if (hull.length < 2) return;
        const col = sectorColor(firmId % N_SECTORS);
        ctx.strokeStyle = col;
        ctx.fillStyle = col + '1f';
        ctx.beginPath();
        ctx.moveTo(hull[0].x, hull[0].y);
        for (let i = 1; i < hull.length; i += 1) ctx.lineTo(hull[i].x, hull[i].y);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      });
      ctx.setLineDash([]);

      // Trade lines: thin connector while approaching, fading toward the
      // retreat. For darts, the line connects the cast member to its
      // ghost destination point so the eye can follow the trade vector.
      for (const t of trades) {
        const u = (now - t.t0) / t.dur;
        let alpha;
        if (u < TRADE_APPROACH_FRAC) alpha = 0.4 * (1 - u / TRADE_APPROACH_FRAC) + 0.6;
        else alpha = Math.max(0, 1 - (u - TRADE_APPROACH_FRAC) / (1 - TRADE_APPROACH_FRAC));
        ctx.globalAlpha = alpha * 0.5;
        ctx.strokeStyle = t.color;
        ctx.lineWidth = t.weight;
        ctx.beginPath();
        ctx.moveTo(t.a.x, t.a.y);
        if (t.kind === 'meet') ctx.lineTo(t.b.x, t.b.y);
        else ctx.lineTo(t.ghost.x, t.ghost.y);
        ctx.stroke();
      }
      ctx.globalAlpha = 1.0;

      // Meeting pulses.
      for (let i = pulses.length - 1; i >= 0; i -= 1) {
        const p = pulses[i];
        const age = now - p.t0;
        const PULSE_DUR = 380;
        if (age > PULSE_DUR) { pulses.splice(i, 1); continue; }
        const u = age / PULSE_DUR;
        ctx.globalAlpha = (1 - u);
        ctx.fillStyle = p.color;
        const r = 4 + u * 18;
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, 2 * Math.PI);
        ctx.fill();
      }
      ctx.globalAlpha = 1.0;

      // Reject overlays.
      for (let i = rejects.length - 1; i >= 0; i -= 1) {
        const r = rejects[i];
        const u = (now - r.t0) / REJECT_DURATION_MS;
        if (u >= 1) { rejects.splice(i, 1); continue; }
        ctx.globalAlpha = (1 - u);
        ctx.strokeStyle = r.color;
        ctx.lineWidth = 2;
        const sz = 5 + u * 6;
        ctx.beginPath();
        ctx.moveTo(r.x - sz, r.y - sz); ctx.lineTo(r.x + sz, r.y + sz);
        ctx.moveTo(r.x + sz, r.y - sz); ctx.lineTo(r.x - sz, r.y + sz);
        ctx.stroke();
        ctx.fillStyle = r.color;
        ctx.font = 'bold 9px "JetBrains Mono", monospace';
        ctx.fillText(r.letter, r.x + sz + 5, r.y - sz);
      }
      ctx.globalAlpha = 1.0;

      // Cast dots.
      cast.forEach((c) => {
        const r = 3 + Math.log10(Math.max(c.wealthSmooth, 0.1)) * 1.8;
        const flashAge = (now - c.lastFlash);
        const glow = flashAge < 400 ? (1 - flashAge / 400) : 0;
        if (glow > 0) {
          ctx.beginPath();
          ctx.arc(c.x, c.y, r + 4 + glow * 4, 0, 2 * Math.PI);
          ctx.fillStyle = sectorColor(c.sector);
          ctx.globalAlpha = glow * 0.35;
          ctx.fill();
          ctx.globalAlpha = 1.0;
        }
        ctx.fillStyle = sectorColor(c.sector);
        if (c.isHuman) {
          ctx.beginPath();
          ctx.arc(c.x, c.y, r, 0, 2 * Math.PI);
          ctx.fill();
          ctx.strokeStyle = 'rgba(231,232,234,0.6)';
          ctx.lineWidth = 1;
          ctx.stroke();
        } else {
          const half = r * 0.95;
          ctx.save();
          ctx.translate(c.x, c.y);
          ctx.rotate(Math.PI / 4);
          ctx.fillRect(-half, -half, half * 2, half * 2);
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
        const d = Math.hypot(c.x - mx, c.y - my);
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
        <div>active trades: ${c.inTrade}</div>
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
            spawnFromPair(p, now);
          }
        }
      }
      const inFirm = [...cast.values()].filter((c) => c.firmId >= 0).length;
      status.textContent = `step ${lastSnapshotStep} · ${cast.size} agents · ${trades.length} live trades · ${rejects.length} rejects · ${inFirm} in firms`;
    }

    function reset() {
      cast.clear();
      trades.length = 0;
      rejects.length = 0;
      pulses.length = 0;
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
