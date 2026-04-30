# engine/data — empirical anchors

Every constant in [`empirical_anchors.py`](empirical_anchors.py) corresponds to a sub-model with a public empirical analog. Anchors are used to calibrate the *structure of randomness* in both engines (heavy-tail shape, sectoral co-movement, regional co-movement, network degree distribution, Hawkes branching ratio). Anchors are deliberately **not** used to calibrate the load-bearing speculative parameters (folding propensity, lift propensity, suppression cost exponent, etc.).

For the rules of what does and does not get anchored here, see [`docs/concepts/epistemic_status.md`](../../docs/concepts/epistemic_status.md).

## Anchor inventory

| Constant | Source | Vintage | Scope |
| --- | --- | --- | --- |
| `T_COPULA_DOF_DEFAULT` | Cont (2001), Quantitative Finance 1, 223-236 | 2001 | Heavy-tail kurtosis of daily returns in liquid markets |
| `HAWKES_BRANCHING_RATIO` | Bacry & Muzy (2015), Quantitative Finance 14(7), 1147-1166 | 2015 | Endogeneity ratio of HF equity markets |
| `HAWKES_DECAY` | Stipulated regularization on top of Bacry/Muzy 2015 | 2026 | Cascade depth at default folding_propensity |
| `NETWORK_DEGREE_EXPONENT` | Atalay et al. (2011), PNAS 108(13), 5199-5202 | 2011 | Pareto exponent of US B2B production network in-degree |
| `BEA_SECTOR_CORR` | BEA Input-Output Use Tables 2022 | 2022 | US sectoral co-movement (12 macro-sectors) |
| `REGION_GROWTH_CORR` | World Bank Global Economic Prospects 2024 | 2024 | Regional macro-growth correlations 2000-2023 |

## Re-anchoring procedure

When updating any anchor:

1. Bump the `vintage` in the corresponding `AnchorProvenance` entry.
2. Re-run `pytest engine/tests/` to confirm nothing breaks.
3. Re-run `agentworld run-all` (or only the scenarios you suspect are sensitive).
4. Re-run `agentworld sobol` and `agentworld exo sobol` to re-fit Sobol indices under the new noise structure.
5. Re-run `agentworld build-dashboard` to refresh the dashboard's About / Sources panel.

The PROVENANCE list at the bottom of `empirical_anchors.py` is what the dashboard reads.
