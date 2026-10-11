"""The contract 108.0.0 write surface, saved on disk (2026-10-11).

Source: battlegrid-manager `tests/fixtures/2026-10-11-surface-108.0.0/manager_schemas_108.0.0.json` (the manager's
stored surface, observed 2026-10-10T21:53:26Z, build 1076c4e7; manager commit d7889bb), copied into
`data/contract/stage_strategy_draft/schema_20261010T215326Z.json`. The vendor's changelog for the move is the README
section "Contract history - v108 (conditions are the only entry gate; signal rules are removed)", vendored at
`.agents/skills/battlegrid/README.md` (pack 31.2.94) and saved beside the fixture.

Every assertion below reads the saved capture; none is typed from memory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / "data/contract/stage_strategy_draft/schema_20261010T215326Z.json"
CAPTURE_91 = ROOT / "data/contract/stage_strategy_draft/schema_20261005T194629Z.json"
FIXTURE = Path("C:/Users/rafae/Documents/GitHub/battlegrid-manager/tests/fixtures/2026-10-11-surface-108.0.0/"
               "manager_schemas_108.0.0.json")
TOOLS = ("stage_strategy_draft", "get_strategy_draft", "commit_strategy_draft", "list_strategy_drafts",
         "preview_strategy_report", "get_strategy")
DOC = json.loads(CAPTURE.read_text(encoding="utf-8"))


def _axes(doc: dict) -> dict:
    return doc["stage_strategy_draft"]["inputSchema"]["properties"]["request"]["properties"]["axes"]["properties"]


def test_the_capture_names_its_contract_build_and_source():
    assert DOC["contractVersion"] == "108.0.0"
    assert DOC["buildSha"] == "1076c4e78456424dd92242eeb30701099c6b9146"
    assert DOC["observedAt"].startswith("2026-10-10T21:53:26")
    assert "manager_schemas_108.0.0.json" in DOC["readFrom"] and "d7889bb" in DOC["readFrom"]
    for tool in TOOLS:
        assert {"inputSchema", "outputSchema", "description"} <= set(DOC[tool]), tool


@pytest.mark.skipif(not FIXTURE.exists(), reason="the battlegrid-manager checkout is not beside this repo")
def test_every_tool_entry_is_the_fixtures_own():
    raw = FIXTURE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == DOC["sourceSha256"]
    fixture = json.loads(raw.decode("utf-8"))
    assert (fixture["contractVersion"], fixture["buildSha"], fixture["hash"]) == (
        DOC["contractVersion"], DOC["buildSha"], DOC["surfaceHash"])
    for tool in TOOLS:
        assert DOC[tool] == fixture["tools"][tool], tool


def test_the_stage_tool_declares_eight_axes_and_refuses_the_two_removed_ones():
    """v108: "stage_strategy_draft refuses the SIGNAL_RULES and SETUP_GATES axes as unrecognized keys"; the axes
    object stays additionalProperties:false."""
    axes_node = DOC["stage_strategy_draft"]["inputSchema"]["properties"]["request"]["properties"]["axes"]
    assert axes_node["additionalProperties"] is False
    assert set(_axes(DOC)) == {"IDENTITY", "TIMEFRAME_PROFILE", "REPORT", "MARKET_READ", "CONDITIONS", "ENTRY",
                               "TRADE_LEVEL_POLICY", "POSITION_MANAGEMENT"}
    assert {"SIGNAL_RULES", "SETUP_GATES"} <= set(_axes(json.loads(CAPTURE_91.read_text(encoding="utf-8"))))


def test_min_atr_pct_is_required_on_the_trade_level_policy_axis():
    """v108: "The ATR floor minAtrPct is staged in the TRADE_LEVEL_POLICY axis, beside the stop-loss multiples and
    the risk-reward minimum; a TRADE_LEVEL_POLICY stage without it is refused." """
    tlp = _axes(DOC)["TRADE_LEVEL_POLICY"]
    assert tlp["additionalProperties"] is False
    assert tlp["required"] == ["minAtrPct", "minStopLossAtrMultiple", "maxStopLossAtrMultiple", "minRiskRewardRatio"]
    assert set(tlp["properties"]) == set(tlp["required"])
    assert tlp["properties"]["minAtrPct"] == {"type": "number"}


def test_the_stage_description_names_the_entry_gate():
    """The served description of the CONDITIONS axis: the only deterministic entry gate is a required or a
    verdict-carrying ENTRY condition, else the draft warns NO_ENTRY_CONDITION."""
    text = DOC["stage_strategy_draft"]["description"]
    assert "the only deterministic entry gate" in text
    assert "with no required and no verdict-carrying entry condition the strategy never routes" in text
    assert "NO_ENTRY_CONDITION" in text


def test_the_draft_diagnostics_lose_mismatches_and_warn_only_no_entry_condition():
    """v108: get_strategy_draft.diagnostics.mismatches is gone; the warning enum is NO_ENTRY_CONDITION alone."""
    for tool in ("stage_strategy_draft", "get_strategy_draft"):
        diag = DOC[tool]["outputSchema"]["properties"]["diagnostics"]
        assert diag["required"] == ["errors", "warnings"], tool
        assert "mismatches" not in diag["properties"], tool
        assert diag["properties"]["warnings"]["items"]["properties"]["code"]["enum"] == ["NO_ENTRY_CONDITION"]


def test_a_strategy_read_carries_no_signal_rule_or_gate_field():
    for tool in ("get_strategy", "commit_strategy_draft"):
        strategy = DOC[tool]["outputSchema"]["properties"]["strategy"]
        gone = {"signalRules", "signalRuleTally", "minAggregateScore", "minRequiredCount"}
        assert not gone & set(strategy["properties"]), tool
        assert "minAtrPct" in strategy["required"], tool
