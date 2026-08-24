# 00 · The Mental Model

The single most useful reframing: **you are not writing indicators. You are composing a
read over quantities the platform already computes.**

You never supply a formula. You pick a *quantity* (metric), pick a *way of reading it*
(transform), pick *when* to read it (timeframe), and the engine compiles that triple into
one or more **output headers** — named cells that land in the Strategy Report the agent
reads before it makes a pick.

Everything else in this repository is detail hanging off that sentence.

---

## The seven layers

```
                                     what you control
                                             │
  1  METRIC        86 named quantities  ─────┤  select
  2  TRANSFORM     16 ways to read one  ─────┤  select
  3  COLUMN        (metric, transform, timeframe, params)
                                        ─────┤  compose      ← "your own data point"
  4  SECTION       a titled group of columns
                                        ─────┤  compose
  5  REPORT        sections, under hard budgets
                                        ─────┤  compose
  ───────────────────────────────────────────────────────────
  6  SIGNALS       84 canonical detectors, each given
                   an allocation tier 0–3 and required flag
                                        ─────┤  weight
  7  AGGREGATION   allocation-weighted mean vs a gate
                                        ─────┤  threshold
                                             │
                                    route / hold
```

Layers 1–5 decide **what the agent can see**. Layers 6–7 decide **what it does about it**.
They are coupled: a signal whose evidence isn't in the report can never fire, no matter
what allocation you give it (see [05](05-signal-aggregation-math.md)).

---

## Layer 1–2: the matrix is sparse

The instinct is to imagine an 86 × 16 grid of metric × transform. It isn't. **Only 322 of
1,376 cells are legal — 23.4% density.** Asking for an illegal one returns:

```
(ADX × classifyState) is not a composable pair — the engine has no
resolution home for it
```

Four independent mechanisms carve the holes, and none of them are guessable:

| Mechanism | Example |
|---|---|
| **Per-metric transform whitelist** | `STOCH_K` has `classifyZone`; `STOCH_D` does not |
| **Unit-typed spread pools** | `RSI14` may only spread against the 6 other oscillators |
| **Per-metric rank orderings** | `CLOSE_CHANGE` offers only `far`/`near` — never `hi`/`lo` |
| **Platform privilege** | `CCI20 × classifyZone` is used by the platform, denied to you |

This is why the corpus is *extracted* rather than *inferred*. Two of those four rules
produce results the opposite of what physical intuition suggests.

## Layer 3: one column is not one number

`RSI14 × trajectory × window:4` does **not** produce one value. It compiles to five headers:

```
RSI14_t3   RSI14_t2   RSI14_t1   RSI14_now   RSI14_trend
```

Four numeric slots plus one `direction` output (`rising | falling | flat`). Each header
carries its own type and therefore its own legal condition operators.

`trajectory` is the **only** fan-out transform. Every other transform emits exactly one
header. Since the report's binding constraint is a ~16,000-token budget rather than the
32-column-per-section cap, trajectory windows are the main thing that spends your budget.

## Layer 4: sections are typed by time

A custom section may pin an explicit `timeframe`. But **timeframe-inert metrics cannot live
in a section that does**:

```
metric 'FUNDING_RATE' is timeframe-inert (a bundle read) and is not allowed
in a section with a timeframe override — it accepts only the section anchor
```

So the composition rule is: *if you want a pinned-timeframe section, every column in it must
be candle-backed.* Funding, open interest, crowd, regime and derived metrics all force the
section to run on the strategy anchor. This is invisible from metric contracts alone — it
only appears when you compile a column inside a section context.

## Layer 5–7: weight is not evidence

The scorecard maths is a plain allocation-weighted mean:

```
aggregate  = Σ(scoreᵢ × allocᵢ) / Σ(allocᵢ)
routes iff   aggregate ≥ gate
```

Allocation tier **0 contributes exactly zero weight** — it is informational, not a light vote.
And allocation only converts evidence into influence; it cannot manufacture evidence. Give
`bollinger_lower_touch` allocation 3 with no Bollinger column in your report and you have
added nothing but a denominator.

---

## The three questions to ask of any column you invent

1. **Is the pair legal?** → `omega.validate`, or `get_strategy_column_contract`.
2. **How many headers does it cost, and what can I condition on?** → `omega.fanout`.
3. **Does it actually feed the signals I'm weighting?** → `derive_strategy_rule_view`.

The toolkit answers 1 and 2 offline. Question 3 needs the connector, because report
membership is not derivable from the column list by inspection.

---

## Reading order

| Doc | For |
|---|---|
| [01 · Metric Layer](01-metric-layer.md) | all 86 metrics, classified |
| [02 · Transform Layer](02-transform-layer.md) | all 16 transforms, formulas, pools, privilege |
| [03 · Column Compilation](03-column-compilation.md) | how a column becomes headers |
| [04 · Sections, Timeframes, Budgets](04-section-report-budget.md) | composition and cost |
| [05 · Signal Aggregation Math](05-signal-aggregation-math.md) | the scoring derivation |
| [06 · Cookbook](06-cookbook.md) | recipes, and the traps |
