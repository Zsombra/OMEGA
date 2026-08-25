# 03 · Column Compilation

How `{metric, transformId, timeframe, …}` becomes named cells in the report.

---

## The column object

```json
{
  "metric": "RSI14",              // required — one of the 86
  "transformId": "trajectory",    // required — must be legal for this metric
  "timeframe": {"rel": "anchor"}, // required — {rel:…} or {abs:…}
  "chainedTransformId": "rank",   // optional — second stage
  "window": 4,                    // optional — series transforms
  "offset": 0,                    // optional — `value` only
  "bars": "closed",               // optional — series transforms
  "ordering": "far",              // optional — rank
  "side": "support",              // optional — entitySet transforms
  "inputs": [{"metric": "EMA13"}] // optional — spread operand (exactly 1)
}
```

Parameters that don't apply to the chosen transform are silently ignored — the compiler
normalises them into `effectiveParameters` with `null`s. `omega.validate` warns on them,
because a silently-ignored `window` usually means you meant a different transform.

## Defaults that bite

| Parameter | Default | Consequence |
|---|---|---|
| `bars` | `"all"` | **includes the live forming bar** |
| `window` (trajectory) | 4 | 5 headers |
| `window` (efficiency) | 21 | needs 21 *points* — N moves needs N+1 |
| `window` (aggregate/maxShare) | 24 | |
| `offset` | 0 | current resolved value |
| `ordering` | `"hi"` | rejected outright if the metric doesn't offer `hi` |

The `bars` default is the dangerous one. On a raw per-bar quantity like `VOLUME` or
`TRADES`, the forming bar ramps from zero each interval, so `bars:"all"` makes every
fresh bar look like a collapse in participation. `omega.validate` raises
`FORMING_BAR_RAMP` when it sees this combination.

## `bars` and `offset` are not interchangeable

`value` **rejects `bars` entirely**. Measured:

```
[column-grammar] transform 'value' does not accept params.bars
  allowedDomain: { rule: "column parameters ... must satisfy the canonical
                          transform contract", candidates: ["offset"] }
```

So for a plain `value` read, `offset` is the *only* parameter available — and that
matters more than it looks, because both are ways to escape the forming bar.

| | excludes the forming bar | available on `value` |
|---|---|---|
| `bars: "closed"` | yes | **no** |
| `offset: 1` or more | yes — the window lands on closed bars | yes |

Measured on the same render: `offset: 0` drifted from a recomputation while `offset: 3`
matched to the cent, because an offset of 1 or more reads bars that no longer move. That
makes `offset` the only stable-read mechanism for every metric whose transform is `value`
— which is most of them.

Two costs to remember when reaching for it:

- **`offset` does not appear in the header.** Two columns differing only by offset collide,
  render anyway, and *both* vanish from `conditionColumns` — cookbook trap 20.
- **`offset` counts against the lookback budget.** `columnLookback = max(window + offset)`,
  capped at 32. An `offset: 3` on a default-window `value` reads 27 of the 32.

## Timeframe-inert metrics take the anchor *reference*, and nothing else

40 of the 86 metrics have `timeframeMode: "timeless"` — they are **bundle reads**, lifted
from a precomputed bundle rather than computed on the candle grid. Their column
`timeframe` must be the literal `{"rel": "anchor"}`. Everything else is refused:

```
[column-grammar] metric 'regMom' is timeframe-inert (a bundle read)
  — it accepts only the anchor timeframe reference, not 'regime'
```

`rel:"lower"`, `rel:"regime"` and any `abs` all fail the same way. The rule is
**syntactic, not semantic** — with a 1h anchor, `{"abs": "1h"}` resolves to exactly the
anchor timeframe and is *still* rejected. All four forms were probed live; see
[`timeless_column_timeframe.json`](../data/audit/timeless_column_timeframe.json). The
error's `allowedDomain` names `offset` as the only column parameter left free.

This is distinct from the *section*-level rule ([04](04-section-report-budget.md)): a
timeless metric cannot sit in a section carrying a `timeframe` override **and** cannot
carry a non-anchor timeframe of its own. `omega.validate` enforced only the first until
2026-08-26 and so accepted three shapes the platform refuses.

**What it does not mean.** A timeless metric is *not* pinned to a fixed horizon. Rendered
at 5m and 4h seconds apart, `REGIME_MOM` changes on 8 of 10 coins and `REGIME_TREND` on
9 of 10 — they follow the report anchor like everything else. What they refuse is a
**second** timeframe declared on the column on top of the one the report already carries.
Measured in [`regime_anchor_variance.json`](../data/audit/regime_anchor_variance.json),
after the opposite had been asserted in this file.

## Fan-out

Only `trajectory` produces more than one header.

```
trajectory, window = N   →   N value slots  +  1 direction output
                             _t{N-1} … _t1, _now, _trend
```

The slot outputs **inherit the base metric's kind**. That includes non-numeric metrics:

```
REGIME_TREND × trajectory × window:4
  regTrend_t3   classification  vocab=[trending up, trending down, ranging]
  regTrend_t2   classification  …
  regTrend_t1   classification  …
  regTrend_now  classification  …
  regTrend_trend  direction     vocab=[rising, falling, flat]
```

A "direction" over a categorical series is doing something unusual — read it as *did the
label move up or down the vocabulary order*, and prefer conditioning on `_now` and the
slots rather than `_trend` for classifications.

## Chaining

`chainedTransformId` gives a second stage. The general successors are
`trajectory | aggregate | efficiency`; `rank` is available only where the contract says so.

```
EMA5 × spread(EMA13) → trajectory   →  EMA5_EMA13_spread_{t4…now,trend}   (6 headers)
VWAP × distance      → rank(far)    →  dist_VWAP_rank_far                 (1 header)
```

The compiled `formula` is the two stages joined by `; `.

> **Known cosmetic defect in the platform's glossary:** for a chained `spread → trajectory`,
> the formula text reads `slots = last 5 non-null EMA5 values` when the slots actually hold
> the *spread* series. The computed values are correct; only the glossary wording is wrong.

### The ranking doctrine

Chained `rank` exists because of a real modelling problem, which the compiler states
plainly when you get it wrong:

> raw price-unit metrics never rank: an ordinal over a price level sorts by token
> denomination, so BTC beats DOGE every bar whatever the metric measures. The comparable
> form is the ranked **composition** (`VWAP × distance × rank` earns the `dist_VWAP`
> ordinal without VWAP itself ranking).

So: **rank the composition, not the level.** The same logic removes `rank` from raw
`VOLUME` — use `RVOL`, which is already a ratio.

`spread → rank` is narrower still. `EMA5.spread` declares
`rankableSpreadOperands: ["EMA13"]`, so only that one operand can chain into rank; the
platform pre-computes a ranked universe for that specific derived quantity and nothing else.

### Two rank universes

Same transform, different denominator:

| Family | Universe | Freshness |
|---|---|---|
| market metrics | the platform's **tracked universe** | as of the last close |
| `CROWD_*` | **this report's coins** | computed per request |

A crowd rank of 3 and a VWAP-distance rank of 3 are not comparable quantities.

## Header naming

Headers key off the metric's **`code`**, not its `METRIC` key — `CLOSE_CHANGE` → `closeChg`,
`BUY_PRESSURE` → `buyPres`, `STRUCT_ZONES` → `zones`. Relative timeframes inject an infix:

| `rel` | infix | example |
|---|---|---|
| `anchor` | — | `close_er` |
| `lower` | `_ltf_` | `close_ltf_er` |
| `regime` | `_htf_` | `zones_htf_support_dist` |

Patterns:

```
value          {code}
trajectory     {code}_t{n-1} … {code}_t1, {code}_now, {code}_trend
distance       dist_{code}
spread         {code}_{operandCode}_spread
efficiency     {code}_er
maxShare       {code}_maxShare
aggregate      {code}_mean{window}
bandTouch      {code}_touch
rank           {code}_rank_{ordering}
chained rank   {stage1Header}_rank_{ordering}
nearestZone*   {code}_{side}_{dist|type|range|age}
```

`omega.fanout.outputs_for()` implements this and is tested against the compiler for every
recorded probe. Still: **confirm a header with `get_strategy_column_contract` before writing
a strategy condition that references it by name.**

## From header to condition

Each compiled output carries `conditionOperators` and `conditionVocabulary`. This is the
bridge from *column* to *strategy condition*:

| Output kind | Operators | Vocabulary |
|---|---|---|
| `numeric` | `lt lte gte gt between` | — |
| `rank` | `lt lte gte gt between` | — |
| `date` | `lt lte gte gt between` | — |
| `classification` | `is in` | metric-specific |
| `direction` | `is in` | `rising falling flat` |
| `event` | `is in` | `Bullish Bearish` |
| `boolean` | `is` | — |

## Nulls

Every output is `nullable`. The report renders a null as the sentinel **`—`**.

Each metric×transform pair documents its own null behaviour, and several are worth
internalising because they are *silent*, not errors:

- `efficiency` returns null when the window holds fewer than two non-null points, **or when
  every consecutive delta is zero** — a perfectly flat series has no efficiency.
- `maxShare` returns null when the window totals zero — a share of nothing is not a number.
- `spread` returns null when the **second** operand is zero.
- `rank` returns null when the ranked universe has no entry for the asset.
- `count` on an empty zone set returns **0**; an unavailable set returns **null**. Those are
  different facts and your conditions should treat them differently.
