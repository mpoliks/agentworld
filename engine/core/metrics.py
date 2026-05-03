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

from engine.core.population import Population


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
        self._last_gini = 0.0

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
    ) -> StepMetrics:
        self._cum_real += real_step
        self._cum_nominal += nominal_step
        self._cum_pigouvian_revenue += pigouvian_revenue
        # Authentic welfare defaults to real welfare when the demand-side
        # feedback flag is off (preserves backward-compat metric values).
        if real_authentic_step is None:
            real_authentic_step = real_step
        self._cum_real_authentic += real_authentic_step
        self._cum_real_from_intermediation += real_added_productive
        self._cum_pigouvian_revenue += pigouvian_revenue

        ebi = (self._cum_nominal / self._cum_real) if self._cum_real > 0 else 1.0
        ebi_authentic = (
            (self._cum_nominal / self._cum_real_authentic)
            if self._cum_real_authentic > 0
            else 1.0
        )

        # Gini is O(n log n) — a 88M sort costs ~1.2s per call. Recompute
        # every K steps and carry forward in between (caller controls K).
        if step == 0 or (gini_every_k_steps > 1 and step % gini_every_k_steps == 0) or gini_every_k_steps <= 1:
            gini = gini_coefficient(pop.wealth, pop.weight)
            self._last_gini = gini
        else:
            gini = self._last_gini

        real_humans = float((pop.weight * pop.is_human).sum())
        per_cap = (self._cum_real / real_humans) if real_humans > 0 else 0.0

        total_attempted = (
            n_tx_real + rejected_law + rejected_market + rejected_align + rejected_cost
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
            (rejected_law + rejected_market + rejected_align) / total_attempted
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
        )
        self.history.append(m)
        return m
