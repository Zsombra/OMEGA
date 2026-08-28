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
| expanded by spread operand and rank ordering | **1779** |
| …of which rendered live at least once | **1759 / 1759 — all of them** |
| documented in the cookbook (doc 06) | 8 |

```python
from omega.space import enumerate_shapes, query
len(enumerate_shapes())                      # 488
len(enumerate_shapes(expand_operands=True))  # 1779
```

### Three ordering axes, not one

A `rank` **atom** varies over the metric's `rankOrderings`. A **chained** `rank` varies over
the atom's own `chainedRankOrderings`, which the contract publishes separately —
`EMA13 × distance` carries `chainSuccessors: [..., "rank"]` *and*
`chainedRankOrderings: [hi, lo, far, near]`. Treating those as one axis undercounts the
space by 78.

> **Corrected 2026-08-26: 2200 → 2136.** Chaining `spread → rank` *narrows* the legal
> operand set — the contract publishes `rankableSpreadOperands`, and for `EMA5 × spread`
> that is `['EMA13']` alone, because *"raw price-unit metrics never rank — rank the
> composition, not the level."* The enumerator paired the chain with all 16 of `spread`'s
> operands × 4 orderings, emitting **64 shapes omega's own validator had always refused**.
> The contract stated the rule and `validate_column` enforced it; only `enumerate_shapes`
> disagreed, and nothing compared the two. `tests/test_space_validate_agreement.py` now
> asserts that every enumerated shape validates.
>
> **Corrected again, same day: 2136 → 1779.** The live sweep found a second rule — one the
> contract publishes *nowhere*: a `spread` chained into a series-building transform needs a
> candle-backed operand (357 shapes). See the addendum in [17](17-the-full-sweep.md) and
> `data/audit/spread_chain_operand.json`. All 1,779 have since been rendered live, 0 header
> mismatches.

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

Untouched by the platform, and untouched here too: none of this account's 25
private strategies carries a single custom column. See doc 15.

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

## The loop, from one command

```bash
python -m omega.table explore --unused --family volumeFlow --max-headers 1
python -m omega.table explain EMA5 spread:EMA13 --chain trajectory
python -m omega.table author  CCI20 trajectory --window 4 --out out/
```

`explore` browses the space and **always states what it truncated** — a capped list that
reads as a complete one is the same failure as a guessed number. `explain` prints the
math, the effective parameters and the rendered values, each labelled with the file it
came from. `author` runs validate → fanout → emit and refuses rather than emitting a
column the platform would reject.

### What `explain` prints

```
EMA5 × spread → trajectory  (operand EMA13)

THE MATH            source: data/contract/transforms/_authoring.json
  stage 1  Spread vs metric
           output = (base - inputs[0]) / inputs[0] × 100
  stage 2  Trajectory
           slots = last window non-null base values; trend = compare(first, last)

KNOWN DEFECT in the platform's own wording
  ... the slots actually hold the SPREAD series, not the base metric.
  The text above is stored exactly as BattleGrid returns it.

EFFECTIVE           source: data/contract/columns/_contracts.json
  {'window': 4, 'inputs': [{'metric': 'EMA13'}], 'bars': 'all'}
  These are what the platform APPLIED, not what was requested.

VALUES              source: data/contract/columns/_renders*.json
  BTC    ..._t3=0.64  ..._t2=0.83  ..._t1=0.79  ..._now=0.82  ..._trend=rising
```

**`explain` computes nothing** — a test asserts no arithmetic appears in the module. For a
column nobody has probed it prints the transform formula (always known, from the authoring
contract) and says the rest is *not captured*, pointing at `omega.probe.FETCH_RECIPE`. It
never fills the gap: a plausible number is indistinguishable from a measured one once it is
rendered as text.

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


## Two rules gate the whole space (measured 2026-08-24)

### 1. `spread` is within-unit-class only

Every metric carries a unit, and `spread` refuses any pair that crosses units. The
whitelist is not a lookup table — it is dimensional analysis, enforced. Eight cliques,
608 ordered pairs (ordered because the denominator differs: `A spread B` is not
`B spread A`):

| unit | metrics | ordered pairs |
|---|---:|---:|
| price | 18 | 306 |
| percent | 15 | 210 |
| oscillator | 7 | 42 |
| signedPrice | 5 | 20 |
| largeCount | 5 | 20 |
| count | 3 | 6 |
| fraction | 2 | 2 |
| usdLargeCount | 2 | 2 |

Price and percent are 85% of the surface. This is also why several standard
constructions are unreachable: Amihud illiquidity is `percent ÷ largeCount`, average
trade size is `largeCount ÷ count`. Cross-clique edges do not exist.

### 2. A spread chains only when its base metric has a stored bar series

| class | chains | does not chain |
|---|---|---|
| price | CLOSE OPEN HIGH LOW VWAP EMA5 EMA13 EMA20 SMA20 SMA50 SMA200 SWING_HIGH SWING_LOW | MARK LAST ORACLE SPOT_CLOSE_CB SPOT_CLOSE_BN |
| percent | PPO ROC12 ATR_PCT BB_WIDTH_PCT CLOSE_CHANGE | CHG_5M CHG_15M CHG_1H CHG_4H CHG_24H FUNDING_RATE FUNDING_ANN OI_CHG HIGH_DEV LOW_DEV |

The non-chaining ones are exactly the point-in-time reads. `MARK`, `LAST` and `ORACLE`
are documented as "read live at report build time — not a bar close"; `SPOT_CLOSE_*`
are venue snapshots; `CHG_*` are published values; `FUNDING_*` and `OI_CHG` sample on
their own schedule. No stored series means nothing for a window operator to consume.

**Consequence:** basis momentum (`MARK spread SPOT_CLOSE_CB → trajectory`) is *not*
buildable as one column. The basis is fine; its evolution is not.

A narrower rule governs the chain to `rank` — only `EMA5 EMA13 EMA20 SMA20 SMA50
SMA200 SWING_HIGH SWING_LOW VWAP` can spread-then-rank.

### 3. Only 31 of 86 metrics are rankable

No price-class metric is rankable directly — only through `distance → rank` on the 13
that chain. Among momentum metrics only `ROC12`, `PPO` and `CLOSE_CHANGE` rank; **the
`CHG_*` family cannot be ranked at all**, which matters because they are the obvious
choice for a cross-sectional momentum sort and they do not work.


## Blocked how: data absent, or operator absent?

Measured 2026-08-24. A trajectory on an unbound section beside the same column on a
benchmark-bound section returns **two time-aligned series in one render**:

```
SOL   0.48  -1.33  1.13  0.35  -0.42  -0.73  0.55  0.61  0.01  1.02  -0.01  0.46
BTC   0.89  -0.72  1.17 -0.57  -0.06  -0.39  0.22 -0.24  0.23  0.06  -0.31  0.04
```

From those rows: sigma(SOL)=0.717, sigma(BTC)=0.557, cov=0.256, **rho=0.642**,
**beta=0.827**. Every one is unavailable in the column layer, and every one is
computable from data the platform already printed.

So the blocked list splits four ways:

| cause | families | note |
|---|---:|---|
| data present, operator absent | 22 | `stddev` alone unlocks 5; `covariance` 6; `slope` 4 |
| operator present, unit guard refuses | 2 | Amihud, average trade size — ordinary divisions the clique rule rejects |
| needs recursive state, not a function | 2 | cumulative series, adaptive MAs |
| data genuinely absent | 1 | historical cross-sectional rank — the ranked set holds current values only |

Plus a soft ceiling that is neither: the 32-bar lookback cap. A 12-period correlation
is reachable; a 200-period one is not.

**The distinction that matters for design.** If a number is needed for a *deterministic
gate*, it must be a column, so the Class-A statistics genuinely cannot gate anything.
If it is needed for the *agent's reasoning*, ship the trajectory slots and let the model
compute it — cost is header width and tokens, nothing else.

That is consistent with the platform's own framing: conditions are "deterministic reads
… advisory: they may make you more selective, never less." The reasoning was always the
agent's job; the column layer's job is to put legible quantities in front of it, and a
trajectory of returns is a legible quantity.
