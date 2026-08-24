# 13 · Temporal Spread

The second axis. Doc 12 asks *would this strategy route on this tape*. This one asks
whether the tape was a tape at all, or a single photograph.

## The problem a second capture exposes

Every conclusion in doc 12 came from five coins read at one instant. That sample has
decent **cross-sectional** spread — three asset classes — and no **temporal** spread
whatsoever. A signal that fired on four of five coins looked like strong evidence.
It was four readings of one moment.

Re-reading the same five pairs ~42 minutes later:

| | |
|---|---|
| fired-signal slots stable across the gap | **59 / 86 = 69%** |
| dominant biases that flipped | **2 of 5** (BTC `MIXED→BEARISH`, GOOGL `BULLISH→BEARISH`) |
| signals that vanished entirely | 5 |
| signals that appeared from nothing | 3 |

Churn is wildly uneven. GOLD moved one slot; BTC moved twelve. Anything that treats
"fired on GOLD" and "fired on BTC" as equally durable evidence is wrong about one of them.

## Coverage buys magnitude stability

Comparing the per-signal leverage estimate at the two timepoints:

| fired on | signals | mean \|shift\| | max \|shift\| |
|---|---:|---:|---:|
| 1/5 coins | 19 | 0.99pp | 3.97pp |
| 2/5 coins | 8 | 0.65pp | 2.68pp |
| 3/5 coins | 9 | 0.69pp | 2.22pp |
| 4/5 coins | 2 | **0.18pp** | **0.33pp** |

This is the first real test of doc 12's `min_coverage` split, and it passes: broad
signals barely move, narrow ones swing by up to 4pp. The monotonicity breaks in the
middle (2/5 and 3/5 are tied) because those buckets are small, but the ends are decisive.

## Pooling two captures breaks the count

`drag_ranking` pools every observation into one list and reports `fired on n/N`. Hand
it two captures and `n` doubles — but **3 coins × 2 times** and **6 coins × 1 time**
become the same number, and they support opposite conclusions. Repeated looks at one
coin are not independent evidence *about coins*. That is pseudoreplication, and it
inflates confidence exactly where the sample is thinnest.

`temporal_drag_ranking` collapses each coin to its own mean across time first, then
averages those coin means. A coin captured twice carries the weight of a coin captured
once, which is the only thing that makes the reported `coins` a real n.

### A worked example of why this matters

`ma_ema_aligned_bull` appears to flip sign between the captures — pooled `+0.63pp` at
T1, `−0.68pp` at T2. It did not drift at all:

```
GOLD/1h    T1 +1.91   T2 +1.91     half-gap 0.00
ETH/4h     T1 −3.20   T2 −3.26     half-gap 0.03
BTC/1h     T1 +3.19   T2  —        stopped firing
```

Every coin held its value. The pooled flip is a **composition artifact** — BTC's
`+3.19` was in the first pool and absent from the second. Coin-averaging dissolves it
and reports a stable `+0.62pp`. The pooled estimator was measuring its own instability,
not the signal's.

## The noise floor is measured, not assumed

Coverage predicts how far a *magnitude* moves. It does not decide whether a *sign* is
real. An estimate of `+0.29pp` is not a direction if the same coin drifted `0.70pp`
between two reads of an unchanged rule set.

So each signal gets its own floor. Wherever a signal fired on the same coin at two
timepoints, the gap between those readings is drift the market handed over for free —
same coin, same rules, only the clock moved. The half-gap, averaged over such coins, is
that signal's noise. An estimate smaller than its own noise is reported `?`, not `DRAG`.

Two ways to be unresolved, and they are different:

- **`|estimate| within drift`** — it fired repeatedly and the effect is real-but-small.
- **`no single coin fired it at both timepoints`** — no drift information exists at any
  magnitude. `macd_bear_divergence` reads `−6.27pp` across two coins seen once each.
  That is the largest carry in the sample and it is still unresolved, because nothing
  distinguishes a large real effect from a large transient.

## What survives

Against the two captures, with `apex-imported` allocations:

| | signal | estimate | evidence |
|---|---|---:|---|
| **drag** | `rel_roc_negative` | **+6.00pp** | 4 coins × 2 times |
| **drag** | `ltf_ma_aligned_bear` | +4.34pp | 3 coins × 2 times |
| **drag** | `htf_rsi_overbought` | +2.65pp | 3 coins × 2 times |
| carries | `cvd_bullish` | −3.56pp | 3 coins × 2 times |
| carries | `ma_sma200_above` | **−4.44pp** | 4 coins × 2 times |

Doc 12's headline holds: `rel_roc_negative` is still the top drag, `ma_sma200_above`
still the top carry. Both now rest on two timepoints instead of one.

## Reading and extending

```python
from omega.feasibility import load_captures, temporal_drag_ranking, load_rules

allocs, _ = load_rules("apex-imported")
print(temporal_drag_ranking(list(allocs.items()), load_captures()))
```

`load_captures()` globs `data/performance/coin_observations*.json`, so a new timepoint
is a new file — no loader change. Each observation is stamped from its file's
`_capturedAt`, or its own `capturedAt` when present.

Write captures the same way: unweighted `get_coin_signal_preview`, non-zero scores
only, and **verify each scorecard against the platform's reported
`aggregateScorePercent` before storing it**. A hand-built fixture's most likely failure
is a transcription slip, and that check catches it. All ten stored scorecards reconcile.

## A third capture, twelve hours out

The first two captures were 42 minutes apart, inside one session. A third taken ~12 hours
later is the first that spans a real stretch of tape — and it changes the picture sharply.

| | 42 minutes (t1→t2) | ~12 hours (t2→t3) |
|---|---:|---:|
| fired-signal slots stable | **69%** | **30%** |
| dominant biases flipped | 2 of 5 | **3 of 5** |

BTC kept **2** of its 17 fired slots. All three bias flips ran the same way,
`BEARISH → BULLISH`, and BTC's aggregate went 54% → 81%.

### The noise floor does its job

With a better drift estimate, the ranking gets *less* confident — which is the point:

| | 2 timepoints | 3 timepoints |
|---|---|---|
| `rel_roc_negative` | +6.00pp, resolved | **+6.00pp, resolved** (drift 0.24) |
| `ma_sma200_above` | −4.44pp, resolved | −2.64pp, resolved (drift 1.14) |
| `bollinger_squeeze` | +0.57pp, resolved | **+0.96pp, UNRESOLVED** (drift 1.17) |
| entries claiming a direction | most | **27 of 52** |

**25 of 52 entries are now unresolved.** Two captures 42 minutes apart made the rankings
look far more settled than they were; the extra timepoint raised the measured drift and
disqualified nearly half of them. Nothing about the estimator changed — only the evidence
it had to judge against.

`rel_roc_negative` survives all three captures as the top drag, with the *tightest* drift
in the sample (0.24pp). `ma_sma200_above` remains the top resolved carry on the broadest
evidence available — 5 coins × 3 timepoints — though its magnitude halved.

## Caveat

Three timepoints across ~12 hours is better than two across 42 minutes, and still thin.
Every noise floor rests on at most a handful of coin-pairs, and the whole sample is one
day. Captures days apart, and more coins, are what would turn this into a measurement
rather than a guard.

The `?` verdicts are the honest output of a small sample, not a permanent judgement — and
the count of them went **up** when better evidence arrived, which is the behaviour to
want.
