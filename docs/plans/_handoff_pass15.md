# Spatial sandbox — Pass 15 handoff

You are picking up the agentworld spatial-sandbox dashboard mid-flight.
Read this whole brief before writing any code.

## Where the work lives

Working directory: `/Users/marek/Documents/economy and ecology/agentworld/`
Branch: `live-engine` (and feature branch `spatial-sandbox-dashboard-week2`
at the same commit).
Current HEAD: `22a8f9d` — Pass 15.

Agentworld is a sub-repo at the path above. **All commits go inside
that sub-repo on `live-engine`.** The outer `economy and ecology` repo
treats agentworld as a gitlink (mode 160000); do **not** proactively
bump the outer-repo pointer — that is Marek's manual step.

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

## What's been built (Week 2, 15 passes)

The dashboard is at `dashboard/sandbox.html` + `dashboard/sandbox/*.js`.
Pass 15 is the current state; intermediate passes are in git for
historical context.

**Pass 15 architecture (current):**

A high-subdivision icosphere is the entire visualisation. The sphere
itself is the canvas; the cells-on-a-sphere paradigm of Passes 1–12 is
gone.

- `surface.js` (main module). Builds a ~398k-triangle
  `IcosahedronGeometry(700, 140)`. Custom `ShaderMaterial` with a
  per-vertex `color` attribute (face-uniform — all 3 vertices of a
  triangle share its colour) and a per-vertex `barycentric` attribute
  that drives an in-shader grid render: `min(barycentric) <
  edgeThreshold ? edgeColor : fillColor`. No `GL_OES_standard_-
  derivatives` (that broke on one of Marek's WebGL contexts).
- Activation pipeline: each cast slot is mapped to one face via a
  `mulberry32` hash of its prototype `idx`, so adjacent slots land on
  far-apart triangles. When `handleCastSnapshot` sees a wealth move
  bigger than `activationThreshold` (0.02), it schedules the
  activation at `currentFrame + Math.random() * STAGGER_FRAMES` (12)
  so same-snapshot triggers spread across the inter-snapshot interval
  instead of pulsing in lockstep.
- Persistence semantics: each activation's lifetime is proportional
  to the magnitude of the wealth move that fired it. log1p-scaled
  between `MIN_PERSIST_FRAMES` (60 ≈ 1s) and `MAX_PERSIST_FRAMES`
  (720 ≈ 12s), saturating at `MAGNITUDE_REF = 10`. Brightness decays
  linearly from active colour at fire frame to base colour at
  expiry. Two engine-tied semantic axes: lifetime ↔ event magnitude,
  intensity ↔ recency.
- `themes.js` — single exported `THEME` (fine-grain). The 10-theme
  switcher was a previous pass; Marek picked fine-grain and dropped
  the rest.
- `scene.js` — minimal renderer + OrbitControls + animation loop. No
  lighting (flat shader), no bloom, no tonemap, no other render
  modules.
- `stream.js` — `POST /runs` + EventSource subscriber for the SSE
  channels. Unchanged from Pass 1.

**Engine surface (consumed by surface.js):**

From the Week-1 PRs, the engine emits these SSE events on
`/runs/{id}/stream`:
- `hello`              — `{run_id, scenario, scale, n_steps_target}`
- `step`               — full `StepMetrics` dict per tick
- `cast_snapshot_v2`   — `{step, snapshot: [agent records]}`
- `edges_v2`           — `{step, edges: [PairSample dicts]}`
- `folds_v2`           — fold-cascade contribution per depth

Each `cast_snapshot_v2` entry carries `idx, is_human, sector, wealth,
capability, autonomy, firm_id, firm_sectors, stack, intermediation_-
pref, certified, norm_distance, norm_xy, norm_vector,
degree_centrality, recent_partners`. Pass 15 only reads `wealth` (for
the delta-detection), `idx` (for slot mapping), and the snapshot list
length (for the initial layout).

## What Marek wants from the next session

Marek has been iterating on the aesthetic for ~3 hours and finally
landed on the Pass 15 paradigm. His most recent direction-setting was:

> "the decay cycle of the triangles should mean something and should
>  not be arbitrary
>  the triangles should persist, ideally for longer than a few seconds
>  remove all the other sample uis"

Pass 15 addresses all three. The triangle persistence is now bound to
wealth-delta magnitude, the lifetimes range 1–12 s, and the 10-theme
switcher is gone.

Open directions for next session — Marek hasn't committed to any of
these specifically, ask him before pursuing:

- **More engine signals bind to triangle visuals.** Currently only
  wealth delta drives activation. Bond strength, cabal membership,
  autonomy, norm distance — each could control a different visual
  axis (per-triangle hue tint within greyscale, edge weight, fade
  curve, opacity floor). Look at the cast_snapshot_v2 entry shape
  before designing.
- **Per-snapshot vs per-tick activation rate.** With `MIN_PERSIST =
  60` and ~3,000 events per snapshot at 5 snapshots/sec, ~150,000
  face-frame-seconds of activity are scheduled per second across
  ~3,300 unique faces (cell-mapped) of 398k total. Density may need
  rebalancing if Marek pushes for more or fewer concurrent active
  faces.
- **Inspector / lever panels.** Plan §7-§9 in
  `docs/plans/spatial-sandbox.md`. Not started. Week-3 territory.
- **URL permalink state.** Plan §9.

Marek's working style:
- Terse direction-setting. Read his feedback as design instructions
  not preferences.
- Decisive redirects. He'll throw out a whole rendering paradigm if
  it doesn't work; do the same when he asks.
- Show diffs before committing — at least on the first change of a
  session. Pushes only when he says so.
- Strict styleguide on prose (commits + docs + user copy). Read
  `styleguide_reference.md` before writing any.

## How to run

```bash
cd "/Users/marek/Documents/economy and ecology/agentworld"

# Engine + SSE bridge (must run for the dashboard to do anything)
source .venv/bin/activate
uvicorn --factory engine.serve:create_app --host 127.0.0.1 --port 8765

# Then open http://127.0.0.1:8765/dashboard/sandbox.html in Chrome
# with a focused window (background tabs throttle rAF aggressively).

# Tests
pytest engine/tests/

# Sweep smoke (must still reproduce after engine changes)
agentworld sweep --quick
```

## Read order before writing code

1. This file.
2. `docs/plans/spatial-sandbox.md` §0 (onboarding) + §11 (week
   breakdown). Note that Marek deviated from the plan in Pass 13:
   the cells-on-a-sphere paradigm became a tessellated surface
   paradigm. The plan's force-directed-graph approach is no longer
   the active design.
3. `dashboard/sandbox/surface.js` (180 lines, the whole renderer).
4. `dashboard/sandbox/themes.js` (single exported config).
5. The most recent ~5 commits (`git log --oneline -5`) to see the
   immediate trajectory.

## Don'ts

- Don't reintroduce a global rotation, additive blending, or dark
  background — Marek explicitly walked away from each of those in
  Passes 7, 13, and 13 respectively.
- Don't add `#extension` directives in WebGL shaders — Pass 14b
  was a fire drill from `GL_OES_standard_derivatives`.
- Don't write 30-frame-fade arbitrary decay constants — Marek
  explicitly required the decay to mean something tied to engine
  state (Pass 15).
- Don't add the other 9 sample themes back — they were dropped
  intentionally.
- Don't push without being asked; do show diff before committing
  on the first change.
