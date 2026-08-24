"""Verify the fired-set aggregate semantics and the routing-feasibility tools.

The central fact under test - that the aggregate denominator counts only signals
that FIRED - overturned an assumption this project carried for most of its life.
These tests pin the evidence so it cannot quietly regress.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.feasibility import (
    Observation, blocking_requirements, drag_ranking, leverage,
    load_observations, load_rules, simulate,
)

ROOT = Path(__file__).resolve().parents[1]


# --- the denominator question, settled --------------------------------------

def test_dunkirk_aggregate_uses_fired_allocation_not_total():
    """The decisive measurement: 0.68 is numerator/21, not numerator/119."""
    d = json.loads((ROOT / "data" / "performance" / "dunkirk_sample.json")
                   .read_text(encoding="utf-8"))

    def walk(o):
        if isinstance(o, dict):
            if "id" in o and "effectiveAllocation" in o and "score" in o:
                yield o
            for v in o.values():
                yield from walk(v)
        elif isinstance(o, list):
            for v in o:
                yield from walk(v)

    sigs = list(walk(d))
    fired = [s for s in sigs if s.get("triggered")]
    num = sum(s["score"] * s["effectiveAllocation"] for s in fired)
    den_fired = sum(s["effectiveAllocation"] for s in fired)
    den_all = sum(s["effectiveAllocation"] for s in sigs)

    assert num / den_fired == pytest.approx(0.68, abs=5e-4)
    assert num / den_all == pytest.approx(0.12, abs=5e-4)
    # The recorded value is 0.68 - so the denominator is the fired set.
    assert abs(num / den_fired - 0.68) < abs(num / den_all - 0.68)


@pytest.mark.parametrize("ticker,expected_pct", [("BTC", 46), ("SOL", 52), ("ETH", 56)])
def test_preview_aggregate_is_mean_over_fired_signals(ticker, expected_pct):
    """Each preview's own aggregateScorePercent reproduces as sum/fired, all alloc 1."""
    raw = json.loads((ROOT / "data" / "performance" / "coin_observations.json")
                     .read_text(encoding="utf-8"))
    o = next(x for x in raw["observations"] if x["ticker"] == ticker)
    scores = list(o["scores"].values())
    assert round(sum(scores) / len(scores) * 100) == expected_pct
    # and the whole-scorecard denominator does NOT reproduce it
    assert round(sum(scores) / 84 * 100) != expected_pct


def test_unfired_signals_are_costless():
    """Adding allocation to a signal that never fires must not move the aggregate."""
    obs = Observation("T", "1h", {"rsi_oversold": 0.8})
    base = simulate([("rsi_oversold", 2)], 0.5, [obs]).results[0].aggregate
    padded = simulate([("rsi_oversold", 2), ("cvd_bullish", 3),
                       ("volume_surge", 3)], 0.5, [obs]).results[0].aggregate
    assert base == padded == 0.8


def test_a_fired_signal_helps_iff_its_score_exceeds_the_aggregate():
    """The defining property of a weighted mean, stated as a rule of thumb."""
    obs = Observation("T", "1h", {"a": 1.0, "b": 1.0, "c": 0.1})
    rules = [("a", 1), ("b", 1), ("c", 1)]
    agg = simulate(rules, 0.5, [obs]).results[0].aggregate
    for lv in leverage(rules, obs):
        if lv.score > agg:
            assert not lv.is_drag, f"{lv.signal_id} scores above the mean but reads as drag"
        else:
            assert lv.is_drag, f"{lv.signal_id} scores below the mean but reads as carrying"


# --- against the real captured scorecard ------------------------------------

def test_apex_sweep_reproduces_hand_computed_aggregates():
    """Per-ticker, so adding coins to the fixture extends rather than breaks this."""
    allocs, gate = load_rules("apex-imported")
    sweep = simulate(list(allocs.items()), gate, load_observations())
    got = {r.ticker: round(r.aggregate * 100, 1) for r in sweep.results}
    expected = {"BTC": 48.0, "SOL": 50.7, "ETH": 56.8, "GOOGL": 46.6, "GOLD": 59.1}
    for ticker, value in expected.items():
        assert got[ticker] == value, f"{ticker}: expected {value}, got {got[ticker]}"


def test_drag_ranking_separates_consistent_from_occasional():
    """A mean from one observation must not be ranked beside a mean from five."""
    allocs, _ = load_rules("apex-imported")
    out = drag_ranking(list(allocs.items()), load_observations(interval="1h"))
    assert "CONSISTENT" in out and "OCCASIONAL" in out
    consistent = out.split("OCCASIONAL")[0]
    # bollinger_squeeze fires on all four 1h coins; volume_surge on one
    assert "bollinger_squeeze" in consistent
    assert "volume_surge" not in consistent


def test_removing_the_top_drag_flips_btc_to_routing():
    """rel_roc_positive fires at 0.0008 and costs BTC 4.8 points of aggregate."""
    allocs, gate = load_rules("apex-imported")
    btc = next(o for o in load_observations() if o.ticker == "BTC")

    before = simulate(list(allocs.items()), gate, [btc]).results[0]
    assert not before.routes and before.aggregate == pytest.approx(0.4800, abs=5e-4)

    trimmed = {k: v for k, v in allocs.items() if k != "rel_roc_positive"}
    after = simulate(list(trimmed.items()), gate, [btc]).results[0]
    assert after.routes and after.aggregate == pytest.approx(0.5280, abs=5e-4)


def test_roc_signals_fire_at_effectively_zero():
    """Score = ROC/5 means ROC must reach 5% for 1.0; an hourly ROC(12) runs ~0.01%.

    Asserted on the scores themselves rather than on rendered text, and on the
    property that actually matters: whenever these fire, they fire at ~0.
    """
    obs = load_observations()
    seen = 0
    for o in obs:
        for sid in ("rel_roc_positive", "rel_roc_negative"):
            if sid in o.scores:
                seen += 1
                assert o.scores[sid] < 0.01, (
                    f"{sid} on {o.ticker} scored {o.scores[sid]} - if ROC signals can "
                    "score meaningfully, the drag conclusion needs revisiting")
    assert seen >= 4, "expected several ROC firings in the sample"


def test_roc_negative_is_the_top_consistent_drag():
    allocs, _ = load_rules("apex-imported")
    obs = load_observations()
    totals: dict[str, list[float]] = {}
    for o in obs:
        for lv in leverage(list(allocs.items()), o):
            totals.setdefault(lv.signal_id, []).append(lv.delta_pp)
    need = max(2, round(len(obs) * 0.5))
    consistent = {sid: sum(v) / len(v) for sid, v in totals.items() if len(v) >= need}
    assert max(consistent, key=consistent.get) == "rel_roc_negative"


# --- the one genuine structural block ---------------------------------------

def test_required_signal_with_no_column_blocks_everything():
    class R:
        def __init__(self, sid, alloc, req):
            self.signalId, self.allocation, self.required = sid, alloc, req

    rules = [R("rsi_oversold", 2, True), R("cvd_bullish", 2, False),
             R("bollinger_squeeze", 1, True)]
    blocked = blocking_requirements(rules, in_report={"rsi_oversold", "cvd_bullish"})
    assert blocked == ["bollinger_squeeze"]


def test_no_blocking_when_every_required_signal_is_fed():
    rules = [{"signalId": "rsi_oversold", "allocation": 2, "required": True}]
    assert blocking_requirements(rules, in_report={"rsi_oversold"}) == []


# --- housekeeping -----------------------------------------------------------

def test_tier_zero_is_excluded_from_both_sums():
    obs = Observation("T", "1h", {"a": 1.0, "b": 0.0})
    r = simulate([("a", 2), ("b", 0)], 0.5, [obs]).results[0]
    assert r.aggregate == 1.0 and r.fired == 1 and r.fired_weight == 2


def test_observation_from_preview_keeps_only_fired_scores():
    payload = {"coinTicker": "X", "allEvaluatedSignals": [
        {"id": "a", "score": 0.5}, {"id": "b", "score": 0}, {"id": "c", "score": 0.25}]}
    o = Observation.from_preview(payload, "1h")
    assert o.scores == {"a": 0.5, "c": 0.25}


def test_empty_scorecard_does_not_divide_by_zero():
    r = simulate([("a", 2)], 0.5, [Observation("T", "1h", {})]).results[0]
    assert r.aggregate == 0.0 and r.fired == 0 and not r.routes
