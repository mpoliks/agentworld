# Coasean Bargaining at Scale — the Smooth Attractor

> *"There is a timeless question at the heart of any (free) society: how do we allow individuals to pursue their own interests when one person's actions inevitably affect the well-being of another in ways that are negative-sum?"* — Séb Krier, *Coasean Bargaining at Scale* (Sept 2025)

---

## Coase, 1960

Ronald Coase's central insight: if bargaining costs are zero, parties will negotiate to the efficient outcome regardless of how property rights are initially allocated. A polluter and her neighbor will strike a deal that internalizes the externality. The state's coercive role becomes minimal.

Coase himself was not a utopian. He emphasized the *transaction cost* clause — and famously argued that the *whole reason firms exist* is that bargaining is expensive. Hierarchies internalize transactions that would otherwise drown in coordination overhead.

For most of the 20th century, transaction costs remained the binding constraint. Pollution was banned because pricing it was infeasible at scale. Healthcare was provided centrally because hyper-individual negotiation was infeasible. Land use was zoned because per-property bargaining was infeasible. Almost every domain that economics calls a "market failure" is really a *transaction-cost failure* — the underlying preferences would clear, if only we could express, communicate, negotiate, and enforce them.

---

## What changes when agents take over

Krier's argument: AI agents drive transaction costs down by 4–6 orders of magnitude. Specifically, agents:

1. **Discover** counterparties cheaply. A perfect partner exists for almost any preference; finding her was the limit. Agents enumerate.
2. **Negotiate** in milliseconds across dimensions humans would never bother to specify. Your noise tolerance varies by hour, by day, by mood, by whether your child is napping. Agents communicate this.
3. **Enforce** through automated escrows, reputation systems, and zero-knowledge attestation. Most enforcement collapses to computational verification.
4. **Express** preferences with granularity humans cannot achieve in language. The "endowment effect" Krier mentions becomes designable rather than tacit.

The Coasean envelope therefore *expands enormously*. Things that were ban-or-permit become priced. Things that were one-size-fits-all become per-capita. Things that were seasonal and political become continuous and computational.

Krier calls this the **virtual agent economy** — a layer in which the bulk of bargaining happens between principal-aligned agents, with humans (or other agents) instructing only the *boundary conditions*.

---

## The smooth attractor

In our model, the **Coasean Paradise** scenario instantiates Krier's vision: low α (0.08), high agent capability, low Matryoshka tax, high cross-stack compatibility. The result is an EBI very close to 1 — almost every dollar of nominal GDP is a dollar of real welfare. Folding is suppressed because, at low α and with high capability, agents have no incentive to spawn sub-markets: every potential transaction *can* clear directly, and there is no surplus to be captured by intermediation.

A subset of related scenarios sit nearby:

- **Universal Advocate** (α=0.20) — the Krier limit *with* moderate institutional layering. Higher EBI but still well within human legibility, and a strong Gini compression because low-capability participants no longer get priced out.
- **Public Defender** (α=0.30) — a deliberate equity intervention: capability variance compressed by subsidy. Almost no rejected-by-cost transactions; alignment-layer rejections become the dominant filter.
- **Smoothing Cascade** — the *transition* into Smoothworld. Starts at α=0.95, decays to α=0.05 over time. Models a society that *successfully* uses agents to dissolve intermediation.

---

## Stylized facts in the smooth attractor

Across our smooth-tilted scenarios:

| Metric | Smoothworld | What it means |
| --- | --- | --- |
| EBI | 1.0–2.5 | Welfare ≈ GDP. Almost no folded value. |
| Per-capita welfare | 0.04–0.06 | Highest in the parameter space. |
| Fold max depth | 0–4 | Folding suppressed below threshold. |
| Governance overhead | 0.10–0.15 | Thin Matryoshka. Most attempted trades clear. |
| Rejection mix | Cost-rejected dominates initially, alignment dominates at the limit | The binding constraint becomes individual preference, not transaction cost. |
| Dominant Matryoshka layer | Individual alignment | When cost is cheap, only *will* matters. |

The "rejection mix" finding is the most underappreciated. Krier's vision is *not* that all transactions execute — most attempted bargains will still fail, but they will fail because *people don't want them*, not because *coordinating them was too expensive*. The economy becomes preference-revealing rather than friction-bound. The *kind* of failure changes.

---

## What Krier underweights, and what the model exposes

Three things the Coasean argument tends to underweight, that our scenarios make legible:

### 1. Power flows to the substrate
In Smoothworld, the firms that historically lived off coordination margins — brokers, agencies, platforms — disappear. But the substrate underneath all that bargaining (foundation models, agent runtimes, payment rails, identity systems) accrues all the value. The state's "framework guarantor" role applies *only* to whatever constitutes the substrate, and "framework guarantor" is a euphemism for "absolute power over the medium of exchange."

A Krierian world in which Anthropic, OpenAI, Google, and a Chinese counterpart provide the agent infrastructure is a four-firm world. It is not capitalism in the firm-as-Coasean-coordinator sense; it is closer to a regulated utility model, but without the regulation, since national-level regulators are themselves dependent on the substrate.

### 2. Smoothing is also a kind of striation
Reducing transaction costs to near-zero does not eliminate measurement; it standardizes it. Every Coasean trade requires the parties to agree on a unit of account, a payment protocol, a dispute-resolution path, and a reputation system. These are themselves *striations* — they grid the space in which smooth bargaining occurs.

In our model, even the Coasean Paradise scenario has a non-zero `friction_floor` and a non-trivial Matryoshka stack. The smooth attractor is a *limit*, not a destination. Real Smoothworld implementations always retain some striation, because *bargaining requires a metric*.

### 3. Smoothing reduces nominal GDP
This is the punchline most readers miss. If you successfully Coasean-clear a market that was previously brokered, your *nominal* GDP falls — because the broker's revenue is no longer a measured economic event. Welfare goes up, but the headline number goes down.

A society whose policy machinery treats nominal GDP as the proxy for prosperity will *resist* smoothing. This is one of the strongest reasons to suspect that, absent deliberate intervention, we drift toward Bratton's Baroque limit and not Krier's Coasean one. Folding is what happens when GDP is the proxy.

---

## What the smooth attractor needs to survive

For Smoothworld to be a stable equilibrium rather than a transitional state, several things must hold:

1. **Agent infrastructure is publicly underwritten** — through "agent vouchers," compute commons, or open-source foundation models. Otherwise the substrate-power problem becomes a foundational political crisis.
2. **Property rights are renegotiated to be modular** — preferences must be expressible at the granularity agents can negotiate. This means redesigning a lot of legal infrastructure (zoning, IP, environmental regulations) so that *price* can substitute for *binary permit*.
3. **Measurement evolves** — GDP is replaced or complemented by welfare and per-capita-real metrics, so policy doesn't actively push toward folding.
4. **The Matryoshka stack is genuinely nested** — law remains binding, market layers remain plural and contestable, individual layers remain genuinely individual.

None of these are technically hard. All are politically hard. The artifact is agnostic on whether they will be met.

---

## References

- Coase, R. (1960). *The Problem of Social Cost.* Journal of Law and Economics.
- Krier, S. (2025). *Coasean Bargaining at Scale.* AI Policy Perspectives.
- Hayek, F. (1945). *The Use of Knowledge in Society.*
- Ostrom, E. (1990). *Governing the Commons.*
- Tomašev et al. (2025). *Virtual Agent Economy.* arXiv:2509.10147.
- Levin, M. & Lyon, B. (2024). *Cognitive glue.*
