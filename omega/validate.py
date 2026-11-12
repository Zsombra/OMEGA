"""Local pre-flight validation of report columns and sections.

Mirrors every composition rule the BattleGrid compiler enforces, so an invalid
column is caught here instead of at submit time. Each Finding carries the
`errorCode` the connector itself would return.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, get_args

from .contract import REFERENCE_PAIRS, Contract, Metric, load, section_subject
from .fanout import (KNOB_SPELLED, KNOB_SPELLING_RENDERED, ROLLING_INNERS, SMOOTHERS,
                     takes_offset)
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


# --- the bars one value reads (contract 161.0.0; measured 2026-11-11) -------------------------------------------------
# ln(1000): a smoother is read once its seed "weighs at most 0.1 %" (the catalogue's words on ema / rma / rsi).
_LN_1000 = math.log(1000)
_READS_WINDOW = frozenset({"aggregate", "wma", "cci", "zscore", "stddev", "linregSlope", "rollingMin", "rollingMax"})
_READS_WINDOW_PLUS_ONE = frozenset({"roc", "pctl"})


def bars_needed(transform_id: str, window: int) -> int | None:
    """How many bars ONE value of a rolling transform reads at `window`: the platform's own count, the N of "reads N
    bars for one value" (REPORT_COLUMN_DEPTH_EXCEEDED, details.receivedValue.need). None for a transform outside the
    table: its depth is unmeasured, and the caller refuses the column rather than guess.

    SERVED-EXACT - the catalogue's own sentence (data/contract/transforms/_authoring.json, the `window` description):
    - aggregate, wma, cci, zscore, stddev, linregSlope, rollingMin, rollingMax read `window` bars ("One value reads
      exactly the length in bars", "How many of this column's newest bars ...");
    - roc and pctl read `window` + 1 ("the newest bar and the one length bars before it"; "bars before the newest ...
      it reads the newest bar too").

    FITTED, not served. The catalogue gives the rule in words ("the bars after which the average's seed weighs at most
    0.1 %") and at one length each (73 bars at ema 20, 108 at rma 14, 109 at rsi 14); the closed forms were fitted to
    the refusals' own figures on 2026-11-11 at 161.0.0:
    - ema: ceil((window + 1) * ln(1000) / 2);
    - rma: 1 at window 1, else window + ceil(ln(1000) / -ln(1 - 1 / window)) - the seed bars, then the settling bars;
    - rsi: rma + 1 - the bar the oldest change starts from.

    What pins the fitted forms (tests/test_v0_12_2.py): the replay of data/audit/authoring_limits_161_2026-11-11.json -
    the count equals the platform's on all 19 depth refusals (two of them predicted on disk before they were sent) and
    gives the hold room the platform serves on 73 rendered columns - and the corpus test, which reproduces every served
    rolling-chain cell (15,106) and standalone depth maximum (2,184) of the 161.0.0 metric files. Two near forms fail
    that corpus test (checked 2026-11-11): the exact 0.1 % decay count for ema, ceil(ln(1000) / -ln(1 - 2 / (window +
    1))), reproduces 11,952 of the cells; a linear rma, window + ceil(window * ln(1000)), 9,628. If a re-extraction
    breaks either test the platform's arithmetic moved: re-measure, never adjust a constant by hand.

    Every form reads at least `window` bars and never fewer for a longer window (largest_window and the chain check's
    clamp rest on both)."""
    if transform_id in _READS_WINDOW:
        return window
    if transform_id in _READS_WINDOW_PLUS_ONE:
        return window + 1
    if transform_id == "ema":
        return math.ceil((window + 1) * _LN_1000 / 2)
    if transform_id in ("rma", "rsi"):
        wilder = 1 if window == 1 else window + math.ceil(_LN_1000 / -math.log(1 - 1 / window))
        return wilder + (1 if transform_id == "rsi" else 0)
    return None


def largest_window(transform_id: str, bars: int) -> int | None:
    """The largest window at which one value of `transform_id` reads at most `bars` bars - the platform's "the largest
    window that fits". None when not even a window of 1 does, or the transform is outside the need table. bars_needed
    never falls as the window grows and is never below it, so the answer lies in 1 .. bars: a bisection."""
    least = bars_needed(transform_id, 1)
    if least is None or least > bars:
        return None
    lo, hi = 1, bars
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if bars_needed(transform_id, mid) <= bars:
            lo = mid
        else:
            hi = mid - 1
    return lo


def depth_budget(m: Metric) -> int | None:
    """The bars one value of a column over `m` may read, from served data: the metric's standalone `aggregate` window
    maximum (data/contract/metrics/<METRIC>.json, transforms.aggregate.maximums.window with bounds.window `depth`).
    aggregate reads exactly its window in bars (bars_needed), so its largest window IS the budget - 2436 on all 168
    metrics that serve it at 161.0.0. It is the 2500 readable bars less the 64-bar columnLookback, as every depth
    refusal says ("at most 2436 of the 2500 readable bars, leaving the lookback budget 64"; details.context depth 2500,
    cap 64), but the corpus carries the maximum and not the 2500, so the maximum is the source. None where the metric
    serves no depth-bound aggregate: the chain check then refuses the chain as unmeasured. tests/test_v0_12_2.py fails
    if the served number moves."""
    served = m.transforms.get("aggregate") or {}
    if (served.get("bounds") or {}).get("window") != "depth":
        return None
    return (served.get("maximums") or {}).get("window")


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
                  'BB_TOUCH x value; where you want \'what the bar\'s range did at a band\', use levelInteraction" - '
                  'and BB_TOUCH itself was removed at contract 161.0.0: read BB_PCT_B for where the close sits, '
                  'BB_UPPER / BB_LOWER x levelInteraction for a touch'),
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
    level = tid in BUFFER_TRANSFORMS or column.chainedTransformId in BUFFER_TRANSFORMS
    if column.touchAtr is not None:
        # 161.0.0 (measured 2026-11-09, authoring_probe_161 groups M / T): levelInteraction's touch distance in ATR,
        # on the transform or a chained levelInteraction outer; "accepts params.buffer or params.touchAtr, never both";
        # "transform 'value' does not accept params.touchAtr"
        spec_atr = (((c.transforms.get("levelInteraction") or {}).get("parameters") or {}).get("touchAtr") or {})
        lo, step = spec_atr.get("minimum"), spec_atr.get("step")
        if not level:
            out.append(Finding(
                "error", "TOUCH_ATR_UNDECLARED", f"{path}.touchAtr",
                f"transform {tid!r} does not accept params.touchAtr: it is levelInteraction's (the transform or a "
                f"chained outer) - REPORT_COLUMN_CONSTRUCTION_FAILED, measured 2026-11-09 at 161.0.0"))
        elif column.buffer is not None:
            out.append(Finding(
                "error", "TOUCH_ATR_AND_BUFFER", f"{path}.touchAtr",
                "levelInteraction accepts params.buffer or params.touchAtr, never both (REPORT_COLUMN_CONSTRUCTION_FAILED,"
                " measured 2026-11-09 at 161.0.0)"))
        elif (lo is not None and column.touchAtr < lo) or (step and lo is not None
                                                             and not _step_ok(column.touchAtr, lo, step)):
            out.append(Finding(
                "error", "PARAMETER_OUT_OF_RANGE", f"{path}.touchAtr",
                f"levelInteraction requires params.touchAtr >= {lo:g} in steps of {step:g} (got {column.touchAtr!r})"))
        elif tid == "levelInteraction":
            hi = ((m.transforms.get("levelInteraction") or {}).get("maximums") or {}).get("touchAtr")
            if hi is not None and column.touchAtr > hi:
                out.append(Finding(
                    "error", "PARAMETER_OUT_OF_RANGE", f"{path}.touchAtr",
                    f"params.touchAtr {column.touchAtr} on {m.metric} is over the served maximum {hi}"))
        else:
            # A CHAINED levelInteraction (rollingMax / rollingMin -> levelInteraction) is bounded as the transform is:
            # measured 2026-11-11 at 161.0.0 on HIGH x rollingMax (20, offset 1) and LOW x rollingMin, touchAtr 2
            # rendered (high_o1_max20_lvl_a2) and 2.1 / 100 were refused "[column-grammar] transform 'levelInteraction'
            # requires params.touchAtr from 0.1 to 2 in steps of 0.1 (got 2.1)", REPORT_COLUMN_CONSTRUCTION_FAILED
            # (data/audit/authoring_limits_161_2026-11-11.json, group B). HIGH and LOW serve no levelInteraction entry
            # of their own, so the maximum is the served chain-outer one (Contract.chain_outer_parameters).
            hi = ((c.chain_outer_parameters.get("levelInteraction") or {}).get("touchAtr") or {}).get("maximum")
            if hi is not None and column.touchAtr > hi:
                out.append(Finding(
                    "error", "PARAMETER_OUT_OF_RANGE", f"{path}.touchAtr",
                    f"params.touchAtr {column.touchAtr} on {m.metric} x {tid} -> levelInteraction is over the served "
                    f"maximum {hi} (chainOuterParameters.levelInteraction.touchAtr.maximum)"))
    if column.chainedWindow is not None:
        outer_spec = (((m.transforms.get(tid) or {}).get("chainedOuters") or {}).get(column.chainedTransformId or "")
                      or {})
        if outer_spec.get("windowParameter") != "chainedWindow":
            # measured 2026-11-09: "transform 'spread' -> 'ema' does not accept params.chainedWindow"
            out.append(Finding(
                "error", "CHAINED_WINDOW_REFUSED", f"{path}.chainedWindow",
                f"transform {tid!r} -> {column.chainedTransformId!r} does not accept params.chainedWindow: only a chain "
                f"whose inner is a rolling transform ({', '.join(ROLLING_INNERS)}) reads its outer window from it "
                f"(served chainedOuters.<outer>.windowParameter; REPORT_COLUMN_CONSTRUCTION_FAILED, 161.0.0)"))
        else:
            outer_min = _window_parameter(column.chainedTransformId or "", c).get("minimum")
            if outer_min is not None and column.chainedWindow < outer_min:
                # The low end of the chain window. Measured 2026-11-12 at 171.0.0 (data/audit/
                # authoring_limits_171_2026-11-12.json, M.* and S3): RSI14 x ema 14 -> zscore / stddev / linregSlope / cci /
                # rollingMin / rollingMax at chainedWindow 1 is refused "[column-grammar] transform 'zscore' requires
                # params.chainedWindow >= 2 (got 1)" (REPORT_COLUMN_CONSTRUCTION_FAILED; a stage carries it as a draft
                # error), 2 renders. The minimum is the outer's catalogued window minimum (authoring.parameters.window
                # .minimum: 2 on those six, 1 elsewhere - the schema's own floor); the depth refusal's allowedDomain
                # .minimum states the same 2 (CLOSE x aggregate -> zscore). The joint depth bound judges the top.
                out.append(Finding(
                    "error", "CHAINED_WINDOW_BELOW_MINIMUM", f"{path}.chainedWindow",
                    f"transform {column.chainedTransformId!r} requires params.chainedWindow >= {outer_min} (got "
                    f"{column.chainedWindow}) (REPORT_COLUMN_CONSTRUCTION_FAILED, measured 2026-11-12 at 171.0.0)"))
    if column.buffer is not None and not level:
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
    if column.chainedTransformId == "spread":
        out.extend(_chained_spread_operand(column, m, spec, c, path))
    elif c.requires_operand(tid):
        inputs = column.inputs or []
        if len(inputs) != 1:
            out.append(Finding(
                "error", "OPERAND_REQUIRED", f"{path}.inputs",
                f"{m.metric} x {tid} requires exactly one operand metric, got {len(inputs)}"))
        elif inputs[0].averaged:
            out.extend(_averaged_operand(inputs[0], m, column, c, f"{path}.inputs[0]"))
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
            elif (m.spread_operands_off_anchor and getattr(column.timeframe, "rel", None) != "anchor"
                  and operand not in m.spread_operands_off_anchor):
                # 161.0.0 (measured 2026-11-09 at {abs: 4h} and {rel: lower}, authoring_probe_161 group P)
                out.append(Finding(
                    "error", "REPORT_COLUMN_OPERAND_UNSUPPORTED", f"{path}.inputs[0]",
                    f"spread operand {operand!r} is a per-bar session-profile level: a relation meets it only at the "
                    f"strategy's anchor rung ({{rel: 'anchor'}}), and this column reads off it (served "
                    f"spreadOperandsOffAnchor)"))
    elif column.inputs and tid in INSTRUMENT_TRANSFORMS:
        # v142.3: the other coin is named by `instrument`, never by an operand metric - measured 2026-10-30:
        # "[column-grammar] transform 'relativeTo' does not accept params.inputs" (REPORT_COLUMN_CONSTRUCTION_FAILED)
        out.append(Finding(
            "error", "OPERAND_REFUSED", f"{path}.inputs",
            f"{tid} does not accept `inputs`: it reads {m.metric} against the same metric of the coin named by "
            f"`instrument` ({RELATIVE_DEFAULT_INSTRUMENT} when omitted)"))
    elif column.inputs and any(o.averaged for o in column.inputs):
        # 168: an operand under an average was measured on spread only (as a plain spread's or a chained spread's
        # operand); anywhere else it is unmeasured, so refused rather than sent
        out.append(Finding(
            "error", "OPERAND_REFUSED", f"{path}.inputs",
            f"an averaged operand ({{metric, transformId, window}}) was measured on `spread` only; {m.metric} x {tid} "
            f"takes no operand"))
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
        if tid == "spread" and any(o.averaged for o in column.inputs or []):
            # 168, measured 2026-11-12 at 169.4.0 (authoring_probe_169 W.chain.*: trajectory, aggregate and rank alike):
            # "operand 'close_ema20' is an averaged spread operand: the comparison is read frame by frame, and no rank
            # or series outer chains over it" - the served chainSuccessors of spread do not say so.
            out.append(Finding(
                "error", "REPORT_COLUMN_CHAIN_UNSUPPORTED", f"{path}.chainedTransformId",
                f"({m.metric} x spread x {chained}) is not a composable chain: an averaged spread operand is read frame "
                f"by frame, and no rank or series outer chains over it"))
        elif not successors:
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
        outer_spec = (spec.get("chainedOuters") or {}).get(chained) or {}
        window_max = chained_window_maximum(spec, chained)
        if outer_spec.get("windowParameter") == "chainedWindow":
            # 161.0.0: a rolling inner keeps `window` and the outer reads `chainedWindow`. The two are bound JOINTLY, by
            # the bars one value reads; the served windowMaximum / innerWindowMaximum are that bound with the other
            # window at its default, so neither is compared here (measured 2026-11-11).
            out.extend(_rolling_chain_depth(column, m, c, path))
        elif window_max is not None and column.window is not None and column.window > window_max:
            # v135: efficiency's largest window is one below columnLookback (it reads window + 1 bars), and pctl's
            # likewise; each outer's maximum is served (chainedOuters.<outer>.windowMaximum). A maximum above the
            # columnLookback budget is the 1,000-bar depth's (v146.4): REPORT_COLUMN_DEPTH_EXCEEDED, measured 2026-11-07
            # at 149.1.0 on HIGH x distance -> ema window 270 ("the largest window that fits is 269").
            depth = window_max > c.budgets["columnLookback"]
            out.append(Finding(
                "error", "DEPTH_EXCEEDED" if depth else "LOOKBACK_EXCEEDED", f"{path}.window",
                f"window={column.window} exceeds the maximum {window_max} the platform serves for the "
                f"{chained} chain on {m.metric} x {tid} (chainedOuters.{chained}.windowMaximum"
                + ("; the readable depth less the lookback budget: 2436 of 2500 bars since 161.0.0)" if depth else ")")))
        offset_min = ((spec.get("chainedOuters") or {}).get(chained) or {}).get("offsetMinimum")
        if offset_min is not None and (column.offset or 0) < offset_min:
            # 148.1.0 (v146.6): distance after a rolling extreme needs the extreme to exclude the bar it is measured on.
            # Measured 2026-11-07 at 149.1.0: "[column-grammar] transform 'rollingMax' at offset 0 cannot be chained into
            # 'distance': a rolling extreme at offset 0 includes the bar the distance is measured on, so a close can
            # never pass it; author offset 1 or more" (REPORT_COLUMN_CONSTRUCTION_FAILED; offset omitted the same).
            out.append(Finding(
                "error", "OFFSET_BELOW_MINIMUM", f"{path}.offset",
                f"transform {tid!r} at offset {column.offset or 0} cannot be chained into {chained!r}: a rolling extreme "
                f"at offset 0 includes the bar the {'interaction is classified' if chained == 'levelInteraction' else 'distance is measured'} "
                f"on, so a close can never pass it; author offset {offset_min} or more "
                f"(chainedOuters.{chained}.offsetMinimum)"))

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
        elif (column.chainedTransformId and tid in ROLLING_INNERS
              and ((spec.get("chainedOuters") or {}).get(column.chainedTransformId) or {}).get("windowParameter")
              == "chainedWindow"):
            pass   # 161.0.0: the inner's window under a rolling-inner chain, judged by the chain block above
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
                    f"(bound depth: the readable depth less the lookback budget, 2436 of 2500 bars since 161.0.0)"))
            else:
                out.append(Finding(
                    "error", "LOOKBACK_EXCEEDED", f"{path}.window",
                    f"window={column.window} exceeds the columnLookback budget of {lookback}"))
        rolling_chain = (((spec.get("chainedOuters") or {}).get(column.chainedTransformId or "") or {})
                         .get("windowParameter") == "chainedWindow")
        owner = column.chainedTransformId if column.chainedTransformId in SERIES_TRANSFORMS and not rolling_chain \
            else tid
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


def _window_parameter(transform_id: str, c: Contract) -> dict:
    """The catalogue's `window` parameter of a transform (authoring.parameters.window: defaultValue, minimum, ...)."""
    return ((c.transforms.get(transform_id) or {}).get("parameters") or {}).get("window") or {}


def _rolling_chain_depth(column: Column, m: Metric, c: Contract, path: str) -> list[Finding]:
    """The ONE depth bound of a chain whose inner is a rolling transform (served windowParameter `chainedWindow`):

        bars_needed(inner, window) + bars_needed(outer, chainedWindow) - 1  <=  depth_budget(metric)

    Measured 2026-11-11 at 161.0.0 (data/audit/authoring_limits_161_2026-11-11.json): RSI14 x ema window 697 ->
    aggregate chainedWindow 2364, each AT its served maximum, is refused - "Column 'RSI14 x ema' chainedWindow 2364
    reads 4774 bars for one value - at most 2436 of the 2500 readable bars, leaving the lookback budget 64; the largest
    chainedWindow that fits is 26" (REPORT_COLUMN_DEPTH_EXCEEDED) - while 14 + 2385, 703 + 5, 704 + 2 and 1 + 2430,
    each PAST a served maximum, render. The served chainedOuters.<outer>.windowMaximum / innerWindowMaximum are this
    rule with the other window at its default (ema 20: 2364; aggregate 24: 697), so they are no threshold of their own:
    inside the bound there is NO finding, past it an error. The same bound holds on a pinned and on a lower column
    timeframe ({abs 4h}, {abs 1d}, {rel lower}). No rolling inner takes an offset, so the rule has no offset term.
    Re-measured 2026-11-12 at 171.0.0 (data/audit/authoring_limits_171_2026-11-12.json): every 161 boundary answered
    the same bar count and the same largest fit, on BTC and ETH and at every authorable main candle (5m, 15m, 1h, 4h -
    the budget is bars, not time), and a stage carries the same refusal as a draft error. The bound is the top of the
    chain window; its bottom is the outer's catalogued minimum (CHAINED_WINDOW_BELOW_MINIMUM, validate_column).

    An omitted window is the catalogue's default, as the platform fills it (N.no.window / N.no.chainedWindow rendered
    close_ema20_mean5 / close_ema20_mean24 on 2026-11-09).

    The finding names `chainedWindow` while some chainedWindow at or above the outer's minimum still fits beside the
    sent window, else `window` - the field the platform names (704 + 5 -> chainedWindow, "the largest chainedWindow
    that fits is 2"; 1394 + 5 and 705 + 1 -> window) - with the largest value that fits, the other window held as sent.

    Fails closed: a transform outside the need table, a metric that serves no budget, or an omitted window with no
    catalogued default is CHAIN_DEPTH_UNMEASURED - never a silent pass."""
    tid, chained = column.transformId, column.chainedTransformId
    budget = depth_budget(m)
    window = column.window if column.window is not None else _window_parameter(tid, c).get("defaultValue")
    chained_window = (column.chainedWindow if column.chainedWindow is not None
                      else _window_parameter(chained, c).get("defaultValue"))
    unknown = [t for t in (tid, chained) if bars_needed(t, 1) is None]
    if unknown or budget is None or window is None or chained_window is None:
        if unknown:
            why = (f"{' and '.join(repr(t) for t in unknown)} {'is' if len(unknown) == 1 else 'are'} outside the need "
                   f"table (omega.validate.bars_needed)")
        elif budget is None:
            why = f"{m.metric} serves no depth-bound aggregate maximum to read the bar budget from"
        else:
            why = f"the catalogue serves no default for the omitted {'window' if window is None else 'chainedWindow'}"
        return [Finding(
            "error", "CHAIN_DEPTH_UNMEASURED", f"{path}.chainedTransformId",
            f"({m.metric} x {tid} -> {chained}) reads its outer window from chainedWindow, and how many bars one value "
            f"of that chain reads is UNMEASURED: {why}. omega does not emit it until a preview past the bound is read "
            f"(REPORT_COLUMN_DEPTH_EXCEEDED states the count) and the table extended")]
    # Every form reads at least its window and never fewer for a longer one, so a window past the budget is judged at
    # budget + 1: the same verdict, and the fitted forms are never evaluated outside 1 .. budget + 1 (omega's type sets
    # no ceiling on a window, and Wilder's form divides by zero at a length past 2^53).
    need_in = bars_needed(tid, min(window, budget + 1))
    need_out = bars_needed(chained, min(chained_window, budget + 1))
    if need_in + need_out - 1 <= budget:
        return []
    reads = need_in + need_out - 1 if max(window, chained_window) <= budget + 1 else f"more than {budget}"
    fits = largest_window(chained, budget + 1 - need_in)
    if fits is not None and fits >= (_window_parameter(chained, c).get("minimum") or 1):
        field, beside = "chainedWindow", f"window {window}"
    else:
        field, beside, fits = "window", f"chainedWindow {chained_window}", largest_window(tid, budget + 1 - need_out)
    return [Finding(
        "error", "DEPTH_EXCEEDED", f"{path}.{field}",
        f"{m.metric} x {tid} window {window} -> {chained} chainedWindow {chained_window} reads {reads} bars for one "
        f"value - at most {budget} fit (the readable depth less the lookback budget); "
        + (f"the largest {field} that fits beside {beside} is {fits} " if fits is not None
           else f"no {field} fits beside {beside} ")
        + f"(REPORT_COLUMN_DEPTH_EXCEEDED: one joint bound, need({tid}, window) + need({chained}, chainedWindow) - 1; "
          f"measured 2026-11-11 at 161.0.0)")]


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
        unspelled = [k for k in m.parameters if k not in KNOB_SPELLED]
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


# --- spread operands under an average, and spread as a chain outer (contract 168) -------------------------------------
# Both served since 168.2.0 and undocumented (the vendor README stops at v156); every rule below was measured on
# 2026-11-12 at 169.4.0 by preview_strategy_report (data/audit/authoring_probe_169_2026-11-12.json groups V and W,
# -c group J). The quoted words are the platform's refusals.
AVERAGE_OPERAND_TRANSFORMS = ("aggregate", "ema", "rma", "wma")
AVERAGE_OPERAND_MIN_WINDOW = 2


def _off_anchor(column: Column) -> bool:
    return getattr(column.timeframe, "rel", None) != "anchor"


def default_window(transform_id: str, c: Contract) -> int | None:
    """The window the platform fills when a column omits it: the catalogue's default (ema 20, rma 14, wma 20,
    aggregate 24) - V.no.inner.window rendered `close_ema20_EMA50_spread`."""
    return _window_parameter(transform_id, c).get("defaultValue")


def _averaged_operand(op, m: Metric, column: Column, c: Contract, path: str) -> list[Finding]:
    """A spread operand under an average, `{metric, transformId, window}`, on a plain spread or a chained one.

    - both or neither: "An averaged operand names both transformId and window, or neither" (W.no.window and its mirror);
    - transformId aggregate / ema / rma / wma: "expected one of ..." (W.transform.rsi / zscore / trajectory);
    - window at least 2: "requires a length of at least 2 (got 1) - at 1 an average is its own source";
    - the bars one operand value reads within the metric's depth: "operand window 705 reads 2439 bars for one value -
      at most 2436 of the 2500 readable bars ...; the largest operand window that fits is 704" (2436 / 704 / 308 /
      2436, the same as a standalone column's). The operand's own lookback does not shorten it: SMA200 under
      aggregate 2436 rendered (J.op.SMA200.agg2436);
    - the metric one of the served spreadAverageOperands (off the anchor rung spreadAverageOperandsOffAnchor): "'MARK'
      is not a legal averaged spread operand for base 'CLOSE' - an average folds a per-bar candle value of the base's
      own unit on the column's bars". The base itself is one (close_close_ema20_spread)."""
    if op.transformId is None or op.window is None:
        return [Finding("error", "OPERAND_AVERAGE_INCOMPLETE", path,
                        f"spread operand {op.metric!r}: an averaged operand names both transformId and window, or "
                        f"neither (got transformId {op.transformId!r}, window {op.window!r})")]
    out: list[Finding] = []
    if op.transformId not in AVERAGE_OPERAND_TRANSFORMS:
        out.append(Finding("error", "OPERAND_AVERAGE_TRANSFORM", f"{path}.transformId",
                           f"an averaged spread operand is read under one of {list(AVERAGE_OPERAND_TRANSFORMS)}, not "
                           f"{op.transformId!r}"))
    if op.window < AVERAGE_OPERAND_MIN_WINDOW:
        out.append(Finding("error", "WINDOW_BELOW_MINIMUM", f"{path}.window",
                           f"spread operand {op.metric!r} under {op.transformId} requires a length of at least "
                           f"{AVERAGE_OPERAND_MIN_WINDOW} (got {op.window}) - at 1 an average is its own source"))
    elif op.transformId in AVERAGE_OPERAND_TRANSFORMS:
        budget = depth_budget(m)
        need = bars_needed(op.transformId, op.window)
        if budget is None:
            out.append(Finding("error", "DEPTH_UNMEASURED", f"{path}.window",
                               f"{m.metric} serves no depth-bound aggregate maximum, so how many bars the averaged "
                               f"operand may read is unmeasured offline"))
        elif need > budget:
            out.append(Finding("error", "DEPTH_EXCEEDED", f"{path}.window",
                               f"operand window {op.window} reads {need} bars for one value - at most {budget} of the "
                               f"readable bars; the largest operand window that fits is "
                               f"{largest_window(op.transformId, budget)}"))
    off = _off_anchor(column)
    allowed = m.spread_average_operands_off_anchor if off else m.spread_average_operands
    if op.metric not in allowed:
        out.append(Finding("error", "OPERAND_NOT_ALLOWED", f"{path}.metric",
                           f"{op.metric!r} is not a legal averaged spread operand for base {m.metric!r}"
                           f"{' off the anchor rung' if off else ''} - an average folds a per-bar candle value of the "
                           f"base's own unit on the column's bars (served spreadAverageOperands"
                           f"{'OffAnchor' if off else ''}: {list(allowed)})"))
    return out


def _chained_spread_operand(column: Column, m: Metric, spec: dict, c: Contract, path: str) -> list[Finding]:
    """The operand of `spread` as a chain outer after an average (`<metric> x aggregate|ema|rma|wma -> spread`): the
    averaged series spread against one operand at the column's own timeframe.

    - exactly one operand: "transform 'ema' -> 'spread' requires params.inputs";
    - a plain operand from the inner's chainedOuters.spread.operands (off the anchor rung operandsOffAnchor) - which
      leaves the base out: "spread operand 'CLOSE' is not a legal relational operand for base 'CLOSE'"; and a level read
      per anchor bar only at the anchor ("'PIVOT_WEEK_P' is a level read per anchor bar ... a relation meets it only at
      the strategy's anchor rung");
    - an averaged operand on the plain spread's rules (close_ema20_close_mean50_spread), except the chain's own
      average: "operand 'close_rma308' is the chain's own average - a spread against itself is identically zero".
    chainedWindow and offset are refused by their own checks (CHAINED_WINDOW_REFUSED, OFFSET_REFUSED); the inner window
    keeps its standalone maximum (DEPTH_EXCEEDED, 2436 / 704 / 308 = the served innerWindowMaximum)."""
    inputs = column.inputs or []
    if len(inputs) != 1:
        return [Finding("error", "OPERAND_REQUIRED", f"{path}.inputs",
                        f"transform {column.transformId!r} -> 'spread' requires params.inputs: exactly one operand, got "
                        f"{len(inputs)}")]
    op = inputs[0]
    tid = column.transformId
    if op.averaged:
        out = _averaged_operand(op, m, column, c, f"{path}.inputs[0]")
        window = column.window if column.window is not None else default_window(tid, c)
        if op.metric == m.metric and op.transformId == tid and op.window == window:
            out.append(Finding("error", "OPERAND_SELF", f"{path}.inputs[0]",
                               f"spread operand {op.metric!r} under {tid} {window} is the chain's own average - a "
                               f"spread against itself is identically zero"))
        return out
    outer = (spec.get("chainedOuters") or {}).get("spread") or {}
    off = _off_anchor(column)
    served = outer.get("operandsOffAnchor") if off else outer.get("operands")
    if served is None:
        return [Finding("error", "TRANSFORM_UNMEASURED", f"{path}.inputs[0]",
                        f"({m.metric} x {tid} -> spread) serves no operand list "
                        f"(chainedOuters.spread.{'operandsOffAnchor' if off else 'operands'}): its operands are "
                        f"unmeasured offline")]
    if op.metric not in served:
        on_anchor_only = off and op.metric in (outer.get("operands") or ())
        return [Finding("error", "REPORT_COLUMN_OPERAND_UNSUPPORTED", f"{path}.inputs[0]",
                        f"spread operand {op.metric!r} is a level read per anchor bar: a relation meets it only at the "
                        f"strategy's anchor rung ({{rel: 'anchor'}}) (served chainedOuters.spread.operandsOffAnchor)"
                        if on_anchor_only else
                        f"spread operand {op.metric!r} is not a legal relational operand for ({m.metric} x {tid} -> "
                        f"spread) (served chainedOuters.spread.{'operandsOffAnchor' if off else 'operands'}: "
                        f"{list(served)})")]
    return []


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
