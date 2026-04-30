"""
Topology — the smooth/striated continuum and friction surface.

Smooth space (Deleuze/Guattari): nomadic, intensive, open-ended, haptic.
    Translated here as: low transaction cost, no folding, direct exchange.

Striated space: gridded, metric, hierarchical, optic.
    Translated here as: high coordination overhead, recursive market folding,
    every transaction layered with intermediating sub-transactions.

The control variable is `alpha` ∈ [0, 1]:
    alpha = 0  →  Smoothworld (Krier limit)
    alpha = 1  →  Baroqueworld (Bratton limit)

Real economies live somewhere in between, and may sit at different alphas
across sectors / stacks / time.

Beyond alpha, the topology specifies:
    - protocol_compat[k1, k2]  : compatibility between hemispherical stacks
    - sector_affinity[s1, s2]  : how readily sectors transact across boundaries
    - friction_floor           : irreducible compute/enforcement cost
    - matryoshka_overhead      : layered governance cost (law/market/individual)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np

from engine.core.population import N_SECTORS


@dataclass
class TopologyConfig:
    """Configuration for the smooth-striated topology."""

    # The variable. 0 = smoothworld, 1 = baroqueworld.
    alpha: float = 0.5

    # Hemispherical compatibility matrix shape (n_stacks, n_stacks).
    # Diagonal is 1.0, off-diagonal in (0, 1] = how easy cross-stack trade is.
    n_stacks: int = 4
    cross_stack_compat: float = 0.55  # default off-diagonal value

    # Sector affinity: sectors close in this matrix transact more readily.
    # Generated from a low-dim latent + small noise, normalized to [0.2, 1.0].
    sector_affinity_seed: int = 1234

    # Friction floor: the irreducible per-transaction cost in units-of-account
    # — set by compute, enforcement, and protocol overhead. Tiny but nonzero.
    friction_floor: float = 1e-4

    # Matryoshka overhead: per-layer governance cost.
    # law layer is binary (transaction is allowed or not).
    # market layer is a tax τ_m on transaction surplus.
    # individual layer is a tax τ_i on transaction surplus.
    market_layer_tax: float = 0.025
    individual_layer_alignment_tax: float = 0.015

    # Coasean parameter: the multiplier that maps capability → friction reduction.
    # friction(τ) = friction_floor + base_friction * (1 - capability)^coase_exp
    coase_exp: float = 1.7
    base_friction: float = 0.05  # at zero capability, friction is high

    # Folding parameter: probability of spawning a sub-market when surplus > 0.
    # Modulated by alpha: at alpha=1, folding is aggressive; at alpha=0, none.
    folding_threshold_surplus: float = 0.01
    folding_max_depth: int = 6
    folding_propensity: float = 0.55  # at alpha=1; scales with alpha

    # Each fold spawns this many sub-markets per parent market on average.
    folding_branching: float = 2.7

    # When folded, each sub-market captures this share of parent surplus,
    # but adds a layer of nominal value-add. This is the *fractal multiplication*
    # of folded surfaces — each layer adds to nominal GDP without adding to
    # real welfare.
    fold_real_efficiency: float = 0.92  # 8% real surplus loss per fold layer
    fold_nominal_multiplier: float = 1.85  # each fold adds 85% to nominal GDP

    # ---- Calibrated noise structure (see docs/concepts/epistemic_status.md) --
    # Noise model for per-pair surplus shocks. The Gaussian default preserves
    # historical scenario behaviour; t_copula injects heavy tails (Cont 2001)
    # and BEA 2022 sectoral co-movement.
    noise_model: Literal["gaussian", "t_copula"] = "gaussian"
    noise_dof: float = 4.0
    noise_sector_share: float = 0.4

    # Folding kernel. Geometric is the original closed-form expectation.
    # Hawkes injects realistic cascade variance (Bacry/Muzy 2015) while
    # preserving the closed-form mean at the same `folding_propensity`.
    folding_model: Literal["geometric", "hawkes"] = "geometric"
    hawkes_branching_ratio: float = 0.65
    hawkes_decay: float = 1.20


@dataclass
class Topology:
    """The smooth-striated topology — a parameter surface that conditions all transactions."""

    cfg: TopologyConfig
    cross_stack: np.ndarray  # (n_stacks, n_stacks) compatibility matrix
    sector_affinity: np.ndarray  # (N_SECTORS, N_SECTORS) affinity matrix

    @classmethod
    def build(cls, cfg: Optional[TopologyConfig] = None) -> "Topology":
        if cfg is None:
            cfg = TopologyConfig()

        # Cross-stack matrix: identity diagonal, cross_stack_compat off-diag.
        K = cfg.n_stacks
        cross = np.full((K, K), cfg.cross_stack_compat, dtype=np.float32)
        np.fill_diagonal(cross, 1.0)

        # Sector affinity: low-dim latent embedding for sectors, then RBF kernel.
        rng = np.random.default_rng(cfg.sector_affinity_seed)
        latent = rng.standard_normal((N_SECTORS, 3)).astype(np.float32)
        # Hand-tune some structure: information / finance close, agriculture far.
        # Just a stylized affinity matrix; not load-bearing on the dynamics.
        d2 = ((latent[:, None, :] - latent[None, :, :]) ** 2).sum(axis=-1)
        aff = np.exp(-d2 / 2.0)  # RBF kernel
        # Normalize to [0.2, 1.0].
        aff = 0.2 + 0.8 * (aff - aff.min()) / (aff.max() - aff.min())
        np.fill_diagonal(aff, 1.0)
        return cls(cfg=cfg, cross_stack=cross, sector_affinity=aff.astype(np.float32))

    # ---- core kernels -----------------------------------------------------

    def transaction_cost(self, capability_a: np.ndarray, capability_b: np.ndarray,
                         stack_a: np.ndarray, stack_b: np.ndarray) -> np.ndarray:
        """
        Compute per-transaction cost in units-of-account for a vector of pairs.

        Lower capability → higher cost (Coase). Cross-stack → higher cost.
        Higher alpha (more striated) increases the protocol overhead.
        """
        cfg = self.cfg
        cap_min = np.minimum(capability_a, capability_b)
        # Cross-stack compatibility (vectorized lookup).
        compat = self.cross_stack[stack_a, stack_b]

        # Coasean term: friction shrinks with capability.
        coase_term = cfg.base_friction * (1.0 - cap_min) ** cfg.coase_exp

        # Striation term: more striated → more protocol overhead, regardless of cap.
        striation_term = cfg.alpha * 0.020 * (1.0 + 0.3 * (1.0 - compat))

        # Cross-stack term.
        cross_term = (1.0 - compat) * 0.015

        # Matryoshka layer overhead (market + individual taxes are applied to
        # surplus elsewhere; here we add only the law/protocol overhead).
        floor = cfg.friction_floor

        return floor + coase_term + striation_term + cross_term

    def folding_propensity(self) -> float:
        """How likely a positive-surplus market is to spawn sub-markets this step."""
        return self.cfg.folding_propensity * (self.cfg.alpha ** 1.4)

    def matryoshka_real_tax(self) -> float:
        """Fraction of real surplus consumed by market+individual layers."""
        return self.cfg.market_layer_tax + self.cfg.individual_layer_alignment_tax

    # ---- diagnostics ------------------------------------------------------

    def label(self) -> str:
        a = self.cfg.alpha
        if a < 0.15:
            return "Smoothworld"
        if a > 0.85:
            return "Baroqueworld"
        if a < 0.45:
            return "smooth-tilted"
        if a > 0.55:
            return "striated-tilted"
        return "balanced"
