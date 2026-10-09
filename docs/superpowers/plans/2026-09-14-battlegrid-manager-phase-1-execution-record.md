# Phase 1 execution record — commander (2026-09-14)

Branch `phase-1-commander`, from `phase-0-foundations` at `aa25992`, to `6b82662` plus this record: 34 commits, 52 files,
+6925/−57 lines. Executed with subagent-driven development: one implementer per task, a spec-and-quality review of each
task, fix rounds where a review governed, one whole-branch review, one fix wave, and one scoped re-review of that wave.
The task-by-task ledger is kept beside this file as `execution-ledger.md`.

## What was built

| Task | Result | Commits | Review |
|---|---|---|---|
| 1 Watch stores full tool definitions (hash version 2) | done | 5800abe..601e647 | clean |
| 2 Proxy exposure: reviewed allowlist ∩ declared read-only ∩ present | done | 601e647..fe4f5ea | 1 fix round (commit trailer) |
| 3 One Postgres token bucket for every service | done | fe4f5ea..290fc2d | 1 fix round (first-insert race) |
| 4 MCP server core: gateway task, native tools, shared views | done | 9ef640b..f2745be | 1 fix round (shutdown race) |
| 10 OAuth tokens refresh without a human, one process at a time | done (added mid-execution) | c31f22f..f311703 | 1 fix round (cancelled refresh lost a rotation) |
| 11 Heartbeats say when reads fail | done (added mid-execution) | 87e344c..30d0fa4 | clean |
| 5 HTTP app, bearer auth, DNS-rebinding protection, `mcp` service | done | 30d0fa4..6b0456e | 1 fix round (duplicated bearer check) |
| 6 Hermes `commander` profile installer | done | dc3822c..ef4ab4d | clean |
| 7 `battlegrid-manager` Hermes skill | done | ef4ab4d..688b80c | clean |
| 8 Daily report from stored data | done (Step 5 is the user's) | 2a967c5..984b490 | clean |
| 9 Acceptance record | done (Step 3 is the user's) | 53fb9b9..7a4ebb0 | clean |
| Final review fix wave | done | 7a4ebb0..6b82662 | re-review: all findings addressed |

Suite: 153 tests, passing on Python 3.14.2 (local) and Python 3.12.14 (the production image), with one third-party
warning (`starlette/testclient.py:53`).

## What execution found that the plan did not know

- **Every BattleGrid read failed from 13:13 to 16:28 UTC while heartbeats said ok.** mcp 2.1.1's `OAuthClientProvider`
  never refreshes tokens it loads from storage and answers a 401 with the interactive flow. Measured the same day:
  access tokens last 3600 s, and **every refresh rotates the refresh token**. Task 10 (one refresher at a time, under a
  file lock, re-reading the stored token) and Task 11 (truthful heartbeats) were added. Refreshes observed afterwards:
  17:27:47, 18:23:40, 19:19:25, 20:14:32 UTC — one grant each, every snapshot OK.
- **A POST error inside the SDK transport cancels the task that opened the session.** The whole-branch review showed
  the gateway died for good after one transport error or refused refresh while `mcp` stayed "Up" (reproduced on Python
  3.14 and 3.12). The fix wave added a supervisor that restarts the worker with backoff, answers the broken call with a
  typed error, keeps queued calls, and records `gateway.restart` in the ledger.
- **Hermes treats MCP server names in `platform_toolsets` as an allowlist**; the plan's `mcp-battlegrid_manager` was not
  a server name, so every enabled MCP server would have loaded. The installer now names the server and replaces
  inherited servers; `tools list` shows exactly one.
- **Hermes' MCP circuit breaker** pauses every tool of a server for 60 s after 3 consecutive error results; the skill now
  tells the commander not to repeat failing calls.
- **Hermes gives the model the local date and UTC offset but no time of day**, so the commander misstated the snapshot
  age by hours. The manager now serves the age, in UTC, with a fresh or stale verdict, and the skill says to quote it.
- **BattleGrid deployed build `d9ad8f8b` under contract 56.1.0 by 17:42:23 UTC**; the watch recorded it with comparable
  per-tool hashes: 0 tools added, removed or changed.
- Hermes desktop sessions always add the `project` and `desktop_ui` toolsets and ignore `agent.disabled_toolsets`
  (recorded as a residual gap). This machine's clock is UTC+7; the MAEZTRO cron named "UTC 00:00" runs at 17:00 UTC.

## Acceptance (docs/phase-1/acceptance.md)

| Check | Verdict |
|---|---|
| 1 Fleet answer vs `manager_fleet_report` | PASS on its written criteria (wallet, slots, Radar count; age restated from `ageLine` with identical values). Open in the same answer: Radar block split miscounted, stale Hermes memory mixed in |
| 2 ROT Alpha scan vs direct `scan_agent_coins` | PASS |
| 3 Close/deploy refusal; before/after reads; no write attempted | PASS |
| 4 Reads survive token expiry | PASS |
| 5 Tool-search bridge reaches only the manager | PASS |
| 6 The commander reaches exactly one MCP server | PASS |

## Decisions that belong to the user

1. Whether Check 1 passes on an identical restatement of `ageLine` or stays open.
2. The commander's memory: `memories/MEMORY.md` and `USER.md` were copied from the default profile and are injected into
   every session; stale account facts from them reached an answer. Recommended: `memory.memory_enabled: false` for the
   commander (reversible; `USER.md` preferences still load), then made permanent in the installer with a test.
3. Pausing the MAEZTRO cron `da33cccb09f7` now that the manager writes the daily report (reversible; removal needs a
   second yes after a week).
4. The exit gate: the user's own conversation with the commander in the Hermes desktop app, including its tool list.
5. The Windows "OMEGA TPO panel" task stays enabled until the Docker panel has 24 clean hours (from 17:05 UTC).
6. How to finish the branch.

## Parked follow-ups (rulings recorded; not blocking)

- An untyped `ValueError` for digit strings that `int()` rejects in native-tool arguments (`manager/mcp/native.py`).
- The skill's "not a BattleGrid outage" wording can be false during a real outage; rule 8 conflicts with rule 5's retry.
- Two gateway docstring overstatements; a timing-dependent grant count in `tests/mcp/test_gateway.py`.
- The installer's "Nothing was changed" message after it created the profile; a dry run on a missing profile returns
  before the credential check.
- Serve per-block-reason Radar counts from the manager so the model never counts.
- The earlier task-level minors in `execution-ledger.md`, triaged DEFER by the whole-branch review.

## Phase 2 inputs

- Graceful SIGTERM for the `run` services, and waiting for an in-flight token refresh on every shutdown path (until
  then, the runbook's deploy guards are the protection).
- Whether BattleGrid ends idle MCP sessions with HTTP 404: mcp 2.1.1 would surface that as an RPC "Session terminated"
  error that does not drop the session (unmeasured).
- Separate bearer tokens per door before any write tool; a deliberate decision on the commander keeping `web`;
  `trust: untrusted` for the manager server; a periodic `mcp` heartbeat.
