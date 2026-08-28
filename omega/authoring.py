"""The authoring surface: what can be said, whether a Thesis says it legally, and
the one-page honest brief (design 2026-08-29). Everything here is DERIVED from the
measured maps and constants, with one exception: MODULE_DESCRIPTIONS, the
plain-language one-liners, which exist nowhere machine-readable and are hand-written."""
from __future__ import annotations

from .execution import (CATALOG_BOUND_ENFORCED, CATALOG_BOUNDS,
                        PLATFORM_EXECUTION_DEFAULTS, SCHEMA_BOUNDS,
                        validate_execution)
from .generate import (CADENCE_FOR_ANCHOR, MODULE_CLAUSES, MODULE_RECIPES,
                       RANKED_LIMIT_MEASURED_MAX, REGIME_TF_FOR_ANCHOR, Thesis)
from .membership import _map
from .validate import Finding

# The one hand-written table: what each module's columns measure, in plain language.
MODULE_DESCRIPTIONS = {
    "BOLLINGER": "price position against the volatility bands (%B, width, touches)",
    "CVD": "cumulative volume delta - net aggressor buying vs selling (crypto-only)",
    "FLOW_DIVERGENCE": "perp-vs-spot flow agreement or divergence (crypto-only)",
    "FUNDING": "perp funding rate level and direction",
    "MACD": "MACD momentum: histogram trend and signal-line crosses",
    "MFI": "money flow index - volume-weighted overbought/oversold",
    "MOVING_AVERAGES": "EMA/SMA stack alignment and distance from the SMA200",
    "OPEN_INTEREST": "open interest level and trend",
    "PRICE_STRUCTURE": "swing highs/lows and position within the recent range",
    "REGIME": "the platform's own trend/volatility/momentum regime labels",
    "RELATIVE_STRENGTH": "PPO/ROC momentum relative to the market",
    "RSI": "RSI level, zone and trajectory",
    "STOCHASTIC": "stochastic %K/%D zone and crosses",
    "SUPPORT_RESISTANCE": "distance to structural support/resistance zones",
    "TREND_STRENGTH": "ADX trend-strength filter (carries no direction of its own)",
    "VOLATILITY": "ATR level and expansion/contraction (filter, no direction)",
    "VOLUME": "volume surges, dry-ups and the OBV trend",
}


def _clause_text(c: dict) -> str:
    col = c["column"]["header"]
    if c["op"] == "is":
        return f"{col} is '{c['label']}'"
    if c["op"] == "in":
        return f"{col} in {c['labels']}"
    if c["op"] == "between":
        return f"{col} between {c['low']} and {c['high']}"
    return f"{col} {c['op']} {c['value']}"


def vocabulary() -> dict:
    """The assistant's complete menu - every module, anchor, universe rule and
    execution knob the platform was MEASURED to accept."""
    sigs = _map()["moduleSignals"]
    modules = {}
    for m in sorted(MODULE_RECIPES):
        spec = MODULE_CLAUSES[m]
        modules[m] = {
            "measures": MODULE_DESCRIPTIONS[m],
            "directional": "up" in spec,
            "readings": {k: _clause_text(spec[k]()) for k in sorted(spec)},
            "signals": sorted(sigs.get(m, [])),
        }
    return {
        "modules": modules,
        "anchors": {a: {"cadence": CADENCE_FOR_ANCHOR[a],
                        "regimeTimeframe": REGIME_TF_FOR_ANCHOR[a]}
                    for a in CADENCE_FOR_ANCHOR},
        "universe": {
            "explicitMaxTickers": 50,
            "rankedMaxLimit": RANKED_LIMIT_MEASURED_MAX,
            "_why": "ranked limit measured 2026-08-28 against BG-14's preview cap for "
                    "the standard report shape; wider reports refuse earlier",
        },
        "execution": {
            "defaults": dict(PLATFORM_EXECUTION_DEFAULTS),
            "schemaBounds": dict(SCHEMA_BOUNDS),
            "catalogBounds": dict(CATALOG_BOUNDS),
            "catalogEnforced": dict(CATALOG_BOUND_ENFORCED),
        },
        "stances": {"ALIGN": "the tape should agree with the direction",
                    "FADE": "the crowd should be leaning the other way"},
    }


DIRECTIONAL_MODULES = frozenset(m for m, s in MODULE_CLAUSES.items() if "up" in s)


def validate_thesis(thesis: Thesis) -> list[Finding]:
    """The guardrails plan() lacks. Each check is a verified footgun or a measured
    bound; nothing here is a style opinion."""
    out: list[Finding] = []
    for m in thesis.modules:
        if m not in MODULE_RECIPES:
            out.append(Finding("error", "THESIS_UNKNOWN_MODULE", f"weights.{m}",
                               f"{m} is not one of the {len(MODULE_RECIPES)} modules - "
                               f"plan() would silently drop it (verified 2026-08-29)"))
    for m, tier in thesis.weights.items():
        if not isinstance(tier, int) or not 0 <= tier <= 3:
            out.append(Finding("error", "THESIS_BAD_WEIGHT", f"weights.{m}",
                               f"allocation tier must be an int 0-3, got {tier!r}"))
    directional = [m for m in thesis.weights if m in DIRECTIONAL_MODULES]
    if len(directional) < 2:
        out.append(Finding("error", "THESIS_TOO_FEW_DIRECTIONAL", "weights",
                           f"only {len(directional)} directional module(s) weighted - "
                           f"below 2, plan() silently emits NO conditions and NO "
                           f"verdicts (verified 2026-08-29)"))
    if thesis.stance not in ("ALIGN", "FADE"):
        out.append(Finding("error", "THESIS_BAD_STANCE", "stance",
                           f"stance must be ALIGN or FADE, got {thesis.stance!r}"))
    if thesis.anchor not in CADENCE_FOR_ANCHOR:
        out.append(Finding("error", "THESIS_UNMEASURED_ANCHOR", "anchor",
                           f"{thesis.anchor!r} is not authorable - the platform's "
                           f"complete anchor set is {sorted(CADENCE_FOR_ANCHOR)} "
                           f"(REPORT_TIMEFRAME_NOT_AUTHORABLE, measured 2026-08-28)"))
    sel = thesis.resolved_coin_selection()
    if sel.get("mode") == "explicit" and len(sel.get("tickers", [])) > 50:
        out.append(Finding("error", "THESIS_UNIVERSE_TOO_WIDE", "coin_selection",
                           f"{len(sel['tickers'])} tickers - the schema caps explicit "
                           f"lists at 50"))
    if sel.get("mode") == "ranked" and sel.get("limit", 0) > RANKED_LIMIT_MEASURED_MAX:
        out.append(Finding("error", "THESIS_UNIVERSE_TOO_WIDE", "coin_selection",
                           f"ranked limit {sel['limit']} exceeds the measured BG-14 "
                           f"boundary {RANKED_LIMIT_MEASURED_MAX} - the compile "
                           f"preview refuses above it (measured 2026-08-28)"))
    feedable = {sid for m, tier in thesis.weights.items() if tier > 0
                for sid in _map()["moduleSignals"].get(m, [])}
    for sid in thesis.required:
        if sid not in feedable:
            out.append(Finding("error", "THESIS_UNFEEDABLE_REQUIRED", f"required.{sid}",
                               f"{sid} is marked required but no weighted module "
                               f"feeds it - it could never fire"))
    out += validate_execution(thesis.execution or {})
    return out
