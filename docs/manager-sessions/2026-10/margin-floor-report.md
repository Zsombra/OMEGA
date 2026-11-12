# Report: pool floor in margin, share capped by free margin, contract 136 (2026-10-26)

Worktree `C:/tmp-bgm-marginfloor`, branch `fix/pool-margin-floor` from main `85c52b7`. Not merged, not pushed, not
deployed, not acked. No BattleGrid call; read-only psql only.

## Commits

- `3ff0c32` Contract 136.0.0: drop the retired `get_top_ranked_coins` from the proxy read allowlist (80 names)
- `d58dc85` Pool: floor and fit in MARGIN units, each share capped by the live free margin, resync on a real move only
- `68b542b` Pool resync: asymmetric hysteresis - lower at once, raise only on $2.00 or 25%
- `cc00640` Guards: a non-raising SYNC_LIMITS counts under its own `pool_lower` category (40/day backstop)
- `19ab7b7` Pool floor at the policy leverage, not the agent's stored one
- `c0db8bf` Pool: record when the floor is over the free room (`floor_over_room`)
- `256151c` Pool: a net unrealized loss comes off the free margin
- `1a2c80e` Pool resync: while the free margin sets the cap, any cent lower is a sync

### Review fixes (MERGE AFTER FIXES)

1. **The floor uses the policy leverage, `values.max_leverage`, in all three places.** That is the `maxLeverage` every
   sync writes. The three places are `pool_shares` (through `pool_from_db`, and `pool_of_state` with a new `leverage`
   argument), `build_trading_config`'s backstop, and `radar_describe`. This matches `review/rules`. Removed: the
   per-agent stored-leverage read, `floor_for`, `floor_note`, and the unread → $10 fallback. A leverage that is not a
   number ≥ 1 raises an error. A hand-built pool given no leverage still floors at the notional.
   - **Section 1 is now out of date.** Its text on the leverage source and the unread → $10 fallback describes the
     state before this fix; this item supersedes it.
2. **When the floor sits above the free room, it is now recorded.** The floor still wins. It shows up as:
   - `PoolShare.floor_over_room`;
   - `floorOverRoom` in the share record;
   - `poolFloorOverRoom` in the SYNC describe notes;
   - `sync_limits_pool_floor_over_room` in the guard metrics;
   - a sentence in the resync target's reason.
3. **A net unrealized loss comes off the free margin:** `free -= min(0, sum(unrealized_pnl_usd))` over the open
   positions. A gain is never counted as margin. Any unread PnL makes the free margin unread, so the share is the policy
   share alone, with a note.
   - Sources: `pool_from_db` reads `positions.unrealized_pnl_usd`, which is filled on all 1690 rows of the last 3
     days. `pool_of_state` reads a new `OpenPosition.unrealized_pnl_usd`.
   - The 3177 room becomes 7.36. The cap stays 4.45 (the policy share).
4. **While `capped_by_free_margin`, any lowering of a cent or more is proposed.** The other hysteresis rules are
   unchanged.
5. **The vendored skill-pack text is left alone**, for the pack refresh.

**Replay after the fixes:** same table as under `pool_lower`. Every agent in the data already sat at the policy's 3x,
so the floor is unchanged. The free-margin cap never bound a cent-level lowering in these 864 snapshots.

The pool change is one commit, because the floor, the free-margin cap and the hysteresis share the same functions in
`pool_state.py` and `describe.py`, and the tests at each step depend on all three.

## Full suite

One full run at `d58dc85`, without `-x` or `-n`: **5380 passed, 5 skipped**, 4 warnings (pre-existing `\(` escape
SyntaxWarnings), in 578.9 s.

After `68b542b`, one full run: **5384 passed, 5 skipped, 1 error**.
- The error was a setup error in `tests/actions/test_strategy_send.py::test_a_stage_approved_over_a_draft_version_that_moved_refuses_before_anything_is_sent`,
  a file this change does not touch.
- Rerun alone, the file passes: 52 passed.
- The run captured only the last two lines, so I cannot confirm the error was `WinError 10055`.

After `cc00640`, one full run: **5390 passed, 5 skipped, 1 failed**.
- The failure was `tests/commands/test_agents.py::test_an_archived_list_over_the_cap_narrows_to_one_read_per_known_agent`,
  on `WinError 10055`, in a file this change does not touch.
- Rerun alone, the file passes: 15 passed.

After the review fixes (`1a2c80e`), one full run: **5399 passed, 5 skipped**, 0 failed. The 4 warnings are the
pre-existing escape SyntaxWarnings.

## 1. Floor in margin units

`manager/risk/pool.py`:
- `margin_floor(min_notional, leverage)` is `min_notional / leverage` rounded UP to cents: 10 / 3 = 3.34, and
  3.34 x 3 = 10.02 still clears the minimum. An exact quotient keeps its own form (10 / 2 = 5).
- `floor_for` falls back to the notional itself (10) when the leverage is unread (absent, bool, not finite, or < 1).
  It returns a note, which `pool_shares` logs and puts on the share as `floor_note`.
- Leverage source: the agent's stored `tradingConfig.maxLeverage`.
  - `pool_from_db` reads it through `stored_configs`, from the latest snapshot's agent rows.
  - `pool_of_state` reads it from `state.agents[].trading_config`.
- `fits = cap >= floor`, and `cap = min(max(share, floor), ceiling)`.
- A hand-built pool that passes no `leverages` keeps the notional floor. That is why the older tests pass unchanged.

Platform evidence that the floor is margin times leverage against a notional: on action 206, `impact.capital` read
`smallestOrderUsd` 31.02 = cap 10.34 x 3 against `orderFloorUsd` 10. Action 217 read 47.91 = 15.97 x 3.

### Audit of every `min_notional_usd` comparison

**Changed (a margin amount was compared with the notional):**

| Place | Change |
|---|---|
| `pool.py` `pool_shares` | The floor (`max(share, floor)`) and `fits` use the per-agent margin floor. |
| `pool.py` `Pool.can_fund_one` | Gross against the lowest margin floor of the deployed agents. The property has no caller outside tests. |
| `pool_state.py` `pool_from_db` | Passes the leverages and the wallet. The `pool_requests` note and the `pool_lines` header now name the margin floor and the free margin. |
| `guards.py` SYNC_LIMITS | The fit test comes through `pool_of_state`. The verdict text for a ceiling below the floor names the margin floor. New metrics: `sync_limits_pool_floor_usd` and `sync_limits_pool_free_room_usd`. |
| `describe.py` | `_pool_recheck` and `_describe_sync` texts. New notes: `poolFlooredAtMin.floorUsd`, `poolCappedByFreeMargin`, `poolFreeMarginNote`, `poolFloorNote`. |
| `agent_config.build_trading_config` | The backstop `exposure < min_notional` became `exposure < floor_for(min_notional, read.trading_config.maxLeverage)`. Without this, every cap below $10 would have been refused at the send. |
| `radar_describe._agent_checks` | Gross against the highest margin floor of the target agents, from their stored leverage in the state. The floor is recorded as `notes.radar.marginFloorUsd`. |
| `review/rules.fleet_capacity` and `capacity_sentence` | `min_margin_usd(limits)` = `min_notional / limits.max_leverage`. The review plans the fleet that a SYNC writes, and a SYNC always writes the policy's `maxLeverage`; the review has no per-agent leverage for a new deployment. |
| `scheduler/jobs.py` | Log text only. |

**Kept notional (both sides are order notionals):**

| Place | Why it stays notional |
|---|---|
| `guards.py` `close_below_min_notional` | `pos.size_usd` is `currentNotionalUsd`. |
| `build_trading_config` `minAllocationUsd` up-clamp to the minimum | `minAllocationUsd` is an order size. README v77: "an order sized under the agent's own `minAllocationUsd`". |
| `policy.py`, `mode.py`, `commands/policy.py`, `pipeline.py:246`, `verify.py:512`, `jobs.py:1094` | They only check that the value is recorded. |
| `measure/platform.py` | Key-name hints only. |
| `review/cycle.py`, `review/views.py`, `pool_record`/`proposal_record` `minNotionalUsd` | They record the policy value as it is. |

**Left as it was, and flagged:** the `minAllocationUsd` clamp-DOWN, `min(raw, exposure)`, still compares a notional
with the margin cap. It cannot cause harm, because the notional up-clamp to the minimum runs right after it, and every
stored `minAllocationUsd` is 10 today. Making it `exposure x leverage` would be a separate, small fix.

## 2. Share capped by live free margin

Inputs, measured before coding:

- **`get_account_state.account.wallet_usdc`.** Read only when the read's status is OK (`wallet_of`).
- **`teams[].balance` is not stored.** The snapshot's `teams` carries ids only (`teams`, `mainTeamId`, `offMain`,
  `unread`), so the brief's Main balance input is not available. One team is the guard's own condition (contract
  132), so the wallet stands in for it.
- **Open margin.** Over all 814 snapshots of the last 3 days with an OK positions read, the sum of
  `positions.raw.marginedUsd` equals `list_user_active_positions.totals.marginedUsd` exactly. No row was null. The pool
  therefore uses the row margins it already holds; any unread margin makes the free margin unread.
- **Resting margin.** From `list_agent_open_orders` through `resting_entries`, as the pool already counts it. A failed,
  cut or unsized read, or no read at all, makes the free margin unread.

Rule:
- `free = wallet - sum(open margin) - sum(resting margin)`.
- `share = min(policy share, floor_cents(own open + own reserved + free))`.
- Then come the floor (`max`) and the ceiling (`min`). The never-raise check (`fresh_cap_refusal`), the ceilings and
  `clamped_loss_lines(cap)` are unchanged on top.
- Any input unread: the policy share alone, with `free_margin_note` on the share and the pool, and in the describe
  notes.

**Interpretation, please confirm.** The brief says "share = min(policy share, live free margin)". I add the agent's
own open and reserved margin back, because the platform counts them against the agent's own cap. The headroom the cap
leaves is therefore exactly the free margin. A literal `min(policy, free)` would put the cap of an agent already
holding a position below its own open margin. For a flat agent, which is every case in the 3177 replay, the two are
identical.

Measured base: on snapshot 11572, `23.665912 - 16.117934 = 7.548`, where the platform told the 3177 order it had
$7.71. On 10-25 08:03Z, `24.512 - 21.894 = 2.62`, where the platform said $2.43. So this estimate sits about ±$0.2 from
the platform's own "available" figure, in either direction.

### The 3177 replay is 4.45, not about 7.5

On snapshot 11572 the gross line was 20.57 (policy v8, applied 10-25 18:28Z) and the others held 16.12 of margin. The
**policy share is 4.45**, which is below the 7.54 free margin, so the cap is **4.45**. The brief's own rule (min of
the two) gives 4.45:
- not 10.34;
- at or below the $7.71 the platform said was free;
- its 3x notional, 13.35, clears $10.

The brief's "about $7.5" holds only when the policy share is above the free margin. The replay test runs that case too:
under a 26.00 gross line the cap is 7.54. A cap of 7.54 at gross 20.57 would breach the user's gross line: 16.12 + 7.54
is 100% of the wallet against `max_gross_exposure_pct` 85. Why the stored cap was 10.34: the old code floored a 4.45
share up to 10, and whole-dollar hysteresis kept an older 10.34.

## 3. Resync on change only

- **`pool_state.cap_moved(stored, cap, positions_moved)`.** A sync is proposed when the cap moves by at least $0.50 or
  at least 5% of the stored cap, whichever binds first. Once the open positions changed since the agent's last DONE
  SYNC_LIMITS, any move of a cent or more also proposes one.
- **How the position set is recorded.** The SYNC describe records `metrics.describe.poolPositionIds`, and
  `last_synced_positions` reads it back.
- **Rows from before this change.** They carry no record, and that counts as "not changed": the threshold still
  compares the two caps. This avoids a burst of syncs across the whole fleet on deploy.
- **The SYNC idempotency key now carries the cap in cents**, where it used to carry whole dollars. Otherwise a $0.50
  move inside one dollar would collide with the earlier key and never be filed. Edge case: a cap that returns to the
  exact same cent value on the same UTC day keeps the earlier key.

### Budget measurement

I replayed the 864 stored snapshots from 10-23 13:40Z to 10-26 13:40Z through the new pool:
- policy v7 / v8 gross lines;
- the recorded $20 ceilings;
- each sync assumed to land at once.

| Day | New rule (syncs) | Old rule: whole dollar, notional floor (syncs) |
|---|---|---|
| 10-23 (from 13:40) | 8 | 8 |
| 10-24 | 4 | 4 |
| 10-25 | 21 | 17 |
| 10-26 (to 13:40) | 16 | 10 |

The same replay without the position-set trigger gives identical counts. Every sync in it is a move of at least $0.50
or 5%, driven by a position opening or closing (or a resting entry reserving margin). Each event moves both TPO agents
together. The free-margin cap seldom binds over the policy share. The increase over the old rule comes from the lower
floor: caps now move between 3.34 and the share, where the old rule pinned them at 10.

### Asymmetric hysteresis (commit `68b542b`, the coordinator's follow-up)

The rule in `cap_moved` is now:
- **A lowering is proposed at once.** It needs at least $0.50 or 5%, or any cent once the open positions changed.
- **A raise needs at least $2.00 or 25% of the stored cap.** The position-set trigger never forces a raise.
- **Ceilings and platform holds are unchanged** and bind both directions.

Tests added:
- `test_any_meaningful_lowering_is_proposed_at_once`
- `test_a_small_raise_is_skipped`
- `test_a_large_raise_is_proposed`
- `test_the_position_set_trigger_lowers_but_never_forces_a_raise`
- the DB tests `test_a_small_raise_is_skipped`, `test_a_large_raise_is_proposed` and
  `test_a_position_change_alone_never_forces_a_raise`

I re-ran the same 3-day replay with this rule:

| Day | New, asymmetric rule (syncs) | Old rule: whole dollar, notional floor (syncs) |
|---|---|---|
| 10-23 (from 13:40Z) | 8 | 8 |
| 10-24 | 4 | 4 |
| 10-25 | 21 | 17 |
| 10-26 (to 13:40Z) | 16 | 10 |

**The counts did not change.** Of the 49 syncs, 22 are lowerings and 27 are raises, and every raise is at least $2.00
or 25%. In this account one position's margin is $3.6 to $11, so each close frees several dollars at once, and both
TPO agents move together. The budget pressure comes from position-sized moves, not from wobble.

What other raise bars would give on the same replay:

| Raise bar | 10-23 | 10-24 | 10-25 | 10-26 |
|---|---|---|---|---|
| $4.00 or 50% | 6 | 4 | 20 | 12 |
| $6.00 or 75% | 6 | 4 | 15 | 10 |
| never raise | 4 | 2 | 1 | 0 |

"Never raise" is degenerate: the caps sink to the floor and stay there.

### `pool_lower` category (commit `cc00640`, the coordinator's second ruling)

**What changed:**
- **A non-raising SYNC_LIMITS has its own guard category, `pool_lower`.** Non-raising means `sync_raising_axis` is
  None: every axis is at or on the tighter side of the stored value.
- **It is capped at `POOL_LOWER_CAP` = 40 a day**, as a runaway backstop.
- **The cap is a constant, not a policy `actions_per_day` key.** This follows the existing pool HALT pattern. A new key
  would read 0 from every stored policy version, which would refuse every lowering until a new policy version is
  applied (the warning on `GUARD_CATEGORY`). The backstop is also not a risk preference the user tunes.

**How each sync is classified once:**
- `risk_guard` computes the category from its own non-raising verdict at send time.
- It records that verdict in `metrics.risk.sync_non_raising`.
- `actions_today` counts each sent row from that recorded verdict (`recorded_non_raising`).
- So the count and the cap always agree. A row from before this change has no record and counts under
  `agent_config`, as it did when it was sent.

**Executor:** when `agent_config` is spent, the fleet resync still proposes the syncs whose pool cap is below the
stored cap (`_lowering_syncs`); the guard classifies them for good at the send. Raising syncs, RESUME and everything
else stay on `agent_config` (12).

**Tests:**
- a lowering counts under `pool_lower` and passes with `agent_config` spent;
- a raising sync is refused at `agent_config` 12 of 12;
- `pool_lower` refuses at 40 and not at 39;
- `actions_today` counts by the recorded verdict;
- `_lowering_syncs` proposes a lowering and skips a raise.

**3-day replay under this rule** (asymmetric hysteresis kept):

| Day | Lowering syncs (`pool_lower`) | Raising syncs (`agent_config`) | `agent_config` at or under 12? |
|---|---|---|---|
| 10-23 (from 13:40Z) | 4 | 4 | yes |
| 10-24 | 4 | 0 | yes |
| 10-25 | 8 | 13 | **no**: 13 from raises alone, before any RESUME |
| 10-26 (to 13:40Z) | 6 | 10 | yes so far; 2 left for the rest of the day |

The lowerings are now safe from the budget. On a day like 10-25, the 13th raise and any later ones are refused until
the UTC rollover. The cap then stays lower than the room: stale in the safe direction, never above it.

So quiet days stay well under the 12 `agent_config` budget, but **busy days do not** (the earlier counts above). On 10-25 the old rule was already
over it (17). The 900 s resync cadence would merge some of these: the real DONE counts were 7 on 10-25, with writes
blocked until 08:05Z, and 6 on 10-26. If the budget binds, the agent_config cap refuses the late syncs, which leaves
the last written cap standing, the same as today. Option for the user: lower at once but raise only on a larger move,
since a raise is not urgent.

## 4. Contract 136.0.0

- **The allowlist.** `get_top_ranked_coins` is removed from `manager/proxy/policy.py` (80 names), so it also leaves
  `READ_ALLOWLIST`. Count tests were updated in `tests/proxy/test_policy.py` and `tests/mcp/test_server.py`, with a new
  v136 test.
- **Skill text.** No Commander skill in this repo (`hermes/`, `skills`) names the tool. The only text that names it is
  the vendored upstream pack `.agents/skills/battlegrid/skills/battlegrid-market-analysis/SKILL.md:30`. I did not edit
  it (it is vendor); the next pack refresh replaces it.
- **The rest of v136.**
  - The rank `scope` and the ranked `coinSelection.rankBy` are both optional and default to the old behaviour. The
    manager's only ranked selection, `panel/columns.py`, sends `mode`/`limit`/`category` and no `rankBy`, so it keeps
    24h-volume ranking.
  - "Category membership is the main category only" can change the panel's coin counts for a non-ALL category, by
    about 1 coin for `defi`. That is a value change, not a code change.
  - `vocabularyDigest` moves; nothing in the manager caches it.
- **Not acked.**

## Tests added

`tests/risk/test_pool_margin_floor.py` (17 tests):
- floor at 3x = 3.34;
- unread leverage gives a floor of 10;
- the 3177 replay: 4.45, not 10.34, and 7.54 when the policy has room;
- an unread wallet, unread orders or an unread margin gives the policy share;
- the ceiling binds;
- a free margin under the floor is floored;
- the loss-line clamp holds under the new cap;
- hysteresis.

`tests/actions/test_pool_margin_floor_db.py` (5 tests):
- floor and free margin come from the snapshot;
- a small move gives no target, and a changed position set gives one;
- `build_trading_config` accepts 5.84 at 3x / 17.5.

Also `poolPositionIds` recorded (`test_pool_sync`) and `get_top_ranked_coins` not allowlisted (`test_policy`).

Tests updated for the intended behaviour change:
- review capacity at the 2x margin floor;
- radar_describe / pool texts name the margin floor;
- the SYNC key in cents;
- `FITTING`'s stored cap 546.0 became 546.1, so the world stays within the new $0.50 band.

## Concerns

1. **Replay expectation:** the 3177 cap is 4.45 by the brief's own rule, not "about 7.5". See section 2.
2. **Own margin added back** to the free-margin room. This is my interpretation; please confirm it.
3. **`agent_config` budget:** busy days replay at 16-21 syncs, against a budget of 12. The old rule already reached 17.
4. **Free-margin accuracy:** the estimate is about ±$0.2 from the platform's own "available" figure, and the $0.50 / 5%
   band lets the cap trail the free margin by up to that much. An order can still fail at the margin check inside that
   band, which the floor-at-min ruling accepts.
5. **No `teams[].balance` in the stored reads.** The wallet stands in for Main.
6. **Today's live state:** the latest snapshot (11685) has a failed agents read and no orders read (the token is
   revoked), so after a deploy every agent floors at 10 and every share is the policy share, until the reads come back.
   This fails safe.
7. **Not edited:** the `minAllocationUsd` clamp-down unit mix, and the vendored skill text naming the retired tool.
