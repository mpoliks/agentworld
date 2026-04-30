# Scenario Atlas

Fifteen scenarios trace the smooth-striated continuum of the 800B-agent / 8B-human economy. Each is a parameterization of the engine in `engine/scenarios/__init__.py`. Run any of them with:

```
agentworld run <name>
```

…or render the full dashboard with `python engine/build_dashboard.py` and open `dashboard/index.html`.

Scenarios are presented here in approximate order along the smooth → striated axis.

---

## 1. Coasean Paradise   [α = 0.08]

The Krier limit. Near-zero transaction cost; agents are uniformly high-capability; folding is suppressed. EBI converges to ≈ 1 — every dollar of nominal GDP is a dollar of real welfare. The state shrinks toward Krier's "framework guarantor" role.

**What to look at:** the rejection-share chart shows that *individual alignment* becomes the binding constraint — almost no transactions die because they were too expensive to coordinate; they die because someone (or someone's agent) didn't want them.

**Open question:** Smoothworld concentrates power in the substrate operators. The model doesn't show this directly because we don't track substrate provider identity. But this is the regime in which "who runs the foundation models" becomes the foundational political question.

---

## 2. Universal Advocate   [α = 0.20]

Krier's vision with capability uplift everywhere. Capability variance compressed to ~0.05 SD around a high mean. Smooth-tilted: EBI ≈ 1.4, fold depth caps at 4. Welfare is high; Gini compresses.

**Why it matters:** This is the most politically *plausible* version of the smooth attractor — it does not require eliminating institutions, only ensuring everyone has access to a strong agent. Krier's "agent voucher" intervention is one path to it.

---

## 3. Public Defender   [α = 0.30]

A deliberate equity intervention: capability variance is compressed by subsidy (Sweden-style voucher model). The cost-rejection rate falls to ~0; alignment-rejection becomes dominant. Per-capita welfare is high; Gini is among the lowest in the parameter space.

**Why it matters:** This is the strongest single intervention available in the parameter space for *Gini compression without surplus loss*. If the goal is to keep the smooth attractor equitable, capability subsidy is the lever.

---

## 4. Smoothing Cascade   [α: 0.95 → 0.05 over 80 steps]

The Coasean transition. Begins as a striated regime; α decays to near-zero over time. Models a society that *successfully* uses agents to dissolve intermediation. Watch nominal GDP collapse while real welfare rises.

**Why it matters:** Most policy interest in agent economies presumes some version of this transition. The model lets you see how slow it is, how reversible, and what the EBI overhang looks like during the years when the Baroque structure is being dismantled.

---

## 5. Equilibrium Drift   [α = 0.50]

The mid-fence steady state. Both attractors pull. EBI sits around 4–5 and is sensitive to seed. The point of this scenario is to study basin-of-attraction shape; small perturbations should be able to flip the system either way.

**Why it matters:** Real economies are likely to live near α = 0.5 in some sectors. The drift dynamics here suggest those sectors are not stable on either side without active policy.

---

## 6. Compute Famine   [α = 0.40, friction floor rises mid-run]

A scenario where compute becomes scarce mid-run. Friction floor steps up from 1e-4 to 5e-2 over 20 timesteps. Models a chip war, energy crisis, or regulatory throttle on inference.

**Why it matters:** Compute is the substrate; substrate scarcity affects every layer. This is the most direct lens on what happens if the trend toward cheap inference reverses.

---

## 7. Hemispherical Schism   [α = 0.55, cross-stack compat = 0.18]

Bratton's *Hemispherical Stacks* condition: cross-stack compatibility collapses. Each stack runs its own protocols, units, alignment regimes. Cross-stack friction is severe.

**Why it matters:** Bratton is on record that *the seams between stacks are where the most interesting economic activity lives* in a multipolar agent economy. The model shows this: cross-stack arbitrage and protocol-translation become enormous sources of both real and nominal GDP. The geopolitics of Agentworld lives at the seam.

---

## 8. Matryoshka Collapse   [α = 0.45, market+individual layers gate-keep heavily]

Both market and individual alignment layers reject heavily. Total governance overhead approaches 40%. Most surplus opportunities die in the gates.

**Why it matters:** The cautionary scenario for over-engineered Matryoshka stacks. This is what happens when "alignment" calcifies into "default refusal." In the limit, the agent layer becomes useless because nothing clears.

---

## 9. NIMBY Cascade   [α = 0.40, individual-layer alignment tax = 0.06]

Krier acknowledges this risk: agent-mediated NIMBYism at unprecedented scale. Each individual's preferences become sticky and exclusive. The promise of Coasean clearance is undone by alignment-layer rejection.

**Why it matters:** Probably the most realistic *failure mode* of the smooth attractor. You give everyone an advocate; everyone's advocate is so good at protecting their principal that nothing happens. The model shows real welfare growth flatlining while the EBI rises modestly because folded sub-markets *do* still clear (they're internal to existing relationships).

---

## 10. Synthetic Consumers   [agent autonomy = 0.97, human autonomy = 0.30]

Agents not only act for humans — they consume on their own behalf. Agent autonomy is maxed; A2A interactions dominate at 98.8%+. Humans are 8B in a society where the 8 × 10¹¹ agents are doing most of the talking, trading, and valuing.

**Why it matters:** The cleanest demonstration of the parasociety dynamic. Even at moderate α, A2A dominance produces nominal/real divergence and human-legibility crash. The economy becomes legible only to itself, even without aggressive folding.

---

## 11. Recursive Simulation   [α responds to EBI; sigmoid takeoff]

α drives itself. As the measurement of "Baroqueness" rises, α rises in response (positive feedback). The model implements this as a precomputed sigmoid schedule, but the dynamic is the point: small initial differences in protocol design amplify rapidly into a Baroque take-off.

**Why it matters:** This is the Antikythera *recursive simulation* concept put to work — the simulation affects what it simulates. It suggests that the Smoothworld/Baroqueworld choice is *path-dependent* and that whichever attractor wins the early years locks in by the time anyone notices.

---

## 12. Fold Avalanche   [α: 0.05 → 0.95 over 80 steps]

The mirror of Smoothing Cascade. Starts smooth, ends striated. Models a society that progressively institutionalizes agent-mediated intermediation. Watch the take-off point — the inflection where folding starts overwhelming direct exchange — and the legibility crash.

**Why it matters:** The clearest visualization of *non-linear take-off*. The transition is not gradual. Once propensity > some threshold, folding rapidly dominates.

---

## 13. Slop Market   [α = 0.85, low capability]

High α plus *low* capability. Folding happens recursively but the underlying economic activity is low-quality. Pure nominal-GDP inflation; real welfare collapses to the lowest in the parameter space.

**Why it matters:** *Probably the default outcome if capability lags behind protocol design.* This is what happens if the protocol stack is built before agents are good enough to use it well. EBI explodes; per-capita welfare crashes; the agent stack is busy without being useful. The artifact's bleakest scenario, and arguably the one closest to where we are right now in 2026.

---

## 14. Baroque Cathedral   [α = 0.92, high capability]

The Bratton limit. Aggressive folding with high capability. EBI reaches into the thousands. Per-capita welfare *modestly* lower than smooth attractors — Baroqueworld is not necessarily welfare-poor; it is welfare-illegible. The folded canopy *does* produce some real surplus; it also produces a lot of nominal volume that has no welfare correlate.

**Why it matters:** This is Bratton's hypothesis instantiated. The interesting finding: per-capita welfare does not collapse the way intuition might suggest. Baroqueworld is a *plausible*, even *prosperous*, equilibrium — it just doesn't look like one to a human auditor. *The economy becomes legible only to itself.*

---

## 15. Exo-Baroque Singularity   [α = 0.97, max depth = 10, branching = 5]

The asymptotic stress test. Folding limits unlocked: EBI ≈ 6 × 10⁶. Useful for verifying that the model behaves sensibly at the limit, and for estimating where the practical ceiling is.

**Why it matters:** Mostly diagnostic — this scenario is not a forecast. It tests whether the dynamics remain bounded under aggressive recursion (they do), and serves as the right-hand anchor of the atlas.

---

## How to use the atlas

The atlas is designed for **comparison**, not for picking a winner. The two most useful comparisons:

1. **Coasean Paradise vs Baroque Cathedral** — the Krier vs Bratton axis, holding capability roughly constant.
2. **Baroque Cathedral vs Slop Market** — the *capability* axis, holding striation roughly constant. Same protocol stack, very different outcomes.

A third interesting comparison:

3. **Universal Advocate vs Synthetic Consumers** — both are smooth-tilted, but one keeps humans in the loop while the other lets agents act independently. Same α, very different parasocieties.

The dashboard supports all of these via the multi-select `compare` panel.

---

## What's missing

- **Spatial dynamics**: the model treats the population as a well-mixed prototype set. Real geographic / network heterogeneity is not represented.
- **Agent learning**: capability is a fixed prototype attribute; no in-simulation training.
- **Endogenous protocol design**: the smooth/striated parameter is exogenous. A v2 model would let agents *choose* α through their fee structures.
- **Ecological externalities**: no carbon, water, or land budget. The "ecology" half of "economy and ecology" is conspicuously absent. Worth adding.
- **Crisis dynamics**: no shocks, contagion, or systemic-risk dynamics. The model is steady-state.

These are good directions for v2. They are not blockers for the conceptual brief.
