# v132 migration report: battlegrid-manager

The worktree is C:/tmp-bgm-v132, on branch `fix/contract-132`, based on main `83c62bb`. Nothing has been merged,
pushed, deployed or acknowledged, and no BattleGrid call was made. The only live access was read-only psql against
`system_state` (`manager_schemas`, `surface_tools`, `manager_schemas_acked`, `contract_live`).

main has since moved to `6ab6aee` (the deploy-check change another branch owns). This branch touches none of
`manager/commands/deploy_check.py`, `scripts/gated_deploy.sh` or `tests/commands/test_deploy_check.py`, and
`git merge-tree` shows it merges onto `6ab6aee` with no conflict.

## Commits (oldest first)

| Commit | What it does |
|---|---|
| ed9227e | The 132.0.0 fixtures; `get_agent_thought_log` (removed at v131) leaves the proxy allowlist, 82 -> 81. |
| 6c8307e | Both draft commits name `teamId`: agent edits send null, a Radar replacement sends its coin's own team; first deployments and team-less rows refuse. |
| eb6726a | The multi-team guard: budget and arming writes refuse unless the snapshot shows one trading team. |
| 4133f99 | `test_contract_132`, and pins for the removed fields (`summary.account`, `sourceThoughtLogId`) and the Hermes docs. |

## What was measured

The diff 129.0.0 -> 132.0.0 over the 52 manager tools in the stored observation matched the brief, with nothing more.
Run through `self_clear_verdict` from a 129.0.0 baseline, D7c calls nine changes unsafe:

- the two REQUIRED `teamId` inputs, on `commit_agent_draft` and `commit_radar_deployment_draft`. The code now sends
  both.
- seven reworded descriptions: `commit_radar_deployment_draft`, `get_account_state`, `get_open_orders`,
  `get_position_audit_history`, `get_radar_deployment`, `list_agent_open_orders`, `list_user_active_positions`. These
  are the user's to read (D7b), which is why the block waits for `manager contract ack 132.0.0`.

Three removed output fields are waived as "not read by the manager":
- `get_agents_hub /summary/account`;
- `get_signal_log /log|#0/sourceThoughtLogId`;
- `list_gate_blocks /entries[]/sourceThoughtLogId`.

Every other change is an added output field or an added optional input. `test_contract_132` pins this exact set.

## Item by item

### 1. `commit_agent_draft` teamId

- `pipeline.agent_commit_request` builds `{agentId, draftVersion, expectedRevision, teamId: null}`, so SYNC_LIMITS,
  REBIND and REMODEL all send `teamId: null`.
- It is added at send time and never stored in `params`. A row approved before 132 keeps its paramsSha.
- Fail closed: `_send_agent_draft` refuses a row whose `expectedRevision` is not an int (null, a bool, a string or a
  float) before the stage. It is FAILED with "not sent", and nothing goes on the wire. `agent_commit_request` itself
  raises on such a base. No manager path builds a create today. The guard makes sure none can.
- The REBIND/REMODEL dry card now reads "commit_agent_draft over revision N with teamId null (an edit never moves the
  agent's team)".

### 2. `commit_radar_deployment_draft` teamId

**Describe** (`radar_describe.py`):
- For a replacement, it reads `policy.teamId` from the `get_radar_deployment` read it already makes and checks it is
  a uuid string. The value goes into the approved params as `teamId`.
- `policy_projection` keeps `teamId` and `teamName`, and the card prints a `team:` line.
- A null or non-uuid teamId refuses with "teamId is unread ... the manager does not pick trading teams".
- A first deployment (`policy: null`) is REFUSED after the coin-cap check, with "a first deployment of this coin (no
  policy deployed): the manager does not pick trading teams ... deploy the coin in BattleGrid first".

**Send** (`radar_send.py`):
- `wire_args` puts `teamId` on the commit and raises without one.
- `_send_stage_commit` returns FAILED "not sent" before the stage when the params carry no team. This covers a
  STAGE_COMMIT_RADAR row described before the deploy. Such a row is also refused on the paramsSha mismatch, because
  describe now adds `teamId`.

**Verify** (`radar_verify.py`): unchanged. The platform keeps a coin's team, and verify settles by slot and revision.

**Read sets:** none needed. `get_radar_deployment` has no declared set, so every change to it is already read.

**Tests:**
- The send and describe tests now deploy over a coin that is already deployed (a replacement).
- New tests cover:
  - the first-deployment refusal;
  - five unread-team values;
  - a row with no team failing before the stage;
  - the wire args validated against the 132.0.0 schema.

### 3. `get_agents_hub` summary.account

There is nothing to change: no code reads `summary.account`.
- The hub read set is `rows[]` counts, `hubStatus`, `cost24hUsd` and `summary/totalCost24hUsd`.
- `lifecycle_describe.py:158` reads only `summary.activeAgents`, for the size watch.
- cap_watch only measures the read's size.
- The pool, the policy and the fleet read `get_account_state.account` (the snapshot's normalized wallet), which still
  describes Main.

A test pins two things: no module names `accountEquityUsd`, `budgetOverSubscribed`, `openUnrealizedPnlUsd` or
`teamAccounts`, and no read set declares them.

### 4. `sourceThoughtLogId`

There is nothing to change: no code and no read set names it. Only an old test fixture row does, and it stays. A test
checks that the read-set gate passes a `list_gate_blocks` page both with and without the key.

### 5. Allowlist

- **Removed:** `get_agent_thought_log` leaves `PROXY_ALLOWLIST`, which goes from 82 to 81 (and so leaves
  `READ_ALLOWLIST`). It was the only allowlisted name that the 132 `surface_tools` does not serve, checked by script
  and by a new test.
- **Not added:** `list_agent_market_grid_decisions`, `get_agent_profile` and `list_trade_conversations`. No Hermes
  skill or persona names them, and a test pins that they stay withheld.
- The counts in `tests/proxy/test_policy.py` and `tests/mcp/test_server.py` moved by one.

### 6. Unchanged reads

Confirmed: none of these needs code.
- `get_open_orders` still takes no `teamId` (Main). This is noted in the A2 comment in `verify.py`, tied to the
  multi-team guard.
- `get_position_audit_history` reads own positions only.
- `list_user_active_positions` rows are stored whole.
- `get_account_state.balance` still describes Main. `allTeamsBalance` is not read.

### 7. Multi-team guard (`manager/risk/teams.py`)

**Inputs.** The guard makes no new read. `take_snapshot` condenses three reads it already makes into
`reads.get_account_state.teams = {teams, mainTeamId, offMain, unread}`:
- `get_account_state.teams[]` (`id`, `role`);
- `list_intelligence_agents.agents[].teamId` (null is a platform agent, which trades on Main);
- `list_user_active_positions.positions[].teamId`.

**Evaluation.** `state_from_db` turns that summary into `AccountState.teams_refusal`. `team_guard` runs in
`guard_all` after `platform_guard`.

**What it refuses.**
- Refused kinds: SYNC_LIMITS (the pool resync's included), RESUME, ACTIVATE, REBIND, STAGE_COMMIT_RADAR,
  RESUME_RADAR, STAGE_COMMIT_ARENA and RESUME_ARENA.
- Verdicts:
  - "multiple trading teams: the pool and cap model is single-wallet (...)" when there is more than one team, or an
    agent or position off Main;
  - "trading teams unread: ..." when the picture is incomplete: a failed read, a missing key, not exactly one MAIN, or
    a snapshot that carries no summary (every snapshot taken before this deploy).
- Never refused: CLOSE, TIGHTEN, HALT, PAUSE_*, DELETE_* and ARCHIVE. REMODEL and the strategy kinds are not refused
  either, because they move no money.

**Read sets.** `get_account_state` declares `/teams[]/id` and `/teams[]/role`, and `list_intelligence_agents` declares
`/agents[]/teamId`. Positions are already declared at `/positions`. A new test checks every declared path of every tool
as served and required in the 132.0.0 observation.

**Tests.** Hand-seeded test snapshots carry `tests/one_team.py:ONE_TEAM`. `tests/risk/test_teams.py` (40 cases) and
two snapshot tests cover:
- one team, a second team, an agent or a position off Main;
- eight unread shapes;
- every kind against the guard;
- `state_from_db` end to end.

### 8. Bookkeeping

New fixtures in `tests/fixtures/2026-10-23-surface-132.0.0/`:
- `manager_schemas_132.0.0.json`: the stored observation, written with sorted keys like the 129 file. Its hash
  recomputes to the stored `1b681890...`.
- `tool_annotations_132.0.0.json`: names and annotations of all 150 served tools.
- `surface_tools_v132_reads.json`: the two Phase B reads' listing rows, identical to 129.0.0.

`tests/actions/fake.py` now checks every fake call against the 132.0.0 input schemas.

`tests/platform/test_contract_132.py` mirrors 129. The 03:56Z observation was written by the deployed code (`d461d84`),
so it lacks `list_signal_logs` and `list_agent_trades`. Both orders are pinned clean:
- **deploy then ack:** the first watch run rewrites the observation and the ack copies it in, with no backfill and no
  drift;
- **ack then deploy:** one `contract.schemas_backfilled`, and writes stay open.

### 9. Commander docs

Nothing to edit. No `hermes/**/*.md` names `get_agent_thought_log` or `sourceThoughtLogId`, and a test pins this.

## Suite

The full run on 4133f99 (no -x, no -n) was clean: **5157 passed, 5 skipped, 0 failed** (559 s). The 4 warnings were
already there before this change (for example, an invalid escape in `tests/review/test_take.py`).

## Concerns

1. **The manager can no longer make a FIRST Radar deployment.**
   - `manager radar deploy` on an undeployed coin, or a Commander proposal for one, is now refused at describe, and
     you deploy new coins in BattleGrid.
   - Replacing the agent on a deployed coin still works.
   - If you want the manager to create deployments, it needs a rule for choosing a team (for example, Main's id from
     `get_account_state.teams`). That is your call.
2. **The guard is unread until the first snapshot after the deploy.**
   - Every stored snapshot predates `reads.get_account_state.teams`, so for up to one snapshot cycle (~5 min) after the
     deploy every budget or arming write is refused as "trading teams unread". Writes are blocked until the ack anyway.
   - After the first snapshot, run
     `psql ... "select reads->'get_account_state'->'teams' from snapshots order by id desc limit 1"` and confirm
     `unread` is `[]` and `offMain` is `[]`.
   - No live 132 payload was read, so I have not confirmed that every live agent row carries the `teamId` key and every
     position carries a uuid.
3. **A flapping read shuts the budget path.** A transient failure of `get_account_state`,
   `list_intelligence_agents` or `list_user_active_positions` now refuses SYNC_LIMITS and resumes for that snapshot.
   That is fail-closed by design, but the pool resync will retry on its `FLEET_RESYNC_EVERY_S` throttle and file
   refusals.
4. **Agents and positions off Main block more than their own writes.** Any private agent on another team in the
   snapshot's agent list (ACTIVE agents) blocks every budget write on the account, not only that agent's. One position
   off Main does the same.
5. **Rows queued before the deploy.**
   - A queued STAGE_COMMIT_RADAR row is refused on its paramsSha.
   - SYNC_LIMITS, REBIND and REMODEL rows keep their sha and send `teamId: null`.
6. **Ack.** Writes stay blocked after the deploy until `manager contract ack 132.0.0`: seven descriptions changed,
   which is your rule for a breaking block. The acked baseline is still 123.2.0, so this ack also covers
   129.x-131.
7. **The 129 concerns still stand.** No live check yet of the `list_signal_logs` / `list_agent_trades` output
   schemas, the A2 `symbol` format, or the first queued TIGHTEN, because main `83c62bb` is not deployed yet.
