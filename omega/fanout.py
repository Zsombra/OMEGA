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

# Rough per-header token cost: header name + value + glossary share, measured
# against observed get_strategy_column_contract payloads.
TOKENS_PER_HEADER = 18
TOKENS_PER_SECTION = 25


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
            "date": ["lt", "lte", "gte", "gt", "between"],
            "classification": ["is", "in"],
            "direction": ["is", "in"],
            "event": ["is", "in"],
            "boolean": ["is"],
        }
        return ops.get(self.kind, [])


def _infix(column: Column) -> str:
    rel = getattr(column.timeframe, "rel", None)
    return REL_INFIX.get(rel, "") if rel else ""


def _stage1_header(column: Column, contract: Contract) -> str:
    """Header produced by the first transform stage (before any chaining)."""
    m = contract.metric(column.metric)
    code, infix, tid = m.code, _infix(column), column.transformId

    if tid == "distance":
        return f"dist{infix or '_'}{code}" if infix else f"dist_{code}"
    if tid == "spread":
        operand = contract.metric(column.inputs[0].metric).code if column.inputs else "?"
        return f"{code}{infix or '_'}{operand}_spread" if infix else f"{code}_{operand}_spread"
    if tid == "efficiency":
        return f"{code}{infix or '_'}er" if infix else f"{code}_er"
    if tid == "maxShare":
        return f"{code}{infix or '_'}maxShare" if infix else f"{code}_maxShare"
    if tid == "aggregate":
        return f"{code}_mean{column.window or 24}"
    if tid == "bandTouch":
        return f"{code}_touch"
    if tid == "rank":
        return f"{code}_rank_{column.ordering or 'hi'}"
    if tid.startswith("nearestZone"):
        suffix = {"nearestZoneType": "type", "nearestZoneRange": "range",
                  "nearestZoneDist": "dist", "nearestZoneAge": "age"}[tid]
        return f"{code}{infix or '_'}{column.side}_{suffix}" if infix else f"{code}_{column.side}_{suffix}"
    if tid == "count":
        return f"{code}{infix or '_'}count" if infix else f"{code}_count"
    # value, classifyZone, crossDetect, trajectory all key off the bare code
    return f"{code}{infix.rstrip('_')}" if infix else code


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
    if tid in ("classifyZone", "bandTouch", "crossDetect", "nearestZoneType"):
        kind = "classification"
    elif tid == "rank":
        kind = "rank"
    elif tid in ("value",):
        kind = m.native_output["kind"]
    else:
        kind = "numeric"
    vocab = tuple(m.vocab or ()) if tid == "value" else ()
    if tid == "bandTouch":
        vocab = ("upper", "lower", "none")
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
            f"estimated tokens    {self.estimated_tokens:>5} / {b['estimatedTokens']}",
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
            m = c.metric(col.metric)
            if not m.is_timeless:
                tf = section.timeframe
                if tf is None:
                    rel = getattr(col.timeframe, "rel", None)
                    tf = c.resolve_timeframe(rel, report.anchor) if rel else getattr(col.timeframe, "abs", None)
                if tf:
                    timeframes.add(tf)

    tokens = headers * TOKENS_PER_HEADER + len(report.sections) * TOKENS_PER_SECTION
    b = c.budgets
    breaches = []
    if len(report.sections) > b["sections"]:
        breaches.append(f"sections {len(report.sections)} > {b['sections']}")
    if len(timeframes) > b["distinctTimeframes"]:
        breaches.append(f"distinct timeframes {len(timeframes)} > {b['distinctTimeframes']}")
    if tokens > b["estimatedTokens"]:
        breaches.append(f"estimated tokens {tokens} > {b['estimatedTokens']}")

    return BudgetReport(
        sections=len(report.sections), columns=columns, headers=headers,
        distinct_timeframes=sorted(timeframes), estimated_tokens=tokens,
        budgets=b, breaches=breaches,
    )
