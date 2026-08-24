# 17 · The full sweep

On 2026-08-24 every legal column shape was rendered against the live compiler, and
the whole condition grammar was exercised in a single report. This doc records what
held and what broke.

Data: `data/audit/sweep_2026-08-24.json`. Harness: `scripts/sweep.py`.

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

`columnLookback` is **constant**. Thirteen renders of 1, 4, 5, 8, 9, 12, 18, 24 and
30 columns — every transform, SMA200 included — reported `columnLookback: 24` every
single time. It never moved.

So it is not a per-column cost, and not a function of metric period. The cap that
binds a batch is **`sectionColumns: 32`**.

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
condition that happens never to fire. See cookbook trap 13.

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
