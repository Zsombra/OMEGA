"""Build the signal-scoring corpus: how every signal turns a reading into a score.

Encodes the score-function FAMILIES generalised from 57 fetched signal definitions and
then CORRECTED against bit-exact live measurements from get_coin_signal_preview.

Provenance is explicit on every entry:

    verified             definition fetched AND a formula-family member reproduced
                         bit-exact against a live reading
    inferred_mirror      not fetched; formula taken from its named opposite-direction
                         twin, which WAS fetched
    documented_mismatch  the published formula does not reproduce the observed score;
                         do not compute it, read the engine's number

Where a published example and a live measurement disagree, the measurement wins and the
disagreement is recorded rather than smoothed over.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "contract" / "signals" / "_scoring.json"

CLAMP_NOTE = "definition publishes a raw example above 1.0; the engine clamps to 1.0"

FAMILIES = {
    "linear_below": {
        "formula": "score = clamp((threshold - value) / normaliser, 0, 1)",
        "note": "Distance below a threshold, normalised. Fires when value < threshold.",
    },
    "linear_above": {
        "formula": "score = clamp((value - threshold) / normaliser, 0, 1)",
        "note": ("Distance above a threshold, normalised. For a metric bounded at 100 or 1 "
                 "the normaliser is the distance to that ceiling; for an unbounded or ratio "
                 "quantity it is the threshold itself. ADX is the exception: bounded 0-100 "
                 "but normalised by the threshold, not by 100-threshold."),
    },
    "proximity": {
        "formula": "score = 1 - (distance / proximityPct)",
        "note": "Closeness to a level. 1.0 at the level, 0 at the proximity boundary.",
    },
    "count_ratio": {
        "formula": "score = count / denominator",
        "note": "Fraction of a discrete set that agrees.",
    },
    "pct_gap_scaled": {
        "formula": "score = clamp(gapPercent / divisor, 0, 1)",
        "note": ("Percentage gap from a REFERENCE level over a fixed divisor. The MA-stack "
                 "signals measure price against SMA50; ma_ema_aligned measures EMA5 against "
                 "EMA20 with divisor 1. The reference is ALWAYS the denominator, in both "
                 "directions - the bear variants divide by SMA50 exactly as the bull "
                 "variants do, not by whichever level happens to be larger. Dividing by the "
                 "larger value instead produces a ~0.5% error that looks entirely plausible; "
                 "it surfaced only under bit-exact comparison with a live reading."),
    },
    "midline_scaled": {
        "formula": "score = clamp(abs(value - 50) / 30, 0, 1)",
        "note": "Distance from the 50 midline over a span of 30, so 80 (or 20) reaches 1.0.",
    },
    "two_state": {
        "formula": "score = high if <primary condition> else low",
        "note": "A fixed pair of scores selected by a secondary test.",
    },
    "fixed": {
        "formula": "score = constant",
        "note": "Event detection with no magnitude dimension.",
    },
    "break_magnitude": {
        "formula": "score = clamp(breakDistancePercent, 0, 1)",
        "note": "The break distance in percentage points, used directly.",
    },
    "flow_rate_gap": {
        "formula": ("rate(x) = clamp((x - prev_x) / abs(prev_x), -1, 1); "
                    "score = rate(leader) - rate(follower)"),
        "note": ("Each CVD stream becomes a self-normalised rate of change clamped to +/-1; "
                 "the score is the gap between them. Verified bit-exact on two coins."),
    },
    "synthesis": {
        "formula": "score = f(component signal scores)",
        "note": ("Second-order: computed from other signals' post-clamp scores at full float "
                 "precision, not from indicators."),
    },
    "unspecified_magnitude": {
        "formula": "score scales with the indicator-vs-price gap (exact form not published)",
        "note": ("The platform documents these only qualitatively. The DIRECTION of the "
                 "relationship is known; the exact curve is not. FIVE live firings have now "
                 "been observed - macd_bear_divergence (BTC), macd_bull_divergence (GOLD), "
                 "cvd_bull_divergence (GOOGL and GOLD), oi_divergence_bull (GOLD) - and "
                 "EVERY ONE returned exactly 1.0. That is suggestive of a fixed score, but "
                 "the oi_divergence_bull definition publishes a 0.50 example, so the "
                 "magnitude clearly can vary. Still refused: read the engine's number."),
    },
}

V = "verified"
M = "inferred_mirror"
D = "documented_mismatch"

S: dict[str, tuple] = {}


def add(sid, family, *, provenance=V, mirror_of=None, **params):
    S[sid] = (family, provenance, mirror_of, params)


# --- RSI --------------------------------------------------------------------
add("rsi_oversold", "linear_below", threshold=30, normaliser="threshold",
    indicator="rsi14", examples=[(27, 0.10), (15, 0.50)])
add("rsi_overbought", "linear_above", threshold=70, normaliser="100 - threshold",
    indicator="rsi14", examples=[(73, 0.10), (85, 0.50)],
    verifiedLive=["ETH 4h RSI 71.0343436 -> 0.03447811999999999 exact"])
add("rsi_bull_divergence", "unspecified_magnitude", indicator="rsi14 vs price")
add("rsi_bear_divergence", "unspecified_magnitude", indicator="rsi14 vs price")
add("htf_rsi_oversold", "linear_below", threshold=30, normaliser="threshold",
    indicator="htf_rsi14", rung="REGIME_RUNG")
add("htf_rsi_overbought", "linear_above", threshold=70, normaliser="100 - threshold",
    indicator="htf_rsi14", rung="REGIME_RUNG",
    verifiedLive=["BTC 1h 72.48511101 -> 0.08283703366666657 exact",
                  "ETH 4h 78.97878029 -> 0.29929267633333345 exact"])
add("ltf_rsi_oversold", "linear_below", threshold=30, normaliser="threshold",
    indicator="ltf_rsi14", rung="LOWER")
add("ltf_rsi_overbought", "linear_above", threshold=70, normaliser="100 - threshold",
    provenance=M, mirror_of="ltf_rsi_oversold", indicator="ltf_rsi14", rung="LOWER")

# --- MACD -------------------------------------------------------------------
add("macd_bull_cross", "unspecified_magnitude", indicator="macd_histogram")
add("macd_bear_cross", "unspecified_magnitude", indicator="macd_histogram")
add("macd_bull_divergence", "unspecified_magnitude", indicator="macd_histogram vs price")
add("macd_bear_divergence", "unspecified_magnitude", indicator="macd_histogram vs price",
    verifiedLive=["BTC 1h -> 1.0 (price higher, histogram falling)"])

# --- STOCHASTIC -------------------------------------------------------------
add("stoch_oversold", "linear_below", threshold=20, normaliser="threshold",
    reads="min(%K, %D)", indicator="stoch_k, stoch_d", examples=[(15, 0.25), (5, 0.75)],
    verifiedLive=["GOOGL 1h K=7.07962432 D=18.85527585 -> 0.646018784 exact "
                  "(confirms the MINIMUM of the pair is read)"])
add("stoch_overbought", "linear_above", threshold=80, normaliser="100 - threshold",
    reads="max(%K, %D)", indicator="stoch_k, stoch_d", examples=[(85, 0.25), (95, 0.75)])
add("stoch_bull_cross", "linear_below", threshold=30, normaliser="threshold",
    reads="%D at the cross", indicator="stoch_k/d", examples=[(15, 0.50), (28, 0.07)])
add("stoch_bear_cross", "linear_above", threshold=70, normaliser="100 - threshold",
    reads="%D at the cross", indicator="stoch_k/d", examples=[(85, 0.50), (72, 0.07)])

# --- VOLUME -----------------------------------------------------------------
add("volume_surge", "linear_above", threshold=2.0, normaliser="threshold",
    indicator="volume_ratio", examples=[(2.4, 0.20), (4.0, 1.00)],
    verifiedLive=["GOOGL 1h ratio 2.351166937666714 -> 0.17558346883335707 exact"])
add("volume_dry_up", "linear_below", threshold=0.5, normaliser="threshold",
    indicator="volume_ratio", examples=[(0.4, 0.20), (0.1, 0.80)])
add("volume_obv_bull_divergence", "unspecified_magnitude", indicator="obv_value vs price")
add("volume_obv_bear_divergence", "unspecified_magnitude", indicator="obv_value vs price")

# --- VOLATILITY -------------------------------------------------------------
add("volatility_atr_expanding", "linear_above", threshold=1.5, normaliser="threshold",
    indicator="atr_value / prev_atr_value", examples=[(1.8, 0.20), (3.0, 1.00)])
add("volatility_atr_contracting", "linear_below", threshold=0.7, normaliser="threshold",
    indicator="atr_value / prev_atr_value", examples=[(0.6, 0.14), (0.3, 0.57)])

# --- BOLLINGER --------------------------------------------------------------
add("bollinger_squeeze", "linear_below", threshold=0.04, normaliser="threshold",
    reads="bb_width / bb_middle", indicator="bb_width, bb_middle",
    verifiedLive=["BTC 1h width/mid 0.023276 -> 0.41808426736396376 exact"])
add("bollinger_lower_touch", "linear_below", threshold=0.05, normaliser="threshold",
    indicator="bb_percent_b", note=CLAMP_NOTE,
    verifiedLive=["GOOGL 1h %B 0.04655411641544565 -> 0.06891767169108706 exact"])
add("bollinger_upper_touch", "linear_above", threshold=0.95, normaliser="1 - threshold",
    indicator="bb_percent_b", note=CLAMP_NOTE,
    verifiedLive=["GOLD 1h %B 0.9571582849660679 -> 0.1431656993213591 exact"])
add("bollinger_cci_oversold", "linear_below", threshold=-100, normaliser="100 (fixed)",
    indicator="cci20_value", examples=[(-150, 0.50), (-250, 1.50)],
    verifiedLive=["GOOGL 1h CCI -179.61719428 -> 0.7961719428 exact"])
add("bollinger_cci_overbought", "linear_above", threshold=100, normaliser="100 (fixed)",
    indicator="cci20_value", examples=[(150, 0.50), (250, 1.50)],
    verifiedLive=["GOLD 1h CCI 248.71764935 -> raw 1.487, engine reports 1 (CLAMP PROOF)"],
    note=("RESOLVED. An earlier note in this project recorded a live 0.269 against a "
          "computed 0.538 and flagged it as an unexplained halving. It was a transcription "
          "error on my part: absent from the stored Dunkirk sample, and the Apex strategy "
          "it was attributed to carries the default threshold 100. Both CCI directions are "
          "now verified bit-exact against live equity and commodity readings."))

# --- MOVING_AVERAGES --------------------------------------------------------
add("ma_ema_aligned_bull", "pct_gap_scaled", divisor=1,
    reads="(ema5 - ema20) / ema20 * 100", indicator="ema5, ema13, ema20",
    verifiedLive=["Dunkirk gap 0.3328% -> 0.333",
                  "BTC 1h gap 0.16150041% -> 0.161500412875903 exact",
                  "ETH 4h gap 2.660% -> raw 2.660, engine reports 1 (CLAMP PROOF)"])
add("ma_ema_aligned_bear", "pct_gap_scaled", divisor=1, provenance=M,
    mirror_of="ma_ema_aligned_bull", indicator="ema5, ema13, ema20")
add("ma_ema_bull_cross", "fixed", constant=0.7, indicator="(cross-detection service)")
add("ma_ema_bear_cross", "fixed", constant=0.7, provenance=M, mirror_of="ma_ema_bull_cross")
add("ma_sma200_above", "pct_gap_scaled", divisor=5,
    reads="(price - sma200) / sma200 * 100", indicator="sma200, price",
    verifiedLive=["Dunkirk +1.951% -> 0.390 exact",
                  "BTC 1h +10.23% -> raw 2.047, engine reports 1 (CLAMP PROOF)",
                  "ETH 4h +24.71% -> raw 4.94, engine reports 1 (CLAMP PROOF)"])
add("ma_sma200_below", "pct_gap_scaled", divisor=5,
    reads="(sma200 - price) / sma200 * 100", indicator="sma200, price",
    verifiedLive=["GOOGL 1h price 343.18 vs SMA200 344.5431 -> "
                  "0.07912507898140898 exact"])
add("htf_ma_aligned_bull", "pct_gap_scaled", divisor=5,
    reads="(price - sma50) / sma50 * 100; requires price > ema20 > sma20 > sma50",
    indicator="htf_price, htf_ema20, htf_sma20, htf_sma50", rung="REGIME_RUNG",
    verifiedLive=["ETH 4h +28.24% -> raw 5.648, engine reports 1 (CLAMP PROOF)"],
    note="NOT a mirror of ma_ema_aligned_bull - different stack AND different divisor")
add("htf_ma_aligned_bear", "pct_gap_scaled", divisor=5, provenance=M,
    mirror_of="htf_ma_aligned_bull", rung="REGIME_RUNG")
add("ltf_ma_aligned_bull", "pct_gap_scaled", divisor=5,
    reads="(price - sma50) / sma50 * 100; requires price > ema20 > sma20 > sma50",
    indicator="ltf_price, ltf_ema20, ltf_sma20, ltf_sma50", rung="LOWER",
    verifiedLive=["ETH 4h price 2444 vs SMA50 2435.41 -> 0.0705425369855601 exact"])
add("ltf_ma_aligned_bear", "pct_gap_scaled", divisor=5,
    reads="(sma50 - price) / sma50 * 100; requires price < ema20 < sma20 < sma50",
    indicator="ltf_price, ltf_ema20, ltf_sma20, ltf_sma50", rung="LOWER",
    verifiedLive=["BTC 1h price 77026 vs SMA50 77450.92 -> 0.10972626277389559 exact"])

# --- TREND_STRENGTH ---------------------------------------------------------
add("trend_adx_trending", "linear_above", threshold=25, normaliser="threshold",
    indicator="adx_value",
    verifiedLive=["ETH 4h ADX 56.077 -> raw 1.243, engine reports 1 (CLAMP PROOF)"],
    note="bounded 0-100 yet normalised by the threshold, NOT by 100-threshold")
add("trend_adx_ranging", "linear_below", threshold=20, normaliser="threshold",
    indicator="adx_value",
    verifiedLive=["BTC 1h ADX 11.68241454 -> 0.415879273 exact"])
add("htf_trend_adx_trending", "linear_above", threshold=25, normaliser="threshold",
    indicator="htf_adx_value", rung="REGIME_RUNG",
    verifiedLive=["ETH 4h HTF ADX 33.47874556 -> 0.3391498224 exact",
                  "BTC 1h HTF ADX 62.692 -> raw 1.508, engine reports 1 (CLAMP PROOF)"])
add("htf_trend_adx_ranging", "linear_below", threshold=20, normaliser="threshold",
    indicator="htf_adx_value", rung="REGIME_RUNG",
    verifiedLive=["GOOGL 1h HTF ADX 12.88840508 -> 0.355579746 exact"])
add("ltf_trend_adx_trending", "linear_above", threshold=25, normaliser="threshold",
    indicator="ltf_adx_value", rung="LOWER")
add("ltf_trend_adx_ranging", "linear_below", threshold=20, normaliser="threshold",
    indicator="ltf_adx_value", rung="LOWER",
    verifiedLive=["BTC 1h LTF ADX 18.61076256 -> 0.06946187199999994 exact",
                  "ETH 4h LTF ADX 16.96850604 -> 0.15157469799999995 exact"])

# --- FUNDING ----------------------------------------------------------------
add("funding_extreme_positive", "linear_above", threshold=0.0005, normaliser="threshold",
    indicator="funding_rate", examples=[(0.0010, 1.00), (0.0006, 0.20)])
add("funding_extreme_negative", "linear_below", threshold=-0.0005, normaliser="threshold",
    provenance=M, mirror_of="funding_extreme_positive", indicator="funding_rate")
add("funding_rate_flipping", "fixed", constant=0.6,
    indicator="funding_rate, prev_funding_rate")

# --- OPEN_INTEREST ----------------------------------------------------------
add("oi_surge", "linear_above", threshold=0.05, normaliser="threshold",
    reads="(oi - prevOi) / prevOi", indicator="open_interest", note=CLAMP_NOTE)
add("oi_divergence_bull", "unspecified_magnitude", indicator="open_interest vs price")
add("oi_divergence_bear", "unspecified_magnitude", provenance=M,
    mirror_of="oi_divergence_bull", indicator="open_interest vs price")

# --- RELATIVE_STRENGTH ------------------------------------------------------
add("rel_ppo_bull_cross", "unspecified_magnitude", indicator="ppo_histogram")
add("rel_ppo_bear_cross", "unspecified_magnitude", provenance=M,
    mirror_of="rel_ppo_bull_cross", indicator="ppo_histogram")
add("rel_roc_positive", "pct_gap_scaled", divisor=5, reads="roc12_value",
    indicator="roc12_value", note="also requires ROC > prevROC (accelerating)",
    verifiedLive=["BTC 1h ROC 0.00394991 -> 0.000789982 exact"])
add("rel_roc_negative", "pct_gap_scaled", divisor=5, reads="abs(roc12_value)",
    indicator="roc12_value", note="also requires ROC < prevROC (decelerating)",
    verifiedLive=["ETH 4h ROC -0.02140333 -> 0.004280666000000001 exact"])

# --- SUPPORT_RESISTANCE -----------------------------------------------------
add("sr_at_support", "proximity", proximityPct=0.005, indicator="swing_low, price",
    reads="distance = (price - swing_low) / PRICE, not / swing_low",
    examples=[("0.2% away", 0.60), ("0.05% away", 0.90)],
    verifiedLive=["GOOGL 1h swing_low 342.66 price 343.18 -> 0.6969520368319938 exact"])
add("sr_at_resistance", "proximity", proximityPct=0.005, indicator="swing_high, price",
    reads="distance = (swing_high - price) / PRICE, not / swing_high",
    examples=[("0.2% away", 0.60), ("0.05% away", 0.90)],
    verifiedLive=["Dunkirk 0.4435% away -> 0.1130 exact",
                  "GOLD 1h swing_high 4657.5 price 4637.8 -> 0.15045926948122745 exact"])
add("sr_support_break", "break_magnitude", indicator="swing_low, price", note=CLAMP_NOTE)
add("sr_resistance_break", "break_magnitude", provenance=M, mirror_of="sr_support_break")

# --- MFI --------------------------------------------------------------------
add("mfi_oversold", "linear_below", threshold=20, normaliser="threshold",
    indicator="mfi14_value", examples=[(13, 0.35), (5, 0.75)])
add("mfi_overbought", "linear_above", threshold=80, normaliser="100 - threshold",
    provenance=M, mirror_of="mfi_oversold", indicator="mfi14_value")
add("mfi_bull_divergence", "unspecified_magnitude", indicator="mfi14_value vs price")
add("mfi_bear_divergence", "unspecified_magnitude", indicator="mfi14_value vs price")
add("mfi_sustained_bullish", "midline_scaled", midline=50, span=30,
    reads="requires mfi > 50 AND prevMfi > 50", indicator="mfi14_value",
    verifiedLive=["ETH 4h MFI 67.24351706 -> 0.5747839020000001 exact"])
add("mfi_sustained_bearish", "midline_scaled", midline=50, span=30,
    reads="requires mfi < 50 AND prevMfi < 50", indicator="mfi14_value",
    verifiedLive=["BTC 1h MFI 46.10357118 -> 0.12988096066666657 exact"])

# --- COMPARISON -------------------------------------------------------------
add("comparison_sector_divergence", "count_ratio", denominator="peers.length",
    gate="divergentCount >= peers.length * minPeerFraction", minPeerFraction=0.5,
    verifiedLive=["GOLD 1h 2 of 3 peers diverging -> 0.6666666666666666 exact"])
add("comparison_sector_momentum", "count_ratio", denominator="peers.length",
    gate="alignedCount >= peers.length * minPeerFraction", minPeerFraction=0.6,
    verifiedLive=["ETH 4h 3/3 peers -> 1.00", "Dunkirk 3/3 peers -> 1.00"])
add("comparison_btc_decorrelation", "linear_below", threshold=0.3,
    normaliser="2 x threshold", reads="correlationToTarget",
    verifiedLive=["ETH 4h corr 0.00 vs maxCorrelation 0.3 -> 0.5 exact; "
                  "confirms normaliser = 2 x maxCorrelation"],
    note="inactive when the evaluated coin IS BTC, and when comparison data is unavailable")

# --- REGIME -----------------------------------------------------------------
add("regime_trend_shift", "two_state", high=1.0, low=0.5,
    reads="1.0 if the shift is current, 0.5 if one window back",
    verifiedLive=["ETH 4h 'trending_up -> trending_up' -> 0.5"])
add("regime_volatility_shift", "two_state", high=1.0, low=0.5,
    reads="1.0 if the shift is current, 0.5 if one window back",
    verifiedLive=["ETH 4h 'expanding -> normal' -> 1.0"])
add("regime_alignment", "count_ratio", denominator=3, gate="alignedCount >= 2",
    provenance=D, examples=[("3 of 3", 1.00), ("2 of 3", 0.67)],
    observedLive=["Dunkirk -> 0.667 (= 2/3, consistent with the published formula)",
                  "BTC 1h  -> 0.7 for trend=trending_up, mom=bullish, vol=normal",
                  "ETH 4h  -> 0.7 for trend=trending_up, mom=bullish, vol=normal"],
    note=("UNRESOLVED. The definition states 'Score = alignedCount / 3' with examples "
          "3/3 -> 1.00 and 2/3 -> 0.67. No integer count over 3 yields 0.7, yet two "
          "independent previews returned exactly 0.7 for the same regime triple. 0.7 == "
          "2.1/3, which would imply fractional credit for a non-directional volatility "
          "state - but that is a hypothesis fitted to two identical samples, not a "
          "measurement. omega.scoring refuses to compute this one."))
add("regime_divergence", "two_state", high=1.0, low=0.6,
    reads="1.0 when momentum diverges from trend, 0.6 on trend-momentum conflict")

# --- PRICE_STRUCTURE --------------------------------------------------------
add("structure_fvg_approach", "proximity", proximityPct=1.0, indicator="distancePct",
    reads="distancePct is already in PERCENT units; proximityPct 1.0 means 1%",
    examples=[("0.3% away", 0.70), ("0.05% away", 0.95)],
    verifiedLive=["GOLD 1h distancePct 0.5401267842511575 -> "
                  "0.45987321574884255 exact"])
add("structure_ob_approach", "proximity", proximityPct=1.0, indicator="distancePct",
    examples=[("0.3% away", 0.70), ("0.05% away", 0.95)])
add("structure_zone_cluster", "count_ratio", denominator=3, gate="zoneCount >= 2",
    indicator="zoneCount", examples=[("2 zones", 0.67), ("3+ zones", 1.00)],
    verifiedLive=["GOLD 1h zoneCount 3 -> 1.0 exact"])
add("structure_zone_confluence", "two_state", high=1.0, low=0.8,
    reads="1.0 when the overlap is exact (<0.05%), 0.8 when merely aligned",
    indicator="overlapPct",
    verifiedLive=["GOOGL 1h overlapPct 0.0294175328495516 -> 1.0 (below 0.05%)",
                  "GOLD 1h overlapPct 0.0784117640374269 -> 0.8 (above 0.05%)",
                  "the pair brackets the 0.05% boundary from both sides"])

# --- CVD --------------------------------------------------------------------
add("cvd_bullish", "two_state", high=1.0, low=0.5,
    reads="CVD > 0; 1.0 if rising, 0.5 if flat", indicator="cvd_value",
    verifiedLive=["BTC 1h CVD 114.196 positive and rising -> 1.0"])
add("cvd_bearish", "two_state", high=1.0, low=0.5,
    reads="CVD < 0; 1.0 if falling, 0.5 if flat", indicator="cvd_value",
    verifiedLive=["ETH 4h CVD -11775.74 negative but RISING -> 0.5",
                  "Dunkirk CVD -12.57M flat -> 0.5"])
add("cvd_bull_divergence", "unspecified_magnitude", indicator="cvd_value vs price")
add("cvd_bear_divergence", "unspecified_magnitude", indicator="cvd_value vs price")

# --- CONFLUENCE (synthesis) -------------------------------------------------
add("mtf_aligned_bull", "synthesis",
    reads="score = (ltf_score + primary_score + htf_score) / 3",
    gate="all three rung alignment signals fire", indicator="rungs_aligned",
    verifiedLive=["ETH 4h (0.0705425369855601 + 1.0 + 1.0)/3 = 0.6901808456618533 exact"],
    note="consumes each component's exact post-clamp score at full float precision")
add("mtf_aligned_bear", "synthesis",
    reads="score = (ltf_score + primary_score + htf_score) / 3",
    gate="all three rung alignment signals fire", indicator="rungs_aligned")
add("mtf_pullback_long", "synthesis", reads="score = the LTF oversold score",
    gate="HTF bull-alignment AND LTF oversold both fire", indicator="htf_score, ltf_score")
add("mtf_pullback_short", "synthesis", reads="score = the LTF overbought score",
    provenance=M, mirror_of="mtf_pullback_long", indicator="htf_score, ltf_score")

# --- FLOW_DIVERGENCE --------------------------------------------------------
add("flow_perp_spot_bull_divergence", "flow_rate_gap",
    reads="score = rate(spot) - rate(perp); fires when spot leads",
    indicator="spot_cvd_value, prev_spot_cvd_value, perp_cvd_value, prev_perp_cvd_value",
    note="suppressed when the previous sample crosses the daily 00:00-UTC anchor")
add("flow_perp_spot_bear_divergence", "flow_rate_gap",
    reads="score = rate(perp) - rate(spot); fires when perp leads",
    indicator="perp_cvd_value, prev_perp_cvd_value, spot_cvd_value, prev_spot_cvd_value",
    verifiedLive=["BTC 1h -> 0.30359968751644006 exact (perp rate clamped from 1.545 to 1.0)",
                  "ETH 4h -> 0.2392909896129719 exact"],
    note="suppressed when the previous sample crosses the daily 00:00-UTC anchor")


def main() -> None:
    m = json.loads((ROOT / "data" / "derived" / "signal_module_map.json")
                   .read_text(encoding="utf-8"))
    all_signals = sorted({s for v in m["moduleSignals"].values() for s in v})
    missing = [s for s in all_signals if s not in S]
    extra = [s for s in S if s not in all_signals]
    if missing or extra:
        raise SystemExit(f"coverage gap\n  missing: {missing}\n  extra: {extra}")

    entries = {}
    for sid in all_signals:
        family, provenance, mirror_of, params = S[sid]
        entry = {"family": family, "provenance": provenance, **params}
        if mirror_of:
            entry["mirrorOf"] = mirror_of
        entries[sid] = entry

    counts: dict[str, int] = {}
    by_family: dict[str, int] = {}
    for e in entries.values():
        counts[e["provenance"]] = counts.get(e["provenance"], 0) + 1
        by_family[e["family"]] = by_family.get(e["family"], 0) + 1
    bit_exact = sum(1 for e in entries.values()
                    if any("exact" in v for v in e.get("verifiedLive", [])))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "_note": ("How each signal turns an indicator reading into a score. Families are "
                  "generalised from 57 fetched definitions and corrected against bit-exact "
                  "live measurements. Every entry carries provenance."),
        "clamp": (
            "EVERY score is clamped to [0,1] by the engine. The signal DEFINITIONS publish "
            "raw examples that exceed 1.0 (ma_sma200_above '+10% -> 2.0') and those examples "
            "are misleading. Four independent clamp proofs measured live: SMA200 gap +10.23% "
            "raw 2.047 -> 1; SMA200 gap +24.71% raw 4.94 -> 1; ADX 62.69 vs 25 raw 1.508 -> "
            "1; EMA gap 2.660% raw 2.660 -> 1. Trust the clamp, not the published examples."),
        "assetClassAvailability": (
            "The BattleGrid universe spans crypto, equities, indices and commodities. "
            "FLOW_DIVERGENCE is crypto-only: GOOGL and GOLD both returned 'Perp/spot flow "
            "data unavailable', so flow_perp_spot_bull/bear_divergence can never fire off "
            "crypto. FUNDING and OPEN_INTEREST DO evaluate on equities and commodities "
            "(synthetic perp markets - GOOGL carried funding 0.0000044395 and OI 123.1M). "
            "COMPARISON is intermittent everywhere, returning 'Comparison data unavailable' "
            "even when peers are listed in the same payload."),
        "aggregateLink": (
            "These scores feed aggregate = SUM(score x allocation) / SUM(allocation) over "
            "the signals that FIRED - unfired signals enter neither sum. So there is no "
            "structural ceiling; the maximum aggregate is 1.0 for any scorecard. What the "
            "clamp bounds is each signal's pull on the mean. A fired signal raises the "
            "aggregate iff its score exceeds the current aggregate. See docs/12."),
        "families": FAMILIES,
        "coverage": {
            "signals": len(entries),
            "byProvenance": counts,
            "bitExactAgainstLiveData": bit_exact,
            "byFamily": dict(sorted(by_family.items(), key=lambda kv: -kv[1])),
        },
        "signals": entries,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{len(entries)} signals")
    for k, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<22} {n}")
    print(f"  {'bit-exact vs live':<22} {bit_exact}")
    print()
    for fam, n in sorted(by_family.items(), key=lambda kv: -kv[1]):
        print(f"  {fam:<24} {n}")


if __name__ == "__main__":
    main()
