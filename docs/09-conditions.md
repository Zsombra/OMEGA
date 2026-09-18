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

*(2026-09-18: the served shape is seven keys — `exit` and `closes` join these five, and
`clock` was retired. See [The hold count](#the-hold-count-the-clock-was-retired-in-contract-6100)
below.)*

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


## Measured 2026-08-24: the layer is wider and shallower than it looks

### `benchmarkTicker` pins a whole section to one ticker

A custom section carries `benchmarkTicker`. Setting it does **not** change what the
columns compute — it changes *whose* data they read. The section renders a single row
for that ticker, identical for every coin being evaluated:

> "Every reading below is BTC's, not the coin being evaluated — this section is bound
> to BTC."

That is the cross-asset primitive. Two sections with identical columns, one bound and
one not, put `this coin` and `BTC` side by side in the same report.

### Headers collide inside a section, not across sections

When two sections emit the same header, the platform qualifies the marker tokens with
the section key — `custom:aaaa….chg24h` rather than a bare `chg24h` — and a condition
clause addresses each by naming its `sectionKey`. Verified: `COIN_UP_24H` on the
unbound section and `BTC_STRONG` on the bound one resolved independently, and a group
over both produced a correct relative read (TRUE on ETH and SOL, FALSE on DOGE).

**You may also supply your own `sectionKey`** on a custom section — the server accepts
`custom:<uuid>` as given rather than minting one. That removes the compile-first step
when authoring conditions, since you already know the key you will reference.

### A null value reads FALSE, not UNRESOLVED

The platform documents three outcomes, and its own boilerplate is explicit:

> "TRUE / FALSE / UNRESOLVED are three distinct states; UNRESOLVED means an input was
> missing, not that the read was false."

It does not behave that way for null column data. `crowdAccLive` rendered `—`, and
`crowdAccLive gt 50` returned **FALSE**, with the evidence line carrying
`operand: "—"`. The connective table follows from that, and is plain two-valued logic:

| expression | members | result |
|---|---|---|
| `ALL` | TRUE, null | FALSE |
| `ANY` | TRUE, null | TRUE |
| `ANY` | FALSE, null | FALSE |
| `NOT` | null | TRUE |
| `N_OF n=1` | TRUE, FALSE, null | TRUE, `unresolvedCount: 0` |

`unresolvedCount` stayed at zero throughout, so the null never entered the third state
at all. **Whatever reaches UNRESOLVED, it is not a null column value** — which is the
obvious path and the one an author would assume.

This matters for design. `crowdAccLive` is null whenever no concurrent sessions are
running, which is most of the time. A condition on it reads FALSE, and FALSE is
indistinguishable from "the crowd was measured and was wrong."

## The hold count (the clock was retired in contract 61.0.0)

A condition carried a `clock` from 2026-08-29 (deployed) and 2026-08-30 (published) until
contract 61.0.0 retired it. The compile definition captured on 2026-09-18 at 08:33:59 UTC
(contract 61.0.1, build `7296172b`,
[`schema_20260918T083359Z.json`](../data/contract/compile_strategy_plan/schema_20260918T083359Z.json))
declares a condition's required keys as
`[conditionKey, name, definition, verdict, required, exit, closes]` with
`additionalProperties: false` — seven keys, no `clock` among them. The platform migrated
the stored records without a revision bump, as it has every time: `824f4343`, created
2026-09-03 and still at revision 1, reads back seven-key conditions with no `clock`
([`824f4343…_20260918T084500Z.json`](../data/contract/get_strategy/824f4343-e51f-4e5a-87b1-6b44d0bc547f_20260918T084500Z.json)).
The vendor pack (31.2.28, `battlegrid-strategy-examples` § Conditions) states both halves:

> `{ conditionKey, name, definition, verdict, required, exit, closes }` — all seven
> required, no defaults. A `clock` key is REFUSED: the per-condition evidence clock was
> retired in contract `61.0.0`.

> **Every condition is decided at the strategy bar's close.** There is no per-condition
> clock. Which bar a condition reads is decided by the surface asking — a decision (the
> radar's close decision, the compose that takes the trade, the exit sweep) reads completed
> strategy bars; a display read shows the forming one and decides nothing — and by each
> candle column's own Confirmed / Developing selector.

So what used to be an author-controlled axis is now two things the author does control: the
column's `bars` selector, and the hold count.

**The hold.** `closes` is the number of consecutive completed strategy bars a condition must
read TRUE, bounded `1..5` with `multipleOf: 1` in the capture. The vendor:

> `closes` is how many consecutive COMPLETED strategy bars must read TRUE (1–5). A hold
> counts the same completed bars whichever surface asks, so a held condition reads them on
> the display lane too. Above `1` it is legal **only** where a completed bar changes the
> reading: over a header resolved from this coin's own candle series, at offset 0, at or
> above the strategy timeframe, read Confirmed. Everything else is refused
> (`CONDITION_HOLD_OPERAND_ILLEGAL`) … A hold also needs a clause of the condition's OWN
> (`CONDITION_HOLD_ILLEGAL`): a referenced condition is resolved once and contributes the
> same answer to every frame, so a hold that moves with the bar only through a reference
> would count reads that never happened.

**The verdict read rule.** A carrier may not read a bar that is still in progress:

> A verdict carrier must read no DEVELOPING bar. A verdict is refused over any closure that
> reads a column selecting Developing above the strategy timeframe
> (`CONDITION_VERDICT_READ_ILLEGAL`). The closure is what the condition reads directly plus
> everything reached through `conditionRef`, transitively: a referenced condition
> contributes what IT reads, so moving the clause into a building block does not launder it.

**The exit read rule.** `exit: true` needs operands that a completed bar actually moves:

> Legal only over a closure every operand of which a completed bar MOVES
> (`CONDITION_EXIT_READ_ILLEGAL`), which rules out a developing read — a bar in progress is
> the forming bar, and an exit fired on one is an intrabar exit — and rules out a
> frame-inert operand, which could never fire.

The three rules share one vocabulary, `bars` per candle column:

> `"closed"` is Confirmed — the newest bar completed at the strategy close — and `"all"` is
> Developing, the higher-timeframe bar still in progress at that close, which REPAINTS until
> it completes. Left unset the default is a rule, not a value: Confirmed for a column ABOVE
> the strategy timeframe, and at or below it the series as the frame carries it.

**A forming bar at the anchor is not a developing read** (ruling recorded 2026-09-18 while
this was implemented). `developing` is *above the anchor and `bars: "all"`* — a column at the
strategy's own timeframe reading `"all"` is not a developing read, so a hold or an exit over
it stays legal offline. That is the vendor's own sentence: "At or below the strategy
timeframe the choice therefore sets only what the live lane shows — no bar is in progress at
the anchor's own close — so Developing there is legal and changes no decision."

**What omega checks offline.** `conditions.report_headers(report)` classifies every header it
can see from the report it was given: `moved` (a completed bar moves it — the header comes
from a custom section's column on this coin's own candle series, on a non-timeless metric, at
**any** offset), `candle` (`moved` *and* the column reads offset 0), `above_anchor` /
`below_anchor` (the column's timeframe against the report anchor, absolute timeframes ordered
by `absoluteTimeframes` in [`_shared.json`](../data/contract/vocabulary/_shared.json)), and
`developing` (`above_anchor and bars == "all"`). The two operand flags are split because the
two sentences are: the hold sentence says "at offset 0" and lists "a non-zero offset" among
its refusals, and the exit sentence says only "every operand of which a completed bar MOVES",
ruling out a developing read and a frame-inert operand and never mentioning offset. So the
hold rule reads `candle` and the exit rule reads `moved`.

`conditions.validate_conditions` then enforces the four rules above at the clause path, naming
the platform's own error code and the pack version: a hold over anything but a confirmed,
offset-0, at-or-above-anchor candle header (`CONDITION_HOLD_OPERAND_ILLEGAL`); a hold with no
clause of its own (`CONDITION_HOLD_ILLEGAL`); a verdict carrier whose closure reads a developing
higher-timeframe bar (`CONDITION_VERDICT_READ_ILLEGAL`); an `exit: true` whose closure reads a
header no completed bar moves, or a developing one (`CONDITION_EXIT_READ_ILLEGAL`). A leftover
`clock` key is an error that names the retirement. The generator emits `closes: 1` everywhere:
a hold above 1 is legal to author by hand where the vendor says, and remains unmeasured for the
presets.

**Where the offline check is conservative.** A platform-section header (`includeRsi`,
`includeHigherTimeframe`, …) has no column omega can inspect, so it is `moved: False`,
`candle: False` with both timeframe flags `False`; the same holds for the ambient report-level
headers (`market-breadth.*`, `reference-pairs.*`, `session-field.*`). A hold or an `exit: true`
over one of those is refused offline. For the ambient headers that matches the platform's own
reasoning — a closed-bar frame cannot move them — but for a platform-section candle header it
may well be a refusal the platform would not make.

**Where the offline check may be looser.** The check is *not* known to be stricter than the
platform in every direction — that claim was never measured, and nothing here has been sent to
a compile since the retirement. Four cells are **unmeasured**, and in each the offline check
may admit a body the platform refuses. None of them is encoded as a rule, because the evidence
that would ground one does not exist in this repo:

| # | cell | what omega does | why it is unmeasured |
|---|---|---|---|
| a | a column **at** the anchor with `bars: "all"` and `closes > 1` | passes: `developing` is `above_anchor and bars == "all"`, so an at-anchor Developing column is not a developing read | on the strength of the vendor's own at-or-below sentence — "no bar is in progress at the anchor's own close — so Developing there is legal and changes no decision" — recorded as a ruling in the plan, not as a compile result |
| b | a `rank` transform over a candle metric | holdable: `report_headers` classifies by the column's **metric**, and the transform never enters the test | the vendor's `CONDITION_HOLD_OPERAND_ILLEGAL` refusal list names "ranks". Whether that means the `rank` transform, a published rank metric, or both, is not stated and was not probed |
| c | `STRUCT_ZONES` / `PRICE_ZONE` | holdable: both are `timeframeMode: candle`, non-timeless, in the 2026-09-09 extraction | the same refusal list names "zone entities". Which metrics that phrase covers is not enumerated by the vendor and was not probed |
| d | `PDH` / `PDL` | holdable: both read `timeframeMode: candle`, non-timeless, in the 2026-09-09 extraction | the vendor pack says the opposite today — "**The previous-session levels are TIMELESS.** `PDH`, `PDL`, `PDO` and the seven floor pivots … read the session profile, not a candle rung" (31.2.28 § the level layer) — and a timeless operand is frame-inert. The extraction has not been refreshed since 09-09; it is the first `notResolved` item of [`_drift_2026-09-18.json`](../data/contract/_drift_2026-09-18.json), and correcting one metric's flag by hand would be encoding a rule from a source this repo has not extracted |

Rows b, c and d would all be closed by one thing: a refreshed metric/transform extraction at
the served contract. Until that exists, guessing at the refusal list would be inventing rules,
which is the one thing this repo does not do.
