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
    - human_legibility_index       : fraction of GDP a human can in principle audit
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
    ) -> StepMetrics:
        self._cum_real += real_step
        self._cum_nominal += nominal_step

        ebi = (self._cum_nominal / self._cum_real) if self._cum_real > 0 else 1.0

        # Gini is O(n log n) — a 88M sort costs ~1.2s per call. Recompute
        # every K steps and carry forward in between (caller controls K).
        if step == 0 or (gini_every_k_steps > 1 and step % gini_every_k_steps == 0) or gini_every_k_steps <= 1:
            gini = gini_coefficient(pop.wealth, pop.weight)
            self._last_gini = gini
        else:
            gini = self._last_gini

        real_humans = float((pop.weight * pop.is_human).sum())
        per_cap = (self._cum_real / real_humans) if real_humans > 0 else 0.0

        # Human legibility: 1/EBI capped at 1.
        leg = 1.0 / max(ebi, 1.0)

        total_attempted = (
            n_tx_real + rejected_law + rejected_market + rejected_align + rejected_cost
        )
        gov_overhead = (
            (rejected_law + rejected_market + rejected_align) / total_attempted
            if total_attempted > 0
            else 0.0
        )

        a2a, h2a, h2h = interaction_shares(pop)

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
        )
        self.history.append(m)
        return m
