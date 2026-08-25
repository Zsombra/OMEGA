# 02 · The Transform Layer

*Generated from `data/contract/transforms/_authoring.json` — do not hand-edit.*

A transform is **how you read** a metric. There are 16 authorable transforms.
Crucially the metric×transform matrix is a **sparse partial function**, not a grid:
only **322 of 86×16 = 1376** cells are legal
(**23.4%** density).

## Reference

### `value` — Value

Select one value at the requested offset.

```
output = base[t - offset]
```

- **Supported on:** 85 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the requested slot is absent or the source value is null.
- **Parameters:**
  - `offset` (optional, default `0`) — Bars before the latest value; 0 selects the current resolved value.

### `trajectory` — Trajectory

Render the recent build-up plus its rising, falling, or flat direction.

```
slots = last window non-null base values; trend = compare(first, last)
```

- **Supported on:** 46 metric(s)
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

- **Supported on:** 18 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when price or the base level is null, or when the base level is zero.
- **Parameters:** none
- **Chains into:** ['trajectory', 'aggregate', 'efficiency'] (candle-backed metrics only)

### `spread` — Spread vs metric

Measure the signed percentage gap between the base and one operand metric.

```
output = (base - inputs[0]) / inputs[0] × 100
```

- **Supported on:** 57 metric(s)
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

- **Supported on:** 43 metric(s)
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

- **Supported on:** 3 metric(s)
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

- **Supported on:** 14 metric(s)
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

- **Supported on:** 31 metric(s)
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

- **Supported on:** 5 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the source oscillator is null.
- **Parameters:** none

### `crossDetect` — Cross detect

Detect a bullish or bearish crossing in the canonical source series.

```
output = crossDirection(base[t - 1], base[t])
```

- **Supported on:** 2 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the two observations required for crossing are unavailable.
- **Parameters:** none

### `bandTouch` — Band touch

Classify current price proximity to the canonical upper and lower bands.

```
output = bandTouch(base, current price)
```

- **Supported on:** 13 metric(s)
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

## Which of these formulas have actually been checked

The formulas above are what the contract *publishes*. Until 2026-08-25 exactly one of
them had ever been checked against what the engine *computes*. **13 of 17 now have.**

Method: render each transform beside its own `trajectory` slots in the same table, so no
external data is needed and no sampling drift can enter between operand and result.
Evidence in `data/audit/transform_formula_audit.json`, guarded by
`tests/test_transform_formulas.py`.

| transform | verdict |
|---|---|
| `trajectory` | exact — slots identical to the last five closed candles |
| `efficiency` | exact — and a monotonic run gives exactly 1.000 |
| `maxShare` | exact on two coins |
| `aggregate` | exact, on a **varying** series — the arithmetic mean, not a median |
| `distance` | exact on two coins |
| `spread` | exact — six columns |
| `rank` | exact — `hi + lo = universe + 1` on every coin tested |
| `value` | exact at offset 0 **and** offset 3 |
| `classifyZone` | behaviourally exact; threshold not pinned from three points |
| `bandTouch` | direction verified; trigger threshold not pinned |
| `nearestZoneType` | consistent on three coins |
| `count` | plausible, not independently verifiable |
| `crossDetect` | **scope exact** — reads the last pair only; trigger not pinned |

The four that remain, and why each is not a matter of effort:

- **`nearestZoneDist`** — measured, and the **published formula is wrong**. The engine
  computes `((midpoint − price) / price) × 100`; the catalogue states the inverse sign
  and a different denominator. See cookbook trap 22.
- **`nearestZoneAge`** — detection timestamps are never exposed, so there is nothing to
  check the hours against.
- **`nearestZoneRange`** — returns `conditionOperators: []`, so it cannot even be gated.
  Only indirectly confirmed, via its midpoint reproducing `nearestZoneDist`.
- **`classifyState`** — `PLATFORM_ONLY`. Refused for custom columns by
  `get_strategy_column_contract` *and* by `preview_strategy_report`. Not buildable, so
  not verifiable.

### The metric conventions that had a real choice

Three metrics have competing definitions in the wild, so which one ships is information
rather than a formality. Measured against 876 Hyperliquid bars:

| | implemented | rejected alternative |
|---|---|---|
| `ADX` | **Wilder's own smoothing** (24.88 vs 24.90) | plain MA of DX — off by 10 points |
| `CCI20` | **`0.015 ×` mean absolute deviation** (−39.27 vs −39.30) | standard deviation — off by 4 |
| `STOCH_K/D` | **slow (14,3,3)** (21.84 / 30.82 vs 22 / 31) | fast (14,1,3); and (14,3,1) fits `%K` but not `%D` |

Ten points of ADX flips `trend_adx_trending` at its 25 threshold. The `(14,3,1)` case is
the instructive one — it reproduces `%K` *exactly* and gets `%D` wrong, so a check of
`%K` alone would have confirmed the wrong convention.

Full detail in [19 · Is the data correct?](19-is-the-data-correct.md).

## Spread operand pools

`spread` is unit-typed. A metric may only spread against operands sharing its
`nativeOutput.unit`, and never against itself. Every pool is fully symmetric
(0 asymmetric edges across the whole graph).

| Unit | Size | Members |
|---|---|---|
| `count` | 3 | `BUY_TRADES`, `SELL_TRADES`, `TRADES` |
| `fraction` | 2 | `BB_PCT_B`, `BUY_PRESSURE` |
| `largeCount` | 5 | `BUY_VOLUME`, `OBV`, `SELL_VOLUME`, `VOLUME`, `VOL_SMA20` |
| `oscillator` | 7 | `ADX`, `CCI20`, `MFI14`, `RSI14`, `RSI7`, `STOCH_D`, `STOCH_K` |
| `percent` | 15 | `ATR_PCT`, `BB_WIDTH_PCT`, `CHG_15M`, `CHG_1H`, `CHG_24H`, `CHG_4H`, `CHG_5M`, `CLOSE_CHANGE`, `FUNDING_ANN`, `FUNDING_RATE`, `HIGH_DEV`, `LOW_DEV`, `OI_CHG`, `PPO`, `ROC12` |
| `price` | 18 | `CLOSE`, `EMA13`, `EMA20`, `EMA5`, `HIGH`, `LAST`, `LOW`, `MARK`, `OPEN`, `ORACLE`, `SMA20`, `SMA200`, `SMA50`, `SPOT_CLOSE_BN`, `SPOT_CLOSE_CB`, `SWING_HIGH`, `SWING_LOW`, `VWAP` |
| `signedPrice` | 5 | `ATR`, `BB_WIDTH`, `CVD`, `MACD`, `SPOT_CVD` |
| `usdLargeCount` | 2 | `NOTIONAL_VOLUME_1D`, `OI` |

`RVOL` (unit `ratio`) is the lone numeric metric with **no** spread transform at all —
its pool would have exactly one member.

29 metrics offer no `spread`: mostly classifications,
booleans, events and the entity set.

## Platform-privileged pairs

The platform's own section templates use pairs that **authors cannot**. Requesting one
returns `REPORT_COLUMN_PAIR_UNSUPPORTED`.

| Metric | Transform | Used by | Authorable substitute |
|---|---|---|---|
| `CCI20` | `classifyZone` | `includeBollingerBands` | — |
| `ADX` | `classifyState` | `includeTrendStrength` | `classifyZone` |
| `MFI14` | `classifyState` | `includeMfi` | `classifyZone` |
| `CVD` | `classifyState` | `includeCvd` | — |

`CCI20 × classifyZone` is the subtle one: `classifyZone` classifies a *bounded*
oscillator, and `CCI20`'s `nativeOutput` carries no `range`. No canonical bounds,
no zone policy exposed to authors — though the platform reserves one for itself.

`bandTouch` is the mirror case: fully authorable, used by **zero** platform templates.
