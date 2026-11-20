"""OMEGA v0.16.0: the re-extraction at contract 182.3.2, replayed against its live record.

Record: data/audit/reextraction_182_2026-11-20.json (previews A1 - A7, B, C, D, H1 - H8, V182, TF; drafts E, L and the
side sweep S; the stage-and-discard proof). Plan: docs/plans/2026-11-20-omega-reextraction-182.md.
"""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import get_args

import pytest

from omega.contract import REFERENCE_PRICES, load, price_operand_refused, stage_schema
from omega.fanout import outputs_for
from omega.types import Column
from omega.validate import validate_column

ROOT = Path(__file__).resolve().parents[1]
RECORD = json.loads((ROOT / "data" / "audit" / "reextraction_182_2026-11-20.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "data" / "contract" / "_manifest.json").read_text(encoding="utf-8"))
MOVES = json.loads((ROOT / "data" / "contract" / "metrics" / "_moves_182.json").read_text(encoding="utf-8"))
P = RECORD["previews"]
DRAFTS = RECORD["drafts"]
L_STAGES = {s["id"]: s for s in DRAFTS["L"]["stages"]}
E_STAGES = {s["id"]: s for s in DRAFTS["E"]["stages"]}
L_LEVELS = {(t["id"], t["coinTicker"]): t["answer"] for t in DRAFTS["L"]["tradeLevels"]}
SCHEMA_180_4 = ROOT / "data/contract/stage_strategy_draft/schema_20261119T202415Z.json"


def _errors(column: Column):
    return [f for f in validate_column(column) if f.severity == "error"]


def _refused(preview: dict) -> dict | None:
    return preview["answer"]["refusal"]


def _sent(preview: dict) -> list[Column]:
    return [Column.model_validate(c) for c in preview["sent"]["columns"]]


# --- the extraction -------------------------------------------------------------------------------------------------
def test_the_extraction_and_the_write_surface_are_182_3_2():
    from tests.manifest_chain import versions
    assert versions(MANIFEST)[:2] == ["182.3.2", "180.4.0"]
    assert versions(MANIFEST["writeSurface"])[:2] == ["182.3.2", "180.4.0"]
    assert MANIFEST["writeSurface"]["buildSha"] == RECORD["buildSha"]
    assert stage_schema()["contractVersion"] == RECORD["contractVersion"] == "182.3.2"
    index = json.loads((ROOT / "data/contract/metrics/_index.json").read_text(encoding="utf-8"))
    assert (index["contractVersion"], index["buildSha"], index["metricCount"]) == ("182.3.2", RECORD["buildSha"], 586)
    assert 'version = "0.16.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_the_six_draft_tools_moved_in_one_output_schema_and_no_input():
    """180.4.0 -> 182.3.2: preview_strategy_report's output schema (README v182) and nothing else - no description,
    no input schema. v181 moved no schema."""
    old = json.loads(SCHEMA_180_4.read_text(encoding="utf-8"))
    new = stage_schema()
    tools = MANIFEST["writeSurface"]["tools"]
    moved = {(t, part) for t in tools for part in ("description", "inputSchema", "outputSchema", "annotations")
             if old[t].get(part) != new[t].get(part)}
    assert moved == {("preview_strategy_report", "outputSchema")}
    out_old = old["preview_strategy_report"]["outputSchema"]["properties"]
    out_new = new["preview_strategy_report"]["outputSchema"]["properties"]

    def outcome(props):
        return props["authoring"]["anyOf"][0]["properties"]["conditionOutcomes"]["items"]["properties"]["outcomes"]["items"]
    assert "developingRead" in outcome(out_old)["properties"] and "developingRead" in outcome(out_old)["required"]
    assert "developingRead" not in outcome(out_new)["properties"]
    assert "developingAsOf" in outcome(out_new)["properties"] and "developingAsOf" in outcome(out_new)["required"]

    def column(props):
        return props["renderedSections"]["items"]["oneOf"][0]["properties"]["section"]["properties"]["columns"]["items"]
    assert "asOf" not in column(out_old)["properties"]
    assert "asOf" in column(out_new)["properties"] and "asOf" not in column(out_new).get("required", [])


def test_the_other_authoring_tools_are_captured_from_this_contract_on():
    import scripts.capture_write_surface as cws
    block = MANIFEST["writeSurface"]["authoringTools"]
    side = json.loads((ROOT / block["schema"]).read_text(encoding="utf-8"))
    assert (side["contractVersion"], side["buildSha"]) == ("182.3.2", RECORD["buildSha"])
    assert side["beside"] == Path(MANIFEST["writeSurface"]["schema"]).name and side["_absent"] == []
    assert set(side["tools"]) == set(cws.AUTHORING_TOOLS)
    for tool in side["tools"].values():
        assert tool["description"] and tool["inputSchema"]["type"] == "object"
    # the three statements 182.3.x added to the trade level preview's description, each measured below
    text = side["tools"]["preview_strategy_trade_levels"]["description"]
    for phrase in ("an ATR option's own multiple; bounds are inclusive", "stated to three decimals",
                   "distancePct, distanceAtr", "validForMinutes"):
        assert phrase in text


def test_the_sidecar_refuses_a_list_that_is_not_the_capture_it_sits_beside():
    import scripts.capture_write_surface as cws
    from datetime import UTC, datetime
    version = {"contractVersion": "182.3.2", "buildSha": "b" * 40}
    tools = [{"name": n, "description": f"d-{n}", "inputSchema": {"type": "object"}, "outputSchema": {}}
             for n in cws.TOOLS + cws.AUTHORING_TOOLS[:-1]]
    beside = {**version, **{t["name"]: {k: t[k] for k in cws.PARTS} for t in tools if t["name"] in cws.TOOLS}}
    at = datetime(2026, 11, 20, 16, 30, tzinfo=UTC)
    side = cws.authoring_tools(version=version, raw=b"x", tools=tools, listed_at=at, beside=beside,
                               beside_name="schema_a.json")
    assert side["beside"] == "schema_a.json" and side["_absent"] == [cws.AUTHORING_TOOLS[-1]]
    assert set(side["tools"]) == set(cws.AUTHORING_TOOLS[:-1])
    moved = {**beside, "get_strategy": {**beside["get_strategy"], "description": "other"}}
    with pytest.raises(SystemExit, match="differ from schema_a.json"):
        cws.authoring_tools(version=version, raw=b"x", tools=tools, listed_at=at, beside=moved,
                            beside_name="schema_a.json")
    with pytest.raises(SystemExit, match="not the same surface"):
        cws.authoring_tools(version=version, raw=b"x", tools=tools, listed_at=at,
                            beside={**beside, "buildSha": "c" * 40}, beside_name="schema_a.json")
    own = cws.authoring_tools(version=version, raw=b"x", tools=tools, listed_at=at)
    assert own["beside"] == "schema_20261120T163000Z.json"


def _stubbed_capture(monkeypatch, tmp_path, versions=None):
    """scripts.capture_write_surface with the network stubbed out: read_version and list_surface answer from memory
    and OUT_DIR is a temporary directory. -> (the module, the listed bytes, the calls made)."""
    import scripts.capture_write_surface as cws
    version = {"contractVersion": "182.3.2", "buildSha": "b" * 40}
    tools = [{"name": n, "description": f"d-{n}", "inputSchema": {"type": "object"}, "outputSchema": {},
              "annotations": {"readOnlyHint": True}} for n in cws.TOOLS + cws.AUTHORING_TOOLS]
    raw = json.dumps({"tools": tools}).encode("utf-8")
    answers = iter(versions) if versions is not None else None
    calls: list[str] = []

    def read_version():
        calls.append("version")
        return dict(next(answers)) if answers is not None else dict(version)

    def list_surface():
        calls.append("list")
        return raw, tools
    monkeypatch.setattr(cws, "read_version", read_version)
    monkeypatch.setattr(cws, "list_surface", list_surface)
    monkeypatch.setattr(cws, "OUT_DIR", tmp_path)
    monkeypatch.delenv("MANAGER_ROW", raising=False)
    return cws, raw, calls


def test_the_default_run_writes_the_capture_and_its_sidecar(monkeypatch, tmp_path, capsys):
    """main() with no argument: one list -> schema_<stamp>.json AND authoring_tools_<stamp>.json. Through v0.16.0's
    first pass the sidecar was built in the --authoring-only branch alone, so this run wrote the schema and died on
    an unbound name (review 2026-11-20, finding 1)."""
    import hashlib
    cws, raw, calls = _stubbed_capture(monkeypatch, tmp_path)
    assert cws.main([]) == 0
    assert calls == ["version", "list", "version"]
    [schema] = sorted(tmp_path.glob("schema_*.json"))
    [side] = sorted(tmp_path.glob("authoring_tools_*.json"))
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([schema.name, side.name])
    assert schema.name.removeprefix("schema_") == side.name.removeprefix("authoring_tools_")
    doc, sidecar = (json.loads(p.read_text(encoding="utf-8")) for p in (schema, side))
    digest = hashlib.sha256(raw).hexdigest()
    assert doc["liveListSha256"] == sidecar["liveListSha256"] == digest
    assert (sidecar["contractVersion"], sidecar["buildSha"]) == (doc["contractVersion"], doc["buildSha"])
    assert sidecar["beside"] == schema.name and schema.name in sidecar["readFrom"]
    assert sidecar["_absent"] == [] and set(sidecar["tools"]) == set(cws.AUTHORING_TOOLS)
    assert doc["_absent"] == [] and all(t in doc for t in cws.TOOLS) and doc["managerRowAgrees"] is None
    assert sidecar["tools"]["discard_strategy_draft"] == {
        "description": "d-discard_strategy_draft", "inputSchema": {"type": "object"}, "outputSchema": {},
        "annotations": {"readOnlyHint": True}}
    out = capsys.readouterr().out
    assert schema.name in out and side.name in out and "10 of 10 authoring tools" in out


def test_the_authoring_only_run_writes_the_sidecar_alone_beside_a_capture(monkeypatch, tmp_path, capsys):
    cws, raw, calls = _stubbed_capture(monkeypatch, tmp_path)
    assert cws.main([]) == 0
    [schema] = sorted(tmp_path.glob("schema_*.json"))
    captured = schema.read_bytes()
    for old in tmp_path.glob("authoring_tools_*.json"):
        old.unlink()
    capsys.readouterr()
    assert cws.main(["--authoring-only", schema.name]) == 0
    assert calls == ["version", "list", "version"] * 2
    assert [p.name for p in tmp_path.glob("schema_*.json")] == [schema.name] and schema.read_bytes() == captured
    [side] = sorted(tmp_path.glob("authoring_tools_*.json"))
    sidecar = json.loads(side.read_text(encoding="utf-8"))
    assert sidecar["beside"] == schema.name and "a later list than" in sidecar["readFrom"]
    assert set(sidecar["tools"]) == set(cws.AUTHORING_TOOLS) and sidecar["_absent"] == []
    assert f"beside {schema.name}" in capsys.readouterr().out
    # a capture of another build is refused and nothing more is written
    other = tmp_path / "schema_other.json"
    other.write_text(json.dumps({**json.loads(captured), "buildSha": "c" * 40}), encoding="utf-8")
    before = sorted(p.name for p in tmp_path.iterdir())
    with pytest.raises(SystemExit, match="not the same surface"):
        cws.main(["--authoring-only", other.name])
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_a_contract_that_moves_during_the_list_writes_nothing(monkeypatch, tmp_path):
    moved = [{"contractVersion": "182.3.2", "buildSha": "b" * 40}, {"contractVersion": "182.4.0", "buildSha": "d" * 40}]
    cws, _, calls = _stubbed_capture(monkeypatch, tmp_path, versions=moved)
    with pytest.raises(SystemExit, match="the contract moved during the list"):
        cws.main([])
    assert calls == ["version", "list", "version"] and list(tmp_path.iterdir()) == []


# --- v181, served: the hints carry the rule -------------------------------------------------------------------------
def test_the_hints_list_no_reference_price_for_a_base_that_is_not_one():
    c = load()
    assert REFERENCE_PRICES == ("CLOSE", "LAST")
    price = [m for m in c.metrics.values() if m.unit == "price"]
    others = [m for m in price if m.metric not in REFERENCE_PRICES]
    assert (len(price), len(others)) == (418, 416) == (MOVES["priceBases"], MOVES["recordsMoved"])
    for m in c.metrics.values():
        if m.metric in REFERENCE_PRICES:
            continue
        for served in (m.spread_operands, m.spread_operands_off_anchor or ()):
            assert not set(REFERENCE_PRICES) & set(served), m.metric
        for spec in m.transforms.values():
            for outer in (spec.get("chainedOuters") or {}).values():
                for key in ("operands", "operandsOffAnchor"):
                    assert not set(REFERENCE_PRICES) & set(outer.get(key) or ()), (m.metric, key)
    close, last = c.metrics["CLOSE"], c.metrics["LAST"]
    assert "LAST" in close.spread_operands and "CLOSE" in last.spread_operands
    assert "LAST" in close.spread_operands_off_anchor and "CLOSE" in last.spread_operands_off_anchor
    # an average of price stays an operand of every price base (README v181: the averaged lists are unchanged)
    assert all("CLOSE" in m.spread_average_operands for m in price)
    # and CLOSE's own averages keep LAST: the base decides, averaged or not
    assert sorted(t for t, spec in close.transforms.items()
                  if "LAST" in ((spec.get("chainedOuters") or {}).get("spread") or {}).get("operands", ())) == [
        "aggregate", "ema", "rma", "wma"]
    assert MOVES["anythingElseMoved"] == [] and MOVES["movedAreThePriceBasesThatAreNotReferencePrices"] is True
    assert MOVES["operandLists"]["plainListsOfTheBase"]["removed"] == {
        "spreadOperands": {"CLOSE": 416, "LAST": 416}, "spreadOperandsOffAnchor": {"CLOSE": 416, "LAST": 416}}
    # the served text names the reference prices
    authoring = json.loads((ROOT / "data/contract/transforms/_authoring.json").read_text(encoding="utf-8"))
    assert "never a reference price (CLOSE, LAST) unless the base is one" in (
        authoring["transforms"]["spread"]["parameters"]["inputs"]["description"])


@pytest.mark.parametrize("key", ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "H4", "H5", "H7"])
def test_the_refused_forms_are_refused_live_and_by_omega(key):
    """Each is REPORT_COLUMN_OPERAND_UNSUPPORTED on the platform, naming the form to write where the server admits it
    at the column's rung; omega refuses the same column from extracted data and names a form in the same cases."""
    refusal = _refused(P[key])
    assert refusal["code"] == "VALIDATION_ERROR" and refusal["authoringCode"] == "REPORT_COLUMN_OPERAND_UNSUPPORTED"
    assert refusal["receivedValue"] in REFERENCE_PRICES and "is a reference price" in refusal["message"]
    assert refusal["path"] == ["sections", 0, "columns", 0, "inputs", 0, "metric"]
    [column] = _sent(P[key])
    found = [f for f in _errors(column) if f.code == "OPERAND_NOT_ALLOWED"]
    assert len(found) == 1 and "v181" in found[0].message
    platform_names_a_form = "; write " in refusal["message"]
    assert platform_names_a_form == ("Write " in found[0].message), (refusal["message"], found[0].message)
    assert platform_names_a_form == (key not in ("A6", "A7"))
    if platform_names_a_form:
        # the same form, in the platform's spelling (x for the multiplication sign, `{ metric: ... }` spaced)
        written = refusal["message"].split("; write ", 1)[1].replace("×", "x")
        ours = found[0].message.split("Write ", 1)[1].split(": price is the base", 1)[0]
        assert written.replace("{ ", "{").replace(" }", "}") == ours


def test_the_refusal_names_the_operands_it_admits_and_no_reference_price():
    domain = _refused(P["A1"])["allowedDomain"]
    assert domain["kind"] == "enum" and domain["holds"]["CLOSE"] is False and domain["holds"]["LAST"] is False
    assert all(domain["holds"][k] for k in ("MARK", "ORACLE", "OPEN", "HIGH", "LOW", "HL2", "HLC3", "OHLC4", "EMA20"))
    assert domain["count"] == len(load().metrics["PRIOR_TPO_VAL"].spread_operands)


def test_the_reference_prices_are_close_and_last_and_no_other_price():
    """B: every other price renders as EMA20's plain operand. D: every other price is refused as the base of a spread
    over CLOSE - it is "another reading", not a reference price."""
    assert set(P["B"]["cases"]) == {"MARK", "ORACLE", "OPEN", "HIGH", "LOW", "HL2", "HLC3", "OHLC4", "SPOT_CLOSE_CB",
                                    "SPOT_CLOSE_BN"}
    for operand, preview in P["B"]["cases"].items():
        assert _refused(preview) is None, operand
        [column] = _sent(preview)
        assert not _errors(column) and not price_operand_refused("EMA20", operand)
        assert [o.header for o in outputs_for(column)] == [c["key"] for c in preview["answer"]["columns"]]
    assert set(P["D"]["cases"]) == {"MARK", "ORACLE", "OPEN", "HIGH", "LOW", "HL2"}
    for base, preview in P["D"]["cases"].items():
        assert _refused(preview)["authoringCode"] == "REPORT_COLUMN_OPERAND_UNSUPPORTED", base
        assert f"write CLOSE × spread({base})" in _refused(preview)["message"]
        [column] = _sent(preview)
        assert [f.code for f in _errors(column)] == ["OPERAND_NOT_ALLOWED"] and price_operand_refused(base, "CLOSE")


@pytest.mark.parametrize("key", ["C", "H1", "H2", "H3", "H8", "COV"])
def test_the_kept_forms_render_and_omega_predicts_their_headers(key):
    """C: two reference prices in both orders, an averaged price operand, price as the base. H1 - H3: CLOSE's own
    averages spread against LAST, on and off the anchor - the form v0.15.0 refused on the README's one example. COV:
    the same four chains as omega.space writes them, the shapes the coverage ledger now holds."""
    preview = P[key]
    assert _refused(preview) is None
    rendered = [c["key"] for c in preview["answer"]["columns"]]
    predicted = []
    for column in _sent(preview):
        assert not _errors(column), column
        predicted += [o.header for o in outputs_for(column)]
    assert predicted == rendered
    if key == "H1":
        assert rendered == ["close_ema34_last_spread"]
    if key == "COV":
        from scripts.render_coverage import CACHE, SEEN_FILES
        assert rendered == ["close_mean24_last_spread", "close_ema20_last_spread", "close_rma14_last_spread",
                            "close_wma20_last_spread"]
        assert "_probe_182_2026-11-20.json" in SEEN_FILES
        assert set(rendered) <= set(json.loads((CACHE / "_probe_182_2026-11-20.json").read_text(
            encoding="utf-8"))["headers"])
    if key == "C":
        assert rendered[:2] == ["close_last_spread", "last_close_spread"]


def test_a_chain_after_a_reference_price_spread_is_refused_for_its_own_reason():
    """H6: CLOSE x spread(LAST) -> trajectory is no chain (LAST has no per-bar value); not the v181 refusal."""
    refusal = _refused(P["H6"])
    assert refusal["authoringCode"] == "REPORT_COLUMN_CHAIN_UNSUPPORTED" and "no per-bar value" in refusal["message"]
    column = _sent(P["H6"])[1]
    assert _errors(column) and not any("v181" in f.message for f in _errors(column))


def test_no_enumerated_shape_is_one_the_platform_refused():
    from omega.space import enumerate_shapes
    shapes = enumerate_shapes(expand_operands=True)
    assert len(shapes) == MANIFEST["counts"]["operandExpandedShapes"] == 515965
    held = {(s.metric, s.transform, s.chained, s.operand) for s in shapes if s.operand in REFERENCE_PRICES}
    assert ("CLOSE", "ema", "spread", "LAST") in held and ("CLOSE", "spread", None, "LAST") in held
    assert ("LAST", "spread", None, "CLOSE") in held
    assert all(metric in REFERENCE_PRICES for metric, *_ in held)
    assert len(enumerate_shapes()) == MANIFEST["counts"]["structuralShapes"] == 27424


# --- v182: a Developing read states when it was read ------------------------------------------------------------------
def test_an_outcome_states_developing_as_of_and_the_inventory_keeps_developing_read():
    answer = P["V182"]["answer"]
    assert "developingAsOf" in answer["outcomeKeys"] and "developingRead" not in answer["outcomeKeys"]
    assert "developingRead" in answer["inventoryOutputKeys"]
    inventory = {o["header"]: o["developingRead"] for o in answer["inventory"]}
    assert inventory == {"RSI14_4h_dev": True, "RSI14_4h": False, "RSI14": False, "chg4h": True,
                         "quoteVol_4h_dev": True}
    for coin in answer["conditionOutcomes"]:
        by_key = {o["conditionKey"]: o for o in coin["outcomes"]}
        assert not any(o["hasDevelopingRead"] for o in coin["outcomes"])
        assert by_key["DEV_UP"]["developingAsOf"] and by_key["DEV_DOWN"]["developingAsOf"]
        assert by_key["CLOSED_HTF"]["developingAsOf"] is None and by_key["ANCHOR_ONLY"]["developingAsOf"] is None
        # narrower than the flag it replaced: a fixed-horizon change is provisional and read no bar in progress
        assert by_key["HORIZON"]["developingAsOf"] is None and by_key["HORIZON"]["provisional"] is True
    columns = {c["key"]: c for c in answer["columns"]}
    assert {k for k, c in columns.items() if "asOf" in c} == {"RSI14_4h_dev", "quoteVol_4h_dev"}
    assert columns["RSI14_4h_dev"]["bars"] == "Developing" and columns["RSI14_4h"]["bars"] == "Confirmed"


def test_omega_reads_no_condition_outcome():
    """v182 removed an OUTPUT field; nothing in omega/ reads an outcome, so nothing broke."""
    for path in sorted((ROOT / "omega").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "conditionOutcomes" not in text and "developingAsOf" not in text, path.name


# --- the nine main candles ---------------------------------------------------------------------------------------------
def test_the_rungs_at_the_nine_main_candles_are_recorded_and_omega_keeps_its_four():
    from omega.generate import REGIME_TF_FOR_ANCHOR
    from omega.types import ANCHOR_TIMEFRAMES
    anchors = P["TF"]["anchors"]
    assert list(anchors) == ["5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d"]
    assert {a: v["regime"] for a, v in anchors.items()} == {
        "5m": "15m", "15m": "1h", "30m": "2h", "1h": "4h", "2h": "8h", "4h": "12h", "8h": "1d", "12h": "1w", "1d": "1w"}
    assert {a: v["lower"] for a, v in anchors.items()} == {
        "5m": "1m", "15m": "5m", "30m": "15m", "1h": "30m", "2h": "1h", "4h": "2h", "8h": "4h", "12h": "8h", "1d": "12h"}
    shared = json.loads((ROOT / "data/contract/vocabulary/_shared.json").read_text(encoding="utf-8"))
    refs = {r["rel"]: r["resolvedByAnchor"] for r in shared["timeframeRefs"]}
    assert refs["lower"] == {a: v["lower"] for a, v in anchors.items()}       # the lower rung is served; measured equal
    assert set(refs["regime"].values()) == {None}                              # the regime rung is not: measured only
    assert shared["timeframes"] == list(anchors)
    assert set(get_args(ANCHOR_TIMEFRAMES)) == set(REGIME_TF_FOR_ANCHOR) == {"5m", "15m", "1h", "4h"} < set(anchors)
    assert REGIME_TF_FOR_ANCHOR == {a: anchors[a]["regime"] for a in REGIME_TF_FOR_ANCHOR}
    assert set(P["TF"]["refused"]) == {"1m", "3m", "3d", "1w"}
    assert {r["authoringCode"] for r in P["TF"]["refused"].values()} == {"REPORT_TIMEFRAME_NOT_AUTHORABLE"}


def test_the_headers_are_the_same_at_every_main_candle():
    columns = [Column.model_validate(c) for c in P["TF"]["columnsSent"]]
    predicted = [o.header for column in columns for o in outputs_for(column)]
    for anchor, answer in P["TF"]["anchors"].items():
        assert list(answer["headers"]) == predicted, anchor
        assert answer["headers"]["RSI14"] == answer["headers"]["atrPct"] == anchor
        assert answer["headers"]["close_htf_EMA20_spread"] == answer["regime"]


# --- the trade level preview: bounds, R:R, the level entry ------------------------------------------------------------
@pytest.mark.parametrize("coin", ["BTC", "ETH", "SOL"])
def test_the_stop_range_bounds_are_inclusive_and_judged_on_the_multiple(coin):
    from omega.trade_levels import STOP_RANGE_VERDICTS, outside_stop_range
    answer = L_LEVELS[("LG1", coin)]
    for side in ("LONG", "SHORT"):
        assert answer[side]["range"] == [0.8, 1.8]
        stops = answer[side]["stops"]
        assert [s["atrMultiple"] for s in stops] == [0.5, 0.79, 0.8, 1, 1.5, 1.8, 1.81, 2]
        for s in stops:
            verdict = outside_stop_range(s["atrMultiple"], 0.8, 1.8)
            assert s["verdict"] == (verdict or "SURVIVED"), (coin, side, s)
            assert s["responsibleBound"] == STOP_RANGE_VERDICTS.get(verdict)
            assert s["distanceAtrMultiple"] == s["atrMultiple"]
        assert answer[side]["counters"]["stopsRemovedByFloor"] == answer[side]["counters"]["stopsRemovedByCeiling"] == 2


def test_a_stop_at_the_bound_survives_where_its_percent_distance_rounds_outside_it():
    """SOL, 2026-11-20: the 0.8 stop's distance in percent is BELOW the floor's and the 1.8 stop's ABOVE the ceiling's,
    by floating-point rounding, and both survive - the stop is judged on its own multiple."""
    side = L_LEVELS[("LG1", "SOL")]["LONG"]
    stops = {s["atrMultiple"]: s for s in side["stops"]}
    assert stops[0.8]["distancePct"] < side["stopBand"]["requestedMinPct"] and stops[0.8]["verdict"] == "SURVIVED"
    assert stops[1.8]["distancePct"] > side["stopBand"]["requestedMaxPct"] and stops[1.8]["verdict"] == "SURVIVED"


def _menu_errors(stage: dict):
    from omega.trade_levels import validate_menu
    policy = stage["sent"]["TRADE_LEVEL_POLICY"]
    dials = {k: v for k, v in policy.items() if k != "tradeLevelMenu"}
    return [f for f in validate_menu(policy["tradeLevelMenu"], dials=dials, sections=[], anchor="1h",
                                     trailing_enabled=True) if f.severity == "error"]


@pytest.mark.parametrize("stage, pays", [("G2", "1.4996"), ("G3", "1.4995"), ("G4", "1.49949"), ("G5", "1.4996"),
                                         ("G6", "1.4994"), ("G7", "2.2496"), ("G8", "2.2494")])
def test_the_minimum_risk_reward_is_judged_at_three_decimals(stage, pays):
    _replay_rr(L_STAGES[stage], pays)


def _replay_rr(stage: dict, pays: str) -> bool:
    """One staged R:R case against omega: the plan pays `pays` exactly as written; the platform's verdict, the field
    it names and its "pays ...R" text are omega's. -> whether the stage accepted the plan."""
    from omega.trade_levels import plan_pays_double, plan_pays_exact, stated_rr
    sent = stage["sent"]["TRADE_LEVEL_POLICY"]
    plan = sent["tradeLevelMenu"]["LONG"]["exitPlans"][1]["targets"]
    assert plan_pays_exact(plan) == Fraction(pays)
    platform = list(stage["answer"]["errors"])
    ours = _menu_errors(stage)
    stated = stated_rr(plan_pays_double(plan))
    below = stated < Fraction(str(sent["minRiskRewardRatio"]))
    assert bool(platform) == bool(ours) == below, (stage["id"], platform, ours)
    if platform:
        assert platform[0]["field"] == "tradeLevelMenu.LONG.exitPlans[1]" == ours[0].path
        assert f"pays {float(stated):g}R" in platform[0]["message"]
        assert f"pays {float(stated):g}R" in ours[0].message
        assert ours[0].code == "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR"
    return not platform


# --- the minimum risk-reward AT the tie (the review-fix draft, 18:40 - 18:43Z) --------------------------------------
TIES = RECORD["ties"]
TIE_STAGES = {s["id"]: s for s in TIES["stages"]}
TIE_LEVELS = {t["id"]: t["answer"] for t in TIES["tradeLevels"]}
TIE_CASES = [  # (stage, the pay exactly as written, accepted by the stage)
    ("K1", "2.2496", True), ("K2", "2.2494", False), ("K3", "1.4995", True),
    ("A", "2.2495", True), ("B", "2.4995", True), ("D6", "2.7495", True), ("D7", "2.9995", True), ("D8", "0.4995", True),
    ("C", "1.4995", True), ("D1", "1.4995", False), ("D2", "1.4995", True), ("D3", "2.2495", True),
    ("D4", "0.9995", True), ("D5", "2.7495", False)]


@pytest.mark.parametrize("stage, pays, accepted", TIE_CASES)
def test_the_minimum_risk_reward_at_an_exact_tie(stage, pays, accepted):
    """Each case as the platform answered it: a single leg at the tie passes whichever side of the tie its double
    lies on; two legs follow the floating-point sum of R x (closePct / 100) - D1 and D5 pay the tie exactly as
    written and are refused. A case that staged clean was previewed: every pair survives, stated at the minimum."""
    from omega.trade_levels import rr_tie_unmeasured, validate_menu
    record = TIE_STAGES[stage]
    assert _replay_rr(record, pays) is accepted
    policy = record["sent"]["TRADE_LEVEL_POLICY"]
    minimum = policy["minRiskRewardRatio"]
    assert record["answer"]["warnings"] == []
    # one or two legs closing 100% is the shape measured at a tie: no "not measured" warning beside the verdict
    assert not rr_tie_unmeasured(policy["tradeLevelMenu"]["LONG"]["exitPlans"][1]["targets"], minimum)
    assert not [f for f in validate_menu(policy["tradeLevelMenu"], dials={"minRiskRewardRatio": minimum}, sections=[],
                                         anchor="1h", trailing_enabled=True) if f.severity == "warning"]
    assert (f"L{stage}" in TIE_LEVELS) is accepted
    if accepted:
        for side in ("LONG", "SHORT"):
            answer = TIE_LEVELS[f"L{stage}"][side]
            assert answer["stage"] == "OK" and answer["entry"] is None and answer["minRiskRewardRatio"] == minimum
            assert answer["rejectedPairs"] == [] and answer["pairsRemovedByRiskReward"] == 0
            assert len(answer["setups"]) == 4 and {s["riskRewardRatio"] for s in answer["setups"]} == {minimum}
    else:
        tie = f"{float(Fraction(str(minimum)) - Fraction(1, 1000)):g}"
        assert f"The LONG exit plan pays {tie}R, below this strategy's minimum risk-reward of {minimum:g}" in (
            record["answer"]["errors"][0]["message"])


def test_what_the_tie_cases_rule_out():
    """The readings of the pay that the measured ties refuse, each on the cases that refuse it."""
    import math
    from omega.trade_levels import plan_pays_double, plan_pays_exact, stated_rr

    def case(stage):
        policy = TIE_STAGES[stage]["sent"]["TRADE_LEVEL_POLICY"]
        legs = [(t["method"]["multiple"], t["closePct"])
                for t in policy["tradeLevelMenu"]["LONG"]["exitPlans"][1]["targets"]]
        return legs, Fraction(str(policy["minRiskRewardRatio"])), not TIE_STAGES[stage]["answer"]["errors"]

    def half_up(value: Fraction) -> Fraction:
        return Fraction(math.floor(value * 1000 + Fraction(1, 2)), 1000)

    def verdicts(reading):
        return {stage: reading(case(stage)[0]) >= case(stage)[1] for stage, _, _ in TIE_CASES}
    measured = {stage: accepted for stage, _, accepted in TIE_CASES}
    assert measured == {stage: case(stage)[2] for stage in measured}

    def wrong(reading):
        return sorted(s for s, v in verdicts(reading).items() if v != measured[s])
    # v0.16.0's first pass: the exact decimal pay, a half up
    assert wrong(lambda legs: half_up(sum(Fraction(str(r)) * p for r, p in legs) / 100)) == ["D1", "D5"]
    # binary doubles, the sum divided once
    assert wrong(lambda legs: stated_rr(sum(r * p for r, p in legs) / 100)) == ["C", "D2", "D5"]
    # binary doubles, each product divided
    assert wrong(lambda legs: stated_rr(sum(r * p / 100 for r, p in legs))) == ["D2", "D5"]
    # the double's own value rounded to three decimals (not its product with 1000)
    assert wrong(lambda legs: half_up(Fraction(sum(r * (p / 100) for r, p in legs)))) == [
        "A", "B", "D3", "D6", "D7", "D8"]
    # the reading omega holds: every case
    assert wrong(lambda legs: stated_rr(sum(r * (p / 100) for r, p in legs))) == []
    for stage in measured:
        legs = TIE_STAGES[stage]["sent"]["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]["LONG"]["exitPlans"][1]["targets"]
        assert plan_pays_double(legs) == sum(r * (p / 100) for r, p in case(stage)[0])
    # D1: 1.4995 as written, a unit in the last place under it as summed
    d1 = TIE_STAGES["D1"]["sent"]["TRADE_LEVEL_POLICY"]["tradeLevelMenu"]["LONG"]["exitPlans"][1]["targets"]
    assert plan_pays_exact(d1) == Fraction("1.4995") and plan_pays_double(d1) == 1.4994999999999998
    # the single legs under 2.25 .. 3 and 0.5: the double lies below the tie, and its product with 1000 is the half
    for stage in ("A", "B", "D6", "D7", "D8"):
        [(r, _)] = case(stage)[0]
        assert Fraction(r) < Fraction(str(r)) and Fraction(r * 1000) == Fraction(str(r)) * 1000
    [(r, _)] = case("K3")[0]
    assert Fraction(r) > Fraction(str(r))                    # 1.4995, the one tie drafts E and L staged


def test_a_tie_through_an_unmeasured_sum_warns():
    """A runner's share, or more than two closing legs, at the exact tie: the stage's verdict is not measured, and
    omega says so beside its own reading."""
    from omega.trade_levels import rr_tie_unmeasured, validate_menu

    def menu(*legs):
        side = {"stops": [{"kind": "ATR", "atrMultiple": 1}],
                "exitPlans": [{"targets": [{"method": {"kind": "R_MULTIPLE", "multiple": r}, "closePct": pct}
                                           for r, pct in legs]}]}
        return {"LONG": side, "SHORT": json.loads(json.dumps(side))}

    def found(minimum, *legs):
        return [(f.severity, f.code, f.path) for f in validate_menu(
            menu(*legs), dials={"minRiskRewardRatio": minimum}, sections=[], anchor="1h", trailing_enabled=True)
            if f.path.startswith("tradeLevelMenu.LONG")]
    warning = ("warning", "TRADE_MENU_EXIT_PLAN_RR_TIE_UNMEASURED", "tradeLevelMenu.LONG.exitPlans[0]")
    assert found(2.25, (2.2495, 50)) == [warning]                              # a 50% runner riding at 2.2495R
    assert found(1.5, (1, 30), (1.5, 30), (1.87375, 40)) == [warning]          # three legs paying 1.4995
    # two legs and a 20% runner at 1.999R: omega's own order of the sum falls under the tie, so it refuses the plan
    # (as v0.15.0 did on the exact pay) and says beside it that the stage's verdict there is not measured
    error = ("error", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR", "tradeLevelMenu.LONG.exitPlans[0]")
    assert found(1.5, (1, 50), (1.999, 30)) == [error, warning]
    assert found(1.5, (1, 50), (1.999, 30), (6, 0)) == [error, warning]        # the same under a trail objective
    # the shapes measured at a tie, and anything off the tie: no warning
    assert found(1.5, (1, 50), (1.999, 50)) == [] and found(2.25, (2.2495, 100)) == []
    assert found(2.25, (2.25, 50)) == [] and found(1.5, (1, 30), (1.5, 30), (1.9, 40)) == []
    # below the minimum AND at no tie: the error alone
    assert found(1.5, (1, 30), (1.5, 30), (1.8, 40)) == [
        ("error", "TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR", "tradeLevelMenu.LONG.exitPlans[0]")]
    legs = menu((2.2495, 50))["LONG"]["exitPlans"][0]["targets"]
    assert rr_tie_unmeasured(legs, 2.25) and not rr_tie_unmeasured(legs, 2.5)
    assert not rr_tie_unmeasured(legs, None) and not rr_tie_unmeasured(legs, float("nan"))
    assert not rr_tie_unmeasured([{"method": {"kind": "LEVEL", "level": {}}, "closePct": 100}], 2.25)
    [message] = [f.message for f in validate_menu(menu((2.2495, 50)), dials={"minRiskRewardRatio": 2.25}, sections=[],
                                                  anchor="1h", trailing_enabled=True)
                 if f.path.startswith("tradeLevelMenu.LONG")]
    assert "pays 2.2495R as written" in message and "not measured" in message


def test_the_tie_draft_was_staged_and_discarded_as_the_others():
    assert TIES["versionBefore"]["contractVersion"] == TIES["versionAfter"]["contractVersion"] == "182.3.2"
    assert TIES["versionBefore"]["buildSha"] == TIES["versionAfter"]["buildSha"] == RECORD["buildSha"]
    assert TIES["versionBefore"]["at"] < TIES["stages"][0]["at"] < TIES["discard"]["at"] < TIES["versionAfter"]["at"]
    for listed in (TIES["runtimeCheck"]["listStrategyDrafts"], TIES["listStrategyDraftsBefore"],
                   TIES["listStrategyDraftsAfter"]):
        [only] = listed["drafts"]
        assert (only["strategyName"], only["version"], only["updatedAt"][:10]) == ("VWAP Reject 15m", 9, "2026-10-23")
        assert only["strategyId"] != TIES["strategyId"]
    assert [s["id"] for s in TIES["stages"]] == ["T0", "K1", "K2", "K3", "A", "B", "C", "D1", "D2", "D3", "D4", "D5",
                                                 "D6", "D7", "D8"]
    assert sorted(TIE_STAGES) == sorted(["T0"] + [stage for stage, _, _ in TIE_CASES])
    assert [(s["namedDraftVersion"], s["versionAfter"]) for s in TIES["stages"]] == [(i, i + 1) for i in range(15)]
    assert TIE_STAGES["T0"]["answer"] == {"errors": [], "warnings": []}
    assert TIES["readBack"]["draftVersion"] == TIES["discard"]["draftVersion"] == 15
    assert TIES["readBack"]["committedRevision"] is None
    assert TIES["discard"]["answer"] == {"strategyId": TIES["strategyId"], "discarded": True}
    assert TIES["discard"]["readAfter"] == {"draft": None, "draftVersion": 0, "committedRevision": None}


def test_a_pair_just_under_the_minimum_survives_a_decision_stated_at_the_minimum():
    for key in ("LG2", "LG3"):
        for side in ("LONG", "SHORT"):
            answer = L_LEVELS[(key, "BTC")][side]
            assert answer["rejectedPairs"] == [] and answer["counters"]["pairsRemovedByRiskReward"] == 0
            assert {s["riskRewardRatio"] for s in answer["setups"]} == {1.5} and len(answer["setups"]) == 4
    assert E_STAGES["T2"]["answer"] == {"errors": [], "warnings": []}
    assert "pays 1.499R" in E_STAGES["T3"]["answer"]["errors"][0]["message"]
    assert E_STAGES["T4"]["answer"] == {"errors": [], "warnings": []}


def test_a_level_entry_states_its_distance_and_how_long_it_stays_valid():
    at_market = L_LEVELS[("LF0", "BTC")]
    assert at_market["LONG"]["entry"] is None and at_market["SHORT"]["entry"] is None
    for key, bars, long_order in (("LF1", 4, "TRIGGER"), ("LF3", 24, "TRIGGER")):
        entry = L_LEVELS[(key, "BTC")]["LONG"]["entry"]
        assert entry["outcome"] == "RESTS" and entry["orderType"] == long_order
        assert entry["validForMinutes"] == bars * 60          # validForBars x the 1h strategy bar
        assert entry["placedPrice"] == pytest.approx(entry["levelPrice"] + 0.2 * entry["atr"])
        assert entry["distanceAtr"] == pytest.approx(abs(entry["placedPrice"] - entry["mark"]) / entry["atr"])
        assert entry["distancePct"] == pytest.approx(100 * abs(entry["placedPrice"] - entry["mark"]) / entry["mark"],
                                                     rel=0.02)
    short = L_LEVELS[("LF2", "BTC")]["SHORT"]["entry"]
    assert (short["outcome"], short["orderType"], short["validForMinutes"]) == ("RESTS", "LIMIT", 360)
    wrong = L_LEVELS[("LF2", "BTC")]["LONG"]
    assert wrong["entry"]["outcome"] == "WRONG_SIDE" and wrong["stage"] == "ENTRY_LEVEL_UNAVAILABLE"
    assert (wrong["entry"]["placedSide"], wrong["entry"]["requiredSide"]) == ("above", "below")
    assert "distancePct" not in wrong["entry"] and "setups" not in wrong
    for side in ("LONG", "SHORT"):
        assert L_LEVELS[("LF4", "BTC")][side]["entry"]["outcome"] == "WRONG_SIDE"


# --- ENTRY_LEVEL_USUALLY_SKIPPED ------------------------------------------------------------------------------------
def _entry_warnings(stage: dict):
    from omega.trade_levels import entry_side_findings
    return sorted((f.path, f.message) for f in entry_side_findings(stage["sent"]["ENTRY"]["entry"]))


def test_the_warning_fires_on_a_level_with_a_side_by_definition_under_the_wrong_order():
    staged = [s for s in list(E_STAGES.values()) + list(L_STAGES.values())
              if isinstance((s["sent"].get("ENTRY") or {}).get("entry"), dict)
              and "levels" in s["sent"]["ENTRY"]["entry"]]
    assert len(staged) == 21
    warned = 0
    for stage in staged:
        platform = sorted((w["field"], w["message"]) for w in stage["answer"]["warnings"])
        assert {w["code"] for w in stage["answer"]["warnings"]} <= {"ENTRY_LEVEL_USUALLY_SKIPPED"}
        assert _entry_warnings(stage) == platform, stage["what"]
        warned += bool(platform)
    assert warned == 3                                    # E9, F4 (stop through the wrong side), F5 (retest of it)
    assert L_STAGES["F6"]["answer"]["warnings"] == [] and L_STAGES["F7"]["answer"]["warnings"] == []
    assert "sits below price by definition, but a buy stop must rest above price" in (
        L_STAGES["F4"]["answer"]["warnings"][0]["message"])
    assert "sits above price by definition, but a buy limit must rest below price" in (
        L_STAGES["F5"]["answer"]["warnings"][0]["message"])


SWEEP = json.loads((ROOT / "data/audit/reextraction_182_side_sweep_2026-11-20.json").read_text(encoding="utf-8"))


def _swept_entry(metric: str) -> dict:
    """The ENTRY every sweep stage sent, with `metric` as both levels (the record's `sent`)."""
    return json.loads(json.dumps(SWEEP["sent"]["ENTRY"]["entry"]).replace("<metric>", metric))


def test_every_sweep_stage_answers_as_omega_warns():
    """The side sweep replayed stage by stage: the 418 answers are kept (data/audit/reextraction_182_side_sweep_...,
    from the probe's raw call logs), so the side table is checked against what the platform said of each metric, not
    against the sweep's own summary. Through v0.16.0's first pass the record held the three lists only."""
    from omega.trade_levels import ENTRY_SIDE_OFFSETS, entry_side_findings
    stages = SWEEP["stages"]
    assert len(stages) == SWEEP["stageCount"] == 418 == len({s["metric"] for s in stages})
    assert DRAFTS["S"]["stages"] == "data/audit/reextraction_182_side_sweep_2026-11-20.json"
    sent = SWEEP["sent"]["ENTRY"]["entry"]
    assert (sent["trigger"], sent["validForBars"]) == ("STOP_THROUGH_LEVEL", 4)
    assert (sent["levelOffsetAtrMultiple"],) == ENTRY_SIDE_OFFSETS
    assert sent["levels"]["LONG"] == sent["levels"]["SHORT"] == {
        "metric": "<metric>", "timeframe": {"rel": "anchor"}, "bars": None, "offset": 0, "knobs": {},
        "windowExtreme": None}
    sides = {"below": [], "above": [], "neither": []}
    for stage in stages:
        assert stage["errors"] == [], stage["metric"]
        assert {w["code"] for w in stage["warnings"]} <= {"ENTRY_LEVEL_USUALLY_SKIPPED"}
        platform = sorted((w["field"], w["message"]) for w in stage["warnings"])
        ours = sorted((f.path, f.message) for f in entry_side_findings(_swept_entry(stage["metric"])))
        assert ours == platform, stage["metric"]
        fields = [field for field, _ in platform]
        assert fields in ([], ["entry.levels.LONG"], ["entry.levels.SHORT"]), stage["metric"]
        if fields == ["entry.levels.LONG"]:
            assert "sits below price by definition, but a buy stop must rest above price" in platform[0][1]
        if fields == ["entry.levels.SHORT"]:
            assert "sits above price by definition, but a sell stop must rest below price" in platform[0][1]
        sides[{"entry.levels.LONG": "below", "entry.levels.SHORT": "above"}.get((fields or [None])[0], "neither")
              ].append(stage["metric"])
    sweep = DRAFTS["S"]
    assert {k: sorted(v) for k, v in sides.items()} == {k: sweep[k] for k in sides}
    assert (len(sides["below"]), len(sides["above"]), len(sides["neither"])) == (9, 9, 400)
    # two drafts: 24 metrics answered on the first before it was stopped, the other 394 on the second, each stage
    # naming the version the one before it made
    first = [s for s in stages if s["run"] == "first"]
    second = [s for s in stages if s["run"] == "second"]
    assert (len(first), len(second)) == (24, 394) and first + second == stages
    assert [(s["namedDraftVersion"], s["versionAfter"]) for s in first] == [(i, i + 1) for i in range(1, 25)]
    assert [(s["namedDraftVersion"], s["versionAfter"]) for s in second] == [(i, i + 1) for i in range(394)]
    assert all(a["at"] < b["at"] for a, b in zip(stages, stages[1:]))
    assert SWEEP["drafts"] == {"first": sweep["firstRun"]["strategyId"],
                               "second": sweep["secondRun"]["draft"]["strategyId"]}
    assert second[0]["metric"] == "EMA9" and len(second[0]["stagedAxes"]) == 8      # the whole body, EMA9 again
    assert all(s["stagedAxes"] == ["ENTRY"] for s in first)
    assert sum(1 for s in second if "REPORT" in s["stagedAxes"]) == 14               # one report per batch of 30


def test_the_stage_counts_are_what_the_logs_show():
    """The first sweep draft took 26 stages and gave 25 answers (one report stage, 24 metrics; the 26th was sent as
    the run was stopped and its answer was never read - the list stated version 26), the second 394 and 394."""
    calls, sweep = RECORD["calls"], DRAFTS["S"]
    first, second = sweep["firstRun"], sweep["secondRun"]
    assert (first["stagesSent"], first["answersRead"], first["metricsMeasured"]) == (26, 25, 24)
    assert first["lastAnswerRead"] == {"metric": "EMA8", "at": "2026-11-20T14:55:24.966Z", "versionAfter": 25}
    assert first["listedAfter"]["version"] == 26 == calls["createDrafts"][first["strategyId"]]
    assert (second["stagesSent"], second["answersRead"], second["metricsMeasured"]) == (394, 394, 394)
    assert second["draft"]["discardedAtDraftVersion"] == 394 == calls["createDrafts"][second["draft"]["strategyId"]]
    assert first["metricsMeasured"] + second["metricsMeasured"] == sweep["measured"] == 418
    assert calls["createDrafts"] == {
        DRAFTS["E"]["strategyId"]: len(DRAFTS["E"]["stages"]), DRAFTS["L"]["strategyId"]: len(DRAFTS["L"]["stages"]),
        first["strategyId"]: 26, second["draft"]["strategyId"]: 394, RECORD["proof"]["strategyId"]: 1,
        TIES["strategyId"]: len(TIES["stages"])}
    assert sum(calls["createDrafts"].values()) == calls["stage_strategy_draft"] == 475
    assert calls["stageAnswersRead"] == 474 == (len(DRAFTS["E"]["stages"]) + len(DRAFTS["L"]["stages"])
                                                + first["answersRead"] + second["answersRead"] + 1
                                                + len(TIES["stages"]))
    assert calls["discard_strategy_draft"] == len(calls["createDrafts"]) == 6
    assert calls["preview_strategy_trade_levels"] == (len(DRAFTS["E"]["tradeLevels"]) + len(DRAFTS["L"]["tradeLevels"])
                                                      + 1 + len(TIES["tradeLevels"])) == 30


def test_the_sides_by_definition_are_the_swept_ones():
    """data/derived/entry_level_sides.json against the sweep's record. The record's lists are themselves derived from
    the 418 stage answers, which test_every_sweep_stage_answers_as_omega_warns replays one by one."""
    from omega.trade_levels import ENTRY_LEVEL_SIDES, entry_level_sides
    sweep = DRAFTS["S"]
    derived = json.loads((ROOT / ENTRY_LEVEL_SIDES).read_text(encoding="utf-8"))
    assert derived["below"] == sweep["below"] and derived["above"] == sweep["above"]
    assert sorted(derived["measured"]) == sorted(sweep["below"] + sweep["above"] + sweep["neither"])
    assert sorted(derived["measured"]) == sorted(s["metric"] for s in SWEEP["stages"])
    assert "reextraction_182_side_sweep_2026-11-20.json" in derived["source"]
    assert sweep["other"] == {} and sweep["measured"] == len(derived["measured"])
    c = load()
    legal = {name for name, m in c.metrics.items() if m.unit == "price"
             and not _errors(Column(metric=name, transformId="value", timeframe={"rel": "anchor"}))}
    assert set(derived["measured"]) | set(derived["unmeasured"]) == legal and len(legal) == 418
    sides = entry_level_sides()
    assert sides["DONCHIAN_LOWER"] == "below" and sides["DONCHIAN_UPPER"] == "above"
    # a name does not tell the side: a broken Donchian HIGH sits below price, the prior bar's band has none
    assert sides["DONCHIAN_BROKEN_HI"] == "below" and sides["DONCHIAN_BROKEN_LO"] == "above"
    assert "DONCHIAN_UPPER_PRIOR" not in sides and "BB_UPPER" not in sides and "PDH" not in sides


def test_validate_entry_levels_warns_only_on_the_form_the_sweep_staged():
    from omega.trade_levels import validate_entry_levels

    def level(metric, **kw):
        return {"metric": metric, "timeframe": {"rel": "anchor"}, "bars": None, "offset": 0, "knobs": {},
                "windowExtreme": None, **kw}
    sections = [{"kind": "custom", "title": "Levels", "benchmarkTicker": None, "marketScope": None, "notes": None,
                 "columns": [{"metric": m, "transformId": "value", "timeframe": {"rel": "anchor"}}
                             for m in ("DONCHIAN_LOWER", "DONCHIAN_UPPER")]}]

    def entry(trigger, long, short):
        return {"trigger": trigger, "levelOffsetAtrMultiple": 0.2, "validForBars": 4,
                "levels": {"LONG": long, "SHORT": short}}
    wrong = validate_entry_levels(entry("STOP_THROUGH_LEVEL", level("DONCHIAN_LOWER"), level("DONCHIAN_UPPER")),
                                  sections=sections, anchor="1h")
    assert [(f.severity, f.code, f.path) for f in wrong] == [
        ("warning", "ENTRY_LEVEL_USUALLY_SKIPPED", "entry.levels.LONG"),
        ("warning", "ENTRY_LEVEL_USUALLY_SKIPPED", "entry.levels.SHORT")]
    for trigger, long, short in (("STOP_THROUGH_LEVEL", "DONCHIAN_UPPER", "DONCHIAN_LOWER"),
                                 ("ON_RETEST", "DONCHIAN_LOWER", "DONCHIAN_UPPER"),
                                 ("EITHER_SIDE_OF_LEVEL", "DONCHIAN_LOWER", "DONCHIAN_UPPER")):
        assert validate_entry_levels(entry(trigger, level(long), level(short)), sections=sections, anchor="1h") == []
    # an unread level is an error and the other direction's warning stands beside it (omega's own reading: whether the
    # stage reports a warning beside an entry level error is not measured)
    unread = validate_entry_levels(entry("STOP_THROUGH_LEVEL", level("DONCHIAN_LOWER"), level("BB_UPPER")),
                                   sections=sections, anchor="1h")
    assert [(f.severity, f.path) for f in unread] == [("error", "entry.levels.SHORT"),
                                                      ("warning", "entry.levels.LONG")]
    # another form of the same metric was not swept and draws nothing
    back = validate_entry_levels(entry("STOP_THROUGH_LEVEL", level("DONCHIAN_LOWER", offset=1),
                                       level("DONCHIAN_UPPER", offset=1)), sections=sections, anchor="1h")
    assert not [f for f in back if f.code == "ENTRY_LEVEL_USUALLY_SKIPPED"]


def _wrong_side_entry(**changes) -> dict:
    """STOP_THROUGH_LEVEL over DONCHIAN_LOWER / DONCHIAN_UPPER as F4 staged it (two warnings), with `changes` to the
    entry; `LONG` / `SHORT` change that level's reference."""
    entry = _swept_entry("DONCHIAN_LOWER")
    entry["levels"]["SHORT"]["metric"] = "DONCHIAN_UPPER"
    for side in ("LONG", "SHORT"):
        entry["levels"][side].update(changes.pop(side, {}))
    return {**entry, **changes}


def test_the_side_warning_is_drawn_on_the_staged_form_only():
    """Every stage that measured the warning carried bars null on the level and levelOffsetAtrMultiple 0.2 on the
    entry (drafts E and L, the sweep): a Developing or explicitly closed level, and any other offset, are not
    measured and draw nothing."""
    from omega.trade_levels import ENTRY_SIDE_OFFSETS, entry_side_findings
    assert ENTRY_SIDE_OFFSETS == (0.2,)
    staged = [s["sent"]["ENTRY"]["entry"] for s in list(E_STAGES.values()) + list(L_STAGES.values())
              if isinstance((s["sent"].get("ENTRY") or {}).get("entry"), dict) and "levels" in s["sent"]["ENTRY"]["entry"]]
    assert {e["levelOffsetAtrMultiple"] for e in staged} == {0.2}
    assert {ref["bars"] for e in staged for ref in e["levels"].values()} == {None}
    assert _wrong_side_entry() == L_STAGES["F4"]["sent"]["ENTRY"]["entry"]
    assert [f.path for f in entry_side_findings(_wrong_side_entry())] == ["entry.levels.LONG", "entry.levels.SHORT"]
    # the level's bars
    for bars in ("all", "closed"):
        assert entry_side_findings(_wrong_side_entry(LONG={"bars": bars}, SHORT={"bars": bars})) == []
    assert [f.path for f in entry_side_findings(_wrong_side_entry(LONG={"bars": "all"}))] == ["entry.levels.SHORT"]
    # the entry's offset in ATR: the schema takes 0 - 2 on a 0.1 step; only 0.2 was staged
    for offset in (0, 0.1, 0.3, 1, 2):
        assert entry_side_findings(_wrong_side_entry(levelOffsetAtrMultiple=offset)) == [], offset
    assert len(entry_side_findings(_wrong_side_entry(levelOffsetAtrMultiple=0.2))) == 2
    # validForBars was 4 on every warned stage; the warning is not gated on it (see the record's "Not measured")
    assert len(entry_side_findings(_wrong_side_entry(validForBars=24))) == 2
    # through validate_entry_levels: the same entries, the level rule's own findings aside
    from omega.trade_levels import validate_entry_levels
    sections = [{"kind": "custom", "title": "Levels", "benchmarkTicker": None, "marketScope": None, "notes": None,
                 "columns": [{"metric": m, "transformId": "value", "timeframe": {"rel": "anchor"}}
                             for m in ("DONCHIAN_LOWER", "DONCHIAN_UPPER")]}]
    assert [f.code for f in validate_entry_levels(_wrong_side_entry(), sections=sections, anchor="1h")] == [
        "ENTRY_LEVEL_USUALLY_SKIPPED"] * 2
    assert validate_entry_levels(_wrong_side_entry(levelOffsetAtrMultiple=0.5), sections=sections, anchor="1h") == []
    assert validate_entry_levels(_wrong_side_entry(LONG={"bars": "closed"}, SHORT={"bars": "closed"}),
                                 sections=sections, anchor="1h") == []


@pytest.mark.parametrize("entry", [
    None, "STOP_THROUGH_LEVEL", 3, [], {}, {"trigger": "STOP_THROUGH_LEVEL"},
    {"trigger": "STOP_THROUGH_LEVEL", "levelOffsetAtrMultiple": 0.2},
    {"trigger": "STOP_THROUGH_LEVEL", "levelOffsetAtrMultiple": 0.2, "levels": None},
    {"trigger": "STOP_THROUGH_LEVEL", "levelOffsetAtrMultiple": 0.2, "levels": ["DONCHIAN_LOWER"]},
    {"trigger": "STOP_THROUGH_LEVEL", "levelOffsetAtrMultiple": 0.2, "levels": {}},
    {"trigger": "STOP_THROUGH_LEVEL", "levelOffsetAtrMultiple": 0.2, "levels": {"LONG": None, "SHORT": "PDH"}},
    {"trigger": "STOP_THROUGH_LEVEL", "levelOffsetAtrMultiple": 0.2, "levels": {"LONG": {}, "SHORT": {"metric": None}}},
    {"trigger": "STOP_THROUGH_LEVEL", "levelOffsetAtrMultiple": 0.2,
     "levels": {"LONG": {"metric": ["DONCHIAN_LOWER"]}, "SHORT": {"metric": {"DONCHIAN_UPPER": 1}}}},
    {"trigger": ["STOP_THROUGH_LEVEL"], "levelOffsetAtrMultiple": 0.2, "levels": {"LONG": {}, "SHORT": {}}},
    {"trigger": {"kind": "STOP_THROUGH_LEVEL"}, "levelOffsetAtrMultiple": 0.2, "levels": {}},
    {"trigger": "ON_CANDLE_CLOSE"},
], ids=lambda e: json.dumps(e)[:60])
def test_the_side_warning_never_raises_on_a_malformed_entry(entry):
    """entry_side_findings is a public name: called on its own with something that is not a well-formed level entry
    it answers [] (the shape is the write schema's walk to refuse), where v0.16.0's first pass raised KeyError,
    AttributeError or TypeError."""
    from omega.trade_levels import entry_side_findings
    assert entry_side_findings(entry) == []


@pytest.mark.parametrize("changes", [
    {"levelOffsetAtrMultiple": None}, {"levelOffsetAtrMultiple": "0.2"}, {"levelOffsetAtrMultiple": True},
    {"levelOffsetAtrMultiple": float("nan")}, {"levelOffsetAtrMultiple": [0.2]},
    {"LONG": {"offset": False}, "SHORT": {"offset": None}}, {"LONG": {"knobs": None}, "SHORT": {"knobs": []}},
    {"LONG": {"timeframe": None}, "SHORT": {"timeframe": "anchor"}},
    {"LONG": {"windowExtreme": {}}, "SHORT": {"windowExtreme": "max"}},
], ids=lambda c: json.dumps(c, default=str)[:60])
def test_a_part_that_is_not_the_staged_form_draws_no_side_warning(changes):
    from omega.trade_levels import entry_side_findings
    assert entry_side_findings(_wrong_side_entry(**changes)) == []


# --- the drafts and the proof -------------------------------------------------------------------------------------------
def test_every_draft_was_discarded_and_read_back_null():
    for key in ("E", "L"):
        discard = DRAFTS[key]["discard"]
        assert discard["answer"]["discarded"] is True
        assert discard["readAfter"] == {"draft": None, "draftVersion": 0, "committedRevision": None}
        for when in ("listStrategyDraftsBefore", "listStrategyDraftsAfter"):
            [only] = DRAFTS[key][when]["drafts"]
            assert (only["strategyName"], only["version"], only["updatedAt"][:10]) == ("VWAP Reject 15m", 9, "2026-10-23")
    second = DRAFTS["S"]["secondRun"]["draft"]
    assert second["discard"]["discarded"] is True and second["readAfter"]["draft"] is None
    assert [d["strategyName"] for d in second["draftsAfter"]["drafts"]] == ["VWAP Reject 15m"]
    assert RECORD["proof"]["discard"]["readAfter"] == {"draft": None, "draftVersion": 0, "committedRevision": None}
    assert TIES["discard"]["readAfter"] == {"draft": None, "draftVersion": 0, "committedRevision": None}


def test_the_proof_body_is_what_omega_generates_and_it_staged_clean():
    from omega.generate import PRESETS, plan
    from omega.preflight import body_sha256
    proof = RECORD["proof"]
    axes = plan(PRESETS[proof["preset"]]).axes()
    assert axes == proof["sentAxes"] and body_sha256(axes) == proof["bodySha256Sent"]
    assert proof["stage"]["answer"] == {"errors": [], "warnings": []}
    assert sorted(proof["stage"]["stagedAxes"]) == sorted(axes)
    read = proof["readBack"]
    assert read["diagnostics"] == {"errors": [], "warnings": []} and read["committedRevision"] is None
    assert read["contentEqualsSentAsValues"] is True and read["axesThatDiffer"] == []
    assert proof["discard"]["answer"]["discarded"] is True
    [only] = proof["discard"]["listStrategyDraftsAfter"]["drafts"]
    assert only["strategyName"] == "VWAP Reject 15m" and only["version"] == 9
    assert proof["versionBefore"]["contractVersion"] == proof["versionAfter"]["contractVersion"] == "182.3.2"
    # the same body the 180.4.0 proof staged: the generator did not move
    old = json.loads((ROOT / "data/audit/reextraction_180_4_2026-11-19.json").read_text(encoding="utf-8"))
    assert old["proof"]["bodySha256Sent"] == proof["bodySha256Sent"]
