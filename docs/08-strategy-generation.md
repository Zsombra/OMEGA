# 08 · Strategy Generation

Compose a complete, validated strategy from a thesis — offline.

Everything in docs 00–07 was about *understanding* the system. This is the part that
uses it: `omega.generate` turns a statement of what a strategy believes into a legal
report, an honest scorecard, and a submit-ready payload.

---

## The real strategy shape

Read back from two live strategies (`EL_ALAMEIN`, `MATH-C3`), a strategy is:

```jsonc
{
  "name": "...", "tagline": "...", "description": "...",
  "timeframe": "1h",            // the anchor
  "cadence": "INTRADAY",        // SCALPER at 5m/15m
  "regimeTimeframe": "4h",      // what rel:regime resolves to - strategy config, not anchor-derived
  "marketReadText": "...",      // agent prompt; interpolates {CONDITION_KEY} and {header}
  "sections": [ ... ],
  "conditions": [ ... ],        // the 16-condition DSL
  "signalRules": [ ... ],       // DENSE - all 84, unused ones at allocation 0
  "minAggregateScore": 0.65,    // THE GATE
  "minRequiredCount": 0,
  // risk block: minAtrPct, stop-loss ATR multiples, R:R, break-even, trailing, time-decay
}
```

Two things worth pinning down:

**`minAggregateScore` is the gate** from [05](05-signal-aggregation-math.md). El Alamein runs
`0.25`; MATH-C3 runs `0.65`. Same maths, very different posture.

**The scorecard is dense.** All 84 signals are always listed; the ones you don't use sit at
`allocation: 0`. So `mtf_*` and `comparison_*` *appear* in every strategy — being listed is
not being fed.

### The condition DSL

Conditions are the 16-condition / 16-clause budget made concrete. From El Alamein:

```jsonc
{
  "conditionKey": "CONFLUENCE_UP",
  "name": "Three of four filters agree - up",
  "definition": {
    "kind": "group", "op": "N_OF", "n": 3,
    "members": [
      {"kind": "clause", "column": {"sectionKey": "includeMacd", "header": "MACD_trend"},
       "op": "is", "label": "rising"},
      {"kind": "clause", "column": {"sectionKey": "includeRsi", "header": "RSI14_now"},
       "op": "gt", "value": 50}
    ]
  },
  "verdict": "UP", "required": false
}
```

Clauses reference `{sectionKey, header}` — which is exactly why the header names in
[03](03-column-compilation.md) matter. The condition key is then interpolated into
`marketReadText` as `{CONFLUENCE_UP}`, so the agent reads the *verdict*, not the raw filters.

`omega.generate` emits `conditions: []`. Conditions are a deliberate authoring act, not
something to synthesise.

## Two entry points

### Forward: from a thesis

```python
from omega.generate import PRESETS, plan
print(plan(PRESETS["mean-reversion"]).render())
```

```
Mean Reversion at Extremes  --  Fade the stretch, only with flow agreeing
anchor 1h | gate 0.65 | 2 sections | 15 columns | 37 headers

weighted signals   22 of 26 in report
  tier 3  (5)  bollinger_cci_overbought, bollinger_cci_oversold, ...
  tier 2  (12)  cvd_bear_divergence, cvd_bearish, ...
  tier 1  (5)  funding_extreme_negative, funding_extreme_positive, ...

all-signals-at-0.75 -> aggregate 75% vs gate 65% -> ROUTES
```

A `Thesis` is modules and weights, nothing more:

```python
Thesis(
    name="Mean Reversion at Extremes",
    gate=0.65,
    weights={"BOLLINGER": 3, "RSI": 2, "CVD": 2, "FUNDING": 1, "VOLATILITY": 1},
    context=["REGIME"],   # included as reading material, weighted 0
)
```

Five presets ship: `mean-reversion`, `trend-continuation`, `squeeze-breakout`,
`flow-divergence`, `structure-reversal`.

### Backward: from the signals you want

```python
plan_for_signals(["cvd_bull_divergence", "oi_surge", "mtf_aligned_bull"], name="Demo")
# thesis.description: "unreachable and therefore unallocated: mtf_aligned_bull"
```

It resolves each signal to its module, builds the report that feeds it, and **refuses to
allocate what it cannot feed**.

## What the generator guarantees

Because it composes the rest of the toolkit, every plan is:

- **legal** — columns come from recipes validated against the composability matrix
- **section-clean** — candle and timeframe-inert metrics go in *separate* sections, so the
  candle section stays free to take a timeframe override later ([04](04-section-report-budget.md))
- **honestly allocated** — allocation only goes to signals `membership.py` says are fed
- **in budget** — checked against all seven budgets
- **gate-consistent** — if every weighted signal scored 0.75 and it still wouldn't route,
  the critique says so

## The critique

```python
plan(thesis).critique()
```

Reports invalid columns, wasted allocation, context-only metrics, budget breaches, token
headroom, an unreachable gate — and one judgement call:

> **correlated oscillators weighted together: BOLLINGER, MFI, RSI, STOCHASTIC — largely one
> piece of evidence counted 4 times**

The platform warns against *"stacking several correlated oscillators as independent
evidence."* Weighting three or more oscillator modules doesn't just cost tokens; because the
aggregate is a weighted **mean**, it triple-counts one observation and crowds out
independent axes — flow, derivatives, structure.

## A limit worth knowing

`simulate_aggregate_score` accepts **at most 20 signals per call**. Real strategies exceed
that — El Alamein weights **32**. So the platform's own what-if tool cannot evaluate a full
production scorecard in one call. `omega.aggregate` has no such limit, and its output is
verified identical to the platform's, so local aggregation is the way to evaluate one.

## Emitting

```python
from omega.generate import emit_plan
emit_plan(plan(PRESETS["squeeze-breakout"]), "squeeze")
# -> out/squeeze.strategy.json   (dense 84-signal scorecard, critique attached)
```

**Nothing is submitted.** The payload is ready; submitting it stays a separate, deliberate
act — and with quota at 24/25, a considered one.

## Verification

All five presets are tested for validity, budget, allocation honesty, gate reachability and
section separation. Every recipe column is checked legal against the composability matrix
and confirmed to actually feed its module. The `squeeze-breakout` plan was submitted to the
live `derive_strategy_rule_view`: **the connector returned exactly the 18 signals the
generator predicted**, signal for signal.
