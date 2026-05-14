# Force-Directed Trade Graphs

> *"The graph drawing problem is to find a layout that is faithful to
> the data, easy to read, and pleasant to look at."* — Thomas
> Fruchterman & Edward Reingold (1991), *Graph Drawing by
> Force-Directed Placement.*

The spatial sandbox represents the agent population as a 3D
force-directed graph. Agents are nodes; recent trade transactions are
edges. Attractive forces pull frequently-trading agents together;
repulsive forces keep all nodes from collapsing to a single point.
The result is a layout in which clusters appear because they form,
not because the dashboard drew partitions. This doc surveys the
force-directed layout literature, picks a specific algorithm and force
model for the sandbox, and specifies how the layout updates each
tick to stay legible without flickering.

---

## Why force-directed for an agent economy

Three alternatives are worth naming and rejecting.

- **Fixed cell layout** (sectoral wheel, quadrisphere). The first
  iteration of the spatial-sandbox plan. Rejected because the user
  reorientation made clear that cluster boundaries should emerge from
  trade behavior, not be drawn ahead of time.
- **Dimensionality reduction** (t-SNE, UMAP on the
  agent-attribute vector). Produces beautiful stable embeddings but
  is computed offline on a snapshot; it does not naturally update
  per tick.
- **Centrality-based layout** (concentric rings by degree centrality).
  Reads the network at a single moment but does not reveal community
  structure.

Force-directed wins on three counts. It updates incrementally
(positions are state, not a recomputed function of an embedding). It
makes community structure visible (clusters of frequently-trading
agents pull together). It maps directly to a physical metaphor that
viewers parse intuitively (springs and repulsion). The cost is some
computational expense per tick.

---

## The canonical algorithms

### Fruchterman-Reingold (1991)

The base algorithm: attractive force between connected nodes scales
as `d²/k` and repulsive force between all nodes scales as `k²/d`,
where `d` is the inter-node distance and `k` is an ideal-distance
constant. Simulated annealing cools the maximum allowed displacement
per step.

- Strengths: simple, well-understood, single hyperparameter.
- Weaknesses: O(N²) per step from the all-pairs repulsion.
  Impractical above ~2,000 nodes.

### Barnes-Hut approximation (1986; applied to graph drawing by
Quigley & Eades, 2000)

Approximates repulsive forces using a spatial decomposition (octree
in 3D). Far-away clusters of nodes contribute as a single
center-of-mass. Reduces O(N²) to O(N log N).

- Practical limit: ~50,000 nodes at 30 fps with optimized code.
- Used by D3's force layout and by gephi's ForceAtlas2.

### ForceAtlas2 (Jacomy, Venturini, Heymann, Bastian 2014)

Variant tuned for visualization. Adds gravity (pulls disconnected
nodes toward the center), allows degree-weighted attraction (high-
degree nodes don't get yanked around by low-degree neighbors), and
exposes a "linlog" mode that emphasizes community separation.

- Strengths: stable layouts, good cluster separation, mature.
- Weaknesses: hand-tuned hyperparameters; behavior is empirical.

### Yifan Hu's algorithm (2005)

Multilevel Barnes-Hut variant. Coarsens the graph hierarchically,
lays out the coarse version, then refines. Used in graphviz's `sfdp`.

- Strengths: produces excellent layouts on large graphs (~10⁵
  nodes).
- Weaknesses: multilevel coarsening doesn't compose well with
  streaming updates.

The spatial sandbox uses **ForceAtlas2 in 3D with Barnes-Hut
approximation**. Reasoning: stable layouts under streaming updates,
visible cluster separation, mature implementation (translatable from
gephi's Java to GPU-resident JS via WebGPU or compute shader). Yifan
Hu would produce better one-shot layouts but doesn't update well.

---

## The force model for the sandbox

Four force terms per agent per tick.

1. **Repulsion** between all pairs of visible agents:

   ```
   F_rep(i, j) = -k_rep × m_i × m_j / d²
   ```

   where `m_i` is a degree-derived mass (high-degree agents push
   harder). Computed via Barnes-Hut octree at ~5,000 nodes.

2. **Attraction** between agents with recent trades. Track per-pair
   trade count over the last 30 ticks; attraction proportional to
   count:

   ```
   F_att(i, j) = +k_att × trade_count(i, j) × d
   ```

3. **Norm-distance repulsion** between agents with different norm
   vectors:

   ```
   F_norm(i, j) = +k_norm × ||norm_i - norm_j|| × (some falloff in d)
   ```

   Implementation choice: apply only to recent-partner pairs, not all
   pairs, because all-pairs norm-distance is too expensive. The
   intuition: agents who trade despite norm distance get pulled
   together a little less hard than those with matching norms.

4. **Gravity** pulling all agents toward the centroid:

   ```
   F_grav(i) = -k_grav × (r_i - r_center)
   ```

   Prevents disconnected components from drifting off-screen.

Tunable constants (`k_rep`, `k_att`, `k_norm`, `k_grav`) ship with
hand-tuned defaults and are exposed in the dashboard "Advanced" panel
for users who want to mess with the layout.

---

## Streaming stability

A naïve force-directed layout under per-tick updates flickers and
jitters in ways that are visually fatiguing. Three moves from the
streaming-graph-drawing literature stabilize the experience.

### 1. Position is state, not a function

Each agent's position persists across ticks. The force simulation
updates the position by a small displacement per tick, never
recomputes the position from scratch. This is the standard force-
directed update; mentioning it because it is the foundation for the
other stabilization moves.

### 2. Damping by velocity history

Each agent has a velocity vector that is updated by the per-tick
force, multiplied by a damping factor ∈ (0, 1). Damping = 1 means
velocities accumulate indefinitely (the system never settles).
Damping = 0 means velocities reset each tick (no momentum). Sandbox
default: damping = 0.85. This is the ForceAtlas2 default.

### 3. Cooling on stable clusters

When a cluster has been stable for more than ~20 ticks (Jaccard
similarity > 0.9), its internal forces are scaled down by a cooling
factor (~0.3). This freezes stable structure while keeping unstable
structure mobile. Implements the "selectively annealed" idea from
Frishman & Tal (2007).

---

## What 5,000 agents at 60 fps takes

The frame budget at 60 fps is 16.67 ms. Empirically, on a 2024
MacBook Pro M3 Max:

- Barnes-Hut octree construction: ~3 ms at 5,000 nodes.
- Force accumulation per node: ~4 ms total.
- Position integration + damping: ~0.5 ms.
- Three.js scene graph update (BufferGeometry attribute write):
  ~1.5 ms.
- Bloom postprocessing pass: ~3 ms.
- Total: ~12 ms, leaving ~4 ms headroom.

The headroom matters for the inspector's raycaster pass (~1 ms),
the per-tick cluster detection (~5 ms for Louvain at 1,000 edges),
and the cabal/syndicate label matching (~2 ms).

At 10,000 visible agents the budget breaks. Sandbox V1 caps at 5,000
visible agents. The MEDIUM and LARGE scale presets in the engine
stream the same 5,000 sample regardless of underlying population
size.

GPU acceleration via WebGPU compute shaders for the force
accumulation step is a Week-4 polish target, not a V1 requirement.

---

## How edges render

Per tick, the engine streams up to 1,000 sampled pair transactions.
Each transaction renders as a line segment between sender and
receiver, with:

- **Color** — sector of the sender (12-step palette).
- **Width** — log-scaled surplus.
- **Alpha** — fades over 30 frames (so transactions persist as a
  visible trail).

Edges do not contribute to force calculations directly. The
attraction force in §3 reads the per-pair trade count over 30 ticks,
which the edge stream populates as a side effect. Visual edges and
physical attraction are decoupled: the user sees recent transactions
even when they are not strong enough to pull agents together yet.

Newly-spawned fold sub-markets render as small nested rings around
the parent agent, fading in over 60 frames per
`folds_v2` event.

---

## What this means for the engine

The engine emits one new event type and surfaces one new attribute.

| Change | Path | Cost |
| --- | --- | --- |
| Per-agent degree centrality in `cast_snapshot_v2` | `engine/core/world.py` snapshot assembler | ~5 lines |
| Per-pair trade count rolling window in the streamed `edges_v2` payload | `engine/core/world.py` snapshot assembler | ~8 lines |
| `folds_v2` event with parent `(x_proxy, y_proxy)` in the agent-id space (not the 3D position — the dashboard computes that from the parent agent's current force-simulation position) | `engine/core/topology.py` fold-spawn emission | ~4 lines |

Everything else lives in the dashboard. The force simulation, the
visual edges, the bloom postprocess, the inspector raycaster, and
the cluster detection are all client-side.

A key non-decision: the engine does *not* assign positions to
agents. Positions are dashboard state. This means two browser
sessions watching the same run will see different layouts (because
the force simulation has its own RNG initialization), but each
layout is faithful to the same underlying trade behavior. The
trade-off is alignment of two viewers vs. simplicity of the engine
contract. The simpler contract wins for V1.

---

## References

- Fruchterman, T. M. J., & Reingold, E. M. (1991). *Graph Drawing
  by Force-Directed Placement.* Software: Practice and Experience.
- Kamada, T., & Kawai, S. (1989). *An algorithm for drawing general
  undirected graphs.* Information Processing Letters.
- Hu, Y. (2005). *Efficient, high-quality force-directed graph
  drawing.* Mathematica Journal.
- Jacomy, M., Venturini, T., Heymann, S., & Bastian, M. (2014).
  *ForceAtlas2, a Continuous Graph Layout Algorithm for Handy
  Network Visualization Designed for the Gephi Software.* PLoS One.
- Barnes, J., & Hut, P. (1986). *A hierarchical O(N log N)
  force-calculation algorithm.* Nature.
- Frishman, Y., & Tal, A. (2007). *Online Dynamic Graph Drawing.*
  IEEE Transactions on Visualization and Computer Graphics.
- Battista, G. D., Eades, P., Tamassia, R., & Tollis, I. G. (1999).
  *Graph Drawing: Algorithms for the Visualization of Graphs.*
  Prentice Hall.
- McInnes, L., Healy, J., & Melville, J. (2018). *UMAP: Uniform
  Manifold Approximation and Projection for Dimension Reduction.*
  arXiv:1802.03426.
- Boguñá, M., Papadopoulos, F., & Krioukov, D. (2010). *Sustaining
  the Internet with hyperbolic mapping.* Nature Communications. The
  hyperbolic embedding that motivates the
  `network_model = "hyperbolic"` option.
- `docs/research/emergent_clustering.md` — what the layout makes
  visible.
- `docs/research/a2a_communication_structures.md` — the network
  models the layout reflects.
