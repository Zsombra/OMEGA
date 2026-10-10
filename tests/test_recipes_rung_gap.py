"""The recipes show every weighted signal's data (2026-10-10).

Measured on every live stage of the trend-continuation preset (2026-10-06 M1; 2026-10-09
23:10Z create, action 60; 2026-10-10 06:34Z update, action 62 - battlegrid-manager
tests/fixtures/2026-10-09-strategy-first-live/, copied to data/contract/stage_strategy_draft/
diagnostics_action6*.json): 12 ACTIVE_SIGNAL_DATA_NOT_IN_REPORT (weighted signals scoring on
data the report did not show: MA_ALIGN / ADX at the `signalHigher` and `lower` rungs, EMA20 /
EMA_CROSS at the anchor), 4 REPORT_DATA_SIGNAL_OFF (the REGIME context columns, whose four
signals sat at allocation 0) and 1 MODULE_IN_REPORT_SCORES_NOTHING warning.

How the vocabulary expresses a rung on a column: the v91 REPORT axis puts `timeframe` on the
COLUMN - {rel: anchor | lower | regime} or {abs: <tf>} - and a custom section carries no
timeframe at all (schema_20261005T194629Z.json, REPORT.sections.items.anyOf[1]). The
platform's own templates spell the two non-anchor rungs out: includeHigherTimeframe is
ADX / RSI14 / MA_ALIGN `value` at {rel: regime}, includeMtfConfluence holds MA_ALIGN `value`
at lower, anchor and regime (data/contract/templates/platform/_all.json). `regime` renders
with the `_htf` infix (RSI14_htf, data/contract/columns/_renders_tfvariants.json), the stem
of the `htf_*` signal ids whose data sits at `signalHigher`.
"""
from __future__ import annotations

import json
from pathlib import Path

from omega.contract import load

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data/contract/stage_strategy_draft"
CREATE = json.loads((FIXTURES / "diagnostics_action60_create_20261009T2310Z.json").read_text(encoding="utf-8"))
UPDATE = json.loads((FIXTURES / "diagnostics_action62_update_20261010T0634Z.json").read_text(encoding="utf-8"))
RUNG_MAP = json.loads((ROOT / "data/derived/signal_data_rungs_91.json").read_text(encoding="utf-8"))["signals"]


def _by_code(diagnostics: dict) -> dict[str, dict[str, set[tuple[str, str]]]]:
    out: dict[str, dict[str, set[tuple[str, str]]]] = {}
    for m in diagnostics["mismatches"]:
        out.setdefault(m["code"], {})[m["signalId"]] = {(d["metric"], d["rung"]) for d in m["data"]}
    return out


# --- the measured fixtures -------------------------------------------------------------

def test_the_two_live_stages_measured_the_same_seventeen_diagnostics():
    # the create's request named no strategy; its response carries the id the server minted
    for rec, action, revision in ((CREATE, 60, None), (UPDATE, 62, 1)):
        assert rec["_source"]["actionId"] == action and rec["_source"]["kind"] == "STAGE_STRATEGY"
        assert rec["_source"]["strategyId"] == "7534b2ee-5cd9-4f0b-81a0-c5dbf0a51278"
        assert rec["_source"]["committedRevision"] == revision
        d = rec["diagnostics"]
        assert d["errors"] == []
        assert rec["_counts"] == {"errors": 0, "mismatches": 16, "warnings": 1,
                                  "byCode": {"ACTIVE_SIGNAL_DATA_NOT_IN_REPORT": 12, "REPORT_DATA_SIGNAL_OFF": 4}}
        assert [w["code"] for w in d["warnings"]] == ["MODULE_IN_REPORT_SCORES_NOTHING"]
    assert CREATE["diagnostics"] == UPDATE["diagnostics"]
    assert CREATE["_source"]["performedAt"].startswith("2026-10-09T23:09")
    assert UPDATE["_source"]["performedAt"].startswith("2026-10-10T06:33")


def test_the_measured_active_mismatches_are_the_rung_maps_entries_for_those_signals():
    """Each mismatch's data is exactly the (metric, rung) the 2026-10-06 rung probe recorded for
    that signal: the two measurements agree, so the map predicts the live list."""
    active = _by_code(CREATE["diagnostics"])["ACTIVE_SIGNAL_DATA_NOT_IN_REPORT"]
    assert set(active) == {
        "htf_ma_aligned_bull", "htf_ma_aligned_bear", "htf_trend_adx_trending", "htf_trend_adx_ranging",
        "ltf_ma_aligned_bull", "ltf_ma_aligned_bear", "ltf_trend_adx_trending", "ltf_trend_adx_ranging",
        "ma_ema_aligned_bull", "ma_ema_aligned_bear", "ma_ema_bull_cross", "ma_ema_bear_cross"}
    for sid, data in active.items():
        assert data <= {(d["metric"], d["rung"]) for d in RUNG_MAP[sid]}, sid
    assert {rung for data in active.values() for _, rung in data} == {"anchor", "lower", "signalHigher"}
    off = _by_code(CREATE["diagnostics"])["REPORT_DATA_SIGNAL_OFF"]
    assert set(off) == {"regime_alignment", "regime_divergence", "regime_trend_shift", "regime_volatility_shift"}
    assert {m for data in off.values() for m, _ in data} == {"REGIME_TREND", "REGIME_VOL", "REGIME_MOM"}


def test_the_vocabulary_puts_the_rung_on_the_column_not_the_section():
    """The v91 REPORT axis: a custom section has no `timeframe`; a column's timeframe is
    {rel: anchor|lower|regime} or {abs}. The platform's own higher-timeframe template is the
    three metrics at {rel: regime}; the confluence template holds MA_ALIGN at all three rels."""
    from omega.contract import stage_schema
    arms = (stage_schema()["stage_strategy_draft"]["inputSchema"]["properties"]["request"]["properties"]
            ["axes"]["properties"]["REPORT"]["properties"]["sections"]["items"]["anyOf"])
    custom = arms[1]
    assert "timeframe" not in custom["properties"] and custom["additionalProperties"] is False
    tf = custom["properties"]["columns"]["items"]["properties"]["timeframe"]["anyOf"]
    assert tf[0]["properties"]["rel"]["enum"] == ["anchor", "lower", "regime"]
    assert "abs" in tf[1]["properties"]
    c = load()
    higher = c.platform_templates["includeHigherTimeframe"]["columns"]
    assert {(x["metric"], x["transformId"], x["timeframe"]["rel"]) for x in higher} >= {
        ("ADX", "value", "regime"), ("RSI14", "value", "regime"), ("MA_ALIGN", "value", "regime")}
    mtf = c.platform_templates["includeMtfConfluence"]["columns"]
    assert {(x["metric"], x["timeframe"]["rel"]) for x in mtf if x["metric"] == "MA_ALIGN"} == {
        ("MA_ALIGN", "lower"), ("MA_ALIGN", "anchor"), ("MA_ALIGN", "regime")}


# --- the predictor against the committed body (step 2) --------------------------------

COMMITTED = json.loads((FIXTURES / "current_7534b2ee_from_get_strategy_20261010T0634Z.json")
                       .read_text(encoding="utf-8"))["draft"]["content"]


def _committed_report_and_rules():
    """The body BattleGrid judged (the 11-column create of 2026-10-09), as omega types."""
    from omega.types import CustomSection, Report, Rule
    sections = [CustomSection.model_validate(s) for s in COMMITTED["REPORT"]["sections"]]
    rules = [Rule.model_validate({k: v for k, v in r.items() if k != "params"})
             for r in COMMITTED["SIGNAL_RULES"]["rules"]]
    return Report(anchor=COMMITTED["TIMEFRAME_PROFILE"]["timeframe"], sections=sections), rules


def test_rung_names_map_onto_the_columns_three_rels():
    from omega.membership import RUNG_REL
    assert RUNG_REL == {"anchor": "anchor", "lower": "lower", "signalHigher": "regime"}
    assert set(RUNG_REL) == {r for data in RUNG_MAP.values() for r in (d["rung"] for d in data)}


def test_the_predictor_reproduces_the_measured_seventeen_on_the_committed_body():
    """Same input, same verdict: on the body the server judged, omega predicts the 12 active
    gaps with the same data, the 4 off signals with the same data, and the one warning."""
    from omega.membership import predicted_diagnostics
    report, rules = _committed_report_and_rules()
    got = predicted_diagnostics(report, rules)
    measured = _by_code(CREATE["diagnostics"])
    by_code: dict[str, dict[str, set]] = {}
    for f in got["mismatches"]:
        by_code.setdefault(f.platform_code, {})[f.signal_id] = set(f.missing)
    assert {f.code for f in got["mismatches"]} == {"SCORING_INPUT_NOT_RENDERED", "REPORT_DATA_SIGNAL_OFF"}
    assert by_code == measured
    assert [w.code for w in got["warnings"]] == ["MODULE_IN_REPORT_SCORES_NOTHING"]
    assert "REGIME" in got["warnings"][0].message and "4" in got["warnings"][0].message


def test_a_column_at_the_rung_closes_the_gap():
    """What the measured list says is missing - MA_ALIGN @ signalHigher, ADX @ lower, EMA20 and
    EMA_CROSS @ anchor - is shown by one column each at the matching rel (the platform's own
    includeHigherTimeframe / includeMtfConfluence columns for the first two)."""
    from omega.membership import scoring_gaps
    from omega.types import Column, CustomSection, Report, Rule
    report, rules = _committed_report_and_rules()
    extra = [Column.model_validate(c) for c in (
        {"metric": "MA_ALIGN", "transformId": "value", "timeframe": {"rel": "regime"}},
        {"metric": "MA_ALIGN", "transformId": "value", "timeframe": {"rel": "lower"}},
        {"metric": "ADX", "transformId": "value", "timeframe": {"rel": "regime"}},
        {"metric": "ADX", "transformId": "value", "timeframe": {"rel": "lower"}},
        {"metric": "EMA20", "transformId": "value", "timeframe": {"rel": "anchor"}},
        {"metric": "EMA_CROSS", "transformId": "value", "timeframe": {"rel": "anchor"}})]
    widened = Report(anchor=report.anchor, sections=report.sections + [
        CustomSection(title="rungs", benchmarkTicker=None, columns=extra)])
    assert scoring_gaps(widened, rules) == []
    # an anchor column never stands in for another rung (2026-08-28, still true at 91)
    anchor_only = Report(anchor=report.anchor, sections=report.sections + [CustomSection(
        title="a", benchmarkTicker=None, columns=[c for c in extra if c.timeframe.rel == "anchor"])])
    left = {(m, r) for f in scoring_gaps(anchor_only, rules) for m, r in f.missing}
    assert left == {("MA_ALIGN", "signalHigher"), ("MA_ALIGN", "lower"),
                    ("ADX", "signalHigher"), ("ADX", "lower")}


def test_weighting_or_dropping_clears_an_off_signal():
    from omega.membership import report_data_signal_off
    from omega.types import Rule
    report, rules = _committed_report_and_rules()
    assert {f.signal_id for f in report_data_signal_off(report, rules)} == {
        "regime_alignment", "regime_divergence", "regime_trend_shift", "regime_volatility_shift"}
    weighted = [Rule(signalId=r.signalId, allocation=1 if r.signalId.startswith("regime_") else r.allocation,
                     required=False) for r in rules]
    assert report_data_signal_off(report, weighted) == []
    from omega.types import Report
    no_context = Report(anchor=report.anchor, sections=[
        s for s in report.sections if not any(c.metric.startswith("REGIME_") for c in s.columns)])
    assert report_data_signal_off(no_context, rules) == []
