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

## The shape was right seven hours before it worked

Do not read the section above as a piece of detective work. The transcript says
otherwise, and the timeline matters to anyone who hits `INTERNAL_ERROR` here.

| time (2026-08-24) | operation | apply request keys | result |
|---|---|---|---|
| 17:53 | CREATE | `confirm, plan, planToken` | unrecognized `plan` |
| 17:56 | CREATE | 29 flattened fields + `confirm, planToken` | unrecognized |
| 18:00 | CREATE | **`confirm, planToken`** | `INTERNAL_ERROR` |
| 18:01 | CREATE | **`confirm, planToken`** | `INTERNAL_ERROR` |
| 18:29 | UPDATE rev 2 | **`confirm, planToken`** | `INTERNAL_ERROR` |
| 18:40 | UPDATE rev 4 | **`confirm, planToken`** | `INTERNAL_ERROR` |
| 18:47 | UPDATE rev 4 | `confirm, plan, planToken` | unrecognized `plan` |
| 19:07 | UPDATE rev 4 | `confirm, plan, planToken` | unrecognized `plan` |
| **19:07** | **UPDATE rev 4** | **`confirm, planToken`** | **APPLIED, rev 4 → 5** |

The 18:40 request and the 19:06 request were byte-identical: same operation, same
`strategyId`, same `expectedRevision: 4`, same `coinSelection`, same eight columns. Both
applies used a token 21 and 89 seconds old respectively — both far inside the five-minute
lifetime, so staleness explains nothing.

The correct shape was found at 18:00 and refused four times. It succeeded at 19:07
unchanged. **The connector's behaviour changed underneath an identical request**, somewhere
in the 27 minutes between 18:40:55 and 19:07:46.

Two consequences for anyone using this doc:

- `INTERNAL_ERROR` from `apply_strategy_plan` is **not** evidence that your payload is
  wrong. It has been returned for a payload that later applied verbatim. Treat it as a
  server-side condition, wait, and retry the same request before changing anything.
- A recorded verdict about this connector expires. "The write path is broken" was written
  into this repo and into an agent memory as settled fact at roughly 18:50; it was false
  by 19:07. Re-probe before trusting any such claim, including one of your own.

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

**The standing rules**, one per failure mode:

- On `unrecognized_keys` — drop the named key and resubmit, even when the published
  schema marks it required. The error names the key it will not take, which is also the
  instruction for what to remove.
- On `INTERNAL_ERROR` — change nothing. Wait and resend the identical request. This is the
  one that cost seven hours: the payload was already correct.
- Before either — re-read the tool schema from the live connection. A schema read before
  the last deployment is not evidence about this one.

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

## What omega emits now — and what it still does not

Everything above is about write *mechanics*. This is about *content*.

The key mismatch this section used to table is **closed and measured**. On 2026-08-28
`StrategyPlan.wire()` was reshaped to the exact CREATE request body — `signalRules`
renamed `rules`, `cadence`/`regimeTimeframe` dropped to `_`-prefixed emit metadata,
`operation`/`intentSummary`/`assumptions`/`coinSelection` added — and a generated plan
was compiled live for the first time. Twice, both **refused**, neither for the old
key mismatch: the reshaped body drew no `unrecognized_keys` and no missing-required
either time. What the two compiles actually measured
([`compile_dry_run_2026-08-28*.json`](../data/audit/compile_dry_run_2026-08-28.json)):

- **A CREATE cannot claim section identities.** Custom `sectionKey` on the compile arm
  is refused outright — `REPORT_CUSTOM_SECTION_NOT_OWNED`, `allowedDomain` an *empty*
  enum. The "omit it; the server mints one" rule above is now enforced-measured, not
  just observed. Omega gap, fixed the same day: `wire()` strips the keys.
- **The 256,000-byte cap bites the preview, not the plan** (BG-14). The tool doc pins
  the cap to *the serialized plan*; a 12,210-byte plan was refused because the compile's
  own report render across `coinSelection` ranked/ALL/30 measured 395,404 bytes. The
  advertised "bounded live report review" refuses rather than bounds. `coinSelection`
  is thereby an *authoring budget input*: preview cost scales with `limit × report
  width`, and no published schema says so. Untested workaround: shrink the selection.

`coinSelection`, previously the substantive omission, now defaults class-aware:
**CRYPTO** when the thesis weights a crypto-only module (`CVD`, `FLOW_DIVERGENCE` —
null off-crypto, and null reads FALSE), else **ALL**, ranked limit 30.

So: a generated plan has now been *compiled at* — and no generated plan has ever
compiled **viable** or been applied. All three proven write axes remain hand-built
payloads. The next compile needs a materially smaller preview footprint.

### The execution surface

| group | parameters |
|---|---|
| risk | `minAtrPct`, `minRiskRewardRatio`, `minStopLossAtrMultiple`, `maxStopLossAtrMultiple` |
| trailing | `trailingEnabled`, `trailingTriggerR`, `trailingGivebackPct`, `trailingBufferPct` |
| break-even | `breakEvenEnabled`, `breakEvenTriggerR` |
| time decay | `timeDecayEnabled`, `timeDecayIntervalMinutes`, `timeDecayGracePeriodMinutes`, `timeDecayTightenPct`, `timeDecayMaxTightenPct`, `timeDecayStaleThresholdTpProgressPct` |

Five of six probed — `trailingEnabled`, `breakEvenTriggerR`, `minStopLossAtrMultiple`,
`timeDecayEnabled`, `minRiskRewardRatio` — appear **nowhere** in `omega/` or `docs/`. Only
`minAtrPct` is mentioned at all.

**omega can author what to look at, and not how to trade it.** A strategy with sound
entries and a bad stop loses money, and the toolkit has nothing to say about the stop. The
schema publishes bounds for each (`trailingGivebackPct` 25–55, `breakEvenTriggerR` 0.5–2,
`minAtrPct` 0.01–50), so the surface is knowable — it simply has not been modelled.

One more axis is untouched: the `rules` array itself. 84 signal IDs, each with an
allocation 0–3 and a `required` flag. A generated plan carries 84 of them and **not one
has ever been written.**

See [`write_surface_gap.json`](../data/audit/write_surface_gap.json).

## CREATE, proven

The last unexercised path closed on 2026-08-24 at 20:16Z. `OMEGA-TEST: From Scratch`
(`43f16fa4-…`) exists at revision 1 with `forkedFromStrategyId: null` — genuinely
created, not forked — carrying 6 custom columns, 10 conditions and a market read.
All seven axes committed at once: `IDENTITY`, `TIMEFRAME_PROFILE`, `REPORT`,
`MARKET_READ`, `CONDITIONS`, `SETUP_GATES`, `LIFECYCLE`.

Three things worth keeping from the run.

**Quota is freed by archiving.** `archive_strategy` on the fork (revision 6 → 7,
`isActive: false`) released the slot, and the archived record keeps its sections and
conditions intact, so `restore_strategy` puts it back.

**A timeout is neither a failure nor a success.** The apply timed out twice before
landing. The safe move is not to retry blind: the `strategyId` is **pre-allocated
inside the signed token**, so `get_strategy` on that id settles what happened. It
returned `NOT_FOUND`, which proved nothing had been written and a retry could not
duplicate. Then the same token applied cleanly on the third attempt.

**The apply shape held a third time.** `{request: {confirm, planToken}}`, no `plan`
key — now confirmed on `REPORT`, on `CONDITIONS`/`MARKET_READ`, and on a
from-scratch `CREATE`.

The compile also revealed the seeding behaviour: `creationSeed` returned **84**
signal rules, and the 10 `ACTIVE_SIGNAL_DATA_NOT_IN_REPORT` mismatches are simply
that default seed activating signals whose data a deliberately narrow 6-column report
does not carry. Non-blocking — viability stayed true.
