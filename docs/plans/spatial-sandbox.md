# Spatial sandbox — three-lever, emergent-cluster engine driver

A single web page. Three lever panels, one 3D agent universe with ~5,000
visible agents drawn from a live simulation running every engine
subsystem. Agents are nodes in a force-directed graph; their positions
emerge from the interaction profiles the user shapes. Sectors are visible
because they form, not because they are drawn. α is on the HUD, not on a
slider. Click any agent to inspect its identity, its memberships (sector,
firm, cabal, syndicate), and what motivates it.

The plan supersedes the previous draft of this document. The Schoenegger
reorientation — the user's note that α should be an outcome and that
sectors should not appear as fixed cells — changes the shape of the
work, not the month-long scope.

---

## Rationale references

The design choices below cite seven research docs in `docs/research/`:

- `alpha_as_outcome.md` — α as an emergent metric of three lever
  categories; mapping function from lever state to α.
- `verifiable_semantics.md` — `NormsConfig.certified_fraction` as
  per-agent communication fidelity.
- `a2a_communication_structures.md` — network model choice as agentic
  lever; the case for adding a hyperbolic option.
- `emergent_clustering.md` — cabal vs. syndicate vs. firm vs. sector
  vocabulary; streaming Louvain + 30-tick SBM inference for cluster
  labels.
- `compute_and_power_as_constraint.md` — `ComputeConfig` as the new
  environmental subsystem.
- `legal_levers_in_agent_economies.md` — Matryoshka stack +
  Pigouvian + fold caps + transaction-size cap as the legal panel.
- `force_directed_trade_graphs.md` — ForceAtlas2 in 3D with Barnes-Hut
  octree; force model; streaming stability.

---

## 0. Starting context for a new agent

If you are a fresh Claude session opening this file for the first
time, here is what to know before reading the rest of the plan.

**Where this work happens.** All code, docs, tests, and commits live
in the agentworld sub-repo at
`/Users/marek/Documents/economy and ecology/agentworld/`. Branch is
`live-engine`. The outer `economy and ecology` repo treats agentworld
as a gitlink (mode 160000); do not bump the outer pointer
proactively — the user makes those pointer-bump commits themselves.

**The repo at a glance.**

| Path | What's there |
| --- | --- |
| `engine/core/` | The vectorized simulation engine. `world.py`, `population.py`, `topology.py`, `transactions.py`, `norms.py`, `institutions.py`, `folding.py`, and the new (post-Week 1) `compute.py`. |
| `engine/scenarios/` | The 40-scenario canonical suite. Touch only to add the two new compute scenarios in Week 1. |
| `engine/tests/` | pytest suite; the Week-1 PRs each ship one new test file. |
| `engine/bench/` | Benchmark scripts. Week 1 adds `spatial_sandbox.py`. |
| `engine/serve.py` | FastAPI live bridge with SSE channel. Already wired. |
| `engine/sensitivity.py` | The Sobol sweep entry point. Do not break the N=2048 baseline at `outputs/sensitivity/sobol_indices.n2048.json`. |
| `dashboard/` | The current cockpit (`live.html` + seven `live_*.js`). Week 3 strips it and replaces with `sandbox.html` + `sandbox/`. |
| `docs/research/` | The seven research docs that ground every design decision in this plan. Read them first. |
| `docs/concepts/` | The existing engine-concept library. Reference; do not duplicate. |
| `docs/plans/` | Per-project plans. This plan is one of them. |

**Three load-bearing memory files** at
`~/.claude/projects/-Users-marek-Documents-economy-and-ecology/memory/`:

- `feedback_agentworld_repo_boundary.md` — commit inside the agentworld
  sub-repo only; do not proactively bump the outer-repo gitlink.
- `feedback_build_plus_repurpose.md` — when adding subsystems, build new
  where the design calls for it, repurpose existing where overlap is
  natural; default new subsystems off so existing baselines reproduce.
- `styleguide_reference.md` — Marek's prose styleguide. Applies to
  docs, dashboard copy, commit messages, README updates. The banned-
  vocabulary list is strict. Read the styleguide before drafting any
  prose.

**How to run the engine.**

```bash
cd /Users/marek/Documents/economy\ and\ ecology/agentworld

# Batch run a scenario
agentworld run baroque_cathedral
# or: PYTHONPATH=. python -m engine.runner baroque_cathedral

# Live engine — the spatial sandbox attaches over SSE to this
uvicorn engine.serve:app --host 0.0.0.0 --port 8765

# Tests
pytest engine/tests/

# Benchmark added in Week 1
python engine/bench/spatial_sandbox.py

# Smoke test the Sobol baseline after each engine PR
agentworld sweep --quick
```

**Default-off principle.** Every new subsystem
(`NormsConfig.certified_fraction`, `LawConfig.transaction_size_cap`,
`ComputeConfig`, cross-sector firms) ships with default values that
preserve existing scenario behavior bit-identically. The Sobol baseline
at `outputs/sensitivity/sobol_indices.n2048.json` must reproduce after
each engine PR.

**Read order before writing any code.**

1. `agentworld/README.md` — the project framing.
2. The seven docs in `docs/research/` in this order:
   `alpha_as_outcome.md`, `verifiable_semantics.md`,
   `a2a_communication_structures.md`, `emergent_clustering.md`,
   `compute_and_power_as_constraint.md`,
   `legal_levers_in_agent_economies.md`,
   `force_directed_trade_graphs.md`.
3. The rest of this plan (§§1–14).
4. Any `docs/concepts/` file cited by the research docs or by §10 of
   this plan.

**When in doubt.** Two safe defaults: (a) prefer adding a new field on
an existing config over inventing a top-level config; (b) keep new
behavior gated behind a flag whose default reproduces today's
behavior. The `feedback_build_plus_repurpose.md` memory codifies this.

---

## 1. Goals

- Replace `dashboard/live.html` with one full-bleed 3D scene driven by
  three lever panels: agentic, legal, environmental.
- All optional engine subsystems on by default: norms (with the new
  `certified_fraction`), demand, pigouvian, registration, institution
  (with cross-sector firms), population dynamics, mission, strategy,
  law (with the new `transaction_size_cap`), regulator, and the new
  `ComputeConfig`.
- Force-directed 3D layout: agent positions emerge from recent trades,
  norm distance, and degree centrality. No fixed sector cells. Clusters
  appear because they form.
- α is reported on the HUD as the EBI readout; the levers produce α,
  the user does not set it.
- Click any agent to inspect identity, memberships, state, norm vector,
  and recent trades. Click empty cluster space to inspect the cluster.
- Every parameter state is a URL; pasting reproduces the run exactly.
- 60 fps target with 5,000 visible agents on a 2024 laptop.

## 2. Non-goals

- No premade scenarios, no scenario family pills, no preset selector.
- No win condition, scoring, or objectives — the page is a sandbox.
- No XLARGE rendering (88M agents). Out of scope for V1.
- No mobile or touch. Desktop browser only.
- No multi-run side-by-side. One run per session.
- No engine-level emergent sector formation. The K=12 hard sector enum
  stays; emergent labels are dashboard observations.
- No regional compute markets in `ComputeConfig` V1 — single global
  pool.

## 3. The three lever panels

### Agentic panel

What the agents are. Each lever exposes a config field that already
exists or is added by the Week-1 engine PRs.

| Control                 | Engine field                                       | Default          | Notes |
| ----------------------- | -------------------------------------------------- | ---------------- | ----- |
| Capability              | `agent_capability_mean`                            | 0.55             | structural; fresh run |
| Communication fidelity  | `NormsConfig.certified_fraction` (new)             | 0.5              | live |
| Network model           | `network_model ∈ {well_mixed, scale_free, sbm, hyperbolic}` | sbm | structural |
| Network locality        | `network_p_local`                                  | 0.6              | structural |
| Autonomy                | `agent_autonomy_mean`                              | 0.7              | live |
| Norm update rate        | `NormsConfig.update_rate`                          | 0.05             | live |
| Trade rate              | `agent_trade_rate_multiplier`                      | 2.0              | live |

Seven controls. Live = pushed via `POST /runs/{id}/update`,
debounced 200 ms. Structural = restarts the run with new config.

### Legal panel

What is imposed on the agents. Eight controls in two collapsible
groups.

**Primary**

| Control              | Engine field                            | Default     | Notes |
| -------------------- | --------------------------------------- | ----------- | ----- |
| Law strength         | `LawConfig.strength`                    | 0.5         | live |
| Pigouvian tax rate   | `PigouvianConfig.tax_rate`              | 0.10        | live |
| Fold-depth cap       | `folding.max_depth`                     | 7           | structural |
| Transaction-size cap | `LawConfig.transaction_size_cap` (new)  | ∞           | live |

**Secondary** (collapsed by default)

| Control                 | Engine field                                     | Default          | Notes |
| ----------------------- | ------------------------------------------------ | ---------------- | ----- |
| Regulator presence      | `RegulatorConfig.enabled`                        | True             | structural |
| Pigouvian recycling     | `PigouvianConfig.recycling ∈ {human_wealth, friction_subsidy, capability}` | human_wealth | structural |
| Pigouvian progressivity | `PigouvianConfig.recycling_progressivity`        | 1.0              | live |
| Market layer tax        | `market_layer_tax`                               | 0.025            | live |

### Environmental panel

What the substrate allows. Five controls.

| Control            | Engine field                              | Default        | Notes |
| ------------------ | ----------------------------------------- | -------------- | ----- |
| Compute budget     | `ComputeConfig.budget_per_tick` (new)     | 1.0            | live |
| Power cost per trade | `ComputeConfig.power_cost_per_trade` (new) | 0.0          | live |
| Compute distribution | `ComputeConfig.distribution ∈ {uniform, wealth_weighted, capability_weighted, autonomy_weighted}` (new) | uniform | structural |
| Scale              | `ScalePreset ∈ {SMALL, MEDIUM, LARGE}`    | SMALL          | structural |
| Cross-stack permeability | `cross_stack_permeability`           | 0.4            | live |

The "Roll" button (new seed) lives in the panel header strip and
triggers a fresh run with the current lever state.

## 4. The α mapping

Levers do not set α. The dashboard computes α each tick from the
current lever state and passes it to `TopologyConfig.alpha`. The
mapping is documented in `docs/research/alpha_as_outcome.md`:

```
α = clamp(0, 1,
    α_base
    + w_cap   · (1 − capability)
    + w_cert  · (1 − certified_fraction)
    + w_net   · scale_free_concentration
    + w_pig   · (1 − pigouvian_tax_rate)
    + w_law   · (1 − law_strength)
    + w_fold  · (folding_max_depth / 10)
    + w_comp  · compute_scarcity
)
```

The weights are pinned offline by regression on a fixed grid of lever
states. The dashboard ships with the pinned weights and exposes them
in a hidden "Why" inspector for the curious.

The HUD reports α and EBI together — α is the input the engine
receives, EBI is the output the engine produces. The two move
together; the gap between them tells the user when the mapping is
imperfect for the current configuration.

## 5. The visualization

A 3D force-directed graph, ForceAtlas2 + Barnes-Hut octree. Per
`force_directed_trade_graphs.md`:

- 5,000 visible agents rendered as `THREE.Points`.
- Up to 1,000 edges per tick rendered as `THREE.LineSegments`,
  alpha-decaying over 30 frames.
- Fold sub-markets as small icosphere meshes near the parent agent,
  fading in over 60 frames.
- Per-agent color from a 12-step sector palette (the hard
  `sector_id`).
- Per-agent glow intensity ∝ autonomy².
- Per-agent size log-scaled by wealth.
- Cluster overlays (cabals, syndicates) render as soft translucent
  hulls around their members, color-tinted by cluster ID.
- Bloom postprocessing via `UnrealBloomPass` (strength 0.8, radius
  0.5, threshold 0.1) + FXAA.

The force model has four terms (repulsion, trade-attraction,
norm-repulsion, gravity). Cooling on stable clusters keeps the
layout from flickering on settled structure.

Camera: `OrbitControls`. Mouse drag rotates, scroll zooms,
double-click on an agent centers and selects.

## 6. Cluster detection

Per `emergent_clustering.md`, the dashboard runs:

- **Streaming Louvain** every tick on the trade-edge feed. Returns
  cabal partition. Time budget: ~50 ms at 5,000 nodes.
- **30-tick SBM inference** for syndicate stability. Time budget:
  ~500 ms, deferred to a Web Worker.
- **Jaccard-based label matching** across detection passes — cluster
  IDs are stable across ticks.
- **Cabal → syndicate promotion** after 50 ticks of >90% Jaccard
  stability; demotion after 80 ticks of <70% stability.

Each visible agent carries four membership labels: `sector` (hard,
from engine), `firm` (engine, possibly cross-sector after Week 1),
`cabal` (dashboard, live), `syndicate` (dashboard, stable).

## 7. Click-to-inspect

Raycaster on `mousedown` if drag distance < 4 px.

**Agent card** — clicking a node opens a pinnable card on the right:

- **Identity** — prototype ID, sector name, stack, firm ID and
  sector list (e.g. "firm 23: retail + finance"), cabal ID with
  member count, syndicate ID with stability age, registration flag.
- **State** — wealth (log + population percentile), capability,
  autonomy, certified fraction, ticks alive.
- **Norms** — K-axis radar (K from `NormsConfig.n_dimensions`). The
  spatial sandbox sets K = 8 in its own `WorldConfig`; the engine
  default of 4 is left alone so the existing `norms_drift`,
  `norms_capture`, `norms_brittle` scenarios reproduce. K may go
  higher if the radar reads thin.
- **Recent trades** — last 5 partners by ID, surplus, sector,
  whether rejected by which gate.
- **Last fold** — if the agent has spawned or joined a sub-market in
  the last 30 ticks.

**Cluster card** — clicking empty space inside a visible cluster
opens a different card:

- Cabal or syndicate ID, member count, sector composition.
- Median wealth percentile.
- Trade volume share this tick.
- Norm centroid distance from population mean.
- Stability age and Jaccard score history.
- Operations: **Pin** (keep highlight on across ticks), **Watch**
  (warn when membership churn exceeds threshold).

Shift-click adds a second card. `Esc` closes.

## 8. The HUD

Bottom-right, mono caps, no borders. Per `alpha_as_outcome.md`:

```
α         0.62      ← computed from lever state
EBI       0.413     ← measured per tick
WELFARE   +12.4     ← per-tick delta
GINI      0.681
REJ MIX
  cost    0.05
  market  0.08
  align   0.31
  law     0.04
  compute 0.02
FOLDS     43
COMPUTE   0.78      ← pool remaining
TICKS/S   1.8       ← 10-tick moving average
```

The rejection mix tells the user *how* their levers are biting. Two
configurations with the same EBI can have very different mixes; the
mix is the signal that the levers did different things.

## 9. Permalink URL state

Every lever set encodes into the URL hash, e.g.:

```
#cap=0.55&cert=0.45&net=sbm&plocal=0.6&auton=0.7&nrate=0.05&trate=2.0&lawstr=0.5&pigrate=0.10&depthcap=7&txcap=inf&compute=0.8&power=0.1&dist=uniform&scale=small&perm=0.4&seed=24601
```

On load, the page decodes the hash, starts a fresh run with those
values, and exposes a "Copy link" affordance on the inspector card.

## 10. Engine PRs (Week 1)

Six PRs in the agentworld sub-repo, all in the `live-engine` branch.

| PR | Path | Cost | Doc reference |
| -- | ---- | ---- | ------------- |
| Cross-sector firms | `engine/core/institutions.py:88-90` — replace `bin_key = sector * n_stacks + stack` with `bin_key = stack` | ~1 line + ~6 lines metadata | `emergent_clustering.md` §"What this means for the engine" |
| `NormsConfig.certified_fraction` | `engine/core/topology.py:198` (after `initial_norm_seed`), `engine/core/population.py:344`, `engine/core/transactions.py:650` (inside the `norms_cfg.enabled` branch) | ~12 lines | `verifiable_semantics.md` §"What this means for the engine" |
| `LawConfig.transaction_size_cap` | `engine/core/topology.py`, `engine/core/transactions.py:506` (the `law_gate` construction block) | ~25 lines | `legal_levers_in_agent_economies.md` §"What this means for the engine" |
| `ComputeConfig` subsystem | `engine/core/compute.py` (new), `engine/core/transactions.py` pair-admission, `engine/core/topology.py`, `engine/core/world.py` `StepMetrics` | ~150 lines | `compute_and_power_as_constraint.md` §"What this means for the engine" |
| Rich SSE stream (`cast_snapshot_v2`, `edges_v2`, `folds_v2`) | `engine/core/world.py` snapshot assembler, `engine/serve.py` SSE | ~80 lines | `force_directed_trade_graphs.md` §"What this means for the engine" |
| Per-agent norm vector + last-5-partners + degree centrality in snapshot | `engine/core/world.py` | ~15 lines | `force_directed_trade_graphs.md` |

Each PR defaults to off (for the new subsystem fields) so that
existing scenarios and the Sobol baseline reproduce bit-identically.
The spatial sandbox sets the defaults specified in §3.

**Benchmark gate** (Week 1, end-of-week): SMALL scale with every
subsystem on, including the new ones. Measure p50 and p95 tick
latency. If p95 > 6 s/tick, cadence the bottom three subsystems
(`LawConfig`, `RegulatorConfig`, `MissionConfig`) to every 5 ticks
via subsystem-cadence flags. Document the measurement in
`engine/bench/spatial_sandbox.py`.

The hyperbolic network model option (`network_model = "hyperbolic"`,
~40 lines in `engine/core/population.py:368`) is **deferred to Week
3** as a polish item, not gated on Week 1.

## 11. Week-by-week

### Week 1 — engine plumbing

Six PRs above, plus tests:

- `engine/tests/test_cross_sector_firms.py` — firms form across
  sectors when binning rule allows it; `firm_sectors` metadata is
  correct.
- `engine/tests/test_certified_fraction.py` — alignment gate scales
  correctly; per-agent state is reproducible from seed.
- `engine/tests/test_transaction_size_cap.py` — windfall tax revenue
  is captured; recycling channels work; reject mode rejects.
- `engine/tests/test_compute_config.py` — distribution rules
  partition pairs correctly; pool recovery is monotone; reject mix
  surfaces `compute_reject_rate`.
- `engine/tests/test_rich_stream.py` — `cast_snapshot_v2` shape is
  stable; identity persistence works under churn.

Ship target end of Week 1: CLI benchmark prints tick latency for
the new full-subsystem configuration. No browser code yet.

### Week 2 — three.js scene and force simulation

In `agentworld/dashboard/sandbox/`:

- `scene.js` — three.js r158 + OrbitControls + EffectComposer +
  UnrealBloomPass + FXAA.
- `agents.js` — `THREE.Points` BufferGeometry with sector palette,
  custom GLSL shader for emissive + size attenuation.
- `edges.js` — `THREE.LineSegments` with per-vertex alpha decay
  over 30 frames; surplus-weighted width.
- `folds.js` — pool of 64 icosphere meshes for sub-market rings,
  60-frame fade-in.
- `force.js` — ForceAtlas2 in 3D + Barnes-Hut octree, four force
  terms, damping = 0.85, cooling on stable clusters.
- `stream.js` — EventSource subscriber, position buffer, one-tick
  buffer for inter-tick interpolation.

Ship target end of Week 2: hardcoded lever state, no controls, full
3D scene streaming from the engine at 60 fps.

### Week 3 — lever panels, α-as-HUD, cluster detection

- `controls/agentic.js`, `controls/legal.js`, `controls/environmental.js`
  — the three lever panels.
- `alpha_map.js` — lever-state-to-α mapping with pinned weights.
- `hud.js` — bottom-right ambient panel with the readouts in §8.
- `clusters.js` — streaming Louvain over the trade-edge buffer.
- `clusters_sbm.js` — Web Worker running SBM inference every 30
  ticks.
- `cluster_labels.js` — Jaccard matching, syndicate promotion.
- `url-state.js` — hash encode/decode, copy-link affordance.

Hyperbolic network model option lands here as a Week-3 add if
Week-1 benchmark allowed time. Strip every scenario-family pill,
preset selector, and family-radio UI; delete `dashboard/live*.js`.

Ship target end of Week 3: full sandbox lever behavior, α-as-HUD,
visible clusters, URL permalinks.

### Week 4 — inspector, cluster cards, polish, cutover

- `inspector_agent.js` — agent card with the eight sections in §7.
- `inspector_cluster.js` — cluster card with the six fields in §7.
- Pin / multi-pin / watch operations.
- Color palette pass: dark background #060810, 12-step
  bloom-tuned sector palette, mono caps in IBM Plex Mono.
- Ambient audio (`audio.js`): drone pad modulated by EBI, soft click
  on each fold-spawn event, pitch shift on the dominant rejection-mix
  layer. Slow-moving, restrained, no earworm. Toggle in the HUD; off
  on first load so users are not surprised. Audio asset budget: one
  drone sample, one click sample, both procedural-quality. Web Audio
  API; no external library.
- Set the FastAPI root route `/` to serve `sandbox.html`. Move the
  legacy cockpit to `/legacy/live`.
- Update `agentworld/README.md` and `agentworld/dashboard/copy.md`.

Ship target end of Week 4: the sandbox is the front door, with
audio shipping as the last polish item.

## 12. What this replaces

After Week 4 the dashboard tree:

```
agentworld/dashboard/
  sandbox.html              # the new front door
  sandbox/
    scene.js
    agents.js
    edges.js
    folds.js
    force.js
    stream.js
    controls/
      agentic.js
      legal.js
      environmental.js
    alpha_map.js
    hud.js
    clusters.js
    clusters_sbm.js  (Web Worker)
    cluster_labels.js
    inspector_agent.js
    inspector_cluster.js
    url-state.js
  index.html                # static 25-scenario basin map, unchanged
  _tokens.css
  copy.md
  legacy/
    live.html               # archived
```

The seven `dashboard/live_*.js` modules are deleted. The `sandbox/`
directory is the sole live-engine front-end.

## 13. Open technical risks

- **Subsystem cost at SMALL with `ComputeConfig` on.** The Week-1
  benchmark gate addresses this. The fallback ladder cadences the
  three lowest-impact subsystems if p95 exceeds 6 s/tick.
- **Hyperbolic network model.** Deferred. If Week-1 benchmark
  budget allows, lands in Week 3 as a fourth `network_model` option.
  If not, stays as a V2 add.
- **Streaming SBM inference.** 500 ms is the budget; if it blows,
  reduce to every 60 ticks or drop SBM entirely and use Louvain
  stability tests alone.
- **Force simulation jitter.** Damping = 0.85 and cooling on stable
  clusters are the first stabilizers. If clusters still flicker,
  raise damping to 0.92 or move to a multilevel Yifan-Hu base layout
  for the first 30 ticks before switching to ForceAtlas2 streaming.
- **Visible-cluster soft hulls.** Convex hull computation at 5,000
  points is fast; concave hull (for cluster shape fidelity) is
  slower. V1 ships with convex hulls; concave is a polish item.

## 14. Out of scope

- Mobile / touch.
- Replay timeline. Forward-only; rewind via fresh run from seed.
- Multi-run comparison. One run per browser session.
- Regional compute markets in `ComputeConfig`.
- Engine-level emergent sectors. Dashboard cabals/syndicates give the
  user the visual experience without the engine surgery.
- Compute-price discovery (markets for compute).
- t-SNE / UMAP layout. ForceAtlas2 only.
