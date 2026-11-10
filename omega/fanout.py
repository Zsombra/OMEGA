"""Predict the output headers a column compiles to, and cost a report against the budgets.

The 32-columns-per-section limit is rarely what bites. `trajectory` fans out to
window+1 headers, so header count - and the ~16000 token budget it drives - is the
real constraint. This module makes that visible before you submit.
"""
from __future__ import annotations

from dataclasses import dataclass

from functools import lru_cache

from .contract import CONTRACT_DIR, Contract, _load as _load_json, load
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


# The metric knobs' header spelling, measured 2026-11-07 at 149.1.0 (preview_strategy_report, BTC 1h;
# data/audit/authoring_probe_149_2026-11-07.json groups C, D, E, I, J). The hint serves each knob's range but not its
# spelling, so the spelling is this table. Two regimes:
#  - a SET: once any of the metric's set knobs is off its default, every one of them is spelled, values concatenated in
#    the served order behind one `_`: MACDline_fast8slow26sig9, K_p21s1d3, bbUpper20_p30sd2.5, kcUpper_p30atr14mult1.5,
#    stLine_atr14mult2, PSAR_start0.01inc0.01max0.3, CMF20_p30, fractalHi_l3r5 / fractalLo_l4r2. `rsiPeriod` is spelled
#    as its own token ahead of the rest: stochRsiK_rsi21_p14s3d3.
#  - SINGLE knobs, each its own token and only when off its default, in the served order: eqh_e1, eqh_atr0,
#    eql_e5_atr0.2; structLvl_s10, iStructLvl_cf (a flag spells no value).
# Explicit defaults spell nothing (MACDline, bbUpper20, PSAR, stLine, fractalHi, eqh). The knob part sits right after
# the code: fractalHi_l3r5_4h, bbUpper20_p30sd2.5_ltf_o2, MACDline_fast8slow26sig9_trend, fractalHi_l3r5_close_spread.
KNOB_SPELLING = {"fast": "fast", "slow": "slow", "signal": "sig", "period": "p", "kSmoothing": "s", "dSmoothing": "d",
                 "stdDev": "sd", "atrPeriod": "atr", "multiplier": "mult", "accelerationStart": "start",
                 "accelerationIncrement": "inc", "accelerationMaximum": "max", "leftBars": "l", "rightBars": "r",
                 # 161.0.0, measured 2026-11-09 (authoring_probe_161 group Q): Ichimoku's set, kijun_conv9base27spanB52disp26
                 "conversionPeriod": "conv", "basePeriod": "base", "spanBPeriod": "spanB", "displacement": "disp"}
KNOB_OWN_TOKEN = {"rsiPeriod": "rsi"}
KNOB_SINGLE = {"equalBars": "e", "equalThreshold": "atr", "swingLength": "s", "confluenceFilter": "cf"}
# Each (metric, knob) whose header has been RENDERED with that knob off its default, at 149.1.0: the authoring probe
# (2026-11-07), the knob-spelling probe (11-07, thirteen columns) and its second run (2026-11-08, the 27 cells neither had
# rendered: MACD_SIGNAL and PPO_HIST had no render at all). The spelling tables above are keyed by knob name, so a metric
# serving a known name would otherwise be spelled by analogy; knob_token raises on a cell outside this table instead
# (review 2026-11-08, "extract, never infer"). tests/test_review_2026_11_08.py recomputes it from the three records.
KNOB_SPELLING_RENDERED = {
    "BB_LOWER": frozenset({'period', 'stdDev'}),
    "BB_PCT_B": frozenset({'period', 'stdDev'}),
    "BB_UPPER": frozenset({'period', 'stdDev'}),
    "CMF20": frozenset({'period'}),
    "EQH": frozenset({'equalBars', 'equalThreshold'}),
    "EQL": frozenset({'equalBars', 'equalThreshold'}),
    "INTERNAL_STRUCTURE_EVENT": frozenset({'swingLength', 'confluenceFilter'}),
    "INTERNAL_STRUCTURE_LEVEL": frozenset({'swingLength', 'confluenceFilter'}),
    "INTERNAL_STRUCTURE_TREND": frozenset({'swingLength', 'confluenceFilter'}),
    "KC_LOWER": frozenset({'period', 'atrPeriod', 'multiplier'}),
    "KC_UPPER": frozenset({'period', 'atrPeriod', 'multiplier'}),
    "MACD_HIST": frozenset({'fast', 'slow', 'signal'}),
    "MACD_LINE": frozenset({'fast', 'slow', 'signal'}),
    "MACD_SIGNAL": frozenset({'fast', 'slow', 'signal'}),
    "MFI14": frozenset({'period'}),
    "PPO_HIST": frozenset({'fast', 'slow', 'signal'}),
    "PPO_LINE": frozenset({'fast', 'slow', 'signal'}),
    "PPO_SIGNAL": frozenset({'fast', 'slow', 'signal'}),
    "PRIOR_SWING_FRACTAL_HIGH": frozenset({'leftBars', 'rightBars'}),
    "PRIOR_SWING_FRACTAL_LOW": frozenset({'leftBars', 'rightBars'}),
    "PSAR": frozenset({'accelerationStart', 'accelerationIncrement', 'accelerationMaximum'}),
    "STOCH_D": frozenset({'period', 'kSmoothing', 'dSmoothing'}),
    "STOCH_K": frozenset({'period', 'kSmoothing', 'dSmoothing'}),
    "STOCH_RSI_D": frozenset({'period', 'kSmoothing', 'dSmoothing', 'rsiPeriod'}),
    "STOCH_RSI_K": frozenset({'period', 'kSmoothing', 'dSmoothing', 'rsiPeriod'}),
    "ST_DIR": frozenset({'atrPeriod', 'multiplier'}),
    "ST_LINE": frozenset({'atrPeriod', 'multiplier'}),
    "SWING_FRACTAL_HIGH": frozenset({'leftBars', 'rightBars'}),
    "SWING_FRACTAL_HIGH_BARS_AGO": frozenset({'leftBars', 'rightBars'}),
    "SWING_FRACTAL_LABEL": frozenset({'leftBars', 'rightBars'}),
    "SWING_FRACTAL_LOW": frozenset({'leftBars', 'rightBars'}),
    "SWING_FRACTAL_LOW_BARS_AGO": frozenset({'leftBars', 'rightBars'}),
    "SWING_STRUCTURE_EVENT": frozenset({'swingLength'}),
    "SWING_STRUCTURE_LEVEL": frozenset({'swingLength'}),
    "SWING_STRUCTURE_TREND": frozenset({'swingLength'}),
    "WILLR14": frozenset({'period'}),
    # 161.0.0, rendered 2026-11-09 (data/audit/authoring_probe_161_2026-11-09.json group Q): the `period` 161 gave ADX,
    # ATR and the two DIs (ADX14_p15, ATR14_p15, DIplus14_p15, DIminus14_p15), VWMA20's (VWMA20_p21), and Ichimoku's
    # four-knob set on its five lines, each knob off alone and two, four and none together (kijun_conv10base27spanB52disp26,
    # tenkan at every default)
    "ADX": frozenset({'period'}),
    "ATR": frozenset({'period'}),
    "DI_MINUS": frozenset({'period'}),
    "DI_PLUS": frozenset({'period'}),
    "VWMA20": frozenset({'period'}),
    **{m: frozenset({'conversionPeriod', 'basePeriod', 'spanBPeriod', 'displacement'})
       for m in ("ICHI_BASE", "ICHI_CONV", "ICHI_LAG", "ICHI_SPAN_A", "ICHI_SPAN_B")},
}


class KnobSpellingUnmeasured(ValueError):
    """A header whose knob part was never rendered (KNOB_SPELLING_RENDERED). omega.validate refuses such a column
    (KNOB_SPELLING_UNMEASURED); a header-predicting caller skips it as it skips an unmeasured metric."""


def predictable(column: Column, contract: Contract) -> bool:
    """False for a column whose header omega cannot predict (KnobSpellingUnmeasured) - it adds no predicted header."""
    try:
        knob_token(column, contract)
        return True
    except KnobSpellingUnmeasured:
        return False


def _knob_number(value) -> str:
    """A knob value as the header prints it: 2.5, 0.01, 0.2; an integral number without its point (sd5, mult10, max1)."""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else f"{value:g}"
    return str(value)


def knob_token(column: Column, contract: Contract) -> str:
    """The knob part of a header (KNOB_SPELLING above), "" when every served knob is at its default. A knob the metric
    does not serve is not spelled (omega.validate refuses it, PARAMETER_UNDECLARED)."""
    served = contract.metric(column.metric).parameters
    if not served:
        return ""
    values = {k: getattr(column, k, None) for k in served}

    def is_off(k: str) -> bool:
        return values[k] is not None and values[k] != served[k].get("defaultValue")

    def value(k: str):
        return values[k] if values[k] is not None else served[k].get("defaultValue")

    unknown = [k for k in served if k not in KNOB_SPELLING and k not in KNOB_OWN_TOKEN and k not in KNOB_SINGLE]
    if unknown and any(is_off(k) for k in served):
        # Any knob off, not only an unknown one: in the SET regime an unspelled knob at its default still belongs in the
        # header, and which regime an unknown knob is in was never rendered either (review 2026-11-08).
        raise KnobSpellingUnmeasured(f"{column.metric} serves knobs whose header spelling was never rendered: {unknown}")
    unrendered = [k for k in served if is_off(k) and k not in KNOB_SPELLING_RENDERED.get(column.metric, ())]
    if unrendered:
        raise KnobSpellingUnmeasured(
            f"{column.metric} at {unrendered} off its default was never rendered (KNOB_SPELLING_RENDERED)")
    set_knobs = [k for k in served if k not in KNOB_SINGLE]
    out = ""
    if any(is_off(k) for k in set_knobs):
        out += "".join(f"_{KNOB_OWN_TOKEN[k]}{_knob_number(value(k))}" for k in set_knobs if k in KNOB_OWN_TOKEN)
        rest = "".join(f"{KNOB_SPELLING[k]}{_knob_number(value(k))}" for k in set_knobs if k in KNOB_SPELLING)
        out += f"_{rest}" if rest else ""
    for k in served:
        if k in KNOB_SINGLE and is_off(k):
            out += f"_{KNOB_SINGLE[k]}" + ("" if served[k].get("bound") == "flag" else _knob_number(values[k]))
    return out


def takes_offset(transform_id: str, contract: Contract) -> bool:
    """Whether the transform's served authoring parameters carry `offset`: `value` always, `rollingMin` / `rollingMax`
    since 148.1.0 (v146.6)."""
    return "offset" in ((contract.transforms.get(transform_id) or {}).get("parameters") or {})


def _token(column: Column, contract: Contract) -> str:
    """The metric's header token: `<code>[knobs][_ltf|_htf|_<abs>][_dev][_o<N>]` (contract 109, measured 2026-10-13 -
    data/contract/columns/header_tokens_2026-10-13.json; the vendor pack 31.2.98 states the same order; the knob part
    measured 2026-11-07 at 149.1.0).

    - the knob part (knob_token): fractalHi_l3r5, MACDline_fast8slow26sig9, eqh_e5_atr0.2;
    - the timeframe part: `_ltf` / `_htf` for rel lower / regime (REL_INFIX), `_<tf>` for ANY pinned `abs` - even one
      equal to the anchor (`ADX14_1h` at a 1h anchor) - and nothing at rel anchor;
    - `_dev` when the column STORES `bars: "all"` (Developing), at any timeframe; `closed` or unset adds nothing;
    - `_o<N>` for an `offset` N > 0, on a transform that takes one: `value`, and since 148.1.0 `rollingMin` /
      `rollingMax` (high_o1_max55, high_ltf_o1_max55, high_4h_o1_max55; measured 2026-11-07).
    `<code>` is the metric file's `code`; since contract v123 the eighteen indicator codes carry their length (`ADX14`,
    `pctB20`, `RVOL20`, ... - data/contract/metrics/_moves_123.json), and omega.contract.load refuses a stale one.
    Until 2026-10-13 omega emitted only the rel part, so `RSI14_1d`, `RSI7_o1` and `ADX_dev_t2` were mispredicted -
    and offset no longer collides two `value` columns (cookbook trap 20 is history)."""
    code = contract.metric(column.metric).code
    rel = getattr(column.timeframe, "rel", None)
    tf = REL_INFIX.get(rel, "").rstrip("_") if rel else f"_{column.timeframe.abs}"
    dev = "_dev" if column.bars == "all" else ""
    off = f"_o{column.offset}" if column.offset and takes_offset(column.transformId, contract) else ""
    return f"{code}{knob_token(column, contract)}{tf}{dev}{off}"


# The six series statistics of contract v135, and the suffix each header carries with its window (default 20).
# Measured 2026-10-26 at 135.2.0 (preview_strategy_report, BTC 1h): RSI14_z20, RSI14_sd10, RSI14_slope10, RSI14_pctl10,
# RSI14_min10, RSI14_max10 on an atom; dist_EMA20_z10, EMA5_EMA13_spread_max10 as a chain outer
# (data/audit/statistics_probe_135_2026-10-26.json).
STATISTIC_SUFFIX = {"zscore": "z", "stddev": "sd", "linregSlope": "slope", "pctl": "pctl",
                    "rollingMin": "min", "rollingMax": "max"}
STATISTIC_DEFAULT_WINDOW = 20
# The five smoothers (ema since 148.1.0, v146.7; rma / wma / rsi / cci since 149.0.0), measured 2026-11-07 at 149.1.0
# (data/audit/authoring_probe_149_2026-11-07.json groups A and J): the header is the base plus `_<id><window>`, the
# window always spelled, its default the catalogue's (ema 20, rma 14, wma 20, rsi 14, cci 20): RSI14_ema20,
# RSI14_rma14, quoteVol_wma14, parDev_cci20; as a chain outer over distance / spread / relativeTo: dist_close_rma10,
# RSI14_RSI7_spread_ema10, close_BTC_rel_cci10; a pinned timeframe sits in the base (RSI14_4h_cci20).
# 161.0.0 adds `roc` (TradingView's ta.roc, default length 9; measured 2026-11-09, authoring_probe_161 groups K and L):
# close_roc9, RSI14_roc3, close_4h_roc5; as a chain outer dist_EMA20_roc9, RSI14_RSI7_spread_roc5, close_BTC_rel_roc5.
# It spells exactly as a smoother does, and takes no offset ("transform 'roc' does not accept params.offset").
SMOOTHERS = ("ema", "rma", "wma", "rsi", "cci", "roc")
# 161.0.0: a chain whose INNER is one of these keeps `window` for the inner and reads the outer's from `chainedWindow`
# (served chainedOuters.<outer>.windowParameter); headers measured 2026-11-09 (authoring_probe_161 group N):
# close_ema20_mean5, RSI14_rma14_roc3, close_mean10_z20, RSI14_roc5_ema10, close_wma10_max20; no chainedWindow ->
# the outer's default (close_ema20_mean24), no window -> the inner's (close_ema20_mean5).
ROLLING_INNERS = ("aggregate", "ema", "rma", "wma", "rsi", "cci", "roc")


def outer_window(column: Column) -> int | None:
    """The window the chain OUTER reads: `chainedWindow` after a rolling inner (161.0.0), `window` otherwise."""
    return column.chainedWindow if column.transformId in ROLLING_INNERS else column.window


def _smoothed(base: str, column: Column, transform_id: str, contract: Contract, window: int | None = None) -> str:
    window = window or contract.transforms[transform_id]["parameters"]["window"]["defaultValue"]
    return f"{base}_{transform_id}{window}"
# v142.3 relativeTo (measured 2026-10-30 at 144.0.0, data/audit/relative_to_probe_144_2026-10-30.json): the token,
# the instrument as the platform spells it, `_rel` - RSI14_ETH_rel, close_BTC_rel (BTC when omitted), RSI14_ltf_ETH_rel,
# RSI14_4h_ETH_rel; a chain outer follows: close_BTC_rel_z20, close_ETH_rel_t3 .. close_ETH_rel_trend. An instrument
# typed `eth` rendered `ETH`: the platform resolves the symbol case-insensitively and prints the roster spelling.
RELATIVE_DEFAULT_INSTRUMENT = "BTC"


# 146 file (2026-11-02): the 144 measurement carried forward plus MKT_ABOVE_EMA (risk-off / neutral / risk-on, rendered on
# a market section); 144 file: 2026-10-30 record; 135 file: 2026-10-26 record
ZONE_VOCABULARY = CONTRACT_DIR / "columns" / "zone_vocabulary_146_2026-11-02.json"
_ZONE_DEFAULT = ("overbought", "oversold", "neutral")


@lru_cache(maxsize=1)
def _zone_vocabularies() -> dict[str, tuple[str, ...]]:
    try:
        return {m: tuple(v) for m, v in _load_json(ZONE_VOCABULARY)["byMetric"].items()}
    except (OSError, KeyError, ValueError):
        return {}


def zone_vocabulary(metric: str) -> tuple[str, ...]:
    """The labels a `metric x classifyZone` header serves, as rendered at 135.2.0: overbought / oversold / neutral on
    the RSIs, stochastics and CCI20, weak / developing / trending / extreme on ADX, and MFI14's five (bullish and bearish
    among them). A metric the measurement did not cover keeps the three-label default."""
    return _zone_vocabularies().get(metric, _ZONE_DEFAULT)


def instrument_token(instrument: str | None) -> str:
    """The instrument as the header spells it (data/audit/relative_to_probe_144b_2026-10-30.json): the roster symbol
    in the platform's own case whatever case the column named it in (`eth` -> `ETH`), without a venue namespace
    (`xyz:BRENTOIL` -> `BRENTOIL`, `AAPL` -> `AAPL`) and without the exchange's `k` thousand-multiplier prefix
    (`kPEPE` and `kpepe` -> `PEPE`). omega reproduces those four measured spellings: the part after the last `:`,
    a leading lower-case `k` before an upper-case symbol dropped, then upper-cased. A roster spelling outside them
    (a symbol the platform prints with lower-case letters) is a header omega cannot predict offline."""
    raw = (instrument or RELATIVE_DEFAULT_INSTRUMENT).rsplit(":", 1)[-1]
    if len(raw) > 1 and raw[0] == "k" and raw[1:].isupper():
        raw = raw[1:]
    return raw.upper()


def scope_token(column: Column) -> str:
    """v136: "A non-default scope adds an `_<scope>` token to the header" - after the ordering: RSI14_rank_hi_crypto,
    EMA5_EMA13_spread_rank_hi_l1 (measured 2026-10-30); `all` and an omitted scope add nothing (RSI14_rank_lo)."""
    return f"_{column.scope}" if column.scope and column.scope != "all" else ""


def _statistic(base: str, column: Column, transform_id: str, window: int | None = None) -> str:
    return f"{base}_{STATISTIC_SUFFIX[transform_id]}{window or STATISTIC_DEFAULT_WINDOW}"


LEVEL_VOCABULARY = ("touch_from_below", "touch_from_above", "reject_from_below", "reject_from_above", "none")


def _level(base: str, column: Column) -> str:
    """levelInteraction's header: `_lvl`, then `_b<bps>` for a non-zero buffer or `_a<atr>` for touchAtr (never both:
    the platform refuses the pair). bbUpper20_lvl_b500, bbUpper20_lvl_a0.5, high_o1_max20_lvl_b10 (161.0.0)."""
    if column.touchAtr is not None:
        return f"{base}_lvl_a{_knob_number(float(column.touchAtr))}"
    return f"{base}_lvl" + (f"_b{column.buffer}" if column.buffer else "")


def _stage1_header(column: Column, contract: Contract) -> str:
    """Header produced by the first transform stage (before any chaining): the token, shaped by the transform.

    Every branch is the token plus the transform's suffix (live renders: close_ltf_er, ADX_ltf_zone, MACD_ltf_cross,
    ADX_ltf_rank_hi, dist_VWAP_4h, EMA5_4h_EMA13_spread, high_4h_dev_mean10, bbUpper_4h_lvl_b25 - each ADX / bbUpper one
    `ADX14` / `bbUpper20` since v123); `distance` is the one
    PREFIX shape (`dist_<token>`)."""
    token, tid = _token(column, contract), column.transformId

    if tid == "distance":
        return f"dist_{token}"
    if tid == "spread":
        operand = contract.metric(column.inputs[0].metric).code if column.inputs else "?"
        return f"{token}_{operand}_spread"
    if tid == "relativeTo":
        return f"{token}_{instrument_token(column.instrument)}_rel"
    if tid == "efficiency":
        return f"{token}_er"
    if tid in STATISTIC_SUFFIX:
        return _statistic(token, column, tid, column.window)
    if tid in SMOOTHERS:
        return _smoothed(token, column, tid, contract, column.window)
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
        return _level(token, column)
    if tid == "crossDetect":
        return f"{token}_cross"
    if tid == "classifyState":          # platform-only, listed for completeness
        return f"{token}_state"
    if tid == "rank":
        return f"{token}_rank_{column.ordering or 'hi'}{scope_token(column)}"
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
        return [Output(f"{base}_rank_{column.ordering or 'hi'}{scope_token(column)}", "rank")]

    if effective == "trajectory":
        window = column.window or 4
        slot_kind = m.native_output["kind"] if column.transformId == "trajectory" else "numeric"
        vocab = tuple(m.vocab or ()) if column.transformId == "trajectory" else ()
        outs = [Output(f"{base}_t{n}", slot_kind, vocab) for n in range(window - 1, 0, -1)]
        outs.append(Output(f"{base}_now", slot_kind, vocab))
        outs.append(Output(f"{base}_trend", "direction", ("rising", "falling", "flat")))
        return outs

    if column.chainedTransformId == "levelInteraction":
        # 161.0.0: a rolling extreme read as a level (high_o1_max20_lvl, low_o1_min20_lvl; measured group M)
        return [Output(_level(base, column), "classification", LEVEL_VOCABULARY)]
    if column.chainedTransformId == "distance":
        # 148.1.0 (v146.6): distance after an offset rolling extreme, a PREFIX as distance always is - dist_high_o1_max55,
        # dist_close_o2_min20, dist_high_4h_o1_max55 (measured 2026-11-07 at 149.1.0, group B / I)
        return [Output(f"dist_{base}", "numeric")]
    if effective in SMOOTHERS:
        return [Output(base if column.chainedTransformId is None
                       else _smoothed(base, column, effective, c, outer_window(column)), "numeric")]
    if effective in ("efficiency", "maxShare"):
        return [Output(base if column.chainedTransformId is None else f"{base}_er", "numeric")]
    if effective in STATISTIC_SUFFIX:
        return [Output(base if column.chainedTransformId is None
                       else _statistic(base, column, effective, outer_window(column)), "numeric")]
    if effective == "aggregate" and column.chainedTransformId:
        return [Output(f"{base}_mean{outer_window(column) or 24}", "numeric")]

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
        vocab = zone_vocabulary(column.metric)
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
            # an unpredictable knob header (refused KNOB_SPELLING_UNMEASURED by omega.validate) charges no header
            headers += len(outputs_for(col, c)) if predictable(col, c) else 0
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
