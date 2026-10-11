"""The execution surface: measured platform defaults and override validation.

Nothing here is designed - every number is measured. Defaults: the viable CREATE
compile's postState (data/audit/execution_surface_ownership_2026-08-28.json), confirmed
identical at 4h by data/audit/defaults_4h_probe_2026-08-28.json (1h and 4h are the only
anchors measured). Bounds enforcement: data/audit/bounds_probe_2026-08-28.json.
SCHEMA_BOUNDS was re-measured against the contract 61.0.1 capture of 2026-09-18; see the
comment on it for the five bounds that moved.
"""
from __future__ import annotations

from .validate import Finding

PLATFORM_EXECUTION_DEFAULTS: dict = {
    "minAtrPct": 0.5, "minRiskRewardRatio": 1.5,
    "minStopLossAtrMultiple": 1, "maxStopLossAtrMultiple": 2,
    "trailingEnabled": True, "trailingTriggerR": 1,
    "trailingGivebackPct": 45, "trailingBufferPct": 0.25,
    "breakEvenEnabled": True, "breakEvenTriggerR": 1.08,
    "timeDecayEnabled": True, "timeDecayIntervalMinutes": 15,
    "timeDecayGracePeriodMinutes": 60, "timeDecayTightenPct": 5,
    "timeDecayMaxTightenPct": 50, "timeDecayStaleThresholdTpProgressPct": 25,
}
EXECUTION_PARAMS = frozenset(PLATFORM_EXECUTION_DEFAULTS)

# Contract 85.0.0 split the flat body into axes, each staged WHOLE (README "Contract
# history - v85"; the v91 schema data/contract/stage_strategy_draft/schema_20261005T194629Z.json
# lists every key below as `required` on its axis). A create therefore sends every dial,
# where the retired compile let omega send none (Decision 1(a)): until a create draft's
# seeded values are read (plan 2026-10-06, measurement M1) omega sends the 08-28 measured
# defaults above. The tuples are in each axis's `required` order.
#
# 2026-10-11, contract 108.0.0 (README "Contract history - v108"): SETUP_GATES is refused as an unrecognized
# key; "the ATR floor minAtrPct is staged in the TRADE_LEVEL_POLICY axis, beside the stop-loss multiples and the
# risk-reward minimum; a TRADE_LEVEL_POLICY stage without it is refused". The 108 capture
# (data/contract/stage_strategy_draft/schema_20261010T215326Z.json) requires the four in the order below.
# SETUP_GATE_DIALS is the retired v91 axis's one dial, kept as history; nothing emits it.
SETUP_GATE_DIALS = ("minAtrPct",)             # RETIRED at contract 108 (was + minAggregateScore, minRequiredCount)
TRADE_LEVEL_DIALS = ("minAtrPct", "minStopLossAtrMultiple", "maxStopLossAtrMultiple", "minRiskRewardRatio")
POSITION_MANAGEMENT_DIALS = (
    "breakEvenEnabled", "breakEvenTriggerR", "trailingEnabled", "trailingTriggerR",
    "trailingGivebackPct", "trailingBufferPct", "timeDecayEnabled",
    "timeDecayGracePeriodMinutes", "timeDecayIntervalMinutes", "timeDecayTightenPct",
    "timeDecayMaxTightenPct", "timeDecayStaleThresholdTpProgressPct",
    "decisionInvalidationExitEnabled",
)
# The thirteenth POSITION_MANAGEMENT dial is not one of the 16 measured on 08-28: the
# compile declared it OPTIONAL and omega never sent it. The axis REQUIRES it. Every record
# on disk reads true - b9438519 (2026-09-05) and the two 09-18 read-backs 43d11467 and
# 824f4343 under data/contract/get_strategy/, plus both records in
# data/audit/drift5_exit_rediscovery_2026-09-04.json - so true is mirrored, not chosen.
# What a create draft seeds for it is part of M1.
POSITION_MANAGEMENT_MIRROR: dict = {"decisionInvalidationExitEnabled": True}

# Bounds the RETIRED compile schema published, as (minimum, maximum); `None` on an edge is
# an open bound the schema did not declare. Since contract 85.0.0 this is a record of a
# retired schema, never a gate (plan 2026-10-06): the v91 axis schemas declare NO numeric
# bound on any dial, and since v89 "a create judges every dial of the new strategy at the
# operator bounds configured now" - in the draft's diagnostics and at commit
# (README "Contract history - v89"). A value outside these edges is a warning.
# First measured 2026-08-28; re-measured against the committed contract 61.0.1 capture
# data/contract/compile_strategy_plan/schema_20260918T083359Z.json, which
# omega.preflight.changelog diffs against the 09-09 capture as exactly five moves:
#   maxStopLossAtrMultiple      bounds {} -> {'maximum': 3}          (new, no minimum)
#   minAtrPct                   bounds {'minimum': 0.01, 'maximum': 50} -> {}  (now unbounded,
#                               so it leaves this table; CATALOG_BOUNDS keeps its 0.1-10)
#   timeDecayGracePeriodMinutes minimum 1 -> 5
#   timeDecayIntervalMinutes    minimum 1 -> 5
#   timeDecayTightenPct         minimum 0.1 -> 0.5
# The measured PLATFORM_EXECUTION_DEFAULTS all sit inside the risen minima - grace 60 >= 5,
# interval 15 >= 5, tighten 5 >= 0.5 - so the default profile omega describes stays legal
# and omega still emits nothing (Decision 1(a), 2026-08-28). The schema also declares a
# multipleOf on these knobs (5, 5 and 0.5 respectively); the preflight walker checks it
# against a real wire body - this table is the min/max surface only.
SCHEMA_BOUNDS: dict = {
    "maxStopLossAtrMultiple": (None, 3), "trailingTriggerR": (0, 2),
    "trailingGivebackPct": (25, 55), "trailingBufferPct": (0.01, 1),
    "breakEvenTriggerR": (0.5, 2), "timeDecayIntervalMinutes": (5, 480),
    "timeDecayGracePeriodMinutes": (5, 1440), "timeDecayTightenPct": (0.5, 50),
    "timeDecayMaxTightenPct": (1, 100), "timeDecayStaleThresholdTpProgressPct": (0, 100),
}
# Bounds the AGENT-facing catalog publishes for two of the knobs - and their MEASURED
# enforcement on the strategy write, which is ASYMMETRIC (2026-08-28):
# minRiskRewardRatio - ENFORCED on BOTH edges at the input-validation layer below the
#   published schema: 5.0 refused "must be <= 3" (bounds_probe_2026-08-28.json), 0.3
#   refused "must be >= 0.5" (bounds_edges_2026-08-28.json). Violations are errors.
# minAtrPct - NOT enforced: 0.05, below the catalog's 0.1 but legal per the schema's
#   0.01-50, compiled viable and persisted un-clamped in postState
#   (bounds_edges_2026-08-28.json). The schema governs the write; outside-catalog
#   values draw a warning for the agent-facing surface, not an error.
CATALOG_BOUNDS: dict = {"minAtrPct": (0.1, 10), "minRiskRewardRatio": (0.5, 3)}
CATALOG_BOUND_ENFORCED: dict = {"minRiskRewardRatio": True, "minAtrPct": False}


def validate_execution(overrides: dict) -> list[Finding]:
    out: list[Finding] = []
    for k, v in overrides.items():
        if k not in EXECUTION_PARAMS:
            out.append(Finding("error", "EXECUTION_UNKNOWN_PARAM", f"execution.{k}",
                               f"{k} is not one of the 16 execution parameters"))
            continue
        if k in SCHEMA_BOUNDS and isinstance(v, (int, float)):
            lo, hi = SCHEMA_BOUNDS[k]
            # An edge is None when the schema declares no bound there (61.0.1:
            # maxStopLossAtrMultiple has a maximum of 3 and no minimum). Skip the open
            # edge, still enforce the closed one.
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                out.append(Finding("warning", "EXECUTION_OUT_OF_BOUNDS", f"execution.{k}",
                                   f"{k}={v} outside the retired 61.0.1 compile schema's bound "
                                   f"{'-inf' if lo is None else lo}-{'inf' if hi is None else hi}; "
                                   f"the v91 axes declare none, and since v89 the operator "
                                   f"bounds in the draft's diagnostics decide"))
        if k in CATALOG_BOUNDS and isinstance(v, (int, float)):
            lo, hi = CATALOG_BOUNDS[k]
            if not (lo <= v <= hi):
                # Severity per the MEASURED per-param enforcement (see the comment on
                # CATALOG_BOUND_ENFORCED): R:R violations refuse at the write, ATR
                # ones pass through un-clamped.
                if CATALOG_BOUND_ENFORCED[k]:
                    out.append(Finding("error", "EXECUTION_OUTSIDE_CATALOG_BOUND",
                                       f"execution.{k}",
                                       f"{k}={v} is outside the catalog's {lo}-{hi}, which "
                                       f"the write validator enforces (measured 2026-08-28)"))
                else:
                    out.append(Finding("warning", "EXECUTION_OUTSIDE_CATALOG_BOUND",
                                       f"execution.{k}",
                                       f"{k}={v} is legal on the strategy write (measured "
                                       f"2026-08-28: persisted un-clamped) but outside the "
                                       f"agent catalog's {lo}-{hi}"))
    return out
