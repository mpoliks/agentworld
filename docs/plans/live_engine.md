# Live engine — exploratory parameter terminal

Status: drafted 2026-05-12. Branch: `live-engine`. Scopes the work to turn
`dashboard/live.html` from a scenario-picker viewer into a parameter
terminal that lets a user tune the Sobol-ranked controls, run an ensemble,
and watch step-resolved metrics + foldtree animation update in real time.

## Companion docs

- `docs/concepts/live_parameters.md` — the eleven exposed controls, their
  bounds, definitions, gloss strings, and the five scenario families. The
  V1 UI imports its labels and tooltips from this doc; the doc is the
  single source of truth.
- `docs/concepts/smooth_striated.md`, `docs/concepts/fractal_folding.md`,
  `docs/concepts/demand_and_intermediation.md` — physics that the live
  parameters control. Not duplicated here.

## Principles (agreed before the plan was drafted)

1. **Live mode is the exploratory sibling, not a replacement for the
   canonical scenarios.** The 33 scenarios and the pinned N=2048 Sobol
   surface remain the publication anchor. The live engine is for
   what-if exploration.
2. **Scenario families are chosen before the run, not toggled mid-run.**
   Structural switches (demand feedback, productive-folding split, law,
   Pigouvian, emergent strategy) change which equations the engine
   evaluates. The UI presents them as a five-option radio at the top of
   the parameter panel.
3. **Sobol bounds become the slider bounds by default.** The S1/ST
   indices the UI displays are valid only inside the sampling box.
   Extending the bounds is an Advanced-drawer option that strips the
   sensitivity anchor.
4. **Tier ST mass first, long tail later.** Eight numeric controls plus
   the α(t) schedule editor and the family selector cover the V1
   surface. Seven Tier-3 parameters live behind an Advanced drawer that
   is not part of V1.

## Current state of the streaming spine

The B-stream work in `_archive/validation_lift_plus_live_viz.plan.md`
already shipped most of the transport:

| Piece | File | Lines | State |
| --- | --- | --- | --- |
| FastAPI + SSE server | `engine/serve.py` | 374 | runs, one at a time, scenario-by-name |
| `World.run(step_callback=...)` | `engine/core/world.py` | 865 | per-step callback contract is wired |
| Live page shell | `dashboard/live.html` | 479 | scenario dropdown + Plotly charts + event log |
| Foldtree renderer | `dashboard/foldtree.js` | 153 | static; the live tab is a B4 placeholder |
| Ensemble runner | `engine/ensemble.py` | 302 | parallel seeds, median + bands, **batch only** |

The plumbing exists. The work in this plan is the *parameter surface* on
top of it, plus the ensemble streaming and foldtree animation that the
existing components imply but do not yet provide.

---

## V1 — Parameter terminal (S1 → S3)

The minimum useful slice. After V1 a user can pick a scenario family,
adjust the eight Sobol-ranked controls and (optionally) an α schedule,
hit Run, and watch a single seed stream. Comparison and ensembles are
deferred to V2.

### S1 — Config-patch endpoint in `serve.py`

**Why.** The current `POST /runs` takes a scenario name. There is no way
to send a parameter override. The simplest extension is an optional
`overrides: dict` field that the server applies to the `WorldConfig`
after the scenario factory builds it.

**What to do.**

1. Extend `RunRequest` (`engine/serve.py` ~line 200) to accept:
   ```python
   class RunRequest(BaseModel):
       scenario: str             # still the base scenario name
       family: Optional[str]     # one of the five families; validated against scenario
       overrides: dict = {}      # flat key → value patch on WorldConfig + TopologyConfig + PopulationConfig
       alpha_schedule: Optional[list[float]] = None  # piecewise-linear control points, len ≤ n_steps
       n_steps: int = 60
       scale: str = "small"
       seed: int = 0
   ```
2. Add `engine/serve.py::_apply_overrides(cfg: WorldConfig, overrides: dict)`
   that walks the override dict and writes into the right sub-config
   (`cfg.topology`, `cfg.population`, etc.). Reject unknown keys with a
   400. Reject values outside the Sobol bounds *unless* an
   `extend_bounds` flag is set (advanced mode).
3. Add `GET /scenarios/families` returning the taxonomy in
   `live_parameters.md`. Used by the UI to populate the family radio
   and to validate that the picked scenario lives inside the picked
   family.
4. Add `GET /sobol_indices?metric=log_exo_baroque_index` returning the
   S1, ST, S1_conf, ST_conf vectors for the requested metric, parsed
   from `outputs/sensitivity/sobol_indices.n2048.json`. Cache in process
   memory.
5. Add `GET /parameter_meta` returning the eleven exposed parameters
   with their labels, tooltips, helps, defaults, bounds — all parsed
   from `docs/concepts/live_parameters.md` at startup. (Parsing the
   markdown means the doc and the UI never drift.)

**Success criteria.**
- `curl -X POST /runs -d '{"scenario":"coasean_paradise","overrides":{"alpha":0.7,"folding_propensity":0.3}}'`
  starts a run with the patched config and the SSE stream returns
  StepMetrics matching the patch.
- New unit test `engine/tests/test_serve_overrides.py` covers: valid
  patch, out-of-bounds rejection, unknown-key rejection, family
  validation.

**Files touched.**
`engine/serve.py`, `engine/tests/test_serve_overrides.py` (new).

### S2 — Parameter terminal in `live.html`

**Why.** The scenario dropdown is a single point of variation. V1
replaces it with a structured panel: family radio, eight slider rows
with S1/ST badges, productive-folding toggle, headline-metric selector,
scenario preset row (demoted but still useful).

**What to do.**

1. Fetch on page load: `/scenarios/families`, `/parameter_meta`,
   `/sobol_indices?metric=log_exo_baroque_index`. Store in module-scope
   constants.
2. New top section in `dashboard/live.html` (replacing the current
   `.controls` block ~line 147):
   - **Family radio** (5 options). Selecting a family filters the
     scenario preset dropdown to scenarios inside that family.
   - **Scenario preset** dropdown — clicking a preset loads its values
     into the sliders. Becomes a "starting point" rather than the
     primary control.
   - **Headline metric selector** (one of the six Sobol metrics). When
     changed, every slider row updates its S1/ST badge.
   - **Eight slider rows**, each:
     ```
     ┌────────────────────────────────────────────────┐
     │ Smooth ↔ baroque (α)     [ — slider — ]  0.50 │
     │ Krier–Bratton axis. 0 = no folding…           │
     │ S1 0.48 · ST 0.71                             │
     └────────────────────────────────────────────────┘
     ```
     Hover shows the tooltip; clicking the row name expands the
     help drawer.
   - **Productive-folding toggle.** When off, `base_variance_absorption`
     is forced to 0 and `max_productive_real_share` greys out.
   - **Family-specific knobs** section — renders only when the selected
     family has extra parameters (e.g., `law.decay_rate` for Dynamic
     law, `pigouvian.tau` for Pigouvian automation). Defer the gloss
     text for these to V2; show raw field names in V1.
3. Submit button assembles `{scenario, family, overrides, n_steps,
   scale, seed}` and POSTs to `/runs`. The SSE flow downstream is
   unchanged.
4. About-the-bounds expander next to the metric selector: one-line
   text quoting `live_parameters.md` § "About the bounds." Avoids
   repeating the caveat eight times.

**Success criteria.**
- A user can land on the page, leave everything at defaults (Family =
  Alpha-engine baseline, scenario = `equilibrium_drift`), drag α to
  0.8, hit Run, and see step metrics stream that reflect the higher
  alpha (visibly larger EBI growth).
- The S1/ST badges change when the metric selector switches between
  `log_exo_baroque_index`, `real_per_capita_welfare`, etc.
- The productive-folding toggle correctly greys out
  `max_productive_real_share` when `base_variance_absorption = 0`.

**Files touched.**
`dashboard/live.html`, `dashboard/_tokens.css` (minor — new row layout
tokens), `dashboard/live_parameters.js` (new — parameter rendering
module, ~200 lines).

### S3 — α(t) schedule editor

**Why.** α has the highest ST in the Sobol surface and three canonical
scenarios (`smoothing_cascade`, `fold_avalanche`, `recursive_simulation`)
depend on it being time-varying. A flat slider cannot represent them.

**What to do.**

1. Add a "Schedule α(t)" toggle next to the α slider row. When toggled
   on, the slider collapses and an editor expands below it.
2. The editor is an SVG `<g>` with up to four draggable control
   points, x ∈ [0, n_steps], y ∈ [0.05, 0.95]. Linear interpolation
   between points. Default schedule on first open: flat at the current
   slider value.
3. On Run, if the schedule is active, emit
   `alpha_schedule = [a(t) for t in range(n_steps)]` (length-n_steps,
   piecewise-linear interpolation). The server already consumes
   `WorldConfig.alpha_schedule` via `engine/core/world.py:442`.
4. Display the active schedule as a faint line over the α subplot in
   the live chart panel so the user can see the schedule next to the
   realised α each step.

**Success criteria.**
- Drawing a ramp from α=0.1 at step 0 to α=0.9 at step 60 reproduces
  `fold_avalanche`'s trajectory shape (visible cumulative EBI
  acceleration in the back half).
- Switching back to constant mode preserves the slider value.

**Files touched.**
`dashboard/live_parameters.js`, `dashboard/live.html` (small).

### V1 acceptance

- Loads at `/live` in under 1 s on the default scale (small, 88K
  prototypes).
- A run with 8 slider overrides + α schedule + family selector hits
  step 1 within 500 ms of clicking Run on a M-series Mac.
- All current `live.html` features (scenario presets, scale, n_steps,
  seed, event log, single-seed charts, scenario description) still
  work — V1 is additive, not a rewrite.
- `engine/tests/` test count climbs by at least 4 (override
  application + family validation + bounds check + alpha_schedule
  round-trip).
- `docs/concepts/live_parameters.md` and the rendered UI agree
  field-for-field. Acceptance is a manual cross-check, not automated.

---

## V2 — Visual instrument (S4 → S5)

After V1 the UI is correct but austere. V2 turns it into the instrument
the user actually wanted: ensemble bands instead of single seeds, live
foldtree animation instead of a static placeholder.

### S4 — Streaming ensemble (32 seeds, p5/p95 bands)

**Why.** Single stochastic trajectories mislead. The existing
`engine/ensemble.py` already runs N seeds in parallel and produces
median + p5/p95 bands, but only as a batch Parquet write at the end.
For live mode the bands need to update per step.

**What to do.**

1. Refactor `engine/ensemble.py` to expose a generator API:
   ```python
   def stream_ensemble(
       scenario_cfg: WorldConfig,
       n_seeds: int = 32,
       scale: Scale = Scale.SMALL,
   ) -> Iterator[EnsembleStepFrame]:
       ...
   ```
   Internally: spawn N processes, each running a `World` with a
   `step_callback` that pushes to a `multiprocessing.Queue`. The
   parent drains the queue, gathers all N step-K frames, and yields
   one `EnsembleStepFrame` (median + p5 + p95 across the N seeds) per
   simulated step. Backpressure: if the parent falls behind, the
   queues bound the workers to step k+2 max.
2. New `POST /runs/ensemble` and `GET /runs/{id}/ensemble_stream`
   endpoints. Same config-patch payload as S1.
3. UI ensemble-mode toggle. When on, every chart renders a band
   instead of a single line.
4. Per-step CPU/wall budget logged. The N=32 × T=60 × small-scale run
   should complete in ~6 s on a M4 Pro. If it does not, fall back to
   N=16 with a UI banner.

**Success criteria.**
- `coasean_paradise` ensemble with N=32 produces visibly tighter EBI
  bands than `recursive_simulation` (which exhibits cascade variance).
- Cancelling a run via the existing `DELETE /runs/{id}` reaps all
  worker processes within 200 ms.

**Files touched.**
`engine/ensemble.py`, `engine/serve.py`, `dashboard/live.html`,
`engine/tests/test_ensemble_stream.py` (new).

### S5 — Live foldtree

**Why.** `dashboard/foldtree.js` currently renders a static tree. The
brief's central image — fractal folding as the engine's distinctive
behaviour — is invisible in the live UI. V2 animates the tree per
streamed frame.

**What to do.**

1. Extend the per-step SSE payload to include a `foldtree_delta`
   record: nodes added this step, accumulated fold count per existing
   node, total transaction volume on each edge this step. The data is
   already in `World.ledger`; the work is shaping it for the wire.
2. `foldtree.js` consumes the delta:
   - New nodes fade in over 200 ms.
   - Node colour interpolates from `--text-3` (cool) to `--accent`
     (hot) as accumulated fold count climbs.
   - Edge thickness interpolates with transaction volume on a log
     scale.
3. Camera anchored to the active fold frontier — nodes spawned in the
   last 5 steps stay on-screen; older nodes drift to the periphery.
4. Hover on a node shows: depth, accumulated folds, last-touched step,
   parent node id.

**Success criteria.**
- A `baroque_cathedral` run shows visible recursive folding building
  in the back half of the run.
- A `coasean_paradise` run produces a near-flat tree of depth 0-1.
- 60 fps on M-series Macs at default scale.

**Files touched.**
`dashboard/foldtree.js`, `engine/serve.py` (delta packing),
`engine/core/world.py` (delta extraction helper).

---

## V3 — Comparison and replay (S6 → S7)

After V2 the user can explore. V3 lets them remember.

### S6 — Pin and diff

**Why.** "I just changed τ from 0.04 to 0.12, what did that actually
do?" is a question the V1/V2 UI cannot answer without re-running both
configs by hand.

**What to do.**

1. **Pin a run.** A button on a completed run snapshots its full
   config + per-step trace to `outputs/live_pins/{run_id}.json`.
2. **Fork.** A button on a pinned run loads its config into the active
   sliders. The user adjusts and runs.
3. **Overlay.** When a pinned run is active and a new run completes,
   both trajectories render on every chart (pinned in grey, new in
   `--accent`). EBI delta strip across the top of the chart panel
   shows step-by-step metric difference.
4. Pinned-run library page at `/pins` — a list of stored configs with
   thumbnail traces.

**Files touched.**
`engine/serve.py`, `dashboard/live.html`, `dashboard/pins.html` (new).

### S7 — Replay and rewind

**Why.** Once the user finds an interesting step (e.g., the EBI
inflection point in a productive-baroque run), they want to rewind and
fork from there with different parameters.

**What to do.**

1. Snapshot the `World` state every K steps (default K=10) into an
   in-process LRU. `World.snapshot()` and `World.restore(snap)` go on
   `engine/core/world.py`.
2. UI scrub bar across the bottom of the chart strip; clicking a step
   loads the nearest snapshot, restores the World, and re-streams from
   there.
3. Fork-from-here button: snapshot the current step, exit live mode,
   load the snapshot's config into the sliders, run with new
   overrides.

**Files touched.**
`engine/core/world.py`, `engine/serve.py`, `dashboard/live.html`.

---

## Out of scope (named so we remember)

- **Multi-user.** Server is `localhost:8765` only; one run at a time.
- **Auth / hosted demo.** Live mode is a local dev tool. Hosting the
  static dashboard is a separate question.
- **Tier-3 parameter exposure.** Seven low-ST parameters
  (`a2a_floor`, `coase_exp`, `cap_slope`, `cross_stack_compat`,
  `productive_decay`, `market_layer_tax`, `fold_real_efficiency`)
  remain behind the Advanced drawer in V1+V2+V3.
- **Mid-run parameter changes.** Sliders are read at Run time. Mid-run
  parameter editing is a different design problem and not in scope.
- **Calibration mode.** The live engine produces no claims that will
  appear in a paper. The canonical scenarios and Sobol surface remain
  the publication anchor.

## Sequencing and effort estimate

| Stage | Estimate | Depends on |
| --- | --- | --- |
| S1 — Config-patch endpoint | 1 day | `live_parameters.md` (✓) |
| S2 — Parameter terminal UI | 2 days | S1 |
| S3 — α(t) schedule editor | 1 day | S2 |
| **V1 ship** | **4 days** | — |
| S4 — Streaming ensemble | 2 days | S1 |
| S5 — Live foldtree | 2 days | S1 + ledger delta |
| **V2 ship** | **+4 days** | — |
| S6 — Pin & diff | 1.5 days | S2 |
| S7 — Replay & rewind | 2 days | World snapshot work |
| **V3 ship** | **+3.5 days** | — |

V1 is the "large chunk" requested. V2 and V3 are scoped here so the
plan does not need re-drafting between phases.

## Risks and decisions deferred

1. **Markdown parsing for `parameter_meta`.** Parsing
   `live_parameters.md` server-side keeps the UI and the doc in sync,
   but the parser becomes its own thing to maintain. Fallback: hand-
   maintained JSON in `engine/data/parameter_meta.json`, with a CI
   check that compares it to the doc. Decision deferred to S1
   implementation start.
2. **Family-specific knobs gloss.** V1 ships raw field names for
   law/Pigouvian/strategy/population-dynamics. A second gloss pass
   over those parameters is V2-tier scope. Decision: defer until V1
   feedback comes in; the family knobs may not need full gloss
   treatment if usage stays advanced.
3. **Ensemble compute budget.** N=32 × T=60 × small scale is the
   target. If wall-clock exceeds 10 s on the reference machine, V2
   ships with N=16 default and N=32 as opt-in. Measured in S4.
