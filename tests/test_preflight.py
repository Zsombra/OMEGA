"""Schema-drift preflight (design 2026-09-04). Pure functions; the fixtures are a
hand-built walker miniature and the REAL records named in the plan. The miniature is a
walker fixture only - never a regression oracle for wire()."""
from __future__ import annotations

import ast
import copy
import inspect
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from omega import preflight as P

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "preflight"
MINI = json.loads((FIX / "schema_walker_min.json").read_text(encoding="utf-8"))

RESEARCH = ROOT / "data" / "research" / "2026-08-29-deep-tail-fade"
V4 = json.loads((RESEARCH / "compile_body_deep_tail_fade_v4.json").read_text(encoding="utf-8"))
V5 = json.loads((RESEARCH / "compile_body_deep_tail_fade_v5.json").read_text(encoding="utf-8"))
PRESTATE = json.loads((ROOT / "data/audit/first_generated_update_2026-08-29.json").read_text(encoding="utf-8"))["probes"]["preState"]["strategy"]
DRIFT5 = json.loads((ROOT / "data/audit/drift5_exit_rediscovery_2026-09-04.json").read_text(encoding="utf-8"))


def test_module_imports_no_network_client():
    """The house rule (omega/probe.py:3), enforced against the import graph."""
    tree = ast.parse(inspect.getsource(P))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"requests", "httpx", "urllib", "aiohttp", "socket", "http"}


def test_finding_is_frozen_and_has_the_four_fields():
    f = P.Finding("ENUM", "entry.trigger", "x", "FAIL")
    assert (f.cls, f.path, f.detail, f.verdict) == ("ENUM", "entry.trigger", "x", "FAIL")
    with pytest.raises(Exception):
        f.cls = "INFO"  # type: ignore[misc]


def test_resolve_arms_selects_by_operation_const_and_returns_root():
    arms, root = P.resolve_arms(MINI)
    assert set(arms) == {"CREATE", "UPDATE"}
    assert arms["CREATE"]["properties"]["operation"]["const"] == "CREATE"
    assert root is MINI["parameters"]


def test_deref_follows_local_refs_relative_to_parameters():
    arms, root = P.resolve_arms(MINI)
    tf = P.deref(arms["UPDATE"]["properties"]["timeframe"], root)
    assert tf["enum"] == ["1h", "4h"]
    # a ref inside a ref target
    entry = P.deref(arms["UPDATE"]["properties"]["entry"], root)
    assert P.deref(entry["properties"]["confirmTf"], root)["enum"] == ["1h", "4h"]


def test_deref_refuses_non_local_refs():
    with pytest.raises(P.UnsupportedSchema):
        P.deref({"$ref": "https://example.invalid/schema#/x"}, MINI["parameters"])


def _create_arm():
    arms, root = P.resolve_arms(MINI)
    return arms["CREATE"], root


def _good_body():
    return {
        "operation": "CREATE", "name": "walker", "timeframe": "1h",
        "sections": [{"kind": "platform", "sectionKey": "includeRsi"},
                     {"kind": "custom", "title": "t", "benchmarkTicker": None, "notes": "n",
                      "columns": [{"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "anchor"}, "window": 4}]}],
        "conditions": [{"conditionKey": "A_ONE", "name": "n", "definition": {"kind": "clause"},
                        "verdict": None, "required": False, "exit": False, "clock": "LIVE", "closes": 1}],
        "rules": [{"signalId": "rsi_oversold", "allocation": 2, "required": False, "params": {}}],
        "entry": {"trigger": "AT_SIGNAL", "confirmTf": "1h", "closes": 1, "bandAtrMultiple": 1,
                  "levelSource": "SWING_HIGH", "levelOffsetAtrMultiple": 0, "validForBars": 4},
    }


def _fails(findings):
    return [(f.cls, f.path) for f in findings if f.verdict == "FAIL"]


def test_walker_passes_a_conforming_body():
    arm, root = _create_arm()
    assert _fails(P.diff_schema(_good_body(), arm, root)) == []


def test_walker_flags_missing_required_at_nested_paths():
    arm, root = _create_arm()
    body = _good_body()
    del body["conditions"][0]["exit"]           # drift #5's exact shape
    del body["entry"]["validForBars"]           # drift #4's exact shape
    fails = _fails(P.diff_schema(body, arm, root))
    assert ("MISSING_REQUIRED", "conditions[0].exit") in fails
    assert ("MISSING_REQUIRED", "entry.validForBars") in fails


def test_walker_flags_undeclared_keys_and_says_it_is_schema_derived():
    arm, root = _create_arm()
    body = _good_body(); body["plan"] = {}      # the 2026-08-24 write-path key
    [f] = [f for f in P.diff_schema(body, arm, root) if f.cls == "UNDECLARED"]
    assert f.path == "plan" and "not measured" in f.detail


def test_walker_flags_enum_const_and_bounds():
    arm, root = _create_arm()
    body = _good_body()
    body["entry"]["trigger"] = "ON_RETEST"      # not in the miniature's enum
    body["entry"]["validForBars"] = 25          # > maximum 24
    body["entry"]["bandAtrMultiple"] = 0        # exclusiveMinimum 0
    body["sections"][1]["columns"][0]["window"] = 0
    body["name"] = ""                           # minLength 1
    fails = _fails(P.diff_schema(body, arm, root))
    assert ("ENUM", "entry.trigger") in fails
    assert ("BOUNDS", "entry.validForBars") in fails
    assert ("BOUNDS", "entry.bandAtrMultiple") in fails
    assert ("BOUNDS", "sections[1].columns[0].window") in fails
    assert ("BOUNDS", "name") in fails


def test_walker_type_mismatch_is_a_bounds_finding():
    arm, root = _create_arm()
    body = _good_body(); body["conditions"][0]["closes"] = "1"
    assert ("BOUNDS", "conditions[0].closes") in _fails(P.diff_schema(body, arm, root))


def test_walker_anyof_by_kind_const_and_by_type():
    arm, root = _create_arm()
    body = _good_body()
    body["sections"][1]["notes"] = None         # null branch of notes
    body["sections"][1]["columns"][0]["timeframe"] = {"abs": "4h"}   # second branch, via $ref
    assert _fails(P.diff_schema(body, arm, root)) == []
    body["sections"][1]["columns"][0]["timeframe"] = {"abs": "1d"}   # not in the ref'd enum
    assert ("ENUM", "sections[1].columns[0].timeframe.abs") in _fails(P.diff_schema(body, arm, root))


def test_walker_reports_unmatched_anyof_as_unsupported_not_silence():
    """RULING: an unmatched anyOf branch leaves the subtree unvalidated, so it is FAIL, not
    WARN - unlike the WARN-and-keep-walking UNSUPPORTED cases (unknown keyword, list type,
    tuple items, unknown type name), where the walk continues over the rest of the value."""
    arm, root = _create_arm()
    body = _good_body(); body["sections"].append({"kind": "mystery"})
    [f] = [f for f in P.diff_schema(body, arm, root) if f.cls == "UNSUPPORTED"]
    assert f.path == "sections[2]" and f.verdict == "FAIL"


def test_walker_checks_unknown_keywords_inside_the_selected_anyof_branch_and_keeps_walking():
    """The unmodelled-keyword check must run again on the BRANCH `_pick_branch` selects,
    not only on the anyOf-holder schema before selection - otherwise a keyword the walker
    does not model (allOf, dependentRequired, ...) placed inside one arm of an anyOf is
    never examined. Verified: allOf inside the custom-section branch used to produce zero
    findings for it while the branch's own required-field check still ran (proving the
    keyword itself was skipped, not the branch)."""
    mini = copy.deepcopy(MINI)
    custom_branch = mini["parameters"]["properties"]["request"]["anyOf"][0]["properties"]["sections"]["items"]["anyOf"][1]
    custom_branch["allOf"] = []          # a construct outside the modelled subset, scoped to this branch only
    arms, root = P.resolve_arms(mini)
    body = _good_body()
    del body["sections"][1]["title"]     # required inside the same branch - proves walking continues
    findings = P.diff_schema(body, arms["CREATE"], root)
    unsupported = [f for f in findings if f.cls == "UNSUPPORTED" and f.path == "sections[1]"]
    assert unsupported and unsupported[0].verdict == "WARN" and "allOf" in unsupported[0].detail
    assert ("MISSING_REQUIRED", "sections[1].title") in _fails(findings)


def test_pick_branch_ignores_a_branch_with_an_unknown_type_name():
    """`_pick_branch`'s type-only matching used `_type_ok(b["type"], value)` with no
    `_KNOWN_TYPES` guard, so an unknown type name (a typo, or a JSON Schema draft keyword
    the walker does not model) matched every value and could steal the match from a real
    candidate later in the list. `_walk` already guards this for the top-level `type`
    keyword; `_pick_branch` must guard it too."""
    root: dict = {}
    branches = [{"type": "frobnicate"}, {"type": "number"}]
    assert P._pick_branch(5, branches, root) == branches[1]


def test_walker_reports_pattern_unchecked_once_per_path_as_info():
    arm, root = _create_arm()
    infos = [f for f in P.diff_schema(_good_body(), arm, root) if f.cls == "INFO"]
    assert any(f.path == "conditions[0].conditionKey" and "pattern" in f.detail for f in infos)


def test_walker_reports_unknown_keywords_as_unsupported_and_keeps_walking():
    mini = copy.deepcopy(MINI)
    create_props = mini["parameters"]["properties"]["request"]["anyOf"][0]["properties"]
    create_props["entry"]["allOf"] = []          # a construct outside the modelled subset
    arms, root = P.resolve_arms(mini)
    body = _good_body()
    del body["entry"]["validForBars"]            # drift #4's exact shape - walking must continue
    findings = P.diff_schema(body, arms["CREATE"], root)
    unsupported = [f for f in findings if f.cls == "UNSUPPORTED"]
    assert any(f.path == "entry" and "allOf" in f.detail and f.verdict == "WARN" for f in unsupported)
    assert ("MISSING_REQUIRED", "entry.validForBars") in _fails(findings)


def test_walker_reports_list_type_and_tuple_items_as_unsupported_not_crash():
    mini = copy.deepcopy(MINI)
    create_props = mini["parameters"]["properties"]["request"]["anyOf"][0]["properties"]
    create_props["name"]["type"] = ["string", "null"]          # type as a list
    create_props["conditions"]["items"] = [{"type": "string"}]  # tuple-form items
    arms, root = P.resolve_arms(mini)
    body = _good_body()
    findings = P.diff_schema(body, arms["CREATE"], root)       # must not raise
    unsupported = {(f.path, f.verdict) for f in findings if f.cls == "UNSUPPORTED"}
    assert ("name", "WARN") in unsupported
    assert ("conditions", "WARN") in unsupported
    assert not any(f.path.startswith("conditions[") for f in findings)


def _body(doc):
    return doc.get("request", doc)


def _migrated_record():
    """The 2026-08-29 genuine read-back, migrated the way drift #3/#4/#5 records read
    back on 2026-09-04 (drift5_exit_rediscovery_2026-09-04.json): every condition gains
    exit=false, clock=LIVE, closes=1 in the platform's key order; entry gains the seven
    mirrored fields, pulled from DRIFT5's OWN read-back of the sibling strategy
    (6a8bca67-45a3-428e-85ba-71ec2cd2218e's entry_verbatim) rather than from the v5 body -
    the two are verified equal by test_drift5_readback_entry_equals_the_mirrored_body_entry
    below, so the provenance is measured, not assumed; decisionInvalidationExitEnabled=true.
    BUILT from records, labelled as such - the first live run replaces it with a verbatim
    capture."""
    rec = json.loads(json.dumps(PRESTATE))
    rec["conditions"] = [
        {"conditionKey": c["conditionKey"], "name": c["name"], "definition": c["definition"],
         "verdict": c["verdict"], "required": c["required"], "exit": False, "clock": "LIVE", "closes": 1}
        for c in rec["conditions"]]
    rec["entry"] = dict(DRIFT5["readbacks"]["6a8bca67-45a3-428e-85ba-71ec2cd2218e"]["entry_verbatim"])
    rec["decisionInvalidationExitEnabled"] = True
    return rec


def test_drift5_readback_entry_equals_the_mirrored_body_entry():
    """Measures the provenance claim in _migrated_record's docstring: DRIFT5's own
    read-back of 6a8bca67's entry is the same seven values as v5's body entry, so building
    the fixture from the read-back (rather than from the body, which is what omega itself
    emits and would make the replay tests circular) changes nothing about what the tests
    assert."""
    assert DRIFT5["readbacks"]["6a8bca67-45a3-428e-85ba-71ec2cd2218e"]["entry_verbatim"] == _body(V5)["entry"]


def test_replay_drift4_three_entry_fields_missing_vs_record():
    arm, root = _create_arm()
    fails = _fails(P.diff_record(_body(V4), _migrated_record(), arm, root))
    assert {("MISSING_VS_RECORD", "entry.levelSource"), ("MISSING_VS_RECORD", "entry.levelOffsetAtrMultiple"),
            ("MISSING_VS_RECORD", "entry.validForBars")} <= set(fails)


def test_replay_drift5_exit_missing_on_every_condition_vs_record():
    arm, root = _create_arm()
    fails = _fails(P.diff_record(_body(V5), _migrated_record(), arm, root))
    assert ("MISSING_VS_RECORD", "conditions[*].exit") in fails
    [f] = [f for f in P.diff_record(_body(V5), _migrated_record(), arm, root) if f.path == "conditions[*].exit"]
    assert "7/7" in f.detail


def test_replay_drift3_clock_and_closes_missing_vs_record():
    """Drift #3 (2026-08-29/30): conditions[].clock and conditions[].closes required by the
    runtime validator before the schema declared them, caught by a record read-back that
    already carried the migrated values."""
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    for c in body["conditions"]:
        c["exit"] = False
        del c["clock"]
        del c["closes"]
    findings = P.diff_record(body, _migrated_record(), arm, root)
    fails = _fails(findings)
    assert ("MISSING_VS_RECORD", "conditions[*].clock") in fails
    assert ("MISSING_VS_RECORD", "conditions[*].closes") in fails
    [fc] = [f for f in findings if f.path == "conditions[*].clock"]
    assert "7/7" in fc.detail
    [fk] = [f for f in findings if f.path == "conditions[*].closes"]
    assert "7/7" in fk.detail


def test_record_diff_is_quiet_when_the_body_carries_everything_the_record_does():
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    for c in body["conditions"]:
        c["exit"] = False
    assert _fails(P.diff_record(body, _migrated_record(), arm, root)) == []


def test_record_diff_top_level_optional_and_server_keys_are_info_not_fail():
    """The 16 platform-defaulted execution parameters (measured 2026-08-27) and the
    optional decisionInvalidationExitEnabled are INFO; id/revision/createdAt are INFO."""
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    for c in body["conditions"]:
        c["exit"] = False
    finds = P.diff_record(body, _migrated_record(), arm, root)
    assert all(f.verdict != "FAIL" for f in finds)
    infos = {f.path for f in finds if f.verdict == "INFO"}
    assert {"minAtrPct", "decisionInvalidationExitEnabled", "id", "revision"} <= infos


def test_record_diff_uses_intersection_for_arrays_and_knows_the_two_deltas():
    """signalRules<->rules alias and the server-minted custom sectionKey never fire;
    a column key present on only SOME record columns never fires."""
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    for c in body["conditions"]:
        c["exit"] = False
    rec = _migrated_record()
    rec["sections"][0]["sectionKey"] = "custom:00000000-0000-4000-8000-000000000000"
    rec["sections"][0]["columns"][0]["window"] = 4      # only on one record column
    paths = {f.path for f in P.diff_record(body, rec, arm, root) if f.verdict == "FAIL"}
    assert not any(p.endswith("sectionKey") for p in paths)
    assert not any("columns" in p for p in paths)
    assert not any("signalRules" in p or p.startswith("rules") for p in paths)


def test_record_diff_column_recursion_keeps_the_array_marker_on_the_path():
    """`_missing_in_elements`'s recursion into columns must keep the "[]" array marker on
    the recursed path (sections[custom][].columns[*].window) - it had regressed to
    "sections[custom].columns[*].window", silently dropping the marker that denotes
    'one entry per section'. Built from a real record (PRESTATE, deep-copied) whose custom
    sections' columns all gain `window` here; the body (V5) genuinely lacks it on some
    columns of its own custom sections."""
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    for c in body["conditions"]:
        c["exit"] = False
    rec = json.loads(json.dumps(PRESTATE))
    for section in rec["sections"]:
        for col in section.get("columns", []):
            col["window"] = 4
    fails = [f for f in P.diff_record(body, rec, arm, root) if f.cls == "MISSING_VS_RECORD"]
    matches = [f for f in fails if "[].columns[*].window" in f.path]
    assert matches


def test_record_diff_platform_section_missing_sectionkey_is_not_suppressed_by_the_custom_delta():
    """RULING: KNOWN_DELTAS' one entry ("server-minted on CREATE, custom:<uuid>, never
    sent") is measured for CUSTOM sections only. Before this fix, `_missing_in_elements`
    computed the same delta key ("sections[].sectionKey") for the platform-kind comparison
    too, so a real platform-side sectionKey drift would have been silently swallowed by an
    allowlist entry whose measured reason does not apply to it. Platform sections must be
    compared under a distinct label so their own sectionKey delta (or any other) still
    fires."""
    arm, root = _create_arm()
    body = {"sections": [{"kind": "platform"}]}          # sectionKey omitted
    rec = {"sections": [{"kind": "platform", "sectionKey": "includeRsi"}]}
    fails = {(f.cls, f.path) for f in P.diff_record(body, rec, arm, root) if f.verdict == "FAIL"}
    assert ("MISSING_VS_RECORD", "sections[platform][*].sectionKey") in fails


def test_record_diff_top_level_object_the_body_lacks_is_a_warn():
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    del body["entry"]
    for c in body["conditions"]:
        c["exit"] = False
    [f] = [f for f in P.diff_record(body, _migrated_record(), arm, root) if f.path == "entry"]
    assert f.cls == "MISSING_VS_RECORD" and f.verdict == "WARN"


def test_record_diff_any_extra_top_level_object_the_body_lacks_is_a_warn():
    """The WARN branch used to be gated on name (`bk in NESTED_REQUEST_OBJECTS`, i.e.
    "entry" only), so a brand-new top-level object on the record - one the arm doesn't
    even declare - fell through to the server-derived INFO branch, an assertion the code
    cannot make about an object it has never seen. Any dict-valued record key the body
    omits entirely is a WARN, regardless of name."""
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    for c in body["conditions"]:
        c["exit"] = False
    rec = _migrated_record()
    rec["riskProfile"] = {"x": 1}
    [f] = [f for f in P.diff_record(body, rec, arm, root) if f.path == "riskProfile"]
    assert f.cls == "MISSING_VS_RECORD" and f.verdict == "WARN"


def test_record_diff_null_valued_record_key_is_info_not_fail():
    """The real 2026-08-29 record's custom sections carry timeframe: null (the platform's
    not-set default for the optional section-level override, omega/validate.py
    section_timeframe); the body never sends it. A null carries nothing to mirror: INFO,
    not FAIL - no drift instance to date was null-valued."""
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    for c in body["conditions"]:
        c["exit"] = False
    finds = P.diff_record(body, _migrated_record(), arm, root)
    infos = [f for f in finds if f.path == "sections[custom][*].timeframe"]
    assert infos and all(f.verdict == "INFO" for f in infos)
    assert not any(f.path == "sections[custom][*].timeframe" and f.verdict == "FAIL" for f in finds)


def test_record_request_view_unwraps_the_get_strategy_envelope():
    assert P.record_request_view({"strategy": {"id": "x"}}) == {"id": "x"}
    assert P.record_request_view({"id": "x"}) == {"id": "x"}


MIRROR_ENTRY = {"trigger": "AT_SIGNAL", "confirmTf": "1h", "closes": 1, "bandAtrMultiple": 1,
                "levelSource": "SWING_HIGH", "levelOffsetAtrMultiple": 0, "validForBars": 4}


def test_mirror_is_quiet_when_values_match_and_ignores_confirmTf():
    rec = _migrated_record()
    body = {"entry": dict(MIRROR_ENTRY, confirmTf="4h"),
            "conditions": [{"clock": "LIVE", "closes": 1, "exit": False}]}
    assert P.mirror_findings(body, rec) == []


def test_mirror_warns_never_fails_on_a_differing_mirror_value():
    rec = _migrated_record()
    body = {"entry": dict(MIRROR_ENTRY, validForBars=6),
            "conditions": [{"clock": "CLOSE", "closes": 1, "exit": False}]}
    finds = P.mirror_findings(body, rec)
    assert {(f.cls, f.path, f.verdict) for f in finds} == {
        ("MIRROR", "entry.validForBars", "WARN"), ("MIRROR", "conditions[0].clock", "WARN")}


def test_mirror_findings_handles_a_list_valued_body_condition_field_without_raising():
    """`c[k] not in seen` raises TypeError when `c[k]` is a list/dict (unhashable) -
    a body condition can legally carry a list-valued field. Must compare by value, not by
    set membership, and still report the mismatch."""
    rec = _migrated_record()
    body = {"entry": dict(MIRROR_ENTRY), "conditions": [{"clock": "LIVE", "closes": [1, 2], "exit": False}]}
    finds = P.mirror_findings(body, rec)          # must not raise
    assert ("MIRROR", "conditions[0].closes", "WARN") in {(f.cls, f.path, f.verdict) for f in finds}


def test_schema_index_and_changelog_see_enum_growth_and_new_optional_keys():
    arm, root = _create_arm()
    cur = json.loads(json.dumps(MINI))
    cur_arms, cur_root = P.resolve_arms(cur)
    cur_arm = cur_arms["CREATE"]
    cur_arm["properties"]["entry"]["properties"]["trigger"]["enum"] += ["STOP_THROUGH_LEVEL", "ON_RETEST"]
    cur_arm["properties"]["newOptional"] = {"type": "boolean"}
    cur_arm["properties"]["entry"]["properties"]["validForBars"]["maximum"] = 48
    prev_idx, cur_idx = P.schema_index(arm, root), P.schema_index(cur_arm, cur_root)
    log = P.changelog(prev_idx, cur_idx)
    assert all(f.cls == "CHANGELOG" and f.verdict == "INFO" for f in log)
    details = " | ".join(f"{f.path}: {f.detail}" for f in log)
    assert "entry.trigger" in details and "STOP_THROUGH_LEVEL" in details
    assert "newOptional" in details
    assert "validForBars" in details and "48" in details


def test_schema_index_terminates_on_a_recursive_definition():
    arm, root = _create_arm()
    arm = json.loads(json.dumps(arm))
    arm["properties"]["conditions"]["items"]["properties"]["definition"] = {
        "anyOf": [{"type": "object", "properties": {"members": {"type": "array", "items": {
            "$ref": "#/properties/request/anyOf/0/properties/conditions/items/properties/definition"}}}}]}
    root2 = json.loads(json.dumps(root)); root2["properties"]["request"]["anyOf"][0] = arm
    idx = P.schema_index(arm, root2)
    assert "conditions[].definition" in idx


def test_fingerprint_schema_flags_a_truncated_enum_as_transcription_suspect():
    arm, root = _create_arm()
    ok = P.fingerprint_schema(arm, root, signal_ids={"rsi_oversold", "rsi_overbought"},
                              template_keys={"includeRsi", "includeMacd"}, timeframes=["1h", "4h"])
    assert ok == []
    bad = P.fingerprint_schema(arm, root, signal_ids={"rsi_oversold", "rsi_overbought", "macd_bull_cross"},
                               template_keys={"includeRsi", "includeMacd"}, timeframes=["1h", "4h"])
    assert [f.cls for f in bad] == ["TRANSCRIPTION_SUSPECT"] and bad[0].verdict == "FAIL"
    assert "rules[].signalId" in bad[0].path


def test_fingerprint_readback_checks_id_rules_and_conditions():
    rec = {"strategy": _migrated_record()}
    assert P.fingerprint_readback(rec, "6a8bca67-45a3-428e-85ba-71ec2cd2218e") == []
    wrong = P.fingerprint_readback(rec, "00000000-0000-4000-8000-000000000000")
    assert wrong and wrong[0].cls == "TRANSCRIPTION_SUSPECT"
    short = json.loads(json.dumps(rec)); short["strategy"]["signalRules"] = short["strategy"]["signalRules"][:83]
    assert any("signalRules" in f.path for f in P.fingerprint_readback(short, rec["strategy"]["id"]))


def test_fingerprint_mismatch_detail_names_the_two_possible_causes():
    """A count mismatch (schema enum or record signalRules) is ambiguous between a
    transcription error and a real platform-side change since the repo data was last
    refreshed; the detail must name both and point at the resolution (a second read-back
    before touching data/derived or data/contract)."""
    arm, root = _create_arm()
    bad = P.fingerprint_schema(arm, root, signal_ids={"rsi_oversold", "rsi_overbought", "macd_bull_cross"},
                               template_keys={"includeRsi", "includeMacd"}, timeframes=["1h", "4h"])
    assert "verify with a second read-back" in bad[0].detail
    rec = {"strategy": _migrated_record()}
    short = json.loads(json.dumps(rec)); short["strategy"]["signalRules"] = short["strategy"]["signalRules"][:83]
    [f] = [f for f in P.fingerprint_readback(short, rec["strategy"]["id"]) if f.path == "signalRules"]
    assert "verify with a second read-back" in f.detail


NOW = datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc)
SCHEMA_META = {"path": "data/contract/compile_strategy_plan/schema_20260904T085500Z.json",
               "capturedAt": "2026-09-04T08:55:00Z", "fingerprint": "ok"}
READBACK_META = {"path": "data/contract/get_strategy/b9438519_20260904T085800Z.json",
                 "capturedAt": "2026-09-04T08:58:00Z", "strategyId": "b9438519-8223-4ef1-a3c3-6f4592bb823d",
                 "revision": 2, "fingerprint": "ok"}


def test_parse_iso_accepts_fractional_seconds_and_offset_and_rejects_garbage():
    """Strict `%Y-%m-%dT%H:%M:%SZ` rejects the millisecond-bearing timestamps the platform
    actually returns (e.g. 6a8bca67's createdAt, 2026-08-28T13:48:33.561Z) and the
    +00:00-offset spelling. `parse_iso` is the public replacement; `_parse_iso` stays as an
    alias for existing internal callers."""
    assert P.parse_iso("2026-08-28T13:48:33.561Z") == datetime(2026, 8, 28, 13, 48, 33, 561000, tzinfo=timezone.utc)
    assert P.parse_iso("2026-08-28T13:48:33+00:00") == datetime(2026, 8, 28, 13, 48, 33, tzinfo=timezone.utc)
    assert P.parse_iso("2026-08-28T13:48:33Z") == datetime(2026, 8, 28, 13, 48, 33, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        P.parse_iso("not-a-timestamp")
    assert P._parse_iso is P.parse_iso


def test_body_sha256_is_canonical():
    a = P.body_sha256({"b": 1, "a": [1, 2]}); b = P.body_sha256({"a": [1, 2], "b": 1})
    assert a == b and len(a) == 64


def test_verdict_fails_only_on_fail_class_findings():
    assert P.verdict([]) == "PASS"
    assert P.verdict([P.Finding("MIRROR", "entry.closes", "d", "WARN"), P.Finding("INFO", "id", "d", "INFO")]) == "PASS"
    assert P.verdict([P.Finding("ENUM", "entry.trigger", "d", "FAIL")]) == "FAIL"


def test_receipt_carries_sha_expiry_disclaimer_and_findings():
    body = _good_body()
    r = P.build_receipt(body=body, body_path="x.json", operation="CREATE", schema_meta=SCHEMA_META,
                        readback_meta=READBACK_META, findings=[], now=NOW, unmeasured=["runtime enforcement of exit"])
    assert r["verdict"] == "PASS" and r["body"]["sha256"] == P.body_sha256(body)
    assert r["expiresAt"] == "2026-09-04T09:55:00Z"          # 60 min from the OLDER capture
    assert r["disclaimer"] == P.DISCLAIMER and r["voided"] is None
    assert r["unmeasured"] == ["runtime enforcement of exit"]
    assert P.gate_line(r).startswith("PREFLIGHT PASS") and "b9438519" in P.gate_line(r) and "rev 2" in P.gate_line(r)


def test_build_receipt_precomputes_the_gate_line_for_the_resolved_receipt_path():
    """The gate line the CLI prints on PASS must also be readable straight out of the
    written receipt JSON (so the checkbox text can be copied from the file, not only from
    a terminal that already scrolled away)."""
    body = _good_body()
    r = P.build_receipt(body=body, body_path="x.json", operation="CREATE", schema_meta=SCHEMA_META,
                        readback_meta=READBACK_META, findings=[], now=NOW,
                        receipt_path="data/audit/compile_preflight_2026-09-04.json")
    assert r["gateLine"].startswith("PREFLIGHT PASS")
    assert "data/audit/compile_preflight_2026-09-04.json" in r["gateLine"]
    assert r["gateLine"] == P.gate_line(r, "data/audit/compile_preflight_2026-09-04.json")


def test_build_receipt_omits_the_gate_line_on_a_fail_receipt():
    """A FAIL receipt used to carry a gateLine reading 'PREFLIGHT PASS ...' anyway, since
    build_receipt called gate_line() unconditionally - a FAIL receipt must never spell out
    a PASS line for anyone to copy into an authorization checkbox."""
    body = _good_body()
    r = P.build_receipt(body=body, body_path="x.json", operation="CREATE", schema_meta=SCHEMA_META,
                        readback_meta=READBACK_META, findings=[P.Finding("ENUM", "p", "d", "FAIL")], now=NOW,
                        receipt_path="data/audit/compile_preflight_2026-09-04.json")
    assert r["verdict"] == "FAIL"
    assert r["gateLine"] is None


def test_gate_check_passes_then_fails_on_expiry_sha_mismatch_fail_and_void():
    body = _good_body()
    r = P.build_receipt(body=body, body_path="x.json", operation="CREATE", schema_meta=SCHEMA_META,
                        readback_meta=READBACK_META, findings=[], now=NOW)
    assert P.gate_check(r, body, NOW) == (True, "PASS")
    assert P.gate_check(r, body, NOW + timedelta(hours=2))[0] is False
    other = dict(body, name="edited")
    ok, why = P.gate_check(r, other, NOW); assert not ok and "sha" in why
    failed = P.build_receipt(body=body, body_path="x.json", operation="CREATE", schema_meta=SCHEMA_META,
                             readback_meta=READBACK_META, findings=[P.Finding("ENUM", "p", "d", "FAIL")], now=NOW)
    assert P.gate_check(failed, body, NOW)[0] is False
    voided = dict(r, voided={"at": "2026-09-04T09:10:00Z", "reason": "refused", "refusalRecord": "x.json"})
    ok, why = P.gate_check(voided, body, NOW); assert not ok and "void" in why


def test_gate_check_refuses_naive_now_and_malformed_receipt_without_raising():
    body = _good_body()
    r = P.build_receipt(body=body, body_path="x.json", operation="CREATE", schema_meta=SCHEMA_META,
                        readback_meta=READBACK_META, findings=[], now=NOW)

    # Test naive now (no tzinfo)
    naive_now = datetime(2026, 9, 4, 9, 0)
    ok, why = P.gate_check(r, body, naive_now)
    assert not ok and "timezone" in why

    # Test missing expiresAt
    malformed_no_expiry = dict(r)
    del malformed_no_expiry["expiresAt"]
    ok, why = P.gate_check(malformed_no_expiry, body, NOW)
    assert not ok and "malformed" in why

    # Test missing body
    malformed_no_body = dict(r)
    del malformed_no_body["body"]
    ok, why = P.gate_check(malformed_no_body, body, NOW)
    assert not ok and "malformed" in why

    # Test unparsable expiresAt - parse_iso's tolerant parsing must still raise ValueError
    # on genuine garbage, and gate_check must keep failing closed on it, not crash
    malformed_bad_expiry = dict(r, expiresAt="not-a-timestamp")
    ok, why = P.gate_check(malformed_bad_expiry, body, NOW)
    assert not ok and "malformed" in why


def test_string_format_keyword_is_declared_but_unchecked_info_not_unsupported():
    """The real definition marks UPDATE/RESTORE strategyId with format: uuid (capture
    2026-09-05). Like pattern, format is declared-but-unchecked: one INFO, never an
    UNSUPPORTED WARN on every UPDATE preflight."""
    cap = ROOT / "data/contract/compile_strategy_plan/schema_20260905T011443Z.json"
    definition = json.loads(cap.read_text(encoding="utf-8"))["response"]
    arms, root = P.resolve_arms(definition)
    body = {"operation": "UPDATE", "strategyId": "b9438519-8223-4ef1-a3c3-6f4592bb823d",
            "expectedRevision": 2, "intentSummary": "x", "assumptions": [],
            "coinSelection": {"mode": "explicit", "tickers": ["BTC"]}}
    found = [f for f in P.diff_schema(body, arms["UPDATE"], root) if f.path == "strategyId"]
    assert [(f.cls, f.verdict) for f in found] == [("INFO", "INFO")]
    assert "format-unchecked" in found[0].detail and "uuid" in found[0].detail
