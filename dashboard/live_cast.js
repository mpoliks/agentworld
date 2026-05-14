/*
 * dashboard/live_cast.js — d3-force swarm.
 *
 * Positions are not predetermined. Each cast member is a node in a
 * d3.forceSimulation. The swarm self-organises via:
 *
 *   - **forceManyBody** (charge, repulsion) — agents push each other
 *     apart so the cloud stays legibly spaced.
 *   - **forceLink** — every cast-to-cast trade adds a transient edge
 *     (TTL ~3.5s); link forces pull trade partners toward each other.
 *     Frequent trade pairs cluster geographically without any pre-set
 *     anchor.
 *   - **firm-link** — pairs of cast members sharing a firm_id get a
 *     persistent link (added on each step's snapshot, refreshed while
 *     the firm holds). Firms surface as tight visible clusters.
 *   - **forceCenter** — keeps the whole swarm grounded near canvas
 *     centre; the cloud never drifts off-screen.
 *
 * Motion is continuous: `alphaDecay = 0`, `alphaMin = 0`. Trade events
 * constantly add edges, edges constantly expire, charge constantly
 * repels — the swarm never settles. Drag a live-tunable slider mid-run
 * and the engine produces a different trade pattern, which reshapes
 * the swarm within a few seconds.
 *
 * Rendering: deck.gl three-layer soft-circle stack (core + halo + wash
 * with additive blending) so dense regions glow gauzy and sparse ones
 * look like single fireflies. Recent trade activity spawns a brief
 * bright streak along the link.
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

  const STYLE = `
    .lc-host { position: relative; background: #000; border: 1px solid var(--border); border-radius: 3px; overflow: hidden; }
    .lc-controls { display: flex; gap: 10px; align-items: center; padding: 10px 14px; font-family: var(--mono); font-size: 11px; color: var(--text-3); border-bottom: 1px solid var(--border); background: var(--panel); }
    .lc-status { margin-left: auto; }
    .lc-canvas-wrap { position: relative; height: 720px; background: #000; }
    .lc-canvas { width: 100%; height: 100%; display: block; }
    .lc-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-family: var(--mono); font-size: 12px; pointer-events: none; }
    .lc-empty .title { font-size: 13px; color: var(--accent); margin-bottom: 6px; letter-spacing: 0.04em; }
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
    const fb = [[184,154,85],[95,165,114],[194,90,90],[91,142,196],[144,119,194],[217,155,107],[124,174,193],[163,168,90],[189,111,166],[108,179,158],[192,121,90],[142,154,168]];
    return fb[i % fb.length];
  }

  function prefToColor(pref) {
    if (pref == null || pref < 0) return null;
    const p = Math.max(0, Math.min(1, pref));
    return [Math.round(95 + (194 - 95) * p), Math.round(165 + (90 - 165) * p), Math.round(114 + (90 - 114) * p)];
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
    controls.appendChild(document.createTextNode('Live world swarm · d3-force · positions emerge from trade interactions'));
    controls.appendChild(status);
    wrap.appendChild(controls);

    const canvasWrap = document.createElement('div');
    canvasWrap.className = 'lc-canvas-wrap';
    const canvas = document.createElement('canvas');
    canvas.className = 'lc-canvas';
    canvasWrap.appendChild(canvas);
    const empty = document.createElement('div');
    empty.className = 'lc-empty';
    empty.innerHTML = '<div style="text-align: center;"><div class="title">Swarm</div><div>Click Run with Continuous on. ~500 agents self-organise as they trade.</div></div>';
    canvasWrap.appendChild(empty);
    wrap.appendChild(canvasWrap);

    // Events log — firm formation/dissolution. Declared before any
    // function references events (TDZ).
    const events = [];
    const EVENTS_MAX = 8;
    let lastFirmSizes = new Map();
    const eventsHost = document.createElement('div');
    eventsHost.className = 'lc-events';
    eventsHost.innerHTML = '<div class="lc-events-title">emergence log · firms form, dissolve, members join, leave</div><div class="lc-events-body"></div>';
    wrap.appendChild(eventsHost);
    function renderEvents() {
      const body = eventsHost.querySelector('.lc-events-body');
      if (!body) return;
      body.innerHTML = events.slice().reverse().map((e) =>
        `<div class="lc-events-row"><span class="ev-step">t${e.stepIdx}</span><span class="ev-kind ${e.kind}">${e.kind}</span><span class="ev-text">${e.text}</span></div>`
      ).join('') || '<div class="lc-events-empty">no firm events yet — try full_emergence to see syndicates form</div>';
    }
    function logEvent(stepIdx, kind, text) {
      events.push({ stepIdx, kind, text });
      if (events.length > EVENTS_MAX) events.shift();
      renderEvents();
    }
    renderEvents();

    if (!window.d3 || !window.d3.forceSimulation) {
      empty.querySelector('.title').textContent = 'd3 v7 not loaded';
      return { applyStep: () => {}, reset: () => {}, dispose: () => {} };
    }
    const d3 = window.d3;

    const deckLib = await ensureDeckGL();
    const { Deck, OrthographicView, ScatterplotLayer, LineLayer } = deckLib;

    // ---- viewport -------------------------------------------------------
    let W = 1100, H = 720;
    function viewportCenter() { return [W / 2, H / 2]; }

    // ---- d3-force simulation -------------------------------------------
    // Nodes carry the live cast state plus the simulation's x,y,vx,vy.
    // Links: { source, target, kind: 'trade'|'firm', expires: ms timestamp }.
    const nodes = [];                // simulation nodes
    const nodeByIdx = new Map();     // proto_idx → node
    const links = [];                // active links
    const linkKeySet = new Set();    // dedupe key 'a|b|kind'
    const TRADE_LINK_TTL_MS = 3500;
    const FIRM_LINK_REFRESH_MS = 1200;   // re-add firm links on every snapshot
    const LINK_CAP = 800;

    function linkKey(a, b, kind) {
      return a < b ? `${a}|${b}|${kind}` : `${b}|${a}|${kind}`;
    }
    function addLink(idxA, idxB, kind, now) {
      if (idxA === idxB) return;
      const a = nodeByIdx.get(idxA);
      const b = nodeByIdx.get(idxB);
      if (!a || !b) return;
      const key = linkKey(idxA, idxB, kind);
      const ttl = kind === 'firm' ? FIRM_LINK_REFRESH_MS : TRADE_LINK_TTL_MS;
      // Refresh existing link's expiry instead of duplicating.
      for (let i = 0; i < links.length; i += 1) {
        if (links[i].key === key) {
          links[i].expires = now + ttl;
          links[i].t0 = links[i].t0 || now;
          return;
        }
      }
      links.push({
        source: a, target: b, kind, key,
        strength: kind === 'firm' ? 0.4 : 0.08,
        distance: kind === 'firm' ? 32 : 70,
        t0: now,
        expires: now + ttl,
      });
      linkKeySet.add(key);
      if (links.length > LINK_CAP) {
        const dropped = links.shift();
        linkKeySet.delete(dropped.key);
      }
    }
    function pruneExpiredLinks(now) {
      let writeIdx = 0;
      for (let i = 0; i < links.length; i += 1) {
        if (links[i].expires > now) {
          links[writeIdx++] = links[i];
        } else {
          linkKeySet.delete(links[i].key);
        }
      }
      links.length = writeIdx;
    }

    const sim = d3.forceSimulation(nodes)
      .alphaDecay(0)
      .alphaMin(0)
      .velocityDecay(0.36)
      .force('charge', d3.forceManyBody().strength((d) => -10 - Math.log10(Math.max(d.wealthSmooth || 1, 1)) * 2).distanceMax(120).theta(0.9))
      .force('link', d3.forceLink(links).id((d) => d.idx).strength((l) => l.strength).distance((l) => l.distance))
      .force('collide', d3.forceCollide().radius((d) => 3 + Math.log10(Math.max(d.wealthSmooth || 1, 1)) * 1.4 + 1.5))
      .force('x', d3.forceX(() => viewportCenter()[0]).strength(0.012))
      .force('y', d3.forceY(() => viewportCenter()[1]).strength(0.012));

    function placeNewNode(m, now) {
      // Random initial position inside a small bubble at canvas centre;
      // forces will fling it outward.
      const [cx, cy] = viewportCenter();
      const r = 80 * Math.sqrt(Math.random());
      const a = Math.random() * 2 * Math.PI;
      return {
        idx: m.idx,
        x: cx + r * Math.cos(a),
        y: cy + r * Math.sin(a),
        vx: 0, vy: 0,
        sector: m.sector,
        isHuman: m.is_human,
        wealth: m.wealth, wealthSmooth: m.wealth,
        capability: m.capability,
        autonomy: m.autonomy,
        firmId: m.firm_id,
        stack: m.stack,
        intermediationPref: m.intermediation_pref,
        lastFlash: 0,
      };
    }

    function ingestSnapshot(stepIdx, snapshot, now) {
      // First snapshot: bulk-create.
      let dirty = false;
      const seen = new Set();
      for (const m of snapshot) {
        seen.add(m.idx);
        let n = nodeByIdx.get(m.idx);
        if (!n) {
          n = placeNewNode(m, now);
          nodes.push(n);
          nodeByIdx.set(m.idx, n);
          dirty = true;
        } else {
          n.wealth = m.wealth;
          n.capability = m.capability;
          n.autonomy = m.autonomy;
          n.intermediationPref = m.intermediation_pref;
          n.sector = m.sector;
          n.stack = m.stack;
          n.firmId = m.firm_id;
        }
        // Refresh firm-link membership.
        if (m.firm_id != null && m.firm_id >= 0) {
          // Find other cast members in the same firm; link to a few of them.
          // (Linking all pairs would be O(n²) — cap at 3 neighbours per
          // member per step for performance.)
          let neighborsAdded = 0;
          for (const o of nodes) {
            if (o.idx === m.idx) continue;
            if (o.firmId !== m.firm_id) continue;
            addLink(m.idx, o.idx, 'firm', now);
            neighborsAdded += 1;
            if (neighborsAdded >= 3) break;
          }
        }
      }
      if (dirty) {
        sim.nodes(nodes);
        sim.force('link').links(links);
        sim.alpha(0.4).restart();
      }
    }

    function detectFirmEvents(stepIdx) {
      const sizes = new Map();
      nodes.forEach((n) => {
        if (n.firmId == null || n.firmId < 0) return;
        sizes.set(n.firmId, (sizes.get(n.firmId) || 0) + 1);
      });
      sizes.forEach((n, id) => {
        if (!lastFirmSizes.has(id) && n >= 2) logEvent(stepIdx, 'firm-form', `firm ${id} formed (${n} members)`);
      });
      lastFirmSizes.forEach((n, id) => {
        if (!sizes.has(id)) logEvent(stepIdx, 'firm-dissolve', `firm ${id} dissolved`);
      });
      lastFirmSizes = sizes;
    }

    function spawnFromPair(p, now) {
      const a = nodeByIdx.get(p.proto_a);
      const b = nodeByIdx.get(p.proto_b);
      if (!a && !b) return;
      if (p.executed && a && b) {
        addLink(a.idx, b.idx, 'trade', now);
        a.lastFlash = now;
        b.lastFlash = now;
      } else {
        if (a) a.lastFlash = now;
        if (b) b.lastFlash = now;
      }
    }

    // ---- deck.gl renderer ----------------------------------------------
    const deck = new Deck({
      canvas,
      width: '100%',
      height: '100%',
      views: new OrthographicView({ id: 'ortho' }),
      controller: false,
      initialViewState: { target: [W/2, H/2, 0], zoom: 0 },
      layers: [],
      parameters: { clearColor: [0, 0, 0, 1] },
    });

    function resize() {
      const r = canvasWrap.getBoundingClientRect();
      W = Math.max(400, r.width);
      H = Math.max(400, r.height);
      deck.setProps({ initialViewState: { target: [W/2, H/2, 0], zoom: 0 } });
      // Re-trigger center force pull toward the new centre.
      sim.alpha(0.1).restart();
    }
    const ro = new ResizeObserver(resize);
    ro.observe(canvasWrap);
    resize();

    let raf;
    function frame() {
      const now = performance.now();
      pruneExpiredLinks(now);
      // Smooth wealth lerp for visible radius growth.
      for (let i = 0; i < nodes.length; i += 1) {
        const n = nodes[i];
        n.wealthSmooth += (n.wealth - n.wealthSmooth) * 0.15;
      }
      sim.tick(2);   // a couple of integration steps per frame keeps motion lively

      // Particle layer data.
      const particles = nodes.map((n) => {
        const r = 3 + Math.log10(Math.max(n.wealthSmooth, 0.1)) * 1.6;
        const flashAge = now - n.lastFlash;
        const flash = flashAge < 360 ? (1 - flashAge / 360) : 0;
        const col = sectorColor(n.sector);
        const baseA = n.isHuman ? 200 : 165;
        return { pos: [n.x, n.y, 0], r, color: [...col, Math.min(255, baseA + Math.round(flash * 55))] };
      });

      // Outline ring particles encoding strategy preference (small, on top).
      const outlines = [];
      for (let i = 0; i < nodes.length; i += 1) {
        const n = nodes[i];
        const oCol = prefToColor(n.intermediationPref);
        if (!oCol) continue;
        const r = 3 + Math.log10(Math.max(n.wealthSmooth, 0.1)) * 1.6 + 1.4;
        outlines.push({ pos: [n.x, n.y, 0], r, color: [...oCol, 130] });
      }

      // Link rendering: trade links as faint glowing lines, firm links
      // a touch brighter and slightly thicker.
      const tradeLines = [];
      const firmLines = [];
      for (let i = 0; i < links.length; i += 1) {
        const l = links[i];
        const age = (now - l.t0) / (l.expires - l.t0);
        const fade = Math.max(0.05, 1 - age);
        const col = sectorColor(l.source.sector);
        const arr = l.kind === 'firm' ? firmLines : tradeLines;
        arr.push({
          src: [l.source.x, l.source.y, 0],
          dst: [l.target.x, l.target.y, 0],
          color: [col[0], col[1], col[2], l.kind === 'firm' ? 180 : Math.round(140 * fade)],
        });
      }

      const blendParams = { blend: true, blendFunc: [770, 1], depthTest: false };  // SRC_ALPHA, ONE
      const layers = [
        new LineLayer({
          id: 'trade-links',
          data: tradeLines,
          getSourcePosition: (d) => d.src,
          getTargetPosition: (d) => d.dst,
          getColor: (d) => d.color,
          getWidth: 1,
          widthUnits: 'pixels',
          parameters: blendParams,
        }),
        new LineLayer({
          id: 'firm-links',
          data: firmLines,
          getSourcePosition: (d) => d.src,
          getTargetPosition: (d) => d.dst,
          getColor: (d) => d.color,
          getWidth: 1.6,
          widthUnits: 'pixels',
          parameters: blendParams,
        }),
        new ScatterplotLayer({
          id: 'wash',
          data: particles,
          getPosition: (d) => d.pos,
          getRadius: (d) => d.r * 4.2,
          getFillColor: (d) => [d.color[0], d.color[1], d.color[2], Math.round(d.color[3] * 0.07)],
          radiusUnits: 'pixels',
          stroked: false,
          parameters: blendParams,
        }),
        new ScatterplotLayer({
          id: 'halo',
          data: particles,
          getPosition: (d) => d.pos,
          getRadius: (d) => d.r * 2.1,
          getFillColor: (d) => [d.color[0], d.color[1], d.color[2], Math.round(d.color[3] * 0.22)],
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
          id: 'outlines',
          data: outlines,
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

    // ---- public API ----------------------------------------------------
    function applyStep(step) {
      const now = performance.now();
      if (step.cast_snapshot && step.cast_snapshot.length) {
        empty.style.display = 'none';
        ingestSnapshot(step.step, step.cast_snapshot, now);
        detectFirmEvents(step.step);
      }
      const pairs = step.pair_samples || [];
      if (pairs.length && nodes.length) {
        for (let i = 0; i < pairs.length; i += 1) {
          const p = pairs[i];
          if (nodeByIdx.has(p.proto_a) || nodeByIdx.has(p.proto_b)) spawnFromPair(p, now);
        }
      }
      status.textContent = `step ${step.step} · ${nodes.length} agents · ${links.length} live links · α ${(step.alpha ?? 0).toFixed(2)}`;
    }
    function reset() {
      nodes.length = 0;
      nodeByIdx.clear();
      links.length = 0;
      linkKeySet.clear();
      events.length = 0;
      lastFirmSizes.clear();
      sim.nodes(nodes);
      sim.force('link').links(links);
      sim.alpha(0).stop();
      empty.style.display = '';
      status.textContent = 'waiting for cast snapshot…';
      renderEvents();
    }
    function dispose() {
      cancelAnimationFrame(raf);
      ro.disconnect();
      sim.stop();
      try { deck.finalize(); } catch (e) { /* version differences */ }
    }
    return { applyStep, reset, dispose };
  }

  window.createLiveCast = createLiveCast;
})();
