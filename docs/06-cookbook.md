# 06 · Cookbook

Recipes that compile, and the traps that don't.

---

## Recipes

### Normalised stretch — "how far, relative to peers"

Raw distance is comparable across assets (it's a percentage); its *ordinal* tells you
whether this coin is the outlier right now.

```json
{"metric":"VWAP","transformId":"distance","timeframe":{"rel":"anchor"}}
{"metric":"VWAP","transformId":"distance","chainedTransformId":"rank",
 "timeframe":{"rel":"anchor"},"ordering":"far"}
```
→ `dist_VWAP`, `dist_VWAP_rank_far`

Swap `VWAP` for any of `SMA20 SMA50 SMA200 EMA5 EMA13 EMA20 SWING_HIGH SWING_LOW`. Those
nine — the moving averages, the swings and VWAP — are the **only** metrics whose `distance`
chains into `rank`, and they allow all four orderings.

`OPEN HIGH LOW CLOSE` and the timeless price reads (`LAST MARK ORACLE SPOT_CLOSE_*`) offer
`distance` but **not** `distance → rank`: a bar's own extreme isn't a reference level the
platform ranks a universe against.

### Impulse vs chop — was the move clean?

```json
{"metric":"CLOSE","transformId":"efficiency","timeframe":{"rel":"lower"},
 "window":6,"bars":"closed"}
```
→ `close_ltf_er`, a fraction in [0,1]. 1 is a straight line, near 0 is chop.

Efficiency is the most underused transform in the catalogue — it separates *"price moved
3%"* from *"price moved 3% in a straight line"*, which is usually the distinction that
matters. Remember `window` counts **points**: N moves needs `window` N+1.

### Momentum trajectory with an honest read

```json
{"metric":"RSI14","transformId":"trajectory","timeframe":{"rel":"anchor"},
 "window":4,"bars":"closed"}
```
→ `RSI14_t3 RSI14_t2 RSI14_t1 RSI14_now RSI14_trend` (5 headers)

`bars:"closed"` excludes the forming bar. On an oscillator this matters less than on a
volume metric, but it makes the series comparable bar-to-bar.

### Fast/slow separation, and its rank

```json
{"metric":"EMA5","transformId":"spread","chainedTransformId":"trajectory",
 "timeframe":{"rel":"anchor"},"inputs":[{"metric":"EMA13"}],"window":5}
{"metric":"EMA5","transformId":"spread","chainedTransformId":"rank",
 "timeframe":{"rel":"anchor"},"inputs":[{"metric":"EMA13"}],"ordering":"far"}
```

`EMA13` is the **only** operand that chains into `rank` here
(`rankableSpreadOperands: ["EMA13"]`). Any other operand is rejected.

### Funding pressure over a window

```json
{"metric":"FUNDING_RATE","transformId":"aggregate","timeframe":{"rel":"anchor"},"window":24}
```
→ `rate_mean24`

`aggregate` computes a **mean** and nothing else — there is no sum/min/max variant. Only
`FUNDING_RATE`, `OI` and `SPOT_CVD` offer it directly (others reach it via chaining).

**This column forces its section to have no `timeframe` override.**

### Concentration — was it one bar or many?

```json
{"metric":"TRADES","transformId":"maxShare","timeframe":{"rel":"anchor"},
 "window":24,"bars":"closed"}
```
→ `trades_maxShare` in [0,1]. 1 means one bar carried everything; 1/24 is perfectly even.

A clean way to distinguish a single print from sustained participation.

### Room to structure

```json
{"metric":"STRUCT_ZONES","transformId":"nearestZoneDist","timeframe":{"rel":"regime"},"side":"support"}
{"metric":"STRUCT_ZONES","transformId":"nearestZoneAge","timeframe":{"rel":"regime"},"side":"support"}
{"metric":"STRUCT_ZONES","transformId":"count","timeframe":{"rel":"regime"}}
```

`side` is **required** on every `nearestZone*` transform. Pair distance with age — a zone
detected 40 hours ago is a different object from one detected 40 minutes ago.

### Band proximity without Bollinger columns

```json
{"metric":"OPEN","transformId":"bandTouch","timeframe":{"rel":"anchor"}}
```
→ `open_touch` ∈ `upper | lower | none`

`bandTouch` is authorable on the **13 candle-backed** price-unit metrics — `OPEN HIGH LOW
CLOSE`, the six moving averages, both swings and `VWAP` — and used by **zero** platform
templates. The five timeless price reads (`LAST MARK ORACLE SPOT_CLOSE_CB SPOT_CLOSE_BN`)
don't offer it: bands are computed on a candle series. If you want something the preset
sections don't give you, start here.

---

## Traps

### 1. The forming bar ramps from zero

`bars` defaults to `"all"`, which includes the live forming bar. On `VOLUME`, `TRADES`,
`BUY_VOLUME`, `SELL_VOLUME`, `BUY_TRADES`, `SELL_TRADES` the forming bar's quantity climbs
from zero across the interval, so every fresh bar reads as a participation collapse.

**Fix:** `bars: "closed"` on any raw per-bar quantity. `omega.validate` raises
`FORMING_BAR_RAMP`.

### 2. Raw base-unit volume is not comparable across assets

44,723 BTC beside 2,100,000 DOGE compares *denominations*, not activity. This is why
`VOLUME` has no `rank` at all.

**Fix:** use `RVOL` (a ratio) for cohort columns; keep raw `VOLUME` for single-coin
thresholds only.

### 3. Ranking a price level

Same disease. An ordinal over a price sorts by token denomination — BTC wins every bar.
The engine refuses.

**Fix:** rank the *composition*: `VWAP × distance × rank`, not `VWAP × rank`.

### 4. `rank` orderings are per-metric policy

`CLOSE_CHANGE` offers only `far`/`near`; `FUNDING_RATE` — also signed — offers all four.
There is no rule you can derive from sign or range. Check `rankOrderings`.

### 5. Mixing timeless metrics into a pinned section

One `FUNDING_RATE` column silently invalidates a section's `timeframe` override.

**Fix:** two sections — one pinned and fully candle-backed, one on the anchor.

### 6. Correlated oscillators are not independent evidence

The platform says this outright: *"Stacking several correlated oscillators as independent
evidence."* `RSI14`, `RSI7`, `STOCH_K`, `STOCH_D`, `MFI14`, `CCI20` largely agree. Six
oscillator columns is one piece of evidence at six times the token cost — and if you then
allocate weight to six oscillator signals, you have six-counted a single observation.

**Fix:** one or two oscillators, then spend the budget on an *independent* axis — flow,
derivatives, structure.

### 7. Trajectory windows eat the token budget

32 columns × `window: 8` = 288 headers from one section.

**Fix:** run `omega.fanout.cost_report` before submitting. Reserve wide trajectories for
the two or three series whose *shape* matters; read the rest with `value`.

### 8. Weighting a signal your report doesn't feed

A `NOT_IN_REPORT` signal never fires, so it never enters the aggregate — it
actively suppresses your aggregate.

**Fix:** `derive_strategy_rule_view` after report design, before allocation.

### 9. Assuming header names

`CLOSE_CHANGE` → `closeChg`, and `rel:lower` inserts `_ltf_`. Conditions reference headers
by name.

**Fix:** `omega.fanout.outputs_for()` predicts them; `get_strategy_column_contract` confirms.

### 10. Silent nulls

A flat series has no `efficiency` (null, not 0). A zero-total window has no `maxShare`.
`spread` nulls when the *second* operand is zero. Nulls render as `—` and your conditions
must decide what that means — an absent reading is not a low reading.

---

### 11. Two columns, one header — and the section goes dark

`offset` changes a column's **value** and never appears in its **header**. So two
`RSI14 × value` columns at `offset: 0` and `offset: 3` compile to the same header.

The platform does not stop you. It renders both:

```
| coin | RSI14 | RSI14 |
| BTC  | 62.7  | 67.8  |
```

…and then **omits the whole section from `conditionColumns`**. The agent still reads the
table; no condition can reference any column in it. No error, anywhere.

Verified live in `data/contract/columns/_renders_collision.json` — in every other capture
`conditionColumns[0]` is the custom section; in that one it starts at `session-field`.

`omega.validate` now raises `DUPLICATE_HEADER` before you get near the platform. If you
need the same metric at two offsets, they must differ in something the header carries —
a different transform, timeframe rel, or operand.

### 12. `_trend` is computed on values you cannot see

A `trajectory` column emits its slots (`_t2`, `_t1`, `_now`) at the metric's declared
display precision, but `_trend` is derived from the **unrounded** series. The two can
disagree, and the table gives you no way to tell.

Measured live on 2026-08-24, DOGE at 1h:

| RSI14_t2 | RSI14_t1 | RSI14_now | RSI14_trend |
|---|---|---|---|
| 38.3 | 39.7 | 38.3 | **falling** |

`_t2` and `_now` print identically, so the slots imply `flat`. The platform says
`falling`, and the platform is right — RSI is displayed at `precision: 1`, and the true
endpoints differ below that.

**Fix:** never recompute a direction from rendered slots, and never write a condition
that reconstructs one. Read `_trend` directly — it is the only place the unrounded
comparison is exposed. The same applies to any derived column beside its own inputs:
the residuals in doc 15's verification panel are display rounding, not error, and they
grow as the metric's precision shrinks (DOGE's 4-decimal price gives a 0.03pp residual
on `spread` where BTC's gives 0.002pp).

### 13. Two zone columns that cannot carry a condition at all

Every `classifyZone` column declares the same `conditionVocabulary`:

```
["overbought", "oversold", "neutral"]
```

Two of the five never emit any of those. Measured across 12 coins on 2026-08-24:

| column | declared | actually emits | in vocabulary |
|---|---|---|---|
| `ADX_zone` | overbought / oversold / neutral | `trending`, `developing`, `weak` | **0 of 12** |
| `MFI14_zone` | overbought / oversold / neutral | `bearish`, `bullish` | **0 of 12** |
| `RSI14_zone` | " | `neutral` | 12 of 12 |
| `RSI7_zone` | " | `neutral`, `oversold` | 12 of 12 |
| `K_zone` | " | `neutral`, `oversold` | 12 of 12 |

So `ADX_zone is "neutral"` is **permanently FALSE** — not an error, not `UNRESOLVED`,
just a clean-looking condition that never fires.

And you cannot fix it by using the label the column actually shows. The platform
refuses that:

```
CONDITION_LITERAL_UNSUPPORTED
'trending' is not a value 'ADX_zone' can take — its vocabulary is
overbought | oversold | neutral.   Nearest canonical key: 'oversold'
```

**Both directions are closed.** Every label that would work is rejected at
validation; every label that is accepted reads FALSE forever. `ADX_zone` and
`MFI14_zone` are display-only: fine to render for an agent to read, impossible to
condition on.

**Fix — threshold the numeric column instead.** Verified live on BTC / SOL / XRP,
and it reproduces the zone exactly:

| coin | `ADX` | `ADX_zone` | `ADX lt 20` | `MFI14` | `MFI14_zone` | `MFI14 lt 50` |
|---|---|---|---|---|---|---|
| BTC | 21.9 | developing | FALSE | 42.8 | bearish | TRUE |
| SOL | 15.7 | weak | TRUE | 63.8 | bullish | FALSE |
| XRP | 10.8 | weak | TRUE | 43.4 | bearish | TRUE |

```
ADX_zone is "trending"   ->   ADX   gte 25
ADX_zone is "weak"       ->   ADX   lt  20
MFI14_zone is "bearish"  ->   MFI14 lt  50
MFI14_zone is "bullish"  ->   MFI14 gte 50
```

Those cutoffs are **consistent with** the observations, not extracted — the zone
thresholds are published nowhere. They match the conventional ADX 20/25 and MFI 50
midline, so treat them as a starting point and re-measure at an edge.

`omega.conditions.validate_conditions` refuses these clauses offline and names the
replacement, so you cannot author one by accident.

### 14. `CROWD × rank` compiles and never renders

Every crowd metric declares `transforms: ["rank", "value"]`. The rank column
compiles cleanly — `get_strategy_column_contract` returns `crowdAcc_rank_hi` with a
full formula — and then returns `INTERNAL_ERROR` on every render. Tested at 1 coin
and 10, ordering `hi` and `lo`, with complete non-null crowd data on every coin.

The contract hints at why. Crowd ranks are the only ones documented as *"ordinal
across THIS REPORT's coins … computed per request"*; every other rank reads the
tracked universe. The per-request path is the one that fails.

**Fix:** use `CROWD_* × value` and threshold it. Crowd metrics are already
cross-coin-comparable percentages, so unlike `VOLUME` they need no normalising —
ranking adds nothing a threshold cannot say. Verified: `crowdAcc between 60 and 100`
resolved UP on SOL (88.9) and XRP (100.0), NEITHER on BTC (40.0).

### 15. `offset` is invisible in the header, so a lag cannot sit beside its own present

`value` accepts `offset`, which reads the metric N bars back. But the header carries
only the metric code — `CLOSE × value` emits `close` at every offset. Two `value`
columns on one metric therefore collide, the section is dropped from
`conditionColumns`, and every condition on it goes `UNRESOLVED` (trap 11).

So you **cannot** put `close` and `close 12 bars ago` in one section and difference
them with a condition. `omega.validate` raises `DUPLICATE_HEADER` before you try.

Two real routes to the same idea:

- `trajectory` — emits `_t3 … _t1 _now` as *distinct* headers, so the history is
  addressable. This is the supported way to compare now against then.
- separate sections — headers only collide within a section, and a condition clause
  can name a `sectionKey` explicitly. Costs a second section and a second lookback
  budget.

And mind the ceiling: lookback is `window + offset` capped at 32, and a plain `value`
carries an implicit window of 24. **The largest usable offset is 8**, not the 64 the
schema advertises.

### 16. A null value reads FALSE, so "missing" and "wrong" are the same answer

The platform documents three outcomes and says so in every conditions block:
*"UNRESOLVED means an input was missing, not that the read was false."* Measured, a
null column value does not produce it.

`crowdAccLive` renders `—` whenever no concurrent sessions are running. The clause
`crowdAccLive gt 50` returns **FALSE**, evidence `operand: "—"`, and the group's
`unresolvedCount` stays at `0`.

**Fix:** on any nullable metric, never let a bare threshold stand for presence. Pair it
with a second clause that establishes the data exists, or prefer a metric that is
always populated. Nullable ones to watch: every `CROWD_*_LIVE`, and the venue closes
`SPOT_CLOSE_CB` / `SPOT_CLOSE_BN`, which the contract says are absent when older than
15 minutes.

### 18. Indicators include the forming bar, so they repaint

Measured 2026-08-25: SMA20 over closed bars was 78376.90, and the rendered value was
**78477.35** - the mean including the bar still in progress. All five indicators tested
(SMA20, EMA5, EMA13, RSI14, ATR) matched the closed-plus-forming set exactly and none
matched closed-only.

So `RSI14 lte 35` can read TRUE at :10 and FALSE at :50 within one bar, with nothing
having closed. If a condition needs to be stable, set `bars: "closed"` on the column.
The contract has always offered it; this is the reason to use it.

Evidence and method: [19 - Is the data correct?](19-is-the-data-correct.md).

**One exception: `rank` does not repaint.** Its header states *"the standing as of the
last close, unchanged until the next one."* Rank columns are stable within the bar;
`value`, `trajectory`, `aggregate` and the rest are not.

### 17. A legal spread whose operands differ by orders of magnitude

`spread` is `(A - B) / B x 100`. That is only informative when A and B are of comparable
size. The unit-clique rule guarantees they are the *same kind* of quantity; it says
nothing about scale.

Measured live on BTC / SOL, all legal, all rendering:

| column | BTC | SOL | why |
|---|---|---|---|
| `rate_chg24h_spread` | -99.91% | -99.95% | funding ~0.0013% vs 24h change ~1.4% |
| `rate_atrPct_spread` | -99.84% | -99.91% | funding vs ATR% |
| `oiChg_PPO_spread` | -2115% | +2948% | PPO near zero, so the ratio explodes |
| `highDev_lowDev_spread` | -343% | -806% | upside vs downside excursion |
| `OBV_volBase_spread` | -956% | -60% | cumulative OBV vs a single bar's volume |

When `A << B` the result pins near -100%; when `B` approaches zero it explodes. Neither is
a bug, and neither is readable as "the percentage gap" in the way `EMA5_EMA13_spread`
(+0.21%) is.

**Fix:** pair operands of similar magnitude - `EMA5` vs `EMA13`, `RSI14` vs `RSI7`,
`STOCH_K` vs `STOCH_D`, `HIGH` vs `LOW`. Where you want two quantities of different scale,
ship them as separate columns and let a condition compare each to its own threshold.

### 19. `rank` is scoped to the whole market, not your coin selection

Measured 2026-08-25. A five-coin preview returned ranks of `36/78`, `48/78`, `25/78` —
against a universe of **78**, not 5. The response says so explicitly:

> Rank columns reflect the full active market, not the previewed coin selection — a coin
> may show a rank higher than the number of rows shown.

So every cross-sectional construction — carry factor, cross-sectional momentum, any
`rank`-based family in the census — is ranking against the entire active market
regardless of how many coins your strategy actually reads. A gate like
`atrPct_rank_hi lte 8` means *top 8 of 78*, not top 8 of your shortlist. If your section
selects 10 coins, that gate may match none of them.

Two consequences worth internalising:

- **You cannot build a within-selection ranking.** There is no scoping parameter. If you
  need "the most volatile of the coins I am looking at", `rank` will not give it to you.
- **Rank thresholds do not scale with your selection.** Widening or narrowing the coin
  list changes nothing about what the rank column returns.

The universe size is rendered alongside the rank (`n/78`), so a condition can be written
against the denominator rather than assuming it — but the denominator itself moves as
coins are listed and delisted.

**This holds at every rung, and the platform's own table preamble says otherwise.** For
`atrPct_ltf_rank_hi` and `atrPct_htf_rank_hi` the preamble claims *"ordinal across THIS
REPORT'S coins … rank/report-size"*, while `conditionColumns` for the very same header
says *"across the tracked universe"*. Measured with an explicit two-coin selection, both
rendered `/78`. The values agree with `conditionColumns`; the preamble is wrong. Trust
the denominator you can see, not the prose above the table.

### 20. A duplicate header renders, but silently loses conditionability

`offset` is **not** part of the header name. Two columns differing only by offset collide:

```
| coin | ... | close_trend | SMA20 | SMA20 |
| BTC  | ... | rising      | $78215.50 | $78469.20 |
```

Both rendered. Both carry different, correct values. And `conditionColumns` for that
section listed **seven** outputs — `close_t5` through `close_trend`. Neither `SMA20`
appeared in it.

The table looks right, and the agent reading it as text sees both numbers. But a
condition referencing `SMA20` has nothing to bind to. Pair that with trap 11 — a null
read is FALSE, never UNRESOLVED — and the gate fails **silently, as a real negative**.

`SMA20` on its own appears in `conditionColumns` normally, so the metric is fine; the
collision is what removes it.

**Fix:** never place two columns in one section whose headers would match. `omega.fanout`
predicts the header, so check before you build — `scripts/family_probe.py` already
enforces exactly this when it packs batches.

### 21. Daily-anchored metrics are null off-crypto, and null reads FALSE

Non-crypto tickers on this platform **are perpetuals** — GOOGL, GOLD and SP500 all carry
funding, open interest and a mark price. What they do not carry is anything the platform
accumulates *since the daily 00:00-UTC anchor*:

| null off-crypto | renders off-crypto |
|---|---|
| `CVD`, `SPOT_CVD`, `OBV`, `VWAP` | `BUY_VOLUME`, `SELL_VOLUME`, `BUY_TRADES`, `SELL_TRADES`, `BUY_PRESSURE` |
| `SPOT_CLOSE_CB`, `SPOT_CLOSE_BN` | `VOLUME`, `RVOL`, `SWING_HIGH`, `REGIME_*`, `STRUCT_ZONES` |
| `PERP_SPOT_FLOW`, `_STRENGTH`, `_CONFIRMS` | funding, open interest, every classical indicator |

Measured across STOCKS, TRADFI, INDICES and COMMODITIES. **The rule is the daily anchor,
not order flow** — the per-bar buy/sell split renders fine; only the cumulative
accumulators are absent.

Six of the 46 buildable families are affected: `vwap-deviation`, `stretch-ranking`,
`obv-divergence`, `perp-spot-cvd`, `venue-dislocation`, `basis`.

They do not error. They render `—`, and **a null reads FALSE, never UNRESOLVED**
(trap 11). So a strategy whose coin selection spans crypto and non-crypto gates those
families silently wrong, and the scorecard looks fully populated while it is answering
from absence of data. `NOT` is the sharp edge again: a negated VWAP gate fires on every
stock in the pool.

**Fix:** either keep the coin selection inside one asset class, or pair any
daily-anchored column with an `ALL` guard on a per-bar column that is never null.

### 22. The stated formula for `nearestZoneDist` has the wrong sign

`transforms/_authoring.json` says:

```
output = ((price - midpoint(nearest zone)) / midpoint(nearest zone)) x 100
```

The engine computes `((midpoint - price) / price) x 100`. **The sign is inverted and the
denominator is price, not the midpoint.** BTC: support zone 77859–77923, midpoint 77891,
close 78883. Stated formula → **+1.3%**. Rendered → **−1.2%**. All three probed coins
render negative where the stated formula is positive.

The header prose — *"signed % from price to the nearest support zone midpoint"* — matches
the engine. Only the machine-readable formula is wrong. Build from the prose, and read
the value as **negative when price is above support**.

### 23. `ROC12` renders a fraction while its label says percent

Measured on three coins with the 12-bar reference visible in the same table:

| coin | close 12 bars ago | close now | as a fraction | as a percent | **rendered** |
|---|---:|---:|---:|---:|---:|
| HYPE | 79.76 | 79.91 | +0.00188 | +0.19% | **+0.00%** |
| ZEC | 836.45 | 843.69 | +0.00866 | +0.87% | **+0.01%** |
| BTC | 79,755 | 78,967 | −0.00988 | −0.99% | **−0.01%** |

The column meaning says *"rate of change vs 12 bars ago (%)"*. **The value is the raw
ratio — one hundred times smaller than the label claims.**

HYPE also rules out the obvious alternative, that the lookback is longer than 12: its
15-bar change is +2.50%, nothing like the rendered +0.00%.

**A threshold written from the label is wrong by 100×.** `ROC gt 2` meaning "up 2 percent"
has to be `ROC gt 0.02`. And because the value is *small* rather than *absent*, the gate
does not error — it just never fires, or always fires, depending on direction.

`PPO` sits in the same module, in the same table, and **is** a percent — measured
−0.2477 against a rendered −0.25. So this is not a house convention applied consistently;
`ROC12` is the odd one out. The `rel_roc_positive` and `rel_roc_negative` scorecard
signals read this metric.

### 24. There is no way to gate on crowd-data freshness

The `CROWD_*` block reports over *"the last 4 settled sessions"*. Whether that is an hour
old or a month old is carried by exactly one column — `SETTLED_AT` — and

```
SETTLED_AT  ->  conditionOperators: []
```

It cannot be referenced by any condition. Measured 2026-08-25, `SETTLED_AT` read
**2026-07-24**: the crowd numbers beside it were 32 days old, and nothing in those columns
said so.

The staleness is likely account state — no sessions had settled recently. The structural
problem is that you cannot *detect* it from inside a strategy. Pair that with trap 11 —
a null reads FALSE, never UNRESOLVED — and a `crowdAcc gte 60` gate answers confidently
from month-old evidence with no guard available.

**Fix:** treat every `CROWD_*` column as advisory context for the agent to read, not as a
deterministic gate. If you must gate on one, accept that its freshness is unknowable at
evaluation time.

### 25. Some categorical labels have never been observed to occur

A `conditionVocabulary` lists what a column *may* emit, not what it *does*. Sampling 25–30
coins found six columns where part of the vocabulary never appeared:

| metric | seen | never seen |
|---|---|---|
| `CONFIDENCE` | high, moderate | low |
| `OI_VELOCITY` | accelerating, decelerating, steady | — *(all observed)* |
| `PERP_SPOT_CONFIRMS` | false, true | — *(all observed)* |
| `PERP_SPOT_FLOW` | neutral, spot_led_accumulation, confirmed_bear | confirmed_bull, perp_led_fragile |
| `PRICE_ZONE` | near low, mid-range, near high | breakout high, breakdown low |
| `REGIME_VOL` | normal, expanding | contracting |

None of this proves a bug — rare labels are rare. But a gate on a label that never occurs
reads FALSE forever without telling you it is inert (trap 11), and a `NOT` around it fires
*always*.

> **Three labels came off this list by re-anchoring, and that is the lesson.** Sweeping
> the same 78 coins across 5m / 15m / 1h / 4h closed `PERP_SPOT_FLOW confirmed_bear` and
> `PERP_SPOT_CONFIRMS true` — both visible **only at 5m**, on six coins, having read
> `false` 24 of 24 at 1h. `REGIME_VOL expanding` had come off the same way earlier.
> None was rare; the *sampling* was single-anchored.
>
> **But re-anchoring has a ceiling.** It surfaces labels whose driver is
> timeframe-sensitive — flow rates decisive over 5 minutes wash out over 4 hours. It does
> not conjure a market state: `PRICE_ZONE`'s extremes need price *outside* its swing
> range, and across 78 coins × 4 anchors nothing was. Six values remain unobserved and
> more anchors will not produce them. See
> [`_anchorSweep`](../data/audit/tier_c_coherence.json).

**Before gating on a categorical label, sample 25+ coins — and vary the anchor as well as
the coin — to confirm the value actually occurs.** `PRICE_ZONE` is the cautionary case in the other direction too: its rule is
**not** the position between `SWING_HIGH` and `SWING_LOW`, despite looking exactly like
that on a three-coin sample — see [19](19-is-the-data-correct.md).

### 26. A timeframe-inert metric takes the anchor reference and nothing else

40 of the 86 metrics are `timeframe-inert` — `REGIME_*`, `OI*`, `CROWD_*`, `FUNDING_*`,
`CHG_*`, `FLOW_ALIGN`, `SMART_RETAIL`, `CONFIDENCE`, `PERP_SPOT_*` and the rest. Their
column `timeframe` must be the literal `{"rel":"anchor"}`. `rel:"lower"`, `rel:"regime"`
and any `abs` are refused — **including an `abs` equal to the anchor**, so the rule is
syntactic rather than semantic.

They still follow the report anchor: `REGIME_MOM` changes on 8 of 10 coins between a 5m
and a 4h render taken seconds apart. What they refuse is a *second* timeframe on top of
the report's.

The trap is a different one, and it survives the above. A `REGIME_*` label can flatly
contradict the momentum columns rendered beside it at the same anchor. AMZN at 1h:
`regMom` **bullish**, while ROC, PPO, MACD, `chg4h` and `chg24h` are *all* negative and
RSI14 sits at 37.3. An exhaustive search over every rule those columns can express got
69% against a 65% mode baseline — so **the classifier is not reading them**, and what it
does read is not exposed.

**Don't write `regMom is bullish AND rsi14 > 55` and call it a confirmation pattern.**
The two clauses are not two views of one quantity; the first is a black box, and the
sample above shows it disagreeing with the second outright.

### 27. `offset` is silently ignored by every categorical candle metric

`offset` walks a column back N bars. It works — on numbers. On a **categorical**
candle-backed metric it is accepted, it spends `offset` of your 32-bar `columnLookback`
budget, and the column answers for **now** anyway. Nothing errors. Nothing warns.

Measured across 78 coins at a 4h anchor, offset 0 vs offset 8:

| honours `offset` | ignores it |
|---|---|
| `close`, `ADX`, `swingHi`, `swingLo`, `STOCH_K`, `MFI14`, `pctB` | `MA_ALIGN`, `BB_TOUCH`, `EMA_CROSS`, `PRICE_ZONE` |

`PRICE_ZONE` was identical on **78 of 78**. That alone would prove nothing — a label can
be stable. What proves it is that its own inputs moved in the same render:

| AMD @ 4h | `close` | `swingLo` | `swingHi` | position | `zone` |
|---|---:|---:|---:|---:|---|
| offset 0 | $480.70 | $451.62 | $482.33 | **94.7%** | near high |
| offset 8 | $460.95 | $451.62 | $477.94 | **35.4%** | near high ← |

At 35% of its range the honest answer is not "near high". It is the offset-0 answer.

**Reconstruct it yourself.** The numeric inputs at an offset are correct, and
`PRICE_ZONE`'s rule is known — percentage distance to the nearer swing
([19](19-is-the-data-correct.md)). `omega.validate` now raises `OFFSET_IGNORED` as a
warning rather than an error, because the column does render; it just answers about a
different bar than the one you asked for.

## Workflow

```
 1. sketch columns              omega.types.Column
 2. validate offline            omega.validate.validate_report      ← catches 1–5, 7, 9
 3. cost it                     omega.fanout.cost_report            ← catches 7
 4. confirm compilation         get_strategy_column_contract        ← confirms 9
 5. check signal membership     derive_strategy_rule_view           ← catches 8
 6. tune allocations            omega.aggregate + simulate_aggregate_score
 7. emit payload                omega.emit.emit                     ← writes to out/
 8. submit                      deliberate, human-initiated, separate
```

Steps 1–3 and 6–7 are offline and free. Steps 4–5 are read-only connector calls. Step 8 is
the only one that touches your account.
