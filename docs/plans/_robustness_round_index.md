# Robustness Round — Index

Ten standalone plans that together address conceptual and numerical robustness gaps in the α- and exo-engines surfaced by a Hadfield/Tomašev-grounded review. Each plan in this folder is self-contained: a small model executing it does **not** need to read the others or any external review document. Cross-plan dependencies are spelled out in each file's `Dependencies` section.

## The plans

| # | File | Tier | Pre-reqs |
|---|---|---|---|
| 1 | [`rng_per_component_split.md`](rng_per_component_split.md) | Hygiene | None — must land first |
| 2 | [`registration_regime.md`](registration_regime.md) | Mechanism | None directly; enables 3 and 4 |
| 3 | [`norm_evolution_alignment.md`](norm_evolution_alignment.md) | Mechanism | 1, 2 |
| 4 | [`regulator_market_split.md`](regulator_market_split.md) | Mechanism | 1, 2 |
| 5 | [`permeability_axis.md`](permeability_axis.md) | Mechanism | 1 |
| 6 | [`human_income_deciles.md`](human_income_deciles.md) | Mechanism | 1 |
| 7 | [`mission_economy_scenario.md`](mission_economy_scenario.md) | Mechanism | 1, 5 |
| 8 | [`coverage_gap_tests.md`](coverage_gap_tests.md) | Hygiene | None |
| 9 | [`repin_canonical_sobol.md`](repin_canonical_sobol.md) | Hygiene | 3, 4, 5, 6, 7 |
| 10 | [`epistemic_assumption_block.md`](epistemic_assumption_block.md) | Docs | None |

## Recommended execution order

1. **Plan 1 (RNG split)** — prerequisite for trustworthy Sobol attribution on every other change. Land first.
2. **Plan 2 (registration)** — opt-in default off. Land second so plans 3 and 4 can consume it.
3. **Plans 3 and 4 in parallel** — both touch `transactions.py`; coordinate the merge but the work is independent.
4. **Plans 5 and 6 in parallel with 3/4** — independent files.
5. **Plan 7 (mission economy)** — needs plan 5's permeability config to express the matched-permeability baseline.
6. **Plan 8 (coverage tests)** — drip in alongside any of the above, scoped to the subsystem the parallel plan does not already cover.
7. **Plan 9 (re-pin Sobol)** — runs after every mechanism that adds a parameter has landed.
8. **Plan 10 (epistemic block)** — drafted last so the conditioning list reflects the new defaults.

Estimate: 1.5–3 weeks depending on parallelism.

## Done criteria for the round

- All 16 existing pinned canonical scenarios reproduce within float tolerance under default config (every new mechanism off by default).
- New scenarios (`low_permeability_smooth`, `high_permeability_striated`, `mission_economy_carbon`, `mission_economy_public_defender`, plus matched-Coasean baselines) are in `engine/scenarios/__init__.py` and exercised by the dashboard.
- New tests (one per uncovered subsystem in plan 8 + per-plan acceptance tests) pass.
- New canonical Sobol pinned at N=2048 on the extended parameter vector; prior pin archived.
- `docs/concepts/epistemic_status.md` opens with the ranked conditioning-assumption block.
- `docs/bibliography.md` includes Hadfield's three recent pieces; `docs/concepts/matryoshkan_alignment.md` cites her on the regulator distinction; `docs/concepts/coasean_bargaining.md` cites her on normative competence.

## What this round does not address

- Endogenous agent strategy beyond the existing bandit. Strategy/learning robustness is a separate round.
- Exo-engine inter-region trade. Last-mile decile work in plan 6 stays inside one region.
- Replacement of the static-vector alignment representation with a higher-dimensional norm space. Plan 3 introduces a community-norm field but keeps alignment as a scalar; lifting that to a vector is v2.

## Cross-cutting style

- Every new config field gets a default that reproduces current behavior bit-for-bit. No silent changes to existing canonical runs.
- Every plan ships at least one regression test that pins its `off` mode against the current canonical.
- Every plan ships one positive test that exercises its `on` mode on a synthetic input where the expected direction of metric movement is obvious.
- Comments in code stay one short line per non-obvious *why*. No multi-paragraph docstrings. Plan files (this folder) carry the long-form rationale.
