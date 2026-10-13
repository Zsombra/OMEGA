"""Local pre-flight validation of report columns and sections.

Mirrors every composition rule the BattleGrid compiler enforces, so an invalid
column is caught here instead of at submit time. Each Finding carries the
`errorCode` the connector itself would return.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .contract import Contract, load
from .types import Column, CustomSection, PlatformSection, Report, Section

# Transforms that walk a series and therefore honour `bars` / `window`.
SERIES_TRANSFORMS = {"trajectory", "efficiency", "maxShare", "aggregate"}

# The chain successors `spread` offers that BUILD A SERIES, as opposed to `rank`, which
# reduces to an ordinal and is restricted separately by rankableSpreadOperands. Chaining
# into one of these needs a per-bar series on both sides of the spread.
SERIES_CHAINS = {"aggregate", "trajectory", "efficiency"}

# A bare `CLOSE x value` column - no window, no offset - already reports
# columnLookback 24/32. The contract publishes `value` as taking ONLY `offset` and no
# window, so this floor is invisible until the platform refuses the column. Measured
# 2026-08-26 across CLOSE, PRICE_ZONE and REGIME_VOL; see data/audit/lookback_floor.json.
LOOKBACK_FLOOR = 24
# Transforms that take no parameters at all.
NULLARY_TRANSFORMS = {"distance", "bandTouch", "classifyZone", "crossDetect", "count"}

# What the changelog says replaces a retired transform (which transforms are retired is derived, contract.py).
RETIRED_TRANSFORM_REPLACEMENT = {
    "bandTouch": ('README "Contract history - v100": "Where you want \'where the close sits in the bands\', read '
                  'BB_TOUCH x value; where you want \'what the bar\'s range did at a band\', use levelInteraction"'),
}
# v100: "`buffer`, a column knob declared by `levelInteraction` only ... `buffer` on any other transform is refused
# as an undeclared parameter."
BUFFER_TRANSFORMS = {"levelInteraction"}
# 48.0.0 (`remove-section-anchor-override`): "a section whose anchor is the strategy timeframe, which it now always
# is"; the 108 custom-section arm has no `timeframe` and additionalProperties false.
SECTION_TIMEFRAME_RETIRED_AT = "48.0.0"


@dataclass(frozen=True)
class Finding:
    severity: str          # "error" | "warning"
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"[{self.severity}] {self.path}: {self.message}"


class ValidationResult:
    def __init__(self, findings: list[Finding]):
        self.findings = findings

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def __bool__(self) -> bool:
        return self.ok

    def __repr__(self) -> str:
        return f"<ValidationResult ok={self.ok} errors={len(self.errors)} warnings={len(self.warnings)}>"

    def report(self) -> str:
        if not self.findings:
            return "OK  no findings"
        return "\n".join(str(f) for f in self.findings)


def validate_column(
    column: Column,
    *,
    path: str = "column",
    contract: Contract | None = None,
) -> list[Finding]:
    """Validate one column. (A section anchor override no longer exists - contract 48.0.0 - so a column is judged
    on its own; validate_section refuses a section that still carries one.)"""
    c = contract or load()
    out: list[Finding] = []

    # --- metric exists ------------------------------------------------------
    if column.metric in c.unmeasured_metrics:
        # Served (the 108 stage schema's column metric enum, data/derived/condition_vocabulary_108.json) but never
        # extracted: which transforms it composes was measured by a live probe at 61.2.0 for the other 156 and is
        # UNMEASURED for these (data/contract/metrics/_unmeasured_108.json). omega refuses to emit what it has not
        # measured.
        rec = c.unmeasured_metrics[column.metric]
        return [Finding("error", "METRIC_UNMEASURED", f"{path}.metric",
                        f"{column.metric!r} is served at contract {rec['servedAt']} (added {rec['addedAt']}) but its "
                        f"transform admissibility is UNMEASURED offline; omega does not emit it until "
                        f"`{rec['measuredBy']}` is read and the corpus re-extracted")]
    if column.metric not in c.metrics:
        return [Finding("error", "UNKNOWN_METRIC", f"{path}.metric",
                        f"{column.metric!r} is not one of the {len(c.metrics)} catalogued "
                        f"metrics (the roster grows with the platform; re-extract before "
                        f"concluding a metric does not exist)")]
    m = c.metric(column.metric)


    # --- metric-declared absolute anchor -------------------------------------
    # PDH, PDL and the seven pivots declare anchor "1d". Measured live 2026-09-09 on
    # PIVOT_P via get_strategy_column_contract: {"rel": "anchor"|"lower"|"regime"} and
    # {"abs": "1d"} are all ACCEPTED; {"abs": "4h"} is REFUSED with "metric 'pivotP' is
    # anchored to '1d' - it accepts only that absolute timeframe reference, not '4h'".
    # So the constraint binds PINNED references only. Record:
    # data/audit/metric_anchor_rule_2026-09-09.json.
    if m.anchor and not m.is_timeless:
        got_abs = getattr(column.timeframe, "abs", None)
        if got_abs is not None and got_abs != m.anchor:
            out.append(Finding(
                "error", "METRIC_ANCHOR_MISMATCH", f"{path}.timeframe",
                f"{m.metric} is anchored to {m.anchor!r} - it accepts only that absolute "
                f"timeframe reference, not {got_abs!r}. Use "
                f'timeframe={{"abs": "{m.anchor}"}} or a relative reference.'))
        elif got_abs is None:
            # The vendor's authoring skill states the SAVE path accepts only {abs: <anchor>}
            # on these metrics. That is a stricter claim than the column contract, and the
            # save path was NOT probed here, so this is a warning rather than an error.
            out.append(Finding(
                "warning", "METRIC_ANCHOR_RELATIVE_UNVERIFIED", f"{path}.timeframe",
                f"{m.metric} declares anchor {m.anchor!r}. A relative reference is accepted "
                f"by the column contract (measured), but the vendor's authoring skill says "
                f'the save path accepts only {{"abs": "{m.anchor}"}}. That path is unmeasured; '
                f"pin it if the column must survive a save."))

    # --- transforms the served enum no longer has, or has and omega never extracted ------------
    tid = column.transformId
    if tid in c.retired_transforms:
        rec = c.retired_transforms[tid]
        return out + [Finding(
            "error", "TRANSFORM_RETIRED", f"{path}.transformId",
            f"{tid!r} is not in the transformId enum the contract {rec['servedAt']} write schema serves "
            f"({rec['schema']}); a column naming it is refused. "
            f"{RETIRED_TRANSFORM_REPLACEMENT.get(tid, 'The changelog names no replacement.')}")]
    if tid in c.unmeasured_transforms:
        rec = c.unmeasured_transforms[tid]
        return out + [Finding(
            "error", "TRANSFORM_UNMEASURED", f"{path}.transformId",
            f"{tid!r} is served at contract {rec['servedAt']} but was never extracted: which metrics it composes, "
            f"its header and its vocabulary are UNMEASURED offline; omega does not emit it until "
            f"`get_strategy_column_contract` is read over it and the corpus re-extracted")]
    if column.buffer is not None and tid not in BUFFER_TRANSFORMS:
        out.append(Finding(
            "error", "BUFFER_UNDECLARED", f"{path}.buffer",
            f"`buffer` is declared by {sorted(BUFFER_TRANSFORMS)} only; on {tid!r} it is refused as an undeclared "
            f'parameter (README "Contract history - v100")'))

    # --- metric x transform composability ----------------------------------
    if not m.offers(tid):
        candidates = sorted(m.transforms)
        if c.is_privileged(m.metric, tid):
            out.append(Finding(
                "error", "REPORT_COLUMN_PAIR_UNSUPPORTED", f"{path}.transformId",
                f"({m.metric} x {tid}) is PLATFORM-PRIVILEGED - the platform's own section "
                f"templates use it but custom columns cannot. Authorable alternatives: {candidates}"))
        else:
            out.append(Finding(
                "error", "REPORT_COLUMN_PAIR_UNSUPPORTED", f"{path}.transformId",
                f"({m.metric} x {tid}) is not a composable pair. Executable transforms "
                f"for {m.metric}: {candidates}"))
        return out  # everything downstream depends on a valid pair

    spec = m.transforms[tid]

    # --- section timeframe compatibility: retired with the override at 48.0.0 ------------------
    # "REPORT_COLUMN_SECTION_TIMEFRAME_UNSUPPORTED leaves the authoringCode vocabulary" (README 48.0.0); measured
    # 2026-08-24 while the override existed (compiler probe timeless-metric-in-overridden-section, now retired).

    # --- column timeframe compatibility -------------------------------------
    # A timeless metric's own timeframe must be LITERALLY {"rel": "anchor"}. The rule is
    # syntactic, not semantic: with anchor 1h the platform still rejects {"abs": "1h"},
    # which resolves to the very same timeframe. All four forms probed live against
    # REGIME_MOM - rel:lower, rel:regime, abs:4h and abs:1h each refused; see
    # data/audit/timeless_column_timeframe.json.
    if m.is_timeless:
        tf = column.timeframe
        rel = getattr(tf, "rel", None)
        if rel != "anchor":
            got = rel if rel is not None else getattr(tf, "abs", None)
            out.append(Finding(
                "error", "REPORT_COLUMN_CONSTRUCTION_FAILED", f"{path}.timeframe",
                f"{m.metric} is timeframe-inert (a bundle read) - it accepts only the "
                f"anchor timeframe reference, not {got!r}. Use "
                f'timeframe={{"rel": "anchor"}}. Note an absolute timeframe is refused '
                f"even when it equals the anchor; only the literal reference passes."))

    # --- spread operands ----------------------------------------------------
    # requiredness from the transform's authoring catalogue, not the per-metric flag v103 removed
    if c.requires_operand(tid):
        inputs = column.inputs or []
        if len(inputs) != 1:
            out.append(Finding(
                "error", "OPERAND_REQUIRED", f"{path}.inputs",
                f"{m.metric} x {tid} requires exactly one operand metric, got {len(inputs)}"))
        else:
            operand = inputs[0].metric
            if operand == m.metric:
                out.append(Finding(
                    "error", "OPERAND_SELF", f"{path}.inputs[0]",
                    f"a metric cannot spread against itself"))
            elif operand not in m.spread_operands:
                out.append(Finding(
                    "error", "OPERAND_NOT_ALLOWED", f"{path}.inputs[0]",
                    f"{operand} is not a valid spread operand for {m.metric} "
                    f"(unit '{m.unit}'). Allowed: {list(m.spread_operands)}"))
    elif column.inputs:
        out.append(Finding(
            "warning", "OPERAND_IGNORED", f"{path}.inputs",
            f"{m.metric} x {tid} takes no operand; `inputs` will be ignored"))

    # --- side (entitySet transforms) ---------------------------------------
    if c.requires_side(tid) and column.side is None:
        out.append(Finding(
            "error", "SIDE_REQUIRED", f"{path}.side",
            f"{tid} requires side='support' or 'resistance'"))
    if column.side is not None and not c.requires_side(tid):
        out.append(Finding(
            "warning", "SIDE_IGNORED", f"{path}.side",
            f"{m.metric} x {tid} does not use `side`"))

    # --- rank ordering ------------------------------------------------------
    if tid == "rank":
        ordering = column.ordering or "hi"
        if ordering not in m.rank_orderings:
            out.append(Finding(
                "error", "REPORT_COLUMN_PAIR_UNSUPPORTED", f"{path}.ordering",
                f"ranked column '{m.code}' does not offer the {ordering!r} ordering. "
                f"Allowed: {list(m.rank_orderings)}"))

    # --- chaining -----------------------------------------------------------
    if column.chainedTransformId:
        chained = column.chainedTransformId
        successors = spec.get("chainSuccessors", [])
        if not successors:
            out.append(Finding(
                "error", "REPORT_COLUMN_CHAIN_UNSUPPORTED", f"{path}.chainedTransformId",
                f"{m.metric} x {tid} produces no chainable output"))
        elif chained not in successors:
            out.append(Finding(
                "error", "REPORT_COLUMN_CHAIN_UNSUPPORTED", f"{path}.chainedTransformId",
                f"({m.metric} x {tid} x {chained}) is not a composable chain. "
                f"Allowed successors: {successors}"))
        elif chained == "rank":
            allowed = spec.get("chainedRankOrderings", [])
            ordering = column.ordering or "hi"
            if ordering not in allowed:
                out.append(Finding(
                    "error", "REPORT_COLUMN_CHAIN_UNSUPPORTED", f"{path}.ordering",
                    f"chained rank on {m.metric} x {tid} does not offer {ordering!r}. "
                    f"Allowed: {allowed}"))
            rankable = spec.get("rankableSpreadOperands")
            if rankable is not None:
                operand = column.inputs[0].metric if column.inputs else None
                if operand not in rankable:
                    out.append(Finding(
                        "error", "REPORT_COLUMN_CHAIN_UNSUPPORTED", f"{path}.chainedTransformId",
                        f"({m.metric} x spread x rank) is only resolvable for operands "
                        f"{rankable}, not {operand!r}. Raw price-unit metrics never rank - "
                        f"rank the composition, not the level."))
        elif tid == "spread" and chained in SERIES_CHAINS:
            # A series-building chain needs a SERIES, and a spread only has one if BOTH
            # sides do. A timeless operand is a bundle read with no per-bar value, so the
            # relation is a single scalar. The contract does not publish this - it is
            # only discoverable by rendering. Measured 2026-08-26 against SPOT_CVD, MARK
            # and CHG_24H, across all three of aggregate / trajectory / efficiency, each
            # against a candle-operand control that passed:
            #
            #   [column-grammar] transform 'spread' cannot be chained into 'aggregate':
            #   'spotCVD' resolves from the bundle and has no per-bar value, so the
            #   relation is a single scalar with no series to build
            #
            # 357 enumerated shapes. See data/audit/spread_chain_operand.json.
            operand = column.inputs[0].metric if column.inputs else None
            if operand in c.metrics and c.metric(operand).is_timeless:
                out.append(Finding(
                    "error", "REPORT_COLUMN_CHAIN_UNSUPPORTED", f"{path}.inputs[0]",
                    f"({m.metric} x spread x {chained}) needs a per-bar series on BOTH "
                    f"sides, and {operand!r} is timeframe-inert - it resolves from the "
                    f"bundle, so the relation is a single scalar with no series to "
                    f"build. Use a candle-backed operand, or drop the chain."))

    # --- offset that did nothing (BG-13), fixed at contract 94.0.0 --------------
    # Measured 2026-08-26 across 78 coins at a 4h anchor: MA_ALIGN, BB_TOUCH, EMA_CROSS
    # and PRICE_ZONE ignored `offset` and answered for NOW (data/audit/offset_ignored.json,
    # the AMD proof). v94: "A candle label column at offset N reads bar t-N's label; it
    # used to read the latest" (vendor README, Contract history - v94), so the
    # OFFSET_NOT_HONOURED warning is retired; the record and its tests stay as history.

    # --- an offset on a timeless metric (v94) ---------------------------------
    # "A value column over a timeless metric ... with offset above 0 is refused at
    # construction (VALIDATION_ERROR, authoring code REPORT_COLUMN_CONSTRUCTION_FAILED)
    # ... a timeless metric has no earlier bar." It used to be accepted and ignored.
    if column.offset and tid == "value" and m.is_timeless:
        out.append(Finding(
            "error", "TIMELESS_OFFSET_REFUSED", f"{path}.offset",
            f"{m.metric} is timeless (no earlier bar): an offset above 0 is refused at "
            f"construction since contract 94.0.0 - drop it"))

    # --- a trajectory of one observation (v93) --------------------------------
    # "A custom column { transformId: "trajectory", window: 1 }, plain or as the chained
    # outer of distance x trajectory, for any metric" is refused: it compared a reading
    # with itself and read `flat` for every coin on every bar.
    if column.window is not None and column.window < 2 and "trajectory" in (tid, column.chainedTransformId):
        out.append(Finding(
            "error", "TRAJECTORY_WINDOW_BELOW_TWO", f"{path}.window",
            f"a trajectory reads at least two observations since contract 93.0.0; window="
            f"{column.window} is refused (REPORT_COLUMN_CONSTRUCTION_FAILED)"))

    # --- window / offset / bars --------------------------------------------
    lookback = c.budgets["columnLookback"]
    if column.window is not None:
        if tid not in SERIES_TRANSFORMS and column.chainedTransformId not in SERIES_TRANSFORMS:
            out.append(Finding(
                "warning", "WINDOW_IGNORED", f"{path}.window",
                f"{m.metric} x {tid} does not consume `window`"))
        elif column.window > ((spec.get("maximums") or {}).get("window") or lookback):
            out.append(Finding(
                "error", "LOOKBACK_EXCEEDED", f"{path}.window",
                f"window={column.window} exceeds the columnLookback budget of {lookback}"))
    if column.offset is not None:
        served_max = (spec.get("maximums") or {}).get("offset")
        if tid != "value":
            out.append(Finding(
                "warning", "OFFSET_IGNORED", f"{path}.offset",
                f"`offset` applies to the `value` transform; {tid} ignores it"))
        elif served_max is not None:
            # 108.4.0 serves the maximum per metric (get_metric_construction_hints, value.parameters.offset.maximum:
            # 31 on most candle metrics, 30/21/12/11 on the bar-geometry ones, 0 on a timeless one). It supersedes
            # the 24-bar floor measured 2026-08-26 below, which made 8 the usable offset.
            if column.offset > served_max:
                out.append(Finding(
                    "error", "LOOKBACK_EXCEEDED", f"{path}.offset",
                    f"offset={column.offset} exceeds the maximum {served_max} the platform serves for "
                    f"{m.metric} x value (REPORT_COLUMN_LOOKBACK_EXCEEDED)"))
        elif column.offset + LOOKBACK_FLOOR > lookback:
            # The floor is the trap. omega compared offset against the raw 32 and so
            # accepted offset 16 and 32, both of which the platform refuses: a bare
            # CLOSE x value column with no window and no offset already reports
            # columnLookback 24/32. Measured 2026-08-26, see
            # data/audit/lookback_floor.json.
            out.append(Finding(
                "error", "LOOKBACK_EXCEEDED", f"{path}.offset",
                f"offset={column.offset} plus the {LOOKBACK_FLOOR}-bar lookback floor is "
                f"{column.offset + LOOKBACK_FLOOR}, over the columnLookback budget of "
                f"{lookback}. The contract publishes `value` as taking only `offset` and "
                f"no window, so the floor is invisible until the platform refuses the "
                f"column. Usable offset is {lookback - LOOKBACK_FLOOR}."))
    if column.bars is not None and tid not in SERIES_TRANSFORMS \
            and column.chainedTransformId not in SERIES_TRANSFORMS:
        out.append(Finding(
            "warning", "BARS_IGNORED", f"{path}.bars",
            f"{m.metric} x {tid} does not read a bar series; `bars` will be ignored"))

    # --- forming-bar honesty check -----------------------------------------
    if (tid in SERIES_TRANSFORMS and column.bars in (None, "all")
            and m.family == "volumeFlow" and m.unit in ("largeCount", "count")):
        out.append(Finding(
            "warning", "FORMING_BAR_RAMP", f"{path}.bars",
            f"{m.metric} is a raw per-bar quantity; the forming bar ramps from zero each "
            f"interval. Set bars='closed' for an honest read."))

    return out


def validate_section(
    section: Section, *, path: str = "section", contract: Contract | None = None
) -> list[Finding]:
    c = contract or load()
    out: list[Finding] = []

    if isinstance(section, PlatformSection):
        if section.sectionKey not in c.platform_templates:
            out.append(Finding("error", "UNKNOWN_SECTION_KEY", f"{path}.sectionKey",
                               f"{section.sectionKey!r} is not a platform section"))
        return out

    assert isinstance(section, CustomSection)
    limit = c.budgets["sectionColumns"]
    if len(section.columns) > limit:
        out.append(Finding("error", "SECTION_COLUMNS_EXCEEDED", f"{path}.columns",
                           f"{len(section.columns)} columns exceeds the budget of {limit}"))

    if section.timeframe is not None:
        out.append(Finding(
            "error", "SECTION_TIMEFRAME_RETIRED", f"{path}.timeframe",
            f"a section anchor override (timeframe={section.timeframe!r}) was removed at contract "
            f"{SECTION_TIMEFRAME_RETIRED_AT} - \"no section can be overridden\" - and the 108 custom-section schema "
            f"refuses the key. Drop it; to read another timeframe, give each column its own `timeframe` "
            f"(rel lower/regime, or abs)."))

    for i, col in enumerate(section.columns):
        out.extend(validate_column(col, path=f"{path}.columns[{i}]", contract=c))

    # THE SILENT ONE. Two columns compiling to the same header do not raise on the
    # platform - it renders both under the duplicate name and then omits the whole
    # section from conditionColumns, so the agent can read the table while no
    # condition can address any column in it. Verified live in
    # data/contract/columns/_renders_collision.json. `offset` is the easy way to
    # trip it: it changes the value and never appears in the header.
    from .fanout import outputs_for          # local import: fanout imports nothing here
    first_seen: dict[str, int] = {}
    for i, col in enumerate(section.columns):
        if col.metric not in c.metrics:
            continue                          # validate_column already reported it
        for out_ in outputs_for(col, c):
            if out_.header in first_seen:
                out.append(Finding(
                    "error", "DUPLICATE_HEADER", f"{path}.columns[{i}]",
                    f"header {out_.header!r} is already produced by "
                    f"columns[{first_seen[out_.header]}]. The platform accepts this "
                    f"silently and then drops the whole section from "
                    f"conditionColumns, leaving every column in it unreferenceable."))
            else:
                first_seen[out_.header] = i
    return out


def validate_report(report: Report, *, contract: Contract | None = None) -> ValidationResult:
    c = contract or load()
    out: list[Finding] = []

    limit = c.budgets["sections"]
    if len(report.sections) > limit:
        out.append(Finding("error", "SECTIONS_EXCEEDED", "report.sections",
                           f"{len(report.sections)} sections exceeds the budget of {limit}"))

    for i, section in enumerate(report.sections):
        out.extend(validate_section(section, path=f"report.sections[{i}]", contract=c))

    # distinct timeframe budget (the regime rung counts, fanout.column_timeframe)
    from .fanout import column_timeframe
    seen: set[str] = set()
    for section in report.sections:
        if isinstance(section, CustomSection):
            for col in section.columns:
                if col.metric not in c.metrics:
                    continue
                tf = column_timeframe(col, section, report.anchor, c)
                if tf:
                    seen.add(tf)
    tf_limit = c.budgets["distinctTimeframes"]
    if len(seen) > tf_limit:
        out.append(Finding("error", "DISTINCT_TIMEFRAMES_EXCEEDED", "report",
                           f"{len(seen)} distinct timeframes {sorted(seen)} exceeds "
                           f"the budget of {tf_limit}"))

    return ValidationResult(out)
