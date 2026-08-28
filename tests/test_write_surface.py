"""What omega emits versus what the write API accepts, and the lookback floor.

Both were found on 2026-08-26 while documenting the session, and both are the same shape
of gap: every verification in this repo compares omega against the READ surface
(preview_strategy_report). These are things only the WRITE surface, or the budget it
charges, can tell you.

Neither is a defect in omega. emit_plan stamps every plan "LOCAL ONLY, not submitted" -
the last mile was deliberately not built. These tests pin the size of it so the gap is a
measured number rather than a vague intention.

2026-08-28: the keyMismatch half of the gap CLOSED - wire() now emits the exact CREATE
request body (schema re-verified live the same day). The execution-surface half (16
parameters) stays pinned open below, awaiting the user's design decisions.
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
def test_wire_is_a_complete_create_request(preset):
    """CLOSED 2026-08-28 (was: 3 rejected keys, 4 missing required ones). wire() now
    emits the exact CREATE body. The old pinned-gap form of this test is preserved in
    git history at a233ec0."""
    emitted = set(plan(PRESETS[preset]).wire())
    assert emitted - API_ACCEPTS == set(), "wire() emits keys the API refuses"
    assert API_REQUIRES - emitted == set(), "wire() omits keys the API requires"


def test_plans_are_still_stamped_local_only():
    """If this ever stops being true, a plan is being submitted and these tests need to
    become a round-trip check instead of a diff."""
    import inspect
    from omega import generate
    assert "LOCAL ONLY, not submitted" in inspect.getsource(generate.emit_plan)


def test_presets_still_emit_no_execution_parameters():
    """CLOSED 2026-08-28 (was: the 16-parameter gap). Decision 1(a): presets emit none and
    the critique states the measured defaults; overrides are explicit per-thesis. The
    old pinned form is preserved in git history."""
    from omega.execution import EXECUTION_PARAMS
    emitted = set(plan(PRESETS["trend-continuation"]).wire())
    assert not (EXECUTION_PARAMS & emitted)
    assert EXECUTION_PARAMS < API_ACCEPTS
    assert "_resolved" in GAP["executionSurfaceNotModelled"]


def test_rules_is_now_the_name():
    w = plan(PRESETS["trend-continuation"]).wire()
    assert "rules" in w and "signalRules" not in w
    assert len(w["rules"]) == 84


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_wire_respects_api_bounds(preset):
    w = plan(PRESETS[preset]).wire()
    assert w["operation"] == "CREATE"
    assert len(w["name"]) <= 50
    assert 1 <= len(w["intentSummary"]) <= 2000
    assert 1 <= len(w["assumptions"]) <= 20
    assert all(1 <= len(a) <= 500 for a in w["assumptions"])
    assert w["coinSelection"]["mode"] in ("ranked", "explicit")


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_create_sections_carry_no_client_section_key(preset):
    """Measured 2026-08-28, first live compile of a generated plan: CREATE refuses ANY
    client-supplied custom sectionKey - REPORT_CUSTOM_SECTION_NOT_OWNED, allowedDomain
    enum []. A strategy that does not exist yet owns no section identities; the server
    mints them (doc 16 already said so for the apply arm). omega's deterministic
    custom:<uuid5> keys stay on the local Report for identity; they must never reach a
    CREATE body. See data/audit/compile_dry_run_2026-08-28-refusal.json."""
    for s in plan(PRESETS[preset]).wire()["sections"]:
        if s["kind"] == "custom":
            assert "sectionKey" not in s, "CREATE must not claim a section identity"


def test_coin_selection_default_is_class_aware():
    """CVD and FLOW_DIVERGENCE are crypto-only (doc 12 + trap 21); FUNDING and
    OPEN_INTEREST are NOT - synthetic perps carry both everywhere. A thesis touching a
    crypto-only module must not default to a universe where its columns render null,
    because null reads FALSE (trap 11). Limit capped to the measured BG-14 boundary,
    2026-08-28: a limit-30 default could never compile (395,404 > 256,000 measured);
    the boundary is 4 (cap_boundary_2026-08-28.json). Old limit in git history."""
    from omega.generate import RANKED_LIMIT_MEASURED_MAX as CAP
    assert plan(PRESETS["mean-reversion"]).wire()["coinSelection"] == {
        "mode": "ranked", "category": "CRYPTO", "limit": CAP}     # weights CVD
    assert plan(PRESETS["trend-continuation"]).wire()["coinSelection"] == {
        "mode": "ranked", "category": "ALL", "limit": CAP}        # no crypto-only module


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
