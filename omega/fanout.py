"""Predict the output headers a column compiles to, and cost a report against the budgets.

The 32-columns-per-section limit is rarely what bites. `trajectory` fans out to
window+1 headers, so header count - and the ~16000 token budget it drives - is the
real constraint. This module makes that visible before you submit.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contract import Contract, load
from .types import Column, CustomSection, PlatformSection, Report

REL_INFIX = {"anchor": "", "lower": "_ltf_", "regime": "_htf_"}


def column_timeframe(column: Column, section: CustomSection, anchor: str, contract: Contract) -> str | None:
    """The distinct timeframe a candle column spends: the rel resolved for the anchor, else the
    abs. (A section override no longer exists - 48.0.0 - and omega.validate refuses one, so the
    section never decides it.) `regime` resolves to null in the authoring contract
    (composition_rules.timeframeResolution: it binds from the strategy's regimeTimeframe, 04)
    yet it IS a distinct timeframe - a 1h preview holding anchor, lower and regime columns
    read budgetUsage.distinctTimeframes.used 3 (data/contract/columns/_renders_tfvariants.json,
    2026-08-24) - so it counts as the literal "regime". None for a timeless metric."""
    if contract.metric(column.metric).is_timeless:
        return None
    rel = getattr(column.timeframe, "rel", None)
    if rel is None:
        return getattr(column.timeframe, "abs", None)
    return contract.resolve_timeframe(rel, anchor) or rel

# APPROXIMATE. Three live preview_strategy_report renders (o200k_base):
#     6 headers /  2 columns / 1 section ->  164 tokens  (27.3 per header)
#    33 headers / 13 columns / 1 section ->  976 tokens  (29.6 per header)
#    34 headers / 11 columns / 2 sections -> 824 tokens  (24.2 per header)
# Note sample 3 has MORE headers than sample 2 but FEWER tokens: the cost is dominated
# by per-metric glossary prose, not by header count, so no simple linear model fits.
# A two-parameter fit on the first two samples looked accurate to 1% and then missed
# the third by 13% - it was overfitting.
# Treat this as a planning aid with roughly +/-15% error. preview_strategy_report
# returns the server's own estimatedTokens as used/cap and is authoritative.
TOKENS_PER_HEADER = 27
TOKEN_ESTIMATE_ERROR_PCT = 15


@dataclass(frozen=True)
class Output:
    header: str
    kind: str
    vocabulary: tuple[str, ...] = ()

    @property
    def condition_operators(self) -> list[str]:
        ops = {
            "numeric": ["lt", "lte", "gte", "gt", "between"],
            "rank": ["lt", "lte", "gte", "gt", "between"],
            # MEASURED (preview_strategy_report, detail "detailed", 108.4.0, 2026-10-13, data/contract/columns/operators_108_4_2026-10-13/base.json):
            # a date header (settledAt) is served NO operators - as SETTLED_AT was on 2026-08-25 (cookbook trap 24)
            "date": [],
            "classification": ["is", "in"],
            "direction": ["is", "in"],
            "event": ["is", "in"],
            "boolean": ["is", "in"],          # measured 2026-10-13: doji is served is/in (+ enters/exits)
        }
        return ops.get(self.kind, [])


def _infix(column: Column) -> str:
    rel = getattr(column.timeframe, "rel", None)
    return REL_INFIX.get(rel, "") if rel else ""


def _token(column: Column, contract: Contract) -> str:
    """The metric's header token: `<code>[_ltf|_htf|_<abs>][_dev][_o<N>]` (contract 109, measured 2026-10-13 -
    data/contract/columns/header_tokens_2026-10-13.json; the vendor pack 31.2.98 states the same order).

    - the timeframe part: `_ltf` / `_htf` for rel lower / regime (REL_INFIX), `_<tf>` for ANY pinned `abs` - even one
      equal to the anchor (`ADX_1h` at a 1h anchor) - and nothing at rel anchor;
    - `_dev` when the column STORES `bars: "all"` (Developing), at any timeframe; `closed` or unset adds nothing;
    - `_o<N>` for an `offset` N > 0, which only `value` reads.
    Until 2026-10-13 omega emitted only the rel part, so `RSI14_1d`, `RSI7_o1` and `ADX_dev_t2` were mispredicted -
    and offset no longer collides two `value` columns (cookbook trap 20 is history)."""
    code = contract.metric(column.metric).code
    rel = getattr(column.timeframe, "rel", None)
    tf = REL_INFIX.get(rel, "").rstrip("_") if rel else f"_{column.timeframe.abs}"
    dev = "_dev" if column.bars == "all" else ""
    off = f"_o{column.offset}" if column.offset and column.transformId == "value" else ""
    return f"{code}{tf}{dev}{off}"


def _stage1_header(column: Column, contract: Contract) -> str:
    """Header produced by the first transform stage (before any chaining): the token, shaped by the transform.

    Every branch is the token plus the transform's suffix (live renders: close_ltf_er, ADX_ltf_zone, MACD_ltf_cross,
    ADX_ltf_rank_hi, dist_VWAP_4h, EMA5_4h_EMA13_spread, high_4h_dev_mean10, bbUpper_4h_lvl_b25); `distance` is the one
    PREFIX shape (`dist_<token>`)."""
    token, tid = _token(column, contract), column.transformId

    if tid == "distance":
        return f"dist_{token}"
    if tid == "spread":
        operand = contract.metric(column.inputs[0].metric).code if column.inputs else "?"
        return f"{token}_{operand}_spread"
    if tid == "efficiency":
        return f"{token}_er"
    if tid == "maxShare":
        return f"{token}_maxShare"
    if tid == "aggregate":
        return f"{token}_mean{column.window or 24}"
    if tid == "bandTouch":                 # retired at v100; kept for the history records
        return f"{token}_touch"
    if tid == "classifyZone":
        return f"{token}_zone"
    if tid == "levelInteraction":
        # Measured 2026-10-13 (get_strategy_column_contract, levelInteraction_108_4_2026-10-13.json): bbUpper_lvl,
        # VWAP_ltf_lvl, and a non-zero buffer names the header - bbUpper_lvl_b25 (bbUpper_4h_lvl_b25 pinned).
        return f"{token}_lvl" + (f"_b{column.buffer}" if column.buffer else "")
    if tid == "crossDetect":
        return f"{token}_cross"
    if tid == "classifyState":          # platform-only, listed for completeness
        return f"{token}_state"
    if tid == "rank":
        return f"{token}_rank_{column.ordering or 'hi'}"
    if tid.startswith("nearestZone"):
        # Verified against live renders (data/contract/columns/_renders_coverage.json),
        # which corrected two guesses here:
        #   - `age` carries its unit: zones_support_age_h, not zones_support_age
        #   - the side is abbreviated ASYMMETRICALLY - "resistance" becomes "resist"
        #     while "support" stays whole
        suffix = {"nearestZoneType": "type", "nearestZoneRange": "range",
                  "nearestZoneDist": "dist", "nearestZoneAge": "age_h"}[tid]
        side = "resist" if column.side == "resistance" else column.side
        return f"{token}_{side}_{suffix}"
    if tid == "count":
        return f"{token}_count"
    # value and trajectory key off the bare token (trajectory adds its slots in outputs_for)
    return token


def outputs_for(column: Column, contract: Contract | None = None) -> list[Output]:
    """The output headers this column compiles to, in order."""
    c = contract or load()
    m = c.metric(column.metric)
    base = _stage1_header(column, c)
    effective = column.chainedTransformId or column.transformId

    # chained rank collapses the stage-1 series to a single ordinal
    if column.chainedTransformId == "rank":
        return [Output(f"{base}_rank_{column.ordering or 'hi'}", "rank")]

    if effective == "trajectory":
        window = column.window or 4
        slot_kind = m.native_output["kind"] if column.transformId == "trajectory" else "numeric"
        vocab = tuple(m.vocab or ()) if column.transformId == "trajectory" else ()
        outs = [Output(f"{base}_t{n}", slot_kind, vocab) for n in range(window - 1, 0, -1)]
        outs.append(Output(f"{base}_now", slot_kind, vocab))
        outs.append(Output(f"{base}_trend", "direction", ("rising", "falling", "flat")))
        return outs

    if effective in ("efficiency", "maxShare"):
        return [Output(base if column.chainedTransformId is None else f"{base}_er", "numeric")]
    if effective == "aggregate" and column.chainedTransformId:
        return [Output(f"{base}_mean{column.window or 24}", "numeric")]

    # single-output transforms
    tid = column.transformId
    if tid in ("classifyZone", "bandTouch", "crossDetect", "nearestZoneType", "levelInteraction"):
        kind = "classification"
    elif tid == "rank":
        kind = "rank"
    elif tid in ("value",):
        kind = m.native_output["kind"]
    else:
        kind = "numeric"
    # vocabularies confirmed against preview_strategy_report renders
    vocab = tuple(m.vocab or ()) if tid == "value" else ()
    if tid == "bandTouch":
        vocab = ("upper", "lower", "none")
    elif tid == "classifyZone":
        vocab = ("overbought", "oversold", "neutral")
    elif tid == "crossDetect":
        vocab = ("Bullish", "Bearish")
    elif tid == "levelInteraction":       # measured 2026-10-13, conditionOperators is/in/enters/exits
        vocab = ("touch_from_below", "touch_from_above", "reject_from_below", "reject_from_above", "none")
    elif tid == "classifyState":
        vocab = ()          # platform-only; vocabulary varies per metric
    return [Output(base, kind, vocab)]


@dataclass
class BudgetReport:
    sections: int
    columns: int
    headers: int
    distinct_timeframes: list[str]
    estimated_tokens: int
    budgets: dict[str, int]
    breaches: list[str]

    @property
    def ok(self) -> bool:
        return not self.breaches

    def render(self) -> str:
        b = self.budgets
        lines = [
            f"sections            {self.sections:>5} / {b['sections']}",
            f"columns             {self.columns:>5}",
            f"output headers      {self.headers:>5}   <- the real cost driver",
            f"distinct timeframes {len(self.distinct_timeframes):>5} / {b['distinctTimeframes']}  {self.distinct_timeframes}",
            f"estimated tokens   ~{self.estimated_tokens:>5}"
            f"   (+/-{TOKEN_ESTIMATE_ERROR_PCT}%; what the agent reads - no platform token cap since contract 92)",
        ]
        if self.breaches:
            lines.append("")
            lines += [f"BREACH: {x}" for x in self.breaches]
        else:
            lines.append("")
            lines.append("within every budget")
        return "\n".join(lines)


def cost_report(report: Report, contract: Contract | None = None) -> BudgetReport:
    c = contract or load()
    columns = headers = 0
    timeframes: set[str] = set()

    for section in report.sections:
        if isinstance(section, PlatformSection):
            tmpl = c.platform_templates.get(section.sectionKey)
            if tmpl:
                columns += len(tmpl["columns"])
                # platform columns are opaque; charge one header each as a floor
                headers += len(tmpl["columns"])
            continue
        assert isinstance(section, CustomSection)
        for col in section.columns:
            if col.metric not in c.metrics:
                continue
            columns += 1
            headers += len(outputs_for(col, c))
            tf = column_timeframe(col, section, report.anchor, c)
            if tf:
                timeframes.add(tf)

    tokens = headers * TOKENS_PER_HEADER
    b = c.budgets
    breaches = []
    if len(report.sections) > b["sections"]:
        breaches.append(f"sections {len(report.sections)} > {b['sections']}")
    if len(timeframes) > b["distinctTimeframes"]:
        breaches.append(f"distinct timeframes {len(timeframes)} > {b['distinctTimeframes']}")
    # Contract 92.0.0 retired budgets.estimatedTokens (the preview is capped in result characters now,
    # previewExecutionLimits.maxResultChars). A budget file that still names a token cap - a record older
    # than v92 - is honoured; the served one has none, so the estimate is information, never a breach.
    if "estimatedTokens" in b:
        upper = tokens * (1 + TOKEN_ESTIMATE_ERROR_PCT / 100)
        if upper > b["estimatedTokens"]:
            breaches.append(
                f"estimated tokens ~{tokens} (+/-{TOKEN_ESTIMATE_ERROR_PCT}%) may exceed "
                f"{b['estimatedTokens']} - confirm with preview_strategy_report")

    return BudgetReport(
        sections=len(report.sections), columns=columns, headers=headers,
        distinct_timeframes=sorted(timeframes), estimated_tokens=tokens,
        budgets=b, breaches=breaches,
    )
