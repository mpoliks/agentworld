# Spatial sandbox — legibility pass

A follow-on plan after the independent PhD-reviewer pass on the live
sandbox. The reviewer found that the engine instrumentation (HUD,
sparklines, inspector card, sector hover, α-gap row) is honest and
load-bearing, but the 3D scene fails to communicate the three
theoretical claims the experiment is built around: α-as-outcome,
emergent clustering, and rejection-mix as moral signal. The dominant
visual is the per-vertex wealth-Δ bump field, which carries
high-frequency local signal and zero perceptible regional signal; the
EBI shape morph loses the fight against that field; cabals and
syndicates render at zero across every regime; ten of the twenty-one
lever weights in `alpha_weights.json` are pinned at zero; the weights
file silently 404s on cold load; the HUD and lever panel overlap.

This plan keeps every part of the current dashboard that the reviewer
flagged as working and fixes only what is failing. The work is ordered
by repair cost ascending so the cheapest, highest-leverage fixes ship
first.

---

## 0. Starting context for a new agent

All code lives in the agentworld sub-repo on `live-engine`. The outer
repo treats agentworld as a gitlink; do not bump it. Read in order:

1. `spatial-sandbox.md` — the originating plan.
2. `spatial-sandbox-completeness.md` — the prior fill-in pass.
3. The seven research docs in `docs/research/`.
4. The current dashboard at `dashboard/sandbox/` — `scene.js`,
   `surface.js`, `agents.js`, `edges.js`, `clusters.js`,
   `cluster_overlay.js`, `cluster_labels.js`, `alpha_map.js`, plus
   the `alpha_weights.json` companion.

Run the dashboard with:

```
cd /Users/marek/Documents/economy\ and\ ecology/agentworld
.venv/bin/uvicorn --factory engine.serve:create_app --host 127.0.0.1 --port 8765
# Then: http://127.0.0.1:8765/dashboard/sandbox.html
```

The default-off principle from prior plans still applies: every new
field defaults to a value that reproduces today's visible behavior.

---

## 1. What this plan must not break

These pieces of the current build are graded "working" by the review
and are non-targets for the remediation. Any phase that regresses one
of them is rejected.

- The α-gap HUD row. It appears when |lever − engine| > 0.05 and is the
  single most honest design move in the dashboard.
- Sector-region Voronoi hover-outline plus floating sector label.
- Sector-compass click-isolate (5 s, 0.18 alpha for non-isolated
  agents).
- Agent inspector card — identity, sector, firm composition, K-axis
  norm radar, recent partners, percentile-stamped wealth.
- Trade-arc colour palette keyed by outcome (executed + 7 reject
  classes) and the three-tier surplus width (`0.5 / 3.0 / 9.0`).
- Fold-icosphere depth gradient (grey → magenta) and its match to the
  matryoshka sparkline.
- Wealth-flow meter — stock split bar plus three 60-tick sparklines
  (matryoshka, legal capture, recycling).
- Pause/Restart semantics with the live-vs-structural dot convention
  and structural-pending banner.
- The seven-channel rejection mix and its `‼ sum` integrity check.

Anything not on this list is in scope for change.

---

## 2. Phase A — cold-load fixes (0.5 days)

Two bugs that produce silent miscommunication on first page load. Both
are one-line fixes plus their tests.

### A.1 `alpha_weights.json` 404 on cold load

`scene.js:1533` calls `loadAlphaWeights('./alpha_weights.json')`.
`fetch()` resolves the relative path against `document.baseURI`, which
is `/dashboard/sandbox.html`. The browser requests
`/dashboard/alpha_weights.json`. The file lives at
`/dashboard/sandbox/alpha_weights.json`. The fetch 404s, the loader
catches the error, the HUD α-lever stays glued at the baseline 0.500
until the user manually triggers a reload.

Fix: change the path in `scene.js:1533` to `./sandbox/alpha_weights.json`
or — preferred — resolve relative to the module URL in `alpha_map.js`:

```js
const DEFAULT_URL = new URL('./alpha_weights.json', import.meta.url);
export function loadAlphaWeights(url = DEFAULT_URL) { … }
```

The module-relative form makes the call site robust to future
relocation of either file.

### A.2 HUD-vs-lever-panel z-collision

`#hud-panel` is `top: 54px; right: 18px; z-index: 50`. `#levers-panel`
is `bottom: 18px; right: 18px; z-index: 50` with
`max-height: calc(100vh - 36px)`. The lever panel content overflows
viewport-height and covers the HUD's rejection-mix rows on any window
under ~1100 px tall.

Fix: move the lever panel to the left edge. The HUD owns the
right edge from `top: 14px` to `bottom: 14px`; lever panel slots to
`left: 18px; bottom: 18px`. The wealth-flow meter swaps to
`bottom: 18px; right: 18px` under the HUD if vertical clearance
allows, otherwise overlaps the lever panel on the left edge.

Alternative if the left-edge swap is too invasive: keep both
right-side but shrink HUD width to 130 px and lever-panel width to
180 px, set HUD `right: 220px` so they sit side by side.

### A.3 Phase-A checks

- `test_alpha_weights_load.spec.js` — Puppeteer: cold load,
  programmatically read `mapAlpha({pigouvian.tax_rate: 0.45})`,
  assert ≠ 0.5.
- `test_layout_no_hud_collision.spec.js` — Puppeteer: cold load at
  viewport 1280×800, assert `hud-rej-cost` element is not occluded
  by `levers-panel` per
  `document.elementFromPoint(getBoundingClientRect().centerX, .centerY)`.

---

## 3. Phase B — substrate aggregation (3 days)

The per-vertex wealth-Δ bump is honest at the agent scale and
swamps every regional signal. The fix preserves the local readout but
adds a complementary regional channel that the eye can integrate.

### B.1 Per-region aggregator

Tag every face with its Voronoi region (already done — `surface.js`
ships the 12-region sector partition). Sum the per-face wealth-Δ
bumps over a 30-tick sliding window into a per-region float. Render
the 12 regional totals as a low-frequency colour overlay on the
substrate — light cream where the region is welfare-positive over the
window, faint copper-red where it is welfare-negative, neutral at
zero. Same palette family as the wealth-stock split bar (amber
positive, blue-grey negative) so the visual rhymes with the meter
panel.

The high-frequency per-vertex bumps stay but get capped: clamp the
per-step bump to ±0.06 (was ±0.20) and drop `positiveBumpFactor` from
10.0 to 3.5. The regional overlay carries the accumulated signal; the
per-vertex bump keeps the "agents make terrain" intuition without
dominating.

### B.2 EBI-driven uAltitudeScale instead of fixed

`surface.js` reads `uAltitudeScale` as a fixed uniform. Drive it from
the EBI EMA so per-vertex amplitude is low in the calibrated band and
rises in the lobed band. This lets the bristle act as a regime
amplifier rather than a uniform texture:

```
uAltitudeScale = 0.6 + 1.4 * smoothstep(2.0, 4.0, ebiSmoothed)
```

At EBI=1.5 (disc): bumps barely visible. At EBI=3.5 (lobes): bumps
register as the lobes' surface texture. This couples the two signals
the substrate is already trying to carry.

### B.3 Caterpillar density toggle

Add a fourth toggle to `#toggles`: "show caterpillars". Default on
matches today. Off renders agents as ~5 px round head dots at the
current face centroid, no trail. The "all caterpillars at 5000 agents"
view is preserved as the default; the dot view is for when the user
wants to read the substrate overlay without caterpillar interference.

### B.4 Phase-B checks

- `test_substrate_regional_overlay.spec.js` — render a stub run where
  one region accumulates +1.0 welfare/tick for 30 ticks and the rest
  are flat; assert the region's overlay reads amber and the others
  read neutral within ±5% luminance.
- `test_substrate_bump_clamp.spec.js` — engine emits a single
  wealth-Δ event of magnitude 100; assert the rendered vertex
  altitude clamp held at +0.06.
- `test_substrate_ebi_morph_amplitude.spec.js` — feed three EBI
  values (1.0, 2.0, 4.0) and assert `uAltitudeScale` reads 0.6, 0.6,
  2.0 respectively (smoothstep boundaries).

---

## 4. Phase C — cluster diagnostic (2 days)

Across 700 ticks at three different lever corners, cabal count stayed
at 0. The reviewer cannot distinguish "engine produces no community
structure" from "detector is broken" from "overlay never wires up."

### C.1 Surface the detector's intermediate state

Add three HUD readouts under the existing `CABALS / SYNDICATES` rows:

```
EDGES IN          1812
CANDIDATES        14
RENDER FLOOR       3 / 14
```

- `EDGES IN` — the size of the trade-edge buffer fed into Louvain
  this tick.
- `CANDIDATES` — number of communities Louvain partitioned the graph
  into, regardless of size.
- `RENDER FLOOR` — `MIN_CABAL_RENDER_SIZE` (currently 3) vs.
  CANDIDATES, so the user sees how many partitions fall below the
  rendering threshold.

This converts the "0 / 0" cliff into a continuous readout that
distinguishes the three failure modes.

### C.2 Drop `MIN_CABAL_RENDER_SIZE`

Lower the render threshold from 3 to 2. The Fortunato-Barthélemy
resolution-limit floor (`√(2E) ≈ 45` at 1000 edges/tick) caps cabal
size from below, not from above; rendering 2-member transient
communities is honest about what Louvain produces and what the
resolution limit forbids.

### C.3 Engine-level cabal seed in one scenario

Add a `cabals_seeded` scenario in `engine/scenarios/__init__.py` that
forces a clear three-cluster trade structure via SBM with extreme
intra-block density and zero inter-block. Use this scenario in a
contract test that asserts the dashboard's HUD reports `CABALS ≥ 3`
within 60 ticks. If the test fails, the wiring bug is in the
dashboard; if it passes, the absence of cabals in the default
`spatial_sandbox` scenario is a true engine result.

### C.4 Phase-C checks

- `test_cabal_diagnostic_rows.spec.js` — stub the cluster worker to
  return a 14-partition result with 11 below floor; assert HUD reads
  `CANDIDATES 14 / RENDER FLOOR 3 / 14`.
- `test_cabals_seeded_scenario.py` — pytest: run the new scenario
  for 60 ticks, assert at least 3 cabals survive both Louvain passes.
- `test_cabal_min_size_2.spec.js` — Puppeteer: stub a 2-member
  cabal; assert overlay patch renders.

---

## 5. Phase D — α-weight completion (1.5 days)

Ten of the twenty-one scalar levers ship with `weight: 0` in
`alpha_weights.json`. The rationale field claims this is forward
compatibility; the UI ships those levers as live controls. The user
sees them respond on the slider and not move α — the lever lies.

### D.1 Hand-pin weights for the remaining ten levers

Each non-zero lever in §3 of `alpha_as_outcome.md` already has a sign
direction. Pin a weight equal to the mean of the existing six
weights (current mean = 0.067) for each of the ten zero-weight
scalars: `agent_capability_mean`, `norms.certified_fraction`,
`network_p_local`, `agent_autonomy_mean`, `norms.update_rate`,
`agent_trade_rate_multiplier`, `law.strength`, `folding.max_depth`,
`law.transaction_size_cap`, `regulator.enabled`. Re-tune downward
together so the all-positive corner still lands at α=0.90 and the
all-negative corner at α=0.10 — the existing range-coverage check
in `alpha_map.js` will fail loudly if it drifts.

### D.2 Mark unmapped levers visibly

Levers whose engine field is not yet implemented (e.g. agentic
levers that need the cross-sector firms PR, certified_fraction PR,
etc., per `spatial-sandbox.md §10`) get a hollow square next to
their label and a tooltip "structural — weight applied to lever-α
only; engine reads on restart." The current hollow-circle is the
live/structural distinction; the new hollow-square marks
"contributes to mapping, not yet sensed by engine."

### D.3 Phase-D checks

- `test_alpha_weights_no_zero.json` — schema test: assert every
  entry in `levers.*` has `weight > 0`.
- `test_alpha_range_corners.spec.js` — call the existing
  `checkRangeCoverage()` and assert `minAlpha ≤ 0.15`,
  `maxAlpha ≥ 0.85`.
- `test_alpha_monotonicity.spec.js` — call `checkMonotonicity()`
  and assert every lever passes 7/8 steps with its declared sign.

---

## 6. Phase E — per-agent signal aggregation (2 days)

Capability, autonomy, and trade-rate are mapped to per-agent step
rate, random-walk probability, and step frequency. At 5,000 agents
on a 700-radius sphere viewed at default zoom, these are below the
human just-noticeable-difference threshold; the visual impact of
dragging `agent_capability_mean` from 0.10 to 0.90 is zero.

### E.1 Population histogram in the toggles panel

Below the sector compass, add a 60-tick population histogram for the
three agentic levers in three small bars:

```
CAPABILITY     ▁▂▃▅▇█▆▄▂▁    μ=0.55  σ=0.12
AUTONOMY       ▂▃▅▇█▇▆▄▃▂    μ=0.70  σ=0.10
TRADE RATE     ▁▁▂▄█▇▅▃▂▁    μ=2.0   σ=0.45
```

Each bar is a 10-bucket histogram of the cast snapshot's per-agent
values for that field, redrawn every tick. The user dragging the
capability slider sees the histogram shift in real time. The
caterpillars on the surface stay agnostic about these levers as
before, but the population-level visual readout makes the slider
honest.

### E.2 Inspector card delta against population

The inspector card already shows per-agent capability/autonomy/
certified. Add a percentile next to each ("0.378 / p23") so the
inspected agent reads against the population the histograms describe.

### E.3 Phase-E checks

- `test_population_histogram_redraw.spec.js` — feed two cast
  snapshots with different capability distributions; assert the
  histogram bars differ.
- `test_inspector_percentile.spec.js` — stub a cast snapshot with
  known capability vector; assert the inspector's percentile reads
  match the computed quantile.

---

## 7. Phase F — firm spoke legibility (1 day)

Firm spokes render at opacity 0.08 and disappear into the substrate
bristle. Cross-sector firms are exactly the engine PR that landed for
this dashboard; the user cannot see them.

### F.1 Spoke opacity floor by firm size

Replace the fixed 0.08 with a size-weighted formula:

```
opacity = min(0.55, 0.10 + 0.025 * log2(member_count))
```

A 2-member firm renders at 0.125; a 64-member firm at 0.275; a
1000-member firm at 0.55. Single-sector firms keep the lower opacity;
cross-sector firms get an additional +0.10 boost so they read more
strongly. The cross-sector data is already in the snapshot per
`emergent_clustering.md §"What this means for the engine"`.

### F.2 Firm hover

Hovering a caterpillar with a non-negative `firm_id` lights up all
co-firm members for the hover duration with a thin amber ring. Click
opens the inspector card as today. The hover is the cheap, ambient
read; the click is the deep read.

### F.3 Phase-F checks

- `test_firm_spoke_opacity.spec.js` — render a stub firm with 64
  members; assert spoke opacity = 0.275 within ±0.01.
- `test_firm_hover_ring.spec.js` — Puppeteer: hover an agent with
  firm_id=5; assert all co-firm members carry a `firm-hover` class
  for the hover duration.

---

## 8. Phase G — live exploration of structural levers (3 days)

Thirteen of the twenty-one levers are structural — they queue and
require a Restart to apply. The theory in `verifiable_semantics.md §4`
asks the user to "drop certified-fraction from 0.8 to 0.2 over 30
ticks" — that interaction does not exist in the live UI.

### G.1 Predicted-after-restart preview

When a structural lever is dragged, the pending banner already
appears. Add a second row under the banner:

```
RESTART PREVIEW
  α (lever)   0.46 → 0.71  (+0.25)
  EBI est     1.92 → 2.65  (+0.73)
```

EBI estimate is the existing pinned-weight α regression run forward
through a single-shot evaluation of the cached `step.alpha → EBI`
curve from the latest Sobol sweep. Read the curve from
`outputs/sensitivity/sobol_indices.n2048.json`. The estimate is
clearly labelled as such and bounded by the curve's interpolation
domain.

### G.2 Engine-side live promotion of three structural levers

`agent_capability_mean`, `agent_trade_rate_multiplier`, and
`network_p_local` are good candidates for promotion from structural
to live, per the existing engine update path that handles
`norms.update_rate` and `pigouvian.tax_rate`. The change is a per-
tick recompute of the affected agent arrays from the new mean. Other
ten remain structural because they involve population resampling
(certified_fraction draws from Beta), enum changes (network_model),
or scenario-level setup.

### G.3 Phase-G checks

- `test_restart_preview_math.spec.js` — set
  `pigouvian.tax_rate: 0.10 → 0.40`; assert the preview reports an
  α delta matching the alpha_map formula and an EBI delta matching
  the Sobol curve at those α values.
- `test_live_capability_promotion.py` — promote
  `agent_capability_mean` to live; pytest asserts a per-tick update
  shifts the per-agent capability array's mean within 3 ticks.

---

## 9. Phase H — adversarial check harness (0.5 days)

Each phase above ships its own checks. This phase wires them all into
the existing `?dev=1` harness so a single page-load with `?dev=1`
runs every check and surfaces the `‼ dev` badge on any failure.

The harness already exists in `dashboard/sandbox/dev/checks.js` —
extend its dispatch table to include the new checks. No new file
structure needed.

---

## 10. Phase order and elapsed time

Total: ~14 days of dashboard-side work, plus the small engine PR for
G.2. Phase ordering is by repair leverage descending:

| Phase | Days | Unblocks |
|---|---|---|
| A — cold-load fixes | 0.5 | every other phase that reads α-lever or rejection mix |
| B — substrate aggregation | 3 | EBI shape morph reads, regional welfare reads |
| C — cluster diagnostic | 2 | trust in the cluster overlay system |
| D — α-weight completion | 1.5 | trust in the agentic lever panel |
| E — per-agent histogram | 2 | trust in agentic levers' downstream effect |
| F — firm spoke legibility | 1 | cross-sector firm visibility |
| G — structural live preview | 3 | live exploration of agentic axis |
| H — check harness wiring | 0.5 | regression protection for all of the above |

Phases A and B are the high-leverage repair pair: they fix the two
problems that cause the reviewer to mistrust the dashboard wholesale.
Phases C through H can ship independently in any order once A and B
land.

---

## 11. What this plan does not do

- It does not replace the icosphere substrate paradigm with a force-
  directed graph. The original `spatial-sandbox.md` plan called for
  ForceAtlas2; the Pass-13 pivot to a tessellated surface is a
  design choice the project has committed to, and the legibility
  fixes above work within that choice.
- It does not migrate the K=12 hard sector enum to a dynamic
  registry. Emergent labels (cabals, syndicates) remain dashboard
  observations of engine output, per
  `emergent_clustering.md §"What this means for the engine"`.
- It does not add ambient audio (`spatial-sandbox.md §11 Week 4`).
  Audio remains a polish item, downstream of the visual fixes here.
- It does not add the hyperbolic network model option (deferred per
  `spatial-sandbox.md §13`).
- It does not change the engine's `step.alpha` from a static config
  knob to an endogenous per-tick computation. The α-as-outcome story
  remains a dashboard-side mapping; the α-gap row continues to be
  the honest disclosure of that separation.

---

## 12. Open risks

- **B.1 regional overlay competes with sector hover-outline.** Both
  paint the substrate's 12 sector regions; the welfare overlay
  could mask the hover boundary. Mitigation: regional welfare uses
  fill alpha at most 0.30; sector hover uses an in-shader edge
  highlight that survives the fill.
- **D.1 hand-pinned weights produce monotonicity violations under
  the existing `checkMonotonicity()`.** Mitigation: every weight is
  positive, signs come straight from the research-doc tables, and
  the existing check catches inversions before merge.
- **G.1 EBI estimate misleads when the Sobol curve interpolation
  fails.** Mitigation: bound the preview to the Sobol design's
  observed α range and show "out of range" instead of an estimate
  when the user drives levers past the corners the sweep covered.
