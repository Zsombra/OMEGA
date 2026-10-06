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


# --- contract 91.0.0: six keys, a hold on every node, exit rules (v84 / v88) ----------
# Capture: data/contract/stage_strategy_draft/schema_20261005T194629Z.json, the CONDITIONS
# axis (required [conditionKey, name, definition, verdict, required, exitSide]; every
# clause and group requires hold {atLeast, of}, integers >= 1; the ref arm is
# additionalProperties:false over kind and conditionKey). Rules quoted from the README
# "Contract history" for v84 and v88.

from omega import preflight as P                       # noqa: E402
from omega.conditions import (                          # noqa: E402
    close_on, exit_rule, held, stables_at_par,
)
from omega.contract import stage_schema                 # noqa: E402

ONE = {"atLeast": 1, "of": 1}


def _conditions_axis():
    root = stage_schema()["stage_strategy_draft"]["inputSchema"]
    axis = root["properties"]["request"]["properties"]["axes"]["properties"]["CONDITIONS"]
    return axis, root


def test_condition_emits_exactly_the_six_v91_keys_in_schema_order():
    c = condition("CHK", "n", num("mktBreadth_all", "gt", 10))
    assert list(c) == ["conditionKey", "name", "definition", "verdict", "required", "exitSide"]
    assert c["exitSide"] is None
    axis, _ = _conditions_axis()
    assert axis["properties"]["conditions"]["items"]["required"] == list(c)


@pytest.mark.parametrize("retired", [{"clock": "LIVE"}, {"closes": 1}, {"exit": False}])
def test_condition_refuses_the_retired_keywords(retired):
    with pytest.raises(TypeError):
        condition("CHK", "n", num("mktBreadth_all", "gt", 10), **retired)


@pytest.mark.parametrize("key,why", [("clock", "61.0.0"), ("closes", "84.0.0"), ("exit", "88.0.0")])
def test_a_hand_built_condition_with_a_retired_key_is_an_error_naming_the_contract(key, why):
    bare = dict(condition("CHK", "n", num("mktBreadth_all", "gt", 10)), **{key: 1})
    [f] = [f for f in validate_conditions(RSI_REPORT, [bare]) if f.path == f".{key}"]
    assert f.severity == "error" and why in f.message


def test_an_undeclared_condition_key_is_an_error():
    bare = dict(condition("CHK", "n", num("mktBreadth_all", "gt", 10)), extra=True)
    assert any(f.path == ".extra" and f.severity == "error"
               for f in validate_conditions(RSI_REPORT, [bare]))


def test_every_clause_and_group_builder_emits_a_one_read_hold_by_default():
    d = all_of(num("RSI14_now", "gt", 50), between("RSI14_now", 1, 2), is_("RSI14_trend", "rising"),
               in_("RSI14_zone", ["neutral"]), not_(num("RSI14_now", "gt", 90)),
               any_of(num("RSI14_now", "lt", 5)), n_of(1, num("RSI14_now", "lt", 5)))
    assert d["hold"] == ONE
    assert all(m["hold"] == ONE for m in d["members"])
    assert list(d) == ["kind", "op", "hold", "members"]
    assert list(num("RSI14_now", "gt", 50)) == ["kind", "column", "op", "value", "hold"]


def test_a_condition_ref_carries_no_hold():
    assert ref("CORE") == {"kind": "conditionRef", "conditionKey": "CORE"}


def test_held_is_n_closes_in_a_row():
    assert held(3) == (3, 3)
    assert num("RSI14_now", "gt", 50, hold=held(3))["hold"] == {"atLeast": 3, "of": 3}
    assert num("RSI14_now", "gt", 50, hold=(1, 4))["hold"] == {"atLeast": 1, "of": 4}


@pytest.mark.parametrize("bad", [(0, 1), (1, 0), (3, 2), (1.5, 2), (True, 1), (1,), "11"])
def test_a_hold_outside_the_schema_or_above_its_window_is_refused_by_the_builders(bad):
    with pytest.raises(ValueError):
        num("RSI14_now", "gt", 50, hold=bad)


def test_there_is_no_fixed_hold_ceiling():
    """v84: "there is no longer a fixed 1-5 limit" - a column's own conditionHold decides."""
    cond = condition("CHK", "n", num("RSI14_now", "gt", 50, hold=held(12)))
    assert not [f for f in validate_conditions(RSI_REPORT, [cond]) if f.severity == "error"]


def test_the_condition_hold_goes_on_the_root_node_and_nowhere_else():
    cond = condition("CHK", "n", all_of(num("RSI14_now", "gt", 50), is_("RSI14_trend", "rising")),
                     hold=held(3))
    assert cond["definition"]["hold"] == {"atLeast": 3, "of": 3}
    assert all(m["hold"] == ONE for m in cond["definition"]["members"])
    assert list(cond["definition"]) == ["kind", "op", "hold", "members"]


def test_a_condition_hold_over_a_root_ref_or_over_held_members_is_refused():
    with pytest.raises(ValueError):
        condition("CHK", "n", ref("CORE"), hold=held(2))
    with pytest.raises(ValueError):
        condition("CHK", "n", all_of(num("RSI14_now", "gt", 50, hold=held(2))), hold=held(3))


def test_a_missing_or_malformed_hold_is_an_error_at_the_node():
    clause = num("RSI14_now", "gt", 50)
    del clause["hold"]
    grp = all_of(num("RSI14_now", "gt", 50))
    grp["hold"] = {"atLeast": 2, "of": 1}
    conds = [condition("AA", "n", clause), condition("BB", "n", grp)]
    errs = {(f.condition_key, f.path) for f in validate_conditions(RSI_REPORT, conds)
            if f.severity == "error"}
    assert ("AA", ".definition.hold") in errs and ("BB", ".definition.hold") in errs


def test_a_hold_on_a_condition_ref_is_an_error():
    core = condition("CORE", "n", num("RSI14_now", "gt", 50))
    bad = condition("TOP", "n", all_of(dict(ref("CORE"), hold=ONE)))
    assert any(f.condition_key == "TOP" and f.path.endswith(".members[0].hold")
               for f in validate_conditions(RSI_REPORT, [core, bad]) if f.severity == "error")


def test_a_group_hold_over_members_that_hold_their_own_bars_is_an_error():
    grp = all_of(num("RSI14_now", "gt", 50, hold=held(2)), is_("RSI14_trend", "rising"), hold=held(3))
    errs = [f for f in validate_conditions(RSI_REPORT, [condition("CHK", "n", grp)])
            if f.severity == "error"]
    assert [f.path for f in errs] == [".definition.members[0].hold"]
    # the same members under a one-read group are legal
    ok = all_of(num("RSI14_now", "gt", 50, hold=held(2)), is_("RSI14_trend", "rising"))
    assert not [f for f in validate_conditions(RSI_REPORT, [condition("CHK", "n", ok)])
                if f.severity == "error"]


def test_a_hold_over_a_custom_candle_header_at_the_anchor_draws_nothing():
    cond = condition("CHK", "n", num("RSI14_now", "gt", 50), hold=held(3))
    assert not validate_conditions(RSI_REPORT, [cond])


@pytest.mark.parametrize("spec,header_prefix", [
    ({"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "anchor"}, "offset": 4}, "RSI14"),
    ({"metric": "FUNDING_RATE", "transformId": "value", "timeframe": {"rel": "anchor"}}, "rate"),
    ({"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "lower"}}, "RSI14"),
])
def test_the_61_hold_operand_rule_is_now_a_warning_never_an_error(spec, header_prefix):
    """Plan 2026-10-06: the 61.2.0 readability flag "is kept as a warning for a hold above 1
    on a column it marked unreadable, never as an error" - since v84 the column's
    conditionHold decides and no v84+ vocabulary read is on disk."""
    rep = _report(spec)
    [header] = [h for h in report_headers(rep) if h.startswith(header_prefix)]
    cond = condition("CHK", "n", num(header, "gt", 0), hold=held(2))
    findings = [f for f in validate_conditions(rep, [cond]) if "CONDITION_HOLD_OPERAND_ILLEGAL" in f.message]
    assert findings and all(f.severity == "warning" for f in findings)


def test_a_group_hold_reaches_its_one_read_clauses():
    """A clause at {1,1} under a group holding 2 is still read over 2 bars."""
    cond = condition("CHK", "n", all_of(stables_at_par()), hold=held(2))
    warns = [f for f in validate_conditions(RSI_REPORT, [cond]) if f.severity == "warning"]
    assert len([f for f in warns if "CONDITION_HOLD_OPERAND_ILLEGAL" in f.message]) == 2


def test_a_group_hold_over_references_alone_warns():
    core = condition("CORE", "n", num("RSI14_now", "gt", 50))
    held_refs = condition("HELD", "n", all_of(ref("CORE")), hold=held(2))
    findings = validate_conditions(RSI_REPORT, [core, held_refs])
    assert not [f for f in findings if f.severity == "error"]
    assert any("CONDITION_HOLD_ILLEGAL" in f.message and f.condition_key == "HELD" for f in findings)


# exitSide (v88)

def test_a_condition_without_exit_side_is_an_error():
    bare = condition("CHK", "n", num("mktBreadth_all", "gt", 10))
    del bare["exitSide"]
    assert ".exitSide" in {f.path for f in validate_conditions(RSI_REPORT, [bare]) if f.severity == "error"}
    bad = dict(bare, exitSide="UP")
    assert ".exitSide" in {f.path for f in validate_conditions(RSI_REPORT, [bad]) if f.severity == "error"}


@pytest.mark.parametrize("side", ["UP", "long", "", False])
def test_condition_refuses_an_exit_side_outside_the_enum(side):
    with pytest.raises(ValueError):
        condition("CHK", "n", num("RSI14_now", "gt", 50), exit_side=side)


def test_exit_rule_is_verdict_null_required_false_and_names_its_side():
    r = exit_rule("XR", "n", num("RSI14_now", "gt", 70), "LONG")
    assert (r["verdict"], r["required"], r["exitSide"]) == (None, False, "LONG")
    with pytest.raises(ValueError):
        exit_rule("XR", "n", num("RSI14_now", "gt", 70), None)


@pytest.mark.parametrize("verdict,side", [("UP", "SHORT"), ("DOWN", "LONG"), ("NEITHER", "BOTH"), (None, "BOTH")])
def test_close_on_is_the_v88_split(verdict, side):
    entry = condition("SETUP", "Setup", num("RSI14_now", "gt", 50), verdict=verdict)
    rule = close_on(entry)
    assert rule == {"conditionKey": "CLOSE_ON_SETUP", "name": "Close on SETUP",
                    "definition": {"kind": "conditionRef", "conditionKey": "SETUP"},
                    "verdict": None, "required": False, "exitSide": side}
    assert entry["exitSide"] is None and entry["verdict"] == verdict      # the entry keeps its verdict
    assert not [f for f in validate_conditions(RSI_REPORT, [entry, rule]) if f.severity == "error"]


def test_close_on_refuses_a_key_too_long_for_the_prefix_rather_than_truncating():
    ok = condition("K" + "X" * 30, "n", num("RSI14_now", "gt", 50))        # 31 chars -> 40
    assert close_on(ok)["conditionKey"] == "CLOSE_ON_" + ok["conditionKey"]
    too_long = condition("K" + "X" * 31, "n", num("RSI14_now", "gt", 50))  # 32 chars -> 41
    with pytest.raises(ValueError, match="too long"):
        close_on(too_long)


def test_close_on_refuses_to_split_an_exit_rule():
    with pytest.raises(ValueError):
        close_on(exit_rule("XR", "n", num("RSI14_now", "gt", 70), "BOTH"))


def test_an_exit_rule_carrying_a_verdict_or_required_is_refused_with_the_typed_codes():
    rule = dict(exit_rule("XR", "n", num("RSI14_now", "gt", 70), "SHORT"), verdict="UP", required=True)
    msgs = " ".join(f.message for f in validate_conditions(RSI_REPORT, [rule]) if f.severity == "error")
    assert "CONDITION_EXIT_RULE_CARRIES_VERDICT" in msgs and "CONDITION_EXIT_RULE_REQUIRED" in msgs


def test_an_entry_condition_cannot_reference_an_exit_rule_but_an_exit_rule_may_reference_anything():
    rule = exit_rule("XR", "n", num("RSI14_now", "gt", 70), "LONG")
    entry = condition("EN", "n", all_of(ref("XR"), num("RSI14_now", "gt", 50)), verdict="UP")
    errs = [f for f in validate_conditions(RSI_REPORT, [rule, entry]) if f.severity == "error"]
    assert [f.condition_key for f in errs if "CONDITION_ENTRY_REFERENCES_EXIT_RULE" in f.message] == ["EN"]
    # "exit when the entry setup stops holding is an exit rule whose definition is NOT a
    # conditionRef to the entry condition" (v88)
    setup = condition("SETUP", "n", num("RSI14_now", "gt", 50), verdict="UP")
    stop = exit_rule("STOP", "n", not_(ref("SETUP")), "LONG")
    assert not [f for f in validate_conditions(RSI_REPORT, [setup, stop]) if f.severity == "error"]


def test_an_exit_rule_needs_operands_a_completed_bar_moves():
    # keys are two characters: ^[A-Z][A-Z0-9_]{1,39}$ refuses a one-character key, and
    # that unrelated finding would mask the clean read below
    inert = exit_rule("XX", "n", num("mktBreadth_all", "gt", 10), "BOTH")
    errs = [f for f in validate_conditions(RSI_REPORT, [inert]) if f.severity == "error"]
    assert any("CONDITION_EXIT_READ_ILLEGAL" in f.message for f in errs)
    moved = exit_rule("YY", "n", num("RSI14_now", "gt", 50), "BOTH")
    assert not [f for f in validate_conditions(RSI_REPORT, [moved]) if f.severity == "error"]


def test_a_close_on_rule_reads_its_source_closure():
    """CLOSE_ON_<key> is a conditionRef, so the exit read rule follows the reference: an
    entry condition over an ambient header cannot be split into a legal exit rule."""
    entry = condition("TAPE", "n", num("mktBreadth_all", "gt", 10), verdict="UP")
    findings = validate_conditions(RSI_REPORT, [entry, close_on(entry)])
    assert any(f.condition_key == "CLOSE_ON_TAPE" and "CONDITION_EXIT_READ_ILLEGAL" in f.message
               for f in findings if f.severity == "error")


def test_an_exit_rule_admits_an_offset_column():
    """"At offset 0" belongs to the HOLD sentence, not to the exit sentence (vendor pack
    31.2.28 § Conditions): a completed bar moves an offset column too, one bar later."""
    rep = _report({"metric": "RSI14", "transformId": "value",
                   "timeframe": {"rel": "anchor"}, "offset": 4})
    [header] = [h for h in report_headers(rep) if h.startswith("RSI14")]
    exiting = exit_rule("XT", "n", num(header, "gt", 50), "BOTH")
    assert not [f for f in validate_conditions(rep, [exiting]) if f.severity == "error"]


def test_a_verdict_carrier_may_not_read_a_developing_higher_timeframe_bar_even_through_a_reference():
    rep = _report({"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "regime"}, "bars": "all"})
    [header] = [h for h in report_headers(rep) if h.startswith("RSI14")]
    block = condition("BLOCK", "n", num(header, "gt", 50))                       # verdict None: legal
    carrier = condition("TOP", "n", ref("BLOCK"), verdict="UP")
    findings = validate_conditions(rep, [block, carrier])
    assert not [f for f in findings if f.condition_key == "BLOCK" and f.severity == "error"]
    assert any("CONDITION_VERDICT_READ_ILLEGAL" in f.message and f.condition_key == "TOP" for f in findings)


def test_a_confirmed_higher_timeframe_read_admits_a_verdict():
    rep = _report({"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "regime"}, "bars": "closed"})
    [header] = [h for h in report_headers(rep) if h.startswith("RSI14")]
    carrier = condition("TOP", "n", num(header, "gt", 50), verdict="UP")
    assert not [f for f in validate_conditions(rep, [carrier]) if f.severity == "error"]


@pytest.mark.parametrize("abs_tf,above,below", [
    ("4h", True, False),      # above the 1h anchor
    ("1h", False, False),     # AT the anchor: neither - "at or above" admits it
    ("15m", False, True),     # below
    ("1d", True, False),      # above
])
def test_an_absolute_column_timeframe_is_placed_by_index_against_the_anchor(abs_tf, above, below):
    """The {"abs": tf} branch of _anchor_side, ordered by absoluteTimeframes.

    A column's timeframe is {"rel": ...} or {"abs": <tf>}; the absolute values are ordered
    in data/contract/vocabulary/_shared.json. Reported through report_headers because that
    is the only surface the read rules consume. bars="all" makes `developing` the mirror of
    `above_anchor` (developing = above_anchor and bars == "all").
    """
    rep = _report({"metric": "RSI14", "transformId": "value",
                   "timeframe": {"abs": abs_tf}, "bars": "all"})
    headers = report_headers(rep)
    [header] = [h for h in headers if h.startswith("RSI14")]
    assert headers[header]["above_anchor"] == above
    assert headers[header]["below_anchor"] == below
    assert headers[header]["developing"] == above


@pytest.mark.parametrize("name", PRESET_IDS)
def test_preset_conditions_walk_clean_against_the_v91_conditions_axis(name):
    """The schema half of the gate: zero FAIL and zero UNSUPPORTED walking each preset's
    conditions through the saved 91.0.0 CONDITIONS axis (patterns are INFO, never checked)."""
    axis, root = _conditions_axis()
    findings = P.diff_schema({"conditions": plan(PRESETS[name]).conditions}, axis, root)
    assert [(f.cls, f.path) for f in findings if f.verdict == "FAIL"] == []
    assert [f for f in findings if f.cls == "UNSUPPORTED"] == []


@pytest.mark.parametrize("name", PRESET_IDS)
def test_presets_hold_one_read_everywhere_and_are_all_entry_conditions(name):
    """Every pre-v84 preset condition held `closes: 1`, which v84 maps to {1,1} on every
    node; no preset declares an exit, so every condition is exitSide null."""
    def holds(d):
        if d.get("kind") in ("clause", "group"):
            yield d["hold"]
        for m in d.get("members") or []:
            yield from holds(m)
    for c in plan(PRESETS[name]).conditions:
        assert c["exitSide"] is None, c["conditionKey"]
        assert all(h == ONE for h in holds(c["definition"])), c["conditionKey"]

