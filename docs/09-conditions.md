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

**You may supply your own `sectionKey` on a PREVIEW, but not on a CREATE.**
`preview_strategy_report` accepts `custom:<uuid>` as given rather than minting one, which
removes the compile-first step when *drafting* conditions — used throughout the 2026-09-10
TPO session without a single refusal.

`compile_strategy_plan` with `operation: CREATE` refuses it (measured 2026-09-10):

```
REPORT_CUSTOM_SECTION_NOT_OWNED
  Custom section 'custom:7b0d4a1e-…' does not belong to this strategy.
  rule: omit sectionKey on a new custom section — the server derives it from the section
```

Which is coherent: on a CREATE the section does not exist yet, so it cannot be owned. The
earlier form of this paragraph asserted the permissive behaviour without qualification; it
was almost certainly measured on an UPDATE, where the section already exists.

**The workaround on CREATE is `sectionKey: null` in the clause**, and it is confirmed: all
three conditions of `56c08ef6` were submitted with `sectionKey: null` and read back carrying
the server-minted `custom:88da7c5c-…`.

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

## The condition clock (deployed 2026-08-29, schema published 2026-08-30)

Every condition now carries two more required fields — the compile refuses their
absence:

- **`clock`**: `'LIVE' | 'CLOSE'`. What frame the condition's reads resolve
  against. `LIVE` reads the current forming state; `CLOSE` reads the last closed
  bar. LIVE is the permissive clock and the platform's own migration default —
  every pre-existing condition was migrated to `clock: "LIVE"` without a revision
  bump (read back from `6a8bca67` on 2026-08-29 and again 2026-08-30).
- **`closes`**: integer 1..5 (schema bounds). Semantics for values above 1 are
  **unmeasured**; omega emits 1 everywhere.

`CLOSE` is the restricted clock, with one measured rule
(`CONDITION_CLOCK_OPERAND_ILLEGAL`, 2026-08-29):

> a CLOSE-clocked condition may only read headers resolved from the coin's own
> candle series, at offset 0

An ambient header (`reference-pairs.*`, `market-breadth.*`, `session-field.*`)
never comes from the coin's candles — "a closed bar frame cannot move it, so it
would read the same number on every close." The refusal's prescription: put the
clause in its own LIVE condition and reference it **from a LIVE condition**.
Timeframe-inert metrics (`FUNDING_RATE`, `OI`, `REGIME_*`, ...) fail the same
test even from a custom section.

**omega's clock policy** (`generate._build_conditions`, decision 2026-08-29):
ambient conditions and the composite verdicts run LIVE; the CORE checklists run
CLOSE only when every contributing module reads the coin's own candle series
(stable reads, matching the closed-bar research); a checklist touching any inert
module stays LIVE. The offline guardrail in `conditions.validate_conditions`
mirrors the rule: a CLOSE condition reading anything but a custom-candle-section
header at offset 0 is an error, as is a CLOSE condition referencing a LIVE one.

This dovetails with the `provisional` flags above: ambient conditions came back
`provisional: false` precisely because ambient data is not read off a live
forming bar. The clock axis makes that distinction author-controlled.

## Measured 2026-09-11: first-true-wins makes condition order into control flow

Verdict resolution is **first-true-wins in array order**. That means the condition array is
not a set of independent tests — it is a `switch` with fall-through. A broad condition
placed early **shadows** every condition below it, which can then evaluate TRUE on most of
the universe and still never decide anything.

Measured on `3d720de3` revision 1 across all 36 active CRYPTO instruments:

| # | conditionKey | verdict | fires | decides |
|---|---|---|---|---|
| 0 | ABOVE_VALUE | UP | 2/36 | 2/36 |
| 1 | VAL_REJECT_DN | DOWN | 1/36 | 1/36 |
| 2 | VAH_CONFLUENCE_DN | DOWN | 13/36 | 12/36 |
| 3 | VAL_CONFLUENCE_UP | UP | 32/36 | 19/36 |
| 4 | SHAPE_B | DOWN | 9/36 | 1/36 |
| 5 | SHAPE_P | UP | 9/36 | **0/36** |
| 6 | BELOW_VALUE | DOWN | 14/36 | 1/36 |
| 7 | POC_ABOVE | UP | 26/36 | **0/36** |
| 8 | INSIDE_VALUE | NEITHER | 34/36 | **0/36** |
| 9 | SHAPE_BALANCED | NEITHER | 18/36 | **0/36** |
| 10 | NO_DECISIVE_LOCATION | NEITHER | 22/36 | **0/36** |

Five conditions fired and never decided. `POC_ABOVE` was TRUE on 26 of 36 and decided
nothing, ever. Reproduce with `scripts/tpo_condition_reachability.py`.

**`fires` without `decides` is dead code.** Audit any condition set by that pair, not by
whether each clause evaluates.

Two consequences worth keeping:

- **Ordering substitutes for boolean composition.** A `clause` references one column, so
  "inside value" needs `VAL < 0 AND VAH > 0`. But placing `ABOVE_VALUE` and `BELOW_VALUE`
  first means anything reaching the third position *is* inside value — the conjunction comes
  free from the order, with no `group` needed.
- **Rare is not unreachable.** A condition at index 0 with nothing above it to shadow it can
  legitimately decide 0 on a given day. Distinguish "shadowed" from "did not happen" before
  calling a condition dead.

### A one-sided clause mislabelled as a two-sided state

`INSIDE_VALUE` tested only `pTpoVAH_close_spread`. "Close is below prior VAH" is true both
when price is inside value **and** when it is below it, so it fired on 34/36 — including all
15 instruments that were *below* value. The `conditionKey` claimed a containment the clause
never checked. A threshold can also sit outside the whole observed range: `VAL_REJECT_DN`
required `>= 6.42` while the 36-instrument range topped out at `+6.26`, so it was dead by
construction.

## Measured 2026-09-11: three different rules for `sectionKey` across three calls

| call | `sectionKey` |
|---|---|
| `CREATE` | **refuses** a caller-supplied key — `REPORT_CUSTOM_SECTION_NOT_OWNED` |
| `UPDATE` | accepts the section's own owned key |
| `preview_strategy_report` | **requires** a non-null string matching a `custom:<uuid>` regex |

`preview_strategy_report` also requires the `benchmarkTicker` and `notes` **keys to be
present**; `benchmarkTicker` may be `null` but `sectionKey` may not. That is zod
`.nullable()` versus `.optional()` — the key must exist, the value may be null. Omitting
`benchmarkTicker` entirely returns `Required`; passing `null` is accepted and is what both
live strategies carry.

## Measured 2026-09-11: the write path's remaining shapes

- **`apply_strategy_plan` takes `{request: {planToken, confirm: true}}`.** A bare
  `{planToken}` is refused, and `confirm` must be the literal `true` — an explicit write
  gate, not a default.
- **`UPDATE` merges.** Omitted fields are preserved: on `56c08ef6` rev 4, omitting `entry`,
  `minAggregateScore` and `signalRules` kept all three exactly. This is what makes it safe
  to send only `sections` and `conditions` to a routing strategy without disturbing its
  weighted signals.
- **`coinSelection` is required on `UPDATE` but is not persisted** — it reads back `null`.
  It is a compile-time input used to run the internal validation preview, so a small
  universe forced by the byte cap does **not** restrict the strategy at runtime.
- **`compile_strategy_plan` runs its own preview and shares the 256,000-byte cap.** The cost
  is linear and was measured: 36 coins → 523,926 bytes; 24 → 409,162; 18 → 351,960; 14 →
  313,702; 12 → 294,652; 10 → 275,534; 8 → 256,420. That is **≈9,550 bytes per coin on
  ≈180,000 bytes of fixed overhead** (fitted intercept 180,126; predicted 256,526 at 8 coins
  against 256,420 measured). The fixed overhead includes the echoed `intentSummary` and
  `assumptions`, so **verbose assumptions shrink the universe a compile will accept.**
- `get_agent_coin_qualification` takes `coinTickers` as an **array** and refuses `symbol`.
