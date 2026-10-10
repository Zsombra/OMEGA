"""Predict strategy-report signal membership OFFLINE.

`derive_strategy_rule_view` answers "which of the 84 signals can my report feed?" but
needs a connector round-trip. This module answers the same question locally, from two
measured maps in data/derived/.

**Custom columns** reach signals through their metrics
(`signal_module_map.json`, 24 probes):

    membership is MODULE-level, not column-level.
    Any ONE satisfying metric puts the module's ENTIRE signal set in report.
    Transform, timeframe, window and every other column parameter are irrelevant.
    Rung variants (htf_*, ltf_*) come free with the base module.

**Platform sections** reach signals directly
(`platform_section_map.json`, 22 probes, 2026-08-25):

    a platform section feeds EXACTLY ONE module, or none.
    17 of the 25 sections feed a module; the other 8 feed nothing at all.

Both routes reach the same 77 signals. CONFLUENCE and COMPARISON - 7 signals - are fed
by neither, because a synthesis module fires off other signals and the comparison module
is fed by the comparison coin set. See docs/07-signal-membership.md.

Two corrections this module carries, kept visible:

- 2026-08-24. A NOT_IN_REPORT signal does not suppress the aggregate; the denominator
  counts only signals that FIRED. What it costs is evidence, not arithmetic.
- 2026-08-25. Platform sections used to be unmodelled. `analyse` iterated sections but
  only CustomSection contributed, so a platform report measured as zero metrics and
  `check_allocations` returned a confident `error` telling you to add a column you
  already had. Every strategy on this account is built from platform sections, so the
  tool was wrong for all of them. They are now measured rather than guessed at.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

from .contract import DERIVED_DIR, load
from .types import CustomSection, PlatformSection, Report
from .validate import Finding

DEFAULT_ALLOCATION = 1

# Sections that carry an indicator at the regime rung but feed no signal themselves.
# Allocating to htf_* while enabling only these is the single most likely mistake the
# map can now catch, so the finding names it explicitly.
_HTF_DECOYS = {"includeHigherTimeframe": {"RSI", "MOVING_AVERAGES", "TREND_STRENGTH"}}


@lru_cache(maxsize=1)
def _map() -> dict:
    return json.loads((DERIVED_DIR / "signal_module_map.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _signal_data() -> dict[str, list[dict]]:
    """The (metric, rung) data each signal scores on, as BattleGrid's own draft diagnostics
    list it (the rung probe of 2026-10-06, contract 91.0.0: 83 of 84 signals). It replaces
    the 2026-08-28 partial map, data/derived/scoring_inputs_measured.json (12 of 84, kept
    as history)."""
    return json.loads(
        (DERIVED_DIR / "signal_data_rungs_91.json").read_text(encoding="utf-8"))["signals"]


# The three rungs the map names -> the three `rel` values a column's timeframe may carry
# (schema_20261005T194629Z.json, REPORT ... columns.items.properties.timeframe.anyOf[0].rel:
# enum [anchor, lower, regime]; a custom section carries no timeframe of its own). `lower` is
# the same word on both sides. `signalHigher` is the vocabulary's one rel above the anchor:
# the platform's own includeHigherTimeframe template is ADX / RSI14 / MA_ALIGN `value` at
# {rel: regime} and includeMtfConfluence holds MA_ALIGN at lower, anchor and regime
# (data/contract/templates/platform/_all.json); a regime column renders with the `_htf` infix
# (RSI14_htf, data/contract/columns/_renders_tfvariants.json), the stem of the `htf_*` ids
# whose data sits at `signalHigher`. That a rel:regime column clears an `htf_*` mismatch is
# PREDICTED from this vocabulary (2026-10-10) and owed a live stage; the 2026-08-28 compile
# proved only that a rel:anchor column clears neither rung.
RUNG_REL = {"anchor": "anchor", "lower": "lower", "signalHigher": "regime"}


@dataclass(frozen=True)
class ScoringFinding(Finding):
    """A mismatch BattleGrid's draft diagnostics would list: `missing` holds the (metric, rung)
    pairs behind it - the data a weighted signal scores on that the report lacks, or the data
    an unweighted signal scores on that the report shows."""
    signal_id: str = ""
    missing: frozenset = frozenset()
    platform_code: str = ""     # the code BattleGrid's diagnostics.mismatches carry


def shown_data(report) -> set[tuple[str, str]]:
    """Every (metric, rel) the report's custom columns show: the column's metric and each
    spread `inputs` metric, at the column's rel (M1 2026-10-06: an EMA5 spread with an EMA13
    input showed EMA13; the transform never matters). Platform sections are not expanded:
    their rendering against the rungs is unmeasured."""
    def _rel(tf):
        # Column.timeframe validates from {"rel": "anchor"} dicts; handle both the
        # dict and the pydantic-model representation without caring which it is.
        return tf.get("rel") if isinstance(tf, dict) else getattr(tf, "rel", None)

    def _metric(x):
        return x.get("metric") if isinstance(x, dict) else getattr(x, "metric", None)

    out: set[tuple[str, str]] = set()
    for s in report.sections:
        for c in getattr(s, "columns", None) or []:
            rel = _rel(c.timeframe)
            if rel is None:
                continue
            out.add((c.metric, rel))
            out.update((_metric(i), rel) for i in (getattr(c, "inputs", None) or []))
    return out


def scoring_gaps(report, rules) -> list[ScoringFinding]:
    """Warn when a weighted signal scores on data the report does not show - BattleGrid's
    `ACTIVE_SIGNAL_DATA_NOT_IN_REPORT`, predicted offline. It does not refuse a commit; it
    means the agent's model is shown none of what drives that part of the score.

    A (metric, rung) is shown by a column whose metric - or one of its spread `inputs` - is
    the metric at the rung's rel (RUNG_REL), whatever the transform. Reproduced exactly on
    the trend-continuation create of 2026-10-09 (12 mismatches, tests/test_recipes_rung_gap.py)
    and the M1 draft of 2026-10-06. A signal the map does not list
    (comparison_btc_decorrelation) is silent."""
    shown = shown_data(report)
    data = _signal_data()
    out = []
    for r in rules:
        if r.allocation <= 0 or r.signalId not in data:
            continue
        missing = frozenset((d["metric"], d["rung"]) for d in data[r.signalId]
                            if (d["metric"], RUNG_REL[d["rung"]]) not in shown)
        if not missing:
            continue
        fix = ", ".join(f"{m} at timeframe {{rel: {RUNG_REL[g]}}}" for m, g in sorted(missing))
        out.append(ScoringFinding(
            "warning", "SCORING_INPUT_NOT_RENDERED", f"rules.{r.signalId}",
            f"{r.signalId} scores on {', '.join(f'{m} @ {g}' for m, g in sorted(missing))}, "
            f"which the report does not show (BattleGrid ACTIVE_SIGNAL_DATA_NOT_IN_REPORT, "
            f"map measured 2026-10-06, list reproduced 2026-10-09/10); add a column on {fix}",
            signal_id=r.signalId, missing=missing, platform_code="ACTIVE_SIGNAL_DATA_NOT_IN_REPORT"))
    return out


def report_data_signal_off(report, rules) -> list[ScoringFinding]:
    """BattleGrid's `REPORT_DATA_SIGNAL_OFF`, predicted offline: a signal at allocation 0 - or
    absent from the rules - whose every (metric, rung) the report shows. The agent reads data
    the scorecard never scores. Measured 2026-10-09/10 on the REGIME context columns: four
    regime_* signals, data REGIME_TREND / REGIME_VOL / REGIME_MOM @ anchor."""
    shown = shown_data(report)
    alloc = {r.signalId: r.allocation for r in rules}
    out = []
    for sid, data in sorted(_signal_data().items()):
        if alloc.get(sid, 0) > 0 or not data:
            continue
        pairs = frozenset((d["metric"], d["rung"]) for d in data)
        if all((m, RUNG_REL[g]) in shown for m, g in pairs):
            out.append(ScoringFinding(
                "warning", "REPORT_DATA_SIGNAL_OFF", f"rules.{sid}",
                f"{sid} is off while the report shows the data it scores on: "
                f"{', '.join(f'{m} @ {g}' for m, g in sorted(pairs))} (BattleGrid "
                f"REPORT_DATA_SIGNAL_OFF, measured 2026-10-09/10); weight it or drop the column",
                signal_id=sid, missing=pairs, platform_code="REPORT_DATA_SIGNAL_OFF"))
    return out


def modules_scoring_nothing(report, rules) -> list[Finding]:
    """BattleGrid's `MODULE_IN_REPORT_SCORES_NOTHING` warning, predicted offline: a module the
    report puts in (analyse) none of whose signals is weighted - shown to the model, scoring
    nothing. Measured 2026-10-09/10: "The Market Regime module is in this report, but all 4
    of its signals are Off"."""
    m = _map()
    weighted = {r.signalId for r in rules if r.allocation > 0}
    out = []
    for module in sorted(analyse(report).modules_in):
        signals = m["moduleSignals"][module]
        if not weighted & set(signals):
            out.append(Finding(
                "warning", "MODULE_IN_REPORT_SCORES_NOTHING", f"report.{module}",
                f"the {module} module is in this report, but all {len(signals)} of its signals "
                f"are off - it is shown to the model and scores nothing"))
    return out


def predicted_diagnostics(report, rules) -> dict[str, list]:
    """The draft diagnostics BattleGrid would return for this report and scorecard, by the
    two keys it uses: `mismatches` (ACTIVE_SIGNAL_DATA_NOT_IN_REPORT as SCORING_INPUT_NOT_RENDERED,
    then REPORT_DATA_SIGNAL_OFF) and `warnings` (MODULE_IN_REPORT_SCORES_NOTHING). Checked
    against the measured 12 + 4 + 1 of actions 60 / 62 in tests/test_recipes_rung_gap.py."""
    return {"mismatches": scoring_gaps(report, rules) + report_data_signal_off(report, rules),
            "warnings": modules_scoring_nothing(report, rules)}


@lru_cache(maxsize=1)
def _platform_map() -> dict:
    return json.loads(
        (DERIVED_DIR / "platform_section_map.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _metric_to_module() -> dict[str, str]:
    out: dict[str, str] = {}
    for module, metrics in _map()["moduleSatisfiedBy"].items():
        for m in metrics:
            out[m] = module
    return out


@lru_cache(maxsize=1)
def _module_to_section() -> dict[str, str]:
    return {mod: key for key, mod in _platform_map()["sectionFeedsModule"].items()}


def modules_for(metrics: set[str]) -> set[str]:
    """Which signal modules this set of metrics puts in report."""
    lookup = _metric_to_module()
    return {lookup[m] for m in metrics if m in lookup}


def modules_for_sections(keys: set[str]) -> set[str]:
    """Which signal modules this set of platform sectionKeys puts in report."""
    feeds = _platform_map()["sectionFeedsModule"]
    return {feeds[k] for k in keys if k in feeds}


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
    sections: set[str] = field(default_factory=set)
    barren_sections: set[str] = field(default_factory=set)
    unknown_sections: set[str] = field(default_factory=set)

    @property
    def coverage_percent(self) -> float:
        total = len(self.signals_in) + len(self.signals_out)
        return 100 * len(self.signals_in) / total if total else 0.0

    @property
    def is_complete(self) -> bool:
        """False when the report carries a sectionKey nothing has measured, which makes
        `signals_in` a lower bound rather than the answer."""
        return not self.unknown_sections

    def can_allocate(self, signal_id: str) -> bool:
        return signal_id in self.signals_in

    def render(self) -> str:
        m = _map()
        pm = _platform_map()
        lines = [
            f"modules in report   {len(self.modules_in):>2} / {len(m['moduleSignals'])}",
            f"signals in report   {len(self.signals_in):>2} / 84   "
            f"({self.coverage_percent:.0f}% coverage)",
            "",
        ]
        by_mod = m["moduleSignals"]
        feeds = pm["sectionFeedsModule"]
        for module in sorted(self.modules_in):
            via = sorted(set(m["moduleSatisfiedBy"][module]) & self.metrics)
            via += [k for k in sorted(self.sections) if feeds.get(k) == module]
            lines.append(
                f"  {module:<18} {len(by_mod[module]):>2} signals   via {', '.join(via)}")
        if self.dead_metrics:
            lines += ["", "  metrics feeding no signal (context only):",
                      "    " + ", ".join(sorted(self.dead_metrics))]
        if self.barren_sections:
            lines += ["", "  sections feeding no signal (context only):"]
            for k in sorted(self.barren_sections):
                lines.append(f"    {k} - {pm['sectionsFeedingNothing'][k]}")
        if self.unknown_sections:
            lines += ["", "  UNMEASURED sections - membership above is a LOWER BOUND:",
                      "    " + ", ".join(sorted(self.unknown_sections))]
        return "\n".join(lines)


def analyse(report: Report) -> MembershipReport:
    """Predict membership for a report, from custom columns and platform sections alike."""
    c = load()
    pm = _platform_map()
    known = set(pm["sectionFeedsModule"]) | set(pm["sectionsFeedingNothing"])

    metrics: set[str] = set()
    keys: set[str] = set()
    for section in report.sections:
        if isinstance(section, CustomSection):
            metrics |= {col.metric for col in section.columns if col.metric in c.metrics}
        elif isinstance(section, PlatformSection):
            keys.add(section.sectionKey)

    m = _map()
    modules = modules_for(metrics) | modules_for_sections(keys)
    all_signals = {s for sigs in m["moduleSignals"].values() for s in sigs}
    signals_in = {s for module in modules for s in m["moduleSignals"][module]}
    lookup = _metric_to_module()

    return MembershipReport(
        metrics=metrics,
        modules_in=modules,
        signals_in=signals_in,
        signals_out=all_signals - signals_in,
        dead_metrics={x for x in metrics if x not in lookup},
        unreachable=m["unreachableModules"],
        sections=keys & set(pm["sectionFeedsModule"]),
        barren_sections=keys & set(pm["sectionsFeedingNothing"]),
        unknown_sections=keys - known,
    )


@dataclass(frozen=True)
class AllocationFinding:
    severity: str
    signal_id: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.signal_id}: {self.message}"


def _how_to_feed(module: str) -> str:
    """Both routes into a module, named concretely."""
    feeders = ", ".join(_map()["moduleSatisfiedBy"][module])
    section = _module_to_section().get(module)
    route = f"add a column on one of: {feeders}"
    if section:
        route += f", or enable the {section} platform section"
    return route


def check_allocations(report: Report, rules: list) -> list[AllocationFinding]:
    """Flag allocations the report cannot actually feed.

    A NOT_IN_REPORT signal never fires, and the aggregate's denominator counts only
    signals that FIRED - so it costs nothing arithmetically. What it costs is
    EVIDENCE: you believed you had allocated weight to that module and you have not.
    The scorecard is narrower than it looks.

    When the report carries a sectionKey this repo has never measured, membership is a
    lower bound, so an absent signal is reported as unknown rather than as an error.
    Refusing to answer is the only honest move there - a confident wrong remedy is worse
    than none, which is exactly the bug this function shipped until 2026-08-25.
    """
    mem = analyse(report)
    m = _map()
    pm = _platform_map()
    unreachable = {s for k, u in m["unreachableModules"].items()
                   if not k.startswith("_") for s in u["signals"]}
    out: list[AllocationFinding] = []

    for rule in rules:
        sid, alloc = rule.signalId, rule.allocation
        if sid in mem.signals_in:
            continue
        module = next(k for k, v in m["moduleSignals"].items() if sid in v)

        if alloc == 0:
            out.append(AllocationFinding(
                "info", sid,
                "not fed by this report, but allocation 0 carries no weight - harmless"))
        elif not mem.is_complete:
            out.append(AllocationFinding(
                "warn", sid,
                f"cannot determine. This report uses "
                f"{', '.join(sorted(mem.unknown_sections))}, which nothing here has "
                f"measured, so membership is a lower bound. Confirm with "
                f"derive_strategy_rule_view before trusting allocation {alloc}."))
        elif sid in unreachable:
            out.append(AllocationFinding(
                "error", sid,
                f"{module} was unreachable in every probe - no column set and no platform "
                f"section is known to feed it. Allocation {alloc} buys nothing: the signal "
                f"never fires, so it never enters the aggregate at all."))
        else:
            decoys = [k for k in sorted(mem.barren_sections)
                      if module in _HTF_DECOYS.get(k, set())]
            note = ""
            if decoys:
                note = (f" Note: this report enables {', '.join(decoys)}, which feeds no "
                        f"signal at all - {pm['sectionsFeedingNothing'][decoys[0]]}.")
            out.append(AllocationFinding(
                "error", sid,
                f"NOT_IN_REPORT - the {module} module has no feeding column or section, so "
                f"this signal never fires and allocation {alloc} is inert (the aggregate "
                f"denominator counts only fired signals). You have less evidence than the "
                f"scorecard suggests. To fix, {_how_to_feed(module)}.{note}"))

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


def suggest_sections_for(signal_ids: list[str]) -> dict[str, str | None]:
    """Given signals you want to weight, which platform section would feed each.

    Returns {signalId: sectionKey or None}. None means no section reaches it - the
    signal is in CONFLUENCE or COMPARISON, which no section feeds.
    """
    m = _map()
    rev = _module_to_section()
    out: dict[str, str | None] = {}
    for sid in signal_ids:
        module = next((k for k, v in m["moduleSignals"].items() if sid in v), None)
        out[sid] = rev.get(module) if module else None
    return out


def platform_caveat() -> str:
    pm = _platform_map()
    return (
        f"Platform sections were measured on {pm['_measured']}: "
        f"{len(pm['sectionFeedsModule'])} of 25 feed exactly one signal module each, and "
        f"{len(pm['sectionsFeedingNothing'])} feed nothing. The eight that feed nothing "
        f"are {', '.join(sorted(pm['sectionsFeedingNothing']))}. "
        "includeHigherTimeframe is the trap: it does NOT feed htf_* - those come free "
        "with RSI, MOVING_AVERAGES and TREND_STRENGTH. A sectionKey outside those 25 is "
        "reported as unmeasured rather than guessed at."
    )
