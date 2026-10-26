"""Contract v134 / v135 / v135.1 (battlegrid-mcp README "Contract history"), against the corpus re-extracted at 135.2.0
on 2026-10-26 (docs/plans/2026-10-26-omega-reextraction-135.md).

- v134: the Multi-Timeframe Confluence platform section is refused; its lower-rung reads are custom columns.
- v135: an efficiency window counts changes; chainedOuters replaces rankableSpreadOperands; six series statistics.
- v135.1: 35 metrics, among them the bar clock and the trading-session levels.
"""
from __future__ import annotations

import json

import pytest

from omega.contract import CONTRACT_DIR, load
from omega.fanout import outputs_for, zone_vocabulary
from omega.preflight import union_key
from omega.types import Column, CustomSection, PlatformSection, Report
from omega.validate import validate_column, validate_report

A, L = {"rel": "anchor"}, {"rel": "lower"}
PROBE = json.loads((CONTRACT_DIR.parent / "audit" / "statistics_probe_135_2026-10-26.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def contract():
    return load()


def _errors(col: dict, contract) -> list:
    return [f for f in validate_column(Column.model_validate(col), path="c", contract=contract)
            if f.severity == "error"]


# --- v134 ---------------------------------------------------------------------------------------------------------
def test_the_mtf_section_is_refused(contract):
    assert "includeMtfConfluence" not in contract.platform_templates
    result = validate_report(Report(anchor="1h", sections=[PlatformSection(sectionKey="includeMtfConfluence")]),
                             contract=contract)
    assert result.errors


def test_its_lower_rung_reads_are_custom_columns_with_the_rendered_headers(contract):
    for col, header in (({"metric": "MA_ALIGN", "transformId": "value", "timeframe": L}, "MAalign_ltf"),
                        ({"metric": "RSI14", "transformId": "classifyZone", "timeframe": L}, "RSI14_ltf_zone"),
                        ({"metric": "ADX", "transformId": "classifyZone", "timeframe": L}, "ADX14_ltf_zone")):
        assert not _errors(col, contract)
        assert [o.header for o in outputs_for(Column.model_validate(col), contract)] == [header]
    report = Report(anchor="1h", sections=[CustomSection(kind="custom", title="Multi-Timeframe Confluence (lower rung)",
                                                         benchmarkTicker=None, columns=[
        Column.model_validate({"metric": "ADX", "transformId": "classifyZone", "timeframe": L})])])
    assert not validate_report(report, contract=contract).errors


def test_adx_zone_serves_its_own_labels():
    assert zone_vocabulary("ADX") == ("weak", "developing", "trending", "extreme")
    assert "bullish" in zone_vocabulary("MFI14") and zone_vocabulary("RSI14") == ("overbought", "oversold", "neutral")


def test_perp_spot_gap_is_in_the_perp_spot_flow_template(contract):
    cols = contract.platform_templates["includePerpSpotFlow"]["columns"]
    assert {"metric": "PERP_SPOT_GAP", "transformId": "value", "timeframe": A} in cols


# --- v135 ---------------------------------------------------------------------------------------------------------
def test_the_stored_efficiency_template_window_moved_to_w_minus_1(contract):
    [er] = [c for c in contract.platform_templates["includeSubTimeframe"]["columns"]
            if c["transformId"] == "efficiency"]
    assert er["window"] == 4            # 5 before v135: the server moved stored windows to w - 1, the same 5 bars


def test_chained_outers_replace_rankable_spread_operands(contract):
    spread = contract.metric("EMA5").transforms["spread"]
    assert "rankableSpreadOperands" not in spread
    assert set(spread["chainedOuters"]) == set(spread["chainSuccessors"])
    assert spread["chainedOuters"]["rank"]["operands"] == ["EMA13"]
    assert spread["chainedOuters"]["efficiency"]["windowMaximum"] == 63
    assert spread["chainedOuters"]["zscore"]["windowMaximum"] == 64


def test_a_chain_window_above_the_served_maximum_is_refused(contract):
    base = {"metric": "EMA20", "transformId": "distance", "timeframe": A}
    assert not _errors(base | {"chainedTransformId": "efficiency", "window": 63}, contract)
    [f] = _errors(base | {"chainedTransformId": "efficiency", "window": 64}, contract)
    assert f.code == "LOOKBACK_EXCEEDED" and "windowMaximum" in f.message
    assert not _errors(base | {"chainedTransformId": "zscore", "window": 64}, contract)


def test_a_spread_chain_over_an_operand_the_outer_does_not_offer_is_refused(contract):
    spread = contract.metric("EMA5").transforms["spread"]
    offered = set(spread["chainedOuters"]["zscore"]["operands"])
    outside = next(o for o in contract.metric("EMA5").spread_operands if o not in offered)
    col = {"metric": "EMA5", "transformId": "spread", "chainedTransformId": "zscore", "timeframe": A, "window": 10}
    assert not _errors(col | {"inputs": [{"metric": "EMA13"}]}, contract)
    assert _errors(col | {"inputs": [{"metric": outside}]}, contract)


def test_the_atom_window_maximum_is_served(contract):
    assert contract.metric("CLOSE").transforms["efficiency"]["maximums"]["window"] == 63
    assert not _errors({"metric": "CLOSE", "transformId": "efficiency", "timeframe": A, "window": 63}, contract)
    assert _errors({"metric": "CLOSE", "transformId": "efficiency", "timeframe": A, "window": 64}, contract)


@pytest.mark.parametrize("case", [c for c in PROBE["renders"] if c["outputs"]],
                         ids=lambda c: json.dumps(c["column"], sort_keys=True))
def test_every_probed_header_is_predicted_exactly(case, contract):
    """The six statistics (atom and chain outer), efficiency, the MTF replacements and PERP_SPOT_GAP, rendered live."""
    col = Column.model_validate(case["column"])
    assert [o.header for o in outputs_for(col, contract)] == [o["header"] for o in case["outputs"]]


def test_the_chain_outer_parameters_carry_a_unit():
    params = json.loads((CONTRACT_DIR / "transforms" / "_chain_outer_parameters.json")
                        .read_text(encoding="utf-8"))["chainOuterParameters"]
    assert params["efficiency"]["window"]["unit"] == "seriesChanges"
    assert params["pctl"]["window"]["unit"] == "priorElements"
    assert params["zscore"]["window"]["unit"] == "seriesElements"


# --- v135.1 -------------------------------------------------------------------------------------------------------
def test_the_bar_clock_and_session_levels_are_in_the_corpus(contract):
    for key in ("UTC_HOUR", "DAY_OF_WEEK", "TRADING_SESSION", "ASIA_HIGH", "PRIOR_NEW_YORK_LOW_SWEPT", "OR15_HIGH",
                "IB_EXT_UP_150"):
        assert key in contract.metrics, key
    assert contract.metric("ASIA_HIGH").is_timeless


# --- v115.1 (between the 110.13.0 and 135.2.0 captures) -----------------------------------------------------------
def test_a_discriminated_union_is_read_under_one_of():
    assert union_key({"oneOf": []}) == "oneOf" and union_key({"anyOf": []}) == "anyOf" and union_key({}) is None
