"""
Per-step stock-and-flow ledger.

The ledger is *instrumentation*. It does not change engine math. Every
flow the engine performs on the population's wealth stock or on the
per-step real-welfare account is recorded here by category. At end-of-step
the world compares the recorded flows against what actually happened and
records the residual to `StepMetrics`. A residual that is non-zero (beyond
numerical tolerance) indicates an unaccounted flow — a silent leak in the
accounting identity of the simulator.

Two accounts:

  - **Wealth** is a *stock*: total population wealth is
    `sum(pop.wealth * pop.weight)`. After each step the change in this
    stock should equal `wealth_in - wealth_out`.

  - **Welfare** is a *per-step flow*: the engine records `real_step` as
    `max(0, real_surplus_added - law_upkeep - fold_overhead +
    fold_productive)`. The ledger tracks the four components plus the
    clip-to-zero loss when the unclipped sum is negative; after the clip
    entry, `max(0, welfare_in - welfare_out) == real_step`.

The artifact this enables is a quantitative answer to: *did this step's
math close?*  See `engine/tests/test_stock_flow.py` for the regression.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StepLedger:
    """Categorised in/out flows for a single simulator step."""

    wealth_in: dict[str, float] = field(default_factory=dict)
    wealth_out: dict[str, float] = field(default_factory=dict)
    welfare_in: dict[str, float] = field(default_factory=dict)
    welfare_out: dict[str, float] = field(default_factory=dict)

    # ---- recording helpers -----------------------------------------------

    def add_wealth_in(self, category: str, amount: float) -> None:
        a = float(amount)
        if a == 0.0:
            return
        if a < 0.0:
            self.wealth_out[category] = self.wealth_out.get(category, 0.0) - a
        else:
            self.wealth_in[category] = self.wealth_in.get(category, 0.0) + a

    def add_wealth_out(self, category: str, amount: float) -> None:
        a = float(amount)
        if a == 0.0:
            return
        if a < 0.0:
            self.wealth_in[category] = self.wealth_in.get(category, 0.0) - a
        else:
            self.wealth_out[category] = self.wealth_out.get(category, 0.0) + a

    def add_welfare_in(self, category: str, amount: float) -> None:
        a = float(amount)
        if a == 0.0:
            return
        if a < 0.0:
            self.welfare_out[category] = self.welfare_out.get(category, 0.0) - a
        else:
            self.welfare_in[category] = self.welfare_in.get(category, 0.0) + a

    def add_welfare_out(self, category: str, amount: float) -> None:
        a = float(amount)
        if a == 0.0:
            return
        if a < 0.0:
            self.welfare_in[category] = self.welfare_in.get(category, 0.0) - a
        else:
            self.welfare_out[category] = self.welfare_out.get(category, 0.0) + a

    # ---- aggregates ------------------------------------------------------

    def wealth_net(self) -> float:
        return sum(self.wealth_in.values()) - sum(self.wealth_out.values())

    def welfare_net(self) -> float:
        return sum(self.welfare_in.values()) - sum(self.welfare_out.values())

    def wealth_residual(self, observed_delta: float) -> float:
        """observed - predicted; non-zero means an unaccounted flow."""
        return float(observed_delta) - self.wealth_net()

    def welfare_residual(self, observed_real_step: float) -> float:
        """observed - max(0, predicted); non-zero means an unaccounted flow.

        The engine clips real_step to zero. The ledger records `clip_floor`
        as a welfare_out entry when the unclipped net is negative, so that
        `max(0, welfare_net()) == observed_real_step` after that entry.
        """
        return float(observed_real_step) - max(0.0, self.welfare_net())

    def to_dict(self) -> dict:
        return {
            "wealth_in": dict(self.wealth_in),
            "wealth_out": dict(self.wealth_out),
            "welfare_in": dict(self.welfare_in),
            "welfare_out": dict(self.welfare_out),
            "wealth_net": self.wealth_net(),
            "welfare_net": self.welfare_net(),
        }
