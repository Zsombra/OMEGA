# Brief: improve the sentinel's close decisions (2026-10-25)

Read first: C:/Users/rafae/Documents/GitHub/OMEGA/.claude/worktrees/app-development-continuation-8b80ba/close-decisions-report.md.
It grades 19 live closes plus 67 shadow-mode and refused decisions, and it is the evidence for everything below.

The user chose three improvements, in this order. `direction_qualifies` stays as it is (not chosen).

## 1. Fix the R numbers

- **The bug, verified 2026-10-25.** `manager/triage/inputs.py:read_initial_stop` takes the FIRST `SL_PLACED` audit
  event. That event is the platform's wide **hard stop** (`linkedEntryDecision.hardStop`, 2xATR), not the decided stop.
  - On MU (position 151e545f, signal log ae40224d), the decided stopLoss is 859.93 and the hardStop 839.75.
  - `triage_initial_stops` holds 839.75, so R is about 40 instead of 20, and every `r_now` and R-based reading is about
    half its real size.
- **The fix.** R comes from the decision's own stop: `get_signal_log` -> `linkedEntryDecision.stopLoss` (or
  `pipeline.decision.stopLoss`). Its entry is the position's entry fill. This matches the platform's own definition of
  R in `list_agent_trades.quality`: "R = |entry fill − decision stop|".
  - Check whether triage already reads `get_signal_log` for the position (`cycle.py` reads a signal_log evidence). Reuse
    that read and cache it like `triage_initial_stops`: add a column, or a new cache keyed by position.
  - Keep the hard stop available as its own field.
  - `stop_distance_atr` / STOP_PROXIMITY must keep measuring against the **current effective stop** on the exchange (what
    actually stops the trade out). Confirm what it uses today and leave it correct.
  - An unread decided stop is UNDETERMINED (Rule 3). Never fall back silently to the hard stop.
- **Thresholds.** Every rule that reads `r_now` (the thesis −0.5R line, TIME_STOP's r_now>0, rules.py) now sees R
  roughly 2x larger in magnitude. Do NOT silently keep thresholds tuned on the wrong scale.
  - List each one with what it effectively was, measured on the old scale against the new.
  - Set its new value only via the replay (task 2). Where the replay is not ready yet, keep the current EFFECTIVE
    behaviour by rescaling it, and say so.
- Update the dossier and the sentinel skill text where R is explained.
- **Tests:** the MU case, and an unread signal log -> UNDETERMINED.

## 2. Replay tester

- **What it is.** A CLI, `manager replay closes [--rules current|<name>] [--since ...]`, read-only (DB plus at most
  cached platform reads), that scores a close-rule set against history.
  - **Inputs:** every stored dossier (with its metrics) for positions that have since closed, in time order per
    position, plus each position's real outcome from `list_agent_trades` (netR, exit, planOutcome/planR, closeReason,
    closedAt). Cache those trade rows in the DB, or as a fixture file, so replays are repeatable and offline.
  - **Simulation, per position:** walk its dossiers in order. The first dossier where the rule set says CLOSE realizes
    R at that dossier's mark, with the corrected R and fees approximated as in the report. If none says CLOSE, the
    position gets its real outcome. Where the real outcome was itself a sentinel CLOSE the rule set would not make, use
    the trade's planOutcome/planR (state the approximation, and count how many trades rely on it).
  - TIGHTEN/break-even suggestions are scored as: from that dossier on, a stop at entry. If the trade's later path
    (maeR after that time, or the stored later dossiers' marks) touched entry, the result is 0R minus fees; otherwise
    its real outcome. State this approximation.
  - **Output:** per rule set, the total and mean R, the count of closes by reason, wins and losses against the actual
    sentinel, and a per-position table; plus a comparison of two rule sets side by side.
  - Encode the CURRENT rules (from `manager/triage/rules.py` and the sentinel skill as the report quotes them) as rule
    set `current`, and check it reproduces the actual decisions on most dossiers. Report the agreement %.
- **Tests:** a small synthetic history with known answers.

## 3. Smarter time stop (tuned with the replay)

- **The problems** (report section on TIME_STOP):
  - It fires at 3 bars on every timeframe: 1h on 15m agents, but 12–16h on 4h agents.
  - The platform already runs its own time decay: `closedProtection.policy.timeDecayEnabled`, grace 60 min, tightening
    5% every 15 min up to 50% once TP progress is under 25%.
  - It CLOSES winners that could be protected instead.
- **Build a candidate rule set `timestop_v2`:**
  - (a) The bars threshold scales with the agent's strategy timeframe and/or its typical time-to-target. Measure that
    from `list_agent_trades` (closedAt − openedAt for TARGET_FIRST trades) per agent or timeframe.
  - (b) When a time-stop condition is met and r_now > 0 (corrected R), suggest TIGHTEN to break-even (entry ± fees)
    instead of CLOSE, unless the stop is already at or beyond entry.
  - (c) Account for the platform's time decay: read the position's protection policy if the dossier has it (or add it
    from `get_signal_log.closedProtection` / `conditionState`), and do not double-act on a stop the platform is already
    tightening.
- **Tune** the thresholds on the replay. Report `current` against `timestop_v2` (and any variants tried).
- **Do not overfit.** Use few parameters, report the sample size, and prefer round values.
- **Only if v2 beats current on the replay**, write the rule into triage (`rules.py`) and the sentinel skill
  (`hermes/skills/**` in the repo) as a proposal commit, clearly separated. Deploying it is my and the user's call after
  reading the numbers.

## Rules

- **Worktree:** `C:/tmp-bgm-closeimprove`, new branch `feat/close-decisions-v2` from main (`64498bb` or later).
- **Do not:** merge, push, deploy, touch Docker/.env/Hermes profiles, or dispatch subagents.
- **BattleGrid MCP:** READ-ONLY tools only (load via ToolSearch, e.g. `mcp__c330236a-7aee-4d07-ae11-e487c8cbc894__list_agent_trades`, `get_signal_log`). Never a write, stage, commit, close or halt tool.
- **Read-only psql:** `docker exec battlegrid-manager-postgres-1 psql -U manager -d manager -Atc "..."`.
- **Write files** with Write/Edit. Small commits, each ending with "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>".
- **Tests:** C:/Users/rafae/Documents/GitHub/battlegrid-manager/.venv/Scripts/python.exe -m pytest -q -p
  no:cacheprovider. Run the affected files, then ONE full run (no -x, no -n). `WinError 10055` = rerun that file alone.
- **Report:** write it to C:/Users/rafae/Documents/GitHub/OMEGA/.claude/worktrees/app-development-continuation-8b80ba/close-improve-report.md.
  It must include the replay table for `current` against `timestop_v2`.
- **Return only:** status, commits, the suite count, the replay headline numbers, and concerns.
