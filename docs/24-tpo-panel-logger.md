# 24. The TPO panel logger (forward record of the nine TPO metrics)

Written 2026-09-14 at session wrap. Everything here was measured on the dates given; re-verify
before trusting.

## Why it exists

BattleGrid exposes no TPO history: `get_coin_candles` returns at most the last 100 bars with no
start time, the nine TPO metrics feed zero of the 84 signal modules (doc 22), and the platform
keeps no performance record for them. Every hour not captured is lost. The logger captures; it
does not score. Every threshold in the three TPO strategies (0.25 room to POC, 2.3 prior-value
width, +/-0.25 band, 0.05 break) came from ONE cross-section on 2026-09-11/12. This file's
purpose is to let those thresholds be re-derived from a distribution once one exists.

## What it is

- Script: `scripts/tpo_panel_pull.py`. Read-only by construction: the only tool it may call is
  `preview_strategy_report` (enforced allowlist). It creates, compiles, applies, binds and
  deploys nothing.
- Output: `data/panel/raw/<UTC stamp>.json` (raw response bytes, written before parsing) and
  `data/panel/tpo_panel.jsonl` (one row per coin per capture). Both tracked in git.
- Row shape: `capturedAt, coin, timeframe, category, cohortLimit, rawFile`, then the continuous
  columns `pTpoPOC, pTpoVAH, pTpoVAL, dist_pTpoPOC, dist_pTpoVAH, dist_pTpoVAL,
  pTpoVAL_open_spread, pTpoVAH_open_spread, pTpoVAL_close_spread, pTpoVAH_close_spread,
  pTpoPOC_close_spread, pTpoVAL_low_spread, pTpoVAH_high_spread, pTpoVAH_pTpoVAL_spread,
  tpoPOC_pTpoPOC_spread, tpoVAH_tpoVAL_spread, tpoShape, px_derived`. Column values, never
  condition booleans, so any threshold can be computed later.
- `px_derived` is display-rounded (see the comment in the script): do NOT score forward returns
  off it; use candles.

## Schedule

Windows Task Scheduler task `OMEGA TPO panel`, hourly at :05, run as user `rafae`:
`C:\Python314\python.exe <worktree>\scripts\tpo_panel_pull.py`. It points at the worktree
`.claude/worktrees/authoring-assistant-plan-0eaf0a`; if that worktree is removed the task must
be re-pointed at the merged checkout. Configured "Stop On Battery Mode, No Start On Batteries".
Query with PowerShell (`schtasks /Query /TN "OMEGA TPO panel" /FO LIST /V`); Git Bash mangles
the `/` flags. Local clock is UTC+7, so the task's "10:05 AM" is the 03:05Z capture.

## Record as of 2026-09-14T03:05Z

| | value |
|---|---|
| captures on disk | 34 (1224 rows, 0 unparseable lines) |
| first / last | 2026-09-10T12:21Z (manual) / 2026-09-14T03:05Z |
| first unattended fire | 2026-09-12T03:05:03Z (capture 5) |
| hourly slots since then | 49 |
| slots captured | 30 |
| slots missed | 19: 09-12 05,06,09-12,14,22,23; 09-13 00-04,06,14,16,17,19 (UTC) |
| coins per capture | 36 (CRYPTO, cohortLimit 50) |
| last task result | 0 (queried 2026-09-14 03:29Z) |

The script records its own call failures on stdout (retry once, verbatim error, exit 1) but a
slot at which the task never fired leaves nothing on disk. The cause of the 19 missed hours is
therefore NOT recorded and not known; the machine being asleep and the battery rule are both
mechanisms that would produce exactly this, neither is verified per gap.

## One measurement the record already gives

The 2026-09-14T00:05:02Z capture has `tpoPOC_pTpoPOC_spread`, `tpoVAH_tpoVAL_spread` and
`tpoShape` null for all 36 coins while every `pTpo*` column is populated. That is the
first-hour-of-UTC-session absence of the developing profile (doc 22, memory
`platform-drift-2026-09-09`) observed directly in the logger, not inferred. Any condition on a
developing-TPO column reads FALSE in that hour (measured 8/8 on 54.1.0), and a `required: true`
gate on one blocks every trade, long and short, for the hour. The migration router's
`TPO_HAS_DIRECTION` gate is such a gate; the rotation and breakout books gate only on `pTpo*`
columns and are unaffected.

## Per-session chores

1. `git add data/panel && git commit` the new captures (they accumulate uncommitted).
2. Note the missed slots; do not explain them without evidence.
3. When the record is long enough to matter, compute the distribution of each threshold column
   and compare against the values configured on the platform. Not started; no target sample
   size has been chosen.
