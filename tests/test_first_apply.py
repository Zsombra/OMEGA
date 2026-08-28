"""The first omega-generated strategy ever applied, 2026-08-28, under the user's
explicit per-instance authorization. One compile, one apply, read back, archived
(the user's chosen disposition). Nothing bound, nothing deployed - ever.

These tests pin the record so the claim 'the loop is closed' stays checkable."""
from __future__ import annotations

import json
from pathlib import Path

from omega.execution import EXECUTION_PARAMS, PLATFORM_EXECUTION_DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
APPLY = json.loads(
    (ROOT / "data/audit/first_generated_apply_2026-08-28.json").read_text(encoding="utf-8"))


def test_the_record_exists_and_is_interpreted():
    assert "FILL IN" not in APPLY["_interpretation"]
    assert "loop is closed" in APPLY["_interpretation"]


def test_the_round_trip_is_revision_1_of_the_generated_create():
    rt = APPLY["roundTrip"]
    assert rt["revision"] == 1
    assert rt["name"] == "Trend Continuation"
    assert rt["forkedFromStrategyId"] is None
    assert rt["id"] == APPLY["sequence"]["2_apply"]["appliedImpactVerbatim"]["strategyId"]


def test_the_dense_scorecard_survived():
    rules = APPLY["roundTrip"]["signalRules"]
    assert len(rules) == 84
    assert sum(1 for r in rules if r["allocation"] > 0) == 24


def test_the_persisted_execution_params_are_the_measured_defaults():
    """The CREATE sent none of the 16; the persisted strategy carries all 16 at
    exactly the measured defaults - Decision 1(a) observed on a real write."""
    rt = APPLY["roundTrip"]
    assert {k: rt[k] for k in EXECUTION_PARAMS} == PLATFORM_EXECUTION_DEFAULTS


def test_the_token_is_redacted_and_nothing_was_bound():
    tok = APPLY["sequence"]["1_compile"]["planToken"]
    assert set(tok) == {"_redacted", "length", "sha256"}
    assert APPLY["sequence"]["2_apply"]["appliedImpactVerbatim"]["boundAgentCount"] == 0
    assert APPLY["sequence"]["2_apply"]["appliedImpactVerbatim"]["propagatedAgentCount"] == 0
    assert APPLY["sequence"]["4_archive"]["result"]["isActive"] is False
