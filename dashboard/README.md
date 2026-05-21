# Dashboard — Sandbox + legacy cockpit

The dashboard is two pages served by the same FastAPI process at
`agentworld serve` (`engine/serve.py`):

| Page | Path | Use |
| --- | --- | --- |
| **Sandbox** | `/dashboard/sandbox.html` | The primary interactive artifact. One 3D scene, three lever panels, six scenario presets, sphere title under the substrate. |
| Legacy cockpit | `/dashboard/live.html` | The earlier per-scenario streaming view with Plotly charts and a fold-tree tab. Kept for chart-style readouts; not the entry point. |

## Run it

```bash
cd agentworld
uv run agentworld serve --host 127.0.0.1 --port 8765
# open http://127.0.0.1:8765/dashboard/sandbox.html
```

`--port` defaults to 8765. `--host 0.0.0.0` exposes the server on the
LAN (off by default). Stop with Ctrl-C.

---

## The sandbox at a glance

One full-bleed 3D scene with a deformed sphere at the centre. Around it:

| Region | What lives there |
| --- | --- |
| top-left | density readout (cast count, caterpillars per 1K faces) |
| top-right (top row) | scenario picker + Start button |
| top-right (second row) | pause / reset / restart |
| top-right (below) | HUD — α (lever), α (engine), Δ, EBI, welfare Δ, gini, folds, compute, cabals, syndicates, ticks/s, stream |
| left edge | lever panel — 27 controls in four sections (agentic / topology / legal / environmental) |
| right edge (lower) | trades panel — cumulative count, success / fail split, per-objection breakdown |
| right edge (bottom) | wealth meter — humans / AI stock split, per-tick flow (matryoshka, legal capture, recycling) |
| bottom centre | preset title and the steady-state line |

The cast renders as ~10K caterpillar agents on the substrate. Their
positions are driven by recent trades, norm distance, and degree
centrality. Trade rejections push the substrate down under the
offending agent; executed trades push it up. Sustained per-sector
real welfare paints the underlying 12 continents.

---

## Lever map

27 controls. A green dot marks live levers (POST `/runs/{id}/update`
on change, applied next tick). A hollow grey dot marks structural
levers (queued until Restart).

### Agentic (7)

| Lever | Engine field | Kind | Range | Default |
| --- | --- | --- | --- | --- |
| capability (mean) | `agent_capability_mean` | live | 0.10 – 0.90 | 0.55 |
| human capability (mean) | `human_capability_mean` | structural | 0.10 – 0.95 | 0.55 |
| autonomy (mean) | `agent_autonomy_mean` | structural | 0.10 – 1.00 | 0.70 |
| trade rate × (agent) | `agent_trade_rate_multiplier` | live | 0.5 – 5.0 | 2.0 |
| network: p-local | `network_p_local` | live | 0 – 1 | 0.60 |
| certified (fraction) | `norms.certified_fraction` | structural | 0 – 1 | 0.50 |
| norms update rate | `norms.update_rate` | live | 0 – 0.50 | 0.05 |
| network model | `network_model` | live | `well_mixed` / `scale_free` / `sbm` | `sbm` |

### Topology (4)

The engine-level fold-rate knobs. All four are live — set them
mid-run and the next tick uses the new values.

| Lever | Engine field | Range | Default |
| --- | --- | --- | --- |
| α (engine) | `alpha` | 0 – 1 | 0.50 |
| folding propensity | `folding_propensity` | 0 – 1 | 0.55 |
| fold nominal multiplier | `fold_nominal_multiplier` | 1.0 – 3.0 | 1.85 |
| base friction | `base_friction` | 0 – 0.10 | 0.025 |

The HUD reports two α values: **α (lever)** is the dashboard-side
projection from the 20 sociopolitical levers via
`alpha_weights.json`; **α (engine)** is the engine's actual
`TopologyConfig.alpha`. When the gap exceeds 0.05 the Δ row appears.

### Legal (11)

| Lever | Engine field | Kind | Range / Values | Default |
| --- | --- | --- | --- | --- |
| market layer tax | `market_layer_tax` | live | 0 – 0.25 | 0.025 |
| pigouvian tax | `pigouvian.tax_rate` | live | 0 – 0.50 | 0.10 |
| recycling progressivity | `pigouvian.recycling_progressivity` | live | 0 – 4 | 1.0 |
| law strength (init) | `law.law_strength_initial` | structural | 0 – 1 | 0.50 |
| law: txn size cap | `law.transaction_size_cap` | live | 0.05 – 1.0 | 0.30 |
| folding max depth | `folding_max_depth` | live | 1 – 12 | 7 |
| regulator | `regulator.enabled` | structural | on / off | on |
| cross-stack permeability | `cross_stack_permeability` | live | 0 – 1 | 0.40 |
| pigouvian recycling | `pigouvian.recycling` | structural | `human_wealth` / `friction_subsidy` / `capability` | `human_wealth` |
| institutions | `institutions.enabled` | structural | on / off | off |
| mission | `mission.enabled` | structural | on / off | off |

### Environmental (4)

| Lever | Engine field | Kind | Range / Values | Default |
| --- | --- | --- | --- | --- |
| compute budget / tick | `compute.budget_per_tick` | live | 0.1 – 5 | 1.0 |
| power cost / trade | `compute.power_cost_per_trade` | live | 0 – 0.001 | 0.0001 |
| compute distribution | `compute.distribution` | structural | `uniform` / `wealth_weighted` / `capability_weighted` / `autonomy_weighted` | `uniform` |
| scale | `scale` | structural | `small` / `medium` / `large` | `small` |

---

## Presets

Each preset is a target lever-state vector that reproduces a
canonical scenario from `engine/scenarios/__init__.py`. Click Start
to apply it: structural levers snap and trigger a restart, then live
levers tween from their post-restart values to the preset targets
over 5 seconds. The title under the sphere flips to the preset
name; the steady-state detector resets.

| Preset | Engine attractor | What to look for (50 s dwell, small scale) |
| --- | --- | --- |
| coasean paradise | α≈0.08, folding propensity 0.10, depth 2 | EBI/step ≈ 1.58, per-cap welfare ≈ 2.8e-3, sub-markets/step ≈ 3 — sphere reads near-spherical, few folds visible |
| universal advocate | α≈0.20, agent cap 0.90, human cap 0.78 | EBI ≈ 1.71, per-cap welfare ≈ 2.0e-3, fold depth ~3.7 |
| mission economy | α≈0.45, institutions + mission on | EBI ≈ 1.79, fold depth ~4, mission levy routes welfare to coordinator sectors |
| baroque cathedral | α≈0.92, folding propensity 0.65, fold mult 2.0 | EBI ≈ 2.25, per-cap welfare ≈ 1.7e-3, sub-markets/step ≈ 25K — visible cascade activity, sphere flattens / lobes |
| slop market | α≈0.85, agent cap 0.40, fold mult 2.2 | EBI ≈ 2.96, per-cap welfare ≈ 6.7e-4 (worst in the set) — folds spawn but produce little real surplus |
| exo-baroque singularity | α≈0.97, folding propensity 0.78, depth 10, fold mult 2.4 | EBI ≈ 2.92, per-cap welfare ≈ 1.1e-3, sub-markets/step ≈ 370K — fractal limit; sphere maximally deformed |

The numbers are means over the last 20 emitted steps at small scale
(800 human prototypes + 87,200 agent prototypes, weighted to 8B
humans + 800B agents). Run-to-run variance is seed-bounded; the
ordering across presets is stable.

---

## Sphere semantics

The substrate carries three independent deformations:

1. **Per-event bumps.** Each executed trade pushes the face under
   one of the two participants up by ~0.012 (`TRADE_BUMP_BASE`,
   plus a √surplus boost). Each rejected trade pushes it down by
   the same. Bumps decay over ~38 s. Concentration bias amplifies
   bumps near existing features and attenuates opposing-sign bumps
   so peaks and trenches grow rather than averaging out.

2. **Sector continents.** Each tick the dashboard reads
   `real_welfare_per_sector_step` (12 floats), EMA-smooths it,
   z-scores against the sector mean, tanh-squashes, and feeds the
   result to `surface.setSectorAltitudeTargets`. Sectors above the
   mean rise, below sink — capped at ±0.18 altitude per sector.
   Boundaries smooth via per-vertex sector weights so the seams
   read as slopes, not cliffs.

3. **EBI-driven global shape.** When per-step EBI drops below 2,
   the sphere flattens toward a disc; above EBI ≈ 2 it grows
   chaotic lobes. The morph is smoothstep-eased so the shape
   changes ride continuously instead of jumping at tick boundaries.

Colour by depth on the cast (caterpillars) tracks the agent's
current folding depth. Cluster overlays (cabal fills, syndicate
outlines + centroid dots) paint Louvain communities detected on
the rolling trade graph.

---

## Steady-state detector

Each tick the dashboard appends EBI and `real_per_capita_welfare`
to two ring buffers of length 60. After a 30-step warmup, when both
ring buffers' coefficient of variation drops under 0.5 % for 30
consecutive steps, the sub-title under the preset name reads
`STEADY STATE`. The line clears when either CoV rises above the
threshold again.

Detector state resets on Reset and on every Start click. Presets
that don't actually settle — `recursive_simulation`, `fold_avalanche`,
high-α presets with positive-feedback folding — should never
trigger the line; that's expected.

---

## URL state

Pasting the page URL reproduces the run exactly. Every lever
position serialises to a query parameter (TODO: this is the spec;
in V1 only `?dev=1` is read). `?dev=1` opts in to the runtime
invariant checks under `dashboard/sandbox/dev/` — extra console
warnings if the engine emits a payload that violates a contract.

---

## Debug hooks

`window.__sandbox` exposes per-subsystem diagnostics:

```js
window.__sandbox.surface()           // heightmap + sector base state
window.__sandbox.agents()            // cast counters + draw stats
window.__sandbox.firms()             // firm spokes + centroids
window.__sandbox.folds()             // fold ring pool occupancy
window.__sandbox.clusters()          // Louvain primary partition
window.__sandbox.clusterLabels()     // SBM secondary + stable tracks
window.__sandbox.inspector()         // currently-pinned agent cards
window.__sandbox.fps()               // last frame rate
```

The HUD's `stream` row reads `live` / `bg · X.Xs` / `STALL` when
SSE events stop arriving. A stalled stream usually means the engine
crashed on an override or the SSE worker thread got throttled.

---

## Files

```
dashboard/
├── sandbox.html              # the page
├── sandbox/
│   ├── scene.js              # main loop, lever wiring, presets, steady-state
│   ├── surface.js            # icosphere substrate + heightmap + sector base
│   ├── agents.js             # caterpillar cast on the substrate
│   ├── edges.js              # arc trade-edges (visually hidden, used for clustering)
│   ├── firms.js              # firm spokes + centroid markers
│   ├── folds.js              # fold-spawn ring pool
│   ├── clusters.js           # Louvain primary clusterer
│   ├── cluster_labels.js     # cabal / syndicate stable tracks
│   ├── cluster_overlay.js    # 3D cluster patches + outlines
│   ├── clusters_sbm.js       # SBM secondary clusterer (Web Worker)
│   ├── stream.js             # SSE start + RunRequest body
│   ├── stream-worker.js      # EventSource worker (background-tab safe)
│   ├── inspector_agent.js    # agent-card stack on click
│   ├── alpha_map.js          # lever → α projection
│   ├── alpha_weights.json    # sign-vector weights for the projection
│   ├── alpha_ebi_curve.js    # cached α→EBI curve from the Sobol sweep
│   ├── trails.js, bonds.js, dust.js   # secondary visuals
│   ├── palette.js, themes.js
│   ├── _legacy/              # previous cockpit assets, kept for reference
│   └── dev/                  # ?dev=1 runtime invariant checks
├── live.html                 # legacy cockpit
└── live_*.js                 # legacy Plotly + fold-tree views
```
