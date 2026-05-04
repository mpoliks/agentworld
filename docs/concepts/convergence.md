# Convergence and stability discipline

> Companion note for `agentworld convergence` and `agentworld stability`.

The α-engine carries a *scale invariance assumption*: ~10⁵ prototypes stand in for ~8 × 10¹¹ entities via importance weighting. [`epistemic_status.md`](epistemic_status.md) names the failure mode — if the dynamics are non-linear in population density (network percolation, herd-immunity-like thresholds), the importance-weighted approximation breaks. It also names the related ambiguity: a "step" has no fixed real-world duration, so terminal-metric values from a 60-step run are not commensurable with a 200-step run unless the trajectory has stabilised.

Two harnesses exist to test those assumptions, and the answer they produce is supposed to be the gate on which numbers from a scenario can be trusted.

| Harness | Sweeps | Question it answers |
| --- | --- | --- |
| [`engine.convergence`](../../engine/convergence.py) | population scale | Is the population large enough that small-scale point estimates fit inside larger-scale bootstrap CIs? |
| [`engine.stability`](../../engine/stability.py) | `n_steps` budget | Has the trajectory finished moving? Do terminal medians at `n_steps = N` and `n_steps = 2N` agree within CI? |

Together they cover the two questions the brief is most often asked:

> *"Should I be running these simulations longer or across larger pools?"*

The answer is whichever harness fails. If `convergence` returns medium-scale CIs that exclude the small-scale mean, run larger. If `stability` returns terminal medians that drift across step budgets, run longer. Otherwise the existing budget is doing the job.

---

## Running convergence

```bash
agentworld convergence --scales small --scales medium --scales large \
    --seeds 4 --only baroque_cathedral --only productive_baroque
```

For the curated subset (3 scenarios, small + medium, 2 seeds), the small-scale terminal EBI mean is expected to lie within the medium-scale bootstrap CI. The pinned regression is in [`engine/tests/test_convergence_pinned.py`](../../engine/tests/test_convergence_pinned.py); it runs a 30-step in-process sweep on each canonical scenario and fails the build if the small-scale mean strays outside the medium-scale CI plus a 50% slack on either side.

What "fragile" looks like in practice:

- **Scale-fragile**: small mean outside medium CI. The importance-weighted prototypes are not standing in cleanly for the full population — a non-linearity in the dynamics is biting. Don't trust small-scale point estimates from this scenario without the medium- or large-scale rerun.
- **Borderline**: small mean inside medium CI, but `large` is needed to confirm. Acceptable for first-pass narrative work; flag for follow-up.
- **Stable**: small mean inside medium CI, medium mean inside large CI. Small-scale numbers are doing what they claim; promote the small-scale runtime to the default for sweep work.

---

## Running stability

```bash
agentworld stability --steps 100 --steps 200 --steps 400 \
    --seeds 4 --only baroque_cathedral
```

For each scenario the harness reports terminal-metric bootstrap CIs at each `n_steps`. A scenario is *stable* if the terminal-EBI median at `n_steps = 400` lies inside the CI at `n_steps = 200`. A scenario that drifts is in *transient* regime and its terminal numbers should be reported as such, not as steady state.

This matters for the cumulative metrics (EBI, real welfare per capita) more than for the instantaneous ones (alpha, gini). Cumulative metrics ratchet — a longer run will change them mechanically even if the underlying dynamics have settled — so the diagnostic is whether the *step-on-step delta* has shrunk to within numerical noise, not whether the cumulative value is the same.

---

## What "running larger / longer" actually buys

The harness exists because the alternative is a vibes decision. Three concrete things they protect against:

1. **Importance-weighting collapse.** A scenario tuned at 88K prototypes may give a clean basin classification that disappears at 8.8M because the underlying dynamics have a percolation threshold the small-scale draw missed. Stress run the convergence harness before quoting terminal numbers.
2. **Transient mistaken for steady state.** A 60-step or 100-step run may catch the trajectory mid-cascade. The brief's narrative scenarios are built to terminate near a regime; the regime claim is only valid if the stability harness shows the metric has stopped moving.
3. **Seed-driven outliers.** Both harnesses run multiple seeds and report bootstrap CIs precisely so a single-seed terminal value isn't misread as the scenario's signature. Quoting an EBI without a band — including the band-of-the-band — is exactly the kind of false precision the [`epistemic_status.md`](epistemic_status.md) document exists to prevent.

When in doubt, run them. The runtime is cheap relative to the cost of misreporting.

---

## Output artefacts

```
outputs/convergence/<scenario>.json   # per-scenario per-scale terminal-metric CIs
outputs/convergence/_summary.json     # all scenarios, all scales, terminal CIs only
outputs/stability/<scenario>.json     # per-scenario per-step-budget terminal-metric CIs
outputs/stability/_summary.json       # same, summary form
```

The dashboard's §0 epistemic-status panel is the natural place to surface scale-fragile and transient flags once these sweeps are committed; that is on the follow-up list.
