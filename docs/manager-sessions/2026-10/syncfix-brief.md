# Brief: a SYNC_LIMITS that lowers limits is never refused for fleet exposure; stop the refused-sync churn (2026-10-25)

## Situation (measured live 10-25, battlegrid-manager main e65c609, deployed main-adb1a05)

- **The account.** Wallet $24.90 (policy v5): `max_gross_exposure_usd` 21.16 (notional), `max_portfolio_heat_usd` 1.24.
- **The fleet.** Three agents are deployed, each with a $20 ceiling the user set (CAP_SET_OUTSIDE_MANAGER alerts 1483,
  1723).
- **The manager halts.**
  - **08:05Z.** Action 129 (SYNC_LIMITS, TPO VAH Rejector 5554eb22) was REFUSED with
    `["portfolio heat 1.31747 exceeds max_portfolio_heat_usd 1.24", "gross exposure 65.50417 exceeds
    max_gross_exposure_usd 21.16"]`.
  - **08:20Z.** Actions 134/135 were REFUSED with `"gross exposure 21.681 exceeds max_gross_exposure_usd 21.16"`, while a
    SINGLE 3x COIN position of $21.68 notional (about $7.23 margin) was open.
  - **Every few minutes since.** About 20 more REFUSED SYNC_LIMITS rows (137-157). Two went through, at 09:36Z (150,
    151), when the account was flat.
- **Why this is a bug.**
  - The fleet resync writes each agent's limits DOWN to its pool share (e.g. `maxConcurrentExposureUsd` 10.09 against a
    stored 20). Lowering limits never adds risk.
  - But `manager/risk/guards.py:risk_guard` keeps the whole fleet-wide guard for SYNC_LIMITS. The docstring at ~565-575
    says SYNC_LIMITS and RESUME "increase exposure", so heat/exposure refuse it.
  - The result: the manager cannot shrink an agent's limits exactly when the fleet is over its limits.
  - The pool's RESUME also waits for the resync ("tighten before re-arm", `manager/risk/pool_state.py:pool_requests`), so
    a pool-halted agent stays halted.
- **The other repeating refusal is correct protection; keep it.** VWAP Sentinel's SYNC is REFUSED because the new
  `maxCumulativeDrawdownUsd` of 1.24 is at or below its current drawdown of 1.49 (`breach_on_write`). Only its repetition
  is noise.

## Tasks

1. **A non-raising SYNC_LIMITS is exempt from the fleet checks.**
   - In `risk_guard`, add a SYNC_LIMITS to `exempt_fleet_checks` (heat, gross exposure, leverage, the open-position
     count, the same-direction cap) ONLY when the write raises nothing against the agent's STORED tradingConfig.
   - **Every numeric limit axis it sends must be at or below the stored value:** `maxConcurrentExposureUsd`,
     `maxCumulativeDrawdownUsd`, `maxDailyLossUsd`, `maxLeverage`, `maxDailyTrades`, `maxSlippageBps`, each
     `positionSizePresets` pct, and `minAllocationUsd` / `balanceThresholdUsd` in whichever direction loosens. Read the
     platform docs/schema descriptions in the stored `manager_schemas` (system_state, read-only psql) to decide each
     axis's tighter direction; do not guess. If unsure, treat it as raising.
   - **The stored config:** the latest snapshot's `list_intelligence_agents` read (`pool_state.stored_configs` /
     `AgentRow.trading_config`).
   - **Unread is raising.** An unread stored config, an axis missing from it, or a non-numeric value counts as raising,
     and the full guard applies (Rule 3).
   - **Breach lines stay.** Every other SYNC verdict (`breach_on_write`, the pool-share checks, unread budgets, the
     action cap, the team guard) stays exactly as is. RESUME keeps the whole guard.
   - Record `metrics["risk"]["sync_non_raising"]` (true/false plus the first raising axis) so the decision is
     auditable.
   - Update the docstring.
   - **Tests:**
     - a lowering SYNC passes while gross is over;
     - a SYNC raising any single axis is still refused;
     - an unread stored config is refused;
     - the VWAP drawdown `breach_on_write` refusal still refuses;
     - a 10-25 replay: action 134's params against a stored $20 cap with a $21.68 open position now passes the fleet
       checks.
2. **Stop re-proposing the same refused SYNC.**
   - Find the proposer of fleet resyncs (`manager/scheduler/jobs.py`: fleet resync / `pool_resync_targets`).
   - When the newest SYNC_LIMITS for an agent was REFUSED with the SAME params hash (or idempotency inputs) and the
     same refusal verdicts, do not propose it again for 1 h (constant `REFUSED_SYNC_RETRY_S = 3600`), unless the
     latest snapshot changed what the refusal was about.
   - Keep it simple: a 1 h throttle on an identical refused proposal is enough.
   - Log at INFO once per throttle.
   - Exposure-reducing kinds (HALT, CLOSE, TIGHTEN) are never throttled.
   - **Tests:** an identical refused proposal within 1 h is skipped; after 1 h it is proposed; changed params are
     proposed at once.
3. **Cosmetic, from the 132 review.** `manager/actions/pipeline.py` `is_edit_base` (~941) must require
   `expectedRevision >= 1` (the schema minimum). Add a test.

## Rules

- **Worktree:** `C:/tmp-bgm-syncfix`, new branch `fix/sync-lowering-not-refused` from main (`e65c609`).
- **Do not:** merge, push, deploy, ack, call BattleGrid, touch Docker/.env/Hermes profiles, or dispatch subagents.
  Read-only psql (`docker exec battlegrid-manager-postgres-1 psql -U manager -d manager -Atc "..."`) is fine: the
  refused actions are rows 129-157 in `actions`.
- **Write files** with Write/Edit.
- **Commits:** small, each ending with "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>".
- **Tests:** C:/Users/rafae/Documents/GitHub/battlegrid-manager/.venv/Scripts/python.exe -m pytest -q -p
  no:cacheprovider. Run the affected files, then ONE full run (no -x, no -n) at the end. `WinError 10055` = rerun that
  file alone.
- **Report:** write it to C:/Users/rafae/Documents/GitHub/OMEGA/.claude/worktrees/app-development-continuation-8b80ba/syncfix-report.md.
  Return only: status, commits, the suite count, and concerns.
