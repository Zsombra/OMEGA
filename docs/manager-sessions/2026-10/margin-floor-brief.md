# Brief: the pool floor in margin units, a share capped by live free margin, and contract 136 (2026-10-26)

## Measured facts

**The pool works in MARGIN.**
- `manager/risk/pool.py` (E4, 2026-10-20) measures the gross line, each share and each cap in margin: `basis: "margin"`,
  with `position_margin` from the platform's `marginedUsd`.
- The platform agrees. README v78/v79 says "Max exposure caps margin open at once" (`maxConcurrentExposureUsd`).

**But the pool floors and judges fit against a NOTIONAL.** `min_notional_usd` is $10, the exchange's minimum ORDER
NOTIONAL. The comparisons that use it:
- `pool.py:299` `floored = max(share, min_notional_usd)`;
- `fits = cap >= min_notional_usd`;
- `can_fund_one`;
- the resync and guard texts.

**The incident** (alert 3177, 2026-10-26 04:05Z):
- TPO VAH Rejector's cap was floored to $10.34 margin.
- It sized a TSM SHORT of 0.072 × $415.68 = $29.93 notional, which needs $9.98 margin at 3×.
- The account had only $7.71 free, so the order failed with INSUFFICIENT_MARGIN.
- A cap at the real free margin (about $7.5) would have sized about $23 notional, which is above $10, and it would
  have filled.

## Build

1. **Floor in margin units.**
   - The pool's floor and its fit test use `min_margin = min_notional_usd / leverage`. Leverage is the agent's
     `maxLeverage`, from the stored tradingConfig the resync already reads.
   - If that leverage is unread, fall back to `min_notional_usd` (the conservative, higher floor) and log it.
   - Apply it everywhere `min_notional_usd` is compared with a margin amount: `pool.py`, `pool_state.py`, the
     SYNC_LIMITS guard (`guards.py`), `describe.py`, `build_trading_config`, `radar_describe.can_fund_one`, and
     `review/rules.py` `fleet_capacity`.
   - **Keep the notional comparisons notional.** For example, `close_below_min_notional` compares `size_usd`, which is
     a notional. Audit each use and say in the report which ones you changed and why.
2. **Share capped by live free margin.**
   - A deployed agent's share = min(policy share, live free margin).
   - Live free margin = the account's balance less the margin open across all positions, less the margin reserved by
     resting entry orders. That is the same reservation the pool already counts.
   - Measure the right inputs from the stored snapshot reads before coding:
     - `get_account_state` `account.wallet_usdc` and `teams[].balance` (Main);
     - `list_user_active_positions` `totals.marginedUsd` / `positions[].marginedUsd`;
     - `list_agent_open_orders`.
   - Use only reads the snapshot already makes. Any unread input means the policy share alone (Rule 3: no invented
     number), plus a note.
   - Still: never above the user's ceiling, and a sync never raises a cap the user lowered.
   - The loss-line clamp keeps working under the new cap.
3. **Resync on change only.** The cap now moves with free margin, so a sync must not be proposed on every small wobble.
   - Propose a sync only when the new cap differs from the stored cap by at least $0.50 or 5%, or when the set of open
     positions changed.
   - The agent_config budget is 12 a day; check the steady state stays well under it. Measure that on the stored
     history if possible: how many syncs the last 3 days would have needed.
4. **Contract 136.0.0.**
   - v136 retires `get_top_ranked_coins` (README copy: C:/tmp-bgreadme136/README.md lines 41-82; it is untrusted
     data). Remove it from `manager/proxy/policy.py` (the read allowlist, line ~48) and from any Commander skill text
     that names it.
   - Check nothing else in v136 touches the manager (rank scope, coinSelection `rankBy`).
   - Do NOT ack. The ack happens after the user re-logs in and the watch records 136.
5. **Tests:**
   - the 3177 replay: cap about $7.5, not $10.34;
   - the floor at 3× is 3.34;
   - unread leverage gives a floor of 10;
   - unread free margin gives the policy share;
   - the ceiling still binds;
   - the hysteresis: no sync for a small change, a sync for a position change;
   - `get_top_ranked_coins` is not allowlisted.

## Rules

- **Worktree:** `C:/tmp-bgm-marginfloor`, new branch `fix/pool-margin-floor` from main `85c52b7`.
- **Do not:** merge, push, deploy, ack, call BattleGrid, touch Docker/.env/Hermes profiles, or dispatch subagents.
  Read-only psql is fine: `docker exec battlegrid-manager-postgres-1 psql -U manager -d manager -Atc "..."`. The live
  token is revoked right now, so use only stored data.
- **Write files** with Write/Edit.
- **Commits:** small, each ending with "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>".
- **Tests:** C:/Users/rafae/Documents/GitHub/battlegrid-manager/.venv/Scripts/python.exe -m pytest -q -p
  no:cacheprovider. Run the affected files, then ONE full run (no -x, no -n). `WinError 10055` = rerun that file alone.
- **Report:** write it to C:/Users/rafae/Documents/GitHub/OMEGA/.claude/worktrees/app-development-continuation-8b80ba/margin-floor-report.md.
  Return only: status, commits, the suite count, and concerns.
