"""OMEGA v0.12 (in progress): the write surface and the vocabulary at contract 148.1.0, measured 2026-11-05.

What was measured (read-only, mcporter, battlegrid-anbu): the live surface at 09:38:43Z (154 tools), the
compare_vocabulary run against it, list_strategy_categories + list_strategy_vocabulary x 11 at 09:43:20-09:45:48Z. The
re-extraction stopped at its step 3: get_metric_construction_hints was read for 170 of the 532 roster metrics
(09:40-10:18Z, none of the 206 added keys) when the mcporter OAuth credential lost its tokens; every later call asked
for an interactive browser authorization. So the 206 keys, `ema` and the six knobs are served and UNMEASURED here:
known by name, refused offline. Record: docs/plans/2026-11-05-omega-reextraction-148.md. Nothing here calls the
platform.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from omega import contract as C
from omega.condition_vocabulary import derive
from omega.contract import CONTRACT_DIR, load
from omega.types import Column
from omega.validate import validate_column

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = CONTRACT_DIR / "stage_strategy_draft" / "schema_20261105T093843Z.json"
CAPTURE_146 = CONTRACT_DIR / "stage_strategy_draft" / "schema_20261101T061733Z.json"
FIXTURE = Path("C:/Users/rafae/Documents/GitHub/battlegrid-manager/tests/fixtures/"
               "2026-11-04-contract-148.1.0/manager_schemas_148.1.0.json")
VOCAB = CONTRACT_DIR / "vocabulary" / "20261105T0943Z"
TOOLS = ("stage_strategy_draft", "get_strategy_draft", "commit_strategy_draft", "list_strategy_drafts",
         "preview_strategy_report", "get_strategy")
KNOBS = ("leftBars", "rightBars", "swingLength", "equalBars", "equalThreshold", "confluenceFilter")
STRUCTURE = {"INTERNAL_STRUCTURE_EVENT", "INTERNAL_STRUCTURE_TREND", "INTERNAL_STRUCTURE_LEVEL",
             "SWING_STRUCTURE_EVENT", "SWING_STRUCTURE_TREND", "SWING_STRUCTURE_LEVEL", "EQH", "EQL"}


def _j(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


DOC = _j(CAPTURE)
# the 148.1.0 capture's OWN inventory: since 2026-11-07 the manifest names the 149.1.0 capture
# (tests/test_v149_surface.py), so what 148.1.0 served is read off this capture, never off vocabulary()
V148 = derive(DOC, source=CAPTURE.name, source_sha256="")
COMPARE = _j(ROOT / "data/audit/contract_148_1_0_vocabulary_2026-11-05.json")
UNMEASURED = _j(CONTRACT_DIR / "metrics" / "_unmeasured_108.json")


def _column_node(doc: dict) -> dict:
    sections = doc["stage_strategy_draft"]["inputSchema"]["properties"]["axes"]["properties"]["REPORT"]
    custom = next(a for a in sections["properties"]["sections"]["items"]["oneOf"] if "columns" in a["properties"])
    return custom["properties"]["columns"]["items"]


def _errors(findings) -> list[str]:
    return [f.code for f in findings if f.severity == "error"]


# --- the write surface -------------------------------------------------------------------------------------------------
def test_the_capture_names_its_contract_build_and_source():
    assert (DOC["contractVersion"], DOC["buildSha"]) == ("148.1.0", "d02121ecdf909505410e079fbaeab2e0f9e290af")
    assert DOC["observedAt"] == "2026-11-05T09:38:43Z"
    assert DOC["surfaceHash"] == "6c7f402746d658003ebea58060d86a34092abeac9818260df5d373a256a96432"
    assert "manager_schemas_148.1.0.json" in DOC["readFrom"] and "09:38:43Z" in DOC["readFrom"]
    for tool in TOOLS:
        assert {"description", "inputSchema", "outputSchema", "annotations"} <= set(DOC[tool]), tool
    # the write surface until 2026-11-07, when the 149.1.0 capture superseded it (kept under `supersedes`); two levels
    # down since the 161.0.0 capture of 2026-11-09 (the 149.1.0 one is the first `supersedes`)
    manifest = _j(CONTRACT_DIR / "_manifest.json")["writeSurface"]["supersedes"]["supersedes"]
    assert manifest["schema"] == "data/contract/stage_strategy_draft/schema_20261105T093843Z.json"
    assert manifest["liveCheckedAt"]["observedAt"] == "2026-11-05T09:38:43Z"
    assert manifest["supersedes"]["servedContractVersion"] == "146.0.0"


@pytest.mark.skipif(not FIXTURE.exists(), reason="the battlegrid-manager checkout is not beside this repo")
def test_every_tool_entry_is_the_manager_fixtures_own():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == DOC["sourceSha256"]
    fixture = json.loads(raw.decode("utf-8"))
    assert (fixture["contractVersion"], fixture["buildSha"], fixture["hash"]) == (
        DOC["contractVersion"], DOC["buildSha"], DOC["surfaceHash"])
    for tool in TOOLS:
        assert DOC[tool] == fixture["tools"][tool], tool


def test_the_column_carries_the_six_knobs_at_the_schemas_bounds():
    props = _column_node(DOC)["properties"]
    assert {k: props[k]["type"] for k in KNOBS} == {
        "leftBars": "integer", "rightBars": "integer", "swingLength": "integer", "equalBars": "integer",
        "equalThreshold": "number", "confluenceFilter": "boolean"}
    assert {k: props[k].get("minimum") for k in KNOBS} == {
        "leftBars": 1, "rightBars": 1, "swingLength": 1, "equalBars": 1, "equalThreshold": 0, "confluenceFilter": None}
    old = _column_node(_j(CAPTURE_146))["properties"]
    assert set(props) - set(old) == set(KNOBS) and not set(old) - set(props)


def test_the_transform_enums_gained_ema_and_the_distance_chain_outer():
    col = V148["reportColumn"]
    old = _column_node(_j(CAPTURE_146))["properties"]
    assert set(col["transformId"]["enum"]) - set(old["transformId"]["enum"]) == {"ema"}
    assert set(col["chainedTransformId"]["enum"]) - set(old["chainedTransformId"]["enum"]) == {"distance", "ema"}
    assert (col["transformId"]["count"], col["chainedTransformId"]["count"]) == (25, 13)


# --- the roster: 206 added, known by name ------------------------------------------------------------------------------
def test_the_compare_before_and_after():
    before, after = COMPARE["before"]["results"], COMPARE["after"]["results"]
    assert (before["metrics"]["live"], before["metrics"]["stored"]) == (532, 326)
    assert len(before["metrics"]["liveNotStored"]) == 206 and before["metrics"]["storedNotLive"] == []
    assert after["metrics"]["liveNotStored"] == [] and after["metrics"]["storedNotLive"] == []
    assert after["metrics"]["storedUnmeasured"] == before["metrics"]["liveNotStored"]
    for r in (before, after):
        assert (r["sectionKeys"]["live"], r["sectionKeys"]["stored"]) == (22, 22)
        assert r["sectionKeys"]["liveNotStored"] == r["sectionKeys"]["storedNotLive"] == []
    assert COMPARE["before"]["liveToolCount"] == 154


def test_the_206_were_listed_by_readme_entry_and_are_measured_since_2026_11_07():
    """Listed by name 2026-11-05 at 148.1.0; their hints read at 149.1.0 on 2026-11-06 and folded into the corpus
    2026-11-07 (history148). The per-key records are kept there as written."""
    history = UNMEASURED["history148"]
    metrics = history["formerlyUnmeasured"]
    assert set(metrics) == set(COMPARE["before"]["results"]["metrics"]["liveNotStored"])
    assert UNMEASURED["metrics"] == {} and load().unmeasured_metrics == {}
    assert set(metrics) <= set(load().metrics)
    by_entry: dict[str, set[str]] = {}
    for key, rec in metrics.items():
        assert rec["servedAt"] == "148.1.0" and rec["transformAdmissibility"] == "UNMEASURED", key
        by_entry.setdefault(rec["describedIn"], set()).add(key)
    assert {k: len(v) for k, v in by_entry.items()} == {"v146.5": 34, "v146.8": 82, "v146.10": 82, "v146.11": 8}
    assert by_entry["v146.11"] == STRUCTURE
    assert all(k.startswith(("PIVOT_WEEK_", "PIVOT_MONTH_")) for k in by_entry["v146.8"])
    assert all(k.startswith(("PIVOT_QUARTER_", "PIVOT_YEAR_")) for k in by_entry["v146.10"])
    assert "10:18Z" in history["why"] and "170 of the 532" in history["why"]
    assert history["measuredBy"].startswith("get_metric_construction_hints x 532 at contract 149.1.0")


@pytest.mark.parametrize("key", ["PIVOT_WEEK_P", "PIVOT_CAM_R1", "SWING_STRUCTURE_LEVEL", "EQH"])
def test_a_column_over_an_added_key_validates_since_the_refresh(key):
    """Refused METRIC_UNMEASURED until 2026-11-07; each rendered as `value` in the 149.1.0 probe (pivotWeekP,
    pivotCamR1, structLvl, eqh)."""
    col = Column.model_validate({"metric": key, "transformId": "value", "timeframe": {"rel": "anchor"}})
    assert _errors(validate_column(col)) == []


def test_ema_is_measured_and_judged_by_its_served_depth():
    """Refused TRANSFORM_UNMEASURED until 2026-11-07; RSI14_ema14 rendered and window 270 was refused
    REPORT_COLUMN_DEPTH_EXCEEDED ("the largest window that fits is 269") at 149.1.0. At 161.0.0 (2026-11-09) the
    readable depth is 2500 bars and ema's served maximum is 704 (2436 of 2500 less the lookback budget): 270 fits."""
    contract = load()
    assert "ema" not in contract.unmeasured_transforms and "ema" in contract.transforms
    col = {"metric": "RSI14", "transformId": "ema", "timeframe": {"rel": "anchor"}}
    assert _errors(validate_column(Column.model_validate({**col, "window": 14}), contract=contract)) == []
    # 161.0.0 (2026-11-09): the served maximum moved 269 -> 704; the judge follows it
    maximum = contract.metric("RSI14").transforms["ema"]["maximums"]["window"]
    assert maximum == 704
    assert _errors(validate_column(Column.model_validate({**col, "window": maximum}), contract=contract)) == []
    assert _errors(validate_column(Column.model_validate({**col, "window": maximum + 1}), contract=contract)) == [
        "DEPTH_EXCEEDED"]


# An unmeasured key is unmeasured wherever the column uses it - not only as its own metric / transformId. Each shape
# below is served at 148.1.0 (the same day's hints: CLOSE serves 368 spread operands incl. PIVOT_WEEK_P; distance /
# spread / relativeTo list `ema` among their chainSuccessors; rollingMax serves `offset` 0-44 and chains into
# `distance` with offsetMinimum 1), and the 146.0.1 corpus refused each one with a platform-style code
# (OPERAND_NOT_ALLOWED, REPORT_COLUMN_CHAIN_UNSUPPORTED, OFFSET_REFUSED) stated as measured fact.
def test_the_unmeasured_chain_outers_are_the_served_enums_delta():
    served = V148["reportColumn"]["chainedTransformId"]["enum"]
    old = _column_node(_j(CAPTURE_146))["properties"]["chainedTransformId"]["enum"]
    history = UNMEASURED["history149"]
    assert set(served) - set(old) == {"distance", "ema"} <= set(history["chainOuters"])
    assert set(history["transformParameters"]) == {"rollingMax", "rollingMin"}
    assert all(set(p) == {"offset"} for p in history["transformParameters"].values())
    # rendered by the 149.1.0 probe (groups A, B, J): nothing is left unmeasured
    assert load().unmeasured_chain_outers == {} and load().unmeasured_parameters == {}
    assert "2026-11-05: 206" in UNMEASURED["_what"] and "2026-11-07: EMPTY again" in UNMEASURED["_what"]


@pytest.mark.parametrize("column,expected", [
    ({"metric": "CLOSE", "transformId": "spread", "inputs": [{"metric": "PIVOT_WEEK_P"}]},
     [("METRIC_UNMEASURED", "column.inputs[0]")]),
    ({"metric": "CLOSE", "transformId": "spread", "inputs": [{"metric": "SWING_STRUCTURE_LEVEL"}],
      "chainedTransformId": "zscore", "window": 20},
     [("METRIC_UNMEASURED", "column.inputs[0]")]),
    ({"metric": "HIGH", "transformId": "distance", "chainedTransformId": "ema", "window": 10},
     [("TRANSFORM_UNMEASURED", "column.chainedTransformId")]),
    ({"metric": "RSI14", "transformId": "spread", "inputs": [{"metric": "RSI7"}], "chainedTransformId": "ema",
      "window": 10},
     [("TRANSFORM_UNMEASURED", "column.chainedTransformId")]),
    ({"metric": "HIGH", "transformId": "rollingMax", "window": 55, "offset": 1, "chainedTransformId": "distance"},
     [("TRANSFORM_UNMEASURED", "column.chainedTransformId"), ("PARAMETER_UNMEASURED", "column.offset")]),
    ({"metric": "LOW", "transformId": "rollingMin", "window": 20, "offset": 2},
     [("PARAMETER_UNMEASURED", "column.offset")]),
])
def test_what_was_refused_as_unmeasured_at_148_validates_since_the_refresh(column, expected):
    """`expected` is what the 148.1.0 corpus answered (unmeasured); since 2026-11-07 every one of these is measured -
    the operands from the served spreadOperands, the outers and the offset rendered in the 149.1.0 probe - and
    validates with no error."""
    col = Column.model_validate({**column, "timeframe": {"rel": "anchor"}})
    assert all(code.endswith("_UNMEASURED") for code, _ in expected)
    now = []
    if column.get("chainedTransformId") == "zscore":
        # the one served refusal: SWING_STRUCTURE_LEVEL is a spread operand of CLOSE, but not one of the 91 operands
        # CLOSE x spread serves under the zscore chain (chainedOuters.zscore.operands, hints at 149.1.0)
        now = [("REPORT_COLUMN_CHAIN_UNSUPPORTED", "column.inputs[0]")]
    assert [(f.code, f.path) for f in validate_column(col) if f.severity == "error"] == now


def test_a_section_with_a_once_unmeasured_operand_validates():
    """validate_section predicts every column's header for the duplicate check; over an operand the corpus did not
    hold that raised KeyError ('unknown metric PIVOT_WEEK_P'). The operand is in the corpus since 2026-11-07."""
    from omega.types import CustomSection
    from omega.validate import validate_section
    section = CustomSection.model_validate({"kind": "custom", "title": "t", "marketScope": None, "columns": [
        {"metric": "CLOSE", "transformId": "spread", "inputs": [{"metric": "PIVOT_WEEK_P"}], "timeframe": {"rel": "anchor"}},
        {"metric": "HIGH", "transformId": "distance", "chainedTransformId": "ema", "window": 10,
         "timeframe": {"rel": "anchor"}},
        {"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "anchor"}}]})
    assert [(f.code, f.path) for f in validate_section(section) if f.severity == "error"] == []


def test_measured_operands_and_chains_still_answer_from_the_corpus():
    """The unmeasured gate is not a blanket: what the corpus measured still gets its measured refusal."""
    ok = Column.model_validate({"metric": "CLOSE", "transformId": "spread", "inputs": [{"metric": "HIGH"}],
                                "timeframe": {"rel": "anchor"}})
    assert _errors(validate_column(ok)) == []
    bad = Column.model_validate({"metric": "CLOSE", "transformId": "spread", "inputs": [{"metric": "RSI14"}],
                                 "timeframe": {"rel": "anchor"}})
    assert _errors(validate_column(bad)) == ["OPERAND_NOT_ALLOWED"]
    chain = Column.model_validate({"metric": "HIGH", "transformId": "distance", "chainedTransformId": "maxShare",
                                   "window": 10, "timeframe": {"rel": "anchor"}})
    assert "REPORT_COLUMN_CHAIN_UNSUPPORTED" in _errors(validate_column(chain))


@pytest.mark.parametrize("knob,value,expected", [
    ("leftBars", 3, []), ("swingLength", 20, ["PARAMETER_UNDECLARED"]),
    ("equalThreshold", 0.2, ["PARAMETER_UNDECLARED"]), ("confluenceFilter", True, ["PARAMETER_UNDECLARED"])])
def test_the_knobs_are_modelled_per_metric(knob, value, expected):
    """Refused by omega.types.Column (extra='forbid') until 2026-11-07. Now the Column carries every knob and the
    metric's served `parameters` judge it: SWING_FRACTAL_HIGH takes leftBars / rightBars only ("metric
    'SWING_FRACTAL_HIGH' does not accept params.swingLength", measured 2026-11-07 at 149.1.0)."""
    col = Column.model_validate({"metric": "SWING_FRACTAL_HIGH", "transformId": "value", "timeframe": {"rel": "anchor"},
                                 knob: value})
    assert _errors(validate_column(col)) == expected


# --- the vocabulary read at 148.1.0 ------------------------------------------------------------------------------------
def test_the_vocabulary_snapshot_and_the_refused_structure_category():
    files = sorted(p.name for p in VOCAB.glob("*.json"))
    assert len(files) == 12 and "_categories.json" in files
    structure = _j(VOCAB / "structure.json")
    assert structure["code"] == "RESULT_TOO_LARGE" and structure["details"]["maximum"] == 150000
    assert structure["details"]["actual"] == 224226
    derived = _j(VOCAB / "derived.json")
    assert [t["id"] for t in derived["transforms"]].index("ema") == [t["id"] for t in derived["transforms"]].index("aggregate") + 1
    assert derived["budgets"]["conditionFrameReads"] == 2048


def test_the_shared_blocks_and_the_categories_moved_as_recorded():
    shared = _j(CONTRACT_DIR / "vocabulary" / "_shared.json")
    # re-read 2026-11-07 at 149.1.0 (rma / wma / rsi / cci, conditionFrameReads 5048) and 2026-11-09 at 161.0.0 (roc); the
    # 148.1.0 read is two `previous` down since 161.0.0 (it was one)
    assert shared["_refreshed"]["previous"]["contractVersion"] == "149.1.0"
    assert shared["_refreshed"]["previous"]["previous"]["contractVersion"] == "148.1.0"
    assert "budgets.conditionFrameReads 256 -> 2048 (v146.4)" in shared["_refreshed"]["previous"]["previous"]["moved"]
    assert {"id": "ema", "label": "Exponential average (EMA)"} in shared["transforms"]
    categories = _j(CONTRACT_DIR / "categories.json")
    counts = {c["category"]: c["metricCount"] for c in categories["categories"]}
    # 161.0.0 (2026-11-09): structure 363 and trend 23, sum 534 (the re-read moved `structure 362 -> 363`, `trend 22 -> 23`);
    # the 148.1.0 move (`structure 156 -> 362`) is two `previous` down
    assert counts["structure"] == 363 and counts["trend"] == 23 and sum(counts.values()) == 534 and len(counts) == 11
    assert categories["_refreshed"]["moved"][:2] == ["structure 362 -> 363", "trend 22 -> 23"]
    assert categories["_refreshed"]["previous"]["previous"]["moved"][0] == "structure 156 -> 362"
    # the 206 added are all `structure`; the corpus holds all 362 since 2026-11-07 (156 before)
    # 363 since 161.0.0 (2026-11-09)
    assert sum(1 for m in load().metrics.values() if m.family == "structure") == 363
    templates = _j(CONTRACT_DIR / "templates" / "platform" / "_all.json")
    # re-read at 161.0.0 (2026-11-09: includeBollingerBands and includeSupportResistance moved); the 148.1.0 read is `previous`
    assert templates["_refreshed"]["contractVersion"] == "161.0.0" and templates["_refreshed"]["previous"]["contractVersion"] == "148.1.0"
    assert len(templates["templates"]) == 22


def test_no_stored_record_names_a_release_that_was_not_cut():
    """The manifest said the schema moved "(OMEGA v0.12.0)" while pyproject.toml is 0.11.0: a reader would pin or
    compare against a release that does not exist. Only a cut version (pyproject) may be named as the mover."""
    import re
    version = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
    if tuple(int(x) for x in version.split(".")) >= (0, 12, 0):
        pytest.skip(f"v0.12.0 is cut (pyproject {version})")
    for rel in ("data/contract/_manifest.json", "data/contract/metrics/_unmeasured_108.json", "tests/test_v146.py"):
        assert "v0.12.0" not in (ROOT / rel).read_text(encoding="utf-8"), rel
