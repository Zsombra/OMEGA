---
name: battlegrid-strategy-examples
description: Full-surface composition patterns for the strategy studio — validated desk-grade examples of custom report sections, benchmark sections, condition trees with verdicts and enforcement gates, tiered signal weights, routing gates, ATR trade levels, and position management. Activate beside strategy-authoring whenever a strategy is being composed or upgraded beyond a basic template.
---

# Strategy Studio — full-power composition patterns

`strategy-authoring` owns the flow (evidence → locked spec → discover → stage → review →
commit). This skill owns **what to compose**: a default build — a few platform sections, no
conditions, untouched weights — wastes the studio. The playbooks below are compiled in CI, so their
shapes are binding in the sense that matters — they are checked, not merely asserted. Loose tokens
elsewhere in this file are not covered by that gate, and vocabulary moves with deploys, so discovery
in the conversation stays the authority — prefer what `list_strategy_vocabulary`,
`get_strategy_column_contract`, and `get_strategy_signal_definition` return over anything
printed here, and read exact headers from a `detail: "detailed"` preview's
`authoring.conditionColumns` before conditioning on them.

## The full-power checklist

Before committing a CREATE, every "no" here is a decision to state, not an omission:

1. At least one **custom section** whose columns encode the thesis — not only platform modules.
2. **Conditions** encode the entry logic: building blocks (`verdict: null`) + verdict carriers,
   and at least one `required: true` condition vetoing obvious disqualifiers **before any
   billing or LLM call**.
3. **Every signal meant to score is named in `rules`** with a deliberate tier — unnamed signals
   keep server defaults (Off on a CREATE). Verify against the rule rows the draft read serves,
   never assume.
4. **Gates** (`minAggregateScore`, `minRequiredCount`, `minAtrPct`) are computed against the
   chosen weight budget, not guessed.
5. **Trade levels + position management** match the setup's geometry and holding period.
6. `marketReadText` states standing orders with `{...}` markers so live values render inline.

## Header grammar (system-generated — never named by the author)

| Transform | Header | Validated example |
|---|---|---|
| `value` | `<code>` | `bbWidthPct`, `RVOL`, `rate` |
| `trajectory` w4 | `<code>_t3…_t1`, `_now`, `_trend` (rising/falling/flat) | `RSI14_now`, `RSI14_trend` |
| `distance` | `dist_<code>` (signed % from price) | `dist_SMA50` |
| `spread` | `<base>_<operand>_spread` | `mark_oracle_spread` |
| `aggregate` wN | `<code>_mean<N>` | `rate_mean24` |
| `rank` | `<code>_rank_<hi\|lo\|far\|near>` — ordinal, `lte N` = top-N | `bbWidthPct_rank_lo` |
| `efficiency` wN | `<code>_er` (1 straight, ~0 chop) | `close_ltf_er` |
| `maxShare` wN | `<code>_maxShare` | `volBase_ltf_maxShare` |
| `classifyZone` / `classifyState` | `<code>_zone` / `<code>_state` | `RSI14_zone`, `ADX_state` |
| `levelInteraction` | `<code>_lvl`, `<code>_lvl_b<N>` at a buffer of N bps | `bbUpper_lvl`, `bbUpper_lvl_b25` |

Non-anchor rungs affix `_ltf` (lower) / `_htf` (regime): `MAalign_htf`,
`zones_htf_support_dist`. Chains are bounded at two: inner `distance`/`spread` → outer
`trajectory`/`aggregate`/`rank` (`EMA5 spread EMA13 × trajectory` →
`EMA5_EMA13_spread_now` + `_trend`).

**Timeframe references are two families.** *Relative* (`anchor`/`lower`/`regime`) re-resolve
when the strategy timeframe changes — `regime` is the anchor's ladder successor (1d for a 4h
anchor). *Pinned* (`{abs: "<tf>"}`) is fixed, ignores anchor retunes, suffixes the literal
(`RSI14_1d`, `dist_SMA200_1d`, `MAalign_1d` — validated), and binds to discovery's
`rankedTimeframes`, a **superset** of the authorable anchor set — `{abs: "1d"}` is valid while
`1d` is not an anchor. `offset: 1` on a pinned `value` column reads the last **closed** bar of
that timeframe (`RSI14[t - 1]`) — the deterministic daily-close read; offset 0 reads the
forming bar (provisional), and offset does not change the header, so one offset per
`metric × timeframe` per section. **Daily-strategy pattern:** anchor 4h, pinned-1d thesis
columns at `offset: 1`, `required: true` daily conditions gating every carrier, anchor-rung
columns only for entry timing and risk — daily inputs then move once per daily close while
stops and time decay keep managing intraday. **Benchmark sections** (`benchmarkTicker: "BTC"`,
required-nullable on every custom section) read the benchmark's values on every row — the
standard market-leader regime gate. Platform `sectionKey`s are their literal keys
(`includeMtfConfluence`). Custom `sectionKey`s are the **server's** to issue, and which of the two
things you do depends on the operation: on a **CREATE, omit `sectionKey` entirely** — supplying one
is refused, since a new strategy owns no custom sections yet; on an **UPDATE or RESTORE, send back
the keys `get_strategy` returned** for the sections you are keeping, and omit it on a section you
add. Either way you never invent one. To section-qualify a duplicated header, read the key from a
`detail: "detailed"` preview's `authoring.conditionColumns` or from the qualified candidates a
`CONDITION_COLUMN_AMBIGUOUS` refusal offers.

**Event columns print only on their event.** `MACD_cross` and `EMA5_13` (Bullish/Bearish) carry a
value on the crossing bar and are null on every other one, which reads as UNRESOLVED. Use an event
column as a TRIGGER inside a carrier, and pair it with a persistent state — a spread sign,
`MAalign` — for regime. A condition that treats an event column as a standing state is unresolved on
nearly every bar, which is a gate that never gates.

**The previous-session levels are TIMELESS.** `PDH`, `PDL`, `PDO` and the seven floor pivots
(`pivotP`, `pivotR1`–`R3`, `pivotS1`–`S3`) read the session profile, not a candle rung, so they take
no timeframe reference at all: bind them `{rel: 'anchor'}` — the default — and they serve the same
previous UTC session from any anchor. An absolute reference is REFUSED at save, including `1d`,
because there is no rung for one to select. They are catalogued price levels, so `dist_PDH gte 0`
composes directly. (`distance` still rejects an `offset`, and a clause still compares a column
with a literal or with its own previous completed bar, never with another column; neither of those
shapes is what a previous-session level needed.) The same holds
for every timeless metric — these levels, funding, the regime and the other bundle
reads: a `value` column over one accepts only `offset: 0`, and a larger offset is REFUSED at save,
because there is no earlier bar to cut back to.

## Conditions

`{ conditionKey, name, definition, verdict, required, exitSide }` — all six
required, no defaults. A `clock` key is REFUSED (the per-condition evidence clock was retired in
contract `61.0.0`), so is a condition-level `closes` key — the hold lives on each clause and each
group (contract `84.0.0`) — and so is a boolean `exit` key: the side an exit closes is its own
`exitSide` (contract `88.0.0`). Clauses — the operator a header takes is served per header
(`conditionOperators`), by its output kind: numeric headers take the comparisons
`lt|lte|gte|gt|between` and the prior-bar operators `crossesAbove|crossesBelow|increased|decreased`;
rank headers take the comparisons only; classification, direction and boolean headers take
`is|in|enters|exits` with the served vocabulary; event headers take `is|in`. Groups:
`ALL | ANY | NOT | N_OF` (with `n`), depth ≤ 2. Every clause and every group carries a required
`hold: { atLeast, of }` — `{ "atLeast": 1, "of": 1 }` is a single read; a clause or group without
`hold` is refused (`CONDITION_HOLD_INVALID`). `conditionRef` composes named conditions (no
cycles; forward refs legal) and carries no hold of its own. `sectionKey: null` is sugar for a report-unique header only.
Verdicts: resolution is taken over the DISTINCT verdicts of the carriers that read TRUE. One
distinct verdict decides, and the first carrier in declaration order carrying it is named as the
decider — so order breaks ties between carriers that AGREE. Carriers that DISAGREE resolve
`NEITHER` and stand the coin aside; declaration order never picks a side between them. Building
blocks carry `null`.

**Prior-bar operators — a column against its own previous completed bar.** A clause compares its
column with a literal, or with the same column's reading on the completed bar before the one it
decides — never with another column. Six operators read that prior bar:

| Operator | Literal | TRUE when |
|---|---|---|
| `crossesAbove` | a number `L` | `x > L` on the decided bar and `x ≤ L` on the bar before |
| `crossesBelow` | a number `L` | `x < L` on the decided bar and `x ≥ L` on the bar before |
| `increased` | none | `x` is strictly above its prior-bar reading |
| `decreased` | none | `x` is strictly below its prior-bar reading |
| `enters` | one label | the label is read now and was not on the bar before |
| `exits` | one label | the label was read on the bar before and is not now |

The crossing boundary is Pine's (`ta.crossover`): a bar sitting exactly on `L` has not crossed until a
later bar closes above it. A change takes no literal at all — `{ "op": "increased" }` with no `value`.
A prior-bar clause reads COMPLETED bars only, on every surface: the decided bar and the one before
it, never the forming bar, so it is never provisional. A failed read on either bar is UNRESOLVED; a
bar with no value (a null) reads FALSE. A header admits them only where its stored history keeps the
bar before: a header whose `conditionHold.maxWindow` is 1 is served none of the six, so
`vol24hUsd increased` is refused (`CONDITION_OPERATOR_UNSUPPORTED`, naming the operators it does
admit), and on a header that keeps them each reads one bar less than its window.

**An edge is held "within n closes" only.** `crossesAbove`, `crossesBelow`, `enters` and `exits` mark
the bar a state changed, so like a crossover event their `maxAtLeast` is 1 — hold them "within n
closes", never "in a row". `increased` and `decreased` are no edge: "3 closes in a row" of
`increased` is three rising closes. A group whose members must all read TRUE together (`ALL`) over an
edge admits "within" only too. Every prior-bar read counts toward the frame-read budget: a clause
held "within 3 closes" reads four bars.

Recipes — each one clause:

- **Close crossed above the 20 SMA** — `dist_SMA20 crossesAbove 0` (the Moving Averages module).
  `dist_SMA20` is the close's distance from the average, so crossing 0 is the close crossing it.
- **RSI entered overbought** — `RSI14_zone enters "overbought"` (the RSI module).
- **Squeeze released** — `kcSqueeze exits "on"`, over a `KC_SQUEEZE` value column.
- **New 20-bar high** — `donchianHi increased`, over a `DONCHIAN_UPPER` value column: the 20-bar
  upper channel rises exactly when the decided bar's high exceeds every high of the 20 bars before it.
- **RSI crossed above 50 within the last 3 closes** — `RSI14_now crossesAbove 50` holding
  `{ "atLeast": 1, "of": 3 }`.

**Two things block a trade, not one.** `required: true` = a FALSE reading blocks compose-trade
before billing. And the RESOLVED verdict binds entry DIRECTION: `UP` admits long setups only,
`DOWN` short only, and `NEITHER`/`UNRESOLVED` admit none — the refused side is absent from the
setups block and from the `decide_trade` contract, not merely discouraged in them. A strategy that
declares no verdict-carrying condition resolves `null` and constrains nothing.

A verdict carrier must read no DEVELOPING bar. A verdict is refused over any closure that reads a
column selecting Developing above the strategy timeframe (`CONDITION_VERDICT_READ_ILLEGAL`). The
closure is what the condition reads directly plus everything reached through `conditionRef`,
transitively: a referenced condition contributes what IT reads, so moving the clause into a building
block does not launder it. A closure whose candle columns all read Confirmed — or whose operands no
bar moves at all, such as a published regime label, an open-interest regime or a published rolling
change — admits a verdict at every decision, because a decision reads the completed strategy bar and
a level is compared against that bar's close.

Evaluation is three-valued: UNRESOLVED never collapses to FALSE; a developing read is provisional,
and so is any reading taken on the display lane's forming bar.

**Every condition is decided at the strategy bar's close.** There is no per-condition clock. Which
bar a condition reads is decided by the surface asking — a decision (the radar's close decision, the
compose that takes the trade, the exit sweep) reads completed strategy bars; a display read shows the
forming one and decides nothing — and by each candle column's own Confirmed / Developing selector.

**Hold — how many closes a clause counts.** A clause's `hold: { atLeast, of }` reads TRUE when the
clause read TRUE on at least `atLeast` of its newest `of` COMPLETED bars — counted on the clause's
OWN column timeframe, not the strategy's: a `4h` column on a `1h` strategy held 3 reads three `4h`
bars. The editor calls the control **Hold** and offers four modes:

| Mode | Hold | Reads as |
|---|---|---|
| Once | `{ 1, 1 }` | a single read of the bar being decided |
| In a row | `{ n, n }` | "3 closes in a row" |
| Within | `{ 1, n }` | "within 5 closes" |
| At least | `{ m, n }` | "at least 2 of 5 closes" |

A hold counts the same completed bars whichever surface asks. Each bar is read or unreadable; an
unreadable bar is never replaced by an older one, and the count decides as soon as the bars read
decide it (TRUE once `atLeast` bars read TRUE, FALSE once the rest can no longer reach it), else
UNRESOLVED.

What a header admits is SERVED, never guessed: every column in the strategy's report catalog
(`preview_strategy_report` at `detail: "detailed"` → `authoring.conditionColumns[].outputs[].conditionHold`, and each scalar metric in
the vocabulary) carries `{ timeframe, maxWindow, maxAtLeast, refusal }` — the timeframe it counts,
the largest `of`, the largest `atLeast`, and, when it admits only Once, why. `maxWindow` is the
history the store keeps for that column, less the column's own lookback and warm-up. A hold past
the served domain is refused (`CONDITION_HOLD_ILLEGAL`, the domain in `allowedDomain`). The reasons
a header admits only Once:

- `NOT_REWINDABLE` — the value is stored for the current bar only (session and universe scalars,
  ranks, zone entities, enrichment metrics, published rolling changes). **Worked liquidity floor:**
  `LIQUID_FLOOR` holds Once because `vol24hUsd` is a bundle scalar.
- `DEVELOPING` — the column reads the bar still forming. **Developing columns cannot be held**; set
  the column Confirmed to count closes.
- `OFFSET` — the column already reads an earlier bar; remove the offset to count closes.
- `BAR_STATE` — the header describes only the bar being decided.
- `HISTORY` — not enough history is stored on that timeframe to count more than one close.

Candle columns (at, above or below the strategy timeframe), the regime (counted on the regime rung),
and the funding and open-interest histories (on the coarser of the strategy timeframe and their own
hourly cadence) can all be held. **A crossover is an event**: it fires on the bar a state changes,
so its `maxAtLeast` is 1 — hold a cross "within n closes", never "in a row".

**Group hold — closes counted together.** A group's `hold` counts its members' joint reading on the
same bar: the group's own outcome, its members folded by its operator, must read TRUE on at least
`atLeast` of its newest `of` bars, counted on its finest member's timeframe. The phrases add
"together": "together on 3 closes in a row", "together within 5 closes", "together on at least 2 of
5 closes". Inside a group holding more than Once, every member holds Once and none is a
`conditionRef` — each read is counted by exactly one hold — so a row holding its own closes, a
reference, or a held group inside is refused, naming the member. A conjunction that needs a
crossover to be TRUE (`ALL(cross, x)`) admits "within" only. Reach for a split to keep a condition's
MEANING separable; a reference carries its condition's one answer for the bar being decided and is
never counted across closes.

**Confirmed / Developing, per candle column.** Every transform whose home is the coin's candle series
carries `bars`: `"closed"` is Confirmed — the newest bar completed at the strategy close — and
`"all"` is Developing, the higher-timeframe bar still in progress at that close, which REPAINTS until
it completes. Left unset the default is a rule, not a value: Confirmed for a column ABOVE the
strategy timeframe, and at or below it the series as the frame carries it. At or below the strategy
timeframe the choice therefore sets only what the live lane shows — no bar is in progress at the
anchor's own close — so Developing there is legal and changes no decision. A condition reading a
developing bar is single-frame: its clause holds Once (a Developing column cannot be held), it
carries no verdict and it cannot be an exit rule. One exception overrides both the stored value and the default: a column reading a metric with
no live value (itself, or a `spread` operand) reads completed bars at every rung, because the forming
bar publishes nothing for it. The resolved answer for a column is served on
`effectiveParameters.bars`, and it states that exception.

**A higher-timeframe level is measured from the current strategy-bar price.** The distance to a `4h`
Donchian band, and every candle label classifier (`MA_ALIGN`, `PRICE_ZONE`, `BB_TOUCH`), compares
against the frame's current price, `LAST` — the strategy bar's close under a decision, the last
traded price on display — not against the higher-timeframe bar's own close, which is up to one
higher-timeframe bar stale. A distance CHAINED into a series transform keeps every slot on its own
bar's close, so one series carries one reference basis.

**The lane a strategy is deployed to.** Report-level scalars split by LANE, and the split is not a
quality of the header — it is which reader runs. Market breadth and the reference pairs are ordinary
market-wide reads with no session dimension, so they resolve everywhere. The five **session-field**
scalars (`fieldPlayers`, `fieldUpBias`, `fieldBiasDir`, `captConc`, `picksSpread`) describe a game
session the agent is playing in, and **radar runs outside one** — so a radar deployment whose
strategy reads one is refused outright (`CONDITION_OPERAND_UNSERVED_IN_LANE`), naming the scalars it
can read instead.

**What the radar scan can read on a coin.** Beyond the lane, a condition the radar acts on — a
required one, one carrying a verdict, an exit rule, and every condition they reference — must be
readable by the radar scan on each coin the radar acts on for the agent, or it would be decided unread.
What a coin can be read for is its market-data profile: the kinds of data the market-data service
publishes that it serves for that coin, never the coin's asset class. A refusal carries
`CONDITION_UNREADABLE_BY_RADAR_SCAN` with its `reachReason`: `INSTRUMENT` when the profile of the coin —
or of a benchmark section's own instrument — carries no such data, or the service publishes no profile
for it at all (spot-tape columns on a coin no spot venue lists, TradFi or crypto alike; any market-data
column on a ticker with no catalog row), `AGENT_TIMEFRAME` when the agent has no such rung on the
enabled ladder, and `FEED` when the radar scan never reads that data for the agent (crowd reads:
compose reads them, but only for a coin the scan has already admitted). An `INSTRUMENT` refusal names
the kind of data the profile lacks, or says the coin has no profile. The fixes it names: take the
condition's radar role away (neither required nor a verdict, or, for an exit rule, its exit role), read a column the radar
scan has on that coin, or free the coin.

**The refusal lands where an agent meets a coin**: at the radar deploy (its preview, the builder's
Save and the draft commit); at a manual entry request, as `CONDITION_UNREADABLE_ON_COIN`;
and, for an agent already deployed or holding a pending manual request, at a
strategy commit (`commit_strategy_draft`, the builder's Save, `restore_strategy`) or a rebind (the
agent draft's STRATEGY_BINDING commit). A commit is checked only on behalf of those agents: a
strategy carries no lane of its own, so one with no agent the radar acts on is never checked, and
the same strategy is legal, and reads session-field scalars correctly, on an arena agent. A draft
may hold such content — staging never refuses a draft for being invalid — but its commit is
refused, so it never reaches the agents.

**Exit rules.** A condition is an entry condition (`exitSide: null`) or an exit rule, never both.
An exit rule's `exitSide` names the side it closes — `LONG`, `SHORT` or `BOTH` — and it has two
effects: a settled TRUE on a completed bar closes the agent's open position on that side, and while it
reads TRUE that side is not offered for entry (a scan qualification or a compose refusal under
`CONDITION_EXIT_RULE_CLOSES_DIRECTION`, after any verdict refusal of the same side). No verdict chooses
the side: an exit rule carries `verdict: null` and `required: false` (`CONDITION_EXIT_RULE_CARRIES_VERDICT`,
`CONDITION_EXIT_RULE_REQUIRED`). An entry condition cannot reference an exit rule
(`CONDITION_ENTRY_REFERENCES_EXIT_RULE`), so editing an exit rule never changes what the agent enters;
an exit rule may reference anything, so "exit when the entry setup stops holding" is an exit rule
whose definition is `NOT` a `conditionRef` to the entry condition. An exit rule is legal only over a
closure every operand of which a completed bar MOVES (`CONDITION_EXIT_READ_ILLEGAL`), which rules out
a developing read — a bar in progress is the forming bar, and an exit fired on one is an intrabar
exit — and rules out a frame-inert operand, which could never fire. A position stamps the exit rules
it opened under, with the report and timeframes they read: an exit-rule edit applies to positions
opened after it, and an open position keeps the exit rules it opened with, so an open position never
refuses a commit or a rebind.

**A state column is not a flip event — `is` reads the state, `enters` reads the flip.** `ST_DIR`
reads the same on every bar of a trend, so `ST_DIR is "bullish"` is a regime filter and never an
entry signal. The flip is `ST_DIR enters "bullish"`: TRUE on the one completed bar the direction
turned, with no event column needed. The same distinction applies to every persisting
classification: `MAalign`, `ADX_state`, `zone` — `is` for the regime, `enters` / `exits` for the
bar it changed.

**Name the anchor when a metric is calibrated for one.** `KC_SQUEEZE is "on"` reads *on* about 57% of
1h crypto bars even at canonical parameters — Bollinger σ is close-to-close while ATR captures
intrabar range, so σ/ATR runs low here — against about 19% at 15m. It is a selective filter at 15m and
below and close to useless at 1h. A metric whose selectivity depends on the anchor is stated with the
anchor, or the author gates on something that admits most bars.

## Bar geometry

What one bar did — against a price level, in its own shape, against the bar before it, and how many
bars ran one way. Every value here reads the bar's own open, high, low and close, so it is a candle
column: it takes a timeframe reference and the Confirmed / Developing selector like any other.

**`levelInteraction` — what the bar did at a level.** It classifies the newest bar of the column as
one of five labels: `touch_from_below`, `touch_from_above`, `reject_from_below`, `reject_from_above`,
`none`. The side is where the PRIOR close stood against the PRIOR bar's level — from below when it
closed at or under it — so a level that moved between the two bars is judged on the bar it stood at.
From below: a bar that closes through the level is a break and reads `none`; a bar whose high
reached the level and whose close came back under it is `reject_from_below`; a bar whose high came
within the buffer of the level is `touch_from_below`. From above is the mirror on the low.

- **A reject bar reports reject.** It is never also reported as a touch, so "touched or rejected" is
  an `in` clause over both labels of a side: `bbUpper_lvl in ["touch_from_below","reject_from_below"]`.
- **`buffer`** is whole basis points of the level, 0–500, default 0 — `buffer: 25` is 0.25%. Only the
  touch reads it: a reject must pierce the level itself. Two buffers are two columns (`bbUpper_lvl`,
  `bbUpper_lvl_b25`).
- **A break is a crossing, never a label.** The break of a level is `distance` over the same level
  crossing 0: `dist_bbUpper crossesAbove 0` from below, `crossesBelow 0` from above. On the strategy's
  own rung a `…_from_below` label never holds on a bar where `crossesAbove 0` holds.
- **Which levels take it.** A candle-homed level — a band (`BB_UPPER`, `BB_LOWER`, `KC_UPPER`,
  `KC_MID`, `KC_LOWER`), `VWAP`, a moving average (`SMA20`, `EMA20`, …), `ST_LINE`, `PSAR`, the
  Ichimoku lines, the swing levels (`SWING_FRACTAL_HIGH`, `SWING_FRACTAL_LOW`) — reads its own value at
  each of the two bars. A prior-session level or pivot (`PDH`,
  `PDL`, `PDO`, `PIVOT_P`, `PRIOR_TPO_POC`, …) has one reading for the session, used as both bars' level;
  a clause over it is a single read with no hold, because the session profile keeps no earlier
  reading. A developing-session level (`TPO_POC`, `TPO_VAH`, …) and the naked points of control move
  between bars with no earlier reading kept, so they are not offered it; neither are the Donchian
  rails (`DONCHIAN_UPPER`, `DONCHIAN_LOWER`), each the extreme of the window ending at the very bar it
  would classify, which a close can never pass. A price fact (`CLOSE`, `HLC3`, `MARK`) is refused: it
  is the price, not a level.
- **A higher-rung level reads that rung's completed bar.** `bbUpper_htf_lvl` classifies the last
  completed regime-rung bar from its own high, low and close, never the strategy bar's price — so
  compose its break on the same rung, `dist_bbUpper_htf crossesAbove 0`.

**`BB_TOUCH` and `BB_UPPER × levelInteraction` answer different questions.** `BB_TOUCH` (`BBtouch`)
says where the CLOSE sits in %B — inside the band edge or not. `BB_UPPER × levelInteraction` says what
the bar's RANGE did at the edge — touched it, or pierced it and closed back.

**Candle patterns** — the bar's shape against the ten bars before it (TA-Lib's default settings). A
pattern carries no trend context: "a hammer in a downtrend" is `pin is "lower_wick"` plus a separate
trend clause.

| Key | Header | Labels |
|---|---|---|
| `CANDLE_DOJI` | `doji` | boolean: the body is at most a tenth of the average range |
| `CANDLE_PIN` | `pin` | `lower_wick`, `upper_wick`, `none` — a short body with one long wick |
| `CANDLE_ENGULFING` | `engulf` | `bullish`, `bearish`, `none` — the body engulfs the prior opposite body |
| `BAR_CONTAINMENT` | `barContain` | `inside`, `outside`, `none` — the range inside, or around, the prior range |

**Gaps** — the open against the bar before it, as three separate keys.

| Key | Header | Reads |
|---|---|---|
| `GAP` | `gap` | `up`, `down`, `none` — the open above the prior high, or below the prior low |
| `GAP_RANGE_CLEAR` | `gapClear` | `up`, `down`, `none` — the whole range clear of the prior range (stricter) |
| `GAP_PCT` | `gapPct` | the signed % from the prior close to the open |

**Runs** — report columns counting consecutive bars, capped at ±20. Gating "three closes in a row" is
the hold's job; a run column shows the streak.

| Key | Header | Counts |
|---|---|---|
| `CLOSE_RUN` | `closeRun` | consecutive closes above (+) or below (−) the close before |
| `CANDLE_RUN` | `candleRun` | consecutive candles of the newest bar's colour, white (+) or black (−) |

**Price sources** — per-bar price facts that take every transform a close takes: `HL2` (`hl2`,
median), `HLC3` (`hlc3`, typical), `OHLC4` (`ohlc4`, average).

**"Within the last N closed bars" is the hold `{ "atLeast": 1, "of": N }`.** A pattern or a gap held
within N reads each of the N bars against its own predecessor.

Recipes — the level recipes on candle-homed levels:

- **Price rejected the upper Bollinger band** — a `BB_UPPER × levelInteraction` column, header
  `bbUpper_lvl`; the clause `bbUpper_lvl is "reject_from_below"`.
- **Price touched or rejected VWAP from above** — `VWAP_lvl in ["touch_from_above","reject_from_above"]`,
  with `buffer: 10` for a touch within 0.1% (header `VWAP_lvl_b10`).
- **Price broke the 20 EMA** — `dist_EMA20 crossesAbove 0`, the `distance` column over the same level.
- **A bullish engulfing within the last 3 bars** — `engulf is "bullish"` holding
  `{ "atLeast": 1, "of": 3 }`.
- **An inside bar** — `barContain is "inside"`.
- **A gap up** — `gap is "up"`; `gapClear is "up"` when the whole range must clear.
- **A run of candles as a report column** — a `CANDLE_RUN` value column (`candleRun`) beside the
  thesis columns; no clause needed.
- **The 20-bar simple moving average of typical price** — `HLC3 × aggregate(20)` with
  `aggregate: "mean"`, header `hlc3_mean20`.

## Swing structure

Swing highs, swing lows and the structure they spell, from the market-data swing engine. Every value
is stored under the bar it describes, so a swing column holds and takes the prior-bar operators like
any candle column.

| Key | Header | Reads |
|---|---|---|
| `SWING_FRACTAL_HIGH` | `fractalHi` | the most recent swing high — a price level |
| `SWING_FRACTAL_LOW` | `fractalLo` | the most recent swing low — a price level |
| `SWING_FRACTAL_LABEL` | `fractalLabel` | `HH`, `HL`, `LH`, `LL`, `none` — the most recent swing against the one before it on its side |

**The rule.** A swing high is a bar whose high is at or above the highs of the two bars before it and
strictly above the highs of the two bars after it; a swing low mirrors it on the lows. An equal extreme
is allowed on the left and not on the right, so of a run of equal highs the newest is the swing (Pine's
`ta.pivothigh(2, 2)`). A swing is published from the bar that completes its right side — two bars
after its own — never earlier and never from a forming bar. Each level is held until the next swing on
its side replaces it.

- **The label is a held state, not an event.** It reads the most recent swing: `HH` / `LH` for a high
  (an equal high is `LH` — it failed to make a higher high), `HL` / `LL` for a low (an equal low is
  `HL`), `none` when no comparable pair is in reach. On too short a history it reads nothing, and a
  clause over it reads FALSE.
- **A swing level does not remember a broken level.** Two to four bars after a break the level steps
  to the next swing, so a retest of the BROKEN level is not a swing-level read.
- **The two levels take what every candle level takes** — `distance`, `spread`, `aggregate`,
  `trajectory`, `efficiency` and `levelInteraction` — and both rank across the board
  (`dist_fractalHi_rank_near`: the coins closest to their own last swing high).
- **The break is the crossing toward the level.** `dist_fractalHi crossesAbove 0` is a close through the
  last swing high and never fires when the level steps onto a new swing, because the bar that confirms
  a swing high sits under it. The opposite crossing (`dist_fractalHi crossesBelow 0`, or
  `dist_fractalLo crossesAbove 0`) CAN fire on the bar the level steps past the close — it is not a
  break.
- **A swing confirmed on the break bar can already have moved the label**, so a structure condition
  paired with a break is held over the bars before it.

Recipes:

- **The swing structure is bullish** — `fractalLabel in ["HH","HL"]`.
- **A higher high was confirmed on this bar** — `fractalHi increased` (it also catches a second
  higher high in a row, which `fractalLabel enters "HH"` cannot); `fractalHi decreased` is a lower
  high.
- **Bullish break of structure** — a `SWING_FRACTAL_HIGH × distance` column, header `dist_fractalHi`;
  the clause `dist_fractalHi crossesAbove 0`.
- **Bearish break of structure** — `dist_fractalLo crossesBelow 0`.
- **A break of the last swing low while the structure was bullish** — `dist_fractalLo crossesBelow 0`
  together with `fractalLabel in ["HH","HL"]` holding `{ "atLeast": 1, "of": 3 }`, so the bullish
  read may sit on the bars before the break.

## Entry

`{ trigger, levelOffsetAtrMultiple, validForBars }` — the axis's keys, and the trigger decides
which of them you send. `ON_CANDLE_CLOSE` is sent ALONE, as `{ "trigger": "ON_CANDLE_CLOSE" }`: a
`levelOffsetAtrMultiple` or `validForBars` beside it is refused as an unrecognized key. A level
trigger — `STOP_THROUGH_LEVEL` or `ON_RETEST` — sends both of them, no defaults. The axis is staged
WHOLE, so a level trigger missing one is refused rather than half-kept. It is not required on every
CREATE: a CREATE that stages no entry takes the platform's seed entry, so stage it whenever the
setup names one. There is no level-source key: the level a level trigger rests at is DERIVED from
the trigger and the trade's direction, never named. There is no confirm-timeframe key either: the
bar whose close decides an entry is the strategy's OWN timeframe.

**Every trigger is decided at the close of the strategy's own bar — there are three, and the close
is the only entry clock.** The newest completed bar is read on the closed basis — every one-close
condition resolves on that bar and the scorecard reads its close — and a reading that still qualifies
fires at that close. A bar that does not qualify decides nothing and is not revisited. The fill lands
at the next tick, and the platform refuses it if the market has already run past its own drift budget
from that close. A fourth value, `AT_SIGNAL`, is readable on strategies authored before this contract
and is REFUSED on every stage and save; there is no live-reading entry to author.

- `ON_CANDLE_CLOSE` — the entry is taken AT the qualifying close, at market.
- `STOP_THROUGH_LEVEL` — at the qualifying close a TRIGGER order rests past the Donchian channel's
  CURRENT edge in the trade's direction (the 20-bar high for a long, the 20-bar low for a short) by
  the offset, and the exchange book is the watcher; the entry is taken when price trades through,
  not when the platform notices.
- `ON_RETEST` — at the qualifying close a LIMIT order rests in front of the edge a close most
  recently BROKE (the channel's break memory: the broken high for a long, the broken low for a
  short) by the offset, waiting for a return to it. Not filling is a correct outcome, not a
  failure; no unrecovered break in memory means no setup, never a fallback level.

**A multi-bar hold belongs to the CLAUSE (or group) that needs it.** Declare that clause's own
`hold` — "3 closes in a row", "within 5 closes" — the entry axis counts no bars, and there is no displacement band: the
platform's entry-deviation gate measures the live mark against the decided close and refuses a fill
that drifted past the budget in either direction.

`levelOffsetAtrMultiple` (0–2) is an UNSIGNED distance from the derived edge in ATR multiples — a
long adds it, a short subtracts it, so a breakout stop rests past its edge and a pullback limit
rests in front of its edge, and a signed value would invert the trigger's meaning. `validForBars`
(1–24) denominates validity in the strategy's OWN bars rather than minutes, because a 1h setup
waiting for a retest has not failed after fifteen minutes. The resting price must sit on the
correct side of the mark when the order is placed — a buy stop above it, a buy limit below it, the
mirror for a sell — or the entry is refused rather than filled at the market; there is no limit on
how far from the mark a level may rest.

**The trigger decides the shape, so there is no inert dial to leave.** Under `ON_CANDLE_CLOSE` the
two parameters do not exist on the input — the server stores its seed values for them — while a
read (`get_strategy`) still shows all three keys. Switching a level trigger back to
`ON_CANDLE_CLOSE` is staging `{ "trigger": "ON_CANDLE_CLOSE" }` alone; never copy the read's
parameters back beside it.

## Report sections

`{ kind, sectionKey, title, benchmarkTicker, notes, columns }` — the custom section shape. A
section carries no `timeframe`: its relative columns resolve against the strategy timeframe, and a
column reaches any other timeframe by pinning it (`timeframe: { abs: '4h' }`). `benchmarkTicker` and `notes` are **required-nullable**: send an explicit `null` rather
than omitting them, because the section is rebuilt whole on save and an omitted key clears the
author's value silently. On a CREATE, omit `sectionKey` — it is derived from the section itself.

## Signal rules

`{ signalId, allocation, required, params }` — one entry per signal you want scoring.
`allocation` is the tier (0–3) and `params` replaces canonical defaults only when present. Staged
into the draft's SIGNAL_RULES axis, every row is complete — `allocation` and `required` on each —
and replaces the drafted row for its signal while every other row is kept.

## Signal weights and gate math

Tiers: 0 Off · 1 Normal · 2 Important · 3 Critical.

```
aggregateScore = Σ(score × allocation) / Σ(allocation)   over triggered signals
```

Weights are relative — build a pyramid: 1–2 Critical (thesis, usually `required`), 2–4
Important (independent confirmation, different modules), 1–3 Normal (context), rest Off so
noise cannot dilute the average. Gate check: with 3/2/2/1 weights, Critical + one Important at
score 1.0 → (3+2)/8 = 0.625, so a 0.6 gate means "thesis plus one confirmation".
`simulate_aggregate_score` does this arithmetic from the draft's values at review time.
`required: true` counts the signal toward `minRequiredCount` when triggered; at
`allocation: 0` it is rejected (contract 34). `params` replace canonical defaults only when
present — read `get_strategy_signal_definition({ signalId, timeframe })` before tuning (e.g.
`rsi_overbought {"threshold": 65}` for a fade book; `volume_surge {"multiplier": 1.5}`).
`derive_strategy_rule_view` shows which signals a draft report feeds — weighting a signal the
report never feeds is dead weight.

## Routing gates

`{ minAggregateScore, minRequiredCount, minAtrPct }` — whether a scored setup may route to a
trade at all. `minAggregateScore` 0–1 · `minRequiredCount` 0–20 · `minAtrPct` is the dead-market
floor, with bounds from `get_trading_config_catalog`.

## Trade levels

`{ minStopLossAtrMultiple, maxStopLossAtrMultiple, minRiskRewardRatio }` — where stops and
targets may sit. `minStopLossAtrMultiple < maxStopLossAtrMultiple` (≤ the 3×ATR structural cap),
`minRiskRewardRatio` within the served range. Sizing is risk-budget based — a wider stop means a
smaller position, never more risk.

## Position management

`{ breakEvenEnabled, breakEvenTriggerR, trailingEnabled, trailingTriggerR, trailingGivebackPct,
trailingBufferPct, timeDecayEnabled, timeDecayGracePeriodMinutes, timeDecayIntervalMinutes,
timeDecayTightenPct, timeDecayMaxTightenPct, timeDecayStaleThresholdTpProgressPct,
decisionInvalidationExitEnabled }` — how the stop moves after entry, and when a position is
closed for reasons other than its stop. The policy is stamped on each position when it opens: an
edit applies to positions opened after it, and an open position keeps the policy it opened with.

Validated bounds: break-even trigger 0.5–2R step 0.01; trailing trigger 0–2R step 0.01 (0 = trail
from entry), giveback 25–55% step 1, buffer 0.01–1% step 0.01; timeDecay grace 5–1440 min step 5,
interval 5–480 min step 5, grace ≥ interval while time decay is armed, tighten 0.5–50% step 0.5,
max tighten 1–100% step 1, stale threshold 0–100% of TP progress step 1. Per-mechanism flags; no
umbrella switch.

`decisionInvalidationExitEnabled` is the post-fill invalidation exit: a **closed**
strategy-timeframe candle beyond the decision's invalidation level closes the position
reduce-only. Bar-close only — the protective stop still owns intrabar moves.

Persona presets: scalper (5m/15m) stops 0.5–1.2 ATR, RR 1.5, BE 0.7R, trail 0.9R/giveback 30,
timeDecay ON (45/15, tighten 15→60, stale 30) · intraday mean-revert (1h) 1.0–2.5 ATR, RR 1.5,
BE 0.8R, no trail, timeDecay ON (120/60, 10→40, stale 25) · swing breakout (4h) 0.75–1.75 ATR,
RR 2, BE 1R, trail 1.2R/giveback 35 · swing trend (4h) 1.0–2.5 ATR, RR 2, BE 1R, trail
1.5R/giveback 45–55, no timeDecay.

## Not expressible — the catalog keys this needs

The one place a claim that the catalog LACKS something may live, and every row names the key it
denies so the claim can be checked. A claim about the grammar's shape (a clause compares one
column with a literal or with its own previous completed bar, never with another column; `distance`
rejects an `offset`) belongs in prose above — those are permanent. A claim that a metric is absent belongs here, or nowhere.

| Script / primitive | Key the catalog would need | Nearest expressible neighbour |
|---|---|---|
| 100-period SMA | `SMA100` | the shipped 50- or 200-period simple average, whichever the thesis leans on |

## Where the worked material lives

This skill's body is the contract — the axes, the header grammar, how conditions and weights behave,
and the absence section above. The worked material is disclosed on demand, so it costs nothing until
you ask for it. Read a reference with `read_skill_reference` when you reach the work it covers:

- **`references/recipes.md`** — copy-adaptable column objects and condition fragments: cross
  detection, board-relative ranks, cross-venue basis, crowd positioning, coin selection, and the
  discovery fields worth reading before you compose.
- **`references/playbooks.md`** — five validated desk-grade compositions end to end, and how to
  adapt one rather than copy it.
- **`references/tradingview-ports.md`** — per-script port recipes for the popular TradingView
  strategies, each naming its substitutions where the catalog lacks a primitive.

Every rule about how a column *behaves* is in this body, not in a reference. If a reference seems to
state one, the body is the authority.
