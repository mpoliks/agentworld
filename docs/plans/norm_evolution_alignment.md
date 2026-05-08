# Norm-evolution layer for individual-layer rejection

Status: `engine/core/transactions.py:312-314` computes the per-trade alignment-layer rejection as

```python
align_reject = rng.random(n_pairs) < (
    0.03 + 0.20 * align_dist * (1.0 - 0.5 * (auto_a + auto_b) / 2.0)
)
```

where `align_dist = abs(al_a - al_b)`. The binding constraint is therefore Euclidean distance between two static alignment vectors at the moment of trade. `docs/concepts/matryoshkan_alignment.md` (around line 71) reports the individual layer carries roughly half the rejection share in Smoothworld scenarios. Hadfield's normative-infrastructure argument (AIhub interview, May 2025; Jurimetrics, Winter 2026) is that alignment is participation in evolving community norms, not preference-matching at fixed pairwise distance. If she is right, the binding constraint is misspecified, and every Smoothworld result inherits the bug.

This plan replaces `align_dist` in the rejection formula with a deviation-from-current-norm quantity. The norm is a population-tracked field that updates from observed accepted and rejected trades. At update rate `eta = 0`, the new code reproduces the current static behavior bit-for-bit.

This plan stands alone. Read these inputs only:

- `engine/core/transactions.py` (the rejection-gate block, currently lines 295–330)
- `engine/core/population.py` (the `Population` dataclass)
- `engine/core/world.py` (the step function and where audit/metrics are emitted)
- `engine/core/metrics.py` (where rejection-share metrics are reported)
- `docs/concepts/matryoshkan_alignment.md` (the existing prose to be amended)
- `docs/concepts/coasean_bargaining.md` (paragraph cite)

## Dependencies

- Plan 1 (per-component RNG split) — preferred. Norm updates draw from `rngs["alignment"]`.
- Plan 2 (registration regime) — required. Norm evolution is meaningful only over registered prototypes (anonymous draws don't carry observation history; their observed-trade summary is just the population mean).

## Why

Static-distance alignment rejection has two failure modes:

1. **Translation invariance.** If every agent's alignment shifts by the same amount, `align_dist` is unchanged, but in the norms-as-evolving view the entire population moved relative to the (now stale) external norm — every trade should suddenly fail. Static distance has no opinion.
2. **No memory.** A trade that was accepted yesterday and is identical today returns the same accept probability today. There is no learning surface for the alignment layer; it is purely a function of two scalars.

Norm evolution makes both go away. The community norm is a single scalar per population (or per stack, if we want stratification); each step it nudges toward the alignment-weighted mean of recently *executed* trades. Rejection is then computed as deviation-from-norm, which (a) is not translation invariant and (b) carries history.

This is the cheap version of Hadfield's normative-competence claim. It does not lift alignment to a vector or implement deliberation — that is v2. It just turns "static distance" into "tracked moving target".

## What to do

### Task 1 — Add `NormConfig` and a community-norm field

In `engine/core/population.py`:

```python
@dataclass
class NormConfig:
    enabled: bool = False                 # when False, current static behavior
    norm_update_eta: float = 0.05         # rate of norm update toward observed mean
    norm_lag_steps: int = 4               # observation window before norm reacts
    initial_norm: float = 0.0             # alignment-space anchor
    stratify_by_stack: bool = False       # per-stack norms instead of one global

@dataclass
class PopulationConfig:
    ...
    norm: NormConfig = field(default_factory=NormConfig)
```

On `Population`, add:

```python
community_norm: np.ndarray   # shape (K,) when stratified, else (1,); float32
norm_observation_buffer: np.ndarray  # rolling, shape (norm_lag_steps, K)
```

Initialise both to `cfg.norm.initial_norm` in `Population.synthesize`.

### Task 2 — Update community norm each step

In `engine/core/world.py` step function, after transactions execute:

```python
if pop.cfg.norm.enabled:
    # Observation: alignment-weighted mean of executed trades, per stack if
    # stratified else global. Use registered prototypes only — anonymous
    # draws don't have continuity to contribute.
    obs = _compute_executed_alignment_mean(pop, executed_mask, ...)
    pop.norm_observation_buffer = np.roll(pop.norm_observation_buffer, -1, axis=0)
    pop.norm_observation_buffer[-1] = obs
    target = pop.norm_observation_buffer.mean(axis=0)  # lag-window mean
    pop.community_norm += pop.cfg.norm.norm_update_eta * (target - pop.community_norm)
```

The lag-window mean prevents a single noisy step from dragging the norm. `norm_lag_steps=1` recovers immediate updating; default 4 gives ~4-step memory.

### Task 3 — Replace `align_dist` in the rejection formula

In `engine/core/transactions.py`, replace the existing block:

```python
if pop.cfg.norm.enabled:
    norm_a = pop.community_norm[stack_a] if stratified else pop.community_norm[0]
    norm_b = pop.community_norm[stack_b] if stratified else pop.community_norm[0]
    dev_a = np.abs(al_a - norm_a)
    dev_b = np.abs(al_b - norm_b)
    binding = np.maximum(dev_a, dev_b)   # the worse-deviating side gates the trade
else:
    binding = np.abs(al_a - al_b)        # legacy static distance

align_reject = rngs["alignment"].random(n_pairs) < (
    0.03 + 0.20 * binding * (1.0 - 0.5 * (auto_a + auto_b) / 2.0)
)
```

The coefficient `0.20` is preserved. If empirical Sobol (plan 9) shows the binding term has too much weight under norm evolution, retune in a follow-up — do not retune here.

### Task 4 — New metrics

`engine/core/metrics.py` `StepMetrics`:

```python
community_norm_mean: float     # mean across stacks (or scalar if not stratified)
community_norm_drift: float    # |community_norm - initial_norm|
align_reject_share_under_norm: float  # 0 when norm.enabled is False
```

These let the dashboard show whether norm evolution is biting.

### Task 5 — Tests

`engine/tests/test_norm_evolution.py`:

```python
def test_eta_zero_reproduces_static():
    """eta=0 with norm.enabled=True must reproduce the static-align run
    bit-for-bit (norm never moves, so deviation == fixed offset)."""

def test_norm_tracks_alignment_weighted_mean():
    """In a population whose alignment is held constant, community_norm
    converges to the alignment-weighted mean within ~5 / eta steps."""

def test_translation_invariance_breaks():
    """If we shift every prototype's alignment by +0.5, the static-distance
    align_reject is unchanged but the norm-deviation align_reject increases
    until the norm catches up."""

def test_norm_uses_registered_only():
    """With registration_coverage=0, community_norm equals initial_norm
    forever (no observers contribute)."""
```

### Task 6 — Doc paragraph

In `docs/concepts/matryoshkan_alignment.md`, after the existing description of the individual layer, add:

> The individual-layer gate is parameter-named: `binding = max(|al_a - community_norm|, |al_b - community_norm|)` when `NormConfig.enabled` is true, else `binding = |al_a - al_b|`. The norm is a tracked field updated each step toward the alignment-weighted mean of the previous `norm_lag_steps` executed trades, with rate `norm_update_eta`. The coefficient on `binding` (0.20) is the same in both regimes; only the binding term differs. Hadfield's normative-competence reading of alignment fits the `enabled` regime; the original Krier-only formulation fits the `disabled` regime. Default is disabled, to preserve the canonical Sobol pin until the round-overview's plan 9 re-pins on the extended parameter set.

In `docs/concepts/coasean_bargaining.md`, add a one-paragraph cross-reference noting that normative competence (this plan) is the missing ingredient that lets Coasean clearing become durable rather than instantaneous-and-amnesic.

In `docs/bibliography.md`, add Hadfield citations if not already present (the round-overview specifies this).

## Exit conditions

- `NormConfig.enabled = False` (the default) reproduces every existing pinned canonical bit-for-bit.
- `NormConfig.enabled = True, eta = 0` also reproduces canonical bit-for-bit (test in Task 5).
- All tests in `test_norm_evolution.py` pass.
- The dashboard shows `community_norm_drift` on at least one panel for `enabled=True` scenarios.

## Acceptance test

```bash
python -m pytest engine/tests/ -x
python -m pytest engine/tests/test_norm_evolution.py -v
```

All green, plus a manual sanity check on a `norm_evolution_smooth` scenario (to be added to `engine/scenarios/__init__.py`): `community_norm_drift` should be visible on the dashboard after 30+ steps.

## Notes for the executor

- The norm is a scalar (or short vector) per stack. Do not generalize to a full alignment-space vector field — that is v2.
- Do not change the `0.03` baseline rate or the `0.20 * binding` coefficient. Retuning happens in plan 9 after Sobol attribution under the new RNG layout is trustworthy.
- The lag buffer is initialised to `initial_norm` at synthesize time; do not initialise to NaN or to the population mean. The convention is "norm starts at the prior".
- `_compute_executed_alignment_mean` should fall back to `initial_norm` if `executed_mask.sum() == 0` for that stack on that step. Do not propagate NaN.
