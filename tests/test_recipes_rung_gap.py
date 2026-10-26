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

RETIRED at contract 108 (2026-10-11): signal rules and the draft's `mismatches` are gone
(README "Contract history - v108"), so the scoring-data columns this file pinned fed nothing,
and plan() no longer adds them (Thesis.show_scoring_data retired). The measured fixtures and
the predictor tests stay as history; the 2026-10-10 shape is omega.generate.plan_pre_108, and
the section "contract 108" below pins what plan() now drops per preset.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tests.moves_110 import rewritten_at_110   # the body as the server holds it since 110
from omega.contract import load, stage_schema
from omega.generate import PRESETS, plan, plan_pre_108

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
    arms = (stage_schema()["stage_strategy_draft"]["inputSchema"]["properties"]
            ["axes"]["properties"]["REPORT"]["properties"]["sections"]["items"]["oneOf"])   # oneOf since v115.1
    custom = arms[1]
    assert "timeframe" not in custom["properties"] and custom["additionalProperties"] is False
    tf = custom["properties"]["columns"]["items"]["properties"]["timeframe"]["anyOf"]
    assert tf[0]["properties"]["rel"]["enum"] == ["anchor", "lower", "regime"]
    assert "abs" in tf[1]["properties"]
    c = load()
    higher = c.platform_templates["includeHigherTimeframe"]["columns"]
    assert {(x["metric"], x["transformId"], x["timeframe"]["rel"]) for x in higher} >= {
        ("ADX", "value", "regime"), ("RSI14", "value", "regime"), ("MA_ALIGN", "value", "regime")}
    # v134 retired includeMtfConfluence (it held MA_ALIGN at lower, anchor and regime); its lower-rung reads are custom
    # columns now, so the template is gone and the section key is refused
    assert "includeMtfConfluence" not in c.platform_templates


# --- the predictor against the committed body (step 2) --------------------------------



COMMITTED = rewritten_at_110(json.loads((FIXTURES / "current_7534b2ee_from_get_strategy_20261010T0634Z.json")
                                         .read_text(encoding="utf-8"))["draft"]["content"])


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


# --- the recipes close the gap (step 3) --------------------------------------------------

def _pre_1010(name: str):
    """The preset as it was planned before 2026-10-10: REGIME as context, no scoring-data
    columns, the pre-108 allocation - the shape BattleGrid judged on 2026-10-06 and 2026-10-09/10."""
    return plan_pre_108(replace(PRESETS[name], context=["REGIME"]), show_scoring_data=False)


def _1010(name: str):
    """The preset as planned 2026-10-10..10-11 (v0.3.2): the scoring-data columns, REGIME dropped."""
    return plan_pre_108(PRESETS[name])


def _cols(p) -> list[tuple[str, str, str, str]]:
    """(section title, metric, transformId, rel) of every custom column, in report order."""
    return [(s.title, c.metric, c.transformId, c.timeframe.rel)
            for s in p.report.sections for c in s.columns]


# The residue closing the ACTIVE gaps leaves on trend-continuation: four unreachable signals
# (CONFLUENCE, COMPARISON - docs/07) whose data is a subset of what the weighted MA signals
# score on. The platform's two rules cannot both be satisfied by columns; predicted, unmeasured.
FORCED = {"trend-continuation": {"mtf_aligned_bull", "mtf_aligned_bear",
                                 "comparison_sector_divergence", "comparison_sector_momentum"}}


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_every_preset_showed_every_weighted_signals_data_and_scored_what_it_showed(name):
    """History (v0.3.2). At 108 the critique carries no `scoring` line at all."""
    from omega.membership import predicted_diagnostics, scoring_gaps
    p = _1010(name)
    assert scoring_gaps(p.report, p.rules) == []
    got = predicted_diagnostics(p.report, p.rules)
    assert got["warnings"] == []
    off = {f.signal_id: f for f in got["mismatches"]}
    assert set(off) == FORCED.get(name, set())
    assert all(f.platform_code == "REPORT_DATA_SIGNAL_OFF" and f.forced for f in off.values())
    assert not [x for x in plan(PRESETS[name]).critique() if x.startswith("scoring ")]


def test_trend_continuation_predicts_zero_where_the_live_stages_measured_sixteen():
    """The fixture's 12 + 4 + 1 came from the pre-10-10 shape, which omega still generates
    (show_scoring_data=False, REGIME as context) and predicts exactly; the preset now
    predicts nothing."""
    from omega.membership import predicted_diagnostics
    old = _pre_1010("trend-continuation")
    got = predicted_diagnostics(old.report, old.rules)
    by_code: dict[str, dict[str, set]] = {}
    for f in got["mismatches"]:
        by_code.setdefault(f.platform_code, {})[f.signal_id] = set(f.missing)
    assert by_code == _by_code(CREATE["diagnostics"])
    assert len(got["mismatches"]) == 16 and len(got["warnings"]) == 1
    new = _1010("trend-continuation")
    now = predicted_diagnostics(new.report, new.rules)
    assert [f for f in now["mismatches"] if f.platform_code == "ACTIVE_SIGNAL_DATA_NOT_IN_REPORT"] == []
    assert now["warnings"] == []
    # none of the measured sixteen survives; what remains is the forced residue, new and unmeasured
    assert {f.signal_id for f in now["mismatches"]} == FORCED["trend-continuation"]
    assert {f.signal_id for f in now["mismatches"]}.isdisjoint(
        {sid for sids in _by_code(CREATE["diagnostics"]).values() for sid in sids})


def test_the_committed_report_is_reproducible_by_plan_with_regime_as_context():
    """The body committed on 2026-10-09 (action 61) stays reproducible, keyless as a CREATE
    sends it - the axes_update round trip is tested against it. At 108 plan() adds no
    scoring-data column, so REGIME as context alone gives it; the pre-108 path agrees."""
    committed = [{k: v for k, v in s.items() if k != "sectionKey"} for s in COMMITTED["REPORT"]["sections"]]
    assert plan(replace(PRESETS["trend-continuation"], context=["REGIME"])).axes()["REPORT"]["sections"] == committed
    assert _pre_1010("trend-continuation").axes()["REPORT"]["sections"] == committed


ADDED = {
    # preset: {(section, metric, transformId, rel)} - the columns 2026-10-10 adds to the recipes
    "mean-reversion": {
        ("Mean Reversion at Extremes Signals", "CCI20", "value", "anchor"),       # bollinger_cci_*
        ("Mean Reversion at Extremes Signals", "BB_WIDTH", "value", "anchor"),    # bollinger_squeeze
        ("Mean Reversion at Extremes Signals", "RSI14", "value", "regime"),       # htf_rsi_*
        ("Mean Reversion at Extremes Signals", "RSI14", "value", "lower"),        # ltf_rsi_*
        ("Mean Reversion at Extremes Context", "FUNDING_ANN", "value", "anchor"),  # funding_extreme_*
    },
    "trend-continuation": {
        ("Trend Continuation Signals", "MA_ALIGN", "value", "regime"),    # htf_ma_aligned_*
        ("Trend Continuation Signals", "MA_ALIGN", "value", "lower"),     # ltf_ma_aligned_*
        ("Trend Continuation Signals", "EMA20", "value", "anchor"),       # ma_ema_aligned_*
        ("Trend Continuation Signals", "EMA_CROSS", "value", "anchor"),   # ma_ema_*_cross
        ("Trend Continuation Signals", "ADX", "value", "regime"),         # htf_trend_adx_*
        ("Trend Continuation Signals", "ADX", "value", "lower"),          # ltf_trend_adx_*
    },
    "squeeze-breakout": {
        ("Squeeze Breakout Signals", "CCI20", "value", "anchor"),
        ("Squeeze Breakout Signals", "BB_WIDTH", "value", "anchor"),
    },
    "flow-divergence": {
        ("Spot-Led Accumulation Context", "FUNDING_ANN", "value", "anchor"),
    },
    "structure-reversal": {
        ("Structure Reversal Signals", "STRUCT_ZONES", "count", "regime"),   # structure_* (no `value` on an entitySet)
        ("Structure Reversal Signals", "RSI14", "value", "regime"),
        ("Structure Reversal Signals", "RSI14", "value", "lower"),
    },
}
# the REGIME context columns every preset dropped (REPORT_DATA_SIGNAL_OFF x4, the module warning)
DROPPED = {("REGIME_TREND", "trajectory", "anchor"), ("REGIME_VOL", "value", "anchor"),
           ("REGIME_MOM", "value", "anchor")}


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_exactly_these_columns_were_added_and_the_regime_context_dropped(name):
    """History: what 2026-10-10 changed (v0.3.2)."""
    new, old = set(_cols(_1010(name))), set(_cols(_pre_1010(name)))
    assert new - old == ADDED[name]
    assert {(m, t, r) for _, m, t, r in old - new} == DROPPED
    # candle metrics land in the Signals section, timeless ones in Context (04: a timeless
    # metric accepts only the anchor; no section carries a timeframe on the v91 axis)
    c = load()
    for section, metric, _, rel in ADDED[name]:
        assert section.endswith("Context" if c.metric(metric).is_timeless else "Signals")
        assert rel == "anchor" or not c.metric(metric).is_timeless


def test_every_added_column_is_a_vocabulary_value():
    """Metric in the served roster, transform in the metric's own list, rel in the schema's
    enum - and the non-anchor MA_ALIGN / ADX / RSI14 columns are the platform's own template
    columns (includeHigherTimeframe at regime, includeMtfConfluence at lower)."""
    c = load()
    rel_enum = (stage_schema()["stage_strategy_draft"]["inputSchema"]["properties"]
                ["axes"]["properties"]["REPORT"]["properties"]["sections"]["items"]["oneOf"][1]["properties"]
                ["columns"]["items"]["properties"]["timeframe"]["anyOf"][0]["properties"]["rel"]["enum"])
    templated = {(x["metric"], x["transformId"], x["timeframe"]["rel"])
                 for x in c.platform_templates["includeHigherTimeframe"]["columns"]}
    # includeMtfConfluence (retired at v134) showed these at {rel: lower}; v134 names its lower-rung reads as custom
    # columns: MA_ALIGN x value, RSI14 x classifyZone and ADX x classifyZone at {rel: lower}
    templated |= {("MA_ALIGN", "value", "lower"), ("RSI14", "classifyZone", "lower"), ("ADX", "classifyZone", "lower")}
    for name, added in ADDED.items():
        for _, metric, transform, rel in added:
            assert metric in c.metrics, (name, metric)
            assert c.metric(metric).offers(transform), (name, metric, transform)
            assert rel in rel_enum
            if metric in ("MA_ALIGN", "ADX", "RSI14") and rel != "anchor":
                # the platform shows this metric at this rel (the transform never matters, M1)
                assert (metric, rel) in {(m, r) for m, _, r in templated}, (name, metric, rel)
    # `value` is the plainest transform; STRUCT_ZONES offers none, so `count` (its first)
    assert "value" not in c.metric("STRUCT_ZONES").transforms
    assert next(iter(c.metric("STRUCT_ZONES").transforms)) == "count"


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_the_reports_walk_the_schema_and_stay_in_budget(name):
    from omega import preflight as P
    p = plan(PRESETS[name])
    root = stage_schema()["stage_strategy_draft"]["inputSchema"]
    findings = P.diff_schema({"draftVersion": 0, "axes": p.axes()}, root, root)
    assert [(f.cls, f.path) for f in findings if f.verdict == "FAIL"] == []
    assert p.validation().ok, p.validation().report()
    cost = p.cost()
    assert cost.breaches == []
    assert len(cost.distinct_timeframes) <= load().budgets["distinctTimeframes"]
    # the preview cap is 150,000 result characters (v92); the agent-token estimate is far inside it
    assert cost.estimated_tokens * 4 < load().shared["previewExecutionLimits"]["maxResultChars"]
    preview = stage_schema()["preview_strategy_report"]["inputSchema"]
    assert [f for f in P.diff_schema(p.preview_request(), preview, preview) if f.verdict == "FAIL"] == []


def test_the_token_estimate_after_the_change():
    """Reported, not capped: trend-continuation read ~918 agent tokens before and after 2026-10-10 (six
    one-header `value` columns in, six REGIME headers out); at 108 the six columns go and it reads ~756."""
    assert _1010("trend-continuation").cost().estimated_tokens == 918
    assert _pre_1010("trend-continuation").cost().estimated_tokens == 918
    assert plan(PRESETS["trend-continuation"]).cost().estimated_tokens == 756


def test_a_context_module_is_still_honoured_and_no_longer_warns():
    """Thesis.context stays: reading material the condition checklist does not read. Before 108
    BattleGrid flagged its unweighted signals (history, the pre-108 plan); at 108 neither the
    platform nor the critique has anything to say about it."""
    from omega.membership import predicted_diagnostics
    t = replace(PRESETS["trend-continuation"], context=["REGIME"])
    old = plan_pre_108(t)
    got = predicted_diagnostics(old.report, old.rules)
    regime = {"regime_alignment", "regime_divergence", "regime_trend_shift", "regime_volatility_shift"}
    assert {f.signal_id for f in got["mismatches"] if not f.forced} == regime
    assert {f.signal_id for f in got["mismatches"] if f.forced} == FORCED["trend-continuation"]
    assert [w.code for w in got["warnings"]] == ["MODULE_IN_REPORT_SCORES_NOTHING"]
    p = plan(t)
    assert {"REGIME_TREND", "REGIME_VOL", "REGIME_MOM"} <= {c.metric for s in p.report.sections for c in s.columns}
    assert not [x for x in p.critique() if x.startswith("scoring ")]


# --- contract 108: the columns that existed only to feed signals are dropped -------------------

@pytest.mark.parametrize("name", sorted(PRESETS))
def test_at_108_plan_drops_exactly_the_scoring_data_columns(name):
    """The REPORT keeps the columns the conditions read and the modules the thesis weights: the module recipes.
    What goes is exactly the 2026-10-10 scoring-data columns (ADDED) - they fed signals and nothing else."""
    now, widened, recipes = plan(PRESETS[name]), _1010(name), plan_pre_108(PRESETS[name], show_scoring_data=False)
    assert set(_cols(widened)) - set(_cols(now)) == ADDED[name]
    assert set(_cols(now)) - set(_cols(widened)) == set()
    assert _cols(now) == _cols(recipes)
    assert now.rules == [] and now._rules() and all(r["allocation"] == 0 for r in now._rules())


@pytest.mark.parametrize("name", sorted(PRESETS))
def test_at_108_every_condition_header_is_still_in_the_report(name):
    """Dropping the scoring-data columns removes no header a condition reads."""
    p = plan(PRESETS[name])
    assert not [f for f in p.condition_findings() if f.severity == "error"]


# --- the regime rung is a distinct timeframe (step 4) ----------------------------------------

def test_the_regime_rung_counts_as_a_distinct_timeframe():
    """The 2026-08-24 preview of anchor + lower + regime columns at 1h read
    distinctTimeframes.used 3 (_renders_tfvariants.json), though the authoring contract resolves
    `regime` to null (it binds from the strategy's regimeTimeframe). cost_report and
    validate_report counted 2; both now count the rung."""
    from omega.fanout import cost_report
    from omega.types import Column, CustomSection, Report
    from omega.validate import validate_report
    variants = json.loads((ROOT / "data/contract/columns/_renders_tfvariants.json").read_text(encoding="utf-8"))
    assert variants["response"]["budgetUsage"]["distinctTimeframes"]["used"] == 3
    cols = [Column.model_validate(c) for c in variants["request"]["sections"][0]["columns"]]
    report = Report(anchor=variants["request"]["timeframe"], sections=[
        CustomSection(title="omega tf variants", benchmarkTicker=None, columns=cols)])
    assert cost_report(report).distinct_timeframes == ["15m", "1h", "regime"]
    assert validate_report(report).ok
    # the three rung-widened presets spent three of the eight (v0.3.2); the other two spent one
    spent = {name: _1010(name).cost().distinct_timeframes for name in PRESETS}
    assert spent == {"mean-reversion": ["15m", "1h", "regime"], "trend-continuation": ["15m", "1h", "regime"],
                     "structure-reversal": ["15m", "1h", "regime"],
                     "squeeze-breakout": ["1h"], "flow-divergence": ["1h"]}
    # at 108 the rung columns are gone: every preset reads its anchor alone
    assert {name: plan(PRESETS[name]).cost().distinct_timeframes for name in PRESETS} == {
        name: ["1h"] for name in PRESETS}


def test_nine_distinct_timeframes_including_the_regime_rung_breach_the_budget_of_eight():
    from omega.fanout import cost_report
    from omega.types import Column, CustomSection, Report
    from omega.validate import validate_report
    abs_tfs = ["1m", "3m", "5m", "30m", "2h", "4h", "8h"]            # 7 pinned + anchor 1h + regime = 9
    cols = [Column.model_validate({"metric": "RSI14", "transformId": "value", "timeframe": {"abs": t}})
            for t in abs_tfs]
    cols += [Column.model_validate({"metric": "RSI14", "transformId": "value", "timeframe": {"rel": r}})
             for r in ("anchor", "regime")]
    report = Report(anchor="1h", sections=[CustomSection(title="t", benchmarkTicker=None, columns=cols)])
    assert len(cost_report(report).distinct_timeframes) == 9
    assert any("distinct timeframes 9 > 8" in b for b in cost_report(report).breaches)
    # (the abs-pinned columns also share a header, so DUPLICATE_HEADER fires alongside)
    assert "DISTINCT_TIMEFRAMES_EXCEEDED" in {f.code for f in validate_report(report).errors}
