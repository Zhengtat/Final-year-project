"""Tests for the Wilson score interval helper (CR-005 §3.2 / canonicalisation
merge-precision spot-checks)."""

from __future__ import annotations

import pytest

from cumap.eval.stats import wilson_ci


def test_wilson_ci_known_value_1_of_1():
    # A well-known reference point: 1/1 success at 95% confidence.
    result = wilson_ci(1, 1)
    assert result.point_estimate == 1.0
    assert result.low == pytest.approx(0.2065, abs=0.001)
    assert result.high == pytest.approx(1.0, abs=0.001)


def test_wilson_ci_point_estimate_matches_raw_proportion():
    result = wilson_ci(30, 40)
    assert result.point_estimate == pytest.approx(0.75)


def test_wilson_ci_bounds_stay_within_0_and_1():
    for successes, n in [(0, 10), (10, 10), (5, 10), (1, 100)]:
        result = wilson_ci(successes, n)
        assert 0.0 <= result.low <= result.high <= 1.0


def test_wilson_ci_widens_as_n_shrinks_for_same_proportion():
    wide = wilson_ci(5, 10)  # 50%, small n
    narrow = wilson_ci(50, 100)  # 50%, larger n
    assert (wide.high - wide.low) > (narrow.high - narrow.low)


def test_wilson_ci_zero_n_returns_degenerate_interval():
    result = wilson_ci(0, 0)
    assert result.point_estimate == 0.0
    assert result.low == 0.0
    assert result.high == 0.0


def test_wilson_ci_rejects_successes_greater_than_n():
    with pytest.raises(ValueError):
        wilson_ci(11, 10)


def test_wilson_ci_rejects_unsupported_confidence():
    with pytest.raises(ValueError):
        wilson_ci(5, 10, confidence=0.90)
