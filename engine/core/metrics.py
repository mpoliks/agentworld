"""
Metrics — what we measure, and (recursively) why.

Every metric here corresponds to a position taken in the conceptual brief.
The most important metric is the *exo-baroque index*:
    EBI = nominal_GDP / real_welfare

In Smoothworld (alpha→0): EBI → 1. Every dollar of GDP is a dollar of welfare.
In Baroqueworld (alpha→1): EBI → ∞. Most GDP is machine-internal accounting.

Also tracked:
    - real_per_capita_welfare      : the only thing that matters to a human
    - gini_wealth                  : how concentrated wealth is
    - fold_depth                   : how deep the recursive intermediation goes
    - human_legibility_index       : share of executed activity with at least one human in the loop (h2h + h2a)
    - agent_to_human_interaction   : ratio of A2A vs H2A vs H2H interactions
    - governance_overhead          : fraction of surplus consumed by Matryoshka layers
    - rejected_fraction            : how much potential trade was filtered out
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from engine.core.population import N_SECTORS, Population


@dataclass
class StepMetrics:
    step: int
    alpha: float

    real_welfare_step: float
    real_welfare_cumulative: float

    nominal_gdp_step: float
    nominal_gdp_cumulative: float

    exo_baroque_index: float
    fold_max_depth: int

    n_transactions_real: float
    n_sub_markets_added: float

    rejected_law: float
    rejected_market: float
    rejected_align: float
    rejected_cost: float

    gini_wealth: float
    real_per_capita_welfare: float

    human_legibility_index: float
    governance_overhead_fraction: float

    a2a_share: float
    h2a_share: float
    h2h_share: float

    # ---- Demand-side feedback (DemandConfig) ---------------------------------
    # `real_welfare_authentic_*` is the share of real welfare that ultimately
    # reaches a human consumer. Equals `real_welfare_*` when DemandConfig is
    # disabled (the back-compat default). `exo_baroque_authentic` is
    # nominal_cumulative / max(authentic_cumulative, eps).
    real_welfare_authentic_step: float = 0.0
    real_welfare_authentic_cumulative: float = 0.0
    exo_baroque_authentic: float = 1.0

    # ---- Productive vs parasitic folding split (TopologyConfig) -------------
    # Per-step productive welfare yield per fold-nominal dollar (in [0, 1]),
    # the residual nominal share, and the cumulative welfare contributed by
    # productive folding. All zero unless `base_variance_absorption > 0`
    # (the back-compat default).
    productive_welfare_yield: float = 0.0
    parasitic_nominal_residual: float = 1.0
    real_welfare_from_intermediation_cumulative: float = 0.0

    # ---- Dynamic law layer (LawConfig) ----------------------------------------
    law_strength: float = 1.0
    law_capture: float = 0.0
    law_weak_surplus_loss_step: float = 0.0
    law_capture_surplus_loss_step: float = 0.0
    law_upkeep_cost_step: float = 0.0
    law_surplus_loss_fraction: float = 0.0

    # ---- Pigouvian automation tax (PigouvianConfig) --------------------------
    pigouvian_revenue_step: float = 0.0
    pigouvian_revenue_cumulative: float = 0.0
    pigouvian_effective_rate: float = 0.0

    # ---- Windfall tax (LawConfig.transaction_size_cap, tax mode) -------------
    # Surplus captured above the per-pair size cap. Zero when the cap
    # is inf (the default) or when cap_recipient = "reject".
    windfall_tax_revenue_step: float = 0.0
    windfall_tax_revenue_cumulative: float = 0.0

    # ---- Compute / power admission (ComputeConfig) ---------------------------
    # `rejected_compute` is the per-tick pair-weight rejected at the
    # compute gate (parallel to rejected_law / _market / _align /
    # _cost / _permeability / _regulator). `compute_budget_remaining`
    # is the carryover pool state after this tick's debiting. Both
    # default to 0 when ComputeConfig.enabled = False.
    rejected_compute: float = 0.0
    compute_budget_remaining: float = 0.0

    # ---- Emergence diagnostics (StrategyConfig) ------------------------------
    endogenous_alpha: float = -1.0
    alpha_std: float = 0.0
    strategy_entropy: float = 0.0
    realized_folding_ratio: float = 0.0
    pref_smooth_share: float = 0.0
    pref_striated_share: float = 0.0

    # ---- Institutional dynamics (InstitutionConfig) --------------------------
    n_firms: int = 0
    mean_firm_size: float = 0.0
    firm_concentration: float = 0.0
    independent_share: float = 1.0

    # ---- Population dynamics (PopulationDynamicsConfig) ----------------------
    mean_capability: float = 0.0
    capability_std: float = 0.0
    churn_rate: float = 0.0
    wealth_floor: float = 0.0

    # ---- Fold cascade per-depth contribution (B4 visualisation) -------------
    # Per-step nominal contribution at each fold depth (index 0 = depth 1).
    # Empty when folding is gated off; not used by the engine math; consumed
    # by the live fold-tree visualisation. Kept on a separate field with a
    # default factory so all serializers continue to round-trip cleanly.
    fold_per_depth_contribution: list = field(default_factory=list)

    # ---- Stock-flow consistency (engine/core/ledger.py) ----------------------
    # `wealth_imbalance_abs` is the residual between observed total
    # population wealth change this step and the sum of *categorized*
    # predicted flows the ledger recorded. Relative is normalised against
    # end-of-step total wealth. `welfare_imbalance_abs` is the residual
    # between observed `real_welfare_step` and the welfare ledger's clipped
    # net. All three should be tiny (~ float32 quantization) when the
    # engine respects its own accounting identity. See
    # `docs/concepts/stock_flow_consistency.md` and
    # `engine/tests/test_stock_flow.py`.
    wealth_imbalance_abs: float = 0.0
    wealth_imbalance_relative: float = 0.0
    welfare_imbalance_abs: float = 0.0

    # ---- Live-engine V2: per-pair sample records ----------------------------
    # Populated only when `WorldConfig.pair_sample_k > 0`. Each record is a
    # `PairSample` dataclass (engine/core/transactions.py). Default empty so
    # canonical pinned StepMetrics serializations remain identical. See
    # `docs/plans/live_engine.md` § V2.
    pair_samples: list = field(default_factory=list)

    # ---- Cockpit Phase 2: population distribution snapshots -----------------
    # All three default to empty lists so legacy StepMetrics serialisations
    # stay identical when the cockpit's distribution emissions are off.
    #
    # `wealth_lorenz`: 11-point Lorenz curve. Index i ∈ [0, 10] is the
    # cumulative wealth share held by the bottom 10·i percent of the
    # weighted population. `wealth_lorenz[0] == 0`, `wealth_lorenz[10] == 1`
    # by construction. Cadence matches `gini_every_k_steps`.
    wealth_lorenz: list = field(default_factory=list)
    # 20-bin weighted capability histograms over [0, 1], split by
    # human/agent so the cockpit can overlay them. Bin edges are
    # `np.linspace(0, 1, 21)`.
    capability_hist_humans: list = field(default_factory=list)
    capability_hist_agents: list = field(default_factory=list)
    # Per-step real welfare bucketed by the production-side sector
    # (`sec_a`) of executed pairs. Length N_SECTORS. Sums to
    # `real_welfare_step` (modulo rounding).
    real_welfare_per_sector_step: list = field(default_factory=list)

    # Cockpit Pass 2: persistent cast snapshot. List of dicts, one per
    # cast member; each carries {idx, is_human, sector, wealth,
    # capability, autonomy, firm_id, stack}. Empty when
    # `WorldConfig.cast_size == 0` (the default), so legacy pinned
    # StepMetrics serialisations stay identical. Attached by World.step
    # after `step_metrics()` returns.
    cast_snapshot: list = field(default_factory=list)

    # ---- Flow-sensitive inequality metrics ------------------------------------
    # Terminal `gini_wealth` is dominated by the initial wealth distribution
    # (lognormal humans, Pareto agents) and barely moves under topology
    # parameters within typical run lengths (variance of (gini_T - gini_0) is
    # ~7e-11 across Sobol samples at n_steps=18). The metrics below isolate
    # what the topology *does* by referencing the wealth state at step 0.
    #
    #   `top_decile_wealth_share` — fraction of total wealth held by the top
    #     10% (weighted). Snapshot, not stock-derived; varies more than gini
    #     over short horizons.
    #
    #   `top_decile_share_change` — `top_decile_wealth_share` at step t minus
    #     its value at step 0. Negative under redistributive topologies,
    #     positive under concentrating ones. Designed to be parameter-
    #     discriminative under Sobol.
    #
    #   `gini_wealth_change_abs` — gini coefficient of |wealth_t - wealth_0|.
    #     Captures *churn* (how much each agent's wealth shifted, signed
    #     direction discarded), regardless of whether the population-level
    #     distribution moved. Also Sobol-friendly.
    top_decile_wealth_share: float = 0.0
    top_decile_share_change: float = 0.0
    gini_wealth_change_abs: float = 0.0

    # ---- Permeability boundary (W1c) -----------------------------------------
    # Cross-stack pairs rejected at the Tomašev / Jacobs sandbox boundary
    # before any Matryoshka filter. Zero when `cross_stack_permeability == 1.0`
    # (the historical default and the canonical pre-2026-05 behavior).
    # Excluded from `governance_overhead_fraction` by design: permeability
    # is a boundary condition, not Matryoshka governance.
    rejected_permeability: float = 0.0

    # ---- Hadfield regulator gate (W1a) ---------------------------------------
    # Pairs rejected by the government-licensed third-party regulator,
    # parallel to but distinct from the platform/`market` gate. Zero when
    # `RegulatorConfig.enabled = False` (the canonical default), so historical
    # baselines remain bit-identical. Counted *inside* the Matryoshka
    # governance overhead — the regulator is one of the middle-layer gates,
    # so its rejections roll up into `governance_overhead_fraction`.
    rejected_regulator: float = 0.0
    # Share of unregistered endpoints whose `registered` bit was forged
    # to True in the regulator's view this step (S1 stretch — audit-trail
    # tampering). 0.0 when `audit_tampering_rate = 0` (the default) or
    # when no unregistered endpoints appeared in the sample. A high
    # value at high capture means the floor is being silently defeated:
    # unregistered agents trade as if registered.
    forged_registration_share: float = 0.0

    # ---- Tail-tamed EBI for variance decomposition ---------------------------
    # Raw `exo_baroque_index = nominal/real` has an unbounded right tail
    # (heavily-folded scenarios push real -> 0 and EBI -> infinity). The
    # tail breaks the Saltelli/Sobol estimator the same way `gini_wealth`
    # did: across an 8704-sim sweep at N=512, max(ST)=1.51 with CI ±2.71
    # for `exo_baroque_index`, vs ~0.84 with CI ±0.12 once log-transformed.
    # log(EBI) preserves rank ordering of EBI (so any "scenario A is
    # more baroque than B" claim still holds) and dashboards keep the
    # raw value above; this field exists for Sobol use and for any
    # variance-sensitive analysis that wants compressed tails.
    log_exo_baroque_index: float = 0.0
    log_exo_baroque_authentic: float = 0.0

    # ---- Human-side labor market (W2c, Jacobs) -------------------------------
    # Real surplus routed to humans this step by the W2c labor wedge.
    # Zero when `LaborConfig.enabled = False`. Cumulative version is
    # `human_labor_wage_cumulative`.
    human_labor_wage_step: float = 0.0
    human_labor_wage_cumulative: float = 0.0
    # Per-sector cumulative wage. List of length N_SECTORS = 12;
    # `[s]` is the cumulative wedge attributed to sector `s` (the
    # production-side sector of contributing pairs, via `sec_a`).
    # Sums to `human_labor_wage_cumulative` by construction. Zeros when
    # `LaborConfig.enabled = False`. `list[float]` so it serialises
    # cleanly through `StepMetrics.to_dict()` / dataclasses.asdict.
    human_labor_wage_cumulative_per_sector: list = field(default_factory=list)
    # Human-only wealth Gini and per-capita welfare. Computed from the
    # human subset of the population; with W2c off, `gini_wealth_human`
    # is just the wealth-side gini restricted to humans and
    # `real_per_capita_welfare_human` is the per-human-capita share of
    # total real welfare (i.e. identical denominator to
    # `real_per_capita_welfare`, since the existing metric already
    # divides by human population). With W2c on, the human-only Gini
    # reflects the wage-channel redistribution and the per-capita
    # human-welfare track tracks the wage cumulative.
    gini_wealth_human: float = 0.0
    real_per_capita_welfare_human: float = 0.0


def gini_coefficient(x: np.ndarray, weights: Optional[np.ndarray] = None) -> float:
    """Weighted Gini coefficient. O(n log n)."""
    x = np.asarray(x, dtype=np.float64)
    if weights is None:
        weights = np.ones_like(x)
    weights = np.asarray(weights, dtype=np.float64)
    if x.sum() == 0:
        return 0.0
    order = np.argsort(x)
    x = x[order]
    w = weights[order]
    cw = np.cumsum(w)
    cwx = np.cumsum(w * x)
    total_w = cw[-1]
    total_wx = cwx[-1]
    if total_wx == 0:
        return 0.0
    # Lorenz formulation.
    g = 1.0 - 2.0 * np.sum(cwx * w) / (total_w * total_wx) + np.sum(w * w * x) / (
        total_w * total_wx
    )
    # Clamp to [0, 1].
    return float(max(0.0, min(1.0, g)))


def top_decile_wealth_share(
    wealth: np.ndarray,
    weights: Optional[np.ndarray] = None,
) -> float:
    """Wealth-weighted share of total wealth held by the top 10% by weight.

    Returns 0 if total wealth is non-positive. Sorts descending by per-unit
    wealth, takes the top weight-decile of the population, returns that
    bucket's wealth share. O(n log n).
    """
    x = np.asarray(wealth, dtype=np.float64)
    if weights is None:
        weights = np.ones_like(x)
    w = np.asarray(weights, dtype=np.float64)
    total_w = float(w.sum())
    total_wx = float((w * x).sum())
    if total_w <= 0 or total_wx <= 0:
        return 0.0
    # Sort descending by per-unit wealth.
    order = np.argsort(-x)
    w_sorted = w[order]
    x_sorted = x[order]
    cum_w = np.cumsum(w_sorted)
    # Find the index where cumulative weight crosses 10% of total.
    cutoff = 0.10 * total_w
    idx = int(np.searchsorted(cum_w, cutoff, side="left"))
    idx = min(idx, len(cum_w) - 1)
    # Fully-included entries: 0..idx-1. Partial entry at idx contributes
    # the leftover weight to hit exactly 10%.
    if idx == 0:
        # First entry already exceeds the decile; pro-rate it.
        frac = cutoff / w_sorted[0] if w_sorted[0] > 0 else 0.0
        wealth_in_decile = frac * w_sorted[0] * x_sorted[0]
    else:
        full_part = float((w_sorted[:idx] * x_sorted[:idx]).sum())
        residual_w = cutoff - float(cum_w[idx - 1])
        residual_w = max(0.0, residual_w)
        wealth_in_decile = full_part + residual_w * x_sorted[idx]
    return float(min(1.0, max(0.0, wealth_in_decile / total_wx)))


def interaction_shares(pop: Population) -> tuple[float, float, float]:
    """
    Estimate the share of interactions that are A2A, H2A, H2H, weighted by
    autonomy * weight (more autonomous prototypes generate more interactions
    per real entity).
    """
    activity = pop.weight * (0.4 + 0.6 * pop.autonomy)
    h_act = activity[pop.is_human].sum()
    a_act = activity[~pop.is_human].sum()
    total = h_act + a_act
    if total == 0:
        return 0.0, 0.0, 0.0
    p_h = h_act / total
    p_a = a_act / total
    h2h = p_h * p_h
    h2a = 2 * p_h * p_a
    a2a = p_a * p_a
    return float(a2a), float(h2a), float(h2h)


@dataclass
class MetricsHistory:
    steps: list[StepMetrics] = field(default_factory=list)

    def append(self, m: StepMetrics):
        self.steps.append(m)

    def to_dict(self) -> dict:
        if not self.steps:
            return {}
        keys = list(self.steps[0].__dict__.keys())
        return {k: [getattr(s, k) for s in self.steps] for k in keys}


class Metrics:
    """A small helper to compute per-step metrics and accumulate history."""

    def __init__(self):
        self.history = MetricsHistory()
        self._cum_real = 0.0
        self._cum_nominal = 0.0
        self._cum_real_authentic = 0.0
        self._cum_real_from_intermediation = 0.0
        self._cum_pigouvian_revenue = 0.0
        # PR #3: cumulative windfall tax revenue from
        # LawConfig.transaction_size_cap (tax mode).
        self._cum_windfall_tax_revenue = 0.0
        # W2c: cumulative wage routed to humans by the labor wedge.
        self._cum_human_labor_wage = 0.0
        # W2c per-sector extension: per-sector cumulative wage. Sums to
        # `_cum_human_labor_wage` by construction. Zero when W2c is off.
        self._cum_human_labor_wage_per_sector = np.zeros(N_SECTORS, dtype=np.float64)
        # Cockpit Phase 2: cached distribution snapshots — reused between
        # recompute ticks so the JSON-serialised StepMetrics is always
        # populated (instead of empty lists on non-recompute steps).
        self._last_wealth_lorenz: list = []
        self._last_cap_hist_humans: list = []
        self._last_cap_hist_agents: list = []
        # W2c: human-only wealth Gini, cached on the gini_every_k_steps
        # throttle so the recompute cadence matches the population-wide
        # Gini.
        self._last_gini_human = 0.0
        self._last_gini = 0.0
        # Snapshot of per-prototype wealth at step 0; used to compute the
        # flow-sensitive inequality metrics. Set on the first call to
        # `step_metrics`. Stored as float64 so the (wealth - wealth_initial)
        # difference doesn't lose precision at xlarge scales.
        self._wealth_initial: Optional[np.ndarray] = None
        self._initial_top_decile_share: float = 0.0
        self._last_top_decile_share: float = 0.0
        self._last_top_decile_share_change: float = 0.0
        self._last_gini_change_abs: float = 0.0

    def step_metrics(
        self,
        step: int,
        pop: "Population",
        alpha: float,
        real_step: float,
        nominal_step: float,
        n_tx_real: float,
        n_subs: float,
        fold_depth: int,
        rejected_law: float,
        rejected_market: float,
        rejected_align: float,
        rejected_cost: float,
        rejected_permeability: float = 0.0,
        rejected_regulator: float = 0.0,
        forged_registration_share: float = 0.0,
        human_labor_wage_step: float = 0.0,
        human_wage_per_sector_step: Optional[np.ndarray] = None,
        gini_every_k_steps: int = 1,
        real_authentic_step: Optional[float] = None,
        productive_welfare_yield: float = 0.0,
        real_added_productive: float = 0.0,
        law_strength: float = 1.0,
        law_capture: float = 0.0,
        law_weak_surplus_loss: float = 0.0,
        law_capture_surplus_loss: float = 0.0,
        law_upkeep_cost: float = 0.0,
        pigouvian_revenue: float = 0.0,
        windfall_tax_revenue: float = 0.0,
        rejected_compute: float = 0.0,
        compute_budget_remaining: float = 0.0,
        a2a_share: Optional[float] = None,
        h2a_share: Optional[float] = None,
        h2h_share: Optional[float] = None,
        strategy_enabled: bool = False,
        realized_alpha: float = 0.0,
        realized_folding_ratio_value: float = 0.0,
        institutions_enabled: bool = False,
        dynamics_enabled: bool = False,
        churn_count: int = 0,
        fold_per_depth_contribution: Optional[list] = None,
        wealth_imbalance_abs: float = 0.0,
        wealth_imbalance_relative: float = 0.0,
        welfare_imbalance_abs: float = 0.0,
        real_surplus_per_sector_step: Optional[np.ndarray] = None,
    ) -> StepMetrics:
        self._cum_real += real_step
        self._cum_nominal += nominal_step
        self._cum_pigouvian_revenue += pigouvian_revenue
        self._cum_windfall_tax_revenue += windfall_tax_revenue
        # Authentic welfare defaults to real welfare when the demand-side
        # feedback flag is off (preserves backward-compat metric values).
        if real_authentic_step is None:
            real_authentic_step = real_step
        self._cum_real_authentic += real_authentic_step
        self._cum_real_from_intermediation += real_added_productive
        self._cum_pigouvian_revenue += pigouvian_revenue
        # W2c: cumulative labor wedge routed to humans.
        self._cum_human_labor_wage += float(human_labor_wage_step)
        if human_wage_per_sector_step is not None:
            self._cum_human_labor_wage_per_sector += np.asarray(
                human_wage_per_sector_step, dtype=np.float64
            )

        ebi = (self._cum_nominal / self._cum_real) if self._cum_real > 0 else 1.0
        ebi_authentic = (
            (self._cum_nominal / self._cum_real_authentic)
            if self._cum_real_authentic > 0
            else 1.0
        )
        # Tail-tamed EBI for Sobol / variance work. EBI is always > 0 (both
        # numerator and denominator are non-negative running sums; EBI
        # defaults to 1.0 when real == 0). The 1e-12 floor is defensive.
        log_ebi = float(np.log(max(ebi, 1e-12)))
        log_ebi_authentic = float(np.log(max(ebi_authentic, 1e-12)))

        # Gini is O(n log n) — a 88M sort costs ~1.2s per call. Recompute
        # every K steps and carry forward in between (caller controls K).
        # Top-decile share and the flow-sensitive inequality metrics share
        # the same recompute schedule.
        recompute = (
            step == 0
            or (gini_every_k_steps > 1 and step % gini_every_k_steps == 0)
            or gini_every_k_steps <= 1
        )
        if recompute:
            gini = gini_coefficient(pop.wealth, pop.weight)
            self._last_gini = gini

            # W2c: human-only wealth Gini. Computed on the same cadence
            # as the population-wide Gini so the throttle still applies.
            h_mask = pop.is_human
            if h_mask.any():
                self._last_gini_human = gini_coefficient(
                    pop.wealth[h_mask], pop.weight[h_mask]
                )
            else:
                self._last_gini_human = 0.0

            # Capture the initial wealth state on the first call so the
            # flow-sensitive metrics can reference it on every subsequent
            # step. Cast to float64 because per-prototype wealth is float32
            # and the differences need full precision.
            if self._wealth_initial is None:
                self._wealth_initial = np.asarray(
                    pop.wealth, dtype=np.float64
                ).copy()
                self._initial_top_decile_share = top_decile_wealth_share(
                    self._wealth_initial, pop.weight
                )

            top_dec = top_decile_wealth_share(pop.wealth, pop.weight)
            top_dec_change = top_dec - self._initial_top_decile_share
            wealth_delta_abs = np.abs(
                np.asarray(pop.wealth, dtype=np.float64) - self._wealth_initial
            )
            gini_change_abs = gini_coefficient(wealth_delta_abs, pop.weight)
            self._last_top_decile_share = top_dec
            self._last_top_decile_share_change = top_dec_change
            self._last_gini_change_abs = gini_change_abs

            # Cockpit Phase 2: 11-point Lorenz curve over weighted wealth.
            # Sort by wealth ascending, then walk cumulative-weight thresholds
            # at [0, 0.1, 0.2, …, 1.0] and read the cumulative-wealth share.
            wealth = np.asarray(pop.wealth, dtype=np.float64)
            weight = np.asarray(pop.weight, dtype=np.float64)
            order = np.argsort(wealth)
            ws = wealth[order]
            wt = weight[order]
            cum_w = np.cumsum(wt)
            cum_wealth = np.cumsum(ws * wt)
            total_w = cum_w[-1] if cum_w.size else 0.0
            total_wealth = cum_wealth[-1] if cum_wealth.size else 0.0
            if total_w > 0 and total_wealth > 0:
                pop_targets = np.linspace(0.0, 1.0, 11) * total_w
                # interp cumulative wealth at each cumulative-weight target.
                lorenz = np.interp(pop_targets, cum_w, cum_wealth) / total_wealth
                lorenz[0] = 0.0
                lorenz[-1] = 1.0
                self._last_wealth_lorenz = [float(x) for x in lorenz]
            else:
                self._last_wealth_lorenz = [0.0] * 11

            # 20-bin weighted capability histograms, split by H/A.
            cap = np.asarray(pop.capability, dtype=np.float64)
            h_mask_cap = pop.is_human.astype(bool)
            bins = np.linspace(0.0, 1.0, 21)
            if h_mask_cap.any():
                hh, _ = np.histogram(cap[h_mask_cap], bins=bins, weights=weight[h_mask_cap])
            else:
                hh = np.zeros(20, dtype=np.float64)
            agent_mask_cap = ~h_mask_cap
            if agent_mask_cap.any():
                ah, _ = np.histogram(cap[agent_mask_cap], bins=bins, weights=weight[agent_mask_cap])
            else:
                ah = np.zeros(20, dtype=np.float64)
            self._last_cap_hist_humans = [float(x) for x in hh]
            self._last_cap_hist_agents = [float(x) for x in ah]
        else:
            gini = self._last_gini

        top_dec_share = self._last_top_decile_share
        top_dec_share_change = self._last_top_decile_share_change
        gini_change_abs = self._last_gini_change_abs

        real_humans = float((pop.weight * pop.is_human).sum())
        per_cap = (self._cum_real / real_humans) if real_humans > 0 else 0.0
        # W2c: per-capita human welfare = cumulative wage routed to
        # humans / human population. With W2c off, the cumulative wage
        # is zero by construction and this lands at 0; with W2c on, it
        # tracks the wage-channel-only welfare.
        per_cap_human = (
            (self._cum_human_labor_wage / real_humans) if real_humans > 0 else 0.0
        )

        total_attempted = (
            n_tx_real
            + rejected_law
            + rejected_market
            + rejected_align
            + rejected_cost
            + rejected_permeability
            + rejected_regulator
        )
        law_surplus_loss = (
            law_weak_surplus_loss + law_capture_surplus_loss + law_upkeep_cost
        )
        law_loss_fraction = (
            law_surplus_loss / (nominal_step + law_surplus_loss)
            if nominal_step + law_surplus_loss > 0
            else 0.0
        )
        gov_overhead = (
            (rejected_law + rejected_market + rejected_regulator + rejected_align)
            / total_attempted
            if total_attempted > 0
            else 0.0
        )

        if a2a_share is None or h2a_share is None or h2h_share is None:
            a2a, h2a, h2h = interaction_shares(pop)
        else:
            a2a, h2a, h2h = a2a_share, h2a_share, h2h_share

        # Human legibility: share of executed activity with at least one
        # human in the loop — i.e. transactions a human can in principle
        # audit. Equivalent to 1 - a2a_share. This deliberately replaces
        # the old definition (1/EBI), which was a pure algebraic inversion
        # of EBI and conveyed no independent information. The new
        # definition tracks human presence in the transaction graph,
        # which moves on a different axis from nominal/real divergence.
        leg = float(min(1.0, max(0.0, h2h + h2a)))

        productive_yield = float(min(1.0, max(0.0, productive_welfare_yield)))
        parasitic_residual = float(1.0 - productive_yield)

        pigouvian_eff_rate = (
            pigouvian_revenue / real_step if real_step > 0 else 0.0
        )

        endogenous_alpha = -1.0
        alpha_std = 0.0
        strategy_entropy = 0.0
        realized_folding_ratio = 0.0
        pref_smooth_share = 0.0
        pref_striated_share = 0.0
        if strategy_enabled and pop.intermediation_pref is not None:
            pref = pop.intermediation_pref.astype(np.float64, copy=False)
            weight = pop.weight.astype(np.float64, copy=False)
            w_sum = float(weight.sum())
            if w_sum > 0:
                endogenous_alpha = float((pref * weight).sum() / w_sum)
                alpha_var = float((((pref - endogenous_alpha) ** 2) * weight).sum() / w_sum)
                alpha_std = float(np.sqrt(max(0.0, alpha_var)))
                pref_smooth_share = float(weight[pref < 0.3].sum() / w_sum)
                pref_striated_share = float(weight[pref > 0.7].sum() / w_sum)
            if pop.last_action is not None:
                actions = pop.last_action[pop.last_action >= 0]
                if actions.size > 0:
                    counts = np.bincount(actions, minlength=3).astype(np.float64)
                    probs = counts / counts.sum()
                    nz = probs > 0
                    strategy_entropy = float(-(probs[nz] * np.log(probs[nz])).sum())
            realized_folding_ratio = float(max(0.0, realized_folding_ratio_value))

        n_firms = 0
        mean_firm_size = 0.0
        firm_concentration = 0.0
        independent_share = 1.0
        if institutions_enabled and pop.firm_id is not None:
            firm_id = pop.firm_id
            active = firm_id >= 0
            independent_share = float((~active).sum() / max(pop.n, 1))
            if active.any():
                counts = np.bincount(firm_id[active])
                sizes = counts[counts > 0].astype(np.float64)
                n_firms = int(sizes.size)
                mean_firm_size = float(sizes.mean()) if sizes.size > 0 else 0.0
                total_size = sizes.sum()
                firm_concentration = (
                    float(((sizes / total_size) ** 2).sum()) if total_size > 0 else 0.0
                )

        mean_capability = 0.0
        capability_std = 0.0
        churn_rate = 0.0
        wealth_floor = 0.0
        if dynamics_enabled:
            mean_capability = float(pop.capability.mean())
            capability_std = float(pop.capability.std())
            churn_rate = float(churn_count / max(pop.n, 1))
            wealth_floor = float(np.percentile(pop.wealth, 10))

        m = StepMetrics(
            step=step,
            alpha=alpha,
            real_welfare_step=real_step,
            real_welfare_cumulative=self._cum_real,
            nominal_gdp_step=nominal_step,
            nominal_gdp_cumulative=self._cum_nominal,
            exo_baroque_index=ebi,
            fold_max_depth=fold_depth,
            n_transactions_real=n_tx_real,
            n_sub_markets_added=n_subs,
            rejected_law=rejected_law,
            rejected_market=rejected_market,
            rejected_align=rejected_align,
            rejected_cost=rejected_cost,
            rejected_permeability=rejected_permeability,
            rejected_regulator=rejected_regulator,
            rejected_compute=rejected_compute,
            compute_budget_remaining=compute_budget_remaining,
            forged_registration_share=float(forged_registration_share),
            gini_wealth=gini,
            real_per_capita_welfare=per_cap,
            human_legibility_index=leg,
            governance_overhead_fraction=gov_overhead,
            a2a_share=a2a,
            h2a_share=h2a,
            h2h_share=h2h,
            real_welfare_authentic_step=real_authentic_step,
            real_welfare_authentic_cumulative=self._cum_real_authentic,
            exo_baroque_authentic=ebi_authentic,
            productive_welfare_yield=productive_yield,
            parasitic_nominal_residual=parasitic_residual,
            real_welfare_from_intermediation_cumulative=self._cum_real_from_intermediation,
            law_strength=law_strength,
            law_capture=law_capture,
            law_weak_surplus_loss_step=law_weak_surplus_loss,
            law_capture_surplus_loss_step=law_capture_surplus_loss,
            law_upkeep_cost_step=law_upkeep_cost,
            law_surplus_loss_fraction=float(min(1.0, max(0.0, law_loss_fraction))),
            pigouvian_revenue_step=pigouvian_revenue,
            pigouvian_revenue_cumulative=self._cum_pigouvian_revenue,
            pigouvian_effective_rate=float(min(1.0, max(0.0, pigouvian_eff_rate))),
            windfall_tax_revenue_step=windfall_tax_revenue,
            windfall_tax_revenue_cumulative=self._cum_windfall_tax_revenue,
            endogenous_alpha=endogenous_alpha,
            alpha_std=alpha_std,
            strategy_entropy=strategy_entropy,
            realized_folding_ratio=realized_folding_ratio,
            pref_smooth_share=pref_smooth_share,
            pref_striated_share=pref_striated_share,
            n_firms=n_firms,
            mean_firm_size=mean_firm_size,
            firm_concentration=firm_concentration,
            independent_share=independent_share,
            mean_capability=mean_capability,
            capability_std=capability_std,
            churn_rate=churn_rate,
            wealth_floor=wealth_floor,
            fold_per_depth_contribution=(
                list(fold_per_depth_contribution)
                if fold_per_depth_contribution
                else []
            ),
            wealth_lorenz=list(self._last_wealth_lorenz),
            capability_hist_humans=list(self._last_cap_hist_humans),
            capability_hist_agents=list(self._last_cap_hist_agents),
            real_welfare_per_sector_step=(
                [float(x) for x in np.asarray(real_surplus_per_sector_step, dtype=np.float64)]
                if real_surplus_per_sector_step is not None
                else []
            ),
            wealth_imbalance_abs=float(wealth_imbalance_abs),
            wealth_imbalance_relative=float(wealth_imbalance_relative),
            welfare_imbalance_abs=float(welfare_imbalance_abs),
            top_decile_wealth_share=float(top_dec_share),
            top_decile_share_change=float(top_dec_share_change),
            gini_wealth_change_abs=float(gini_change_abs),
            log_exo_baroque_index=log_ebi,
            log_exo_baroque_authentic=log_ebi_authentic,
            human_labor_wage_step=float(human_labor_wage_step),
            human_labor_wage_cumulative=float(self._cum_human_labor_wage),
            human_labor_wage_cumulative_per_sector=[
                float(v) for v in self._cum_human_labor_wage_per_sector
            ],
            gini_wealth_human=float(self._last_gini_human),
            real_per_capita_welfare_human=float(per_cap_human),
        )
        self.history.append(m)
        return m
