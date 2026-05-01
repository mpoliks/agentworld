"""Pin test for the historical anchor (A1).

The anchor's job is to produce one calibrated number — the RMSE between the
engine's governance_overhead_fraction and the FIRE share of US GDP — that
every future engine claim has to live next to. This test:

- runs the anchor at the small default,
- asserts the run completes with finite, in-range numbers,
- verifies the empirical series is the right length and shape so a future
  refactor can't silently change the anchor's denominator.

We do NOT pin a tight RMSE here. Tightening the bar happens deliberately,
not as a side-effect of unrelated engine changes.
"""

from __future__ import annotations

import math

import pytest

from engine.validation.historical_anchor import (
    ANCHOR_N_YEARS,
    ANCHOR_YEAR_END,
    ANCHOR_YEAR_START,
    US_FIRE_SHARE_OF_GDP_1980_2024,
    alpha_schedule_for_anchor,
    run_historical_anchor,
)


def test_empirical_series_length():
    assert len(US_FIRE_SHARE_OF_GDP_1980_2024) == ANCHOR_N_YEARS
    assert ANCHOR_YEAR_END - ANCHOR_YEAR_START + 1 == ANCHOR_N_YEARS


def test_empirical_series_in_face_validity_band():
    # FIRE share of GDP for the US 1980-2024 sits in [0.10, 0.30] regardless
    # of which BEA vintage you pull. If a future edit drives a value outside
    # this band, the typo is the test failure, not the band.
    for v in US_FIRE_SHARE_OF_GDP_1980_2024:
        assert 0.10 <= v <= 0.30


def test_alpha_schedule_shape():
    sched = alpha_schedule_for_anchor()
    assert len(sched) == ANCHOR_N_YEARS
    assert sched[0] == pytest.approx(0.40)
    assert sched[-1] == pytest.approx(0.70)
    # Monotone non-decreasing — the schedule is a hand-picked secular rise.
    for a, b in zip(sched[:-1], sched[1:]):
        assert b >= a


def test_anchor_runs_and_produces_finite_rmse():
    res = run_historical_anchor(scale="small", seed=0)
    assert len(res.simulated) == ANCHOR_N_YEARS
    assert len(res.empirical) == ANCHOR_N_YEARS
    assert math.isfinite(res.rmse) and res.rmse >= 0
    assert math.isfinite(res.mae) and res.mae >= 0
    assert math.isfinite(res.bias)
    # Values are shares so they should sit in [0, 1].
    for v in res.simulated:
        assert 0.0 <= v <= 1.0
    for v in res.empirical:
        assert 0.0 <= v <= 1.0
    # The empirical list mirrors the constant exactly.
    assert tuple(res.empirical) == US_FIRE_SHARE_OF_GDP_1980_2024
    # Sanity bound: a totally broken engine could produce |error| > 0.5; we'd
    # want to know.
    assert res.rmse < 0.5
