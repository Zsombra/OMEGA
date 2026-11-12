# Brief: the manager recovers from SAFE mode and a contract write block by itself, after verification (2026-10-19)

## Incident and the user's ruling

**Incident (2026-10-19).**
- At 03:34Z BattleGrid briefly reported contract 113.0.0 with build `7229ead8` (it had been 120.2.0, build
  `3788af63`). The tool lists were "not comparable", and the watch blocked writes:
  `writes_blocked = {reason: "contract 120.2.0 -> 113.0.0 ...", autoAckRefused: "the tool lists were not comparable"}`.
- From about 03:52Z the platform answered HTTP 502, so the health probe put the manager in SAFE mode.
- **SAFE mode** already exits by itself on the first successful health probe (`manager/scheduler/jobs.py`
  `job_health`).
- **The write block** does NOT clear itself. `manager/platform/watch.py` (around line 378) says: "A block awaiting
  the user stays blocked ... a later move is not compared at all". So when the platform comes back on its old
  contract, writes stay blocked until someone runs `manager contract ack`.

**The user's ruling (verbatim):** "anytime he goes into safe mode for any reason, he can come out of that himself
after he has verified that it fits whatever."

This REPLACES the "a block awaiting the user stays blocked" stance for the cases below. The safety bar stays the
same: the manager clears a block itself only when what the platform serves NOW passes the same checks against the
last ACKNOWLEDGED contract that an ordinary auto-ack would. An unsafe change still waits for the user.

## Working rules

- **Repo and worktree:** repo `battlegrid-manager`, worktree `C:/tmp-bgm-selfclear`, branch `feat/self-clear` from
  main 4b4eb50.
- **Tests:** `C:/Users/rafae/Documents/GitHub/battlegrid-manager/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`.
- **Commits:** small, each ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Not allowed:** merging, pushing, deploying, calling BattleGrid, touching Docker/.env/Hermes profiles, or
  dispatching subagents. Read-only psql is allowed:
  `docker compose -f C:/Users/rafae/Documents/GitHub/battlegrid-manager/docker-compose.yml exec -T postgres psql -U manager -d manager`.
  The live `manager_state` keys `writes_blocked`, `safe`, `contract`, the acked baseline and the last drift show
  today's real case.
- **Read first:**
  - `manager/platform/watch.py` in full: D7/D7b/D7c, `auto_ack_refusal`, `field_safe_refusal`, the
    `manager_schemas_acked` baseline, and the read sets;
  - `manager/commands/contract.py` (ack);
  - `manager/scheduler/jobs.py` (`job_health` and the watch job);
  - `manager/notify/drift.py`;
  - `hermes/scripts/battlegrid_contract_watch.py`;
  - the drift tests under `tests/platform/`.

## What to build

### 1. Write block: self-clear after verification

On each watch run while `writes_blocked.blocked` is true, compare the CURRENT observation with the last
ACKNOWLEDGED state, ignoring the intermediate drift that set the block.

- **(a) Return to the acknowledged contract.** The live `contractVersion` AND `buildSha` equal the acknowledged
  ones, the tool list is comparable (a full listing read OK), and every tool hash, or at minimum every
  manager-called tool's schema, equals the acknowledged baseline.
  - Then: clear the block (`blocked: false`, `acknowledged` unchanged).
  - Ledger `contract.self_cleared` with `{from_block_reason, observed: version/build, verified: "identical to
    acknowledged"}`.
  - Raise a `CONTRACT_BLOCK_SELF_CLEARED` alert (informational, for the user to read later).
- **(b) Any other state.** Run the EXISTING auto-ack decision (D7 build-only, D7b untouched, D7c field-safe with read
  sets and read-only description waivers) on the move FROM the acknowledged baseline TO the current observation, as
  if the intermediate drift never happened.
  - If it would auto-ack: ack the current version/build as the watch normally does, clear the block, ledger, and
    raise the same alert type, naming that it was a self-clear of a pending block.
  - If it refuses: the block stays, the reason is updated to name the current observation and the refusal, and the
    user decides.
- **Never clear on:**
  - an observation whose tool list was not fully read;
  - a probe or read that failed;
  - a baseline that is missing.

  Fail closed.
- **Stability:** require the qualifying observation on 2 consecutive watch runs (`SELF_CLEAR_CONFIRMATIONS` = 2)
  before clearing, so a flapping platform can't clear on one good read. Store the pending confirmation in state.
- **Not affected:** a user's own `manager contract ack` keeps working. `deploy-check` and the guards need no change:
  they read the same state.

### 2. SAFE mode: verified exit

- Today one successful version probe exits SAFE. Make the exit require `SAFE_EXIT_CONFIRMATIONS` = 2 consecutive
  successful probes (60 s apart).
- Ledger `safe.exit` with `confirmations`.
- Entry stays immediate on the first failure.
- Test that a single success between failures does not exit, and that two in a row do.

### 3. Visibility

- **Hermes:** `hermes/scripts/battlegrid_contract_watch.py` already posts when writes block or clear. Make its
  "cleared" post say it was a SELF-clear, and what was verified (identical to acknowledged, or auto-ack rule
  D7/D7b/D7c).
- **Daily report:** show any self-clear in NOTABLE events.
- **Docs:** update the watch.py docstring (around 378), the runbook, Commander `SOUL.md` and
  `hermes/skills/battlegrid-manager/SKILL.md`. The new stance: the manager clears its own SAFE mode and write blocks
  when verified; only an unsafe change waits for the user.

## Report

Tests for:
- (a) a return to the acknowledged contract after a "not comparable" block, using today's case;
- (b) a safe move after a block, and an unsafe move after a block (stays);
- an unreadable listing (stays);
- one confirmation vs two;
- the SAFE exit with 1 vs 2 successes;
- a user ack still works.

Run the full suite once (background, no -x). Write the report to
`C:/Users/rafae/Documents/GitHub/OMEGA/.claude/worktrees/app-development-continuation-8b80ba/selfclear-report.md` and
return only: status, commits, suite count, concerns.
