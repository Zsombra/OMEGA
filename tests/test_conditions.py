"""Condition DSL: builders, offline type-checking, and live-verified fixtures."""
from __future__ import annotations

import json

import pytest

from omega.conditions import (
    all_of, ambient_headers, any_of, between, condition, in_, is_, market_read_text,
    n_of, not_, num, ref, report_headers, validate_conditions, validate_market_read,
)
from omega.contract import DERIVED_DIR
from omega.fanout import TOKENS_PER_HEADER, outputs_for
from omega.generate import PRESETS, plan
from omega.types import Column, CustomSection, Report

SURFACE = json.loads((DERIVED_DIR / "condition_surface.json").read_text(encoding="utf-8"))
PRESET_IDS = sorted(PRESETS)

SECTION_KEY = "custom:18c11ae8-bb26-5025-a01c-957043d42445"


def _report(*specs) -> Report:
    return Report(anchor="1h", sections=[CustomSection(
        title="T", sectionKey=SECTION_KEY, benchmarkTicker=None,
        columns=[Column.model_validate(s) for s in specs])])


RSI_REPORT = _report(
    {"metric": "RSI14", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4},
    {"metric": "RSI14", "transformId": "classifyZone", "timeframe": {"rel": "anchor"}},
)


# --- header prediction, corrected by the live render ----------------------
@pytest.mark.parametrize("spec,expected", [
    ({"metric": "RSI14", "transformId": "classifyZone", "timeframe": {"rel": "anchor"}}, "RSI14_zone"),
    ({"metric": "MFI14", "transformId": "classifyZone", "timeframe": {"rel": "anchor"}}, "MFI14_zone"),
    ({"metric": "MACD", "transformId": "crossDetect", "timeframe": {"rel": "anchor"}}, "MACD_cross"),
    ({"metric": "BB_TOUCH", "transformId": "value", "timeframe": {"rel": "anchor"}}, "BBtouch"),
    ({"metric": "MA_ALIGN", "transformId": "value", "timeframe": {"rel": "anchor"}}, "MAalign"),
    ({"metric": "SMA200", "transformId": "distance", "timeframe": {"rel": "anchor"}}, "dist_SMA200"),
    ({"metric": "REGIME_VOL", "transformId": "value", "timeframe": {"rel": "anchor"}}, "regVol"),
])
def test_header_matches_live_render(spec, expected):
    assert outputs_for(Column.model_validate(spec))[0].header == expected


def test_classify_zone_vocabulary_matches_live_render():
    out = outputs_for(Column.model_validate(
        {"metric": "RSI14", "transformId": "classifyZone", "timeframe": {"rel": "anchor"}}))[0]
    assert out.condition_operators == ["is", "in"]


# --- ambient headers ------------------------------------------------------
def test_ambient_headers_are_available_without_columns():
    amb = ambient_headers()
    for h in ("mktBreadth_all", "fieldUpBias_session", "usdtUsdDev_market", "fieldBiasDir_session"):
        assert h in amb
    # available even to an empty report
    assert "mktBreadth_all" in report_headers(Report(anchor="1h", sections=[]))


def test_ambient_condition_validates_with_no_columns():
    empty = Report(anchor="1h", sections=[])
    conds = [condition("BREADTH_UP", "Broad tape", num("mktBreadth_all", "gt", 20), verdict="UP")]
    assert not [f for f in validate_conditions(empty, conds) if f.severity == "error"]


def test_a_header_with_no_operators_is_rejected():
    empty = Report(anchor="1h", sections=[])
    conds = [condition("SPREAD", "n/a", num("picksSpread_session", "gt", 1))]
    errs = [f for f in validate_conditions(empty, conds) if f.severity == "error"]
    assert any("no condition operators" in f.message for f in errs)


# --- type checking --------------------------------------------------------
def test_unknown_header_is_rejected():
    conds = [condition("X", "bad", num("NOT_A_HEADER", "gt", 1))]
    errs = validate_conditions(RSI_REPORT, conds)
    assert any("not produced by any column" in f.message for f in errs)


def test_wrong_operator_for_kind_is_rejected():
    # RSI14_now is numeric; `is` is not offered
    conds = [condition("X", "bad", is_("RSI14_now", "rising"))]
    errs = validate_conditions(RSI_REPORT, conds)
    assert any("does not accept 'is'" in f.message for f in errs)


def test_label_outside_vocabulary_is_rejected():
    conds = [condition("X", "bad", is_("RSI14_trend", "sideways"))]
    errs = validate_conditions(RSI_REPORT, conds)
    assert any("vocabulary" in f.message for f in errs)


def test_in_labels_are_checked_against_vocabulary():
    conds = [condition("X", "bad", in_("RSI14_zone", ["overbought", "nonsense"]))]
    errs = validate_conditions(RSI_REPORT, conds)
    assert any("nonsense" in f.message for f in errs)


def test_valid_condition_passes():
    conds = [condition("OK", "fine",
                       all_of(is_("RSI14_trend", "rising"), num("RSI14_now", "lt", 70)),
                       verdict="UP")]
    assert not [f for f in validate_conditions(RSI_REPORT, conds) if f.severity == "error"]


def test_mismatched_section_key_is_rejected():
    conds = [condition("X", "bad", num("RSI14_now", "gt", 1, section_key="custom:deadbeef"))]
    errs = validate_conditions(RSI_REPORT, conds)
    assert any("lives in" in f.message for f in errs)


def test_null_section_key_is_accepted():
    """The live render resolved sectionKey=null to the right section."""
    conds = [condition("OK", "fine", num("RSI14_now", "gt", 30), verdict="UP")]
    assert not [f for f in validate_conditions(RSI_REPORT, conds) if f.severity == "error"]


# --- grammar --------------------------------------------------------------
def test_group_ops_are_the_schema_ops():
    assert set(SURFACE["grammar"]["definitionKinds"]["group"]["op"]) == {"ALL", "ANY", "NOT", "N_OF"}
    with pytest.raises(ValueError):
        any_of(num("RSI14_now", "gt", 1))  # fine
        from omega.conditions import group
        group("ALL_OF", [])


def test_n_of_exceeding_members_can_never_be_true():
    conds = [condition("X", "impossible",
                       n_of(4, is_("RSI14_trend", "rising"), num("RSI14_now", "lt", 70)))]
    errs = validate_conditions(RSI_REPORT, conds)
    assert any("can never be true" in f.message for f in errs)


def test_n_of_equal_to_members_warns():
    conds = [condition("X", "use ALL",
                       n_of(2, is_("RSI14_trend", "rising"), num("RSI14_now", "lt", 70)))]
    warns = [f for f in validate_conditions(RSI_REPORT, conds) if f.severity == "warning"]
    assert any("ALL says this more plainly" in f.message for f in warns)


def test_not_takes_exactly_one_member():
    from omega.conditions import group
    conds = [condition("X", "bad", group("NOT", [is_("RSI14_trend", "rising"),
                                                 num("RSI14_now", "lt", 70)]))]
    errs = validate_conditions(RSI_REPORT, conds)
    assert any("exactly one member" in f.message for f in errs)


def test_condition_ref_must_resolve():
    good = [condition("BASE", "a", num("RSI14_now", "gt", 30)),
            condition("DERIVED", "b", all_of(ref("BASE"), is_("RSI14_trend", "rising")))]
    assert not [f for f in validate_conditions(RSI_REPORT, good) if f.severity == "error"]

    bad = [condition("DERIVED", "b", ref("MISSING"))]
    assert any("unknown condition" in f.message
               for f in validate_conditions(RSI_REPORT, bad))


def test_self_reference_is_rejected():
    conds = [condition("SELF", "a", ref("SELF"))]
    assert any("references itself" in f.message
               for f in validate_conditions(RSI_REPORT, conds))


def test_bad_condition_key_is_rejected():
    conds = [condition("lower_case", "x", num("RSI14_now", "gt", 1))]
    assert any("conditionKey" in f.path for f in validate_conditions(RSI_REPORT, conds))


def test_duplicate_keys_are_rejected():
    conds = [condition("DUPE", "a", num("RSI14_now", "gt", 1)),
             condition("DUPE", "b", num("RSI14_now", "lt", 9))]
    assert any("duplicate" in f.message for f in validate_conditions(RSI_REPORT, conds))


def test_between_bounds_are_checked():
    conds = [condition("RANGE", "a", between("RSI14_now", 70, 30))]
    assert any("not below" in f.message for f in validate_conditions(RSI_REPORT, conds))


def test_condition_budget_is_enforced():
    conds = [condition(f"C{i}", "x", num("RSI14_now", "gt", 1)) for i in range(20)]
    assert any("exceeds the budget" in f.message
               for f in validate_conditions(RSI_REPORT, conds))


# --- marketReadText -------------------------------------------------------
def test_market_read_tokens_must_resolve():
    conds = [condition("OK", "fine", num("RSI14_now", "gt", 30), verdict="UP")]
    good = validate_market_read("Read {OK} then {RSI14_now}.", conds, RSI_REPORT)
    assert not good
    bad = validate_market_read("Read {NOPE}.", conds, RSI_REPORT)
    assert any("neither a conditionKey nor a header" in f.message for f in bad)


def test_generated_market_read_text_resolves():
    conds = [condition("A", "first", num("RSI14_now", "gt", 30), verdict="UP"),
             condition("B", "second", num("RSI14_now", "lt", 70), verdict="DOWN")]
    text = market_read_text("Intro.", conds)
    assert "{A}" in text and "{B}" in text
    assert not validate_market_read(text, conds, RSI_REPORT)


# --- generated plans ------------------------------------------------------
@pytest.mark.parametrize("name", PRESET_IDS)
def test_preset_conditions_type_check(name):
    p = plan(PRESETS[name])
    errs = [f for f in p.condition_findings() if f.severity == "error"]
    assert not errs, [str(e) for e in errs]


@pytest.mark.parametrize("name", PRESET_IDS)
def test_preset_emits_two_directional_conditions(name):
    """Layered now: 7 conditions, of which exactly two carry a verdict."""
    p = plan(PRESETS[name])
    assert len(p.conditions) == 7
    assert {c["verdict"] for c in p.conditions if c["verdict"]} == {"UP", "DOWN"}


@pytest.mark.parametrize("name", PRESET_IDS)
def test_preset_custom_sections_are_referenceable(name):
    for section in plan(PRESETS[name]).report.sections:
        assert section.sectionKey and section.sectionKey.startswith("custom:")


def test_section_keys_are_deterministic():
    assert ([s.sectionKey for s in plan(PRESETS["mean-reversion"]).report.sections]
            == [s.sectionKey for s in plan(PRESETS["mean-reversion"]).report.sections])


def test_wire_includes_conditions_and_market_read():
    payload = plan(PRESETS["trend-continuation"]).wire()
    assert len(payload["conditions"]) == 7
    assert "{TC_UP}" in payload["marketReadText"]


# --- live-verified fixture ------------------------------------------------
def test_trend_continuation_conditions_match_the_live_render():
    """Recorded from preview_strategy_report; both conditions resolved with evidence."""
    p = plan(PRESETS["trend-continuation"])
    keys = [c["conditionKey"] for c in p.conditions]
    assert keys[-2:] == ["TC_UP", "TC_DOWN"]
    core = [c for c in p.conditions if c["conditionKey"] == "TC_CORE_UP"][0]
    headers = {cl["column"]["header"] for cl in core["definition"]["members"][0]["members"]}
    # every clause header appeared in the live conditionColumns for that report
    assert headers == {"MAalign", "MACD_trend", "OBV_trend"}


def test_token_estimate_is_labelled_approximate():
    text = plan(PRESETS["trend-continuation"]).cost().render()
    assert "+/-" in text and "authoritative" in text
    assert TOKENS_PER_HEADER == 27


# --- layered DAG synthesis (live-verified) --------------------------------
@pytest.mark.parametrize("name", PRESET_IDS)
def test_preset_builds_a_layered_dag(name):
    p = plan(PRESETS[name])
    keys = {c["conditionKey"] for c in p.conditions}
    pre = sorted(keys)[0].split("_")[0]
    assert {f"{pre}_RISK_ON", f"{pre}_CTX_UP", f"{pre}_CTX_DOWN",
            f"{pre}_CORE_UP", f"{pre}_CORE_DOWN", f"{pre}_UP", f"{pre}_DOWN"} == keys


@pytest.mark.parametrize("name", PRESET_IDS)
def test_only_the_top_level_conditions_carry_a_verdict(name):
    """Building blocks are verdict=None; only the composed pair decides a direction."""
    p = plan(PRESETS[name])
    verdicts = {c["conditionKey"]: c["verdict"] for c in p.conditions}
    pre = sorted(verdicts)[0].split("_")[0]
    assert {k for k, v in verdicts.items() if v} == {f"{pre}_UP", f"{pre}_DOWN"}
    assert verdicts[f"{pre}_UP"] == "UP" and verdicts[f"{pre}_DOWN"] == "DOWN"


@pytest.mark.parametrize("name", PRESET_IDS)
def test_top_level_conditions_are_built_from_condition_refs(name):
    p = plan(PRESETS[name])
    top = [c for c in p.conditions if c["verdict"] in ("UP", "DOWN")]
    for c in top:
        kinds = {m["kind"] for m in c["definition"]["members"]}
        assert kinds == {"conditionRef"}, f"{c['conditionKey']} should compose by reference"


def test_ambient_context_costs_no_columns():
    """Verified live: sectionColumns counted only the report's own columns."""
    p = plan(PRESETS["squeeze-breakout"])
    ambient = {"mktBreadth_all", "usdtUsdDev_market", "usdcUsdtDev_market",
               "fieldUpBias_session"}
    used = set()
    def walk(d):
        if d.get("kind") == "clause":
            used.add(d["column"]["header"])
        for m in d.get("members") or []:
            walk(m)
    for c in p.conditions:
        walk(c["definition"])
    assert used & ambient, "expected the generated plan to use free ambient context"
    report_metrics = {col.metric for s in p.report.sections for col in s.columns}
    assert "mktBreadth_all" not in report_metrics    # no column pays for it


def test_fade_and_align_select_opposite_readings():
    """A reversion thesis must not buy strength, and a breakout must not buy the low band."""
    def core_up(name):
        p = plan(PRESETS[name])
        pre = p.conditions[0]["conditionKey"].split("_")[0]
        c = [x for x in p.conditions if x["conditionKey"] == f"{pre}_CORE_UP"][0]
        node = c["definition"]["members"][0]
        members = node["members"] if node.get("op") == "N_OF" else c["definition"]["members"]
        return {(m["column"]["header"], m["op"], m.get("value")) for m in members}

    fade = core_up("mean-reversion")
    align = core_up("squeeze-breakout")
    assert ("pctB_now", "lt", 0.05) in fade      # buy the lower band
    assert ("pctB_now", "gt", 0.95) in align     # buy the breakout
    assert ("RSI14_now", "lt", 35) in fade       # oversold, not "above midline"


def test_stance_is_recorded_on_every_preset():
    for name in PRESET_IDS:
        assert PRESETS[name].stance in ("ALIGN", "FADE")


def test_market_read_references_only_verdict_conditions():
    p = plan(PRESETS["mean-reversion"])
    for c in p.conditions:
        token = "{" + c["conditionKey"] + "}"
        if c["verdict"]:
            assert token in p.market_read_text
        else:
            assert token not in p.market_read_text


# --- the declared vocabulary is not always the real one ----------------------
# Measured 2026-08-24. ADX_zone and MFI14_zone declare
# ["overbought","oversold","neutral"] and emit none of them. Worse, the platform
# REFUSES the labels they do emit (CONDITION_LITERAL_UNSUPPORTED). So no label
# works: every legal one is FALSE forever, every useful one is rejected. omega
# refuses the clause and names the numeric replacement instead.

def _zone_report(metric):
    from omega.types import Column, CustomSection, RelTimeframe, Report
    col = Column(metric=metric, transformId="classifyZone",
                 timeframe=RelTimeframe(rel="anchor"))
    return Report(anchor="1h", sections=[CustomSection(
        kind="custom", title="z", benchmarkTicker=None, columns=[col])])


def _findings(report, defn):
    from omega.conditions import condition, validate_conditions
    return validate_conditions(report, [condition("TEST_ZONE", "t", defn)])


def test_a_disjoint_zone_header_cannot_carry_a_condition_at_all():
    """Not a warning - there is no working label, so the clause is refused."""
    from omega.conditions import is_
    f = _findings(_zone_report("ADX"), is_("ADX_zone", "neutral"))
    assert [x for x in f if x.severity == "error"], "must refuse, not warn"


def test_the_refusal_names_the_numeric_replacement():
    """A refusal that does not say what to do instead is half a finding."""
    from omega.conditions import is_
    msg = _findings(_zone_report("MFI14"), is_("MFI14_zone", "neutral"))[0].message
    assert "MFI14 lt 50" in msg and "trap 13" in msg


def test_the_observed_labels_are_still_rejected_because_the_platform_rejects_them():
    """omega must not emit a payload the platform refuses."""
    from omega.conditions import in_
    f = _findings(_zone_report("ADX"), in_("ADX_zone", ["trending", "developing"]))
    assert [x for x in f if x.severity == "error"]


def test_a_consistent_zone_header_draws_nothing():
    """RSI14_zone declares and emits the same labels - it must stay clean."""
    from omega.conditions import is_
    assert not _findings(_zone_report("RSI14"), is_("RSI14_zone", "neutral"))


def test_the_measured_vocabulary_is_never_treated_as_exhaustive():
    from omega.conditions import observed_vocabulary
    for header, m in observed_vocabulary().items():
        assert m["complete"] is False, (
            f"{header}: one capture cannot enumerate a label set")


def test_every_disjoint_header_carries_a_numeric_replacement():
    """The refusal path depends on this key existing."""
    from omega.conditions import observed_vocabulary
    for header, m in observed_vocabulary().items():
        if m.get("observedInDeclared") == 0:
            assert m.get("numericReplacement"), f"{header} refuses with no way out"
