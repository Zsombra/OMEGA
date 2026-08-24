# 12 · Routing Feasibility

Would this strategy route, and which signals are holding it back — answered before the
strategy exists.

---

## The correction this document exists to record

This project spent most of its life believing something false about the aggregate:

```
                    WRONG                                    RIGHT
aggregate = Σ(scoreᵢ×allocᵢ) / Σ(allocᵢ)      aggregate = Σ(scoreᵢ×allocᵢ) / Σ(allocᵢ)
            over EVERY allocated signal                   over the signals that FIRED
```

The formula never changed. What changed is which signals are in the sums.

### The measurements

| source | recorded | ÷ fired allocation | ÷ total allocation |
|---|---:|---:|---:|
| Dunkirk signal log | **0.68** | **0.680** | 0.120 |
| BTC 1h preview | **46%** | **45.7%** | 7.6% |
| SOL 1h preview | **52%** | **52.0%** | 5.6% |
| ETH 4h preview | **56%** | **55.8%** | 12.6% |

Four independent confirmations, one of them a real closed trade. `simulate_aggregate_score`
was never wrong — it computes over exactly the signal set you hand it, and the live engine
hands it the fired set. I had been handing it whole scorecards padded with zeros, which
answers a different and misleading question.

### What the error cost

Three claims in this repo followed from it, and all three were wrong:

- *"A `NOT_IN_REPORT` signal at tier 3 is pure denominator — it actively suppresses your
  aggregate."* It never fires, so it enters neither sum. It costs **nothing**
  arithmetically.
- *"MATH-C3's gate 0.65 is unreachable; the long-side ceiling is 0.524."* There is no
  structural ceiling. The maximum aggregate is 1.0 for any scorecard.
- *"Every added signal dilutes."* Only signals that **fire** dilute.

Docs 00, 05, 06, 07 and 11 have been amended in place, each carrying a dated note saying
what it used to claim.

## What is actually true

**Unfired signals are free.** Breadth costs nothing until a signal triggers. A module with
no feeding column, a signal that never reaches its threshold, an entire unreachable
family — none of them touch the aggregate.

What an unfed signal costs is **evidence**. You believed you had weighted that module and
you had not. The scorecard is narrower than it looks — which is a real problem, just not an
arithmetic one.

**The aggregate is a mean, so fired signals pull it toward their own score:**

> A fired signal raises the aggregate **iff its score exceeds the current aggregate.**

That single line is the whole design principle. The expensive signal is not the one that
sits idle; it is the one that **fires often and scores low**.

### The worst profile in the catalogue

`rel_roc_positive` and `rel_roc_negative` score `ROC12 / 5`, so ROC must reach **5%** for a
score of 1.0. On an hourly bar ROC(12) is typically around 0.01%, giving scores like
`0.000789982`. And they fire almost always — ROC is nearly always either
positive-and-accelerating or negative-and-decelerating.

Fires constantly, scores ~0. Under a mean, that is the worst possible combination.

Measured on the real Apex scorecard against BTC:

```
baseline                                                    48.00%   held
  remove rel_roc_positive  (score 0.0008, alloc 2)  ->      52.80%   ROUTES   +4.79pp
  remove htf_rsi_overbought (score 0.0828, alloc 2) ->      51.98%            +3.97pp
  remove ltf_ma_aligned_bear (score 0.1097, alloc 2) ->     51.71%            +3.70pp
  ...
  remove ma_sma200_above   (score 1.0000, alloc 2)  ->      42.81%            −5.20pp
```

Deleting one near-zero signal flips the coin from held to routing.

### Both directions is a dilution strategy

Allocate `_bull` and `_bear` for every module — the Apex "kitchen sink" shape — and in any
given market one side fires meaningfully while the other fires weakly. The weak side is
always present, always below the mean, always pulling down. Directional focus is not about
conviction; it is about not carrying the losing half of every pair into your denominator
on every single bar.

## The only genuine unreachability left

A signal marked `required: true` that no column feeds. It can never fire, so its
precondition can never be satisfied, and the strategy never routes regardless of market
state.

```python
blocking_requirements(rules, in_report=membership.analyse(report).signals_in)
# ['bollinger_squeeze']   -> this strategy is dead until BOLLINGER gets a column
```

Everything else is empirical.

## Why this is computable at all

`get_coin_signal_preview` returns **all 84 signal scores at `effectiveAllocation: 1`** — the
unweighted path, when you omit `agentId`. A signal's score never depends on its allocation;
allocation enters only the weighting. So re-weighting those scores with any hypothetical
allocation vector is pure arithmetic on data you already hold.

**A strategy that does not exist can be evaluated against live market data, with no writes
and no quota spent.** The platform only offers weighted aggregates for agents that already
exist; this gets you there beforehand.

## Using it

```python
from omega.feasibility import (
    simulate, drag_ranking, blocking_requirements,
    load_observations, load_rules, FETCH_RECIPE,
)

print(FETCH_RECIPE)                       # the read-only call sequence
allocs, gate = load_rules("apex-imported")
obs = load_observations(interval="1h")    # keep one interval per sweep

print(simulate(list(allocs.items()), gate, obs).render())
print(drag_ranking(list(allocs.items()), obs))
```

```
gate 50.0%   2/3 coins would route   best observed 56.8%

  ROUTES  ETH     56.8%  18 fired (weight 29)   regime_volatility_shift 12%, ...
  ROUTES  SOL     50.7%   9 fired (weight 14)   ma_sma200_above 28%, cvd_bearish 28%, ...
    held  BTC     48.0%  13 fired (weight 22)   macd_bear_divergence 19%, ...

  allocated but never fired across 3 coins - COSTLESS, not dead weight:
    56 signals; they enter neither sum
```

`leverage(rules, observation)` gives the per-signal marginal effect on one coin;
`drag_ranking` averages it across the sample.

## What this does not measure

Routing frequency is not profitability. A sweep says *"these allocations would clear the
gate on this tape"*, not *"these allocations make money"*. Those are easy to conflate once
both are floats.

Profitability lives in [10 · Outcome Feedback](10-outcome-feedback.md), which refuses to
report a win rate below 20 closed trades. A high routing rate with no outcome history is a
strategy that will trade a lot, and nothing more.

A three-coin sample taken at one instant is also thin. Capture more coins, and re-run at
different times before drawing conclusions about a shape.

## Verification

`tests/test_feasibility.py` — 14 tests. The first four pin the denominator evidence
directly: the Dunkirk log reproduces at 0.680 against fired allocation and 0.120 against
total; each preview's own `aggregateScorePercent` reproduces as the mean over fired signals
and demonstrably *not* over all 84. One test asserts the weighted-mean property
(`helps ⟺ score > aggregate`) holds for every signal in a constructed case; another
verifies that padding a scorecard with signals that never fire leaves the aggregate
bit-identical.
