"""The generated UPDATE (design 2026-08-29, carried onto the v85 draft lifecycle):
axes_update(current) stages the thesis's own axes into an existing strategy's draft and
never moves a dial the thesis does not name. The 2026-08-29 compile UPDATE (wire_update)
sent a dial only when `thesis.execution` named it; a v91 axis is staged WHOLE, so the
dials it does not name come from the strategy's current axes (`current`, as
get_strategy_draft reads them) - never from omega's 08-28 defaults. The record pins for
the live loop follow."""
from __future__ import annotations

from dataclasses import replace

import pytest

from omega.generate import PRESETS, plan

# A tuned existing strategy: every dial differs from omega's 08-28 defaults.
CURRENT = {
    "SETUP_GATES": {"minAggregateScore": 0.4, "minRequiredCount": 0, "minAtrPct": 0.8},
    "TRADE_LEVEL_POLICY": {"minStopLossAtrMultiple": 1.2, "maxStopLossAtrMultiple": 2.5,
                           "minRiskRewardRatio": 1.8},
    "POSITION_MANAGEMENT": {
        "breakEvenEnabled": False, "breakEvenTriggerR": 1.5, "trailingEnabled": False,
        "trailingTriggerR": 1.2, "trailingGivebackPct": 30, "trailingBufferPct": 0.5,
        "timeDecayEnabled": False, "timeDecayGracePeriodMinutes": 120,
        "timeDecayIntervalMinutes": 30, "timeDecayTightenPct": 2, "timeDecayMaxTightenPct": 20,
        "timeDecayStaleThresholdTpProgressPct": 10, "decisionInvalidationExitEnabled": False},
}


def test_an_update_never_stages_entry_or_request_fields():
    """v85: "Axes you omit keep the values the draft has" - so leaving ENTRY out of an
    update is how an existing strategy's entry axis is never touched (the 2026-08-29 rule:
    its semantics on an update are unmeasured). strategyId and draftVersion are request
    fields, never axes."""
    u = plan(PRESETS["trend-continuation"]).axes_update(CURRENT)
    assert "ENTRY" not in u
    assert not {"strategyId", "draftVersion", "expectedRevision"} & set(u)


def test_an_update_without_overrides_keeps_every_dial_of_the_strategy():
    """The review of 2026-10-06: staging the 08-28 defaults whole would reset a tuned
    strategy (trailing off -> on, minAtrPct 0.8 -> 0.5). The dial axes are left out, and
    SETUP_GATES - whole, and carrying the thesis's gate - keeps the strategy's minAtrPct."""
    p = plan(PRESETS["trend-continuation"])
    u = p.axes_update(CURRENT)
    assert "TRADE_LEVEL_POLICY" not in u and "POSITION_MANAGEMENT" not in u
    assert u["SETUP_GATES"]["minAtrPct"] == 0.8
    assert u["SETUP_GATES"]["minAggregateScore"] == p.thesis.gate
    a = p.axes()
    for k in ("IDENTITY", "TIMEFRAME_PROFILE", "REPORT", "MARKET_READ", "CONDITIONS", "SIGNAL_RULES"):
        assert u[k] == a[k], k


def test_an_override_moves_exactly_its_own_dial_on_an_update():
    """The 2026-08-29 proof change (one R:R override) lands on TRADE_LEVEL_POLICY, whose
    other two dials keep the strategy's values; no other dial axis is staged."""
    t = replace(PRESETS["trend-continuation"], execution={"minRiskRewardRatio": 2.0})
    up = plan(t).axes_update(CURRENT)
    assert up["TRADE_LEVEL_POLICY"] == {**CURRENT["TRADE_LEVEL_POLICY"], "minRiskRewardRatio": 2.0}
    assert "POSITION_MANAGEMENT" not in up
    t = replace(PRESETS["trend-continuation"], execution={"trailingTriggerR": 1.5})
    up = plan(t).axes_update(CURRENT)
    assert up["POSITION_MANAGEMENT"] == {**CURRENT["POSITION_MANAGEMENT"], "trailingTriggerR": 1.5}
    assert "TRADE_LEVEL_POLICY" not in up


def test_an_update_refuses_rather_than_invent_a_dial_it_cannot_read():
    p = plan(PRESETS["trend-continuation"])
    with pytest.raises(ValueError, match="minAtrPct"):
        p.axes_update(None)
    with pytest.raises(ValueError, match="minAtrPct"):
        p.axes_update({})
    # a thesis that names minAtrPct needs no read for SETUP_GATES
    t = replace(PRESETS["trend-continuation"], execution={"minAtrPct": 0.6})
    assert plan(t).axes_update(None)["SETUP_GATES"]["minAtrPct"] == 0.6
    # a dial override on an axis the read does not carry cannot be completed
    t = replace(PRESETS["trend-continuation"], execution={"minAtrPct": 0.6, "trailingTriggerR": 1.5})
    with pytest.raises(ValueError, match="POSITION_MANAGEMENT"):
        plan(t).axes_update(None)


# --- the live loop, 2026-08-29: pinned record ---------------------------------

import json
from pathlib import Path

from omega.execution import PLATFORM_EXECUTION_DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
REC = json.loads(
    (ROOT / "data/audit/first_generated_update_2026-08-29.json").read_text(encoding="utf-8"))


def test_the_loop_is_recorded_end_to_end():
    assert set(REC["probes"]) >= {"preState", "restore", "compile", "apply",
                                  "readBack", "archive"}
    assert "FILL IN" not in REC["_interpretation"]
    assert REC["verdicts"]["sectionKeysOnUpdate"] in ("PRESERVED", "LOCKSTEP_REMINT")
    assert REC["verdicts"]["rrDiffAxis"] == "tradeLevelPolicy"


def test_the_override_landed_and_nothing_else_moved():
    pre = REC["probes"]["preState"]["strategy"]
    post = REC["probes"]["readBack"]["strategy"]
    assert pre["minRiskRewardRatio"] == 1.5 and post["minRiskRewardRatio"] == 2
    for k in PLATFORM_EXECUTION_DEFAULTS:
        if k != "minRiskRewardRatio":
            assert post[k] == pre[k]
    assert post["signalRules"] == pre["signalRules"]
    assert post["marketReadText"] == pre["marketReadText"]
    strip = lambda secs: [{k: v for k, v in s.items() if k != "sectionKey"}
                          for s in secs]
    assert strip(post["sections"]) == strip(pre["sections"])
    if REC["verdicts"]["sectionKeysOnUpdate"] == "PRESERVED":
        assert post["sections"] == pre["sections"]


def test_the_remint_was_lockstep_consistent():
    """The loop's one platform finding: a full-body UPDATE re-mints custom section
    identities even when the re-sent report is byte-identical - but re-resolves every
    condition reference to the new keys. Semantically safe; identity churns."""
    import re
    post = REC["probes"]["readBack"]["strategy"]
    post_keys = {s["sectionKey"] for s in post["sections"]}
    refs = set(re.findall(r'custom:[0-9a-f-]{36}', json.dumps(post["conditions"])))
    assert refs and refs <= post_keys
    pre_keys = {s["sectionKey"] for s in REC["probes"]["preState"]["strategy"]["sections"]}
    assert post_keys.isdisjoint(pre_keys), "keys re-minted - this pin documents it"


def test_the_lifecycle_ends_where_it_started():
    assert REC["probes"]["readBack"]["strategy"]["isActive"] is True
    assert REC["probes"]["archive"]["strategy"]["isActive"] is False
    assert REC["probes"]["apply"]["appliedImpact"]["committedRevision"] == 4
    assert REC["probes"]["apply"]["appliedImpact"]["boundAgentCount"] == 0
    assert REC["probes"]["apply"]["appliedImpact"]["propagatedAgentCount"] == 0
    tok = REC["probes"]["compile"].get("planToken")
    assert tok is not None and set(tok) == {"_redacted", "length", "sha256"}
