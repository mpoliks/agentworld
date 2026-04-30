"""CLI for the Agentworld engine."""

from __future__ import annotations

from pathlib import Path

import click

from engine.ensemble import run_ensemble, run_ensemble_all
from engine.runner import run_all, run_scenario
from engine.scale import Scale
from engine.scenarios import list_scenarios
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
def run_cmd(name, out, no_progress, scale):
    """Run a single scenario by name."""
    out_path = Path(out)
    res = run_scenario(
        name, output_dir=out_path, progress=not no_progress, scale=Scale(scale),
    )
    click.echo(
        f"\n[agentworld] {name} done in {res.elapsed_sec:.1f}s "
        f"(scale={scale}) alpha={res.final_alpha:.3f} "
        f"({res.final_label}) -- written to {out_path / (name + '.json')}"
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
def sweep_cmd(out, steps, pairs, humans, agents):
    """Run an alpha/capability phase-space sweep."""
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
@click.option("--samples", "n_base_samples", default=64, show_default=True,
              help="SALib base samples; total sims = samples * (D + 2).")
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
@click.option("--samples", "n_base_samples", default=32, show_default=True)
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


if __name__ == "__main__":
    main()
