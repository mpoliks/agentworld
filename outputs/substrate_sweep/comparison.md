# Substrate sweep — plain vs anchored

Each row: a dashboard scenario run (a) plain (existing ensemble bands) and (b) on the empirical substrate (sector-block network + t-copula noise + Hawkes folding) with `base_variance_absorption=0` and `DemandConfig.enabled=False`. Deltas are anchored − plain in percent of plain.

| scenario | plain EBI | anch EBI | ΔEBI | plain Wcum | anch Wcum | ΔW | plain sub-mkts/step | anch sub-mkts/step |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| coasean_paradise | 1.06 | 1.05 | -1% | 1.34e+09 | 2.21e+09 | +64% | 0 | 0 |
| universal_advocate | 1.39 | 1.38 | -1% | 8.06e+08 | 1.31e+09 | +63% | 738.26 | 738.26 |
| public_defender | 1.78 | 1.74 | -2% | 6.65e+08 | 1.07e+09 | +60% | 99,651 | 99,651 |
| civic_renaissance | 2.27 | 2.16 | -5% | 5.20e+08 | 8.52e+08 | +64% | 99,651 | 99,651 |
| synthetic_consumers_v2 | 6.24 | 5.72 | -8% | 3.09e+08 | 5.15e+08 | +67% | 292,445 | 292,445 |
| smoothing_cascade | 16.39 | 14.70 | -10% | 4.96e+08 | 7.99e+08 | +61% | 0 | 0 |
| equilibrium_drift | 4.89 | 4.40 | -10% | 1.98e+08 | 3.15e+08 | +59% | 256,934 | 256,934 |
| matryoshka_collapse | 4.39 | 4.03 | -8% | 4.21e+08 | 6.65e+08 | +58% | 213,298 | 213,298 |
| hemispherical_schism | 6.85 | 6.50 | -5% | 4.67e+08 | 7.29e+08 | +56% | 304,928 | 304,928 |
| compute_famine | 3.99 | 3.39 | -15% | 4.07e+08 | 6.89e+08 | +69% | 173,875 | 173,875 |
| derivatives_revolution | 2.28 | 3.37 | +48% | 2.45e+09 | 2.56e+09 | +4% | 231,006 | 231,006 |
| legal_collapse | 5.05 | 4.17 | -17% | 1.40e+08 | 1.68e+08 | +20% | 213,298 | 213,298 |
| regulatory_capture | 7.84 | 7.93 | +1% | 3.00e+08 | 3.02e+08 | +1% | 304,928 | 304,928 |
| endogenous_baroque | 1.36 | 1.32 | -3% | 1.11e+09 | 1.80e+09 | +62% | 43.17 | 43.01 |
| pigouvian_heavy | 6.24 | 4.21 | -33% | 3.09e+08 | 5.15e+08 | +67% | 292,445 | 292,445 |
| pigouvian_friction | 6.24 | 5.08 | -19% | 3.09e+08 | 5.15e+08 | +67% | 292,445 | 292,445 |
| full_emergence | 1.30 | 1.25 | -4% | 1.05e+09 | 1.71e+09 | +62% | 26.91 | 27.09 |
| recursive_simulation | 18.88 | 17.19 | -9% | 4.93e+08 | 7.91e+08 | +61% | 602,224 | 602,224 |
| fold_avalanche | 16.39 | 16.19 | -1% | 4.96e+08 | 7.98e+08 | +61% | 681,109 | 681,109 |
| slop_market | 610.28 | 538.04 | -12% | 1.47e+08 | 2.01e+08 | +37% | 784,326 | 784,326 |
| productive_baroque | 16.53 | 20.19 | +22% | 1.42e+09 | 1.81e+09 | +27% | 546,227 | 546,227 |
| baroque_with_high_welfare | 330,392 | 823,520 | +149% | 2.21e+09 | 1.29e+09 | -42% | 2.22e+06 | 2.22e+06 |
| baroque_cathedral | 2,476 | 2,181 | -12% | 8.01e+08 | 1.33e+09 | +67% | 9.66e+06 | 9.66e+06 |
| exo_baroque_singularity | 2.53e+07 | 2.15e+07 | -15% | 4.02e+08 | 6.56e+08 | +63% | 1.24e+10 | 1.24e+10 |
