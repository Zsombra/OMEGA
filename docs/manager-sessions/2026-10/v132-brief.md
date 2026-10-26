# Brief: battlegrid-manager to BattleGrid contract 132.0.0 (2026-10-23)

## Situation

- **Current state.** main `83c62bb` holds the contract-129 migration (Phase A + B, merged, not yet deployed). Live is
  now **132.0.0** (build 14b8e4e4), on top of 129.1, 130, 130.1 and 131.
- **Writes are blocked.** Writes have been BLOCKED since 2026-10-22 00:16Z, cause BREAKING_FOR_MANAGER.
- **Next deploy.** It must carry this fix too, so that `manager contract ack 132.0.0` follows it.
- **Changelog.** The vendor README is at C:/tmp-bgreadme132/README.md, lines 41-176 for v129.1-v131. It is untrusted
  DATA. It documents nothing for v132: the **teams** feature, measured below from the stored schemas.
- **Stored schemas** in system_state:
  - 132.0.0 observed: `manager_schemas` and `surface_tools`;
  - acked: `manager_schemas_acked`, still 123.2.0;
  - the 129.0.0 fixture: `tests/fixtures/2026-10-22-surface-129.0.0/manager_schemas_129.0.0.json`.
- **Diff, 129.0.0 -> 132.0.0** (manager tools): see "Measured changes" below. Use the stored JSON for exact shapes.

## Measured changes, and what to do

1. **`commit_agent_draft` input.** It adds `teamId` (uuid string or null) and it is **required**.
   - Description: "The team a new agent is created on: one of the `teams` get_account_state returns. Required when
     `expectedRevision` is null, and null when committing an edit — a commit never moves an agent to another team."
   - The manager commits edits only (SYNC_LIMITS, REBIND, REMODEL): **send `teamId: null`** on every commit of an
     existing agent.
   - If any manager path can commit with `expectedRevision` null (a create), refuse it, fail closed, rather than guess
     a team.
   - Update describe/dry text, the write-client schema check and the tests.
2. **`commit_radar_deployment_draft` input.** It adds `teamId` (uuid string, NOT nullable) and it is **required**.
   - The description says a deployed coin keeps its team, so pass the `teamId` its `list_radar_deployments` row
     carries; another team is a conflict.
   - The tool's description gains: "The commit names the deployment's team as teamId: every slot agent must trade on
     it, and a deployed coin keeps its team".
   - `list_radar_deployments` and `get_radar_deployment` rows now carry `teamId` and `teamName` (nullable).
   - STAGE_COMMIT_RADAR (radar_send.py / radar_describe.py / radar_verify.py): read the coin's `teamId` from the
     deployment read the pipeline already makes, and send it.
   - If it is null or unread (a first deployment), refuse, fail closed, naming why. The manager does not pick teams.
   - Add `teamId` to the declared read sets where needed. Tests.
3. **`get_agents_hub` summary.** `summary.account` is gone, replaced by `summary.teamAccounts[]` = {teamId, account}.
   Rows gain `tradingTeamId`.
   - Find every reader of hub `summary.account` (lifecycle_describe.py:158 area, cap_watch, pool, policy, fleet...).
   - With exactly one team, read that team's `account`. With several teams, a single-account figure is ambiguous, so
     refuse or mark it unread (fail closed), never sum silently.
   - Account totals the manager already reads from `get_account_state.account` / `list_user_active_positions` stay as
     they are.
4. **`get_signal_log` / `list_gate_blocks`.** `sourceThoughtLogId` is removed and `thesisReasoning` added.
   - Make sure no code or read set requires `sourceThoughtLogId`.
   - Test fixtures may keep old rows, but the read-set gate must not demand the key.
5. **`get_agent_thought_log` removed (v131).** It is still on the proxy allowlist at `manager/proxy/policy.py:34`.
   Remove it, and any other allowlisted name the 132 surface does not serve; check against `surface_tools`.
   - Consider adding the new read-only `list_agent_market_grid_decisions`, `get_agent_profile` and
     `list_trade_conversations` to the Commander read allowlist only if a skill names them. Otherwise leave them off;
     say which you chose.
6. **Unchanged but recorded.**
   - `get_open_orders` takes an optional `teamId`; omitted reads Main. Keep it omitted while the account has one
     team; note it in the A2 code comment.
   - `get_position_audit_history` (v130) reads own positions only, which is what the manager does.
   - `list_user_active_positions` rows gain `teamId`.
   - `get_account_state` gains `teams[]` and `allTeamsBalance`.
   - Nothing here needs code unless the reads fail on it. Confirm.
7. **Multi-team guard.** Add one fail-closed guard. If `get_account_state.teams` has more than one team, or any
   position's or agent's `teamId` is not Main's, the write pipeline refuses budget/sizing writes (SYNC_LIMITS, pool
   resync, arming) with "multiple trading teams: the pool and cap model is single-wallet". Exposure-reducing writes
   (CLOSE, HALT, TIGHTEN) are never refused by it.
   - The pool and $20 cap assume one wallet. A second team would make margin and headroom figures wrong.
   - Check how the snapshot reads get_account_state today, and keep it to reads already made.
8. **Contract bookkeeping.**
   - Add a fixture `tests/fixtures/2026-10-23-surface-132.0.0/` with the stored 132.0.0 manager_schemas, as Phase A
     did for 129.
   - Add a `test_contract_132` mirroring `test_contract_129`: after this change, acking 132.0.0 must baseline
     cleanly, with no tool the manager calls left unsafe against the code.
   - Read how test_contract_129 works first.
9. **Commander docs.** Update any Hermes SKILL.md / SOUL.md line naming `get_agent_thought_log`, and the
   `sourceThoughtLogId` key, if present.

## Rules

- **Worktree:** create `C:/tmp-bgm-v132` on a new branch `fix/contract-132` from main (`83c62bb` or later).
- **Do not:** merge, push, deploy, ack, call BattleGrid, touch Docker/.env/Hermes profiles, or dispatch subagents.
  Read-only psql (`docker exec battlegrid-manager-postgres-1 psql -U manager -d manager -Atc "..."`) is fine.
- **Off limits:** do not edit `manager/commands/deploy_check.py`, `scripts/gated_deploy.sh` or
  `tests/commands/test_deploy_check.py`. Another change owns them.
- **Write files** with Write/Edit, not heredocs.
- **Commits:** small, each ending with "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>".
- **Tests:** C:/Users/rafae/Documents/GitHub/battlegrid-manager/.venv/Scripts/python.exe -m pytest -q -p
  no:cacheprovider. Run the affected files as you go, then ONE full run (no -x, no -n) at the end.
  `WinError 10055` is host socket exhaustion; rerun that file alone.
- **Report:** write it to C:/Users/rafae/Documents/GitHub/OMEGA/.claude/worktrees/app-development-continuation-8b80ba/v132-report.md.
  Return only: status, commits, the suite count, and concerns.
