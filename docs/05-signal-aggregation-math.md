# 05 · Signal Aggregation Math

The layer above the report: 84 canonical signals across 19 modules, each carrying an
allocation tier and a `required` flag, aggregated into one number and compared to a gate.

---

## The formula

Not documented by the connector — derived by probing `simulate_aggregate_score`, then
confirmed against it.

**Probe 1** — four signals, all scoring 1.0, at tiers 0/1/2/3:

```
attributions →  0%,  17%,  33%,  50%
```

Those are `0/6, 1/6, 2/6, 3/6`. So the weight *is* the allocation tier.

**Probe 2** — pin down the denominator with unequal scores:

```
{score 1 @ alloc 3,  score 0 @ alloc 1}   →   aggregate 0.75
```

`(1×3 + 0×1) / (3+1) = 0.75`. If the denominator were total *contribution* it would be
1.0. It is total **allocation**.

```
aggregate      = Σ(scoreᵢ × allocᵢ) / Σ(allocᵢ)
attributionᵢ   = (scoreᵢ × allocᵢ) / Σ(scoreⱼ × allocⱼ)
wouldRoute     = aggregate ≥ gate
```

Verified end-to-end: a 5-signal set returns `0.7187499999999999` / 72% / routes, with
attributions 47/24/14/15/0 — identical to `omega.aggregate` to the last digit.

## What follows from it

**Tier 0 is not a light vote — it is zero.** It appears in the attribution list at 0% and
contributes nothing to numerator or denominator. Use it to mark a signal as *watched but not
counted*; never as "slightly important".

**The aggregate is a weighted mean, so it is bounded by your best and worst scoring signal.**
Adding a signal that scores below the current aggregate always drags it down, regardless of
tier. You cannot raise the aggregate by adding more confirming evidence at low scores.

**Score and weight trade off, and small weights are not negligible.** From the worked case:

```
funding_extreme_negative   tier 1 @ 0.85   →  15%
cvd_bull_divergence        tier 2 @ 0.40   →  14%
```

A tier-1 signal scoring well outweighs a tier-2 signal scoring poorly.

**Every added signal dilutes.** Because the denominator is Σallocation, a report with many
tier-3 signals needs broad agreement to clear a high gate. Concentration is a real lever:
three tier-3 signals clear a 0.7 gate far more easily than nine do.

## Gate calibration

With all signals at tier `a` and gate `g`, the fraction of signals that must score ~1.0
(others ~0) to route is just `g`. So the gate reads directly as *"what share of my weighted
evidence must be present."*

| Gate | Reading |
|---|---|
| 0.5 | simple weighted majority |
| 0.65 | clear majority — the balanced default |
| 0.8 | near-unanimity; expect few routes |

`omega.aggregate.minimum_score_to_route(signals, gate, label)` inverts the formula: holding
the others fixed, what would *this* signal need to score to clear the gate? It returns
`None` when the signal cannot change the outcome — always true for tier 0.

## The coupling you cannot see from the maths

Allocation converts evidence into influence. It **cannot manufacture evidence.**

`derive_strategy_rule_view` returns, for each of the 84 signals, whether it is `IN_REPORT`.
For the 7-column panel in `examples/build_section.py`, 15 signals came back in-report — but
`bollinger_lower_touch` did not, because the panel carries no Bollinger column.

A `NOT_IN_REPORT` signal at tier 3 is pure denominator: it adds 3 to Σallocation and,
having nothing to read, contributes ~0 to the numerator. **It actively suppresses your
aggregate.**

> Run `derive_strategy_rule_view` after designing the report and *before* assigning
> allocations. Report membership is not derivable from the column list by inspection —
> our panel unlocked all four `cvd_*` signals without containing a single `CVD` column
> (`BUY_PRESSURE` satisfies that module).

## `required`

Separate from allocation. A `required` signal acts as a gate precondition rather than a
weight — the setup is disqualified if it isn't present, however high the aggregate. Treat
`required: true` as a veto and allocation as a vote; using tier 3 as a stand-in for
"mandatory" does not do the same thing.

## Using the module

```python
from omega.aggregate import Signal, aggregate, minimum_score_to_route

signals = [
    Signal("rsi_oversold",             0.90, 3),
    Signal("bollinger_lower_touch",    0.70, 2),
    Signal("cvd_bull_divergence",      0.40, 2),
    Signal("funding_extreme_negative", 0.85, 1),
    Signal("regime_alignment",         1.00, 0),   # informational
]
print(aggregate(signals, gate=0.65).render())
print(minimum_score_to_route(signals, 0.65, "cvd_bull_divergence"))  # 0.125
```

```
aggregate 72%  vs gate 65%  -> ROUTES
  rsi_oversold                 a3 score  0.90   47% ############
  bollinger_lower_touch        a2 score  0.70   24% ######
  funding_extreme_negative     a1 score  0.85   15% ####
  cvd_bull_divergence          a2 score  0.40   14% ####
  regime_alignment             a0 score  1.00    0%
```
