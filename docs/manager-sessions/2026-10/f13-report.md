# F1 + F3 report (battlegrid-manager, worktree C:/tmp-bgm-f13, branch feat/finish-watch-report from main d680be7)

Not merged, not pushed, not deployed. No BattleGrid call. Docker was touched only for the read-only psql read of
`surface_tools` / `manager_schemas`.

## Commits

- 23f6a73 AGENT_ENTRIES_NOT_FILLING: the rule, the route, the daily report, the agent status
- 1005b2c Halt watch posts it once; runbook, Commander SOUL and skill (one line each)
- 19c9247 Daily analytics read + "Agent analytics" in the daily report and in manager_fleet_report
- b9420c7 Commander skill paragraph + runbook section

## F1: AGENT_ENTRIES_NOT_FILLING (manager/inventory/entry_not_filling.py)

- The streak and rule come from entry_failures (`streak()` now takes a tuple of counted statuses). FAILED and EXPIRED
  both count and EXECUTED ends the streak. It shares the other two watches' join boundary, 24 h silence, AGENT_HALTED
  exclusion, settled-reason rule (the 3 newest), one alert per streak (`covering`), ack scope and the three resolutions.
- **The double-alert rule: MIXED streaks only.** It files only when neither specific watch's own streak (FAILED-only,
  EXPIRED-only, each computed exactly as that watch computes it) holds 3. So it never files for a pure streak, or for a
  mix where one kind alone reaches 3 (e.g. F,E,F,F belongs to the entry-fail watch). If one kind later reaches 3, the
  new specific alert **supersedes** the open not-filling alert: it resolves with "superseded by <KIND> alert N" and
  `supersededBy` in the ledger. The agent then has one entry alert open. The rule runs after the failing and expiring
  rules in job_snapshot.
- Detail: `failed`, `expired`, `failedReasons`, `expiredReasons`, the entries (status, coin, reason), the newest status
  and reason, and a note. Ledger: `entry_not_filling.alerted` / `.resolved`.
- Wired into `GET /api/entry-not-filling`, the ack scope (one alert per streak), the sentinel-poll exclusion, the agent
  status line ("entries-not-filling alert N open"), and the daily report ("## Entries not filling" and NOTABLE events).
  The halt watch adds a source, `not_filling_message`, which posts each alert once.
- Tests: tests/inventory/test_entry_not_filling.py (11) and 3 new in tests/hermes/test_halt_watch.py.

## F3: daily analytics (manager/inventory/analytics.py, manager/platform/reads.py)

- Schemas: stored state (123.2.0) has input schemas and descriptions for all five tools and **no output schema** in
  either `surface_tools` or `manager_schemas`. The shapes are NOT MEASURED. Only
  get_agent_entry_discipline takes extra input (windowStartAt/windowEndAt, at most 90 d). I use the last 7 days.
- Read: after a snapshot whose core reads are all OK, and after the heartbeat and every watch, in its own try. It runs
  once per UTC day and reads at most 10 deployed agents (the snapshot's deployed set), each tool at most once per
  agent per day. The account read is made once per day. A failure stays UNDETERMINED for the day, with no retry.
  State: system_state `analytics.daily` holds today's extracted figures and served top-level keys, not raw answers.
- Fail-closed: `reads.read_analytics` makes the call. A failure, a non-object answer, or an answer missing a path in
  `ANALYTICS_READ_SETS` is UNDETERMINED, and no figure from it is quoted.
- Report: "## Agent analytics" appears in the daily report and at the end of the Commander's `manager_fleet_report`.
  Per agent it shows readiness (top-level readiness/minSampleSize, "k of n cells ready"), the headline subtrees
  flattened to path + served value, every numeric count whose key names "fill", and cost vs net (the cost read's
  totals and counts, and the review read's `llm`). The account totals come last. A cell that reads INSUFFICIENT, or
  whose sampleSize is below minSampleSize, shows "not ready yet (sample n of m)", never 0. Nothing is recomputed.
- SKILL.md: one paragraph on reading the section, quoting figures as served, "not ready yet", and null not 0.
- Tests: tests/inventory/test_analytics.py (16). The answers are INVENTED from the descriptions and labelled as such.

## Suite

The full suite (no -x) on b9420c7: **4890 passed, 5 skipped, 0 failed** (9 min 54 s). The warnings are older ones, such
as the SyntaxWarning in tests/review/test_take.py. An earlier partial run showed 1 error in
`test_entry_failures::test_a_read_set_check_that_fails_reads_undetermined_never_fine`. That run overlapped my edits. The
test passes on its own and in the full run.

## Concerns

1. **Read sets outside READ_SETS / MANAGER_TOOLS (a design choice for you to confirm).** READ_SETS must cover
   MANAGER_TOOLS tools only, and each path must be served by a stored output schema (tests/platform/test_reads.py).
   None exists for these five. Putting them in MANAGER_TOOLS would let an input move on a report-only read block every
   write, the safety path's SYNC_LIMITS included. So they live in a separate `ANALYTICS_READ_SETS` and are exempt from
   D7c, following the `PLAN_TIME_READS` precedent. The cost: a platform change to them goes unreviewed, and the only
   effect is an UNDETERMINED report line.
2. **(Superseded by the live-shape round below: the shapes are now measured, and this design was wrong.)** **Shapes are not measured.** The declared paths are only the backticked names in the descriptions (`filterValue`,
   `exitQuality.prematureStop`, `costErodedCount`, `unreconciledCount`, `overall`, `llm`, `totals`). If the live nesting
   differs, those reads go UNDETERMINED every day. Check the first live report and re-declare. "Fill/unfilled counts"
   is a key-name search for "fill", since no field for it is named. It may find nothing, and then says so.
3. No READ_PATH_MISSING alert is filed for these reads, on purpose (it would reach the sentinel poll from an
   unmeasured shape). The report line names the missing paths instead.
4. Like the other two watches, a not-filling alert can fire while the streak's oldest reason is still UNREAD (only the
   3 newest must be settled). Its counts then show UNREAD.
5. After a deploy: recopy the halt watch script (`install_commander.py --halt-watch`). The first snapshot of each UTC
   day makes up to 1 + 4 x deployed calls (about 21 for 5 agents) through the 3 req/s bucket.

## Live-shape round (coordinator's fix request, 2026-10-21)

The coordinator measured all five tools live (analytics-live-2026-10-21.md). Every answer is wrapped in one top-level
key: `quality` (decision quality), `stats` (entry discipline), `economics` (cost economics), and `analytics` (both
review reads). The first F3 version expected none of them, so every line would have read UNDETERMINED.

Commits:
- 97c6cec: the read sets, readers and tests moved to the live shapes, with the measured fixtures.
- 78e7913: the Commander skill and the runbook.

1. **Wrapped paths.** `reads.ANALYTICS_WRAPPERS` names each tool's wrapper. `ANALYTICS_READ_SETS` now declares only
   wrapped paths:
   - `/quality/filterValue`, `/quality/exitQuality/prematureStop`, `/quality/verdictDistribution`
   - `/stats/confirmationTax`, `/stats/fastStopOutRate`, `/stats/maeBeforeMfe`
   - `/economics/totals`, `/economics/costErodedCount`, `/economics/unreconciledCount`
   - `/analytics/overall` and `/analytics/llm` (agent review), `/analytics/totals` (account)

   Every reader uses the same wrapped paths: `HEADLINES`, the `minSampleSize` floor read inside the wrapper, and
   `servedKeys`. The report shows each path relative to its wrapper. A list of rows is keyed by the row's label, so
   `filterValue[H1].enter` reads "meanSignedReturnPct 0.22 (READY, sample 97)" and `filterValue[H1].skip` reads "not
   ready yet (sample 0 of 20)". Before this, a list rendered as "[n rows]".
2. **Fixtures.** The live answers are in tests/fixtures/2026-10-21-analytics-live/<tool>.json, labelled "MEASURED
   2026-10-21" in the test module. They are verbatim except:
   - the parts the capture itself abbreviated (scopeCaveat, convictionByHorizon);
   - the review analytics: its verdict and filterValue lists and its slice arrays are cut to at most one row.

   The invented answers are gone. A new parametrized test checks two things for each tool: every declared path is
   served by the measured answer under its wrapper, and the unwrapped answer is refused (fail-closed).
3. **Fill picture from verdictDistribution.** The report now reads decision quality's `verdictDistribution`, and falls
   back to the review's `overall.verdictDistribution` when that read fails. It shows the unfilled verdicts
   (UNFILLED_MISSED 36, UNFILLED_SAVED 35, UNFILLED_FLAT 7) beside the filled ones (THESIS_PLAYED_OUT 4, WRONG_DIRECTION
   2, SCALPED_WIN 2, STOPPED_EARLY 1), each count as served and never totalled. A verdict name containing SKIP or
   PENDING would be listed as "other". The search for keys containing "fill" is removed.
4. **LLM cost from the review's `llm`.** It has its own line: "platform credit 0; own OpenRouter key (BYOK) 0.27; calls
   106; netAfterLlmUsd 0.33". The line adds that netAfterLlmUsd subtracts platform credit only. A key that is not
   served reads "not served".
5. **Tests.**
   - Affected files: test_analytics (24), persona_files, platform/test_reads, test_watch, mcp/test_server and
     scheduler/test_jobs, 256 passed.
   - Full suite (no -x, background) on 78e7913: **4899 passed, 5 skipped, 0 failed** (8 min 12 s).

Concern 2 above is resolved. Concern 1 (outside D7c) still stands. One remaining point: entry discipline's headline
shows confirmationTax, fastStopOutRate, maeBeforeMfe and provisionalRequiredReads, 15 figures capped at 14 ("... 1
more"). `baseline` is left out on purpose because it is not like-for-like.
