# Verifiable Semantics — Certified Vocabulary as a Friction Floor

> *"Core-guarded reasoning constraining agents to use only certified
> terms reduces disagreement by 51–96% across experiments."* —
> Schoenegger, Carlson, Schneider, Daly (2026), *Verifiable Semantics
> for Agent-to-Agent Communication*, arXiv:2602.16424.

Agent-to-agent transactions clear only when the two agents agree on
what the transaction is about. The Coasean machinery in
`docs/concepts/coasean_bargaining.md` assumes that disagreement is
priced into transaction cost; it does not say where the disagreement
floor comes from when prices are perfectly matched. Schoenegger et al.
identify the missing primitive: a *certified vocabulary*, a vocabulary
of terms with statistically-bounded inter-agent disagreement, produced
by a certification protocol that tests agents on shared observable
events.

This doc maps the Schoenegger result into agentworld as a new field on
`NormsConfig`. The mapping makes a previously implicit assumption of
the engine — that agents share a common semantic substrate — into a
tunable lever.

---

## The Schoenegger result, briefly

The certification protocol works in four moves:

1. Agents are presented with a battery of shared observable events.
2. For each event, each agent reports its interpretation in terms of a
   candidate vocabulary.
3. Terms whose pairwise empirical disagreement falls below a statistical
   threshold are *certified*. Terms above the threshold are not.
4. Agents reasoning over certified terms operate within a known
   disagreement floor. Agents reasoning over uncertified terms have
   unbounded disagreement.

Two recovery moves layer on top:

- **Recertification** — periodic re-test against new events catches
  semantic drift before it accumulates.
- **Renegotiation** — when drift exceeds a threshold, agents drop the
  affected terms and rebuild the certified set.

The trade is autonomy for fidelity. Agents that confine themselves to
certified terms communicate reliably but cannot reason about
unconstrained content. Agents that reason freely communicate
unreliably.

---

## Why this is a lever in an a2a economy

The current engine has two adjacent surfaces but no
communication-fidelity primitive.

- `NormsConfig` (W1b) gives every prototype a K-dimensional
  `norm_vector` and updates it toward the capability-weighted mean of
  recent partners. The vector affects whether a transaction is
  rejected by the individual-alignment gate
  (`engine/core/transactions.py:651`) but does not affect whether the
  two agents understand the transaction's terms.
- `cross_stack_permeability` (W1c) gates whether two agents from
  different hemispherical stacks can even attempt a trade. It controls
  contact, not understanding.

The Schoenegger primitive sits between these two. Two agents from the
same stack and with similar norm vectors can still fail to transact
because they assign different meanings to the contract's terms. The
failure mode is misunderstanding, not preference disagreement and not
geographic incompatibility.

The economic consequence: in a population with low certified-fraction,
the marginal cost of a long-tail transaction (a transaction over
unusual terms) is high; in a population with high certified-fraction,
the marginal cost is low. This is a friction floor that scales with
the vocabulary, not the contract value.

---

## Two design options for the engine

The Explore-agent survey of `engine/core/norms.py:56-127` and
`engine/core/transactions.py:647-661` identified two clean ways to
implement the primitive.

### Option A — Per-agent certified fraction (chosen)

Add one field on `NormsConfig`:

```python
certified_fraction: float = 0.5
```

Initialize a per-prototype `pop.certified` array at population
synthesis, drawn from `Beta(α, β)` with mean equal to the configured
`certified_fraction`. At the alignment gate, replace

```python
align_dist = norm_distance(norm_a, norm_b, K)
```

with

```python
align_dist = norm_distance(norm_a, norm_b, K) * (1 - min(cert_a, cert_b))
```

A pair where both agents have `certified = 1.0` has zero alignment
distance regardless of their norm vectors. A pair where either agent
has `certified = 0.0` has full alignment distance, recovering the
current behavior. Pairs in between scale linearly.

Cost: one new field on `NormsConfig`, one new array on `Population`,
one multiplication at `transactions.py:651`.

### Option B — Pair-wise certification with decay (not chosen)

Track `pop.pair_certifications` as a sparse matrix incremented on
executed trade and decayed every tick. Pairs that have traded recently
have a high certification; first-contact pairs have zero. The
alignment gate reads pair-level certification.

This is closer to the Schoenegger spec — certification is
pair-conditional in the paper — but the dense pairwise state is
infeasible at 88M prototypes, and even at 88K the per-step cost is
O(executed_pairs) for updates plus O(pairs_in_step × log n) for reads.

Option A loses the pair-conditioning but preserves the population-level
signal at a fraction of the cost.

---

## What this lets the user explore

The certification-fraction slider in the agentic panel of the spatial
sandbox lets the user pose four questions the current engine cannot
answer.

1. **Does communication fidelity substitute for capability?** Low
   capability with high certified-fraction should produce similar
   transaction throughput as high capability with low certified-fraction,
   at least for trades over common terms.
2. **What does a certification collapse look like?** Drop
   certified-fraction from 0.8 to 0.2 over 30 ticks while holding all
   other levers constant. The expected signature: rejection mix shifts
   toward alignment, real welfare per agent falls, nominal volume
   falls less (because successful trades are higher-value direct
   clearance), Gini decreases (because the long tail of marginal trades
   was the wealth-equalizer).
3. **Is there a Schoenegger–Hadfield tension?** Hadfield's
   `NormsConfig` story is convergence through repeated interaction.
   Schoenegger's story is a discrete certification protocol that bounds
   disagreement before any drift. The two are complementary in the
   engine: high `update_rate` produces norm convergence;
   `certified_fraction` produces a baseline understanding floor that
   convergence happens on top of. A regime with high update-rate and
   low certified-fraction is the W1b `norms_brittle` scenario — fast
   convergence with no floor, producing oscillation.
4. **Does cross-stack permeability matter without certified
   vocabulary?** Two agents from different stacks may share zero
   certified terms even when the permeability gate lets them try to
   trade. The expected reading: low cross-stack permeability and low
   certified-fraction together produce the `hemispherical_schism`
   scenario in `docs/concepts/smooth_striated.md` as a stable
   equilibrium rather than a transient.

---

## What this means for the engine

| Change | Path | Cost |
| --- | --- | --- |
| Add `certified_fraction: float = 0.5` to `NormsConfig` | `engine/core/topology.py:198` (after `initial_norm_seed`) | 1 line |
| Add `certified_fraction_sd: float = 0.15` to `NormsConfig` (controls Beta dispersion) | `engine/core/topology.py:199` | 1 line |
| Initialize `pop.certified` at synthesis from `Beta(α, β)` | `engine/core/population.py:344` (new block) | ~6 lines |
| Multiply norm distance by `(1 - min(cert_a, cert_b))` at the alignment gate | `engine/core/transactions.py:650` (inside the `norms_cfg.enabled` branch) | 1 line |
| Optional: certification decay per tick | `engine/core/norms.py:128` (new block) | ~4 lines |
| Surface `pop.certified[i]` in `cast_snapshot_v2` payload | `engine/core/world.py` snapshot assembler | 1 line |

Default is `certified_fraction = 1.0` so existing scenarios run with
zero change in behavior (the multiplication becomes a no-op). The
spatial sandbox sets `certified_fraction = 0.5` as its default.

The optional decay block models the Schoenegger recertification
horizon: certification drifts down without renewal, drifts up after
high-rejection clusters renegotiate. Wire to `NormsConfig.cert_decay`
and `NormsConfig.cert_renewal_rate`. Skip for V1; revisit if the
sandbox surfaces interesting drift behavior without it.

---

## References

- Schoenegger, P., Carlson, M., Schneider, C., Daly, C. (Feb 2026).
  *Verifiable Semantics for Agent-to-Agent Communication.*
  arXiv:2602.16424.
- Hadfield, G. K. (May 2025). *Normative infrastructure for AI
  alignment.* AIhub. The norm-participation lineage that NormsConfig
  encodes.
- `docs/concepts/coasean_bargaining.md` — the Coasean assumption that
  bargaining costs are about coordination, not about meaning.
- `docs/concepts/matryoshkan_alignment.md` — the individual-alignment
  gate that the certification multiplier modifies.
- Quine, W. V. O. (1960). *Word and Object.* The stimulus-meaning
  model Schoenegger builds on.
