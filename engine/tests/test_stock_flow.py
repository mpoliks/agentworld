"""Stock-flow consistency regression.

Runs each canonical scenario at small scale and asserts the per-step
ledger residuals are tiny — i.e. the engine respects its own accounting
identity. A non-trivial residual means an unaccounted wealth or welfare
flow has been introduced; investigate before merging.

The tolerance is set against float32 quantization of the per-prototype
wealth update plus float32→float64 casts in the bracketing reads. At
small scale (~88K prototypes, total wealth ~1e6-1e7) the relative
imbalance should sit at ~1e-7 or better.
"""

from __future__ import annotations

import pytest

from engine.core.world import World
from engine.scenarios import get_scenario


# Canonical scenarios that exercise the default, productive-folding,
# law, demand, dynamics, and institutions code paths. Together these
# cover every per-step wealth or welfare flow the ledger tracks.
LEDGER_SCENARIOS = (
    "coasean_paradise",
    "baroque_cathedral",
    "fold_avalanche",
    "matryoshka_collapse",
    "synthetic_consumers",
    "exo_baroque_singularity",
    "productive_baroque",
    "endogenous_baroque",
)


@pytest.mark.parametrize("name", LEDGER_SCENARIOS)
def test_canonical_scenario_balances_stock_and_flow(name: str) -> None:
    cfg = get_scenario(name)
    cfg.n_steps = 30  # short run is enough; ledger fires every step
    world = World.build(cfg)
    world.run(progress=False)

    steps = world.metrics.history.steps
    wealth_rel = max(abs(s.wealth_imbalance_relative) for s in steps)
    welfare_abs = max(abs(s.welfare_imbalance_abs) for s in steps)
    welfare_per_step = max(
        abs(s.welfare_imbalance_abs) / max(abs(s.real_welfare_step), 1e-9)
        for s in steps
    )

    assert wealth_rel < 1e-5, (
        f"{name}: wealth ledger imbalance {wealth_rel:.3e} > 1e-5; "
        f"a categorised flow is missing or incorrect"
    )
    assert welfare_per_step < 1e-5 or welfare_abs < 1e-5, (
        f"{name}: welfare ledger imbalance {welfare_per_step:.3e} relative "
        f"({welfare_abs:.3e} absolute); a categorised welfare flow is "
        f"missing or incorrect"
    )


def test_track_ledger_disabled_is_zero() -> None:
    """When the flag is off, all imbalance fields stay at default zero."""
    cfg = get_scenario("coasean_paradise")
    cfg.n_steps = 5
    cfg.track_ledger = False
    world = World.build(cfg)
    world.run(progress=False)
    for s in world.metrics.history.steps:
        assert s.wealth_imbalance_abs == 0.0
        assert s.wealth_imbalance_relative == 0.0
        assert s.welfare_imbalance_abs == 0.0


def test_track_ledger_does_not_perturb_results() -> None:
    """Bit-identical EBI between track_ledger=True and =False."""
    cfg_a = get_scenario("baroque_cathedral")
    cfg_a.n_steps = 20
    cfg_a.track_ledger = True
    world_a = World.build(cfg_a)
    world_a.run(progress=False)

    cfg_b = get_scenario("baroque_cathedral")
    cfg_b.n_steps = 20
    cfg_b.track_ledger = False
    world_b = World.build(cfg_b)
    world_b.run(progress=False)

    ebi_a = world_a.metrics.history.steps[-1].exo_baroque_index
    ebi_b = world_b.metrics.history.steps[-1].exo_baroque_index
    assert ebi_a == ebi_b, (
        f"track_ledger flag perturbs results: EBI {ebi_a} != {ebi_b}"
    )
