"""CI-aware Sobol comparison harness.

Promoted from the throwaway `/tmp/sobol_compare.py` named in
`docs/plans/rng_per_component_split.md`. Given two Sobol summaries
(each `outputs/sensitivity/sobol_indices*.json`), classify every
`(metric, parameter)` pair as one of four transition classes by
comparing `|S1|` against its bootstrap CI (`S1_conf`) under each layout:

* `noise → noise`   — `|S1| < S1_conf` in both summaries (true null)
* `signal → noise`  — first reports `|S1| > S1_conf`, second reports
                      `|S1| < S1_conf` (the first was unmasked
                      draw-sequence cross-talk)
* `noise → signal`  — first reports `|S1| < S1_conf`, second reports
                      `|S1| > S1_conf` (the second resolves real
                      signal that the first's CI couldn't separate
                      from zero)
* `signal → signal` — `|S1| > S1_conf` in both (stable real signal)

The bet baked into `docs/plans/sobol_n_bump.md` is that doubling N
shrinks `S1_conf` enough to convert a chunk of `noise → noise` params
into `signal → ?`, resolving the residual band the per-component
re-pin left inside the `|S1| ≈ S1_conf` regime.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


# The four transition classes. Ordered for readable JSON output.
TRANSITIONS: tuple[str, ...] = (
    "noise_to_noise",
    "signal_to_noise",
    "noise_to_signal",
    "signal_to_signal",
)


def _classify(s1: float, conf: float) -> str:
    """A param is `signal` iff `|S1| > S1_conf`; otherwise `noise`."""
    return "signal" if abs(float(s1)) > float(conf) else "noise"


def _transition(s1_a: float, conf_a: float, s1_b: float, conf_b: float) -> str:
    a = _classify(s1_a, conf_a)
    b = _classify(s1_b, conf_b)
    return f"{a}_to_{b}"


def _by_metric(summary: dict) -> dict:
    """Index a Sobol summary by metric name for cross-comparison."""
    return {entry["metric"]: entry for entry in summary["indices"]}


@dataclass
class TransitionCounts:
    """Four-way counts for one (a → b) comparison."""

    label_a: str
    label_b: str
    n_base_a: int
    n_base_b: int
    counts: dict  # transition → int
    per_metric: dict  # metric → {transition → int}
    per_param_examples: dict  # transition → [{metric, param, s1_a, conf_a, s1_b, conf_b}, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def compare_two(
    summary_a: dict, summary_b: dict, *, label_a: str, label_b: str,
    examples_per_transition: int = 6,
) -> TransitionCounts:
    """Classify every (metric, parameter) pair across two Sobol summaries.

    Both summaries must declare the same parameter inventory under each
    metric's `parameter_names`. Metrics present in only one summary are
    silently dropped — the comparison is on the intersection.
    """
    by_m_a = _by_metric(summary_a)
    by_m_b = _by_metric(summary_b)
    common_metrics = [m for m in by_m_a if m in by_m_b]

    counts = {t: 0 for t in TRANSITIONS}
    per_metric: dict = {}
    per_param_examples: dict = {t: [] for t in TRANSITIONS}

    for metric in common_metrics:
        entry_a = by_m_a[metric]
        entry_b = by_m_b[metric]
        # Align parameters by name in case ordering differs.
        names_a = entry_a["parameter_names"]
        names_b = entry_b["parameter_names"]
        if list(names_a) != list(names_b):
            common_params = [p for p in names_a if p in names_b]
        else:
            common_params = list(names_a)

        m_counts = {t: 0 for t in TRANSITIONS}
        for p in common_params:
            i_a = names_a.index(p)
            i_b = names_b.index(p)
            s1_a = entry_a["S1"][i_a]
            conf_a = entry_a["S1_conf"][i_a]
            s1_b = entry_b["S1"][i_b]
            conf_b = entry_b["S1_conf"][i_b]
            t = _transition(s1_a, conf_a, s1_b, conf_b)
            counts[t] += 1
            m_counts[t] += 1
            if len(per_param_examples[t]) < examples_per_transition:
                per_param_examples[t].append(
                    {
                        "metric": metric,
                        "param": p,
                        f"s1_{label_a}": float(s1_a),
                        f"conf_{label_a}": float(conf_a),
                        f"s1_{label_b}": float(s1_b),
                        f"conf_{label_b}": float(conf_b),
                    }
                )
        per_metric[metric] = m_counts

    return TransitionCounts(
        label_a=label_a,
        label_b=label_b,
        n_base_a=int(summary_a.get("n_base_samples", 0)),
        n_base_b=int(summary_b.get("n_base_samples", 0)),
        counts=counts,
        per_metric=per_metric,
        per_param_examples=per_param_examples,
    )


@dataclass
class SobolComparisonReport:
    """Full multi-source comparison artifact written to JSON."""

    sources: list  # [{label, path, n_base_samples}, ...]
    comparisons: list  # [TransitionCounts, ...]

    def to_dict(self) -> dict:
        return {
            "sources": self.sources,
            "comparisons": [c.to_dict() for c in self.comparisons],
        }


def compare_sobol_outputs(
    sources: Sequence[tuple[str, Path]],
    *,
    examples_per_transition: int = 6,
) -> SobolComparisonReport:
    """Pairwise-compare a sequence of (label, path) Sobol summaries.

    `sources` must be in *intended order* — comparisons are produced
    between adjacent entries (`sources[i]` vs `sources[i+1]`). Typical
    layout for the N-bump round:

        compare_sobol_outputs([
            ("legacy",          Path("outputs/sensitivity/sobol_indices.n2048.json")),
            ("percomp_n2048",   Path("outputs/sensitivity/sobol_indices.per_component.n2048.json")),
            ("percomp_n4096",   Path("outputs/sensitivity/sobol_indices.per_component.n4096.json")),
        ])

    Returns a report whose `comparisons[0]` is `legacy → percomp_n2048`
    (the original RNG-split effect) and `comparisons[1]` is
    `percomp_n2048 → percomp_n4096` (the N-bump effect).
    """
    loaded = []
    for label, path in sources:
        path = Path(path)
        d = json.loads(path.read_text())
        loaded.append((label, path, d))

    comparisons: list[TransitionCounts] = []
    for (lab_a, _, d_a), (lab_b, _, d_b) in zip(loaded[:-1], loaded[1:]):
        comparisons.append(
            compare_two(
                d_a, d_b,
                label_a=lab_a, label_b=lab_b,
                examples_per_transition=examples_per_transition,
            )
        )

    return SobolComparisonReport(
        sources=[
            {
                "label": lab,
                "path": str(path),
                "n_base_samples": int(d.get("n_base_samples", 0)),
                "n_simulations": int(d.get("n_simulations", 0)),
            }
            for lab, path, d in loaded
        ],
        comparisons=comparisons,
    )


def write_comparison_report(
    report: SobolComparisonReport, out_path: Path
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.to_dict(), indent=2))
