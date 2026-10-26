# Brief: an alert when a deployed agent's ENTER decisions keep failing at the order stage (2026-10-18)

## Incident and the user's ruling

**Incident.** Since 2026-10-16 12:00Z, every signal of the live agent "VWAP Sentinel 4h"
(`959739dd-2865-4bc4-8a36-3a58aed28e0f`) has ended `terminalStatus: FAILED`: 30 of 30.
- The model decides ENTER each time.
- The platform then refuses the order: `execution.failureReason: BELOW_EXCHANGE_MINIMUM`, with the
  `executionMessage` "Order notional $6.93 below exchange minimum $10.00 — risk budget $0.26 at a 3.75% hard stop
  cannot buy a legal order".

Nothing in the manager or Hermes noticed:
- triage works per open position, and there are none;
- `list_gate_blocks` stops before execution;
- the snapshot does not read signal logs or entry decisions.

**The user's ruling:** build the watch. Detection only: no automatic change, no new write.

## Working rules

- **Repo and worktree:** repo `battlegrid-manager`, worktree `C:/tmp-bgm-entryfail`, branch `feat/entry-fail-watch`
  (from main 796f050).
- **Tests:** `C:/Users/rafae/Documents/GitHub/battlegrid-manager/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.
- **Commits:** small, each ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Not allowed:** merging, pushing, deploying, calling BattleGrid, touching Docker/.env/Hermes profiles, or
  dispatching subagents. The one exception: read-only psql queries for shapes, e.g. through
  `docker compose -f C:/Users/rafae/Documents/GitHub/battlegrid-manager/docker-compose.yml exec -T postgres psql -U manager -d manager`.
  - The `manager_schemas` table holds every tool's live input and output schema (contract 120.2.0).
- **Model to follow:** the halt watch merged at main `0404412`, which is the pattern to copy:
  - `manager/inventory/halts.py`;
  - its snapshot columns and the `get_agent_budget` read in `manager/inventory/snapshot.py`;
  - the AGENT_HALTED_IDLE alert;
  - `hermes/scripts/battlegrid_halt_watch.py`;
  - the daily-report lines and the read set in `manager/platform/reads.py`.

  Read those first, then `git show 0404412 --stat` for every file it touched.

## What to build

1. **Read.** Each snapshot, per DEPLOYED agent (the same set the halt watch uses), reads its recent ENTER outcomes.
   - Prefer `list_entry_decisions(agentId, decision: "ENTER", limit: 10)`. Use its `status` (EXECUTED / FAILED /
     EXPIRED / ...).
   - Check the output schema in `manager_schemas` for whether a failure reason is carried.
   - If the reason is not in the list, read `get_signal_log(agentId, logId)` ONLY for the newest FAILED decision
     whose id the manager has not seen before (cache by decision id). Use its `pipeline.execution.failureReason`
     and `executionMessage`.
   - Keep extra reads to at most 1 list + 1 detail per agent per snapshot.
   - A failed read stores UNDETERMINED, never "fine". Add the read sets to `reads.py` (fail-closed, as for
     `get_agent_budget`).
2. **Store** enough to apply the rule: a small table or columns, your choice; say why.
3. **Rule** (a new module, e.g. `manager/inventory/entry_failures.py`, run after each snapshot).
   - **When it fires:** the agent is deployed, AND its newest N decisions (`ENTRY_FAIL_STREAK` = 3) with
     `decision == ENTER` all have `status == FAILED`, AND the newest is under 24 h old.
   - **What it files:** ONE alert per (agent, first decision id of the streak), kind `AGENT_ENTRIES_FAILING`. The
     detail carries:
     - the agent name;
     - the streak length;
     - the newest failure's reason code and `executionMessage`;
     - counts per reason;
     - the agent's `maxConcurrentExposureUsd` and presets from the snapshot.

     Also write a ledger event.
   - **When it resolves:** an EXECUTED decision ends the streak; resolve the open alert the way the halt watch
     auto-resolves a lifted halt. Acknowledging silences that streak only, and a new streak alerts again.
   - **Not a failure:** a halted agent, since its decisions never reach execution. EXPIRED and CANCELLED neither
     count as a failure nor end the streak; SKIPPED is not ENTER.
4. **Visibility.**
   - Generalise `hermes/scripts/battlegrid_halt_watch.py` so the SAME Hermes job also posts each new
     AGENT_ENTRIES_FAILING alert once, keeping its state like the halt watch. There is no new cron job: the
     Commander's "BattleGrid halt watch" job already runs that script every 5 minutes.
   - The message says plainly:
     - what failed and why (quote the `executionMessage`);
     - that the Commander cannot change risk settings;
     - that the fix is the user's (raise presets, the exposure cap, or the policy), or ack the alert.
   - Add AGENT_ENTRIES_FAILING to the daily report's NOTABLE events, and a standing line while open, like the halt.
5. **Docs:**
   - Commander `SOUL.md` and `hermes/skills/battlegrid-manager/SKILL.md`: one short paragraph each.
   - The runbook entry.

## Report

Tests for every rule, including the fail-closed paths:
- a read failed → no alert, no "fine";
- EXPIRED in the middle;
- an EXECUTED ends the streak and auto-resolves;
- ack silences only that streak;
- a halted agent → no alert.

Run the full suite once (background, no -x). Write the report to
`C:/Users/rafae/Documents/GitHub/OMEGA/.claude/worktrees/app-development-continuation-8b80ba/entryfail-report.md` and
return only: status, commits, suite count, concerns.
