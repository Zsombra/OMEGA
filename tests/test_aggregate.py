"""Hold omega.aggregate to recorded simulate_aggregate_score responses."""
from __future__ import annotations

import json
import random

import pytest

from omega.aggregate import Signal, aggregate, minimum_score_to_route
from omega.contract import DERIVED_DIR

ORACLE = json.loads((DERIVED_DIR / "aggregate_oracle.json").read_text(encoding="utf-8"))
CASES = ORACLE["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_matches_platform(case):
    signals = [Signal(s["label"], s["score"], s["allocation"]) for s in case["signals"]]
    got = aggregate(signals, case["gate"])
    want = case["expect"]

    assert got.aggregate_score == pytest.approx(want["aggregateScore"])
    assert got.aggregate_score_percent == want["aggregateScorePercent"]
    assert got.would_route == want["wouldRoute"]

    for a in got.attributions:
        assert a.attribution_percent == want["attributionPercent"][a.label], (
            f"{a.label}: got {a.attribution_percent}%, platform says "
            f"{want['attributionPercent'][a.label]}%")


def test_tier_zero_carries_no_weight():
    base = [Signal("a", 0.5, 2), Signal("b", 0.5, 2)]
    with_informational = base + [Signal("noise", 0.0, 0)]
    assert aggregate(base, 0.4).aggregate_score == aggregate(with_informational, 0.4).aggregate_score
    assert aggregate(with_informational, 0.4).attributions[-1].attribution_percent == 0


def test_all_zero_allocation_does_not_divide_by_zero():
    result = aggregate([Signal("x", 1.0, 0)], 0.5)
    assert result.aggregate_score == 0.0
    assert result.would_route is False


def test_aggregate_is_bounded_by_min_and_max_score():
    rng = random.Random(20260824)
    for _ in range(200):
        signals = [
            Signal(f"s{i}", rng.random(), rng.randint(1, 3))
            for i in range(rng.randint(1, 8))
        ]
        score = aggregate(signals, 0.5).aggregate_score
        assert min(s.score for s in signals) - 1e-9 <= score <= max(s.score for s in signals) + 1e-9


def test_attributions_sum_to_100_when_any_contribution():
    rng = random.Random(7)
    for _ in range(200):
        signals = [
            Signal(f"s{i}", rng.random(), rng.randint(1, 3))
            for i in range(rng.randint(2, 8))
        ]
        total = sum(a.attribution_percent for a in aggregate(signals, 0.5).attributions)
        # integer rounding can drift a point or two across many signals
        assert abs(total - 100) <= len(signals)


def test_minimum_score_to_route_is_exact():
    signals = [Signal("a", 0.9, 3), Signal("b", 0.2, 2)]
    gate = 0.7
    need = minimum_score_to_route(signals, gate, "b")
    assert need is not None
    lifted = [Signal("a", 0.9, 3), Signal("b", need, 2)]
    assert aggregate(lifted, gate).aggregate_score == pytest.approx(gate)
    assert aggregate(lifted, gate).would_route


def test_tier_zero_signal_cannot_change_outcome():
    signals = [Signal("a", 0.1, 3), Signal("informational", 0.0, 0)]
    assert minimum_score_to_route(signals, 0.9, "informational") is None


def test_unreachable_gate_returns_none():
    signals = [Signal("a", 0.0, 3), Signal("b", 0.0, 1)]
    assert minimum_score_to_route(signals, 0.99, "b") is None


def test_rejects_out_of_range_inputs():
    with pytest.raises(ValueError):
        Signal("bad", 1.5, 2)
    with pytest.raises(ValueError):
        Signal("bad", 0.5, 4)
    with pytest.raises(ValueError):
        aggregate([Signal("a", 0.5, 1)], 1.5)
