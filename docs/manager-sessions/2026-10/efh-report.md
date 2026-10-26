# Entry-fail watch hardening (battlegrid-manager, branch fix/entry-fail-hardening)

Worktree `C:/tmp-bgm-efh`, from main `c741bd6`. Not merged, not pushed, not deployed. No BattleGrid call, no Docker / .env / Hermes edit.

## Commits

| commit | finding |
|---|---|
| `0735e8a` | 1. NOT_FOUND by code only, never on TRANSPORT |
| `0b3fafc` | 2. FAILED with no signalLogId stored UNREADABLE |
| `90f6b25` | 3. list pages through the read-set check; unknown statuses recorded |
| `3d7eea3` | 4. bounded and indexed history reads; boundary unchanged |

## 1. `_not_found` (manager/inventory/snapshot.py)

Now `error.kind is not Kind.TRANSPORT and error.code == "NOT_FOUND"`. `PlatformError.code` is the platform's own code: the read client sets it from the refusal body's `code` (`client.parse_call_result`, TOOL_ERROR). Message text is no longer matched.

Tests:
- The give-up-at-once parametrisation now covers a TOOL_ERROR or RPC error with `code="NOT_FOUND"`, and `log: null`. The message-only case was removed.
- New: "Session not found" (TRANSPORT), TRANSPORT that also carries `code=NOT_FOUND`, "NOT_FOUND" only in a TOOL_ERROR message, and HTTP 404. Each counts one attempt, stays UNDETERMINED and is retried on the next snapshot.
- Unit test of `_not_found`.

## 2. FAILED with no signalLogId (`_store_entries`)

On every upsert, a row served FAILED with no `signalLogId` is set to `reason_read_status = "UNREADABLE"` unless its reason is already settled. "Settled" means OK or UNREADABLE, and a settled reason is never overwritten. A PENDING row with no log waits; it becomes UNREADABLE once it is served FAILED.

Tests:
- The newest of three failures has no log. It is UNREADABLE with 0 attempts, and the alert fires with reasonCounts `{BELOW_EXCHANGE_MINIMUM: 2, UNREADABLE: 1}`.
- PENDING then FAILED, and a settled OK reason that survives.

The `EntryDecisionRow` docstring was updated.

## 3. Read-set check and unknown statuses

- `_entry_read_set_failure` runs `reads.missing_paths("list_entry_decisions", page)` on each page after it normalises. If a declared path is missing, the agent reads UNDETERMINED: `error = "PARSE: declared read paths absent ..."`, `missingPaths` is recorded on the read, and no row is stored. If the check itself raises, the agent also reads UNDETERMINED ("read-set check failed"). Neither case ever reads as "fine".
- After the snapshot is stored, every served page also goes through `check_read(..., "list_entry_decisions", ...)`, as the other snapshot reads do. That files the day's READ_PATH_MISSING alert.
- `ENTRY_STATUSES = (EXECUTED, FAILED, EXPIRED, CANCELLED, PENDING, SKIPPED)`. A test checks this against the `entries[].status` enum of the stored 104.1.0 output schema.
  - Any other served value logs a WARNING and is recorded as `unknownStatuses` on the read.
  - The daily report's "Failing entries" section names it, e.g. "served ENTER status(es) REJECTED the entry-fail watch does not know".
  - The rule still passes such rows over, as before.

Tests:
- A page whose rows lack `direction`: UNDETERMINED, `missingPaths`, no rows stored, no detail read, one READ_PATH_MISSING alert for the tool over three snapshots.
- A monkeypatched check that raises: UNDETERMINED.
- An unknown status: the log line, the read field and the daily-report line.

## 4. Bounded, indexed history reads (manager/inventory/entry_failures.py)

- **`latest_halted_at(..., since=)`** scans only snapshots whose id is at least the first snapshot taken at or after `since`.
  - `join_boundary` passes the base less `HALT_CLOCK_SKEW_S` (1 h). The base is the deployment start, or taken − 72 h when that is not known.
  - A halt at or before the base cannot move `max(base, halt)`. A halt is only read by a snapshot taken after it. So the boundary is the same as before for every history.
  - When no deployment start is known, the window is the 72 h cap plus 1 h.
- **`deployed_since`** gives the same answer as before.
  - It reads the agent's unread rows newest-first, with `EXISTS` watched-in-the-same-snapshot and `LIMIT 1`.
  - It starts from the first watched snapshot, found by two index seeks. No earlier snapshot can be a gap.
  - The old version had an `IN (every watched snapshot)` subquery over the whole table.
- **Three `agents` indexes**, declared in `AgentRow.__table_args__` and in `db/session._ADDED_INDEXES`:
  - `(agent_id, snapshot_id)`
  - `(agent_id, entry_read_status, snapshot_id)`
  - `(entry_read_status, snapshot_id)`

Tests:
- A property test over 6 seeded random 240-snapshot histories: `deployed_since` and `join_boundary` equal the 65f6334 code, copied into the test as the reference, on every snapshot. I checked that it catches a mutation: tightening the halt bound by 12 h fails 6 of 6.
- A deterministic case: a halt older than the cap is not scanned and changes nothing; a recent halt is seen.
- An index-existence and migration test.

## Suite

Full suite, run once from `C:/tmp-bgm-efh` on `3d7eea3` without `-x`: **4583 passed, 5 skipped, 4 warnings in 562.62 s.** The four warnings were already there before this branch: SyntaxWarnings in tests/review/test_take.py and a starlette deprecation.

The affected files also passed when run on their own: tests/inventory, tests/db and tests/platform/test_reads.py.

## Concerns

1. **Already in the code before this branch, not fixed here: a duplicate alert on streaks over 72 h when no deployment start is known.** VWAP Sentinel was deployed before the watch, so it is in this case.
   - The join boundary is taken − 72 h, and it slides forward.
   - A streak's first decision is therefore re-chosen each snapshot. Once it passes the alert's `at`, `covering` finds no alert and a second one is filed.
   - This happens about 72 h into an unbroken, unacknowledged-or-acknowledged streak.
   - Bounding `deployed_since` to 72 h, as the brief suggested, would have spread this to every agent. That is why finding 4 bounds the reads exactly instead of truncating them.
2. **The three new indexes are created with a plain `CREATE INDEX`** (the existing pattern) on the live `agents` table at the next service start. That takes a SHARE lock, which blocks snapshot inserts while the indexes build. Expect seconds, but not measured.
3. **An unknown status is recorded, not fail-closed.** The agent still reads OK and those rows are passed over. A renamed FAILED would hide failures, but it now shows in the log, the read record and the daily report.
4. **The read-set gate is fail-closed on all seven declared row fields.** If the platform drops a display-only field such as `direction` or `coinTicker`, every agent reads UNDETERMINED until `READ_SETS` is updated, and READ_PATH_MISSING says which path is missing.

## Round 2

Commits:
- `fbc8227` — read-set narrowing and the runbook note.
- `862c7bd` — the settings label.

Affected tests: tests/inventory, tests/hermes/test_halt_watch.py and tests/platform/{test_reads,test_watch,test_watch_schemas}.py all pass, 280 + 194 across two runs. The full suite was not re-run.

1. **The read-set gate covers only the five fields the rule needs.**
   - `READ_SETS["list_entry_decisions"]` is now `/entries[]/id`, `decision`, `status`, `createdAt` and `signalLogId`. The snapshot gate and the contract watch both use this one set.
   - `coinTicker` and `direction` are still read, but only as optional display fields and they are not declared. If they are absent, the alert leaves them out. They never make an agent UNDETERMINED, never file READ_PATH_MISSING, and a change to them never blocks writes.
   - Tests:
     - A page without `direction` or `coinTicker` reads OK and files its alert with `newestCoin` and `newestDirection` null.
     - The UNDETERMINED test now drops `signalLogId` instead.
   - The runbook's "seven row fields" now reads five.
2. **The settings are labelled as current, not as the ones the failures happened under.**
   - The entry-fail post in `hermes/scripts/battlegrid_halt_watch.py` now says: "Its current settings (as of this snapshot): exposure cap $X, presets a/b/c (small/medium/large, % of headroom at risk) - snapshot N." It adds that these were read when the alert was filed and that the failures may predate a change to them. The old "Its risk settings" wording is gone.
   - The daily-report line carries the same label. The values come from the latest snapshot's agent row, falling back to the alert's own snapshot, and the line names the snapshot id.
   - Tests:
     - test_halt_watch checks the label, "snapshot 412" and the "may predate" wording.
     - A new daily test changes the latest snapshot's config to 18 / 3/4/4.5 and checks that the line shows those values.
3. **The 72 h re-alert is accepted.** One sentence was added to the runbook's entry-fail section: when the deployment start is not known, a streak longer than 72 h re-alerts.
