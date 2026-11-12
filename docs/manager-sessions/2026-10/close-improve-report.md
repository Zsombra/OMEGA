# Improving the sentinel's close decisions: R fix, replay tester, time stop (2026-10-26)

Brief: `close-improve-brief.md`. Evidence: `close-decisions-report.md`.
Worktree `C:/tmp-bgm-closeimprove`, branch `feat/close-decisions-v2` from main `64498bb`. Nothing merged, pushed or
deployed; no Docker, `.env` or Hermes profile touched. Platform calls: `list_agent_trades` (2 pages) and
`get_signal_log` (4 logs), all reads. Database: read-only `psql`.

## Status

| Task | Result |
|---|---|
| 1. Fix the R numbers | Done. R is the decided stop's; thresholds rescaled, then `loss_r` set by the replay. |
| 2. Replay tester | Done. `manager replay closes`; `current` reproduces 100% of triage's stored reasons and 87% of the sentinel's recorded outcomes. |
| 3. Smarter time stop | Built and tuned. `timestop_v2` does **not** beat the current time stop once the R fix is applied (+0.01R over 114 positions, 7 better / 12 worse). No proposal commit; see section 3. |

Commits (on `feat/close-decisions-v2`):

| sha | what |
|---|---|
| `8129743` | Triage R from the decided stop, not the hard stop (MU 151e545f: R 20.01, not 40.19) |
| `2306abf` | `manager replay closes`: score close-rule sets against the stored triage history |
| `01cb40e` | THESIS_GATE_FALSE at -0.5 decided R, set by the close-rule replay |

## 1. The R fix

### What changed

- `manager/triage/inputs.py`:
  - `read_initial_stop` still reads the first `SL_PLACED` order. It is now documented as the **hard stop**.
  - New `read_decided_stop` reads the entry decision's `stopLoss` from the tick's one `get_signal_log` read. It tries
    `log.linkedEntryDecision.stopLoss` first, then `log.pipeline.decision.stopLoss`.
  - The tick still makes one `get_signal_log` call per position. The new `fetch_signal_log` serves both the live
    overlay and the decided stop.
  - It is cached per position in the new table `triage_decided_stops`. That is a new table, so `create_all` is its
    whole migration. The table stores the stop, the take-profit, the hard stop (`linkedEntryDecision.hardStop.price`),
    the decision id and the source path.
- It is refused, never guessed, in these cases. Each one is UNDETERMINED, which is Rule 3:
  - no signal log;
  - a failed read;
  - no `stopLoss`;
  - a log whose `pipeline.execution.positionId` names another position;
  - a stop on the winning side of the entry.
- The hard stop is never substituted. `metrics.undetermined` names `decided_stop`, `r_now` stays null, and the row
  cannot be GREEN.
- `manager/triage/rules.py`:
  - `Inputs.initial_stop` became `decided_stop`.
  - `hard_stop` was added as evidence only.
  - `metrics` now carries `r_basis: "decided_stop"`, `decided_stop` and `hard_stop`.
- The dossier:
  - `position` carries `decided_stop`, `hard_stop` and `r_basis`.
  - `platform_reads.decided_stop` is the new read.
- `manager/platform/reads.py`: the `get_signal_log` read set now declares the paths read. Two stored drift-replay
  expectations moved by 4 changes each because of this: `test_reads` and `test_read_only_descriptions` for
  110.13.0 -> 116.0.0.
- **`stop_distance_atr` / STOP_PROXIMITY** were checked and are unchanged. They use `Inputs.current_stop`, which is
  `position.stop` from the inventory, the live exchange stop. On MU the stored rows show it decaying
  839.75 -> 841.73 -> 843.65. A test pins this.
- The sentinel skill (`hermes/skills/battlegrid-sentinel/SKILL.md`) has a new "R: one scale, the platform's" section:
  - R is the decided-stop R, and `position.stop` is the live stop.
  - The live stop starts at the hard stop and decays in, so a stop-out costs more than -1R until it has decayed.
  - Pre-10-26 records quoted R about 2x too small.
  - With an unread decided stop, no R may be improvised.
  - The THESIS_GATE_FALSE and MOMENTUM_STALL lines were restated.

Tests:
- The MU case: entry 879.94, mark 886.18, decided 859.929 gives r_now +0.312, which equals the platform's grossR
  0.312. The hard stop 839.75 gives +0.155. `stop_distance_atr` is measured to the live 843.65.
- The 09-18 DOGE fixture: decided stop 0.08681607 gives r_now 0.504. The hard stop 0.087512 gives 0.298.
- An unreadable signal log (HTTP 502) is UNDETERMINED with the hard stop on hand.
- No stop, another position's log, and a wrong-side stop are each UNDETERMINED.
- The cache serves a later tick whose read fails.
- A missing `SL_PLACED` now costs only the hard stop.

### The thresholds that read R

Ratio of the hard-stop distance to the decided distance, measured on 112 closed positions:
- The hard stop comes from `triage_initial_stops`.
- The decided stop comes from each trade's `|exit - entry| / |grossR|`, which matches MU's `stopLoss` to 0.01.

| agent | n | min | median | max |
|---|---|---|---|---|
| VWAP Sentinel 4h (959739dd) | 25 | 1.35 | 2.02 | 2.17 |
| VWAP Sentinel 15m (2e725543) | 17 | 1.33 | 2.00 | 2.77 |
| TPO VAH Rejector 4h (5554eb22) | 1 | 1.82 | 1.82 | 1.82 |
| PVM 15m (c8ca25c7, retired) | 58 | 0.99 | 1.38 | 3.03 |
| STRUCT Fork B 1h (38e4ddff) | 10 | 1.67 | 1.72 | 1.99 |
| all | 112 | | 1.68 | |

| Threshold | Before (hard-stop R) | What it effectively was, in decided R | Now | How it was set |
|---|---|---|---|---|
| `loss_r` (THESIS_GATE_FALSE `r_now <= -loss_r`) | 0.5 | about -1.0R (median x2.0; -0.67 to -1.39 by position) | **0.5** | Replay (below). Commit `8129743` first rescaled it to 1.0 to keep behaviour; `01cb40e` set 0.5. |
| `profit_r` (MOMENTUM_STALL `r_now >= profit_r`) | 1.0 | about +2.0R | **2.0** | Rescaled only. MOMENTUM_STALL never fired in the 114 replayed positions, so there is nothing to tune on. |
| TIME_STOP `r_now > 0` / `<= 0` zones | sign only | unchanged (the sign does not depend on the scale) | unchanged | n/a |
| `time_stop_bars` 3, `tp_progress_pct` 25 | not R | unchanged | unchanged | n/a |
| `stop_atr` 0.5 (STOP_PROXIMITY) | ATR to the live stop | unchanged | unchanged | n/a |
| Skill text "-0.5R" and "beyond 1R" | hard R | -1.0R and +2.0R | "-0.5R (decided)" and "beyond 2R" | Skill updated |

The replay grid for `loss_r` on the decided scale:
- All other rules are as live.
- Every row is compared with `current`, the live rules on hard-stop R.
- There are 114 positions. The two halves are opened before and after 10-08 (59 / 55).

| loss_r (decided R) | total R | vs current | halves | better / worse | bootstrap 90% | slippage 0 / 0.10R |
|---|---|---|---|---|---|---|
| `current` (0.5 hard = about 1.0 decided) | -36.05 | 0 | | | | -33.60 / -38.50 |
| 1.25 | -35.27 | +0.78 | +1.43 / -0.65 | 5 / 2 | [-2.31, +3.69] | -33.02 / -37.52 |
| 1.0 (old line rescaled) | -35.03 | +1.02 | +1.43 / -0.41 | 4 / 1 | [-2.00, +3.78] | -32.68 / -37.38 |
| 0.75 | -34.65 | +1.40 | +0.40 / +1.00 | 4 / 1 | [+0.24, +2.76] | -32.25 / -37.05 |
| **0.5** | **-32.76** | **+3.28** | +0.42 / +2.86 | 8 / 1 | [+1.24, +5.66] | -30.16 / -35.36 |

- 0.5 wins in both halves and on the 4h positions too (26 of them: -2.42R against -4.07R for `current`).
- The one worse case is PUMP 801aee57: the real close was at -0.44R, and the replay closes at an earlier mark at
  -1.01R.
- Why "1.0 vs current" is not zero: the rescale uses the median ratio, and each position has its own ratio.

## 2. The replay tester

`manager replay closes [--rules current,timestop_v2] [--since ISO] [--history FILE] [--trades FILE] [--slippage R]
[--out FILE]`. Two helper commands:
- `manager replay fetch-trades --since ISO --out FILE`. It calls `list_agent_trades` only.
- `manager replay export-history --out FILE`. It writes the database tables to JSON, so a replay runs without the
  database.

The code is in `manager/replay/`: `trades.py`, `history.py`, `rules.py` and `simulate.py`. The tests are in
`tests/replay/test_replay.py`: 19 tests on a synthetic history whose answers were worked out by hand.

### Inputs

- **History.** Every triage row since 09-19 (5,442 rows, 117 positions) is joined to the inventory snapshot that the
  tick read: its mark, its live stop and its take-profit.
  - The decisions and the CLOSE actions come along with it.
  - This uses the triage rows rather than only the 220 dossiers. Rows run every 5 min for every colour, while dossiers
    exist only for an AMBER with new reasons. The dossier rows are included, since each dossier has its triage row.
  - For this report the tables were exported read-only with `psql`, in the `export-history` JSON shape, because the
    Postgres port is not published to the host.
- **Outcomes.** `tests/fixtures/2026-10-26-replay/trades.json` holds 128 `list_agent_trades` rows since 09-19.
  - They were read 2026-10-26 between 04:15Z and 04:35Z.
  - The count, the sum of netPnl (-$7.49) and the mean netR (0.389) match the served `summary` and `resultSummary`.
  - 112 decided stops are derived from `grossR`. 2 came from `get_signal_log` (PURR c83dd3c9 and 5ea1c04f, where
    |grossR| < 0.05).
- **Sample.** 114 positions are replayed. Three were excluded because the trade was outside the cache (still open).
  - By agent: 58 PVM 15m, 25 V4h, 19 VS 15m, 10 Fork B 1h, 1 BRK 1h, 1 TPO 4h.
  - By timeframe: 77 at 15m, 26 at 4h, 11 at 1h.
  - 20 of them were closed by a manager CLOSE.

### Simulation, and its approximations

The same text is in `manager/replay/simulate.py`.

- **RED steps are skipped.** STALE_PRICING, CONTRACT_DRIFT and budget lines produce no dossier.
- **CLOSE** at a step realizes `r_now` at that step's mark, in decided R. Two costs come off it:
  - the trade's own round-trip `feesR`;
  - **0.05R latency**, the 5 to 10 min from dossier to fill.

  The sensitivity at 0 and at 0.10R is in the tables. The ranking never changes. When the step carries the
  dossier of the sentinel's own executed CLOSE, the trade's real netR is used.
- **No action** means the real netR. If the real exit was a manager CLOSE that the rule set would not have made,
  the trade's **planR - feesR** stands in for it. This is an approximation: planR scores the decided levels, while
  the live stop starts wider. It is counted per rule set, and it is used 4 times for `current` and 2 for
  `timestop_v2`.
- **Break-even TIGHTEN** arms a stop at entry from that step on. It scores **0R - feesR** if a later stored mark is
  at or through entry, or if the hold outcome ends at or through entry (a losing exit, or a STOP_FIRST plan).
  Otherwise the hold outcome stands. Approximation: the marks are 5 min apart, so a touch between two marks is
  missed. `timestop_v2` relies on this 4 times (2 filled, 2 kept).
- **The rules** recompute the AMBER conditions from each row's stored readings. `r_now` is computed on the rule
  set's own basis, and bars on its own threshold. The outcome follows the skill, made deterministic:
  - THESIS_GATE_FALSE and STOP_PROXIMITY are CLOSE.
  - TIME_STOP follows the skill's fixed zones.
  - REGIME_FLIP is CLOSE when r_now <= 0.
  - MOMENTUM_STALL is TIGHTEN.

### How faithful `current` is

- **Stored reasons.** On every non-RED step, `current` reproduces the AMBER reasons triage stored on **2,329 of
  2,329** steps (EVIDENCE_UNDETERMINED and TPO_GATE_FALSE are left out of both sides).
- **Recorded outcomes.** It matches the sentinel's recorded outcome on **95 of 109 decided dossiers (87%)**. The 14
  mismatches:

| Count | Recorded | Replay |
|---|---|---|
| 4 | TIGHTEN on TIME_STOP (shadow, 09-2x) | CLOSE |
| 3 | HOLD on REGIME_FLIP | CLOSE (r <= 0) |
| 3 | CLOSE as "THESIS_GATE_FALSE" though triage had not fired it (#85, #86-style overrides) | HOLD |
| 2 | HOLD on STOP_PROXIMITY | CLOSE |
| 1 | CLOSE on TIME_STOP | HOLD |
| 1 | CLOSE on REGIME_FLIP | HOLD |

### Headline: `current` against the real outcomes

| rule set | total R | mean R | actual total R | better / worse / same vs actual |
|---|---|---|---|---|
| `current` (live rules, hard R) | -36.05 | -0.316 | -37.24 | 34 / 18 / 62 |
| `current_fixed` (decided R, loss_r 0.5) | -32.76 | -0.287 | -37.24 | |

- The gap between `current` and the real outcomes (+1.2R) is mostly the 22 refused and 45 shadow CLOSE decisions,
  which the replay executes.
- These are loss-making strategies. -0.32R per position is the strategy, not the close rule.

## 3. The time stop (`timestop_v2`)

Measured from `list_agent_trades`: minutes to target on TARGET_FIRST plans (`planOutcome.firstHitAfterMinutes`).

| timeframe | trades | median minutes | median bars |
|---|---|---|---|
| 15m | 21 | 152 | 10.1 |
| 1h | 2 | 338 | 5.6 |
| 4h | 4 | 204 | 0.85 |

`timestop_v2` is `current_fixed` with TIME_STOP replaced by three parts, each a knob of `TimeStop`:
- **(a)** The bar count is k x the timeframe's median bars-to-target, rounded. With k = 1.5 that gives 15m: 15 bars,
  1h: 8 bars and 4h: 1 bar.
- **(b)** When r_now > 0 and the direction no longer qualifies, it TIGHTENs to break-even instead of CLOSE, unless
  the live stop is already at or beyond entry. That case is HOLD. `direction_qualifies` is kept as it is, per the
  brief.
- **(c)** When r_now <= 0, it HOLDs while the platform's TIME_DECAY is still pulling the live stop in. That is when
  the live stop has left the hard stop but is still wider than both the decided stop and the 50% floor.
  - The open position's protection policy is not served live: `closedProtection` exists only after close, and
    `conditionState` is the exit rules.
  - So the decay is inferred from the live stop against the hard and decided stops. The policy that every log shows
    after close was the same: grace 60 min, 5% per 15 min, 50% max, stale below 25% TP progress.

Every variant tried, compared with `current_fixed` (114 positions, loss_r 0.5 in all of them):

| variant | total R | vs current_fixed | halves | better / worse | bootstrap 90% |
|---|---|---|---|---|---|
| `current_fixed` (3 bars, CLOSE) | -32.76 | 0 | | | |
| **`timestop_v2`** (a k=1.5 + b + c) | -32.76 | **+0.01** | -3.11 / +3.12 | 7 / 12 | [-7.17, +8.38] |
| a, k=1 | -31.11 | +1.66 | -1.66 / +3.32 | 8 / 11 | [-5.49, +9.79] |
| a+b, k=1 | -31.84 | +0.93 | -2.42 / +3.35 | 7 / 12 | [-6.14, +9.28] |
| a+b+c, k=1 | -32.07 | +0.70 | -2.42 / +3.12 | 7 / 12 | [-6.23, +8.92] |
| a, k=1.5 | -31.79 | +0.98 | -2.35 / +3.32 | 8 / 11 | [-6.40, +9.32] |
| a+b, k=1.5 | -32.53 | +0.24 | -3.11 / +3.35 | 7 / 12 | [-7.00, +8.74] |
| a, k=2 | -34.60 | -1.83 | -2.67 / +0.83 | 4 / 12 | [-8.49, +6.22] |
| a+b(+c), k=2 | -35.09 | -2.32 | -3.11 / +0.79 | 4 / 12 | [-9.13, +5.83] |
| 3 bars + b | -30.57 | +2.19 | +2.34 / -0.15 | 1 / 6 | [-2.49, +9.89] |
| 3 bars + c | -32.76 | 0.00 | | 0 / 0 | |
| 4h 1 bar, 15m/1h 3 bars | -30.38 | +2.39 | 0.00 / +2.39 | 3 / 1 | [0.00, +5.32] |
| 2 bars everywhere | -29.31 | +3.45 | +0.45 / +3.00 | 9 / 4 | [+0.64, +6.81] |
| 4 bars everywhere | -33.72 | -0.95 | -0.77 / -0.18 | 4 / 7 | [-2.43, +0.39] |
| no time stop | -35.09 | -2.32 | -3.11 / +0.79 | 4 / 12 | [-9.13, +5.83] |

Per timeframe (total R; `timestop_v2` against `current_fixed`):

| tf | n | actual | `current` | `current_fixed` | `timestop_v2` |
|---|---|---|---|---|---|
| 15m | 77 | -32.49 | -32.60 | -31.37 | -31.64 |
| 1h | 11 | -2.07 | +0.62 | +1.02 | -0.89 |
| 4h | 26 | -2.68 | -4.07 | -2.42 | -0.23 |

**Verdict: `timestop_v2` does not beat the current time stop, so nothing was written into `rules.py` or the skill.**
- Against `current` it shows +3.29R. All of that is the R fix and `loss_r` 0.5: `current_fixed` alone is +3.28R.
- Against `current_fixed` it is +0.01R, 7 better and 12 worse, and the two halves cancel out (-3.1 / +3.1).
- Part by part:
  - **(a)** Scaling to time-to-target loosens 15m from 3 bars to 15 bars. On these loss-making 15m strategies that
    costs as much as it gains elsewhere. k = 2 is clearly worse.
  - **(b)** Break-even instead of CLOSE gives +2.19R only at 3 bars, and it is one trade: LINK c09545ae
    (+3.78R, a +4.38R TP that a CLOSE at +0.6R would have cut). Without that trade it is about -1.6R, with 1 better
    and 6 worse. A break-even stop on these strategies usually gets filled.
  - **(c)** It never changed an outcome. At 3 or more bars, TIME_DECAY has finished by the time TIME_STOP fires:
    grace 1 h plus 10 steps of 15 min, so 3.5 h, against 45 min for 3 x 15m.

What the replay does support, written up as findings and not as rules:
- **"2 bars everywhere"** (+3.45R, positive in both halves, 9 / 4, CI excludes 0) and **"4h at 1 bar"** (+2.39R,
  3 / 1) are better.
  - Both mean closing sooner. On strategies that lose about 0.3R per trade, any earlier exit near entry looks good.
  - That is the evidence report's caution, and the brief's "do not overfit": it is not a smarter time stop.
  - The 4h evidence is 26 positions and 4 TARGET_FIRST trades.
- If you want to act on one, "4h at 1 bar" matches the measured time-to-target for the only live agents (V4h, TPO).
  It is your and the user's call.

## Full suite

5354 passed, 5 skipped, 0 failed (one full run, 712 s, at `01cb40e`).

## Concerns

1. **Not deployed.** Nothing takes effect until a merge and a `gated_deploy.sh` run.
   - After deploying, the first tick of each open position reads its decided stop from `get_signal_log` and caches
     it.
   - r_now values in rows and dossiers jump to about 2x their old magnitude. THESIS_GATE_FALSE then fires at -0.5
     decided R, which is about -0.25 on the old scale, so it will fire much more often: 22 closes against 13 in the
     replay.
   - Decision rationales from before the deploy are on the old scale.
2. **Rule 3 makes the beat stricter.** A position without a signal log, or with a failed `get_signal_log` read, now
   has no R. It is AMBER EVIDENCE_UNDETERMINED with a dossier and never GREEN, and the tick's `ok` is false.
   - Before, the audit history's `SL_PLACED` stood in for it.
   - Every currently open position has a signalLogId.
3. **The eval harness still measures excursions on the hard stop.** `manager/eval/score.py` and `eval_excursions` read
   `triage_initial_stops`. I left them unchanged, as outside the brief, so eval mfeR and maeR are on the old,
   about 2x smaller, scale.
   - `risk/state.py` `OpenPosition.initial_stop` is also the hard stop. No guard reads it.
4. **The replay is approximate and the sample is small.**
   - 114 positions, 77 of them on two retired 15m agents that lose money.
   - Fill latency is fixed at 0.05R.
   - The plan stands in for 2 to 4 trades, and break-even touches are judged from 5-min marks.
   - The LLM sentinel matches the deterministic `current` 87% of the time, not always.
   - Treat the threshold numbers as directional. `loss_r` 0.5 is the one result that holds across both halves, both
     slippage bounds and the bootstrap.
5. **The live skill copy.** I updated only the repo's `hermes/skills/battlegrid-sentinel/SKILL.md`. The live Hermes
   profile copy is untouched, as instructed.
6. **Line endings.** Some edit passes wrote CRLF in the working tree. The commits are LF, since git normalized them
   and the diff stat is clean, but `git status` may list those files until the index is refreshed.

## The replay table: `current` against `timestop_v2`

Output of `manager replay closes --rules current,timestop_v2`. The same output with `--rules current_fixed,timestop_v2`
ends: "timestop_v2 minus current_fixed: total +0.01R over 114 positions; 7 better, 12 worse, 95 same".

#### current

| positions | total R | mean R | actual total R | better / worse / same vs actual | plan-substituted |
|---|---|---|---|---|---|
| 114 | -36.05 | -0.316 | -37.24 | 34 / 18 / 62 | 4 |

Closes by reason: REGIME_FLIP 11, STOP_PROXIMITY 19, THESIS_GATE_FALSE 13, TIME_STOP 18. Break-even tightens by reason: none.

#### timestop_v2

| positions | total R | mean R | actual total R | better / worse / same vs actual | plan-substituted |
|---|---|---|---|---|---|
| 114 | -32.76 | -0.287 | -37.24 | 36 / 14 / 64 | 2 |

Closes by reason: REGIME_FLIP 12, STOP_PROXIMITY 17, THESIS_GATE_FALSE 25, TIME_STOP 1. Break-even tightens by reason: TIME_STOP 4.

### current vs timestop_v2

| position | coin | tf | actual R | current R (action, basis) | timestop_v2 R (action, basis) | timestop_v2 - current |
|---|---|---|---|---|---|---|
| 94e4de58 | DOGE | 1h | +0.037 | -0.178 (CLOSE REGIME_FLIP, mark) | -0.178 (CLOSE REGIME_FLIP, mark) | +0.000 |
| af1e16a3 | SOL | 1h | -0.985 | -0.003 (CLOSE TIME_STOP, mark) | -0.718 (CLOSE STOP_PROXIMITY, mark) | -0.714 |
| 801828cb | FARTCOIN | 15m | +0.219 | +0.745 (CLOSE STOP_PROXIMITY, mark) | +0.745 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| ad0ff556 | LINK | 15m | -1.192 | -1.192 (HOLD, real) | -1.192 (HOLD, real) | +0.000 |
| b75d57c0 | DOGE | 1h | +1.929 | +1.929 (HOLD, real) | +1.929 (HOLD, real) | +0.000 |
| c5e408fa | AAVE | 15m | -0.384 | -0.384 (HOLD, real) | -0.384 (HOLD, real) | +0.000 |
| d6c3319e | AAVE | 15m | -0.275 | -0.275 (HOLD, real) | -0.275 (HOLD, real) | +0.000 |
| 4a99a72d | AAVE | 15m | -0.983 | -0.983 (HOLD, real) | -0.983 (HOLD, real) | +0.000 |
| 189819a8 | AAVE | 15m | -1.367 | -1.367 (HOLD, real) | -1.367 (HOLD, real) | +0.000 |
| 6ad00578 | AAVE | 15m | -1.647 | -1.647 (HOLD, real) | -1.647 (HOLD, real) | +0.000 |
| 8e0f88a9 | LINK | 15m | +0.169 | +0.397 (CLOSE STOP_PROXIMITY, mark) | +0.397 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| 2a708aa4 | ENA | 15m | -1.770 | -1.770 (HOLD, real) | -1.770 (HOLD, real) | +0.000 |
| 133eb239 | DOGE | 1h | -1.285 | -1.285 (HOLD, real) | -1.285 (HOLD, real) | +0.000 |
| c09545ae | LINK | 15m | +4.380 | +0.596 (CLOSE TIME_STOP, mark) | +4.380 (HOLD, real) | +3.784 |
| 51e3115d | BTC | 1h | +0.473 | +0.473 (HOLD, real) | +0.473 (HOLD, real) | +0.000 |
| 89c0aeb6 | ZEC | 15m | +3.400 | +0.006 (CLOSE TIME_STOP, mark) | -1.033 (CLOSE STOP_PROXIMITY, mark) | -1.039 |
| f697c54b | LINK | 15m | -1.297 | +0.065 (CLOSE TIME_STOP, mark) | -1.088 (CLOSE STOP_PROXIMITY, mark) | -1.153 |
| 8c4c8b1f | SOL | 1h | +1.125 | +1.125 (HOLD, real) | +1.125 (HOLD, real) | +0.000 |
| 12c6ab5e | SOL | 1h | -0.903 | -0.110 (CLOSE TIME_STOP, mark) | -0.858 (CLOSE STOP_PROXIMITY, mark) | -0.748 |
| 3cb99d25 | SUI | 15m | -1.408 | -1.426 (CLOSE STOP_PROXIMITY, mark) | -1.426 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| 30ca95f2 | XRP | 15m | +0.054 | +0.421 (CLOSE STOP_PROXIMITY, mark) | +0.421 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| 53c05211 | UNI | 15m | -0.874 | -0.292 (CLOSE REGIME_FLIP, mark) | -0.292 (CLOSE REGIME_FLIP, mark) | +0.000 |
| 9ea2827e | SOL | 1h | -1.202 | -1.061 (CLOSE THESIS_GATE_FALSE, mark) | -0.667 (CLOSE THESIS_GATE_FALSE, mark) | +0.393 |
| fadd5591 | SOL | 1h | +0.039 | +0.697 (CLOSE TIME_STOP, mark) | +0.039 (HOLD, real) | -0.658 |
| fd0cff15 | SOL | 1h | -0.001 | -0.218 (CLOSE TIME_STOP, mark) | -0.001 (HOLD, real) | +0.217 |
| 6b7ec0a3 | UNI | 15m | +0.266 | +0.266 (HOLD, real) | +0.266 (HOLD, real) | +0.000 |
| c1fc37bd | UNI | 15m | -1.205 | -1.205 (HOLD, real) | -1.205 (HOLD, real) | +0.000 |
| 75f12702 | AAVE | 1h | -1.297 | -0.745 (CLOSE THESIS_GATE_FALSE, mark) | -0.745 (CLOSE THESIS_GATE_FALSE, mark) | +0.000 |
| 71827ac6 | UNI | 15m | -0.970 | +0.184 (CLOSE TIME_STOP, mark) | -0.715 (CLOSE THESIS_GATE_FALSE, mark) | -0.898 |
| 42caa8a6 | SUI | 15m | -1.363 | -0.630 (CLOSE TIME_STOP, mark) | -0.777 (CLOSE THESIS_GATE_FALSE, mark) | -0.147 |
| 3d1f9d02 | PEPE | 15m | -1.036 | -0.284 (CLOSE REGIME_FLIP, mark) | -0.284 (CLOSE REGIME_FLIP, mark) | +0.000 |
| be2f4de1 | XRP | 15m | -1.286 | -0.592 (CLOSE TIME_STOP, mark) | -0.778 (CLOSE THESIS_GATE_FALSE, mark) | -0.186 |
| de5ed1b2 | UNI | 15m | -1.285 | -0.189 (CLOSE REGIME_FLIP, mark) | -0.189 (CLOSE REGIME_FLIP, mark) | +0.000 |
| 8930bbd8 | PEPE | 15m | -1.381 | -0.515 (CLOSE TIME_STOP, mark) | -1.381 (HOLD, real) | -0.866 |
| 5f954a78 | XRP | 15m | -1.509 | -1.073 (CLOSE THESIS_GATE_FALSE, mark) | -0.902 (CLOSE THESIS_GATE_FALSE, mark) | +0.171 |
| 5ea69360 | XRP | 15m | +0.079 | +0.079 (HOLD, real) | +0.079 (HOLD, real) | +0.000 |
| 71b66641 | XRP | 15m | -1.525 | -1.525 (HOLD, real) | -1.525 (HOLD, real) | +0.000 |
| 63d40c61 | UNI | 15m | -1.153 | -1.153 (HOLD, real) | -1.153 (HOLD, real) | +0.000 |
| 59c19c4c | PEPE | 15m | +0.419 | +0.419 (HOLD, real) | +0.419 (HOLD, real) | +0.000 |
| 0817a55c | PEPE | 15m | +0.031 | +0.031 (HOLD, real) | +0.031 (HOLD, real) | +0.000 |
| 9cacb1b2 | PEPE | 15m | -0.606 | -0.606 (HOLD, real) | -0.606 (HOLD, real) | +0.000 |
| 2429547f | PEPE | 15m | +0.741 | +0.741 (HOLD, real) | +0.741 (HOLD, real) | +0.000 |
| 04ea007d | PEPE | 15m | +0.819 | -1.102 (HOLD, plan) | -1.102 (HOLD, plan) | +0.000 |
| 84884491 | SUI | 15m | -1.430 | -1.078 (CLOSE REGIME_FLIP, mark) | -1.078 (CLOSE REGIME_FLIP, mark) | +0.000 |
| c0b83141 | SUI | 15m | +0.098 | -0.605 (CLOSE REGIME_FLIP, mark) | -0.605 (CLOSE REGIME_FLIP, mark) | +0.000 |
| 9b80c217 | SUI | 15m | -1.444 | -1.444 (HOLD, real) | -1.444 (HOLD, real) | +0.000 |
| 913d11f0 | SUI | 15m | -1.360 | -0.838 (CLOSE REGIME_FLIP, mark) | -0.838 (CLOSE REGIME_FLIP, mark) | +0.000 |
| 94731ebc | SUI | 15m | +2.258 | +2.258 (HOLD, real) | +2.258 (HOLD, real) | +0.000 |
| 77d8bbe1 | UNI | 15m | +0.353 | -0.548 (CLOSE TIME_STOP, mark) | -0.736 (CLOSE THESIS_GATE_FALSE, mark) | -0.188 |
| 544156e6 | SUI | 15m | -1.289 | -1.289 (HOLD, real) | -1.289 (HOLD, real) | +0.000 |
| 7ae40513 | UNI | 15m | +0.143 | +0.957 (CLOSE STOP_PROXIMITY, mark) | +0.957 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| 390ee0cb | PEPE | 15m | +0.246 | -0.306 (CLOSE TIME_STOP, mark) | -0.967 (CLOSE THESIS_GATE_FALSE, mark) | -0.661 |
| 681ce15b | UNI | 15m | -0.334 | -0.334 (HOLD, real) | -0.334 (HOLD, real) | +0.000 |
| e0730f7f | PEPE | 15m | +0.050 | +0.050 (HOLD, real) | +0.050 (HOLD, real) | +0.000 |
| d667b5f2 | XRP | 15m | +0.689 | +0.689 (HOLD, real) | +0.689 (HOLD, real) | +0.000 |
| 93d8430b | LINK | 15m | -0.842 | -0.842 (HOLD, real) | -0.842 (HOLD, real) | +0.000 |
| dc3da87e | SUI | 15m | +0.030 | +0.030 (HOLD, real) | +0.030 (HOLD, real) | +0.000 |
| a03be199 | SUI | 15m | +0.055 | +0.055 (HOLD, real) | +0.055 (HOLD, real) | +0.000 |
| a08424a2 | UNI | 15m | -1.078 | -1.078 (HOLD, real) | -1.078 (HOLD, real) | +0.000 |
| 955e197e | SUI | 15m | -1.059 | -1.059 (HOLD, real) | -1.059 (HOLD, real) | +0.000 |
| 56618acf | XRP | 15m | -1.166 | -1.166 (HOLD, real) | -1.166 (HOLD, real) | +0.000 |
| 3e10a635 | XRP | 15m | +0.729 | -0.235 (CLOSE TIME_STOP, mark) | +0.521 (CLOSE STOP_PROXIMITY, mark) | +0.756 |
| ffd36cd3 | PEPE | 15m | -1.081 | -0.463 (CLOSE REGIME_FLIP, mark) | -0.463 (CLOSE REGIME_FLIP, mark) | +0.000 |
| b53c1b2e | LINK | 15m | +2.833 | +2.833 (HOLD, real) | +2.833 (HOLD, real) | +0.000 |
| ead373bf | PEPE | 15m | +0.077 | +0.286 (CLOSE STOP_PROXIMITY, mark) | +0.286 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| 6f6aa405 | XRP | 15m | +0.300 | +0.300 (HOLD, real) | +0.300 (HOLD, real) | +0.000 |
| c25bfbdf | LINK | 15m | -1.384 | -1.631 (CLOSE TIME_STOP, mark) | -1.384 (HOLD, real) | +0.247 |
| 65fa61c3 | XRP | 15m | -1.093 | -0.864 (CLOSE THESIS_GATE_FALSE, mark) | -0.822 (CLOSE THESIS_GATE_FALSE, mark) | +0.042 |
| 84726d0f | XRP | 15m | -1.052 | -0.298 (CLOSE TIME_STOP, mark) | -0.366 (CLOSE REGIME_FLIP, mark) | -0.068 |
| 5ea1c04f | PURR | 15m | -0.132 | -0.264 (CLOSE REGIME_FLIP, mark) | -0.264 (CLOSE REGIME_FLIP, mark) | +0.000 |
| 8df49382 | SMSN | 4h | -0.774 | -1.035 (HOLD, plan) | -0.709 (CLOSE THESIS_GATE_FALSE, mark) | +0.326 |
| dd0121ed | INTC | 4h | +0.235 | -1.131 (HOLD, plan) | -1.131 (HOLD, plan) | +0.000 |
| fbd6b742 | PURR | 15m | -1.458 | -1.458 (HOLD, real) | -1.458 (HOLD, real) | +0.000 |
| 75b89a40 | HYPE | 15m | -1.404 | -1.404 (HOLD, real) | -1.404 (HOLD, real) | +0.000 |
| c0970a97 | MOODENG | 15m | +0.059 | +0.059 (CLOSE REGIME_FLIP, actual_close) | +0.059 (CLOSE REGIME_FLIP, actual_close) | +0.000 |
| 221423bb | HYPE | 15m | -1.188 | -1.372 (CLOSE THESIS_GATE_FALSE, mark) | -0.931 (CLOSE THESIS_GATE_FALSE, mark) | +0.441 |
| adb87395 | COIN | 4h | +0.190 | -1.040 (HOLD, plan) | -0.040 (TIGHTEN TIME_STOP, be_hit) | +1.000 |
| 2ee271f7 | HYPE | 15m | -1.428 | -1.428 (HOLD, real) | -1.428 (HOLD, real) | +0.000 |
| 801aee57 | PUMP | 15m | -0.439 | -1.014 (CLOSE THESIS_GATE_FALSE, mark) | -1.014 (CLOSE THESIS_GATE_FALSE, mark) | +0.000 |
| 9a477af9 | PURR | 15m | -1.571 | -1.512 (CLOSE THESIS_GATE_FALSE, mark) | -0.786 (CLOSE THESIS_GATE_FALSE, mark) | +0.725 |
| 7d51e8c2 | CRCL | 4h | -0.724 | -0.724 (CLOSE STOP_PROXIMITY, actual_close) | -0.667 (CLOSE THESIS_GATE_FALSE, mark) | +0.057 |
| 885816bf | MET | 15m | +0.556 | +0.770 (CLOSE STOP_PROXIMITY, mark) | +0.770 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| a92f85b0 | MET | 15m | +0.072 | +0.598 (CLOSE STOP_PROXIMITY, mark) | +0.598 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| bdc2b7cc | PURR | 15m | -2.079 | -2.079 (HOLD, real) | -2.079 (HOLD, real) | +0.000 |
| 35734a4f | PUMP | 15m | +0.752 | +0.752 (HOLD, real) | +0.752 (HOLD, real) | +0.000 |
| b5a02315 | CRCL | 4h | +0.205 | +0.523 (CLOSE STOP_PROXIMITY, mark) | +0.523 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| cca900bf | MET | 15m | +0.425 | +0.652 (CLOSE STOP_PROXIMITY, mark) | +0.652 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| dd775b1b | APT | 15m | -0.563 | -0.854 (CLOSE THESIS_GATE_FALSE, mark) | -0.854 (CLOSE THESIS_GATE_FALSE, mark) | +0.000 |
| 4c7b384b | MET | 15m | -2.328 | -2.474 (CLOSE THESIS_GATE_FALSE, mark) | -2.474 (CLOSE THESIS_GATE_FALSE, mark) | +0.000 |
| 57b4ee50 | HYPE | 15m | +2.107 | +2.107 (HOLD, real) | +2.107 (HOLD, real) | +0.000 |
| 5133bd21 | MOODENG | 15m | -1.972 | -1.585 (CLOSE THESIS_GATE_FALSE, mark) | -1.585 (CLOSE THESIS_GATE_FALSE, mark) | +0.000 |
| 94720e54 | ETH | 15m | -1.091 | -1.091 (CLOSE THESIS_GATE_FALSE, actual_close) | -1.091 (CLOSE THESIS_GATE_FALSE, actual_close) | +0.000 |
| c83dd3c9 | PURR | 15m | -0.122 | -0.122 (CLOSE REGIME_FLIP, actual_close) | -0.122 (CLOSE REGIME_FLIP, actual_close) | +0.000 |
| 91b1fc23 | USAR | 4h | +2.931 | +2.931 (HOLD, real) | +2.931 (HOLD, real) | +0.000 |
| 030ac65c | SNDK | 4h | -0.812 | -0.812 (CLOSE STOP_PROXIMITY, actual_close) | -0.812 (CLOSE THESIS_GATE_FALSE, actual_close) | +0.000 |
| 2b973907 | INTC | 4h | -1.580 | -1.243 (CLOSE THESIS_GATE_FALSE, mark) | -0.593 (CLOSE THESIS_GATE_FALSE, mark) | +0.649 |
| 4bae957c | HIMS | 4h | -1.768 | -1.345 (CLOSE THESIS_GATE_FALSE, mark) | -0.675 (CLOSE THESIS_GATE_FALSE, mark) | +0.669 |
| d4fef250 | COIN | 4h | +0.297 | +0.437 (CLOSE STOP_PROXIMITY, mark) | +0.437 (CLOSE STOP_PROXIMITY, mark) | +0.000 |
| f7ea999c | INTC | 4h | -0.428 | -0.428 (CLOSE STOP_PROXIMITY, actual_close) | -0.031 (TIGHTEN TIME_STOP, be_hit) | +0.397 |
| 1465216f | HIMS | 4h | -0.387 | -0.387 (CLOSE STOP_PROXIMITY, actual_close) | -0.387 (CLOSE THESIS_GATE_FALSE, actual_close) | +0.000 |
| f6fae8f8 | COIN | 4h | -0.432 | -0.432 (CLOSE STOP_PROXIMITY, actual_close) | -0.432 (CLOSE STOP_PROXIMITY, actual_close) | +0.000 |
| da513516 | CRCL | 4h | -0.868 | -0.625 (CLOSE STOP_PROXIMITY, mark) | -0.625 (CLOSE THESIS_GATE_FALSE, mark) | +0.000 |
| 2f71cc42 | INTC | 4h | +2.488 | +2.488 (HOLD, real) | +2.488 (HOLD, real) | +0.000 |
| 15f083ed | COIN | 4h | +0.238 | +0.238 (HOLD, real) | +0.238 (HOLD, real) | +0.000 |
| be53760c | INTC | 4h | +0.800 | +0.800 (HOLD, real) | +0.800 (HOLD, real) | +0.000 |
| aede2c90 | COIN | 4h | +0.034 | +0.034 (HOLD, real) | +0.034 (HOLD, real) | +0.000 |
| acea7616 | HIMS | 4h | -1.402 | -1.402 (HOLD, real) | -1.402 (HOLD, real) | +0.000 |
| 699ab4ab | MSTR | 4h | +0.259 | +0.259 (HOLD, real) | +0.259 (HOLD, real) | +0.000 |
| 91bc8f12 | COIN | 4h | +0.472 | +0.472 (HOLD, real) | +0.472 (HOLD, real) | +0.000 |
| 151e545f | MU | 4h | +0.282 | +0.282 (CLOSE TIME_STOP, actual_close) | +0.155 (TIGHTEN TIME_STOP, be_kept) | -0.127 |
| 1f9903fb | BRENTOIL | 4h | +0.385 | +0.385 (CLOSE TIME_STOP, actual_close) | +0.364 (TIGHTEN TIME_STOP, be_kept) | -0.021 |
| caf82c74 | COIN | 4h | -0.714 | -0.714 (CLOSE STOP_PROXIMITY, actual_close) | -0.714 (CLOSE THESIS_GATE_FALSE, actual_close) | +0.000 |
| 043cae15 | SNDK | 4h | -0.536 | -0.536 (CLOSE STOP_PROXIMITY, actual_close) | -0.582 (CLOSE THESIS_GATE_FALSE, mark) | -0.046 |
| be724ff7 | MU | 4h | -1.067 | -1.067 (HOLD, real) | -0.131 (CLOSE TIME_STOP, mark) | +0.936 |

timestop_v2 minus current: total +3.29R over 114 positions; 15 better, 13 worse, 86 same (|diff| <= 0.05R).
Median difference +0.000R.

## Review fixes (MERGE AFTER FIXES, 2026-10-26)

`git merge main`: already up to date (main is `64498bb`, the branch base).

| sha | fix |
|---|---|
| `51fd097` | Eval excursions use the decided stop (`triage_decided_stops`) when it is cached. A position triaged before 10-26 still uses the hard stop, and `stop_source` "triage_initial_stops" is now documented as hard-stop R (about half the platform's R). Docstrings on `initial_risk` and `EvalExcursion` are corrected. The sentinel skill notes that a dossier `position` without `r_basis` predates 10-26 and reads R at about half size. New test: decided stop preferred, hard stop labelled. |
| `33e1f7c` | `manager replay closes` never calls `init_db` (its ALTER/index DDL could lock the live DB). It reads through `export_read_only`: `SET TRANSACTION READ ONLY` on Postgres, always rolled back, engine disposed. Tests: the CLI runs with `init_db` patched to raise, and the export issues `SET TRANSACTION READ ONLY` first and rolls back. |
| `1299e36` | Runbook, triage section: a note on the R basis cutover. From 2026-10-26 R is measured to the decided stop, before that to the hard stop. Mixed rNow history is told apart by `metrics.r_basis` / `position.r_basis`, and the note says what the THESIS line means on each scale. |

Full suite after the fixes: 5357 passed, 5 skipped, 0 failed.

Concerns after the fixes:
- Eval excursions already stored in `eval_excursions` keep their hard-stop `stop_source`; nothing is recomputed. Positions closed before the deploy never get a decided-stop row, so their excursions stay on hard-stop R. That is correct, but it is mixed-scale data.
- The `SET TRANSACTION READ ONLY` path is tested with a fake session only; it has not run against the live Postgres, because the port is not published to the host.
