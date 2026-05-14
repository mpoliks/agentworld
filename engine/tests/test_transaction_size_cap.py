"""LawConfig.transaction_size_cap — windfall tax mode and reject mode.

Default `inf` cap is bit-identical to no cap (no RNG draws, no surplus
clip). Tax mode captures surplus above the cap into
StepMetrics.windfall_tax_revenue_* and recycles via the same channels
as Pigouvian. Reject mode adds high-surplus pairs to law_reject.
"""
from __future__ import annotations

import numpy as np

from engine.core.population import PopulationConfig
from engine.core.topology import (
    InstitutionConfig, LawConfig, PigouvianConfig, TopologyConfig,
)
from engine.core.world import World, WorldConfig


def _make_world(
    cap: float = float("inf"),
    cap_recipient: str = "tax",
    pigouvian_enabled: bool = False,
    seed: int = 31,
) -> World:
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=60, n_agent_prototypes=540, seed=seed,
        ),
        topology=TopologyConfig(
            alpha=0.7,  # high alpha → larger gross surpluses → cap bites
            law=LawConfig(
                enabled=True,
                transaction_size_cap=cap,
                cap_recipient=cap_recipient,
            ),
            pigouvian=PigouvianConfig(
                enabled=pigouvian_enabled,
                tax_rate=0.10,
                recycling="human_wealth",
            ),
        ),
        n_steps=4,
        pairs_per_step=8_000,
        seed=seed,
    )
    return World.build(cfg)


def _run(world: World) -> list:
    return [world.step() for _ in range(world.cfg.n_steps)]


def test_infinite_cap_captures_no_windfall() -> None:
    metrics = _run(_make_world(cap=float("inf"), cap_recipient="tax"))
    for m in metrics:
        assert m.windfall_tax_revenue_step == 0.0
    assert metrics[-1].windfall_tax_revenue_cumulative == 0.0


def test_tax_mode_captures_windfall_above_cap() -> None:
    """A finite cap in tax mode captures positive windfall on at least one step."""
    metrics_capped = _run(_make_world(cap=0.001, cap_recipient="tax"))
    captured = [m.windfall_tax_revenue_step for m in metrics_capped]
    assert sum(captured) > 0.0, (
        f"expected windfall revenue with cap=0.001 (tax mode); got {captured}"
    )
    assert metrics_capped[-1].windfall_tax_revenue_cumulative == sum(captured)


def test_tax_mode_does_not_change_reject_counts() -> None:
    """Tax mode caps surplus on executed pairs; it should not raise rejections."""
    base = _run(_make_world(cap=float("inf"), cap_recipient="tax"))
    capped = _run(_make_world(cap=0.001, cap_recipient="tax"))
    base_rejects = sum(m.rejected_law for m in base)
    cap_rejects = sum(m.rejected_law for m in capped)
    # Tax mode is downstream of the law gate; it should not bump law rejects.
    assert cap_rejects == base_rejects


def test_reject_mode_increases_law_rejects() -> None:
    """Reject mode filters high-surplus pairs at the law gate."""
    no_cap = _run(_make_world(cap=float("inf"), cap_recipient="reject"))
    capped = _run(_make_world(cap=0.001, cap_recipient="reject"))
    rejects_no = sum(m.rejected_law for m in no_cap)
    rejects_cap = sum(m.rejected_law for m in capped)
    assert rejects_cap > rejects_no, (
        f"expected reject mode to raise rejected_law; "
        f"no_cap={rejects_no} cap={rejects_cap}"
    )


def test_reject_mode_collects_no_windfall_revenue() -> None:
    metrics = _run(_make_world(cap=0.001, cap_recipient="reject"))
    for m in metrics:
        assert m.windfall_tax_revenue_step == 0.0


def test_windfall_recycles_to_humans_when_pigouvian_enabled() -> None:
    """Pigouvian-enabled recycling lifts human wealth above the no-recycle baseline."""
    def _final_human_wealth(pig_on: bool) -> float:
        w = _make_world(
            cap=0.001, cap_recipient="tax", pigouvian_enabled=pig_on, seed=41,
        )
        _run(w)
        return float(w.population.wealth[w.population.is_human].sum())

    w_off = _final_human_wealth(pig_on=False)
    w_on = _final_human_wealth(pig_on=True)
    assert w_on > w_off, (
        f"expected pigouvian-enabled recycle to lift human wealth; "
        f"off={w_off:.4f} on={w_on:.4f}"
    )


def test_default_law_disabled_keeps_windfall_zero() -> None:
    """With law_cfg.enabled=False the cap branch is skipped entirely."""
    cfg = WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=30, n_agent_prototypes=270, seed=53,
        ),
        topology=TopologyConfig(
            alpha=0.7,
            law=LawConfig(
                enabled=False,
                transaction_size_cap=0.001,
                cap_recipient="tax",
            ),
        ),
        n_steps=3,
        pairs_per_step=4_000,
        seed=53,
    )
    world = World.build(cfg)
    metrics = [world.step() for _ in range(cfg.n_steps)]
    for m in metrics:
        assert m.windfall_tax_revenue_step == 0.0
