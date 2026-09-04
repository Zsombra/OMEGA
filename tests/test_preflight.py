"""Schema-drift preflight (design 2026-09-04). Pure functions; the fixtures are a
hand-built walker miniature and the REAL records named in the plan. The miniature is a
walker fixture only - never a regression oracle for wire()."""
from __future__ import annotations

import ast
import copy
import inspect
import json
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
    arm, root = _create_arm()
    body = _good_body(); body["sections"].append({"kind": "mystery"})
    [f] = [f for f in P.diff_schema(body, arm, root) if f.cls == "UNSUPPORTED"]
    assert f.path == "sections[2]" and f.verdict == "WARN"


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
    mirrored fields - the v5 body's entry is the mirrored one (trigger AT_SIGNAL,
    confirmTf 1h, closes 1, bandAtrMultiple 1, levelSource SWING_HIGH,
    levelOffsetAtrMultiple 0, validForBars 4), matching DRIFT5's own read-back of the
    sibling strategy; decisionInvalidationExitEnabled=true. BUILT from records, labelled
    as such - the first live run replaces it with a verbatim capture."""
    rec = json.loads(json.dumps(PRESTATE))
    rec["conditions"] = [
        {"conditionKey": c["conditionKey"], "name": c["name"], "definition": c["definition"],
         "verdict": c["verdict"], "required": c["required"], "exit": False, "clock": "LIVE", "closes": 1}
        for c in rec["conditions"]]
    rec["entry"] = dict(_body(V5)["entry"])
    rec["decisionInvalidationExitEnabled"] = True
    return rec


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


def test_record_diff_top_level_object_the_body_lacks_is_a_warn():
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    del body["entry"]
    for c in body["conditions"]:
        c["exit"] = False
    [f] = [f for f in P.diff_record(body, _migrated_record(), arm, root) if f.path == "entry"]
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
    infos = [f for f in finds if f.path == "sections[*].timeframe"]
    assert infos and all(f.verdict == "INFO" for f in infos)
    assert not any(f.path == "sections[*].timeframe" and f.verdict == "FAIL" for f in finds)


def test_record_request_view_unwraps_the_get_strategy_envelope():
    assert P.record_request_view({"strategy": {"id": "x"}}) == {"id": "x"}
    assert P.record_request_view({"id": "x"}) == {"id": "x"}
