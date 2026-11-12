# Report: agent status - the manager knows every agent's status and reports every change (2026-10-19)

Repo `battlegrid-manager`, worktree `C:/tmp-bgm-agentstatus`, branch `feat/agent-status` from main `d76e53e`.
Not merged, pushed or deployed. No BattleGrid call made; read-only psql only (shapes of `agents`, `radar_policies`,
`entry_decisions`, `snapshots`).

## Commits

- `0d1180e` Agent status: one status per agent per snapshot, debounced transitions, AGENT_STATUS_CHANGED
- `97e4d26` Agent status: GET /api/agents/status, /api/agents/status-changes and the Commander's manager_agent_status
- `dd06fae` manager agents status, and agents list --archived no longer overflows the 150k cap
- `7bf4def` Halt watch posts each AGENT_STATUS_CHANGED once; Commander docs on agent status

## Suite

Full suite, one background run, no -x, on the final commit 7bf4def: **4673 passed, 5 skipped, 0 failed** (4 warnings, pre-existing; 574.72 s).

## What was built

### 1. One status per agent per snapshot (`manager/inventory/agent_status.py`, table `agent_statuses`)

`derive_statuses(s, snapshot_id, now)` runs in `job_snapshot` right after the halt and entry-fail watches (so their
open alerts are current). It is idempotent per snapshot. It writes one `agent_statuses` row per agent. A new table,
so `create_all` adds it with no migration. Each row holds `observed` (this snapshot's reading), `baseline` (the last
confirmed value of each comparable part) and `summary`. Agents covered: every agent in the snapshot's agent list,
plus every agent the previous status carried that the list no longer does. Parts:

- **lifecycle:** ACTIVE, or NOT_LISTED (gone from `list_intelligence_agents` since the last status), or UNDETERMINED
  (the agent list read failed). The snapshot reads ACTIVE agents only. ARCHIVED cannot be told apart from deleted
  without the both-statuses read, and that read is what overflows the cap. So it says "no longer listed (archived?)".
  A NOT_LISTED agent gets one row, then none until it is listed again. It stays in the view and is compared for 7 days.
- **binding:** strategy name, id and revision, binding state, and the model.
- **run:** from `get_agent_budget`. The state is HALTED (reason, since), BLOCKED (reason), the served runStatus, NOT_READ
  or UNDETERMINED. **Choice:** the budget read now covers every ACTIVE agent. Deployed agents come first, then the
  rest, with a total cap of `BUDGET_MAX_READS` = 10 (`snapshot.budget_read_ids`). The account held 2 ACTIVE agents on
  10-19, so the cost is at most 2 reads per snapshot (1 more than before). Agents past the cap read "run not read".
  The halt watch is unchanged in scope: `check_halts` now filters to the snapshot's deployed set, so an undeployed
  halted agent shows in its status and never files AGENT_HALTED_IDLE (new test). The `entry_decisions` reads stay
  deployed-only.
- **deployment:** each Radar coin the agent is in a slot of: enabled or paused, section, reason, blocked reason,
  timeframe. Also each Arena deployment.
- **activity:** the newest stored ENTER decision (status; failure reason and message when read; instant), with
  "(as last read)" when this snapshot did not read it. Also open positions, and the open AGENT_HALTED_IDLE /
  AGENT_ENTRIES_FAILING alert ids.
- **summary line**, matching the brief:
  - `VWAP Sentinel 4h: ACTIVE, running, on 11 coins (11 scanning); last entry FAILED BELOW_EXCHANGE_MINIMUM 10-18 16:01Z`
  - `VWAP Sentinel: ACTIVE, running, on 6 coins, ALL PAUSED (policy disabled) - doing nothing`
  - `Trend Continuation: no longer listed (archived?) since 10-19 06:10Z`

  The "since" time is the last snapshot that listed the agent.

**Fail closed:** a failed read makes that part UNDETERMINED in the summary ("run UNDETERMINED", "Radar UNDETERMINED",
"positions UNDETERMINED", "entries UNDETERMINED"). It is never compared and never becomes a baseline value. An unread
agent list never yields NOT_LISTED. A view whose newest status is older than the newest snapshot says so.

### 2. Transitions

- **Compared parts:** lifecycle, run value, the coin map (coin -> enabled | paused), doingNothing (no enabled coin and
  no Arena deployment that may play), and the entry outcome (the newest EXECUTED or FAILED decision, only when this
  snapshot read the decisions).
- **Debounce choice:** lifecycle changes are reported at once. Every other part must be seen on 2 consecutive
  statuses before it replaces the baseline, so a one-snapshot blip is never reported (tested). An unread part never
  moves the baseline. A part first read after being unknown is established silently. A new agent is reported once as
  "newly listed" and its coins become its baseline. SCANNING <-> IDLE section flips are not compared.
- **Ledger:** `agent.status_changed {agentName, changes, agent, from, to, at, snapshotId, alertId}`, one per agent per
  batch.
- **Alert:** ONE `AGENT_STATUS_CHANGED` per agent per batch. It is informational: no ack needed, and the system
  acknowledges it after 1 h (`AUTO_RESOLVED_NOTE`). It is excluded from the triage poll like the other two kinds. A
  user's ack scope is that alert only.
- **Standing condition:** at least one coin, all coins paused, no Arena deployment that may play, the positions read
  OK and none open, for at least 1 h (`allPausedSince` is carried row to row). It is listed under `## Agent status` in
  the daily report every day it lasts.

### 3. Visibility

- **CLI:** `manager agents status` prints a header and one summary line per agent, with a `[STANDING ...]` tag where it
  applies. `--agent ID|prefix|name` adds the detail lines. It reads only the database. Exit 1 when `--agent` matches
  nothing.
- **API:** `GET /api/agents/status[?agent=]` serves the full status. `GET /api/agents/status-changes` serves the last
  24 h of AGENT_STATUS_CHANGED alerts, each `informational: true`.
- **MCP:** a new native read-only tool `manager_agent_status`, so the Commander can read it. Native count 13 -> 14;
  test counts updated.
- **Hermes:** `battlegrid_halt_watch.py` reads `/api/agents/status-changes` as a third source and posts each alert
  once, through the shared `posted` list. Because these alerts auto-resolve, it posts one even when it is already
  acknowledged (`SOURCES` gained an `informational` flag). An unreadable route is logged and the other two kinds still
  post. No new cron job: the existing 5-minute job carries it.
- **Daily report:** a new `## Agent status` table (agent | summary line), then the standing lines. `agent.status_changed`
  was added to NOTABLE, so the day's transitions are listed under "Since". The payload puts the name and change texts
  first, because the report quotes the first 300 characters.
- **Commander docs:** one paragraph each in `hermes/commander/SOUL.md` and `hermes/skills/battlegrid-manager/SKILL.md`,
  plus a tool-table row. They say the Commander reads status and explains it, and that deployments and settings are
  the user's. These are the repo copies only; no installed profile was touched.
- **Plugin Fleet tab:** SKIPPED (optional). The API route is there for it.

### 4. `manager agents list --archived`

`list_intelligence_agents` takes only `statuses`, with no page or field argument (checked against the stored 119.0.0
schema). The fix is in `manager/actions/lifecycle_propose.roster_view`:

- It reads ACTIVE (`{}`, what the snapshot reads every 5 min) and ARCHIVED (`{statuses: [ARCHIVED]}`) separately.
- If the ARCHIVED list alone still fails, it narrows further: one `get_intelligence_agent` per agent id the manager's
  snapshots have seen that the ACTIVE list lacks, up to 40 reads. Each answer is a single agent, far under the cap.
  The output says it used this fallback and that an archived agent the manager never saw is not listed.
- With no known ids, or with any unread agent, the result is `archived: UNDETERMINED ...` and exit 1. It never shows
  "no archived agent".

## Tests

- `tests/inventory/test_agent_status.py` (19 tests):
  - the brief's three summary lines;
  - fail-closed reads (a failed budget/Radar/positions/entry read, and an unread agent list that never becomes
    NOT_LISTED);
  - lifecycle gone, listed again and newly listed;
  - run debounce, including a one-snapshot blip that is never reported;
  - coins added, removed, paused and resumed, doing nothing (all paused, or none left) and active again;
  - SCANNING/IDLE flips ignored;
  - entry outcome EXECUTED <-> FAILED, with PENDING passed over;
  - `advance` never moves on an unread part;
  - the alert: informational, auto-resolve, out of the triage poll, per-alert ack, idempotent per snapshot;
  - the CLI line format and details, the stale note, the standing condition (not at 55 min, yes at 60 min, not with a
    position), transitions in the daily report;
  - the budget read set and cap, and the MCP tool.
- `tests/inventory/test_halts.py`: an undeployed halted agent is read and never alerted. Updated: 9 budget reads (5
  deployed first) and the new wording.
- `tests/hermes/test_halt_watch.py`: a status change is posted once even when resolved, the `posted` list is shared
  with the other two kinds, and an unreadable status route still posts the others.
- `tests/commands/test_agents.py`: `--archived` uses two reads, the over-cap fallback reads one agent per known id,
  an unreadable archived list exits 1 as UNDETERMINED, and `agents status` lines, details and no platform call.
- `tests/api/test_app.py`: both routes need the token, and `/api/agents/status` serves and narrows.
- Updated counts and wording in `tests/inventory/test_report.py`, `tests/scheduler/test_jobs.py` (34 reads a snapshot
  in the 09-14 fixture: 9 budgets, not 5) and `tests/mcp/test_server.py` (+1 native tool).

## Concerns

1. **ARCHIVED vs deleted is not determined.** The snapshot reads ACTIVE only, so a vanished agent is "NOT_LISTED
   (archived?)". `manager agents list --archived` can confirm by hand.
2. **The ARCHIVE/ACTIVATE write path still reads `{statuses: [ACTIVE, ARCHIVED]}`.** Those are
   `lifecycle_propose.propose_user_lifecycle` and `lifecycle_describe` (`ROSTER_ARGS`), and they will hit the same
   150k cap: `manager agents archive|activate` is likely broken today. Out of this brief's scope, and on the write
   path, so I did not touch it. It needs the same split (ACTIVE for an archive, ARCHIVED or a per-id
   `get_intelligence_agent` for an activation, and slot usage from the ACTIVE read).
3. **More budget reads.** The budget read widened to every ACTIVE agent: +1 call per snapshot on today's 2-agent
   account, at most 10 in all. The snapshot heartbeat note counts change (e.g. "34/34 reads OK" on a 9-agent fleet).
   `halted_lines` in the daily report now also lists an undeployed halted agent, and its "none halted" line is
   reworded.
4. **Volume.** `agent_statuses` grows by about 1 row per agent per snapshot (about 600 a day at 2 agents), with JSON.
   No retention, consistent with decision 11 ("nothing else" is pruned).
5. **Timing.** An AGENT_STATUS_CHANGED for a non-lifecycle change arrives one snapshot (about 5 min) after it is first
   seen, because of the debounce.
6. **First run after deploy.** It establishes the baseline silently. Today's conditions (e.g. Trend Continuation
   already gone) are not alerted. They show in the status and the daily table.
7. **Not run live.** Not deployed or exercised against the live database: it needs a manager image rebuild and the
   Hermes script copied into the commander profile (`hermes/install_commander.py`), both the user's/deploy step.


## Fix round 1

The review verdict was SHIP with follow-ups. Same rules as before: no merge, push, deploy or BattleGrid call.

### Commits

- `4baf9a7` Agent status fix round 1: a mass drop from an OK agent list is debounced; coins keyed coin_id/timeframe; E402
- `9e0c982` ARCHIVE/ACTIVATE propose, describe and verify no longer read the over-cap combined roster

### What changed

1. **A mass drop from an OK agent list (MEDIUM).** `agent_status._suspects` applies when an OK list drops every agent
   listed before, or more than one at once. Those agents read `UNDETERMINED` for that snapshot, with
   `suspectNotListed` and a summary of "missing from the agent list: ...; reported if still missing next snapshot".
   They are reported NOT_LISTED only when the next snapshot still misses them, because a suspect already flagged is
   believed. An empty-list blip posts nothing: no "gone" and no "listed again". One agent vanishing from a list that
   still carries others is reported at once. When the only agent listed vanishes, that counts as "every one", so it is
   debounced too. `lastListedAt` carries through the UNDETERMINED snapshot, so "since" stays the last real listing.
2. **The `--archived` fallback and NOT_FOUND (LOW).** In the one-by-one fallback, `get_intelligence_agent` failing
   with the platform's `NOT_FOUND` code is now counted as deleted ("N no longer exist (NOT_FOUND: deleted)"), not as
   unread. The check is `roster.is_not_found`: the code only, never message text, and never for a TRANSPORT error. A
   deleted id no longer keeps the listing UNDETERMINED.
3. **Coin keys (LOW).** Radar coins are keyed `coin_id/timeframe` (`coin_key`). Each entry carries `ticker` and a
   display `label`, which is the ticker, plus the timeframe when two policies share it. Change texts use the label.
   Labels are carried row to row (`coinLabels`), so a removed coin is still named by its ticker. Tested with two
   policies of one ticker served in alternating order: no shift and no spurious change, and "APT 4h paused" is
   reported correctly.
4. **The write path (confirmed concern 1).** New `manager/actions/roster.locate_agent`. It is used by
   `lifecycle_propose` (ARCHIVE/ACTIVATE), `lifecycle_describe._agent_of` and `lifecycle_verify`, and replaces every
   `{statuses: [ACTIVE, ARCHIVED]}` read. It reads in order, stopping as soon as it has the answer:
   - `list_intelligence_agents {}`, the ACTIVE list. It also carries the account-level `slotUsage` (limit, used,
     remaining) that ACTIVATE's slot check needs.
   - `{statuses: [ARCHIVED]}`, only when the ACTIVE list does not carry the agent.
   - `get_intelligence_agent {agentId}`, only when the ARCHIVED list is unread too.

   What describe and verify actually use from the row: `id`, `status`, `revision`, `displayName`, `scope`,
   `capabilities.canArchive`, `tradingConfig`, `bindingState`, `strategyId`, `hasActiveAssignments`,
   `activeGameCount`, plus `slotUsage` for ACTIVATE. `get_intelligence_agent` serves every one of those (its 119.0.0
   output schema requires them all). Only `slotUsage` needs a list read, which is why the ACTIVE list is always read
   first.

   It stays fail-closed throughout:
   - An unread ACTIVE list, or an unread agent after both narrower reads, raises. Propose refuses ("the agent roster
     could not be read; nothing was proposed"). Describe raises `PlatformError`, so the row stays QUEUED. Verify notes
     "an unread roster settles nothing", re-raises, and `verify_one` returns unsettled, never DONE.
   - Only the NOT_FOUND code reads as "not among the account's ACTIVE and ARCHIVED agents".
   - `VERIFY_READS` for ARCHIVE/ACTIVATE now reserves the three possible reads.
   - `ROSTER_ARGS` stays in `kinds.py` as the documented full-fleet argument, which a schema test checks, but nothing
     reads with it any more.
5. **E402 (style nit).** `triage/views.py` and `triage/review.py` import `AGENT_STATUS_CHANGED` from
   `manager.inventory.agent_status`. There is no import cycle; checked by importing each module on its own.

### Tests

- **Agent status:** 5 new tests in `tests/inventory/test_agent_status.py`:
  - an empty OK list is debounced and a blip posts nothing;
  - two dropped at once are reported only on the next snapshot, once;
  - one of two vanishing is reported at once;
  - the only agent vanishing is debounced;
  - two policies of one ticker are keyed stably.

  Two existing tests were adjusted: a coin key now reads `mu/15m`, and the ack test drops two agents, which now
  confirms one snapshot later.
- **Propose:** 4 new tests in `tests/actions/test_lifecycle_propose.py`:
  - ARCHIVE proposes, with only the `{}` list read;
  - ACTIVATE proposes through the one-agent read when the ARCHIVED list is over the cap too;
  - ACTIVATE proposes from the ARCHIVED list;
  - NOT_FOUND refuses as not listed, while a transport "not found", or an unread ACTIVE list, refuses as unread.
    Nothing is proposed in any of these.
- **Describe:** 4 new tests in `tests/actions/test_lifecycle_describe.py`:
  - ARCHIVE describes over the cap;
  - ACTIVATE describes from the ARCHIVED list, with the ACTIVE list's slotUsage;
  - ACTIVATE through the one-agent read refuses on the slot limit;
  - an unread roster raises.
- **Verify:** 3 new tests in `tests/actions/test_lifecycle_verify.py`:
  - DONE from the ARCHIVED list;
  - DONE through the one-agent read;
  - an unread roster never settles.
- **CLI:** 1 new test in `tests/commands/test_agents.py`: a NOT_FOUND agent counts as deleted (exit 0), and a
  transport error stays UNDETERMINED (exit 1).
- **Support and updates:** `tests/actions/lifecycle_support.capped` and `over_cap` serve a roster whose combined read
  is over the cap. Updated assertions: describe's first roster call is `{}`; `VERIFY_READS` holds three reads; verify
  never sends the combined args.
- **Affected files:** `tests/actions/test_lifecycle_{propose,describe,verify,kinds}.py` plus
  `tests/commands/test_agents.py`: 153 passed. `tests/inventory`, `tests/triage`, `tests/hermes/test_halt_watch.py`,
  `tests/mcp` and `tests/commands/test_agents.py`: 608 passed.

### Suite

Full suite, one background run, no -x, on 9e0c982: **4690 passed, 5 skipped, 0 failed** (4 pre-existing warnings; 580.44 s).

### Concerns (fix round 1)

1. **ARCHIVED agents and `get_intelligence_agent`: not measured.** Whether `get_intelligence_agent` answers for an
   ARCHIVED agent is still unmeasured (Phase 4E task 0.4). The write path reaches that read only when the ARCHIVED list
   alone is also over the cap. If the platform then answers NOT_FOUND for an archived agent, ACTIVATE refuses as "not
   among the account's agents". That is fail-closed, but wrong in wording. The first live ARCHIVE settles the question.
2. **The over-cap error code: not measured.** The fakes set none, and nothing depends on it.
3. **More reads per action.** ARCHIVE/ACTIVATE now spend 1-3 reads instead of 1, and the guard reserves 3.
4. **Debounce trade-off.** Two agents genuinely archived in the same 5 minutes are reported one snapshot (about 5
   min) later.
