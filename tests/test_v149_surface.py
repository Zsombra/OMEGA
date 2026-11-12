"""OMEGA v0.12 (in progress): the write surface at contract 149.1.0, offline, 2026-11-07.

The capture is battlegrid-manager's committed fixture of the watch's stored 149.1.0 row (build aa4ab640, hash 656c9bf6,
acknowledged by the user 2026-11-05T20:31:47Z after the manager's review, docs/status/2026-11-05-contract-149.md there).
OMEGA made no platform call for it. What 149 moved, read from the schemas (the README has no v148 / v149 entry): the
column's transformId and chainedTransformId gain rma, wma, rsi and cci; the column gains thirteen optional knobs; the
four length knobs of 146.9 / 146.11 and the eight new ones are `$ref`s to the new $defs/barCount; equalThreshold loses
its minimum 0; no metric key and no tool moved.

The 532 metric hints read at 149.1.0 on 2026-11-06 are summarized in data/audit/hints_149_1_0_2026-11-06.json and are
NOT folded into the corpus yet (see that record's `_what`). Record: docs/plans/2026-11-05-omega-reextraction-148.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from omega import contract as C
from omega.condition_vocabulary import derive, vocabulary
from omega.contract import CONTRACT_DIR, load
from omega.types import Column
from omega.validate import validate_column

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = CONTRACT_DIR / "stage_strategy_draft" / "schema_20261105T181932Z.json"
CAPTURE_148 = CONTRACT_DIR / "stage_strategy_draft" / "schema_20261105T093843Z.json"
FIXTURE = Path("C:/Users/rafae/Documents/GitHub/battlegrid-manager/tests/fixtures/"
               "2026-11-05-contract-149.1.0/manager_schemas_149.1.0.json")
TOOLS = ("stage_strategy_draft", "get_strategy_draft", "commit_strategy_draft", "list_strategy_drafts",
         "preview_strategy_report", "get_strategy")
NEW_TRANSFORMS = {"rma", "wma", "rsi", "cci"}
BAR_COUNT = ("atrPeriod", "dSmoothing", "fast", "kSmoothing", "period", "rsiPeriod", "signal", "slow")
PLAIN_NUMBERS = ("multiplier", "stdDev", "accelerationStart", "accelerationIncrement", "accelerationMaximum")
NEW_KNOBS = BAR_COUNT + PLAIN_NUMBERS
BAR_COUNT_BOUNDS = {"minimum": 1, "maximum": 9007199254740991}


def _j(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


DOC = _j(CAPTURE)
# 161.0.0 (2026-11-09): the stored inventory (omega.condition_vocabulary.vocabulary()) now derives from the 161.0.0
# capture; this file pins the 149.1.0 surface as history, so it derives its own vocabulary from the 149.1.0 capture
# (what the inventory held from 2026-11-07 to 2026-11-09) instead of reading today's.
V = derive(DOC, source=CAPTURE.name, source_sha256="")
V148 = derive(_j(CAPTURE_148), source=CAPTURE_148.name, source_sha256="")
HINTS = _j(ROOT / "data/audit/hints_149_1_0_2026-11-06.json")


def _errors(findings) -> list[str]:
    return [f.code for f in findings if f.severity == "error"]


# --- the write surface -------------------------------------------------------------------------------------------------
def test_the_capture_names_its_contract_build_and_source():
    assert (DOC["contractVersion"], DOC["buildSha"]) == ("149.1.0", "aa4ab6407e62bd0c2465ca7790b276b39bbf76d4")
    assert DOC["observedAt"] == "2026-11-05T18:19:32Z"
    assert DOC["surfaceHash"] == "656c9bf6692a222d83701c06ff5f73b6298b5470494954d510a395fc1de2a96f"
    assert "manager_schemas_149.1.0.json" in DOC["readFrom"] and "OFFLINE" in DOC["readFrom"]
    assert DOC["liveListSha256"] is None                 # no live list: OMEGA made no platform call
    for tool in TOOLS:
        assert {"description", "inputSchema", "outputSchema", "annotations"} <= set(DOC[tool]), tool
    # 161.0.0 (2026-11-09): the manifest's writeSurface names the 161.0.0 capture; the 149.1.0 block is its `supersedes`
    # 2026-11-11, contract 168.3.0: the manifest names the 168.3.0 capture, the 161.0.0 block is its `supersedes` and
    # the 149.1.0 block sits under that - two levels down, it was one
    # 2026-11-12, contract 169.4.0: one level deeper again - the 169.4.0 capture on top, 168.3.0 its `supersedes`
    assert C.stage_schema()["contractVersion"] == "169.4.0"
    current = _j(CONTRACT_DIR / "_manifest.json")["writeSurface"]
    assert current["servedContractVersion"] == "169.4.0"
    current = current["supersedes"]
    assert current["servedContractVersion"] == "168.3.0"
    assert current["supersedes"]["servedContractVersion"] == "161.0.0"
    ws = current["supersedes"]["supersedes"]
    assert ws["servedContractVersion"] == "149.1.0"
    assert ws["schema"] == "data/contract/stage_strategy_draft/schema_20261105T181932Z.json"
    # cross-checked against the manager's own live observation when its stack came back (2026-11-07T03:16:53Z)
    assert ws["liveCheckedAt"]["observedAt"] == "2026-11-07T03:16:53Z"
    assert ws["liveCheckedAt"]["buildSha"] == DOC["buildSha"] and "no platform call" in ws["liveCheckedAt"]["how"]   # 161.0.0: the `offline` key left the block; its `how` says it
    assert ws["supersedes"]["servedContractVersion"] == "148.1.0"


@pytest.mark.skipif(not FIXTURE.exists(), reason="the battlegrid-manager checkout is not beside this repo")
def test_every_tool_entry_is_the_manager_fixtures_own():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == DOC["sourceSha256"]
    fixture = json.loads(raw.decode("utf-8"))
    assert (fixture["contractVersion"], fixture["buildSha"], fixture["hash"]) == (
        DOC["contractVersion"], DOC["buildSha"], DOC["surfaceHash"])
    for tool in TOOLS:
        assert DOC[tool] == fixture["tools"][tool], tool


def test_no_metric_key_and_no_section_key_moved_since_148():
    assert V["reportColumn"]["metric"]["enum"] == V148["reportColumn"]["metric"]["enum"]
    assert V["reportColumn"]["metric"]["count"] == 532
    assert V["reportSection"] == V148["reportSection"]


def test_the_conditions_grammar_did_not_move_since_148():
    from omega.condition_vocabulary import strip_pointers
    for key in ("clauseOperators", "groupOperators", "conditionsArray", "servedPerHeader"):
        assert strip_pointers(V[key]) == strip_pointers(V148[key]), key
    assert strip_pointers(V["grammar"]) == strip_pointers(V148["grammar"])


def test_the_live_surface_compared_clean():
    rec = _j(ROOT / "data/audit/contract_149_1_0_vocabulary_2026-11-07.json")
    cmp = rec["compare"]
    assert (cmp["contractVersion"], cmp["buildSha"], cmp["liveToolCount"]) == (
        "149.1.0", "aa4ab6407e62bd0c2465ca7790b276b39bbf76d4", 154)
    assert cmp["storedStageCapture"] == "data/contract/stage_strategy_draft/schema_20261105T181932Z.json"
    m = cmp["results"]["metrics"]
    assert (m["live"], m["stored"], m["liveNotStored"], m["storedNotLive"]) == (532, 532, [], [])
    assert len(m["storedUnmeasured"]) == 206
    k = cmp["results"]["sectionKeys"]
    assert (k["live"], k["stored"], k["liveNotStored"], k["storedNotLive"]) == (22, 22, [], [])


# --- the column -------------------------------------------------------------------------------------------------------
def test_the_transform_enums_gained_rma_wma_rsi_and_cci():
    col, old = V["reportColumn"], V148["reportColumn"]
    assert set(col["transformId"]["enum"]) - set(old["transformId"]["enum"]) == NEW_TRANSFORMS
    assert set(col["chainedTransformId"]["enum"]) - set(old["chainedTransformId"]["enum"]) == NEW_TRANSFORMS
    assert not set(old["transformId"]["enum"]) - set(col["transformId"]["enum"])
    assert (col["transformId"]["count"], col["chainedTransformId"]["count"]) == (29, 17)


def test_the_thirteen_knobs_and_the_bar_count_ref():
    col, old = V["reportColumn"], V148["reportColumn"]
    assert set(col["fields"]) - set(old["fields"]) == set(NEW_KNOBS) and not set(old["fields"]) - set(col["fields"])
    stage = DOC["stage_strategy_draft"]["inputSchema"]
    assert stage["$defs"]["barCount"] == {"type": "integer", **BAR_COUNT_BOUNDS}
    # every bar-count knob - the eight new ones and the four of 146.9 / 146.11 - names the shared definition
    assert {k for k, ref in col["refs"].items() if ref == "/stage_strategy_draft/inputSchema/$defs/barCount"} == \
        set(BAR_COUNT) | {"leftBars", "rightBars", "swingLength", "equalBars"}
    for k in (*BAR_COUNT, "leftBars", "rightBars", "swingLength", "equalBars"):
        assert col["types"][k] == "integer" and col["bounds"][k] == BAR_COUNT_BOUNDS, k
    for k in PLAIN_NUMBERS:
        assert col["types"][k] == "number" and col["bounds"][k] == {}, k
    # equalThreshold: >= 0 at 148.1.0, no bound at 149.1.0 (the manager's review: the loosened OUTPUT minimum)
    assert old["bounds"]["equalThreshold"] == {"minimum": 0} and col["bounds"]["equalThreshold"] == {}


def test_all_twenty_one_numeric_fields_keep_their_bounds_through_the_ref():
    """Before the `$ref` fix the derive kept bounds for 9 of the 21 numeric fields: the twelve bar-count knobs read
    as untyped."""
    col = V["reportColumn"]
    numeric = {k for k, t in col["types"].items() if t in ("integer", "number")}
    assert len(numeric) == 21 and set(col["bounds"]) == numeric


@pytest.mark.parametrize("knob,value", [(k, 14) for k in BAR_COUNT] + [(k, 2.0) for k in PLAIN_NUMBERS])
def test_the_new_knobs_are_modelled_per_metric(knob, value):
    """Refused by omega.types.Column until 2026-11-07 (no header token or refusal of theirs rendered). The probe at
    149.1.0 rendered them (MACDhist_fast12slow26sig7, ...) and refused the undeclared ones ("metric 'MACD_LINE' does
    not accept params.period"): MACD_HIST takes fast / slow / signal, as its hint serves."""
    col = Column.model_validate({"metric": "MACD_HIST", "transformId": "value", "timeframe": {"rel": "anchor"},
                                 knob: value})
    expected = [] if knob in ("fast", "slow", "signal") else ["PARAMETER_UNDECLARED"]
    assert _errors(validate_column(col)) == expected


# --- the new transforms: unmeasured until 2026-11-07, measured since -------------------------------------------------
def test_the_five_smoothers_are_measured_as_transform_and_as_chain_outer():
    """Unmeasured (served, never extracted) from 2026-11-07 03:22Z until the refresh folded the 2026-11-06 hints in and
    the probe rendered them the same day (RSI14_rma14, dist_close_rma10, ...)."""
    contract = load()
    # 2026-11-11, contract 168.3.0 (extraction 20261111): no transform is unmeasured, and the five smoothers are
    # measured as chain outers still; the one unmeasured chain outer is `spread`, which 168 added to
    # chainedTransformId (19 -> 20, not in the 149.1.0 enum) and no probe has rendered (_unmeasured_108.json chainOuters)
    # 2026-11-12, contract 169.4.0 (OMEGA v0.13.1): `spread` too is measured and modelled - nothing is unmeasured
    assert contract.unmeasured_transforms == {} and contract.unmeasured_chain_outers == {}
    assert ({"ema"} | NEW_TRANSFORMS).isdisjoint(contract.unmeasured_chain_outers)
    assert {"ema"} | NEW_TRANSFORMS <= set(contract.transforms)
    history = C._load(CONTRACT_DIR / "metrics" / "_unmeasured_108.json")["history149"]
    assert set(history["chainOuters"]) == {"distance", "ema"} | NEW_TRANSFORMS
    assert set(history["chainOuters"]) <= set(V["reportColumn"]["chainedTransformId"]["enum"])
    assert "spread" not in V["reportColumn"]["chainedTransformId"]["enum"]
    assert "spread" in vocabulary()["reportColumn"]["chainedTransformId"]["enum"]


@pytest.mark.parametrize("transform", sorted(NEW_TRANSFORMS))
def test_a_column_using_a_new_transform_validates(transform):
    """Refused TRANSFORM_UNMEASURED until 2026-11-07; both shapes rendered at 149.1.0 (RSI14_<id>14,
    dist_high_<id>10 / dist_close_<id>10)."""
    own = Column.model_validate({"metric": "RSI14", "transformId": transform, "window": 14,
                                 "timeframe": {"rel": "anchor"}})
    assert _errors(validate_column(own)) == []
    chained = Column.model_validate({"metric": "HIGH", "transformId": "distance", "chainedTransformId": transform,
                                     "window": 10, "timeframe": {"rel": "anchor"}})
    assert _errors(validate_column(chained)) == []


# --- the 532 hints at 149.1.0, recorded and not folded in -------------------------------------------------------------
def test_the_hint_record_covers_the_whole_roster_at_149_1_0():
    assert (HINTS["contractVersion"], HINTS["buildSha"]) == ("149.1.0", "aa4ab6407e62bd0c2465ca7790b276b39bbf76d4")
    assert HINTS["roster"] == {"count": 532, "equalsWriteSchemaEnum": True, "measuredInCorpus": 326,
                               "knownByNameOnly": 206}
    assert all("149.1.0" in line for line in HINTS["versionReads"]) and len(HINTS["versionReads"]) >= 3
    assert "0 failed" in HINTS["readBy"] and "NOT folded into the corpus" in HINTS["_what"]


def test_the_refresh_dry_run_found_every_authoring_block_invariant():
    dry = HINTS["refreshDryRun"]
    assert dry["written"] == 532 and dry["failed"] == [] and dry["retired"] == []
    assert set(dry["authoringVariantsPerTransform"].values()) == {1}
    assert dry["catalogueAdded"] == ["cci", "ema", "rma", "rsi", "wma"]
    assert dry["catalogueChanged"] == ["aggregate", "rollingMax", "rollingMin"]


def test_the_five_smoothers_as_served_per_metric():
    new = HINTS["newTransforms"]
    assert {t: v["metricsServing"] for t, v in new.items()} == {t: 165 for t in ("ema", "rma", "wma", "rsi", "cci")}
    assert {t: list(v["windowMaximum"]) for t, v in new.items()} == {
        "ema": ["269"], "rma": ["118"], "wma": ["936"], "rsi": ["118"], "cci": ["936"]}
    assert {t: list(v["windowUnit"]) for t, v in new.items()} == {
        "ema": ["smoothingLength"], "rma": ["wilderLength"], "wma": ["seriesElements"], "rsi": ["wilderChanges"],
        "cci": ["seriesElements"]}
    # as a chain outer the same maximum, on every successor position that serves it
    assert all(v["asChainOuterWindowMaximum"] == {m: 387 for m in v["windowMaximum"]} for v in new.values())


def test_the_knobs_are_served_per_metric_and_the_subjects_four():
    params = HINTS["parameters"]
    assert set(params) == set(NEW_KNOBS) | {"leftBars", "rightBars", "swingLength", "equalBars", "equalThreshold",
                                            "confluenceFilter"}
    assert params["leftBars"]["metrics"] == params["rightBars"]["metrics"] == 7      # the seven swing metrics
    assert params["equalBars"]["metrics"] == params["equalThreshold"]["metrics"] == 2  # EQH, EQL
    assert params["swingLength"]["metrics"] == 6 and params["confluenceFilter"]["metrics"] == 3
    assert HINTS["subjectKinds"] == {"benchmark,evaluated-coin": 489, "evaluated-coin": 25, "market": 13,
                                     "benchmark,evaluated-coin,reference": 4, "reference": 1}
