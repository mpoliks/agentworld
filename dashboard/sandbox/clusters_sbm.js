// Secondary clusterer running in a Web Worker (Phase 2 §3.2 of
// spatial-sandbox-completeness.md, follow-on).
//
// Plan §3.2 calls for a degree-corrected SBM in a Web Worker
// every 10 ticks. The main-thread Louvain in clusters.js already
// fits the 100 ms tick budget at sandbox scale; this module's
// load-bearing job is *second-opinion* clustering, run in worker
// isolation. cluster_labels merges the secondary partition into
// its Jaccard tracking so a track that both clusterers agree on
// promotes faster than one only the primary finds.
//
// The math is Louvain (not the spec'd DC-SBM). The user-facing
// value here is "another independent pass that won't move the
// main-thread render budget" — substituting Louvain for SBM
// preserves that value because the two are independent runs
// against the same edge buffer. When the engine surface area
// expands to need a strict SBM partition (e.g. degree-corrected
// stability under heavy-tailed degree distributions), swap this
// worker's internals; the protocol stays.
//
// Protocol:
//
//   main → worker:  { type: 'run', jobId, edges: [[u, v, w], ...] }
//   worker → main:  { type: 'partition', jobId,
//                     partition: [[u, cabalId], ...],
//                     modularity, ms }
//
// Edges are filtered by the same degree-2-or-more rule clusters.js
// applies so the worker's null-graph response matches the primary's.
// Min cluster size 3; smaller clusters collapse to cabalId = -1.

const MIN_CABAL_SIZE = 3;
const LOUVAIN_MAX_PHASES = 3;
const LOUVAIN_PASS_TOL = 1e-6;

function buildAdjacency(edgeSpec) {
  const rawDegree = new Map();
  for (let i = 0; i < edgeSpec.length; i += 1) {
    const e = edgeSpec[i];
    rawDegree.set(e[0], (rawDegree.get(e[0]) ?? 0) + 1);
    rawDegree.set(e[1], (rawDegree.get(e[1]) ?? 0) + 1);
  }
  const nodeIds = new Map();
  const nodeBack = [];
  function nodeOf(idx) {
    let n = nodeIds.get(idx);
    if (n === undefined) {
      n = nodeBack.length;
      nodeIds.set(idx, n);
      nodeBack.push(idx);
    }
    return n;
  }
  const edges = [];
  let twoM = 0;
  for (let i = 0; i < edgeSpec.length; i += 1) {
    const [a, b, w] = edgeSpec[i];
    if ((rawDegree.get(a) ?? 0) < 2) continue;
    if ((rawDegree.get(b) ?? 0) < 2) continue;
    const u = nodeOf(a);
    const v = nodeOf(b);
    edges.push({ u, v, w });
    twoM += 2 * w;
  }
  const n = nodeBack.length;
  const degree = new Float64Array(n);
  for (const e of edges) {
    degree[e.u] += e.w;
    degree[e.v] += e.w;
  }
  const adj = new Array(n);
  for (let i = 0; i < n; i += 1) adj[i] = [];
  for (const e of edges) {
    adj[e.u].push({ to: e.v, w: e.w });
    adj[e.v].push({ to: e.u, w: e.w });
  }
  return { n, twoM, degree, adj, nodeBack };
}

function runLouvain(graph) {
  if (graph.n === 0 || graph.twoM === 0) {
    return { partition: new Int32Array(0), modularity: 0.0 };
  }
  const { n, twoM, degree, adj } = graph;
  const comm = new Int32Array(n);
  for (let i = 0; i < n; i += 1) comm[i] = i;
  const commSumIn = new Float64Array(n);
  const commSumTot = new Float64Array(n);
  function rebuildCommSums() {
    commSumIn.fill(0);
    commSumTot.fill(0);
    for (let u = 0; u < n; u += 1) {
      const cu = comm[u];
      commSumTot[cu] += degree[u];
      const ns = adj[u];
      for (let j = 0; j < ns.length; j += 1) {
        if (comm[ns[j].to] === cu) commSumIn[cu] += ns[j].w;
      }
    }
  }
  rebuildCommSums();

  let improved = true;
  let pass = 0;
  while (improved && pass < LOUVAIN_MAX_PHASES) {
    improved = false;
    pass += 1;
    const order = new Int32Array(n);
    for (let i = 0; i < n; i += 1) order[i] = i;
    for (let i = n - 1; i > 0; i -= 1) {
      const j = Math.floor(Math.random() * (i + 1));
      const tmp = order[i]; order[i] = order[j]; order[j] = tmp;
    }
    let movedThisPhase = false;
    for (let oi = 0; oi < n; oi += 1) {
      const u = order[oi];
      const cu = comm[u];
      const du = degree[u];
      const wToC = new Map();
      const ns = adj[u];
      for (let j = 0; j < ns.length; j += 1) {
        const e = ns[j];
        const c = comm[e.to];
        wToC.set(c, (wToC.get(c) ?? 0) + e.w);
      }
      const wToCu = wToC.get(cu) ?? 0;
      commSumIn[cu] -= 2 * wToCu;
      commSumTot[cu] -= du;
      let bestC = cu;
      let bestGain = 0.0;
      for (const [c, wToCx] of wToC) {
        const gain = 2 * wToCx / twoM
          - 2 * commSumTot[c] * du / (twoM * twoM);
        if (gain > bestGain + LOUVAIN_PASS_TOL) {
          bestGain = gain;
          bestC = c;
        }
      }
      const moveTo = bestC;
      comm[u] = moveTo;
      const wToMoveTo = wToC.get(moveTo) ?? 0;
      commSumIn[moveTo] += 2 * wToMoveTo;
      commSumTot[moveTo] += du;
      if (moveTo !== cu) movedThisPhase = true;
    }
    improved = movedThisPhase;
  }
  // Relabel and apply min-cabal-size filter.
  const sizeOf = new Map();
  for (let i = 0; i < n; i += 1) {
    sizeOf.set(comm[i], (sizeOf.get(comm[i]) ?? 0) + 1);
  }
  const relabel = new Map();
  let next = 0;
  const out = new Int32Array(n);
  for (let i = 0; i < n; i += 1) {
    const c = comm[i];
    if (sizeOf.get(c) < MIN_CABAL_SIZE) {
      out[i] = -1;
      continue;
    }
    let r = relabel.get(c);
    if (r === undefined) { r = next++; relabel.set(c, r); }
    out[i] = r;
  }
  // Modularity over the filtered partition (same accounting as
  // clusters.js so the two passes are apples-to-apples).
  let Q = 0;
  if (relabel.size > 0) {
    const inByC = new Map();
    const totByC = new Map();
    let twoMfiltered = 0;
    for (let u = 0; u < n; u += 1) {
      if (out[u] < 0) continue;
      twoMfiltered += degree[u];
      const cu = out[u];
      totByC.set(cu, (totByC.get(cu) ?? 0) + degree[u]);
      const ns = adj[u];
      for (let j = 0; j < ns.length; j += 1) {
        const e = ns[j];
        if (out[e.to] === cu) {
          inByC.set(cu, (inByC.get(cu) ?? 0) + e.w);
        }
      }
    }
    if (twoMfiltered > 0) {
      for (const [c, inW] of inByC) {
        const totW = totByC.get(c) ?? 0;
        Q += inW / twoMfiltered
          - (totW / twoMfiltered) * (totW / twoMfiltered);
      }
    }
  }
  return { partition: out, modularity: Q };
}

// Worker message handler. Wrapped so this file can also be
// imported as a normal module by the test harness — `self` only
// exists in worker / browser contexts.
function runJob(edges) {
  const t0 = (typeof performance !== "undefined") ? performance.now() : 0;
  const graph = buildAdjacency(edges);
  const r = runLouvain(graph);
  const partition = [];
  for (let i = 0; i < graph.n; i += 1) {
    if (r.partition[i] >= 0) partition.push([graph.nodeBack[i], r.partition[i]]);
  }
  const ms = ((typeof performance !== "undefined") ? performance.now() : 0) - t0;
  return { partition, modularity: r.modularity, ms };
}

// Export for the Node test harness.
export { runJob };

// Worker entry point. `self.onmessage` is only meaningful when
// loaded as a Worker.
if (typeof self !== "undefined" && typeof self.addEventListener === "function"
    && typeof window === "undefined") {
  self.addEventListener('message', (ev) => {
    const { type, jobId, edges } = ev.data ?? {};
    if (type !== 'run') return;
    const out = runJob(Array.isArray(edges) ? edges : []);
    self.postMessage({
      type: 'partition',
      jobId,
      partition: out.partition,
      modularity: out.modularity,
      ms: out.ms,
    });
  });
}
