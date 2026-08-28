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
# Bounds the AGENT-facing catalog publishes for two of the knobs. Task 3 measured
# ENFORCED (2026-08-28): minRiskRewardRatio 5.0 - legal per the published schema -
# was refused at the write validator's input layer with "must be <= 3", the catalog's
# upper edge (bounds_probe_2026-08-28.json). Enforcement lives below the declared
# schema, so violating these is an error, not advice. Only R:R's upper edge was
# probed directly; the rest of these bounds are trusted to the same validator.
CATALOG_BOUNDS: dict = {"minAtrPct": (0.1, 10), "minRiskRewardRatio": (0.5, 3)}


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
                # "error" per the Task 3 measurement: the catalog bound is enforced on
                # the strategy write (R:R 5.0 refused, "must be <= 3", 2026-08-28).
                out.append(Finding("error", "EXECUTION_OUTSIDE_CATALOG_BOUND",
                                   f"execution.{k}",
                                   f"{k}={v} is outside the catalog's {lo}-{hi}, which "
                                   f"the write validator enforces (measured 2026-08-28)"))
    return out
