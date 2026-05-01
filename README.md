# AGENTWORLD

### A computational research artifact for Antikythera's *100:1 Parasociety* brief

> *"Instead of removing friction, labor and people from supply and demand, there is equal potential for the fractal multiplication of folded surfaces."* — Benjamin Bratton, April 2026

---

## What this is

**Agentworld** is a research artifact — a conceptual brief, a vectorized simulation engine, a scenario atlas, and a dashboard — for thinking about the planetary economy when society is composed of **8 billion humans and 800 billion to 1 trillion AI agents**.

It is built around a single variable: **smooth ↔ striated**.

At one pole, agents *disintermediate* — they collapse transaction costs to near-zero, evaporate middle-layer institutions, and flatten the supply chain into a frictionless plane. This is the Coasean limit. Krier's vision realized.

At the other pole, agents *fold* — they generate new layers of intermediation, new contractual surfaces, new micro-markets stacked on micro-markets. Every interaction begets two negotiations; every negotiation begets four sub-negotiations. GDP, measured on paper, explodes — not because more is produced but because more is *priced*. This is the Baroque limit.

Both are stable equilibria of the same underlying technology. Which one materializes is not predetermined. **It is a question of mechanism design, of property rights, of compute economics, and of what we — and the agents — choose to count.**

---

## The 100:1 condition

Antikythera frames *Agentworld* as a "parasociety of a trillion minds": ~8B humans, ~10²–10³× as many human-level agents, nested within and evolving alongside human society. The most personal interactions remain between humans. The most *socially important* ones are agent-to-agent. (See [Antikythera Research](https://antikythera.org/research).)

This is not science fiction. It is a near-term extrapolation of three trends that are already underway by Q2 2026:

1. **Inference is collapsing toward the cost of electricity.** A general-purpose model running at the marginal cost of compute is functionally a free agent. Krier (Sept 2025) calls this "cognition-and-agency on demand."
2. **Agent-to-agent payment infrastructure is shipping.** AP2, x402, ClawCoin, Mastercard Agent Pay, Stripe Agentic Commerce — the rails for sub-cent, high-frequency, autonomous transactions are being laid right now.
3. **Personal advocate agents are becoming the dominant interface.** A "fiduciary extension of yourself" (Krier) negotiates on your behalf at speeds and granularities no human can match.

When these three converge, the transaction-cost floor that Coase identified — the friction that justifies hierarchy, the firm, the regulator, the platform — drops by 4–6 orders of magnitude. Almost every market failure becomes, in principle, a tractable bilateral or n-lateral deal.

But "in principle" is the slippery word. *What actually happens* depends on whether the agent layer behaves as a **sieve** (smooth) or a **scaffold** (striated). And our intuition that it must be one or the other is wrong: at scale, **both happen at once**, in different sub-strata of the same economy.

---

## The two attractors

### Attractor A — Smooth (Krier limit)

Agents act as universal solvent. Every middle-layer firm whose value-add was *coordination* dissolves. Travel agents, insurance brokers, real-estate agents, advertising agencies, recruiters, talent agents, supply-chain coordinators, B2B sales orgs, most of legal services — gone, or reduced to thin compliance shells. The economy looks more like a **commons** than a market: most exchanges are direct, near-zero-margin, hyper-personalized.

- Measured GDP **falls** in nominal terms (the brokerage layers were a large fraction of services GDP) even as welfare rises.
- The state shrinks toward a "framework guarantor" role (Krier's term).
- Power consolidates in the *foundation model providers* and *infrastructure operators* — the few entities that own the substrate on which all agents run.
- **Risk:** this is the world where a handful of companies own the cognitive infrastructure of all bargaining. Hayek wins the surface argument; Schmitt wins the ground.

### Attractor B — Striated / Baroque (Bratton limit)

Agents act as fractal cell-divider. Every existing market spawns sub-markets; every sub-market spawns sub-sub-markets. Your noise-preference agent negotiates with your neighbor's leaf-blower-routing agent, which negotiates with the leaf-blower OEM's warranty agent, which negotiates with the lithium-supply-futures agent, which... A delivery to your door involves **2,400 priced micro-transactions**, none of which a human ever sees, all of which are denominated in a unit-of-account that some agent decided this morning.

- Measured GDP **explodes** in nominal terms. Each transaction is a "real" economic event by national-accounts standards.
- Most "GDP" is *machine-internal* — the economy folds into itself like a Hilbert curve. The surface area available for pricing is fractal, and therefore unbounded.
- The state becomes a *ledger arbiter* and *unit-of-account guarantor*, not a planner.
- Power consolidates in whoever **defines the protocols and units**. Whoever sets what counts as a transaction sets what counts as wealth.
- **Risk:** the economy becomes legible only to itself. Humans lose the ability to navigate the surfaces they nominally own. The Baroque becomes a labyrinth.

These are not opposites. They are the same machine, run at two different settings of one parameter — the **friction coefficient** between agent-mediated negotiations.

---

## What this artifact does

Three deliverables, in increasing order of fidelity:

### 1. The Brief (this document + `docs/concepts/`)
A conceptual map of the variable space, glossary, bibliography, and 15 scenario sketches. Designed to be readable as a standalone research note, citable in Bratton's *Agentworld* brief.

### 2. The Engines (`engine/` and `engine/exo/`)

This artifact carries **two engines** rather than one. They model the same underlying situation through deliberately different ontologies, and the disagreement between them is part of the deliverable.

#### α-engine (`engine/`)
A vectorized agent-economy simulator written in Python + NumPy. Sample size: 10⁶ agents per run, statistically representing the 800B-agent population through importance-weighted sampling across the smooth-striated continuum.

It models, at minimum:

- A **Coasean transaction-cost surface** parameterized by agent capability, protocol overhead, and enforcement cost.
- A **fractal folding operator** that lets markets recursively spawn sub-markets when transaction cost drops below a threshold and there is positive expected surplus from sub-division.
- A **Matryoshka alignment stack** (law / market / individual) that sets the boundaries within which agents can transact.
- **Hemispherical splits** (multi-stack regions with incompatible protocols) as a topological constraint.
- **Recursive measurement** — the GDP measured in striated regimes is partly a function of the measurement protocol itself, which is itself negotiable.

Outputs: time-series of GDP (real and nominal), Gini, surplus per capita, market depth (folding factor), agent-to-human interaction ratio, and an "exo-baroque index" that quantifies how much of the economy has folded out of human legibility.

The engine now has two modes:

- **Scenario mode** runs the 15 named narrative attractors.
- **Phase-space mode** (`engine/sensitivity.py` / `agentworld sweep`) sweeps `α × capability` and classifies each grid point as smooth, mixed, striated, baroque, or slop. This is the sanity check that the named scenarios are samples from a wider basin structure, not just hand-picked stories.

#### exo-engine (`engine/exo/`)

A second simulator written from scratch in dialogue with Poliks & Trillo's *Exocapitalism* (2025). It rejects the α-engine's central diagnostic — `EBI = nominal / real` — on the grounds that the diagnostic privileges last-mile activity as the "real" denominator and treats the smooth/striated dial as a free parameter. Instead, the exo-engine models four operators:

1. **Lift** (`engine/exo/stack.py`) — capital's continuous drift through `K` abstraction layers, fractally branching.
2. **Drag** (`engine/exo/drag.py`) — the labor of producing legibility tokens for capital to lift through; the "Coasean dampener" mode lets drag consume welfare without enabling lift.
3. **Last mile** (`engine/exo/last_mile.py`) — bounded material throughput, *not privileged* as more real than the lifted layers; only more bounded.
4. **Differential** (`engine/exo/differential.py`) — endogenous market creation from ontological variance, with convex-cost suppression toward the "Combine state" limit.

It runs eight scenarios — `fold_cathedral`, `pure_lift`, `combine_state`, `drag_saturation`, `last_mile_revolt`, `scavenger_republic`, `anxiety_dampener`, `hemispherical_split` — and a drag × suppression phase-space sweep. Detailed comparison: `docs/concepts/exocapitalism.md`.

```bash
agentworld exo list
agentworld exo run fold_cathedral
agentworld exo run-all
agentworld exo sweep
```

### 3. The Atlas (`dashboard/` + `outputs/`)
An interactive web dashboard that lets you slide the smooth-striated variable, run scenarios, compare attractor basins, and read the narrative for each. Built so that Bratton (or anyone) can sit with it and *see* the parameter space.

A Cursor canvas (`review/`) provides the executive-summary view for in-IDE review.

---

## What this artifact is *not*

- **Not a forecast.** It is a tool for thinking. The numbers are stylized. The dynamics are real.
- **Not a normative argument.** Both attractors are plausible. The artifact tries to be agnostic between them and instead clarify the variable-space.
- **Not complete.** It is built to be extended. The scenarios are 15 of an obviously infinite set.

For the rules of what is and isn't claimed — which parameters are calibrated to public empirical data, which are stipulated for face validity, and which are deliberately speculative — see [`docs/concepts/epistemic_status.md`](docs/concepts/epistemic_status.md). The dashboard's §0 panel surfaces the same taxonomy.

---

## Calibrated noise + uncertainty discipline

The 2026-Q2 upgrade pass added a "calibrated noise" layer to both engines without changing any of the speculative load-bearing parameters. The four upgrades are independent and behind feature flags so existing scenarios reproduce exactly:

1. **N-seed ensembles + bootstrapped 5/95 bands.** Every scenario can be run as an N-seed ensemble; bands are bootstrapped (band-of-the-band) and persisted as Parquet so the dashboard can render median + 5/95 envelope without re-running.

   ```bash
   agentworld ensemble baroque_cathedral --seeds 64
   agentworld ensemble-all --seeds 32 --workers 4
   agentworld exo ensemble fold_cathedral --seeds 32
   agentworld exo ensemble-all --seeds 16
   ```

2. **t-copula coupled noise.** Per-pair surplus shocks (`engine/core/transactions.py`) and per-region drag wobble (`engine/exo/drag.py`) gain an opt-in `noise_model="t_copula"` that uses Student-t marginals (df=4 from Cont 2001) coupled across sectors / regions by a Gaussian copula whose correlation matrix comes from BEA 2022 input-output data and World Bank regional growth correlations. Default flips on for new scenarios; existing scenarios keep the IID Gaussian default to preserve their seed-pinned outputs.

3. **Hawkes folding cascades.** `engine/core/folding.py` gains `folding_model="hawkes"` — a vectorized self-exciting cascade that is *mean-equivalent* to the original geometric kernel at the same `folding_propensity`, but injects realistic per-depth variance and self-excitation (Bacry & Muzy 2015 endogeneity ratio).

4. **Saltelli/Sobol global sensitivity.** Replaces the OAT 7×6 alpha/capability grid with a SALib Saltelli sweep over the dozen knobs that actually move EBI / welfare / Gini, and an exo-side equivalent. First-order (S1) and total-order (ST) variance indices are reported with confidence intervals.

   ```bash
   agentworld sobol --samples 64
   agentworld exo sobol --samples 32
   ```

   The legacy phase-space basin map is kept as `agentworld sweep` for backward compatibility.

5. **Network-structured partner sampling.** `PopulationConfig` gains `network_model="scale_free"` (Barabási-Albert with the Atalay et al. 2011 degree exponent) and `"sbm"` (sector-block stochastic block model). Two new scenarios, `coasean_paradise_networked` and `baroque_cathedral_networked`, exercise the new sampler combined with the t-copula and Hawkes upgrades.

The empirical anchors live in [`engine/data/empirical_anchors.py`](engine/data/empirical_anchors.py); each constant cites its source, vintage, and scope. The dashboard's §0 epistemic-status panel reads them directly so the provenance table is visible in-page.

---

## The opposite of capitalism

In the Telegram exchange that prompted this, Bratton asked for a name for the scenario in which agents remove all disintermediation — the smooth limit. *"Endocapitalism doesn't really make sense."* Marek replied: *"It wouldn't be capitalism."*

He's right. If transaction costs go to zero, the firm — Coase's original explanandum — has no reason to exist. If the firm doesn't exist, neither does the wage relation as we know it, nor the profit motive in its standard form, nor the labor market as a market. What remains is a **continuous bilateral negotiation surface** between every pair of agents in the economy, mediated by a unit-of-account whose value depends on collective agreement and whose enforcement depends on a thin state-shaped layer underneath.

This is closer to **agentic mutualism**, or **flat-fee planetary commons**, than to capitalism. It is what Marx might have recognized as "association of free producers" — except the producers are mostly not human, and the association is mostly negotiated in the millisecond. Working name in this artifact: **Smoothworld**.

The opposite — the fractal-folded limit — has no clean name either. We call it **Baroqueworld**, after the architectural movement that took the Renaissance grid and *folded* it. (Deleuze on Leibniz: "the Baroque trait twists and turns its folds, pushing them to infinity, fold over fold, one upon the other.")

The real economy of the late 2030s is not at either pole. It is some weighted average of both, varying by sector, by jurisdiction, by stack, by the second.

---

## Reading order

For the conceptual reader:
1. This file
2. `docs/concepts/smooth_striated.md` — the variable
3. `docs/concepts/coasean_bargaining.md` — the smooth attractor
4. `docs/concepts/fractal_folding.md` — the striated attractor
5. `docs/concepts/matryoshkan_alignment.md` — the nested governance
6. `docs/concepts/parasociety.md` — the demographic substrate
7. `docs/concepts/epistemic_status.md` — what is and isn't claimed
8. `docs/scenarios/` — the 15 scenarios

For the technical reader:
1. This file
2. `engine/README.md` — engine architecture
3. `engine/core/` — the model
4. `engine/data/empirical_anchors.py` — calibrated noise structure
5. `engine/scenarios/` — the parameterizations
6. `engine/ensemble.py` / `engine/exo/ensemble.py` — N-seed ensembles
7. `engine/sensitivity.py` — Saltelli/Sobol global sensitivity (and legacy phase-space sweep)
8. `notebooks/` — the runs

For the executive reader:
1. This file
2. `review/agentworld.canvas.tsx` (open in Cursor)
3. `dashboard/` (run locally; see `dashboard/README.md`)

---

## Development

The project requires Python 3.10 or newer. On macOS, `/usr/bin/python3` may be
Python 3.9 and will not have the dev dependencies installed. Use `uv` to run
tests in the project environment:

```bash
uv run --extra dev python -m pytest engine/tests/
```

---

## Running on Linux

A copy-pasteable runbook for bringing the engine up on a fresh Linux box,
verifying it, and exercising it at non-trivial size. Times are from a 2023
Apple Silicon laptop; recent x86 Linux should land within ±2×.

### 1. Bring-up

```bash
sudo apt-get update && sudo apt-get install -y \
    python3.11 python3.11-venv git build-essential

git clone git@github.com:mpoliks/agentworld.git
cd agentworld

python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev,viz,serve]"
```

`numba` is an optional accelerator (Python <3.13 only). If wheels fail,
the engine still runs without it.

### 2. Verify (the floor)

```bash
python -m pytest engine/tests/ -v        # ~30s, expect 142/142
```

The test that matters most for trust is `test_regression_canonical.py` —
it asserts the 33 canonical scenarios reproduce their saved
`outputs/runs/*.json` baselines to within float noise. If anything else
fails, stop and investigate before running anything heavier.

### 3. Reproduce the validation artifacts

These are the numbers the brief now has to live next to. Each writes to
`outputs/validation/` and overwrites in place. Run them in order:

```bash
agentworld validate anchor                        # ~1 min
# expect: RMSE≈0.0634, MAE≈0.0612, bias≈-0.0612, worst year=2009

agentworld validate adversarial --n-evals 200     # ~10s
# expect: found_counter_example: TRUE
# best_ebi >> 10, best_welfare slightly above paradise

agentworld validate priors --samples 2000         # ~1 min
# expect: P(smooth)≈1.85%, P(mixed)≈66%, P(baroque)≈32%
# EBI quantiles p05/p50/p95 ≈ 1.58 / 3.18 / 22.34
```

For a stronger adversarial pass and a wider posterior:

```bash
agentworld validate adversarial --n-evals 1000    # ~50s
agentworld validate priors --samples 4096 --seed 7  # ~2 min
```

The committed `outputs/validation/*.json` files are the reference; your
re-runs should match basin probabilities to ~0.5pp and EBI quantiles to
~5%.

### 4. Stress runs (sizeable workloads)

Pick by how much time you want to spend.

```bash
# Full canonical run-all at default scale (~88K prototypes per scenario):
agentworld run-all --scale small --workers 4              # ~2-4 min

# Same at medium scale (880K prototypes), ~8 GB RAM:
agentworld run-all --scale medium --workers 4             # ~30-60 min

# Same at large (8.8M prototypes), ~20 GB RAM:
agentworld run-all --scale large --workers 2              # ~3-5 hr

# xlarge (88M prototypes) needs ≥32 GB RAM; usually only run on a single
# scenario for spot-checks:
agentworld run baroque_cathedral --scale xlarge

# Sobol global sensitivity sweep on the alpha-engine
# (samples × (D+2) actual sims, e.g. 64 base = 576 sims):
agentworld sobol --samples 64                             # ~5-15 min

# Sobol on the exo-engine:
agentworld exo sobol --samples 32                         # ~3-8 min

# Ensemble bands across seeds for one scenario:
agentworld ensemble baroque_cathedral --seeds 64 --workers 4   # ~5-15 min
agentworld ensemble-all --seeds 32 --workers 4                  # ~30-60 min
```

A reasonable end-to-end "solid test" in one shell:

```bash
python -m pytest engine/tests/ \
  && agentworld validate anchor --no-progress \
  && agentworld validate adversarial --n-evals 1000 --no-progress \
  && agentworld validate priors --samples 2000 --no-progress \
  && agentworld run-all --scale small --workers 4 --no-progress \
  && agentworld sobol --samples 32 --no-progress
```

Wall-clock: ~25–45 min on a modern Linux laptop. Exits non-zero on first
failure.

### 5. Live viz

```bash
agentworld serve --host 127.0.0.1 --port 8765
```

**Desktop Linux:** open `http://127.0.0.1:8765/` in a browser, pick
`productive_baroque` from the dropdown, hit *Run*. Three streaming
Plotly charts (α, EBI, real welfare/capita) update in place; the
*Fold tree* tab fills in column-by-column as steps arrive.

**Headless server:** SSH-tunnel from your laptop:

```bash
ssh -N -L 8765:127.0.0.1:8765 your-server
# then open http://127.0.0.1:8765/ locally
```

If the page loads but charts stay empty, check the browser DevTools
network tab for the `text/event-stream` response — some corporate
proxies strip SSE.

### 6. What "passing" looks like

| Check | Expected | Where it lives |
| --- | --- | --- |
| `pytest engine/tests/` | 142/142 | — |
| `outputs/validation/historical_anchor.json` | `rmse ≈ 0.063`, `bias ≈ -0.061` | A1 |
| `outputs/validation/adversarial_search.json` | `"found_counter_example": true` | A3 |
| `outputs/validation/posterior_sweep.summary.json` | `p_baroque > p_smooth × 10` | A2 |
| `agentworld run-all` | 33 scenario JSONs in `outputs/runs/` | regenerated baselines |
| Live page | `hello → step×N → done` events visible in DevTools → Network | B2/B3/B4 |

### 7. Hardware notes

| Workload | RAM | Time (small scale) |
| --- | --- | --- |
| `pytest engine/tests/` | <2 GB | ~30s |
| `agentworld validate anchor` | ~1 GB | ~1 min |
| `agentworld validate priors --samples 2000` | ~2 GB | ~1 min |
| `agentworld run-all --scale small` | ~3 GB peak | ~2-4 min |
| `agentworld sobol --samples 64` | ~3 GB | ~5-15 min |
| `agentworld run-all --scale medium` | ~8 GB | ~30-60 min |
| `agentworld run-all --scale large` | ~20 GB | ~3-5 hr |
| `agentworld run baroque_cathedral --scale xlarge` | ~32 GB | ~30-60 min |

The validation artifacts are all small-scale on purpose — a 4 GB / 4-core
VM is enough to reproduce every documented number. Scale-ups exist for
checking that aggregate behavior is stable as N rises and for
investigating per-scenario noise structure; they are not required to
trust the artifact's claims.

---

## Citing

This artifact is a companion to Antikythera's *Agentworld* research brief by Benjamin Bratton. It is not a substitute for that brief; it is a sandbox for the brief's hypotheses.

Built April 2026, in conversation between Marek Poliks and Benjamin Bratton, with Sébastien Krier's *Coasean Bargaining at Scale* (Sept 2025) and Tomašev et al's *Virtual Agent Economy* (Sept 2025) as immediate intellectual neighbors.

— *agentworld/*
