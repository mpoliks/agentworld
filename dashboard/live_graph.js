/*
 * dashboard/live_graph.js — d3-force prototype graph (Graph tab).
 *
 * Force-directed social network read from per-pair samples. Each
 * sampled prototype becomes a node attracted to its sector anchor;
 * each executed trade adds a transient edge that fades after ~2.5s.
 * Nodes accumulate a recent-activity count that drives their radius;
 * idle nodes evict after ~10s. Hard cap of 600 active nodes.
 *
 * Uses d3.forceSimulation (already loaded with d3 v7) — no extra
 * CDN dependency. Renders to SVG; 600 circles + 500 lines is well
 * within SVG's comfort range.
 *
 * `window.createGraph(host) → { applyStep, reset, dispose }`.
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
    .lp-graph-svg { width: 100%; height: 100%; display: block; cursor: grab; }
    .lp-graph-svg .anchor { fill: rgba(20, 22, 26, 0.85); stroke-width: 1.5; }
    .lp-graph-svg .anchor-label { font-family: var(--mono); font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; fill: var(--text-2); pointer-events: none; }
    .lp-graph-svg .proto { stroke: var(--bg); stroke-width: 0.6; }
    .lp-graph-svg .edge { stroke-width: 0.6; }
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
    status.textContent = 'idle · waiting for run';
    controls.appendChild(document.createTextNode('Prototype graph · d3-force · ~600-node cap'));
    controls.appendChild(status);
    wrap.appendChild(controls);

    const canvasWrap = document.createElement('div');
    canvasWrap.className = 'lp-graph-canvas-wrap';
    wrap.appendChild(canvasWrap);

    const W = 960;
    const H = 540;
    const RADIUS = 220;
    const cx = W / 2;
    const cy = H / 2;

    if (!window.d3) {
      const err = document.createElement('p');
      err.style.color = 'var(--red)';
      err.style.padding = '12px';
      err.textContent = 'd3 v7 required but not loaded';
      canvasWrap.appendChild(err);
      return { applyStep: () => {}, reset: () => {}, dispose: () => {} };
    }
    const d3 = window.d3;

    const svg = d3.select(canvasWrap).append('svg')
      .attr('class', 'lp-graph-svg')
      .attr('viewBox', `0 0 ${W} ${H}`)
      .attr('preserveAspectRatio', 'xMidYMid meet');

    const emptyState = document.createElement('div');
    emptyState.className = 'lp-graph-empty';
    emptyState.textContent = 'nodes appear here once the run starts';
    canvasWrap.appendChild(emptyState);

    const legend = document.createElement('div');
    legend.className = 'lp-graph-legend';
    SECTOR_NAMES.forEach((name, i) => {
      const s = document.createElement('span');
      s.innerHTML = `<span class="swatch" style="background: ${sectorColor(i)};"></span>${name}`;
      legend.appendChild(s);
    });
    wrap.appendChild(legend);

    // ---- sector anchors (fixed positions; pulled by sector force) --------
    const sectorAnchors = [];
    for (let i = 0; i < N_SECTORS; i += 1) {
      const a = (i / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
      sectorAnchors.push({
        x: cx + RADIUS * Math.cos(a),
        y: cy + RADIUS * Math.sin(a),
        i,
      });
    }

    const anchorGroup = svg.append('g').attr('class', 'anchors');
    anchorGroup.selectAll('circle.anchor')
      .data(sectorAnchors)
      .enter()
      .append('circle')
      .attr('class', 'anchor')
      .attr('cx', (d) => d.x)
      .attr('cy', (d) => d.y)
      .attr('r', 12)
      .attr('stroke', (d) => sectorColor(d.i));
    anchorGroup.selectAll('text.anchor-label')
      .data(sectorAnchors)
      .enter()
      .append('text')
      .attr('class', 'anchor-label')
      .attr('x', (d) => d.x + Math.cos((d.i / N_SECTORS) * 2 * Math.PI - Math.PI / 2) * 24)
      .attr('y', (d) => d.y + Math.sin((d.i / N_SECTORS) * 2 * Math.PI - Math.PI / 2) * 24 + 3)
      .attr('text-anchor', (d) => {
        const a = (d.i / N_SECTORS) * 2 * Math.PI - Math.PI / 2;
        return Math.cos(a) < -0.3 ? 'end' : Math.cos(a) > 0.3 ? 'start' : 'middle';
      })
      .text((d) => SECTOR_NAMES[d.i]);

    const edgeGroup = svg.append('g').attr('class', 'edges');
    const nodeGroup = svg.append('g').attr('class', 'nodes');

    // ---- d3 force simulation --------------------------------------------
    const nodes = [];           // { id, proto, sector, x, y, vx, vy, activity, lastSeen }
    const edges = [];           // { source, target, addedAt, color }
    const nodeById = new Map();
    const edgeByKey = new Map();

    function sectorForce() {
      // Pull each node toward its sector anchor with strength proportional
      // to (1 - activity_normalised) — popular prototypes drift toward the
      // centre of the cluster, lonely ones snap back to their anchor.
      return (alpha) => {
        for (const n of nodes) {
          const a = sectorAnchors[n.sector];
          if (!a) continue;
          const k = 0.045 * alpha;
          n.vx += (a.x - n.x) * k;
          n.vy += (a.y - n.y) * k;
        }
      };
    }

    const sim = d3.forceSimulation(nodes)
      .alphaDecay(0)               // run continuously
      .alphaMin(0)
      .velocityDecay(0.55)
      .force('charge', d3.forceManyBody().strength(-6).distanceMax(80))
      .force('link', d3.forceLink(edges).id((d) => d.id).distance(12).strength(0.6))
      .force('sector', sectorForce())
      .force('collide', d3.forceCollide().radius((d) => d.r + 0.5))
      .on('tick', renderFrame);

    function renderFrame() {
      // Edges.
      const edgeSel = edgeGroup.selectAll('line.edge').data(edges, (d) => d.key);
      edgeSel.enter().append('line').attr('class', 'edge')
        .attr('stroke', (d) => d.color)
        .attr('stroke-opacity', 0.55)
        .merge(edgeSel)
        .attr('x1', (d) => d.source.x)
        .attr('y1', (d) => d.source.y)
        .attr('x2', (d) => d.target.x)
        .attr('y2', (d) => d.target.y)
        .attr('stroke-opacity', (d) => d.opacity);
      edgeSel.exit().remove();

      // Nodes.
      const nodeSel = nodeGroup.selectAll('circle.proto').data(nodes, (d) => d.id);
      nodeSel.enter().append('circle').attr('class', 'proto')
        .merge(nodeSel)
        .attr('cx', (d) => d.x)
        .attr('cy', (d) => d.y)
        .attr('r', (d) => d.r)
        .attr('fill', (d) => d.color)
        .attr('fill-opacity', (d) => d.opacity);
      nodeSel.exit().remove();
    }

    // ---- state machine ---------------------------------------------------
    const NODE_TTL_MS = 10_000;
    const EDGE_TTL_MS = 2_500;
    const MAX_NODES = 600;
    const MAX_EDGES = 500;

    function nodeKey(protoIdx) { return `p${protoIdx}`; }
    function edgeKey(a, b) { return a < b ? `${a}-${b}` : `${b}-${a}`; }

    function ensureNode(protoIdx, sector, now) {
      const id = nodeKey(protoIdx);
      let n = nodeById.get(id);
      if (n) {
        n.lastSeen = now;
        n.activity = Math.min(40, n.activity + 1);
        n.r = 2 + Math.log2(n.activity + 1) * 1.6;
        return n;
      }
      // Seed near sector anchor with jitter so new nodes don't all overlap.
      const a = sectorAnchors[sector];
      n = {
        id,
        proto: protoIdx,
        sector,
        x: a.x + (Math.random() - 0.5) * 30,
        y: a.y + (Math.random() - 0.5) * 30,
        vx: 0, vy: 0,
        activity: 1,
        lastSeen: now,
        r: 2,
        color: sectorColor(sector),
        opacity: 0.95,
      };
      nodes.push(n);
      nodeById.set(id, n);
      return n;
    }

    function ensureEdge(protoA, protoB, sector, now) {
      const ek = edgeKey(protoA, protoB);
      let e = edgeByKey.get(ek);
      const sourceNode = nodeById.get(nodeKey(protoA));
      const targetNode = nodeById.get(nodeKey(protoB));
      if (!sourceNode || !targetNode) return;
      if (e) {
        e.addedAt = now;
        return;
      }
      e = {
        key: ek,
        source: sourceNode,
        target: targetNode,
        addedAt: now,
        color: sectorColor(sector),
        opacity: 0.55,
      };
      edges.push(e);
      edgeByKey.set(ek, e);
    }

    function evictAndAge(now) {
      // Age edges (fade).
      for (let i = edges.length - 1; i >= 0; i -= 1) {
        const e = edges[i];
        const age = now - e.addedAt;
        if (age > EDGE_TTL_MS) {
          edges.splice(i, 1);
          edgeByKey.delete(e.key);
        } else {
          e.opacity = 0.55 * (1 - age / EDGE_TTL_MS);
        }
      }
      // Age nodes.
      for (let i = nodes.length - 1; i >= 0; i -= 1) {
        const n = nodes[i];
        const idle = now - n.lastSeen;
        if (idle > NODE_TTL_MS) {
          nodes.splice(i, 1);
          nodeById.delete(n.id);
        } else {
          n.opacity = 0.5 + 0.5 * Math.max(0, 1 - idle / NODE_TTL_MS);
        }
      }
      // Hard caps.
      if (nodes.length > MAX_NODES) {
        nodes.sort((a, b) => a.lastSeen - b.lastSeen);
        const drop = nodes.length - MAX_NODES;
        for (let i = 0; i < drop; i += 1) {
          nodeById.delete(nodes[i].id);
        }
        nodes.splice(0, drop);
      }
      if (edges.length > MAX_EDGES) {
        edges.sort((a, b) => a.addedAt - b.addedAt);
        const drop = edges.length - MAX_EDGES;
        for (let i = 0; i < drop; i += 1) {
          edgeByKey.delete(edges[i].key);
        }
        edges.splice(0, drop);
      }
    }

    // Resync forces against the latest arrays so d3 sees newly-added items.
    function rebindSim() {
      sim.nodes(nodes);
      sim.force('link').links(edges);
      sim.alpha(0.18).restart();
    }

    // ---- public API ------------------------------------------------------

    function applyStep(step) {
      const pairs = step.pair_samples || [];
      if (!pairs.length) return;
      emptyState.style.display = 'none';
      const now = performance.now();
      // Cap per-step processing so a K=1500 burst doesn't lag the page.
      const TAKE = Math.min(pairs.length, 500);
      for (let i = 0; i < TAKE; i += 1) {
        const rec = pairs[i];
        if (!rec.executed) continue;
        ensureNode(rec.proto_a, rec.sec_a, now);
        ensureNode(rec.proto_b, rec.sec_b, now);
        ensureEdge(rec.proto_a, rec.proto_b, rec.sec_a, now);
      }
      evictAndAge(now);
      rebindSim();
      status.textContent = `step ${step.step} · ${nodes.length} nodes · ${edges.length} edges`;
    }

    function reset() {
      nodes.length = 0;
      edges.length = 0;
      nodeById.clear();
      edgeByKey.clear();
      rebindSim();
      renderFrame();
      status.textContent = 'idle · waiting for run';
      emptyState.style.display = '';
    }

    function dispose() {
      sim.stop();
    }

    return { applyStep, reset, dispose };
  }

  window.createGraph = createGraph;
})();
