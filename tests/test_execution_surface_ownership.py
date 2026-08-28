"""Where the 16 execution parameters live - measured 2026-08-28, user-prompted.

The user recalled risk/reward being configured at AGENT creation. Measured across every
MCP-visible surface: all 16 are STRATEGY fields (compile schemas take them, TRAJ-03
stores tuned values, the compile postState fills defaults), while the agent owns only
the capital block (USD caps, leverage, slippage, sizing presets). These tests pin the
record and cross-check it against the compile record its defaults were read from, so a
quiet edit to either file fails loudly.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWN = json.loads((ROOT / "data/audit/execution_surface_ownership_2026-08-28.json")
                 .read_text(encoding="utf-8"))
COMPILE = json.loads((ROOT / "data/audit/compile_dry_run_2026-08-28-small.json")
                     .read_text(encoding="utf-8"))

EXEC_PARAMS = [
    "minAtrPct", "minRiskRewardRatio", "minStopLossAtrMultiple", "maxStopLossAtrMultiple",
    "trailingEnabled", "trailingTriggerR", "trailingGivebackPct", "trailingBufferPct",
    "breakEvenEnabled", "breakEvenTriggerR",
    "timeDecayEnabled", "timeDecayIntervalMinutes", "timeDecayGracePeriodMinutes",
    "timeDecayTightenPct", "timeDecayMaxTightenPct", "timeDecayStaleThresholdTpProgressPct",
]


def test_the_recorded_defaults_match_the_compile_they_came_from():
    """The ownership record's platformDefaults were read out of the viable compile's
    postState; the two audit files must agree field for field."""
    ps = COMPILE["responseVerbatim"]["approvedPlan"]["postState"]
    rec = OWN["evidence"]["platformDefaults_fromCompilePostState"]
    for p in EXEC_PARAMS:
        assert rec[p] == ps[p], f"{p}: record says {rec[p]!r}, compile postState {ps[p]!r}"


def test_the_agent_surface_carries_no_execution_parameter():
    """Two live agent reads, identical capital-only key sets - and not one of the 16."""
    reads = OWN["evidence"]["agentReads"]
    keysets = [v for k, v in reads.items() if not k.startswith("_")]
    assert len(keysets) == 2 and keysets[0] == keysets[1]
    assert not set(EXEC_PARAMS) & set(keysets[0])
    assert {"maxLeverage", "maxConcurrentExposureUsd", "positionSizePresets"} <= set(keysets[0])


def test_traj03_diverges_from_defaults_in_exactly_three_fields():
    """The tuned strategy vs the measured defaults: minAtrPct, trailingTriggerR and
    trailingGivebackPct moved; the other 13 sit at the default. If this ever changes,
    someone edited a record - both are point-in-time snapshots of 2026-08-28."""
    tuned = OWN["evidence"]["strategyRead_TRAJ03_rev7"]
    defaults = OWN["evidence"]["platformDefaults_fromCompilePostState"]
    moved = sorted(p for p in EXEC_PARAMS if tuned[p] != defaults[p])
    assert moved == ["minAtrPct", "trailingGivebackPct", "trailingTriggerR"]


def test_the_verdict_is_strategy_owned_with_limits_stated():
    assert OWN["verdict"]["the16ExecutionParameters"].startswith("STRATEGY-owned")
    assert len(OWN["honestLimits"]) >= 3, (
        "the record must keep saying what it could NOT see (web UI, one-compile "
        "defaults, bounds enforcement)")
