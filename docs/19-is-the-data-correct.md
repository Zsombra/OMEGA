# 19 · Is the data correct?

Everything else in this repo verifies **consistency** — that `omega` predicts what
BattleGrid does. 300 of 300 column shapes, 46 of 46 indicator families, 25 of 25
platform sections. None of it would notice if the platform's RSI were secretly a
12-period, or if its prices were synthetic.

That is a different claim, and it needs a source outside BattleGrid.

Script: `scripts/verify_indicators.py`.
Evidence: `data/audit/candles_btc_1h_battlegrid.json`,
`data/audit/candles_btc_1h_hyperliquid_400.json`.

## Three questions, three methods

| question | method | what it catches |
|---|---|---|
| Is the tape real? | diff BattleGrid candles vs the Hyperliquid public API | synthetic feed, stale feed, wrong symbol, unit error |
| Is the maths right? | recompute SMA/EMA/RSI/ATR from the bars | wrong formula, window, or smoothing constant |
| Is a derived column arithmetically sound? | render operands beside the derived column | a broken transform |

## Tier 3 — the tape is real

BTC 1h, 60 bars, 2026-08-22T12:00Z → 2026-08-24T23:00Z.

```
OHLC identical              57 / 60
differing in CLOSE only      3
    worst close gap          0.0126%   (79,110 vs 79,120)
    open/high/low            never differ, on any bar
volume gap                   mean -0.3%, range [-10.3%, 0.0%]
```

Open, high and low match the exchange **exactly on every bar**. Only three closes
differ, by 1, 1 and 10 points on ~79,000 — that is a sampling instant, not a different
feed. Volume differs slightly and consistently in one direction, which means it is a
different *measure* of volume rather than a broken one.

Funding and open interest confirm the units, which is where a silent factor-of-100 bug
would live:

| | exchange | rendered | |
|---|---|---|---|
| BTC funding | `0.0000125` decimal | `+0.0013%` | `rate = funding × 100` ✓ |
| BTC open interest | 38,379 coins × $78,925 = **$3.03B** | **$3.0B** | USD notional ✓ |
| SOL open interest | 5,241,069 × $99.904 = **$0.52B** | **$520.4M** | ✓ |

SOL's funding read `0.0017%` against an exchange value of `0.002068%` fetched minutes
later. The platform describes `rate` as *"a point-in-time read at its own sample time"*,
and funding moves hourly, so a drift is expected — but this one is **not** verified to
the instant, only to unit and order of magnitude. BTC's matched to display precision.

## Tier 2 — the maths is textbook

Recomputed from 400 bars, using BattleGrid's own candles for the recent window and the
exchange tape for the deep history.

| indicator | rendered | closed bars only | closed + forming |
|---|---:|---:|---:|
| SMA20 | 78477.3500 | 78376.9000 | **78477.3500** ✓ |
| EMA5 | 78915.2300 | 78896.8390 | **78915.2260** ✓ |
| EMA13 | 78746.0200 | 78711.6900 | **78746.0200** ✓ |
| RSI14 | 58.1000 | 58.7383 | **58.0898** ✓ |
| ATR | 591.9472 | 632.6354 | **591.9472** ✓ |

**5 of 5, exact to four decimal places.** The formulas are standard: simple mean,
`α = 2/(n+1)` EMA, Wilder-smoothed RSI and ATR.

### Three indicators where two implementations are both defensible

Verifying that BattleGrid's SMA is a mean proves little — everyone's SMA is a mean. Three
of the thirty have genuinely competing conventions in the wild, so knowing *which one
ships* is information rather than a formality.

Each was read at `offset: 1` — these metrics reject `bars`, and an offset of 1 or more is
the documented escape from the forming bar — with a closed `CLOSE` trajectory beside them
to pin the exact anchor bar. Recomputed from 876 Hyperliquid bars ending on that bar.

| indicator | convention | computed | rendered | |
|---|---|---:|---:|---|
| **ADX** | Wilder's own smoothing | **24.88** | 24.90 | ✓ |
| | plain moving average of DX | 34.78 | 24.90 | rejected by 10 points |
| **CCI** | `0.015 ×` **mean absolute deviation** | **−39.27** | −39.30 | ✓ |
| | `0.015 ×` standard deviation | −35.13 | −39.30 | rejected by 4 points |
| **%K/%D** | **slow (14,3,3)** | **21.84 / 30.82** | 22 / 31 | ✓ |
| | fast (14,1,3) | 18.15 / 21.84 | 22 / 31 | rejected |
| | (14,3,1) | 21.84 / 21.84 | 22 / 31 | %K fits, **%D does not** |

None of these is a near miss. The rejected alternatives are wrong by 10 points of ADX and
4 points of CCI — enough to flip a `trend_adx_trending` gate at its 25 threshold, or a
`bollinger_cci_oversold` gate at −100.

The `(14,3,1)` row is the one that earns the table: it reproduces `%K` exactly and gets
`%D` wrong, which is precisely how a half-right convention hides. Testing `%K` alone would
have "confirmed" it.

**And the header declaration was accurate.** The column meaning states `%K (14,3,3)`, and
that is what the engine implements. Worth saying plainly, because BG-9 showed a published
formula that was wrong — the documentation here is not uniformly unreliable, it is
unreliable in specific places, and the only way to know which is to check.

That brings tier-B metric verification to **9 of 30** — SMA20, EMA5, EMA13, RSI14, ATR,
ADX, CCI20, STOCH_K, STOCH_D. The remaining 21 are single-definition indicators where no
competing convention exists to distinguish.

### The finding that matters for strategy design

Look at which column matched. **BattleGrid computes indicators on closed bars *plus the
forming bar*.** SMA20 over closed bars is 78376.90; the rendered value is 78477.35, and
that is the SMA *including* the bar still in progress.

That is not wrong, but it has a consequence nobody documents: **every indicator repaints
within the hour.** A condition reading `RSI14 lte 35` can be TRUE at :10 and FALSE at
:50 on the same bar, with no new bar having closed. If you want a stable read, set
`bars: "closed"` on the column explicitly — the contract offers it, and this is the
reason to use it.

## A false positive worth keeping

The first run of this script reported ATR as **4.8 low** — a clean-looking defect. It
was not. Wilder smoothing is an infinite-memory filter, and 60 bars is not enough for
the seed to wash out:

```
 bars used          ATR        gap
        61     587.1427    -4.8045
       100     592.2113    +0.2641
       200     591.9472    +0.0000
       400     591.9472    -0.0000
```

Sixty bars reads as a defect. Two hundred reads as an exact match. Same engine, same
rendered value. The script prints this table rather than hiding it, because *"the tool
disagrees with me"* and *"my window was too short"* look identical until you check —
and only one of them is the platform's problem.

## Tier 1 — the derived columns are arithmetically sound

The `-99%` readings on funding spreads are correct arithmetic, verified by rendering the
operands beside the result. `spread` is exactly `(A − B) / B × 100`.

But the audit surfaced something better than "the number is fine". Given that the
operands are *displayed rounded*, the interval each rendered spread must fall in is:

| column | rendered | range implied by the shown operands | width |
|---|---:|---|---:|
| `rate_atrPct_spread` | −99.83% | [−99.83%, −99.82%] | 0.02pp |
| `rate_chg24h_spread` | −102.30% | [−103.00%, −102.27%] | 0.73pp |

Both are consistent. But when the denominator sits near zero, display rounding is
amplified roughly 700× — so `rate_chg24h_spread` **cannot be audited from what the table
shows**, while `rate_atrPct_spread` can. That is a sharper reason to avoid near-zero
denominators than "the number looks strange", and it generalises: see cookbook trap 17.

Note also that the earlier claim that such a spread "pins near −100%" was incomplete.
When the denominator is *negative* it passes −100% — this render produced −102.30%.

## How far does the verification generalise?

Not as far as it looks, and the reason is worth stating plainly: **the metrics that can
be checked are the ones that were always easy to get right.** Anyone can compute an EMA.
Verifying it tells you little about the parts where a platform actually differentiates
itself — and those are exactly the parts with no outside referent.

All 86 metrics, by whether anything outside BattleGrid can settle them:

| tier | | count | verified |
|---|---|---:|---|
| **A** | a public exchange publishes it directly | 24 | OHLC, funding, OI checked |
| **B** | published formula over tier-A inputs | 30 | 5 of 30 checked, exact |
| **C** | no external referent | **32** | 0 — and not verifiable that way |

Mapped onto the scorecard, five modules are fed *only* by tier-C metrics:

| module | signals | fed by |
|---|---:|---|
| SUPPORT_RESISTANCE | 4 | `SWING_HIGH` `SWING_LOW` `PRICE_ZONE` |
| REGIME | 4 | `REGIME_TREND` `REGIME_VOL` `REGIME_MOM` |
| PRICE_STRUCTURE | 4 | `STRUCT_ZONES` |
| CVD | 4 | `CVD` `BUY_PRESSURE` `BUY_VOLUME` … |
| FLOW_DIVERGENCE | 2 | `SPOT_CVD` `PERP_SPOT_*` |

**18 of 84 signals rest entirely on inputs no outside source can check**, and 3 more
(OPEN_INTEREST, via `OI_VELOCITY` / `OI_PX_REGIME`) can. 63 rest on fully checkable
inputs.

## Tier C is not a closed door

"No external referent" is not the same as "uncheckable". A tier-C metric can still be
tested for **coherence against BattleGrid's own tier-A numbers**, and two such tests ran
on 2026-08-25 across BTC / ETH / SOL:

**`SWING_HIGH` and `SWING_LOW` are real bar extremes.** BTC read `swingHi 80,035` and
`swingLo 76,862`. Both land *exactly* on candles in the 60-bar window — the 15:00 high
and the 08:00 low. They are verifiable against the tape, so they leave tier C.

**The CVD volume split reconciles.** `buyVol + sellVol` against `volBase`, and
`buyPres` against `buyVol / volBase`:

| coin | buy+sell vs volume | buyTr+sellTr vs trades | buyPres check |
|---|---:|---:|---|
| BTC | −0.42% | −0.05% | 0.303 vs 0.30 ✓ |
| ETH | +1.37% | +0.30% | 0.452 vs 0.45 ✓ |
| SOL | +0.07% | +0.07% | 0.440 vs 0.44 ✓ |

`buyPres` is exactly `buyVol / volBase` on all three. The residuals are small and
**mixed in sign** — not a systematic bias, which is what a real double-count or a unit
error would produce. They are consistent with the components being sampled at slightly
different instants inside the forming bar, the same "own sample time" the platform
documents for funding and OI.

What that leaves genuinely irreducible is the game state: the nine `CROWD_*` metrics,
`SMART_RETAIL`, `CAPTAIN_CONF`, `CONFIDENCE`, `FLOW_ALIGN`. These have no referent even
in principle — they *are* BattleGrid. Their correctness is not a measurable property,
only their internal consistency over time is.

## Tier C — coherence, which is weaker evidence and worth saying so

The 32 tier-C metrics have no external referent, so the Hyperliquid method cannot touch
them. But *no external referent* is not *uncheckable*: most can be tested against
BattleGrid's own tier-A numbers, or against each other.

**Read these verdicts as weaker than the ones above.** Coherence shows a metric is
consistent with its stated definition and its neighbours. It cannot show a classification
is *correct* — a regime classifier can be perfectly self-consistent and still wrong about
the regime.

Record: `data/audit/tier_c_coherence.json`. Guard: `tests/test_tier_c_coherence.py`.

### Coherent

| metric | invariant that held |
|---|---|
| `CVD` | ΔCVD per bar **=** `BUY_VOLUME − SELL_VOLUME`, in base-asset units, daily-anchored |
| flow split | `buy+sell` reconciles to `VOLUME`/`TRADES`; `BUY_PRESSURE` = `BUY_VOLUME/VOLUME` exactly |
| `SWING_HIGH/LOW` | real bar extremes from the tape |
| `STRUCT_ZONES` | a real three-bar FVG, exact on both bounds |
| `OI_PX_REGIME` | the classic four-quadrant OI-vs-price read, 2 of 2 |
| `CROWD_*` | percentages in range, and `upBias`/`crowdAcc` share a denominator — SOL's 22.2% and 88.9% are **2/9 and 8/9** |
| `FLOW_ALIGN` | sign(**last-bar** CVD delta) vs sign(`upBias − 50`), 4 of 4 |
| `SMART_RETAIL` | sign(`buyPres − 0.5`) vs sign(`upBias − 50`), **13 of 13** |

`CVD` accumulates in **base-asset units** despite a declared unit class of `signedPrice`.
That is an observation, not a defect — the unit *tag* drives the spread-clique guard, and
`SPOT_CVD` shares the class, which is exactly what the perp-spot family needs.

### Resampled — and one verdict went the wrong way

Most of the first pass's "not verifiable" verdicts were **"not verifiable from two or
three coins"**, which is a different claim. Re-run against 30 coins (regime block) and 25
(flow block). Three verdicts improved. **One got worse, and it was mine.**

#### `PRICE_ZONE` — downgraded from "coherent"

The first pass called it coherent **3 of 3** on a three-coin render. Thirty coins produce
**31 inverted pairs** under position ordering:

| | position between swings | label |
|---|---:|---|
| XRP | 10.0% | mid-range |
| ETH | 22.2% | **near low** |
| AAPL | 49.4% | **near high** |
| SKHX | 86.4% | mid-range |

ATR-normalised distance is no better — 32 inversions to the high, 40 to the low. **No
candidate ordering separates the labels.**

That was a small-sample artifact: the exact error this document criticises elsewhere,
committed in this document. Three points cannot distinguish a rule from a coincidence
when the labels are ordered and the sample is tiny. A practical consequence: the swings
`PRICE_ZONE` references **may not be** the `SWING_HIGH`/`SWING_LOW` columns rendered
beside it.

#### `SMART_RETAIL` — solved, 13 of 13

`sign(buyPres − 0.5)` against `sign(upBias − 50)`. Agreement → `confirmed`; bullish flow
with bearish crowd → `hidden accumulation`; the reverse → `hidden distribution`. Null when
either side sits too near neutral — the 12 nulls sit at neutrality distance 0.00–0.20 and
every non-null at 0.20–0.76.

#### `FLOW_ALIGN` — refined to the actual proxy

Not `BUY_PRESSURE` (that fits only 13 of 25) and not the multi-bar CVD trend. It is the
**last-bar CVD delta**. PENGU discriminates: its `CVD_trend` reads "falling" across the
window while its last bar rose **+12.8M**, and `FLOW_ALIGN` reports "divergent" against a
0% bullish crowd. 4 of 4.

> **A contradiction that turned out to be mine.** AVAX shows `buyPres 0.61` — net buying,
> so a positive CVD delta — beside a CVD delta of **−623**. Different *bars*: `buyPres` is
> a plain `value` read and lands on the forming bar, while my CVD trajectory was pinned
> with `bars: "closed"`. So "different proxy" and "different bar" cannot be separated from
> this evidence, and neither is claimed.

#### `REGIME_TREND` — the "stuck" concern is closed

18 "trending up", 6 "trending down", 6 "ranging". Three distinct values; the first pass's
3-of-3 was coincidence. `REGIME_MOM` varies across all four of its labels too.

What survives is stranger. Of 24 directionally-labelled coins the label agrees with the
sign of the 24h change **7 times — 29%**. "Trending up" coins are 72% negative on the day.
**Caveat that matters:** these are 30 coins at *one instant in one market*, so they are
not independent observations — a broadly red day with an up-trending longer horizon
produces exactly this. No significance is claimed and it needs a repeat on another day.

### Labels never observed

Not evidence of a bug — a label can be rare and correct. But a gate written against one of
these has never been seen to fire:

| metric | seen | never seen |
|---|---|---|
| `CONFIDENCE` | high, moderate | low |
| `OI_VELOCITY` | accelerating, decelerating, steady | — *(all observed)* |
| `PERP_SPOT_CONFIRMS` | false | true |
| `PERP_SPOT_FLOW` | neutral, spot_led_accumulation | confirmed_bull, confirmed_bear, perp_led_fragile |
| `PRICE_ZONE` | near low, mid-range, near high | breakout high, breakdown low |
| `REGIME_VOL` | normal, expanding | contracting |

`REGIME_VOL` is the one to watch: 30 of 30 read "normal" while `atrPct` spanned 0.14% to
3.11%, a **22× range**. Consistent with a per-coin-relative measure on a calm day, and
equally consistent with a constant. One snapshot cannot separate those.

### An error of mine, recorded

I first called `OI_PX_REGIME` a mismatch on BTC. I had tested it against `OI_CHG` — which
is *"open interest against the mean of its own 24 hourly samples"*, **not** its recent
change. Wrong operand entirely. With an actual `OI` trajectory the quadrant holds on both
coins.

### The rule search, run for all three remaining metrics

I had written that `REGIME_MOM`, `OI_VELOCITY` and `CONFIDENCE` *"would need the same
search against operands that aren't exposed either"* — and never run it. That sentence
asserted an outcome. Here is the run: 78 coins at the 1h anchor, every label rendered
**beside its candidate drivers in one table**, every candidate the exposed columns can
express enumerated and scored, and the winner reported next to the mode baseline it had
to beat.

| metric | rows | baseline | best | margin | verdict |
|---|---:|---:|---:|---:|---|
| `REGIME_MOM` | 78 | 65% | 69% | **+4** | not identified |
| `OI_VELOCITY` | 78 | 56% | 78% | **+22** | partial |
| `CONFIDENCE` | 36 | 58% | 72% | **+14** | not identified |

Three different answers, and the difference between them is explanatory rather than
arbitrary.

**`OI_VELOCITY` is the second difference of the OI trajectory.** Compare `|last delta|`
with `|previous delta|`: growing is `accelerating`, shrinking `decelerating`, equal
`steady`. 78% of 78 against a 56% floor.

> Seven rows print all four OI values identically — `$4.0M`, `$1.3M`, `$1.7B` — so their
> second difference is `0 − 0`, undefined at display precision rather than wrong.
> Excluding *only* those lifts the fit to **86%**. That subset is a diagnostic and the
> 78% figure is the result; both are recorded, because filtering rows until a hypothesis
> fits is the standard way to manufacture one.

**`REGIME_MOM` produces the same negative as `REGIME_TREND`,** and for the same reason:
the driver is not exposed. AMZN is the sharpest case — labelled `bullish` with ROC, PPO,
MACD, `chg4h` and `chg24h` all negative and RSI14 at 37.3. That is an inversion, not a
near miss, and it is **unexplained**.

> **A claim I made here and then had to withdraw.** I wrote that `REGIME_MOM` is a bundle
> read whose value *"never touches the anchor candle grid"*, which would have made the
> whole search a category error. Then I tested it: rendered at 5m and 4h seconds apart,
> `REGIME_MOM` changes on **8 of 10 coins** and `REGIME_TREND` on **9 of 10**. It follows
> the anchor. *Timeframe-inert* means it refuses a **second** timeframe declared on the
> column, not that its horizon is fixed. So the 1h search compared a 1h label against 1h
> drivers — like for like — and the negative stands on its own terms rather than being
> excused by a mechanism I had invented. Two renders settled it; see
> [`regime_anchor_variance.json`](../data/audit/regime_anchor_variance.json).

**`CONFIDENCE` is not `PERP_SPOT_STRENGTH`,** despite the contract describing
`perpSpotStr` as using the *"CONFIDENCE idiom"*. That phrase names a shared **bucketing
function**, not a shared value: 32 of 36 rows read `perpSpotStr` `low` while `conf`
splits 15 `high` / 21 `moderate`, and the identity candidate scored at chance. So
`CONFIDENCE` buckets some continuous convergence strength that no column exposes — the
same shape as `REGIME_MOM`, an operand that is structurally unavailable rather than
merely unguessed.

### Not verifiable, and why each is not a matter of effort

- **`REGIME_TREND` / `REGIME_MOM`** — searched exhaustively, above and in
  [`_ruleSearch`](../data/audit/tier_c_coherence.json). Neither classifier reads the
  columns rendered beside it: best fits of 55% and 69% against baselines of 53% and 65%.
  The negative is measured, with a stated search space and a margin, and it is not
  explained by any horizon mismatch — both follow the report anchor.
- **`REGIME_VOL`** — relative to each coin's own history (atrPct spanning 0.14%–3.11%
  all read "normal") and that history is not available.
- **`CONFIDENCE`** — buckets a convergence strength that is not a column. 72% against a
  58% floor on 36 rows, which is suggestive and no more.
- **`PERP_SPOT_*`** — no discriminating case; the observed values are consistent with
  every hypothesis.
- **`SMART_RETAIL`** — the *rule* is solved (13 of 13); what is unstated is when it is
  absent.

`OI_VELOCITY` has left this list — it is the second difference of the OI trajectory.

### The one thing worth acting on

`SETTLED_AT` returns **`conditionOperators: []`**. It is the only column carrying the age
of the `CROWD_*` block, and it cannot be referenced by any condition — so **there is no
way to write a gate that refuses stale crowd data.**

It read `2026-07-24` against a `2026-08-25` render: 32 days. That staleness is probably
account state rather than a platform bug — no sessions have settled here recently. The
gap that *is* structural is that the timestamp exposing it is ungateable, and combined
with trap 11 a condition on `crowdAcc` answers confidently from month-old evidence with
no available guard.

## What none of this proves

Stated plainly, because the gap is the point of the document:

- **The forming bar's own price at the instant of render.** Verified to 0.0126% on
  closed bars; the live bar was never compared tick-for-tick.
- **Any coin other than BTC**, for tier 2. Funding and OI were checked on BTC and SOL;
  the indicator recompute was BTC only.
- **CVD, crowd, structure zones, regime, perp-spot flow.** These have *no exchange
  equivalent* to check against. `CVD` and `BUY_PRESSURE` depend on a trade-side
  classification the exchange does not publish; every `CROWD_*` metric is internal to
  BattleGrid by definition. They can be checked for internal consistency and nothing
  more.
- **That any of this stays true.** These are measurements from 2026-08-25, not
  invariants. Re-run the script.

The honest summary: **the price tape, the funding, the open interest and the classical
indicator maths all check out against an independent source.** The platform-native
metrics are unfalsifiable from outside, and should be weighted accordingly.
