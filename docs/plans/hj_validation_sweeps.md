# H-J validation sweeps — permeability + norms sensitivity

Status: drafted 2026-05-12. Two pinned artifacts the
`hadfield_jacobs_robustness.md` umbrella plan named under "Validation
lift" but did not ship in the W1–W3 round. Both are sweep scripts +
JSON outputs that let the dashboard label the conditional nature of
the round's claims.

## Dependencies

W1c permeability (`commit 68eb436`) and W1b norms (`commit 6476319`)
must be landed. Both are; this plan is unblocked.

## Why

The umbrella plan's "Validation lift" section called for:

- `outputs/validation/permeability_sweep.json` — basin distribution
  under wide prior, with `cross_stack_permeability` swept
  independently of α.
- `outputs/validation/norms_sensitivity.json` — how much of the
  Smoothworld rejection share moves when norm-participation replaces
  static distance.

Without these, the dashboard's panels on the two new levers read as
"flag exists, default off, see the test for what it does." Pinning a
sweep over the prior lets us make a substantive claim about *where*
the lever lands the economy and *how much* it moves the binding
constraint.

## What to do

### Task 1 — Permeability sweep CLI

`engine/cli.py` already has a `validate` group with `anchor`,
`priors`, and `adversarial` subcommands. Add a fourth: `validate
permeability`. The sweep:

- Permeability grid: `[0.0, 0.1, 0.2, ..., 1.0]` (11 points; the
  legacy `1.0` is the canonical right edge).
- For each permeability point, sample `N=128` parameter vectors from
  the wide prior already used by `validate priors`
  (`engine/validation/posterior_sweep.py:wide_prior_problem`).
- Run each at small scale (`n_steps=24`, `pairs_per_step=20_000`,
  `n_human_prototypes=600`, `n_agent_prototypes=6_000`), with
  `cross_stack_permeability` overriding the prior's α-coupling.
- Classify each run's terminal regime via `engine.sensitivity.classify_basin`
  (the existing smooth/striated/baroque/slop labels).

Output: `outputs/validation/permeability_sweep.json`. Structure:

```json
{
  "permeability_values": [0.0, 0.1, ...],
  "n_samples_per_point": 128,
  "n_steps": 24,
  "basin_distribution": [
    {"permeability": 0.0, "smooth": 0.05, "baroque": 0.55, ...},
    ...
  ],
  "ebi_quantiles": [
    {"permeability": 0.0, "p10": ..., "p50": ..., "p90": ...},
    ...
  ]
}
```

Hook into `engine/cli.py` with `--out` flag defaulted to that path.

### Task 2 — Norms sensitivity sweep CLI

Same harness, second subcommand: `validate norms`. The question is
"how much does the binding-constraint rejection share move when we
toggle norm-participation on?"

- Two configurations: `NormsConfig(enabled=False)` (the canonical
  baseline) and `NormsConfig(enabled=True, update_rate=0.05,
  n_dimensions=4)`.
- For each configuration, sample `N=128` parameter vectors from the
  same wide prior used for `validate priors`.
- Record per-run: terminal `rejected_law / rejected_market /
  rejected_align / rejected_cost` shares, plus terminal EBI and
  per-capita welfare. Compute the cross-sample distribution of the
  rejected-mix vector under each configuration.

Output: `outputs/validation/norms_sensitivity.json`. Structure:

```json
{
  "n_samples": 128,
  "configurations": [
    {
      "label": "static",
      "rejection_share_distribution": {
        "law":      {"p10": ..., "p50": ..., "p90": ...},
        "market":   {...},
        "align":    {...},
        "cost":     {...}
      },
      "ebi":          {"p10": ..., "p50": ..., "p90": ...},
      "per_capita":   {"p10": ..., "p50": ..., "p90": ...}
    },
    {
      "label": "norm_participation",
      ...
    }
  ],
  "alignment_share_delta": {
    "p10": ..., "p50": ..., "p90": ...
  }
}
```

The `alignment_share_delta` is the load-bearing summary: it's the
per-sample swing in `rejected_align`'s share under the toggle.

### Task 3 — Wire into the dashboard

The dashboard already reads pinned validation outputs. Add two
panels:

- "Permeability sweep" — stacked-bar of basin distribution across the
  permeability grid. Shows whether sandboxed (`cross_stack_permeability
  → 0`) economies actually shift the basin counts away from
  baroque/smooth toward something distinct.
- "Norms sensitivity" — paired-violin of the four rejection-share
  components under static-distance vs norm-participation, plus the
  delta summary.

Both panels use the existing JSON-loader path in
`agentworld/dashboard/index.html`.

## Exit conditions

- `validate permeability` and `validate norms` CLIs both pinned in
  `engine/cli.py` with `--no-progress` defaults that produce
  reproducible JSON.
- Both JSON artifacts committed to `outputs/validation/`.
- Dashboard renders both panels and they tell a defensible story
  (the permeability lever moves the basin distribution by ≥ 15
  percentage points between 0.0 and 1.0; the norms toggle moves the
  alignment-share median by ≥ 5 percentage points).
- `engine/tests/test_validation_*.py` gain pin tests on the new
  artifacts in the existing pattern.

## Notes for the executor

- Compute budget: 11 × 128 + 2 × 128 ≈ 1.7K simulations at small
  scale → roughly 5–8 minutes wall under per-component RNG. A single
  background task is fine.
- The wide prior in `engine/validation/posterior_sweep.py` already
  includes `alpha`, `agent_capability_mean`, `folding_propensity`,
  etc. — `cross_stack_permeability` is *not* currently swept and the
  task-1 driver needs to override it explicitly. Same goes for
  `norms_config` in task 2.
