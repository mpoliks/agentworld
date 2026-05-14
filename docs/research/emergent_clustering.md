# Emergent Clustering — Cabals, Syndicates, and the Detection of Sectors

> *"Communities are groups of vertices which probably share common
> properties and/or play similar roles within the graph."* — Santo
> Fortunato, *Community detection in graphs* (Physics Reports, 2010).

The user's reorientation: sectors should not be visible as fixed cells
of equal size. Visible groupings should form because agents with
shared profiles and shared trade history come together, not because
the dashboard drew partitions. This doc covers the literature on
community detection in trade networks, distinguishes four kinds of
emergent grouping (sector, firm, cabal, syndicate), and specifies how
the spatial sandbox computes and labels them live.

The result is a soft-label overlay computed by the dashboard, not a
change to the engine's hard `sector_id`. The hard sector remains the
engine's input attribute. Emergent labels are output observations.

---

## Four kinds of grouping, in increasing softness

The terms get used interchangeably in informal discussion. The sandbox
distinguishes them precisely because the user asked for cross-sector
firms and emergent sector formation, both of which require a stable
vocabulary.

**Sector** — engine-level attribute. The 12 named sectors at
`engine/core/population.py:31` (agriculture, extraction,
manufacturing, …). Assigned at population synthesis via Dirichlet
draw. Hard, fixed, predeclared. Used by the transaction kernel's
`sector_affinity` matrix at `engine/core/transactions.py:451`.

**Firm** — engine-level attribute that can form, dissolve, and reform.
Assigned by `InstitutionConfig.formation_step` at
`engine/core/institutions.py:88` when an independent prototype's
surplus crosses a threshold. Currently single-sector by the
binning rule at `institutions.py:88-90` (`bin_key = sector * n_stacks
+ stack`). The user's note: firms should be able to be cross-sector.
The smallest engine change is to replace the binning rule with
`bin_key = stack`, allowing firms to span sectors. That is one of
the engine PRs in the revised plan.

**Cabal** — dashboard-level label. A persistent subgraph of the
recent trade network detected by a community-detection algorithm
(Louvain or equivalent) run on the streaming trade-edge feed. A cabal
is a cluster of agents that trade with each other more than with the
rest of the population over the last ~30 ticks. Cabals can span
sectors and span firms. They are observations, not impositions.

**Syndicate** — dashboard-level label. A cabal whose membership has
been stable for more than ~50 ticks. A syndicate is a cabal that has
ceased to churn. Stability is measured by Jaccard similarity of
membership across consecutive 30-tick windows. Syndicates can outlive
the firms they overlap with.

The four-level vocabulary maps cleanly to the inspector card: an
agent's identity reads "agent N, sector retail, firm 23 (cross-sector),
cabal 4 (12 members), syndicate B (stable for 86 ticks)."

---

## Community-detection methods

Three methods stand out from the literature for streaming agent-trade
graphs. The selection criterion: works on weighted directed graphs at
~5,000 nodes per tick, returns a partition, runs in under 200 ms per
detection pass.

### Louvain modularity

Blondel et al. (2008). Modularity Q is the fraction of edges within
communities minus the expected fraction under a degree-preserving null
model. Louvain greedily maximizes Q by moving nodes between
communities; consolidates communities into super-nodes; repeats.

- Time complexity: O(N log N) empirically; ~50 ms at 5,000 nodes.
- Strengths: fast, well-understood, parameter-free.
- Weaknesses: resolution limit (Fortunato & Barthélemy, 2007) —
  communities below a critical size get merged. For agentworld, this
  caps the smallest detectable cabal at roughly √(2E), where E is the
  edge count. At 1,000 edges/tick, the floor is ~45 nodes.

Louvain is the default for the spatial sandbox cabal detector.

### Leiden modularity

Traag, Waltman, van Eck (2019). Variant of Louvain that fixes the
"badly connected community" problem (Louvain occasionally produces
disconnected communities). Slightly slower (~80 ms at 5,000 nodes) but
more reliable for visual continuity across ticks.

- Worth considering if the visual experience under Louvain shows
  jitter at community boundaries.

### Stochastic Block Model inference

Peixoto's `graph-tool` implementation does Bayesian inference over
hierarchical SBMs (Peixoto 2014, 2017). Returns a partition with
posterior uncertainty.

- Time complexity: O(N log² N) for the hierarchical case; ~500 ms at
  5,000 nodes.
- Strengths: principled uncertainty, hierarchical structure surfaces
  syndicates-within-cabals naturally.
- Weaknesses: too slow for per-tick recomputation; suitable for
  every-N-tick "deep detection" passes.

The sandbox runs Louvain every tick for the visible cluster overlay
and runs SBM inference every 30 ticks for the syndicate stability
test.

---

## How to keep the labels stable across ticks

Naïve per-tick community detection produces flickering labels: cluster
indices reshuffle between calls even when the partition is unchanged.
Three stabilization moves from the streaming-community-detection
literature.

1. **Match labels by overlap.** After each detection pass, match new
   communities to existing ones by maximum Jaccard overlap. Communities
   below 30% overlap get a new label. This is the standard move from
   Greene, Doyle, Cunningham (2010) on dynamic community evolution.
2. **Carry centroids forward.** Each cabal has a centroid in
   norm-space and a centroid in sector-affinity space. After each
   detection pass, match new partitions to old centroids by minimum
   Euclidean distance.
3. **Hysteresis on syndicate flags.** A cabal is promoted to syndicate
   after 50 ticks of stability; it is demoted only after 80 ticks of
   churn. Asymmetric thresholds prevent rapid promote/demote cycling.

The sandbox implements all three. Cabal IDs are stable across ticks;
syndicate flags promote and demote slowly.

---

## What syndicate formation looks like in this engine

Three predictions from running the math on the existing engine state.

1. **Scale-free networks produce hub-anchored syndicates.** The
   highest-degree agent becomes the syndicate's anchor; trade flows
   through it. Removing the anchor (via `PopulationDynamicsConfig`
   churn) collapses the syndicate within ~5 ticks unless a substitute
   anchor emerges. This is the Watts-Strogatz preferential-rewiring
   prediction.
2. **SBM networks produce sector-block syndicates.** When
   `network_p_local` is high (intra-block density >> inter-block),
   syndicates align with sector blocks. Cross-sector syndicates only
   form when `cross_stack_permeability` is high enough that
   inter-block trade is dense enough for community detection to surface
   it as a separate community.
3. **Hyperbolic networks produce hierarchical syndicates.** Boguñá's
   embedding produces nested community structure at multiple scales.
   SBM inference recovers the hierarchy and surfaces both small
   tight-knit syndicates and large loose ones. The spatial sandbox
   visualizes the hierarchy as nested 3D regions in the inspector.

The last prediction is the most exciting for the visualization. A 3D
force-directed layout under a hyperbolic network model with
hierarchical SBM detection produces what the user described in the
reorientation: visible groupings that look like sectors but are
actually emergent, with the sense that they could subdivide further
under stress.

---

## What the inspector shows

When the user clicks an agent, the inspector card includes a
**Memberships** section:

```
Sector       retail (hard)
Firm         23 (cross-sector: retail + finance)
Cabal        4 (12 members, stable 18 ticks)
Syndicate    B (89 members, stable 86 ticks)
```

When the user clicks empty space inside a visible cluster, the
inspector opens a **Cluster** card instead:

```
Cabal 4
  12 members spanning sectors retail, finance, information
  Median wealth percentile: 78
  Trade volume share this tick: 4.2%
  Norm-vector centroid distance from population mean: 0.31
  Promoted from cluster on tick 109
  → 7 of 12 members also in syndicate B
```

Two operations on cluster cards:
- **Pin** — keep the cluster's visual highlight on across ticks.
- **Watch** — record the cluster's membership Jaccard score every
  tick and warn the user if churn exceeds a threshold (i.e. the
  cluster is dissolving). Useful for spotting the moment a syndicate
  breaks.

---

## What this means for the engine

The engine gets two changes; everything else lives in the dashboard.

| Change | Path | Cost |
| --- | --- | --- |
| Cross-sector firm formation | replace `bin_key = sector * n_stacks + stack` with `bin_key = stack` | `engine/core/institutions.py:88-90`, 1 line |
| Surface multi-sector firm metadata in snapshot | `engine/core/world.py` snapshot assembler | ~6 lines: track unique sectors per firm |

The dashboard gets:
- a streaming Louvain detector on the trade-edge feed
- a 30-tick SBM inference pass for syndicate stability
- a Jaccard-based label matcher
- centroid tracking in norm-space
- the inspector cards above

The engine remains agnostic about cabals and syndicates. They are
dashboard observations of engine outputs.

Emergent sector formation — letting the engine's `sector_id` itself
grow beyond K=12 — is *not* in scope for V1. The dashboard's emergent
labels give the user the visual experience of new sector formation
without the much-larger engine surgery of replacing the fixed sector
enum with a dynamic registry. If the visualization makes the V1
experience compelling enough, the K=12-to-dynamic migration can be a
later workstream.

---

## References

- Fortunato, S. (2010). *Community detection in graphs.* Physics
  Reports.
- Blondel, V. D., Guillaume, J.-L., Lambiotte, R., & Lefebvre, E.
  (2008). *Fast unfolding of communities in large networks.* Journal
  of Statistical Mechanics.
- Traag, V. A., Waltman, L., & van Eck, N. J. (2019). *From Louvain
  to Leiden: guaranteeing well-connected communities.* Scientific
  Reports.
- Peixoto, T. P. (2014). *Hierarchical block structures and
  high-resolution model selection in large networks.* Physical Review
  X.
- Peixoto, T. P. (2017). *Bayesian stochastic blockmodeling.*
  arXiv:1705.10225.
- Greene, D., Doyle, D., & Cunningham, P. (2010). *Tracking the
  Evolution of Communities in Dynamic Social Networks.* ASONAM.
- Fortunato, S., & Barthélemy, M. (2007). *Resolution limit in
  community detection.* PNAS.
- Hidalgo, C. A., Klinger, B., Barabási, A.-L., & Hausmann, R.
  (2007). *The Product Space Conditions the Development of Nations.*
  Science.
- `docs/concepts/matryoshkan_alignment.md` — the layered governance
  stack that cabals and syndicates live inside.
- `engine/core/institutions.py` — the existing firm formation code.
