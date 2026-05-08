# Matryoshkan Alignment — Nested Governance

> *"The meta-framework is a series of nested layers of governance, like a set of Matryoshka dolls. The outermost is the law. Within that operates the second layer: the free market of different services, deployers, products, and providers. Finally, at the core, is the individual."* — Séb Krier (Sept 2025), riffing on Michael Levin's "scale-free cognition"

---

## The three layers

Krier's framing — borrowed from Levin and refined for AI agents — is that no single locus of alignment makes sense. Asking "is your agent aligned to you, or to the platform, or to the law?" is a category error. The agent is aligned to all three, *in nested order*. Like the dolls.

The three layers are:

1. **Law** (outermost) — *binary*, *non-negotiable*, *enforced by the state*. Your agent cannot help you commit fraud, hire a hitman, synthesize a bioweapon. There is no negotiation here; transactions that violate the law layer are simply forbidden. The state enforces. There is no opt-out.
2. **Market / platform** (middle) — *probabilistic*, *plural*, *contestable*. The agent provider, the model developer, the foundation model's deployer — each imposes its own policies. Different platforms have different rules. You choose your platform; you accept its rules; you can switch.
3. **Individual** (innermost) — *continuous*, *personal*, *evolving*. Your agent learns your preferences, values, dispositions. It enforces *your* rules, including ones you couldn't articulate but it can infer.

A transaction must pass all three filters to execute. It must be legal (else hard-rejected), it must be platform-permitted (else stochastically-rejected), and it must be individually-aligned (else preference-rejected).

---

## In the model

The Matryoshka stack is implemented in `engine/core/transactions.py`. For each candidate transaction pair, we compute three rejection probabilities:

```
law_reject    = ~U(0,1) < 0.01 + 0.04 × (1 - cross_stack_compat)
market_reject = platform_reject ∨ regulator_reject
align_reject  = ~U(0,1) < 0.03 + 0.20 × |alignment_a - alignment_b| × (1 - 0.5 × autonomy_avg)
```

The middle layer is two independent sublayers composed by OR — either subgate can refuse a trade. Conflating them in a single gate (as the original engine did) erased a substantive distinction Hadfield drew explicitly: platforms and regulatory markets are different objects with different parameter dependencies and different policy levers.

- **Platform / deployer gate** (Krier's market doll). Always on. Foundation-model deployers, agent providers, and platform owners filter on sector compatibility and pairwise alignment distance: `platform_reject = ~U(0,1) < 0.02 + 0.06 × (1 - sector_affinity) + 0.04 × |alignment_a - alignment_b|`. Reads as "platform compatibility gate" — a B2B finance-stack agent transacting with a consumer-leisure-stack agent is platform-incompatible regardless of any external regulator.
- **Licensed-regulator gate** (Hadfield 2025/2026). Off by default; enabled per scenario. When `RegulatorConfig.enabled = True`, every attempted pair is sampled at probability `coverage` and audited pairs are rejected at `base_reject_rate + audit_quality × max(defect_score_a, defect_score_b)`. The defect score is `rejections / max(rejections + acceptances, 1)` over the prototype's audit trail (zero for unregistered prototypes — there is no continuity to defect against). Coverage is structurally bounded above by `PopulationConfig.registration_coverage`: a regulator cannot audit a prototype it cannot identify. See `docs/plans/regulator_market_split.md` and the `regulator_active` scenario.

The `cost_reject` (transaction cost > expected surplus) is *only* applied to transactions that survive all three Matryoshka layers. So the cascade is:

```
attempted → law_filter → platform_filter → regulator_filter → align_filter → cost_filter → executed
```

This ordering matters. In the smooth attractor (low α, high capability), `cost_filter` is rarely binding — almost any transaction *can* clear, but only if it passes the three Matryoshka layers. So **alignment becomes the dominant constraint**. In the striated attractor (high α, possibly low capability), `cost_filter` is more binding, but the Matryoshka layers are also more saturated — every layer of folding adds Matryoshka overhead.

Each executed transaction is also taxed by the market and individual layers (`market_layer_tax`, `individual_layer_alignment_tax`) — these eat into real surplus regardless of whether the transaction was nominally completed.

The individual-layer gate is parameter-named: `binding = max(|al_a - community_norm|, |al_b - community_norm|)` when `NormConfig.enabled` is true, else `binding = |al_a - al_b|`. The norm is a tracked field updated each step toward the alignment-weighted mean of the previous `norm_lag_steps` executed trades, with rate `norm_update_eta`. Observations only count from prototypes that were registered under `PopulationConfig.registration_coverage` — anonymous draws have no continuity to contribute. The coefficient on `binding` (0.20) is the same in both regimes; only the binding term differs. Hadfield's normative-competence reading of alignment fits the `enabled` regime; the original Krier-only formulation fits the `disabled` regime. Default is disabled, to preserve the canonical Sobol pin until the round-overview's plan 9 re-pins on the extended parameter set. See `docs/plans/norm_evolution_alignment.md`.

---

## Why three layers and not one or seven

Krier's three-layer choice isn't arbitrary. It maps to the three irreducible governance problems any decentralized economy must solve:

| Layer | Solves what | Failure mode |
| --- | --- | --- |
| Law | The *coercion monopoly* problem — preventing violence, theft, fraud | Tyranny if too much; chaos if too little |
| Market | The *intermediary diversity* problem — preventing platform monopoly | Capture if too few platforms; balkanization if too many |
| Individual | The *preference revelation* problem — making private values public-bargainable | Atomization if no aggregation; collectivism if no individuation |

Other layer counts have other tradeoffs:

- **One layer (law only)**: this is the e/acc / pure-libertarian limit. Krier rejects this on the grounds that anti-Coasean externalities still need pricing, and pricing requires platform mediation.
- **Two layers (law + individual, no market)**: this is what an A2A protocol-only world would look like. No platform — agents talk directly. The problem is that the protocol *is* the platform, just unowned. Power concentrates in protocol design rather than platform operation, which is in some ways worse.
- **Five layers (e.g. law + supranational + national + platform + individual)**: this is the EU regulator's preferred stack. Higher friction, more accountability, more capture surface.
- **Seven layers (per OSI-style decomposition)**: this is the full bureaucratic dream. Incompatible with sub-second negotiation.

The three-layer Matryoshka is the minimum stack that covers the irreducible problems while keeping the negotiation latency tractable.

---

## What the layers reject, in each attractor

The model's `rejection_share_by_layer` chart, visible per-scenario in the dashboard, shows which layer is binding in which regime. Stylized findings:

### Smoothworld (low α, high cap, e.g. Coasean Paradise)
- **Cost rejection**: low (~5%) — friction is low, most trades clear
- **Alignment rejection**: high (~50%+) — *individual will is the binding constraint*
- **Market rejection**: moderate (~25%) — platforms still filter, but lightly
- **Law rejection**: low (~10%) — most trades are legal

This is what a successful Coasean smoothing produces: the dominant *kind* of transaction failure is "I (or my agent on my behalf) didn't want to." That is a *good* failure mode — it means the economy is preference-revealing rather than friction-bound.

### Baroqueworld (high α, e.g. Baroque Cathedral)
- **Cost rejection**: rises (~15%) — folding-induced cross-stack costs eat into marginal trades
- **Alignment rejection**: similar to smooth (~45%) — individual filtering doesn't change much
- **Market rejection**: rises (~30%) — more platform layers, more filtering
- **Law rejection**: similar (~10%)

The proportions don't shift dramatically. What changes is that the *transactions that clear* are then *folded*, multiplying the nominal volume.

### Matryoshka Collapse (high market+individual taxes)
- **Cost rejection**: low (~10%)
- **Alignment rejection**: high (~55%)
- **Market rejection**: very high (~30%) — platforms are highly restrictive
- **Law rejection**: ~5%

Total governance overhead approaches 40%. The system is over-constrained: most attempted trades die in the gates. This is the failure mode of *too much* Matryoshka, where individual and platform-level filtering combine to suppress most economic activity.

---

## The "default position" problem

Krier raises this directly: agents operate within the rules, but *the rules themselves require a default*. Do people have a right to make noise, or a right to quiet? Do you have a right to clean air, or do polluters have a right to emit and be paid for restraint? The Coasean machinery clears either way, but the wealth distribution depends on which side starts with the entitlement.

The model is silent on this — it treats initial entitlements as fixed. But the **public_defender** scenario is implicitly an answer: a deliberate redistribution of *agent capability* (not entitlement) compensates for whatever entitlement asymmetries exist. This is not a substitute for getting the default right; it is a partial offset.

A more aggressive intervention — re-allocating actual entitlements via the Matryoshka law layer — would require modeling the law-layer as a richer object than a binary filter. We leave that for v2.

---

## What can break the Matryoshka

The three-layer stack assumes:

1. The state has *unique* coercion authority. (Threatened by stack-balkanization, by para-state actors with their own enforcement, by sovereign cloud platforms.)
2. The market layer is *plural* and *competitive*. (Threatened by foundation-model concentration, by switching costs, by network effects on platform choice.)
3. The individual layer is *genuinely individual*. (Threatened by foundation-model influence on agent personality defaults, by collective-bargaining clubs that absorb individual preferences, by social contagion.)

If any one of these conditions breaks down, the Matryoshka collapses into something else:

- If (1) breaks: anarchy or warlord-platform regime
- If (2) breaks: monopoly platform = de facto state, which then merges with (1)
- If (3) breaks: collective alignment = de facto market layer, eliminating individual layer

The model can simulate (2) and (3) breaking via concentration parameters. The hemispherical_schism scenario is implicitly a partial breakdown of (1) at the international level: each stack has its own coercion authority.

---

## The most important Matryoshka observation

Both Smoothworld and Baroqueworld can be *Matryoshka-respecting*. The smooth/striated dimension is largely *orthogonal* to the question of governance-stack architecture. You can have a Coasean Paradise with a thin or a thick Matryoshka; you can have a Baroque Cathedral with either.

This matters because it means the Bratton/Krier debate is not the only debate. *Who controls each Matryoshka layer* is an equally important and somewhat orthogonal question. A Krier-favoring liberal who is also a strong defender of the law layer; a Bratton-leaning Baroque-thinker who is also a strong defender of platform plurality — these are coherent and probably more representative positions than the cartoon poles.

The model is built so that you can vary smooth/striated and Matryoshka-thickness independently. Try it.

---

## References

- Krier, S. (2025). *Coasean Bargaining at Scale*, "Matryoshkan Alignment" section.
- Levin, M. (2019). *The Computational Boundary of a "Self": Developmental Bioelectricity Drives Multicellularity and Scale-Free Cognition*, Frontiers in Psychology.
- Bratton, B. (2015). *The Stack: On Software and Sovereignty*, MIT Press — for the original layered-stack framing of planetary computation.
- Schmitt, C. (1922). *Politische Theologie* — for the question of which layer holds the sovereign exception.
- Hadfield, G. K. (2025, May). Interview, *AIhub*. Normative-competence reading of alignment as participation in evolving community norms — the conceptual basis of the `NormConfig.enabled` regime.
- Hadfield, G. K. (2026). *Jurimetrics*, Winter — extended argument for normative infrastructure as the binding constraint on agent alignment.
- Hadfield, G. K. (2026, February). *Legal Infrastructure for Transformative AI Governance* — registration regimes for autonomous agents (the precondition for `PopulationConfig.registration_coverage > 0`).
