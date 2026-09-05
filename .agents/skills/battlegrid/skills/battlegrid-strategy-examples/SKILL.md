---
name: battlegrid-strategy-examples
description: Full-surface composition patterns for the strategy studio — validated desk-grade examples of custom report sections, benchmark sections, condition trees with verdicts and enforcement gates, tiered signal weights, routing gates, ATR trade levels, and position management. Activate beside strategy-authoring whenever a strategy is being composed or upgraded beyond a basic template.
---

# Strategy Studio — full-power composition patterns

`strategy-authoring` owns the flow (evidence → locked spec → discover → compile → review →
apply). This skill owns **what to compose**: a default build — a few platform sections, no
conditions, untouched weights — wastes the studio. The playbooks below are compiled in CI, so their
shapes are binding in the sense that matters — they are checked, not merely asserted. Loose tokens
elsewhere in this file are not covered by that gate, and vocabulary moves with deploys, so discovery
in the conversation stays the authority — prefer what `list_strategy_vocabulary`,
`get_strategy_column_contract`, and `get_strategy_signal_definition` return over anything
printed here, and read exact headers from a preview's `conditionColumns` before conditioning on
them.

## The full-power checklist

Before compiling a CREATE, every "no" here is a decision to state, not an omission:

1. At least one **custom section** whose columns encode the thesis — not only platform modules.
2. **Conditions** encode the entry logic: building blocks (`verdict: null`) + verdict carriers,
   and at least one `required: true` condition vetoing obvious disqualifiers **before any
   billing or LLM call**.
3. **Every signal meant to score is named in `rules`** with a deliberate tier — unnamed signals
   keep server defaults (typically Off). Verify in the compiled scorecard, never assume.
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
the keys `get_strategy` returned** for the sections you are keeping. Either way you never invent
one. To section-qualify a duplicated header, read the key from a preview's `conditionColumns` or
from the qualified candidates a `CONDITION_COLUMN_AMBIGUOUS` refusal offers.

**Event columns print only on their event.** `MACD_cross` and `EMA5_13` (Bullish/Bearish) carry a
value on the crossing bar and are null on every other one, which reads as UNRESOLVED. Use an event
column as a TRIGGER inside a carrier, and pair it with a persistent state — a spread sign,
`MAalign` — for regime. A condition that treats an event column as a standing state is unresolved on
nearly every bar, which is a gate that never gates.

**`PDH` and `PDL` are anchored to `1d`.** They are catalogued price levels, so `dist_PDH gte 0`
composes directly — but bind them `{abs: '1d'}`, which is the only reference the save path accepts on
them, and read them from any anchor that way. (`distance` still rejects an `offset`, and a clause
still compares a column against a literal; neither of those shapes is what a previous-day level
needed.)

## Conditions

`{ conditionKey, name, definition, verdict, required, exit, clock, closes }` — all eight
required, no defaults. Clauses: numeric/rank headers take `lt|lte|gte|gt|between`;
classification/direction headers take `is|in` with the served vocabulary. Groups:
`ALL | ANY | NOT | N_OF` (with `n`), depth ≤ 2. `conditionRef` composes named conditions (no
cycles; forward refs legal). `sectionKey: null` is sugar for a report-unique header only.
Verdicts: first TRUE carrier **in declaration order** decides UP/DOWN/NEITHER — order carriers
most-specific first; building blocks carry `null`. `required: true` = FALSE blocks compose-trade
before billing. Evaluation is three-valued: UNRESOLVED never collapses to FALSE; forming-bar
reads are provisional.

**The evidence clock.** `clock: "LIVE"` reads the forming bar; `clock: "CLOSE"` reads settled
bars, and `closes` is how many consecutive closed bars must read TRUE (1–5) — always `1` under
LIVE, which has exactly one frame. A CLOSE clock is legal **only** over a header resolved from
this coin's own candle series at offset 0. Frame-inert operands are refused
(`CONDITION_CLOCK_OPERAND_ILLEGAL`): perp-payload scalars, published rolling changes, ranks, zone
entities, MDS regime labels, enrichment metrics, session scalars, and any clause authored at a
non-zero offset. A closed frame cannot move them, so "held for N closes" would describe reads
that never happened. The remedy is a split, not a re-clock: move that clause into its own LIVE
condition and `conditionRef` it. **Worked liquidity floor:** `LIQUID_FLOOR` is LIVE because
`vol24hUsd` is a bundle scalar; the carrier that refs it may be CLOSE over its own candle-series
clauses.

**The lane a strategy is deployed to.** Report-level scalars split by LANE, and the split is not a
quality of the header — it is which reader runs. Market breadth and the reference pairs are ordinary
market-wide reads with no session dimension, so they resolve everywhere. The five **session-field**
scalars (`fieldPlayers`, `fieldUpBias`, `fieldBiasDir`, `captConc`, `picksSpread`) describe a game
session the agent is playing in, and **radar runs outside one** — so a radar deployment whose
strategy reads one is refused outright (`CONDITION_OPERAND_UNSERVED_IN_LANE`), naming the scalars it
can read instead. The refusal lands at DEPLOY rather than at save, because a strategy carries no lane
of its own: the same strategy is legal, and reads those scalars correctly, on an arena agent.

**The exit role.** `exit: true` makes a settled TRUE reading close open positions its verdict
opposes — UP exits SHORTs, DOWN exits LONGs, a NEITHER or `null` verdict exits both. Legal only
under `clock: "CLOSE"`: a LIVE reading is the forming bar, and an exit fired on one is an
intrabar exit. Orthogonal to `required` — the two act on disjoint lifecycles, pre-entry versus
open — so a condition may carry both, either, or neither.

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

`{ trigger, confirmTf, closes, bandAtrMultiple, levelOffsetAtrMultiple, validForBars }` — all six
required on every CREATE, no defaults. This axis is replaced WHOLE on save, so an omitted key would
silently revert an author's discipline rather than be refused. There is no level-source key: the
level a level trigger rests at is DERIVED from the trigger and the trade's direction, never named.

**The trigger decides WHEN, and for two of them WHERE, an entry is taken.**

- `AT_SIGNAL` — fire the moment the radar observes the qualification flip, at whatever bar is on
  the tape, keeping the platform's flat wall-clock entry window. Today's behaviour.
- `ON_CANDLE_CLOSE` — the flip ARMS the pair; the entry is taken only after a close on
  `confirmTf` that still reads the conditions true and has not displaced beyond the band.
- `STOP_THROUGH_LEVEL` — a TRIGGER order rests past the Donchian channel's CURRENT edge in the
  trade's direction (the 20-bar high for a long, the 20-bar low for a short) by the offset, and
  the exchange book is the watcher; the entry is taken when price trades through, not when the
  platform notices.
- `ON_RETEST` — a LIMIT order rests in front of the edge a close most recently BROKE (the
  channel's break memory: the broken high for a long, the broken low for a short) by the offset,
  waiting for a return to it. Not filling is a correct outcome, not a failure; no unrecovered
  break in memory means no setup, never a fallback level.

`confirmTf` is the bar whose close confirms. Exactly two values are legal: the strategy's own
timeframe and the rung below it — one only, when the strategy sits on the ladder floor. It is
NOT the authorable main-candle set; a rung further down names a bar nothing else in the strategy
observes and makes the radar sweep on every one of its closes.

`closes` (1–5) is how many consecutive confirming closes are required, and `bandAtrMultiple` is
the veto width: the entry is VOIDED when the confirming close has moved at or beyond that many
ATR against the armed verdict. Strictly greater than zero — zero is not "no filter" but a filter
that voids on any adverse move — and at or below the platform's own entry-deviation gate, since
a wider band cannot refuse anything the platform will not refuse anyway.

`levelOffsetAtrMultiple` (0–2) is an UNSIGNED distance from the derived edge in ATR multiples — a
long adds it, a short subtracts it, so a breakout stop rests past its edge and a pullback limit
rests in front of its edge, and a signed value would invert the trigger's meaning. `validForBars`
(1–24) denominates validity in the strategy's OWN bars rather than minutes, because a 1h setup
waiting for a retest has not failed after fifteen minutes. The resting price must sit on the
correct side of the mark when the order is placed — a buy stop above it, a buy limit below it, the
mirror for a sell — or the entry is refused rather than filled at the market; there is no limit on
how far from the mark a level may rest.

**The legality matrix runs one way.** All six keys are always present, so the question is never
"is it set" but "is it set to something that MEANS anything under this trigger". `closes` ≠ 1 is
refused under any trigger but `ON_CANDLE_CLOSE`; `levelOffsetAtrMultiple` ≠ 0 and `validForBars`
≠ 4 are refused under a non-level trigger. Leave a dial at its inert value rather than setting one
the platform will ignore.

## Report sections

`{ kind, sectionKey, title, benchmarkTicker, notes, columns }` — the custom section shape. A
section carries no `timeframe`: its relative columns resolve against the strategy timeframe, and a
column reaches any other timeframe by pinning it (`timeframe: { abs: '4h' }`). `benchmarkTicker` and `notes` are **required-nullable**: send an explicit `null` rather
than omitting them, because the section is rebuilt whole on save and an omitted key clears the
author's value silently. On a CREATE, omit `sectionKey` — it is derived from the section itself.

## Signal rules

`{ signalId, allocation, required, params }` — one entry per signal you want scoring.
`allocation` is the tier (0–3) and `params` replaces canonical defaults only when present.

## Signal weights and gate math

Tiers: 0 Off · 1 Normal · 2 Important · 3 Critical.

```
aggregateScore = Σ(score × allocation) / Σ(allocation)   over triggered signals
```

Weights are relative — build a pyramid: 1–2 Critical (thesis, usually `required`), 2–4
Important (independent confirmation, different modules), 1–3 Normal (context), rest Off so
noise cannot dilute the average. Gate check: with 3/2/2/1 weights, Critical + one Important at
score 1.0 → (3+2)/8 = 0.625, so a 0.6 gate means "thesis plus one confirmation".
`simulate_aggregate_score` does this arithmetic from compiled values at review time.
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
closed for reasons other than its stop.

Validated bounds: break-even trigger 0.5–2R; trailing trigger 0–2R step 0.01 (0 = trail from
entry), giveback 25–55%, buffer 0.01–1%; timeDecay grace ≥ interval, tighten 0.1–50% to max
1–100%, stale threshold 0–100% of TP progress. Per-mechanism flags; no umbrella switch.

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
