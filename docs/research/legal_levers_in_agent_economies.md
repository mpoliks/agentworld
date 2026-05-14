# Legal Levers in Agent Economies

> *"The state's coercive role becomes minimal."* — Coase (1960),
> describing the zero-transaction-cost limit.
>
> *"Legal infrastructure for transformative AI governance is the
> precondition for everything else."* — Hadfield (Feb 2026),
> arXiv:2602.01474.

Legal levers in agentworld are the policy moves a regulator, a
platform, or a sovereign can make to constrain agent behavior in the
agent-to-agent economy. The Coasean smoothing scenario assumes
governance can be thin; the Bratton folding scenario predicts
governance gets bypassed by recursive sub-markets. Both are
extremes. The interesting design space is the middle, where specific
legal moves push the economy toward one pole or the other without
either being absent or omnipotent.

This doc inventories the legal levers currently in the engine,
identifies one missing lever (transaction-size cap), and maps the full
set to the legal panel of the spatial sandbox.

---

## The Matryoshka stack as the legal substrate

`docs/concepts/matryoshkan_alignment.md` documents the three-layer
governance stack the engine implements: law (outermost), market /
platform (middle), individual alignment (innermost). Each layer
filters a transaction before execution; each layer can tax surplus on
executed transactions.

The legal lever panel exposes controls on all three layers:

- **Law layer**: `LawConfig.strength`, `LawConfig.capture`.
  Strength controls how often a transaction is rejected by the law
  gate. Capture controls how responsive law strength is to civic
  pushback vs. captured renewal. Both are documented in
  `docs/concepts/matryoshkan_alignment.md` and implemented in
  `engine/core/transactions.py:506` (the `law_gate` construction
  block).

- **Market / platform layer**: `market_layer_tax` (the surplus tax),
  `RegulatorConfig.enabled` and `RegulatorConfig.cost` (the
  Hadfield third-party regulator that can split the market layer
  into platform and regulator components). The W1a workstream
  separates `market_reject` into `platform_reject` and
  `regulator_reject`; this is the only existing path for
  Hadfield-style regulatory markets in the engine.

- **Individual layer**: `individual_layer_alignment_tax`. The
  filter itself (`align_reject`) is a function of the norm
  distance plus the new `certified_fraction` from
  `verifiable_semantics.md`.

The Matryoshka inventory of legal moves on its own gives the user
five sliders. But the Matryoshka is not the whole legal lever set —
two adjacent surfaces matter too.

---

## Pigouvian taxation as a non-Matryoshka lever

`docs/concepts/pigouvian_automation.md` documents the Pigouvian
A2A tax: a per-pair tax proportional to how far the pair is from
having a human consumer at either endpoint, recycled to humans via
one of three channels. The Pigouvian tax operates *after* the
Matryoshka filtering and *before* the Nash bargaining split, on
executed transactions. It is orthogonal to the layer stack.

The legal-panel surface for Pigouvian:

- **Tax rate** — `PigouvianConfig.tax_rate ∈ [0, 0.5]`.
- **Recycling channel** — `PigouvianConfig.recycling ∈
  {human_wealth, friction_subsidy, capability}`.
- **Progressivity** — `PigouvianConfig.recycling_progressivity`
  (the exponent on inverse-wealth weighting in the human_wealth
  channel).

The Pigouvian tax is the single most-developed legal lever in the
engine. Four scenarios in `docs/concepts/pigouvian_automation.md`
bracket the axis.

---

## Fold-depth and branching as legal levers

The folding operator in `docs/concepts/fractal_folding.md` is
parameterized by `folding.propensity`, `folding.branching`, and
`folding.max_depth`. The first two are agentic-side
parameters — they describe how readily agents spawn sub-markets.
The third is unambiguously a legal lever: a fold-depth cap is a
direct restriction on recursive market formation.

Two analogous restrictions in real-world law:

- US Glass-Steagall (1933) capped which financial intermediation
  layers a single firm could span. The repeal (1999) is the canonical
  example of removing a fold-depth cap with subsequent EBI inflation.
- EU MiCA (2023) caps derivative-on-derivative depth for crypto
  assets at two layers. The cap is a fold-depth restriction in
  agent-economy vocabulary.

The legal-panel surface:

- **Fold-depth cap** — `folding.max_depth ∈ {2, 3, 4, …, 10}`.
- **Fold-branching cap** — `folding.branching ∈ [1.0, 5.0]`.

Both are existing engine fields. The sandbox exposes them in the
legal panel rather than the agentic one because they describe what
the law tolerates, not what the agents are.

---

## The missing lever: transaction-size cap

The user explicitly named "transaction limits" as a legal lever. The
existing engine has no per-trade surplus ceiling. Every executed
transaction's surplus is determined by the Coasean bargaining formula
in `transactions.py`; there is no policy field that caps it.

Three real-world analogs make the case for adding one:

1. **Anti-money-laundering** transaction caps (US: $10,000 reporting
   threshold). These are not exactly value caps but rather caps on
   undocumented transactions. The agent-economy translation: cap on
   transactions whose two parties have not been certified by a
   Hadfield regulator.
2. **Securities regulation** position caps (e.g. SEC Rule 13D
   reporting at 5% of outstanding shares). These cap the *cumulative*
   trade size between two parties.
3. **Antitrust** merger thresholds (HSR Act notification at $111M).
   Caps on the surplus a single transaction can claim before
   regulatory review.

A `transaction_size_cap` field in the legal panel implements the
analog:

```python
@dataclass
class LawConfig:
    ...
    transaction_size_cap: float = inf  # default: no cap
    cap_recipient: str = "tax"  # "tax" | "reject"
```

If `cap_recipient = "tax"`, the surplus above the cap is taxed to
the law layer (a kind of windfall tax). If `cap_recipient =
"reject"`, the transaction is rejected by `law_reject` when its
expected surplus exceeds the cap.

The mechanism plugs into the existing law gate at
`transactions.py:506` (the `law_gate` construction block that scales
`base_surplus`). Cost: ~10 lines on the engine side.

---

## Interactions

Five interactions matter for the sandbox.

1. **Pigouvian × fold-depth cap.** Both push α down, but through
   different mechanisms. Pigouvian reduces wealth accrual at A2A
   intermediaries; fold-depth cap blocks the sub-market spawn
   directly. Pigouvian alone allows fold spawning but taxes the
   capture; fold-depth cap alone prevents the spawn. Combining them
   produces a more compressed Gini than either alone.

2. **Law strength × certified fraction.** When `LawConfig.strength`
   is high, the law gate filters more transactions. When
   `certified_fraction` is high, the individual gate filters fewer.
   The total rejection rate is the sum of the two layers'
   contributions. Two regimes can have the same total rejection rate
   but different distributions across layers — and different welfare
   profiles.

3. **Regulator presence × Pigouvian recycling.** A Hadfield regulator
   acts as a parallel filter to the platform layer. If `RegulatorConfig`
   is enabled and `pigouvian.recycling = "human_wealth"`, the
   recycling is redundant: the regulator already redistributes via the
   regulator-cost surplus tax. If `pigouvian.recycling =
   "capability"`, the two channels complement.

4. **Transaction-size cap × scale-free network.** Scale-free networks
   concentrate trade at hubs; hub transactions are systematically
   larger. A `transaction_size_cap` bites hardest at scale-free
   hubs and barely affects well-mixed networks. The cap is therefore
   network-conditional in its effect, which is the standard finding
   in antitrust enforcement.

5. **Fold-depth cap × autonomy.** High-autonomy agents are the ones
   spawning sub-markets. A fold-depth cap reduces their effective
   action space. The cap acts as a tax on autonomy without
   appearing as one in the rejection mix.

---

## What the user gets in the legal panel

Eight controls, four primary and four secondary:

**Primary**

- **Law strength** — `LawConfig.strength ∈ [0, 1]`
- **Pigouvian tax rate** — `PigouvianConfig.tax_rate ∈ [0, 0.5]`
- **Fold-depth cap** — `folding.max_depth ∈ {2, 4, 6, 8, 10}`
- **Transaction-size cap** — `LawConfig.transaction_size_cap` ∈
  `{inf, 100k, 10k, 1k}` (log-scale toggle)

**Secondary** (collapsible)

- **Regulator presence** — `RegulatorConfig.enabled` toggle
- **Pigouvian recycling channel** — radio over the three options
- **Pigouvian progressivity** — `PigouvianConfig.recycling_progressivity ∈ [0, 2]`
- **Market layer tax** — `market_layer_tax ∈ [0, 0.1]`

Default positions: middle of each range. The reading of the lever
panel as the user moves it: every control pushes α down (per
`docs/research/alpha_as_outcome.md`). What differs is *how* α moves
down — through reduced volume, reduced fold count, reduced surplus
capture at hubs, or reduced misunderstanding-driven rejection.

---

## What this means for the engine

Existing surface, no engine change:

- `LawConfig.strength`, `LawConfig.capture`
- `PigouvianConfig.*`
- `market_layer_tax`, `individual_layer_alignment_tax`
- `folding.max_depth`, `folding.branching`
- `RegulatorConfig.enabled`, `RegulatorConfig.cost`

New surface, engine PR required:

| Change | Path | Cost |
| --- | --- | --- |
| Add `transaction_size_cap` and `cap_recipient` to `LawConfig` | `engine/core/topology.py` | ~6 lines |
| Implement size-cap filter in `law_gate` | `engine/core/transactions.py:506` | ~12 lines |
| Add `windfall_tax_revenue` to `StepMetrics` | `engine/core/world.py` | ~3 lines |
| Recycle windfall tax via the same channels as Pigouvian | `engine/core/transactions.py` | ~8 lines |

Default `transaction_size_cap = inf`, `cap_recipient = "tax"`.
Existing scenarios run unchanged.

---

## References

- Hadfield, G. K. (Winter 2026). *Regulatory Markets: The Future of
  AI Governance.* Jurimetrics.
- Hadfield, G. K. (Feb 2026). *Legal Infrastructure for
  Transformative AI Governance.* arXiv:2602.01474.
- Hadfield, G. K. (May 2025). *Normative infrastructure for AI
  alignment.* AIhub.
- Krier, S. (Sept 2025). *Coasean Bargaining at Scale.* AI Policy
  Perspectives. The Matryoshka source.
- Coase, R. (1960). *The Problem of Social Cost.* Journal of Law
  and Economics.
- Pigou, A. C. (1920). *The Economics of Welfare.* Macmillan.
- Ostrom, E. (1990). *Governing the Commons.* Cambridge.
- Acemoglu, D., & Robinson, J. (2012). *Why Nations Fail.* Crown.
- `docs/concepts/matryoshkan_alignment.md` — the three-layer
  governance stack.
- `docs/concepts/pigouvian_automation.md` — the A2A tax mechanism.
- `docs/concepts/fractal_folding.md` — the folding operator and its
  parameters.
