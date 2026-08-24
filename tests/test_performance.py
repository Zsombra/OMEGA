"""Edge analysis: parses real shapes, and refuses to over-claim on small samples."""
from __future__ import annotations

import json

import pytest

from omega.contract import ROOT
from omega.performance import (
    MIN_SAMPLE, analyse, load_sample, recommend_allocations, wilson_interval,
)

SAMPLE = json.loads(
    (ROOT / "data" / "performance" / "dunkirk_sample.json").read_text(encoding="utf-8"))


def _obs(fired: bool, won: bool, pnl: float = 1.0, sid: str = "sig") -> dict:
    return {"signals": [{"id": sid, "triggered": fired, "attributionPercent": 10}],
            "outcome": {"tradeOutcome": "WIN" if won else "LOSS", "netPnl": pnl}}


# --- the discipline -------------------------------------------------------
def test_below_minimum_sample_there_is_no_rate_at_all():
    """Not a missing value - a deliberate refusal, mirroring the platform."""
    r = analyse([_obs(True, True) for _ in range(MIN_SAMPLE - 1)])
    e = r.edges["sig"]
    assert e.fired == MIN_SAMPLE - 1
    assert e.readiness == "INSUFFICIENT_DATA"
    assert e.win_rate is None
    assert e.confidence_interval is None
    assert e.avg_net_pnl is None
    assert "INSUFFICIENT_DATA" in str(e)


def test_a_perfect_tiny_sample_still_reports_nothing():
    """4 wins from 4 is not a 100% edge."""
    r = analyse([_obs(True, True) for _ in range(4)])
    assert r.edges["sig"].win_rate is None
    assert r.ready == []


def test_at_the_threshold_it_becomes_readable():
    r = analyse([_obs(True, True) for _ in range(MIN_SAMPLE)])
    e = r.edges["sig"]
    assert e.readiness == "READY"
    assert e.win_rate == 1.0
    assert e.confidence_interval is not None


def test_recommendations_are_empty_when_nothing_is_ready():
    r = analyse([_obs(True, True) for _ in range(5)])
    assert recommend_allocations(r, {"sig": 1}) == []


# --- statistics -----------------------------------------------------------
def test_wilson_interval_is_wide_on_small_n_and_tight_on_large_n():
    lo_s, hi_s = wilson_interval(3, 4)
    lo_l, hi_l = wilson_interval(300, 400)
    assert (hi_s - lo_s) > (hi_l - lo_l)
    assert lo_s < 0.75 < hi_s and lo_l < 0.75 < hi_l


def test_wilson_never_leaves_the_unit_interval():
    for wins, n in [(0, 1), (1, 1), (0, 50), (50, 50), (0, 0)]:
        lo, hi = wilson_interval(wins, n)
        assert 0.0 <= lo <= hi <= 1.0


def test_lift_compares_fired_against_not_fired():
    obs = ([_obs(True, True) for _ in range(30)]          # fires: 100% win
           + [_obs(False, False) for _ in range(30)])      # absent: 0% win
    e = analyse(obs).edges["sig"]
    assert e.lift == pytest.approx(1.0)


def test_lift_is_none_without_a_comparable_absent_sample():
    e = analyse([_obs(True, True) for _ in range(MIN_SAMPLE)]).edges["sig"]
    assert e.lift is None


def test_a_signal_that_fires_on_everything_shows_no_lift():
    obs = [_obs(True, i % 2 == 0) for i in range(60)]
    e = analyse(obs).edges["sig"]
    assert e.readiness == "READY"
    assert e.lift is None          # never absent, so no baseline to compare against


# --- recommendations ------------------------------------------------------
def test_a_clearly_better_signal_is_promoted():
    obs = ([_obs(True, True) for _ in range(40)]
           + [_obs(False, False) for _ in range(40)])
    r = analyse(obs, totals={"winRate": 0.5})
    sug = recommend_allocations(r, {"sig": 1})
    assert sug and sug[0].suggested == 2
    assert "beats" in sug[0].reason


def test_a_clearly_worse_signal_is_demoted():
    obs = ([_obs(True, False) for _ in range(40)]
           + [_obs(False, True) for _ in range(40)])
    r = analyse(obs, totals={"winRate": 0.5})
    sug = recommend_allocations(r, {"sig": 3})
    assert sug and sug[0].suggested == 2
    assert "trails" in sug[0].reason


def test_an_inseparable_signal_is_left_alone():
    obs = [_obs(True, i % 2 == 0) for i in range(30)]
    r = analyse(obs, totals={"winRate": 0.5})
    sug = recommend_allocations(r, {"sig": 2})
    assert sug and sug[0].suggested == 2
    assert "straddles" in sug[0].reason


def test_allocation_stays_inside_the_legal_tier_range():
    up = analyse([_obs(True, True) for _ in range(40)] + [_obs(False, False) for _ in range(40)],
                 totals={"winRate": 0.5})
    assert recommend_allocations(up, {"sig": 3})[0].suggested == 3
    down = analyse([_obs(True, False) for _ in range(40)] + [_obs(False, True) for _ in range(40)],
                   totals={"winRate": 0.5})
    assert recommend_allocations(down, {"sig": 0})[0].suggested == 0


# --- real data ------------------------------------------------------------
def test_the_real_sample_parses():
    r = load_sample()
    assert r.observations == 1 and r.with_outcome == 1
    assert len(r.edges) == 66
    fired = [e for e in r.edges.values() if e.fired]
    assert len(fired) == 12


def test_the_real_sample_yields_no_conclusions():
    r = load_sample()
    assert r.ready == []
    assert recommend_allocations(r, {}) == []


def test_a_comparison_signal_did_fire_at_runtime():
    """Corrects doc 07: COMPARISON is unreachable via column design, not at runtime."""
    r = load_sample()
    assert r.edges["comparison_sector_momentum"].fired == 1


def test_trades_needed_is_reported_for_the_closest_signals():
    r = load_sample()
    need = r.trades_needed()
    assert need["bollinger_squeeze"] == MIN_SAMPLE     # fired on 1 of 1
    assert all(v is None or v >= MIN_SAMPLE for v in need.values())


def test_the_fleet_has_no_history():
    assert SAMPLE["fleetStatus"]["agentsWithAnyHistory"] == 1
    assert SAMPLE["fleetStatus"]["agents"] == 24


def test_min_sample_matches_the_platform_threshold():
    assert MIN_SAMPLE == SAMPLE["convictionCalibration"]["minSampleSize"] == 20


def test_render_is_ascii_safe():
    load_sample().render().encode("cp1252")
