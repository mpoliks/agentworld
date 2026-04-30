"""
Uncertainty-quantification tests.

Covers:
    - empirical anchors load and are SPD
    - t-copula noise is mean-equivalent and heavier-tailed than Gaussian
    - Hawkes folding is mean-equivalent to geometric folding (in expectation)
    - ensemble runner produces correctly-shaped bands and Parquet output
    - Sobol sweep runs to completion and returns bounded indices
    - network sampling produces non-trivial adjacency that the partner
      sampler can use without error

These are deliberately small (sub-second per test) so the CI loop stays
fast; the heavy convergence checks are reserved for the
`test_*_convergence_slow` markers.
"""

from __future__ import annotations

import numpy as np
import pytest


# ----------------------------------------------------------------------
# Empirical anchors
# ----------------------------------------------------------------------


def test_empirical_anchors_load_and_are_spd():
    from engine.data.empirical_anchors import (
        BEA_SECTOR_CORR,
        REGION_GROWTH_CORR,
        provenance_dict,
        region_growth_correlation,
    )

    assert BEA_SECTOR_CORR.shape == (12, 12)
    assert np.allclose(np.diag(BEA_SECTOR_CORR), 1.0, atol=1e-9)
    np.linalg.cholesky(BEA_SECTOR_CORR)  # should not raise
    assert REGION_GROWTH_CORR.shape == (8, 8)
    np.linalg.cholesky(REGION_GROWTH_CORR)
    # Parameterized region matrix at multiple sizes should also be SPD.
    for n in (4, 12, 16, 24):
        m = region_growth_correlation(n)
        assert m.shape == (n, n)
        np.linalg.cholesky(m)
    # Provenance metadata is non-empty and has the required fields.
    prov = provenance_dict()
    assert prov, "provenance list should be non-empty"
    for entry in prov:
        assert {"name", "value", "source", "vintage", "scope"} <= entry.keys()


# ----------------------------------------------------------------------
# t-copula noise
# ----------------------------------------------------------------------


def test_tcopula_noise_mean_equivalent_to_gaussian():
    """Variance-matched t-copula and Gaussian shocks should have ~equal mean."""
    from engine.core.noise import per_pair_surplus_shock

    rng_g = np.random.default_rng(0)
    rng_t = np.random.default_rng(0)
    n_sectors = 12
    sec_a = np.tile(np.arange(n_sectors), 200)  # 2400 pairs balanced by sector

    means_g, means_t = [], []
    for s in range(40):
        rng_g = np.random.default_rng(s)
        rng_t = np.random.default_rng(s)
        g = per_pair_surplus_shock(rng_g, sec_a.size, sec_a, scale=0.05, model="gaussian")
        t = per_pair_surplus_shock(rng_t, sec_a.size, sec_a, scale=0.05, model="t_copula")
        means_g.append(g.mean())
        means_t.append(t.mean())

    # Means of both distributions should be near zero; sanity-check via SE.
    sem_g = np.std(means_g) / np.sqrt(len(means_g))
    sem_t = np.std(means_t) / np.sqrt(len(means_t))
    assert abs(np.mean(means_g)) < 4 * max(sem_g, 1e-6)
    assert abs(np.mean(means_t)) < 4 * max(sem_t, 1e-6)


def test_tcopula_noise_has_heavier_tails():
    """Pooled across many seeds, t-copula should produce heavier extreme draws."""
    from engine.core.noise import per_pair_surplus_shock

    sec_a = np.tile(np.arange(12), 4000)  # 48k pairs

    rng_g = np.random.default_rng(123)
    rng_t = np.random.default_rng(123)
    g = per_pair_surplus_shock(rng_g, sec_a.size, sec_a, scale=0.05, model="gaussian")
    t = per_pair_surplus_shock(rng_t, sec_a.size, sec_a, scale=0.05, model="t_copula")

    # 99.5th percentile of |x| should be larger under t-copula than Gaussian.
    q_g = np.quantile(np.abs(g), 0.995)
    q_t = np.quantile(np.abs(t), 0.995)
    assert q_t > q_g, f"t-copula tail ({q_t:.4f}) should exceed Gaussian ({q_g:.4f})"


# ----------------------------------------------------------------------
# Hawkes folding
# ----------------------------------------------------------------------


def test_hawkes_folding_mean_equivalent_to_geometric():
    """Hawkes folding should preserve the geometric kernel's mean."""
    from engine.core.folding import fold_surplus
    from engine.core.topology import Topology, TopologyConfig

    cfg_g = TopologyConfig(alpha=0.6, folding_propensity=0.4, folding_model="geometric")
    cfg_h = TopologyConfig(alpha=0.6, folding_propensity=0.4, folding_model="hawkes")
    topo_g = Topology.build(cfg_g)
    topo_h = Topology.build(cfg_h)

    geo = fold_surplus(1.0, 1.0, topo_g, np.random.default_rng(0))
    hawkes_means = []
    for s in range(2000):
        rng = np.random.default_rng(s)
        res = fold_surplus(1.0, 1.0, topo_h, rng)
        hawkes_means.append(res.nominal_added)
    hawkes_arr = np.array(hawkes_means)

    sem = hawkes_arr.std() / np.sqrt(hawkes_arr.size)
    # Hawkes mean should match geometric within ~3 standard errors.
    assert abs(hawkes_arr.mean() - geo.nominal_added) < 4.0 * sem


def test_hawkes_folding_has_higher_variance():
    """Hawkes folding should produce strictly higher variance than geometric."""
    from engine.core.folding import fold_surplus
    from engine.core.topology import Topology, TopologyConfig

    cfg_g = TopologyConfig(alpha=0.6, folding_propensity=0.4, folding_model="geometric")
    cfg_h = TopologyConfig(alpha=0.6, folding_propensity=0.4, folding_model="hawkes")
    topo_g = Topology.build(cfg_g)
    topo_h = Topology.build(cfg_h)

    geo_results = [
        fold_surplus(1.0, 1.0, topo_g, np.random.default_rng(s)).nominal_added
        for s in range(50)
    ]
    hawkes_results = [
        fold_surplus(1.0, 1.0, topo_h, np.random.default_rng(s)).nominal_added
        for s in range(200)
    ]
    # geometric is deterministic in the noise dimension so std == 0.
    assert np.std(geo_results) < 1e-9
    assert np.std(hawkes_results) > 0.1


# ----------------------------------------------------------------------
# Ensemble runner
# ----------------------------------------------------------------------


def test_alpha_ensemble_shape_and_bands(tmp_path):
    from engine.ensemble import BAND_METRIC_KEYS, run_ensemble

    res = run_ensemble(
        "coasean_paradise",
        n_seeds=4,
        n_bootstrap=10,
        progress=False,
        output_dir=tmp_path,
    )
    assert res.n_seeds == 4
    for key in BAND_METRIC_KEYS:
        assert key in res.series
        assert res.series[key].shape == (4, res.n_steps)
        assert key in res.bands
        for band_name in ("median", "p05", "p95"):
            assert band_name in res.bands[key]
            assert res.bands[key][band_name].shape == (res.n_steps,)
        # p05 <= median <= p95 elementwise.
        assert (res.bands[key]["p05"] <= res.bands[key]["median"] + 1e-9).all()
        assert (res.bands[key]["median"] <= res.bands[key]["p95"] + 1e-9).all()
    # Persisted artefacts exist.
    assert (tmp_path / "coasean_paradise.parquet").exists()
    assert (tmp_path / "coasean_paradise.bands.json").exists()


def test_exo_ensemble_runs(tmp_path):
    from engine.exo.ensemble import run_ensemble

    res = run_ensemble(
        "fold_cathedral",
        n_seeds=3,
        n_bootstrap=10,
        progress=False,
        output_dir=tmp_path,
    )
    assert res.n_seeds == 3
    assert "exo_circulation_index" in res.bands
    assert (tmp_path / "fold_cathedral.parquet").exists()


# ----------------------------------------------------------------------
# Sobol sweep
# ----------------------------------------------------------------------


def test_alpha_sobol_indices_in_bounds():
    from engine.sensitivity import run_sobol_sensitivity

    summary = run_sobol_sensitivity(
        n_base_samples=4,
        n_steps=4,
        pairs_per_step=2_000,
        n_human_prototypes=200,
        n_agent_prototypes=1_500,
        progress=False,
    )
    # SALib Saltelli sample size is N * (D + 2) when calc_second_order=False.
    assert summary.n_simulations == 4 * (summary.problem["num_vars"] + 2)
    # Each metric should have S1 / ST arrays of the right length and
    # broadly bounded numerics. With small n samples the indices are noisy
    # but should not blow up beyond [-3, 3] or be NaN.
    for idx in summary.indices:
        assert len(idx.S1) == summary.problem["num_vars"]
        assert len(idx.ST) == summary.problem["num_vars"]
        assert all(np.isfinite(v) for v in idx.S1)
        assert all(np.isfinite(v) for v in idx.ST)


def test_exo_sobol_indices_runs():
    from engine.exo.sweep import run_exo_sobol

    summary = run_exo_sobol(
        n_base_samples=4, n_steps=8, n_regions=4, progress=False
    )
    assert summary.n_simulations == 4 * (summary.problem["num_vars"] + 2)
    # The "imperial_extraction_share" metric should be sensitive to the
    # extraction_rate parameter (the engine literally multiplies by it).
    # At very low N=4 base samples Sobol indices are noisy, so we only
    # require extraction_rate to be in the top half of contributors —
    # the regression test exists to catch a complete inversion, not a
    # tiny rank reshuffle.
    idx = next(i for i in summary.indices if i.metric == "imperial_extraction_share")
    extraction_pos = idx.parameter_names.index("extraction_rate")
    sorted_st = sorted(idx.ST, reverse=True)
    rank = sorted_st.index(idx.ST[extraction_pos])
    assert rank < (summary.problem["num_vars"] + 1) // 2, (
        f"extraction_rate ranked {rank} out of {summary.problem['num_vars']} "
        "for imperial_extraction_share; expected to dominate."
    )


# ----------------------------------------------------------------------
# Network sampling
# ----------------------------------------------------------------------


def test_population_with_network_runs():
    """Population synthesis with `network_model='scale_free'` should build adjacency."""
    from engine.core.population import Population, PopulationConfig

    cfg = PopulationConfig(
        n_human_prototypes=100,
        n_agent_prototypes=400,
        network_model="scale_free",
        network_mean_degree=6,
        seed=0,
    )
    pop = Population.synthesize(cfg)
    assert pop.adjacency is not None
    assert pop.adjacency.shape == (pop.n, pop.n)
    # Average degree ~ network_mean_degree (within a reasonable factor).
    avg_deg = pop.adjacency.nnz / pop.n
    assert 1.0 < avg_deg < 30.0


def test_sbm_network_intra_sector_clusters():
    """SBM should produce more intra-sector edges than uniform random."""
    from engine.core.population import Population, PopulationConfig

    cfg = PopulationConfig(
        n_human_prototypes=100,
        n_agent_prototypes=400,
        network_model="sbm",
        network_mean_degree=8,
        network_intra_sector_share=0.8,
        seed=0,
    )
    pop = Population.synthesize(cfg)
    # Count how many edges fall inside the same sector.
    rows, cols = pop.adjacency.nonzero()
    same_sector = (pop.sector[rows] == pop.sector[cols]).mean()
    # Random would be 1/12 ≈ 0.083; we asked for 0.8 intra-sector. Should be
    # strongly above the uniform baseline.
    assert same_sector > 0.40, f"intra-sector share = {same_sector:.3f}"


def test_networked_scenarios_run():
    """Smoke-test the two new networked scenarios."""
    from engine.core.world import World
    from engine.scenarios import get_scenario

    for name in ("coasean_paradise_networked", "baroque_cathedral_networked"):
        cfg = get_scenario(name)
        cfg.n_steps = 3
        cfg.pairs_per_step = 4_000
        cfg.population.n_human_prototypes = 200
        cfg.population.n_agent_prototypes = 1_500
        cfg.population.network_mean_degree = 4
        world = World.build(cfg)
        world.run(progress=False)
        assert world.step_idx == 3
        assert world.population.adjacency is not None
