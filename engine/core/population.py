"""
Population — the agent and human substrate.

The population is *vectorized*. Each row in the arrays below is a "prototype"
that represents some weighted slice of the actual population (which is on the
order of 10^11 agents and 10^10 humans). We simulate ~10^5 to 10^6 prototypes
and use importance weights to scale up to population aggregates.

Each prototype has:
    capability      : float in [0, 1]    — how good its agent (or its agent-set) is
    sector          : int in [0, S)      — which economic sector it primarily lives in
    stack           : int in [0, K)      — which hemispherical stack it belongs to
    alignment       : float in [-1, 1]   — Matryoshka individual-layer parameter
    wealth          : float >= 0         — units-of-account held
    weight          : float > 0          — population this prototype stands for
    is_human        : bool               — humans (~10^10) vs agents (~10^11)
    autonomy        : float in [0, 1]    — for humans: how much they delegate to agents
                                           for agents: how much they act independently

Sectoral structure is inspired by ISIC but compressed to ~12 macro-sectors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import numpy as np

# 12 macro-sectors. Order matters for reproducibility.
SECTOR_NAMES = [
    "agriculture",
    "extraction",
    "manufacturing",
    "energy",
    "logistics",
    "construction",
    "retail",
    "finance",
    "information",
    "health",
    "education",
    "leisure",
]
N_SECTORS = len(SECTOR_NAMES)


@dataclass
class PopulationConfig:
    """Configuration for population generation."""

    # Total population (in real units, e.g. 8e9 humans, 8e11 agents).
    n_humans_real: float = 8.0e9
    n_agents_real: float = 8.0e11

    # Sample size — how many prototypes to actually simulate.
    n_human_prototypes: int = 8_000
    n_agent_prototypes: int = 80_000

    # Number of hemispherical stacks (e.g. NATO/PRC/RU/EU/Gulf split).
    n_stacks: int = 4

    # Stack-share weights (must sum to 1).
    stack_shares: tuple = (0.34, 0.34, 0.16, 0.16)

    # Initial wealth distribution (Pareto exponent for agent wealth tail).
    wealth_pareto_alpha: float = 1.6
    initial_wealth_human_mean: float = 100.0
    initial_wealth_agent_mean: float = 5.0

    # Capability distribution: agents are higher-capability on average.
    human_capability_mean: float = 0.45
    human_capability_sd: float = 0.18
    agent_capability_mean: float = 0.72
    agent_capability_sd: float = 0.20

    # Autonomy (delegation) distribution.
    human_autonomy_mean: float = 0.55  # how much humans delegate to agents on avg
    agent_autonomy_mean: float = 0.85  # how independently agents act on avg

    # Per-class trade-rate multipliers. Real-time per entity: a human might
    # attempt a trade per day, an agent might attempt thousands per second.
    # The model's pair-sampling probability is `weight × rate`, so a higher
    # agent multiplier means agents are over-represented in the sampled
    # trades for the same step. Both default to 1.0, which keeps the
    # back-compat assumption that every real entity has the same per-tick
    # trade probability. Setting `agent_trade_rate_multiplier = 100` says
    # "agents attempt trades 100× more often than humans."
    human_trade_rate_multiplier: float = 1.0
    agent_trade_rate_multiplier: float = 1.0

    # Sector concentration: Dirichlet alpha for sector shares (lower = more uneven).
    sector_dirichlet_alpha: float = 1.5

    # Random seed for reproducibility.
    seed: int = 0

    # Optional network structure (see engine/core/network.py).
    # "well_mixed" (default) preserves the original Bernoulli + uniform sampler.
    # "scale_free" / "sbm" build a sparse adjacency at synthesize time and the
    # partner sampler draws from neighborhoods with probability `network_p_local`.
    # Only built at SMALL scales (n <= MAX_NETWORK_NODES); falls back with a
    # warning otherwise.
    network_model: Literal["well_mixed", "scale_free", "sbm"] = "well_mixed"
    network_mean_degree: int = 10
    network_intra_sector_share: float = 0.7
    network_p_local: float = 0.85


@dataclass
class Population:
    """A vectorized population of human and agent prototypes.

    Memory layout (per prototype, post-dtype-audit):
        capability      float32  (4B)
        sector          int16    (2B)
        stack           int8     (1B)
        alignment       float32  (4B)
        wealth          float32  (4B)
        weight          float32  (4B)   -- uniform within (is_human, stack)
        is_human        bool     (1B)
        autonomy        float32  (4B)
    Total ~24 B/prototype, ~2.1 GB at 88M.

    Sampling structures (pre-built once at synthesize time, reused every step):
        global_weight_cumulative   float64 (8B/proto, ~700 MB at 88M)
        stack_indices[k]           int32   (subset, total ~350 MB at 88M)
        stack_weight_cumulative[k] float64 (subset, total ~700 MB at 88M)
    """

    capability: np.ndarray
    sector: np.ndarray
    stack: np.ndarray
    alignment: np.ndarray
    wealth: np.ndarray
    weight: np.ndarray
    is_human: np.ndarray
    autonomy: np.ndarray
    intermediation_pref: np.ndarray | None = None
    bandit_rewards: np.ndarray | None = None
    bandit_counts: np.ndarray | None = None
    last_action: np.ndarray | None = None
    firm_id: np.ndarray | None = None
    firm_next_id: int = 0
    # Persistent agent identity (W2a, Hadfield). `agent_id[i]` is a
    # stable int64 issued at prototype creation; `engine/core/dynamics.py`
    # re-issues fresh identifiers on prototype recycle (entry/exit).
    # `registered[i]` is the Hadfield bit a regulator can read; humans
    # are exempt and always carry True. With
    # `RegistrationConfig.enabled = False` (the canonical default) the
    # fields are populated but no engine code reads them, so canonical
    # baselines stay bit-identical. See `docs/concepts/registration.md`
    # and W2a in `docs/plans/hadfield_jacobs_robustness.md`.
    agent_id: np.ndarray | None = None
    registered: np.ndarray | None = None
    agent_next_id: int = 0
    # S3 stretch — multi-jurisdiction registration arbitrage. When the
    # arbitrage flag is set on `RegistrationConfig`, each agent picks
    # the stack with the lowest effective regulator rejection rate at
    # world build; that stack becomes their `registration_stack` and the
    # regulator-gate floor for the agent reads its strength, not the
    # trading partner's. `None` when arbitrage is off (the W2a default),
    # preserving bit-identity at the canonical scenarios.
    registration_stack: np.ndarray | None = None
    # W1b — norm-participation alignment. `norm_vector[i, k]` is
    # prototype i's position on norm dimension k. Generalises the
    # scalar `alignment` to a K-dim space; the per-step update toward
    # executed partners in `engine/core/norms.py` is the mechanism.
    # With `NormsConfig.enabled = False` (the canonical default) the
    # field is populated but unread, so the canonical baselines stay
    # bit-identical. See `docs/concepts/matryoshkan_alignment.md`.
    norm_vector: np.ndarray | None = None

    # Sampling structures — built once at synthesize time, immutable thereafter.
    # See _build_sampling_structures. We exploit a structural property: in
    # PopulationConfig, all humans share one weight and all agents share
    # another, so weighted sampling reduces to a Bernoulli on (human|agent)
    # plus a uniform-integer index inside that class. This is ~10x faster
    # than CDF + searchsorted at n=88M (~30ms vs ~500ms per global draw).
    total_weight: float = 0.0
    p_human_global: float = 0.0
    human_idx_in_stack: list = field(default_factory=list)   # list[np.ndarray]
    agent_idx_in_stack: list = field(default_factory=list)
    p_human_in_stack: list = field(default_factory=list)     # list[float]
    real_weight_in_stack: list = field(default_factory=list) # list[float]

    # Optional sparse adjacency (scipy.sparse.csr_matrix or None).
    adjacency: Optional[Any] = None

    config: PopulationConfig = field(default_factory=PopulationConfig)

    @classmethod
    def synthesize(
        cls,
        config: Optional[PopulationConfig] = None,
        strategy_config: Optional[Any] = None,
        registration_config: Optional[Any] = None,
        norms_config: Optional[Any] = None,
    ) -> "Population":
        """Generate a synthetic population from a config.

        `registration_config` (optional) is W2a's `RegistrationConfig`. When
        provided and `enabled = True`, the `registered` mask is drawn from a
        dedicated seed (`initial_registration_seed`) so the registration
        bit can be toggled without perturbing any other prototype draw.
        With `enabled = False` (or `None`) every agent is marked
        registered, the field exists but engine code never reads it, and
        canonical pinned baselines stay bit-identical.
        """
        if config is None:
            config = PopulationConfig()

        rng = np.random.default_rng(config.seed)
        n_h = config.n_human_prototypes
        n_a = config.n_agent_prototypes
        n = n_h + n_a

        is_human = np.zeros(n, dtype=bool)
        is_human[:n_h] = True

        cap = np.empty(n, dtype=np.float32)
        cap[:n_h] = np.clip(
            rng.normal(config.human_capability_mean, config.human_capability_sd, n_h),
            0.01,
            0.99,
        )
        cap[n_h:] = np.clip(
            rng.normal(config.agent_capability_mean, config.agent_capability_sd, n_a),
            0.01,
            0.99,
        )

        sector_shares = rng.dirichlet(
            np.full(N_SECTORS, config.sector_dirichlet_alpha)
        )
        sector = rng.choice(N_SECTORS, size=n, p=sector_shares).astype(np.int16)

        stack = rng.choice(
            config.n_stacks, size=n, p=np.asarray(config.stack_shares)
        ).astype(np.int8)

        alignment = np.empty(n, dtype=np.float32)
        alignment[:n_h] = np.clip(rng.normal(0.0, 0.45, n_h), -1.0, 1.0)
        alignment[n_h:] = np.clip(rng.normal(0.0, 0.25, n_a), -1.0, 1.0)

        wealth = np.empty(n, dtype=np.float32)
        wealth[:n_h] = rng.lognormal(
            mean=np.log(config.initial_wealth_human_mean), sigma=0.9, size=n_h
        )
        wealth[n_h:] = config.initial_wealth_agent_mean * (
            rng.pareto(config.wealth_pareto_alpha, size=n_a) + 1.0
        )

        autonomy = np.empty(n, dtype=np.float32)
        autonomy[:n_h] = np.clip(
            rng.beta(2.5, 2.0, n_h) * 0.9 + 0.05, 0.05, 0.95
        )
        scale_h = config.human_autonomy_mean / autonomy[:n_h].mean()
        autonomy[:n_h] = np.clip(autonomy[:n_h] * scale_h, 0.05, 0.99)
        autonomy[n_h:] = np.clip(
            rng.beta(5.0, 1.5, n_a) * 0.95 + 0.04, 0.04, 0.99
        )
        scale_a = config.agent_autonomy_mean / autonomy[n_h:].mean()
        autonomy[n_h:] = np.clip(autonomy[n_h:] * scale_a, 0.05, 0.99)

        # Importance weights — float32 (saves 350 MB at 88M vs float64).
        # Within-class weight is uniform; precision loss is negligible because
        # values are O(10^4) and we never accumulate naive sums (CDF is f64).
        weight = np.empty(n, dtype=np.float32)
        weight[:n_h] = np.float32(config.n_humans_real / n_h)
        weight[n_h:] = np.float32(config.n_agents_real / n_a)

        strategy_enabled = bool(getattr(strategy_config, "enabled", False))
        if strategy_enabled:
            intermediation_pref = np.clip(
                rng.normal(
                    getattr(strategy_config, "initial_pref", 0.5),
                    getattr(strategy_config, "initial_pref_sd", 0.15),
                    n,
                ),
                0.01,
                0.99,
            ).astype(np.float32)
        else:
            intermediation_pref = np.zeros(n, dtype=np.float32)
        bandit_rewards = np.zeros((n, 3), dtype=np.float32)
        bandit_counts = np.ones((n, 3), dtype=np.int32)
        last_action = np.full(n, -1, dtype=np.int8)
        firm_id = np.full(n, -1, dtype=np.int32)

        # W2a — persistent agent identity. Stable int64 issued
        # monotonically; entry/exit re-issues fresh identifiers on
        # prototype recycle. Independent of population/strategy rng so
        # toggling W2a does not perturb other draws.
        agent_id = np.arange(n, dtype=np.int64)
        agent_next_id = int(n)
        # `registered` defaults to all-True when W2a is disabled or
        # `initial_registered_share = 1.0`, so no rng draws are
        # consumed in the canonical default path. When the share is
        # below 1.0, a dedicated `initial_registration_seed` rng is
        # used so the registration toggle never moves downstream draws.
        registration_enabled = bool(
            getattr(registration_config, "enabled", False)
        )
        share = float(
            getattr(registration_config, "initial_registered_share", 1.0)
        )
        registered = np.ones(n, dtype=bool)
        if registration_enabled and share < 1.0:
            reg_rng = np.random.default_rng(
                int(getattr(
                    registration_config, "initial_registration_seed", 0
                ))
            )
            # Agents register with probability `share`; humans are
            # exempt and always registered.
            agent_slice = slice(n_h, n)
            registered[agent_slice] = reg_rng.random(n_a) < share

        # W1b — norm-participation initial draw. Uses a dedicated rng
        # seed so toggling the norms mechanism does not perturb any
        # other population draw. K=1 with sd matching the alignment
        # scalar produces a near-bit-identical generalization; the
        # default K=4 widens the norm space. When the mechanism is
        # disabled we still allocate the field (sized to a sensible
        # default K=1) so downstream code can rely on it being present.
        norms_enabled = bool(getattr(norms_config, "enabled", False))
        K = int(getattr(norms_config, "n_dimensions", 1)) if norms_enabled else 1
        K = max(K, 1)
        norm_vector = np.zeros((n, K), dtype=np.float32)
        if norms_enabled:
            norms_rng = np.random.default_rng(
                int(getattr(norms_config, "initial_norm_seed", 0))
            )
            sd_h = float(getattr(norms_config, "initial_norm_sd_human", 0.45))
            sd_a = float(getattr(norms_config, "initial_norm_sd_agent", 0.25))
            norm_vector[:n_h] = np.clip(
                norms_rng.normal(0.0, sd_h, size=(n_h, K)), -1.0, 1.0
            ).astype(np.float32)
            norm_vector[n_h:] = np.clip(
                norms_rng.normal(0.0, sd_a, size=(n_a, K)), -1.0, 1.0
            ).astype(np.float32)

        pop = cls(
            capability=cap,
            sector=sector,
            stack=stack,
            alignment=alignment,
            wealth=wealth,
            weight=weight,
            is_human=is_human,
            autonomy=autonomy,
            intermediation_pref=intermediation_pref,
            bandit_rewards=bandit_rewards,
            bandit_counts=bandit_counts,
            last_action=last_action,
            firm_id=firm_id,
            agent_id=agent_id,
            registered=registered,
            agent_next_id=agent_next_id,
            norm_vector=norm_vector,
            config=config,
        )
        pop._build_sampling_structures()
        pop._build_network(rng)
        return pop

    def _build_network(self, rng: np.random.Generator) -> None:
        """Optionally build a sparse adjacency from PopulationConfig."""
        if self.config.network_model == "well_mixed":
            self.adjacency = None
            return
        # Local import to avoid a hard scipy dependency for the default path.
        from engine.core.network import build_adjacency

        self.adjacency = build_adjacency(
            n=self.n,
            sector=self.sector.astype(np.int64),
            model=self.config.network_model,
            rng=rng,
            mean_degree=self.config.network_mean_degree,
            intra_sector_share=self.config.network_intra_sector_share,
        )

    # ---- sampling structures ----------------------------------------------

    def _build_sampling_structures(self) -> None:
        """Pre-compute uniform-class sampling structures.

        Two distinct quantities live side by side:

        * **mass weights** (``self.total_weight`` and per-stack
          ``real_weight_in_stack``) — ``N_class_real / n_class_proto``.
          These are mass-only and are the denominator of
          ``pair_real_count = w_a * w_b / total_weight``: how many real
          pair-events does a single sampled prototype-pair stand for.

        * **sampling probabilities** (``self.p_human_global`` and
          per-stack ``p_human_in_stack``) — derived from
          ``mass × trade_rate_multiplier``. These bias which prototypes
          get drawn each step. An agent rate of 100× says agents attempt
          trades 100 times more often than humans per unit of real time,
          so the sampler picks them 100× more often *relative to* their
          mass weight.

        The two are kept separate because rate-rescaled sampling shifts
        the *mix* of trades the engine sees, but does not change how many
        real entities each prototype represents.
        """
        n_h = self.config.n_human_prototypes
        n_a = self.config.n_agent_prototypes
        K = self.config.n_stacks

        # Mass weights (rate-independent — used for pair_real_count).
        w_h = self.config.n_humans_real / n_h
        w_a = self.config.n_agents_real / n_a
        self.total_weight = float(n_h * w_h + n_a * w_a)

        # Sampling weights (mass × per-entity trade rate).
        rate_h = float(self.config.human_trade_rate_multiplier)
        rate_a = float(self.config.agent_trade_rate_multiplier)
        sw_h = w_h * rate_h
        sw_a = w_a * rate_a
        sample_total = n_h * sw_h + n_a * sw_a
        self.p_human_global = (
            float(n_h * sw_h / sample_total) if sample_total > 0 else 0.0
        )

        # Per-stack class splits.
        # stack indexing: 0..n_h-1 are humans, n_h..n_h+n_a-1 are agents.
        h_stack = self.stack[:n_h]
        a_stack = self.stack[n_h:]
        self.human_idx_in_stack = []
        self.agent_idx_in_stack = []
        self.p_human_in_stack = []
        self.real_weight_in_stack = []
        for k in range(K):
            h_idx = np.where(h_stack == k)[0].astype(np.int64)
            a_idx = np.where(a_stack == k)[0].astype(np.int64) + n_h
            n_h_k = h_idx.shape[0]
            n_a_k = a_idx.shape[0]
            # mass-based stack totals (used by external real-pair-count math).
            real_h_k = n_h_k * w_h
            real_a_k = n_a_k * w_a
            real_total_k = real_h_k + real_a_k
            # rate-weighted stack sampling probabilities.
            sample_h_k = n_h_k * sw_h
            sample_a_k = n_a_k * sw_a
            sample_total_k = sample_h_k + sample_a_k
            self.human_idx_in_stack.append(h_idx)
            self.agent_idx_in_stack.append(a_idx)
            self.p_human_in_stack.append(
                float(sample_h_k / sample_total_k) if sample_total_k > 0 else 0.0
            )
            self.real_weight_in_stack.append(float(real_total_k))

    def sample_global(self, n_samples: int, rng: np.random.Generator) -> np.ndarray:
        """Sample n_samples prototype indices weighted by importance weight.

        Bernoulli(p_human_global) + uniform integer within class. O(n_samples).
        """
        n_h = self.config.n_human_prototypes
        n_a = self.config.n_agent_prototypes
        is_h = rng.random(n_samples) < self.p_human_global
        n_h_pick = int(is_h.sum())
        out = np.empty(n_samples, dtype=np.int64)
        if n_h_pick > 0:
            out[is_h] = rng.integers(0, n_h, size=n_h_pick)
        n_a_pick = n_samples - n_h_pick
        if n_a_pick > 0:
            out[~is_h] = n_h + rng.integers(0, n_a, size=n_a_pick)
        return out

    def sample_in_stack(
        self, stack: int, n_samples: int, rng: np.random.Generator
    ) -> np.ndarray:
        """Sample n_samples weighted indices restricted to one stack."""
        h_idx = self.human_idx_in_stack[stack]
        a_idx = self.agent_idx_in_stack[stack]
        n_h_k = h_idx.shape[0]
        n_a_k = a_idx.shape[0]
        if n_h_k + n_a_k == 0:
            return np.empty(0, dtype=np.int64)
        p_h = self.p_human_in_stack[stack]
        is_h = rng.random(n_samples) < p_h
        n_h_pick = int(is_h.sum())
        n_a_pick = n_samples - n_h_pick
        out = np.empty(n_samples, dtype=np.int64)
        if n_h_pick > 0 and n_h_k > 0:
            out[is_h] = h_idx[rng.integers(0, n_h_k, size=n_h_pick)]
        elif n_h_pick > 0:
            out[is_h] = a_idx[rng.integers(0, n_a_k, size=n_h_pick)]
        if n_a_pick > 0 and n_a_k > 0:
            out[~is_h] = a_idx[rng.integers(0, n_a_k, size=n_a_pick)]
        elif n_a_pick > 0:
            out[~is_h] = h_idx[rng.integers(0, n_h_k, size=n_a_pick)]
        return out

    @property
    def n(self) -> int:
        return self.capability.shape[0]

    @property
    def n_humans(self) -> int:
        return int(self.is_human.sum())

    @property
    def n_agents(self) -> int:
        return int((~self.is_human).sum())

    @property
    def total_real_population(self) -> float:
        return float(self.weight.sum())

    def summary(self) -> dict:
        """One-shot summary statistics."""
        h = self.is_human
        a = ~self.is_human
        return {
            "n_prototypes": self.n,
            "n_human_prototypes": int(h.sum()),
            "n_agent_prototypes": int(a.sum()),
            "real_humans": float((self.weight * h).sum()),
            "real_agents": float((self.weight * a).sum()),
            "human_to_agent_ratio": float(
                (self.weight * a).sum() / max((self.weight * h).sum(), 1.0)
            ),
            "mean_capability_human": float(self.capability[h].mean()),
            "mean_capability_agent": float(self.capability[a].mean()),
            "mean_wealth_human": float(self.wealth[h].mean()),
            "mean_wealth_agent": float(self.wealth[a].mean()),
            "mean_autonomy_human": float(self.autonomy[h].mean()),
            "mean_autonomy_agent": float(self.autonomy[a].mean()),
        }
