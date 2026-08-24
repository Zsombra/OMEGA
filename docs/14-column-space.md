# 14 · Column Space

Every table you could build, counted — and what the platform itself has never touched.

Docs 01–03 describe the pieces: 86 metrics, 16 transforms, and the rules that decide which
pair up. This one asks the question those leave open — *what can I actually make?* — and
answers it with a number rather than a shrug.

## The space is finite

`composition_rules.chaining.stages` is **2**. A column is one metric, one transform, and at
most one chained successor. That cap is the whole reason this is countable:

| level | count |
|---|---:|
| metric × transform pairs | 1376 |
| **legal atoms** | **322** |
| atoms accepting a chained stage | 52 — 42 × 3 successors, 10 × 4 including `rank` |
| **structural shapes** | **488** |
| expanded by spread operand and rank ordering | **2200** |
| documented in the cookbook (doc 06) | 8 |

```python
from omega.space import enumerate_shapes, query
len(enumerate_shapes())                      # 488
len(enumerate_shapes(expand_operands=True))  # 2200
```

### Three ordering axes, not one

A `rank` **atom** varies over the metric's `rankOrderings`. A **chained** `rank` varies over
the atom's own `chainedRankOrderings`, which the contract publishes separately —
`EMA13 × distance` carries `chainSuccessors: [..., "rank"]` *and*
`chainedRankOrderings: [hi, lo, far, near]`. Treating those as one axis undercounts the
space by 78 (2122 instead of 2200).

## Parameters are not enumerated

`window` is 1–64, `offset` 0–64, `bars` is one of two values, and `inputs` takes up to four
metrics. Materialising that cross-product would produce millions of rows of no value.
Parameters are axes you vary on a shape you have already chosen.

More importantly, **their effective values are not guessable**. Ask the platform:

| transform | parameter | default |
|---|---|---|
| `trajectory` | `window` | **4** |
| `efficiency` | `window` | **21** |
| any windowed transform | `bars` | **`all`** |
| chained `rank` | `ordering` | **`hi`** |

Every one of those was measured, not assumed — a contract request that sent neither
`window` nor `bars` came back with both filled in.

`bars: "all"` is the one that bites. It **includes the live forming bar**, which is trap #1
in the cookbook. You can watch it happen in the captured render below: `CCI_t1` and
`CCI_now` are identical on both coins, because the forming bar occupies `now` and repeats
the last closed observation until it closes.

## What the platform itself uses

`data/contract/templates/platform/_all.json` holds BattleGrid's own **25** templates,
carrying **106** distinct (metric, transform) pairs between them. That makes "unexplored"
measurable against what actually ships, rather than against eight cookbook recipes:

| | shapes |
|---|---:|
| the platform's templates use | 139 |
| **nothing has ever used** | **349** |

**71% of the legal space is untouched.** By family:

| family | unused shapes |
|---|---:|
| volumeFlow | 82 |
| momentum | 78 |
| price | 60 |
| trend | 51 |
| structure | 29 |
| volatility | 28 |
| crowd | 9 |
| derivatives | 9 |
| regime | 3 |

One transform is untouched entirely: **`bandTouch`** appears in no platform template at all,
while remaining fully authorable.

```python
query(platform_uses=False, family="volumeFlow")   # 82 shapes nobody has built
query(max_headers=1)                              # 390 shapes that cost one header
```

## Extract, never compute

No code in `omega` evaluates a transform. Formulas and values come from BattleGrid verbatim
and are cached under `data/contract/columns/`. Two read-only tools supply them:

- `get_strategy_column_contract` — compiles one column into effective parameters, output
  headers with types, `formula`, `glossary`, and `nullBehavior`. Reads no market values.
- `preview_strategy_report` — renders live values *"without saving or mutating strategy
  state"*. No write, no strategy slot, no quota.

`omega` cannot call MCP tools (see `omega/performance.py:244`). `omega.probe` builds the
payloads and ingests the saved responses; the agent runs the calls. `probe.FETCH_RECIPE`
documents the procedure, and a test enforces the no-network rule against the import graph.

### All 16 transforms are exercised on live data

A second render covers the 11 transforms the first did not, so every transform has now
produced a real header from the live compiler. That capture immediately paid for itself
by falsifying three of `omega.fanout`'s eleven header predictions:

| shape | predicted | live |
|---|---|---|
| `STRUCT_ZONES × nearestZoneAge` | `zones_support_age` | **`zones_support_age_h`** |
| `STRUCT_ZONES × nearestZoneRange` | `zones_resistance_range` | **`zones_resist_range`** |
| `STRUCT_ZONES × nearestZoneType` | `zones_resistance_type` | **`zones_resist_type`** |

Two rules, neither guessable: `nearestZoneAge` carries its **unit** in the header, and the
side is abbreviated **asymmetrically** — `resistance` becomes `resist` while `support`
stays whole.

Fixing the predictor then broke a test elsewhere, which is the interesting part.
`omega.generate`'s `PRICE_STRUCTURE` preset built a condition against
`zones_resistance_dist` — a header the platform never emits. The offline type-checker had
been passing it because the generator and the predictor shared the same wrong assumption.
**Two self-consistent components agree with each other and both disagree with reality;
only ground truth breaks the tie.** A generated strategy carrying that condition would
have been unresolvable live.

### The timeframe marker: infix for most, suffix for two

`REL_INFIX` maps `anchor` to nothing, `lower` to `_ltf_`, `regime` to `_htf_`. Two
renders at non-anchor timeframes corrected four more predictions — every one a branch
that silently dropped the marker:

| transform @ `rel: lower` | predicted | live |
|---|---|---|
| `CLOSE × bandTouch` | `close_touch` | **`close_ltf_touch`** |
| `ADX × classifyZone` | `ADX_zone` | **`ADX_ltf_zone`** |
| `MACD × crossDetect` | `MACD_cross` | **`MACD_ltf_cross`** |
| `ADX × rank` | `ADX_rank_hi` | **`ADX_ltf_rank_hi`** |
| `VWAP × distance` | `dist_ltf_VWAP` | **`dist_VWAP_ltf`** |

The rule that emerged: **`value` and `distance` carry the marker as a trailing suffix;
every other transform takes it as an infix** between the code and the suffix. Nothing in
doc 02 or 03 states this — it came out of the renders.

### The rank denominator contradicts its own prose

For a non-anchor rank the section text claims the ordinal is *"across THIS REPORT's coins
… rendered as rank/report-size"*. That render previewed **one** coin and returned
`32/78` and `12/78`. The denominator is the tracked universe, not the report.

The `conditionColumns` `meaning` for the same headers says *"across the tracked universe"*,
and the trailing `rankScopingNote` agrees. The section prose is the outlier, contradicted
by its own numbers. Stored verbatim; recorded, not repaired.

### `aggregate` cannot be an atom in a timeframed section

`aggregate` has exactly **3** atoms — `FUNDING_RATE`, `OI`, `SPOT_CVD` — and all three are
`timeless`, so none can sit in a timeframe-pinned section (doc 06, trap #5). Reaching it at
`1h` means chaining: it is available as a chained stage on **52** candle-backed shapes.

### The header stem is the metric's `code`

`CCI20 × trajectory` renders as `CCI_t3 … CCI_now, CCI_trend` — **not** `CCI20_*`. The stem
comes from the metric's `code` field, not its key. `omega.fanout.outputs_for` predicts this
correctly; a test asserts its output matches the live compiler header-for-header on every
captured case.

### The platform's formula text contains a known error

For a chained `spread → trajectory`, the live contract returns:

```
output = (EMA5 - EMA13) / EMA13 × 100; slots = last 4 non-null EMA5 values; trend = compare(first, last)
```

The slots hold the **spread** series, not raw EMA5 values.

This is stored **verbatim** and is asserted by a test that would fail if someone "fixed" it.
One-to-one means the stored text is what BattleGrid says; the correction lives beside it, in
`composition_rules.chaining.knownDocDefect` and here. A reader must be able to see both.

The same policy covers `classifyState`, recorded as `PLATFORM_ONLY` — used by five platform
templates but rejected for authoring with `REPORT_COLUMN_PAIR_UNSUPPORTED`.

## A worked loop

Four shapes spanning the structurally distinct cases — an atom, a chain, a bare fan-out, and
a rank-chain — rendered against BTC and GOOGL at `1h`:

| coin | RSI14 | EMA5_EMA13_spread_now | EMA5_EMA13_spread_trend | CCI_t1 | CCI_now | CCI_trend | dist_VWAP_rank_hi |
|---|---|---|---|---|---|---|---|
| BTC | 64.9 | 0.82 | rising | 183.5 | 183.5 | falling | 14/78 |
| GOOGL | 73.4 | 0.69 | rising | 247.8 | 247.8 | rising | 10/78 |

Three things to read off it:

1. `CCI_t1 == CCI_now` on both coins — the forming bar, as promised above.
2. `dist_VWAP_rank_hi` renders as **`14/78`**, an ordinal over the universe size, not a bare
   integer. The response's own `rankScopingNote` warns that rank spans the full active
   market, not the previewed selection — so a coin can show a rank larger than the row count.
3. Four columns cost **24 of the 32** `columnLookback` budget. Fan-out is the expensive
   axis: only `trajectory` fans out, and two of these four carry one.

```python
from omega.probe import FIRST_CUT, contract_request, render_request, load_contracts

req = contract_request(FIRST_CUT[1], window=4)   # payload for the agent to run
case = load_contracts()[1]                       # the captured response
```

### `offset` is invisible in the header

`offset` shifts which bar a `value` column reads and leaves no trace in the header name.
Two columns differing only by offset collide, the platform accepts it silently, and the
section is dropped from `conditionColumns` — see cookbook trap #11. `omega.validate`
raises `DUPLICATE_HEADER` for it.

`bars` is invisible the same way: `bars: "closed"` changed `CCI_now` from 183.5 to 143.8
in a live render while every header stayed identical. You cannot tell from a header
whether the forming bar is in the series.

## Caveat

The captured contracts and render are a **dated snapshot** — `capturedAt` is on both files.
The connector's own instructions warn that cached capability lists stop being authoritative
after a deployment. Re-run the calls in `probe.FETCH_RECIPE` before trusting the defaults on
a changed platform; if `test_trajectory_default_window_is_four_not_eight` ever fails, that is
a real finding about the platform, not a broken test.

Thirty-three shapes across six renders and four contract calls — **6.8%** of the space.
Complete on every structural axis: all 16 transforms, all 3 timeframe rels, all 8 chained
combinations, and both the `offset` and `bars` parameters.

**455 of the 488 shapes have still never been compiled or rendered.** 55 columns compiled
live have exposed nine header mispredictions, one shipped condition bug, and one silent
platform failure. The last batch found nothing, which is the first evidence that the
structural surface may now be sound — but it is one clean batch, not a guarantee about
the untouched 93%.
