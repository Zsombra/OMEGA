"""Platform-section membership, replayed against the live measurement.

Until 2026-08-25 `omega.membership` modelled custom columns only. Platform sections
contributed nothing, so `analyse` reported a platform-built report as having zero
metrics and `check_allocations` returned a confident `error` telling you to add a
column you already had. The audit found all 25 private strategies on this account are
platform-sections-only, so the tool was wrong for every strategy that exists.

All 25 sections were then measured with `derive_strategy_rule_view`. These tests replay
that measurement and pin the two properties that make the fix safe: the mapping is
exactly 1:1, and an unmeasured section is refused rather than guessed at.
"""
from __future__ import annotations

import json

import pytest

from omega.contract import DERIVED_DIR
from omega.membership import (
    analyse, check_allocations, modules_for_sections, platform_caveat,
    suggest_sections_for,
)
from omega.types import Column, CustomSection, PlatformSection, Report, Rule

PM = json.loads((DERIVED_DIR / "platform_section_map.json").read_text(encoding="utf-8"))
MAP = json.loads((DERIVED_DIR / "signal_module_map.json").read_text(encoding="utf-8"))
FEEDS = PM["sectionFeedsModule"]
BARREN = PM["sectionsFeedingNothing"]
COUNTS = PM["measuredSignalCount"]

# The sectionKey enum, copied verbatim from the live derive_strategy_rule_view schema.
# If the platform adds a section, this list goes stale and the coverage test fails -
# which is the point: an unmeasured section must never be silently treated as empty.
SCHEMA_KEYS = [
    "includePriceAction", "includeSubTimeframe", "includeRsi", "includeMacd",
    "includeVolume", "includeVolatility", "includeBollingerBands",
    "includeMovingAverages", "includeStochastic", "includeFundingRates",
    "includeOpenInterest", "includeRelativeStrength", "includeSupportResistance",
    "includeTrendStrength", "includeMfi", "includeCvd", "includeHigherTimeframe",
    "includeMtfConfluence", "includeRegimeContext", "includeCrowdIntelligence",
    "includeCvdCrowdConvergence", "includeStructureZones", "includePerpSpotFlow",
    "includeMarketBreadth", "includeReferencePairs",
]


def _platform(*keys) -> Report:
    return Report(anchor="1h",
                  sections=[PlatformSection(sectionKey=k) for k in keys])


# --- the measurement, replayed ----------------------------------------------

@pytest.mark.parametrize("key", SCHEMA_KEYS)
def test_a_section_predicts_its_measured_signal_count(key):
    """What omega derives must equal what the connector actually returned."""
    assert len(analyse(_platform(key)).signals_in) == COUNTS[key]


@pytest.mark.parametrize("key", sorted(FEEDS))
def test_a_feeding_section_delivers_its_whole_module(key):
    """The 1:1 rule. A section that feeds a module feeds ALL of it, rung variants
    included - which is why includeMovingAverages measured 10 and not 6."""
    assert COUNTS[key] == len(MAP["moduleSignals"][FEEDS[key]])


def test_every_schema_section_is_measured():
    assert set(SCHEMA_KEYS) == set(FEEDS) | set(BARREN)
    assert not (set(FEEDS) & set(BARREN))


def test_no_two_sections_feed_the_same_module():
    """If two did, the reverse lookup in _how_to_feed would be ambiguous."""
    mods = list(FEEDS.values())
    assert len(mods) == len(set(mods))


def test_sections_and_columns_reach_the_same_77_signals():
    """Neither route is a superset of the other. Both stop at CONFLUENCE and
    COMPARISON, and those two are the entire 84-minus-77 gap."""
    by_section = set()
    for key in FEEDS:
        by_section |= analyse(_platform(key)).signals_in
    every = {s for v in MAP["moduleSignals"].values() for s in v}
    unreachable = {s for k, u in MAP["unreachableModules"].items()
                   if not k.startswith("_") for s in u["signals"]}
    assert len(by_section) == 77
    assert every - by_section == unreachable


def test_a_section_and_its_metric_are_interchangeable():
    """Measured: includeRsi alone and one RSI14 column give identical membership."""
    col = Report(anchor="1h", sections=[CustomSection(
        title="rsi", benchmarkTicker=None,
        columns=[Column(metric="RSI14", transformId="value",
                        timeframe={"rel": "anchor"})])])
    assert analyse(_platform("includeRsi")).signals_in == analyse(col).signals_in


# --- the eight that feed nothing --------------------------------------------

@pytest.mark.parametrize("key", sorted(BARREN))
def test_a_barren_section_feeds_nothing(key):
    mem = analyse(_platform(key))
    assert mem.signals_in == set()
    assert mem.barren_sections == {key}


def test_higher_timeframe_does_not_feed_htf_signals():
    """The trap worth naming: the section called 'higher timeframe' feeds no htf_*
    signal. Those come free with RSI, MOVING_AVERAGES and TREND_STRENGTH."""
    assert "htf_rsi_oversold" not in analyse(_platform("includeHigherTimeframe")).signals_in
    assert "htf_rsi_oversold" in analyse(_platform("includeRsi")).signals_in
    assert "includeHigherTimeframe" not in FEEDS


def test_the_htf_decoy_is_called_out_in_the_finding():
    finding = check_allocations(
        _platform("includeHigherTimeframe"),
        [Rule(signalId="htf_rsi_oversold", allocation=3, required=False)])[0]
    assert finding.severity == "error"
    assert "includeRsi" in finding.message
    assert "includeHigherTimeframe" in finding.message


# --- the regression itself --------------------------------------------------

def test_a_platform_report_no_longer_produces_a_false_error():
    """The bug: this returned [error] rsi_oversold ... 'Add one of: RSI14, RSI7'
    for a report that already had RSI in report with reportDefaultAllocation 1."""
    findings = check_allocations(
        _platform("includeRsi"),
        [Rule(signalId="rsi_oversold", allocation=3, required=False)])
    assert findings == []


def test_a_real_gap_in_a_platform_report_is_still_an_error():
    """The fix must not have turned the check off."""
    finding = check_allocations(
        _platform("includeRsi"),
        [Rule(signalId="macd_bull_cross", allocation=2, required=False)])[0]
    assert finding.severity == "error"
    assert "includeMacd" in finding.message
    assert "MACD" in finding.message


def test_an_unmeasured_section_is_refused_not_guessed():
    """A sectionKey the platform adds later must degrade to 'cannot determine',
    never to a confident NOT_IN_REPORT - that is the failure mode being fixed."""
    report = _platform("includeSomethingAddedLater")
    mem = analyse(report)
    assert not mem.is_complete
    assert mem.unknown_sections == {"includeSomethingAddedLater"}
    finding = check_allocations(
        report, [Rule(signalId="rsi_oversold", allocation=2, required=False)])[0]
    assert finding.severity == "warn"
    assert "derive_strategy_rule_view" in finding.message


def test_a_mixed_report_unions_both_routes():
    mixed = Report(anchor="1h", sections=[
        PlatformSection(sectionKey="includeRsi"),
        CustomSection(title="m", benchmarkTicker=None, columns=[
            Column(metric="MACD", transformId="value", timeframe={"rel": "anchor"})]),
    ])
    mem = analyse(mixed)
    assert mem.modules_in == {"RSI", "MACD"}
    assert len(mem.signals_in) == 12
    assert mem.sections == {"includeRsi"}
    assert mem.metrics == {"MACD"}


# --- the helpers ------------------------------------------------------------

def test_suggest_sections_names_a_section_or_admits_none():
    got = suggest_sections_for(["cvd_bullish", "mtf_aligned_bull", "htf_rsi_oversold"])
    assert got["cvd_bullish"] == "includeCvd"
    assert got["mtf_aligned_bull"] is None
    assert got["htf_rsi_oversold"] == "includeRsi"
    assert "CVD" in modules_for_sections({got["cvd_bullish"]})


def test_the_caveat_no_longer_claims_sections_are_unmodelled():
    text = platform_caveat()
    assert "not modelled" not in text.lower()
    assert "includeHigherTimeframe" in text
    assert PM["_measured"] in text
