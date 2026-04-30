"""
Agentworld — a computational research artifact for the smooth-striated continuum
of an 800B agent / 8B human economy.

See ../README.md for the conceptual brief.
"""

__version__ = "0.1.0"

from engine.core.world import World, WorldConfig
from engine.core.population import Population
from engine.core.topology import Topology
from engine.core.metrics import Metrics

__all__ = ["World", "WorldConfig", "Population", "Topology", "Metrics"]
