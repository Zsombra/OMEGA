"""What omega emits versus what the write API accepts, and the lookback floor.

Both were found on 2026-08-26 while documenting the session, and both are the same shape
of gap: every verification in this repo compares omega against the READ surface
(preview_strategy_report). These are things only the WRITE surface, or the budget it
charges, can tell you.

Neither is a defect in omega. emit_plan stamps every plan "LOCAL ONLY, not submitted" -
the last mile was deliberately not built. These tests pin the size of it so the gap is a
measured number rather than a vague intention.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega import contract as C
from omega.generate import PRESETS, plan
from omega.types import Column
from omega.validate import LOOKBACK_FLOOR, validate_column

ROOT = Path(__file__).resolve().parents[1]
GAP = json.loads((ROOT / "data/audit/write_surface_gap.json").read_text(encoding="utf-8"))
FLOOR = json.loads((ROOT / "data/audit/lookback_floor.json").read_text(encoding="utf-8"))

# Read from the live compile_strategy_plan CREATE schema on 2026-08-26.
API_ACCEPTS = {
    "operation", "intentSummary", "assumptions", "coinSelection", "name", "timeframe",
    "sections", "conditions", "description", "tagline", "marketReadText", "rules",
    "minAggregateScore", "minRequiredCount", "minAtrPct", "minRiskRewardRatio",
    "minStopLossAtrMultiple", "maxStopLossAtrMultiple", "trailingEnabled",
    "trailingTriggerR", "trailingGivebackPct", "trailingBufferPct", "breakEvenEnabled",
    "breakEvenTriggerR", "timeDecayEnabled", "timeDecayIntervalMinutes",
    "timeDecayGracePeriodMinutes", "timeDecayTightenPct", "timeDecayMaxTightenPct",
    "timeDecayStaleThresholdTpProgressPct",
}
API_REQUIRES = {"operation", "intentSummary", "assumptions", "coinSelection", "name",
                "timeframe", "sections"}


@pytest.fixture(scope="module")
def contract():
    return C.load()


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_the_emit_compile_gap_is_the_recorded_one(preset):
    """Pinned so the gap shrinks deliberately rather than drifting."""
    emitted = set(plan(PRESETS[preset]).wire())
    # Sets, not sorted lists: the record lists these in logical order (operation first)
    # and order carries no meaning here. Comparing sorted lists would fail on a
    # cosmetic difference and teach us to edit the record instead of reading it.
    assert emitted - API_ACCEPTS == set(GAP["keyMismatch"]["omegaEmitsButTheApiRejects"])
    assert API_REQUIRES - emitted == set(GAP["keyMismatch"]["apiRequiresButOmegaOmits"])


def test_plans_are_still_stamped_local_only():
    """If this ever stops being true, a plan is being submitted and these tests need to
    become a round-trip check instead of a diff."""
    import inspect
    from omega import generate
    assert "LOCAL ONLY, not submitted" in inspect.getsource(generate.emit_plan)


def test_the_execution_surface_is_still_unmodelled():
    """16 parameters. When omega starts emitting them this fails, which is the point -
    the count in the audit record must move at the same time as the code."""
    emitted = set(plan(PRESETS["trend-continuation"]).wire())
    groups = GAP["executionSurfaceNotModelled"]["parameters"]
    execution = {p for g in groups.values() for p in g}
    assert len(execution) == GAP["executionSurfaceNotModelled"]["count"] == 16
    assert not (execution & emitted), "omega now emits execution parameters; update the record"
    assert execution < API_ACCEPTS, "every one must be a field the API actually takes"


def test_rules_is_the_name_not_signalRules():
    """The single cheapest fix in the gap, and worth naming explicitly."""
    emitted = set(plan(PRESETS["trend-continuation"]).wire())
    assert "signalRules" in emitted and "rules" not in emitted
    assert "rules" in API_ACCEPTS and "signalRules" not in API_ACCEPTS


def test_generated_plans_carry_84_rules():
    p = plan(PRESETS["trend-continuation"])
    assert len(p.wire()["signalRules"]) == 84, (
        "84 is the API's maxItems for `rules`; not one has ever been written")


# --- the lookback floor ------------------------------------------------------

def test_offset_over_the_floor_is_an_error(contract):
    """omega previously compared offset against the raw 32 and accepted 16 and 32, both
    of which the platform refuses."""
    for offset, ok in ((0, True), (8, True), (9, False), (16, False), (32, False)):
        col = Column.model_validate({"metric": "CLOSE", "transformId": "value",
                                     "timeframe": {"rel": "anchor"}, "offset": offset})
        errors = [f for f in validate_column(col, section_timeframe=None, path="s",
                                             contract=contract) if f.severity == "error"]
        assert (not errors) is ok, f"offset={offset} should be {'legal' if ok else 'refused'}"


def test_the_floor_matches_the_measurement(contract):
    assert LOOKBACK_FLOOR == 24
    assert FLOOR["theDecidingProbe"]["budgetUsage"]["columnLookback"] == "24/32"
    assert LOOKBACK_FLOOR + 8 == contract.budgets["columnLookback"], (
        "usable offset is cap minus floor; if either moves this arithmetic must be redone")


def test_the_floor_record_does_not_overclaim():
    """Three metrics cannot separate 'global floor' from 'every metric carries 24'. The
    record must keep saying so rather than asserting a mechanism it did not measure."""
    assert len(FLOOR["measured"]["metricsObservedAt24"]) == 3
    assert "cannot separate" in FLOOR["measured"]["_honestLimit"]
