# Optional persistent agent registration

Status: `engine/core/population.py` represents the population as vectorised prototype rows. Each row is a weighted slice; rows have no stable identity across timesteps and no per-prototype audit trail. Every transaction in the model is between anonymous prototype draws. Hadfield (Legal Infrastructure for Transformative AI Governance, Feb 2026) treats registration regimes for autonomous agents as the precondition for any meaningful regulatory or alignment intervention. Without persistent identity, two downstream improvements (norm-tracking, regulator audit) cannot do real work — there is no continuity across draws to track norms over, and no counterparty to audit.

This plan stands alone. Read these inputs only:

- `engine/core/population.py` (full file)
- `engine/core/transactions.py` (the pair-sampling and execution path)
- `engine/core/world.py` (build and step, to see where Population lives)
- `engine/core/metrics.py` (to know where new metrics get registered)
- `engine/tests/test_engine.py` (pattern for engine-level tests)

## Dependencies

- Plan 1 (per-component RNG split) should land first if possible — registration consumes the population RNG child cleanly. If plan 1 has not landed, use the existing single RNG and refactor later.

This plan is a prerequisite for plans 3 (norm evolution) and 4 (regulator-market split). Both consume registration when on, and degrade gracefully when off.

## Why

Two distinct claims hang off this plan:

1. **Norm-tracking requires identity.** A community norm is the alignment-weighted mean of accepted/observed-rejected trades; if every trade is between fresh anonymous draws, "the norm" is just the population mean, which is already represented as `pop.alignment.mean()`. To make norms move differently from population mean, we need some prototypes whose trade history accumulates over time.

2. **Audit requires identity.** A regulator that levies a per-trade audit-quality penalty is incoherent if the counterparty is a one-shot draw. The audit mechanism only makes sense over a sequence of trades by the same identified prototype — defect_score has to compound.

The cheap version of this is not to make every prototype persistent, just to make a configurable fraction persistent, and let the rest stay anonymous draws as today. That fraction (`registration_coverage`) becomes a first-class policy lever that mechanisms 3 and 4 read from.

## What to do

### Task 1 — Add `registration_coverage` to `PopulationConfig`

In `engine/core/population.py`:

```python
@dataclass
class PopulationConfig:
    ...
    # Fraction of agent prototypes (NOT humans) that carry a stable ID and
    # accumulate a per-prototype audit trail across timesteps. At 0.0 (default),
    # the model behaves identically to today: every transaction is between
    # anonymous prototypes. At 1.0, every agent prototype is registered.
    registration_coverage: float = 0.0
```

Default 0.0 — preserves current behavior bit-for-bit when this plan is the only one landed.

### Task 2 — Add per-prototype identity and audit fields to `Population`

```python
@dataclass
class Population:
    ...
    prototype_id: np.ndarray              # int64, shape (N,), -1 means unregistered
    audit_acceptances: np.ndarray         # int32, shape (N,), running count
    audit_rejections: np.ndarray          # int32, shape (N,), running count
    audit_last_alignment: np.ndarray      # float32, shape (N,), most-recent observed alignment
```

In `Population.synthesize`:

- Allocate `prototype_id = np.full(N, -1, dtype=np.int64)`.
- Sample `mask_registered = rng.random(N) < cfg.registration_coverage` for the agent rows only (humans stay -1).
- Assign `prototype_id[mask_registered] = np.arange(mask_registered.sum())` (compact IDs starting at 0).
- Initialise the three audit arrays to zeros.

These fields are always present on `Population`; consumers that don't need them ignore them.

### Task 3 — Update audit counters during execution

In `engine/core/transactions.py`, inside the per-step trade execution path (after `executed_mask` is computed, before metrics are emitted):

```python
# Update audit trail for registered prototypes that participated this step.
# `pair_a_idx` and `pair_b_idx` index into the population arrays; some
# may be -1 (unregistered) — skip those.
def _update_audit(side_idx: np.ndarray, executed: np.ndarray, rejected: np.ndarray, align_obs: np.ndarray) -> None:
    reg = pop.prototype_id[side_idx] >= 0
    np.add.at(pop.audit_acceptances, side_idx[reg & executed], 1)
    np.add.at(pop.audit_rejections,  side_idx[reg & rejected], 1)
    pop.audit_last_alignment[side_idx[reg]] = align_obs[reg]

_update_audit(pair_a_idx, executed_mask, rejected_any_mask, al_a)
_update_audit(pair_b_idx, executed_mask, rejected_any_mask, al_b)
```

Use `np.add.at` for the unbuffered scatter-add that handles repeated indices correctly. This is a hot path; profile after landing — if `np.add.at` is too slow on xlarge, replace with `np.bincount` + assignment.

### Task 4 — Expose registered-fraction-active metric

In `engine/core/metrics.py`, add to `StepMetrics`:

```python
registered_active_share: float    # share of executed trades whose either side is registered
```

Compute as `(reg_a | reg_b) & executed_mask` divided by `executed_mask.sum()`, weighted by population weight. At `registration_coverage=0.0` this is always 0; at 1.0 it should approach 1.0 (some humans are involved in mixed trades, so it never quite hits 1).

### Task 5 — Configuration sanity test

`engine/tests/test_registration.py`:

```python
def test_registration_coverage_zero_reproduces_canonical():
    """coverage=0 must produce bit-for-bit identical history to a control run
    with no registration logic."""

def test_registration_coverage_one_assigns_all_agents():
    """coverage=1.0 means every non-human prototype has a non-negative ID."""

def test_audit_counters_accumulate_monotonically():
    """Acceptance and rejection counts only increase over time."""

def test_humans_never_registered():
    """is_human=True implies prototype_id == -1 regardless of coverage."""
```

## Exit conditions

- `registration_coverage=0.0` reproduces every existing pinned canonical bit-for-bit.
- `Population.prototype_id`, `audit_acceptances`, `audit_rejections`, `audit_last_alignment` exist on every `Population` instance.
- Audit counters increment correctly (verified by the test in Task 5).
- New `registered_active_share` metric appears in `StepMetrics`, `outputs/runs/<scenario>.json`, and the dashboard's metric table.

## Acceptance test

```bash
python -m pytest engine/tests/test_registration.py -v
python -m pytest engine/tests/ -x
```

All green. The canonical scenarios in `outputs/runs/*.json` reproduce within float tolerance < 1e-9.

## Notes for the executor

- This plan deliberately does not include a `governance_overhead` cost for registration. The cost is the regulator's job (plan 4); registration on its own is just identity, free at the model level.
- Do not add per-prototype persistence for *humans*. Human income work happens in plan 6 (decile vector), not as per-prototype IDs. Human prototypes stay anonymous.
- The audit trail is intentionally minimal (3 scalars per prototype). Richer audit logs (e.g. per-trade alignment series) are deferred to v2; the regulator (plan 4) only needs the current 3 scalars to compute defect score.
