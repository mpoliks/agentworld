# Parasociety — the 100:1 Demographic Substrate

> *"100:1: A Parasociety of a Trillion Minds. ~8B humans, ~10²–10³× as many human-level agents, nested within and evolving alongside human society."* — Antikythera, *Agentworld* R&D unit, San Francisco 2026

---

## The numbers

The headline ratio in Bratton's brief is **100:1** — for every human, 100 human-level agent minds. With ~8B humans, that's 800B agents. Antikythera's marketing language sometimes rounds this to a trillion. The brief's actual number floats between ~5 × 10¹¹ and ~1.2 × 10¹².

In our model we default to 800B agents, 8B humans. The exact number doesn't change the qualitative dynamics; what matters is that the ratio is **at least one to two orders of magnitude**, because that is the threshold above which agent-to-agent (A2A) interactions dominate the social graph by simple combinatorics.

If a population has a fraction `p_A` of activity originating from agents and `p_H = 1 - p_A` from humans (where activity is weighted by autonomy, since agents act faster and more often than humans):

- `H2H` interactions = `p_H²`
- `H2A` interactions = `2 p_H p_A`
- `A2A` interactions = `p_A²`

At the 100:1 ratio with realistic autonomy weights (humans delegate ~55% of their interactions to agents, agents act ~85% autonomously), the model produces:

| Interaction type | Share |
| --- | --- |
| A2A (agent ↔ agent) | ≈ 98.4% |
| H2A (human ↔ agent) | ≈ 1.6% |
| H2H (human ↔ human) | ≈ 0.0001% |

This is the empirical confirmation of Antikythera's framing: **the most personal interactions remain between humans, but the most socially important interactions are agent-to-agent.** Almost everything that happens in this economy happens between non-human entities, even though humans are the principals.

---

## What the ratio is, and what it isn't

The 100:1 ratio is not a count of "AI deployments." It is a count of *agent identities* — discrete, individuated, principal-aligned entities that are doing things on someone's behalf.

A useful heuristic: most humans, in the late 2030s, have:

- 1 primary advocate / fiduciary agent (the Krier-style personal agent)
- 5–15 specialist agents (financial, medical, scheduling, family-relationship, civic-participation, etc.)
- 30–80 "instance" agents — short-lived, task-bound, often shared across many principals (the "delivery routing agent" handling your packages, the "neighborhood noise broker" your block uses)
- A long tail of micro-agents inside specific applications

That gets us to 50–100 agents per human as the *background level* of agentic identity. The 100:1 ratio is therefore a *floor*, not a ceiling, by the late 2030s. Bratton's brief takes the floor as the working number; Antikythera's "trillion" framing is a reasonable upper bound.

Beyond this, there are also agents that have *no human principal* — agents acting on behalf of other agents, agents managing the operations of platforms, agents running parts of the substrate. These are not counted in the 100:1, and may be a large multiple of it. The model treats them as part of the agent population by default.

---

## The parasociety, not the post-human society

The crucial framing word is **parasociety** — *para*, alongside. This is not a successor society. It is a society that exists in parallel to ours, sharing a substrate, sharing protocols, sharing units of account, but operating at a different speed and at a different granularity.

Bratton has been careful, in his Antikythera writing, to distinguish this from:

- **Post-humanism** (the agent population is on a trajectory to *replace* humans). It isn't. Humans remain the principals of the agent economy in any plausible 2030s scenario.
- **Trans-humanism** (humans are augmented to keep up with the agent population). They aren't, in aggregate; *delegation* is the dominant strategy, not augmentation.
- **Singletonism** (a single AGI takes over). It doesn't, because (per Krier) a singleton is economically inefficient relative to a vast ecology of specialized agents.

The 100:1 parasociety is the *baseline* extrapolation of the AI deployment trajectory we are already on. It is not an exotic scenario; it is the boring version. The exotic scenarios are the ones where human/agent ratios depart radically from this — singletonism, full automation of all human roles, etc. Those are tail risks; the parasociety is the body of the distribution.

---

## What it means for an economic model

Three modeling implications:

### 1. Most economic activity is invisible to humans
At >98% A2A share, the *visible* economy (the part humans actually interact with directly) is a tiny slice of the *measured* economy. Per-capita welfare is the right metric for human wellbeing; nominal GDP is the right metric for the substrate's activity level. They are now two different things.

### 2. Per-capita welfare must be measured per *human*, not per agent
This sounds obvious but matters: if you naively compute per-capita anything across the parasociety, you divide by 8 × 10¹¹, not 8 × 10⁹. Welfare per *agent* is a meaningless number. Welfare per *human* is the only one that matters.

In the model, `real_per_capita_welfare = real_welfare_cumulative / real_human_population`.

### 3. The model must support agent autonomy as a continuous variable
Not all agents act with full autonomy — some are tightly leashed to their principals, some are free-floating. The model treats autonomy as a per-prototype scalar in [0, 1], with humans typically delegating ~55% of interactions and agents typically acting at ~85% autonomy.

The **Synthetic Consumers** scenario maxes agent autonomy and minimizes human autonomy, producing the most extreme A2A-dominance regime. The **Universal Advocate** scenario keeps autonomy moderate and capability high — the more politically palatable version of the parasociety.

---

## Stratification within the agent population

A common error is to treat the 800B agents as fungible. They aren't. The model represents:

- **Capability** (≈ how good the underlying inference is)
- **Sector** (which economic domain the agent primarily lives in)
- **Stack** (which hemispherical / jurisdictional protocol family)
- **Alignment** (Matryoshka individual-layer parameter)
- **Autonomy** (delegation vs independent action)

Empirical heterogeneity in the parasociety will be at least this rich. A high-capability foundation-model agent in the North-Atlantic finance stack with high alignment and high autonomy is a *very different actor* from a low-capability instance agent in the Global South logistics stack with low alignment and bound autonomy. The economics of their interactions differ accordingly.

The most important stratification is *capability*. Capability variance directly drives wealth Gini in the model: high-capability agents capture more surplus per transaction, fold more aggressively, and accrete substrate-power. The **Public Defender** scenario explicitly compresses capability variance and shows that this is one of the strongest single Gini-compression interventions available in the parameter space.

---

## The ratio is the substrate, not the story

Bratton's *Agentworld* brief is built around the 100:1 ratio because it is the demographic fact that all the economic dynamics presuppose. But the ratio itself is *not* the dramatic event. The dramatic event is *what happens economically given the ratio*.

The two attractors — Smoothworld and Baroqueworld — are both compatible with the 100:1 parasociety. The same demographic substrate, the same population of humans and agents, can produce wildly different economies depending on the smooth/striated parameter.

This is why we treat the parasociety as a *boundary condition* of the model rather than a variable. We accept the 100:1 ratio as approximately fixed (it can be varied for sensitivity analysis, but the qualitative dynamics are stable across reasonable variations) and study the smooth/striated dimension *given* this ratio.

---

## References

- Antikythera (2026). *Agentworld* R&D unit, San Francisco 2026 — described on antikythera.org/research.
- Bratton, B. (2026). *Agentworld* research brief (forthcoming).
- Krier, S. (2025). *Coasean Bargaining at Scale*, on personalized advocate agents.
- Tomašev et al. (2025). *Virtual Agent Economy*, arXiv:2509.10147.
- Leibo et al. (2025). On the "patchwork polychrome quilt" framing of socio-technical evolution, arXiv:2505.05197.
