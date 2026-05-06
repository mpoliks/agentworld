# Agentworld dashboard – editable copy

Every visible string on the dashboard lives in this file — including the per-scenario card labels and descriptions in §3 / §4. Edit the prose below, send it back, and I'll rebuild the HTML template (`dashboard/index.html`) and sync `SCENARIO_LABELS` (in `engine/build_dashboard.py`) and `SCENARIO_DESCRIPTIONS` (in `engine/scenarios/__init__.py`) so the changes survive the next dashboard rebuild. **Section headings (H1 / H2 / H3) are load-bearing** — keep their structure exact so I can match each block to its slot. Inside each block, rewrite freely.

## Conventions

- `**bold**` → bold
- `*italic*` → italic
- Unicode renders as-is: `α`, `×10⁶`, `≈`, `→`, `↔`, `–` (en-dash), etc.
- LaTeX inside `$ … $` (inline) and `$$ … $$` (display) renders via KaTeX — preserve the delimiters.
- `<code>foo</code>` becomes inline monospace; `<b>` and `<i>` are also accepted inline if you need them mid-sentence.
- Blank line between paragraphs.
- Anything in `[brackets]` is a directive to me, not visible text.
- Some blocks are short (one line); some are paragraphs. Either is fine.
- In **§3 SCENARIO CARDS**: each scenario is keyed by an `H2` heading whose text is the *slug* (e.g. `coasean_paradise`). **Do not change the slug** — it's the lookup key in the codebase. The `**Label:**` line is the display name on the card; the `**Description:**` paragraph is what fills the card body and the §4 active-scenario description.

---

# HEADER

## Super line (small-caps strip above the title)

Antikythera × Disintegrator · companion artifact

## Title (line 1 / italic line 2)

Agentworld
*An atlas of agentic macroeconomics*

## Lead paragraph

A Monte Carlo sandbox for a planetary economy composed of **8 billion humans** and **800 billion AI agents** (it's worth 100xing that latter figure in future work). This atlas primarily isolates one variable through twenty-five scenarios: at one limit, agents *dissolve* economic intermediation (transaction barriers fall and middle layers thin out), and at the other, agents *fractally multiply* economic intermediation — every trade spawns sub-trades on top of itself. Both limits are stable equilibria of the same underlying technology, and which one materializes in reality is an open question. What this dashboard offers is a sample of distributions across the variable space between them.

## Meta chips (one per line, four chips total)

- 25 scenarios
- 66K importance-weighted prototypes per scenario
- 200 steps · 200K prototype pairs sampled per step
- 1 step ≈ 1 quarter · e.g. 2026 → 2076

---

# §1 INTRODUCTION

## Section title

Introduction

## Section sub

A working-paper exposition of what this dashboard is and what is being computed. Every chart from §2 onward presupposes the definitions developed here.

## Opening — the question

**What does the planetary economy do when the population of economic actors expands, within a few years, from roughly eight billion humans to roughly eight billion humans plus eight hundred billion AI agents?** If anything, eight hundred billion is an underestimation: the inference cost of a capable agent is now within an order of magnitude of the cost of the electricity that runs it, and the rails for high-frequency, sub-cent, autonomous payments are being laid as this is written — but it's a nice starting point. The real question is what regime of *intermediation* a hundred-to-one ratio of agents to humans selects for. Two regimes are equally consistent with the underlying technology. In the first, agents act as a kind of economic solvent: they evaporate transaction costs, dissolve middle-layer firms whose entire value-add was coordination, and flatten the economy into a continuous bilateral surface. In the second, agents act according to exocapitalist principles: every existing market spawns sub-markets, every sub-market spawns sub-sub-markets, and a single delivery to a human's door eventually involves thousands of priced micro-transactions that no human ever sees. We do not know, in 2026, which of these will materialize, in what proportion, in what sectors. The artifact you are reading is an attempt to clarify what each regime would cost, and what diagnostics one would need to tell which regime one is in before it is too late to intervene (good luck).

## Opening — methodology

The work is pretty modest. It runs a vectorized agent-economy simulator across twenty-five named scenarios that bracket the variable space, and reports a small set of summary statistics in a way that is pretty honest about the speculative load each parameter carries. It's best to think of this as less of a forecast and more of a controlled exercise in *what would have to be true* for this metric to behave that way under that regime. The hope is that a reader can sit with the atlas in §2, scrub through the scenarios in §3, and develop intuitions about a parameter space that is otherwise too large and too unfamiliar to reason about by hand.

### 1.1 Core metric

The most important metric here is a scalar $\alpha \in [0, 1]$. $\alpha$ is a proxy for the degree to which trades in the economy are allowed to spawn further trades on top of themselves. At $\alpha = 0$ every exchange is one direct exchange — a buyer and a seller meet, agree, and the value moves; nothing intermediates. At $\alpha = 1$ every base exchange routes through layers of derivative sub-trades, fees, repackaged rights, attention markets, and metadata markets, each one adding overhead and each one (potentially) priced as a "real" economic event by national-accounts standards. Our current economic world sits somewhere in the middle, varying by sector and jurisdiction.

## Figure 1 caption

**The smooth-striated continuum.** The single parameter $\alpha$ is a proxy for the depth and rate at which a base trade is allowed to spawn derivative sub-trades. $\alpha$ enters the engine in two places: it raises the per-trade transaction cost by a small additive term (so highly striated economies are also slightly more expensive per base trade), and it raises folding propensity as $\alpha^{1.4}$, so the cascade depth grows super-linearly as $\alpha \to 1$.

### 1.2 What the simulator is

We are modeling off of a population of $H = 8 \times 10^{9}$ humans and $A = 8 \times 10^{11}$ AI agents, represented through importance-weighted prototypes ($\approx 6.6\text{M}$ sampled prototypes carry the full population's mass). At every step of a two-hundred-step run, the engine draws on the order of $2 \times 10^{5}$ random pairs of trading partners. For each pair it asks four questions in sequence: would this trade create surplus; what would it cost; would any of the three governance filters block it; and, if it does execute, does it spawn a folding cascade of sub-trades on top of itself. Surviving trades transfer wealth between the parties and accumulate into the run-level aggregates that the rest of this dashboard plots.

## 1.2 — type asymmetries paragraph

Human and agentic activities are processed through the same trade engine — the matching, the surplus computation, the filters, and the fold rules are type-blind once a pair has been drawn. *Type* matters only at three points: which prototypes get drawn into pairs (population mass and the trade-rate multiplier discussed below), how the prototypes are seeded (capability, autonomy, alignment, wealth all sample from different distributions), and how their resulting surplus maps to welfare downstream (per-capita welfare divides by humans only, and a "demand-modulation" mode in some scenarios further discounts pure agent-to-agent surplus). That being said, agents and humans do not behave the same (further work can be done here to turn this work into its own set of modulable variables):

## 1.2 — asymmetry list

- **Population mass.** $A / H = 100$ agents per human at the demographic level. Most random pairings are A2A.
- **Trade speed.** An AI agent can attempt thousands of trades in the time a human attempts one. In the fractal-trade scenarios we model this with a trade-rate multiplier $\rho_{\text{agent}} = 100$ on top of the demographic ratio, so humans appear in roughly $1$ in $10{,}000$ executed trades. In smooth-limit scenarios $\rho_{\text{agent}} = 1$ — which proposes a counterfactual world in which agents trade at human speed.
- **Wealth.** Human wealth is lognormal with $\bar{w}_H \approx 100$ per prototype; agent wealth is Pareto-tailed with $\bar{w}_A \approx 5$. Agents are individually poorer but collectively far wealthier.
- **Capability.** Agent capability $c_A \sim \mathcal{N}(0.72,\, 0.20^{2})$; human capability $c_H \sim \mathcal{N}(0.45,\, 0.18^{2})$. Agents on average bring better matching, pricing, and execution to any trade they enter.
- **Autonomy and alignment.** Agents act independently $\approx 85\%$ of the time on average, humans $\approx 55\%$; human alignment values are spread wider ($\sigma_{H} \approx 0.45$) than agent values ($\sigma_{A} \approx 0.25$), so a human-touching pair is more likely to fail the alignment filter than a pure agent-agent pair.

### 1.3 How a single trade resolves

The decision a pair $(a, b)$ faces, on every step, is whether the surplus it could generate exceeds the cost of generating it, and then whether the three Matryoshka governance filters — law, market, individual alignment — let it through. Let $c_a, c_b \in [0,1]$ denote the parties' capabilities, $s_{ab} \in [0,1]$ the cosine compatibility of their sectoral profiles, and $v$ the base match volume. Surplus is a capability-weighted match score with an additive noise term:

## 1.3 — equation 1 (surplus)

$$
S_{ab} \;=\; v \cdot \Bigl(\, 0.05 \;+\; 0.5\, c_a\, c_b\, s_{ab} \;+\; \varepsilon \,\Bigr),
\qquad \varepsilon \sim \mathcal{N}(0,\, 0.05^{2}) \tag{1}
$$

## 1.3 — gloss on equation 1, intro to cost

where $\varepsilon$ is Gaussian by default; an opt-in Student-$t$ copula calibrated to BEA 2022 input-output correlations is available in the calibrated-noise scenarios. Cost is the sum of a hard friction floor $\varphi_0$, a Coasean term controlled by an exponent $\kappa$ that rewards the better-matched pair, an $\alpha$-dependent striation term, and a cross-stack penalty in the compatibility $\sigma_{ab} \in [0,1]$:

## 1.3 — equation 2 (cost)

$$
C_{ab} \;=\; \varphi_{0}
\;+\; \varphi_{1}\,\bigl( 1 - \min(c_a, c_b) \bigr)^{\kappa}
\;+\; 0.020\, \alpha \,\bigl( 1 + 0.3\,(1 - \sigma_{ab}) \bigr)
\;+\; 0.015\,(1 - \sigma_{ab}) \tag{2}
$$

## 1.3 — clearing rule, intro to filters

The trade clears iff $S_{ab} \geq C_{ab}$ *and* none of the three filters reject it. Each filter invokes a Bernoulli with probability that scales with relevant disagreement, like cross-stack incompatibility for the law layer, sector mismatch and alignment distance for the market layer, or alignment distance attenuated by autonomy for the individual layer. We use $\Delta_{ab}$ for the alignment distance and $u_{ab}$ for the mean autonomy of the pair:

## 1.3 — equation 3 (filters)

$$
\begin{aligned}
\Pr(\text{law reject})    \;&=\; 0.01 \;+\; 0.04\,(1 - \sigma_{ab}) \\
\Pr(\text{market reject}) \;&=\; 0.02 \;+\; 0.06\,(1 - s_{ab}) \;+\; 0.04\, |\Delta_{ab}| \\
\Pr(\text{align reject})  \;&=\; 0.03 \;+\; 0.20\, |\Delta_{ab}|\,\bigl( 1 - 0.5\, u_{ab} \bigr)
\end{aligned} \tag{3}
$$

## 1.3 — bookkeeping closing paragraph

A trade rejected by any one of the three contributes nothing to either nominal GDP or real welfare; a trade that clears contributes $S_{ab}$ to the real-welfare ledger and $S_{ab} + C_{ab}$ to the nominal-GDP ledger, and is then handed to the folding operator.

## Figure 2 caption

**The per-step trade pipeline.** We pick a pair, compare surplus against cost (eqs. 1–2), push through three independent governance filters in sequence (eq. 3), and the surviving trade contributes simultaneously to two ledgers — the welfare ledger ($S_{ab}$ only) and the nominal-GDP ledger ($S_{ab} + C_{ab}$, plus everything the folding cascade adds). 

### 1.4 The folding operator

Folding is the mechanism that lets the nominal ledger run away from the welfare ledger. When a base trade clears, the engine considers whether to spawn derivative sub-trades on top of it — a derivative on the trade, then a derivative on the derivative, and so on, up to a per-scenario maximum depth $D$. Let $p_{0}$ denote the scenario's base folding propensity. The propensity to fold at depth $d$ depends on $\alpha$ and decays geometrically:

## 1.4 — equation 4 (per-depth propensity)

$$
p_{d} \;=\; p_{0}\;\cdot\;\alpha^{1.4}\;\cdot\;0.85^{\,d - 1},
\qquad d = 1, 2, \ldots, D \tag{4}
$$

## 1.4 — bookkeeping intro to equation 5

At each depth, the cascade branches by a factor $\beta(\alpha) = \beta_{0}\,(0.6 + 0.4\,\alpha)$ that itself rises with $\alpha$ (deeper economies are also wider economies), each layer is amplified by a nominal multiplier $m$, and each layer adds to the nominal ledger while shaving a small fraction off the real ledger. The default kernel is geometric and deterministic at the layer level; we use an opt-in Hawkes self-exciting kernel to preserve the same mean but inject realistic per-depth variance and self-excitation calibrated to the Bacry & Muzy 2015 endogeneity ratio. Writing $N_{d}$ for the nominal contribution and $R$ for the base real surplus of the trade, with $\eta = $ <code>fold_real_efficiency</code> $< 1$, the per-depth bookkeeping is:

## 1.4 — equation 5 (per-depth ledgers)

$$
\begin{aligned}
N_{d}      \;&=\; N_{d-1}\;\cdot\;\beta(\alpha)\;\cdot\;m\;\cdot\;p_{d}, \\
L_{d}      \;&=\; R\;\cdot\;\bigl( 1 - \eta^{\,d} \bigr)\;\cdot\;p_{d}, \\
\Delta\text{Nominal} \;&=\; \sum_{d=1}^{D} N_{d}, \qquad
\Delta\text{Real} \;=\; -\,\max_{d}\, L_{d}.
\end{aligned} \tag{5}
$$

## Figure 3 caption

**A folding cascade.** A base trade (gold, depth $0$) spawns sub-trades that themselves spawn sub-trades, governed by $\alpha$ and the per-depth branching factor $\beta(\alpha)$. The right margin tracks the additive contributions $N_{d}$ to the nominal-GDP ledger; the left margin tracks the real-welfare ledger, which is bounded by the base surplus $R$ and erodes by a factor $\eta < 1$ at each layer. In a low-$\alpha$ scenario the cascade rarely makes it past depth $0$ or $1$ and the two ledgers track each other. In a high-$\alpha$ scenario the cascade sustains itself across many layers and the nominal ledger separates from the real ledger by orders of magnitude.

### 1.5 The diagnostics that follow from the model

The whole point of carrying both ledgers is to take their ratio. Let $\mathcal{T}_{t}$ denote the set of trades that cleared at step $t$. Real welfare and nominal GDP accumulate as

## 1.5 — equation 6 (cumulative ledgers)

$$
W \;=\; \sum_{t}\,\sum_{(a,b)\in\mathcal{T}_{t}} S_{ab},
\qquad
G \;=\; \sum_{t}\,\sum_{(a,b)\in\mathcal{T}_{t}} \bigl( S_{ab} + C_{ab} + \Delta\text{Nominal}_{ab}\bigr).
\tag{6}
$$

## 1.5 — definition of EBI

The dashboard's central diagnostic is the **exo-baroque index** (exo from exocapitalism, baroque from Deleuze, basically just meaning how insane of a meta-meta-meta-deriviative stack exists on top of any given trade). It's defined as the ratio of these two ledgers:

## 1.5 — equation 7 (EBI)

$$
\mathrm{EBI} \;=\; \frac{G}{W} \;=\; \frac{\sum_{t} \text{nominal\_GDP}_{t}}{\sum_{t} \text{real\_welfare}_{t}}. \tag{7}
$$

## 1.5 — gloss on EBI

$\mathrm{EBI} = 1$ is the parity level (no ficticious capital), meaning that every unit of measured economic activity reached a human as actual consumption. $\mathrm{EBI} = 100$ means $99\%$ of measured activity was trades-of-trades that never delivered anything to a human. $\mathrm{EBI}$ in the low millions, which a few of the high-$\alpha$ scenarios do reach, means the on-paper economy and the consumed economy live on different planets. $\mathrm{EBI}$ is plotted on a log scale because it ranges over six orders of magnitude across the scenario set. Because it is a ratio, $\mathrm{EBI}$ is dimensionless and scenario-comparable; absolute values of the underlying ledgers are not.

## 1.5 — EBI and welfare are partially decoupled

A subtlety worth flagging here, because one of the conclusions in §2 turns on it: $\mathrm{EBI}$ and absolute per-capita welfare are not the same diagnostic and can move in different directions. A regime with $\mathrm{EBI} = 10^{6}$ — most of the on-paper economy is parasitic accounting that no human consumed — can still produce substantial per-capita welfare, because the on-paper economy being printed is enormous and even a tiny share of it reaching humans is a sizeable absolute amount. *Productive Cathedral* in the scenario set carries both attributes: high $\mathrm{EBI}$ (parasitic share dominant) and high per-capita welfare (the small productive share is large in absolute terms). Two readers asking different questions of the same economy — *are people materially better off?* and *is the economy connected to anything humans experience?* — can come to opposite conclusions and both be right. $\mathrm{EBI}$ is the diagnostic for the second question; per-capita welfare is the diagnostic for the first; neither subsumes the other.

## 1.5 — downstream quantities, intro

The other quantities the dashboard plots are downstream of the same ledgers, and are introduced briefly here so that the charts in §4–§7 read without reference back. **Real welfare** $W$ is the sum, across the run, of the surplus that survived the filters; **per-capita welfare** divides that by $H = 8 \times 10^{9}$ humans only, since agent surplus that never benefits a human does not count as welfare on this dashboard:

## 1.5 — equation 8 (per-capita welfare)

$$
w \;=\; \frac{W}{H} \;\cdot\; 10^{3} \qquad \text{(unitless; scaled for legibility)}. \tag{8}
$$

## 1.5 — quantities continuation, intro to legibility

*Compare scenarios by ratios, not absolute values.* **Nominal GDP** $G$ is the sum of cleared $(S + C)$ plus everything the folding cascade contributed. **Fold depth** is the height of the tallest derivative tower seen in any single base trade in a step — depth $0$ means no sub-trades happened, depth $7$ means a base trade had a seven-layer stack of derivatives wrapped around it. **Human legibility** $\ell$ is the share of executed trades in which at least one party is a human, equivalent to one minus the agent-to-agent share:

## 1.5 — equation 9 (legibility)

$$
\ell \;=\; \pi_{\text{H2H}} + \pi_{\text{H2A}} \;=\; 1 - \pi_{\text{A2A}}. \tag{9}
$$

## 1.5 — closing on quantities

$\ell$ is a measure of how much of the economy a human can in principle observe, contest, or audit at last-mile resolution; it sits around $\ell \in [10^{-3},\,3 \times 10^{-2}]$ in smooth scenarios and falls to $\ell \in [10^{-5},\,10^{-4}]$ in fractal scenarios with the $\rho_{\text{agent}} = 100$ multiplier on. **Wealth Gini** is the standard $[0, 1]$ inequality measure across the combined human-and-agent population. The **three filters** — law, market, alignment (eq. 3) — are reported in §4 as rejection-rate decompositions, so the reader can see which institutional layer is doing the most blocking under each scenario.

## 1.5 — uncertainty bands paragraph

Every chart from §2 onward is drawn as a *solid line* at the median across $N = 64$ random seeds with a *shaded band* covering the $[P_{5},\, P_{95}]$ envelope. The band shows how much randomness within a fixed scenario configuration could shift the result. A wide band means the scenario is sensitive to noise; a tight band means the outcome is robust under fixed assumptions. *The band is not a probability that the world will land in this range* — it is just a sensitivity reading on the simulation under fixed parameters.

### 1.6 What we are trying to settle

Our goal is pretty narrow and specific: to produce a usable atlas of the parameter space inside which the next decade of mechanism-design choices about the agent economy will be made. We are not arguing that any one of the twenty-five scenarios is the world that will arrive, but we are arguing that the *shape* of the trade-off — that high $\alpha$ produces high nominal GDP and low welfare share, that the middle of the $\alpha$ range is the default landing spot in the absence of active mechanism design, that $\mathrm{EBI}$ is the diagnostic that distinguishes "the economy got bigger" from "the economy got more legible to itself and less to us" — is robust across plausible parameterizations of the model, and is therefore worth taking seriously as a frame for policy thinking.

## 1.6 — note on simulation method

One interesting note on simulation method before we dig into a few conclusions. Twenty-one of the twenty-five scenarios on this dashboard run on a pretty complex simulation stack — sector-block trading network calibrated to Atalay et al. 2011, t-copula correlated noise calibrated to the BEA 2022 input-output matrix, and a self-exciting Hawkes folding kernel calibrated to the Bacry & Muzy 2015 endogeneity ratio. Boom. The four exceptions to that rule are the productive-folding scenarios (*Productive Cathedral*, *Productive Baroque*, *Derivatives Revolution*) and one adversarial-search variant (*Baroque (High Welfare)*) whose hand-tuned parameters don't make sense in that context. This means that when you compare *Slop Market* to *Productive Cathedral* across the high-$\alpha$ band, the only meaningful difference is productive folding. When you compare *Coasean Paradise* to *Baroque Cathedral*, both are using the same engine. Welfare numbers on this dashboard are systematically higher than they would be on a well-mixed default — by roughly 60% across the board — because realistic trading networks pre-match compatible pairs, raising matching efficiency. But it's super important to note that this simulation engine pretty much just changes the welfare height the basins can support, but not which basin the scenario is in. 

## 1.6 — six-points trailer

The six conclusions the simulator keeps surfacing, across scenarios and seeds, are enumerated in the callout in §2. In short: *(i)* direct-trade regimes (e.g. Coarsen bargaining) are unstable on their own — staying there is an active engineering task, not a passive default; *(ii)* productive sub-markets raise welfare in absolute terms but do not move the share of measured activity that reaches humans, so $\mathrm{EBI}$ and welfare can both come out high in the same regime; *(iii)* a targeted tax on agent-to-agent transaction volume is the one corrective lever the simulator finds, and it is bounded by the share of nominal activity that would have produced welfare if not deterred; *(iv)* wealth inequality moves only when bargaining power is equalized before trades happen, not by post-trade redistribution; *(v)* the share of the economy that any human is party to collapses with $\alpha$ independently of welfare, raising a separate concern about democratic legibility; and *(vi)* even when agents are free to learn their own preferred $\alpha$, they settle at upper-mid $\alpha$ rather than at either extreme. The atlas in §2 makes (i) and (ii) visible at a glance. The detail panes in §4, the §5 Sankey, and the §6 overlays make the rest legible.

## 1.6 — aside ("what the artifact is not")

Again, this is not a forecast — the numbers are stylized and the parameters are explicitly bracketed in the form of scenarios. This also isn't a normative argument; both poles are plausible and the artifact tries to be agnostic about them. This is also not complete; the twenty-five scenarios are samples from an obviously infinite set, and the model itself privileges last-mile material consumption as the welfare denominator in a way that the companion exo-engine deliberately rejects. For the rules of what is and is not claimed — which parameters are calibrated to public empirical data, which are stipulated for face validity, and which are deliberately speculative — the epistemic-status panel in <code>docs/concepts/epistemic_status.md</code> and the empirical-anchor table at the foot of this page are better authoritative references.

---

# §2 THE ATLAS

## Section title

The atlas

## Section sub — what the chart is

Each point is one scenario at its terminal step. The **x-axis** is α — how complicated trades are allowed to get, on [0, 1]. The **y-axis** is the exo-baroque index (EBI) — nominal GDP divided by real welfare, log-scaled. **Color** encodes per-capita real welfare; greener is better. The dashed line at EBI = 1 represents parity where every unit of measured economic activity matched a unit of human welfare. Anything sustained above that line is measured activity the human side of the economy never received — accounting that lives only in agent-to-agent ledgers.

## Section sub — what to read off the chart

**What to read off the chart.** Bottom-left: low α, no folding, accounting tracks welfare. Top-right: high α, recursive folding, accounting separates from welfare by orders of magnitude. A point that sits high on the y-axis *and* dim in color is a kind of failure case as far as human experience goes – a regime printing volume without producing anything humans consume. 

## Atlas chart title

α × exo-baroque index · color = per-capita welfare

## Atlas chart caption

**Dashed horizontal:** EBI = 1 – the parity line where welfare equals nominal GDP. **Color** is per-capita welfare scaled by 10³ (model state is unchanged; the scaling exists so values like Coasean Paradise ≈ 279 and Slop Market ≈ 25 are legible at a glance instead of collapsing into the raw per-capita figures around 0.28 and 0.025). Hover any point for the scenario label, exact α, EBI, and welfare.

## Callout — opening framing

The right-hand limit — the **fractal-trade economy**, where every base trade spawns layers of derivative sub-trades — is at least as plausible as the left-hand limit, and is where the on-paper GDP gains in the late 2020s and 2030s will plausibly come from. *Coasean Paradise* sits in the bottom-left (everything is a direct trade). *Exo-Baroque Singularity* sits in the top-right (everything is folded into towers of sub-trades). Real economies are a weighted blend of the two, varying by sector and jurisdiction. *The atlas does not predict where any given regime lands. It clarifies what landing somewhere costs.*

## Callout — what the atlas does not show

**What the atlas does not show.** These terminal-step snapshots compress twenty-five trajectories into twenty-five dots. Two scenarios can land at the same coordinate by very different routes – a slow drift through the mid-α basin reads identically to a fast climb that overshoots and falls back. §4 unfolds each path as a six-chart panel; §5 stacks any subset of paths on a shared time axis so the route, not just the destination, becomes clear.

## Callout — what this means for decisions (six conclusions)

**What this means for decisions.** Six conclusions fall out of the scenario set, in order of how load-bearing they are.

**(1) The direct-trade regime is unstable on its own.** The economy's direct-trade regime — where every transaction is a single observable exchange between two parties, with no derivatives or sub-markets stacked on top — does not hold itself in place. Whenever we let agents themselves decide how much to spawn sub-trades on the back of an existing trade, and we make that decision responsive to what they observe in the rest of the economy, the system collapses out of direct trade in roughly twenty steps (about five years on this clock). Two scenarios on the dashboard, *Recursive Simulation* and *Endogenous Baroque*, set this up explicitly: agents become more willing to spawn sub-markets the more sub-markets they see around them. Both slide into the layered, hard-to-audit regime quickly, regardless of where they start. The implication is that staying in the direct-trade regime requires active engineering, not just choosing not to intervene. Concretely: caps on how many derivative layers can stack on top of any base trade; a price floor on every transaction so the cheapest sub-trades can't exist; the right of individuals to veto trades on values grounds even when those trades would be profitable; a targeted tax on agent-to-agent transaction volume; *and* a contract-enforcement layer that can handle eight billion humans plus eight hundred billion agents at once. The popular reading of the direct-trade regime as a "shrunken state" — a libertarian default — is super off-base because direct trade is the harder thing to engineer, not the easier one.

**(2) Making sub-markets useful raises welfare in absolute terms but doesn't restore the human share of measured activity.** When sub-markets layered on top of a base trade do real economic work — a derivative that's a genuine risk-pooling mechanism, a sub-market that's a genuine price-discovery mechanism, a layered trade that's a genuine liquidity transfer between parties who both benefit — the dashboard calls this *productive folding*. When sub-markets are pure overhead — fees stacked on fees, attention markets feeding metadata markets feeding rights markets, with nothing being delivered to a person at the end — the dashboard calls this *parasitic folding*. Real economies have both, in some proportion, and one of the things the simulator tries to clarify is what happens when you tilt that mix toward productive. The finding is more split than first impression suggests: productive folding *does* raise welfare, meaningfully. *Productive Cathedral* — high-α with the productive setting turned all the way up, on a realistic trading network with calibrated noise from US input-output data and self-exciting cascade dynamics drawn from financial-market data — produces the highest per-capita welfare in the entire high-α band of the atlas. The on-paper economy it prints is enormous; even a tiny share of it reaching humans is a substantial absolute amount of welfare. So if the question you bring to the simulator is *are people materially better off?* — productive folding helps, even at high α. What it does not do is move the share of measured activity that reaches humans. Roughly 99.99% of nominal GDP in *Productive Cathedral* still goes to agent-to-agent ledgers that no human consumes (the §5 Sankey shows this directly). EBI stays in the high band. So if the question you bring is *is the economy connected to anything humans experience?* — productive folding doesn't fix that. The absolute volume reaching humans grows because the volume *being printed* is enormous; the *fraction* that reaches them stays microscopic. The deeper implication is that EBI and welfare are partially decoupled diagnostics. A regime can score well on welfare and poorly on EBI at the same time, because absolute welfare scales with the size of the on-paper economy while the share-of-GDP reaching humans is a separate quantity that depends on the cascade structure. Two readers asking different questions of the same economy — *are people better off?* vs *can the population see the economy that nominally runs on its behalf?* — can come to opposite conclusions about *Productive Cathedral* and both be right. 

**(3) A targeted tax on agent-to-agent volume is the one corrective lever the simulator finds, and it's bounded by its own tax base.** A *Pigouvian tax* is a tax aimed at an activity that imposes a cost the rest of the economy pays for, but which doesn't show up in the activity's own price — the textbook example is a carbon tax. Here, the cost being paid is parasitic accounting: agent-to-agent transaction volume that no human ever consumes but which the rest of the economy's measurement systems treat as economic activity. Two scenarios run different versions of this lever. *Pigouvian Heavy* taxes 35% of all agent-to-agent transaction volume — both base trades and the volume the cascade spawns on top of them — and recycles the revenue back to humans, weighted toward the lower deciles. The result, at α≈0.6, is that EBI lands 25–30% below what it would be in the same configuration with no tax. Welfare doesn't crash. *Pigouvian Friction* is the same idea routed differently: a 15% tax recycled as a subsidy on the friction cost of any human-touching trade, which brings humans back into the economy through the supply side rather than as a cash transfer. The constraint that bounds them is sneaky and worth understanding directly. The tax is collected on volume, but its corrective effect — the part that lowers EBI rather than just transferring money around — depends on the share of that volume that *would have* become real surplus if the tax hadn't deterred it. In deep baroque regimes most of the activity being taxed wasn't going to produce welfare anyway, so the deterrence has nothing to grab onto. The parasitic Sankey ribbon dominates, the surplus-bearing share is small, and you can't compensate for that with a higher rate — past a certain point, raising the rate just stops the part of the activity that *would have* been productive, leaving the parasitic ribbon to fill the space. The §5 Sankey is the place to read this off of: the ribbon labeled "recycled (Pigouvian)" can only get as thick as the surplus-bearing slice of the nominal flow, no matter how aggressively the rate is set.

**(4) Wealth inequality moves at the source, not after the fact.** The wealth Gini — the standard 0-to-1 inequality measure (0 = perfectly equal, 1 = one party owns everything) — moves in this simulator only when the asymmetry that produced the inequality in the first place is removed before the trades happen. *Universal Advocate*, the only scenario in the set that meaningfully compresses the Gini, raises agent capability across the entire population: every household, regardless of starting wealth, gets the same level of representation in any trade negotiation. The wealth distribution flattens because the bargaining-power gap that previously compounded across deciles has been closed at the source. The two contrast scenarios fill in the picture. *Public Defender* runs a more politically tractable version of the same idea: capability uplift targeted only to the lower deciles, leaving the upper deciles where they were. The Gini compresses, but less than under universal access — targeted access doesn't reach the asymmetry that produces inequality in high-skill matchups. *Pigouvian Heavy* runs the opposite intervention: leave bargaining power where it was before any trades happened, and instead tax agent-to-agent volume after the fact, recycling the revenue to humans with progressivity baked into the recycling. The EBI moves. The Gini doesn't. Distributional outcomes in this model are determined by who has bargaining power *before* the trade engine runs, not by transfers *after* it has run. The implication for policy is the unfashionable one: post-trade redistribution can move how much money is in whose hands, but it does not move the shape of the distribution that comes out of the trade engine itself. Gini compression has to happen upstream.

**(5) Even when welfare is high, the share of the economy any human is party to collapses with α.** The dashboard tracks a third diagnostic alongside EBI and welfare, called *human legibility*: the share of executed trades in which at least one party is a human. In direct-trade scenarios this sits between 0.1% and 3% — already small, because there are a hundred agents for every human just by counting. In fractal scenarios with realistic agent trade speed (one human-paced step for every hundred agent-paced trades), it falls another two orders of magnitude, to between one in a hundred thousand and one in ten thousand executed trades. Welfare and EBI tell you *whether* the economy is reaching humans. Legibility tells you whether humans can *see* the economy at all — whether there is any single trade that a specific person was party to and could in principle audit, contest, or remember happening. This number falls with α regardless of whether the cascade is productive or parasitic, and regardless of where welfare lands. *Productive Cathedral*, the scenario from conclusion 2 with high welfare and high EBI, has very low legibility — the high welfare reaches humans through statistical aggregates, not through trades that any specific person was on either side of. The implication for democratic accountability is direct: in the high-α scenarios, the economy is theoretically observable to itself — agents can audit agents, sub-markets can audit sub-markets (there's further work here to model out situations where that's not the case) — but it is no longer observable to the population on whose behalf it nominally runs. 

**(6) When agents are free to choose how complicated trades get, they settle at upper-mid α — not at the extremes.** There is one scenario in the set, *Endogenous Baroque*, that gives every prototype a learning algorithm — a contextual bandit — on its own preferred α. Each agent can learn over the run what level of fractal trade it wants to participate in, given what it observes around it. The population's average α drifts to wherever this learning takes it. Agents drift to the upper-mid range — α settles somewhere around 0.7, not the cathedral (α near 1), and not the direct-trade corner (α near 0). This says two things: first, the cathedral regime — α near 1, fold cascade everywhere, EBI in the millions — does not arise from agent preferences alone. Sustaining it takes external scaffolding: low platform fees, no ceiling on how deep the cascade can go, weak alignment vetoes, no friction floor. Without those institutional conditions in place, the cathedral evaporates back toward the upper-mid attractor. Second, and equally important, the direct-trade corner doesn't arise from agent preferences either. Agents free to choose any α don't choose direct trade. The gravitational pull of the population's own learning is mid-fractal, which reinforces the first conclusion — that staying in the direct-trade corner is an active engineering task, not a passive default. The simulator finds that even before any institutional pressure is applied, agents that can learn settle at α ≈ 0.7 because that's where their own incentives land.

---

# §3 THE SCENARIOS

## Section title

The scenarios

## Section sub

Click a card to load its detail pane below. Cards are ordered along α – *Coasean Paradise* on the far left, *Exo-Baroque Singularity* on the far right. Each card prints the scenario's terminal α, exo-baroque index, and per-capita welfare. The twenty-five scenarios fix different levers – alignment-layer rejection rate, agent autonomy, friction floor, capability variance, fold ceiling, the rate at which α responds to its own EBI, demand-side feedback, productive folding, and opt-in time-varying law schedules – so that the rest of the system can be read as a response to that lever.

## Convergence/stability sub-panel header

Scale stability & trajectory convergence at the 50-year horizon

## Convergence/stability sub-panel — meta line

via <code>agentworld convergence</code> / <code>agentworld stability</code>

## Convergence/stability sub-panel — reading guide (gold accent)

**Reading the panel.** The numbers everywhere else on this dashboard are **50-year-horizon values** — one step is one quarter, so <code>n_steps=200</code> ≈ the brief's 2026→2076 frame. This **drift column** shows how much each scenario's terminal EBI moves if you double the horizon to <code>n_steps=400</code> (year 100): a continuous quantity, not a pass/fail. Low drift (&lt;1%) means the trajectory has effectively saturated within the brief's window — what you see is the answer. High drift means EBI is still climbing past year 50. Steady-state values would require multi-century extrapolation past the point where the speculative load-bearing parameters really make sense for a simulation of this size, so the dashboard quotes the 50-year value alongside that drift marker, not in place of it.

## Convergence/stability sub-panel — methods note

One diagnostic per scenario: **(drift)** what is the percentage shift in terminal EBI between <code>n_steps=200</code> and <code>n_steps=400</code>? The earlier scale-stability flag (small-vs-medium-population EBI consistency) is currently small-only because the empirical SBM substrate exceeds the network-node ceiling at medium scale and would fall back to well-mixed sampling, contaminating the comparison. The drift column comes from a 4-seed stability sweep on the substrate at the small population. See [convergence.md](https://github.com/mpoliks/agentworld/blob/main/docs/concepts/convergence.md) and [time_discretization.md](https://github.com/mpoliks/agentworld/blob/main/docs/concepts/time_discretization.md) for method and the dt anchor.

---

# §3 SCENARIO CARDS

[Twenty-five blocks, one per scenario, in the order they appear on the card strip (left → right along α). Each block has a **slug** (the H2 heading — *don't rename*), a **Label** (display name on the card), and a **Description** (card body and §4 active-scenario text). Edit the Label and Description freely.]

## coasean_paradise

**Label:** Coasean Paradise

**Description:** Seb Krier's dream, peak smooth-world. α is held near 0, the friction floor is low, and the folding kernel is effectively off. Every cleared trade is a single direct exchange between two parties, so cumulative nominal GDP and real welfare track each other to within noise and EBI lands at ≈ 1. Used as the reference scenario against which all higher-α regimes are read.

## universal_advocate

**Label:** Universal Advocate

**Description:** Agent capability is raised across the entire population — high-capability representation is available to every household, not just the wealthy. The folding parameters are pulled down to the low-α direct-trade baseline. The wealth Gini compresses because the asymmetric bargaining power that might otherwise be compounded across deciles is removed at the source rather than redistributed after the fact.

## public_defender

**Label:** Public Defender

**Description:** A targeted capability uplift for the bottom of the wealth distribution: agent capability variance is widened and the lower tail is raised, leaving the upper deciles untouched. Folding parameters sit at the low-α baseline. A more politically tractable analogue of universal_advocate; tests whether redistributive access alone is enough to compress the wealth Gini in a moderately folded economy.

## civic_renaissance

**Label:** Civic Renaissance

**Description:** Active legal upkeep is on and civic pushback against capture is active. The optimistic mirror of legal_collapse and regulatory_capture; tests whether decentralised maintenance can hold legal capacity at the level the other two scenarios let it slip away from. The welfare ledger sits between the two and the EBI band is tighter than either.

## synthetic_consumers_v2

**Label:** Synthetic Customers

**Description:** synthetic_consumers with demand-side weighting on. Trades that reach a human consumer count for full welfare; pure agent-to-agent trades are credited at the 15% floor that accounts for indirect downstream benefits. This reports the gap between what the economy printed and what humans got, separating accounting from welfare in a way the unweighted version cannot.

## smoothing_cascade

**Label:** Smoothing Cascade

**Description:** α is scheduled to decay linearly from 0.95 down to 0.05 over the run. A controlled test of whether an economy already deep in the fractal regime can be steered back toward direct trade by a credible commitment to wind down folding. The recovery in EBI lags behind the policy schedule by several steps because the existing folded layers do not unwind instantaneously.

## equilibrium_drift

**Label:** Equilibrium Drift

**Description:** α is held at 0.5. Both attractors exert pull and the seed-to-seed envelope on EBI is wide. Used to read off how much active mechanism design is needed to keep the economy off the mid-α default that an unmanaged population drifts toward.

## matryoshka_collapse

**Label:** Matryoshka Collapse

**Description:** Both the market filter and the alignment filter are raised toward their tightest setting. Most attempted trades die in the filters before reaching the cost calculation, so cumulative nominal GDP and real welfare both contract. Read as the institutional side of the smooth attractor in the limit: when governance is strict on every layer, surviving trade volume is small and the Gini barely moves because marginal trade does not happen.

## hemispherical_schism

**Label:** Hemispherical Schism

**Description:** Multiple incompatible economic stacks (a US/EU/China-style fragmentation in miniature). Cross-stack compatibility is set near zero, which raises both the law-filter rejection probability and the per-trade cost on any inter-stack pair. Intra-stack trade dominates; the surplus that previously cleared across stacks is lost to translation, compliance, and trust costs.

## compute_famine

**Label:** Compute Famine

**Description:** The friction floor on every trade rises mid-run, modeling a sudden revaluation of compute cost. The marginal sub-trade — the one that depended on a near-zero floor to clear — gets priced out first. Read as the asymmetric exposure of high-α scenarios to a friction-floor shock: low-α regimes barely register the change, high-α regimes shed deep folding layers within a few steps.

## derivatives_revolution

**Label:** Derivatives Revolution

**Description:** Mid-α (~0.6), low platform fees, and the productive-folding parameter is on. Folding is moderate but generative: each layer adds value rather than overhead. The cleanest test of whether fractal trade can deliver welfare gains within reasonable bounds when sub-markets are skilled enough to execute the jobs they nominally claim.

## legal_collapse

**Label:** Legal Collapse

**Description:** The law layer's rejection probability rises smoothly over the run as legal capacity decays. Stranger-to-stranger trades (high cross-stack distance, high alignment distance) bear most of the cost and trades inside trusted networks are largely unaffected. The welfare loss takes the shape of a slow regression measured in lost contracts rather than a single event.

## regulatory_capture

**Label:** Regulatory Capture

**Description:** Wealth concentrates over the run and the law layer is gradually captured: the cross-stack compatibility falls and the captured law preferentially blocks trades against the captured group's interest. The welfare loss is paid disproportionately by the unconcentrated population. Read alongside legal_collapse and civic_renaissance as the three-way test on the law layer's stability.

## endogenous_baroque

**Label:** Endogenous Baroque

**Description:** Fractal configuration with the same learning layer enabled. Tests what α agents converge to when they are free to choose. Empirically the learning settles in the upper-mid range, not at the high-α extreme — the cathedral takes external scaffolding to sustain.

## pigouvian_heavy

**Label:** Pigouvian Heavy

**Description:** A 35% Pigouvian tax on A2A nominal volume (base + fold cascade), recycled to human wealth with progressivity 1.5 (poorer humans receive disproportionately more of the recycled revenue). The deterrence effect is substantial: at α = 0.6 the cascade's nominal contribution is suppressed enough to lower EBI by ~25-30% versus the no-tax baseline, and the tax revenue is roughly an order of magnitude larger than under the welfare-only tax base used before. Tests whether a heavy-handed Pigouvian rate can compress EBI without proportionally compressing real welfare.

## pigouvian_friction

**Label:** Pigouvian Friction

**Description:** A 15% Pigouvian tax on A2A nominal volume (base + fold cascade), recycled as a friction subsidy on H2A trades rather than as cash to humans. The deterrence on fold-cascade nominal is the same as Pigouvian Light at the higher rate, but the recycling channel routes revenue to *cost relief* on human-touching trades — bringing humans back into the executable trade set via the supply side rather than via the demand side. At α = 0.6 EBI is suppressed ~10-12% below the no-tax baseline; the welfare/recycling differences vs Pigouvian Heavy are best read off the §5 Sankey, not the EBI line.

## full_emergence

**Label:** Full Emergence

**Description:** All four feedback layers on at once: strategic learning, firm formation, population churn, and accumulating fold pressure. The maximal-richness configuration in the scenario set. A kind of stress test for whether the diagnostic story here can survive heavy compounding rather than a specific regime to plan for.

## recursive_simulation

**Label:** Recursive Simulation

**Description:** α responds endogenously to the running EBI: the more fractal the economy gets, the higher the propensity to spawn further sub-trades. A positive-feedback loop with no governor. The basin around the smooth attractor is shallow and the system tips into the fractal attractor within roughly twenty steps; useful for reading off how locally-stable the smooth regime is under reflexive folding pressure.

## fold_avalanche

**Label:** Fold Avalanche

**Description:** α is scheduled to ramp from 0 toward 1 over the run — the mirror of smoothing_cascade. EBI take-off precedes the welfare collapse: the nominal ledger compounds immediately while welfare losses propagate through the per-depth efficiency leak. This reports the lag between the two ledgers when the schedule moves α faster than the welfare side can register.

## slop_market

**Label:** Slop Market

**Description:** High α with low agent capability — capability roughly N(0.30, 0.15). Sub-trades spawn at the maximum permitted rate but cannot extract real value from the layering, so they accumulate as rent-collecting noise on top of every base exchange. EBI ranges into 10⁵–10⁶; per-capita welfare lands well below the smooth baseline. The clearest failure case in the whole scenario set.

## productive_baroque

**Label:** Productive Baroque

**Description:** Same fractal-folding rate as slop_market, but with high-capability agents — capability roughly N(0.80, 0.15). Sub-trades produce real surplus (risk pooling, price discovery, liquidity transfer) rather than pure overhead, so the per-layer welfare leak is reduced. This reports the productive-vs-parasitic split in the high-α regime: how much of the headline output is genuine welfare and how much is structurally inseparable from accounting theatre.

## baroque_with_high_welfare

**Label:** Baroque (High Welfare)

**Description:** A counter-example using adversarial parameter search over the prior. α and the folding kernel are configured to produce EBI > 10, but capability and demand-side parameters are tuned so per-capita welfare exceeds the smooth baseline. A proof that high EBI does not strictly imply low welfare, even though the two correlate strongly across the population of plausible scenarios.

## baroque_cathedral

**Label:** Baroque Cathedral

**Description:** The fractal-limit baseline. α is high, the folding kernel sustains itself across the full per-scenario depth budget, and the per-layer nominal multiplier is set to its design value. Cumulative nominal GDP separates from real welfare by several orders of magnitude over the run; per-capita welfare lands well below the smooth baseline. The reference scenario for the high-α attractor.

## baroque_cathedral_networked

**Label:** Productive Cathedral

**Description:** The richest-stack baroque variant: high-α cathedral configuration on a sector-block stochastic block model, with t-copula coupled noise (df = 4, BEA 2022 input-output correlations), a Hawkes self-exciting folding kernel (Bacry & Muzy 2015 endogeneity), productive folding on (base_variance_absorption = 0.35, so 35% of fold-nominal volume converts to real welfare via risk pooling, hedging, and price discovery), and demand-side weighting on (DemandConfig.enabled = True, A2A surplus credited at the 15% floor). Per-capita real welfare is the highest in the high-α band; nominal residual is still ≈ 99.99% parasitic by Sankey share, so the two ledgers diverge in opposite directions — W large in absolute terms, share-of-G to humans tiny. Compare to plain baroque_cathedral.

## exo_baroque_singularity

**Label:** Exo-Baroque Singularity

**Description:** The depth limit on the folding kernel is removed; folding compounds without a ceiling. EBI ranges into the 10⁶–10⁷ band and per-capita welfare collapses to within an order of magnitude of zero. Think of it as an upper-bound diagnostic on what unbounded fractal trade asymptotes to.

---

# §4 SCENARIO DETAIL

## Section title

Scenario detail · *[the active scenario's Label fills in here at runtime]*

[The active-scenario description below the title is the same Description block edited above in §3 SCENARIO CARDS. The chart titles and captions in §4 are edited under their own headings further down.]

## Transaction-space animation — chart title

transaction space — live animation

## Transaction-space animation — caption

A 500-prototype sample of the economy. **<span style="color:#5b8ec4;">Blue dots</span>** are humans (50 of 500 — visually inflated from the actual ~1% mass share so they're visible). **<span style="color:#d49e5c;">Amber dots</span>** are agents (450 of 500). Each **flash** is a sample of executed trades: <span style="color:#d49e5c;">**amber**</span> = agent-to-agent, <span style="color:#5b8ec4;">**teal**</span> = human-to-agent, <span style="color:#5fa572;">**green**</span> = human-to-human. Flash density tracks <code>n_transactions_real</code>; the type-mix tracks <code>a2a_share / h2a_share / h2h_share</code>. **Fractal fans** branching off an a2a flash represent the fold cascade — each curved sub-branch is a sub-trade in a derivative market; sub-branches fork further to represent derivatives-of-derivatives. Fan density and depth are driven by the <code>n_sub_markets_added / n_transactions_real</code> ratio at each step, so smooth scenarios show plain flashes and baroque scenarios fill the canvas with dense recursive trees. **Welfare particles** emerge from each flash: with probability ≈ 1/EBI they fly to a human dot and land as a green pulse (welfare delivered); otherwise they dissipate in the agent layer. Counters update step by step.

## Animation HUD — labels (one per line, in display order)

- live
- step
- real welfare (cum)
- nominal GDP (cum)
- EBI
- sub-markets/step
- a2a share

## Animation controls — labels

- ▶ play
- ↺ restart
- (speed options) 0.35× / 0.6× / 1× / 1.75× / 3.5×

## Chart — α over time

### Title
α (smooth ↔ striated) over time

### Caption
The control schedule. A flat line means α was held constant; a ramp or decay means α was scheduled to move; a jagged trace means α responded to the run itself – *Recursive Simulation* is the easiest example, where α climbs whenever EBI climbs.

## Chart — cumulative real welfare vs nominal GDP

### Title
cumulative real welfare vs nominal GDP

### Caption
Two cumulative curves on a log y-axis. They start together. Watch the vertical gap between them (that *is* the exo-baroque index) – the wider it opens, the more measured economic activity has folded into accounting that no human ever consumes.

## Chart — exo-baroque index over time

### Title
exo-baroque index over time (log scale)

### Caption
The same gap, expressed as a single ratio. The dashed reference at EBI = 1 is the parity line. Anything sustained above it is GDP that the human side of the economy did not receive.

## Chart — sub-markets created per step

### Title
sub-markets created per step (log)

### Caption
How many derivative / sub-trade markets were spawned by the fold cascade each step, in real units across the whole economy. Log y-axis because values span ~7 orders of magnitude across scenarios. A flat zero means the scenario refuses to fold; rising values mean fractal multiplication is intensifying. This replaces the older "max fold depth" panel — depth saturated at the cap in most scenarios and carried almost no information beyond "is folding on or off"; the sub-market count actually varies meaningfully both within a run and across scenarios.

## Chart — per-capita welfare

### Title
per-capita welfare · ×10³ stylized units

### Caption
Real welfare divided across 8 × 10⁹ humans, step by step. The actual material outcome on the human side. These are not dollars, these are stylized units for comparison! Coasean Paradise tops out near 280; Slop Market near 25. Productive Cathedral (the high-α scenario with productive folding turned on) is the welfare leader at ≈ 620. Use this trace to compare scenarios on welfare alone, with α and EBI deliberately set aside.

## Chart — rejections by filter

### Title
why trades got rejected — by filter

### Caption
Of the trades that did not complete, which filter killed them. <span style="color:#c25a5a;">law</span> = the trade was illegal. <span style="color:#5b8ec4;">market</span> = the platform blocked it or its fees made it uneconomic. <span style="color:#5fa572;">alignment</span> = one of the parties objected on values grounds. <span style="color:#b89a55;">cost</span> = the trade's underlying friction was higher than its surplus, so it wasn't worth doing. 

## Chart — authentic vs un-modulated welfare

### Title
authentic vs un-modulated real welfare (cumulative, log)

### Caption
**Authentic** real welfare is the share that reaches a human consumer (or a human-controlled agent acting on a principal's behalf). The **un-modulated** trace is the legacy aggregate. The two coincide when <code>DemandConfig.enabled = False</code> (the default) — one curve is drawn on top of the other. When demand-side feedback is on, the gap between the curves is the surplus that A2A activity printed but no person consumed.

## Chart — max fold depth per step

### Title
max fold depth per step

### Caption
The deepest derivative tower observed in any single base trade per step — an integer count of how many sub-markets stacked on top of the deepest cleared trade. Climbs stair-step in the scheduled-α scenarios (*Smoothing Cascade*, *Fold Avalanche*) where α moves over the run, and in the endogenous-α scenarios (*Recursive Simulation*, *Endogenous Baroque*) where α reacts to its own EBI. Saturates at the per-scenario cap (typically 6 or 7) in static high-α scenarios. Sits at zero in direct-trade regimes. Read as a snapshot of where the cascade ceiling is at each moment.

---

# §5 WHERE DID THE WELFARE GO?

## Section title

Where did the welfare go? · *[active scenario name fills in dynamically]*

## Section sub

Same scenario as §4 above. Every unit of measured economic activity (nominal GDP) ends up in one of five places: directly consumed by humans, captured by agents (and never reaching humans), lost to the law system as overhead or capture, recycled via Pigouvian transfer (when that lever is on), or sitting as *parasitic accounting* — nominal volume that the fold cascade printed without producing any consumable welfare. The Sankey below traces those flows for whichever scenario you picked in §3, so you can see **why** the scenario landed where it did, not just that it did.

## Sankey — chart title

nominal GDP flow

## Sankey readout — section label and rows (in display order)

**breakdown**

- total nominal GDP
- → to humans
- → to agents
- → lost to law
- → recycled (Pigouvian)
- → parasitic accounting

## Sankey — how-to-read panel

**how to read it**

Each ribbon's **thickness** is the absolute share of nominal GDP flowing to that destination. A thick green ribbon means most measured activity reached a human; a thick gray ribbon means most was just folded accounting that no one consumed. **Pigouvian recycling is bounded by the slice of nominal that actually became surplus** — in baroque scenarios the parasitic ribbon dominates and the tax base is small even at high tax rates.

[The trailing per-scenario callout (`#welfare-note`) is filled dynamically — edit the scenario module to change it.]

---

# §6 COMPARE SCENARIOS

## Section title

Compare scenarios

## Section sub

Pick any subset of scenarios and overlay them on a shared time axis. Useful for questions like:*what do the Slop Market and the Baroque Cathedral share, and where do they diverge?* Both end at high α; only one converts that α into welfare. Stacking the EBI and per-capita-welfare curves makes the divergence step visible.

## Compare-help — usage instructions

Click a chip to toggle it in or out of the overlay. <kbd>⌥ alt-click</kbd> a chip to **solo** it – keep just that one and clear the rest. The buttons at the right of the strip act on the whole set: **All** turns every scenario on, **Clear** removes everything, **Reset** restores the four corner-defining scenarios.

## Chart — EBI overlay

### Title
exo-baroque index (log)

### Caption
How fast each scenario's accounting separates from welfare over time. Curves that hug 1 are smooth regimes; curves that climb are folding regimes; curves that climb and then stall have hit a fold ceiling.

## Chart — per-capita welfare overlay

### Title
per-capita welfare · ×10³ stylized units

### Caption
What households actually got at each step. Shape distinguishes cumulative growth from stagnation; height ranks the selected scenarios on welfare alone, regardless of how much GDP each printed. Y-axis is scaled by 10³ for legibility – model state is identical to the §1 definition.

## Chart — cumulative nominal GDP overlay

### Title
cumulative nominal GDP (symlog)

### Caption
Total measured economic activity. The symlog y-axis carries both *Coasean Paradise* (≈ unity) and *Exo-Baroque Singularity* (≈ 10⁶ +) on the same chart without one flattening the other.

## Chart — human legibility overlay

### Title
human legibility index

### Caption
Bounded 0–1: the share of nominal GDP a human could in principle audit. 1.0 means the market is fully readable from the outside; values near 0 mean the market is legible only to itself.

---

# §7 GLOBAL SENSITIVITY

## Section title

Global sensitivity · which knobs actually move what

## Section sub — method

Saltelli/Sobol decomposition at N=2048 base samples (34,816 simulations, 15-parameter problem). **S1** is the share of output variance the parameter explains on its own; **ST** includes interactions with the other parameters. A bar where **ST >> S1** means the parameter mostly matters through interactions with other parameters. Parameters where both are near zero are cosmetic within the bounds we swept. Bounds for each parameter are listed alongside the chart — the indices are conditional on those bounds, so they tell you the variance structure inside the explored space, not outside it.

## Section sub — transformed metrics rationale

Two metrics are shown in transformed form so the Saltelli estimator stays inside its assumptions: **log(EBI)** instead of raw EBI (raw EBI's right tail is unbounded — real → 0 in baroque regimes pushes EBI → ∞, which breaks variance decomposition), and **gini of |Δwealth|** instead of terminal gini (terminal gini is ~100% determined by initial population synthesis; corr(gini₀, gini_T) = 1.0000 across the parameter space, so Sobol on it would attribute population-seed noise to topology parameters). Both transformed metrics preserve rank ordering of the originals and produce well-bounded indices (max ST ≤ 0.85, all sum(S1) ≤ 1.0). Raw EBI and gini_wealth time series are still on the dashboard above.

## Sobol chart — α-engine, log(EBI)

### Title
α-engine · Sobol indices for log(EBI)

### Caption
First-order S1 (filled) and total-order ST (outlined) for the log-transformed exo-baroque index. Tall S1 + short ST gap = the parameter acts independently. Tall ST with low S1 = the parameter only matters through interactions with others. Log transform tames the unbounded right tail of raw EBI so the variance decomposition stays valid.

## Sobol chart — α-engine, terminal welfare

### Title
α-engine · Sobol indices for terminal welfare

### Caption
Same decomposition, target = real per-capita welfare. Compare to the EBI panel: knobs that dominate EBI may not dominate welfare, and vice versa.

## Sobol chart — α-engine, wealth-change inequality

### Title
α-engine · Sobol indices for wealth-change inequality

### Caption
Sensitivity for gini of |wealth_t − wealth_0| — captures topology-driven wealth churn rather than the initial-population baseline (terminal gini was ~100% determined by population synthesis, so was unusable for Sobol). Top driver is typically agent capability: more capable agents extract more surplus and shift the distribution further.

## Sobol chart — α-engine, productive welfare yield

### Title
α-engine · Sobol indices for productive welfare yield

### Caption
Per-step share of fold-nominal volume that becomes real welfare. Distinguishes productive folding (real intermediation) from parasitic folding (markup-only). Top driver is the productive-vs-parasitic split parameter (base_variance_absorption); alpha and folding_propensity follow.

## Sobol chart — exo-engine, circulation index

### Title
exo-engine · Sobol indices for circulation index

### Caption
Same decomposition for the exo-engine target (exo_circulation_index). This chart says which exo-side knobs impact exo-side diagnostics.

## Sobol chart — exo-engine, imperial extraction share

### Title
exo-engine · Sobol indices for imperial extraction share

### Caption
Sensitivity of the imperial extraction-share metric. Useful for the question "is the extraction rate parameter the only thing that controls extraction share?" (Spoiler: it usually is, and that is itself maybe an indictment of the engine.)

## §7 fallback — shown only if no Sobol indices have been computed

No Sobol indices found. Run <code>agentworld sobol</code> and <code>agentworld exo sobol</code> to populate.

---

# FOOTER

## Footer paragraph

Agentworld is a tool for thinking about a near-term variable space. The immediate conceptual neighbors are Sébastien Krier's *Coasean Bargaining at Scale* (Sept 2025) and Tomašev et al's *Virtual Agent Economy* (Sept 2025); the alternative ontology supplied by the exo-engine is Poliks & Trillo, *Exocapitalism* (2025).
