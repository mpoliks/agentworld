"""
Exo engine — exocapitalist primitives for Agentworld.

The α-engine in `engine.core` treats smooth↔striated as a single dial and
EBI = nominal / real as a clean diagnostic. The exo-engine refuses both
moves. Following Poliks & Trillo (2025), it instead models:

- **Lift** as the basic operating logic of capital: continuous upward drift
  through layers of abstraction, fractally branching at each layer.
- **Drag** as a first-class operator: the manual labor (states, brokers,
  white-collar work) that opens legible surfaces for capital to touch.
- **Last mile** as one zone among others, not a privileged "real economy".
  Physical need-meeting is bounded by resources, but the value it creates
  is no more "real" than the value at any other layer.
- **Differential creation** as endogenous: new markets emerge from
  ontological variance and are suppressed only at large enforcement cost.
- **Imperial tracts** as a third topology layer non-coextensive with polity:
  geological / resource attractors that pool capital and inherit chronic
  violence over millennia. Many polities map to one tract; capital
  concentrates by tract independently of polity-level governance.

The Krier "Coasean Paradise" appears here as a specific corner of parameter
space (extreme suppression + drag-as-coordination) and the exo claim is that
it requires politically infeasible levels of differential suppression to
maintain.

Usage:

    from engine.exo.world import ExoWorld
    from engine.exo.scenarios import get_scenario

    cfg = get_scenario("fold_cathedral")
    world = ExoWorld.build(cfg)
    history = world.run(progress=True)
    print(history.terminal_metrics())
"""

from engine.exo.config import (
    DifferentialConfig,
    DragConfig,
    ExoWorldConfig,
    ImperialConfig,
    LastMileConfig,
    RegionConfig,
    StackConfig,
)

__all__ = [
    "DifferentialConfig",
    "DragConfig",
    "ExoWorldConfig",
    "ImperialConfig",
    "LastMileConfig",
    "RegionConfig",
    "StackConfig",
]
