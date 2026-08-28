"""The execution surface: measured platform defaults and override validation.

Nothing here is designed - every number is measured. Defaults: the viable CREATE
compile's postState (data/audit/execution_surface_ownership_2026-08-28.json), confirmed
identical at 4h by data/audit/defaults_4h_probe_2026-08-28.json (1h and 4h are the only
anchors measured). Bounds enforcement: data/audit/bounds_probe_2026-08-28.json.
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

# Bounds the compile schema publishes (re-verified live 2026-08-28, execution-day
# preflight: zero drift). Params absent here are unbounded in the schema.
SCHEMA_BOUNDS: dict = {
    "minAtrPct": (0.01, 50), "trailingTriggerR": (0, 2),
    "trailingGivebackPct": (25, 55), "trailingBufferPct": (0.01, 1),
    "breakEvenTriggerR": (0.5, 2), "timeDecayIntervalMinutes": (1, 480),
    "timeDecayGracePeriodMinutes": (1, 1440), "timeDecayTightenPct": (0.1, 50),
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
            if not (lo <= v <= hi):
                out.append(Finding("error", "EXECUTION_OUT_OF_BOUNDS", f"execution.{k}",
                                   f"{k}={v} outside the schema bound {lo}-{hi}"))
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
