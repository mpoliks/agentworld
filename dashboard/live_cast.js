/*
 * dashboard/live_cast.js — particle-cloud live world.
 *
 * Aesthetic-first rewrite: drop the sector grid, drop the rectangles
 * and labels, drop the crisp-circle agents. Instead render the cast
 * as a soft particle cloud — each prototype is one particle drawn at
 * three superposed radii (bright core, mid halo, faint wash) with
 * additive blending, so overlapping populations create the gauzy
 * gradient effect of the reference design.
 *
 * Twelve sector centroids placed on a smooth ellipse (not a grid).
 * Particles get a stable angular offset around their centroid via a
 * hash of their prototype index, plus a slow rotational drift and
 * tiny random jitter for organic motion. Trade events spawn a brief
 * bright streak between the two participants; rejections produce a
 * desaturated flicker on the affected agent.
 *
 * `window.createLiveCast(host) → { applyStep, reset, dispose }`.
 *
 * deck.gl is loaded lazily — the cockpit's Flow tab already pulls it,
 * but live_cast.js may be the first surface that needs it.
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
    .lc-host { position: relative; background: #000; border: 1px solid var(--border); border-radius: 3px; overflow: hidden; }
    .lc-controls { display: flex; gap: 10px; align-items: center; padding: 10px 14px; font-family: var(--mono); font-size: 11px; color: var(--text-3); border-bottom: 1px solid var(--border); background: var(--panel); }
    .lc-status { margin-left: auto; }
    .lc-canvas-wrap { position: relative; height: 680px; background: #000; }
    .lc-canvas { width: 100%; height: 100%; display: block; }
    .lc-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-family: var(--mono); font-size: 12px; pointer-events: none; }
    .lc-empty .title { font-size: 13px; color: var(--accent); margin-bottom: 6px; letter-spacing: 0.04em; }
    .lc-edge-labels { position: absolute; inset: 0; pointer-events: none; }
    .lc-edge-labels .lab { position: absolute; font-family: var(--mono); font-size: 9px; color: rgba(231,232,234,0.35); text-transform: uppercase; letter-spacing: 0.08em; transform: translate(-50%, -50%); white-space: nowrap; }
    .lc-events { font-family: var(--mono); font-size: 10px; color: var(--text-3); background: var(--panel); border-top: 1px solid var(--border); padding: 8px 14px; max-height: 110px; overflow-y: auto; }
    .lc-events-title { font-size: 9px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); margin-bottom: 4px; }
    .lc-events-row { display: grid; grid-template-columns: 50px 90px 1fr; gap: 8px; padding: 1px 0; align-items: center; }
    .lc-events-row .ev-step { color: var(--text-3); }
    .lc-events-row .ev-kind { color: var(--text-2); text-transform: uppercase; letter-spacing: 0.04em; }
    .lc-events-row .ev-kind.firm-form { color: var(--green); }
    .lc-events-row .ev-kind.firm-dissolve { color: var(--red); }
    .lc-events-row .ev-kind.firm-join { color: var(--accent); }
    .lc-events-row .ev-kind.firm-leave { color: var(--text-3); }
    .lc-events-row .ev-text { color: var(--text); }
    .lc-events-empty { font-style: italic; color: var(--text-3); padding: 4px 0; }
  `;

  function ensureStyle() {
    if (!document.querySelector('style[data-lc]')) {
      const s = document.createElement('style');
      s.setAttribute('data-lc', '1');
      s.textContent = STYLE;
      document.head.appendChild(s);
    }
  }

  // Lazy deck.gl loader (shared with live_flow.js; safe to call twice).
  let deckPromise = null;
  function ensureDeckGL() {
    if (window.deck) return Promise.resolve(window.deck);
    if (deckPromise) return deckPromise;
    deckPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://unpkg.com/deck.gl@9.0.27/dist.min.js';
      s.onload = () => window.deck ? resolve(window.deck) : reject(new Error('deck.gl loaded but window.deck missing'));
      s.onerror = () => reject(new Error('failed to load deck.gl'));
      document.head.appendChild(s);
    });
    return deckPromise;
  }

  function sectorColor(i) {
    if (window.d3 && window.d3.interpolateRainbow) {
      const c = window.d3.interpolateRainbow((i + 0.5) / N_SECTORS);
      const m = c.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
      if (m) return [Number(m[1]), Number(m[2]), Number(m[3])];
    }
    const fallback = [
      [184, 154, 85], [95, 165, 114], [194, 90, 90], [91, 142, 196],
      [144, 119, 194], [217, 155, 107], [124, 174, 193], [163, 168, 90],
      [189, 111, 166], [108, 179, 158], [192, 121, 90], [142, 154, 168],
    ];
    return fallback[i % fallback.length];
  }

  function hashUnit(n) {
    let h = (n + 0x9e3779b9) | 0;
    h ^= h >>> 16; h = Math.imul(h, 0x85ebca6b);
    h ^= h >>> 13; h = Math.imul(h, 0xc2b2ae35);
    h ^= h >>> 16;
    return (h >>> 0) / 0xffffffff;
  }

  async function createLiveCast(host) {
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
    controls.appendChild(document.createTextNode('Live world · particle cloud · ~500 prototypes per snapshot'));
    controls.appendChild(status);
    wrap.appendChild(controls);

    const canvasWrap = document.createElement('div');
    canvasWrap.className = 'lc-canvas-wrap';
    const canvas = document.createElement('canvas');
    canvas.className = 'lc-canvas';
    canvasWrap.appendChild(canvas);
    const empty = document.createElement('div');
    empty.className = 'lc-empty';
    empty.innerHTML = '<div style="text-align: center;"><div class="title">Live world cloud</div><div>Click Run with Continuous on. ~500 particles fade in, drift, exchange.</div></div>';
    canvasWrap.appendChild(empty);
    const labelLayer = document.createElement('div');
    labelLayer.className = 'lc-edge-labels';
    canvasWrap.appendChild(labelLayer);
    wrap.appendChild(canvasWrap);

    // Events log (firm formation / dissolution narration). Lives below
    // the canvas — a single muted strip rather than a panel of its own.
    const events = [];
    const EVENTS_MAX = 8;
    let lastFirmSizes = new Map();
    const eventsHost = document.createElement('div');
    eventsHost.className = 'lc-events';
    eventsHost.innerHTML = '<div class="lc-events-title">emergence log · firm formation, dissolution, joins, leaves</div><div class="lc-events-body"></div>';
    wrap.appendChild(eventsHost);
    function renderEvents() {
      const body = eventsHost.querySelector('.lc-events-body');
      if (!body) return;
      body.innerHTML = events.slice().reverse().map((e) =>
        `<div class="lc-events-row"><span class="ev-step">t${e.stepIdx}</span><span class="ev-kind ${e.kind}">${e.kind}</span><span class="ev-text">${e.text}</span></div>`
      ).join('') || '<div class="lc-events-empty">no firm events yet — try full_emergence or institutional_emergence to see syndicates form</div>';
    }
    function logEvent(stepIdx, kind, text) {
      events.push({ stepIdx, kind, text });
      if (events.length > EVENTS_MAX) events.shift();
      renderEvents();
    }
    function detectFirmEvents(stepIdx) {
      const sizes = new Map();
      cast.forEach((c) => {
        if (c.firmId == null || c.firmId < 0) return;
        sizes.set(c.firmId, (sizes.get(c.firmId) || 0) + 1);
      });
      sizes.forEach((n, id) => {
        if (!lastFirmSizes.has(id) && n >= 2) logEvent(stepIdx, 'firm-form', `firm ${id} formed (${n} members)`);
      });
      lastFirmSizes.forEach((n, id) => {
        if (!sizes.has(id)) logEvent(stepIdx, 'firm-dissolve', `firm ${id} dissolved`);
      });
      lastFirmSizes = sizes;
    }
    renderEvents();

    const deckLib = await ensureDeckGL();
    const { Deck, OrthographicView, ScatterplotLayer } = deckLib;

    // ---- view + sector centroids ----------------------------------------
    let W = 1100, H = 680;
    const cx = () => W / 2;
    const cy = () => H / 2;
    // 12 sector positions on a smooth ellipse — wide aspect ratio so the
    // cloud breathes horizontally. Slight per-sector radial offset
    // (hash-derived) so the arrangement reads as organic, not radial.
    function sectorCentroid(s) {
      const ang = (s / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
      const RX = Math.min(W, H) * 0.36;
      const RY = RX * 0.78;
      const wobble = 1 + (hashUnit(s + 19) - 0.5) * 0.12;
      return { x: cx() + RX * Math.cos(ang) * wobble, y: cy() + RY * Math.sin(ang) * wobble };
    }
    function placeEdgeLabels() {
      labelLayer.innerHTML = '';
      for (let s = 0; s < N_SECTORS; s += 1) {
        const c = sectorCentroid(s);
        const ang = (s / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
        const lx = cx() + (Math.min(W, H) * 0.36 + 28) * Math.cos(ang);
        const ly = cy() + (Math.min(W, H) * 0.36 * 0.78 + 28) * Math.sin(ang);
        const el = document.createElement('span');
        el.className = 'lab';
        el.style.left = `${(lx / W) * 100}%`;
        el.style.top = `${(ly / H) * 100}%`;
        el.textContent = SECTOR_NAMES[s];
        labelLayer.appendChild(el);
      }
    }

    // ---- cast state -----------------------------------------------------
    const cast = new Map();
    const trades = [];
    const rejects = [];
    let lastSnapshotStep = -1;
    const TRADE_DUR_MS = 900;
    const REJECT_DUR_MS = 700;
    const TRADE_CAP = 100;
    const REJECT_CAP = 80;

    function placeMember(m) {
      const c = sectorCentroid(m.sector);
      // Particle distributed around its sector centroid via 2D Gaussian
      // (Box–Muller) seeded by prototype index → stable across reloads.
      const u1 = Math.max(1e-6, hashUnit(m.idx + 1));
      const u2 = hashUnit(m.idx + 7919);
      const r = Math.sqrt(-2 * Math.log(u1));
      const theta = 2 * Math.PI * u2;
      const SPREAD = Math.min(W, H) * 0.078;
      // Per-particle phase for slow rotational drift.
      const phase0 = hashUnit(m.idx + 31) * 2 * Math.PI;
      return {
        sector: m.sector,
        isHuman: m.is_human,
        wealth: m.wealth, wealthSmooth: m.wealth,
        capability: m.capability,
        autonomy: m.autonomy,
        firmId: m.firm_id,
        stack: m.stack,
        idx: m.idx,
        intermediationPref: m.intermediation_pref,
        // Anchor position around sector centroid + jitter offset.
        baseX: c.x + r * Math.cos(theta) * SPREAD,
        baseY: c.y + r * Math.sin(theta) * SPREAD,
        x: c.x + r * Math.cos(theta) * SPREAD,
        y: c.y + r * Math.sin(theta) * SPREAD,
        phase: phase0,
        wobble: 0.4 + hashUnit(m.idx + 1009) * 0.7,
        lastFlash: 0,
      };
    }

    function buildPositions(snapshot) {
      cast.clear();
      for (const m of snapshot) cast.set(m.idx, placeMember(m));
    }
    function ingestSnapshot(stepIdx, snapshot) {
      if (cast.size === 0) {
        buildPositions(snapshot);
        lastSnapshotStep = stepIdx;
        return;
      }
      for (const m of snapshot) {
        const c = cast.get(m.idx);
        if (!c) continue;
        c.wealth = m.wealth;
        c.capability = m.capability;
        c.autonomy = m.autonomy;
        c.firmId = m.firm_id;
        c.intermediationPref = m.intermediation_pref;
        if (c.sector !== m.sector) {
          // sector reassignment (rare) — re-anchor.
          const newAnchor = sectorCentroid(m.sector);
          c.baseX = newAnchor.x + (c.baseX - sectorCentroid(c.sector).x);
          c.baseY = newAnchor.y + (c.baseY - sectorCentroid(c.sector).y);
          c.sector = m.sector;
        }
      }
      lastSnapshotStep = stepIdx;
    }

    function spawnFromPair(p, now) {
      const a = cast.get(p.proto_a);
      const b = cast.get(p.proto_b);
      if (!a && !b) return;
      if (!p.executed) {
        if (a) { rejects.push({ x: a.x, y: a.y, t0: now, color: sectorColor(a.sector) }); a.lastFlash = now; }
        if (b) { rejects.push({ x: b.x, y: b.y, t0: now, color: sectorColor(b.sector) }); b.lastFlash = now; }
        if (rejects.length > REJECT_CAP) rejects.splice(0, rejects.length - REJECT_CAP);
        return;
      }
      if (a && b && trades.length < TRADE_CAP) {
        trades.push({ a, b, t0: now, dur: TRADE_DUR_MS, color: sectorColor(a.sector) });
        a.lastFlash = now; b.lastFlash = now;
      } else if (a || b) {
        const me = a || b;
        me.lastFlash = now;
      }
    }

    // ---- deck.gl renderer -----------------------------------------------
    const deck = new Deck({
      canvas,
      width: '100%',
      height: '100%',
      views: new OrthographicView({ id: 'ortho' }),
      controller: false,
      initialViewState: { target: [cx(), cy(), 0], zoom: 0 },
      layers: [],
      parameters: { clearColor: [0, 0, 0, 1] },
    });

    function resize() {
      const wRect = canvasWrap.getBoundingClientRect();
      W = Math.max(400, wRect.width);
      H = Math.max(400, wRect.height);
      deck.setProps({ initialViewState: { target: [cx(), cy(), 0], zoom: 0 } });
      // Rebuild anchor positions if the cast already exists — keeps the
      // cloud centred when the panel resizes.
      cast.forEach((c) => {
        const anchor = sectorCentroid(c.sector);
        c.baseX = anchor.x; c.baseY = anchor.y;
        // Re-spread by hash so layout is deterministic per resize.
        const u1 = Math.max(1e-6, hashUnit(c.idx + 1));
        const u2 = hashUnit(c.idx + 7919);
        const r = Math.sqrt(-2 * Math.log(u1));
        const theta = 2 * Math.PI * u2;
        const SPREAD = Math.min(W, H) * 0.078;
        c.baseX = anchor.x + r * Math.cos(theta) * SPREAD;
        c.baseY = anchor.y + r * Math.sin(theta) * SPREAD;
      });
      placeEdgeLabels();
    }
    const ro = new ResizeObserver(resize);
    ro.observe(canvasWrap);
    resize();

    let raf;
    function frame() {
      const now = performance.now();

      // Update per-particle position with slow drift + phase rotation.
      cast.forEach((c) => {
        c.wealthSmooth += (c.wealth - c.wealthSmooth) * 0.15;
        c.phase += 0.003 * c.wobble;
        const dx = Math.cos(c.phase) * 4 * c.wobble;
        const dy = Math.sin(c.phase * 1.31) * 3.5 * c.wobble;
        c.x = c.baseX + dx + (Math.random() - 0.5) * 0.25;
        c.y = c.baseY + dy + (Math.random() - 0.5) * 0.25;
      });

      // Build particle layer data.
      const particles = [];
      cast.forEach((c) => {
        const r = 4 + Math.log10(Math.max(c.wealthSmooth, 0.1)) * 1.8;
        const flashAge = now - c.lastFlash;
        const flash = flashAge < 400 ? (1 - flashAge / 400) : 0;
        const col = sectorColor(c.sector);
        const baseAlpha = c.isHuman ? 180 : 150;
        particles.push({ pos: [c.x, c.y, 0], r, color: [...col, baseAlpha + Math.round(flash * 60)] });
      });

      // Trade streaks: spawn a few intermediate particles along the
      // approach path for the lifetime of the trade.
      const tradeParticles = [];
      for (let i = trades.length - 1; i >= 0; i -= 1) {
        const t = trades[i];
        const u = (now - t.t0) / t.dur;
        if (u >= 1) { trades.splice(i, 1); continue; }
        const alpha = (1 - u) * 220;
        const steps = 6;
        for (let k = 0; k < steps; k += 1) {
          const f = u + (k / steps) * (1 - u);
          if (f > 1) break;
          const px = t.a.x + (t.b.x - t.a.x) * f;
          const py = t.a.y + (t.b.y - t.a.y) * f;
          tradeParticles.push({ pos: [px, py, 0], r: 2.2, color: [...t.color, Math.round(alpha * (1 - k / steps))] });
        }
      }

      // Reject overlays as a dim wash around the affected agent.
      for (let i = rejects.length - 1; i >= 0; i -= 1) {
        const r = rejects[i];
        const u = (now - r.t0) / REJECT_DUR_MS;
        if (u >= 1) { rejects.splice(i, 1); continue; }
        particles.push({ pos: [r.x, r.y, 0], r: 10 + u * 6, color: [194, 90, 90, Math.round(140 * (1 - u))] });
      }

      // Three layered scatterplots emulate a Gaussian falloff — bright
      // core + mid halo + outer wash, additively blended.
      const blendParams = {
        blend: true,
        blendFunc: [770, 1],            // SRC_ALPHA, ONE
        depthTest: false,
      };
      const layers = [
        new ScatterplotLayer({
          id: 'wash',
          data: particles,
          getPosition: (d) => d.pos,
          getRadius: (d) => d.r * 4.2,
          getFillColor: (d) => [d.color[0], d.color[1], d.color[2], Math.round(d.color[3] * 0.08)],
          radiusUnits: 'pixels',
          stroked: false,
          parameters: blendParams,
        }),
        new ScatterplotLayer({
          id: 'halo',
          data: particles,
          getPosition: (d) => d.pos,
          getRadius: (d) => d.r * 2.0,
          getFillColor: (d) => [d.color[0], d.color[1], d.color[2], Math.round(d.color[3] * 0.25)],
          radiusUnits: 'pixels',
          stroked: false,
          parameters: blendParams,
        }),
        new ScatterplotLayer({
          id: 'core',
          data: particles,
          getPosition: (d) => d.pos,
          getRadius: (d) => d.r,
          getFillColor: (d) => d.color,
          radiusUnits: 'pixels',
          stroked: false,
          parameters: blendParams,
        }),
        new ScatterplotLayer({
          id: 'trades',
          data: tradeParticles,
          getPosition: (d) => d.pos,
          getRadius: (d) => d.r,
          getFillColor: (d) => d.color,
          radiusUnits: 'pixels',
          stroked: false,
          parameters: blendParams,
        }),
      ];
      deck.setProps({ layers });
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);

    // ---- public API -----------------------------------------------------
    function applyStep(step) {
      if (step.cast_snapshot && step.cast_snapshot.length) {
        empty.style.display = 'none';
        ingestSnapshot(step.step, step.cast_snapshot);
        detectFirmEvents(step.step);
      }
      const pairs = step.pair_samples || [];
      if (pairs.length && cast.size) {
        const now = performance.now();
        for (let i = 0; i < pairs.length; i += 1) {
          const p = pairs[i];
          if (cast.has(p.proto_a) || cast.has(p.proto_b)) spawnFromPair(p, now);
        }
      }
      status.textContent = `step ${lastSnapshotStep} · ${cast.size} particles · ${trades.length} active trades`;
    }
    function reset() {
      cast.clear();
      trades.length = 0;
      rejects.length = 0;
      events.length = 0;
      lastFirmSizes.clear();
      lastSnapshotStep = -1;
      empty.style.display = '';
      status.textContent = 'waiting for cast snapshot…';
      renderEvents();
    }
    function dispose() {
      cancelAnimationFrame(raf);
      ro.disconnect();
      try { deck.finalize(); } catch (e) { /* version differences */ }
    }
    return { applyStep, reset, dispose };
  }

  window.createLiveCast = createLiveCast;
})();
