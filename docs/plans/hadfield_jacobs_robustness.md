# Hadfield / Jacobs Critique Response — Engine Hardening Plan

Status: drafted 2026-05-11. Doc-first sweep (W3) lands with this commit;
code workstreams (W1, W2) staged behind feature flags so the canonical
N=2048 Sobol pin stays bit-identical until each lever is opted in.

---

## What this addresses

A targeted critique from Marek (2026-05) flagged eight defensibility
gaps relative to two reading communities the artifact will run into:
Tomašev / Jacobs (DeepMind, *Virtual Agent Economies*, arXiv:2509.10147)
and Hadfield (regulatory markets; normative infrastructure; Legal
Infrastructure for Transformative AI Governance, arXiv:2602.01474).

The gaps are conceptual, not numerical. The engine already pins at
N=2048 Sobol, runs t-copula noise and Hawkes folding, and ships the
validation lift (A1 historical anchor, A2 wide-prior sweep, A3
adversarial counter-example). What it does not do is parameterize what
it implicitly assumes.

## What robustness means here

A reviewer in the Hadfield / Jacobs orbit can read the artifact and
agree that:

- Krier's middle layer is not Hadfield's regulatory market, and the
  artifact says so.
- `align_reject` is a static-distance proxy for norm-participation,
  and the artifact says so.
- Permeability is an orthogonal axis to smooth / striated, and the
  artifact either runs it or names that it doesn't.
- Persistent agent identity is absent from the model, and the artifact
  names this as a conditioning assumption.

The plan delivers a doc-first pass that surfaces every one of those
admissions, then a code pass that implements the levers behind feature
flags so the canonical pre-2026-05 scenario behavior is preserved
bit-for-bit when the flags are off.

---

## Three workstreams

### W1 — endogenize the Matryoshka filters

Targets tier-1 issues 2 and 3, tier-2 issue 5.

#### W1a. Split the middle layer into `platform_reject` and `regulator_reject`

`engine/core/transactions.py:305` currently bundles deployer policy and
regulatory filter into one formula:

```
market_reject = ~U(0,1) < 0.02 + 0.06·(1 − sec_aff) + 0.04·|Δalign|
```

Split into two filters that a transaction must both pass:

- `platform_reject` — keep the current formula. This is Krier's middle
  layer: foundation-model deployer and platform policy.
- `regulator_reject` — Hadfield-style government-licensed third-party
  regulator. Parameterized by `regulator_strength`, `regulator_capture`,
  `regulator_audit_quality` per stack. Each stack draws a regulator
  vendor from a pool; vendors compete on a quality / strictness
  frontier the operator sets.

Each filter contributes a separate surplus tax channel parallel to the
existing `market_layer_tax`. New `RegulatorConfig` on `TopologyConfig`,
off by default.

#### W1b. Replace static-distance `align_reject` with norm-participation

Largest single change in the plan; carries the most epistemic load.
`align_reject` is ~50% of Smoothworld rejection share per
`docs/concepts/matryoshkan_alignment.md:71`. If it is the binding
constraint, the binding constraint cannot be a Euclidean distance on a
fixed scalar.

Direction: each agent carries `norm_vector: np.ndarray` shape `(N, K)`
sparse. The vector evolves toward the local distribution it transacts
with, weighted by capability and successful-execution frequency.
`align_reject` becomes distance in norm-space, recomputed each step.

New module `engine/core/norms.py`. New fields in
`engine/core/population.py`. Flagged off by default behind
`NormsConfig.enabled`.

New scenarios: `norms_drift` (slow convergence), `norms_capture` (one
cluster absorbs the rest), `norms_brittle` (high update rate produces
alignment whiplash).

#### W1c. `permeability` as a first-class topology parameter

`engine/core/topology.py` currently collapses two Tomašev / Jacobs-
distinct ideas into `cross_stack_compat`: (i) whether a cross-stack
trade can be attempted at all (impermeable → permeable), (ii)
institutional fit once attempted. Split:

- `cross_stack_compat` stays as institutional-fit, used in the law
  gate at `engine/core/transactions.py:278`.
- New `cross_stack_permeability ∈ [0, 1]` gates whether the trade is
  *attempted*, applied before the Matryoshka cascade. Permeability 0 →
  sandboxed stacks; permeability 1 → current behavior.

New scenarios `agent_economy_sandbox` (low permeability) and
`permeable_default` (current). Smallest code change in W1; lands first.

### W2 — add the missing objects

Targets tier-1 issue 4, tier-2 issues 6 and 7.

#### W2a. Persistent agent identity + registration tax

`engine/core/population.py` gets `agent_id: np.int64` stable across
steps and a `registered: np.ndarray[bool]` mask. New
`RegistrationConfig`:

- per-step `registration_cost` charged against wealth for registered
  agents,
- `registration_floor`: unregistered agents face an additional
  rejection probability at the regulator layer (couples to W1a).

This is what makes the registration regime do work in the model.
Hadfield's Feb-2026 paper treats this as the precondition for
everything else.

Scenarios: `registration_strict`, `registration_lax`,
`registration_collapse` (capture eats registration → audit trails
forge → regulator quality drops endogenously).

#### W2b. `mission_economy` scenario

`engine/scenarios/__init__.py` gets one new scenario plus two
adversarial siblings.

Smallest credible implementation:

- `MissionConfig` biases firm formation in
  `engine/core/institutions.py:formation_step` toward coordinator-
  tagged sectors,
- a `mission_levy` routes a fraction of cleared surplus to a public-
  objective pool that funds capability uplift in those sectors.

Siblings `mission_captured` and `mission_competing` make the point
that the mission lever isn't free. Without a Tomašev-style entry the
artifact reads as "every path leads to one of two attractors," which
is the conclusion that paper is warning against.

#### W2c. Explicit human-side labor market

Currently humans and agents are both prototypes in `Population` with
`is_human` flagging which weights apply. There is no explicit price-
on-human-labor or substitution closure that addresses Jacobs's labor-
displacement work.

Smallest credible add: a per-sector `labor_share` parameter splits
surplus between agent operators and human labourers, with substitution
elasticity driven by the automation gap that already exists for the
Pigouvian tax. Outputs add a human-only Gini and human-only welfare/
capita series separated from agent-side aggregates.

The exo-engine drag stays the legibility-token channel; the α-engine
transaction surplus becomes the substitution channel. No new
mechanism — just factor the human-side accounting out of the agent-
side.

### W3 — documentation deltas

Targets tier-1 issue 1 and cross-cutting epistemic-status hardening.

- **W3a. `docs/bibliography.md`** — add a "Regulatory infrastructure"
  section with the three Hadfield pieces. Cross-list Tomašev / Jacobs
  into a new "Sandbox economies" subsection.
- **W3b. `docs/concepts/matryoshkan_alignment.md`** — add a "What this
  model is not" section naming the Krier-vs-Hadfield conflation, the
  static-distance `align_reject` misspecification, and the absence of
  persistent agent identity. Retire the stale "law layer is v2"
  caveat (the dynamic-law mechanism is in code).
- **W3c. `docs/concepts/coasean_bargaining.md`** — one paragraph on
  normative competence as a prerequisite for durable Coasean
  clearance. Citing Hadfield's May-2025 piece. Lands after W1b so the
  prose can point at the implementation.
- **W3d. `docs/concepts/smooth_striated.md`** — paragraph naming
  permeability as the orthogonal axis Tomašev / Jacobs formalize.
- **W3e. `docs/concepts/registration.md`** — new file. Stub for the
  Hadfield registration regime. Names what is not modeled even after
  W2a: audit-trail tampering, identity laundering through firm
  formation, multi-jurisdiction registration arbitrage.
- **W3f. `docs/concepts/epistemic_status.md`** — promote three
  conditioning assumptions: implicit permeability = 1 in canonical
  scenarios, persistent agent identity is absent, `align_reject` is
  static-distance.

---

## Sequencing

| # | Workstream | Status | Reason for position |
| --- | --- | --- | --- |
| 1 | W3a, W3b, W3d, W3e, W3f | **landed** | Doc-first sweep, half a day. Surfaces the most visible omissions before code lands. |
| 2 | W1c permeability | **landed** | One scalar on `TopologyConfig`, threads cleanly through the existing topology. |
| 3 | W1a regulator split | **landed** | Adds `RegulatorConfig`, flagged. Canonical pins stay green. |
| 4 | W2a registration | **landed** | Couples to W1a (rejection floor depends on regulator layer). |
| 5 | W2b mission economy | **landed** | Single scenario, uses existing levers, low risk. |
| 6 | W2c labor accounting | **landed** | Output separation only, no new mechanism. |
| 7 | W1b norm-participation | **landed** | Largest change. Behind a flag. The conceptual centerpiece for the Hadfield critique. Lands last so it can be swept against the existing baseline. |
| 8 | W3c coasean prose | **landed** | After W1b. The prose claim needs the implementation to point at. |

## Validation lift

Each new flag gets a pin test on the `engine/tests/test_validation_*.py`
pattern. The canonical N=2048 Sobol stays bit-identical with all new
flags off.

Two new artifacts:

- `outputs/validation/permeability_sweep.json` — basin distribution
  under wide prior, with permeability swept independently of α.
- `outputs/validation/norms_sensitivity.json` — how much of the
  Smoothworld rejection share moves when norm-participation replaces
  static distance.

## What this plan fixes and does not fix

Fixes tier-1 (1, 2, 3, 4) and tier-2 (5, 6, 7) directly. Does not
address tier-3 (DeepMind scoop risk) by itself. The shape of the plan
doubles down on the parts of the engine least likely to be replicated
in-house: the exo-engine, productive folding at depth, the smooth /
striated classifier, and now the norm-participation alignment layer.
Any subsequent in-house Coasean simulator becomes the second in the
field on the parts where the originality lives.
