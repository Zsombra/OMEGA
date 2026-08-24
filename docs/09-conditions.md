# 09 · Conditions

Deterministic reads of your report columns, resolved server-side and surfaced to the agent
as a named verdict.

---

## What conditions are not

The platform says it plainly, in the rendered report itself:

> Conditions are deterministic reads of your report columns, resolved server-side at
> prompt-build time. **They are advisory: they may make you more selective, never less —
> they do not gate, score, or qualify anything.** TRUE / FALSE / UNRESOLVED are three
> distinct states; UNRESOLVED means an input was missing, not that the read was false.

So the natural assumption — *conditions are the entry filter* — is wrong. The gate is
`minAggregateScore` over the signal scorecard ([05](05-signal-aggregation-math.md)).
Conditions change what the agent **reads**, and the agent may become more selective as a
result. Nothing more, and that is enough: El Alamein's whole thesis is *"read the verdict
rather than re-counting the filters."*

## The grammar

From the `compile_strategy_plan` / `preview_strategy_report` schema — authoritative:

```jsonc
{
  "conditionKey": "CONFLUENCE_UP",       // ^[A-Z][A-Z0-9_]{1,39}$  - minimum TWO chars
  "name": "Three of four filters agree - up",   // 1-80
  "definition": { ... },
  "verdict": "UP",                       // UP | DOWN | NEITHER | null
  "required": false
}
```

A `definition` is one of six things:

| kind | shape |
|---|---|
| numeric clause | `{kind:"clause", column, op: lt\|lte\|gte\|gt, value}` |
| range clause | `{kind:"clause", column, op:"between", low, high}` |
| label clause | `{kind:"clause", column, op:"is", label}` |
| label-set clause | `{kind:"clause", column, op:"in", labels:[…]}` |
| **condition ref** | `{kind:"conditionRef", conditionKey}` |
| group | `{kind:"group", op: ALL\|ANY\|NOT\|N_OF, members:[…], n?}` |

Two things worth calling out. Group operators are **`ALL | ANY | NOT | N_OF`** — not
`ALL_OF`/`ANY_OF`. And **`conditionRef`** lets one condition reference another by key, so
conditions compose into a DAG rather than a flat list. Groups nest, so a checklist can sit
inside an `ALL` beside a non-directional filter — which is exactly how the generator builds
them.

`column` is `{sectionKey, header}`, and **`sectionKey` may be `null`** — the server resolves
the header. Verified live: a payload with `sectionKey: null` came back attributed to the
right custom section.

Budgets: the schema permits 64 conditions, but the discovery budget caps
`strategyConditions` at **16** and `conditionClauses` at **16**.

## Referenceable headers

A clause can name any header the report produces — see [03](03-column-compilation.md) for
naming — **plus three ambient sections that no column creates**:

| sectionKey | headers |
|---|---|
| `session-field` | `fieldPlayers_session` `fieldUpBias_session` `fieldBiasDir_session` `captConc_session` `picksSpread_session` |
| `market-breadth` | `mktUp_all` `mktDown_all` `mktBreadth_all` `mktAvgChg_all` |
| `reference-pairs` | `usdtUsdDev_market` `usdcUsdtDev_market` |

These cost **nothing** against your column or token budget. This is why the
`includeMarketBreadth` and `includeReferencePairs` platform templates ship with zero
columns — the data is ambient and the template is a no-op.

A condition over `mktBreadth_all` works on a report with no columns at all:

```python
condition("BREADTH_UP", "Broad tape", num("mktBreadth_all", "gt", 20), verdict="UP")
```

One gotcha: `picksSpread_session` has an **empty operator set** — it can be read but never
conditioned on.

## The type check

This is the payoff of the column type system. A clause asserts three things at once — a
header, an operator, a literal — and `omega.conditions.validate_conditions` checks all three
against what the report actually compiles to:

```python
from omega.conditions import condition, is_, validate_conditions

conds = [condition("BAD", "wrong", is_("RSI14_now", "rising"))]
validate_conditions(report, conds)
# [error] BAD.definition: 'RSI14_now' does not accept 'is'. Allowed: ['lt','lte','gte','gt','between']
```

It catches:

- a header no column in the report produces (and none of the ambient ones)
- an operator the output doesn't offer — `is` on a numeric, `gt` on a classification
- a label outside the header's vocabulary (`RSI14_zone` is `overbought|oversold|neutral`)
- a `sectionKey` that doesn't match where the header lives
- `N_OF` with `n` greater than the member count — **can never be true**
- `N_OF` with `n` equal to the member count — a warning; `ALL` says it more plainly
- `NOT` with more than one member, empty groups, self-references, dangling `conditionRef`s
- duplicate keys, malformed keys, `between` with `low >= high`, budget overruns

`validate_market_read` does the same for `marketReadText`: every `{TOKEN}` must resolve to a
condition key or a header.

> Building this caught two bugs in `omega.fanout`'s header prediction: `classifyZone` emits
> `{code}_zone` (not `{code}`) and `crossDetect` emits `{code}_cross`, both with
> vocabularies. Neither appeared in the original 20 compiler probes. They are fixed and
> regression-tested against the live render.

## Generated conditions

`plan()` emits a **layered DAG**, not one flat checklist. Building blocks carry
`verdict: null` and are composed by `conditionRef` into the two verdict-bearing conditions:

```
{P}_RISK_ON    stablecoin pairs at par             ambient - free
{P}_CTX_UP     tape / crowd context for longs      ambient - free
{P}_CTX_DOWN   tape / crowd context for shorts     ambient - free
{P}_CORE_UP    N_OF checklist over your modules    your columns
{P}_CORE_DOWN  ...
{P}_UP         ALL(CORE_UP, CTX_UP, RISK_ON)       -> verdict UP
{P}_DOWN       ALL(CORE_DOWN, CTX_DOWN, RISK_ON)   -> verdict DOWN
```

Seven conditions against a budget of 16, and **three of them cost nothing** — the context
and risk layers read only ambient headers.

```
conditions          7
  MR_RISK_ON       -        Stablecoin pairs at par
  MR_CTX_UP        -        Crowd leaning down - room to fade up
  MR_CTX_DOWN      -        Crowd leaning up - room to fade down
  MR_CORE_UP       -        2 of 4 filters agree - up
  MR_CORE_DOWN     -        2 of 4 filters agree - down
  MR_UP            UP       Setup confirmed - up
  MR_DOWN          DOWN     Setup confirmed - down
```

`marketReadText` references only the two verdict conditions, so the agent reads a verdict
rather than a lattice.

### Stance decides which reading a module gets

A `Thesis` carries a `stance`, and it is not cosmetic. The same module means opposite
things to opposite theses:

| module | `ALIGN` (trend) | `FADE` (contrarian) |
|---|---|---|
| `BOLLINGER` | `pctB_now > 0.95` — buy the breakout | `pctB_now < 0.05` — buy the lower band |
| `RSI` | `RSI14_now > 50` — buy strength | `RSI14_now < 35` — buy the oversold |
| `MFI` / `STOCHASTIC` | zone `overbought` | zone `oversold` |

Without this split the generator produced clauses that were **legal but backwards**: a
mean-reversion thesis buying strength while claiming to fade it, and a squeeze-breakout
thesis buying the *lower* band. Nothing in validation catches that — the clauses type-check
perfectly. Only the semantics are wrong, which is exactly the kind of error that survives
into production.

### The free context layer

`omega.conditions` ships clause builders over the ambient sections:

```python
tape_bullish(10.0)        # mktBreadth_all > 10
tape_bearish(-10.0)
crowd_leaning_up(60.0)    # fieldUpBias_session > 60
crowd_leaning_down(40.0)
crowd_concentrated(40.0)  # captConc_session > 40
stables_at_par(0.5)       # both deviation pairs within +/-0.5% - a risk-off veto
```

An `ALIGN` thesis wants the tape agreeing with its direction. A `FADE` thesis wants the
**crowd leaning the other way** — you buy when the field is short. `stables_at_par` is a veto
either way: a depeg is the market saying something the indicators have not priced.

## Checking against live market data

`preview_strategy_report` renders a draft report *and its conditions* against live prices —
explicitly **"without saving or mutating strategy state"**. It returns per-clause evidence:

```jsonc
{"conditionKey":"TC_UP","outcome":"FALSE","evidence":[
  {"header":"MAalign","op":"is","operand":"bullish","literal":"bullish","outcome":"TRUE"},
  {"header":"MACD_trend","op":"is","operand":"falling","literal":"rising","outcome":"FALSE"},
  {"header":"OBV_trend","op":"is","operand":"rising","literal":"rising","outcome":"TRUE"},
  {"header":"ADX_now","op":"gte","operand":"11.7","literal":"25","outcome":"FALSE"}],
 "provisional":true}
```

It also returns `markerConditions[].unreferenceableReason` (null when a condition can be
referenced), `marketReadMarkers` resolving each token as `condition` or `column`, and the
server's own `estimatedTokens` as used/cap.

**Use it before committing a report.** It is the authority on token cost — see the honest
caveat in [04](04-section-report-budget.md).

## Verified live

A generated `squeeze-breakout` plan went to `preview_strategy_report` with its full DAG:

```jsonc
{"conditionKey":"SB_UP","outcome":"FALSE","evidence":[
  {"kind":"conditionRef","conditionKey":"SB_CORE_UP","outcome":"FALSE"},
  {"kind":"conditionRef","conditionKey":"SB_CTX_UP","outcome":"TRUE"},
  {"kind":"conditionRef","conditionKey":"SB_RISK_ON","outcome":"TRUE"}]}
```

**`conditionRef` resolves and reports each reference's own outcome.** The ambient layers
evaluated against real market-wide data — `usdtUsdDev_market: -0.01%`,
`usdcUsdtDev_market: +0.01%`, `mktBreadth_all: 69.2% of 78` — while `sectionColumns used`
stayed at **4**, counting only the report's own columns. The context and risk layers were
genuinely free.

One further detail: the ambient conditions came back `provisional: false` while the
column-based ones were `provisional: true`. Ambient data is not read off a live forming bar,
so it cannot change under you before the bar closes.

## Verification

Both generated conditions for `trend-continuation` were submitted to the live
`preview_strategy_report` alongside their report and `marketReadText`. Every clause header
resolved, both conditions evaluated with full evidence, and both marker tokens came back
`status: "condition"` with `unreferenceableReason: null`. All five presets type-check with
zero errors offline.
