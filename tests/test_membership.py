"""Replay every derive_strategy_rule_view probe against the offline predictor."""
from __future__ import annotations

import json

import pytest

from omega.contract import DERIVED_DIR, load
from omega.membership import (
    analyse, check_allocations, modules_for, signals_for, suggest_columns_for,
)
from omega.types import Column, CustomSection, Report, Rule

MAP = json.loads((DERIVED_DIR / "signal_module_map.json").read_text(encoding="utf-8"))
PROBES = [p for p in MAP["probes"] if "metrics" in p]
CONTRACT = load()

# simplest legal transform per metric, so probe replay builds valid columns
SPECIAL = {"STRUCT_ZONES": "count"}


def _report(metrics) -> Report:
    cols = [Column(metric=m, transformId=SPECIAL.get(m, "value"),
                   timeframe={"rel": "anchor"},
                   **({"side": "support"} if m == "STRUCT_ZONES" else {}))
            for m in metrics]
    return Report(anchor="1h", sections=[
        CustomSection(title="P", benchmarkTicker=None, columns=cols)])


@pytest.mark.parametrize("probe", PROBES, ids=[p["id"] for p in PROBES])
def test_predicted_modules_match_connector(probe):
    predicted = modules_for(set(probe["metrics"]))
    expected = set(probe["modules"])
    assert predicted == expected, (
        f"\n  predicted: {sorted(predicted)}\n  connector: {sorted(expected)}")


@pytest.mark.parametrize("probe", PROBES, ids=[p["id"] for p in PROBES])
def test_predicted_signals_match_connector(probe):
    predicted = signals_for(set(probe["metrics"]))
    expected = {s for mod in probe["modules"] for s in MAP["moduleSignals"][mod]}
    assert predicted == expected


def test_map_is_internally_consistent():
    all_signals = {s for v in MAP["moduleSignals"].values() for s in v}
    assert len(all_signals) == 84, f"expected 84 distinct signals, got {len(all_signals)}"
    # every module in moduleSignals has a satisfiedBy entry
    assert set(MAP["moduleSignals"]) == set(MAP["moduleSatisfiedBy"])
    # no metric feeds two modules
    seen: dict[str, str] = {}
    for module, metrics in MAP["moduleSatisfiedBy"].items():
        for m in metrics:
            assert m not in seen, f"{m} maps to both {seen[m]} and {module}"
            seen[m] = module


def test_every_mapped_metric_exists_in_corpus():
    for module, metrics in MAP["moduleSatisfiedBy"].items():
        for m in metrics:
            assert m in CONTRACT.metrics, f"{module} references unknown metric {m}"


def test_mapped_plus_dead_covers_all_86_metrics():
    mapped = {m for v in MAP["moduleSatisfiedBy"].values() for m in v}
    dead = set(MAP["metricsSatisfyingNoModule"])
    assert not (mapped & dead), f"metric both mapped and dead: {mapped & dead}"
    assert mapped | dead == set(CONTRACT.metrics), (
        f"unaccounted metrics: {set(CONTRACT.metrics) - (mapped | dead)}")


def test_coverage_counts_are_accurate():
    c = MAP["coverage"]
    mapped = {m for v in MAP["moduleSatisfiedBy"].values() for m in v}
    assert c["metricsMappedToAModule"] == len(mapped)
    assert c["metricsSatisfyingNothing"] == len(MAP["metricsSatisfyingNoModule"])
    unreachable = {s for k, u in MAP["unreachableModules"].items()
                   if not k.startswith("_") for s in u["signals"]}
    assert c["signalsUnreachable"] == len(unreachable) == 7
    assert c["signalsReachable"] == 84 - len(unreachable)


def test_dead_metrics_are_reported():
    # VWAP is the headline surprise: canonical MR reference, feeds nothing
    result = analyse(_report(["VWAP", "RSI14"]))
    assert "VWAP" in result.dead_metrics
    assert "RSI14" not in result.dead_metrics
    assert "RSI" in result.modules_in


def test_the_original_panel_reproduces_the_recorded_membership():
    """The 7-column MR Stretch Panel returned 15 signals from the connector."""
    recorded = json.loads(
        (DERIVED_DIR / "aggregate_oracle.json").read_text(encoding="utf-8"))["reportMembership"]
    panel = _report(["VWAP", "RSI14", "CLOSE", "FUNDING_RATE", "BUY_PRESSURE"])
    predicted = analyse(panel).signals_in
    assert predicted == set(recorded["inReport"])
    assert len(predicted) == recorded["inReportCount"] == 15


def test_wasted_allocation_is_flagged():
    panel = _report(["RSI14"])
    rules = [
        Rule(signalId="rsi_oversold", allocation=3, required=False),
        Rule(signalId="bollinger_lower_touch", allocation=2, required=False),
        Rule(signalId="mtf_aligned_bull", allocation=1, required=False),
    ]
    findings = check_allocations(panel, rules)
    errs = {f.signal_id for f in findings if f.severity == "error"}
    assert errs == {"bollinger_lower_touch", "mtf_aligned_bull"}
    boll = next(f for f in findings if f.signal_id == "bollinger_lower_touch")
    assert "BB_PCT_B" in boll.message
    mtf = next(f for f in findings if f.signal_id == "mtf_aligned_bull")
    assert "unreachable" in mtf.message


def test_zero_allocation_is_not_an_error():
    findings = check_allocations(
        _report(["RSI14"]),
        [Rule(signalId="bollinger_squeeze", allocation=0, required=False)])
    assert all(f.severity == "info" for f in findings)


def test_suggest_columns_round_trips():
    got = suggest_columns_for(["cvd_bullish", "mtf_aligned_bull"])
    assert "BUY_PRESSURE" in got["cvd_bullish"]
    assert got["mtf_aligned_bull"] == []
    # what it suggests must actually work
    assert "CVD" in modules_for({got["cvd_bullish"][0]})


def test_membership_is_union_not_intersection():
    a, b = signals_for({"RSI14"}), signals_for({"MACD"})
    assert signals_for({"RSI14", "MACD"}) == a | b


def test_transform_and_timeframe_do_not_affect_membership():
    r1 = Report(anchor="1h", sections=[CustomSection(
        title="a", benchmarkTicker=None,
        columns=[Column(metric="RSI14", transformId="value", timeframe={"rel": "anchor"})])])
    r2 = Report(anchor="4h", sections=[CustomSection(
        title="b", benchmarkTicker=None,
        columns=[Column(metric="RSI14", transformId="trajectory",
                        timeframe={"rel": "regime"}, window=8, bars="closed")])])
    assert analyse(r1).signals_in == analyse(r2).signals_in
