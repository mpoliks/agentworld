# Spatial sandbox — completeness pass

A follow-on plan to `spatial-sandbox.md`. The original plan described a
three-lever, emergent-cluster engine driver. The current build delivers
the substrate (icosphere mesh + caterpillar agents + trade arcs + EBI
shape morph) but ships several encodings as placeholders: α is a static
HUD label, firms never appear, fold spawn events are silent, cabals
and syndicates do not exist, sectors are pre-drawn rather than
observed, and the agentic lever panel is absent. This plan fills in
those gaps and adds adversarial checks to every component so the
visualization cannot quietly drift from the underlying signal.

Cost is not a constraint on this pass. Where a cheaper option was on
the table in the prior review, the more thorough option is picked
here: Sobol-sized α regression instead of 200 samples, Leiden
clustering instead of streaming Louvain, full raycaster instead of
slot-index lookups, every plan §3 lever live where the engine permits.
The objective is a dashboard whose visible state cannot lie about the
underlying engine state — every encoding has a check that fails if it
does.

---

## 0. Starting context for a new agent

All code lives in the agentworld sub-repo on `live-engine`. The outer
repo treats agentworld as a gitlink; do not bump it. Read in order:

1. `spatial-sandbox.md` — the originating plan (§1–§14). This plan
   refers to its sections directly.
2. The seven research docs in `docs/research/`.
3. The current dashboard at `dashboard/sandbox/`:
   `scene.js`, `surface.js`, `agents.js`, `edges.js`, `themes.js`,
   `stream.js`, `stream-worker.js`. Existing stubs at
   `dashboard/sandbox/cabals.js`, `bonds.js`, `dust.js`, `trails.js`
   are from the prior Pass-15 cells-on-sphere render path. The
   tessellated-surface render in `scene.js` Pass 13 onwards superseded
   them; verify before repurposing.

How to run, default-off principle, and load-bearing memory files are
all unchanged from `spatial-sandbox.md` §0.

The adversarial check harness (§7 of this plan) is mandatory: each
phase ships its checks alongside the feature. No phase is complete
without its checks passing in CI.

---

## 1. Phase 0 — triage (0.5 days)

Three root-cause questions to answer before writing feature code.

**Q1: Why is `firm_id = -1` in every cast snapshot?**

Three candidates: (a) `InstitutionConfig.enabled = False` in the
spatial_sandbox scenario; (b) the cross-sector firms PR landed the
`bin_key` change in `engine/core/institutions.py` but not the
snapshot field; (c) firm formation needs more ticks than a live run
has accumulated.

Action: open a live run, dump one `cast_snapshot_v2` payload, grep
for any non-negative `firm_id`. Cross-reference against
`engine/scenarios/spatial_sandbox.py` and the snapshot assembler in
`engine/core/world.py`.

**Q2: Where does `step.alpha = 0.500` come from?**

Either the scenario hard-codes `TopologyConfig.alpha = 0.5`, or the
engine emits a per-tick value that never moves because the scenario
fixes alpha at construction. Check `engine/scenarios/spatial_sandbox.py`
and the `StepMetrics` assembly.

**Q3: Are `folds_v2` events firing at all?**

Wire a temporary `console.log` in `dashboard/sandbox/scene.js`
`onFolds` handler; run for 300 ticks; count events. Whatever the
matryoshka flow row reads as a non-zero rate, folds should be firing.

Output of Phase 0: a short triage section appended to this plan with
root causes and the exact line numbers to touch in Phase 1.

### Adversarial check 0.1
Run the triage on a fresh-clone checkout of `live-engine` to verify
no local state contaminates the diagnosis.

### 1.1 Phase 0 findings (2026-05-17)

Reproduced the sandbox factory at SMALL-scale (60 humans + 540 agent
prototypes, cast 200, `pairs_per_step = 2_000`, then 200 + 1_800,
`pairs_per_step = 20_000`) for 50 ticks. The three Q answers below
all reproduce against the canonical
`get_scenario('spatial_sandbox')` config from `live-engine` HEAD
(4d5b531).

**Q1 — firm_id = -1 in every cast snapshot.**

None of the three originally-named candidates is the cause. The
config is enabled
(`engine/scenarios/__init__.py:1466` sets
`InstitutionConfig(enabled=True, cross_sector_firms=True)`),
the snapshot row already carries `firm_id` and `firm_sectors`
(`engine/core/world.py:1011-1012`), and `formation_step` runs every
5 ticks from `engine/core/world.py:790`.

The actual cause is a fourth candidate: the formation gate
`(surplus_per_proto >= cfg.formation_surplus_threshold)` at
`engine/core/institutions.py:77` never matches any prototype. Per-tick
trade surplus per prototype in the sandbox sits at min `0.0000`,
median `~0.0003`, max `~0.0017` (measured on tick-0..15, 600
prototypes). The default threshold is `0.02`
(`engine/core/topology.py:498`) — ~10–60× above the realised surplus.
`pop.firm_next_id` stays at 0 for all 50 ticks; no firms exist for
the cast to land on.

Phase 1.2 fix lives in the `spatial_sandbox()` factory at
`engine/scenarios/__init__.py:1437-1488`: override
`institutions=InstitutionConfig(..., formation_surplus_threshold=
<calibrated>)`. Calibrate against the measured per-prototype surplus
distribution so a small but nonzero fraction qualifies each cycle
(target: ~50–200 new firms in the first 30 ticks at full scale).
Keep the engine default at `0.02` so the Sobol N=2048 baseline
reproduces bit-identically.

Risk note for adversarial check 2.2 "persistence": with a lowered
threshold and the current `dissolution_wealth_threshold = 0.5`,
firms may form and dissolve faster than the >50% / 30-tick target
the check expects. Tune both thresholds together.

**Q2 — `step.alpha = 0.500` always.**

Candidate (a) is correct. The sandbox factory hard-codes
`TopologyConfig(alpha=0.5, ...)` at
`engine/scenarios/__init__.py:1449`. Engine emits the static field as
`step.alpha` with no per-tick recomputation. Reproduced: 50/50 ticks
all reported `step.alpha = 0.5000` exact.

Phase 2.1 builds the dashboard-side `mapAlpha(leverState)` and shows
the gap to the engine value. The engine field continues to read
0.5 as long as the scenario fixes it — that is the diagnostic the
dashboard surfaces. No engine change required for §2.1.

**Q3 — `folds_v2` event firing rate.**

Events fire every tick (50/50 in the 50-tick SMALL-scale run). Engine
emits `fold_per_depth_contribution` with three nonzero depth buckets
(last sample: `[16.3M, 1.17M, 0.071M]`) and `n_sub_markets_added`
per tick (~37 at the sample point). The
`_v2_subpayloads` wiring at `engine/serve.py:91-101` produces the
event whenever `fold_per_depth_contribution` is non-empty, which it
is.

The dashboard is the silent end. Both `startStream` call sites in
`dashboard/sandbox/scene.js` pass `onFolds: () => {}` —
`scene.js:851` (restart path) and `scene.js:881` (initial mount).
The events arrive on the SSE channel and the worker (`stream.js:53`,
`stream-worker.js:49`) dispatches them, but the scene drops them on
the floor. There is no `folds.js` module yet, and no `__sandbox.folds()`
accessor for the future HUD FOLDS row.

Phase 2.3 work is therefore entirely additive: build
`dashboard/sandbox/folds.js`, wire it into both call sites, and
expose an `activeCount()` for adversarial check 6.x (HUD FOLDS row).
No engine change required for §2.3.

---

## 2. Phase 1 — re-animate dead encodings (4 days)

### 2.1 α mapping → HUD

Per `spatial-sandbox.md` §4, the dashboard computes α each tick from
current lever state.

- New: `dashboard/sandbox/alpha_map.js` exporting
  `mapAlpha(leverState) → α ∈ [0, 1]`.
- Weights pinned offline. Run `engine/sensitivity.py` with the
  existing N=2048 Sobol design across all 20 plan-§3 levers (not just
  the six implemented today — the regression is forward-compatible
  with Phase 4 additions). Each sample runs 100 ticks. Regress
  observed mean `step.alpha` against lever values via ridge regression
  with α-cross-validation on the regularizer. Persist weights at
  `dashboard/sandbox/alpha_weights.json` along with R², residual
  std, and per-lever marginal slopes.
- `scene.js`: call `mapAlpha` on lever debounce-flush and on each
  `onStep`. HUD shows the mapped α as the headline value. If
  `|mapped − step.alpha| > 0.05`, show both:
  ```
  α (lever)    0.62
  α (engine)   0.71   Δ +0.09
  ```
  The gap is the diagnostic — the user sees when the mapping is
  imperfect for the current configuration.

#### Adversarial checks 2.1

- **Range coverage.** A scripted sweep drives every implemented
  slider to its min, then its max, in 24 corner configurations.
  Assert the HUD α touches at least 0.15 and 0.85 somewhere across
  the sweep. If α stays in a narrow band, the mapping is dead and the
  test fails.
- **Monotonicity.** For each lever in the plan-§3 inventory, the
  research docs assign a sign for `dα/dlever`. Build a sign vector
  (pigouvian ↓ α, capability ↓ α, law strength ↓ α, fold-depth cap ↑
  α, certified_fraction ↓ α, …). Sweep each lever in 8 steps; assert
  the empirical sign matches the predicted sign in at least 7 of 8
  steps.
- **Bounds correctness.** The mapping must clamp to [0, 1]. Drive
  inputs to corners that should overflow; assert no overflow.
- **Decoupling test.** Disable all engine subsystems (set
  `LawConfig.enabled = False`, `PigouvianConfig.enabled = False`,
  `ComputeConfig.enabled = False`); start a run; assert HUD α still
  responds to lever drags. The mapping is dashboard-side; it must
  not depend on engine readiness.

### 2.2 Firms unstuck

Acting on the Phase-0 root cause:

- If `InstitutionConfig.enabled = False`: flip the default only in
  `engine/scenarios/spatial_sandbox.py`. The Sobol baseline at
  `outputs/sensitivity/sobol_indices.n2048.json` must reproduce
  bit-identically — the scenario-scoped flip keeps that contract.
- If snapshot-omitted: extend `_assemble_cast_snapshot_v2` in
  `engine/core/world.py` to include `firm_id` and `firm_sectors`
  (list of sector ids spanned by the firm). Tests in
  `engine/tests/test_rich_stream.py` confirm field presence.
- If insufficient-ticks: lower the formation threshold for the
  sandbox scenario only.

Once `firm_id` is finite for any agent:

- `agents.js` already builds `firmCentroids` per cast snapshot. No
  change needed there.
- New `dashboard/sandbox/firms.js`: a `THREE.LineSegments` group, one
  segment per (agent → firm centroid), opacity 0.08, drawn at
  substrate altitude. Render order set so spokes sit under the trade
  arcs.
- Firm color: a 64-step HCL palette indexed by `firm_id`. Stable
  across ticks.

#### Adversarial checks 2.2

- **Cross-sector formation.** With `cross_stack_permeability = 1.0`
  and `n_steps = 200`, assert ≥10% of active firms span ≥2 sectors.
  The cross-sector firms PR was the whole point; if no firm crosses
  sectors at full permeability, the bin_key change did not land.
- **Persistence.** Track each `firm_id` over 200 ticks. Assert >50%
  of firms persist for ≥30 ticks (the median lifetime of a
  meaningful institution in the engine's calibrated regime). Below
  that threshold, the visual is rendering noise.
- **Centroid spread.** For every firm with ≥3 members, compute member
  RMS distance from centroid. Assert <30% of sphere radius. A firm
  drawn as a hub-and-spoke whose members are antipodal is misleading.
- **Spoke ↔ membership match.** Sample 50 spokes; for each, verify
  the agent at the spoke endpoint actually has `firm_id` equal to
  the firm at the other endpoint.

### 2.3 Fold spawn visualization

- New: `dashboard/sandbox/folds.js`. Unbounded pool — allocate on
  demand, no fixed cap. `THREE.InstancedMesh` with
  `IcosahedronGeometry(R * 0.012, 1)` so 5000 concurrent folds is
  cheap.
- `onFolds` handler in `scene.js`: each `folds_v2` event lists the
  agents that spawned a sub-market this tick. Place one icosphere at
  the parent agent's current face centroid, offset radially by 1.5%
  of R. Fade in over 30 frames, hold 60, fade out 60.
- Color by depth via the matryoshka palette: depth 1 = neutral grey,
  depth 7 = saturated magenta `rgb(140, 102, 191)` (same as the
  matryoshka flow row). Linear interpolation between depths.
- Render order above the substrate, below the trade arcs.

#### Adversarial checks 2.3

- **Quantitative consistency.** Over each rolling 60-tick window,
  integrate `(nominal_step − real_step) / nominal_step` (the
  matryoshka flow row source). Separately count visible fold-spawn
  events × depth-weighted cost from the same window. Assert the two
  agree within 20%. If the visual count and the meter diverge, one
  channel is wrong.
- **Depth-color monotonicity.** Sample 20 fold meshes at random;
  read their material color saturation. Assert saturation increases
  monotonically with depth. A pure correlation test (Spearman ρ
  > 0.95) over the sample.
- **Decay correctness.** A fold mesh at frame 30 must have alpha
  ~0.7; at frame 90 alpha 1.0; at frame 150 alpha ~0.0. Snapshot
  three frames; assert within ±0.05.
- **Spawn locality.** For each spawn event, the icosphere position
  must sit within R × 1.05 of the parent agent's current face
  centroid. Random placement is a bug.

---

## 3. Phase 2 — emergent cluster detection (7 days)

Goal: deliver the cabal / syndicate vocabulary from `spatial-sandbox.md`
§6. Use Leiden rather than streaming Louvain — Leiden gives strictly
non-degenerate partitions and is the modern default; the cost
difference is negligible.

### 3.1 Leiden in main thread

- New: `dashboard/sandbox/clusters.js`. Use the `graphology-leiden`
  build from a vendored `dashboard/vendor/`. No CDN dependency.
- Rolling 30-tick edge buffer: `Map<edgeKey, weight>` with per-tick
  decay `weight *= 0.92`. Each `onEdges` event adds to the buffer
  with weight = base_surplus.
- Leiden pass every tick (~5 Hz). Time budget 100 ms at 5,000 nodes
  / ~600 active edges. Higher cadence than the original plan called
  for; the user sees cluster changes within 200 ms of a lever drag.
- Output: `{ agentIdx → cabalId, cabalIds: [], modularity }`.

### 3.2 Degree-corrected SBM in Web Worker

- New: `dashboard/sandbox/clusters_sbm.js` (worker),
  `dashboard/sandbox/cluster_labels.js` (main thread).
- Degree-corrected SBM every 10 ticks (~2 s). Worker isolation
  keeps the main thread at full render rate. Time budget 1 s in
  worker.
- Jaccard matching across passes: every tick, compute Jaccard for
  each cabal vs. its closest predecessor by member overlap. Cabal →
  syndicate after 50 ticks of >90% mean Jaccard; demote after 80
  ticks below 70%.
- Stability metadata persisted per syndicate: age (ticks since
  promotion), Jaccard history (last 100), churn rate.

### 3.3 Cluster overlay rendering

- New: `dashboard/sandbox/cluster_overlay.js`. The existing
  `dashboard/sandbox/cabals.js` is a stub from the prior render
  path; archive it under `dashboard/sandbox/_legacy/`.
- Per cluster: spherical convex hull of member positions on the
  current displaced substrate (not the unit sphere — the hull
  follows the EBI shape morph). Render as a `THREE.Mesh` with a
  shader that tints by cluster ID hash. Cabal opacity 0.10,
  syndicate opacity 0.22.
- Smooth crossfade when membership changes: each cluster keeps a
  60-frame trailing membership; the hull is rebuilt from the
  union, weighted toward the current membership.
- Cluster ID hue is stable across ticks via Jaccard matching, so a
  user can recognize "the same cabal" frame to frame.

#### Adversarial checks 3.x

These are the strongest checks in the plan because clustering is the
component most likely to produce false positives.

- **Null-graph control.** Feed Leiden a synthetic edge stream that
  is pure Erdős–Rényi random — same edge count and degree
  distribution as the real stream, but with rewired endpoints.
  Modularity must stay below 0.10. If Leiden finds clusters in
  noise the test fails. CI test in
  `engine/tests/test_sandbox_clusters_synthetic.py`.
- **Planted partition recovery.** Synthetic stochastic block model
  graph with K = 6 planted communities, intra-block edge probability
  10× inter-block. Run Leiden. Assert recovered partition has
  Jaccard ≥0.85 with planted truth.
- **Permutation invariance.** Run Leiden at tick t with the real
  edge buffer. Apply a random permutation to agent indices and run
  again. Assert the partition is identical up to label renaming
  (compute Jaccard against the permutation-corrected reference;
  must be 1.0).
- **Syndicate promotion gate.** Construct a cabal whose Jaccard
  with its own predecessor sequence is engineered to be 0.95 for
  10 ticks then 0.65 for 5 ticks. Assert no promotion at any tick.
  Reverse the sequence; assert promotion at tick 50 of sustained
  ≥0.90.
- **Visual ↔ partition consistency.** Each frame, sample 100 random
  visible agents. For each, find which cluster hull contains its
  rendered position. Assert the hull's cluster ID matches the
  agent's Leiden assignment. Diff is intolerable — visual must not
  drift from partition state.
- **Cross-tick label stability.** Run two adjacent ticks; for every
  cabal in tick t with ≥5 members, find the best Jaccard match in
  tick t+1. Assert the matched cabal carries the same ID.

---

## 4. Phase 3 — emergent sector overlays (4 days)

The current implementation binds each agent to its engine sector at
spawn ([agents.js:298-309](../dashboard/sandbox/agents.js#L298)) and
filters every walk step to same-sector neighbours. Drop the binding
entirely. Sectors should appear because trade behavior keeps
same-sector agents close, not because geometry forces them.

### 4.1 Engine-sector tint

- `agents.js` `chooseNeighbour`: remove the same-sector filter; agents
  walk wherever the firm / partner pull steers them.
- Per-segment color attribute: each caterpillar segment carries the
  agent's `sector_id` color from the 12-step palette in
  [themes.js:34-47](../dashboard/sandbox/themes.js#L34). Color is
  written once per segment when the segment enters the trail.
- New material: `THREE.ShaderMaterial` with a vertex color attribute
  replacing the current `MeshBasicMaterial`.
- Drop the Voronoi cap rendering on the substrate entirely. The
  substrate stays neutral; sectoral identity moves to the agent layer.
- Hover-to-identify on the agent itself (Phase 6.1), not on the
  substrate.

### 4.2 Sector compass legend

A persistent 12-swatch strip near the toggles panel. Each swatch is a
small color square + sector name (`agriculture`, `extraction`, …).
Clicking a swatch isolates that sector (other agents fade to 0.2 alpha
for 5 s). Lets the user answer "where do the manufacturing agents
end up under this configuration?"

#### Adversarial checks 4.x

- **Permeability dispersion.** Set `cross_stack_permeability = 1.0`,
  `network_p_local = 0.0`, `trade_rate_multiplier = 4.0`. Run 300
  ticks. Compute Moran's I on sector color over agent positions.
  Assert Moran's I < 0.15 (near-random spatial mixing). At default
  permeability 0.4 Moran's I should be > 0.40 (strong clumping). The
  difference between these two regimes is the entire test of whether
  sectors are emergent.
- **Sector tint truthfulness.** Sample 200 visible segments at
  random. Look up the corresponding agent's `sector_id` from the
  most recent cast snapshot. Assert the segment color matches the
  palette entry for that sector. Mismatch is a bug.
- **No phantom binding.** Take a live snapshot; randomize each
  agent's `sector_id` field in a copy; replay the rendering path
  against the modified snapshot. Assert the visible sectoral
  structure changes completely — i.e. the structure is sourced
  from `sector_id` alone, not from any leftover geometric binding.
- **Compass ↔ palette match.** Each compass swatch's RGB must
  exactly equal the palette entry. Pixel-exact, no drift.

---

## 5. Phase 4 — lever inventory completion (5 days)

The plan §3 inventory minus the six currently shipping:

**Agentic (all 7 missing):**
- `agent_capability_mean` (structural)
- `NormsConfig.certified_fraction` (live)
- `network_model ∈ {well_mixed, scale_free, sbm, hyperbolic}` (structural)
- `network_p_local` (structural)
- `agent_autonomy_mean` (live)
- `NormsConfig.update_rate` (live)
- `agent_trade_rate_multiplier` (live)

**Legal (5 missing):**
- `LawConfig.strength` (live)
- `folding.max_depth` (structural)
- `LawConfig.transaction_size_cap` (live)
- `RegulatorConfig.enabled` (structural)
- `PigouvianConfig.recycling ∈ {human_wealth, friction_subsidy, capability}` (structural)

**Environmental (2 missing):**
- `ComputeConfig.distribution ∈ {uniform, wealth_weighted, capability_weighted, autonomy_weighted}` (structural)
- `ScalePreset ∈ {SMALL, MEDIUM, LARGE}` (structural)

Each new control needs:

1. UI in the right panel — rebuild
   [sandbox.html:441-470](../dashboard/sandbox.html#L441) into the
   three-panel layout the plan specifies (agentic, legal,
   environmental).
2. A live / structural icon next to the label. Structural icon
   tooltip: "applies on Restart."
3. Engine `_LIVE_TUNABLE` allowlist expansion in `engine/serve.py` for
   every live-flagged control. Where a config field can be safely
   mutated mid-run (mutation does not require re-allocating agent
   arrays or re-initializing topology), it goes live.

### 5.1 Network model live mutation (stretch)

`network_model` is structural in the canonical plan. Investigate:
if the engine can rewire topology mid-run by re-running
`build_topology` and re-seeding edge cache, the lever can go live.
Cost is 50–200 ms during the rewire — acceptable. If feasible, ship
it live; otherwise leave structural.

#### Adversarial checks 5.x

- **Live response.** For each live-flagged lever: drive from its
  default to the min and to the max in a CI test
  (`engine/tests/test_lever_response.py`). For each, identify the
  engine metric expected to respond (e.g. `LawConfig.strength` ↔
  `rejected_law` rate). Assert the metric changes by ≥3× the
  noise floor within 50 ticks of the change.
- **Structural override.** For each structural lever: set the slider,
  click Restart, capture the first cast snapshot's relevant config
  field. Assert it matches the slider value. Test in
  `engine/tests/test_lever_restart.py`.
- **Bounds containment.** UI slider min/max must lie inside the
  engine `_LIVE_TUNABLE` bounds. No slider value can be rejected by
  the engine validator. CI test pulls both schemas and verifies
  containment.
- **Unit-label correctness.** Each slider's value readout uses the
  right unit (% for rates, raw float for thresholds, enum string
  for categorical). CI snapshot test asserts unit format strings
  match a fixed table.
- **Default reproducibility.** Setting every slider to its default
  and clicking Restart must produce a run whose first 30 ticks are
  bit-identical to the Sobol N=2048 baseline. Otherwise the default
  set drifted.

---

## 6. Phase 5 — HUD diagnostics (3 days)

The rejection mix is the highest-value addition. Engine already emits
per-gate-stage rejection rates ([scene.js:697-706](../dashboard/sandbox/scene.js#L697)).

### 6.1 HUD additions

```
α (lever)     0.62
α (engine)    0.71      Δ +0.09  (shown only when |Δ| > 0.05)
EBI           3.82
Δ welfare     +394
GINI          0.51
FOLDS         12        active fold meshes
COMPUTE       0.78      step.compute_pool_remaining
SYNDICATES    3         currently-promoted clusters
CABALS        7         currently-detected clusters
REJ MIX
  cost        0.05
  market      0.08
  align       0.31
  law         0.04
  compute     0.02
  perm        0.01      cross-stack permeability rejects
  reg         0.00      regulator rejects
TICKS/S       4.8
STREAM        live
```

All rows are read-only. Layout: mono caps, no borders, IBM Plex Mono
or system mono fallback.

### 6.2 EBI regime caption

A small line under the HUD that names the current regime band:

- EBI < 0.7: "flat real economy"
- 0.7 ≤ EBI < 1.5: "low baroque"
- 1.5 ≤ EBI < 2.5: "calibrated reference"
- 2.5 ≤ EBI < 4.0: "pricing reflexivity dominant"
- 4.0 ≤ EBI < 6.0: "exo-baroque"
- EBI ≥ 6.0: "untethered"

Caption updates on each `onStep`. The regime name tells the user what
the shape morph *means*.

#### Adversarial checks 6.x

- **Rejection mix completeness.** `rej_cost + rej_market + rej_align
  + rej_law + rej_compute + rej_perm + rej_reg` must equal the
  engine's `total_rejected_fraction` to within 1e-6 per step. The
  HUD computes the sum and shows a red ‼ if the assertion ever
  fails.
- **HUD ↔ engine consistency.** Each numeric row reads from a
  specific `StepMetrics` field; a CI test
  (`engine/tests/test_hud_field_mapping.py`) drives random metric
  values via a mock SSE stream and asserts the DOM text matches the
  injected value within rounding tolerance.
- **Folds count.** HUD FOLDS row must equal
  `__sandbox.folds().activeCount` every frame.
- **Compute pool monotonicity within a tick.** The pool only refills
  at tick boundaries. Sample HUD COMPUTE 10× between ticks; assert
  no in-tick increase.
- **Regime caption matches band.** Sample EBI and caption; assert
  the caption is the band label for the current EBI value.

---

## 7. Phase 6 — legibility (5 days)

### 7.1 Click-to-inspect

Full raycaster, not slot-index lookups.

- New: `dashboard/sandbox/inspector_agent.js`,
  `dashboard/sandbox/inspector_cluster.js`.
- `THREE.Raycaster` against the agent mesh's full BufferGeometry on
  `mousedown` if drag distance < 4 px. Identify hit triangle index;
  map to agent slot via `Math.floor(triangleIndex / MAX_TRAIL)`
  (segments-per-agent stride from `agents.js`).
- Agent card on the right side, pinnable:
  - **Identity:** idx, prototype ID, sector name, firm_id with
    sector list, current cabal ID (member count), current syndicate
    ID (stability age, Jaccard history sparkline).
  - **State:** wealth (raw + population percentile), capability,
    autonomy, certified_fraction, ticks alive, stack depth.
  - **Norms:** 8-axis radar — `WorldConfig.norms_n_dimensions = 8`
    for the sandbox. Each axis labelled.
  - **Recent trades:** last 5 partners with surplus, sector, gate
    outcome.
  - **Last fold:** if any in the last 30 ticks.
- Cluster card on click inside a hull (and not on an agent):
  - Cabal / syndicate ID, member count, sector composition pie
    (12-segment).
  - Median wealth percentile.
  - Trade volume share this tick.
  - Norm centroid distance from population mean.
  - Stability age and Jaccard history sparkline.
  - Operations: Pin (keep highlight across ticks), Watch (warn
    when membership churn exceeds threshold).

Shift-click adds a second card. Esc closes the most recent.

### 7.2 Trade arc legibility

Don't reduce arc density — add information.

- Color arcs by reject reason instead of binary blue/red. Palette:
  - `executed` → blue `rgb(26, 89, 242)`
  - `reject_cost` → desaturated grey `rgb(128, 128, 128)`
  - `reject_market` → tan `rgb(184, 135, 89)`
  - `reject_align` → magenta `rgb(186, 76, 178)`
  - `reject_law` → red `rgb(217, 89, 89)`
  - `reject_compute` → cyan `rgb(89, 178, 196)`
  - `reject_perm` → green `rgb(89, 178, 115)`
  - `reject_reg` → amber `rgb(217, 166, 77)` (same as humans —
    intentional; the regulator and the humans are both governance
    levers)
- The arc colors match the HUD rejection-mix row palette so a user
  cross-references "the screen is mostly magenta" with "alignment
  rejects dominate."
- Keep three thickness tiers but increase the gap: TIER_WIDTHS from
  [0.6, 2.2, 6.0] to [0.5, 3.0, 9.0].

### 7.3 Wealth meter redesign

- **Stock:** single horizontal split bar. Humans amber on the left,
  AI blue-grey on the right. No gap (the two compose to 1.0 by
  construction).
- **Flow:** three small 60-tick sparklines (matryoshka, legal
  capture, recycling) each labeled with the current rate. Time
  axis = `step.step`, integer index. New value pushed per `onStep`.
- Drop the per-frame EMA. EMA's only purpose was to mask sampling
  noise at frame rate, but it was making backgrounded tabs show
  stale targets indefinitely.

### 7.4 Trade-arc legend + sector compass

- Toggles panel anchors three small affordances:
  - Trade-arc legend: 8 color dots labelled by outcome name.
  - Sector compass: 12 swatches as in §4.2.
  - EBI shape morph legend: a small `📉 disc / ⚪ sphere / ☁️ lobes`
    icon strip (or equivalent neutral glyphs) with the current
    regime active.

### 7.5 Stream-state clarity

- Tooltip on the HUD STREAM row: "tab is backgrounded — render rate
  reduced; engine and stream are unaffected." Shown when prefix is
  `bg ·`.
- When `_lastEdgeT` staleness exceeds 5 s, the prefix flips to
  `STALL` and the tooltip explains: "no edge events for 5+ seconds
  — engine may have stopped."

#### Adversarial checks 7.x

- **Inspector identity correctness.** A scripted click on a known
  agent position (driven by JS coordinate calculation from the agent
  buffer) must open a card whose `idx` matches the agent under the
  cursor. CI uses Playwright headed with the sandbox running against
  a deterministic seed.
- **Inspector sector match.** The opened card's "sector" field must
  equal the engine `sector_id` from the most recent cast snapshot
  for that idx.
- **Inspector norm radar shape.** The 8-axis radar plots must match
  the engine's per-agent norm vector to within float-precision
  rounding (the radar reads the same `agent_norms` field the engine
  exposes).
- **Arc legend palette match.** Each legend dot's RGB must equal
  the rendered arc color for that outcome. Pixel-exact.
- **Wealth stock invariant.** Stock bar humans% + AI% = 100.0 ±
  0.05% on every step. The bar must visually never show a gap.
- **Sparkline tick alignment.** The integer index on the sparkline
  x-axis must equal `step.step` for the rightmost point.
- **Stall-detection correctness.** A scripted test pauses the
  engine (does not cancel the run) for 6 s; assert the STREAM row
  flips to `STALL` within 5.0 ± 0.5 s of the last event.

---

## 8. Check harness — where the adversarial tests live

Three layers.

### 8.1 Engine-side response and invariant tests
`engine/tests/test_dashboard_invariants.py`. Spins up the FastAPI
test client, starts a run with controlled overrides, drives lever
updates, asserts the SSE stream's metrics behave as the dashboard
expects. Covers checks 2.2 (firms), 5.x (levers), 6.x (HUD field
mappings), and parts of 7.x (stall detection).

### 8.2 Synthetic graph tests for clustering
`engine/tests/test_sandbox_clusters_synthetic.py`. Generates Erdős-
Rényi, planted SBM, and permuted-real-data graphs in pure Python,
feeds them through the same Leiden / SBM code paths the dashboard
uses (via a small Node.js subprocess for graphology, or a Python
port). Covers checks 3.x.

### 8.3 Dashboard runtime invariants
`dashboard/sandbox/dev/checks.js`. Default off. Enable with
`?dev=1` URL parameter. Runs invariants every animation frame:
- HUD numeric ↔ engine field equality (with tolerance).
- Visual ↔ partition consistency (sample 50 agents).
- Stock bar humans% + AI% = 100%.
- Folds DOM count = mesh count.
On any failure, prints a console error with the assertion and
flashes a small red badge in the toggles panel.

A nightly Playwright job runs the full sandbox for 30 minutes with
`?dev=1` against a deterministic seed and a fixed lever trajectory,
captures any badge flash, fails CI if any assertion ever triggered.

### 8.4 Visual regression
`dashboard/sandbox/dev/regression/`. Six canonical lever states
(low-α / mid-α / high-α / low-EBI / mid-EBI / chaos-EBI). For each,
take 4 screenshots over 200 ticks. Compare against checked-in
baselines via SSIM. Any tile whose SSIM < 0.92 fails the check —
forces explicit baseline updates when behavior changes.

---

## 9. Sequencing

| Phase | Days | Depends on |
| --- | --- | --- |
| 0 — triage | 0.5 | — |
| 1 — re-animate (α, firms, folds) | 4 | 0 |
| 2 — cluster detection (cabals, syndicates) | 7 | 1.2 |
| 3 — emergent sector overlays | 4 | 2 |
| 4 — lever inventory | 5 | 0 |
| 5 — HUD diagnostics | 3 | 0 |
| 6 — legibility | 5 | 2, 4 |

Critical path: 0 → 1 → 2 → 3 → 6. About 24 calendar days at one
engineer working in series. Phases 4 and 5 land in parallel with
2 and 3. Realistic schedule with parallelism: 4 weeks elapsed.

---

## 10. Risk notes

1. **Caterpillar geometry stays.** The plan does not revert to the
   force-directed render the original `spatial-sandbox.md` §5
   specified. The substrate-as-memory encoding the caterpillar build
   added (altitude bumps from trades, stack carving, EBI shape
   morph) is too valuable to throw out. Cluster hulls (Phase 2) and
   per-segment sector tint (Phase 3) give the user what the
   force-directed render was supposed to give: visible interaction
   structure overlaid on agent positions.
2. **Engine-side scenario flips.** Phases 1 and 4 may flip
   subsystem defaults (`InstitutionConfig`, `NormsConfig`,
   `ComputeConfig`). The flips live only in
   `engine/scenarios/spatial_sandbox.py`. The Sobol N=2048 baseline
   reproduces because the scenario is one row of the design space,
   not the engine default. The
   `feedback_build_plus_repurpose.md` memory codifies this; the
   adversarial check 5.x "default reproducibility" enforces it.
3. **Compute cost of Phase 2.** Leiden every tick (100 ms) + SBM
   every 10 ticks (1 s in worker) is the budget. At 5,000 cast and
   ~600 active edges this fits in the engine tick interval (200 ms
   at 5 Hz). Worker SBM is isolated. If p95 main-thread frame time
   exceeds 33 ms (30 fps), drop Leiden to every 2 ticks but keep
   the per-tick visualization update from cached partition.
4. **Network model live mutation.** Phase 5.1 stretch. The cost
   estimate (50–200 ms rewire) is for SMALL scale. At LARGE scale
   it may be 1–2 s — visible pause. Acceptable per the
   "expensive is fine" framing, but flag the pause with a "rewiring
   topology…" overlay.
5. **Inspector raycaster cost.** Full raycast against the 100k+
   triangles of the agent mesh is expensive (~5 ms per click).
   That's a click event, not a frame event — fine.
6. **α-mapping accuracy.** Sobol-sized regression on 20 inputs
   should give R² > 0.85 against engine α. Below that, the mapping
   is misleading and the gap-display in Phase 2.1 will surface the
   mismatch frequently — which is the right outcome.

---

## 11. Out of scope here

- Force-directed render revert (substrate stays icosphere + caterpillar).
- Ambient audio (`spatial-sandbox.md` §11 Week 4).
- URL-state permalinks (`spatial-sandbox.md` §9). Revisit in a later
  pass; the current plan does not encode lever state into the hash.
- Hyperbolic network model (`spatial-sandbox.md` §10 deferred item).
- Mobile, touch, replay timeline, multi-run side-by-side, regional
  compute markets.
