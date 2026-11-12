# Brief: platform-first — a change the user makes on BattleGrid takes priority (2026-10-25)

## The user's words and rulings (2026-10-25)

- **Words:** "Sometimes I might do stuff directly on the platform that he doesn't know about ... If something happened
  directly on the platform, this should take priority ... update him that that was turned on, so he can adjust
  whatever he has to adjust."
- **Ruling 1, safety still acts.** The hard safety rules still act on an agent the user changed, and the user is told
  why:
  - a RED HALT on a daily-loss or drawdown breach;
  - a CLOSE for stop proximity, time stop or thesis;
  - a TIGHTEN.

  The pool's "no room" HALT (POOL_FULL) is NOT a safety rule. It must respect the user's change.
- **Ruling 2, duration.** The user's change holds **until that agent's next trade closes**: the first position of that
  agent with a close time after the change. After that, the manager manages the agent normally again and says so.

## The incident that prompted it (measured)

- **The halt.** The pool HALTed TPO VAL Defender 4h (2c05ced6) at 08:06Z: action 131, POOL_FULL.
- **The resume.** The user resumed it in the app at some point before 13:4xZ. The manager has no record of that resume.
  It did not re-halt the agent only by accident: `pool_halt_key` matched the DONE halt row.
- **Today's detection.** The only platform-change detection is the exposure-cap ceiling (`manager/risk/cap_ceiling.py`
  `record_outside_edits`, alert CAP_SET_OUTSIDE_MANAGER, with officer attribution in `manager/risk/officers.py`).
  - **Keep its semantics unchanged:** a user-set cap stays a permanent ceiling (the 10-16 ruling; memory
    "automation must not raise user-lowered limits").
  - The new hold sits on top of it.

## What to build

1. **Detect.** On every snapshot, for each deployed or owned ACTIVE agent, compare the live reading of each axis below
   with the previous snapshot's.
   - **Axes:**
     - **run state** (halted/active, from `get_agent_budget` `haltedAt` / `haltReason`, or wherever the snapshot stores
       it);
     - **tradingConfig**, per key;
     - **strategy binding**: strategyId, revision, bindingState;
     - **model**;
     - **Radar slot membership and enablement**: coin, slot agent, enabled/paused;
     - **Arena deployment state**, if read.
   - **Attribution.** A change is manager-made when a manager `actions` row of a kind that writes that axis, on that
     target, was performed between the two snapshots, with a margin of the verify window. Otherwise it is
     **platform-made**.
   - **Officers.** Reuse the officer attribution for the cap axis where it already exists; officers are "platform" too.
   - **Rule 3.** An unread reading on either side is not a change. Never invent one.
2. **Record.** Store each platform-made change in a new table or a `system_state` key (pick the pattern the code already
   uses for similar ledgers), with:
   - agent and axis;
   - before and after;
   - when it was seen, and the snapshot ids;
   - the hold state: ACTIVE, ENDED (with why), or SUPERSEDED (a later platform change on the same axis).
   - Write an audit ledger event too.
3. **Tell.** Alert `PLATFORM_CHANGE_SEEN`, one per change, carrying the human text. Example: "TPO VAL Defender 4h was
   resumed on the platform (seen 12:41Z); the manager adopts it and holds until this agent's next trade closes".
   - Wire it into the halt watch that posts to the Commander chat (`hermes/scripts/battlegrid_halt_watch.py`) the way
     other alerts are posted.
   - When a hold ends, alert `PLATFORM_HOLD_ENDED`: "...'s next trade closed; the manager manages it normally again".
   - Add the agent's ACTIVE holds to the sentinel's dossier/poll context and to `manager report inventory` / agent
     status, so the models do not read the user's change as an anomaly.
4. **Respect.** While a hold is ACTIVE on an axis, any manager action that would change that axis is REFUSED in the
   guards. The refusal names the hold: "held: <axis> changed on the platform at <t>; until the agent's next trade
   closes". In practice:
   - **Run state held** after a user RESUME: the pool HALT and the fleet-resync and review/allocation halts are
     refused. After a user HALT, any manager RESUME is refused.
   - **tradingConfig held:** SYNC_LIMITS that would change a held key are refused. The fleet resync should instead skip
     that agent and log why. The cap ceiling rule continues separately.
   - **Binding/model held:** REBIND/REMODEL are refused.
   - **Radar/Arena held:** stage/commit/pause/resume of that coin's or preset's deployment is refused.
   - **Safety kinds are NEVER refused by a hold:** RED HALT (a breach), CLOSE, TIGHTEN, and the pause/delete
     exposure-reducing kinds (`REDUCES_RISK` / `DEPLOYMENT_REDUCING`). Record in metrics that a hold existed and was
     overridden for safety, and alert so the user is told why.
5. **Adjust.** The manager re-plans around a held state.
   - **Pool shares:** the exposure pool counts a user-resumed agent as active, so the others' shares shrink and their
     syncs lower accordingly.
   - **Allocation and review:** treat the held state as given.
   - Make sure nothing loops: no repeated refused proposals for a held axis. Skip proposing; do not propose-then-refuse
     every tick.
6. **End.** A hold ends when the agent has a closed trade with `closedAt` after the change's seen time. Read
   `list_agent_trades` (already used by allocation/review) or the snapshot's position disappearances; reuse what is
   already read and add no new per-tick platform calls if avoidable. Also:
   - a later platform change on the same axis supersedes the hold, and the new change starts a new hold;
   - add a manual `manager holds list` / `manager holds end <id> --note` CLI for the operator.

## Out of scope

- **Do not change:** the cap-ceiling semantics, the safety guards, contract handling, deploy scripts.
- **No new platform write kinds.**

## Rules

- **Worktree:** `C:/tmp-bgm-platformfirst`, new branch `feat/platform-first-holds` from main `39feebb`.
- **Do not:** merge, push, deploy, call BattleGrid, touch Docker/.env/Hermes profiles (editing the repo's
  `hermes/scripts` source is fine), or dispatch subagents. Read-only psql (`docker exec battlegrid-manager-postgres-1
  psql -U manager -d manager -Atc "..."`) is fine: measure the stored snapshot shapes for each axis before coding.
- **Write files** with Write/Edit.
- **Commits:** small, each ending with "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>".
- **Tests:** C:/Users/rafae/Documents/GitHub/battlegrid-manager/.venv/Scripts/python.exe -m pytest -q -p
  no:cacheprovider. Cover detect, attribute, hold, refuse, the safety bypass, end, supersede, and the 10-25 replay (pool
  HALT 131, then a user RESUME seen: a hold, no re-halt, other shares shrink). Run the affected files, then ONE full
  run (no -x, no -n). `WinError 10055` = rerun that file alone.
- **Report:** write it to C:/Users/rafae/Documents/GitHub/OMEGA/.claude/worktrees/app-development-continuation-8b80ba/platform-first-report.md.
  Return only: status, commits, the suite count, and concerns.
