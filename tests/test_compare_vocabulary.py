"""scripts/compare_vocabulary.py: a stored surface whose enums equal the extraction compares identical; one that
adds, drops or omits an enum is caught. The surfaces here are built from the repo's own extraction, so the test
needs no fixture of the platform's schema.

Contract 108 (2026-10-11): the SIGNAL_RULES axis is gone, so the `signals` kind is retired - two enums are compared,
metrics and sectionKeys."""
from __future__ import annotations

import json

import pytest

from scripts.compare_vocabulary import compare, first_enum, live_enums, main, stored_enums


def _surface(metrics, sections, *, drop_tool: str | None = None, envelope: bool = False) -> dict:
    """At contract 108 the sectionKey enum lives on stage_strategy_draft's REPORT axis; there is no SIGNAL_RULES
    axis (README "Contract history - v108"). Since v111 (110.13.0) `axes` is a top-level argument; `envelope` builds
    the pre-v111 shape, `{request: {axes}}`."""
    axes = {
        "REPORT": {"type": "object", "properties": {"sections": {"type": "array", "items": {"anyOf": [
            {"type": "object", "properties": {"kind": {"const": "platform"},
                                              "sectionKey": {"type": "string", "enum": sorted(sections)}}}]}}}},
    }
    tools = [
        {"name": "get_metric_construction_hints",
         "inputSchema": {"type": "object", "properties": {"metric": {"type": "string", "enum": sorted(metrics)}}}},
        {"name": "stage_strategy_draft",
         "inputSchema": {"type": "object", "properties": {"axes": {"type": "object", "properties": axes}}}},
    ]
    if envelope:
        tools[1]["inputSchema"] = {"type": "object", "properties": {"request": tools[1]["inputSchema"]}}
    return {"contractVersion": "0.0.0", "buildSha": "test", "observedAt": "2026-10-11T00:00:00Z",
            "tools": [t for t in tools if t["name"] != drop_tool]}


def test_first_enum_finds_a_nested_property_and_ignores_enumless_ones():
    schema = {"properties": {"a": {"properties": {"sectionKey": {"type": "string"}}},
                             "b": {"items": [{"properties": {"sectionKey": {"enum": ["X", "Y"]}}}]}}}
    assert first_enum(schema, "sectionKey") == ["X", "Y"]
    assert first_enum(schema, "absent") is None


def test_the_extraction_against_itself_is_identical_and_not_empty():
    stored = stored_enums()
    assert set(stored) == {"metrics", "sectionKeys"}          # `signals` retired at contract 108
    assert all(stored[k] for k in stored), "an empty stored enum would make every comparison vacuous"
    results = compare(live_enums(_surface(stored["metrics"], stored["sectionKeys"])), stored)
    assert set(results) == {"metrics", "sectionKeys"}
    for name, r in results.items():
        assert r["live"] == r["stored"] > 0, name
        assert r["liveNotStored"] == [] and r["storedNotLive"] == [], name


def test_a_pre_v111_surface_with_the_request_envelope_still_compares():
    """A surface stored before 110.13.0 wraps the stage's arguments in `request`; it reads the same enums."""
    stored = stored_enums()
    flat = live_enums(_surface(stored["metrics"], stored["sectionKeys"]))
    assert live_enums(_surface(stored["metrics"], stored["sectionKeys"], envelope=True)) == flat


def test_an_added_and_a_dropped_value_are_named_on_the_right_side():
    stored = stored_enums()
    dropped = sorted(stored["metrics"])[0]
    metrics = (stored["metrics"] - {dropped}) | {"NOT_A_REAL_METRIC"}
    results = compare(live_enums(_surface(metrics, stored["sectionKeys"])), stored)
    assert results["metrics"]["liveNotStored"] == ["NOT_A_REAL_METRIC"]
    assert results["metrics"]["storedNotLive"] == [dropped]
    assert results["sectionKeys"]["liveNotStored"] == results["sectionKeys"]["storedNotLive"] == []


def test_a_missing_tool_or_enum_refuses_rather_than_reporting_everything_removed():
    stored = stored_enums()
    with pytest.raises(KeyError, match="stage_strategy_draft"):
        live_enums(_surface(stored["metrics"], stored["sectionKeys"], drop_tool="stage_strategy_draft"))
    with pytest.raises(ValueError, match="sectionKeys"):
        live_enums(_surface(stored["metrics"], set()))


def test_main_exits_0_when_identical_and_1_when_an_enum_moved(tmp_path, capsys):
    stored = stored_enums()
    same, moved = tmp_path / "same.json", tmp_path / "moved.json"
    same.write_text(json.dumps(_surface(stored["metrics"], stored["sectionKeys"])), encoding="utf-8")
    moved.write_text(json.dumps(_surface(stored["metrics"], stored["sectionKeys"] | {"newSection"})),
                     encoding="utf-8")
    assert main([str(same)]) == 0
    assert json.loads(capsys.readouterr().out)["results"]["sectionKeys"]["liveNotStored"] == []
    assert main([str(moved)]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["results"]["sectionKeys"]["liveNotStored"] == ["newSection"]
    assert printed["storedStageCapture"] == "data/contract/stage_strategy_draft/schema_20261029T152942Z.json"   # 144.0.0


def test_the_stored_enums_are_read_off_the_saved_108_stage_schema():
    """25 platform sections on the REPORT axis of the saved 108.0.0 capture, as on the 91.0.0 one; 24 on the 135.2.0
    capture (the newest): v134 retired includeMtfConfluence."""
    from omega.contract import stage_schema
    from omega.preflight import resolve_axes
    stored = stored_enums()
    axes, _ = resolve_axes(stage_schema())
    assert len(stored["sectionKeys"]) == 24 and "includeMtfConfluence" not in stored["sectionKeys"]
    assert stored["sectionKeys"] == set(first_enum(axes["REPORT"], "sectionKey"))
    assert "SIGNAL_RULES" not in axes


def test_the_saved_108_surface_compares_identical_on_the_stage_enum():
    """The stage tool entry exactly as saved, in a surface: no hand-built schema."""
    from omega.contract import stage_schema
    stored = stored_enums()
    surface = _surface(stored["metrics"], stored["sectionKeys"])
    surface["tools"][1] = {"name": "stage_strategy_draft", **stage_schema()["stage_strategy_draft"]}
    results = compare(live_enums(surface), stored)
    assert results["sectionKeys"]["liveNotStored"] == results["sectionKeys"]["storedNotLive"] == []


def test_a_91_surface_still_compares_its_two_enums():
    """A stage tool that still carries SIGNAL_RULES (a pre-108 surface) is read the same way: the axis is ignored."""
    import json as _json
    from pathlib import Path
    old = _json.loads((Path(__file__).resolve().parents[1] / "data/contract/stage_strategy_draft/"
                       "schema_20261005T194629Z.json").read_text(encoding="utf-8"))
    stored = stored_enums()
    surface = _surface(stored["metrics"], stored["sectionKeys"])
    surface["tools"][1] = {"name": "stage_strategy_draft", **old["stage_strategy_draft"]}
    assert set(compare(live_enums(surface), stored)) == {"metrics", "sectionKeys"}
