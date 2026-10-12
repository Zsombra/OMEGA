# 09 · Conditions

Deterministic reads of your report columns, resolved server-side and surfaced to the agent
as a named verdict.

---

## What conditions are not

> **Superseded 2026-10-11 by contract 108:** conditions are now the *only* entry gate — see
> [the 108 section](#2026-10-11-contract-108--conditions-are-the-only-entry-gate) at the end. The
> text below describes the platform before 108 and stays as history.

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

## At contract 91 (2026-10-06): a hold on every node, and exit rules

The section above is the 61.0.1 grammar and stays as history. Two contracts reshaped the
condition since; both are read from the README's contract history and the saved 91.0.0
`CONDITIONS` axis ([`schema_20261005T194629Z.json`](../data/contract/stage_strategy_draft/schema_20261005T194629Z.json)).
A condition is now exactly six keys, all required: `conditionKey, name, definition, verdict,
required, exitSide`.

**v84 — the hold moves onto each clause and group.** `closes` is refused. "Every clause and
every group requires `hold: { atLeast, of }`, whole numbers of at least 1": `{1,1}` is one read
(what `closes: 1` did), `{n,n}` is n closes in a row, `{1,n}` is within n closes, anything else
at least m of n. A `conditionRef` carries none. There is no fixed 1–5 ceiling any more: each
column serves `conditionHold {timeframe, maxWindow, maxAtLeast, refusal}`, and the builder
judges the window, `atLeast` above `of`, and "a group hold over members that hold their own
bars".

**v88 — an exit rule names the side it closes.** `exit` is refused; `exitSide` is "nullable,
never optional": `null` for an entry condition, `LONG` / `SHORT` / `BOTH` for an exit rule. An
exit rule carries `verdict: null` and `required: false`, and an entry condition cannot reference
one (`CONDITION_EXIT_RULE_CARRIES_VERDICT`, `CONDITION_EXIT_RULE_REQUIRED`,
`CONDITION_ENTRY_REFERENCES_EXIT_RULE`). A stored `exit: true` condition was split by the
platform: it keeps its verdict as an entry condition, and its strategy gains `CLOSE_ON_<key>`, a
`conditionRef` to it closing the side its verdict opposed (`UP` → `SHORT`, `DOWN` → `LONG`,
`NEITHER` or `null` → `BOTH`).

**In omega:**

```python
num("RSI14_now", "gt", 50)                       # ... "hold": {"atLeast": 1, "of": 1}
num("RSI14_now", "gt", 50, hold=held(3))         # 3 closes in a row
condition("K", "n", all_of(a, b), hold=held(3))  # the CONDITION's hold: on the root, members at {1,1}
exit_rule("STOP", "n", not_(ref("SETUP")), "LONG")
close_on(setup)                                  # the v88 split: CLOSE_ON_SETUP, side from the verdict
```

`close_on` refuses a source key longer than 31 characters (the prefix would push the key past
`^[A-Z][A-Z0-9_]{1,39}$`) instead of truncating it, and names the rule `Close on <key>` — the
platform's migrated name is not published.

`validate_conditions` checks the six keys (the three retired ones are errors naming the contract
that retired them), `exitSide`, a schema-shaped `hold` on every clause and group and none on a
ref, `atLeast ≤ of`, the group-over-held-members refusal, and the three v88 codes. The exit read
rule now applies to exit rules (a `CLOSE_ON_<key>` reads its source's whole closure, so a split
over an ambient header is refused offline), and the verdict read rule is unchanged.

**What became a warning.** No v84+ vocabulary read is on disk, so the per-column `conditionHold`
is unknown offline (measurement M2 of the plan). The 61.0.1 operand rule
(`CONDITION_HOLD_OPERAND_ILLEGAL`: a hold above one read only over a confirmed, offset-0,
at-or-above-anchor candle header) and the hold-over-references rule (`CONDITION_HOLD_ILLEGAL`)
are therefore **warnings**, never errors — a clause is judged over the widest `of` on its path,
so a `{1,1}` clause under a group holding 3 bars is read over 3. The four unmeasured cells in the
table above are unchanged.

The presets still hold one read everywhere and declare no exit; `Thesis.exits` opts a generated
condition into its `CLOSE_ON_` rule (see [08](08-strategy-generation.md)).

## 2026-10-11: contract 108 — conditions are the only entry gate

"Signal rules, the aggregate-score gate and the required-count gate are removed … A strategy's
deterministic entry gate is its conditions: a required condition, or a condition that carries a
verdict. A strategy that declares neither never trades, and its draft says so with the warning
`NO_ENTRY_CONDITION`" (README "Contract history — v108"). The served `stage_strategy_draft`
description narrows it to entry conditions: "the only deterministic entry gate — with no required
and no verdict-carrying entry condition the strategy never routes, and the draft warns
NO_ENTRY_CONDITION" ([`schema_20261010T215326Z.json`](../data/contract/stage_strategy_draft/schema_20261010T215326Z.json)).
The draft's warning enum is now that one code, and `diagnostics.mismatches` is gone. The condition
grammar did not move at 108: the `CONDITIONS` axis is identical at 106 and 108, six keys as at 91.
It did move between 91 and 106, and omega has not followed yet: the 64-item cap is gone, and the
clause arms gained `crossesAbove` / `crossesBelow` (numeric arm), `enters` / `exits` (label arm) and
a fifth arm `increased` / `decreased` with no operand (README "Contract history — v98 (a clause can read the bar before)").
omega's builders and `validate_conditions` still model the 91 operators only; nothing it generates
uses the new ones, and the preflight walks them against the schema.
*(Closed the same day — see [the condition vocabulary at contract 108](#2026-10-11-the-condition-vocabulary-at-contract-108)
below.)*

So "What conditions are not", above, is history: since 108 they gate entry. Two things already
gated before — `required: true` (a FALSE reading blocked the trade) and, since 56.1.0, the resolved
verdict binding direction — and they are now the whole gate.

**In omega:**

```python
entry_gates(conditions)        # the keys of every ENTRY condition (exitSide null) that is
                               # required or carries a verdict (UP / DOWN / NEITHER)
validate_entry_gate(conditions)  # [] or one ERROR: "NO_ENTRY_CONDITION: ..."
```

`validate_entry_gate` is kept apart from `validate_conditions`, which type-checks any set of
conditions — fragments included — and has no opinion about completeness. `StrategyPlan
.condition_findings()` runs both, so the critique and battlegrid-manager's checks carry the finding;
`authoring.validate_thesis` reports it under the code `NO_ENTRY_CONDITION` from the conditions
`_build_conditions` would generate. The platform warns; omega refuses, because a strategy that can
never trade is not a plan. An exit rule never counts, even a malformed one carrying a verdict.

**What the generator does.** `_build_conditions` is unchanged: the seven roles, with `{P}_UP` and
`{P}_DOWN` the verdict carriers, so every thesis with two or more directional modules has an entry
gate of two conditions and every preset passes. Below two directional modules it emits nothing —
which was already `THESIS_TOO_FEW_DIRECTIONAL` and is now also `NO_ENTRY_CONDITION`. No generated
condition is `required`; a required veto is still the author's call.

**Unmeasured.** Whether the platform counts a strategy whose only verdict carriers are `NEITHER` as
having an entry gate (the wording "carries a verdict" says yes, and omega follows it) — and whether
such a strategy can ever enter, since a resolved `NEITHER` admits no side (vendor strategy-examples
skill, exported at contract 105). TPO suite members S1 and S7 are exactly that case; their design
records say so (`entryGate.note`). Also unmeasured: what the gate does with a required condition
that reads UNRESOLVED.

## 2026-10-11: the condition vocabulary at contract 108

Since 108 the conditions are the whole entry gate, so the condition vocabulary is omega's core. It is now
**derived**, not typed: `omega.condition_vocabulary.derive` walks the saved 108 write schema
([`schema_20261010T215326Z.json`](../data/contract/stage_strategy_draft/schema_20261010T215326Z.json)) and writes
[`condition_vocabulary_108.json`](../data/derived/condition_vocabulary_108.json) — every clause arm, operator,
operand, the hold, the column, the ref and group arms, the condition object, the per-header fields the preview serves,
and the REPORT column's `metric` / `transformId` / `chainedTransformId` enums, each with its JSON Pointer into the
schema file. `tests/test_condition_vocabulary_108.py` re-derives it on every run, so the next schema swap shows up as a
diff of that file (`python scripts/derive_condition_vocabulary.py` rewrites it; `--check` only compares).

**The grammar the schema admits.** Thirteen clause operators in five arms, every arm
`additionalProperties: false`, every one carrying `hold {atLeast, of}` (integers ≥ 1):

| arm | operators | operand |
|---|---|---|
| 1 | `lt` `lte` `gte` `gt` **`crossesAbove` `crossesBelow`** | `value`: a number |
| 2 | `between` | `low`, `high`: numbers |
| 3 | `is` **`enters` `exits`** | `label`: one string, 1–80 |
| 4 | `in` | `labels`: 1–32 strings, 1–80 each |
| 5 | **`increased` `decreased`** | none — a `value` beside them is refused |

So a crossing compares the column with **one number**, never another column (a level break is `dist_<LEVEL>
crossesAbove 0`); `enters` / `exits` take **one label**, never a range or a set; `increased` / `decreased` take **no
operand and no lookback** — "the bar before" is fixed. `conditionRef` is `{kind, conditionKey}` and carries no hold;
a group is `ALL | ANY | NOT | N_OF` over 1–64 members, `n` in 1..64. The conditions array has no bound in the schema
(v103: the budgets judge it — `strategyConditions` 16). `preview_strategy_report`'s `source.conditions` is the same
grammar (`previewConditions.sameGrammarAsStage`).

**In omega:**

```python
crosses_above("RSI14_now", 50)                 # {kind, column, op: crossesAbove, value: 50, hold: {1,1}}
crosses_below("dist_SMA20", 0, hold=(1, 3))    # within the last 3 closes
increased("donchianHi", hold=held(3))          # three rising closes in a row - a change is no edge
enters("RSI14_zone", "overbought")             # the flip; `is` reads the state
exits("kcSqueeze", "on")
```

The builders refuse what the schema refuses (a non-number `value`, an empty or 81-character `label`) and one thing the
changelog states: an **edge** (`crossesAbove`, `crossesBelow`, `enters`, `exits`) held `atLeast` above 1 —
"a hold with atLeast above 1 is refused (`CONDITION_HOLD_ILLEGAL`) — hold them 'within n closes'" (README v98) — and,
from the vendor skill, an `ALL` group held `atLeast` above 1 over an edge.

**`validate_conditions`** checks each clause against the arm the derived inventory names for its `op`, so it **errs
exactly where the schema refuses**: an operator outside the thirteen, a missing operand, an undeclared key beside it
(the `value` on `increased`), a mistyped or out-of-bounds operand. `tests/test_conditions_prior_bar.py` walks every
positive and negative body through both `validate_conditions` and the preflight's schema walk and requires them to
agree.

**What is only a warning, and why.** Which header admits which operator is not in the write schema: the platform serves
it **per header and per strategy** (`conditionOperators` on `preview_strategy_report` at `detail: "detailed"`). omega
reads it offline only from descriptions, so each of these is a warning that quotes its source:

- a header kind the changelog says does not take the operator — "Numeric headers take the crossings and changes;
  classification, direction and boolean headers take the transitions; event and rank headers take none of them"
  (README v98; `CONDITION_OPERATOR_UNSUPPORTED`); a `date` header is named by no sentence and is unmeasured;
- a header omega cannot see the history of — an ambient or timeless header (`chg24h`, `mktBreadth_all`): "a header
  whose `conditionHold.maxWindow` is 1 is served none of the six" (vendor strategy-examples, exported at 105);
- an edge held "in a row", and an `ALL` group held above one read over an edge (the two hold rules above);
- a transition label outside the header's vocabulary (measured for `is`, prose for `enters` / `exits`).

The pre-v98 operators keep their errors exactly as before.

**Metrics.** The 108 column `metric` enum is 171 — the same set, in the same order, as the 104.0.0 / 104.1.0
`get_metric_construction_hints` enum the manager stored. 156 are the measured 61.2.0 extraction; the other 15 (v100:
`CANDLE_DOJI`, `CANDLE_PIN`, `CANDLE_ENGULFING`, `BAR_CONTAINMENT`, `GAP`, `GAP_RANGE_CLEAR`, `GAP_PCT`, `CLOSE_RUN`,
`CANDLE_RUN`, `HL2`, `HLC3`, `OHLC4`; v101.1: `SWING_FRACTAL_HIGH`, `SWING_FRACTAL_LOW`, `SWING_FRACTAL_LABEL`) are
**known names** in [`_unmeasured_108.json`](../data/contract/metrics/_unmeasured_108.json): which transforms they
compose, their kind, header and vocabulary are unmeasured (measured live per metric at 61.2.0). `validate_column`
refuses a column over one (`METRIC_UNMEASURED`), the generator never picks one, and `scripts/compare_vocabulary.py`
counts them as stored and names them under `storedUnmeasured`.

**Transforms — a gap recorded, not closed** *(closed 2026-10-12 — see
[03](03-column-compilation.md#2026-10-12-the-column-at-contract-108): `bandTouch` is derived as retired and refused,
`levelInteraction` as unmeasured and refused, `buffer` is modelled, the 64 maxima are gone)*. The 108 `transformId` enum is 17: it adds `levelInteraction` (v100) and
lists `classifyState` (platform-privileged at 61.2.0), and it no longer has `bandTouch`, "retired" at v100. The 61.2.0
corpus and `omega.space` still list `bandTouch` for the band and level metrics; the generator never emits it and the
preflight's schema walk refuses it, but `validate_column` would pass a hand-written one. Refusing it there moves the
681-cell composability space, which is a REPORT re-extraction — its own slice. The same holds for the `buffer` column
knob (v100) and the 64 maxima v103 removed from `window` / `offset` / `columns`.

**Presets.** No preset changed. A new operator goes into a preset only where the preset's own description asks for
it, and none does: all five describe states, not a cross, a flip or a change on the bar before. TPO suite S6 "POC
Cross-Recross" — "One bar that crossed the prior POC and closed back on its original side" — is a single bar's range
crossing and returning, which `crossesAbove` (a close-to-close crossing over two completed bars) does not express; the
README's reading for it is a `levelInteraction` reject, a transform whose admissibility on `PRIOR_TPO_POC` is
unmeasured here. S6 is unchanged.

The record, the unmeasured list and the live reads that would close it:
[`docs/plans/2026-10-11-omega-condition-vocabulary-108.md`](plans/2026-10-11-omega-condition-vocabulary-108.md).
