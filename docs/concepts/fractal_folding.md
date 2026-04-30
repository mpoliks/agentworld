# Fractal Folding — the Striated Attractor

> *"There is equal potential for the fractal multiplication of folded surfaces, and this may be where the real on-paper GDP gains will come from."* — Benjamin Bratton, April 21 2026

---

## The hypothesis

Most discussion of agent economies assumes that agents *disintermediate* — they collapse middle layers, route around platforms, smooth supply chains. Bratton's hypothesis is the *equally plausible inverse*: agents may *fractally multiply intermediation*. Every existing market becomes the parent of sub-markets; every sub-market becomes the parent of sub-sub-markets. The economy folds into itself, like a Hilbert curve, until the surface area available for pricing is effectively unbounded.

This is not a theoretical possibility. The conditions for it are *already* in place:

- **Agents are very good at noticing surplus.** Where there is a positive expected gain from a sub-division of an existing transaction, an agent will spawn the sub-market.
- **Agents are very good at *creating* surplus through measurement.** A previously un-priced attribute (the SLA on a packet's last-mile delivery, the metadata on an inference request, the freshness of a search query) becomes priceable as soon as some agent decides it should be.
- **Compute is cheap enough that the marginal cost of one more layer is essentially zero.**
- **National accounting cannot tell the difference** between a transaction that creates new welfare and a transaction that re-prices existing welfare. Both register as GDP.

These four facts together make folding the *path of least resistance* for an agent layer that has been told to "do more economic activity." The fractal is what you get if you optimize for measurable activity instead of measurable welfare.

---

## The folding operator

In our model, the folding operator works as follows. After each step of Coasean bargaining produces some `real_surplus_added` and some `nominal_volume`, we apply:

```
nominal_added = base_nominal × Σ_d (depth_propensity^d × branching^d × multiplier^d)
real_lost = base_real × (1 - efficiency^d)
```

…for fold depths `d = 1, 2, ..., D_max`. Each level adds nominally; each level eats a small fraction of real welfare as friction. The propensity is a function of α: at α=0 there is no folding, at α=1 it is aggressive.

Two key parameters set the fractal's character:

- **`folding_branching`** — how many sub-markets each parent spawns on average. We use 2.7 by default; aggressive Baroque scenarios push toward 5.
- **`fold_nominal_multiplier`** — how much nominal value each sub-market generates relative to its parent. We use 1.85 by default; this is the GDP-amplification factor per layer.

At default settings, three levels of folding turn one unit of nominal volume into about 14 units. Six levels turns it into about 800. Ten levels into about 250,000. The fractal is exponential in depth, and depth is bounded only by compute and protocol-design choices.

---

## Why this is the path of least resistance

There are four mechanisms that push an unintervened agent layer toward folding rather than smoothing:

### 1. Measurement reflexivity
GDP is what gets counted. What gets counted is what is transacted. What is transacted is what someone has built a market for. *Therefore: building markets increases GDP, regardless of whether it increases welfare.* An agent layer optimizing for any GDP-correlated objective (commission, transaction-fee revenue, "engagement," "AUM," "throughput") will build markets for the sake of building markets.

### 2. Agent-side economies of scope
Once you have an agent capable of negotiating a primary transaction, the marginal cost of negotiating a derivative transaction is near-zero. The agent already knows the principal, the counterparty, the context. Spawning a sub-market is purely additive in revenue and trivially small in cost.

### 3. Asymmetric counterfactuals
If your agent does *not* spawn a sub-market and a competitor's agent does, the competitor captures the surplus. This is a one-way ratchet. Defection from the folding equilibrium is individually costly even when collectively wasteful — a classic prisoner's dilemma at the protocol level.

### 4. Rent extraction by protocol owners
Whoever defines the protocol on which sub-markets clear gets to charge. Making the protocol *easier to fold on* is in the protocol owner's interest. Existing payment-protocol design (the AP2 / x402 / ClawCoin family) tends, by default, to *encourage* folding because it is what generates fee revenue.

The point is not that any of these mechanisms is malign. It is that all four point in the same direction, and that direction is *up the EBI scale*.

---

## What Baroqueworld looks like

The **Baroque Cathedral** scenario in our model: α=0.92, capability mean 0.78, branching factor 3.2, max depth 7. Result: EBI ≈ 1100. Per-capita real welfare modestly lower than Smoothworld. Fold depth saturates at 7. Human legibility ≈ 0.001.

What does this *look like* from the inside?

- **Your morning coffee.** Order placed by your home agent. Coffee-bean futures hedged in real time by your principal's grocery agent. Roast-quality SLA between your roastery and your delivery agent priced on a per-batch basis. Last-mile carbon offset auto-traded against three different offset markets. Insurance on the spillage risk between cup and table priced and paid. None of which you see, all of which contributes to GDP, all of which is denominated in a unit of account negotiated this morning between five payment-rail providers.
- **Your apartment building.** The HVAC system runs a continuous double auction with each unit's preference agent, with sub-markets in air-quality (PM2.5 clearing), temperature volatility (a reactive futures market), noise floor (per-decade-of-Hz pricing), and humidity (separate from temperature). Your "rent" is a derivative position on an aggregate of these.
- **Your work.** You have a primary contract with an employer; on top of which sits a real-time market in your attention (priced per minute by topic-domain), your IP exhaust (each ambient-recording goes to a market for derived training data), and your reputation (priced per signal you emit). All of this earns you GDP attribution.

Most of these markets are *real* in the sense that someone gets paid and the payments clear. But the relationship between this payment-volume and the underlying economic *substrate* — the actual coffee you drank, the actual room you sat in, the actual work you did — has become tenuous.

This is the **exo-baroque** condition. Most of the economy is, from the human perspective, exterior to anything they can audit. It is legible only to itself.

---

## Stylized facts in the striated attractor

Across our striated-tilted scenarios:

| Metric | Baroqueworld | What it means |
| --- | --- | --- |
| EBI | 50–10⁶ | Wide range; depends on fold depth ceiling |
| Per-capita welfare | 0.005–0.04 | Lower than smooth, but not always dramatically |
| Fold max depth | 6–10 | Saturates at the configured ceiling |
| Governance overhead | 0.13–0.15 | Similar to smooth — most filtering happens *inside* folded markets, not at intake |
| A2A interaction share | > 0.985 | Almost all activity is agent-internal |
| Human legibility | 0.001–0.05 | Effectively zero |

Notice that *governance overhead* is roughly the same in both attractors. This is one of the model's clearer findings: the Matryoshka stack does roughly the same fraction of filtering whether the system is smooth or striated. What changes is *what gets through* and *what happens to it after it does*.

---

## What Bratton sees that Krier doesn't

Krier's piece is, intentionally, an argument *for* the smooth attractor. It treats folding implicitly as a failure mode. Bratton's question — and the reason to take it seriously — is whether folding might be the *attractor we end up in regardless of preferences*, because of the four mechanisms above.

If that's right, then a research brief that tries to think clearly about Agentworld cannot just argue for smoothing. It has to also model what striation looks like *as a stable, possibly even desirable, regime* — what the Baroque enables that smoothing forecloses. Fragmenting plural value-systems can survive in Baroqueworld because there is room for many small sub-markets each with their own units, norms, and reputational economies. Smoothworld tends toward a single unit of account and a single bargaining metric, which has a particular politics of its own.

The artifact does not pick a side. The artifact argues that the smooth/striated dimension is *the question*, and that intuitions about it are largely wrong:

- Smoothing is *not* automatically liberatory.
- Striation is *not* automatically extractive.
- Both can host concentration of power; both can host pluralism.
- The choice between them is *a design choice* embedded in protocol-level decisions made today.

---

## Provocations from the model

Three observations the model surfaces that may be useful for the brief:

### a) The Slop Market scenario
At high α and low capability — i.e. the agents are busy folding but not very good at the underlying economic activity — EBI explodes (335 in our run) but per-capita welfare collapses (0.0059, lowest of any scenario). This is the worst-of-all-worlds outcome. **It is also the default outcome if capability lags behind protocol design**, which is plausibly what happens during the next 24–48 months of agent deployment.

### b) The Recursive Simulation scenario
When α responds to EBI (a feedback loop where measured "Baroqueness" drives further folding), we get a sigmoid take-off: small initial differences in protocol choice amplify rapidly. This suggests a path-dependent dynamic in which whichever attractor wins the early years *locks in* by the time anyone notices.

### c) The Hemispherical Schism scenario
At low cross-stack compatibility, each stack tends toward its own α — and the resulting variance is itself an economic phenomenon. Cross-stack arbitrage becomes an enormous, possibly dominant, source of both real and nominal GDP. *The seams between stacks become the most folded surfaces of all.* This may be where the geopolitics of Agentworld actually lives.

---

## References

- Bratton, B. (2026). *Agentworld* research brief, Antikythera (forthcoming).
- Bratton, B. (2026). Telegram correspondence with Marek Poliks, April 21.
- Deleuze, G. (1988). *Le Pli: Leibniz et le Baroque.* The Fold: Leibniz and the Baroque.
- Tomašev et al. (2025). *Virtual Agent Economy.* arXiv:2509.10147.
- ClawCoin / x402 / AP2 protocol specifications, 2025–2026.
