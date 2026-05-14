"""CLI for the Agentworld engine."""

from __future__ import annotations

from pathlib import Path

import click

from engine.ensemble import run_ensemble, run_ensemble_all
from engine.runner import run_all, run_scenario
from engine.scale import Scale
from engine.scenarios import SCENARIOS, list_scenarios
from engine.sensitivity import basin_counts, run_phase_space_sweep, run_sobol_sensitivity
from engine.exo import scenarios as exo_scenarios
from engine.exo.ensemble import run_ensemble as exo_run_ensemble
from engine.exo.ensemble import run_ensemble_all as exo_run_ensemble_all
from engine.exo.runner import run_all as exo_run_all
from engine.exo.runner import run_scenario as exo_run_scenario
from engine.exo.sweep import basin_counts as exo_basin_counts
from engine.exo.sweep import run_exo_sobol, run_exo_sweep, run_imperial_sweep


SCALE_CHOICES = [s.value for s in Scale]


@click.group()
def main():
    """Agentworld — a computational research artifact for the smooth/striated continuum."""


@main.command("list")
def list_cmd():
    """List all scenarios."""
    rows = list_scenarios()
    width = max(len(name) for name, _ in rows) + 2
    for name, desc in rows:
        click.echo(f"  {name.ljust(width)}{desc}")


@main.command("run")
@click.argument("name")
@click.option("--out", default="outputs/runs", show_default=True,
              help="Directory to write JSON output to.")
@click.option("--no-progress", is_flag=True, help="Suppress progress bar.")
@click.option("--scale", type=click.Choice(SCALE_CHOICES), default="small",
              show_default=True,
              help="Population scale (small=88K, medium=880K, large=8.8M, xlarge=88M).")
@click.option("--seed", default=None, type=int,
              help="Override the scenario's seed (default: scenario default). "
                   "Use to reproduce or perturb a specific run variant.")
@click.option("--bands", "n_bands", default=None, type=int,
              help="If set, also run an N-seed ensemble and write a "
                   "<name>.bands.json alongside the single-trajectory JSON. "
                   "Use this to see variance around the reported point estimate.")
@click.option("--bands-base-seed", default=20260430, show_default=True, type=int,
              help="Base seed for the variance ensemble (only used with --bands).")
@click.option("--bands-workers", default=1, show_default=True, type=int,
              help="Workers for the variance ensemble (only used with --bands).")
def run_cmd(name, out, no_progress, scale, seed, n_bands, bands_base_seed, bands_workers):
    """Run a single scenario by name."""
    out_path = Path(out)
    res = run_scenario(
        name, output_dir=out_path, progress=not no_progress, scale=Scale(scale),
        seed=seed,
    )
    seed_str = f", seed={seed}" if seed is not None else ""
    click.echo(
        f"\n[agentworld] {name} done in {res.elapsed_sec:.1f}s "
        f"(scale={scale}{seed_str}) alpha={res.final_alpha:.3f} "
        f"({res.final_label}) -- written to {out_path / (name + '.json')}"
    )
    if n_bands is not None and n_bands > 1:
        click.echo(
            f"[agentworld] running {n_bands}-seed variance ensemble "
            f"for {name} (base_seed={bands_base_seed})..."
        )
        run_ensemble(
            name,
            n_seeds=n_bands,
            base_seed=bands_base_seed,
            scale=Scale(scale),
            n_workers=bands_workers,
            output_dir=out_path,
            progress=not no_progress,
        )
        click.echo(
            f"[agentworld] bands -> {out_path / (name + '.bands.json')}"
        )


@main.command("run-all")
@click.option("--out", default="outputs/runs", show_default=True)
@click.option("--no-progress", is_flag=True)
@click.option("--scale", type=click.Choice(SCALE_CHOICES), default="small",
              show_default=True)
@click.option("--workers", "n_workers", default=1, show_default=True,
              help="Parallel scenarios (each holds full population in memory).")
def run_all_cmd(out, no_progress, scale, n_workers):
    """Run every scenario and write JSON outputs."""
    out_path = Path(out)
    results = run_all(
        output_dir=out_path,
        progress=not no_progress,
        scale=Scale(scale),
        n_workers=n_workers,
    )
    click.echo(f"\n[agentworld] {len(results)} scenarios done — outputs in {out_path}")


@main.command("ensemble")
@click.argument("name")
@click.option("--out", default="outputs/ensembles", show_default=True,
              help="Directory for parquet + bands JSON.")
@click.option("--seeds", "n_seeds", default=64, show_default=True,
              help="Number of independent seeds.")
@click.option("--base-seed", default=20260430, show_default=True)
@click.option("--bootstrap", "n_bootstrap", default=200, show_default=True,
              help="Bootstrap resamples for the band-of-the-band correction.")
@click.option("--scale", type=click.Choice(SCALE_CHOICES), default="small",
              show_default=True)
@click.option("--workers", "n_workers", default=1, show_default=True)
@click.option("--no-progress", is_flag=True)
def ensemble_cmd(name, out, n_seeds, base_seed, n_bootstrap, scale, n_workers, no_progress):
    """Run a scenario across N seeds and store median + 5/95 bands."""
    out_path = Path(out)
    res = run_ensemble(
        name,
        n_seeds=n_seeds,
        base_seed=base_seed,
        scale=Scale(scale),
        n_workers=n_workers,
        n_bootstrap=n_bootstrap,
        output_dir=out_path,
        progress=not no_progress,
    )
    click.echo(
        f"\n[agentworld] ensemble {name} done in {res.elapsed_sec:.1f}s "
        f"(n_seeds={res.n_seeds}, scale={scale}) "
        f"-> {out_path / (name + '.parquet')}"
    )


@main.command("ensemble-all")
@click.option("--out", default="outputs/ensembles", show_default=True)
@click.option("--seeds", "n_seeds", default=32, show_default=True)
@click.option("--base-seed", default=20260430, show_default=True)
@click.option("--scale", type=click.Choice(SCALE_CHOICES), default="small",
              show_default=True)
@click.option("--workers", "n_workers", default=1, show_default=True)
@click.option("--no-progress", is_flag=True)
def ensemble_all_cmd(out, n_seeds, base_seed, scale, n_workers, no_progress):
    """Run an ensemble for every alpha-engine scenario."""
    out_path = Path(out)
    res = run_ensemble_all(
        n_seeds=n_seeds,
        base_seed=base_seed,
        scale=Scale(scale),
        n_workers=n_workers,
        output_dir=out_path,
        progress=not no_progress,
    )
    click.echo(f"\n[agentworld] {len(res)} ensembles done -> {out_path}")


@main.command("sweep")
@click.option("--out", default="outputs/sensitivity/phase_space.json", show_default=True)
@click.option("--steps", default=18, show_default=True, help="Steps per grid point.")
@click.option("--pairs", default=20_000, show_default=True, help="Candidate pairs per step.")
@click.option("--humans", default=600, show_default=True, help="Human prototypes per point.")
@click.option("--agents", default=6_000, show_default=True, help="Agent prototypes per point.")
@click.option(
    "--quick", is_flag=True,
    help="Smoke-mode regression sweep used between engine PRs: "
         "8 steps, 4_000 pairs, 200 humans, 2_000 agents. Writes to "
         "outputs/sensitivity/phase_space.quick.json so the canonical "
         "phase_space.json is not overwritten.",
)
def sweep_cmd(out, steps, pairs, humans, agents, quick):
    """Run an alpha/capability phase-space sweep."""
    if quick:
        # Quick-mode defaults: ~5x faster than the canonical sweep,
        # picked to land inside the engine-PR regression-check budget.
        # Overridden by any explicit --steps/--pairs/--humans/--agents.
        steps = 8 if steps == 18 else steps
        pairs = 4_000 if pairs == 20_000 else pairs
        humans = 200 if humans == 600 else humans
        agents = 2_000 if agents == 6_000 else agents
        if out == "outputs/sensitivity/phase_space.json":
            out = "outputs/sensitivity/phase_space.quick.json"
    out_path = Path(out)
    summary = run_phase_space_sweep(
        n_steps=steps,
        pairs_per_step=pairs,
        n_human_prototypes=humans,
        n_agent_prototypes=agents,
        output_path=out_path,
    )
    counts = ", ".join(f"{k}={v}" for k, v in basin_counts(summary.points).items())
    click.echo(
        f"\n[agentworld] {len(summary.points)} sweep points done — {counts}; "
        f"written to {out_path}"
    )


@main.command("sobol")
@click.option("--out", default="outputs/sensitivity/sobol_indices.json",
              show_default=True)
@click.option("--samples", "n_base_samples", default=512, show_default=True,
              help="SALib base samples; total sims = samples * (D + 2). "
                   "Drop to 64 for a fast research-iteration sweep; "
                   "raise above 512 for paper-grade Sobol CIs.")
@click.option("--steps", default=18, show_default=True)
@click.option("--pairs", default=20_000, show_default=True)
@click.option("--humans", default=600, show_default=True)
@click.option("--agents", default=6_000, show_default=True)
@click.option("--no-progress", is_flag=True)
def sobol_cmd(out, n_base_samples, steps, pairs, humans, agents, no_progress):
    """Run a Saltelli/Sobol global sensitivity sweep on the alpha-engine."""
    out_path = Path(out)
    summary = run_sobol_sensitivity(
        n_base_samples=n_base_samples,
        n_steps=steps,
        pairs_per_step=pairs,
        n_human_prototypes=humans,
        n_agent_prototypes=agents,
        output_path=out_path,
        progress=not no_progress,
    )
    click.echo(
        f"\n[agentworld] sobol: {summary.n_simulations} sims, "
        f"{len(summary.indices)} metrics -> {out_path}"
    )


@main.group("exo")
def exo_group():
    """Exo-engine commands (Poliks/Trillo-style lift/drag/last-mile model)."""


@exo_group.command("list")
def exo_list_cmd():
    """List exo scenarios."""
    rows = exo_scenarios.list_scenarios()
    width = max(len(name) for name, _ in rows) + 2
    for name, desc in rows:
        click.echo(f"  {name.ljust(width)}{desc}")


@exo_group.command("run")
@click.argument("name")
@click.option("--out", default="outputs/exo_runs", show_default=True)
@click.option("--no-progress", is_flag=True)
def exo_run_cmd(name, out, no_progress):
    """Run a single exo scenario by name."""
    out_path = Path(out)
    res = exo_run_scenario(name, output_dir=out_path, progress=not no_progress)
    click.echo(f"\n[exo] {name} done — written to {out_path / (name + '.json')}")


@exo_group.command("run-all")
@click.option("--out", default="outputs/exo_runs", show_default=True)
@click.option("--no-progress", is_flag=True)
def exo_run_all_cmd(out, no_progress):
    """Run every exo scenario."""
    out_path = Path(out)
    results = exo_run_all(output_dir=out_path, progress=not no_progress)
    click.echo(f"\n[exo] {len(results)} scenarios done — outputs in {out_path}")


@exo_group.command("ensemble")
@click.argument("name")
@click.option("--out", default="outputs/exo_ensembles", show_default=True)
@click.option("--seeds", "n_seeds", default=32, show_default=True)
@click.option("--base-seed", default=20260430, show_default=True)
@click.option("--bootstrap", "n_bootstrap", default=200, show_default=True)
@click.option("--workers", "n_workers", default=1, show_default=True)
@click.option("--no-progress", is_flag=True)
def exo_ensemble_cmd(name, out, n_seeds, base_seed, n_bootstrap, n_workers, no_progress):
    """Run an exo scenario across N seeds and store median + 5/95 bands."""
    out_path = Path(out)
    res = exo_run_ensemble(
        name,
        n_seeds=n_seeds,
        base_seed=base_seed,
        n_workers=n_workers,
        n_bootstrap=n_bootstrap,
        output_dir=out_path,
        progress=not no_progress,
    )
    click.echo(
        f"\n[exo] ensemble {name} done in {res.elapsed_sec:.1f}s "
        f"(n_seeds={res.n_seeds}) -> {out_path / (name + '.parquet')}"
    )


@exo_group.command("ensemble-all")
@click.option("--out", default="outputs/exo_ensembles", show_default=True)
@click.option("--seeds", "n_seeds", default=16, show_default=True)
@click.option("--base-seed", default=20260430, show_default=True)
@click.option("--workers", "n_workers", default=1, show_default=True)
@click.option("--no-progress", is_flag=True)
def exo_ensemble_all_cmd(out, n_seeds, base_seed, n_workers, no_progress):
    """Run an ensemble for every exo-engine scenario."""
    out_path = Path(out)
    res = exo_run_ensemble_all(
        n_seeds=n_seeds,
        base_seed=base_seed,
        n_workers=n_workers,
        output_dir=out_path,
        progress=not no_progress,
    )
    click.echo(f"\n[exo] {len(res)} ensembles done -> {out_path}")


@exo_group.command("sweep")
@click.option("--out", default="outputs/sensitivity/exo_phase_space.json", show_default=True)
@click.option("--steps", default=40, show_default=True)
@click.option("--regions", default=8, show_default=True)
def exo_sweep_cmd(out, steps, regions):
    """Run a drag x suppression phase-space sweep for the exo engine."""
    out_path = Path(out)
    summary = run_exo_sweep(n_steps=steps, n_regions=regions, output_path=out_path)
    counts = ", ".join(f"{k}={v}" for k, v in exo_basin_counts(summary.points).items())
    click.echo(
        f"\n[exo] {len(summary.points)} sweep points done — {counts}; written to {out_path}"
    )


@exo_group.command("sobol")
@click.option("--out", default="outputs/sensitivity/exo_sobol_indices.json",
              show_default=True)
@click.option("--samples", "n_base_samples", default=128, show_default=True,
              help="SALib base samples; raised from 32 to 128 so Sobol "
                   "indices are not noise-dominated. Drop to 32 for a fast "
                   "research-iteration sweep.")
@click.option("--steps", default=40, show_default=True)
@click.option("--regions", default=8, show_default=True)
@click.option("--no-progress", is_flag=True)
def exo_sobol_cmd(out, n_base_samples, steps, regions, no_progress):
    """Run a Saltelli/Sobol sweep on the exo-engine."""
    out_path = Path(out)
    summary = run_exo_sobol(
        n_base_samples=n_base_samples,
        n_steps=steps,
        n_regions=regions,
        output_path=out_path,
        progress=not no_progress,
    )
    click.echo(
        f"\n[exo] sobol: {summary.n_simulations} sims, "
        f"{len(summary.indices)} metrics -> {out_path}"
    )


@exo_group.command("imperial-sweep")
@click.option(
    "--out",
    default="outputs/sensitivity/exo_imperial_phase_space.json",
    show_default=True,
)
@click.option("--steps", default=40, show_default=True)
@click.option("--regions", default=12, show_default=True)
@click.option("--tracts", default=4, show_default=True)
def exo_imperial_sweep_cmd(out, steps, regions, tracts):
    """Run an extraction x capital-pooling sweep for the imperial layer."""
    out_path = Path(out)
    summary = run_imperial_sweep(
        n_steps=steps,
        n_regions=regions,
        n_tracts=tracts,
        output_path=out_path,
    )
    counts = ", ".join(f"{k}={v}" for k, v in exo_basin_counts(summary.points).items())
    click.echo(
        f"\n[exo] {len(summary.points)} imperial sweep points done — {counts}; "
        f"written to {out_path}"
    )


@main.group("validate")
def validate_group():
    """Validation artifacts (anchor / priors / adversarial)."""


@validate_group.command("anchor")
@click.option("--scenario", default="equilibrium_drift", show_default=True,
              help="Base scenario; the anchor's α-schedule is applied on top.")
@click.option("--scale", type=click.Choice(SCALE_CHOICES), default="small",
              show_default=True)
@click.option("--seed", default=0, show_default=True, type=int)
@click.option("--out", default="outputs/validation/historical_anchor",
              show_default=True,
              help="Path prefix; .json (summary) + .png (chart) are written.")
@click.option("--no-progress", is_flag=True)
def validate_anchor_cmd(scenario, scale, seed, out, no_progress):
    """Run the stylized US 1980-2024 historical anchor."""
    from engine.validation.historical_anchor import (
        run_historical_anchor, write_anchor_chart, write_anchor_summary,
    )
    out_path = Path(out)
    res = run_historical_anchor(
        scenario=scenario, scale=scale, seed=seed, progress=not no_progress,
    )
    summary_path = out_path.with_suffix(".json")
    chart_path = out_path.with_suffix(".png")
    write_anchor_summary(res, summary_path)
    write_anchor_chart(res, chart_path)
    click.echo(
        f"\n[anchor] RMSE={res.rmse:.4f} MAE={res.mae:.4f} bias={res.bias:+.4f}"
    )
    click.echo(
        f"         worst year={res.largest_error_year} "
        f"({res.largest_error:+.4f}) -> {summary_path} {chart_path}"
    )


@validate_group.command("priors")
@click.option("--samples", "n_samples", default=256, show_default=True, type=int,
              help="Sobol sample count. Plan canonical = 2000.")
@click.option("--seed", default=0, show_default=True, type=int)
@click.option("--n-steps", default=20, show_default=True, type=int,
              help="Steps per evaluation (short horizon).")
@click.option("--out", default="outputs/validation/posterior_sweep",
              show_default=True,
              help="Path prefix; .parquet, .summary.json, .png are written.")
@click.option("--no-progress", is_flag=True)
def validate_priors_cmd(n_samples, seed, n_steps, out, no_progress):
    """Sweep the speculative-parameter prior; persist outcome distribution."""
    from engine.validation.posterior_sweep import (
        run_posterior_sweep, write_posterior_artifacts,
    )
    out_path = Path(out)
    df, summary = run_posterior_sweep(
        n_samples=n_samples, seed=seed, n_steps=n_steps, progress=not no_progress,
    )
    write_posterior_artifacts(
        df, summary,
        parquet_path=out_path.with_suffix(".parquet"),
        summary_path=out_path.with_suffix(".summary.json"),
        chart_path=out_path.with_suffix(".png"),
    )
    click.echo(
        f"\n[priors] {summary.n_samples} samples in {summary.elapsed_sec:.1f}s -> "
        f"{out_path.with_suffix('.parquet')}"
    )
    click.echo(
        f"        P(smooth)={summary.p_smooth:.2%}  "
        f"P(mixed)={summary.p_mixed:.2%}  "
        f"P(baroque)={summary.p_baroque:.2%}  "
        f"P(diverged)={summary.p_diverged:.2%}"
    )
    click.echo(
        f"        EBI p05/p50/p95 = "
        f"{summary.ebi_quantiles['p05']:.2f} / "
        f"{summary.ebi_quantiles['p50']:.2f} / "
        f"{summary.ebi_quantiles['p95']:.2f}"
    )


@validate_group.command("adversarial")
@click.option("--n-evals", default=200, show_default=True, type=int,
              help="Number of simulated-annealing proposals.")
@click.option("--seed", default=0, show_default=True, type=int)
@click.option("--out", default="outputs/validation/adversarial_search.json",
              show_default=True)
@click.option("--n-steps", default=30, show_default=True, type=int,
              help="Steps per evaluation.")
@click.option("--n-replicate-seeds", default=5, show_default=True, type=int,
              help="Re-evaluate the best candidate across K seeds; the "
                   "verdict requires a >=50%% hit rate so a counter-example "
                   "isn't single-seed brittle. Set to 1 to skip.")
@click.option("--no-progress", is_flag=True)
def validate_adversarial_cmd(n_evals, seed, out, n_steps, n_replicate_seeds, no_progress):
    """Search for a parameter region where EBI > 10 AND welfare > paradise."""
    from engine.validation.adversarial import (
        adversarial_search, write_adversarial_summary,
    )
    out_path = Path(out)
    res = adversarial_search(
        n_evals=n_evals, seed=seed, n_steps=n_steps, progress=not no_progress,
        n_replicate_seeds=n_replicate_seeds,
    )
    write_adversarial_summary(res, out_path)
    verdict = "COUNTER-EXAMPLE FOUND" if res.found_counter_example else "INVARIANT (no counter-example)"
    click.echo(
        f"\n[adversarial] {verdict} after {res.n_evals} evals in "
        f"{res.elapsed_sec:.1f}s -> {out_path}"
    )
    click.echo(
        f"             best_ebi={res.best_ebi:.3f} (target>{res.ebi_target}) "
        f"best_welfare={res.best_welfare:.4e} (paradise={res.paradise_welfare:.4e})"
    )
    if res.n_replicate_seeds > 1:
        click.echo(
            f"             replicate hit-rate: "
            f"{int(round(res.replicate_hit_rate * res.n_replicate_seeds))}/"
            f"{res.n_replicate_seeds} seeds clear thresholds "
            f"({res.replicate_hit_rate:.0%})"
        )


@validate_group.command("permeability")
@click.option("--samples", "n_samples", default=128, show_default=True, type=int,
              help="Sobol samples per permeability grid point. "
                   "11 grid points × N samples = 11N simulations.")
@click.option("--seed", default=0, show_default=True, type=int)
@click.option("--n-steps", default=24, show_default=True, type=int,
              help="Steps per evaluation.")
@click.option("--pairs", default=20_000, show_default=True, type=int)
@click.option("--humans", default=600, show_default=True, type=int)
@click.option("--agents", default=6_000, show_default=True, type=int)
@click.option("--out", default="outputs/validation/permeability_sweep.json",
              show_default=True)
@click.option("--no-progress", is_flag=True)
def validate_permeability_cmd(
    n_samples, seed, n_steps, pairs, humans, agents, out, no_progress,
):
    """Sweep `cross_stack_permeability` over the wide prior; pin basin shifts."""
    from engine.validation.sweeps import (
        run_permeability_sweep, write_permeability_summary,
    )
    out_path = Path(out)
    summary = run_permeability_sweep(
        n_samples_per_point=n_samples,
        seed=seed,
        n_steps=n_steps,
        pairs_per_step=pairs,
        n_human_prototypes=humans,
        n_agent_prototypes=agents,
        progress=not no_progress,
    )
    write_permeability_summary(summary, out_path)
    n_runs = len(summary.permeability_values) * summary.n_samples_per_point
    click.echo(
        f"\n[permeability] {n_runs} sims in {summary.elapsed_sec:.1f}s -> "
        f"{out_path}"
    )
    # Sandboxed vs open: basin share at the two ends.
    sandbox = summary.basin_distribution[0]
    open_end = summary.basin_distribution[-1]
    click.echo(
        f"             p=0.0  smooth={sandbox['smooth']:.0%} "
        f"baroque={sandbox['baroque']:.0%}; "
        f"p=1.0  smooth={open_end['smooth']:.0%} "
        f"baroque={open_end['baroque']:.0%}"
    )


@validate_group.command("norms")
@click.option("--samples", "n_samples", default=128, show_default=True, type=int,
              help="Sobol samples per configuration. "
                   "2 configurations × N samples = 2N simulations.")
@click.option("--seed", default=0, show_default=True, type=int)
@click.option("--n-steps", default=24, show_default=True, type=int)
@click.option("--pairs", default=20_000, show_default=True, type=int)
@click.option("--humans", default=600, show_default=True, type=int)
@click.option("--agents", default=6_000, show_default=True, type=int)
@click.option("--out", default="outputs/validation/norms_sensitivity.json",
              show_default=True)
@click.option("--no-progress", is_flag=True)
def validate_norms_cmd(
    n_samples, seed, n_steps, pairs, humans, agents, out, no_progress,
):
    """Toggle norm-participation vs static-distance; pin the alignment-share swing."""
    from engine.validation.sweeps import (
        run_norms_sensitivity, write_norms_summary,
    )
    out_path = Path(out)
    summary = run_norms_sensitivity(
        n_samples=n_samples,
        seed=seed,
        n_steps=n_steps,
        pairs_per_step=pairs,
        n_human_prototypes=humans,
        n_agent_prototypes=agents,
        progress=not no_progress,
    )
    write_norms_summary(summary, out_path)
    delta = summary.alignment_share_delta
    click.echo(
        f"\n[norms] 2x{summary.n_samples} sims in {summary.elapsed_sec:.1f}s -> "
        f"{out_path}"
    )
    click.echo(
        f"       align-share delta (norms - static): "
        f"p10={delta['p10']:+.3f}  p50={delta['p50']:+.3f}  p90={delta['p90']:+.3f}"
    )


@main.command("convergence")
@click.option("--scales", multiple=True, default=("small", "medium"),
              show_default=True, type=click.Choice(SCALE_CHOICES),
              help="Population scales to sweep. Repeat the flag for multiples.")
@click.option("--seeds", "n_seeds", default=15, show_default=True, type=int,
              help="Independent seeds per scale. Raised from 3 to 15 so "
                   "bootstrap CIs on the per-scale mean are not themselves "
                   "noise-dominated; drop back to 3 for a fast iteration loop.")
@click.option("--steps", "n_steps", default=None, type=int,
              help="Override n_steps (default: scenario default).")
@click.option("--only", multiple=True, default=(),
              help="Optional scenario allowlist (repeatable).")
@click.option("--out", default="outputs/convergence", show_default=True)
def convergence_cmd(scales, n_seeds, n_steps, only, out):
    """Sweep population scale; report bootstrap CIs on terminal metrics.

    Answers: is the population big enough that small-scale point estimates
    sit inside the medium-scale (and larger) CIs? Where they don't, the
    importance-weighting failure mode flagged in epistemic_status.md is
    biting and the scenario should be flagged as scale-fragile.
    """
    from engine.convergence import run_convergence
    out_path = Path(out)
    scenarios = list(only) if only else list(SCENARIOS.keys())
    scales_enum = [Scale(s) for s in scales]
    run_convergence(
        scenarios=scenarios,
        scales=scales_enum,
        n_seeds=n_seeds,
        n_steps=n_steps,
        output_dir=out_path,
    )


@main.command("stability")
@click.option("--steps", "n_steps_grid", multiple=True, type=int,
              default=(100, 200, 400), show_default=True,
              help="n_steps values to sweep. Repeat the flag for multiples.")
@click.option("--seeds", "n_seeds", default=15, show_default=True, type=int,
              help="Independent seeds per n_steps point. Raised from 3 to 15 "
                   "so bootstrap CIs on the per-budget mean can resolve "
                   "drift smaller than the seed-to-seed noise.")
@click.option("--scale", type=click.Choice(SCALE_CHOICES), default="small",
              show_default=True)
@click.option("--only", multiple=True, default=(),
              help="Optional scenario allowlist (repeatable).")
@click.option("--out", default="outputs/stability", show_default=True)
def stability_cmd(n_steps_grid, n_seeds, scale, only, out):
    """Sweep n_steps; report bootstrap CIs on terminal metrics.

    Answers: has the trajectory finished moving? If terminal-metric
    medians drift outside their bootstrap CIs as n_steps rises, the
    scenario has not converged on its long-run regime within the smaller
    step budget — interpret terminal numbers from those scenarios as
    *transient*, not steady-state.
    """
    from engine.stability import run_stability
    out_path = Path(out)
    scenarios = list(only) if only else list(SCENARIOS.keys())
    run_stability(
        scenarios=scenarios,
        n_steps_grid=list(n_steps_grid),
        n_seeds=n_seeds,
        scale=Scale(scale),
        output_dir=out_path,
    )


@main.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True,
              help="Bind address. Default 127.0.0.1 (localhost only).")
@click.option("--port", default=8765, show_default=True, type=int)
@click.option("--log-level", default="info", show_default=True,
              type=click.Choice(["critical", "error", "warning", "info", "debug"]))
def serve_cmd(host, port, log_level):
    """Start the SSE streaming server (dev only).

    Streams alpha-engine StepMetrics over HTTP/SSE so a browser at
    http://localhost:8765 can watch a run progress step-by-step. Requires
    the `serve` extra: `pip install agentworld[serve]`.
    """
    try:
        from engine.serve import serve  # local import: optional dependency
    except ImportError as e:
        raise click.UsageError(
            f"Could not import the serve module ({e}). Install the extras: "
            "pip install fastapi uvicorn"
        ) from e
    click.echo(f"[agentworld] serving on http://{host}:{port} (Ctrl+C to stop)")
    serve(host=host, port=port, log_level=log_level)


if __name__ == "__main__":
    main()
