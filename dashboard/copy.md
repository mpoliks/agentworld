# Agentworld dashboard – editable copy

Every visible string on the dashboard lives in this file. Edit the prose below, send it back, and I'll rebuild the HTML template from it. **Section headings (H2 / H3) are load-bearing** – keep their structure exact so I can match each block to its slot. Inside each block, rewrite freely.

## Conventions

- `**bold`** → bold
- `*italic*` → italic
- Unicode renders as-is: `α`, `×10⁶`, `≈`, `→`, `↔`, `–` (en-dash), etc.
- Blank line between paragraphs.
- Anything in `[brackets]` is a directive to me, not visible text.
- Some blocks are short (a single line); some are paragraphs. Either is fine.

---

# HEADER

## Super line (small-caps strip above the title)

Antikythera × Disintegrator · companion artifact

## Title (line 1 / italic line 2)

Agentworld
*An atlas of the smooth-striated continuum*

## Lead paragraph

A computational sandbox for the planetary economy when society is composed of **8 billion humans** and **800 billion to 1 trillion AI agents**. We look at one variable through fifteen scenarios that range from agents *dissolving* economic intermediation (e.g. removing transaction barriers) or *fractally multiplingy* it (introducing new, recursive transaction barriers)? Both are stable equilibria of the same underlying technology, and which one materializes is an open question. What we offer here is a few distributions of possible scenarios.

## Meta chips (one per line, three chips total)

- 15 scenarios
- 8 × 10⁹ humans + 8 × 10¹¹ agents · 6.6M importance-weighted prototypes
- 60 steps · 20M pair-interactions per step

---

# §1 READER'S PRIMER

## Section title

Reader's primer · what every variable means

## Section sub

Read this first, because every chart downstream uses these terms. Units, axes, and reference lines are defined here for §2–§6.

## Panel: α – the control variable

A single number on [0, 1] that interpolates between two **limit regimes** from zero economic mediation (a totally smooth market) to an infinitely complex market. A *limit regime* is the qualitatively distinct behavior the system collapses to at an extreme value of α: **α = 0** is the *Smooth* limit (next panel) and **α = 1** is the *Striated* limit (panel after that). Real economies live in the interior of [0, 1] and are usually a sectoral mix of both. Every other quantity in this dashboard is causally downstream of α (sometimes set by a schedule, sometimes responding to the run via feedback). The atlas places each scenario at *its* terminal α; the §4 detail pane shows α moving over time.

## Panel: Smooth · α → 0 · Krier limit

[green left-border accent]

Near-zero transaction cost and continuous bilateral negotiation between agents. No recursive intermediation – every trade is one trade, not a tower of derivative trades. The state collapses to a contract guarantor; markets are direct exchanges between buyer and seller. Nominal GDP and real welfare stay in lockstep: every measured dollar of economic activity ends up as something a human consumed. *Coasean Paradise* is the ideal scenario and *Universal Advocate* is the equity-corrected version, both borrowed from Seb Krier's work.

## Panel: Striated · α → 1 · Bratton limit

[red left-border accent]

Recursive intermediation everywhere. Every transaction passes through Matryoshka layers (see below) and any transaction with positive expected surplus may spawn sub-markets that price derived rights, derived attention, or derived metadata. Each new tier adds nominal accounting volume and consumes some of the underlying surplus as friction. Nominal GDP detaches from real welfare by orders of magnitude. *Baroque Cathedral*, *Slop Market*, and *Exo-Baroque Singularity* are the canonical instances.

## Panel: Real welfare · per-capita welfare

**Real welfare** is the surplus that ended up in human hands at last-mile consumption, summed across the run. **Per-capita welfare** divides cumulative real welfare by 8 × 10⁹ humans. **Units are stylized – not dollars, ** because raw values across 8 billion humans land in the 5 × 10⁻⁵ to 5 × 10⁻⁴ range, which is unreadable at four decimal places. Every number on the dashboard is therefore **multiplied by 10⁶ for display** so that Coasean Paradise reads as ≈ 513 and Slop Market as ≈ 57. Read the *ratios*, not the absolute numbers – Coasean Paradise produces roughly 9× more welfare per human than Slop Market, for example.

## Panel: Nominal GDP

Total measured economic activity, summed across the run, in the same stylized unit as real welfare. Includes both real surplus and the layered accounting volume produced by folding. In a smooth regime nominal ≈ real; in a striated regime nominal can exceed real by a factor of 10⁶ or more.

## Panel: EBI – exo-baroque index

[gold left-border accent]

Nominal GDP ÷ real welfare. The single clearest measure of how much of *the economy* has folded out of human consumption. **EBI = 1** is the parity regime (Smoothworld). Anything sustained above 1 is GDP that the human side never received – accounting that lives only in agent-to-agent ledgers.

## Panel: Folding · fold depth

When a transaction has positive expected surplus, agents may spawn sub-markets that trade in derived rights, derived attention, derived metadata. Each tier is one fold. **Fold depth** is the height of the tallest such tower observed in any single transaction this step. Smooth regimes hold this at zero; striated regimes climb to integers in the single or low double digits. The exo-engine renames folding *lift* – the basic operating logic of capital, not a parameter setting.

## Panel: Matryoshka layers (after Krier)

Every attempted transaction passes through three nested filters before it can clear: **law** (binary statutory veto), **market / platform** (probabilistic fee-or-rules filter), and **individual alignment** (continuous person-level objection). A trade that fails any layer is a rejection. The §4 rejection chart shows which layer is the binding constraint in each regime.

## Panel: Human legibility index

1 ÷ EBI, capped at 1. The share of nominal economic activity a human could in principle audit at last-mile resolution. 1.0 means the market is fully readable from the outside; values near 0 mean the market is legible only to itself.

## Panel: Wealth Gini

Standard 0–1 Gini over the joint human + agent wealth distribution at the terminal step. Reported in §4 alongside per-capita welfare so that *welfare* and *distribution of welfare* can be read together. *Public Defender* is a specific example where this variable is compressed.

## Panel: Interaction shares · A2A / H2A / H2H

Three counters per scenario: **A2A** agent-to-agent, **H2A** human-to-agent, **H2H** human-to-human. Above the smooth limit, A2A dominates by two or three orders of magnitude – the population that produces nearly all transactions is also the population that consumes them. Reported in the §4 detail pane.

## Panel: Population

~10⁵ prototypes, importance-weighted to 8 × 10⁹ humans and 8 × 10¹¹ agents (a 100:1 agent-to-human ratio). Each prototype carries (capability, sector, hemispherical stack, alignment, autonomy, wealth). Sample size makes the run tractable; weights make the totals correct at planetary scale.

---

# §2 THE ATLAS

## Section title

The atlas

## Sub paragraph 1

Each point is one scenario at its terminal step. The **x-axis** is α, the smooth-striated control variable on [0, 1]. The **y-axis** is the *exo-baroque index* (EBI) – nominal GDP divided by real welfare, log-scaled. **Color** encodes per-capita real welfare; greener is better. The dashed line at EBI = 1 is the parity regime: every measured dollar of GDP matches a dollar of human welfare. Anything sustained above that line is GDP that the human side of the economy never receives – accounting that has folded out of last-mile consumption.

## Sub paragraph 2

**What to read off the chart.** Bottom-left: low α, no folding, accounting tracks welfare. Top-right: high α, recursive folding, accounting separates from welfare by orders of magnitude. A point that sits high on the y-axis *and* dim in color is the brief's failure case – a regime printing volume without producing anything humans consume. Every point is hover-only; identifying the cluster scenarios by name needs a mouse-over, which keeps the plotting region uncluttered and the y-axis range honest.

## Atlas chart caption (sits between section sub and the chart)

**Dashed horizontal:** EBI = 1 – the parity line where welfare equals nominal GDP. **Color** is per-capita welfare scaled by 10⁶ (model state is unchanged; the scaling exists so values like Coasean Paradise ≈ 513 and Slop Market ≈ 57 are legible at a glance instead of collapsing into "0.0005" and "0.0001"). Hover any point for the scenario label, exact α, EBI, and welfare.

## Atlas callout · paragraph 1 (Bratton's hypothesis)

Bratton's hypothesis is that the right-hand limit – **Baroqueworld** – is at least as plausible as the Krier limit on the left, and that this is where the on-paper GDP gains will come from. Krier's *Coasean Paradise* sits in the bottom-left. Bratton's *Exo-Baroque Singularity* sits in the top-right. The economies of the late 2030s are a weighted blend of the two, varying by sector, jurisdiction, and stack. *The atlas does not predict where any given regime lands. It clarifies what landing somewhere costs.*

## Atlas callout · paragraph 2 (What the atlas does not show)

**What the atlas does not show.** These terminal-step snapshots basically compress fifteen trajectories into fifteen dots. Two scenarios can land at the same coordinate by very different routes – a slow drift through the mid-α basin reads identically to a fast climb that overshoots and falls back. §4 unfolds each path as a six-chart panel; §5 stacks any subset of paths on a shared time axis so the route, not just the destination, becomes clear.

## Atlas callout · paragraph 3 (What this means for decisions)

**What this means for decisions.** There are five main points here based on this simulation. **(1)** The thing that really moves regimes is α – protocol striation – not capability. Smarter agents raise welfare *inside* a basin without moving a population across a basin boundary, so a "smarter agents" policy with no α policy still ends in Baroqueworld if α was high. **(2)** High nominal GDP is not a win condition. Above EBI = 1, the marginal dollar is accounting that the human side never received, so the decision-relevant metric is per-capita real welfare and the diagnostic-relevant metric is EBI itself. Optimizing for nominal GDP under high α funds the Slop Market. **(3)** The mid-α basin is the default attractor – without active mechanism design, a population drifts toward striation rather than toward the smooth corner. Landing in the bottom-left is a deliberate act, sustained by concrete choices about platform fees, fold ceilings, alignment-layer veto rights, and the friction floor. **(4)** Smoothworld is not a free lunch. It requires near-zero transaction cost *and* contract enforcement that scales to 8 × 10⁹ humans plus 8 × 10¹¹ agents – a heavier institutional ask than its "shrunken state" framing suggests. **(5)** Two scenarios at the same atlas coordinate are not the same policy. *Recursive Simulation* and *Baroque Cathedral* can both end at high α and high EBI, but one got there via positive-feedback drift (no one chose it) and the other via deliberate construction. Use §4 and §5 to see the specific routes taken.

---

# §3 THE SCENARIOS

## Section title

The scenarios

## Section sub

Click a card to load its detail pane below. Cards are ordered along α – *Coasean Paradise* on the far left, *Exo-Baroque Singularity* on the far right. Each card prints the scenario's terminal α, exo-baroque index, and per-capita welfare. The fifteen scenarios fix a different levers – alignment-layer rejection rate, agent autonomy, friction floor, capability variance, fold ceiling, the rate at which α responds to its own EBI – so that the rest of the system can be read as a response to that lever.

[scenario cards themselves are auto-generated from the run data; the per-scenario one-line descriptions live in `engine/scenarios/__init__.py` SCENARIO_DESCRIPTIONS – let me know if you want those editable here too]

---

# §4 SCENARIO DETAIL

## Section title

Scenario detail · *[active scenario name fills in dynamically]*

[Below: six side-by-side chart panels. Each has a small uppercase title and a one-paragraph caption. Edit either freely.]

## Chart 1 · title

α (smooth ↔ striated) over time

## Chart 1 · caption

The control schedule. A flat line means α was held constant; a ramp or decay means α was scheduled to move; a jagged trace means α responded to the run itself – *Recursive Simulation* is the canonical example, where α climbs whenever EBI climbs.

## Chart 2 · title

cumulative real welfare vs nominal GDP

## Chart 2 · caption

Two cumulative curves on a log y-axis. They start together. The vertical gap between them *is* the exo-baroque index – the wider it opens, the more measured economic activity has folded into accounting that no human ever consumes.

## Chart 3 · title

exo-baroque index over time (log scale)

## Chart 3 · caption

The same gap, expressed as a single ratio. The dashed reference at EBI = 1 is the parity line. Anything sustained above it is GDP that the human side of the economy did not receive – folded surplus that exists only in agent-to-agent ledgers.

## Chart 4 · title

max fold depth this step

## Chart 4 · caption

The tallest tower of recursive sub-markets observed in any single transaction this step. Step shape because depth is integer-valued. A flat zero means the scenario refuses to fold; a staircase climb is folding take-off – each new tier reflects the pricing of a derived right, derived attention, or derived metadata.

## Chart 5 · title

per-capita welfare · ×10⁶ stylized units

## Chart 5 · caption

Real welfare divided across 8 × 10⁹ humans, step by step. The actual material outcome on the human side. Multiplied by 10⁶ for legibility – these are not dollars. Coasean Paradise tops out near 500; Slop Market near 60. Use this trace to compare scenarios on welfare alone, with α and EBI deliberately set aside.

## Chart 6 · title

rejection share by Matryoshka layer

## Chart 6 · caption

Of the trades that did not clear, which Matryoshka layer killed them. **law** (red) = a binary statutory veto. **market** (blue) = a probabilistic platform / fee filter. **alignment** (green) = an individual-level objection. **cost** (gold) = the friction floor. The dominant color names the binding constraint at each step.

---

# §5 COMPARE SCENARIOS

## Section title

Compare scenarios

## Section sub

Pick any subset of scenarios and overlay them on a shared time axis. Useful for the question: *what do the Slop Market and the Baroque Cathedral share, and where do they diverge?* Both end at high α; only one converts that α into welfare. Stacking the EBI and per-capita-welfare curves makes the divergence step visible.

## Compare-help text (small line above the chip strip)

Click a chip to toggle it in or out of the overlay. **⌥ alt-click** a chip to **solo** it – keep just that one and clear the rest. The buttons at the right of the strip act on the whole set: **All** turns every scenario on, **Clear** removes everything, **Reset** restores the four corner-defining scenarios.

## Chart 1 · title

exo-baroque index (log)

## Chart 1 · caption

How fast each scenario's accounting separates from welfare over time. Curves that hug 1 are smooth regimes; curves that climb are folding regimes; curves that climb and then stall have hit a fold ceiling.

## Chart 2 · title

per-capita welfare · ×10⁶ stylized units

## Chart 2 · caption

What households actually got at each step. Shape distinguishes cumulative growth from stagnation; height ranks the selected scenarios on welfare alone, regardless of how much GDP each printed. Y-axis is scaled by 10⁶ for legibility – model state is identical to the §1 definition.

## Chart 3 · title

cumulative nominal GDP (symlog)

## Chart 3 · caption

Total measured economic activity. The symlog y-axis carries both *Coasean Paradise* (≈ unity) and *Exo-Baroque Singularity* (≈ 10⁶ +) on the same chart without one flattening the other.

## Chart 4 · title

human legibility index

## Chart 4 · caption

Bounded 0–1: the share of nominal GDP a human could in principle audit. 1.0 means the market is fully readable from the outside; values near 0 mean the market is legible only to itself.

---

# §6 PHASE-SPACE SWEEP

## Section title

Phase-space sweep

## Sub paragraph 1

The sweeps provide a regular grid across α (x-axis) and agent capability (y-axis), with each cell classified into one of five basins: *smooth*, *mixed*, *striated*, *baroque*, *slop*. Cell color encodes log₁₀(EBI).

## Sub paragraph 2

**How to read the grid.** Walk any row from left-to-right and watch the glyph change – that change is a basin transition, and the α column where it happens is the tipping point for that level of capability. Then climb a column instead: the glyph holds. Capability raises welfare *inside* a basin without moving it across a boundary. The full population can be made wildly more capable and still sit in the same regime.

## Note on phase-space (text below the heat map)

The boundary that matters here most is α, not capability. Capability does increase welfare inside a regime, but it does not move a point across a basin line. Whether the same population sits in *smooth*, *mixed*, or *baroque* is instead decided by protocol striation. It's worth noting that the on-paper gains visible at the right edge of the grid are not gains in welfare but are gains in the number of priced surfaces.

---

# FOOTER

Agentworld is a tool for thinking about a near-term variable space. The immediate conceptual neighbors are Sébastien Krier's *Coasean Bargaining at Scale* (Sept 2025) and Tomašev et al's *Virtual Agent Economy* (Sept 2025); the alternative ontology supplied by the exo-engine is Poliks & Trillo, *Exocapitalism* (2025).