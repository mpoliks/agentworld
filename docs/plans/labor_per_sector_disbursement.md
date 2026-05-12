# W2c extension — per-sector labor wage disbursement

Status: drafted 2026-05-12. Operational extension to W2c
(`commit 15c4499`). Replaces the uniform-across-humans wage
disbursement with sector-matched routing so the wage channel reads
as "humans in the sector where the trade happened get the wage."

## Dependencies

W2c labor wedge landed in `commit 15c4499`. This plan replaces the
disbursement logic only; the wedge calculation and the
`human_labor_wage_step` / `_cumulative` / `gini_wealth_human` /
`real_per_capita_welfare_human` metrics stay as they are.

## Why

W2c shipped with the simplest possible disbursement: aggregate the
wedge across all pairs, divide by total human weight, credit every
human prototype the same per-capita amount. The Jacobs framing the
labor wedge implements is *sector-specific*: when an A2A trade in
finance displaces a finance worker, the wage goes (or fails to go)
to humans in the finance labor market, not to humans in
agriculture.

The uniform routing was acceptable as a first pass because the
wage-vs-no-wage delta on aggregate metrics (`gini_wealth_human`,
`real_per_capita_welfare_human`) is the same magnitude under either
routing rule — only the *distribution* of the wage within humans
changes. Per-sector routing makes that distribution informative:
high-A2A sectors concentrate wage payments to humans who happen to
live in those sectors; low-A2A sectors do not.

## What to do

### Task 1 — Aggregate the wedge per sector inside `coasean_step`

`engine/core/transactions.py:574-606` computes `wedge_pair` and the
scalar `human_labor_wage` total. Replace the scalar aggregate with
a per-sector aggregate using `sec_a` as the production-side sector:

```python
human_wage_per_sector = np.bincount(
    sec_a,
    weights=wedge_pair * pair_real_count,
    minlength=N_SECTORS,
)
human_labor_wage = float(human_wage_per_sector.sum())
```

Keep `human_labor_wage` as the scalar (the metric reader still
wants the total). Add `human_wage_per_sector` as a new ndarray
field on `TransactionResult` (defaults to `np.zeros(N_SECTORS)` so
back-compat at `LaborConfig.enabled=False` is preserved).

### Task 2 — Route per-sector pool to humans in that sector

Replace the uniform disbursement block at
`engine/core/transactions.py:593-606`. For each sector `s` with
non-zero `human_wage_per_sector[s]`:

```python
mask_s = pop.is_human & (pop.sector == s)
h_weight_s = pop.weight[mask_s].astype(np.float64)
total_h_weight_s = float(h_weight_s.sum())
if total_h_weight_s > 0:
    per_proto_delta = human_wage_per_sector[s] / total_h_weight_s
    wealth_delta[mask_s] += per_proto_delta
```

Edge case: a sector with no human prototypes (a possibility at small
n) means the wage attributed to that sector falls into the void.
Document as a known behaviour rather than try to redistribute —
sector-no-humans is a structural property of the population, not a
runtime accident.

### Task 3 — Update the chunked variant aggregation

`_coasean_step_chunked` accumulates `human_labor_wage` across
chunks. Add a parallel accumulator for `human_wage_per_sector`
(np.zeros(N_SECTORS) initialised; `+=` per chunk).

### Task 4 — Expose per-sector cumulative on Metrics

The existing metric `human_labor_wage_cumulative` is a scalar.
Add an ndarray `human_labor_wage_cumulative_per_sector` of shape
`(N_SECTORS,)` to `Metrics` (accumulated in
`Metrics.__init__`), populated each step, and exposed on
`StepMetrics` as a `list[float]` of length N_SECTORS (lists
serialise cleanly via the existing `to_dict()` path).

### Task 5 — Test coverage

Extend `engine/tests/test_labor.py` with:

- A pin test that with the wedge on and `labor_share=[0.6 if s==9 else 0.0 for s in range(N_SECTORS)]` (mission-style health-sector-only labor share), wage cumulative is concentrated on the health sector and zero elsewhere.
- A pin test on the no-humans-in-sector edge case: with the wedge on, no failure / no NaN.
- The existing aggregate tests (bit-identity, conservation, growth) should still pass.

## Exit conditions

- Per-sector disbursement is the default behaviour when
  `LaborConfig.enabled = True`. The uniform-routing first pass is
  retired.
- All canonical regression scenarios stay bit-identical (W2c is
  off by default; this plan only affects the on-path).
- New per-sector wage metric is exposed on StepMetrics and read
  by the dashboard.
- Three new test cases in `test_labor.py` cover the per-sector
  contract.

## Notes for the executor

- `sec_a` rather than `sec_b` is the production-side sector by the
  same convention W2b uses for `coordinator_sectors`. The wedge
  attributes the wage to where the work happens.
- N_SECTORS = 12 (see `engine/core/population.SECTOR_NAMES`). At
  N=12 the per-sector bincount is cheap; no performance concerns.
- The dashboard's W2c panel currently reads only the scalar
  cumulative. Per-sector exposure motivates a new stacked-area chart
  of wage-per-sector-over-time, which is a separate dashboard plan.
