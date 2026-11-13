"""Contract 146.0.0 (2026-11-01, undocumented in the battlegrid-mcp README, which stops at v143), against the write
surface captured from battlegrid-manager's stored 146.0.0 surface (docs/plans/2026-11-01-omega-v0.10.2-market-scope-146.md).

- A custom section REQUIRES `marketScope`: null is a per-coin section (the shape every OMEGA section has; probed live
  2026-11-01T07:58Z by the manager's panel request, accepted); a named scope (all, crypto, l1, memes, defi, tradfi,
  stocks, indices, commodities) is a MARKET section, which refuses per-coin metrics ("a market section cannot carry
  this column — metric 'PRIOR_TPO_POC' is not read on a market section's bars", the same probe).
- The platform sections includeMarketBreadth and includeReferencePairs are retired (sectionKey enum 24 -> 22).
- 24 metric keys are added to $defs/metricKey (302 -> 326): served, known by name only, unmeasured
  (data/contract/metrics/_unmeasured_108.json); OMEGA refuses a column over one until a re-extraction measures them.

The schema checks here are made the way battlegrid-manager's authoring/preflight.py makes them: jsonschema over the
whole stage input schema as root, minus the JavaScript `\\p{}` patterns Python's `re` cannot compile.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from omega import contract as C
from omega.contract import CONTRACT_DIR, load
from omega.generate import PRESETS, emit_plan, plan
from omega.probe import render_request
from omega.types import Column, CustomSection, PlatformSection, Report
from omega.validate import validate_column, validate_report
from scripts.compare_vocabulary import compare, live_enums, stored_enums, stored_unmeasured

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_146 = "data/contract/stage_strategy_draft/schema_20261101T061733Z.json"
SCHEMA_144 = "data/contract/stage_strategy_draft/schema_20261029T152942Z.json"
SCHEMA_161 = "data/contract/stage_strategy_draft/schema_20261109T162100Z.json"   # the last capture with a metricKey ENUM on the stage schema
FIXTURE =Path("C:/Users/rafae/Documents/GitHub/battlegrid-manager/tests/fixtures/2026-11-01-surface-146.0.0/"
               "manager_schemas_146.0.0.json")
DOC = json.loads((ROOT / SCHEMA_146).read_text(encoding="utf-8"))
DOC_144 = json.loads((ROOT / SCHEMA_144).read_text(encoding="utf-8"))
MARKET_SCOPES = ["all", "crypto", "l1", "memes", "defi", "tradfi", "stocks", "indices", "commodities"]
RETIRED_SECTION_KEYS = {"includeMarketBreadth", "includeReferencePairs"}
ADDED_METRICS = {
    "MKT_UP", "MKT_DOWN", "MKT_NET", "MKT_AVG_CHG", "MKT_DISPERSION", "MKT_PPO_UP", "MKT_PPO_DOWN", "MKT_PPO_NET",
    "MKT_AVG_PPO", "MKT_VOL_NET", "MKT_STRETCH", "MKT_ABOVE_EMA", "MKT_UNIVERSE",
    "CROWD_UP_LEAN_Z", "CROWD_UP_EXCESS_Z", "CROWD_CAPT_EXCESS_Z", "CROWD_ACC_EDGE_Z",
    "CROWD_UP_LEAN_Z_LIVE", "CROWD_UP_EXCESS_Z_LIVE", "CROWD_CAPT_EXCESS_Z_LIVE", "CROWD_ACC_EDGE_Z_LIVE",
    "PAR_DEV", "REGIME_WARNING_CRASH", "REGIME_WARNING_DIVERGENCE",
}
assert len(ADDED_METRICS) == 24
SECTIONS = ("properties", "axes", "properties", "REPORT", "properties", "sections", "items")
A_COLUMN = {"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "anchor"}}


# --- the manager's schema reading, reproduced ----------------------------------------------------------------------
def _compiles(pattern: str) -> bool:
    try:
        re.compile(pattern)
    except re.error:
        return False
    return True


def without_uncompilable_patterns(schema: dict) -> tuple[dict, list[str]]:
    """battlegrid-manager manager/platform/output_schema.py: a deep copy without the `pattern` keywords Python's
    re.compile rejects (the platform's `\\p{Cc}` classes), and the paths removed."""
    removed: list[str] = []

    def copy_without(node, path):
        if isinstance(node, dict):
            kept = {}
            for key, value in node.items():
                if key == "pattern" and isinstance(value, str) and not _compiles(value):
                    removed.append(path)
                    continue
                kept[key] = copy_without(value, f"{path}.{key}")
            return kept
        if isinstance(node, list):
            return [copy_without(item, f"{path}[{i}]") for i, item in enumerate(node)]
        return copy.deepcopy(node)

    return copy_without(schema, "$"), removed


def _arm(root: dict, kind: str) -> dict:
    node = root
    for seg in SECTIONS:
        node = node[seg]
    want = "columns" if kind == "custom" else "sectionKey"
    return next(a for a in node["oneOf"] if want in a["properties"])


def _section_validator(doc: dict) -> jsonschema.Draft202012Validator:
    """A validator for one custom section, with the WHOLE stage input schema as root (so `$ref: #/$defs/metricKey`
    resolves), exactly as authoring/preflight.py validates a staged axis."""
    root, removed = without_uncompilable_patterns(doc["stage_strategy_draft"]["inputSchema"])
    assert removed, "the served schema carries \\p{} patterns; none removed means the copy read the wrong document"
    return jsonschema.Draft202012Validator(root).evolve(schema=_arm(root, "custom"))


# --- the capture ---------------------------------------------------------------------------------------------------
def test_the_capture_names_its_contract_build_and_source():
    assert DOC["contractVersion"] == "146.0.0"
    assert DOC["buildSha"] == "1cd4466aace4e047a44672b6d531e4deabc8fe12"
    assert DOC["observedAt"] == "2026-11-01T06:17:33.505770+00:00"
    assert DOC["surfaceHash"] == "16cff97454de920641d071adfd79b367c9c8ff4ccc302cb3ce92c14b08b4a9df"
    assert "manager_schemas_146.0.0.json" in DOC["readFrom"] and "07:56:45Z" in DOC["readFrom"]
    for tool in ("stage_strategy_draft", "get_strategy_draft", "commit_strategy_draft", "list_strategy_drafts",
                 "preview_strategy_report", "get_strategy"):
        assert {"inputSchema", "outputSchema", "description"} <= set(DOC[tool]), tool
    # superseded as the write surface by the 148.1.0 capture on 2026-11-05 and the 149.1.0 one on 2026-11-07 (the
    # v0.12 branch, unreleased: pyproject.toml stays 0.11.0 until the full re-extraction lands); kept as history
    # and by the 161.0.0 one on 2026-11-09 (the 149.1.0 capture is the manifest's `supersedes`)
    # 2026-11-11, contract 168.3.0: and by the 168.3.0 capture (the 161.0.0 one is the manifest's `supersedes` now); this
    # 146.0.0 capture is four `supersedes` down the write surface chain (161.0.0, 149.1.0, 148.1.0, then it)
    # 2026-11-12: found by version, not depth (tests/manifest_chain.py) - the pins moved 169.4.0 -> 171.0.0 that morning
    from tests.manifest_chain import surface
    assert C.stage_schema() is not None and C.stage_schema()["contractVersion"] == "171.0.0"   # 149.1.0 until 2026-11-09, 161.0.0 until 2026-11-11, 168.3.0 / 169.4.0 until 2026-11-12
    assert surface("146.0.0")["schema"] == SCHEMA_146


@pytest.mark.skipif(not FIXTURE.exists(), reason="the battlegrid-manager checkout is not beside this repo")
def test_every_tool_entry_is_the_manager_fixtures_own():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == DOC["sourceSha256"]
    fixture = json.loads(raw.decode("utf-8"))
    assert (fixture["contractVersion"], fixture["buildSha"], fixture["hash"]) == (
        DOC["contractVersion"], DOC["buildSha"], DOC["surfaceHash"])
    for tool in ("stage_strategy_draft", "get_strategy_draft", "commit_strategy_draft", "list_strategy_drafts",
                 "preview_strategy_report", "get_strategy"):
        assert DOC[tool] == fixture["tools"][tool], tool


# --- marketScope ---------------------------------------------------------------------------------------------------
def test_the_served_custom_section_arm_requires_market_scope_with_the_nine_scopes_or_null():
    before = _arm(DOC_144["stage_strategy_draft"]["inputSchema"], "custom")
    after = _arm(DOC["stage_strategy_draft"]["inputSchema"], "custom")
    assert before["required"] == ["kind", "title", "benchmarkTicker", "notes", "columns"]
    assert after["required"] == ["kind", "title", "benchmarkTicker", "marketScope", "notes", "columns"]
    assert after["additionalProperties"] is False
    arms = after["properties"]["marketScope"]["anyOf"]
    assert next(a for a in arms if "enum" in a)["enum"] == MARKET_SCOPES
    assert {"type": "null"} in arms


def test_a_default_section_wires_market_scope_null_and_validates_against_the_146_arm():
    section = CustomSection(title="Signals", columns=[Column.model_validate(A_COLUMN)])
    assert section.marketScope is None
    wire = section.wire()
    assert wire["marketScope"] is None and "marketScope" in wire       # present, null
    assert list(wire) == ["kind", "title", "columns", "benchmarkTicker", "marketScope", "notes"]
    assert not list(_section_validator(DOC).iter_errors(wire))


def test_a_section_without_the_key_fails_on_exactly_that_property():
    """What every v0.10.1 plan hit in battlegrid-manager's preflight from 2026-11-01T06:12Z (SCHEMA_REQUIRED at
    axes.REPORT.sections[].marketScope)."""
    section = CustomSection(title="Signals", columns=[Column.model_validate(A_COLUMN)]).wire()
    del section["marketScope"]
    assert [e.message for e in _section_validator(DOC).iter_errors(section)] == \
        ["'marketScope' is a required property"]
    # history: the closed 144.0.0 arm refused the key the other way round
    assert [e.message for e in _section_validator(DOC_144).iter_errors(section | {"marketScope": None})] == \
        ["Additional properties are not allowed ('marketScope' was unexpected)"]


@pytest.mark.parametrize("scope", MARKET_SCOPES)
def test_a_named_scope_is_schema_legal_and_wires_as_given(scope):
    """Schema-legal; whether the platform renders it depends on the columns (a market section refuses per-coin
    metrics, measured once on PRIOR_TPO_POC 2026-11-01T07:58Z), which no offline check models."""
    section = CustomSection(title="Breadth", marketScope=scope, columns=[Column.model_validate(A_COLUMN)])
    assert section.wire()["marketScope"] == scope
    assert not list(_section_validator(DOC).iter_errors(section.wire()))


def test_a_scope_outside_the_enum_is_refused_before_the_wire():
    with pytest.raises(ValidationError):
        CustomSection(title="x", marketScope="equities", columns=[Column.model_validate(A_COLUMN)])
    section = CustomSection(title="x", columns=[Column.model_validate(A_COLUMN)]).wire() | {"marketScope": "equities"}
    errors = list(_section_validator(DOC).iter_errors(section))
    # the served arm is anyOf [enum, null], so jsonschema reports the anyOf, at the key
    assert [list(e.path) for e in errors] == [["marketScope"]]
    assert errors[0].message == "'equities' is not valid under any of the given schemas"


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_every_generated_section_carries_the_key_and_the_emitted_body_walks_the_146_schema_clean(tmp_path, preset):
    from omega import preflight as P
    doc = json.loads(Path(emit_plan(plan(PRESETS[preset]), preset, out_dir=tmp_path)).read_text(encoding="utf-8"))
    body = {k: v for k, v in doc.items() if not k.startswith("_")}
    sections = body["axes"]["REPORT"]["sections"]
    # every thesis section is per-coin (null); since v0.12.1 the Market Tape context section is a market section
    # ("all") and Stablecoin Par a reference section bound to USDT_USD (null scope)
    assert sections and all(s["marketScope"] == ("all" if s["title"] == "Market Tape" else None)
                            for s in sections if s["kind"] == "custom")
    root = DOC["stage_strategy_draft"]["inputSchema"]
    # 2026-11-11, contract 168.3.0 (extraction 20261111): every plan emits TRADE_LEVEL_POLICY.tradeLevelMenu, which 168
    # requires and this 146 capture's closed axis does not declare. As emitted the body walks the CURRENT capture clean
    # (strict, the key present) and the 146 capture reads exactly that one key UNDECLARED; the 146 walk this test is
    # about runs on a copy without that one key (the key must be there to take out).
    current = C.stage_schema()["stage_strategy_draft"]["inputSchema"]
    assert [(f.cls, f.path) for f in P.diff_schema(body, current, current)
            if f.verdict == "FAIL" or f.cls == "UNSUPPORTED"] == []
    assert [(f.cls, f.path) for f in P.diff_schema(body, root, root)
            if f.verdict == "FAIL" or f.cls == "UNSUPPORTED"] == [("UNDECLARED", "axes.TRADE_LEVEL_POLICY.tradeLevelMenu")]
    pre_168 = copy.deepcopy(body)
    del pre_168["axes"]["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]
    findings = P.diff_schema(pre_168, root, root)
    assert [(f.cls, f.path) for f in findings if f.verdict == "FAIL" or f.cls == "UNSUPPORTED"] == []
    validator = _section_validator(DOC)
    for s in sections:
        if s["kind"] == "custom":
            assert not list(validator.iter_errors(s)), preset


def test_the_probe_request_carries_the_key():
    """omega.probe.render_request is the one hand-built section in the package; the preview tool's custom arm
    requires the key too (the manager's hourly panel pull was refused from 06:12Z until it named it)."""
    from omega.space import ColumnShape
    [section] = render_request([ColumnShape(metric="RSI14", transform="value")], ["BTC"])["sections"]
    assert section["marketScope"] is None and section["benchmarkTicker"] is None


# --- the two retired platform sections -----------------------------------------------------------------------------
def test_the_section_key_enum_lost_the_two_zero_column_sections():
    before = _arm(DOC_144["stage_strategy_draft"]["inputSchema"], "platform")["properties"]["sectionKey"]["enum"]
    after = _arm(DOC["stage_strategy_draft"]["inputSchema"], "platform")["properties"]["sectionKey"]["enum"]
    assert set(before) - set(after) == RETIRED_SECTION_KEYS and not set(after) - set(before)
    assert len(after) == 22 and set(after) == set(load().platform_templates)
    stored = stored_enums()
    assert stored["sectionKeys"] == set(after)
    categories = json.loads((CONTRACT_DIR / "categories.json").read_text(encoding="utf-8"))
    assert not RETIRED_SECTION_KEYS & {m["sectionKey"] for m in categories["modules"]}


@pytest.mark.parametrize("key", sorted(RETIRED_SECTION_KEYS))
def test_a_retired_platform_section_is_refused_offline(key):
    result = validate_report(Report(anchor="1h", sections=[PlatformSection(sectionKey=key)]))
    assert [f.code for f in result.findings if f.severity == "error"] == ["UNKNOWN_SECTION_KEY"]


# --- the 24 metrics 146.0.0 added -------------------------------------------------------------------------------------
# Served and known by name only from 2026-11-01 (OMEGA v0.10.2: data/contract/metrics/_unmeasured_108.json, refused
# offline as METRIC_UNMEASURED); measured 2026-11-02 by the re-extraction at 146.0.1 (OMEGA v0.11.0,
# data/contract/metrics/_moves_146.json, tests/test_v146_1.py). These tests pin the history and the present state.
def test_the_added_metrics_are_served_and_now_in_the_corpus():
    contract = load()
    served = set(DOC["stage_strategy_draft"]["inputSchema"]["$defs"]["metricKey"]["enum"])
    before = set(DOC_144["stage_strategy_draft"]["inputSchema"]["$defs"]["metricKey"]["enum"])
    assert served - before == ADDED_METRICS and not before - served and (len(before), len(served)) == (302, 326)
    # 24 unmeasured from 2026-11-01 to 2026-11-02; since 2026-11-05 the record holds the 206 keys the 148.1.0 capture
    # added (tests/test_condition_vocabulary_108.py), none of these
    assert set(contract.unmeasured_metrics).isdisjoint(ADDED_METRICS)
    # the corpus is the 146 enum plus the 206 the 148.1.0 capture added (in the corpus since 2026-11-07)
    added_148 = set(json.loads((CONTRACT_DIR / "metrics" / "_moves_149.json").read_text(encoding="utf-8"))["added"])
    # 161.0.0 (2026-11-09): BB_TOUCH, served at 146, is retired (_moves_161.json) and its three additions are in the corpus
    moves_161 = json.loads((CONTRACT_DIR / "metrics" / "_moves_161.json").read_text(encoding="utf-8"))
    # 2026-11-11, contract 168.3.0 (extraction 20261111): 47 keys added, none retired (_moves_168.json). The 47 are the
    # 168.3.0 roster (the capture's get_strategy outputSchema $defs/metricKey - the stage schema names a metric by
    # pattern now) less the 161.0.0 stage enum, and the corpus is that roster: 534 -> 581
    moves_168 = json.loads((CONTRACT_DIR / "metrics" / "_moves_168.json").read_text(encoding="utf-8"))
    roster_168 = set(C.stage_schema()["get_strategy"]["outputSchema"]["$defs"]["metricKey"]["enum"])
    roster_161 = set(json.loads((ROOT / SCHEMA_161).read_text(encoding="utf-8"))
                     ["stage_strategy_draft"]["inputSchema"]["$defs"]["metricKey"]["enum"])
    assert set(moves_168["added"]) == roster_168 - roster_161 and len(moves_168["added"]) == 47
    assert moves_168["retired"] == [] and not roster_161 - roster_168
    assert ADDED_METRICS <= set(contract.metrics) and set(contract.metrics) == (
        (served - set(moves_161["retired"])) | added_148 | set(moves_161["added"]) | set(moves_168["added"]))
    assert set(contract.metrics) == roster_168 and len(roster_168) == 581
    record = json.loads((CONTRACT_DIR / "metrics" / "_unmeasured_108.json").read_text(encoding="utf-8"))
    assert set(record["metrics"]).isdisjoint(ADDED_METRICS)
    assert set(record["history146"]["formerlyUnmeasured"]) == ADDED_METRICS
    assert record["history146"]["listedOn"] == "2026-11-01" and record["history146"]["measuredOn"] == "2026-11-02"
    for key in sorted(ADDED_METRICS):
        column = Column.model_validate({"metric": key, "transformId": "value", "timeframe": {"rel": "anchor"}})
        codes = [f.code for f in validate_column(column, contract=contract) if f.severity == "error"]
        # PAR_DEV was read by NO section subject at 146 (METRIC_NO_SUBJECT); since 148 its served subjectKinds say a pair
        # section reads it, so the column is fine and the section decides (tests/test_v146_1.py)
        assert codes == [], key


def test_the_stored_capture_compares_identical_with_nothing_unmeasured():
    """The stage tool entry as saved, in a surface, beside a v137.2-shaped hints tool that names the same `$defs`:
    nothing moved on either kind and nothing is `storedUnmeasured` (the 24 were, from 2026-11-01 to 2026-11-02), so
    battlegrid-manager's pin-drift gate reads none."""
    stage = DOC["stage_strategy_draft"]
    surface = {"contractVersion": DOC["contractVersion"], "buildSha": DOC["buildSha"], "observedAt": DOC["observedAt"],
               "tools": [dict(name="stage_strategy_draft", **stage),
                         {"name": "get_metric_construction_hints",
                          "inputSchema": {"type": "object",
                                          "properties": {"metric": {"$ref": "#/$defs/metricKey"}},
                                          "$defs": {"metricKey": stage["inputSchema"]["$defs"]["metricKey"]}}}]}
    results = compare(live_enums(surface), stored_enums(), stored_unmeasured())
    # 161.0.0 (2026-11-09): this 146.0.0 surface still serves BB_TOUCH, which the corpus no longer stores (retired)
    assert results["metrics"]["liveNotStored"] == ["BB_TOUCH"] and results["sectionKeys"]["liveNotStored"] == []
    assert results["sectionKeys"]["storedNotLive"] == []
    # since 2026-11-07 the store holds the 206 keys the 148.1.0 capture added (unmeasured 11-05 .. 11-07), which this
    # 146.0.0 surface does not serve
    added_148 = json.loads((CONTRACT_DIR / "metrics" / "_moves_149.json").read_text(encoding="utf-8"))["added"]
    # and, since 161.0.0 (2026-11-09), VWMA20 and the two DONCHIAN_BROKEN_*_PRIOR (_moves_161.json)
    added_161 = json.loads((CONTRACT_DIR / "metrics" / "_moves_161.json").read_text(encoding="utf-8"))["added"]
    # and, since 168.3.0 (2026-11-11, extraction 20261111), the 47 keys of _moves_168.json (none retired, so
    # liveNotStored above is still BB_TOUCH alone)
    added_168 = json.loads((CONTRACT_DIR / "metrics" / "_moves_168.json").read_text(encoding="utf-8"))["added"]
    assert len(added_161) == 3 and len(added_168) == 47
    assert results["metrics"]["storedNotLive"] == sorted(added_148 + added_161 + added_168) and len(added_148) == 206
    assert (results["metrics"]["live"], results["sectionKeys"]["live"]) == (326, 22)
    assert results["metrics"]["storedUnmeasured"] == []


def test_the_version_moved_past_v0_10_2():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # 0.11.0 at 146.0.1 (2026-11-02); 0.12.0 at 161.0.0 (2026-11-10); 0.12.1 the same day (no retired ambient header);
    # 0.12.2 on 2026-11-11 (the joint depth bound, the chained touchAtr maximum); 0.13.0 the same day (re-extracted at
    # contract 168.3.0: the trade level menu, 581 metrics, tests/test_v168.py); 0.13.1 on 2026-11-12 (what 168 served and
    # 0.13.0 left unmeasured, measured at 169.4.0 and modelled: tests/test_v169.py); 0.14.0 the same day (contract 170's
    # exit plans, pinned at 171.0.0: tests/test_exit_plans_170.py); 0.14.1 the same day (the chain window limits measured
    # at 171.0.0: tests/test_v0_14_1.py; and the exit plan's runner: tests/test_exit_plan_runner_171.py); 0.14.2 the same
    # day (the update rules and the last unmeasured items, measured at 171.0.0: tests/test_update_rules_171.py); 0.14.3 on
    # 2026-11-13 (the default menu inside the stop range: tests/test_stop_band_171.py)
    assert 'version = "0.10.2"' not in text and 'version = "0.14.3"' in text
