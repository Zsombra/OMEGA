# 01 · The Metric Layer

*Generated from `data/contract/metrics/` — do not hand-edit.*

581 metrics across 14 families. A metric is a **named quantity the platform already
computes**; you never define the maths, you select the quantity and then choose how
to read it. Four fields govern everything you can do with one:

| Field | What it decides |
|---|---|
| `nativeOutput.kind` | which condition operators the compiled column accepts |
| `nativeOutput.unit` | which other metrics it may `spread` against |
| `timeframeMode` | whether it resolves on the candle grid (`candle`) or is a bundle read (`timeless`) |
| `transforms[]` | the *only* transforms the engine can execute for it |

## Price — `price` (27)

> Read the raw traded price, the individual bar’s own open, high, low and close, its price sources (HL2, HLC3, OHLC4), and what the bar did: its candle shape, whether it gapped from the bar before, and how many bars ran one way.

**Common misuses (platform's own words):**

- Treating the perpetual mark as the traded price — they are separate metrics.
- Comparing raw price levels across assets instead of a percentage relation.
- Reading a run length as a gate where a held clause says "N in a row" directly.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `BAR_CONTAINMENT` | `barContain` | classification / inside·outside·none | candle | value |
| `BAR_FORMING` | `bar` | classification / forming·closed | candle | value |
| `CANDLE_DOJI` | `doji` | boolean / true·false | candle | value |
| `CANDLE_ENGULFING` | `engulf` | classification / bullish·bearish·none | candle | value |
| `CANDLE_PIN` | `pin` | classification / lower_wick·upper_wick·none | candle | value |
| `CANDLE_RUN` | `candleRun` | numeric / count [-20–20] | candle | value |
| `CLOSE` | `close` | numeric / price | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `CLOSE_LOCATION` | `closeLoc` | numeric / fraction [0–1] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `CLOSE_RUN` | `closeRun` | numeric / count [-20–20] | candle | value |
| `DAY_OF_WEEK` | `dayOfWeek` | numeric / count [0–6] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |
| `GAP` | `gap` | classification / up·down·none | candle | value |
| `GAP_PCT` | `gapPct` | numeric / percent | candle | value |
| `GAP_RANGE_CLEAR` | `gapClear` | classification / up·down·none | candle | value |
| `HIGH` | `high` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `HL2` | `hl2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `HLC3` | `hlc3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `LAST` | `last` | numeric / price | timeless | value, spread |
| `LOW` | `low` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `MARK` | `mark` | numeric / price | timeless | value, distance, spread |
| `OHLC4` | `ohlc4` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `OPEN` | `open` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `ORACLE` | `oracle` | numeric / price | timeless | value, distance, spread |
| `PAR_DEV` | `parDev` | numeric / percent | candle | value, trajectory, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, classifyZone, cci, ema, rma, rsi, wma, roc |
| `SPOT_CLOSE_BN` | `bnClose` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `SPOT_CLOSE_CB` | `cbClose` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `TRADING_SESSION` | `tradingSession` | classification / asia·london·newYork… | candle | value |
| `UTC_HOUR` | `utcHour` | numeric / count [0–23] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |

## Momentum — `momentum` (30)

> Describe directional impulse, exhaustion, and the pace of price movement.

**Common misuses (platform's own words):**

- Treating an overbought reading as an automatic short.
- Stacking several correlated oscillators as independent evidence.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `CCI20` | `CCI20` | numeric / oscillator | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, classifyZone, cci, ema, rma, rsi, wma, roc |
| `CHG_15M` | `chg15m` | numeric / percent | timeless | value, spread |
| `CHG_1H` | `chg1h` | numeric / percent | timeless | value, spread |
| `CHG_24H` | `chg24h` | numeric / percent | timeless | value, spread |
| `CHG_4H` | `chg4h` | numeric / percent | timeless | value, spread |
| `CHG_5M` | `chg5m` | numeric / percent | timeless | value, spread |
| `CLOSE_CHANGE` | `closeChg` | numeric / percent | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |
| `MACD_HIST` | `MACDhist` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, crossDetect, cci, ema, rma, rsi, wma, roc |
| `MACD_LINE` | `MACDline` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, crossDetect, cci, ema, rma, rsi, wma, roc |
| `MACD_SIGNAL` | `MACDsig` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, crossDetect, cci, ema, rma, rsi, wma, roc |
| `MFI14` | `MFI14` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, classifyZone, cci, ema, rma, rsi, wma, roc |
| `PPO_HIST` | `PPOhist` | numeric / percent | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, crossDetect, cci, ema, rma, rsi, wma, roc |
| `PPO_LINE` | `PPOline` | numeric / percent | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, crossDetect, cci, ema, rma, rsi, wma, roc |
| `PPO_SIGNAL` | `PPOsig` | numeric / percent | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, crossDetect, cci, ema, rma, rsi, wma, roc |
| `QQE_RSI_MA` | `qqeRsi` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `QQE_STOP` | `qqeStop` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `ROC12` | `ROC12` | numeric / percent | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, crossDetect, cci, ema, rma, rsi, wma, roc |
| `ROC15` | `ROC15` | numeric / percent | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, crossDetect, cci, ema, rma, rsi, wma, roc |
| `ROC9` | `ROC9` | numeric / percent | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, crossDetect, cci, ema, rma, rsi, wma, roc |
| `RSI14` | `RSI14` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, classifyZone, cci, ema, rma, rsi, wma, roc |
| `RSI2` | `RSI2` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, classifyZone, cci, ema, rma, rsi, wma, roc |
| `RSI7` | `RSI7` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, classifyZone, cci, ema, rma, rsi, wma, roc |
| `SQZ_MOM` | `sqzMom20` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, crossDetect, cci, ema, rma, rsi, wma, roc |
| `STOCH_D` | `D` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, classifyZone, cci, ema, rma, rsi, wma, roc |
| `STOCH_K` | `K` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, classifyZone, cci, ema, rma, rsi, wma, roc |
| `STOCH_RSI_D` | `stochRsiD` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, classifyZone, cci, ema, rma, rsi, wma, roc |
| `STOCH_RSI_K` | `stochRsiK` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, classifyZone, cci, ema, rma, rsi, wma, roc |
| `WILLR14` | `willR14` | numeric / oscillator [-100–0] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |
| `WT1` | `wt1` | numeric / oscillator | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |
| `WT2` | `wt2` | numeric / oscillator | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |

## Trend — `trend` (26)

> Describe direction, persistence, and price location relative to trend references — the moving averages, and the trailing stops (Supertrend, Parabolic SAR) that follow a trend from behind.

**Common misuses (platform's own words):**

- Assuming a lagging average predicts a reversal.
- Comparing trend levels without matching timeframes.
- Treating a trailing stop as support or resistance it has not been tested at — it moves only with the trend.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `ADX` | `ADX14` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, classifyZone, cci, ema, rma, rsi, wma, roc |
| `DI_MINUS` | `DIminus14` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `DI_PLUS` | `DIplus14` | numeric / oscillator [0–100] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `EMA13` | `EMA13` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `EMA20` | `EMA20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `EMA21` | `EMA21` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `EMA5` | `EMA5` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `EMA50` | `EMA50` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `EMA55` | `EMA55` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `EMA8` | `EMA8` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `EMA9` | `EMA9` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `EMA_CROSS` | `EMA5_13` | event / Bullish·Bearish | candle | value |
| `HMA20` | `HMA20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `ICHI_BASE` | `kijun` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `ICHI_CONV` | `tenkan` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `ICHI_LAG` | `chikou` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `ICHI_SPAN_A` | `senkouA` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `ICHI_SPAN_B` | `senkouB` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `MA_ALIGN` | `MAalign` | classification / bullish·bearish·mixed | candle | value |
| `PSAR` | `PSAR` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `SMA20` | `SMA20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `SMA200` | `SMA200` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `SMA50` | `SMA50` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `ST_DIR` | `stDir` | classification / bullish·bearish | candle | value |
| `ST_LINE` | `stLine` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWMA20` | `VWMA20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |

## Volatility — `volatility` (6)

> Describe the magnitude and expansion or contraction of market movement.

**Common misuses (platform's own words):**

- Reading high volatility as inherently bullish or bearish.
- Using raw price-unit volatility across unlike assets.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `ATR` | `ATR14` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `ATR_PCT` | `atrPct` | numeric / percent | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |
| `BB_WIDTH_PCT` | `bbWidthPct` | numeric / percent | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |
| `HIGH_DEV` | `highDev` | numeric / percent | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |
| `KC_SQUEEZE` | `kcSqueeze` | classification / on·off | candle | value |
| `LOW_DEV` | `lowDev` | numeric / percent | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |

## Bands & Channels — `channels` (14)

> Describe the envelope around price — Bollinger, Keltner and Donchian channels — its edges, and where price sits inside it.

**Common misuses (platform's own words):**

- Treating a touch of the upper band as a sell signal by itself — price walks the band in a trend.
- Comparing a band width across assets in price units rather than as a share of price.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `BB_LOWER` | `bbLower20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `BB_PCT_B` | `pctB20` | numeric / fraction | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |
| `BB_UPPER` | `bbUpper20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `DONCHIAN_BROKEN_HI` | `donchianBrkHi20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `DONCHIAN_BROKEN_HI_PRIOR` | `donchianBrkHiPrior20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `DONCHIAN_BROKEN_LO` | `donchianBrkLo20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `DONCHIAN_BROKEN_LO_PRIOR` | `donchianBrkLoPrior20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `DONCHIAN_LOWER` | `donchianLo20` | numeric / price | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `DONCHIAN_LOWER_PRIOR` | `donchianLoPrior20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `DONCHIAN_UPPER` | `donchianHi20` | numeric / price | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `DONCHIAN_UPPER_PRIOR` | `donchianHiPrior20` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `KC_LOWER` | `kcLower` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `KC_UPPER` | `kcUpper` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `PRICE_ZONE` | `zone` | classification / breakout high·breakdown low·near high… | candle | value |

## Volume & Flow — `volumeFlow` (22)

> Describe participation and the balance of buying and selling pressure.

**Common misuses (platform's own words):**

- Equating high volume with bullish demand.
- Comparing raw volume counts across structurally different markets.
- Comparing raw base-unit volume across assets — that compares denominations, not activity (44,723 BTC beside 2,100,000 DOGE); use the ratio for cohort columns.
- Reading a raw per-bar quantity off the forming bar, whose volume ramps from zero each interval — a closed-bar trajectory is the honest read.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `BUY_PRESSURE` | `buyPres` | numeric / fraction [0–1] | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `BUY_PRES_BN` | `bnBuyPres` | numeric / fraction [0–1] | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `BUY_PRES_CB` | `cbBuyPres` | numeric / fraction [0–1] | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `BUY_QUOTE_VOL` | `buyQuoteVol` | numeric / usdLargeCount [≥0] | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `BUY_TRADES` | `buyTr` | numeric / count [≥0] | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `BUY_VOLUME` | `buyVol` | numeric / largeCount [≥0] | candle | value, trajectory, spread, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |
| `CMF20` | `CMF20` | numeric / oscillator [-1–1] | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, crossDetect, cci, ema, rma, rsi, wma, roc |
| `CUM_VOLUME_DELTA` | `cumVolDelta` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, classifyZone, cci, ema, rma, rsi, wma, roc |
| `CVD` | `CVD` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, classifyZone, cci, ema, rma, rsi, wma, roc |
| `NOTIONAL_VOLUME_1D` | `vol24hUsd` | numeric / usdLargeCount | timeless | value, spread |
| `OBV` | `OBV` | numeric / largeCount | candle | trajectory, efficiency, zscore, stddev, linregSlope, pctl |
| `QUOTE_VOL` | `quoteVol` | numeric / usdLargeCount [≥0] | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `RVOL` | `RVOL20` | numeric / ratio | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |
| `SELL_QUOTE_VOL` | `sellQuoteVol` | numeric / usdLargeCount [≥0] | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `SELL_TRADES` | `sellTr` | numeric / count [≥0] | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `SELL_VOLUME` | `sellVol` | numeric / largeCount [≥0] | candle | value, trajectory, spread, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |
| `SPOT_AVG_TRADE` | `spotAvgTrade` | numeric / largeCount [≥0] | candle | value, trajectory, spread, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |
| `SPOT_CVD` | `spotCVD` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, classifyZone, cci, ema, rma, rsi, wma, roc |
| `SPOT_DOMINANCE` | `spotDom` | numeric / fraction [0–1] | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `TRADES` | `trades` | numeric / count [≥0] | candle | value, trajectory, spread, relativeTo, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, rank, cci, ema, rma, rsi, wma, roc |
| `VOLUME` | `volBase` | numeric / largeCount [≥0] | candle | value, trajectory, spread, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |
| `VOL_SMA20` | `volSMA20` | numeric / largeCount | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |

## Derivatives — `derivatives` (7)

> Describe positioning, leverage demand, and funding pressure in perpetual markets.

**Common misuses (platform's own words):**

- Treating positive funding as an immediate short signal.
- Interpreting open-interest growth without price context.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `FUNDING_ANN` | `ann` | numeric / percent | timeless | value, spread |
| `FUNDING_LABEL` | `rateLbl` | classification / low·moderate·elevated… | timeless | value |
| `FUNDING_RATE` | `rate` | numeric / percent | timeless | value, trajectory, spread, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |
| `OI` | `OI` | numeric / usdLargeCount | timeless | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, rank, cci, ema, rma, rsi, wma, roc |
| `OI_CHG` | `oiChg` | numeric / percent | timeless | value, spread, rank |
| `OI_PX_REGIME` | `oiRegime` | classification / new longs·new shorts·short covering… | timeless | value |
| `OI_VELOCITY` | `oiVel` | classification / accelerating·decelerating·steady | timeless | value |

## VWAP & Profile — `vwapProfile` (81)

> Describe where volume traded — the anchored VWAPs and their standard-deviation bands, the TPO and volume profiles, their value areas and points of control.

**Common misuses (platform's own words):**

- Treating VWAP as a fixed support level when its anchor resets.
- Reading a developing profile’s value area as settled before its session closes.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `MONTH_TPO_POC` | `mTpoPOC` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `MONTH_TPO_VAH` | `mTpoVAH` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `MONTH_TPO_VAL` | `mTpoVAL` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `NAKED_POC_ABOVE` | `nPocAbove` | numeric / price | timeless | value, distance, spread |
| `NAKED_POC_BELOW` | `nPocBelow` | numeric / price | timeless | value, distance, spread |
| `NAKED_SINGLE_PRINT_ABOVE` | `nSpAbove` | numeric / price | timeless | value, distance, spread |
| `NAKED_SINGLE_PRINT_BELOW` | `nSpBelow` | numeric / price | timeless | value, distance, spread |
| `PRIOR_TPO_IB_HIGH` | `pTpoIBH` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_TPO_IB_LOW` | `pTpoIBL` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_TPO_POC` | `pTpoPOC` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_TPO_SHAPE` | `pTpoShape` | classification / p-shape·b-shape·balanced | timeless | value |
| `PRIOR_TPO_VAH` | `pTpoVAH` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_TPO_VAL` | `pTpoVAL` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_TPO_VPOC` | `pTpoVPOC` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_TPO_VVAH` | `pTpoVVAH` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_TPO_VVAL` | `pTpoVVAL` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `TPO_IB_HIGH` | `tpoIBH` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `TPO_IB_LOW` | `tpoIBL` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `TPO_POC` | `tpoPOC` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `TPO_SHAPE` | `tpoShape` | classification / p-shape·b-shape·balanced | timeless | value |
| `TPO_SINGLE_PRINT_ABOVE` | `tpoSpAbove` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `TPO_SINGLE_PRINT_BELOW` | `tpoSpBelow` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `TPO_VAH` | `tpoVAH` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `TPO_VAL` | `tpoVAL` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `TPO_VPOC` | `tpoVPOC` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `TPO_VVAH` | `tpoVVAH` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `TPO_VVAL` | `tpoVVAL` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `VWAP` | `VWAP` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_LB1` | `vwapLb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_LB2` | `vwapLb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_LB3` | `vwapLb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_MONTH` | `vwapM` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_MONTH_LB1` | `vwapMLb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_MONTH_LB2` | `vwapMLb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_MONTH_LB3` | `vwapMLb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_MONTH_UB1` | `vwapMUb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_MONTH_UB2` | `vwapMUb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_MONTH_UB3` | `vwapMUb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_1H` | `rvwap1h` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_1H_LB1` | `rvwap1hLb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_1H_LB2` | `rvwap1hLb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_1H_LB3` | `rvwap1hLb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_1H_UB1` | `rvwap1hUb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_1H_UB2` | `rvwap1hUb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_1H_UB3` | `rvwap1hUb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_24H` | `rvwap24h` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_24H_LB1` | `rvwap24hLb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_24H_LB2` | `rvwap24hLb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_24H_LB3` | `rvwap24hLb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_24H_UB1` | `rvwap24hUb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_24H_UB2` | `rvwap24hUb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_24H_UB3` | `rvwap24hUb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_4H` | `rvwap4h` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_4H_LB1` | `rvwap4hLb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_4H_LB2` | `rvwap4hLb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_4H_LB3` | `rvwap4hLb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_4H_UB1` | `rvwap4hUb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_4H_UB2` | `rvwap4hUb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_ROLLING_4H_UB3` | `rvwap4hUb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_SWING_HIGH` | `avwapSwHi` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_SWING_LOW` | `avwapSwLo` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_TRADING_SESSION` | `vwapTs` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_TRADING_SESSION_LB1` | `vwapTsLb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_TRADING_SESSION_LB2` | `vwapTsLb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_TRADING_SESSION_LB3` | `vwapTsLb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_TRADING_SESSION_UB1` | `vwapTsUb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_TRADING_SESSION_UB2` | `vwapTsUb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_TRADING_SESSION_UB3` | `vwapTsUb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_UB1` | `vwapUb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_UB2` | `vwapUb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_UB3` | `vwapUb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_WEEK` | `vwapW` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_WEEK_LB1` | `vwapWLb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_WEEK_LB2` | `vwapWLb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_WEEK_LB3` | `vwapWLb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_WEEK_UB1` | `vwapWUb1` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_WEEK_UB2` | `vwapWUb2` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `VWAP_WEEK_UB3` | `vwapWUb3` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `WEEK_TPO_POC` | `wTpoPOC` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `WEEK_TPO_VAH` | `wTpoVAH` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `WEEK_TPO_VAL` | `wTpoVAL` | numeric / price | timeless | value, distance, spread, levelInteraction |

## Sessions & Levels — `levels` (274)

> Describe the fixed prices a period or a session left behind — the trading sessions’ highs, lows and opens, the opening ranges, the initial-balance extensions, the prior day’s, week’s and month’s highs and lows, and the floor pivots.

**Common misuses (platform's own words):**

- Treating every pivot as equally strong.
- Reading a session’s high before the session has closed as its final high.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `ASIA_HIGH` | `asiaHi` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `ASIA_LOW` | `asiaLo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `ASIA_OPEN` | `asiaOpen` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `IB_EXT_DOWN_150` | `ibExtDown150` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `IB_EXT_DOWN_200` | `ibExtDown200` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `IB_EXT_UP_150` | `ibExtUp150` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `IB_EXT_UP_200` | `ibExtUp200` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `LONDON_HIGH` | `londonHi` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `LONDON_LOW` | `londonLo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `LONDON_OPEN` | `londonOpen` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `NEW_YORK_HIGH` | `nyHi` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `NEW_YORK_LOW` | `nyLo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `NEW_YORK_OPEN` | `nyOpen` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `OR15_HIGH` | `or15Hi` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `OR15_LOW` | `or15Lo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `OR30_HIGH` | `or30Hi` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `OR30_LOW` | `or30Lo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PDH` | `pdh` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PDL` | `pdl` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PDO` | `pdo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CAM_R1` | `pivotCamR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CAM_R2` | `pivotCamR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CAM_R3` | `pivotCamR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CAM_R4` | `pivotCamR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CAM_R5` | `pivotCamR5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CAM_S1` | `pivotCamS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CAM_S2` | `pivotCamS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CAM_S3` | `pivotCamS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CAM_S4` | `pivotCamS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CAM_S5` | `pivotCamS5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CLASSIC_R3` | `pivotClassicR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CLASSIC_R4` | `pivotClassicR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CLASSIC_S3` | `pivotClassicS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_CLASSIC_S4` | `pivotClassicS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_DM_P` | `pivotDmP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_DM_R1` | `pivotDmR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_DM_S1` | `pivotDmS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_FIB_R1` | `pivotFibR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_FIB_R2` | `pivotFibR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_FIB_S1` | `pivotFibS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_FIB_S2` | `pivotFibS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CAM_R1` | `pivotMonthCamR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CAM_R2` | `pivotMonthCamR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CAM_R3` | `pivotMonthCamR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CAM_R4` | `pivotMonthCamR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CAM_R5` | `pivotMonthCamR5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CAM_S1` | `pivotMonthCamS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CAM_S2` | `pivotMonthCamS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CAM_S3` | `pivotMonthCamS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CAM_S4` | `pivotMonthCamS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CAM_S5` | `pivotMonthCamS5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CLASSIC_R3` | `pivotMonthClassicR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CLASSIC_R4` | `pivotMonthClassicR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CLASSIC_S3` | `pivotMonthClassicS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_CLASSIC_S4` | `pivotMonthClassicS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_DM_P` | `pivotMonthDmP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_DM_R1` | `pivotMonthDmR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_DM_S1` | `pivotMonthDmS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_FIB_R1` | `pivotMonthFibR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_FIB_R2` | `pivotMonthFibR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_FIB_S1` | `pivotMonthFibS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_FIB_S2` | `pivotMonthFibS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_P` | `pivotMonthP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_R1` | `pivotMonthR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_R2` | `pivotMonthR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_R3` | `pivotMonthR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_R4` | `pivotMonthR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_R5` | `pivotMonthR5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_S1` | `pivotMonthS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_S2` | `pivotMonthS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_S3` | `pivotMonthS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_S4` | `pivotMonthS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_S5` | `pivotMonthS5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_WOODIE_P` | `pivotMonthWoodieP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_WOODIE_R1` | `pivotMonthWoodieR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_WOODIE_R2` | `pivotMonthWoodieR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_WOODIE_R3` | `pivotMonthWoodieR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_WOODIE_R4` | `pivotMonthWoodieR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_WOODIE_S1` | `pivotMonthWoodieS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_WOODIE_S2` | `pivotMonthWoodieS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_WOODIE_S3` | `pivotMonthWoodieS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_MONTH_WOODIE_S4` | `pivotMonthWoodieS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_P` | `pivotP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CAM_R1` | `pivotQuarterCamR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CAM_R2` | `pivotQuarterCamR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CAM_R3` | `pivotQuarterCamR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CAM_R4` | `pivotQuarterCamR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CAM_R5` | `pivotQuarterCamR5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CAM_S1` | `pivotQuarterCamS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CAM_S2` | `pivotQuarterCamS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CAM_S3` | `pivotQuarterCamS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CAM_S4` | `pivotQuarterCamS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CAM_S5` | `pivotQuarterCamS5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CLASSIC_R3` | `pivotQuarterClassicR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CLASSIC_R4` | `pivotQuarterClassicR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CLASSIC_S3` | `pivotQuarterClassicS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_CLASSIC_S4` | `pivotQuarterClassicS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_DM_P` | `pivotQuarterDmP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_DM_R1` | `pivotQuarterDmR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_DM_S1` | `pivotQuarterDmS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_FIB_R1` | `pivotQuarterFibR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_FIB_R2` | `pivotQuarterFibR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_FIB_S1` | `pivotQuarterFibS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_FIB_S2` | `pivotQuarterFibS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_P` | `pivotQuarterP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_R1` | `pivotQuarterR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_R2` | `pivotQuarterR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_R3` | `pivotQuarterR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_R4` | `pivotQuarterR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_R5` | `pivotQuarterR5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_S1` | `pivotQuarterS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_S2` | `pivotQuarterS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_S3` | `pivotQuarterS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_S4` | `pivotQuarterS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_S5` | `pivotQuarterS5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_WOODIE_P` | `pivotQuarterWoodieP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_WOODIE_R1` | `pivotQuarterWoodieR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_WOODIE_R2` | `pivotQuarterWoodieR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_WOODIE_R3` | `pivotQuarterWoodieR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_WOODIE_R4` | `pivotQuarterWoodieR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_WOODIE_S1` | `pivotQuarterWoodieS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_WOODIE_S2` | `pivotQuarterWoodieS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_WOODIE_S3` | `pivotQuarterWoodieS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_QUARTER_WOODIE_S4` | `pivotQuarterWoodieS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_R1` | `pivotR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_R2` | `pivotR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_R3` | `pivotR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_R4` | `pivotR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_R5` | `pivotR5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_S1` | `pivotS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_S2` | `pivotS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_S3` | `pivotS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_S4` | `pivotS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_S5` | `pivotS5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CAM_R1` | `pivotWeekCamR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CAM_R2` | `pivotWeekCamR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CAM_R3` | `pivotWeekCamR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CAM_R4` | `pivotWeekCamR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CAM_R5` | `pivotWeekCamR5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CAM_S1` | `pivotWeekCamS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CAM_S2` | `pivotWeekCamS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CAM_S3` | `pivotWeekCamS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CAM_S4` | `pivotWeekCamS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CAM_S5` | `pivotWeekCamS5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CLASSIC_R3` | `pivotWeekClassicR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CLASSIC_R4` | `pivotWeekClassicR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CLASSIC_S3` | `pivotWeekClassicS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_CLASSIC_S4` | `pivotWeekClassicS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_DM_P` | `pivotWeekDmP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_DM_R1` | `pivotWeekDmR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_DM_S1` | `pivotWeekDmS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_FIB_R1` | `pivotWeekFibR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_FIB_R2` | `pivotWeekFibR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_FIB_S1` | `pivotWeekFibS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_FIB_S2` | `pivotWeekFibS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_P` | `pivotWeekP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_R1` | `pivotWeekR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_R2` | `pivotWeekR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_R3` | `pivotWeekR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_R4` | `pivotWeekR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_R5` | `pivotWeekR5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_S1` | `pivotWeekS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_S2` | `pivotWeekS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_S3` | `pivotWeekS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_S4` | `pivotWeekS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_S5` | `pivotWeekS5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_WOODIE_P` | `pivotWeekWoodieP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_WOODIE_R1` | `pivotWeekWoodieR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_WOODIE_R2` | `pivotWeekWoodieR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_WOODIE_R3` | `pivotWeekWoodieR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_WOODIE_R4` | `pivotWeekWoodieR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_WOODIE_S1` | `pivotWeekWoodieS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_WOODIE_S2` | `pivotWeekWoodieS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_WOODIE_S3` | `pivotWeekWoodieS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WEEK_WOODIE_S4` | `pivotWeekWoodieS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WOODIE_P` | `pivotWoodieP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WOODIE_R1` | `pivotWoodieR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WOODIE_R2` | `pivotWoodieR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WOODIE_R3` | `pivotWoodieR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WOODIE_R4` | `pivotWoodieR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WOODIE_S1` | `pivotWoodieS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WOODIE_S2` | `pivotWoodieS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WOODIE_S3` | `pivotWoodieS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_WOODIE_S4` | `pivotWoodieS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CAM_R1` | `pivotYearCamR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CAM_R2` | `pivotYearCamR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CAM_R3` | `pivotYearCamR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CAM_R4` | `pivotYearCamR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CAM_R5` | `pivotYearCamR5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CAM_S1` | `pivotYearCamS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CAM_S2` | `pivotYearCamS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CAM_S3` | `pivotYearCamS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CAM_S4` | `pivotYearCamS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CAM_S5` | `pivotYearCamS5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CLASSIC_R3` | `pivotYearClassicR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CLASSIC_R4` | `pivotYearClassicR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CLASSIC_S3` | `pivotYearClassicS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_CLASSIC_S4` | `pivotYearClassicS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_DM_P` | `pivotYearDmP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_DM_R1` | `pivotYearDmR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_DM_S1` | `pivotYearDmS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_FIB_R1` | `pivotYearFibR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_FIB_R2` | `pivotYearFibR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_FIB_S1` | `pivotYearFibS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_FIB_S2` | `pivotYearFibS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_P` | `pivotYearP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_R1` | `pivotYearR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_R2` | `pivotYearR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_R3` | `pivotYearR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_R4` | `pivotYearR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_R5` | `pivotYearR5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_S1` | `pivotYearS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_S2` | `pivotYearS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_S3` | `pivotYearS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_S4` | `pivotYearS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_S5` | `pivotYearS5` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_WOODIE_P` | `pivotYearWoodieP` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_WOODIE_R1` | `pivotYearWoodieR1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_WOODIE_R2` | `pivotYearWoodieR2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_WOODIE_R3` | `pivotYearWoodieR3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_WOODIE_R4` | `pivotYearWoodieR4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_WOODIE_S1` | `pivotYearWoodieS1` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_WOODIE_S2` | `pivotYearWoodieS2` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_WOODIE_S3` | `pivotYearWoodieS3` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PIVOT_YEAR_WOODIE_S4` | `pivotYearWoodieS4` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PMH` | `pmh` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PML` | `pml` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_ASIA_DEMAND_AVG` | `pAsiaDemAvg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_ASIA_DEMAND_EDGE` | `pAsiaDemEdge` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_ASIA_DEMAND_WAVG` | `pAsiaDemWavg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_ASIA_HIGH` | `pAsiaHi` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_ASIA_HIGH_SWEPT` | `pAsiaHiSwept` | classification / swept·intact | timeless | value |
| `PRIOR_ASIA_LOW` | `pAsiaLo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_ASIA_LOW_SWEPT` | `pAsiaLoSwept` | classification / swept·intact | timeless | value |
| `PRIOR_ASIA_OPEN` | `pAsiaOpen` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_ASIA_SUPPLY_AVG` | `pAsiaSupAvg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_ASIA_SUPPLY_EDGE` | `pAsiaSupEdge` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_ASIA_SUPPLY_WAVG` | `pAsiaSupWavg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_DAY_DEMAND_AVG` | `pdDemAvg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_DAY_DEMAND_EDGE` | `pdDemEdge` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_DAY_DEMAND_WAVG` | `pdDemWavg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_DAY_SUPPLY_AVG` | `pdSupAvg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_DAY_SUPPLY_EDGE` | `pdSupEdge` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_DAY_SUPPLY_WAVG` | `pdSupWavg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_LONDON_DEMAND_AVG` | `pLondonDemAvg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_LONDON_DEMAND_EDGE` | `pLondonDemEdge` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_LONDON_DEMAND_WAVG` | `pLondonDemWavg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_LONDON_HIGH` | `pLondonHi` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_LONDON_HIGH_SWEPT` | `pLondonHiSwept` | classification / swept·intact | timeless | value |
| `PRIOR_LONDON_LOW` | `pLondonLo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_LONDON_LOW_SWEPT` | `pLondonLoSwept` | classification / swept·intact | timeless | value |
| `PRIOR_LONDON_OPEN` | `pLondonOpen` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_LONDON_SUPPLY_AVG` | `pLondonSupAvg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_LONDON_SUPPLY_EDGE` | `pLondonSupEdge` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_LONDON_SUPPLY_WAVG` | `pLondonSupWavg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_MONTH_TPO_POC` | `pmTpoPOC` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_MONTH_TPO_VAH` | `pmTpoVAH` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_MONTH_TPO_VAL` | `pmTpoVAL` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_NEW_YORK_DEMAND_AVG` | `pNyDemAvg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_NEW_YORK_DEMAND_EDGE` | `pNyDemEdge` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_NEW_YORK_DEMAND_WAVG` | `pNyDemWavg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_NEW_YORK_HIGH` | `pNyHi` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_NEW_YORK_HIGH_SWEPT` | `pNyHiSwept` | classification / swept·intact | timeless | value |
| `PRIOR_NEW_YORK_LOW` | `pNyLo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_NEW_YORK_LOW_SWEPT` | `pNyLoSwept` | classification / swept·intact | timeless | value |
| `PRIOR_NEW_YORK_OPEN` | `pNyOpen` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_NEW_YORK_SUPPLY_AVG` | `pNySupAvg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_NEW_YORK_SUPPLY_EDGE` | `pNySupEdge` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_NEW_YORK_SUPPLY_WAVG` | `pNySupWavg` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_WEEK_TPO_POC` | `pwTpoPOC` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_WEEK_TPO_VAH` | `pwTpoVAH` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PRIOR_WEEK_TPO_VAL` | `pwTpoVAL` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PWH` | `pwh` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `PWL` | `pwl` | numeric / price | timeless | value, distance, spread, levelInteraction |

## Market Structure — `structure` (38)

> Describe the swings price has made, the structure breaks between them, and the active support and resistance zones.

**Common misuses (platform's own words):**

- Treating every swing as an equally strong level.
- Reading a zone column as the decision timeframe’s levels when its timeframe reference names another rung — a zone column reads zones on its own resolved timeframe.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `EQH` | `eqh` | boolean / true·false | candle | value |
| `EQH_LEVEL` | `eqhLvl` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `EQL` | `eql` | boolean / true·false | candle | value |
| `EQL_LEVEL` | `eqlLvl` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `INTERNAL_PENDING_HIGH` | `iStructHi` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `INTERNAL_PENDING_LOW` | `iStructLo` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `INTERNAL_STRUCTURE_EVENT` | `iStructEvt` | event / BOS↑·BOS↓·CHoCH↑… | candle | value |
| `INTERNAL_STRUCTURE_LEVEL` | `iStructLvl` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `INTERNAL_STRUCTURE_TREND` | `iStructTrend` | classification / bullish·bearish | candle | value |
| `LIQUIDITY_POOL_ABOVE` | `poolAbove` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `LIQUIDITY_POOL_ABOVE_INTACT` | `poolAboveOk` | boolean / true·false | candle | value |
| `LIQUIDITY_POOL_ABOVE_RECLAIMED` | `poolAboveRecl` | boolean / true·false | candle | value |
| `LIQUIDITY_POOL_ABOVE_RETIRED` | `poolAboveRetired` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `LIQUIDITY_POOL_ABOVE_TOUCHES` | `poolAboveTouch` | numeric / count | candle | value, trajectory, spread, efficiency |
| `LIQUIDITY_POOL_BELOW` | `poolBelow` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `LIQUIDITY_POOL_BELOW_INTACT` | `poolBelowOk` | boolean / true·false | candle | value |
| `LIQUIDITY_POOL_BELOW_RECLAIMED` | `poolBelowRecl` | boolean / true·false | candle | value |
| `LIQUIDITY_POOL_BELOW_RETIRED` | `poolBelowRetired` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `LIQUIDITY_POOL_BELOW_TOUCHES` | `poolBelowTouch` | numeric / count | candle | value, trajectory, spread, efficiency |
| `PRIOR_SWING_FRACTAL_HIGH` | `pFractalHi` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `PRIOR_SWING_FRACTAL_LOW` | `pFractalLo` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `STRUCT_ZONES` | `zones` | entitySet /  | candle | count, nearestZoneType, nearestZoneRange, nearestZoneDist, nearestZoneAge |
| `SWING_FRACTAL_HIGH` | `fractalHi` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `SWING_FRACTAL_HIGH_BARS_AGO` | `fractalHiAgo` | numeric / count | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `SWING_FRACTAL_LABEL` | `fractalLabel` | classification / HH·HL·LH… | candle | value |
| `SWING_FRACTAL_LOW` | `fractalLo` | numeric / price | candle | value, trajectory, distance, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, levelInteraction, cci, ema, rma, rsi, wma, roc |
| `SWING_FRACTAL_LOW_BARS_AGO` | `fractalLoAgo` | numeric / count | candle | value, trajectory, spread, relativeTo, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `SWING_PENDING_HIGH` | `structHi` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `SWING_PENDING_LOW` | `structLo` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `SWING_STRUCTURE_EVENT` | `structEvt` | event / BOS↑·BOS↓·CHoCH↑… | candle | value |
| `SWING_STRUCTURE_LEVEL` | `structLvl` | numeric / price | candle | value, trajectory, distance, spread, efficiency, levelInteraction |
| `SWING_STRUCTURE_TREND` | `structTrend` | classification / bullish·bearish | candle | value |
| `ZONE_RESIST_HIGH` | `zoneResHi` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `ZONE_RESIST_LOW` | `zoneResLo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `ZONE_RESIST_MID` | `zoneResMid` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `ZONE_SUPPORT_HIGH` | `zoneSupHi` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `ZONE_SUPPORT_LOW` | `zoneSupLo` | numeric / price | timeless | value, distance, spread, levelInteraction |
| `ZONE_SUPPORT_MID` | `zoneSupMid` | numeric / price | timeless | value, distance, spread, levelInteraction |

## Regime — `regime` (18)

> Describe the platform-classified trend, volatility, and momentum environment, the composite regime it resolves to, and the quantities the classifier read to decide.

**Common misuses (platform's own words):**

- Treating a regime label as a guaranteed trade direction.
- Reconstructing regime labels from unrelated client heuristics.
- Reading conviction as how comfortably the regime matched. It encodes WHICH rule in the priority ladder matched — the margins carry comfort.
- Treating a trend direction as confirmed without checking whether it came from the decisive DI spread or from the fallback that fires when the spread is indecisive.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `REGIME_CONVICTION` | `regConv` | classification / maximum·high·medium… | timeless | value |
| `REGIME_CRASH_LATCH` | `regLatch` | classification / armed·clear | timeless | value |
| `REGIME_CRASH_MARGIN` | `regCrash` | numeric / oscillator | timeless | value, spread |
| `REGIME_DI_SPREAD` | `regDI` | numeric / points [-100–100] | timeless | value |
| `REGIME_MOM` | `regMom` | classification / bullish·bearish·neutral… | timeless | value, trajectory |
| `REGIME_MOM_BEAR_VOTES` | `regBear` | numeric / count | timeless | value, spread |
| `REGIME_MOM_BULL_VOTES` | `regBull` | numeric / count | timeless | value, spread |
| `REGIME_RUN_BARS` | `regBars` | numeric / count | timeless | value, spread |
| `REGIME_STATE` | `regState` | classification / bull trend·bear trend·bull range… | timeless | value |
| `REGIME_TREND` | `regTrend` | classification / trending up·trending down·ranging | timeless | value, trajectory |
| `REGIME_TREND_GATE` | `regGate` | classification / cleared·held·dropped | timeless | value |
| `REGIME_TREND_MARGIN` | `regMargin` | numeric / oscillator [0–100] | timeless | value, spread |
| `REGIME_TREND_SOURCE` | `regSrc` | classification / di spread·ema fallback | timeless | value |
| `REGIME_VOL` | `regVol` | classification / expanding·contracting·normal | timeless | value, trajectory |
| `REGIME_VOL_ATR_RATIO` | `regAtrR` | numeric / ratio | timeless | value, spread |
| `REGIME_VOL_BBW_RATIO` | `regBbwR` | numeric / ratio | timeless | value, spread |
| `REGIME_WARNING_CRASH` | `regWCrash` | classification / raised·clear | timeless | value |
| `REGIME_WARNING_DIVERGENCE` | `regWDiv` | classification / raised·clear | timeless | value |

## Crowd — `crowd` (17)

> Describe aggregate player positioning, confidence, and historical accuracy.

**Common misuses (platform's own words):**

- Assuming consensus is always correct.
- Using crowd values as candle-timeframe indicators.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `CROWD_ACC` | `crowdAcc` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_ACC_EDGE_Z` | `accEdgeZ` | numeric / oscillator | timeless | value, rank |
| `CROWD_ACC_EDGE_Z_LIVE` | `accEdgeZLive` | numeric / oscillator | timeless | value, rank |
| `CROWD_ACC_LIVE` | `crowdAccLive` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_CAPT` | `captRate` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_CAPT_EXCESS_Z` | `captExcessZ` | numeric / oscillator | timeless | value, rank |
| `CROWD_CAPT_EXCESS_Z_LIVE` | `captExcessZLive` | numeric / oscillator | timeless | value, rank |
| `CROWD_CAPT_LIVE` | `captRateLive` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_PICK` | `pick` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_PICK_LIVE` | `pickLive` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_UPBIAS` | `upBias` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_UPBIAS_LIVE` | `upBiasLive` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_UP_EXCESS_Z` | `upExcessZ` | numeric / oscillator | timeless | value, rank |
| `CROWD_UP_EXCESS_Z_LIVE` | `upExcessZLive` | numeric / oscillator | timeless | value, rank |
| `CROWD_UP_LEAN_Z` | `upLeanZ` | numeric / oscillator | timeless | value, rank |
| `CROWD_UP_LEAN_Z_LIVE` | `upLeanZLive` | numeric / oscillator | timeless | value, rank |
| `SETTLED_AT` | `settledAt` | date /  | timeless | value |

## Derived — `derived` (8)

> Describe platform-owned cross-family classifications and convergence facts.

**Common misuses (platform's own words):**

- Recomputing the classification with client-local rules.
- Treating a summary label as proof that every input agrees.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `CAPTAIN_CONF` | `captainConf` | boolean / true·false | timeless | value |
| `CONFIDENCE` | `conf` | classification / high·moderate·low | timeless | value |
| `FLOW_ALIGN` | `flowAlign` | classification / aligned bullish·aligned bearish·divergent… | timeless | value |
| `PERP_SPOT_CONFIRMS` | `perpSpotConf` | boolean / true·false | timeless | value |
| `PERP_SPOT_FLOW` | `perpSpotFlow` | classification / confirmed_bull·confirmed_bear·perp_led_fragile… | timeless | value |
| `PERP_SPOT_GAP` | `perpSpotGap` | numeric / oscillator [0–2] | timeless | value, rank |
| `PERP_SPOT_STRENGTH` | `perpSpotStr` | classification / high·moderate·low | timeless | value |
| `SMART_RETAIL` | `smartRetail` | classification / hidden accumulation·hidden distribution·confirmed | timeless | value |

## Market — `market` (13)

> Read the whole field at one breadth scope — how much of it closed up or down, carries momentum, participates, is extended, and trades above its own trend — on a section bound to the market at that scope.

**Common misuses (platform's own words):**

- Treating one bar’s net breadth as a regime — it carries almost no persistence.
- Adding a market metric to a coin section — the market is its own subject, bound in the section dialog.
- Expecting history before the breadth history began: a lookback before it reads absent.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `MKT_ABOVE_EMA` | `mktAboveEma` | numeric / percent [0–100] | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, classifyZone, cci, ema, rma, rsi, wma, roc |
| `MKT_AVG_CHG` | `mktAvgChg` | numeric / percent | candle | value, trajectory, spread, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `MKT_AVG_PPO` | `mktAvgPpo` | numeric / percent | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `MKT_DISPERSION` | `mktDispersion` | numeric / percent | candle | value, trajectory, spread, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `MKT_DOWN` | `mktDown` | numeric / percent [0–100] | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |
| `MKT_NET` | `mktBreadth` | numeric / percent [-100–100] | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `MKT_PPO_DOWN` | `mktPpoDown` | numeric / percent [0–100] | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |
| `MKT_PPO_NET` | `mktPpoNet` | numeric / percent [-100–100] | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `MKT_PPO_UP` | `mktPpoUp` | numeric / percent [0–100] | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |
| `MKT_STRETCH` | `mktStretch` | numeric / oscillator [0–100] | candle | value, trajectory, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |
| `MKT_UNIVERSE` | `mktUniverse` | numeric / count | candle | value, trajectory, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
| `MKT_UP` | `mktUp` | numeric / percent [0–100] | candle | value, trajectory, spread, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, maxShare, cci, ema, rma, rsi, wma, roc |
| `MKT_VOL_NET` | `mktVolNet` | numeric / ratio | candle | value, trajectory, efficiency, aggregate, zscore, stddev, linregSlope, pctl, rollingMin, rollingMax, cci, ema, rma, rsi, wma, roc |
