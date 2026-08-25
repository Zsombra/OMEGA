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
