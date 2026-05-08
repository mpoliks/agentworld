# Split market-layer rejection into platform and regulator

Status: `engine/core/transactions.py:305-307` computes a single market-layer rejection probability,

```python
market_reject = rng.random(n_pairs) < (
    0.02 + 0.06 * (1.0 - sec_aff) + 0.04 * align_dist
)
```

`docs/concepts/matryoshkan_alignment.md` describes this as the "market" doll in Krier's three-doll stack. The current artifact also gestures at this gate as a stand-in for Hadfield-style regulatory markets (government-licensed private regulators competing on audit quality). Those are two different objects: Krier's market doll is foundation-model deployers and platform owners; Hadfield's regulatory market is licensed third-party regulators. Conflating them is a substantive elision a Hadfield-aligned reader will notice on the first page.

This plan splits the gate into two independent sublayers — platform/deployer and regulator — with separate parameters and separate metrics. At default config, the combined rejection rate matches today's `market_reject` to within float noise.

This plan stands alone. Read these inputs only:

- `engine/core/transactions.py` (the gate block, currently lines 295–330)
- `engine/core/institutions.py` (full file — this is where the regulator object lives)
- `engine/core/population.py` (to read `audit_acceptances` / `audit_rejections` / `audit_last_alignment` from plan 2)
- `engine/core/metrics.py` (rejection-share metrics)
- `engine/core/world.py` (step path)
- `docs/concepts/matryoshkan_alignment.md` (prose to amend)

## Dependencies

- Plan 1 (per-component RNG split) — preferred. Two gates, two RNG streams (`rngs["market"]` for platform, a new `rngs["regulator"]` child or reuse of `rngs["law"]`).
- Plan 2 (registration regime) — required. Regulator audit operates on the per-prototype audit trail. `regulator_coverage` is bounded above by `registration_coverage` (you cannot audit an unregistered counterparty).

## Why

Krier's market layer (deployer/platform compatibility) and Hadfield's regulatory market (licensed audit) have different parameter dependencies and different policy levers:

- The platform gate scales with sector affinity and platform compatibility — a B2B finance-stack agent transacting with a consumer-leisure-stack agent is platform-incompatible regardless of any external regulator.
- The regulator gate scales with audit coverage and audit quality, and with how *defective* a counterparty's history is — a registered agent with a high recent-rejection rate is a poor audit risk and gets blocked by a higher-quality regulator at a higher rate.

Modeling them separately lets us answer policy questions the current single gate cannot:

- What does increasing audit quality do to EBI when sector affinity is held fixed?
- Does a high-quality regulator under low coverage outperform a low-quality regulator under high coverage?
- Is the Matryoshka-collapse scenario (governance overhead ~40%) driven by platform friction, regulator friction, or both?

## What to do

### Task 1 — Add `RegulatorConfig`

In `engine/core/institutions.py`:

```python
@dataclass
class RegulatorConfig:
    enabled: bool = False
    coverage: float = 0.0       # fraction of trades audited; 0 = layer absent
    audit_quality: float = 0.0  # sensitivity of audit to defect score [0, 1]
    base_reject_rate: float = 0.01
    defect_decay: float = 0.95  # rolling decay applied to defect score
```

Default `enabled=False, coverage=0` — the layer is invisible.

In `WorldConfig` or `TopologyConfig`, add:

```python
regulator: RegulatorConfig = field(default_factory=RegulatorConfig)
```

Wire to wherever the engine config block lives.

### Task 2 — Define the defect score

In `engine/core/institutions.py`, add:

```python
def compute_defect_score(pop: Population) -> np.ndarray:
    """Per-prototype defect score in [0, 1].

    Uses the audit trail from plan 2:
        defect = rejections / max(rejections + acceptances, 1)
    Unregistered prototypes (id < 0) have defect = 0.0 — they cannot be
    audited, so the regulator layer cannot affect their trades.
    """
```

This is the simplest reasonable defect score. A more sophisticated version would weight recent observations more (using `audit_last_alignment`'s deviation from `community_norm` once plan 3 is in). Defer that to a follow-up.

### Task 3 — Replace the single market gate with two

In `engine/core/transactions.py`, replace the current block:

```python
# Platform/deployer layer (Krier's market doll).
platform_reject = rngs["market"].random(n_pairs) < (
    0.02 + 0.06 * (1.0 - sec_aff)
)

# Regulator layer (Hadfield's licensed-regulator market).
if reg_cfg.enabled and reg_cfg.coverage > 0.0:
    audited = rngs["regulator"].random(n_pairs) < reg_cfg.coverage
    defect_a = compute_defect_score(pop)[pair_a_idx]
    defect_b = compute_defect_score(pop)[pair_b_idx]
    defect_pair = np.maximum(defect_a, defect_b)
    regulator_reject = audited & (
        rngs["regulator"].random(n_pairs)
        < reg_cfg.base_reject_rate + reg_cfg.audit_quality * defect_pair
    )
else:
    regulator_reject = np.zeros(n_pairs, dtype=bool)

# Effective market-layer rejection is the OR.
market_reject = platform_reject | regulator_reject
```

The legacy `0.04 * align_dist` term moves into the alignment layer (plan 3 already restructures that gate). The two gates compose by OR — either the platform refuses or the regulator does.

When `regulator.enabled=False`, `regulator_reject` is all-False and `market_reject == platform_reject`. The `0.06 * (1-sec_aff)` term on the platform side equals the dominant term in the legacy single-gate formula, so default-config canonical scenarios reproduce within float noise.

### Task 4 — Bound regulator coverage by registration coverage

In `World.build`, after `Population.synthesize`:

```python
effective_reg_coverage = min(reg_cfg.coverage, pop.cfg.registration_coverage)
if reg_cfg.enabled and effective_reg_coverage < reg_cfg.coverage:
    warnings.warn(
        f"regulator.coverage ({reg_cfg.coverage}) exceeds "
        f"registration_coverage ({pop.cfg.registration_coverage}); "
        f"effective coverage clamped to {effective_reg_coverage}"
    )
reg_cfg = replace(reg_cfg, coverage=effective_reg_coverage)
```

Hard upper bound: you cannot audit what you cannot identify.

### Task 5 — Metrics

`engine/core/metrics.py` `StepMetrics`:

```python
platform_reject_share: float     # share of pairs killed by platform gate alone
regulator_reject_share: float    # share killed by regulator gate (after platform)
audit_quality_effective: float   # reg_cfg.audit_quality * registered_active_share
```

The reject_share split lets the dashboard's stacked-rejection panel grow from three layers (law / market / individual / cost) to four (law / platform / regulator / individual / cost).

### Task 6 — Tests

`engine/tests/test_regulator.py`:

```python
def test_regulator_disabled_reproduces_market_baseline():
    """With regulator.enabled=False, total reject share matches the legacy
    market gate output to within float noise."""

def test_regulator_coverage_clamped_to_registration_coverage():
    """If reg.coverage=0.8 and registration_coverage=0.3, effective is 0.3."""

def test_high_audit_quality_blocks_high_defect_prototypes():
    """Construct a population where some prototypes have defect=0.9. With
    audit_quality=1.0 and coverage=1.0, those prototypes should see ~90%
    regulator rejection over a long run."""

def test_regulator_layer_does_not_affect_unregistered():
    """Unregistered (prototype_id=-1) prototypes have defect=0, so the
    regulator layer's marginal rejection over them is base_reject_rate
    only — no quality contribution."""
```

### Task 7 — Doc amendment

In `docs/concepts/matryoshkan_alignment.md`, replace the existing "market layer" paragraph with a two-paragraph version:

- Paragraph 1: platform/deployer (Krier). The `platform_reject = 0.02 + 0.06 * (1 - sec_aff)` formula. Reads as "platform compatibility gate".
- Paragraph 2: regulator (Hadfield). `regulator_reject = base + audit_quality * defect_score`, gated by `coverage`, bounded above by `registration_coverage`. Reads as "licensed-regulator audit gate". Cite Hadfield 2025 (AIhub interview), 2026 (Jurimetrics), and 2026 (Legal Infrastructure).

If `docs/bibliography.md` does not already include Hadfield, add the three pieces.

## Exit conditions

- All existing canonical scenarios reproduce within float tolerance < 1e-9 with the new code at `regulator.enabled=False`.
- `regulator_reject_share` appears in `StepMetrics` and the dashboard's rejection panel.
- All tests in `test_regulator.py` pass.
- `docs/concepts/matryoshkan_alignment.md` distinguishes platform from regulator.

## Acceptance test

```bash
python -m pytest engine/tests/ -x
python -m pytest engine/tests/test_regulator.py -v
```

Plus: a new scenario `regulator_active` (in `engine/scenarios/__init__.py`) with `registration_coverage=0.7, regulator.enabled=True, coverage=0.5, audit_quality=0.6`. Run on dashboard; rejection panel should show a non-zero regulator slice.

## Notes for the executor

- Do not couple the regulator gate to alignment distance. The whole point of the split is that platform compatibility (sector) and audit quality (defect history) are different signals.
- Do not make `audit_quality` time-varying in this plan. Adaptive audit quality (regulators that learn defect distributions and adjust thresholds) is a follow-up.
- The `defect_decay` field in `RegulatorConfig` is a placeholder for the time-decay version of defect score. If you find time, implement it (replace the `rejections / total` ratio with an exponentially decayed version); otherwise leave the field unused for now and note the omission inline.
- Keep `compute_defect_score` vectorized — it's called every step over the full prototype array.
