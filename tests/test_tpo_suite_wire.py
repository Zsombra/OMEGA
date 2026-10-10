"""The TPO suite builder's stage axes and preview bodies must pass the schema walker OFFLINE.

Why this test exists (2026-09-11): the builder had emitted design records and called them
"submit-ready". Run through scripts/preflight.py against a fresh schema capture, every one
FAILED - five required fields missing, ten undeclared keys. Offline validation had passed
with zero errors. This test closes that gap by walking every body against the COMMITTED
schema capture with the same walker the preflight uses.

Ported 2026-10-10 (skipped since 2026-10-09): the builder now emits the ten v91 axes of a
CREATE stage_strategy_draft (omega.generate.StrategyPlan.axes()) and a FIELDS preview body
(preview_request()), walked here against data/contract/stage_strategy_draft/
schema_20261005T194629Z.json - the capture omega.contract.stage_schema() points at.

Pure: no network; the one file-writing test writes into tmp_path.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from omega import preflight as P
from omega.conditions import CONDITION_FIELDS, RETIRED_CONDITION_FIELDS, validate_market_read
from omega.contract import stage_schema
from omega.generate import ENTRY_MIRROR

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tpo_suite_build", ROOT / "scripts" / "tpo_suite_build.py")
builder = importlib.util.module_from_spec(spec)
# Python 3.14's dataclass resolves annotations through sys.modules[cls.__module__]; a module
# executed from a spec without being registered there makes @dataclass raise at import.
sys.modules["tpo_suite_build"] = builder
spec.loader.exec_module(builder)  # type: ignore[union-attr]

SCHEMA = stage_schema()
AXIS_SCHEMAS, SCHEMA_ROOT = P.resolve_axes(SCHEMA)
PREVIEW_ROOT = SCHEMA["preview_strategy_report"]["inputSchema"]

# The annotation keys the design record carries and no axis may.
DESIGN_ONLY = {"_what", "_provenance", "id", "thesis", "teaches", "nullExposure", "anchor",
               "predictedHeaders", "thresholds", "validation", "entryMirror", "gateMirror",
               "assumptions", "v91Mappings", "verdictResolutionNote", "coinSelection"}

BUILT = builder.build()
IDS = [b.spec["id"] for b in BUILT]


def _built(sid):
    return next(b for b in BUILT if b.spec["id"] == sid)


def _fails(findings):
    return [(f.cls, f.path, f.detail) for f in findings if f.verdict == "FAIL" or f.cls == "UNSUPPORTED"]


def _nodes(defn):
    """Every clause and group node under a definition, refs included as leaves."""
    if not isinstance(defn, dict):
        return
    yield defn
    for m in defn.get("members") or []:
        yield from _nodes(m)


def _keys_anywhere(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys_anywhere(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys_anywhere(v)


def test_every_suite_entry_validates_offline():
    for b in BUILT:
        assert not b.report_errors and not b.condition_errors, (b.spec["id"], b.report_errors, b.condition_errors)
        assert validate_market_read(b.plan.market_read_text, b.spec["conds"], b.plan.report) == []


@pytest.mark.parametrize("sid", IDS)
def test_axes_walk_clean_against_the_saved_stage_schema(sid):
    """The gate this file exists for: zero FAIL and zero UNSUPPORTED on every axis."""
    assert _fails(P.diff_axes(_built(sid).axes, AXIS_SCHEMAS, SCHEMA_ROOT)) == []


@pytest.mark.parametrize("sid", IDS)
def test_axes_are_the_ten_of_91_and_the_stage_request_walks_clean(sid):
    b = _built(sid)
    assert set(b.axes) == set(P.AXES_91)
    request = builder.stage_request(b)
    assert set(request) == {"draftVersion", "axes"} and request["draftVersion"] == 0
    assert "strategyId" not in request          # a CREATE: v85 "omit strategyId to open a NEW create draft"
    stage_root = SCHEMA["stage_strategy_draft"]["inputSchema"]
    assert _fails(P.diff_schema({"request": request}, stage_root, stage_root)) == []


@pytest.mark.parametrize("sid", IDS)
def test_axes_are_what_strategy_plan_axes_returns(sid):
    b = _built(sid)
    assert b.axes == b.plan.axes()
    assert b.preview == b.plan.preview_request()


@pytest.mark.parametrize("sid", IDS)
def test_design_only_keys_never_reach_an_axis(sid):
    b = _built(sid)
    for axis, value in b.axes.items():
        assert not (DESIGN_ONLY & set(value)), (axis, sorted(DESIGN_ONLY & set(value)))
    assert not any(k.startswith("_") for k in _keys_anywhere(b.axes))
    assert not any(k.startswith("_") for k in _keys_anywhere(b.preview))
    # and the design record is the human-facing object, carrying the port's provenance
    assert DESIGN_ONLY <= set(b.design)
    assert b.design["v91Mappings"] and "schema_20261005T194629Z" in b.design["_provenance"]


@pytest.mark.parametrize("sid", IDS)
def test_preview_body_is_a_fields_preview_of_the_same_report_and_conditions(sid):
    b = _built(sid)
    assert _fails(P.diff_schema(b.preview, PREVIEW_ROOT, PREVIEW_ROOT)) == []
    assert b.preview["coinSelection"] == {"mode": "explicit", "tickers": builder.COINS}
    src = b.preview["source"]
    assert src["kind"] == "FIELDS" and src["timeframe"] == builder.ANCHOR
    assert src["sections"] == b.axes["REPORT"]["sections"]
    assert src["conditions"] == b.axes["CONDITIONS"]["conditions"]
    assert src["marketReadText"] == b.axes["MARKET_READ"]["marketReadText"]
    assert 0 < len(src["marketReadText"]) <= 2000


@pytest.mark.parametrize("sid", IDS)
def test_conditions_carry_the_v91_grammar(sid):
    """Six keys, exitSide null (no member carried exit: true), a hold on every clause and
    group and none on a ref, and nothing the retired grammar carried."""
    for cond in _built(sid).axes["CONDITIONS"]["conditions"]:
        assert tuple(cond) == CONDITION_FIELDS, cond.keys()
        assert cond["exitSide"] is None
        assert not (set(cond) & set(RETIRED_CONDITION_FIELDS))
        for node in _nodes(cond["definition"]):
            if node["kind"] == "conditionRef":
                assert "hold" not in node
            else:
                h = node["hold"]
                assert set(h) == {"atLeast", "of"} and 1 <= h["atLeast"] <= h["of"]


def test_the_held_leg_maps_closes_2_to_hold_2_of_2_on_the_clause_and_the_join_reads_once():
    s5 = _built("S5")
    conds = {c["conditionKey"]: c for c in s5.axes["CONDITIONS"]["conditions"]}
    for key in ("RSI_HELD_UP_2C", "RSI_HELD_DOWN_2C"):
        d = conds[key]["definition"]
        assert d["kind"] == "clause" and d["column"]["header"] == "RSI14"
        assert d["hold"] == {"atLeast": builder.HELD_CLOSES, "of": builder.HELD_CLOSES} == {"atLeast": 2, "of": 2}
    for key in ("REENTRY_CONFIRMED_UP", "REENTRY_CONFIRMED_DOWN"):
        d = conds[key]["definition"]
        assert d["kind"] == "group" and d["hold"] == {"atLeast": 1, "of": 1}
        assert all(m["kind"] == "conditionRef" for m in d["members"])
    assert any("closes: 2" in m for m in s5.design["v91Mappings"])
    # no other member holds above one read, so none records the held mapping
    for b in BUILT:
        if b.spec["id"] != "S5":
            assert b.design["v91Mappings"] == builder.V91_MAPPINGS["common"]


@pytest.mark.parametrize("sid", IDS)
def test_no_custom_section_key_is_sent_on_a_create(sid):
    # Measured 2026-08-28 and 2026-09-10: CREATE refuses a caller-supplied custom sectionKey.
    for sec in _built(sid).axes["REPORT"]["sections"]:
        if sec.get("kind") == "custom":
            assert "sectionKey" not in sec, sec.keys()


@pytest.mark.parametrize("sid", IDS)
def test_entry_and_gate_are_the_mirrors_not_inventions(sid):
    axes = _built(sid).axes
    assert axes["ENTRY"] == {"entry": ENTRY_MIRROR} == {"entry": {"trigger": "ON_CANDLE_CLOSE"}}
    assert axes["SETUP_GATES"] == {**builder.GATE_MIRROR, "minAtrPct": 0.5}
    assert axes["TIMEFRAME_PROFILE"] == {"timeframe": builder.ANCHOR}
    assert all(r["allocation"] == 0 and r["required"] is False for r in axes["SIGNAL_RULES"]["rules"])
    assert len(axes["SIGNAL_RULES"]["rules"]) == 84


@pytest.mark.parametrize("sid", IDS)
def test_identity_strings_respect_the_local_caps(sid):
    ident = _built(sid).axes["IDENTITY"]
    assert ident["name"].startswith("OMEGA-TEST: ") and len(ident["name"]) <= 50
    assert 0 < len(ident["tagline"]) <= 80 and not ident["tagline"].endswith(" ")
    assert 0 < len(ident["description"]) <= 500


def test_conditions_are_directional_first():
    """Kept from the 54.1.0 design: UP/DOWN carriers first, then verdict-null building blocks,
    then NEITHER tags. Since 56.1.0 the order only names the decider among AGREEING carriers
    (disagreeing carriers resolve NEITHER regardless of order) - the builder records that on
    every design record rather than pretending the order still prevents masking."""
    rank = {"UP": 0, "DOWN": 0, None: 1, "NEITHER": 2}
    for b in BUILT:
        ranks = [rank.get(c.get("verdict"), 1) for c in b.spec["conds"]]
        assert ranks == sorted(ranks), (b.spec["id"], [c.get("verdict") for c in b.spec["conds"]])
        assert "56.1.0" in b.design["verdictResolutionNote"]


def test_main_writes_design_stage_and_preview_per_member_and_a_manifest(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(builder, "OUT", str(tmp_path))
    assert builder.main() == 0
    assert "total errors: 0" in capsys.readouterr().out
    manifest = json.loads((tmp_path / "_manifest.json").read_text(encoding="utf-8"))
    assert [m["id"] for m in manifest["suite"]] == IDS and manifest["totalErrors"] == 0
    for m in manifest["suite"]:
        design = json.loads((tmp_path / m["design"]).read_text(encoding="utf-8"))
        stage = json.loads((tmp_path / m["stage"]).read_text(encoding="utf-8"))
        preview = json.loads((tmp_path / m["preview"]).read_text(encoding="utf-8"))
        assert design["id"] == m["id"] and design["_what"].startswith("DESIGN RECORD")
        assert stage == builder.stage_request(_built(m["id"]))
        assert preview == _built(m["id"]).preview
