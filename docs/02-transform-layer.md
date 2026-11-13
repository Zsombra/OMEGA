# 02 · The Transform Layer

*Generated from `data/contract/transforms/_authoring.json` — do not hand-edit.*

A transform is **how you read** a metric. There are 29 authorable transforms omega has extracted.
Crucially the metric×transform matrix is a **sparse partial function**, not a grid:
only **4735 of 581×29 = 16849** cells are legal
(**28.1%** density).

Against the column `transformId` enum the contract 171.0.0 write schema serves (`data/contract/stage_strategy_draft/schema_20261112T093211Z.json`):

- **`bandTouch` is retired** — extracted, no longer served; it is dropped from every metric's transforms in doc 01 and here, and `omega.validate` refuses it (`TRANSFORM_RETIRED`). Its reference entry is kept as history.

## Reference

### `value` — Value

Select one value at the requested offset.

```
output = {base}[t - {offset}]
```

- **Supported on:** 579 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the requested slot is absent or the source value is null.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `offset` (optional, default `0`) — Bars to step back inside the Read bar set, counted from the newest bar that set admits; 0 reads that newest bar. At or below the strategy timeframe, Developing offset 1 and Confirmed offset 0 read the same completed bar on the live report. A timeless metric (one the catalog serves as "timeless") accepts only 0.

### `trajectory` — Trajectory

Render the recent build-up plus its rising, falling, or flat direction.

```
slots = the newest {window} bars of {base}, present or not; trend = compare(oldest non-null slot, now)
```

- **Supported on:** 189 metric(s)
- **Emits:** window + 1 — window value slots (_t{n-1}..._t1, _now) plus one _trend direction output.
- **Null behaviour:** A bar with no value is a null slot, and now is null when the newest bar has none; the trend is null when now is null or fewer than two bars hold a value.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `4`) — How many of this column's newest bars the trajectory shows, including bars with no value — at least 2, because the trend compares the oldest present reading with the newest.

### `distance` — Distance from price

Measure signed percentage distance from price to a price-level metric: a candle-homed level from its own bar’s close at every slot, a period level or a mark from the current price.

```
output = (({price} − {base}) / {base}) × 100
```

- **Supported on:** 409 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when price or the base level is null, or when the base level is zero. A session-profile level is read at each completed bar as it stood when the bar opened: a level formed before the bar from that bar's own snapshot, a level formed from its own bar (a developing value area, a session's running high) from the prior bar's snapshot in the same period instance, so a value stamped inside a completed bar is never part of that bar's read; null on the instance's first bar and where the snapshot is not held. A live read's forming bar reads the level bound at the read instant, the value a display shows.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
- **Chains into:** ['trajectory', 'aggregate', 'efficiency'] (candle-backed metrics only)

### `spread` — Spread vs metric

Compare the base with one same-unit operand: a difference for a comparable unit, a signed percentage gap for an asset-relative unit.

```
output = comparable(unit) ? {base} − {inputs[0]} : (({base} − {inputs[0]}) / {inputs[0]}) × 100
```

- **Supported on:** 501 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when either operand is null, or, for an asset-relative unit, when the operand is zero. An averaged side (an operand `{ metric, transformId, window }`, or the base of `metric × average × spread`) is the average with each bar as its newest, null where that average is. A session-profile level is read at each completed bar as it stood when the bar opened: a level formed before the bar from that bar's own snapshot, a level formed from its own bar (a developing value area, a session's running high) from the prior bar's snapshot in the same period instance, so a value stamped inside a completed bar is never part of that bar's read; null on the instance's first bar and where the snapshot is not held. A live read's forming bar reads the level bound at the read instant, the value a display shows.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `inputs` (required) — Exactly one operand at the base column timeframe: a same-unit metric `{ metric }`, or a metric under one average at a length `{ metric, transformId, window }` — transformId one of aggregate, ema, rma, wma (aggregate is the simple average), window at least 2, the metric the base itself or any of its operands with a per-bar candle value.
- **Chains into:** ['trajectory', 'aggregate', 'efficiency'] (candle-backed metrics only)

### `relativeTo` — Relative to coin

Compare the base metric with the same metric of another roster instrument, bar by bar: a difference for a comparable unit, a ratio for a price.

```
output = comparable(unit) ? {base} − {instrument}.{base} : {base} ÷ {instrument}.{base}
```

- **Supported on:** 143 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when either coin's value is null on the bar, or, for a price, when the instrument's is zero. A bar either coin does not hold, an instrument with no catalog row or a stopped feed, and a frame past the instrument's history are reads that never ran: a condition over them is UNRESOLVED.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `instrument` (optional, default `BTC`) — The instrument the base metric is read against, bar by bar. On a coin section: any active coin or TRADFI instrument — left unset, BTC. On a section bound to a stablecoin pair: another declared pair, which must be named — that section has no default.

### `efficiency` — Efficiency (ER)

Measure how directly the series travelled: net movement divided by the total distance covered.

```
output = |{base}[t] - {base}[t - {window}]| / sum(|{base}[i] - {base}[i-1]|) over the newest {window} changes
```

- **Supported on:** 165 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the series holds fewer bars than the window reads (its changes plus one), when the newest or the oldest of them has no value, when fewer than two hold a value, or when every consecutive change is zero (a flat series has no efficiency).
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `20`) — How many bar-to-bar changes of this column the ratio measures; it reads one more bar than that. Null when the newest or oldest bar it reads has no value.
- **Output range:** [0, 1]

### `aggregate` — Moving average (SMA)

The simple moving average (TradingView's ta.sma) of the selected window: the mean of its non-null values.

```
output = sum(nonNull({base}[-{window}:])) / count(nonNull({base}[-{window}:]))
```

- **Supported on:** 171 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the series holds fewer bars than the window, or the window has no non-null values.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `24`) — How many of this column's newest bars are averaged into one value — the length of the simple moving average, as TradingView's ta.sma. Null when the series holds fewer bars than the length.
- **Note:** Mean only — there is no sum/min/max variant.

### `zscore` — Z-score

Measure how many standard deviations the newest value sits from its window's mean.

```
output = ({base}[t] - mean) / stdev, mean and population stdev over the present values of the newest {window} bars
```

- **Supported on:** 172 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the series holds fewer bars than the window, when the newest or the oldest of them has no value, when fewer than two hold a value, or when the window is flat (a standard deviation of 0).
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `20`) — How many of this column's newest bars the z-score is taken over, including bars with no value — at least 2. Null when the newest or oldest bar it reads has no value.

### `stddev` — Std deviation

Measure how widely the window spreads around its mean, in the column’s own units.

```
output = sqrt(sum(({base}[i] - mean)^2) / count) over the present values of the newest {window} bars
```

- **Supported on:** 172 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the series holds fewer bars than the window, when the newest or the oldest of them has no value, or when fewer than two hold a value; a flat window reads 0.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `20`) — How many of this column's newest bars the standard deviation is taken over, including bars with no value — at least 2. Null when the newest or oldest bar it reads has no value.

### `linregSlope` — Regression slope

Fit a straight line through the window and report its slope per bar, in the column’s own units.

```
output = least-squares slope of {base}[i] against its bar position i over the present values of the newest {window} bars
```

- **Supported on:** 172 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the series holds fewer bars than the window, when the newest or the oldest of them has no value, or when fewer than two hold a value.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `20`) — How many of this column's newest bars the regression is taken over, including bars with no value — at least 2. Null when the newest or oldest bar it reads has no value.

### `pctl` — Percentile

Report what share of the prior values sit at or below the newest one, 0 to 100.

```
output = 100 * count({base}[t - k] <= {base}[t]) / count(present {base}[t - k]), k = 1 .. {window}
```

- **Supported on:** 172 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the series holds fewer bars than the window plus the newest, when the newest or the oldest of them has no value, or when no prior bar holds a value.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `20`) — How many of this column's bars before the newest the newest is ranked against; it reads the newest bar too. Null when the newest or oldest bar it reads has no value.

### `rollingMin` — Rolling min

Report the lowest value of the window, which ends offset bars before the newest.

```
output = min(nonNull({base}[t - {offset} - {window} + 1 .. t - {offset}]))
```

- **Supported on:** 171 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the series holds fewer bars than the window, or when the newest or the oldest of them has no value.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `offset` (optional, default `0`) — How many bars before the newest the window ends; 0 ends it at the newest bar. At 1 the extreme is formed from the bars before the newest, a level a close can break, and the column can chain into distance (offset 1 or more).
  - `window` (optional, default `20`) — How many of this column's newest bars the minimum is taken over, including bars with no value — at least 2. Null when the newest or oldest bar it reads has no value.

### `rollingMax` — Rolling max

Report the highest value of the window, which ends offset bars before the newest.

```
output = max(nonNull({base}[t - {offset} - {window} + 1 .. t - {offset}]))
```

- **Supported on:** 171 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the series holds fewer bars than the window, or when the newest or the oldest of them has no value.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `offset` (optional, default `0`) — How many bars before the newest the window ends; 0 ends it at the newest bar. At 1 the extreme is formed from the bars before the newest, a level a close can break, and the column can chain into distance (offset 1 or more).
  - `window` (optional, default `20`) — How many of this column's newest bars the maximum is taken over, including bars with no value — at least 2. Null when the newest or oldest bar it reads has no value.

### `maxShare` — Largest share

Report how much of the window total sits in its single largest observation.

```
output = max(nonNull({base}[-{window}:])) / sum(nonNull({base}[-{window}:]))
```

- **Supported on:** 36 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the window holds no non-null values, or when they total zero (a share of nothing is not a number).
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `24`) — How many of this column's newest bars the share is taken over. Bars with no value are left out.
- **Output range:** [0, 1]

### `rank` — Peer rank

Read the ordinal of the base metric among its ranked set: the tracked universe for a metric the platform ranks exchange-wide, this report’s coins for a crowd metric. The ranked set holds current values only, so there is no historical ordinal to offset into.

```
output = ordinal({base} among its ranked set, by the chosen ordering)
```

- **Supported on:** 62 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the ranked set carries no entry for the asset.
- **Parameters:**
  - `ordering` (optional, default `hi`) — Which end of the ranked set rank 1 names: Highest, Lowest, Furthest from zero, or Closest to zero. The magnitude pair is offered only where the metric can be negative.
  - `scope` (optional, default `all`) — Which coins of the ranked set the column ranks among: 'all' ranks every coin in the set, and a category scope ranks only the coins it holds — its asset class (crypto, tradfi) or its coins' main category — with the rank and its universe counted over those coins. A scope holding fewer than 5 coins in the set ranks none. Accepted only where the column ranks the tracked universe.
- **Note:** Current values only — no historical offset. Allowed orderings are per-metric policy (see rankOrderings), NOT derivable from whether the metric can be negative.

### `classifyZone` — Zone label

Classify the reading into the zones its own classifier declares.

```
output = zoneOf({base})
```

- **Supported on:** 15 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the source reading is null.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.

### `crossDetect` — Cross detect

Detect a bullish or bearish crossing in the canonical source series.

```
output = crossDirection({base}[t - 1], {base}[t])
```

- **Supported on:** 11 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the two observations required for crossing are unavailable.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.

### `levelInteraction` — Level interaction

Classify what the newest bar did against a price level: none when it closed through the level, a rejection that pierced the level and closed back, or a touch within the TOUCH tolerance, on the side the prior close stood.

```
output = levelInteraction(bar t, close t−1, {base}[t], {base} in force when bar t opened, touch tolerance {tolerance})
```

- **Supported on:** 393 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the series holds no prior bar, a price or the level at the newest bar is absent, the level in force when the bar opened is absent (the prior bar's level, for a level computed from its own bar), or either level is not positive; with touchAtr, a bar that neither closed through the level nor rejected it reads null when the prior bar has no ATR. A session-profile level is read at each completed bar as it stood when the bar opened: a level formed before the bar from that bar's own snapshot, a level formed from its own bar (a developing value area, a session's running high) from the prior bar's snapshot in the same period instance, so a value stamped inside a completed bar is never part of that bar's read; null on the instance's first bar and where the snapshot is not held. A live read's forming bar is judged against the level bound at the read instant, from the side in force when it opened.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `buffer` (optional, default `0`) — How near a TOUCH must come to the level, in whole basis points of the level; a column carries this or touchAtr, never both. At 0, the default, a TOUCH is exact contact: the bar reaches the level and closes exactly on it. "Reached and did not close through" is an in clause over the TOUCH and REJECT labels of a side, and a close through the level is the distance crossing (BREAK), which reads none here. Only TOUCH reads the buffer; a REJECT pierces the level itself. A distance of X% is a buffer of X × 100 bps.
  - `touchAtr` (optional, default `None`) — How near a TOUCH must come to the level, as a multiple of the ATR14 of the column's own timeframe at the prior bar; a column carries this or buffer, never both. Only TOUCH reads it: a close through the level still reads none and a REJECT still reads where the prior bar has no ATR, and a TOUCH reads no value there.

### `bandTouch` — Band touch (RETIRED)

Classify current price proximity to the canonical upper and lower bands.

```
output = bandTouch(base, current price)
```

- **Retired** at contract 171.0.0: not in the served enum; the 61.2.0 extraction offered it on 0 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when the price or band values required by the classifier are unavailable.
- **Parameters:** none
- **Note:** Authorable but used by ZERO platform templates.

### `count` — Zone count

Count active entities in the resolved set.

```
output = cardinality({base})
```

- **Supported on:** 1 metric(s)
- **Emits:** 1
- **Null behaviour:** An empty resolved set returns zero; an unavailable entity set returns null.
- **Parameters:** none

### `nearestZoneType` — Nearest zone type

Return the canonical type of the nearest zone on the selected side.

```
output = type(nearest({base} filtered by {side}))
```

- **Supported on:** 1 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when no active zone exists on the selected side.
- **Parameters:**
  - `side` (required) — Select whether the nearest support or resistance zone is resolved.

### `nearestZoneRange` — Nearest zone range

Return the low-to-high price range of the nearest zone on the selected side.

```
output = [low, high] of nearest({base} filtered by {side})
```

- **Supported on:** 1 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when no active zone exists on the selected side.
- **Parameters:**
  - `side` (required) — Select whether the nearest support or resistance zone is resolved.

### `nearestZoneDist` — Nearest zone distance

Measure the signed percentage of price from the nearest zone's near edge (a support zone's high, a resistance zone's low); 0 while price is inside the zone.

```
output = 0 when low ≤ {price} ≤ high, else (({price} − nearEdge(nearest zone)) / nearEdge(nearest zone)) × 100
```

- **Supported on:** 1 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when no active zone exists on the selected side or its near edge is zero.
- **Parameters:**
  - `side` (required) — Select whether the nearest support or resistance zone is resolved.

### `nearestZoneAge` — Nearest zone age

Count the whole bars of the column's timeframe since the bar that completed the nearest zone.

```
output = (lastClosedBar - completingBar(nearest zone)) / barDuration
```

- **Supported on:** 1 metric(s)
- **Emits:** 1
- **Null behaviour:** Returns null when no active zone exists on the selected side.
- **Parameters:**
  - `side` (required) — Select whether the nearest support or resistance zone is resolved.

### `cci` — Commodity channel index (CCI)

The commodity channel index (TradingView's ta.cci): the newest value's distance from its window's mean, in mean absolute deviations over 0.015.

```
output = ({base}[t] − mean) / (0.015 · mean |{base} − mean|) over the newest {window} bars
```

- **Supported on:** 171 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the series holds fewer bars than the length, any of them has no value, or all of them are equal.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `20`) — The length of the commodity channel index, as TradingView's ta.cci(source, length). One value reads exactly the length in bars, and is null when the series holds fewer, any of them has no value, or all of them are equal. A stored CCI metric is the exact source at its own length.

### `ema` — Exponential average (EMA)

The exponential moving average (TradingView's ta.ema) folded over the newest unbroken run of bars up to the readable depth, seeded by the oldest of them.

```
output = ema[t], ema[0] = {base}[-run], ema[i] = α·{base}[i] + (1 − α)·ema[i − 1], α = 2 / ({window} + 1), run = min(present bars in a row, depth)
```

- **Supported on:** 171 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the newest bars hold fewer present values in a row than the length needs.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `20`) — The length of the exponential moving average, as TradingView's ta.ema(source, length). One value folds the newest unbroken run of bars, up to the readable depth, and needs at least the bars after which the average's seed weighs at most 0.1 % — 73 bars at length 20 — so it is null when the newest bars hold fewer present values in a row. A stored EMA metric is the exact source at its own length.

### `rma` — Wilder average (RMA)

Wilder's moving average (TradingView's ta.rma) folded over the newest unbroken run of bars up to the readable depth, seeded by the mean of its oldest length bars.

```
output = rma[t], rma[0] = mean({base}[-run..][0..{window}]), rma[i] = α·{base}[i] + (1 − α)·rma[i − 1], α = 1 / {window}, run = min(present bars in a row, depth)
```

- **Supported on:** 171 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the newest bars hold fewer present values in a row than the length needs.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `14`) — The length of Wilder's moving average, as TradingView's ta.rma(source, length). One value folds the newest unbroken run of bars, up to the readable depth, and needs at least the length's seed bars plus the bars after which that seed weighs at most 0.1 % — 108 bars at length 14 — so it is null when the newest bars hold fewer present values in a row.

### `rsi` — Relative strength index (RSI)

Wilder's relative strength index (TradingView's ta.rsi) of the series' changes folded over the newest unbroken run of bars up to the readable depth, 0 to 100.

```
output = 100 − 100 / (1 + rma(gain, {window}) / rma(loss, {window})) over the newest run of present bars up to the depth, 100 where nothing was lost, 0 where nothing was gained
```

- **Supported on:** 171 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the newest bars hold fewer present values in a row than the length needs, or all of them are equal.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `14`) — The length of the relative strength index, as TradingView's ta.rsi(source, length). One value folds the newest unbroken run of bars, up to the readable depth plus one, and needs at least the changes its two Wilder averages need to converge plus the bar the oldest change starts from — 109 bars at length 14 — so it is null when the newest bars hold fewer present values in a row, or all of them are equal. A stored RSI metric is the exact source at its own length.

### `wma` — Weighted average (WMA)

The linearly weighted moving average (TradingView's ta.wma) over the newest length bars, the newest weighing most.

```
output = Σ (i + 1)·{base}[i] / ({window}·({window} + 1)/2) over the newest {window} bars, oldest first
```

- **Supported on:** 171 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the series holds fewer bars than the length, or any of them has no value.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `20`) — The length of the linearly weighted moving average, as TradingView's ta.wma(source, length): the newest bar weighs the length, the oldest weighs 1. One value reads exactly the length in bars, and is null when the series holds fewer or any of them has no value.

### `roc` — Rate of change (ROC)

The rate of change (TradingView's ta.roc): the newest value's percent change from the value length bars before it.

```
output = 100 · ({base}[t] − {base}[t − {window}]) / {base}[t − {window}]
```

- **Supported on:** 171 metric(s)
- **Emits:** not served by `get_metric_construction_hints` for this transform (measured per render)
- **Null behaviour:** Returns null when the series holds fewer bars than the length plus the newest, when the newest or the older value has no value, or when the older value is 0.
- **Parameters:**
  - `bars` (optional, default `None`) — Which bars the read may include: 'closed' (Confirmed) uses completed bars only; 'all' (Developing) admits the bar still in progress at the frame instant. Left unset, a column reads Confirmed at every timeframe; Developing applies only where it is chosen.
  - `window` (optional, default `9`) — The length of the rate of change, as TradingView's ta.roc(source, length): the percent change from the value length bars back. It reads the newest bar and the one length bars before it, and is null when either has no value or the older one is 0. A stored ROC metric is the exact close at its own length.

## Spread operand pools

`spread` is unit-typed. A metric may only spread against operands sharing its
`nativeOutput.unit`, and never against itself. Every pool is fully symmetric
(0 asymmetric edges across the whole graph).

| Unit | Size | Members |
|---|---|---|
| `count` | 12 | `BUY_TRADES`, `DAY_OF_WEEK`, `LIQUIDITY_POOL_ABOVE_TOUCHES`, `LIQUIDITY_POOL_BELOW_TOUCHES`, `REGIME_MOM_BEAR_VOTES`, `REGIME_MOM_BULL_VOTES`, `REGIME_RUN_BARS`, `SELL_TRADES`, `SWING_FRACTAL_HIGH_BARS_AGO`, `SWING_FRACTAL_LOW_BARS_AGO`, `TRADES`, `UTC_HOUR` |
| `fraction` | 6 | `BB_PCT_B`, `BUY_PRESSURE`, `BUY_PRES_BN`, `BUY_PRES_CB`, `CLOSE_LOCATION`, `SPOT_DOMINANCE` |
| `largeCount` | 5 | `BUY_VOLUME`, `SELL_VOLUME`, `SPOT_AVG_TRADE`, `VOLUME`, `VOL_SMA20` |
| `oscillator` | 20 | `ADX`, `CCI20`, `CMF20`, `DI_MINUS`, `DI_PLUS`, `MFI14`, `QQE_RSI_MA`, `QQE_STOP`, `REGIME_CRASH_MARGIN`, `REGIME_TREND_MARGIN`, `RSI14`, `RSI2`, `RSI7`, `STOCH_D`, `STOCH_K`, `STOCH_RSI_D`, `STOCH_RSI_K`, `WILLR14`, `WT1`, `WT2` |
| `percent` | 29 | `ATR_PCT`, `BB_WIDTH_PCT`, `CHG_15M`, `CHG_1H`, `CHG_24H`, `CHG_4H`, `CHG_5M`, `CLOSE_CHANGE`, `FUNDING_ANN`, `FUNDING_RATE`, `HIGH_DEV`, `LOW_DEV`, `MKT_ABOVE_EMA`, `MKT_AVG_CHG`, `MKT_AVG_PPO`, `MKT_DISPERSION`, `MKT_DOWN`, `MKT_NET`, `MKT_PPO_DOWN`, `MKT_PPO_NET`, `MKT_PPO_UP`, `MKT_UP`, `OI_CHG`, `PPO_HIST`, `PPO_LINE`, `PPO_SIGNAL`, `ROC12`, `ROC15`, `ROC9` |
| `price` | 413 | `ASIA_HIGH`, `ASIA_LOW`, `ASIA_OPEN`, `BB_LOWER`, `BB_UPPER`, `CLOSE`, `DONCHIAN_BROKEN_HI`, `DONCHIAN_BROKEN_HI_PRIOR`, `DONCHIAN_BROKEN_LO`, `DONCHIAN_BROKEN_LO_PRIOR`, `DONCHIAN_LOWER`, `DONCHIAN_LOWER_PRIOR`, `DONCHIAN_UPPER`, `DONCHIAN_UPPER_PRIOR`, `EMA13`, `EMA20`, `EMA21`, `EMA5`, `EMA50`, `EMA55`, `EMA8`, `EMA9`, `EQH_LEVEL`, `EQL_LEVEL`, `HIGH`, `HL2`, `HLC3`, `HMA20`, `IB_EXT_DOWN_150`, `IB_EXT_DOWN_200`, `IB_EXT_UP_150`, `IB_EXT_UP_200`, `ICHI_BASE`, `ICHI_CONV`, `ICHI_LAG`, `ICHI_SPAN_A`, `ICHI_SPAN_B`, `INTERNAL_PENDING_HIGH`, `INTERNAL_PENDING_LOW`, `INTERNAL_STRUCTURE_LEVEL`, `KC_LOWER`, `KC_UPPER`, `LAST`, `LIQUIDITY_POOL_ABOVE`, `LIQUIDITY_POOL_ABOVE_RETIRED`, `LIQUIDITY_POOL_BELOW`, `LIQUIDITY_POOL_BELOW_RETIRED`, `LONDON_HIGH`, `LONDON_LOW`, `LONDON_OPEN`, `LOW`, `MARK`, `MONTH_TPO_POC`, `MONTH_TPO_VAH`, `MONTH_TPO_VAL`, `NAKED_POC_ABOVE`, `NAKED_POC_BELOW`, `NAKED_SINGLE_PRINT_ABOVE`, `NAKED_SINGLE_PRINT_BELOW`, `NEW_YORK_HIGH`, `NEW_YORK_LOW`, `NEW_YORK_OPEN`, `OHLC4`, `OPEN`, `OR15_HIGH`, `OR15_LOW`, `OR30_HIGH`, `OR30_LOW`, `ORACLE`, `PDH`, `PDL`, `PDO`, `PIVOT_CAM_R1`, `PIVOT_CAM_R2`, `PIVOT_CAM_R3`, `PIVOT_CAM_R4`, `PIVOT_CAM_R5`, `PIVOT_CAM_S1`, `PIVOT_CAM_S2`, `PIVOT_CAM_S3`, `PIVOT_CAM_S4`, `PIVOT_CAM_S5`, `PIVOT_CLASSIC_R3`, `PIVOT_CLASSIC_R4`, `PIVOT_CLASSIC_S3`, `PIVOT_CLASSIC_S4`, `PIVOT_DM_P`, `PIVOT_DM_R1`, `PIVOT_DM_S1`, `PIVOT_FIB_R1`, `PIVOT_FIB_R2`, `PIVOT_FIB_S1`, `PIVOT_FIB_S2`, `PIVOT_MONTH_CAM_R1`, `PIVOT_MONTH_CAM_R2`, `PIVOT_MONTH_CAM_R3`, `PIVOT_MONTH_CAM_R4`, `PIVOT_MONTH_CAM_R5`, `PIVOT_MONTH_CAM_S1`, `PIVOT_MONTH_CAM_S2`, `PIVOT_MONTH_CAM_S3`, `PIVOT_MONTH_CAM_S4`, `PIVOT_MONTH_CAM_S5`, `PIVOT_MONTH_CLASSIC_R3`, `PIVOT_MONTH_CLASSIC_R4`, `PIVOT_MONTH_CLASSIC_S3`, `PIVOT_MONTH_CLASSIC_S4`, `PIVOT_MONTH_DM_P`, `PIVOT_MONTH_DM_R1`, `PIVOT_MONTH_DM_S1`, `PIVOT_MONTH_FIB_R1`, `PIVOT_MONTH_FIB_R2`, `PIVOT_MONTH_FIB_S1`, `PIVOT_MONTH_FIB_S2`, `PIVOT_MONTH_P`, `PIVOT_MONTH_R1`, `PIVOT_MONTH_R2`, `PIVOT_MONTH_R3`, `PIVOT_MONTH_R4`, `PIVOT_MONTH_R5`, `PIVOT_MONTH_S1`, `PIVOT_MONTH_S2`, `PIVOT_MONTH_S3`, `PIVOT_MONTH_S4`, `PIVOT_MONTH_S5`, `PIVOT_MONTH_WOODIE_P`, `PIVOT_MONTH_WOODIE_R1`, `PIVOT_MONTH_WOODIE_R2`, `PIVOT_MONTH_WOODIE_R3`, `PIVOT_MONTH_WOODIE_R4`, `PIVOT_MONTH_WOODIE_S1`, `PIVOT_MONTH_WOODIE_S2`, `PIVOT_MONTH_WOODIE_S3`, `PIVOT_MONTH_WOODIE_S4`, `PIVOT_P`, `PIVOT_QUARTER_CAM_R1`, `PIVOT_QUARTER_CAM_R2`, `PIVOT_QUARTER_CAM_R3`, `PIVOT_QUARTER_CAM_R4`, `PIVOT_QUARTER_CAM_R5`, `PIVOT_QUARTER_CAM_S1`, `PIVOT_QUARTER_CAM_S2`, `PIVOT_QUARTER_CAM_S3`, `PIVOT_QUARTER_CAM_S4`, `PIVOT_QUARTER_CAM_S5`, `PIVOT_QUARTER_CLASSIC_R3`, `PIVOT_QUARTER_CLASSIC_R4`, `PIVOT_QUARTER_CLASSIC_S3`, `PIVOT_QUARTER_CLASSIC_S4`, `PIVOT_QUARTER_DM_P`, `PIVOT_QUARTER_DM_R1`, `PIVOT_QUARTER_DM_S1`, `PIVOT_QUARTER_FIB_R1`, `PIVOT_QUARTER_FIB_R2`, `PIVOT_QUARTER_FIB_S1`, `PIVOT_QUARTER_FIB_S2`, `PIVOT_QUARTER_P`, `PIVOT_QUARTER_R1`, `PIVOT_QUARTER_R2`, `PIVOT_QUARTER_R3`, `PIVOT_QUARTER_R4`, `PIVOT_QUARTER_R5`, `PIVOT_QUARTER_S1`, `PIVOT_QUARTER_S2`, `PIVOT_QUARTER_S3`, `PIVOT_QUARTER_S4`, `PIVOT_QUARTER_S5`, `PIVOT_QUARTER_WOODIE_P`, `PIVOT_QUARTER_WOODIE_R1`, `PIVOT_QUARTER_WOODIE_R2`, `PIVOT_QUARTER_WOODIE_R3`, `PIVOT_QUARTER_WOODIE_R4`, `PIVOT_QUARTER_WOODIE_S1`, `PIVOT_QUARTER_WOODIE_S2`, `PIVOT_QUARTER_WOODIE_S3`, `PIVOT_QUARTER_WOODIE_S4`, `PIVOT_R1`, `PIVOT_R2`, `PIVOT_R3`, `PIVOT_R4`, `PIVOT_R5`, `PIVOT_S1`, `PIVOT_S2`, `PIVOT_S3`, `PIVOT_S4`, `PIVOT_S5`, `PIVOT_WEEK_CAM_R1`, `PIVOT_WEEK_CAM_R2`, `PIVOT_WEEK_CAM_R3`, `PIVOT_WEEK_CAM_R4`, `PIVOT_WEEK_CAM_R5`, `PIVOT_WEEK_CAM_S1`, `PIVOT_WEEK_CAM_S2`, `PIVOT_WEEK_CAM_S3`, `PIVOT_WEEK_CAM_S4`, `PIVOT_WEEK_CAM_S5`, `PIVOT_WEEK_CLASSIC_R3`, `PIVOT_WEEK_CLASSIC_R4`, `PIVOT_WEEK_CLASSIC_S3`, `PIVOT_WEEK_CLASSIC_S4`, `PIVOT_WEEK_DM_P`, `PIVOT_WEEK_DM_R1`, `PIVOT_WEEK_DM_S1`, `PIVOT_WEEK_FIB_R1`, `PIVOT_WEEK_FIB_R2`, `PIVOT_WEEK_FIB_S1`, `PIVOT_WEEK_FIB_S2`, `PIVOT_WEEK_P`, `PIVOT_WEEK_R1`, `PIVOT_WEEK_R2`, `PIVOT_WEEK_R3`, `PIVOT_WEEK_R4`, `PIVOT_WEEK_R5`, `PIVOT_WEEK_S1`, `PIVOT_WEEK_S2`, `PIVOT_WEEK_S3`, `PIVOT_WEEK_S4`, `PIVOT_WEEK_S5`, `PIVOT_WEEK_WOODIE_P`, `PIVOT_WEEK_WOODIE_R1`, `PIVOT_WEEK_WOODIE_R2`, `PIVOT_WEEK_WOODIE_R3`, `PIVOT_WEEK_WOODIE_R4`, `PIVOT_WEEK_WOODIE_S1`, `PIVOT_WEEK_WOODIE_S2`, `PIVOT_WEEK_WOODIE_S3`, `PIVOT_WEEK_WOODIE_S4`, `PIVOT_WOODIE_P`, `PIVOT_WOODIE_R1`, `PIVOT_WOODIE_R2`, `PIVOT_WOODIE_R3`, `PIVOT_WOODIE_R4`, `PIVOT_WOODIE_S1`, `PIVOT_WOODIE_S2`, `PIVOT_WOODIE_S3`, `PIVOT_WOODIE_S4`, `PIVOT_YEAR_CAM_R1`, `PIVOT_YEAR_CAM_R2`, `PIVOT_YEAR_CAM_R3`, `PIVOT_YEAR_CAM_R4`, `PIVOT_YEAR_CAM_R5`, `PIVOT_YEAR_CAM_S1`, `PIVOT_YEAR_CAM_S2`, `PIVOT_YEAR_CAM_S3`, `PIVOT_YEAR_CAM_S4`, `PIVOT_YEAR_CAM_S5`, `PIVOT_YEAR_CLASSIC_R3`, `PIVOT_YEAR_CLASSIC_R4`, `PIVOT_YEAR_CLASSIC_S3`, `PIVOT_YEAR_CLASSIC_S4`, `PIVOT_YEAR_DM_P`, `PIVOT_YEAR_DM_R1`, `PIVOT_YEAR_DM_S1`, `PIVOT_YEAR_FIB_R1`, `PIVOT_YEAR_FIB_R2`, `PIVOT_YEAR_FIB_S1`, `PIVOT_YEAR_FIB_S2`, `PIVOT_YEAR_P`, `PIVOT_YEAR_R1`, `PIVOT_YEAR_R2`, `PIVOT_YEAR_R3`, `PIVOT_YEAR_R4`, `PIVOT_YEAR_R5`, `PIVOT_YEAR_S1`, `PIVOT_YEAR_S2`, `PIVOT_YEAR_S3`, `PIVOT_YEAR_S4`, `PIVOT_YEAR_S5`, `PIVOT_YEAR_WOODIE_P`, `PIVOT_YEAR_WOODIE_R1`, `PIVOT_YEAR_WOODIE_R2`, `PIVOT_YEAR_WOODIE_R3`, `PIVOT_YEAR_WOODIE_R4`, `PIVOT_YEAR_WOODIE_S1`, `PIVOT_YEAR_WOODIE_S2`, `PIVOT_YEAR_WOODIE_S3`, `PIVOT_YEAR_WOODIE_S4`, `PMH`, `PML`, `PRIOR_ASIA_DEMAND_AVG`, `PRIOR_ASIA_DEMAND_EDGE`, `PRIOR_ASIA_DEMAND_WAVG`, `PRIOR_ASIA_HIGH`, `PRIOR_ASIA_LOW`, `PRIOR_ASIA_OPEN`, `PRIOR_ASIA_SUPPLY_AVG`, `PRIOR_ASIA_SUPPLY_EDGE`, `PRIOR_ASIA_SUPPLY_WAVG`, `PRIOR_DAY_DEMAND_AVG`, `PRIOR_DAY_DEMAND_EDGE`, `PRIOR_DAY_DEMAND_WAVG`, `PRIOR_DAY_SUPPLY_AVG`, `PRIOR_DAY_SUPPLY_EDGE`, `PRIOR_DAY_SUPPLY_WAVG`, `PRIOR_LONDON_DEMAND_AVG`, `PRIOR_LONDON_DEMAND_EDGE`, `PRIOR_LONDON_DEMAND_WAVG`, `PRIOR_LONDON_HIGH`, `PRIOR_LONDON_LOW`, `PRIOR_LONDON_OPEN`, `PRIOR_LONDON_SUPPLY_AVG`, `PRIOR_LONDON_SUPPLY_EDGE`, `PRIOR_LONDON_SUPPLY_WAVG`, `PRIOR_MONTH_TPO_POC`, `PRIOR_MONTH_TPO_VAH`, `PRIOR_MONTH_TPO_VAL`, `PRIOR_NEW_YORK_DEMAND_AVG`, `PRIOR_NEW_YORK_DEMAND_EDGE`, `PRIOR_NEW_YORK_DEMAND_WAVG`, `PRIOR_NEW_YORK_HIGH`, `PRIOR_NEW_YORK_LOW`, `PRIOR_NEW_YORK_OPEN`, `PRIOR_NEW_YORK_SUPPLY_AVG`, `PRIOR_NEW_YORK_SUPPLY_EDGE`, `PRIOR_NEW_YORK_SUPPLY_WAVG`, `PRIOR_SWING_FRACTAL_HIGH`, `PRIOR_SWING_FRACTAL_LOW`, `PRIOR_TPO_IB_HIGH`, `PRIOR_TPO_IB_LOW`, `PRIOR_TPO_POC`, `PRIOR_TPO_VAH`, `PRIOR_TPO_VAL`, `PRIOR_TPO_VPOC`, `PRIOR_TPO_VVAH`, `PRIOR_TPO_VVAL`, `PRIOR_WEEK_TPO_POC`, `PRIOR_WEEK_TPO_VAH`, `PRIOR_WEEK_TPO_VAL`, `PSAR`, `PWH`, `PWL`, `SMA20`, `SMA200`, `SMA50`, `SPOT_CLOSE_BN`, `SPOT_CLOSE_CB`, `ST_LINE`, `SWING_FRACTAL_HIGH`, `SWING_FRACTAL_LOW`, `SWING_PENDING_HIGH`, `SWING_PENDING_LOW`, `SWING_STRUCTURE_LEVEL`, `TPO_IB_HIGH`, `TPO_IB_LOW`, `TPO_POC`, `TPO_SINGLE_PRINT_ABOVE`, `TPO_SINGLE_PRINT_BELOW`, `TPO_VAH`, `TPO_VAL`, `TPO_VPOC`, `TPO_VVAH`, `TPO_VVAL`, `VWAP`, `VWAP_LB1`, `VWAP_LB2`, `VWAP_LB3`, `VWAP_MONTH`, `VWAP_MONTH_LB1`, `VWAP_MONTH_LB2`, `VWAP_MONTH_LB3`, `VWAP_MONTH_UB1`, `VWAP_MONTH_UB2`, `VWAP_MONTH_UB3`, `VWAP_ROLLING_1H`, `VWAP_ROLLING_1H_LB1`, `VWAP_ROLLING_1H_LB2`, `VWAP_ROLLING_1H_LB3`, `VWAP_ROLLING_1H_UB1`, `VWAP_ROLLING_1H_UB2`, `VWAP_ROLLING_1H_UB3`, `VWAP_ROLLING_24H`, `VWAP_ROLLING_24H_LB1`, `VWAP_ROLLING_24H_LB2`, `VWAP_ROLLING_24H_LB3`, `VWAP_ROLLING_24H_UB1`, `VWAP_ROLLING_24H_UB2`, `VWAP_ROLLING_24H_UB3`, `VWAP_ROLLING_4H`, `VWAP_ROLLING_4H_LB1`, `VWAP_ROLLING_4H_LB2`, `VWAP_ROLLING_4H_LB3`, `VWAP_ROLLING_4H_UB1`, `VWAP_ROLLING_4H_UB2`, `VWAP_ROLLING_4H_UB3`, `VWAP_SWING_HIGH`, `VWAP_SWING_LOW`, `VWAP_TRADING_SESSION`, `VWAP_TRADING_SESSION_LB1`, `VWAP_TRADING_SESSION_LB2`, `VWAP_TRADING_SESSION_LB3`, `VWAP_TRADING_SESSION_UB1`, `VWAP_TRADING_SESSION_UB2`, `VWAP_TRADING_SESSION_UB3`, `VWAP_UB1`, `VWAP_UB2`, `VWAP_UB3`, `VWAP_WEEK`, `VWAP_WEEK_LB1`, `VWAP_WEEK_LB2`, `VWAP_WEEK_LB3`, `VWAP_WEEK_UB1`, `VWAP_WEEK_UB2`, `VWAP_WEEK_UB3`, `VWMA20`, `WEEK_TPO_POC`, `WEEK_TPO_VAH`, `WEEK_TPO_VAL`, `ZONE_RESIST_HIGH`, `ZONE_RESIST_LOW`, `ZONE_RESIST_MID`, `ZONE_SUPPORT_HIGH`, `ZONE_SUPPORT_LOW`, `ZONE_SUPPORT_MID` |
| `ratio` | 3 | `REGIME_VOL_ATR_RATIO`, `REGIME_VOL_BBW_RATIO`, `RVOL` |
| `signedPrice` | 8 | `ATR`, `CUM_VOLUME_DELTA`, `CVD`, `MACD_HIST`, `MACD_LINE`, `MACD_SIGNAL`, `SPOT_CVD`, `SQZ_MOM` |
| `usdLargeCount` | 5 | `BUY_QUOTE_VOL`, `NOTIONAL_VOLUME_1D`, `OI`, `QUOTE_VOL`, `SELL_QUOTE_VOL` |

80 metrics offer no `spread`; by kind, classification 40, numeric 26, boolean 9, event 3, date 1, entitySet 1.
26 of them are numeric: `CANDLE_RUN`, `CLOSE_RUN`, `CROWD_ACC`, `CROWD_ACC_EDGE_Z`, `CROWD_ACC_EDGE_Z_LIVE`, `CROWD_ACC_LIVE`, `CROWD_CAPT`, `CROWD_CAPT_EXCESS_Z`, `CROWD_CAPT_EXCESS_Z_LIVE`, `CROWD_CAPT_LIVE`, `CROWD_PICK`, `CROWD_PICK_LIVE`, `CROWD_UPBIAS`, `CROWD_UPBIAS_LIVE`, `CROWD_UP_EXCESS_Z`, `CROWD_UP_EXCESS_Z_LIVE`, `CROWD_UP_LEAN_Z`, `CROWD_UP_LEAN_Z_LIVE`, `GAP_PCT`, `MKT_STRETCH`, `MKT_UNIVERSE`, `MKT_VOL_NET`, `OBV`, `PAR_DEV`, `PERP_SPOT_GAP`, `REGIME_DI_SPREAD`.

## Platform-privileged pairs

The platform's own section templates use pairs that **authors cannot**. Requesting one
returns `REPORT_COLUMN_PAIR_UNSUPPORTED`.

| Metric | Transform | Used by | Authorable substitute |
|---|---|---|---|
| `ADX` | `classifyState` | `includeTrendStrength` | `classifyZone` |
| `MFI14` | `classifyState` | `includeMfi` | `classifyZone` |
| `CVD` | `classifyState` | `includeCvd` | `classifyZone` |
