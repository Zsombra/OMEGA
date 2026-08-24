# 16 · The write path

Doc 15 established that no custom column had ever existed on this account, and that
`apply_strategy_plan` appeared to be dead. It is not dead. It has a stale schema.

On **2026-08-24 19:07Z** the first custom data table in this account's history was
written through the connector. `OMEGA-TEST: Fork Build` went revision 4 → 5,
`changedAxes: ["REPORT"]`.

## The workaround

`apply_strategy_plan` publishes this shape:

```
request: { plan, planToken, confirm }      // all three required
```

Send that and it is refused:

```
unrecognized_keys: ['plan']   at path ['request']
```

The `request` wrapper is correct — the path proves it. The runtime validator simply does
not accept `plan`, **the key its own published schema marks required**. And no
"missing key" error accompanies the refusal, which pins the validator's accepted set for
`request` to exactly `{confirm, planToken}`.

So: **omit `plan`.**

```
compile_strategy_plan(...)          →  approvedPlan + planToken
apply_strategy_plan({request: {confirm: true, planToken: "<verbatim>"}})
```

This works. The plan is redundant on the wire because it is already sealed inside the
token — decode the `planToken` payload and you find `postStateDigest`,
`expectedRevision`, `proposedRevision`, `strategyId`, `operation` and
`authoringCatalogDigest`. The server reconstructs the post-state from its own compile
record; the client copy exists only to be diffed against, and the current build no longer
asks for it.

The token is valid five minutes. Past that, recompile — never retry a stale one.

## Why this keeps happening

This is the second instance of the same drift. Grid-Commander recorded the first on
2026-08-15 (`openspec/backlog/every-apply-the-product-composes-is-refused.md`):
`regimeAutoDerive` and `regimeTimeframe` were declared **required** on the UPDATE plan and
simultaneously rejected by the live validator. Dropping them made the write succeed.

Their diagnosis holds here verbatim: *the tool list goes stale after a deployment,
rediscover at runtime.* The connector's own MCP instructions say the same thing —
"cached capability lists are not authoritative after a deployment."

Today's case is that bug one level up: the rejected key is no longer a field *inside*
`plan`, it is `plan` itself.

**The standing rule:** when the validator rejects a key the schema declares required,
drop the key and resubmit. Do not trust a schema you read before the last deployment, and
do not conclude a tool is broken from a validation error alone — the error names the key
it will not take, which is also the instruction for what to remove.

## A fork is not a second-class object

The write above landed on a *forked* strategy, which settles the open question. The fork
carries `forkedFromStrategyId: "6280a7c0-…"` permanently, and that field restricts
nothing:

| check | result |
|---|---|
| `compile_strategy_plan` UPDATE accepted | yes, `viable: true` |
| custom section accepted | yes, 8 columns |
| server assigned a section key | yes, `custom:3b1ce9ed-…` |
| apply committed | yes, revision 4 → 5 |
| special-case rules for forks | **none observed** |

A fork starts at revision 1 with the source's snapshot copied coherently, and from there
behaves exactly like a created strategy. Since `apply_strategy_plan` CREATE is capped by
the 25/25 quota, **fork-then-UPDATE is the practical way to author a new table** — it
costs the same one quota slot and needs no free slot beyond it.

## Section keys

A custom section is keyed `custom:<uuid>`. The two arms differ, and this is the one place
the flow is easy to get wrong:

- `compile_strategy_plan` — `sectionKey` is **not** required. Omit it; the server mints one.
- `apply_strategy_plan` — `sectionKey` **is** required, pattern `^custom:[0-9a-fA-F-]{36}$`.

Since the apply arm no longer receives a plan at all, this only matters if the schema is
ever repaired. Copy the minted key out of `approvedPlan.postState.sections[].sectionKey`
rather than generating one.

## What was verified

The panel is the eight-column design from `out/omega-test-build-sheet.md` — each derived
value shipped beside its own inputs so the arithmetic is checkable from one rendered row.
Rendered live across BTC, ETH, SOL, GOLD and DOGE:

| check | result |
|---|---|
| `(EMA5 − EMA13) / EMA13 × 100` vs `EMA5_EMA13_spread` | 5/5 within display rounding |
| `(close − VWAP) / VWAP × 100` vs `dist_VWAP` | 5/5 within display rounding |
| `RSI14_now` == `RSI14` | 5/5 exact |
| `_trend` reconstructible from slots | **4/5** — see cookbook trap 12 |

That last row is the finding. DOGE printed `RSI14_t2 = 38.3` and `RSI14_now = 38.3` with
`RSI14_trend = falling`. The direction is computed before rounding.
