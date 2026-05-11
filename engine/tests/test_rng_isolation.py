"""Stream-isolation invariance for the per-component RNG split.

Companion test for `docs/plans/rng_per_component_split.md`. Pinned here
because Saltelli/Sobol attribution rests on the property this test
verifies: under `WorldConfig.rng_split_mode = "per_component"`, draws
made on one subsystem stream do not advance the draw sequence any other
subsystem sees.

The test is parametrised over both modes:

* Under `per_component`, terminal metrics are bit-for-bit identical
  whether or not we burn an arbitrary number of draws on a stream that
  the alpha-engine never reads (`rngs["exo"]`). This is the property
  that makes Sobol indices noise-floor at ~0.005 instead of ~0.03.
* Under `legacy`, every key in `world.rngs` aliases the same generator,
  so the same burn shifts the shared RNG and terminal metrics differ.
  We assert the divergence so the test is also a regression check on
  the bug the per-component split is meant to fix — if some future
  refactor accidentally isolates the legacy streams, this side of the
  parametrisation will start failing and tell us the safety net moved.

The "order permutation" framing in the plan reduces to this stream
isolation property: permuting the order in which subsystems consume
draws is equivalent to inserting a phantom prefix on whichever stream
went second. Streams that don't talk to each other don't care.
"""

from __future__ import annotations

import pytest

from engine.core.world import World
from engine.scenarios import get_scenario


def _build_canonical(rng_split_mode: str) -> World:
    cfg = get_scenario("equilibrium_drift")
    cfg.n_steps = 6
    cfg.pairs_per_step = 5_000
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 2_000
    cfg.seed = 123
    cfg.population.seed = 456
    cfg.rng_split_mode = rng_split_mode
    return World.build(cfg)


def _terminal_triple(world: World) -> tuple[float, float, float]:
    last = world.metrics.history.steps[-1]
    return (
        last.exo_baroque_index,
        last.real_welfare_cumulative,
        last.gini_wealth,
    )


@pytest.mark.parametrize("mode", ["legacy", "per_component"])
def test_subsystem_stream_isolation(mode: str) -> None:
    """Burn draws on an unused stream; check whether terminal metrics move.

    The alpha-engine `World.step` never reads `rngs["exo"]` (that key is
    reserved for the exo-engine, which lives in its own orchestrator).
    So under per-component RNG, advancing it before `run` is a no-op
    against terminal EBI / welfare / gini. Under legacy, every key
    aliases the same generator and the burn shifts every other draw.
    """
    base = _build_canonical(mode)
    perturbed = _build_canonical(mode)
    perturbed.rngs["exo"].random(10_000)

    base.run(progress=False)
    perturbed.run(progress=False)

    base_terminal = _terminal_triple(base)
    perturbed_terminal = _terminal_triple(perturbed)

    if mode == "per_component":
        assert base_terminal == perturbed_terminal, (
            "Per-component RNG must isolate streams: burning draws on the "
            "exo stream (unused by the alpha-engine) should leave terminal "
            f"metrics bit-identical. Got {base_terminal} vs "
            f"{perturbed_terminal}."
        )
    else:
        assert base_terminal != perturbed_terminal, (
            "Legacy RNG aliases all subsystem keys to one generator, so a "
            "burn on any key must shift terminal metrics. If this assertion "
            "fires, the legacy mode has accidentally been isolated — "
            "investigate `_build_rng_dict` in `engine/core/world.py`."
        )


def test_per_component_is_deterministic() -> None:
    """Two independent World.builds with the same seed and per-component
    layout reproduce bit-identical terminal metrics. Sanity check that
    the SeedSequence-spawn path is itself reproducible.
    """
    a = _build_canonical("per_component")
    b = _build_canonical("per_component")
    a.run(progress=False)
    b.run(progress=False)
    assert _terminal_triple(a) == _terminal_triple(b)


def test_legacy_matches_pre_split_layout() -> None:
    """Under legacy, every key in `world.rngs` points at the *same*
    `Generator` instance. A change to the build code that accidentally
    split them would silently shift every canonical baseline; this test
    catches it before the regression suite does.
    """
    world = _build_canonical("legacy")
    rngs = world.rngs
    first = next(iter(rngs.values()))
    for name, gen in rngs.items():
        assert gen is first, (
            f"Legacy mode aliases all subsystem keys to one generator; "
            f"key {name!r} resolved to a distinct object."
        )


def test_permeability_stream_is_isolated() -> None:
    """Permeability-axis (W1c) gets its own stream when `per_component`.

    The permeability gate fires `rng.random(n_pairs)` whenever
    `cross_stack_permeability < 1.0`. Under per_component this draw is
    routed through `rngs["permeability"]`, so a parameter that toggles
    the permeability admission rate does not perturb the draw sequence
    for the law/market/alignment gates downstream. We test that by
    advancing the permeability stream before the run and asserting
    every other subsystem (and therefore every terminal metric) is
    unchanged — at `cross_stack_permeability == 1.0` the gate doesn't
    fire, so a burn on the dedicated stream is a no-op by construction.
    """
    base = _build_canonical("per_component")
    perturbed = _build_canonical("per_component")
    perturbed.rngs["permeability"].random(5_000)
    base.run(progress=False)
    perturbed.run(progress=False)
    assert _terminal_triple(base) == _terminal_triple(perturbed)
