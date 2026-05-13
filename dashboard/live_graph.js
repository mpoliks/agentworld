/*
 * dashboard/live_graph.js — Sigma.js force-directed graph (Graph tab).
 *
 * The underlying social network read from per-pair samples. Each
 * sampled prototype becomes a node (positioned with ForceAtlas2,
 * biased toward its sector's anchor); each trade adds a transient
 * edge that fades after ~2.5s. Nodes accumulate a recent-activity
 * count that drives their radius; idle nodes evict.
 *
 * Lazy-loads sigma + graphology + graphology-layout-forceatlas2 from
 * jsDelivr. `window.createGraph(host) → { applyStep, reset, dispose }`.
 *
 * Caps:
 *   - 800 most-recently-active nodes
 *   - 600 edges in flight
 *   - 10s node idle TTL · 2.5s edge TTL
 *
 * Use cases: high-α scenarios where clusters form; emergent-strategy
 * runs where firm-like clusters appear; norms-layer runs where
 * sub-populations decouple in norm space.
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
    .lp-graph-host { background: var(--bg); border: 1px solid var(--border); border-radius: 3px; overflow: hidden; }
    .lp-graph-controls { display: flex; gap: 8px; align-items: center; padding: 10px 14px; font-family: var(--mono); font-size: 11px; color: var(--text-3); border-bottom: 1px solid var(--border); background: var(--panel); }
    .lp-graph-status { margin-left: auto; }
    .lp-graph-canvas-wrap { position: relative; height: 540px; }
    .lp-graph-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-family: var(--mono); font-size: 12px; pointer-events: none; }
    .lp-graph-legend { padding: 8px 14px; font-family: var(--mono); font-size: 10px; color: var(--text-3); border-top: 1px solid var(--border); background: var(--panel); display: flex; flex-wrap: wrap; gap: 12px; }
    .lp-graph-legend .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 50%; vertical-align: middle; margin-right: 4px; }
  `;

  function ensureStyle() {
    if (!document.querySelector('style[data-lp-graph]')) {
      const s = document.createElement('style');
      s.setAttribute('data-lp-graph', '1');
      s.textContent = STYLE;
      document.head.appendChild(s);
    }
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      // Check if a previous load is in flight or done.
      const existing = document.querySelector(`script[data-graph-src="${src}"]`);
      if (existing) {
        if (existing.dataset.loaded === '1') return resolve();
        existing.addEventListener('load', () => resolve());
        existing.addEventListener('error', () => reject(new Error(`failed to load ${src}`)));
        return;
      }
      const s = document.createElement('script');
      s.src = src;
      s.dataset.graphSrc = src;
      s.onload = () => { s.dataset.loaded = '1'; resolve(); };
      s.onerror = () => reject(new Error(`failed to load ${src}`));
      document.head.appendChild(s);
    });
  }

  let depsPromise = null;
  function ensureDeps() {
    if (window.graphology && window.Sigma && window.graphologyLayoutForceatlas2) {
      return Promise.resolve();
    }
    if (depsPromise) return depsPromise;
    depsPromise = (async () => {
      await loadScript('https://cdn.jsdelivr.net/npm/graphology@0.25.4/dist/graphology.umd.min.js');
      await loadScript('https://cdn.jsdelivr.net/npm/graphology-layout-forceatlas2@0.10.1/build/graphology-layout-forceatlas2.min.js');
      await loadScript('https://cdn.jsdelivr.net/npm/sigma@2.4.0/build/sigma.min.js');
    })();
    return depsPromise;
  }

  function sectorColorHex(i) {
    if (window.d3 && window.d3.interpolateRainbow) {
      // d3 returns rgb(); we want hex for sigma.
      const c = window.d3.interpolateRainbow((i + 0.5) / N_SECTORS);
      const m = c.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
      if (m) {
        const toHex = (n) => Number(n).toString(16).padStart(2, '0');
        return `#${toHex(m[1])}${toHex(m[2])}${toHex(m[3])}`;
      }
    }
    const fallback = [
      '#b89a55', '#5fa572', '#c25a5a', '#5b8ec4',
      '#9077c2', '#d99b6b', '#7caec1', '#a3a85a',
      '#bd6fa6', '#6cb39e', '#c0795a', '#8e9aa8',
    ];
    return fallback[i % fallback.length];
  }

  async function createGraph(host) {
    ensureStyle();
    host.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'lp-graph-host';
    host.appendChild(wrap);

    const controls = document.createElement('div');
    controls.className = 'lp-graph-controls';
    const status = document.createElement('span');
    status.className = 'lp-graph-status';
    status.textContent = 'loading sigma…';
    controls.appendChild(document.createTextNode('Prototype graph · ForceAtlas2 · ~800-node cap'));
    controls.appendChild(status);
    wrap.appendChild(controls);

    const canvasWrap = document.createElement('div');
    canvasWrap.className = 'lp-graph-canvas-wrap';
    const sigmaContainer = document.createElement('div');
    sigmaContainer.style.width = '100%';
    sigmaContainer.style.height = '100%';
    canvasWrap.appendChild(sigmaContainer);
    const emptyState = document.createElement('div');
    emptyState.className = 'lp-graph-empty';
    emptyState.textContent = 'nodes appear here once the run starts';
    canvasWrap.appendChild(emptyState);
    wrap.appendChild(canvasWrap);

    const legend = document.createElement('div');
    legend.className = 'lp-graph-legend';
    SECTOR_NAMES.forEach((name, i) => {
      const s = document.createElement('span');
      s.innerHTML = `<span class="swatch" style="background: ${sectorColorHex(i)};"></span>${name}`;
      legend.appendChild(s);
    });
    wrap.appendChild(legend);

    try {
      await ensureDeps();
    } catch (e) {
      status.textContent = 'sigma load failed';
      emptyState.textContent = `${e.message}`;
      emptyState.style.color = 'var(--red)';
      return { applyStep: () => {}, reset: () => {}, dispose: () => {} };
    }

    const Graph = window.graphology.Graph || window.graphology;
    const forceAtlas2 = window.graphologyLayoutForceatlas2;
    const Sigma = window.Sigma;

    // ---- graph + layout --------------------------------------------------
    const graph = new Graph({ multi: false, type: 'undirected' });

    // Sector anchors as labelled hub nodes — give the force layout a
    // stable skeleton that flows attract toward.
    const RADIUS = 220;
    for (let i = 0; i < N_SECTORS; i += 1) {
      const a = (i / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
      graph.addNode(`__sec_${i}`, {
        label: SECTOR_NAMES[i].toUpperCase(),
        x: RADIUS * Math.cos(a),
        y: RADIUS * Math.sin(a),
        size: 8,
        color: sectorColorHex(i),
        type: 'circle',
        sector: i,
        isAnchor: true,
        bornAt: 0,
      });
    }

    const sigma = new Sigma(graph, sigmaContainer, {
      renderLabels: true,
      labelDensity: 0.06,
      labelRenderedSizeThreshold: 6,
      labelFont: 'JetBrains Mono, SF Mono, Menlo, monospace',
      labelSize: 10,
      labelColor: { color: '#9ea2a8' },
      defaultEdgeColor: '#2a2d33',
      minCameraRatio: 0.5,
      maxCameraRatio: 2.5,
    });

    // Continuous ForceAtlas2. We re-run a short iteration per step
    // rather than a worker so the prototype anchors stay pinned and
    // the layout converges fast enough between frames.
    function tickLayout() {
      const fa2 = forceAtlas2.assign || forceAtlas2;
      // Pin sector anchors.
      graph.forEachNode((nid, attr) => {
        if (attr.isAnchor) { attr.fixed = true; }
      });
      try {
        fa2(graph, {
          iterations: 6,
          settings: {
            barnesHutOptimize: false,
            gravity: 0.4,
            scalingRatio: 6,
            slowDown: 6,
            outboundAttractionDistribution: false,
          },
        });
      } catch (e) {
        // forceatlas2 occasionally errors on degenerate graph state;
        // skip this tick rather than break the loop.
      }
    }

    // ---- state machine ---------------------------------------------------
    const NODE_TTL_MS = 10_000;
    const EDGE_TTL_MS = 2_500;
    const MAX_NODES = 800;
    const MAX_EDGES = 600;

    // proto_idx → { lastSeen, sector, activity }
    const nodeMeta = new Map();
    // edgeKey → { addedAt, sec_a }
    const edgeMeta = new Map();

    function nodeKey(protoIdx) { return `p${protoIdx}`; }
    function edgeKey(a, b) { return a < b ? `${a}-${b}` : `${b}-${a}`; }

    function ensureNode(protoIdx, sector, now) {
      const k = nodeKey(protoIdx);
      if (graph.hasNode(k)) {
        const meta = nodeMeta.get(k);
        meta.lastSeen = now;
        meta.activity = Math.min(40, meta.activity + 1);
        // Bump rendered size from accumulated activity.
        graph.setNodeAttribute(k, 'size', 2 + Math.log2(meta.activity + 1) * 1.8);
        return;
      }
      // Initial position: jitter around the sector anchor.
      const a = (sector / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
      const jitter = 60 + Math.random() * 40;
      const x = (RADIUS - jitter) * Math.cos(a) + (Math.random() - 0.5) * 30;
      const y = (RADIUS - jitter) * Math.sin(a) + (Math.random() - 0.5) * 30;
      graph.addNode(k, {
        x, y,
        size: 2,
        color: sectorColorHex(sector),
        label: '',
        type: 'circle',
        sector,
        isAnchor: false,
      });
      nodeMeta.set(k, { lastSeen: now, sector, activity: 1 });
    }

    function ensureEdge(protoA, protoB, sector, now) {
      const ek = edgeKey(protoA, protoB);
      const ka = nodeKey(protoA);
      const kb = nodeKey(protoB);
      if (!graph.hasNode(ka) || !graph.hasNode(kb)) return;
      if (graph.hasEdge(ka, kb)) {
        // Refresh timestamp so it stays visible while the pair keeps trading.
        const meta = edgeMeta.get(ek);
        if (meta) meta.addedAt = now;
        return;
      }
      graph.addEdgeWithKey(ek, ka, kb, {
        color: sectorColorHex(sector),
        size: 1.2,
      });
      edgeMeta.set(ek, { addedAt: now, sec_a: sector });
    }

    function evictStale(now) {
      // Edges first (smaller, less expensive removal).
      let edgeDrop = 0;
      for (const [ek, meta] of edgeMeta) {
        if (now - meta.addedAt > EDGE_TTL_MS) {
          if (graph.hasEdge(ek)) graph.dropEdge(ek);
          edgeMeta.delete(ek);
          edgeDrop += 1;
        }
      }
      // Nodes: drop idle ones, but never drop sector anchors.
      let nodeDrop = 0;
      for (const [nk, meta] of nodeMeta) {
        if (now - meta.lastSeen > NODE_TTL_MS) {
          if (graph.hasNode(nk)) graph.dropNode(nk);
          nodeMeta.delete(nk);
          nodeDrop += 1;
        }
      }
      // Hard caps: if still over, drop oldest.
      if (nodeMeta.size > MAX_NODES) {
        const sorted = [...nodeMeta.entries()].sort((a, b) => a[1].lastSeen - b[1].lastSeen);
        const drop = nodeMeta.size - MAX_NODES;
        for (let i = 0; i < drop; i += 1) {
          const [nk] = sorted[i];
          if (graph.hasNode(nk)) graph.dropNode(nk);
          nodeMeta.delete(nk);
          nodeDrop += 1;
        }
      }
      if (edgeMeta.size > MAX_EDGES) {
        const sorted = [...edgeMeta.entries()].sort((a, b) => a[1].addedAt - b[1].addedAt);
        const drop = edgeMeta.size - MAX_EDGES;
        for (let i = 0; i < drop; i += 1) {
          const [ek] = sorted[i];
          if (graph.hasEdge(ek)) graph.dropEdge(ek);
          edgeMeta.delete(ek);
          edgeDrop += 1;
        }
      }
      return { edgeDrop, nodeDrop };
    }

    // Layout ticker — runs every animation frame so motion stays smooth.
    let raf = requestAnimationFrame(function loop() {
      tickLayout();
      raf = requestAnimationFrame(loop);
    });

    // ---- public API ------------------------------------------------------

    function applyStep(step) {
      const pairs = step.pair_samples || [];
      if (!pairs.length) return;
      emptyState.style.display = 'none';
      const now = performance.now();
      // Process up to a per-step cap so a huge K (~5000) doesn't stall.
      const TAKE = Math.min(pairs.length, 600);
      for (let i = 0; i < TAKE; i += 1) {
        const rec = pairs[i];
        if (!rec.executed) continue;
        ensureNode(rec.proto_a, rec.sec_a, now);
        ensureNode(rec.proto_b, rec.sec_b, now);
        ensureEdge(rec.proto_a, rec.proto_b, rec.sec_a, now);
      }
      evictStale(now);
      status.textContent = `step ${step.step} · ${nodeMeta.size} nodes · ${edgeMeta.size} edges`;
    }

    function reset() {
      // Drop all non-anchor nodes/edges.
      for (const ek of [...edgeMeta.keys()]) {
        if (graph.hasEdge(ek)) graph.dropEdge(ek);
      }
      for (const nk of [...nodeMeta.keys()]) {
        if (graph.hasNode(nk)) graph.dropNode(nk);
      }
      nodeMeta.clear();
      edgeMeta.clear();
      status.textContent = 'idle';
      emptyState.style.display = '';
    }

    function dispose() {
      cancelAnimationFrame(raf);
      try { sigma.kill(); } catch (e) { /* sigma version differences */ }
    }

    status.textContent = 'idle · waiting for run';
    return { applyStep, reset, dispose };
  }

  window.createGraph = createGraph;
})();
