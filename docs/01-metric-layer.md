# 01 · The Metric Layer

*Generated from `data/contract/metrics/` — do not hand-edit.*

86 metrics across 10 families. A metric is a **named quantity the platform already
computes**; you never define the maths, you select the quantity and then choose how
to read it. Four fields govern everything you can do with one:

| Field | What it decides |
|---|---|
| `nativeOutput.kind` | which condition operators the compiled column accepts |
| `nativeOutput.unit` | which other metrics it may `spread` against |
| `timeframeMode` | whether it resolves on the candle grid (`candle`) or is a bundle read (`timeless`) |
| `transforms[]` | the *only* transforms the engine can execute for it |

## Price — `price` (10)

> Read the raw traded price and the individual bar’s own open, high, low, and close.

**Common misuses (platform's own words):**

- Treating the perpetual mark as the traded price — they are separate metrics.
- Comparing raw price levels across assets instead of a percentage relation.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `BAR_FORMING` | `bar` | classification / forming·closed | candle | value |
| `CLOSE` | `close` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `HIGH` | `high` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `LAST` | `last` | numeric / price | timeless | value, distance, spread |
| `LOW` | `low` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `MARK` | `mark` | numeric / price | timeless | value, distance, spread |
| `OPEN` | `open` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `ORACLE` | `oracle` | numeric / price | timeless | value, distance, spread |
| `SPOT_CLOSE_BN` | `bnClose` | numeric / price | timeless | value, distance, spread |
| `SPOT_CLOSE_CB` | `cbClose` | numeric / price | timeless | value, distance, spread |

## Momentum — `momentum` (15)

> Describe directional impulse, exhaustion, and the pace of price movement.

**Common misuses (platform's own words):**

- Treating an overbought reading as an automatic short.
- Stacking several correlated oscillators as independent evidence.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `CCI20` | `CCI` | numeric / oscillator | candle | value, trajectory, spread, efficiency, rank |
| `CHG_15M` | `chg15m` | numeric / percent | timeless | value, spread |
| `CHG_1H` | `chg1h` | numeric / percent | timeless | value, spread |
| `CHG_24H` | `chg24h` | numeric / percent | timeless | value, spread |
| `CHG_4H` | `chg4h` | numeric / percent | timeless | value, spread |
| `CHG_5M` | `chg5m` | numeric / percent | timeless | value, spread |
| `CLOSE_CHANGE` | `closeChg` | numeric / percent | candle | value, trajectory, spread, efficiency, rank |
| `MACD` | `MACD` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, crossDetect |
| `MFI14` | `MFI14` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, maxShare, rank, classifyZone |
| `PPO` | `PPO` | numeric / percent | candle | value, trajectory, spread, efficiency, rank |
| `ROC12` | `ROC` | numeric / percent | candle | value, trajectory, spread, efficiency, rank, crossDetect |
| `RSI14` | `RSI14` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, maxShare, rank, classifyZone |
| `RSI7` | `RSI7` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, maxShare, rank, classifyZone |
| `STOCH_D` | `D` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, maxShare, rank |
| `STOCH_K` | `K` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, maxShare, rank, classifyZone |

## Trend — `trend` (9)

> Describe direction, persistence, and price location relative to trend references.

**Common misuses (platform's own words):**

- Assuming a lagging average predicts a reversal.
- Comparing trend levels without matching timeframes.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `ADX` | `ADX` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, maxShare, rank, classifyZone |
| `EMA13` | `EMA13` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `EMA20` | `EMA20` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `EMA5` | `EMA5` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `EMA_CROSS` | `EMA5_13` | event / Bullish·Bearish | candle | value |
| `MA_ALIGN` | `MAalign` | classification / bullish·bearish·mixed | candle | value |
| `SMA20` | `SMA20` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `SMA200` | `SMA200` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `SMA50` | `SMA50` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |

## Volatility — `volatility` (6)

> Describe the magnitude and expansion or contraction of market movement.

**Common misuses (platform's own words):**

- Reading high volatility as inherently bullish or bearish.
- Using raw price-unit volatility across unlike assets.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `ATR` | `ATR` | numeric / signedPrice | candle | value, trajectory, spread, efficiency |
| `ATR_PCT` | `atrPct` | numeric / percent | candle | value, trajectory, spread, efficiency, rank |
| `BB_WIDTH` | `BBwidth` | numeric / signedPrice | candle | value, trajectory, spread, efficiency |
| `BB_WIDTH_PCT` | `bbWidthPct` | numeric / percent | candle | value, trajectory, spread, efficiency, rank |
| `HIGH_DEV` | `highDev` | numeric / percent | timeless | value, spread, rank |
| `LOW_DEV` | `lowDev` | numeric / percent | timeless | value, spread, rank |

## Volume & Flow — `volumeFlow` (13)

> Describe participation and the balance of buying and selling pressure.

**Common misuses (platform's own words):**

- Equating high volume with bullish demand.
- Comparing raw volume counts across structurally different markets.
- Comparing raw base-unit volume across assets — that compares denominations, not activity (44,723 BTC beside 2,100,000 DOGE); use the ratio for cohort columns.
- Reading a raw per-bar quantity off the forming bar, whose volume ramps from zero each interval — a closed-bar trajectory is the honest read.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `BUY_PRESSURE` | `buyPres` | numeric / fraction [0–1] | candle | value, trajectory, spread, efficiency, maxShare, rank |
| `BUY_TRADES` | `buyTr` | numeric / count [≥0] | candle | value, trajectory, spread, efficiency, maxShare, rank |
| `BUY_VOLUME` | `buyVol` | numeric / largeCount [≥0] | candle | value, trajectory, spread, efficiency, maxShare |
| `CVD` | `CVD` | numeric / signedPrice | candle | value, trajectory, spread, efficiency |
| `NOTIONAL_VOLUME_1D` | `vol24hUsd` | numeric / usdLargeCount | timeless | value, spread |
| `OBV` | `OBV` | numeric / largeCount | candle | value, trajectory, spread, efficiency |
| `RVOL` | `RVOL` | numeric / ratio | candle | value, trajectory, efficiency, rank |
| `SELL_TRADES` | `sellTr` | numeric / count [≥0] | candle | value, trajectory, spread, efficiency, maxShare, rank |
| `SELL_VOLUME` | `sellVol` | numeric / largeCount [≥0] | candle | value, trajectory, spread, efficiency, maxShare |
| `SPOT_CVD` | `spotCVD` | numeric / signedPrice | timeless | value, trajectory, spread, efficiency, aggregate |
| `TRADES` | `trades` | numeric / count [≥0] | candle | value, trajectory, spread, efficiency, maxShare, rank |
| `VOLUME` | `volBase` | numeric / largeCount [≥0] | candle | value, trajectory, spread, efficiency, maxShare |
| `VOL_SMA20` | `volSMA20` | numeric / largeCount | candle | value, trajectory, spread, efficiency |

## Derivatives — `derivatives` (7)

> Describe positioning, leverage demand, and funding pressure in perpetual markets.

**Common misuses (platform's own words):**

- Treating positive funding as an immediate short signal.
- Interpreting open-interest growth without price context.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `FUNDING_ANN` | `ann` | numeric / percent | timeless | value, spread |
| `FUNDING_LABEL` | `rateLbl` | classification / low·moderate·elevated… | timeless | value |
| `FUNDING_RATE` | `rate` | numeric / percent | timeless | value, trajectory, spread, efficiency, aggregate, rank |
| `OI` | `OI` | numeric / usdLargeCount | timeless | value, trajectory, spread, efficiency, aggregate, rank |
| `OI_CHG` | `oiChg` | numeric / percent | timeless | value, spread, rank |
| `OI_PX_REGIME` | `oiRegime` | classification / new longs·new shorts·short covering… | timeless | value |
| `OI_VELOCITY` | `oiVel` | classification / accelerating·decelerating·steady | timeless | value |

## Structure — `structure` (7)

> Describe price location, reference levels, and active support or resistance zones.

**Common misuses (platform's own words):**

- Treating every nearby level as equally strong.
- Applying a separate timeframe override to anchor-derived zones.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `BB_PCT_B` | `pctB` | numeric / fraction [0–1] | candle | value, trajectory, spread, efficiency, maxShare, rank |
| `BB_TOUCH` | `BBtouch` | classification / upper·lower·none | candle | value |
| `PRICE_ZONE` | `zone` | classification / breakout high·breakdown low·near high… | candle | value |
| `STRUCT_ZONES` | `zones` | entitySet /  | candle | count, nearestZoneType, nearestZoneRange, nearestZoneDist, nearestZoneAge |
| `SWING_HIGH` | `swingHi` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `SWING_LOW` | `swingLo` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |
| `VWAP` | `VWAP` | numeric / price | candle | value, trajectory, distance, spread, efficiency, bandTouch |

## Regime — `regime` (3)

> Describe the platform-classified trend, volatility, and momentum environment.

**Common misuses (platform's own words):**

- Treating a regime label as a guaranteed trade direction.
- Reconstructing regime labels from unrelated client heuristics.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `REGIME_MOM` | `regMom` | classification / bullish·bearish·neutral… | timeless | value, trajectory |
| `REGIME_TREND` | `regTrend` | classification / trending up·trending down·ranging | timeless | value, trajectory |
| `REGIME_VOL` | `regVol` | classification / expanding·contracting·normal | timeless | value, trajectory |

## Crowd — `crowd` (9)

> Describe aggregate player positioning, confidence, and historical accuracy.

**Common misuses (platform's own words):**

- Assuming consensus is always correct.
- Using crowd values as candle-timeframe indicators.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `CROWD_ACC` | `crowdAcc` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_ACC_LIVE` | `crowdAccLive` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_CAPT` | `captRate` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_CAPT_LIVE` | `captRateLive` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_PICK` | `pick` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_PICK_LIVE` | `pickLive` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_UPBIAS` | `upBias` | numeric / percent [0–100] | timeless | value, rank |
| `CROWD_UPBIAS_LIVE` | `upBiasLive` | numeric / percent [0–100] | timeless | value, rank |
| `SETTLED_AT` | `settledAt` | date /  | timeless | value |

## Derived — `derived` (7)

> Describe platform-owned cross-family classifications and convergence facts.

**Common misuses (platform's own words):**

- Recomputing the classification with client-local rules.
- Treating a summary label as proof that every input agrees.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `CAPTAIN_CONF` | `captainConf` | boolean /  | timeless | value |
| `CONFIDENCE` | `conf` | classification / high·moderate·low | timeless | value |
| `FLOW_ALIGN` | `flowAlign` | classification / aligned bullish·aligned bearish·divergent… | timeless | value |
| `PERP_SPOT_CONFIRMS` | `perpSpotConf` | boolean /  | timeless | value |
| `PERP_SPOT_FLOW` | `perpSpotFlow` | classification / confirmed_bull·confirmed_bear·perp_led_fragile… | timeless | value |
| `PERP_SPOT_STRENGTH` | `perpSpotStr` | classification / high·moderate·low | timeless | value |
| `SMART_RETAIL` | `smartRetail` | classification / hidden accumulation·hidden distribution·confirmed | timeless | value |
