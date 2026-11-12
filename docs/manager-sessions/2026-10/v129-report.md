# v129 migration report: battlegrid-manager

The worktree is C:/tmp-bgm-v129, on branch fix/contract-129, based on main 860f8e4. Nothing has been merged, pushed, deployed or acknowledged, and no BattleGrid call was made. The only live access was read-only psql against system_state.

## Phase A

### Commits (oldest first)

| Commit | What it does |
|---|---|
| 0a3cbf8 | TIGHTEN at v128: sends the stop level, settles the leg-by-leg answer, and verifies by reading the stop back. |
| 41fcb57 | Agents hub at v126: reads `hubStatus` and drops `pendingApprovalCount` (describe for archive, activate, rebind and remodel). |
| 253a40b | Bookkeeping: the reads that v124-v126 removed leave the allowlist, and 129.0.0 holds as a clean baseline. |
| 678964e | Pins that no code matches `AWAITING_APPROVAL` or reads a field that v125/v126 removed. |
| ec55cf0 | TIGHTEN: a stop leg's `exchange-error` is FAILED, not UNKNOWN. |

### 1. TIGHTEN (`override_agent_protection`)

**Describe.** Describe now builds `{decisionId, stopLossPrice}`. The stop level is break-even (the entry price), as before. The audit-history read for the live stop order id is gone, and so is `_live_stop_order_id`.

**Send.** `manager/actions/tighten.py:wire_params` refuses to build a send in two cases:
- the row still carries `effectiveStopLoss` or `effectiveStopLossOrderId`;
- the row lacks `decisionId` or `stopLossPrice`.

When that happens, `execute` records FAILED with "not sent", and nothing goes on the wire. Describe always rebuilds the params, so a pre-v128 QUEUED row that was approved by its params sha is refused on the sha mismatch.

**Answer: `tighten.send_outcome`.** Every branch except "committed" stores its reason in the row's `error` field.

| Answer | Status after the send |
|---|---|
| `dispatched`, stopLoss `committed`, success true | VERIFYING |
| `dispatched`, stopLoss `queued`, success false | VERIFYING, with the note "recorded, placed after the amendment in progress" |
| `level-crossed`, `mark-unavailable`, `rate-limited` (success false) | FAILED: nothing was written |
| stopLoss `lock-busy`, `version-conflict`, `mark-in-flight-conflict`, `execution-not-open`, `no-position`, `no-improvement`, `approval-expired`, `exchange-error` | FAILED: the stop did not move, per "only committed moved the leg" |
| Anything else | UNKNOWN |

"Anything else" covers:
- not a dict, or no `result`;
- no boolean `success`;
- a top-level kind the manager does not know, such as the old bare `committed` or `stale-order`;
- a stop leg kind it does not know, a null stop leg, or a dispatch without both legs;
- a `takeProfit` leg the manager never sent;
- a `decisionId` other than the one sent;
- `success` contradicting the legs (committed with false, queued or a refusal with true).

**Verify.** `verify._verify_tighten` settles the row in three steps:
1. It reads `list_user_active_positions`. The row is DONE when the position's `effectiveStopLoss` equals `stopLossPrice` (compared as Decimals).
2. Otherwise it reads `get_position_audit_history`. The row is DONE if there is an `SL_REPLACED` at or after the send to the requested price.
3. Otherwise it quotes `get_open_orders` into the note and leaves the row unsettled. The verify window then makes it UNKNOWN.

The verify pass never FAILS a TIGHTEN, because a queued stop has not moved yet. Pre-v128 rows, which hold `effectiveStopLoss`, are still settled by the same comparison. `VERIFY_READS["TIGHTEN"]` now reserves 3 reads.

**Fakes.** The test fakes now check every call against the stored 129.0.0 input schemas, so any send that still names a retired key fails the test. The new fixture `tests/fixtures/2026-10-22-surface-129.0.0/manager_schemas_129.0.0.json` is `manager_schemas` verbatim. The fake answers for override, halt and resume follow the 129.0.0 output shapes.

**Tests.** `tests/actions/test_tighten_v128.py` covers:
- a table of outcomes per kind, with each answer validated against the 129.0.0 output schema;
- a coverage test that the table names every arm the schema serves;
- 15 fail-closed UNKNOWN cases;
- the wire input validated against the 129.0.0 input schema;
- retired-key refusals.

The pipeline and verify tests were updated to match.

### 2. Archive/activate describe (`get_agents_hub`)

- `classify_exposure` no longer reads `pendingApprovalCount`. It now reads `hubStatus` as follows:
  - any value except IDLE makes the exposure LIVE;
  - a missing value, or one outside IN_TRADE, RADAR_ARMED, ARENA_DEPLOYED and IDLE (`AWAITING_APPROVAL` and `PROPOSED` included), is unread, so describe refuses with "an unread exposure is not an idle one".
- `archive_blockers` names a non-IDLE `hubStatus` that no count explains.
- REBIND refuses on `activeTradeCount > 0` or on `IN_TRADE`, which replaces the old pending-approval check.
- The dry card shows the hub status.
- The read set for `get_agents_hub` declares `/rows[]/hubStatus` instead of `/rows[]/pendingApprovalCount`.

### 3. `get_signal_log` `PROPOSED`

There is nothing to change. No code matches the execution status: the manager reads only `failureReason`, `expiryReason` and `executionMessage`. A test pins this, and checks that the 129.0.0 enum has `PROPOSED` and not `AWAITING_APPROVAL`. The Hermes skills do not name it either.

### 4. Bookkeeping

**Allowlist.** `PROXY_ALLOWLIST` went from 94 to 81. These thirteen removed reads left it:
- get_agent_journal, get_user_thought_log, get_user_activity_feed
- list_trade_outcomes, get_signal_performance, get_agent_open_positions
- get_public_agent_unrealized_pnl, list_session_agent_positions, get_order_status
- get_decision_order_attribution, list_entry_decisions, get_agent_fund_allocation
- list_pending_approvals

`accept_entry_decision` and `cancel_entry_decision` were never on any list. The read client now refuses all of these with NOT_ALLOWED before the wire, and a test covers each one.

**Deviation from the brief.** `list_entry_decisions` and `list_trade_outcomes` stay in `MANAGER_TOOLS` and `READ_SETS` until Phase B, because the snapshot and allocation code still name them.
- They are harmless to D7, D7b and D7c. No contract serves them, so they are absent from both the baseline and every observation and can never move again. A comment in `watch.py` says this.
- Removing them now would have meant rewriting about 15 historical replay and count tests that Phase B touches anyway.
- In the meantime their callers fail closed:
  - the entry watches read UNDETERMINED, which is a watch read and does not turn the snapshot red;
  - allocation and review record the agent's performance read as failed.
- That is the same result as today's unknown-tool error from the platform, but it no longer spends rate-bucket tokens.
- `WRITE_PIPELINE_READS` held none of the removed tools.

**Read sets.**
- `get_agents_hub`: updated as described in section 2.
- `list_user_active_positions`: stays `{/positions, /totals}`. Nothing reads the nested `agents[].positions` that v125 removed. The comment was updated.
- `halt_intelligence_agent` and `resume_intelligence_agent`: stay undeclared, so they are judged strictly as writes. Nothing reads `allocation.availableUsd`, `lifetimeAllocatedUsd` or `lifetimeRecalledUsd`, and a test pins this.

**Clean baseline.** `tests/platform/test_contract_129.py` checks four things:
- `manager_schemas()` over the 129.0.0 listing equals the stored observation tool for tool, with the same hash, so nothing is "never recorded";
- `MANAGER_TOOLS` minus the served tools is only the two retired writes plus the two Phase-B tools;
- `self_clear_verdict` reads 129 against a 129 baseline as `identical`;
- an end-to-end `job_watch` after the ack keeps 129.0.0 with no drift, no backfill and writes open.

The code change does not move the `manager_schemas` hash. The ack's `observed` row, written at 00:16:01Z under 129.0.0 build b8a77808, is therefore exactly what the new code computes, and `manager contract ack 129.0.0` will baseline it directly.

### Suite

The run on 678964e, with ec55cf0 landing mid-run, gave 4992 passed, 5 skipped, 1 failed and 1 error. The failure and the error were both `WinError 10055` (socket buffer exhaustion) in tests/hermes/test_plugin_api.py and tests/review/test_views.py. Both files pass on their own (59 passed).

The final full run on ec55cf0 was clean: **4994 passed, 5 skipped, 0 failed** (611 s).

### Concerns

- **No live evidence for the new answer.** No TIGHTEN has been sent since v128, so the answer handling rests on the published 129.0.0 schema and README only. The first live TIGHTEN should be read back by hand.
- **TIGHTEN rows can block a CLOSE.** A queued, or otherwise unconfirmed, TIGHTEN stays VERIFYING and then UNKNOWN for up to the verify window (600 s). During that time it holds the position's in-flight key, which blocks a CLOSE on the same position. This already happened before (a committed stop with no `SL_REPLACED`). Moving `exchange-error` to FAILED narrows it.
- **Stop loosening.** v128 says the move "bypasses the platform ratchet, so a stop may be loosened". The manager only tightens to break-even when entry lies strictly between the stop and the mark, so it never loosens. That geometry check is now the only guard against loosening.
- **Interim reads.** Until Phase B deploys, the entry watches (failures, expiries, not-filling, and the agent-status 24 h counts) read UNDETERMINED, and allocation and review lack performance data. This is the same state as today.
- **Ack timing.** After the deploy, writes stay blocked until `manager contract ack 129.0.0`. The self-clear will not clear the block by itself: write-tool descriptions and annotations changed, and halt/resume output fields were removed. This is your rule for a breaking block.
- **Flaky run.** One full run earlier in this session showed `test_an_approved_sync_sends_when_its_reads_are_unchanged` failing once, and it passed on 3 reruns. It looks timing-related and is unrelated to this change.

## Phase B

The worktree merged main first (now at or after 9a9ab9a). Nothing has been merged, pushed, deployed or acknowledged, and no BattleGrid call was made. The only live access was read-only psql: `system_state` (surface_tools, manager_schemas, contract and writes_blocked) and `entry_decisions` / `actions`.

### Commits (oldest first)

| Commit | What it does |
|---|---|
| 05d58e1 | Items 6 and 7 plus bookkeeping: the entry watches read `list_signal_logs`, and allocation and review read `list_agent_trades`. The two tools v125 removed leave `MANAGER_TOOLS` and `READ_SETS`. |
| 7d02ac3 | A1: a CLOSE is no longer refused when the only in-flight row on its position is a TIGHTEN that is settling (VERIFYING or UNKNOWN). |
| 81c12b4 | A2: a stop that was not reported `committed` is DONE only with corroboration. |
| 3ff88f3 | Item 9: the Commander skill drops removed tools and names the replacement reads. A test pins that no Hermes file names a removed tool. |

These are four commits, not one per item. Items 6, 7 and the bookkeeping share `watch.py`, `reads.py` and `policy.py`, and the historical replay tests need all of them at once, so they went in one commit (05d58e1).

### Item 6: entry watches on `list_signal_logs`

**The read.** Each deployed agent gets one `list_signal_logs {agentId, window: "1D", limit: 25}` page per snapshot.
- A page over the result cap is narrowed with `call_narrowing`, down to 5 rows, the same way gate blocks are.
- The read key is now `list_signal_logs:<agent>`.

**The parse.** `normalize.normalize_signal_entries` keeps ENTER rows only. The read can no longer filter on the decision server-side, so SKIP (`decision` null) and GATED rows share the page and are dropped here.
- It fails closed in these cases:
  - no `signals` list;
  - a row that is not an object, or lacks the `decision` key;
  - an ENTER row without a string `id`, `terminalStatus` or `createdAt`;
  - a non-null `rejection` without a string `reason`.
- The read-set gate (`missing_paths`) still runs before any row is used. The declared paths are `/signals[]/id`, `decision`, `terminalStatus`, `createdAt` and `rejection` (rooted at `rejection`).
- `coinTicker`, `assessmentDirection` and `levels.entryPrice` are optional display fields.

**Status vocabulary.** `terminalStatus` is stored in the vocabulary the watches already use: OPEN is stored as EXECUTED, and every other value is stored as served. Because of that, the streak, ack and auto-resolve rules and all 43 stored rows read unchanged.
- The known set is the 129.0.0 `terminalStatus` enum, taken from `get_signal_log`'s `log.terminalStatus` in the stored schema: BLOCKED, EVALUATING, INELIGIBLE, SKIPPED, PENDING, OPEN, FAILED, EXPIRED, CANCELLED and PASS.
- Any other value is still recorded as `unknownStatuses`.

**Reasons.**
- **FAILED with a `rejection`:** `rejection.reason` and `rejection.detail` become `failure_reason` and `execution_message`, settled OK at once with no detail read. A settled reason is never overwritten, and a rejection of `AGENT_HALTED` still does not count.
- **FAILED without a rejection, and EXPIRED:** these still take the one bounded `get_signal_log` per agent per snapshot. FAILED goes first, then EXPIRED, with `logId` set to the row id. That read is unchanged otherwise: up to 3 attempts, NOT_FOUND or `log: null` makes it UNREADABLE, and a transport error is retried.

**Keys.**
- The signal-log rows carry no decision id. A row first seen now is stored with `decision_id` = `signal_log_id` = the signal log id.
- Served rows are matched by `signal_log_id`. All 43 stored rows have a unique one (checked by psql), so a row stored from `list_entry_decisions` is updated in place: it keeps its old decision-id key, its `created_at` and its settled reason, and it is never doubled.
- A new index `ix_entry_decisions_signal_log_id` is added through `_ADDED_INDEXES`. There is no data migration. Alert identity is by instant, so existing alerts and acks are unaffected.

### Item 7: allocation and review on `list_agent_trades`

- `performance.read_trades` pages `list_agent_trades {agentId, limit: 50, cursor}` with the same guards as before:
  - `nextCursor` must be readable;
  - a repeated cursor is refused;
  - narrowing over the cap restarts from the first page;
  - rows are de-duplicated by `positionId`;
  - the page budget is bounded.
- `netPnl` is a decimal string. It is parsed to Decimal (finite only; a number, bool, NaN or garbage is refused) and summed exactly. The total is handed to the ranking and the review as a float, the type they already take. A win is still netPnl > 0, which matches the platform's `isWin` rule.
- The review's window still uses `closedAt`.
- No `get_trade_outcome_by_decision` call was needed, because only the coin, net P&L and close time are read.

### Bookkeeping

- **`MANAGER_TOOLS`** loses `list_entry_decisions` and `list_trade_outcomes` and gains `list_signal_logs` and `list_agent_trades`; it stays at 56. `READ_SETS` is swapped the same way.
- **Allowlist.** `list_agent_trades` joins `PROXY_ALLOWLIST`, which goes from 81 to 82. The read client needs it, and it replaces `list_trade_outcomes`, which was on that list. It is readOnlyHint true in the stored 129.0.0 surface. `list_signal_logs` was already on the list.
- **Historical replay tests** (`test_reads`, `test_read_only_descriptions`, `test_watch`) now judge moves from 95 to 123 with the tool set and read sets of that time, kept in `tests/platform/history.py`.
- **Ack, two orders.** `test_contract_129` pins both:
  - Phase B deployed, then `manager contract ack 129.0.0`: the first watch run rewrites the 00:16Z observation with the two new reads, because its hash moved. The ack then copies that in, with no backfill and no drift.
  - Acked under Phase A, then Phase B deployed: the watch backfills the two reads on its first unchanged tick. It records one `contract.schemas_backfilled` and nothing blocks.
- **New fixtures** in `tests/fixtures/2026-10-22-surface-129.0.0`:
  - `surface_tools_v129_reads.json`: the two reads' stored surface rows, verbatim.
  - `live_samples.json`: the brief's live samples, with the brief's elisions noted.

### Item 8: windows

Skipped (it is optional). The entry read uses `window: "1D"`. Nothing else is paged by time: gate blocks are one newest page, and allocation and review need each agent's whole record.

### Item 9: Commander skills

`hermes/skills/battlegrid-manager/SKILL.md` had two stale lines:
- It still said `accept_entry_decision` opens the position. It now says `propose_entry_decision` queues an entry that is placed at the decided close with no approval step, and that `cancel_entry_request` withdraws it.
- It named `upsert_radar_deployment`, which 69.0.0 retired. It now names the stage and commit drafts.

It also now names `list_signal_logs` → `get_signal_log` and `list_agent_trades` → `get_trade_outcome_by_decision`. Neither SOUL.md nor the sentinel skill named a removed tool. A test pins that no Hermes .md file does.

### A1: a CLOSE behind a settling TIGHTEN

- `AccountState.in_flight_settling_tightens` counts TIGHTEN rows that are VERIFYING or UNKNOWN on each target, with the same exclusions as `in_flight`. It is built by `state.settling_tightens`.
- `in_flight_guard` lets a CLOSE pass when every in-flight row on its position is one of those. The metric records `settlingTightensIgnored`.
- These still refuse the CLOSE:
  - a QUEUED or PERFORMING TIGHTEN;
  - any other row on the position, including a settling CLOSE;
  - a settling TIGHTEN on the position together with any other row.
- Every other kind keeps the existing rules, including the RED HALT and pause carve-outs.
- Tests in `tests/risk/test_guards.py` cover VERIFYING and UNKNOWN passing, QUEUED and PERFORMING refusing, a mixed set refusing, a TIGHTEN on another position, and TIGHTEN-behind-TIGHTEN still refusing.

### A2: corroboration of a stop that was not committed

**When it applies.** An equal `effectiveStopLoss` read-back is DONE on its own only when the stored answer says the stop leg was `committed` with `success` true (`tighten.stop_committed`). In every other case the row needs one of two corroborations before DONE: `queued`, an UNKNOWN answer, or a row with no v128 answer.

Both kinds of evidence were measured from the stored 129.0.0 output schemas.

- **Audit history.** `get_position_audit_history` shows an `SL_REPLACED` event, matched on `kind`, `createdAt` and `toPrice`, at or after `performed_at` and to the requested price.
- **Open orders.** `get_open_orders` holds an order that matches all of these:
  - `status` OPEN;
  - `reduceOnly` true;
  - `side` is the closing side: SELL for a LONG, BUY for a SHORT;
  - `triggerPrice` equals the requested stop, compared as Decimals;
  - `symbol` is the position's coin ticker or its stored Hyperliquid symbol (`coin_symbols`).

**Otherwise** the row keeps its status, its note says "not corroborated yet", and the existing 600 s window makes it UNKNOWN. The verify pass never calls it DONE.

**Limits of the evidence.**
- No live `get_open_orders` answer is stored, so the format of `symbol` is not measured. A symbol that is neither name never matches, which fails closed.
- `SL_PLACED` is not accepted, because it is not a replacement.

The reads stay within `VERIFY_READS["TIGHTEN"]`, which is 3. Tests cover these cases, and each invented answer is validated against the 129.0.0 schemas:
- queued, UNKNOWN and pre-v128 rows waiting for corroboration;
- the `SL_REPLACED` path, including a replacement from before the send;
- the open-order path, including the Hyperliquid-symbol match;
- seven non-matching orders;
- the window taking an uncorroborated row to UNKNOWN.

### Suite

The full run on 3ff88f3 (no -x, no -n) was clean: **5045 passed, 5 skipped, 0 failed** (607 s). In an earlier `tests/actions` run, `test_a_plan_from_another_omega_pin_is_refused` errored once. The file passed on rerun (60 passed) and in the full run, so it looks like the same transient socket error seen in Phase A.

### Concerns

1. **The two new reads' 129.0.0 output schemas are not stored anywhere.** `surface_tools` holds input schemas only, and the `manager_schemas` observation predates the two reads.
   - Their declared read paths are checked as served against the brief's live samples only, not as required in a schema.
   - After the first watch run post-deploy, read `manager_schemas.tools.list_signal_logs` and `.list_agent_trades` and confirm that `id`, `decision`, `terminalStatus`, `createdAt`, `rejection`, `positionId`, `coinTicker`, `netPnl`, `closedAt` and `nextCursor` are served and required.
2. **OPEN = EXECUTED is inferred from the enum.** The 129 `terminalStatus` enum has no CLOSED, so a signal whose position opened (and later closed) is taken to stay OPEN. If a closed trade reads anything else, the "entries executing again" resolve and the streak break would miss it.
3. **Display and timing differences on new rows.**
   - The direction is the assessment's (UP/DOWN mapped to LONG/SHORT).
   - `created_at` is the signal log's instant, slightly before the old decision's.
   - `expires_at` and `executed_order_id` are no longer served, so the expiry alert and agent status omit them on new rows.
4. **Page coverage.** A page is 25 rows for the last 24 h, SKIP and GATED included. An agent with more than 25 signals between two snapshots could drop the oldest from the read. They are still stored from earlier snapshots, so this is a risk only if snapshots stall.
5. **Commander exposure.** `list_agent_trades` on the proxy allowlist also exposes it to the Commander. It is a like-for-like replacement of `list_trade_outcomes`, but say if you want it limited to the read client (`PHASE0_READS`) instead.
6. **Ack order.** Either order clears cleanly (see Bookkeeping). If a platform version move lands after the ack under Phase A and before the backfill tick, D7c refuses it as "never recorded" until one more ack.
7. **A2 depends on unmeasured fields.** The open-order branch depends on the unmeasured `symbol` (and `orderType` is not used). The first live queued TIGHTEN should be read back by hand to confirm which branch corroborated it.

### Phase B review fixes

The review verdict was MERGE AFTER FIXES. There is one commit per fix, on top of 3ff88f3.

| Commit | Fix |
|---|---|
| 94c7693 | **1 (required).** A closed trade's PASS now counts as EXECUTED, and a stored EXECUTED is never downgraded. |
| a015e1d | **2.** An `SL_PLACED` at the requested stop also corroborates a TIGHTEN. |
| b0ccb3a | **3.** `stop_committed` requires the answer's `decisionId` to equal the one sent. |

**Fix 1: a closed trade reads PASS.**
- **Mapping.** `TERMINAL_AS_ENTRY_STATUS` is now `{OPEN: EXECUTED, PASS: EXECUTED}`. The evidence is the 09-18 review, section 3: the DOGE log moved OPEN → PASS when its position closed.
- **No downgrade.** `_store_entries` never moves a stored EXECUTED to another status. The rejection reason is written only on a row stored FAILED. `_reasons_read` treats a stored EXECUTED as settled, so a stray later status triggers no detail read.
- **Tests:**
  - OPEN then PASS: the streak ends at the trade, `covering()` misses the old acknowledged alert, and a new alert is filed whose first decision is d5;
  - a trade first served as PASS resolves the open alert as "entries executing again";
  - six later statuses each fail to downgrade a stored EXECUTED;
  - the 24 h count keeps the closed trade as filled;
  - a non-ENTER PASS is dropped.

**PASS on non-ENTER rows.** Nothing stored says what PASS means on a SKIP or GATED row.
- In the 129.0.0 schemas, PASS appears only as a bare enum member, with no description (`get_signal_log`'s `terminalStatus`, and the facet enums of the public signal and trade reads).
- README lines 41-346 do not mention it.
- The stored `entry_decisions` rows came from `list_entry_decisions {decision: ENTER}`, so they are ENTER rows only.
- No fixture holds a SKIP or GATED log.

The fix does not depend on that answer. `normalize_signal_entries` drops every row whose `decision` is not ENTER before mapping, so a non-ENTER PASS is never stored or counted as filled. A test pins this.

**Fix 2: `SL_PLACED` corroborates.**
- `SL_PLACED` comes from the 129.0.0 schema arm `{kind, createdAt, price}`. One at or after `performed_at`, at the requested price, now corroborates the same way `SL_REPLACED` (`toPrice`) does.
- It counts on both paths: the equal read-back path and the moved-on path.
- **Tests** cover two cases where it settles DONE: the stop reads back equal, or the stop has already moved on. They also cover three cases that do not corroborate: another price, a null price, and an event from before the send.

**Fix 3: `stop_committed` checks the decision.**
- `stop_committed` now takes `decision_id`, and verify passes the row's `params.decisionId`.
- An absent `decisionId` is never committed (the 129.0.0 output schema requires it). So is a different one, or a case-changed one, and so is a row with no sent id.
- **Tests** cover the unit cases and a verify-level case. In that case, a committed answer about another decision waits for corroboration, and the same answer with the right id is DONE.

**Suite.** The full run on b0ccb3a gave **5066 passed, 5 skipped, 1 error** (618 s). The error was `WinError 10055` (socket buffer exhaustion) in `test_contract_129.py::test_the_read_client_refuses_a_removed_tool_before_the_wire[get_agent_fund_allocation]`. That file then passed on its own, 29 of 29. A second `WinError 10055` hit `test_verify.py` once during the affected-file runs and passed on rerun. Both are host socket exhaustion, not the code.
