"""Local pre-flight validation of report columns and sections.

Mirrors every composition rule the BattleGrid compiler enforces, so an invalid
column is caught here instead of at submit time. Each Finding carries the
`errorCode` the connector itself would return.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, get_args

from .contract import REFERENCE_PAIRS, Contract, Metric, load, section_subject
from .fanout import KNOB_OWN_TOKEN, KNOB_SINGLE, KNOB_SPELLING, KNOB_SPELLING_RENDERED, SMOOTHERS, takes_offset
from .types import KNOBS, MARKET_SCOPE, Column, CustomSection, PlatformSection, Report, Section

# The nine market scopes the 146.0.0 stage schema enumerates (omega.types.MARKET_SCOPE), for the subject message.
MARKET_SCOPE_VALUES = get_args(MARKET_SCOPE)

# The six series statistics contract v135 added (README "Contract history - v135"), offered on every metric with a
# series home and as a chain outer over every relation.
SERIES_STATISTICS = {"zscore", "stddev", "linregSlope", "pctl", "rollingMin", "rollingMax"}

# Transforms that walk a series and therefore honour `bars` / `window`. The five smoothers (148.1.0 / 149.0.0) too.
SERIES_TRANSFORMS = {"trajectory", "efficiency", "maxShare", "aggregate"} | SERIES_STATISTICS | set(SMOOTHERS)

# The chain successors `spread` offers that BUILD A SERIES, as opposed to `rank`, which
# reduces to an ordinal. Chaining into one of these needs a per-bar series on both sides of the spread. Since v135
# the operands each outer accepts are served (chainedOuters.<outer>.operands; rankableSpreadOperands before).
SERIES_CHAINS = {"aggregate", "trajectory", "efficiency"} | SERIES_STATISTICS | set(SMOOTHERS)


def chained_operands(spec: dict, outer: str) -> list | None:
    """The spread operands a chain into `outer` accepts, or None where nothing narrows them. Since v135 the transform
    entry serves `chainedOuters` (keyed by its chainSuccessors, each {operands, windowMaximum}; operands null where the
    inner names none); a corpus extracted before v135 carries `rankableSpreadOperands`, rank's list alone."""
    outers = spec.get("chainedOuters")
    if outers is not None:
        return (outers.get(outer) or {}).get("operands")
    return spec.get("rankableSpreadOperands") if outer == "rank" else None


def chained_window_maximum(spec: dict, outer: str) -> int | None:
    """The largest `window` a chain into `outer` accepts (v135 chainedOuters.<outer>.windowMaximum), else None."""
    return ((spec.get("chainedOuters") or {}).get(outer) or {}).get("windowMaximum")

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
# v142.3: `instrument` is relativeTo's own knob; v136: `scope` is rank's. Each is refused anywhere else - measured
# 2026-10-30 at 144.0.0 ("transform 'value' does not accept params.instrument" / "params.scope",
# REPORT_COLUMN_CONSTRUCTION_FAILED; data/audit/relative_to_probe_144_2026-10-30.json).
INSTRUMENT_TRANSFORMS = {"relativeTo"}
SCOPE_TRANSFORMS = {"rank"}
# The served default (get_metric_construction_hints relativeTo.authoring.parameters.instrument.defaultValue).
RELATIVE_DEFAULT_INSTRUMENT = "BTC"
# `bars` measured 2026-10-30 at 144.0.0 (data/audit/relative_to_probe_144c_2026-10-30.json): accepted on value (RSI14_dev),
# classifyZone (RSI14_zone) and relativeTo (RSI14_ETH_rel) as on every series transform; refused on rank ("transform
# 'rank' does not accept params.bars", REPORT_COLUMN_CONSTRUCTION_FAILED). The rest is unmeasured and still warned.
BARS_ACCEPTED_TRANSFORMS = SERIES_TRANSFORMS | {"value", "classifyZone", "relativeTo"}
BARS_REFUSED_TRANSFORMS = {"rank"}
# 48.0.0 (`remove-section-anchor-override`): "a section whose anchor is the strategy timeframe, which it now always
# is"; the 108 custom-section arm has no `timeframe` and additionalProperties false.
SECTION_TIMEFRAME_RETIRED_AT = "48.0.0"


# The codes for a served key OMEGA knows by name only (data/contract/metrics/_unmeasured_108.json, or a transform the
# served enum has and the extraction never read): the column is refused before any corpus rule is applied to it.
UNMEASURED_CODES = {"METRIC_UNMEASURED", "TRANSFORM_UNMEASURED", "PARAMETER_UNMEASURED",
                    # a knob setting whose header was never rendered (omega.fanout.KNOB_SPELLING_RENDERED): the column
                    # is refused, and no header is predicted for it (knob_token raises) - review 2026-11-08
                    "KNOB_SPELLING_UNMEASURED"}


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
    if column.metric in c.retired_metrics:
        rec = c.retired_metrics[column.metric]
        return [Finding("error", "METRIC_RETIRED", f"{path}.metric",
                        f"{column.metric!r} was retired by the platform ({rec.get('readme', 'README v110')}; measured "
                        f"at {rec['retiredAt']}, {rec.get('record', '_moves_110.json')}): author {rec['author']!r} "
                        f"instead - {rec['quote']}")]
    if column.metric not in c.metrics:
        return [Finding("error", "UNKNOWN_METRIC", f"{path}.metric",
                        f"{column.metric!r} is not one of the {len(c.metrics)} catalogued "
                        f"metrics (the roster grows with the platform; re-extract before "
                        f"concluding a metric does not exist)")]
    m = c.metric(column.metric)
    if m.subject is None:
        # Served (the enum, the vocabulary, a hint) but read by NO section subject: every preview refuses it on an
        # evaluated-coin section AND on a market section (PAR_DEV, measured 2026-11-02 at 146.0.1,
        # data/contract/metrics/_subjects_146.json). No column over it can render, so omega never emits one.
        return [Finding("error", "METRIC_NO_SUBJECT", f"{path}.metric",
                        f"{column.metric!r} is served but no section subject reads it: refused on an evaluated-coin "
                        f"section (marketScope null) and on a market section alike (\"metric {column.metric!r} is not "
                        f"read on a evaluated-coin section's bars\" / \"... on a market section's bars\", "
                        f"REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED, measured 2026-11-02 at 146.0.1); no column over "
                        f"it renders")]


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
    if column.instrument is not None and tid not in INSTRUMENT_TRANSFORMS:
        out.append(Finding(
            "error", "INSTRUMENT_UNDECLARED", f"{path}.instrument",
            f"`instrument` is declared by {sorted(INSTRUMENT_TRANSFORMS)} only; on {tid!r} it is refused "
            f"(\"transform {tid!r} does not accept params.instrument\", REPORT_COLUMN_CONSTRUCTION_FAILED, "
            f"measured 2026-10-30 at 144.0.0)"))
    if column.scope is not None and tid not in SCOPE_TRANSFORMS and column.chainedTransformId not in SCOPE_TRANSFORMS:
        out.append(Finding(
            "error", "SCOPE_UNDECLARED", f"{path}.scope",
            f"`scope` is declared by a `rank` stage only (README v136); on {tid!r} it is refused "
            f"(\"transform {tid!r} does not accept params.scope\", REPORT_COLUMN_CONSTRUCTION_FAILED, "
            f"measured 2026-10-30 at 144.0.0)"))

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

    # --- an unmeasured key anywhere else in the column ------------------------------------------------------------
    # The column's own metric and transformId are checked above. A served key OMEGA knows by name only can also sit in
    # an operand, the chain outer or a transform knob; every check below that would see it compares against the older
    # corpus (spreadOperands, chainSuccessors, the 144-era offset rule) and would answer with a measured-looking
    # refusal for what the served contract offers (2026-11-05 at 148.1.0: CLOSE x spread [PIVOT_WEEK_P], HIGH x
    # distance -> ema, HIGH x rollingMax(offset 1) -> distance are all served). So these are refused as unmeasured.
    unmeasured_parts = _unmeasured_parts(column, tid, path, c)
    if unmeasured_parts:
        return out + unmeasured_parts

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
    elif column.inputs and tid in INSTRUMENT_TRANSFORMS:
        # v142.3: the other coin is named by `instrument`, never by an operand metric - measured 2026-10-30:
        # "[column-grammar] transform 'relativeTo' does not accept params.inputs" (REPORT_COLUMN_CONSTRUCTION_FAILED)
        out.append(Finding(
            "error", "OPERAND_REFUSED", f"{path}.inputs",
            f"{tid} does not accept `inputs`: it reads {m.metric} against the same metric of the coin named by "
            f"`instrument` ({RELATIVE_DEFAULT_INSTRUMENT} when omitted)"))
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
        if column.scope is not None and m.rank_scope != "exchangeWide":
            # v136: "`scope` is refused on a report-scoped rank, which ranks the report's own coins". The served
            # `rankScope` names the set; measured 2026-10-30 on CROWD_UPBIAS: "'upBias_rank_hi_crypto' ranks this
            # report's coins, so it takes no category scope - a scope narrows a rank of the tracked universe".
            out.append(Finding(
                "error", "REPORT_COLUMN_PAIR_UNSUPPORTED", f"{path}.scope",
                f"'{m.code}_rank_{ordering}_{column.scope}' ranks this report's coins (rankScope {m.rank_scope!r}), "
                f"so it takes no category scope - a scope narrows a rank of the tracked universe (exchangeWide)"))

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
            rankable = chained_operands(spec, "rank")
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
            else:
                # v135: "A series chain over a spread operand with no per-bar value is no longer offered" - the
                # operands each outer accepts are served, so the served list is the rule where it exists.
                served = chained_operands(spec, chained)
                if served is not None and operand not in served:
                    out.append(Finding(
                        "error", "REPORT_COLUMN_CHAIN_UNSUPPORTED", f"{path}.inputs[0]",
                        f"({m.metric} x spread x {chained}) is only offered over the operands "
                        f"{served}, not {operand!r} (chainedOuters.{chained}.operands)."))
        window_max = chained_window_maximum(spec, chained)
        if window_max is not None and column.window is not None and column.window > window_max:
            # v135: efficiency's largest window is one below columnLookback (it reads window + 1 bars), and pctl's
            # likewise; each outer's maximum is served (chainedOuters.<outer>.windowMaximum). A maximum above the
            # columnLookback budget is the 1,000-bar depth's (v146.4): REPORT_COLUMN_DEPTH_EXCEEDED, measured 2026-11-07
            # at 149.1.0 on HIGH x distance -> ema window 270 ("the largest window that fits is 269").
            depth = window_max > c.budgets["columnLookback"]
            out.append(Finding(
                "error", "DEPTH_EXCEEDED" if depth else "LOOKBACK_EXCEEDED", f"{path}.window",
                f"window={column.window} exceeds the maximum {window_max} the platform serves for the "
                f"{chained} chain on {m.metric} x {tid} (chainedOuters.{chained}.windowMaximum"
                + ("; at most 936 of the 1000 readable bars, leaving the lookback budget)" if depth else ")")))
        offset_min = ((spec.get("chainedOuters") or {}).get(chained) or {}).get("offsetMinimum")
        if offset_min is not None and (column.offset or 0) < offset_min:
            # 148.1.0 (v146.6): distance after a rolling extreme needs the extreme to exclude the bar it is measured on.
            # Measured 2026-11-07 at 149.1.0: "[column-grammar] transform 'rollingMax' at offset 0 cannot be chained into
            # 'distance': a rolling extreme at offset 0 includes the bar the distance is measured on, so a close can
            # never pass it; author offset 1 or more" (REPORT_COLUMN_CONSTRUCTION_FAILED; offset omitted the same).
            out.append(Finding(
                "error", "OFFSET_BELOW_MINIMUM", f"{path}.offset",
                f"transform {tid!r} at offset {column.offset or 0} cannot be chained into {chained!r}: a rolling extreme "
                f"at offset 0 includes the bar the distance is measured on, so a close can never pass it; author offset "
                f"{offset_min} or more (chainedOuters.{chained}.offsetMinimum)"))

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
            # Until 144 a warning (WINDOW_IGNORED, the platform read past it). Measured 2026-10-30 at 144.0.0: "transform
            # 'value' does not accept params.window", the same on rank (REPORT_COLUMN_CONSTRUCTION_FAILED, [column-grammar]).
            out.append(Finding(
                "error", "WINDOW_REFUSED", f"{path}.window",
                f"transform {tid!r} does not accept params.window: {m.metric} x {tid} builds no series "
                f"(REPORT_COLUMN_CONSTRUCTION_FAILED, measured 2026-10-30 at 144.0.0)"))
        elif column.chainedTransformId in SERIES_TRANSFORMS:
            # A chained window belongs to the OUTER: the chain block above judges it against the served
            # chainedOuters.<outer>.windowMaximum (269 / 118 / 936 at 149.1.0, the platform's own "the largest window
            # that fits"). The inner (distance, spread, relativeTo) serves no window maximum of its own, so reading it
            # here refused every chained window from 65 up (review 2026-11-08). The 64-bar budget stays the bound only
            # where the outer serves no maximum (a corpus older than v135).
            if chained_window_maximum(spec, column.chainedTransformId) is None and column.window > lookback:
                out.append(Finding(
                    "error", "LOOKBACK_EXCEEDED", f"{path}.window",
                    f"window={column.window} exceeds the columnLookback budget of {lookback}"))
        elif column.window > ((spec.get("maximums") or {}).get("window") or lookback):
            # Since 146.x the served `bound` says which budget the maximum is (bounds.window): `depth` is the 1,000-bar
            # history (REPORT_COLUMN_DEPTH_EXCEEDED, "at most 936 of the 1000 readable bars ... the largest window that
            # fits is 269" on RSI14 x ema, measured 2026-11-07 at 149.1.0), `lookback` the 64-bar columnLookback.
            served = (spec.get("maximums") or {}).get("window")
            if (spec.get("bounds") or {}).get("window") == "depth":
                out.append(Finding(
                    "error", "DEPTH_EXCEEDED", f"{path}.window",
                    f"window={column.window} exceeds the maximum {served} the platform serves for {m.metric} x {tid} "
                    f"(bound depth: at most 936 of the 1000 readable bars, leaving the lookback budget)"))
            else:
                out.append(Finding(
                    "error", "LOOKBACK_EXCEEDED", f"{path}.window",
                    f"window={column.window} exceeds the columnLookback budget of {lookback}"))
        owner = column.chainedTransformId if column.chainedTransformId in SERIES_TRANSFORMS else tid
        minimum = (((c.transforms.get(owner) or {}).get("parameters") or {}).get("window") or {}).get("minimum")
        if minimum is not None and column.window < minimum and "trajectory" not in (tid, column.chainedTransformId):
            # The catalogue's served minimum (authoring.parameters.window.minimum). Measured 2026-11-07 at 149.1.0:
            # "[column-grammar] transform 'cci' requires params.window >= 2 (got 1)". trajectory keeps its own v93 rule.
            out.append(Finding(
                "error", "WINDOW_BELOW_MINIMUM", f"{path}.window",
                f"transform {owner!r} requires params.window >= {minimum} (got {column.window})"))
    if column.offset is not None:
        served_max = (spec.get("maximums") or {}).get("offset")
        if not takes_offset(tid, c):
            # Until 144 a warning (OFFSET_IGNORED). Measured 2026-10-30 at 144.0.0: "transform 'trajectory' does not
            # accept params.offset", the same on relativeTo (REPORT_COLUMN_CONSTRUCTION_FAILED, [column-grammar]); on
            # each smoother 2026-11-07 ("transform 'ema' does not accept params.offset"). `value` takes it, and since
            # 148.1.0 (v146.6) rollingMin / rollingMax (the catalogue's authoring parameters say which).
            out.append(Finding(
                "error", "OFFSET_REFUSED", f"{path}.offset",
                f"transform {tid!r} does not accept params.offset: `offset` is taken by value, rollingMin and "
                f"rollingMax only (REPORT_COLUMN_CONSTRUCTION_FAILED, measured 2026-10-30 at 144.0.0 and 2026-11-07 at "
                f"149.1.0)"))
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
    if column.bars is not None and tid in BARS_REFUSED_TRANSFORMS and column.chainedTransformId is None:
        out.append(Finding(
            "error", "BARS_REFUSED", f"{path}.bars",
            f"transform {tid!r} does not accept params.bars (REPORT_COLUMN_CONSTRUCTION_FAILED, measured 2026-10-30 "
            f"at 144.0.0): a rank is read at the frame instant, closed or developing is not its choice"))
    elif column.bars is not None and tid not in BARS_ACCEPTED_TRANSFORMS \
            and column.chainedTransformId not in SERIES_TRANSFORMS:
        out.append(Finding(
            "warning", "BARS_IGNORED", f"{path}.bars",
            f"{m.metric} x {tid} does not read a bar series; `bars` is unmeasured there (accepted on value, "
            f"classifyZone, relativeTo and every series transform; refused on rank - 2026-10-30 at 144.0.0)"))

    # --- forming-bar honesty check -----------------------------------------
    if (tid in SERIES_TRANSFORMS and column.bars in (None, "all")
            and m.family == "volumeFlow" and m.unit in ("largeCount", "count")):
        out.append(Finding(
            "warning", "FORMING_BAR_RAMP", f"{path}.bars",
            f"{m.metric} is a raw per-bar quantity; the forming bar ramps from zero each "
            f"interval. Set bars='closed' for an honest read."))

    out.extend(_knob_findings(column, m, spec, path))
    return out


# Why an off-default knob is refused under a transform (or chain outer) whose served `metricParametersAccepted` is
# false - the platform's three reasons, measured 2026-11-07 at 149.1.0 (data/audit/authoring_probe_149_2026-11-07.json):
# rank reads the materialized plane, relativeTo reads the other coin's stored value, every other one reaches history the
# server never proved the settings over.
def _not_accepted_reason(under: str, code: str) -> str:
    if under == "rank":
        return f"a ranked read reads the materialized plane, which holds {code!r} at its registered defaults only"
    if under == "relativeTo":
        return (f"its instrument side is read off the other coin's stored {code!r} at its defaults, so the ratio would "
                f"mix two settings")
    return ("its window reaches slots older than the history the server proves the settings over, so it would read "
            "bars the settings were never proven on")


def _step_ok(value: float, minimum: float, step: float) -> bool:
    """On the served step grid AND exactly the number a header can print. A float carrying representation noise
    (0.1 * 3 = 0.30000000000000004) is sent to the platform as is, its tolerance for that is unmeasured, and the header
    would print the rounded 0.3 - so it is refused here rather than predicted (review 2026-11-08)."""
    ratio = (value - minimum) / step
    places = max(0, -Decimal(str(step)).as_tuple().exponent)
    return abs(ratio - round(ratio)) < 1e-9 and round(value, places) == value


def _knob_findings(column: Column, m: Metric, spec: dict, path: str) -> list[Finding]:
    """The metric knobs (148.1.0 / 149.0.0), judged against what the metric serves (Metric.parameters) and what the
    transform serves (`metricParametersAccepted`, on the entry and on each chain outer). Platform wording measured
    2026-11-07 at 149.1.0 (data/audit/authoring_probe_149_2026-11-07.json, groups C, D, E, J)."""
    out: list[Finding] = []
    set_knobs = column.knobs()
    off_default: list[str] = []
    for knob, value in set_knobs.items():
        served = m.parameters.get(knob)
        if served is None:
            out.append(Finding(
                "error", "PARAMETER_UNDECLARED", f"{path}.{knob}",
                f"[column-grammar] metric {m.metric!r} does not accept params.{knob} (it serves "
                f"{sorted(m.parameters) or 'no knob'}; REPORT_COLUMN_CONSTRUCTION_FAILED)"))
            continue
        if value != served.get("defaultValue"):
            off_default.append(knob)
        bound, lo, hi, step = served.get("bound"), served.get("minimum"), served.get("maximum"), served.get("step")
        if bound == "flag":
            continue
        if bound == "range":
            if (lo is not None and value < lo) or (hi is not None and value > hi) \
                    or (step and lo is not None and not _step_ok(value, lo, step)):
                span = f"from {lo:g} to {hi:g}" if lo is not None and hi is not None else \
                    (f">= {lo:g}" if lo is not None else f"<= {hi:g}" if hi is not None else "on its grid")
                steps = f" in steps of {step:g}" if step else ""
                out.append(Finding(
                    "error", "PARAMETER_OUT_OF_RANGE", f"{path}.{knob}",
                    f"[column-grammar] metric {m.metric!r} requires params.{knob} {span}{steps} "
                    f"(got {value!r}; REPORT_COLUMN_CONSTRUCTION_FAILED)"))
            continue
        if lo is not None and value < lo:
            out.append(Finding(
                "error", "PARAMETER_OUT_OF_RANGE", f"{path}.{knob}",
                f"[column-grammar] metric {m.metric!r} requires params.{knob} >= {lo} (got {value})"))
        elif hi is not None and value > hi:
            # bound `depth`: the largest value whose read fits 936 of the 1000 readable bars with every other knob at
            # its default ("the largest fast that fits is 260", REPORT_COLUMN_DEPTH_EXCEEDED), except swingLength,
            # whose 10 - 100 is a grammar range ("requires params.swingLength from 10 to 100 (got 101)").
            out.append(Finding(
                "error", "PARAMETER_OUT_OF_RANGE", f"{path}.{knob}",
                f"params.{knob} {value} on {m.metric} is over the served maximum {hi} (bound depth: the largest "
                f"{knob} that fits, the metric's other knobs at their defaults)"))

    # The swing pair reads left + right + 1 bars to decide one pivot (measured: 934/2 reads 937, 933/933 reads 1867),
    # so the pair is bound jointly: each side's served maximum holds only with the other at its default.
    if "leftBars" in m.parameters and "rightBars" in m.parameters and {"leftBars", "rightBars"} & set(off_default):
        left_p, right_p = m.parameters["leftBars"], m.parameters["rightBars"]
        left = column.leftBars if column.leftBars is not None else left_p["defaultValue"]
        right = column.rightBars if column.rightBars is not None else right_p["defaultValue"]
        limit = left_p["maximum"] + right_p["defaultValue"]
        if left <= left_p["maximum"] and right <= right_p["maximum"] and left + right > limit:
            out.append(Finding(
                "error", "PARAMETER_OUT_OF_RANGE", f"{path}.leftBars",
                f"swing pair {left}/{right} reads {left + right + 1} bars to decide one pivot - at most "
                f"{limit + 1} fit (REPORT_COLUMN_DEPTH_EXCEEDED)"))
    else:
        depth_off = [k for k in off_default if (m.parameters[k].get("bound") == "depth")]
        if len(depth_off) > 1:
            out.append(Finding(
                "warning", "PARAMETER_DEPTH_UNVERIFIED", f"{path}.{depth_off[0]}",
                f"{depth_off} are each within their served maximum, but those maxima hold with the other knobs at "
                f"their defaults; how many bars the combination reads is unmeasured offline - preview it"))

    if off_default:
        # The header of an off-default knob is a measured spelling (omega.fanout): a served knob none of the tables
        # spells, or a (metric, knob) never rendered off its default, is refused here as unmeasured rather than raised
        # out of the header prediction (review 2026-11-08, pass 2).
        unspelled = [k for k in m.parameters if k not in KNOB_SPELLING and k not in KNOB_OWN_TOKEN and k not in KNOB_SINGLE]
        unrendered = [k for k in off_default if k not in KNOB_SPELLING_RENDERED.get(m.metric, ())]
        if unspelled or unrendered:
            out.append(Finding(
                "error", "KNOB_SPELLING_UNMEASURED", f"{path}.{off_default[0]}",
                f"{m.metric} at {', '.join(f'{k} {set_knobs[k]}' for k in off_default)}: the header of "
                + (f"knobs {unspelled} has no measured spelling" if unspelled else
                   f"{unrendered} off its default was never rendered (omega.fanout.KNOB_SPELLING_RENDERED)")
                + " - render it once (scripts/probe_knob_spelling_149.py, KNOB_COLUMNS) before authoring it"))
        unders = [column.transformId] if spec.get("metricParametersAccepted") is False else []
        chained = column.chainedTransformId
        if chained and ((spec.get("chainedOuters") or {}).get(chained) or {}).get("metricParametersAccepted") is False:
            unders.append(chained)
        for under in unders:
            out.append(Finding(
                "error", "PARAMETER_NOT_ACCEPTED", f"{path}.{off_default[0]}",
                f"[column-grammar] {m.metric} at {', '.join(f'{k} {set_knobs[k]}' for k in off_default)} cannot be "
                f"read under {under!r}: {_not_accepted_reason(under, m.code)} (metricParametersAccepted false; "
                f"REPORT_COLUMN_CONSTRUCTION_FAILED)"))
    return out


def _unmeasured_parts(column: Column, tid: str, path: str, c: Contract) -> list[Finding]:
    """Findings for every served-but-unmeasured key a column uses outside its own metric / transformId: an operand
    metric (`_unmeasured_108.json` metrics), the chain outer (`chainOuters`, or an unmeasured transform), a transform
    knob (`transformParameters`)."""
    out: list[Finding] = []
    for i, operand in enumerate(column.inputs or []):
        rec = c.unmeasured_metrics.get(operand.metric)
        if rec is not None:
            out.append(Finding(
                "error", "METRIC_UNMEASURED", f"{path}.inputs[{i}]",
                f"operand {operand.metric!r} is served at contract {rec['servedAt']} (added {rec['addedAt']}) but its "
                f"contract is UNMEASURED offline (which metrics take it as an operand included); omega does not emit "
                f"it until `{rec['measuredBy']}` is read and the corpus re-extracted"))
    chained = column.chainedTransformId
    if chained is not None:
        rec = c.unmeasured_chain_outers.get(chained) or c.unmeasured_transforms.get(chained)
        if rec is not None:
            out.append(Finding(
                "error", "TRANSFORM_UNMEASURED", f"{path}.chainedTransformId",
                f"{chained!r} is served as a chain outer at contract {rec['servedAt']} but OMEGA never rendered it "
                f"({column.metric} x {tid} -> {chained}): which inners it follows, its window maximum and its header "
                f"are UNMEASURED offline; omega does not emit it until "
                f"`{rec.get('measuredBy', 'get_strategy_column_contract')}` is read and the corpus re-extracted"))
    for knob, rec in (c.unmeasured_parameters.get(tid) or {}).items():
        if getattr(column, knob, None) is not None:
            out.append(Finding(
                "error", "PARAMETER_UNMEASURED", f"{path}.{knob}",
                f"`{knob}` on {tid!r} is served at contract {rec['servedAt']} (README {rec['describedIn']}) but OMEGA "
                f"never rendered it: its range and its header are UNMEASURED offline; omega does not emit it until "
                f"`{rec['measuredBy']}` is read and the corpus re-extracted"))
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

    unmeasured_columns: set[int] = set()
    for i, col in enumerate(section.columns):
        found = validate_column(col, path=f"{path}.columns[{i}]", contract=c)
        if any(f.code in UNMEASURED_CODES for f in found):
            unmeasured_columns.add(i)         # no header can be predicted for it (an operand may not be in the corpus)
        out.extend(found)

    # --- the section's subject (contract 146.0.0; measured 2026-11-02 at 146.0.1) -------------------------------
    # `marketScope: null` is an evaluated-coin section; a named scope makes a MARKET section whose subject is the field
    # at that scope. Each subject reads its own metric domain, served in the refusal
    # (REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED, details.allowedDomain.candidates): the market section reads exactly
    # the thirteen MKT_* metrics (family `market`, study marketBreadth) and the coin section every other one
    # (data/audit/market_section_probe_146_2026-11-02.json). The split is the served family, not a typed list.
    # Since 148 / 149 (measured 2026-11-07 at 149.1.0, data/audit/authoring_probe_149_2026-11-07.json group G): four
    # subjects, the metric's served `subjectKinds` saying which read it. `benchmarkTicker` binds an instrument: a declared
    # reference pair (USDT_USD, USDC_USDT) is a `reference` section (OHLC and PAR_DEV), any other ticker a `benchmark`
    # section (every evaluated-coin metric but the twenty-five coin-only ones). Both keys at once is refused.
    if section.benchmarkTicker and section.marketScope is not None:
        out.append(Finding(
            "error", "SECTION_SUBJECT_CONFLICT", f"{path}",
            "A section reads one subject: bind an instrument in `benchmarkTicker` or the market in `marketScope`, not "
            "both (VALIDATION_ERROR, measured 2026-11-07 at 149.1.0)"))
    subject = section_subject(section.benchmarkTicker, section.marketScope)
    for i, col in enumerate(section.columns):
        m = c.metrics.get(col.metric)
        if m is None or m.reads_on(subject) or m.subject is None:
            continue                          # validate_column reports an unknown metric and a metric with no subject
        if subject in ("reference", "benchmark"):
            msg = (f"a {subject} section cannot carry this column - metric {col.metric!r} is not read on a {subject} "
                   f"section's bars (it reads on {list(m.subject_kinds)}; REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED, "
                   f"measured 2026-11-07 at 149.1.0)")
        elif subject == "market":
            msg = (f"a market section cannot carry this column - metric {col.metric!r} is not read on a market "
                   f"section's bars (marketScope {section.marketScope!r} reads the market subject's "
                   f"{sum(1 for mm in c.metrics.values() if mm.subject == 'market')} metrics only: "
                   f"{sorted(k for k, mm in c.metrics.items() if mm.subject == 'market')}; REPORT_COLUMN_SUBJECT_METRIC_"
                   f"UNSUPPORTED, measured 2026-11-02 at 146.0.1). Put it in a section with marketScope null.")
        else:
            msg = (f"a evaluated-coin section cannot carry this column - metric {col.metric!r} is not read on a "
                   f"evaluated-coin section's bars (a market metric renders only on a MARKET section: set marketScope "
                   f"to one of {sorted(MARKET_SCOPE_VALUES)}; REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED, measured "
                   f"2026-11-02 at 146.0.1)")
        out.append(Finding("error", "SECTION_SUBJECT_METRIC_UNSUPPORTED", f"{path}.columns[{i}].metric", msg))

    # relativeTo on a pair section reads against another declared pair, never the BTC default: "relativeTo on a section
    # bound to 'USDT_USD' requires an instrument - another declared reference pair; a reference section has no default"
    # (REPORT_COLUMN_INSTRUMENT_UNKNOWN, measured 2026-11-07 at 149.1.0).
    if subject == "reference":
        bound = section.benchmarkTicker.upper()
        for i, col in enumerate(section.columns):
            if "relativeTo" not in (col.transformId, col.chainedTransformId):
                continue
            other = (col.instrument or "").upper()
            if other not in REFERENCE_PAIRS or other == bound:
                out.append(Finding(
                    "error", "REFERENCE_INSTRUMENT_REQUIRED", f"{path}.columns[{i}].instrument",
                    f"relativeTo on a section bound to {section.benchmarkTicker!r} requires an instrument - another "
                    f"declared reference pair ({[p for p in REFERENCE_PAIRS if p != bound]}); a reference section has "
                    f"no default (got {col.instrument!r}; REPORT_COLUMN_INSTRUMENT_UNKNOWN)"))

    # THE SILENT ONE. Two columns compiling to the same header do not raise on the
    # platform - it renders both under the duplicate name and then omits the whole
    # section from conditionColumns, so the agent can read the table while no
    # condition can address any column in it. Verified live in
    # data/contract/columns/_renders_collision.json. `offset` is the easy way to
    # trip it: it changes the value and never appears in the header.
    from .fanout import outputs_for          # local import: fanout imports nothing here
    first_seen: dict[str, int] = {}
    for i, col in enumerate(section.columns):
        if col.metric not in c.metrics or i in unmeasured_columns:
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
