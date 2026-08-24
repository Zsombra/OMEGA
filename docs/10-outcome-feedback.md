# 10 · Outcome Feedback

Which signals actually earned their allocation — and the discipline of not answering when
the data can't support an answer.

---

## The state of your data

This is the first thing to say, because it determines what the rest of this document is
worth to you today.

| | |
|---|---|
| Agents | 24 (slots full) |
| Agents with **any** history | **1** — the archived `Dunkirk` |
| Fleet agents bound to your own strategies | 23, **all with zero evaluations** |
| Dunkirk closed trades | 18 (5W / 13L, −$4.47 net) |
| Platform's minimum sample | **20 closed trades** |

`list_signal_logs` on the MATH-C3 agent returns `{"entries": [], "total": 0}`. The
strategies you built have never run. The only agent with history is bound to a different,
imported strategy.

And the platform's own calibration tool already refuses to draw a conclusion from it:

```json
{"windowDays": 90, "minSampleSize": 20, "totalSampleSize": 7,
 "bands": [{"band": "LOW", "readiness": "INSUFFICIENT_DATA", "sampleSize": 0},
           {"band": "MODERATE", "readiness": "INSUFFICIENT_DATA", "sampleSize": 5},
           {"band": "HIGH", "readiness": "INSUFFICIENT_DATA", "sampleSize": 2}]}
```

> "below the minimum sample size a group carries INSUFFICIENT_DATA and a sampleSize and
> **NO rate at all** — there is deliberately no win rate to read off a sample too small to
> support one."

## The data model

Each closed trade carries a `signalLogId`. That log holds the full scorecard, so the join is
exact:

```
list_trade_outcomes  ->  trade { signalLogId, netPnl, conviction, closeReason }
                              |
get_signal_log       ->  log.scorecard.allEvaluatedSignals  [84 x {id, triggered, score,
                                                                  effectiveAllocation}]
                         log.attributions                   [attributionPercent per fired signal]
                         log.pipeline.outcome                {tradeOutcome, netPnl, roePercent}
```

`omega.performance.FETCH_RECIPE` prints the exact read-only call sequence. None of it
consumes strategy or agent quota.

## What it computes

Per signal, across observations:

- **fired** — how many closed trades it triggered on
- **win rate** — but **only at or above `MIN_SAMPLE = 20` firings**; `None` below that
- **Wilson 95% interval** — so `3/4` never reads as "75%"
- **average net P&L** when it fired
- **average attribution** — its share of the aggregate on those trades
- **lift** — win rate when it fired *minus* win rate when it didn't

Lift is the one that matters. "Do trades win when this fires?" is the wrong question — in a
winning strategy everything looks good. The question is whether trades win **more** when it
fires. A signal that fires on every trade has no lift to measure, and the tool says so
rather than crediting it.

## What it refuses to do

```python
>>> r = load_sample()          # the one real Dunkirk observation
>>> r.ready
[]
>>> recommend_allocations(r, {})
[]
```

An empty list is the correct answer to a small sample, not a failure to produce output. A
recommender that turned 18 trades into per-signal weights across 84 signals would be
manufacturing an edge out of noise, and would be worse than no tool at all — it would carry
the authority of a number.

The readiness view tells you what you'd need instead:

```
[ARCHIVED] Dunkirk
observations 1  |  with a closed trade 1  |  minimum sample 20

READY (0): no signal has fired often enough to support a rate.

INSUFFICIENT_DATA (66), most-fired first:
  bollinger_squeeze                INSUFFICIENT_DATA  fired=1 (need 20)
  ...

closest to a readable rate:
  bollinger_squeeze                ~20 closed trades at its current fire rate
```

`trades_needed()` inverts each signal's fire rate: a signal firing on a fraction *f* of
trades needs `20 / f` trades to become readable. A signal firing on a third of trades needs
~60.

## Recommendations, once the data exists

Only READY signals produce a suggestion, and only when the **whole confidence interval**
clears the baseline:

| condition | action |
|---|---|
| interval low end **above** baseline win rate | promote one tier (capped at 3) |
| interval high end **below** baseline | demote one tier (floored at 0) |
| interval **straddles** the baseline | leave alone — *"not separable yet"* |

That third row is the important one. Most signals will land there for a long time, and
leaving them alone is the right call.

## A correction to doc 07

Doc 07 lists CONFLUENCE and COMPARISON — 7 signals — as unreachable, because
`derive_strategy_rule_view` never put them `IN_REPORT` under any column combination.

The real log shows `comparison_sector_momentum` **firing live**:

```json
{"id": "comparison_sector_momentum", "module": "COMPARISON", "triggered": true,
 "score": 1, "effectiveAllocation": 1, "attributionPercent": 7,
 "details": "Sector momentum: 3/3 peers confirm BULLISH trend"}
```

So the accurate statement is narrower than doc 07's: these signals are **unreachable through
column design**, because they aren't fed by report columns at all. They're fed by the
**comparison coin set** — the log carries a `comparison` block of benchmarks and sector
peers with correlations. `derive_strategy_rule_view` answers "what do my *columns* feed",
so it correctly reports them absent; that is not the same as them never evaluating.

Doc 07 has been amended.

## Using it

```python
from omega.performance import analyse, load_sample, recommend_allocations, FETCH_RECIPE

print(FETCH_RECIPE)                    # the read-only call sequence
report = load_sample()                 # or analyse(your_observations, totals=...)
print(report.render())
for s in recommend_allocations(report, current_allocations):
    print(s)
```

## What would make this useful

Run the fleet. Twenty-three strategies are built, validated and bound to agents that have
never evaluated anything. Until they do, this module has nothing to weigh — and says so.
