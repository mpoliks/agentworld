/*
 * dashboard/live_flow.js — deck.gl particle flow (V2 S5 / Flow tab).
 *
 * Replaces the SVG Grid tab. Each sampled pair becomes a particle that
 * travels from sec_a → sec_b along a curved arc over ~500ms. Active
 * particles render as glowing dots with trailing arcs; the canvas
 * always carries roughly K * tail_seconds worth of motion.
 *
 * deck.gl from CDN; no React. Two layers:
 *   - ArcLayer for the trail (faded, colour by pair type)
 *   - ScatterplotLayer for the particle head (bright, glow)
 *
 * `window.createFlow(host) → { applyStep(step), reset() }`.
 *
 * Sector layout: 12 fixed positions arranged on a circle of radius R.
 * Sector colours match the chord palette (d3.interpolateRainbow).
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
    .lp-flow-host { position: relative; background: var(--bg); border: 1px solid var(--border); border-radius: 3px; overflow: hidden; }
    .lp-flow-canvas { width: 100%; height: 540px; display: block; }
    .lp-flow-controls { display: flex; gap: 8px; align-items: center; padding: 10px 14px; font-family: var(--mono); font-size: 11px; color: var(--text-3); border-bottom: 1px solid var(--border); background: var(--panel); }
    .lp-flow-status { margin-left: auto; }
    .lp-flow-chip { padding: 4px 10px; background: var(--panel-2); border: 1px solid var(--border); border-radius: 3px; cursor: pointer; color: var(--text-2); user-select: none; }
    .lp-flow-chip.active { background: var(--accent); color: #1a1208; border-color: var(--accent); }
    .lp-flow-sector-labels { position: absolute; top: 0; left: 0; pointer-events: none; width: 100%; height: 100%; }
    .lp-flow-sector-labels .label { position: absolute; font-family: var(--mono); font-size: 10px; color: var(--text-2); transform: translate(-50%, -50%); text-transform: uppercase; letter-spacing: 0.06em; text-shadow: 0 0 4px var(--bg); }
    .lp-flow-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-family: var(--mono); font-size: 12px; pointer-events: none; }
  `;

  function ensureStyle() {
    if (!document.querySelector('style[data-lp-flow]')) {
      const s = document.createElement('style');
      s.setAttribute('data-lp-flow', '1');
      s.textContent = STYLE;
      document.head.appendChild(s);
    }
  }

  // deck.gl is loaded lazily — only when the Flow factory is invoked.
  // Returns a promise that resolves to `window.deck`.
  let deckPromise = null;
  function ensureDeckGL() {
    if (window.deck) return Promise.resolve(window.deck);
    if (deckPromise) return deckPromise;
    deckPromise = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://unpkg.com/deck.gl@9.0.27/dist.min.js';
      s.onload = () => {
        if (window.deck) resolve(window.deck);
        else reject(new Error('deck.gl loaded but window.deck missing'));
      };
      s.onerror = () => reject(new Error('failed to load deck.gl from CDN'));
      document.head.appendChild(s);
    });
    return deckPromise;
  }

  function sectorColor(i) {
    if (window.d3 && window.d3.interpolateRainbow) {
      const c = window.d3.interpolateRainbow((i + 0.5) / N_SECTORS);
      // d3 returns rgb(r, g, b); convert to [r, g, b].
      const m = c.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
      if (m) return [Number(m[1]), Number(m[2]), Number(m[3])];
    }
    const palette = [
      [184, 154, 85], [95, 165, 114], [194, 90, 90], [91, 142, 196],
      [144, 119, 194], [217, 155, 107], [124, 174, 193], [163, 168, 90],
      [189, 111, 166], [108, 179, 158], [192, 121, 90], [142, 154, 168],
    ];
    return palette[i % palette.length];
  }

  function pairTypeColor(rec) {
    // H↔H green, H↔A accent, A↔A blue. Tints the particle head only;
    // the trail uses the sector palette so flow patterns read by geography.
    if (rec.is_a_human && rec.is_b_human) return [95, 165, 114];
    if (!rec.is_a_human && !rec.is_b_human) return [91, 142, 196];
    return [184, 154, 85];
  }

  async function createFlow(host) {
    ensureStyle();
    host.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'lp-flow-host';
    host.appendChild(wrap);

    const controls = document.createElement('div');
    controls.className = 'lp-flow-controls';
    const includeRejected = makeChip('show rejected', false);
    const status = document.createElement('span');
    status.className = 'lp-flow-status';
    status.textContent = 'waiting for run…';
    controls.appendChild(includeRejected);
    controls.appendChild(status);
    wrap.appendChild(controls);

    function makeChip(label, active) {
      const c = document.createElement('span');
      c.className = 'lp-flow-chip' + (active ? ' active' : '');
      c.textContent = label;
      return c;
    }
    let showRejected = false;
    includeRejected.addEventListener('click', () => {
      showRejected = !showRejected;
      includeRejected.classList.toggle('active', showRejected);
    });

    const canvasHost = document.createElement('div');
    canvasHost.style.position = 'relative';
    const canvas = document.createElement('canvas');
    canvas.className = 'lp-flow-canvas';
    canvasHost.appendChild(canvas);
    const labelLayer = document.createElement('div');
    labelLayer.className = 'lp-flow-sector-labels';
    canvasHost.appendChild(labelLayer);
    const emptyState = document.createElement('div');
    emptyState.className = 'lp-flow-empty';
    emptyState.textContent = 'particles will appear here once the run starts';
    canvasHost.appendChild(emptyState);
    wrap.appendChild(canvasHost);

    const deckLib = await ensureDeckGL();

    // ---- view + sector layout --------------------------------------------
    const W = 960;
    const H = 540;
    const RADIUS = 220;
    const cx = W / 2;
    const cy = H / 2;
    const sectorPos = [];
    for (let i = 0; i < N_SECTORS; i += 1) {
      const a = (i / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
      sectorPos.push([cx + RADIUS * Math.cos(a), cy + RADIUS * Math.sin(a)]);
    }

    // sector labels in HTML overlay so they don't fight the canvas
    SECTOR_NAMES.forEach((name, i) => {
      const a = (i / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
      const lx = cx + (RADIUS + 26) * Math.cos(a);
      const ly = cy + (RADIUS + 26) * Math.sin(a);
      const el = document.createElement('span');
      el.className = 'label';
      el.style.left = `${(lx / W) * 100}%`;
      el.style.top = `${(ly / H) * 100}%`;
      el.style.color = `rgb(${sectorColor(i).join(',')})`;
      el.textContent = name;
      labelLayer.appendChild(el);
    });

    // ---- particles -------------------------------------------------------
    // Each particle: { src, dst, t0, dur, color, executed, sectorColor }.
    // Trail = fading arc behind the head. Lifetime ≈ dur + tail.
    const particles = [];
    const DURATION_MS = 900;          // flight time
    const TAIL_MS = 700;              // trail fade after arrival

    function spawnFromRec(rec, now) {
      const src = sectorPos[rec.sec_a];
      const dst = sectorPos[rec.sec_b];
      if (!src || !dst) return;
      const colorHead = pairTypeColor(rec);
      const colorArc = sectorColor(rec.sec_a);
      particles.push({
        src, dst,
        t0: now, dur: DURATION_MS,
        color: colorHead, arcColor: colorArc,
        executed: rec.executed,
        weight: Math.max(0.5, Math.min(5, Math.log10(rec.pair_weight + 1) + 1)),
      });
    }

    function currentPos(p, t) {
      const u = Math.min(1, (t - p.t0) / p.dur);
      // Quadratic Bézier through a slightly elevated midpoint so arcs
      // bow outward toward the canvas centre.
      const midX = (p.src[0] + p.dst[0]) / 2;
      const midY = (p.src[1] + p.dst[1]) / 2;
      const inwardX = cx + (midX - cx) * 0.55;
      const inwardY = cy + (midY - cy) * 0.55;
      const oneMinus = 1 - u;
      const x = oneMinus * oneMinus * p.src[0] + 2 * oneMinus * u * inwardX + u * u * p.dst[0];
      const y = oneMinus * oneMinus * p.src[1] + 2 * oneMinus * u * inwardY + u * u * p.dst[1];
      return [x, y];
    }

    // ---- deck.gl instance ------------------------------------------------
    const { Deck, OrthographicView, ScatterplotLayer, ArcLayer } = deckLib;
    const deck = new Deck({
      canvas,
      width: '100%',
      height: '100%',
      views: new OrthographicView({ id: 'ortho' }),
      initialViewState: { target: [cx, cy, 0], zoom: 0 },
      controller: false,
      layers: [],
    });

    function frame() {
      const t = performance.now();
      // Drop particles past their full lifetime.
      const cutoff = t - (DURATION_MS + TAIL_MS);
      let writeIdx = 0;
      for (let i = 0; i < particles.length; i += 1) {
        if (particles[i].t0 > cutoff) {
          particles[writeIdx++] = particles[i];
        }
      }
      particles.length = writeIdx;

      // Build layer data fresh each frame. Heads = active particles in
      // flight. Arcs = trails behind every particle (alpha-fades over
      // time once the head reaches its destination).
      const heads = [];
      const arcs = [];
      for (const p of particles) {
        if (!showRejected && !p.executed) continue;
        const age = t - p.t0;
        const u = Math.min(1, age / p.dur);
        const fadeFromArrival = Math.max(0, 1 - Math.max(0, age - p.dur) / TAIL_MS);
        const pos = currentPos(p, t);
        const headAlpha = p.executed ? 255 : 120;
        const arcAlpha = p.executed ? Math.round(150 * fadeFromArrival) : Math.round(60 * fadeFromArrival);

        arcs.push({
          source: p.src,
          target: pos,
          sourceColor: [...p.arcColor, arcAlpha],
          targetColor: [...p.color, Math.min(255, arcAlpha + 60)],
          width: p.weight,
        });
        if (u < 1) {
          heads.push({
            position: pos,
            color: [...p.color, headAlpha],
            radius: p.executed ? 6 + p.weight : 3,
          });
        }
      }

      // Sector anchors render as faint background discs so the geometry
      // is legible even when traffic is thin.
      const anchors = sectorPos.map((p, i) => ({
        position: p,
        color: [...sectorColor(i), 110],
        radius: 12,
      }));

      const layers = [
        new ScatterplotLayer({
          id: 'sectors',
          data: anchors,
          getPosition: (d) => d.position,
          getRadius: (d) => d.radius,
          getFillColor: (d) => d.color,
          radiusUnits: 'pixels',
          stroked: true,
          getLineColor: [60, 60, 60, 200],
          lineWidthUnits: 'pixels',
          getLineWidth: 1,
        }),
        new ArcLayer({
          id: 'trails',
          data: arcs,
          getSourcePosition: (d) => d.source,
          getTargetPosition: (d) => d.target,
          getSourceColor: (d) => d.sourceColor,
          getTargetColor: (d) => d.targetColor,
          getWidth: (d) => d.width,
          widthUnits: 'pixels',
          greatCircle: false,
        }),
        new ScatterplotLayer({
          id: 'heads',
          data: heads,
          getPosition: (d) => d.position,
          getFillColor: (d) => d.color,
          getRadius: (d) => d.radius,
          radiusUnits: 'pixels',
          stroked: false,
        }),
      ];
      deck.setProps({ layers });
      raf = requestAnimationFrame(frame);
    }
    let raf = requestAnimationFrame(frame);

    // ---- public API ------------------------------------------------------

    function applyStep(step) {
      const pairs = step.pair_samples || [];
      if (!pairs.length) return;
      emptyState.style.display = 'none';
      const now = performance.now();
      // Spread the K particles' launch times across the step's tick so the
      // canvas doesn't ingest 1500 spawns in one frame. ~300ms window.
      const stagger = 300 / Math.max(pairs.length, 1);
      for (let i = 0; i < pairs.length; i += 1) {
        const rec = pairs[i];
        spawnFromRec(rec, now + i * stagger);
      }
      const ex = pairs.filter((r) => r.executed).length;
      status.textContent = `step ${step.step} · +${pairs.length} pairs (${ex} executed) · ${particles.length} in flight`;
    }

    function reset() {
      particles.length = 0;
      status.textContent = 'waiting for run…';
      emptyState.style.display = '';
    }

    function dispose() {
      cancelAnimationFrame(raf);
      try { deck.finalize(); } catch (e) { /* deck.gl version differences */ }
    }

    return { applyStep, reset, dispose };
  }

  window.createFlow = createFlow;
})();
