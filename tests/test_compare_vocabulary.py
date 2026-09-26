"""scripts/compare_vocabulary.py: a stored surface whose enums equal the extraction compares identical; one that
adds, drops or omits an enum is caught. The surfaces here are built from the repo's own extraction, so the test
needs no fixture of the platform's schema."""
from __future__ import annotations

import json

import pytest

from scripts.compare_vocabulary import compare, first_enum, live_enums, main, stored_enums


def _surface(metrics, signals, sections, *, drop_tool: str | None = None) -> dict:
    tools = [
        {"name": "get_metric_construction_hints",
         "inputSchema": {"type": "object", "properties": {"metric": {"type": "string", "enum": sorted(metrics)}}}},
        {"name": "update_strategy_signal_rule",
         "inputSchema": {"type": "object", "properties": {"request": {"type": "object", "properties": {
             "signalId": {"type": "string", "enum": sorted(signals)}}}}}},
        {"name": "compile_strategy_plan",
         "inputSchema": {"type": "object", "properties": {"plan": {"type": "object", "properties": {"sections": {
             "type": "array", "items": {"type": "object", "properties": {
                 "sectionKey": {"type": "string", "enum": sorted(sections)}}}}}}}}},
    ]
    return {"contractVersion": "0.0.0", "buildSha": "test", "observedAt": "2026-09-26T00:00:00Z",
            "tools": [t for t in tools if t["name"] != drop_tool]}


def test_first_enum_finds_a_nested_property_and_ignores_enumless_ones():
    schema = {"properties": {"a": {"properties": {"sectionKey": {"type": "string"}}},
                             "b": {"items": [{"properties": {"sectionKey": {"enum": ["X", "Y"]}}}]}}}
    assert first_enum(schema, "sectionKey") == ["X", "Y"]
    assert first_enum(schema, "absent") is None


def test_the_extraction_against_itself_is_identical_and_not_empty():
    stored = stored_enums()
    assert all(stored[k] for k in stored), "an empty stored enum would make every comparison vacuous"
    results = compare(live_enums(_surface(stored["metrics"], stored["signals"], stored["sectionKeys"])), stored)
    for name, r in results.items():
        assert r["live"] == r["stored"] > 0, name
        assert r["liveNotStored"] == [] and r["storedNotLive"] == [], name


def test_an_added_and_a_dropped_value_are_named_on_the_right_side():
    stored = stored_enums()
    dropped = sorted(stored["metrics"])[0]
    metrics = (stored["metrics"] - {dropped}) | {"NOT_A_REAL_METRIC"}
    results = compare(live_enums(_surface(metrics, stored["signals"], stored["sectionKeys"])), stored)
    assert results["metrics"]["liveNotStored"] == ["NOT_A_REAL_METRIC"]
    assert results["metrics"]["storedNotLive"] == [dropped]
    assert results["signals"]["liveNotStored"] == results["sectionKeys"]["storedNotLive"] == []


def test_a_missing_tool_or_enum_refuses_rather_than_reporting_everything_removed():
    stored = stored_enums()
    with pytest.raises(KeyError, match="compile_strategy_plan"):
        live_enums(_surface(stored["metrics"], stored["signals"], stored["sectionKeys"],
                            drop_tool="compile_strategy_plan"))
    with pytest.raises(ValueError, match="signals"):
        live_enums(_surface(stored["metrics"], set(), stored["sectionKeys"]))


def test_main_exits_0_when_identical_and_1_when_an_enum_moved(tmp_path, capsys):
    stored = stored_enums()
    same, moved = tmp_path / "same.json", tmp_path / "moved.json"
    same.write_text(json.dumps(_surface(stored["metrics"], stored["signals"], stored["sectionKeys"])), encoding="utf-8")
    moved.write_text(json.dumps(_surface(stored["metrics"], stored["signals"] | {"NEW_SIGNAL"}, stored["sectionKeys"])),
                     encoding="utf-8")
    assert main([str(same)]) == 0
    assert json.loads(capsys.readouterr().out)["results"]["signals"]["liveNotStored"] == []
    assert main([str(moved)]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["results"]["signals"]["liveNotStored"] == ["NEW_SIGNAL"]
    assert printed["storedCompileCapture"].startswith("data/contract/compile_strategy_plan/schema_")
