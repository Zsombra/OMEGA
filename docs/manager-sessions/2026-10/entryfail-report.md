# Entry-fail watch: report (2026-10-19)

Worktree `C:/tmp-bgm-entryfail`, branch `feat/entry-fail-watch`, from main `796f050`. Not merged, pushed or deployed.
No BattleGrid call was made. The only live reads were read-only psql queries on `system_state`, for shapes.

## Commits

| sha | what |
|---|---|
| `b9855c0` | The reads and the storage: one `list_entry_decisions` per deployed agent, at most one `get_signal_log` per agent per snapshot, the `entry_decisions` table, `agents.entry_read_status`, the read sets, `MANAGER_TOOLS` |
| `2996706` | The rule `manager/inventory/entry_failures.py` (AGENT_ENTRIES_FAILING): auto-resolve, ack scope, `GET /api/entry-failures`, the triage-poll exclusion, the daily report, the tests |
| `9b317d0` | `hermes/scripts/battlegrid_halt_watch.py` generalised: the same job also posts each new AGENT_ENTRIES_FAILING alert once |
| `cb51097` | Docs: Commander `SOUL.md`, `hermes/skills/battlegrid-manager/SKILL.md`, the runbook entry |
| `8df6788` | Hardening: a decision row without a `decision` field reads UNDETERMINED |

Each commit ends with the Co-Authored-By line.

## What was built

### 1. The reads (`manager/inventory/snapshot.py`, `_read_entries`)

- **The list read.** One `list_entry_decisions {agentId, decision: "ENTER", limit: 10}` per DEPLOYED agent. The set
  is the halt watch's `deployed`: enabled Radar slots plus Arena deployments that may play, in the agent list, capped at
  `BUDGET_MAX_READS` (10).
- **The detail read.** The output schema of the list (104.1.0, the newest stored for this tool) carries `status` but no
  failure reason. So at most ONE `get_signal_log {agentId, logId}` runs per agent per snapshot, for the newest FAILED
  decision whose reason is not yet stored as read OK. It reads `log.pipeline.execution.failureReason` and
  `executionMessage`, which match the live 120.2.0 schema in `manager_schemas`.
  - A long streak fills in its older reasons one per snapshot.
  - The steady state is zero detail reads.
  - A failed detail read is retried on a later snapshot.
- **Failures fail closed.** A failed list read, or an unreadable page, sets `entry_read_status` UNDETERMINED and stores
  no row. An unreadable page is: no `entries` list, a row with no `decision`, or an ENTER row without
  `id`/`status`/`createdAt`. Each read goes into `snapshot.reads` under `list_entry_decisions:<agent>` and
  `get_signal_log:<agent>`, so the inventory report counts them and the heartbeat sees a failure.
- **Read sets (`manager/platform/reads.py`).**
  - `list_entry_decisions` is declared `None`. That is fail-closed, as `get_agent_budget` is: every unsafe output
    change blocks.
  - `get_signal_log` gains `/log/pipeline/execution/failureReason` and `/log/pipeline/execution/executionMessage`.
    Both are checked served and required at 119 by the existing test.
- **`MANAGER_TOOLS`.** `list_entry_decisions` joined it (`manager/platform/watch.py`).

### 2. Storage: why a table

The new table is `entry_decisions`, keyed by the platform's decision id (unique). Each row has the agent, the signal
log id, the coin, the direction, the status, `created_at`, the first-seen and last-seen snapshot ids, and the cached
failure reason, message and read status. One new column, `agents.entry_read_status`, holds the per-snapshot read
outcome.

- **Why a table and not snapshot columns.** The streak must keep a STABLE first decision id, so that there is "one
  alert per (agent, first decision of the streak)".
  - The snapshot sees only the newest 10 rows. On a 30-failure streak, the oldest row visible slides with every new
    failure, so per-snapshot storage would give a new "first" id, and a new alert, each time.
  - The table keeps the history, and one row per decision is also the natural cache key for "read the reason once".
  - Status is updated in place, for example PENDING to EXECUTED.
- **Growth.** The table is not pruned; it grows by the deployed agents' decision rate. Retention decision 11 covers
  only the gate blocks, scans and allocations.

### 3. The rule (`manager/inventory/entry_failures.py`, run after each snapshot from `job_snapshot`)

**The streak.** The agent's stored ENTER decisions, newest first:

- FAILED counts.
- EXECUTED ends it.
- PENDING, EXPIRED, CANCELLED and a gate-overridden SKIPPED neither count nor end it.
- A FAILED decision whose stored reason is AGENT_HALTED does not count, because a halted agent's refusals are the halt
  watch's to report.

**When it fires.** All of these must hold:

- the snapshot read the agent's decisions OK;
- its budget read is OK and the agent is not halted (an unread halt state files nothing);
- the streak is at least `ENTRY_FAIL_STREAK` = 3;
- the newest failure is under 24 h old;
- no alert exists yet for (agent, `firstDecisionId`), acknowledged or not.

**What it files.** An Alert of kind `AGENT_ENTRIES_FAILING`, plus the ledger event `entry_fail.alerted`. The detail
carries the agent name, the streak length, the first and newest decision ids and times, the newest reason and
`executionMessage`, counts per reason (`UNREAD` for reasons not read yet), `maxConcurrentExposureUsd`,
`positionSizePresets` and a note.

**How it resolves.** If the agent was read OK and its stored decisions show an EXECUTED decision created after the
streak's first, the open alert is acknowledged by the system with "entries executing again: ...". The ledger event is
`entry_fail.resolved`. An unread agent resolves nothing.

**Acknowledging.** The scope is the alert id only (`manager/triage/review.py`), the same as the halt alert. A new streak
gets a new `firstDecisionId` and therefore a new alert.

### 4. Visibility

- **Hermes post.** `hermes/scripts/battlegrid_halt_watch.py` now reads `/api/halts` and then `/api/entry-failures`.
  - One `posted` list serves both kinds, because alert ids are unique.
  - The post says what failed and why, with the `executionMessage` quoted.
  - It says the Commander cannot change risk settings, and that the fix is the user's (presets, exposure cap, policy)
    or `manager alerts ack <id>`.
  - The two reads are independent. An older manager answers 404 on the new route; that is logged, and the halts still
    post. If nothing is readable, nothing is posted and the state is kept.
  - There is no new cron job.
- **Daily report.**
  - NOTABLE gains `entry_fail.alerted` and `entry_fail.resolved`.
  - A new `## Failing entries` section has a standing line per open alert, quoting the message, and an UNDETERMINED
    line per agent whose decision read failed.
- **Inventory report.** The header now reads "entry decisions: N of M deployed agents OK (failure reasons: x of y OK)".
- **Triage poll.** It leaves the alert out, as it does AGENT_HALTED_IDLE.

### 5. Docs

- One paragraph each in `hermes/commander/SOUL.md` and `hermes/skills/battlegrid-manager/SKILL.md`.
- The runbook entry "Failing entries: the entry-fail watch" in `docs/phase-0/runbook.md`, after the halt-watch entry.

## Tests

The new file is `tests/inventory/test_entry_failures.py` (20 tests), and `tests/hermes/test_halt_watch.py` has 4 new
ones. They cover:

- **Normalising.** Only ENTER rows are kept. A half-read page is refused, and so is a row with its verdict renamed. A
  null pipeline reads as no reason.
- **The reads.** There is one list read per deployed agent with the exact arguments. A non-deployed agent is not read.
  One detail read goes to the newest FAILED decision; the older reasons backfill one per snapshot, and then none are
  read. A status update lands on the same row.
- **Fail-closed paths.**
  - A failed list read stores UNDETERMINED, files no alert, and shows in the daily report.
  - An unreadable page reads UNDETERMINED and stores no row.
  - A failed read after an alert neither files nor resolves.
  - A failed detail read still files, with the reason unread and the count shown as `UNREAD`, and is retried on the
    next snapshot.
- **The rule.**
  - It fires on 3 FAILED, and the detail carries the reason, the message, the cap and the presets.
  - The same streak does not alert again.
  - The first id stays stable when the page slides.
  - Two failures, or a streak whose newest is older than 24 h, file nothing.
  - EXPIRED, CANCELLED or PENDING in the middle does not break the streak.
  - An EXECUTED inside the window breaks it.
  - An EXECUTED auto-resolves the open alert, and a new streak re-alerts.
  - An ack silences only that alert, not another agent's. The silence holds while the streak grows, and a new streak
    after an EXECUTED alerts.
  - A halted agent files no alert, nor does an unread halt state.
  - AGENT_HALTED failures are not counted.
- **Visibility.** The reports and the view are covered, the triage poll leaves the alert out, and
  `/api/entry-failures` is served and covered by the 401/403 check.
- **Hermes.** A new entry-fail alert is posted once with the quoted message and whose fix it is. Both kinds post in
  one run, and an acknowledged one is recorded without being posted. Either route being unreadable still lets the other
  post. A bare alert posts without inventing values.

**Existing tests adjusted** to the new reads:

- `no_entries()` was added in `tests/inventory/arena_support.py` and wired where every read must be OK: report,
  snapshot, app, jobs (the heartbeat is now "30/30 reads OK").
- The report header strings were updated.
- The MANAGER_TOOLS counts went 53 to 54, in test_watch and test_watch_schemas.
- The 104.0.0 schema-size baseline was re-measured: 52 tools, 490,333 bytes (+7,017).
- The halt-watch test `_run` now routes by URL.

**Full suite:** 4549 passed, 5 skipped, 0 failed, in 7 min 44 s.

- It ran once, in the background, without `-x`, at `cb51097`.
- The baseline before the change was 4525 + 5 skipped, so the 24 new tests account for the difference.
- `8df6788`, the one-line hardening that came after it, was verified with `tests/inventory/test_entry_failures.py`
  (20 passed).

## Concerns

1. **The brief's schema source does not hold this tool.** `manager_schemas` holds only the 51 `MANAGER_TOOLS` schemas
   at 120.2.0, not every tool, and `surface_tools` stores no output schemas. `list_entry_decisions` was therefore not
   in it.
   - Its row shape comes from the newest stored output schema, 104.1.0 (`tests/fixtures/2026-10-08-surface-104.1.0`).
   - The test rows are INVENTED from that schema.
   - The `get_signal_log` execution arm IS from live 120.2.0.
   - Mitigation: an unreadable or renamed shape reads UNDETERMINED, never "fine".
   - Worth a single read-only capture of a live page before trusting it. VWAP Sentinel's 30 FAILED rows would confirm
     both `status` and the `signalLogId` -> `get_signal_log` path.
2. **One `manager contract ack` is needed after deploy.** `list_entry_decisions` is now in `MANAGER_TOOLS` but not in
   the acknowledged baseline, so D7c will refuse the next platform move as "never recorded" until that ack. This is the
   same step the Arena reads needed, and it is noted in the runbook.
3. **The Hermes script must be re-copied.** It needs `python hermes/install_commander.py --halt-watch`, which copies a
   differing script and keeps the existing job. Until then, the deployed job posts halts only.
4. **The first snapshot after deploy will alert at once for VWAP Sentinel 4h,** provided it is still deployed, not
   halted and still failing. Only the newest reason is read on that first snapshot, so the counts show `UNREAD` for the
   rest. The alert text carries the newest message either way.
5. **Reads per snapshot.** Up to 1 list + 1 detail per deployed agent; 3 deployed today, so +3..6 reads per snapshot.
   A failed detail or list read now marks the snapshot heartbeat not-OK, like any other read.
6. **Limits of the rule.**
   - `entry_decisions` is never pruned.
   - An alert for an agent that is no longer deployed stays open (nothing reads it, so nothing resolves it). It shows in
     the daily report until acknowledged.
7. **Line endings.** Some files I edited carry CRLF in the working copy only. Git normalises them to LF on commit, and
   the commits are clean.

## Fix round 1 (2026-10-19)

The independent review said FIX FIRST. All five findings are fixed in the same worktree and branch. Nothing was merged,
pushed or deployed, and no BattleGrid call was made. This section supersedes the earlier text wherever the two differ:
concerns 2, 4, 5 and 6 above are replaced by the behaviour below.

| sha | finding |
|---|---|
| `5d12861` | 1 (MEDIUM): an unreadable signal log no longer stalls the watch; watch reads are kept out of the heartbeat |
| `3471fb8` | 2 (MEDIUM), 3 (LOW), 5 (LOW): no alert on unread or pre-halt refusals; "gate or exchange" wording; auto-resolve and join bounds |
| `248828f` | 4 (LOW): a declared read set for `list_entry_decisions`; the contract-ack note corrected |

### 1. One unreadable signal log stalls the watch

- **Attempt counting.** `entry_decisions.reason_attempts` counts the failed `get_signal_log` reads of a decision. That
  decision is marked `UNREADABLE` (permanent) in two cases:
  - after `ENTRY_DETAIL_MAX_ATTEMPTS` = 3 failed reads;
  - at once when the refusal names NOT_FOUND (the platform's code, or the word in its message), or when the answer is
    `{"log": null}`.
- **The backfill moves on.** `UNREADABLE` counts as settled, so the next snapshot reads the next unread decision. A
  failed retry never overwrites a reason already read OK or marked `UNREADABLE`.
- **The heartbeat.** `job_snapshot` now computes the snapshot heartbeat's `ok`, and the tape-symbols gate, from the core
  reads only. The watch-only keys are `snapshot.WATCH_READ_PREFIXES`: `get_agent_budget:`, `list_entry_decisions:` and
  `get_signal_log:`.
  - Those keys stay in `reads` and in the `snapshot.taken` event's `undetermined`.
  - The note names them as "watch reads only: ...".
- **Tests:**
  - 3 attempts, then `UNREADABLE`, and the backfill moves to log2 and then log1. The alert then files with
    `UNREADABLE` in its counts.
  - NOT_FOUND by message, NOT_FOUND by code, and `log: null` are each given up at once (parametrized).
  - A retry never overwrites a settled reason.
  - Heartbeat: every watch read failing leaves the beat OK and the refresh called; a core read failing still turns it
    red.

### 2. False alert right after a resume

- **Settled reasons only.** The rule fires only when the `ENTRY_FAIL_STREAK` newest counted failures all have their
  reason settled: read OK (AGENT_HALTED ones are never in the streak), or `UNREADABLE`, which counts as a failure of
  unknown reason. An unread reason waits.
- **The halt boundary.** A FAILED decision created at or before the agent's latest known `haltedAt` never counts. The
  `haltedAt` is the newest any stored snapshot read.
- **Streak identity is now by instant, not by decision id.** The old key was (agent, first decision id). A backfill that
  read old refusals as AGENT_HALTED would drop them and move the first id, which files a second alert. The key is now:
  no alert of the agent was filed at or after the streak's first decision (`covering`). It holds because:
  - a backfill only removes rows from a streak, so its first decision moves later, but stays before the alert;
  - a genuinely new streak (after an EXECUTED, a halt, a redeploy, or a 24 h silence) starts after every earlier alert;
  - acknowledging still silences that streak only.
- **Tests:**
  - Halted, then resumed with 4 unread AGENT_HALTED refusals: no alert over 5 snapshots.
  - The same 4 refusals plus 3 real failures: exactly one alert over 8 snapshots, even after the backfill reaches the
    refusals and moves the first decision.
  - Failures made before the latest halt: never counted.
  - An unread reason waits, and a failed detail read is retried.
  - Every earlier rule test now runs the 3 snapshots the backfill needs (`settle`).

### 3. Wording

- **"Refused (gate or exchange)".** The alert note, the daily report's standing line and the Hermes post now say
  "refused (gate or exchange)", not "the platform refused the order".
- **What gets named.** They give the reason code and the quoted `executionMessage` only when those were read.
  `UNREADABLE` says the signal log could not be read, and "no reason code served" covers a read with no code.
- The SOUL and SKILL paragraphs were reworded to match.
- **Tests:** the Hermes post wording, both read and `UNREADABLE`; the alert note; the daily line.

### 4. Read sets

- **`list_entry_decisions`** now has a declared set instead of None:
  `/entries[]/{id, decision, status, createdAt, signalLogId, coinTicker, direction}`.
- **`/entries` itself is deliberately NOT declared.**
  - This departs from the review's list.
  - In `reads.overlaps`, a declared root makes every change beneath it "read". So declaring `/entries` would make any
    row-field change block writes, which is what the fix is meant to stop.
  - Removing or retyping `/entries` still blocks, because that change contains every declared path.
- **`get_signal_log` was not None.** It already held `/log/pipeline/execution/failureReason` and `executionMessage`.
  - I did not add `execution.status`: the watch does not read it, and the registry rule is to declare only what is read.
  - A `log: null` answer needs no path: it is a served null, which `missing_paths` never counts as absent.
- **The served-and-required test** checks the new set against the tool's newest stored schema, 104.1.0. The 119.0.0
  capture predates the tool's entry, and the coordinator verified the live 120.2.0 row carries the same fields.
- **The runbook and the `watch.py` comment were corrected.** An ack is needed only if D7c refuses a move as "never
  recorded", and only AFTER the first watch run post-deploy has recorded the tool in `manager_schemas`.

### 5. Auto-resolve and the join bounds

- **New resolutions.** An open alert now also resolves in two more cases:
  - **No longer deployed.** The agent is in no enabled Radar slot and no unpaused Arena deployment, on a snapshot whose
    `list_intelligence_agents`, `list_radar_deployments` and `list_deployment_policies` reads were all OK. An unread
    roster resolves nothing.
  - **No failure in 24 h.** The agent was read OK and shows no counted failure in the last 24 h.
- **Deployment boundary.** A FAILED decision made before the agent's current deployment never joins a streak.
  - The deployment start is `deployed_since`: the latest snapshot in which the watch read some agent's decisions but
    not this one's.
  - When no such snapshot exists, the join is capped at 72 h (`ENTRY_FAIL_JOIN_CAP_S`).
- **The 24 h silence rule (added).** A silence of 24 h or more between two counted failures also ends a streak, so the
  stale resolution and a later re-alert agree.
- **Tests:**
  - No longer deployed resolves; a snapshot whose Radar read failed does not.
  - A day without failures resolves.
  - Failures older than a redeploy never alert.
  - With no deployment start known, the 72 h cap applies.
  - A 24 h silence ends the streak.

### Suite

The affected files passed: test_entry_failures (33), test_halt_watch (14), test_jobs, test_reads, test_watch,
test_watch_schemas, test_snapshot, test_report, test_halts and test_app, 328 together.

**Full suite:** 4565 passed, 5 skipped, 0 failed, in 9 min 10 s. It ran once, in the background, without `-x`, at
`248828f`. The +16 tests are 13 in test_entry_failures, 1 hermes, 1 jobs and 1 read-set parameter.

### Concerns after fix round 1

1. **The first VWAP Sentinel alert comes later.** It needs about 3 snapshots (about 15 min) after deploy, because the
   three newest reasons must be read first. After that, the older reasons backfill one per snapshot.
2. **`deployed_since` is the manager's own observation.**
   - An agent missing entirely from a watched snapshot (not listed at all) is not seen as a gap.
   - An agent past the 10-read cap is seen as undeployed.
   - With 3 deployed agents today, neither applies.
   - Snapshots taken before this ships carry no decision reads, so the 72 h cap governs history.
3. **Clock assumption.** The streak identity compares the manager's alert time with the platform's `createdAt`. It
   holds for any clock skew smaller than the time between a streak's first failure and its alert, because the alert
   needs three failures with reasons read first.
4. **Commits were verified at the branch head only.** `5d12861` and `3471fb8` were not suite-run on their own.
5. **Unchanged from round 1:**
   - the Hermes script must be re-copied with `install_commander.py --halt-watch`;
   - `entry_decisions` is never pruned;
   - the CRLF note on working-copy line endings still applies.
