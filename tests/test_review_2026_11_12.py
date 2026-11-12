"""The independent review of the v0.13.0 branch (2026-11-12), outside the menu validator
(tests/test_trade_level_menu_168.py holds that part).

  preflight  the metric node is recognised by identity (through a union arm or a `$ref` chain); a plain pattern is
             judged with ECMA semantics; a non-finite number fails; the command line warns when no roster applies.
  refresh    an operand set must be a list; no operand-set id is stored unresolved; a hint is the metric asked.
  capture    "agrees on all six" only when all six were compared.
"""
from __future__ import annotations

import json
import math
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from omega import preflight as P
from omega.contract import stage_schema
from omega.generate import PRESETS, plan

ROOT = Path(__file__).resolve().parents[1]
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="the runtime transport starts `node`")


# --- preflight ---------------------------------------------------------------------------------------------------

def test_the_metric_key_is_checked_however_the_schema_reaches_it():
    """A direct `$ref` is how the 168.3.0 capture names it; a union arm or a `$ref` chain reached the same node and was
    skipped with no finding at all."""
    root = {"type": "object",
            "properties": {"direct": {"$ref": "#/$defs/metricKey"},
                           "nullable": {"anyOf": [{"$ref": "#/$defs/metricKey"}, {"type": "null"}]},
                           "chained": {"$ref": "#/$defs/alias"}},
            "$defs": {"metricKey": {"type": "string", "minLength": 1, "maxLength": 64, "pattern": "^[A-Z][A-Z0-9_]*$"},
                      "alias": {"$ref": "#/$defs/metricKey"}}}
    roster = frozenset({"ADX"})
    body = {"direct": "NOPE", "nullable": "NOPE", "chained": "NOPE"}
    assert sorted((f.cls, f.path) for f in P.diff_schema(body, root, root, roster=roster) if f.verdict == "FAIL") == [
        ("ENUM", "chained"), ("ENUM", "direct"), ("ENUM", "nullable")]
    assert [f for f in P.diff_schema({"direct": "ADX", "nullable": None, "chained": "ADX"}, root, root, roster=roster)
            if f.verdict == "FAIL"] == []
    unchecked = [f.path for f in P.diff_schema(body, root, root) if "metric-roster-unchecked" in f.detail]
    assert sorted(unchecked) == ["chained", "direct", "nullable"]


def test_a_plain_pattern_is_judged_as_the_platform_judges_it():
    key = "^[A-Z][A-Z0-9_]*$"
    assert P._pattern_ok(key, "ADX") is True and P._pattern_ok(key, "adx") is False
    assert P._pattern_ok(key, "ADX\n") is False          # Python's `$` also matches before a final newline; ECMA's not
    assert P._pattern_ok(r"^\d+$", "12") is True and P._pattern_ok(r"^\d+$", "１２") is False     # ASCII digits
    assert P._pattern_ok(r"^\p{Lu}+$", "ADX") is None    # a Unicode property class is left to the platform
    assert P._pattern_ok("^(unclosed", "x") is None      # so is a pattern `re` cannot compile


def test_a_non_finite_number_fails_the_walk():
    doc = stage_schema()
    root = doc["stage_strategy_draft"]["inputSchema"]
    body = {"draftVersion": 0, "axes": plan(PRESETS["trend-continuation"]).axes()}
    for value in (math.nan, math.inf, -math.inf):
        body["axes"]["TRADE_LEVEL_POLICY"]["minAtrPct"] = value
        fails = [(f.cls, f.path) for f in P.diff_schema(body, root, root, roster=P.read_roster(doc)) if f.verdict == "FAIL"]
        assert fails == [("BOUNDS", "axes.TRADE_LEVEL_POLICY.minAtrPct")], value


def test_the_command_line_takes_the_roster_through_either_definition_shape_and_warns_without_one():
    import scripts.preflight as cli
    pinned = stage_schema()["stage_strategy_draft"]
    assert len(cli._roster_for({"inputSchema": pinned["inputSchema"]})) == 581
    assert len(cli._roster_for({"parameters": pinned["inputSchema"]})) == 581        # the ToolSearch shape
    other = json.loads((ROOT / "data/contract/stage_strategy_draft/schema_20261109T162100Z.json")
                       .read_text(encoding="utf-8"))["stage_strategy_draft"]
    assert cli._roster_for({"inputSchema": other["inputSchema"]}) is None            # the 161 surface: its own enum
    assert cli._roster_for({}) is None and cli._roster_for(None) is None
    assert cli._names_metric_by_pattern(pinned["inputSchema"]) is True
    assert cli._names_metric_by_pattern(other["inputSchema"]) is False


# --- refresh -----------------------------------------------------------------------------------------------------

def _refresh():
    """tests/test_refresh_metric_contracts.py's throwaway tree and stand-in runtime."""
    import tests.test_refresh_metric_contracts as t
    return t


@needs_node
@pytest.mark.parametrize("sets, why", [
    ({"operands-1": "CLOSE", "operands-2": ["CLOSE"]}, "operands-1"),               # a string: list() gives characters
    ({"operands-1": {"CLOSE": 1}, "operands-2": ["CLOSE"]}, "operands-1"),          # a dict: list() gives its keys
])
def test_an_operand_set_that_is_not_a_list_stops_the_build(tmp_path, sets, why):
    t = _refresh()
    table = {"B": {"ok": True, "value": t._hint_168("B", sets=sets)}}
    run = t._tree(tmp_path, roster=["A", "B"], raw=["A"], stub_stderr=t.OAUTH, runtime=table)
    out = run["proc"].stderr + run["proc"].stdout
    assert run["proc"].returncode != 0 and why in out and "not a list" in out
    assert json.loads((run["metrics"] / "B.json").read_text(encoding="utf-8")) == {"metric": "B", "stored": True}


@needs_node
def test_an_operand_set_id_under_a_key_the_builder_does_not_resolve_stops_the_build(tmp_path):
    t = _refresh()
    hint = t._hint_168("B")
    hint["metric"]["rankOrderings"] = "operands-2"          # copied as served: it would have been stored as the id
    run = t._tree(tmp_path, roster=["A", "B"], raw=["A"], stub_stderr=t.OAUTH, runtime={"B": {"ok": True, "value": hint}})
    out = run["proc"].stderr + run["proc"].stdout
    assert run["proc"].returncode != 0 and "left unresolved" in out and "rankOrderings" in out
    assert json.loads((run["metrics"] / "_index.json").read_text(encoding="utf-8"))["metricCount"] == 2


@needs_node
def test_a_hint_for_another_metric_is_a_failed_read_never_cached(tmp_path):
    t = _refresh()
    table = {"B": {"ok": True, "value": t._hint("C")}, "C": {"ok": True, "value": t._hint("C")}}
    run = t._tree(tmp_path, roster=["A", "B", "C"], raw=["A"], stub_stderr=t.OAUTH, runtime=table)
    assert run["proc"].returncode == 1
    assert "the hint is for 'C', not 'B'" in run["proc"].stdout
    assert not (run["hints"] / "B.json").exists() and (run["hints"] / "C.json").exists()


# --- capture -----------------------------------------------------------------------------------------------------

def _listed(names):
    return [{"name": n, "description": f"d-{n}", "inputSchema": {"type": "object"}, "outputSchema": {"type": "object"}}
            for n in names]


def test_the_capture_agrees_only_when_all_six_tools_were_compared():
    import scripts.capture_write_surface as cws
    version = {"contractVersion": "168.3.0", "buildSha": "af8b2c96"}
    tools = _listed(cws.TOOLS)
    row = {**version, "at": "2026-11-11T20:52:17", "hash": "60f000e7",
           "tools": {t["name"]: {k: t[k] for k in cws.PARTS} for t in tools}}
    doc = cws.capture(version=version, raw=b"x", tools=tools, manager_row=row, row_name="row.json",
                      listed_at=datetime(2026, 11, 11, 21, 32, tzinfo=UTC))
    assert set(doc["managerRowAgrees"]) == set(cws.TOOLS)
    assert all(all(parts.values()) for parts in doc["managerRowAgrees"].values())
    # a row that lacks a tool, or whose `tools` is not keyed by name, compared nothing for it: not "agrees on all six"
    short = {**row, "tools": {k: v for k, v in row["tools"].items() if k != "get_strategy"}}
    for bad in (short, {**row, "tools": list(row["tools"].values())}, {**row, "tools": None}):
        with pytest.raises(SystemExit, match="would not cover the six draft tools"):
            cws.capture(version=version, raw=b"x", tools=tools, manager_row=bad, row_name="row.json",
                        listed_at=datetime(2026, 11, 11, 21, 32, tzinfo=UTC))
    moved = {**row, "tools": {**row["tools"], "get_strategy": {**row["tools"]["get_strategy"], "description": "other"}}}
    doc = cws.capture(version=version, raw=b"x", tools=tools, manager_row=moved, row_name="row.json",
                      listed_at=datetime(2026, 11, 11, 21, 32, tzinfo=UTC))
    assert doc["managerRowAgrees"]["get_strategy"] == {"description": False, "inputSchema": True, "outputSchema": True}
