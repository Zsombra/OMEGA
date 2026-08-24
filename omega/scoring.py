"""The score layer: raw indicator reading -> the 0-1 number the aggregate consumes.

This is the transformation directly beneath omega.aggregate. Aggregation asks
"given scores and allocations, does this route?"; this module answers the question
underneath it: "given the market, what IS the score?"

Every formula here was reproduced bit-exact against a live get_coin_signal_preview
reading before being written down. See data/contract/signals/_scoring.json for the
per-signal provenance and data/performance/score_probes.json for the readings.

Two facts drive the whole design:

1. EVERY score is clamped to [0, 1]. The published signal definitions show raw
   examples above 1.0 - ma_sma200_above "+10% -> 2.0" - and those examples are
   misleading. Measured: +10.23% gives raw 2.047 and the engine reports 1.

2. Not every signal is computable. 16 divergence signals are documented only
   qualitatively, and regime_alignment's published formula contradicts live
   readings. Those return Score(computable=False) rather than a plausible guess,
   because a guess is indistinguishable from a measurement once it is a float.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

__all__ = ["Score", "score", "clamp01", "SCORERS", "UNCOMPUTABLE"]


def clamp01(x: float) -> float:
    """The engine's clamp. Four independent live proofs; see module docstring."""
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


@dataclass(frozen=True)
class Score:
    """A score, or an explicit refusal to produce one.

    `computable` is a separate field rather than `value is None` on purpose: the
    caller must be able to tell "this signal did not fire" (value 0.0, computable)
    from "this toolkit cannot model this signal" (computable False).
    """

    signal_id: str
    value: float | None
    computable: bool = True
    raw: float | None = None
    clamped: bool = False
    reason: str = ""

    def __str__(self) -> str:
        if not self.computable:
            return f"{self.signal_id}: not computable - {self.reason}"
        tail = f"  (raw {self.raw:.6f}, clamped)" if self.clamped else ""
        return f"{self.signal_id}: {self.value:.10f}{tail}"


# --- the families -----------------------------------------------------------

def linear_below(value: float, threshold: float, normaliser: float) -> float:
    return (threshold - value) / normaliser


def linear_above(value: float, threshold: float, normaliser: float) -> float:
    return (value - threshold) / normaliser


def proximity(distance_pct: float, proximity_pct: float) -> float:
    return 1.0 - (distance_pct / proximity_pct)


def pct_gap(value: float, reference: float, divisor: float = 1.0) -> float:
    """Percentage gap from a REFERENCE level, over a fixed divisor.

    The reference is always the denominator, in both directions - the bear variants
    divide by SMA50 exactly as the bull variants do, not by whichever level is
    larger. Getting this backwards produces a ~0.5% error that looks perfectly
    plausible in isolation; it was caught only by asserting bit-exact equality
    against a live reading (BTC 1h ltf_ma_aligned_bear).
    """
    return abs(value - reference) / reference * 100.0 / divisor


def midline_scaled(value: float, midline: float = 50.0, span: float = 30.0) -> float:
    return abs(value - midline) / span


def flow_rate(current: float, previous: float) -> float:
    """A CVD stream's self-normalised rate of change, clamped to +/-1.

    The clamp is visible in the engine's own text: BTC's perp rate was raw 1.545
    and the details string printed "perp rate 1.00".
    """
    r = (current - previous) / abs(previous)
    return -1.0 if r < -1.0 else (1.0 if r > 1.0 else r)


def synthesis_mean(*component_scores: float) -> float:
    """Second-order signals average their components' exact post-clamp scores."""
    return sum(component_scores) / len(component_scores)


# --- signals the toolkit deliberately will not model ------------------------

UNCOMPUTABLE: dict[str, str] = {
    "regime_alignment": (
        "published formula is alignedCount/3, but two independent live previews "
        "returned 0.7, which no integer count over 3 can produce - unresolved"
    ),
}
_DIVERGENCE_REASON = (
    "the platform documents this signal's magnitude only qualitatively; the "
    "direction of the relationship is known, the curve is not"
)
for _sid in (
    "rsi_bull_divergence", "rsi_bear_divergence",
    "macd_bull_cross", "macd_bear_cross",
    "macd_bull_divergence", "macd_bear_divergence",
    "volume_obv_bull_divergence", "volume_obv_bear_divergence",
    "oi_divergence_bull", "oi_divergence_bear",
    "rel_ppo_bull_cross", "rel_ppo_bear_cross",
    "mfi_bull_divergence", "mfi_bear_divergence",
    "cvd_bull_divergence", "cvd_bear_divergence",
):
    UNCOMPUTABLE[_sid] = _DIVERGENCE_REASON


# --- per-signal scorers -----------------------------------------------------
# Each takes (indicatorValues, params) and returns the RAW score, pre-clamp.
# Param names are the engine's own, taken from a live strategy's signalRules.

IV = Mapping[str, float]
P = Mapping[str, float]
Scorer = Callable[[IV, P], float]

SCORERS: dict[str, Scorer] = {
    # RSI - bounded 0-100, so the normaliser is the distance to the bound
    "rsi_oversold":       lambda v, p: linear_below(v["rsi14"], p.get("threshold", 30), p.get("threshold", 30)),
    "rsi_overbought":     lambda v, p: linear_above(v["rsi14"], p.get("threshold", 70), 100 - p.get("threshold", 70)),
    "htf_rsi_oversold":   lambda v, p: linear_below(v["htf_rsi14"], p.get("threshold", 30), p.get("threshold", 30)),
    "htf_rsi_overbought": lambda v, p: linear_above(v["htf_rsi14"], p.get("threshold", 70), 100 - p.get("threshold", 70)),
    "ltf_rsi_oversold":   lambda v, p: linear_below(v["ltf_rsi14"], p.get("threshold", 30), p.get("threshold", 30)),
    "ltf_rsi_overbought": lambda v, p: linear_above(v["ltf_rsi14"], p.get("threshold", 70), 100 - p.get("threshold", 70)),

    # STOCHASTIC - oversold reads the lower of K/D, overbought the higher
    "stoch_oversold":   lambda v, p: linear_below(min(v["stoch_k"], v["stoch_d"]), p.get("threshold", 20), p.get("threshold", 20)),
    "stoch_overbought": lambda v, p: linear_above(max(v["stoch_k"], v["stoch_d"]), p.get("threshold", 80), 100 - p.get("threshold", 80)),
    "stoch_bull_cross": lambda v, p: linear_below(v["stoch_d"], p.get("zoneThreshold", 30), p.get("zoneThreshold", 30)),
    "stoch_bear_cross": lambda v, p: linear_above(v["stoch_d"], p.get("zoneThreshold", 70), 100 - p.get("zoneThreshold", 70)),

    # VOLUME / VOLATILITY - unbounded ratios, normalised by the threshold itself
    "volume_surge":  lambda v, p: linear_above(v["volume_ratio"], p.get("multiplier", 2.0), p.get("multiplier", 2.0)),
    "volume_dry_up": lambda v, p: linear_below(v["volume_ratio"], p.get("multiplier", 0.5), p.get("multiplier", 0.5)),
    "volatility_atr_expanding":   lambda v, p: linear_above(v["atr_value"] / v["prev_atr_value"], p.get("multiplier", 1.5), p.get("multiplier", 1.5)),
    "volatility_atr_contracting": lambda v, p: linear_below(v["atr_value"] / v["prev_atr_value"], p.get("multiplier", 0.7), p.get("multiplier", 0.7)),

    # BOLLINGER
    "bollinger_squeeze":     lambda v, p: linear_below(v["bb_width"] / v["bb_middle"], p.get("bandwidthPct", 0.04), p.get("bandwidthPct", 0.04)),
    "bollinger_lower_touch": lambda v, p: linear_below(v["bb_percent_b"], p.get("pctBThreshold", 0.05), p.get("pctBThreshold", 0.05)),
    "bollinger_upper_touch": lambda v, p: linear_above(v["bb_percent_b"], p.get("pctBThreshold", 0.95), 1 - p.get("pctBThreshold", 0.95)),
    "bollinger_cci_oversold":   lambda v, p: linear_below(v["cci20_value"], p.get("threshold", -100), 100.0),
    "bollinger_cci_overbought": lambda v, p: linear_above(v["cci20_value"], p.get("threshold", 100), 100.0),

    # MOVING AVERAGES - note the two different reference levels and divisors
    # reference level is the denominator in BOTH directions - see pct_gap's docstring
    "ma_ema_aligned_bull": lambda v, p: pct_gap(v["ema5"], v["ema20"], 1.0),
    "ma_ema_aligned_bear": lambda v, p: pct_gap(v["ema5"], v["ema20"], 1.0),
    "ma_ema_bull_cross":   lambda v, p: 0.7,
    "ma_ema_bear_cross":   lambda v, p: 0.7,
    "ma_sma200_above": lambda v, p: pct_gap(v["price"], v["sma200"], 5.0),
    "ma_sma200_below": lambda v, p: pct_gap(v["price"], v["sma200"], 5.0),
    "htf_ma_aligned_bull": lambda v, p: pct_gap(v["htf_price"], v["htf_sma50"], 5.0),
    "htf_ma_aligned_bear": lambda v, p: pct_gap(v["htf_price"], v["htf_sma50"], 5.0),
    "ltf_ma_aligned_bull": lambda v, p: pct_gap(v["ltf_price"], v["ltf_sma50"], 5.0),
    "ltf_ma_aligned_bear": lambda v, p: pct_gap(v["ltf_price"], v["ltf_sma50"], 5.0),

    # TREND STRENGTH - ADX is bounded 0-100 but normalises by the THRESHOLD
    "trend_adx_trending":     lambda v, p: linear_above(v["adx_value"], p.get("threshold", 25), p.get("threshold", 25)),
    "trend_adx_ranging":      lambda v, p: linear_below(v["adx_value"], p.get("threshold", 20), p.get("threshold", 20)),
    "htf_trend_adx_trending": lambda v, p: linear_above(v["htf_adx_value"], p.get("threshold", 25), p.get("threshold", 25)),
    "htf_trend_adx_ranging":  lambda v, p: linear_below(v["htf_adx_value"], p.get("threshold", 20), p.get("threshold", 20)),
    "ltf_trend_adx_trending": lambda v, p: linear_above(v["ltf_adx_value"], p.get("threshold", 25), p.get("threshold", 25)),
    "ltf_trend_adx_ranging":  lambda v, p: linear_below(v["ltf_adx_value"], p.get("threshold", 20), p.get("threshold", 20)),

    # FUNDING / OPEN INTEREST
    "funding_extreme_positive": lambda v, p: linear_above(v["funding_rate"], p.get("thresholdPct", 0.0005), p.get("thresholdPct", 0.0005)),
    "funding_extreme_negative": lambda v, p: linear_below(v["funding_rate"], -p.get("thresholdPct", 0.0005), p.get("thresholdPct", 0.0005)),
    "funding_rate_flipping":    lambda v, p: 0.6,
    "oi_surge": lambda v, p: linear_above(
        (v["open_interest"] - v["prev_open_interest"]) / v["prev_open_interest"],
        p.get("thresholdPct", 0.05), p.get("thresholdPct", 0.05)),

    # RELATIVE STRENGTH
    "rel_roc_positive": lambda v, p: v["roc12_value"] / 5.0,
    "rel_roc_negative": lambda v, p: abs(v["roc12_value"]) / 5.0,

    # SUPPORT / RESISTANCE
    "sr_at_support":    lambda v, p: proximity(abs(v["price"] - v["swing_low"]) / v["price"], p.get("proximityPct", 0.005)),
    "sr_at_resistance": lambda v, p: proximity(abs(v["swing_high"] - v["price"]) / v["price"], p.get("proximityPct", 0.005)),
    "sr_support_break":    lambda v, p: (v["swing_low"] - v["price"]) / v["swing_low"] * 100.0,
    "sr_resistance_break": lambda v, p: (v["price"] - v["swing_high"]) / v["swing_high"] * 100.0,

    # MFI
    "mfi_oversold":   lambda v, p: linear_below(v["mfi14_value"], p.get("threshold", 20), p.get("threshold", 20)),
    "mfi_overbought": lambda v, p: linear_above(v["mfi14_value"], p.get("threshold", 80), 100 - p.get("threshold", 80)),
    "mfi_sustained_bullish": lambda v, p: midline_scaled(v["mfi14_value"]),
    "mfi_sustained_bearish": lambda v, p: midline_scaled(v["mfi14_value"]),

    # COMPARISON - normaliser is TWICE maxCorrelation, verified at corr 0.0 -> 0.5
    "comparison_btc_decorrelation": lambda v, p: linear_below(
        v["correlation"], p.get("maxCorrelation", 0.3), 2 * p.get("maxCorrelation", 0.3)),
    "comparison_sector_momentum":   lambda v, p: v["alignedCount"] / v["peerCount"],
    "comparison_sector_divergence": lambda v, p: v["divergentCount"] / v["peerCount"],

    # PRICE STRUCTURE
    "structure_fvg_approach": lambda v, p: proximity(v["distancePct"], p.get("proximityPct", 1.0)),
    "structure_ob_approach":  lambda v, p: proximity(v["distancePct"], p.get("proximityPct", 1.0)),
    "structure_zone_cluster": lambda v, p: v["zoneCount"] / 3.0,

    # FLOW DIVERGENCE
    "flow_perp_spot_bull_divergence": lambda v, p: (
        flow_rate(v["spot_cvd_value"], v["prev_spot_cvd_value"])
        - flow_rate(v["perp_cvd_value"], v["prev_perp_cvd_value"])),
    "flow_perp_spot_bear_divergence": lambda v, p: (
        flow_rate(v["perp_cvd_value"], v["prev_perp_cvd_value"])
        - flow_rate(v["spot_cvd_value"], v["prev_spot_cvd_value"])),

    # CONFLUENCE - synthesis over component scores, not indicators
    "mtf_aligned_bull": lambda v, p: synthesis_mean(v["ltf_score"], v["primary_score"], v["htf_score"]),
    "mtf_aligned_bear": lambda v, p: synthesis_mean(v["ltf_score"], v["primary_score"], v["htf_score"]),
    "mtf_pullback_long":  lambda v, p: v["ltf_score"],
    "mtf_pullback_short": lambda v, p: v["ltf_score"],
}

# Two-state signals: the score depends on a categorical secondary test the caller
# must supply as `state_high`, because the engine reads it from regime/CVD context
# rather than from a numeric indicator.
_TWO_STATE: dict[str, tuple[float, float]] = {
    "cvd_bullish": (1.0, 0.5),
    "cvd_bearish": (1.0, 0.5),
    "regime_trend_shift": (1.0, 0.5),
    "regime_volatility_shift": (1.0, 0.5),
    "regime_divergence": (1.0, 0.6),
    "structure_zone_confluence": (1.0, 0.8),
}
for _sid, (_hi, _lo) in _TWO_STATE.items():
    SCORERS[_sid] = (lambda hi, lo: lambda v, p: hi if v.get("state_high") else lo)(_hi, _lo)


def score(signal_id: str, indicator_values: IV, params: P | None = None) -> Score:
    """Compute one signal's score from a reading, or refuse and say why.

    >>> score("trend_adx_ranging", {"adx_value": 11.68241454}, {"threshold": 20}).value
    0.415879273
    """
    if signal_id in UNCOMPUTABLE:
        return Score(signal_id, None, computable=False, reason=UNCOMPUTABLE[signal_id])
    fn = SCORERS.get(signal_id)
    if fn is None:
        return Score(signal_id, None, computable=False, reason="unknown signal id")
    try:
        raw = float(fn(indicator_values, params or {}))
    except KeyError as exc:
        return Score(signal_id, None, computable=False,
                     reason=f"missing indicator {exc.args[0]!r}")
    except ZeroDivisionError:
        return Score(signal_id, None, computable=False, reason="zero denominator")
    value = clamp01(raw)
    return Score(signal_id, value, raw=raw, clamped=(value != raw))
