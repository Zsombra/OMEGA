# Syncfix report: lowering syncs are no longer refused for fleet exposure; refused-sync churn throttled (2026-10-25)

Worktree `C:/tmp-bgm-syncfix`, branch `fix/sync-lowering-not-refused` from main `e65c609`. Not merged, pushed or
deployed. No BattleGrid calls and no Docker or .env changes; the only database access was read-only psql. Written at 13:02Z.

## Commits

| sha | what |
|---|---|
| def85a0 | A SYNC_LIMITS that raises nothing is exempt from the fleet checks |
| 9a899b1 | The fleet resync does not re-propose an identical refused SYNC for 1 h |
| ecb4652 | is_edit_base requires expectedRevision >= 1 (the schema minimum) |
| 6874e20 | A held-draft SYNC refusal is never throttled |

## Task 1: a non-raising SYNC skips the fleet checks (`manager/risk/guards.py`)

- **New function.** `sync_raising_axis(params, stored)` returns None when the sync raises nothing. Otherwise it returns
  the first raising axis, or the reason the stored config counts as unread.
- **Axes where the tighter value is lower:** `maxConcurrentExposureUsd`, `maxCumulativeDrawdownUsd`, `maxDailyLossUsd`,
  `maxLeverage`, `maxDailyTrades`, `maxSlippageBps`, and the three `positionSizePresets` pcts. The preset direction comes
  from the TRADING_CONFIG schema description: "the most of the agent's free headroom ... one trade loses".
- **Axes where the tighter value is higher, so lowering them loosens:**
  - `minAllocationUsd`. README v78 says an order under it is refused (`BELOW_AGENT_MIN_ORDER`), and that "a lower
    minAllocationUsd" clears a capital-feasibility refusal.
  - `balanceThresholdUsd`. The README calls it the "Balance floor"; an accept is refused while equity is below it.
  - The stored `manager_schemas` carry no per-field description for these two. The README text above is the only
    platform statement of their direction.
- **What counts as raising (Rule 3):**
  - an unread or empty stored config, or an agent the state does not carry;
  - an axis missing on either side;
  - a non-numeric value, including a bool;
  - a change to any key outside the list.
- **Where the stored config comes from.** The guard reads `AgentState.trading_config` for the target. That is the latest
  snapshot's `list_intelligence_agents` row, overlaid by describe's same-action `get_intelligence_agent` read. It is the
  base the commit lands over.
- **How the exemption works.**
  - The exemption is a separate `skip_fleet_checks` flag. It skips only heat, gross exposure, leverage, the open-position
    count and the same-direction cap.
  - I did NOT add the SYNC to `exempt_fleet_checks` itself. That flag also narrows the breach lines to the target alone.
    The brief says the breach lines must stay fleet-wide.
  - These are unchanged: the fleet-wide breach lines, the pool-share checks, the action cap, the unread-snapshot refusal,
    the team guard and describe's `breach_on_write`. RESUME keeps the whole guard.
- **Audit trail.** Every SYNC records `metrics["risk"]["sync_non_raising"] = {"non_raising": bool, "first_raising_axis":
  str|None}`. The docstring is updated.
- **Tests** (`tests/risk/test_sync_non_raising.py`, 23 tests):
  - a lowering SYNC passes while gross is over;
  - raising any single axis is refused (one test per axis), and lowering either floor axis is refused;
  - an unread stored config is refused, and so is an agent the state does not carry;
  - missing, non-numeric and unknown keys count as raising;
  - the breach lines, the action cap and the pool share still refuse;
  - RESUME is unchanged.
  - **The 10-25 replay of action 134.** Policy v5 lines are gross 21.16 and heat 1.24. The stored cap is $20 (the
    08:18Z snapshot: drawdown 4 and daily loss 2). The open position is the $21.681 COIN 3x long, margin 7.25648. The
    replay now PASSES with pool share 13.90.
- **The VWAP refusal still stands** (added to `tests/actions/test_sync_breach.py`). Its sync is non-raising, so the guard
  would let it past the fleet lines. `breach_on_write` still refuses it: drawdown line 1.24 against a drawdown of 1.49.

## Task 2: identical refused syncs are throttled (`manager/scheduler/jobs.py`)

- **Constant:** `REFUSED_SYNC_RETRY_S = 3600`. The fleet resync loop calls `_refused_sync_throttle` for each agent
  before it proposes.
- **When a sync is skipped.** All of these must hold:
  - the agent's newest SYNC_LIMITS is REFUSED and younger than 1 h;
  - `key_for` gives the same idempotency key (same UTC day, policy version and deployed fleet);
  - the pool cap, floored to cents, equals the cap the refused params wrote;
  - the snapshot's stored limits equal the refused row's `describe.baseTradingConfig` on every axis;
  - the open-position count equals the one the refused row's risk guard counted.
- Each comparison runs only if the refused row recorded that input. If anything cannot be computed, the sync is proposed
  as before.
- **Logging:** one INFO line per throttled row, quoting its verdicts.
- **Never throttled:**
  - HALT, CLOSE and TIGHTEN. They never pass through this loop.
  - A **held-draft** refusal (commit 6874e20). The player clears it in the agent editor, which no snapshot shows, and
    its verdict promises "the next fleet resync proposes again". The existing test
    `test_a_commit_conflict_proposes_no_retry_and_the_next_fleet_resync_proposes_again` caught this.
- **Tests** (`tests/actions/test_refused_sync_throttle.py`, 7 tests):
  - an identical refused sync is skipped within the hour and logged once;
  - it is proposed again at 3600 s;
  - changed params are proposed at once;
  - a moved stored config or position count is proposed at once;
  - a non-REFUSED row is never throttled, and neither is a held-draft refusal.

## Task 3: `is_edit_base` (`manager/actions/pipeline.py`)

`is_edit_base` now requires an int of at least 1, never a bool. The new test
`test_an_edit_base_is_an_int_of_at_least_one` covers 1, 4, 0, -1, None and True.

## Suite

Full run: **5197 passed, 5 skipped, 1 error** (510 s).

- The error was the teardown of `tests/review/test_take.py::test_a_resume_whose_slot_agent_changed_since_the_review_is_refused`:
  "'ProactorEventLoop' object has no attribute '_ssock'". That is a Windows event-loop flake.
- Rerunning that file alone gave 24 passed.

## Concerns

1. **The `minAllocationUsd` direction disagrees with existing code.**
   - The README says a higher `minAllocationUsd` is tighter, so this guard treats lowering it as loosening.
   - The F1 helper `agent_config.only_lowers` (`LOWER_IS_SAFER`) says the opposite.
   - `build_trading_config` clamps `minAllocationUsd` down to the pool share. A sync that does this clamp counts as
     raising here, so it still faces the fleet checks. None of the 10-25 rows did (10 -> 10).
   - The user should rule on this axis. Once ruled, `only_lowers` should be reconciled with it.
2. **The stored config is describe's live read.** The guard compares against the live read when describe overlaid it,
   not strictly the snapshot. That read is the commit's actual base.
   - The throttle compares the snapshot against the refused row's live base. If the snapshot lags, the throttle may
     simply not engage. That direction is safe: churn, not a missed write.
3. **The VWAP refusal still repeats, but hourly.** The throttle cuts it from every 15 min to every 60 min. It is not
   suppressed. It clears only when the user raises the 1.24 drawdown line or resets the agent's baseline, which is
   already open as the user's decision.
4. **This takes effect only after a deploy.** Pool-halted agents waiting on "tighten before re-arm" are released only
   once this branch is merged and deployed, which is the user's call.

## Review fixes (verdict MERGE AFTER FIXES; written 13:20Z)

| sha | finding | fix |
|---|---|---|
| 2c9298c | MEDIUM: a row with no recorded inputs held a sync for 60 min on the key alone | The throttle now requires two things. First, the refused row must carry params. Second, every verdict must be on an allow-list: `breach_on_write`'s exact line, or one of the five fleet-check lines when the guard judged the sync RAISING (`sync_non_raising.non_raising` false). A verdict naming undetermined, unread, expired or rate is never throttled. Tests cover 14 excluded shapes: expiry; refusal before the build; unread draft; UNDETERMINED pool share; heat undetermined; rate; revision race; both breach lines; a fleet line on a non-raising sync or one with no judgement; `breach_on_write` mixed with an UNDETERMINED line; an allowed line next to the action cap; no verdict. |
| 559c4b4 | LOW: a throttle exception could abort the tick | `_throttled_safely` logs the exception, rolls back, and treats the sync as not throttled. The test makes the throttle raise and checks that the sync and the pool HALT are still proposed. |
| 2712d91 | LOW: NaN | `_axis_number` returns None unless the value is finite. NaN, "NaN", inf and "-Infinity" count as raising, and the guard applies in full. |
| f0d8e91 | LOW: other axes | Each of these counts as raising: a draft axis other than `TRADING_CONFIG`, a key in that axis other than `tradingConfig`, a top-level `tradingConfig`, or any params key beyond `sync_request`'s four (`agentId`, `draftVersion`, `expectedRevision`, `axes`). An unknown key INSIDE the tradingConfig still passes only when it equals the stored value, as before. |
| ba6b54f | `minAllocationUsd` direction | Dropped from `LOWER_IS_SAFER`, so `only_lowers` now treats a lower minimum as no lowering. This matches `SYNC_TIGHTER_IS_HIGHER`. A test was added to `test_pool_ceilings.py`. No existing test pinned the old direction. Concern 1 above is resolved. |
| f9f0e44 | Nit: unbounded set | `_throttle_logged` is now a map from row id to proposed_at. Entries older than `REFUSED_SYNC_RETRY_S` are pruned on every call. Tested. |

**Suite:** 5222 passed, 5 skipped, 1 error.
- The error was `tests/actions/test_red.py::test_one_agent_s_unexpected_failure_does_not_cost_another_agent_its_rollover`, from Windows socket exhaustion (WinError 10055) during event-loop setup.
- That file alone: 50 passed.
