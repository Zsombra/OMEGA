# 02 · The Transform Layer

*Generated from `data/contract/transforms/_authoring.json` — do not hand-edit.*

A transform is **how you read** a metric. There are 15 authorable transforms omega has extracted.
Crucially the metric×transform matrix is a **sparse partial function**, not a grid:
only **619 of 156×15 = 2340** cells are legal
(**26.5%** density).

Against the column `transformId` enum the contract 108.0.0 write schema serves (`data/contract/stage_strategy_draft/schema_20261010T215326Z.json`):

- **`bandTouch` is retired** — extracted, no longer served; it is dropped from every metric's transforms in doc 01 and here, and `omega.validate` refuses it (`TRANSFORM_RETIRED`). Its reference entry is kept as history.
- **`levelInteraction` is served and unmeasured** — never extracted, so it has no entry here; `omega.validate` refuses it (`TRANSFORM_UNMEASURED`) until its column contract is read.

## Reference

### `value` — Value

Select one value at the requested offset.

```
output = base[t - offset]
```

- **Supported on:** 155 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the requested slot is absent or the source value is null.
- **Parameters:**
  - `offset` (optional, default `0`) — Bars before the latest value; 0 selects the current resolved value.

### `trajectory` — Trajectory

Render the recent build-up plus its rising, falling, or flat direction.

```
slots = last window non-null base values; trend = compare(first, last)
```

- **Supported on:** 71 metric(s)
- **Emits:** window + 1 — window value slots (_t{n-1}..._t1, _now) plus one _trend direction output.
- **Null behaviour:** Missing observations produce null slots; an empty series has null now and trend.
- **Parameters:**
  - `window` (optional, default `4`) — Number of non-null observations represented by the trajectory.
  - `bars` (optional, default `all`) — Which bars feed the series: 'all' includes the live forming bar as now; 'closed' uses closed bars only.

### `distance` — Distance from price

Measure signed percentage distance from current price to a price-level metric.

```
output = ((price - base) / base) × 100
```

- **Supported on:** 62 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when price or the base level is null, or when the base level is zero.
- **Parameters:** none
- **Chains into:** ['trajectory', 'aggregate', 'efficiency'] (candle-backed metrics only)

### `spread` — Spread vs metric

Measure the signed percentage gap between the base and one operand metric.

```
output = (base - inputs[0]) / inputs[0] × 100
```

- **Supported on:** 119 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when either operand is null or the second operand is zero.
- **Parameters:**
  - `inputs` (required) — Exactly one candle-backed operand metric, resolved at the base column timeframe.
- **Chains into:** ['trajectory', 'aggregate', 'efficiency'] (candle-backed metrics only)

### `efficiency` — Efficiency (ER)

Measure how directly the series travelled: net movement divided by the total distance covered.

```
output = |base[last] - base[first]| / sum(|base[i] - base[i-1]|) over the window
```

- **Supported on:** 68 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the window holds fewer than two non-null points, or when every consecutive delta is zero (a flat series has no efficiency).
- **Parameters:**
  - `window` (optional, default `21`) — Number of non-null POINTS in the window — N moves needs window N+1.
  - `bars` (optional, default `all`) — Which bars feed the series: 'all' includes the live forming bar; 'closed' uses closed bars only.
- **Output range:** [0, 1]

### `aggregate` — Windowed aggregate

Compute the mean of non-null history values in the selected window.

```
output = sum(nonNull(base[-window:])) / count(nonNull(base[-window:]))
```

- **Supported on:** 68 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the selected history window has no non-null values.
- **Parameters:**
  - `window` (optional, default `24`) — Number of history observations included in the canonical mean.
- **Note:** Mean only — there is no sum/min/max variant.

### `maxShare` — Largest share

Report how much of the window total sits in its single largest observation.

```
output = max(nonNull(base[-window:])) / sum(nonNull(base[-window:]))
```

- **Supported on:** 20 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the window holds no non-null values, or when they total zero (a share of nothing is not a number).
- **Parameters:**
  - `window` (optional, default `24`) — Number of non-null observations included in the window total.
  - `bars` (optional, default `all`) — Which bars feed the series: 'all' includes the live forming bar; 'closed' uses closed bars only.
- **Output range:** [0, 1]

### `rank` — Peer rank

Read the platform-computed ordinal for the base metric across the tracked universe. The ranked set holds current values only, so there is no historical ordinal to offset into.

```
output = ordinal(base among the ranked universe, by the chosen ordering)
```

- **Supported on:** 40 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the ranked universe carries no entry for the asset.
- **Parameters:**
  - `ordering` (optional, default `hi`) — Which end of the universe rank 1 names: Highest, Lowest, Furthest from zero, or Closest to zero. The magnitude pair is offered only where the metric can be negative.
- **Note:** Current values only — no historical offset. Allowed orderings are per-metric policy (see rankOrderings), NOT derivable from whether the metric can be negative.

### `classifyZone` — Zone label

Classify a bounded oscillator with its canonical overbought and oversold policy.

```
output = oscillatorZone(base)
```

- **Supported on:** 8 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the source oscillator is null.
- **Parameters:** none

### `crossDetect` — Cross detect

Detect a bullish or bearish crossing in the canonical source series.

```
output = crossDirection(base[t - 1], base[t])
```

- **Supported on:** 3 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the two observations required for crossing are unavailable.
- **Parameters:** none

### `bandTouch` — Band touch (RETIRED)

Classify current price proximity to the canonical upper and lower bands.

```
output = bandTouch(base, current price)
```

- **Retired** at contract 108.0.0: not in the served enum; the 61.2.0 extraction offered it on 62 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the price or band values required by the classifier are unavailable.
- **Parameters:** none
- **Note:** Authorable but used by ZERO platform templates.

### `count` — Zone count

Count active entities in the resolved set.

```
output = cardinality(base)
```

- **Supported on:** 1 metric(s)
- **Emits:** 1
- **Null behaviour:** An empty resolved set returns zero; an unavailable entity set returns null.
- **Parameters:** none

### `nearestZoneType` — Nearest zone type

Return the canonical type of the nearest zone on the selected side.

```
output = type(nearest(base filtered by side))
```

- **Supported on:** 1 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when no active zone exists on the selected side.
- **Parameters:**
  - `side` (required) — Select whether the nearest support or resistance zone is resolved.

### `nearestZoneRange` — Nearest zone range

Return the low-to-high price range of the nearest zone on the selected side.

```
output = [low, high] of nearest(base filtered by side)
```

- **Supported on:** 1 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when no active zone exists on the selected side.
- **Parameters:**
  - `side` (required) — Select whether the nearest support or resistance zone is resolved.

### `nearestZoneDist` — Nearest zone distance

Measure signed percentage distance from price to the nearest zone midpoint.

```
output = ((price - midpoint(nearest zone)) / midpoint(nearest zone)) × 100
```

- **Supported on:** 1 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when no active zone exists on the selected side or its midpoint is zero.
- **Parameters:**
  - `side` (required) — Select whether the nearest support or resistance zone is resolved.

### `nearestZoneAge` — Nearest zone age

Return whole hours since the nearest zone was detected.

```
output = floor((now - detectedAt(nearest zone)) / 1 hour)
```

- **Supported on:** 1 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when no active zone exists on the selected side.
- **Parameters:**
  - `side` (required) — Select whether the nearest support or resistance zone is resolved.

## Spread operand pools

`spread` is unit-typed. A metric may only spread against operands sharing its
`nativeOutput.unit`, and never against itself. Every pool is fully symmetric
(0 asymmetric edges across the whole graph).

| Unit | Size | Members |
|---|---|---|
| `count` | 6 | `BUY_TRADES`, `REGIME_MOM_BEAR_VOTES`, `REGIME_MOM_BULL_VOTES`, `REGIME_RUN_BARS`, `SELL_TRADES`, `TRADES` |
| `fraction` | 3 | `BB_PCT_B`, `BUY_PRESSURE`, `STOCH_RSI14` |
| `largeCount` | 5 | `BUY_VOLUME`, `OBV`, `SELL_VOLUME`, `VOLUME`, `VOL_SMA20` |
| `oscillator` | 17 | `ADX`, `CCI20`, `DI_MINUS`, `DI_PLUS`, `MFI14`, `QQE_RSI_MA`, `QQE_STOP`, `REGIME_DI_SPREAD`, `REGIME_TREND_MARGIN`, `RSI14`, `RSI2`, `RSI7`, `STOCH_D`, `STOCH_K`, `WILLR14`, `WT1`, `WT2` |
| `percent` | 16 | `ATR_PCT`, `BB_WIDTH_PCT`, `CHG_15M`, `CHG_1H`, `CHG_24H`, `CHG_4H`, `CHG_5M`, `CLOSE_CHANGE`, `FUNDING_ANN`, `FUNDING_RATE`, `HIGH_DEV`, `LOW_DEV`, `OI_CHG`, `PPO`, `REGIME_CRASH_MARGIN`, `ROC12` |
| `price` | 62 | `BB_LOWER`, `BB_UPPER`, `CLOSE`, `DONCHIAN_LOWER`, `DONCHIAN_UPPER`, `EMA13`, `EMA20`, `EMA21`, `EMA5`, `EMA50`, `EMA9`, `HIGH`, `HMA20`, `ICHI_BASE`, `ICHI_CONV`, `ICHI_LAG`, `ICHI_SPAN_A`, `ICHI_SPAN_B`, `KC_LOWER`, `KC_MID`, `KC_UPPER`, `LAST`, `LOW`, `MARK`, `NAKED_POC_ABOVE`, `NAKED_POC_BELOW`, `OPEN`, `ORACLE`, `PDH`, `PDL`, `PDO`, `PIVOT_P`, `PIVOT_R1`, `PIVOT_R2`, `PIVOT_R3`, `PIVOT_S1`, `PIVOT_S2`, `PIVOT_S3`, `PRIOR_TPO_IB_HIGH`, `PRIOR_TPO_IB_LOW`, `PRIOR_TPO_POC`, `PRIOR_TPO_VAH`, `PRIOR_TPO_VAL`, `PRIOR_TPO_VPOC`, `PRIOR_TPO_VVAH`, `PRIOR_TPO_VVAL`, `PSAR`, `SMA20`, `SMA200`, `SMA50`, `SPOT_CLOSE_BN`, `SPOT_CLOSE_CB`, `ST_LINE`, `TPO_IB_HIGH`, `TPO_IB_LOW`, `TPO_POC`, `TPO_VAH`, `TPO_VAL`, `TPO_VPOC`, `TPO_VVAH`, `TPO_VVAL`, `VWAP` |
| `ratio` | 3 | `REGIME_VOL_ATR_RATIO`, `REGIME_VOL_BBW_RATIO`, `RVOL` |
| `signedPrice` | 5 | `ATR`, `BB_WIDTH`, `CVD`, `MACD`, `SPOT_CVD` |
| `usdLargeCount` | 2 | `NOTIONAL_VOLUME_1D`, `OI` |

`RVOL` (unit `ratio`) is the lone numeric metric with **no** spread transform at all —
its pool would have exactly one member.

37 metrics offer no `spread`: mostly classifications,
booleans, events and the entity set.

## Platform-privileged pairs

The platform's own section templates use pairs that **authors cannot**. Requesting one
returns `REPORT_COLUMN_PAIR_UNSUPPORTED`.

| Metric | Transform | Used by | Authorable substitute |
|---|---|---|---|
| `ADX` | `classifyState` | `includeTrendStrength` | `classifyZone` |
| `MFI14` | `classifyState` | `includeMfi` | `classifyZone` |
| `CVD` | `classifyState` | `includeCvd` | — |

`CCI20 × classifyZone` is the subtle one: `classifyZone` classifies a *bounded*
oscillator, and `CCI20`'s `nativeOutput` carries no `range`. No canonical bounds,
no zone policy exposed to authors — though the platform reserves one for itself.

`bandTouch` is the mirror case: fully authorable, used by **zero** platform templates.
