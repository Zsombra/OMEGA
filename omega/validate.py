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
# Transforms that take no parameters at all.
NULLARY_TRANSFORMS = {"distance", "bandTouch", "classifyZone", "crossDetect", "count"}


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
    section_timeframe: str | None = None,
    path: str = "column",
    contract: Contract | None = None,
) -> list[Finding]:
    """Validate one column. `section_timeframe` is the section's explicit override, if any."""
    c = contract or load()
    out: list[Finding] = []

    # --- metric exists ------------------------------------------------------
    if column.metric not in c.metrics:
        return [Finding("error", "UNKNOWN_METRIC", f"{path}.metric",
                        f"{column.metric!r} is not one of the 86 catalogued metrics")]
    m = c.metric(column.metric)

    # --- metric x transform composability ----------------------------------
    tid = column.transformId
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

    # --- section timeframe compatibility ------------------------------------
    if m.is_timeless and section_timeframe is not None:
        out.append(Finding(
            "error", "REPORT_COLUMN_SECTION_TIMEFRAME_UNSUPPORTED", f"{path}.metric",
            f"{m.metric} is timeframe-inert (a bundle read) and cannot sit in a section "
            f"carrying a timeframe override (section timeframe={section_timeframe!r}). "
            f"Drop the section override, or move this column to its own section."))

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
    if spec.get("operandRequired"):
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
    if spec.get("sideRequired") and column.side is None:
        out.append(Finding(
            "error", "SIDE_REQUIRED", f"{path}.side",
            f"{tid} requires side='support' or 'resistance'"))
    if column.side is not None and not spec.get("sideRequired"):
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

    # --- offset that does nothing (BG-13) -----------------------------------
    # `offset` is accepted, validates, and CONSUMES columnLookback budget - then is
    # silently ignored by every candle-backed CATEGORICAL metric. Measured 2026-08-26
    # across 78 coins at a 4h anchor: close, ADX, swingHi, swingLo, STOCH_K, MFI14 and
    # BB_PCT_B all moved between offset 0 and 8; MA_ALIGN, BB_TOUCH, EMA_CROSS and
    # PRICE_ZONE were identical on all 78. AMD is the proof - at offset 8 its close sits
    # at 35% of its own swing range and PRICE_ZONE still answers "near high", which is
    # the offset-0 answer. The inputs are right there in the same render and the
    # classifier is not using them. See data/audit/offset_ignored.json.
    if column.offset and m.timeframe_mode == "candle" and m.vocab:
        out.append(Finding(
            "warning", "OFFSET_IGNORED", f"{path}.offset",
            f"{m.metric} is a candle-backed CATEGORICAL metric: it accepts offset"
            f"={column.offset}, spends {column.offset} of the columnLookback budget, and "
            f"returns the value for NOW anyway. Read its numeric inputs at the offset and "
            f"classify them yourself, or drop the offset."))

    # --- window / offset / bars --------------------------------------------
    lookback = c.budgets["columnLookback"]
    if column.window is not None:
        if tid not in SERIES_TRANSFORMS and column.chainedTransformId not in SERIES_TRANSFORMS:
            out.append(Finding(
                "warning", "WINDOW_IGNORED", f"{path}.window",
                f"{m.metric} x {tid} does not consume `window`"))
        elif column.window > lookback:
            out.append(Finding(
                "error", "LOOKBACK_EXCEEDED", f"{path}.window",
                f"window={column.window} exceeds the columnLookback budget of {lookback}"))
    if column.offset is not None:
        if tid != "value":
            out.append(Finding(
                "warning", "OFFSET_IGNORED", f"{path}.offset",
                f"`offset` applies to the `value` transform; {tid} ignores it"))
        elif column.offset > lookback:
            out.append(Finding(
                "error", "LOOKBACK_EXCEEDED", f"{path}.offset",
                f"offset={column.offset} exceeds the columnLookback budget of {lookback}"))
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

    for i, col in enumerate(section.columns):
        out.extend(validate_column(
            col, section_timeframe=section.timeframe,
            path=f"{path}.columns[{i}]", contract=c))

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

    # A section-level diagnosis that is easy to miss column-by-column.
    if section.timeframe is not None:
        inert = [col.metric for col in section.columns
                 if col.metric in c.metrics and c.metric(col.metric).is_timeless]
        if inert:
            out.append(Finding(
                "error", "SECTION_MIXES_INERT_METRICS", f"{path}.timeframe",
                f"section sets timeframe={section.timeframe!r} but contains timeframe-inert "
                f"metrics {sorted(set(inert))}. Either drop the override or split them out."))
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

    # distinct timeframe budget
    seen: set[str] = set()
    for section in report.sections:
        if isinstance(section, CustomSection):
            for col in section.columns:
                if col.metric not in c.metrics:
                    continue
                m = c.metric(col.metric)
                if m.is_timeless:
                    continue
                tf = section.timeframe
                if tf is None:
                    rel = getattr(col.timeframe, "rel", None)
                    tf = c.resolve_timeframe(rel, report.anchor) if rel else getattr(col.timeframe, "abs", None)
                if tf:
                    seen.add(tf)
    tf_limit = c.budgets["distinctTimeframes"]
    if len(seen) > tf_limit:
        out.append(Finding("error", "DISTINCT_TIMEFRAMES_EXCEEDED", "report",
                           f"{len(seen)} distinct timeframes {sorted(seen)} exceeds "
                           f"the budget of {tf_limit}"))

    return ValidationResult(out)
