"""What omega emits versus what the write API accepts, and the lookback floor.

Both were found on 2026-08-26 while documenting the session, and both are the same shape
of gap: every verification in this repo compares omega against the READ surface
(preview_strategy_report). These are things only the WRITE surface, or the budget it
charges, can tell you.

Neither is a defect in omega. emit_plan stamps every plan "LOCAL ONLY, not submitted" -
the last mile was deliberately not built. These tests pin the size of it so the gap is a
measured number rather than a vague intention.

2026-08-28: the keyMismatch half of the gap CLOSED - the generator emitted the exact
compile CREATE body (schema re-verified live the same day). Contract 85.0.0 removed the
compile; the generator now emits the ten axes of a CREATE stage_strategy_draft, pinned
below against the saved 91.0.0 schema. The compile pins stay, as history, against the
three named compile captures.
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

# The RETIRED compile CREATE surface, read from the live compile_strategy_plan schema on
# 2026-08-26; re-read 2026-08-30 (`entry` published and REQUIRED on CREATE) and 2026-09-04
# (an optional top-level `decisionInvalidationExitEnabled`). Kept to pin the three named
# compile captures below; the tool itself was removed at contract 85.0.0.
API_ACCEPTS = {
    "operation", "intentSummary", "assumptions", "coinSelection", "name", "timeframe",
    "sections", "conditions", "description", "tagline", "marketReadText", "rules",
    "minAggregateScore", "minRequiredCount", "minAtrPct", "minRiskRewardRatio",
    "minStopLossAtrMultiple", "maxStopLossAtrMultiple", "trailingEnabled",
    "trailingTriggerR", "trailingGivebackPct", "trailingBufferPct", "breakEvenEnabled",
    "breakEvenTriggerR", "timeDecayEnabled", "timeDecayIntervalMinutes",
    "timeDecayGracePeriodMinutes", "timeDecayTightenPct", "timeDecayMaxTightenPct",
    "timeDecayStaleThresholdTpProgressPct", "entry", "decisionInvalidationExitEnabled",
}
API_REQUIRES = {"operation", "intentSummary", "assumptions", "coinSelection", "name",
                "timeframe", "sections", "entry"}


@pytest.fixture(scope="module")
def contract():
    return C.load()


def _axis_schemas():
    root = C.stage_schema()["stage_strategy_draft"]["inputSchema"]
    return root["properties"]["request"]["properties"]["axes"]["properties"]


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_axes_are_a_complete_create_stage(preset):
    """Every axis a create sends is one the v91 schema declares, and each carries exactly
    the keys its axis declares, every required one included (each axis is staged WHOLE)."""
    schemas = _axis_schemas()
    axes = plan(PRESETS[preset]).axes()
    assert set(axes) == set(schemas)
    for name, value in axes.items():
        declared = set(schemas[name]["properties"])
        assert set(value) - declared == set(), f"{name} emits keys the axis refuses"
        assert set(schemas[name]["required"]) - set(value) == set(), f"{name} omits required keys"


def test_plans_are_still_stamped_local_only():
    """If this ever stops being true, a plan is being submitted and these tests need to
    become a round-trip check instead of a diff."""
    import inspect
    from omega import generate
    assert "LOCAL ONLY, not submitted" in inspect.getsource(generate.emit_plan)


def test_the_execution_surface_gap_stays_resolved():
    """CLOSED 2026-08-28 (was: the 16-parameter gap). Since v85 the dials ride whole on
    their axes (tests/test_execution.py); the gap record keeps its resolution."""
    assert "_resolved" in GAP["executionSurfaceNotModelled"]


def test_signal_rules_carry_the_dense_84_named_by_the_schema_enum():
    """`rules` is still the name (the read-back calls them `signalRules`); the axis enum
    names exactly the 84 signals the repo's module map holds."""
    rules = plan(PRESETS["trend-continuation"]).axes()["SIGNAL_RULES"]["rules"]
    enum = _axis_schemas()["SIGNAL_RULES"]["properties"]["rules"]["items"]["properties"]["signalId"]["enum"]
    assert len(rules) == 84 == len(enum)
    assert {r["signalId"] for r in rules} == set(enum)


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_create_sections_carry_no_client_section_key(preset):
    """Measured 2026-08-28, first live compile of a generated plan: CREATE refuses ANY
    client-supplied custom sectionKey - REPORT_CUSTOM_SECTION_NOT_OWNED, allowedDomain
    enum []. A strategy that does not exist yet owns no section identities; the server
    mints them (doc 16 already said so for the apply arm). omega's deterministic
    custom:<uuid5> keys stay on the local Report for identity; they never reach a create
    draft's REPORT axis either (acceptance there is unmeasured).
    See data/audit/compile_dry_run_2026-08-28-refusal.json."""
    for s in plan(PRESETS[preset]).axes()["REPORT"]["sections"]:
        if s["kind"] == "custom":
            assert "sectionKey" not in s, "a create must not claim a section identity"


def test_coin_selection_default_is_class_aware():
    """CVD and FLOW_DIVERGENCE are crypto-only (doc 12 + trap 21); FUNDING and
    OPEN_INTEREST are NOT - synthetic perps carry both everywhere. A thesis touching a
    crypto-only module must not default to a universe where its columns render null,
    because null reads FALSE (trap 11). Limit capped to the measured BG-14 boundary,
    2026-08-28: a limit-30 default could never compile (395,404 > 256,000 measured);
    the boundary is 4 (cap_boundary_2026-08-28.json). Since v85 the selection is an
    input of preview_strategy_report only."""
    from omega.generate import RANKED_LIMIT_MEASURED_MAX as CAP
    assert plan(PRESETS["mean-reversion"]).preview_request()["coinSelection"] == {
        "mode": "ranked", "category": "CRYPTO", "limit": CAP}     # weights CVD
    assert plan(PRESETS["trend-continuation"]).preview_request()["coinSelection"] == {
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


# --- pins vs the NAMED schema captures --------------------------------------------------
#
# 2026-09-05 was the first live preflight run (contract 51-era). 2026-09-18 is the current
# capture (contract 61.0.1); 2026-09-09 (contract 54.1.0) sits between them. All three are
# pinned: the top-level write surface did not move across them - 61.0.0 moved `entry` and
# `conditions[]`, not the request's own properties - and asserting that explicitly is what
# makes "unchanged" a measurement rather than an assumption.

SCHEMA_CAPTURE_2026_09_05 = ROOT / "data/contract/compile_strategy_plan/schema_20260905T011443Z.json"
SCHEMA_CAPTURE_2026_09_09 = ROOT / "data/contract/compile_strategy_plan/schema_20260909T080307Z.json"
SCHEMA_CAPTURE_2026_09_18 = ROOT / "data/contract/compile_strategy_plan/schema_20260918T083359Z.json"


@pytest.mark.parametrize("capture", [SCHEMA_CAPTURE_2026_09_05, SCHEMA_CAPTURE_2026_09_09,
                                     SCHEMA_CAPTURE_2026_09_18],
                         ids=["2026-09-05", "2026-09-09", "2026-09-18"])
def test_api_pins_agree_with_the_named_schema_capture(capture):
    """A green suite proves pin-vs-capture agreement for THESE dated captures, not platform
    agreement. The preflight's gate never reads a committed capture (design 2026-09-04,
    'nothing stored in the repo is ever the truth for a verdict')."""
    from omega import preflight as P
    definition = json.loads(capture.read_text(encoding="utf-8"))["response"]
    arms, root = P.resolve_arms(definition)
    create = P.deref(arms["CREATE"], root)
    assert set(create["properties"]) == API_ACCEPTS
    assert set(create["required"]) == API_REQUIRES


def test_entry_keys_match_the_v91_entry_arm():
    """The regression this exists for: on 2026-09-09 contract 54.1.0 removed
    `entry.levelSource`, and 60.0.0 took `confirmTf`, `closes` and `bandAtrMultiple` out of
    the entry object, each time while omega still sent the key. v85 then made the entry a
    union on `trigger` whose ON_CANDLE_CLOSE arm is `trigger` ALONE ("naming either dial is
    refused"). Pin both directions against that arm of the saved 91.0.0 schema."""
    arms = _axis_schemas()["ENTRY"]["properties"]["entry"]["anyOf"]
    [close_arm] = [a for a in arms if "ON_CANDLE_CLOSE" in a["properties"]["trigger"]["enum"]]
    assert set(close_arm["properties"]) == {"trigger"} and close_arm["additionalProperties"] is False
    for name in sorted(PRESETS):
        emitted = plan(PRESETS[name]).axes()["ENTRY"]["entry"]
        assert set(emitted) == set(close_arm["properties"]) == set(close_arm["required"]), name
        assert emitted["trigger"] in close_arm["properties"]["trigger"]["enum"]


# --- the v91 write surface: the strategy draft lifecycle -------------------------------
#
# v85 retired compile_strategy_plan with no alias (README "Contract history — v85"); a
# strategy changes only through get_strategy_draft -> stage_strategy_draft ->
# commit_strategy_draft. The input schemas of the six draft tools at contract 91.0.0 are
# saved verbatim from battlegrid-manager's stored surface; the manifest names that file and
# retires the two pre-v84 capture directories (plan 2026-10-06, Work step 1).

V91_TOOLS = {"stage_strategy_draft", "get_strategy_draft", "commit_strategy_draft",
             "discard_strategy_draft", "list_strategy_drafts", "preview_strategy_report"}
V91_AXES = {"IDENTITY", "TIMEFRAME_PROFILE", "REPORT", "MARKET_READ", "CONDITIONS", "ENTRY",
            "SETUP_GATES", "TRADE_LEVEL_POLICY", "POSITION_MANAGEMENT", "SIGNAL_RULES"}


def test_manifest_names_the_v91_draft_schema_and_retires_the_compile_captures():
    manifest = json.loads((ROOT / "data/contract/_manifest.json").read_text(encoding="utf-8"))
    ws = manifest["writeSurface"]
    assert ws["servedContractVersion"] == "91.0.0"
    assert ws["schema"] == "data/contract/stage_strategy_draft/schema_20261005T194629Z.json"
    assert (ROOT / ws["schema"]).is_file()
    retired = manifest["retired"]
    assert set(retired) == {"data/contract/compile_strategy_plan/", "data/contract/get_strategy/"}
    for path in retired:                         # kept on disk, never deleted
        assert any((ROOT / path).glob("*.json")), path
    # the metric/transform extraction is a separate snapshot and keeps its own version
    assert manifest["servedContractVersion"] == "61.2.0"


def test_the_named_v91_schema_holds_the_six_draft_tools_and_the_ten_axes():
    doc = C.stage_schema()
    assert doc["contractVersion"] == "91.0.0"
    assert V91_TOOLS <= set(doc)
    axes = doc["stage_strategy_draft"]["inputSchema"]["properties"]["request"]["properties"]["axes"]
    assert set(axes["properties"]) == V91_AXES
    assert axes["additionalProperties"] is False
