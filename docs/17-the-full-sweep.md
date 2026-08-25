# 17 · The full sweep

On 2026-08-24 every legal column shape was rendered against the live compiler, and
the whole condition grammar was exercised in a single report. This doc records what
held and what broke.

Data: `data/audit/sweep_2026-08-24.json`. Harness: `scripts/sweep.py`.

> **Superseded 2026-08-26 — and the number was not the problem.** This page recorded
> "300 of 300 legal shapes". The 300 was accurate; the **denominator** was not. A second
> sweep rendered every remaining shape and closed live coverage at **1,759 / 1,759
> operand-expanded, 301 / 301 structural, zero header mismatches** — and found two
> legality rules omega had never modelled, which had inflated the space by 421 shapes.
> See the addendum at the foot of this page.

## The headline

**300 of 300 legal shapes verified. Zero header mismatches.**

`omega.fanout.outputs_for` predicts the platform's headers exactly — across all 16
transforms, chained forms (`dist_X_mean24`, `dist_X_er`, `dist_X_rank_hi`),
categorical trajectories (`regTrend_t3` … `regTrend_trend`), rank orderings,
structure counts (`zones_count`), and the deep moving averages. 536 predicted
headers, 536 matched.

That is the claim the rest of the toolkit rests on, and it is now measured rather
than sampled.

## What the budget actually is

`columnLookback` is **`max(window + offset)` across the report's columns**, capped at
32. It is not a per-column sum and not a function of metric period.

It read exactly 24 in thirteen straight renders, and I wrote that down as "constant,
carries no information." That was wrong, and the reason is embarrassing in a useful
way: **every one of those renders used default parameters**, and the defaults put the
maximum at 24 — `aggregate` and `maxShare` default to `window: 24`, and a plain
`value` column carries an implicit window of 24 too. The number never moved because I
never moved it.

The platform stated the rule itself once a parameter was pushed:

```
REPORT_COLUMN_LOOKBACK_EXCEEDED
Column 'CLOSE × value' requests a lookback of 36 bars (window + offset)
— the cap is 32.
receivedValue: { window: 24, offset: 12, lookback: 36 }
```

Confirmed from the other side: `value` at `offset: 8`, `trajectory` at `window: 32`
and `efficiency` at `window: 32` render together and report `columnLookback: 32/32`.

Two consequences:

- A plain `value` column can only be lagged by **8 bars** (24 implicit + 8 = 32), not
  the 64 the schema's `offset` bound suggests.
- The binding cap depends on what you are building. `sectionColumns: 32` binds a wide
  report of shallow columns; `columnLookback: 32` binds a narrow report of deep ones.

This corrects a hypothesis written into `scripts/sweep.py` earlier the same day:
SMA50 and SMA200 were isolated on the theory that a 200-period metric would blow a
32-bar cap. It does not. Both render like anything else. The wrong guess is left
documented in place rather than quietly deleted, because "we tried it and it was
false" is worth more than silence.

## The condition grammar holds completely

One render exercised every construct at once, and all of it resolved:

| construct | result |
|---|---|
| clause ops `lt` `lte` `gte` `gt` `between` `is` `in` | all 7 evaluate with evidence |
| group ops `ALL` `ANY` `NOT` `N_OF` | all 4 evaluate |
| `N_OF` counts | `{trueCount: 3, total: 3, unresolvedCount: 0}` |
| `conditionRef` | resolves |
| **group referencing groups** | resolves — a three-level DAG |
| `required: true` | enforced upstream |
| verdict | `UP`, `decidedBy: CONF_UP` |
| market-read markers | 5/5 resolved (3 conditions, 2 columns), 0 unreferenceable |

The `provisional` flag behaves exactly as documented: all 12 conditions reading
custom columns came back `provisional: true`, and the one reading an ambient header
(`usdtUsdDev_market`) came back `false`. The live forming bar propagates from column
to condition without being asked to.

## Two shapes the platform declares and cannot deliver

### `CROWD × rank` — declared legal, crashes

Every crowd metric declares `transforms: ["rank", "value"]` in the platform's own
contract. Every one returns `INTERNAL_ERROR` when `rank` is rendered — alone or in
company, settled or `_LIVE`. All nine crowd `value` shapes render fine.

Four were confirmed one column at a time (`CROWD_ACC`, `CROWD_ACC_LIVE`,
`CROWD_CAPT`, `CROWD_UPBIAS`); the other four are covered by group renders that
failed as a set. They are quarantined in `scripts/sweep.py:UNRENDERABLE` rather than
deleted — they are legal by the contract, so `omega.space` must keep enumerating
them, but shipping one poisons a whole batch.

### `classifyZone` — a published vocabulary two columns never emit

All five `classifyZone` columns declare `conditionVocabulary:
["overbought", "oversold", "neutral"]`. Two of them never produce any of those
values. Measured across 12 coins:

| column | observed | in vocabulary |
|---|---|---|
| `ADX_zone` | `trending`, `developing`, `weak` | **0 of 12** |
| `MFI14_zone` | `bearish`, `bullish` | **0 of 12** |
| `RSI14_zone` | `neutral` | 12 of 12 |
| `RSI7_zone` | `neutral`, `oversold` | 12 of 12 |
| `K_zone` | `neutral`, `oversold` | 12 of 12 |

This is the worse of the two defects, because it is **silent**. A condition
`ADX_zone is "neutral"` — written from the vocabulary the platform publishes, using
the operator the platform lists — is permanently `FALSE`. Not an error. Not
`UNRESOLVED`, which would at least signal a missing input. It looks like a working
condition that happens never to fire.

And the obvious fix does not work. Writing the label the column actually shows is
refused:

```
CONDITION_LITERAL_UNSUPPORTED
'trending' is not a value 'ADX_zone' can take — its vocabulary is
overbought | oversold | neutral.   Nearest canonical key: 'oversold'
```

Both directions are closed: every label that would fire is rejected at validation,
every label that is accepted reads FALSE forever. `ADX_zone` and `MFI14_zone` are
**display-only** — renderable for an agent to read, impossible to condition on. See
cookbook trap 13.

## The legality model, confirmed from the other side

`BB_PCT_B × classifyZone` was rejected by the platform:

```
REPORT_COLUMN_PAIR_UNSUPPORTED
(BB_PCT_B × classifyZone) is not a composable pair —
the engine has no resolution home for it
```

`omega.space` had already excluded it. That is the enumeration being right about an
*absence*, which the 300/300 pass alone would not prove. The error also names the
allowed set for that metric — `value, trajectory, spread, efficiency, maxShare,
rank` — which is a free contract read worth harvesting if more of these turn up.

## The pattern across the day

Three separate places where BattleGrid's declared contract and its runtime disagree:

1. `apply_strategy_plan` requires a `plan` key its validator rejects (doc 16)
2. `CROWD × rank` is declared legal and cannot render
3. `classifyZone` publishes a vocabulary two of its columns never emit

Plus Grid-Commander's 2026-08-15 case (`regimeAutoDerive` / `regimeTimeframe`
declared required, rejected live). Four instances, one shape: **the contract is a
claim, not a guarantee.** Every number in this repo is extracted from a live render
for exactly this reason — and now the extraction itself has been checked end to end.

## All three write axes are now closed

The doc-16 write moved the `REPORT` axis. This sweep closed the other two:
`OMEGA-TEST: Fork Build` went revision 5 → 6 with
`changedAxes: ["MARKET_READ", "CONDITIONS"]`, carrying all 13 conditions above.

Two things the server does on the way in, worth knowing before you author:

- **`sectionKey: null` is rewritten.** Every clause was submitted with a null
  section key; every one came back bound to `custom:3b1ce9ed-…`, and the ambient
  clause came back bound to `reference-pairs`. You do not resolve section keys —
  the server does, and it stores the resolved form.
- **The apply shape is the same one doc 16 found.** `{request: {confirm, planToken}}`,
  no `plan` key, on a second independent axis. That is the workaround holding twice.

So the full authoring chain — enumerate, validate, predict, compile, write, read
back, render, reconcile — is closed end to end for columns, conditions and market
read. What remains untested is `CREATE` from scratch (quota is 25/25, and every
CREATE attempt predates the connector change) and agent binding, which is deferred
by choice.

## Addendum — the sweep completed, 2026-08-26

The 2026-08-24 pass covered 300 shapes. It did not cover all of them, and this page said
it did. Completing it took 11 more renders and turned up two rules the contract does not
enforce anywhere omega could see.

| | shapes |
|---|---:|
| operand-expanded, as published | 2,200 |
| minus `rankableSpreadOperands` — a published field nobody read | −64 |
| minus the series-chain operand rule — **a rule nobody published** | −357 |
| **legal** | **1,779** |
| rendered live, every header checked | **1,759 / 1,759** |

**421 of the original 2,200 were never legal — 19%.**

The second rule is the one worth reading twice. Chaining a `spread` into a series-building
successor (`aggregate`, `trajectory`, `efficiency`) requires a **candle-backed operand**; a
timeless operand is a bundle read and the spread is a single scalar with no series to build
from. The contract publishes nothing about it. It surfaced on the **545th pair**, after 544
had passed clean, and every offline check available had already come back green — omega
reads all 6 transform-spec fields and all 10 metric fields the contract exposes.

That is the argument for rendering over reading, and it is not one that could be made
before doing it.

### The caps, measured

Three bind, at different times, and which one binds depends on the batch:

| cap | rate | binds on |
|---|---|---|
| `estimatedTokens` 16,000 | ~32 / header | wide unchained batches |
| `estimatedTokens` 16,000 | ~46 / header | chained batches — longer preamble text |
| `mcp_result_bytes` 256,000 | ~586 bytes / header | **trajectory batches, first** |

A 480-header trajectory batch returned **281,346 bytes** and was refused while
`estimatedTokens` sat at ~13k of 16k. Sizing against the token budget alone is wrong.

### `sectionColumns` is per-section

Two sections of 3 columns reports `used: 3, cap: 32` — the **max**, not the sum. A render
holds up to 32 sections × 32 columns. `omega.validate` already enforced this correctly and
[04](04-section-report-budget.md) already said "columns per section"; the doubt was mine.

### Ordering aliases

For a metric whose values are all one sign, two of the four rank orderings are the **same
column under different names**. Measured, not reasoned — BTC `OI_rank_lo` and
`OI_rank_near` both `78/78`; `lowDev_rank_lo` and `lowDev_rank_far` both `38/78`.

- non-negative metric → `rank_lo` **is** `rank_near`, and `rank_hi` **is** `rank_far`
- non-positive metric → `rank_lo` **is** `rank_far`, and `rank_hi` **is** `rank_near`

Authoring both spends two of your 32 section slots on one measurement, and the headers
differ so nothing warns you.

### The lookback floor

A single bare `CLOSE × value` column — no window, no offset — reports
`columnLookback: 24/32`. The contract publishes `value` as taking **only** `offset`, no
window at all, so the budget you compute from the contract is 24 bars short of the budget
charged. **Usable `offset` on a `value` column is 8.** See
[`lookback_floor.json`](../data/audit/lookback_floor.json).

## Workarounds

Both defects have a clean replacement, and both were verified live rather than
reasoned about.

### Zone columns → threshold the numeric column

`ADX × value` and `MFI14 × value` reproduce their broken zone columns exactly:

| coin | `ADX` | `ADX_zone` | `ADX lt 20` | `MFI14` | `MFI14_zone` | `MFI14 lt 50` |
|---|---|---|---|---|---|---|
| BTC | 21.9 | developing | FALSE | 42.8 | bearish | TRUE |
| SOL | 15.7 | weak | TRUE | 63.8 | bullish | FALSE |
| XRP | 10.8 | weak | TRUE | 43.4 | bearish | TRUE |

The cutoffs (`ADX` 20/25, `MFI14` 50) are **consistent with** the observations, not
extracted — the zone thresholds are published nowhere. They match the conventional
values, which is reassuring but not evidence. Re-measure at an edge before trusting
one.

### `CROWD × rank` → threshold the value

Crowd metrics are already cross-coin-comparable percentages, so unlike `VOLUME` they
need no normalising and `rank` adds nothing a threshold cannot express. `crowdAcc
between 60 and 100` resolved UP on SOL (88.9) and XRP (100.0), NEITHER on BTC (40.0).

### And omega now refuses the trap offline

`omega.conditions.validate_conditions` rejects a clause on a disjoint zone header and
names the numeric replacement in the error. That closes the loop: the failure that
was silent on the platform is now loud before the round-trip.

**One correction worth recording.** The first fix I wrote *widened* the legal
vocabulary to `declared ∪ observed`, so that `ADX_zone is "developing"` would be
accepted. That was wrong, and only the live probe caught it — the platform rejects
exactly those labels, so the "fix" would have produced payloads that fail validation.
The rule holds: mirror what the platform *does*, and find out what it does by asking
it.
