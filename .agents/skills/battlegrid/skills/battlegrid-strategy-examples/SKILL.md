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
printed here, and read exact headers from a preview's `conditionColumns` before conditioning on
them.

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

Non-anchor rungs affix `_ltf` (lower) / `_htf` (regime): `MAalign_htf`,
`zones_htf_support_dist`. Chains are bounded at two: inner `distance`/`spread` → outer
`trajectory`/`aggregate`/`efficiency`/`maxShare`/`rank` (`EMA5 spread EMA13 × trajectory` →
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
preview's `conditionColumns` or from the qualified candidates a `CONDITION_COLUMN_AMBIGUOUS`
refusal offers.

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
against a literal; neither of those shapes is what a previous-session level needed.)

## Conditions

`{ conditionKey, name, definition, verdict, required, exitSide }` — all six
required, no defaults. A `clock` key is REFUSED (the per-condition evidence clock was retired in
contract `61.0.0`), so is a condition-level `closes` key — the hold lives on each clause and each
group (contract `84.0.0`) — and so is a boolean `exit` key: the side an exit closes is its own
`exitSide` (contract `88.0.0`). Clauses: numeric/rank headers take `lt|lte|gte|gt|between`;
classification/direction headers take `is|in` with the served vocabulary. Groups:
`ALL | ANY | NOT | N_OF` (with `n`), depth ≤ 2. Every clause and every group carries a required
`hold: { atLeast, of }` — `{ "atLeast": 1, "of": 1 }` is a single read; a clause or group without
`hold` is refused (`CONDITION_HOLD_INVALID`). `conditionRef` composes named conditions (no
cycles; forward refs legal) and carries no hold of its own. `sectionKey: null` is sugar for a report-unique header only.
Verdicts: resolution is taken over the DISTINCT verdicts of the carriers that read TRUE. One
distinct verdict decides, and the first carrier in declaration order carrying it is named as the
decider — so order breaks ties between carriers that AGREE. Carriers that DISAGREE resolve
`NEITHER` and stand the coin aside; declaration order never picks a side between them. Building
blocks carry `null`.

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
(`preview_strategy_report` → `conditionColumns[].outputs[].conditionHold`, and each scalar metric in
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

**A state column is not a flip event.** `ST_DIR` reads the same on every bar of a trend, so
`ST_DIR is "bullish"` is a regime filter and never an entry signal. The flip needs an event column
beside it — an `EMA5_13` cross, or a `ST_DIR` trajectory whose `_trend` changes. The same distinction
applies to every persisting classification: `MAalign`, `ADX_state`, `zone`.

**Name the anchor when a metric is calibrated for one.** `KC_SQUEEZE is "on"` reads *on* about 57% of
1h crypto bars even at canonical parameters — Bollinger σ is close-to-close while ATR captures
intrabar range, so σ/ATR runs low here — against about 19% at 15m. It is a selective filter at 15m and
below and close to useless at 1h. A metric whose selectivity depends on the anchor is stated with the
anchor, or the author gates on something that admits most bars.

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
column against a literal; `distance` rejects an `offset`) belongs in prose above — those are
permanent. A claim that a metric is absent belongs here, or nowhere.

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
