# 01 · The Metric Layer

*Generated from `data/contract/metrics/` — do not hand-edit.*

144 metrics across 10 families. A metric is a **named quantity the platform already
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
| `CLOSE` | `close` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `HIGH` | `high` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `LAST` | `last` | numeric / price | timeless | value, distance, spread, bandTouch |
| `LOW` | `low` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `MARK` | `mark` | numeric / price | timeless | value, distance, spread, bandTouch |
| `OPEN` | `open` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `ORACLE` | `oracle` | numeric / price | timeless | value, distance, spread, bandTouch |
| `SPOT_CLOSE_BN` | `bnClose` | numeric / price | timeless | value, distance, spread, bandTouch |
| `SPOT_CLOSE_CB` | `cbClose` | numeric / price | timeless | value, distance, spread, bandTouch |

## Momentum — `momentum` (22)

> Describe directional impulse, exhaustion, and the pace of price movement.

**Common misuses (platform's own words):**

- Treating an overbought reading as an automatic short.
- Stacking several correlated oscillators as independent evidence.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `CCI20` | `CCI` | numeric / oscillator | candle | value, trajectory, spread, efficiency, aggregate, rank, classifyZone |
| `CHG_15M` | `chg15m` | numeric / percent | timeless | value, spread |
| `CHG_1H` | `chg1h` | numeric / percent | timeless | value, spread |
| `CHG_24H` | `chg24h` | numeric / percent | timeless | value, spread |
| `CHG_4H` | `chg4h` | numeric / percent | timeless | value, spread |
| `CHG_5M` | `chg5m` | numeric / percent | timeless | value, spread |
| `CLOSE_CHANGE` | `closeChg` | numeric / percent | candle | value, trajectory, spread, efficiency, aggregate, rank |
| `MACD` | `MACD` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate, crossDetect |
| `MFI14` | `MFI14` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank, classifyZone |
| `PPO` | `PPO` | numeric / percent | candle | value, trajectory, spread, efficiency, aggregate, rank, crossDetect |
| `QQE_RSI_MA` | `qqeRsi` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank |
| `QQE_STOP` | `qqeStop` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank |
| `ROC12` | `ROC` | numeric / percent | candle | value, trajectory, spread, efficiency, aggregate, rank, crossDetect |
| `RSI14` | `RSI14` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank, classifyZone |
| `RSI2` | `RSI2` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank, classifyZone |
| `RSI7` | `RSI7` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank, classifyZone |
| `STOCH_D` | `D` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank, classifyZone |
| `STOCH_K` | `K` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank, classifyZone |
| `STOCH_RSI14` | `stochRSI` | numeric / fraction [0–1] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank |
| `WILLR14` | `willR` | numeric / oscillator [-100–0] | candle | value, trajectory, spread, efficiency, aggregate, rank |
| `WT1` | `wt1` | numeric / oscillator | candle | value, trajectory, spread, efficiency, aggregate, rank |
| `WT2` | `wt2` | numeric / oscillator | candle | value, trajectory, spread, efficiency, aggregate, rank |

## Trend — `trend` (21)

> Describe direction, persistence, and price location relative to trend references.

**Common misuses (platform's own words):**

- Assuming a lagging average predicts a reversal.
- Comparing trend levels without matching timeframes.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `ADX` | `ADX` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank, classifyZone |
| `DI_MINUS` | `DIminus` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank |
| `DI_PLUS` | `DIplus` | numeric / oscillator [0–100] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank |
| `EMA13` | `EMA13` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `EMA20` | `EMA20` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `EMA21` | `EMA21` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `EMA5` | `EMA5` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `EMA50` | `EMA50` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `EMA9` | `EMA9` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `EMA_CROSS` | `EMA5_13` | event / Bullish·Bearish | candle | value |
| `HMA20` | `HMA20` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `ICHI_BASE` | `kijun` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `ICHI_CONV` | `tenkan` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `ICHI_LAG` | `chikou` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `ICHI_SPAN_A` | `senkouA` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `ICHI_SPAN_B` | `senkouB` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `MA_ALIGN` | `MAalign` | classification / bullish·bearish·mixed | candle | value |
| `SMA20` | `SMA20` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `SMA200` | `SMA200` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `SMA50` | `SMA50` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `ST_DIR` | `stDir` | classification / bullish·bearish | candle | value |

## Volatility — `volatility` (7)

> Describe the magnitude and expansion or contraction of market movement.

**Common misuses (platform's own words):**

- Reading high volatility as inherently bullish or bearish.
- Using raw price-unit volatility across unlike assets.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `ATR` | `ATR` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate |
| `ATR_PCT` | `atrPct` | numeric / percent | candle | value, trajectory, spread, efficiency, aggregate, rank |
| `BB_WIDTH` | `BBwidth` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate |
| `BB_WIDTH_PCT` | `bbWidthPct` | numeric / percent | candle | value, trajectory, spread, efficiency, aggregate, rank |
| `HIGH_DEV` | `highDev` | numeric / percent | timeless | value, spread, rank |
| `KC_SQUEEZE` | `kcSqueeze` | classification / on·off | candle | value |
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
| `BUY_PRESSURE` | `buyPres` | numeric / fraction [0–1] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank |
| `BUY_TRADES` | `buyTr` | numeric / count [≥0] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank |
| `BUY_VOLUME` | `buyVol` | numeric / largeCount [≥0] | candle | value, trajectory, spread, efficiency, aggregate, maxShare |
| `CVD` | `CVD` | numeric / signedPrice | candle | value, trajectory, spread, efficiency, aggregate |
| `NOTIONAL_VOLUME_1D` | `vol24hUsd` | numeric / usdLargeCount | timeless | value, spread |
| `OBV` | `OBV` | numeric / largeCount | candle | value, trajectory, spread, efficiency, aggregate |
| `RVOL` | `RVOL` | numeric / ratio | candle | value, trajectory, spread, efficiency, aggregate, rank |
| `SELL_TRADES` | `sellTr` | numeric / count [≥0] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank |
| `SELL_VOLUME` | `sellVol` | numeric / largeCount [≥0] | candle | value, trajectory, spread, efficiency, aggregate, maxShare |
| `SPOT_CVD` | `spotCVD` | numeric / signedPrice | timeless | value, trajectory, spread, efficiency, aggregate |
| `TRADES` | `trades` | numeric / count [≥0] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank |
| `VOLUME` | `volBase` | numeric / largeCount [≥0] | candle | value, trajectory, spread, efficiency, aggregate, maxShare |
| `VOL_SMA20` | `volSMA20` | numeric / largeCount | candle | value, trajectory, spread, efficiency, aggregate |

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

## Structure — `structure` (32)

> Describe price location, reference levels, and active support or resistance zones.

**Common misuses (platform's own words):**

- Treating every nearby level as equally strong.
- Applying a separate timeframe override to anchor-derived zones.

| Metric | `code` | Kind / unit | TF mode | Transforms |
|---|---|---|---|---|
| `BB_LOWER` | `bbLower` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `BB_PCT_B` | `pctB` | numeric / fraction [0–1] | candle | value, trajectory, spread, efficiency, aggregate, maxShare, rank |
| `BB_TOUCH` | `BBtouch` | classification / upper·lower·none | candle | value |
| `BB_UPPER` | `bbUpper` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `DONCHIAN_LOWER` | `donchianLo` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `DONCHIAN_UPPER` | `donchianHi` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `KC_LOWER` | `kcLower` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `KC_MID` | `kcMid` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `KC_UPPER` | `kcUpper` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `PDH` | `pdh` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `PDL` | `pdl` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `PIVOT_P` | `pivotP` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `PIVOT_R1` | `pivotR1` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `PIVOT_R2` | `pivotR2` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `PIVOT_R3` | `pivotR3` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `PIVOT_S1` | `pivotS1` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `PIVOT_S2` | `pivotS2` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `PIVOT_S3` | `pivotS3` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `PRICE_ZONE` | `zone` | classification / breakout high·breakdown low·near high… | candle | value |
| `PRIOR_TPO_POC` | `pTpoPOC` | numeric / price | timeless | value, distance, spread, bandTouch |
| `PRIOR_TPO_VAH` | `pTpoVAH` | numeric / price | timeless | value, distance, spread, bandTouch |
| `PRIOR_TPO_VAL` | `pTpoVAL` | numeric / price | timeless | value, distance, spread, bandTouch |
| `PSAR` | `PSAR` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `STRUCT_ZONES` | `zones` | entitySet /  | candle | count, nearestZoneType, nearestZoneRange, nearestZoneDist, nearestZoneAge |
| `ST_LINE` | `stLine` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |
| `TPO_IB_HIGH` | `tpoIBH` | numeric / price | timeless | value, distance, spread, bandTouch |
| `TPO_IB_LOW` | `tpoIBL` | numeric / price | timeless | value, distance, spread, bandTouch |
| `TPO_POC` | `tpoPOC` | numeric / price | timeless | value, distance, spread, bandTouch |
| `TPO_SHAPE` | `tpoShape` | classification / p-shape·b-shape·balanced | timeless | value |
| `TPO_VAH` | `tpoVAH` | numeric / price | timeless | value, distance, spread, bandTouch |
| `TPO_VAL` | `tpoVAL` | numeric / price | timeless | value, distance, spread, bandTouch |
| `VWAP` | `VWAP` | numeric / price | candle | value, trajectory, distance, spread, efficiency, aggregate, bandTouch |

## Regime — `regime` (16)

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
| `REGIME_CRASH_MARGIN` | `regCrash` | numeric / percent | timeless | value, spread |
| `REGIME_DI_SPREAD` | `regDI` | numeric / oscillator [-100–100] | timeless | value, spread |
| `REGIME_MOM` | `regMom` | classification / bullish·bearish·neutral… | timeless | value, trajectory |
| `REGIME_MOM_BEAR_VOTES` | `regBear` | numeric / count | timeless | value, spread |
| `REGIME_MOM_BULL_VOTES` | `regBull` | numeric / count | timeless | value, spread |
| `REGIME_RUN_BARS` | `regBars` | numeric / count | timeless | value, spread |
| `REGIME_STATE` | `regState` | classification / bull expansion·bear expansion·bull ranging… | timeless | value |
| `REGIME_TREND` | `regTrend` | classification / trending up·trending down·ranging | timeless | value, trajectory |
| `REGIME_TREND_GATE` | `regGate` | classification / cleared·held·dropped | timeless | value |
| `REGIME_TREND_MARGIN` | `regMargin` | numeric / oscillator [0–100] | timeless | value, spread |
| `REGIME_TREND_SOURCE` | `regSrc` | classification / di spread·ema fallback | timeless | value |
| `REGIME_VOL` | `regVol` | classification / expanding·contracting·normal | timeless | value, trajectory |
| `REGIME_VOL_ATR_RATIO` | `regAtrR` | numeric / ratio | timeless | value, spread |
| `REGIME_VOL_BBW_RATIO` | `regBbwR` | numeric / ratio | timeless | value, spread |

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
| `CAPTAIN_CONF` | `captainConf` | boolean / true·false | timeless | value |
| `CONFIDENCE` | `conf` | classification / high·moderate·low | timeless | value |
| `FLOW_ALIGN` | `flowAlign` | classification / aligned bullish·aligned bearish·divergent… | timeless | value |
| `PERP_SPOT_CONFIRMS` | `perpSpotConf` | boolean / true·false | timeless | value |
| `PERP_SPOT_FLOW` | `perpSpotFlow` | classification / confirmed_bull·confirmed_bear·perp_led_fragile… | timeless | value |
| `PERP_SPOT_STRENGTH` | `perpSpotStr` | classification / high·moderate·low | timeless | value |
| `SMART_RETAIL` | `smartRetail` | classification / hidden accumulation·hidden distribution·confirmed | timeless | value |
