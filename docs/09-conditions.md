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

`plan()` emits one `UP` and one `DOWN` confluence condition over the thesis's weighted
modules, modelled on El Alamein:

```
conditions          2
  TC_UP            UP       2 of 3 filters agree - up
  TC_DOWN          DOWN     2 of 3 filters agree - down
```

```jsonc
{"kind":"group","op":"ALL","members":[
  {"kind":"group","op":"N_OF","n":2,"members":[
    {"kind":"clause","column":{"sectionKey":null,"header":"MAalign"},"op":"is","label":"bullish"},
    {"kind":"clause","column":{"sectionKey":null,"header":"MACD_trend"},"op":"is","label":"rising"},
    {"kind":"clause","column":{"sectionKey":null,"header":"OBV_trend"},"op":"is","label":"rising"}]},
  {"kind":"clause","column":{"sectionKey":null,"header":"ADX_now"},"op":"gte","value":25}]}
```

The checklist is `N_OF` at two-thirds of the directional modules; non-directional modules
(trend strength, volatility) become filter clauses in the surrounding `ALL`. Custom sections
get a deterministic `sectionKey` (`custom:<uuid5 of the title>`) so clauses can name them.

`marketReadText` is generated to reference each condition by key, and validated:

```
Trend Continuation. Full MA alignment with trend strength, entered on momentum resumption.

- {TC_UP} (UP) - 2 of 3 filters agree - up.
- {TC_DOWN} (DOWN) - 2 of 3 filters agree - down.

Read these verdicts rather than re-deriving them from the columns.
```

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

## Verification

Both generated conditions for `trend-continuation` were submitted to the live
`preview_strategy_report` alongside their report and `marketReadText`. Every clause header
resolved, both conditions evaluated with full evidence, and both marker tokens came back
`status: "condition"` with `unreferenceableReason: null`. All five presets type-check with
zero errors offline.
