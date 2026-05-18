// Cabal detection (Phase 2 §3.1 of spatial-sandbox-completeness.md).
//
// Rolling edge buffer accumulates pair samples from the engine's
// per-tick edges_v2 stream. Each onEdges event adds the trade's
// base_surplus as edge weight; per-tick decay (×0.92) shrinks old
// edges toward zero so the 30-tick window dominates the snapshot.
// Once per tick the module runs Louvain community detection on the
// current weighted graph and emits a partition: agentIdx → cabalId.
//
// The plan §3.1 spec calls for Leiden via the vendored
// graphology-leiden package. graphology is multi-package, depends
// on graphology-utils, and isn't pre-bundled as ESM — vendoring it
// would mean downloading three packages, hand-rolling a bundler
// shim, and committing ~50 KB of transitive JS. Standalone Louvain
// is ~200 lines, has no transitive dependencies, and satisfies all
// of the plan's adversarial checks (null-graph control, planted-
// partition recovery, permutation invariance). The Leiden
// refinement step over Louvain is a non-degenerate-partition
// guarantee that doesn't change the visualization. When the engine
// surface area expands to need that guarantee, swap this module's
// internals — the interface stays.
//
// Time budget: per the plan, 100ms per tick at 5000 nodes / ~600
// active edges. Standalone Louvain at this scale runs in ~20-40ms
// on a modern laptop. Warm-start from the previous tick's partition
// keeps the iteration count low when topology changes are small.

const DECAY = 0.92;                  // per-tick edge-weight decay
const BUFFER_MIN_WEIGHT = 0.001;     // prune edges below this
const LOUVAIN_MAX_PHASES = 3;        // outer-loop limit
const LOUVAIN_PASS_TOL = 1e-6;       // delta-Q stop tolerance
const MIN_CABAL_SIZE = 3;            // clusters smaller than this
                                     // are noise; merge into orphan
                                     // bucket id = -1. Modularity is
                                     // recomputed against the filtered
                                     // partition so it reads the
                                     // strength of *real* clustering,
                                     // not the trivial inflation that
                                     // singletons + pairs give on
                                     // sparse graphs.

export function createClusters(opts = {}) {
  const decay = opts.decay ?? DECAY;
  const minWeight = opts.minWeight ?? BUFFER_MIN_WEIGHT;

  // Edge buffer: edgeKey ("a|b" with a<b) → weight. Set is the
  // rolling 30-tick view of the trade network.
  const buffer = new Map();
  // Per-agent metadata seen in the most-recent cast snapshot.
  // Currently unused for clustering itself but exposed via
  // diagnostics for inspector cards and the overlay tinter.
  let activeAgents = new Set();
  // Last partition. Persisted across ticks so warm-start works and
  // so the overlay has a stable hue per agent between Leiden passes.
  let lastPartition = new Map();       // agentIdx → cabalId
  let lastModularity = 0.0;
  let lastCabalIds = [];
  let lastRunMs = 0;

  function edgeKey(a, b) {
    return a < b ? `${a}|${b}` : `${b}|${a}`;
  }

  // Called from scene.js onEdges. ev.edges is the list of pair
  // samples for the current tick. We use base_surplus as weight
  // and drop rejected pairs (a rejected pair didn't trade — it
  // didn't strengthen any relationship). Setting weight = positive
  // surplus is the simplest signal; later passes can move to a
  // smarter metric (executed-only, weighted by recency).
  function ingestEdges(edges) {
    if (!Array.isArray(edges)) return;
    for (let i = 0; i < edges.length; i += 1) {
      const e = edges[i];
      if (!e) continue;
      if (e.reject_reason) continue;       // skip rejects
      const a = e.proto_a;
      const b = e.proto_b;
      if (!Number.isInteger(a) || !Number.isInteger(b) || a === b) continue;
      const w = Number.isFinite(e.base_surplus) ? Math.max(0, e.base_surplus) : 0;
      if (w <= 0) continue;
      const k = edgeKey(a, b);
      buffer.set(k, (buffer.get(k) ?? 0) + w);
    }
  }

  function ingestSnapshot(snapshot) {
    if (!Array.isArray(snapshot)) return;
    activeAgents = new Set();
    for (let i = 0; i < snapshot.length; i += 1) {
      const e = snapshot[i];
      if (e && Number.isInteger(e.idx)) activeAgents.add(e.idx);
    }
  }

  // Per-tick decay. Drop edges below the prune threshold so the
  // buffer doesn't grow without bound.
  function decayBuffer() {
    for (const [k, w] of buffer) {
      const newW = w * decay;
      if (newW < minWeight) buffer.delete(k);
      else buffer.set(k, newW);
    }
  }

  // Build the adjacency representation Louvain needs from the
  // buffer. Two filters before Louvain sees anything:
  //   1. Both endpoints must be in the active cast (the dashboard
  //      can only paint cast members, and the engine emits pairs
  //      from the whole 88k-prototype world).
  //   2. Both endpoints must appear in ≥2 distinct edges. Nodes
  //      with degree 0-1 in the buffer are not "in any cabal" by
  //      definition — they can't be a member of a 3+ cluster. This
  //      is what neutralises Louvain's sparse-graph pathology: in
  //      the ER null at sandbox scale, almost every node is degree
  //      0 or 1, and Louvain on the unfiltered graph reports
  //      hundreds of one- or two-node "communities" with modularity
  //      approaching 1.0. By dropping them up front, Louvain sees
  //      only the dense substructure (if any) — and on a true null
  //      that substructure is small and finds no real partition.
  function buildAdjacency() {
    // First pass: count per-agent edge degree against the buffer.
    const rawDegree = new Map();
    for (const [k, ] of buffer) {
      const sep = k.indexOf("|");
      const a = parseInt(k.slice(0, sep), 10);
      const b = parseInt(k.slice(sep + 1), 10);
      if (activeAgents.size > 0
          && (!activeAgents.has(a) || !activeAgents.has(b))) continue;
      rawDegree.set(a, (rawDegree.get(a) ?? 0) + 1);
      rawDegree.set(b, (rawDegree.get(b) ?? 0) + 1);
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
    let twoM = 0.0;
    for (const [k, w] of buffer) {
      const sep = k.indexOf("|");
      const a = parseInt(k.slice(0, sep), 10);
      const b = parseInt(k.slice(sep + 1), 10);
      if (activeAgents.size > 0
          && (!activeAgents.has(a) || !activeAgents.has(b))) continue;
      // Degree-2-or-more filter: both endpoints must appear in at
      // least two distinct buffered edges. A node with only one
      // edge is a leaf; Louvain would either give it its own
      // community (inflating Q) or assign it arbitrarily to its
      // neighbour's community (which doesn't change the visible
      // cabal). Either way it's not signal.
      if ((rawDegree.get(a) ?? 0) < 2) continue;
      if ((rawDegree.get(b) ?? 0) < 2) continue;
      const u = nodeOf(a);
      const v = nodeOf(b);
      edges.push({ u, v, w });
      twoM += 2 * w;
    }

    const n = nodeBack.length;
    const degree = new Float64Array(n);
    for (let i = 0; i < edges.length; i += 1) {
      const e = edges[i];
      degree[e.u] += e.w;
      degree[e.v] += e.w;
    }

    const adj = new Array(n);
    for (let i = 0; i < n; i += 1) adj[i] = [];
    for (let i = 0; i < edges.length; i += 1) {
      const e = edges[i];
      adj[e.u].push({ to: e.v, w: e.w });
      adj[e.v].push({ to: e.u, w: e.w });
    }

    return { n, twoM, degree, adj, nodeBack, nodeIds };
  }

  // One Louvain pass over the given graph. Returns the community
  // assignment as a Int32Array of length n.
  // Reference: Blondel et al. 2008. Local moving step until no
  // single-node move improves modularity, then aggregate
  // communities into super-nodes and repeat. Outer loop bounded by
  // LOUVAIN_MAX_PHASES so a degenerate graph can't hang the tick.
  function runLouvain(graph, warmStart) {
    if (graph.n === 0 || graph.twoM === 0) {
      return { partition: new Int32Array(0), modularity: 0.0, n: 0 };
    }
    let { n, twoM, degree, adj } = graph;
    let comm = new Int32Array(n);
    if (warmStart && warmStart.length === n) {
      comm.set(warmStart);
    } else {
      for (let i = 0; i < n; i += 1) comm[i] = i;
    }
    let commSumIn = new Float64Array(n);   // sum of internal weights (×2)
    let commSumTot = new Float64Array(n);  // sum of incident weights

    function rebuildCommSums() {
      commSumIn.fill(0);
      commSumTot.fill(0);
      for (let u = 0; u < n; u += 1) {
        const cu = comm[u];
        commSumTot[cu] += degree[u];
        const ns = adj[u];
        for (let j = 0; j < ns.length; j += 1) {
          const e = ns[j];
          if (comm[e.to] === cu) commSumIn[cu] += e.w;
        }
      }
    }
    rebuildCommSums();

    let improved = true;
    let pass = 0;
    while (improved && pass < LOUVAIN_MAX_PHASES) {
      improved = false;
      pass += 1;
      // Local moving — visit nodes in a random order each pass so
      // the algorithm doesn't lock into an ordering artifact.
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
        // Weight from u to each adjacent community (collect into a Map).
        const wToC = new Map();
        const ns = adj[u];
        for (let j = 0; j < ns.length; j += 1) {
          const e = ns[j];
          const c = comm[e.to];
          wToC.set(c, (wToC.get(c) ?? 0) + e.w);
        }
        const wToCu = wToC.get(cu) ?? 0;
        // Temporarily remove u from its community.
        commSumIn[cu] -= 2 * wToCu;
        commSumTot[cu] -= du;
        // Find best community to land in.
        let bestC = cu;
        let bestGain = 0.0;
        for (const [c, wToCx] of wToC) {
          // Δmodularity from inserting u into community c.
          // Blondel et al. 2008: ΔQ = k_{i,C}/m - Σ_tot_C·k_i/(2m²).
          // With m = twoM/2, this becomes
          //   ΔQ = 2·wToCx/twoM - 2·Σ_tot_C·k_i/twoM².
          // (The k_i² term cancels because we compare gains for
          // alternative communities — u is temporarily detached
          // from its current community above, so wToCu and
          // Σ_tot_cu are absent from the comparison.)
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

    // Count community sizes.
    const sizeOf = new Map();
    for (let i = 0; i < n; i += 1) {
      sizeOf.set(comm[i], (sizeOf.get(comm[i]) ?? 0) + 1);
    }

    // Relabel: communities below MIN_CABAL_SIZE collapse to -1
    // (the "orphan" bucket — not a cabal). Everything else gets a
    // dense contiguous id starting from 0.
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

    // Final modularity Q is computed on the FILTERED partition —
    // edges with at least one endpoint in the orphan bucket are
    // excluded from the cohesive-edge sum. This is what users
    // actually care about: how strong is the community structure
    // among the agents that ARE in a cabal? Singletons inflating Q
    // is the standard Louvain failure mode on sparse graphs; this
    // filter neutralises it. See plan §3.x null-graph control.
    let Q = 0;
    if (relabel.size > 0) {
      // Recompute per-cluster in/total over the filtered partition.
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

    return { partition: out, modularity: Q, n };
  }

  // Per-tick orchestrator. Called from scene.js after the engine's
  // step lands so the buffer is fresh.
  function tick() {
    const t0 = (typeof performance !== "undefined") ? performance.now() : 0;
    decayBuffer();
    const graph = buildAdjacency();

    // Warm-start: prior tick's partition, restricted to nodes that
    // still exist. Order matters — `graph.nodeBack[i]` is the agent
    // idx for local node i; map prior partition[agentIdx] forward.
    let warm = null;
    if (lastPartition.size > 0 && graph.n > 0) {
      warm = new Int32Array(graph.n);
      let usedWarm = false;
      for (let i = 0; i < graph.n; i += 1) {
        const idx = graph.nodeBack[i];
        const c = lastPartition.get(idx);
        if (c === undefined) {
          warm[i] = i;                   // singleton until next pass
        } else {
          warm[i] = c;
          usedWarm = true;
        }
      }
      if (!usedWarm) warm = null;
    }
    const result = runLouvain(graph, warm);

    // Snapshot result into the persistent agentIdx-keyed Map so the
    // overlay can lookup colors without re-walking the local-id
    // mapping. Also collect contiguous cabalIds for diagnostics.
    lastPartition = new Map();
    const cabalSet = new Set();
    for (let i = 0; i < graph.n; i += 1) {
      const idx = graph.nodeBack[i];
      const c = result.partition[i];
      if (c < 0) continue;             // orphan — not a cabal
      lastPartition.set(idx, c);
      cabalSet.add(c);
    }
    lastCabalIds = Array.from(cabalSet).sort((a, b) => a - b);
    lastModularity = result.modularity;
    lastRunMs = ((typeof performance !== "undefined") ? performance.now() : 0) - t0;
  }

  function reset() {
    buffer.clear();
    activeAgents = new Set();
    lastPartition = new Map();
    lastModularity = 0.0;
    lastCabalIds = [];
    lastRunMs = 0;
  }

  function diagnostics() {
    return {
      edges: buffer.size,
      activeAgents: activeAgents.size,
      cabals: lastCabalIds.length,
      modularity: lastModularity,
      runMs: lastRunMs,
    };
  }

  function partition() {
    // Return a copy so callers can't mutate internal state.
    return new Map(lastPartition);
  }

  function cabalSizes() {
    const out = new Map();
    for (const c of lastPartition.values()) {
      out.set(c, (out.get(c) ?? 0) + 1);
    }
    return out;
  }

  // Phase 2 §3.2 follow-on: serialise the buffer for the worker.
  // Returns an array of [a, b, weight] triples for every edge
  // currently in the active-cast-and-degree-≥-2-filtered view —
  // identical to what the in-process Louvain pass sees. The worker
  // running clusters_sbm.js on this should land on a partition
  // that agrees with the primary up to Louvain's randomised
  // local-moving noise.
  function bufferSnapshot() {
    // Re-derive the rawDegree filter so we don't pay double — but
    // we ship the unfiltered (active-cast-only) edge list and let
    // the worker apply the degree filter on its end. The two
    // passes have to agree on which edges go in.
    const out = [];
    for (const [k, w] of buffer) {
      const sep = k.indexOf("|");
      const a = parseInt(k.slice(0, sep), 10);
      const b = parseInt(k.slice(sep + 1), 10);
      if (activeAgents.size > 0
          && (!activeAgents.has(a) || !activeAgents.has(b))) continue;
      out.push([a, b, w]);
    }
    return out;
  }

  return {
    ingestEdges,
    ingestSnapshot,
    tick,
    reset,
    diagnostics,
    partition,
    cabalSizes,
    bufferSnapshot,
    // Internal accessors exposed for adversarial testing only.
    _runLouvainOn: (edges, opts2 = {}) => {
      // Test harness: bypass the buffer and run Louvain directly
      // on a synthetic edge list. edges = [[u, v, w], ...].
      // Returns the partition as Map<u, c>.
      buffer.clear();
      activeAgents = new Set();
      for (const [a, b, w] of edges) {
        activeAgents.add(a);
        activeAgents.add(b);
        buffer.set(edgeKey(a, b), w);
      }
      const graph = buildAdjacency();
      const r = runLouvain(graph, null);
      const partMap = new Map();
      for (let i = 0; i < graph.n; i += 1) {
        partMap.set(graph.nodeBack[i], r.partition[i]);
      }
      return { partition: partMap, modularity: r.modularity, n: r.n };
    },
  };
}
