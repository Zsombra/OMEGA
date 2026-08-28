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
  width`, and no published schema says so. Workaround **confirmed** later the same day:
  the identical plan at an explicit 3-ticker selection compiled clean. The cap
  ~~*boundary* — the largest selection that still compiles — remains unmeasured~~ —
  **measured later on 2026-08-28** by the measurement campaign
  ([`cap_boundary_2026-08-28.json`](../data/audit/cap_boundary_2026-08-28.json)):
  the boundary is **ranked limit 4**, an exact adjacent-pair bracket — `ALL/4` viable
  (BTC, ETH, SOL, HYPE), `ALL/5` refused at 258,883 bytes, `CRYPTO/4` also viable.
  The byte curve is **concave** (5 → 258,883; 19 → 368,235; 30 → 395,404), so the
  first handful of coins spends most of the budget and no realistic ranked universe
  fits. Report-relative: measured for the trend-continuation report's 11 columns; a
  wider report refuses earlier. Realistic breadth needs explicit lists (≤50 per
  schema; their own cap edge unmeasured) or a platform-side fix.

`coinSelection`, previously the substantive omission, now defaults class-aware:
**CRYPTO** when the thesis weights a crypto-only module (`CVD`, `FLOW_DIVERGENCE` —
null off-crypto, and null reads FALSE), else **ALL**, ranked — capped since
2026-08-28 to the measured BG-14 boundary (`RANKED_LIMIT_MEASURED_MAX`, currently 4;
the limit-30 default it replaced could never compile).

And then, later on 2026-08-28 with one more user-authorized call: **the first generated
plan compiled `viable: true`** — the identical CREATE body at an explicit BTC/ETH/SOL
selection, `proposedRevision: 1`, quota and name admissible, 16 non-blocking advisories,
token left to expire, nothing applied
([`compile_dry_run_2026-08-28-small.json`](../data/audit/compile_dry_run_2026-08-28-small.json)).
The compile also settled three smaller things constructively:

- the server **mints** the custom `sectionKey`s (`postState` carries fresh ones, not
  omega's deterministic uuid5s);
- `cadence`/`regimeTimeframe` are **server-derived from the anchor** — we sent neither,
  `postState` carries `INTRADAY`/`4h`, exactly omega's mapping (confirmed at 1h only;
  the 2026-08-28 4h probe later proved the cadence half of omega's mapping **wrong** at
  4h — the server derives `SWING`, not `INTRADAY` — and the mapping was corrected) —
  which is *why* the CREATE schema has no such fields. The same day's anchor sweep
  ([`anchor_sweep_2026-08-28.json`](../data/audit/anchor_sweep_2026-08-28.json))
  finished the axis: the schema's 13-value `timeframe` enum is NOT the authorable
  surface — the server refuses everything outside **`5m / 15m / 1h / 4h`**
  (`REPORT_TIMEFRAME_NOT_AUTHORABLE`, allowedDomain naming all four), and every value
  is now measured: 5m → SCALPER/15m (the map's guessed `1h` regime died here),
  15m → SCALPER/1h, 1h → INTRADAY/4h, 4h → SWING/1d, with the 16 execution defaults
  identical at all four;
- the persisted shape answers **`signalRules`** where the write API takes `rules`, and
  carries **no `coinSelection` at all** — the selection scoped the review, and where a
  strategy's tradable universe actually lives is an open question, not assumed.

The 12 `ACTIVE_SIGNAL_DATA_NOT_IN_REPORT` advisories are worth one more sentence:
platform *membership* (IN_REPORT — what `omega.membership` models, verified
signal-for-signal on 2026-08-25) is a different relation from "all of a signal's
scoring inputs are rendered", which is what the compile advisory checks. Omega models
only the first. Non-blocking, but an agent will score those signals on data its own
report never shows it.

~~No generated plan has been **applied**; all three proven write axes remain hand-built
payloads~~ — resolved later the same day: see [A generated strategy exists](#a-generated-strategy-exists-2026-08-28)
below. Applying a generated plan remains a deliberate, per-instance user-authorized act.

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

**omega could author what to look at, and not how to trade it.** A strategy with sound
entries and a bad stop loses money, and the toolkit had nothing to say about the stop. The
schema publishes bounds for each (`trailingGivebackPct` 25–55, `breakEvenTriggerR` 0.5–2,
`minAtrPct` 0.01–50), so the surface was knowable — and on 2026-08-28 it was modelled.

**Modelled 2026-08-28 (Decision 1a).** [`omega/execution.py`](../omega/execution.py)
now carries the surface: presets emit **none** of the 16, every plan's critique states
the measured effective profile, and explicit `Thesis.execution` overrides merge into
`wire()` last, validated against the measured bounds. Bounds enforcement was measured
the same day
([`bounds_probe_2026-08-28.json`](../data/audit/bounds_probe_2026-08-28.json)):
`minRiskRewardRatio` 5.0 — legal per the published compile schema, which leaves the
field unbounded — was refused at the write validator's input layer with
`"must be <= 3"`, the agent catalog's upper edge. The catalog bounds are **enforced
below the declared schema**, so `validate_execution` treats violating them as errors.
The defaults are anchor-independent as far as measured — identical at 1h and 4h
([`defaults_4h_probe_2026-08-28.json`](../data/audit/defaults_4h_probe_2026-08-28.json));
the same probe caught omega's 4h cadence mapping predicting `INTRADAY` where the
server derives `SWING`, corrected the same day.

Two ownership facts, measured 2026-08-28
([`execution_surface_ownership_2026-08-28.json`](../data/audit/execution_surface_ownership_2026-08-28.json)):
these 16 are **strategy** fields — the agent's `tradingConfig` carries only the capital
block (USD exposure/drawdown/daily-loss caps, leverage, slippage, sizing presets) and
none of them. And omitting all 16 does not mean flat-passive: the platform's measured
defaults (from the viable compile's `postState`) switch trailing, break-even *and* time
decay **on** — minAtrPct 0.5, R:R 1.5, stop 1–2×ATR, trailing 1R/45%/0.25, break-even
1.08R, decay 15/60 min, 5%→50%, stale at 25%.

~~One more axis is untouched: the `rules` array itself~~ — written on 2026-08-28 by the
first generated apply (below): all 84 rules, 24 of them weighted, survived the round
trip byte-for-byte.

See [`write_surface_gap.json`](../data/audit/write_surface_gap.json).

### A generated strategy exists (2026-08-28)

The loop closed today, under the user's explicit per-instance authorization ("ONE
`apply_strategy_plan` of the compiled trend-continuation CREATE") and the plan's hard
gate: one fresh compile (viable, as it was that morning), one apply within the token's
five minutes — `{confirm: true, planToken}`, no `plan` key, first attempt, no retry —
and a read-back verified by script.

**Strategy `6a8bca67-45a3-428e-85ba-71ec2cd2218e`, "Trend Continuation", revision 1.**
Every content field of the read-back equals the compile's approved `postState`: 2
custom sections under server-minted keys, the dense 84-rule scorecard with its 24
weighted entries, 7 conditions (their `sectionKey: null` column refs rewritten by the
server to resolved sections at persist), and — the Decision 1(a) proof — all 16
execution parameters present at exactly the measured platform defaults, none of them
sent. Bound to nothing at every step (`boundAgentCount` 0, `propagatedAgentCount` 0).

**Disposition, per the user's choice: archived immediately** after verification —
revision 2, `isActive: false`, restorable, quota slot returned (24/25). Full record:
[`first_generated_apply_2026-08-28.json`](../data/audit/first_generated_apply_2026-08-28.json),
pinned by `tests/test_first_apply.py`. Binding to an agent and radar/arena deployment
remain user-gated, always.

### A generated strategy can be revised (2026-08-29)

The UPDATE half closed the next day, under a four-write user authorization (restore,
≤2 compiles, ONE apply, archive): `wire_update` — the full `wire()` body plus exactly
`operation`/`strategyId`/`expectedRevision`, the Thesis staying the single source of
truth — was compiled against the restored `6a8bca67` and applied once. The change was
one Thesis-level execution override (`minRiskRewardRatio` 2.0), giving Decision 1(a)'s
override path its first real-write proof: the read-back shows **1.5 → 2.0 and nothing
else moved** (18 scripted checks). Revisions walked 2 →(restore) 3 →(update) 4
→(archive) 5; quota ended where it started.

Two UPDATE facts got measured on the way:

- **`minRiskRewardRatio` diffs under the `tradeLevelPolicy` axis** (null on the
  CREATE, populated here) — the first sighting of the axis that carries the
  position-management execution params.
- **A full-body UPDATE re-mints custom `sectionKey`s even when the re-sent report is
  byte-identical** — `changedAxes` listed `REPORT` and `CONDITIONS` alongside
  `TRADE_LEVEL_POLICY`, with every condition reference re-resolved to the new keys in
  lockstep. Semantically safe, but **section identity churns on every full-body
  revision**; anything caching a `sectionKey` across revisions is holding a stale
  name. (Whether sending the existing keys back would preserve them is unmeasured —
  CREATE refuses client keys; UPDATE was not probed with them.)

The pre-committed diff-inspection gate ran between compile and apply and authorized
proceeding on the lockstep branch. Record:
[`first_generated_update_2026-08-29.json`](../data/audit/first_generated_update_2026-08-29.json),
pinned by `tests/test_first_update.py`. Conflict handling (a wrong
`expectedRevision`) and omitted-field delta semantics remain deliberately unmeasured.

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
