"""Predict strategy-report signal membership OFFLINE.

`derive_strategy_rule_view` answers "which of the 84 signals can my report feed?" but
needs a connector round-trip. This module answers the same question locally, from the
metric->module map probed in data/derived/signal_module_map.json.

The rule, established over 24 probes:

    membership is MODULE-level, not column-level.
    Any ONE satisfying metric puts the module's ENTIRE signal set in report.
    Transform, timeframe, window and every other column parameter are irrelevant.
    Rung variants (htf_*, ltf_*) come free with the base module.

Two modules (CONFLUENCE, COMPARISON - 7 signals) were unreachable in every probe and
are reported as such rather than guessed at.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

from .contract import DERIVED_DIR, load
from .types import CustomSection, PlatformSection, Report

DEFAULT_ALLOCATION = 1


@lru_cache(maxsize=1)
def _map() -> dict:
    return json.loads((DERIVED_DIR / "signal_module_map.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _metric_to_module() -> dict[str, str]:
    out: dict[str, str] = {}
    for module, metrics in _map()["moduleSatisfiedBy"].items():
        for m in metrics:
            out[m] = module
    return out


def modules_for(metrics: set[str]) -> set[str]:
    """Which signal modules this set of metrics puts in report."""
    lookup = _metric_to_module()
    return {lookup[m] for m in metrics if m in lookup}


def signals_for(metrics: set[str]) -> set[str]:
    """Which signals this set of metrics puts in report."""
    sigs = _map()["moduleSignals"]
    return {s for module in modules_for(metrics) for s in sigs[module]}


@dataclass
class MembershipReport:
    metrics: set[str]
    modules_in: set[str]
    signals_in: set[str]
    signals_out: set[str]
    dead_metrics: set[str] = field(default_factory=set)
    unreachable: dict = field(default_factory=dict)

    @property
    def coverage_percent(self) -> float:
        total = len(self.signals_in) + len(self.signals_out)
        return 100 * len(self.signals_in) / total if total else 0.0

    def can_allocate(self, signal_id: str) -> bool:
        return signal_id in self.signals_in

    def render(self) -> str:
        m = _map()
        lines = [
            f"modules in report   {len(self.modules_in):>2} / {len(m['moduleSignals'])}",
            f"signals in report   {len(self.signals_in):>2} / 84   ({self.coverage_percent:.0f}% coverage)",
            "",
        ]
        by_mod = m["moduleSignals"]
        for module in sorted(self.modules_in):
            feeders = sorted(set(m["moduleSatisfiedBy"][module]) & self.metrics)
            lines.append(f"  {module:<18} {len(by_mod[module]):>2} signals   via {', '.join(feeders)}")
        if self.dead_metrics:
            lines += ["", "  metrics feeding no signal (context only):",
                      "    " + ", ".join(sorted(self.dead_metrics))]
        return "\n".join(lines)


def analyse(report: Report) -> MembershipReport:
    """Predict membership for a report. Custom sections only - see `platform_caveat`."""
    c = load()
    metrics: set[str] = set()
    for section in report.sections:
        if isinstance(section, CustomSection):
            metrics |= {col.metric for col in section.columns if col.metric in c.metrics}

    m = _map()
    modules = modules_for(metrics)
    all_signals = {s for sigs in m["moduleSignals"].values() for s in sigs}
    signals_in = signals_for(metrics)
    lookup = _metric_to_module()

    return MembershipReport(
        metrics=metrics,
        modules_in=modules,
        signals_in=signals_in,
        signals_out=all_signals - signals_in,
        dead_metrics={x for x in metrics if x not in lookup},
        unreachable=m["unreachableModules"],
    )


@dataclass(frozen=True)
class AllocationFinding:
    severity: str
    signal_id: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.signal_id}: {self.message}"


def check_allocations(report: Report, rules: list) -> list[AllocationFinding]:
    """Flag allocations the report cannot actually feed.

    A NOT_IN_REPORT signal never fires, and the aggregate's denominator counts only
    signals that FIRED - so it costs nothing arithmetically. What it costs is
    EVIDENCE: you believed you had allocated weight to that module and you have not.
    The scorecard is narrower than it looks.

    (Before 2026-08-24 this docstring claimed such a signal was "pure denominator"
    and suppressed the aggregate. That was wrong - see omega.feasibility for the
    four measurements that settled it.)
    """
    mem = analyse(report)
    m = _map()
    unreachable = {s for k, u in m["unreachableModules"].items()
                   if not k.startswith("_") for s in u["signals"]}
    out: list[AllocationFinding] = []

    for rule in rules:
        sid, alloc = rule.signalId, rule.allocation
        if sid in mem.signals_in:
            continue
        if alloc == 0:
            out.append(AllocationFinding(
                "info", sid,
                "not fed by this report, but allocation 0 carries no weight - harmless"))
        elif sid in unreachable:
            module = next(k for k, v in m["unreachableModules"].items()
                          if not k.startswith("_") and sid in v["signals"])
            out.append(AllocationFinding(
                "error", sid,
                f"{module} was unreachable in every probe - no column set is known to feed it. "
                f"Allocation {alloc} buys nothing: the signal never fires, so it never "
                f"enters the aggregate at all."))
        else:
            module = next(k for k, v in m["moduleSignals"].items() if sid in v)
            feeders = m["moduleSatisfiedBy"][module]
            out.append(AllocationFinding(
                "error", sid,
                f"NOT_IN_REPORT - the {module} module has no feeding column, so this "
                f"signal never fires and allocation {alloc} is inert (the aggregate "
                f"denominator counts only fired signals). You have less evidence than "
                f"the scorecard suggests. Add one of: {', '.join(feeders)}"))

    for rule in rules:
        if rule.signalId in mem.signals_in and rule.allocation == 0:
            out.append(AllocationFinding(
                "info", rule.signalId,
                "fed by the report but allocation 0 - informational only, zero weight"))
    return out


def suggest_columns_for(signal_ids: list[str]) -> dict[str, list[str]]:
    """Given signals you want to weight, which metrics would feed them.

    Returns {signalId: [metrics that would put it in report]}. An empty list means
    the signal was unreachable in every probe.
    """
    m = _map()
    out: dict[str, list[str]] = {}
    for sid in signal_ids:
        module = next((k for k, v in m["moduleSignals"].items() if sid in v), None)
        out[sid] = list(m["moduleSatisfiedBy"].get(module, [])) if module else []
    return out


def platform_caveat() -> str:
    return (
        "Platform sections are NOT modelled. Probing showed they are inconsistent: "
        "includeRsi alone puts 8 signals in report, while includeMtfConfluence alone puts "
        "ZERO in report despite carrying MA_ALIGN, RSI14 and ADX columns. If your report "
        "uses platform sections, confirm membership with derive_strategy_rule_view."
    )
