# Spatial sandbox — Pass 25 handoff

You are picking up the agentworld spatial-sandbox dashboard mid-flight.
Read this whole brief before writing any code. The earlier Pass 15
brief (`_handoff_pass15.md`) covers the cells-on-a-sphere transition
that preceded the current paradigm — useful background, not strictly
required.

## Where the work lives

Working directory: `/Users/marek/Documents/economy and ecology/agentworld/`
Branch: `live-engine`
Current HEAD: `7da2e99` — Pass 25 wealth-flow meter + continuous mode.

Agentworld is a sub-repo at the path above. **All commits go inside
that sub-repo on `live-engine`.** The outer `economy and ecology`
repo treats agentworld as a gitlink (mode 160000); never proactively
bump the outer pointer — that is Marek's manual step.

Three load-bearing memory files at
`~/.claude/projects/-Users-marek-Documents-economy-and-ecology/memory/`:

- `feedback_agentworld_repo_boundary.md` — commit inside agentworld
  only, never bump the outer pointer.
- `feedback_build_plus_repurpose.md` — when adding capability, build
  new where design calls for it, repurpose existing where overlap is
  natural; default new subsystems off.
- `styleguide_reference.md` — Marek's prose styleguide. Strict
  banned-vocabulary list. Read this before drafting docs, commit
  messages, or any user-visible copy.

## What's been built since Pass 15

Pass 15 was a high-subdivision icosphere with per-face wealth-Δ
activations. Passes 16–25 replaced that paradigm with a deformable
substrate, persistent caterpillar agents, sector regions, live trade
arcs, and a wealth-flow meter.

### Pass 17 — caterpillar agents (graph-walking)

`dashboard/sandbox/agents.js`. Each cast slot is a caterpillar that
occupies one icosphere face and steps to an edge-adjacent face every
N frames. Body segments are the actual three vertices of the face,
scaled to `segmentScale=0.75` toward the centroid. Bindings:

- wealth → body length (log2 bucket)
- capability → step rate
- is_human → body-length multiplier
- recent_partners / firm_id → bias the neighbour-choice scoring

Surface.js owns the icosphere geometry, face centroids, and a
3-neighbour adjacency table (vertex-dedup hashed with integer keys at
startup, ~1–2 s for the 398k-face mesh).

### Pass 18–19b — heightmap substrate

`dashboard/sandbox/surface.js`. The icosphere is no longer rigid:

- Per-unique-vertex altitude (~200k unique verts). Adjacent faces
  sharing a vertex agree on its altitude, so the deformed mesh stays
  continuous — no cliffs at face boundaries.
- Vertex shader displaces position by `(1 + (altitude + uGlobalAltitude) * uAltitudeScale)`.
- Altitude-only shading: `vShade = max(0.55, 1 + altitude * 1.8)`.
  Peaks brighten, pits darken with a floor.
- Global modulation clamped tightly: `uAltitudeScale ∈ [0.9, 1.10]`,
  `uGlobalAltitude ∈ [-0.03, +0.03]`. Earlier loose ranges drove the
  displacement into a regime where the grid disappeared.
- Asymmetric altitude cap: `altitudeMaxPos = 0.40`, `altitudeMaxNeg = 0.12`.
  Inward pressure floors early so positive growth dominates the
  per-vertex budget.

### Pass 20–21 — bumps

- Wealth-Δ uses `sqrt(delta)` (was `log1p`). Small deltas still
  register; big deltas saturate gracefully.
- Positive bumps multiplied by `positiveBumpFactor = 10`.
- Primary positive driver is **successful trades** from `edges_v2`,
  not snapshot-to-snapshot wealth delta. Every executed pair raises
  both partners' faces by `TRADE_BUMP_BASE × (1 + √surplus)`.
- Negatives: reject bumps, stack-N carve per step, wealth losses.

### Pass 22 — sector partition

`surface.js` precomputes 12 Voronoi regions on the unit sphere with
Fibonacci-distributed anchor points; each face is tagged with its
sector. Agents are constrained to walk inside their sector's region
(`chooseNeighbour` filters to same-sector neighbours with a fallback
at boundaries).

Mouse hover: analytic ray-vs-sphere intersection, nearest-anchor
lookup in O(12). The hovered sector gets a soft blue outline along
its Voronoi boundary edges (per-vertex `sectorBoundary` attribute) +
~6% brightness boost + a label following the cursor with the sector
name (`agriculture, extraction, ..., leisure` — see
`engine/core/population.py::SECTOR_NAMES`).

### Pass 23 — trade arcs

`dashboard/sandbox/edges.js`. `LineSegments2 + LineMaterial` for
screen-space-thick lines. Every sampled pair in `edges_v2` becomes
an arc anchored to both agents' current head faces. Lifetime 4 s
(240 frames); the arc tracks both endpoints live as the caterpillars
walk. Each frame rebuilds the geometry from current positions.

- Blue when executed, red when `reject_reason` is set.
- `sin(πt)` parabolic arch, 28% of radius at apex, 60 samples.
- Colour fades toward the cream paper background over lifetime.
- `depthTest: false` so arcs always render on top of the substrate.

Toggle panel (bottom-left): show trades, show sectors. Cumulative
trade counter that increments per snapshot, formatted with commas.

### Pass 24–25 — wealth flow meter

Engine now emits `human_wealth_share = Σ(weight×wealth | human) / Σ(weight×wealth)`
in StepMetrics (cached on the gini cadence).

Bottom-right side panel shows:

- Cumulative real welfare (`real_welfare_cumulative`) at the top.
- Five meter rows with coloured dots, percentages, and bar fills:
  - humans, ai, matryoshka (Matryoshka stack overhead),
    legal capture, pigouvian recycling.
- Per-frame ±1.2% sine jitter so the bars wobble even when the
  underlying shares are stable.

`continuous: true` was added to `LEVERS` in `scene.js` so the run
loops indefinitely.

Three earlier welfare-cap directions were tried and dropped:

- Persistent line chart of `human_wealth_share` over time.
- Single drawRange-based welfare cap on a second icosphere.
- Five concentric shader-driven welfare shells, camera-anchored.

The fifth direction (the meter) is what survives.

## Open directions Marek may pursue next

These are pulled from the `docs/plans/spatial-sandbox.md` plan but
none of them are committed. Ask before starting.

- **Three lever panels** (plan §3 — agentic / legal / environmental).
  Currently no controls; LEVERS is a literal in `scene.js`. Building
  these will require **engine work**: `engine/serve.py::_LIVE_TUNABLE`
  is a 14-key whitelist that doesn't include `NormsConfig.*`,
  `LawConfig.*`, `PigouvianConfig.*`, or `ComputeConfig.*` fields.
  `_apply_overrides` only resolves against `WorldConfig`,
  `TopologyConfig`, `PopulationConfig` — it does not recurse into
  nested configs. So most of the plan's lever rows can't be wired
  live without extending these.

- **α-as-HUD** (plan §4 + §8). α is currently a hardcoded value in
  scenario configs. Plan §4 has the lever-state → α mapping. The
  HUD readout would surface α + EBI + a few other Sobol-grounded
  metrics.

- **URL permalink state** (plan §9). The dashboard would
  hash-encode the lever state so reloading replays the same run.

- **Inspector / cluster cards** (plan §7). Click an agent to open
  a card with its identity / memberships / norm vector / recent
  trades. Click empty cluster space → cluster card.

- **Reject-hole topology** (mentioned in pass-19 conversations,
  never built). Reject events would punch alpha-zero holes through
  the outer substrate, exposing the agent strata beneath.

## Engine surface (consumed by the dashboard)

- `cast_snapshot_v2` (5 Hz): per-agent state — `idx, is_human,
  sector, wealth, capability, autonomy, firm_id, firm_sectors,
  stack, intermediation_pref, certified, norm_distance, norm_xy,
  norm_vector, degree_centrality, recent_partners`.

- `edges_v2` (5 Hz): per-pair sampled trades — `proto_a, proto_b,
  is_a_human, is_b_human, sec_a, sec_b, cap_a, cap_b, base_surplus,
  friction, real_surplus, executed, reject_reason, pair_weight`.

- `step` (5 Hz): full `StepMetrics`. The dashboard currently reads
  `step.fold_max_depth, step.exo_baroque_index,
  step.rejected_law/_market/_align/_cost/_compute/_permeability/_regulator,
  step.real_welfare_cumulative, step.human_wealth_share,
  step.governance_overhead_fraction, step.law_surplus_loss_fraction,
  step.pigouvian_effective_rate`.

`pair_sample_k = 1500` per snapshot. The cast is `cast_size = 5000`
agents (50% human quota). Only pairs whose `proto_a` AND `proto_b`
are in the cast render as arcs — about 5–10% of sampled pairs.

## Marek's working style

- **Terse direction-setting.** Read his feedback as design
  instructions, not preferences.
- **Decisive redirects.** He throws out whole rendering paradigms
  when they don't work — do the same when he asks. Don't argue.
- **Iterates fast.** Ship a visible pass, let him react. Don't
  over-engineer or wait for clarification when the cost of doing
  the wrong thing is small.
- **Show diff before committing on first change of session.**
  After that, commit when he says.
- **Push only when asked.**
- **Strict styleguide on all prose** (commit messages, docs,
  UI copy). The banned-vocabulary list is in
  `styleguide_reference.md` — keep that open when drafting.

## Don'ts gleaned from passes 16–25

- **Don't combine large `uAltitudeScale` with large `uGlobalAltitude`** —
  the displacement factor can approach zero or invert and the grid
  disappears. Pass 19 broke this way. Clamp both tightly.
- **Don't switch ShaderMaterial to `glslVersion: THREE.GLSL3`
  without testing first.** three.js auto-injects an `out highp vec4
  pc_fragColor` that conflicts with a user-declared `out vec4`. Pass
  19's grid vanished silently because of this.
- **Don't camera-anchor visualizations that are supposed to be
  world-fixed.** Use `depthTest: false` + `side: DoubleSide`
  instead so the structure stays anchored and just renders on top.
- **Don't use `log1p()` to compress wealth-delta bumps.** Kills
  positive-deformation visibility in scenarios where deltas are
  small. Use `sqrt()` for gentler compression.
- **Don't symmetrically cap altitude.** Asymmetric (`+0.40` peaks,
  `−0.12` pits) lets positive growth dominate against the three
  negative sources (loss + stack carve + reject bump).
- **Don't use `LineBasicMaterial` for thick lines.** Capped at 1px
  on most WebGL drivers. Use `LineSegments2 + LineMaterial` with
  `linewidth` in screen pixels.
- **Don't push without asking.** Don't bump the outer-repo gitlink.

## How to run

```bash
cd "/Users/marek/Documents/economy and ecology/agentworld"
source .venv/bin/activate

# Engine + SSE bridge — must run for the dashboard to do anything.
uvicorn --factory engine.serve:create_app --host 127.0.0.1 --port 8765 --log-level warning

# Then open http://127.0.0.1:8765/dashboard/sandbox.html in a focused
# Chrome window (background tabs throttle rAF aggressively).

# Tests
pytest engine/tests/

# Sobol baseline smoke (run after any engine PR)
agentworld sweep --quick
```

The engine occasionally hangs after long runs; if `/healthz` doesn't
respond, kill the uvicorn process and restart.

## Read order before writing code

1. This file.
2. `~/.claude/projects/.../memory/styleguide_reference.md`.
3. `dashboard/sandbox/scene.js` (the entry point, ~500 lines).
4. `dashboard/sandbox/surface.js`, `agents.js`, `edges.js`.
5. The recent commit history: `git log --oneline -15` inside the
   agentworld sub-repo.
6. `docs/plans/spatial-sandbox.md` §3, §4, §7, §8, §9 for the open
   directions.
