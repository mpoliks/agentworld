"""W2c — explicit human-side labor market.

Pre-W2c the alpha-engine's every cleared pair distributes its surplus
50/50 between the two endpoints by Nash bargaining; there is no
explicit price-on-human-labor and no substitution closure that
addresses Jacobs's labor-displacement work. W2c adds the smallest
credible split: per-sector `labor_share` carves a wage wedge out of
cleared surplus, attenuated by `(1 − automation_gap)` so the wedge
shrinks as a pair becomes more A2A.

These tests pin five contracts:

1. Default-off is bit-identical to the canonical baseline.
2. With the wedge on, total wealth is conserved (the wedge re-routes
   surplus from agent-side Nash payouts to human-side wage payouts;
   it does not destroy or create welfare).
3. Human-side aggregate wealth strictly grows under the wedge versus
   the same scenario without it, holding everything else fixed.
4. The automation gap couples to the wedge: making a population more
   A2A (raising agent autonomy / lowering human share) shrinks the
   per-pair wage and the cumulative `human_labor_wage_cumulative`.
5. `gini_wealth_human` is a separate human-only Gini track, distinct
   from the population-wide `gini_wealth`. Per-capita human welfare
   reports the wage-channel cumulative.
"""

from __future__ import annotations

import numpy as np
import pytest

from engine.core.topology import LaborConfig
from engine.core.world import World
from engine.scenarios import get_scenario


def _small_cfg() -> "WorldConfig":  # noqa: F821
    cfg = get_scenario("equilibrium_drift")
    cfg.n_steps = 4
    cfg.pairs_per_step = 4_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 2_000
    cfg.seed = 91
    cfg.population.seed = 19
    return cfg


def _terminal_triple(world: World) -> tuple[float, float, float]:
    last = world.metrics.history.steps[-1]
    return (
        last.exo_baroque_index,
        last.real_welfare_cumulative,
        last.gini_wealth,
    )


def _human_wealth_total(world: World) -> float:
    pop = world.population
    h = pop.is_human
    return float((pop.wealth[h].astype(np.float64) * pop.weight[h].astype(np.float64)).sum())


def test_labor_off_is_bit_identical() -> None:
    """`LaborConfig.enabled = False` (the default) preserves canonical
    bit-identity.
    """
    cfg_default = _small_cfg()
    cfg_explicit = _small_cfg()
    cfg_explicit.topology.labor = LaborConfig(enabled=False, labor_share=0.5)

    w_default = World.build(cfg_default)
    w_default.run(progress=False)
    w_explicit = World.build(cfg_explicit)
    w_explicit.run(progress=False)

    assert _terminal_triple(w_default) == _terminal_triple(w_explicit)
    # Cumulative wage is zero in both, by construction.
    assert all(m.human_labor_wage_cumulative == 0.0 for m in w_default.metrics.history.steps)
    assert all(m.human_labor_wage_cumulative == 0.0 for m in w_explicit.metrics.history.steps)


def test_wedge_conserves_total_wealth() -> None:
    """The labor wedge re-routes surplus; it does not destroy or create
    it. Total real-wealth flow from transactions should match between
    a wedge-on and a wedge-off run (within float tolerance).
    """
    cfg_off = _small_cfg()
    w_off = World.build(cfg_off)
    w_off.run(progress=False)
    cum_real_off = w_off.metrics.history.steps[-1].real_welfare_cumulative

    cfg_on = _small_cfg()
    cfg_on.topology.labor = LaborConfig(enabled=True, labor_share=0.4)
    w_on = World.build(cfg_on)
    w_on.run(progress=False)
    cum_real_on = w_on.metrics.history.steps[-1].real_welfare_cumulative

    # Cumulative real welfare (a flow-summed measure) is unchanged by
    # the routing — the wedge moves wealth between accounts, not into
    # or out of the welfare ledger.
    assert cum_real_off == pytest.approx(cum_real_on, rel=1e-6), (
        f"Wedge should conserve cumulative real welfare: "
        f"off={cum_real_off:.6f}, on={cum_real_on:.6f}."
    )


def test_wedge_grows_human_wealth() -> None:
    """With the wedge on, human-side aggregate wealth strictly grows
    versus the same scenario without it, holding everything else
    fixed. This is the Jacobs claim made operational.
    """
    cfg_off = _small_cfg()
    w_off = World.build(cfg_off)
    w_off.run(progress=False)
    h_wealth_off = _human_wealth_total(w_off)

    cfg_on = _small_cfg()
    cfg_on.topology.labor = LaborConfig(enabled=True, labor_share=0.4)
    w_on = World.build(cfg_on)
    w_on.run(progress=False)
    h_wealth_on = _human_wealth_total(w_on)

    assert h_wealth_on > h_wealth_off, (
        f"Labor wedge should redirect surplus to humans: "
        f"off={h_wealth_off:.4f}, on={h_wealth_on:.4f}."
    )
    # Cumulative wage tracks a non-zero positive value.
    cum_wage = w_on.metrics.history.steps[-1].human_labor_wage_cumulative
    assert cum_wage > 0.0


def test_automation_gap_dampens_wedge() -> None:
    """Raising autonomy on both humans and agents makes the population
    more A2A-equivalent, which raises `automation_gap` and shrinks the
    wedge. Cumulative wage under the high-autonomy variant should be
    strictly less than the baseline.
    """
    base_cfg = _small_cfg()
    base_cfg.topology.labor = LaborConfig(enabled=True, labor_share=0.4)
    w_base = World.build(base_cfg)
    w_base.run(progress=False)
    base_wage = w_base.metrics.history.steps[-1].human_labor_wage_cumulative

    # Push autonomy up; both humans and agents act more independently,
    # increasing the automation gap and shrinking the wedge per pair.
    high_auto_cfg = _small_cfg()
    high_auto_cfg.topology.labor = LaborConfig(enabled=True, labor_share=0.4)
    high_auto_cfg.population.human_autonomy_mean = 0.90
    high_auto_cfg.population.agent_autonomy_mean = 0.98
    w_high = World.build(high_auto_cfg)
    w_high.run(progress=False)
    high_wage = w_high.metrics.history.steps[-1].human_labor_wage_cumulative

    assert high_wage < base_wage, (
        f"Higher autonomy widens the automation gap and shrinks the wedge: "
        f"base wage={base_wage:.4f}, high-autonomy wage={high_wage:.4f}."
    )


def test_human_only_metrics_reported() -> None:
    """`gini_wealth_human` and `real_per_capita_welfare_human` are
    populated independently of the population-wide metrics. With W2c
    off they are no-op-ish; with W2c on they reflect the redistribution.
    """
    cfg_on = _small_cfg()
    cfg_on.topology.labor = LaborConfig(enabled=True, labor_share=0.4)
    w_on = World.build(cfg_on)
    w_on.run(progress=False)
    last = w_on.metrics.history.steps[-1]
    # Human-only gini is a real number in [0, 1].
    assert 0.0 <= last.gini_wealth_human <= 1.0
    # Cumulative per-capita welfare from the wage channel matches what
    # we'd compute from cumulative wage divided by human population.
    pop = w_on.population
    real_humans = float((pop.weight * pop.is_human).sum())
    expected_per_cap = last.human_labor_wage_cumulative / real_humans
    assert last.real_per_capita_welfare_human == pytest.approx(
        expected_per_cap, rel=1e-6
    )


def test_per_sector_labor_share_validates_length() -> None:
    """`labor_share` accepts a scalar or a length-N_SECTORS sequence;
    mismatched lengths must raise at world build / first step rather
    than silently broadcast.
    """
    from engine.core.population import N_SECTORS

    cfg = _small_cfg()
    cfg.topology.labor = LaborConfig(
        enabled=True,
        labor_share=tuple([0.3] * (N_SECTORS + 1)),  # one too many
    )
    world = World.build(cfg)
    with pytest.raises(ValueError, match="labor_share"):
        world.run(progress=False)
