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

## V2 — Live exchange surface (S4 → S6)

V1 surfaces aggregates; V2 surfaces the per-pair activity that
produces them. The user's framing: "I want to see the actual
exchanges, not just the graphs." Three views over the same substrate:

| View | Reads like | What it answers |
| --- | --- | --- |
| **Trade tape** | A Bloomberg ticker | What did this specific trade do? |
| **Living grid** | A trading floor | Are the agents *doing things* right now? |
| **Sector chord** | A flow diagram | Who is trading with whom at the sector level? |

All three read from one new SSE channel — `step.pairs` — and the
engine work is shared. The original V2 (streaming ensembles + live
foldtree) is bumped to V2.5; per-pair visibility is a higher
priority than statistical bands or fold-cascade animation.

### S4 — Pair-sample substrate

**Why.** The engine processes ~200K pairs per step but only emits
aggregates. To show pairs the user needs a per-pair sample stream.
`coasean_step` already has every per-pair quantity in scope at the
return site; the work is sampling K of them and packaging records.

**What to do.**

1. New dataclass `PairSample` in `engine/core/transactions.py`:
   ```python
   @dataclass
   class PairSample:
       proto_a: int           # prototype index
       proto_b: int
       is_a_human: bool
       is_b_human: bool
       sec_a: int             # 0..N_SECTORS-1 (12 macro-sectors)
       sec_b: int
       cap_a: float
       cap_b: float
       base_surplus: float    # pre-tax surplus
       friction: float        # cost per pair
       real_surplus: float    # realized real welfare delta
       executed: bool
       reject_reason: str     # "" | "law" | "market" | "align" | "cost" | "permeability" | "regulator"
       pair_weight: float     # pair_real_count — number of real pairs this prototype-pair stands in for
   ```
2. Add `pair_sample_k: int = 0` to `coasean_step` parameters. When
   `> 0`, sample K uniform-random pair indices (using a deterministic
   sampling rng — see RNG-isolation note below) and emit
   `PairSample` records. Default 0 keeps the canonical scenarios
   bit-identical.
3. Add `pair_sample_k: int = 0` to `WorldConfig`. World.step passes
   it through to coasean_step alongside the sampling rng. Records
   land in `StepMetrics.pair_samples: list[PairSample] = []`.
4. **RNG isolation.** Adding a new subsystem to `_RNG_SUBSYSTEMS`
   would shift every per-component child stream and break the
   pinned N=2048 Sobol output. So the sampling rng lives outside
   the registry — `World._pair_sample_rng = default_rng(seed ^
   0xC0DEC0DE)` — deterministic per seed, isolated from every other
   stream.

**Tests.** New `engine/tests/test_pair_sampling.py`:
- K=0 yields zero records and consumes no extra RNG draws (pinned
  output bit-identical against a recorded fixture).
- K=50 yields 50 distinct records with the expected schema.
- Sampled pair fields agree with the per-pair arrays at their
  indices (proto_a, proto_b, sec_a, etc.).
- Reject-reason precedence is deterministic when multiple masks fire
  (law > market > align > cost > permeability > regulator).

**Files touched.**
`engine/core/transactions.py`, `engine/core/world.py`,
`engine/core/metrics.py` (StepMetrics field), `engine/tests/
test_pair_sampling.py` (new).

### S5 — Trade tape + Living grid (UI)

**Why.** Two views, one engine event. The tape is the literal answer
("show me each exchange"); the grid is the visceral one ("agents are
busy right now").

**Trade tape.**

- New `<div id="trade-tape">` panel in `live.html`, behind a "Tape"
  tab alongside Charts and Fold tree.
- One DOM row per `PairSample`, latest-first, capped to last 200.
- Row layout (monospace): `step.idx | type | sec_a→sec_b | s=base ƒ=friction | result`
  where `type` is one of `H↔H`, `H↔A`, `A↔A`, and `result` is either
  `+real_surplus` for executed or the reject_reason for rejected.
- Filter chips above the tape: pair-type filter, executed-only,
  rejected-only.
- Click a pair-type chip or a row → grid (S5b) filters to that
  prototype.

**Living grid.**

- Fixed-size SVG (or canvas for performance) showing N_PROTOS dots
  arranged in a 60×40 grid (the actual prototype count varies by
  scale; we project onto a grid of slots).
- Per step, the K sampled pairs flash:
  - Each participant dot pulses (radius up briefly, fades back).
  - A short edge segment between the two dots draws and fades.
  - Colour by pair type: `--green` for H↔H, `--accent` for H↔A,
    `--blue` for A↔A.
- Hover a dot shows prototype index, sector, recent activity count.
- Click a dot → tape filters to that prototype.
- Canvas fallback if perf at K=200 × 60Hz drops below 50 fps.

**Files touched.**
`dashboard/live.html` (tape tab + grid tab), `dashboard/live_pairs.js`
(new — renders tape + grid from `step.pairs` events),
`engine/serve.py` (forward `pair_samples` in step SSE).

### S6 — Sector chord (UI)

**Why.** The third view answers a different question — not "what is
this trade?" or "who's busy?" but "which sectors couple?". A chord
diagram around a circle, sectors as arcs, inter-sector volume as
ribbons that pulse per step.

**What to do.**

- D3 `d3.chord()` layout over the 12 sectors
  (`engine/core/population.py` N_SECTORS).
- Per step, accumulate sample-derived per-sector-pair volume into a
  12×12 matrix; redraw the chord with that matrix; ribbons fade
  briefly on update.
- Toggle between **per-step** (instantaneous pulse) and **cumulative**
  (running total over the run) modes.
- Hover a ribbon shows `sec_a × sec_b` pair, volume, executed share.

**Files touched.**
`dashboard/live.html` (chord tab), `dashboard/live_sector_chord.js`
(new). No engine change beyond S4 — the sample stream is enough.

### V2 acceptance

- A run with `pair_sample_k = 200`, `n_steps = 60`, scale `small`
  emits 12,000 pair records over the SSE stream in roughly the same
  wall-clock as the V1 run (overhead < 5%).
- The Tape tab shows live rows that scroll faster on high-α runs.
- The Grid tab shows visible activity hotspots in a high-stack run
  (e.g. `hemispherical_schism`).
- The Chord tab shows sector decoupling under cross-stack-low-compat
  scenarios.
- Pinned canonical scenarios (`outputs/runs/*.json`) stay
  bit-identical under `pair_sample_k = 0`.

## V2.5 — Statistical bands + foldtree animation (deferred from V2)

Streaming ensemble (32 seeds, p5/p95 bands) and live foldtree
animation remain in the plan but at lower priority than V2 above.
Spec preserved verbatim in `docs/plans/_archive/v2_ensemble_foldtree_deferred.md`
when the V2 work ships.

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
