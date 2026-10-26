# Grading the sentinel's CLOSE decisions (LIVE account)

Data pulled on 2026-10-26. The work was read-only:
- Postgres `decisions`, `actions`, `dossiers`, `triage_rows` and `triage_initial_stops`.
- BattleGrid `list_agent_trades` (LIFETIME, from 2026-09-18 to now), `get_position_audit_history` (two positions) and `get_coin_candles` at 4h (six coins).

No write tool was called.

## 0. Sample

- There are **20 CLOSE actions with status DONE**. Action 34 (PEPE, 2026-10-05) was a manual CLI close (`proposed_by=cli:rafael`, no decision), so it is excluded. That leaves **19 sentinel LIVE closes**, from 2026-10-13 to 2026-10-25.
  - By the sentinel's own reason: 8 STOP_PROXIMITY, 5 THESIS_GATE_FALSE, 3 REGIME_FLIP and 3 TIME_STOP.
  - The "time-decay" closes the user noticed are MU and BRENTOIL on 10-25 (both after 8 bars on 4h strategies) and APT on 10-14 (4 bars on a 15m strategy).
- Two closes (COIN #108 and SNDK #109) are still `planOutcome=RUNNING`.
- There is extra counterfactual evidence:
  - 45 SHADOW CLOSE decisions from 09-19 to 09-27, and 22 LIVE CLOSE decisions the guards REFUSED from 09-27 to 10-20.
  - In both cases the trade ran on to the platform's own exit, which tells us what "hold" actually returned.
- **This is a small sample.** Three TIME_STOP closes, 19 closes in all and 1 to 2 weeks of LIVE trading. Nothing below is statistically strong. Treat the verdicts as directional.

Agents:
- **V4h** = VWAP Sentinel 4h (959739dd)
- **VS** = VWAP Sentinel, 15m (2e725543)
- **TPO** = TPO VAH Rejector 4h (5554eb22)
- **PVM** = PVM 15m (c8ca25c7)

## 1. Per-trade table (the 19 sentinel closes)

How to read the table:
- r_now, bars, tp% (tp_progress_pct), stopATR (stop_distance_atr) and dq (direction_qualifies) come from the dossier the decision cites.
- netR, plan, vsPlan, MFE/MAE and post-exit come from `list_agent_trades.quality` and `postExitMove`.
- Post-exit signedReturnPct is measured in the trade's direction: + means price kept going the trade's way after the exit.
- Plan states: SF = STOP_FIRST, TF = TARGET_FIRST, NEI = NEITHER.

| Dec | Closed (UTC) | Agent | Coin / dir | Reason chosen | Triage reasons | r_now | bars | tp% | stopATR | dq | netR | plan state / planR | vsPlanR | MFE / MAE | H4 | H24 | Grade |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 85 | 10-13 07:36 | V4h | SMSN S | THESIS_GATE_FALSE | EVID_UNDET only | -0.37 | 0 | -37 | n/a | F | -0.774 | SF / -1.00 | +0.26 | 0.30 / -0.82 | -0.21 FLAT | -0.52 REV | GOOD |
| 86 | 10-13 08:16 | V4h | INTC L | THESIS_GATE_FALSE | EVID_UNDET only | +0.01 | 0 | 0.5 | n/a | F | +0.235 | SF (330 min) / -1.09 | +1.37 | n/a | -0.93 REV | +2.29 PERS | GOOD |
| 87 | 10-13 14:05 | VS | MOODENG L | REGIME_FLIP | REGIME_FLIP | -0.08 | 0 | -5.6 | 1.88 | F | +0.059 | SF (9 min) / -1.00 | +1.24 | 0.65 / -1.03 | +0.41 FLAT | -2.96 REV | GOOD (candles: the live stop was hit by 16:00) |
| 90 | 10-14 01:51 | V4h | COIN L | REGIME_FLIP | EVID_UNDET only | -0.01 | 2 | -0.7 | n/a | F | +0.190 | SF (1258 min) / -1.00 | +1.23 | 0.49 / -0.30 | +0.04 FLAT | -5.81 REV | GOOD |
| 91 | 10-14 02:12 | VS | PUMP S | THESIS_GATE_FALSE | THESIS, STOP_PROX | -0.78 | 1 | -50 | 0.42 | F | -0.439 | SF (6 min) / -1.02, TP later | +0.70 | -0.23 / -1.17 | +1.71 PERS | +8.33 PERS | **BAD** (plan says GOOD, but candles show the live stop at 0.005146 was never touched and the TP at 0.0049526 printed in the 08:00 to 12:00 bar: about -2.4R vs holding) |
| 93 | 10-14 09:12 | V4h | CRCL L | STOP_PROXIMITY | STOP_PROX | -0.34 | 1 | -33 | 0.44 | F | -0.724 | SF / -1.03 | +0.35 | 0.10 / -0.78 | -2.29 REV | -7.93 REV | GOOD |
| 95 | 10-14 23:26 | VS | APT S | TIME_STOP | TIME_STOP | -0.47 | 4 | -31 | 1.12 | F | -0.563 | SF (109 min) / -1.00, TP at 241 min | +0.54 | 0.20 / -0.79 | +5.46 PERS | -1.97 REV | UNCLEAR (the 00:00 to 04:00 bar's high of 0.8229 sat between the decaying live stop, 0.8236 and falling, and the decided stop, 0.8212; the TP printed in the same bar) |
| 97 | 10-15 03:55 | VS | ETH L | THESIS_GATE_FALSE | THESIS | -0.54 | 3 | -19 | 0.59 | F | -1.091 | SF (46 min) / -2.08 | +1.25 | 1.02 / -1.13 | +1.04 PERS | +3.59 PERS | GOOD (the live stop at 2343.2 was hit by 08:00, before the TP) |
| 98 | 10-15 05:14 | VS | PURR L | REGIME_FLIP | REGIME_FLIP | -0.02 | 0 | -1.1 | 1.91 | F | -0.122 | SF (108 min) / -1.03 | +0.99 | n/a | +0.27 FLAT | +0.96 PERS | GOOD (the live stop at 0.10081 was hit in the 04:00 to 08:00 bar) |
| 99 | 10-20 14:03 | V4h | HIMS S | THESIS_GATE_FALSE | THESIS, STOP_PROX | -0.70 | 0 | -67 | 0.34 | F | **-1.768** | SF (89 min) / -1.04 | -0.68 | 0.01 / -1.73 | -4.53 REV | -2.00 REV | GOOD in reality (plan says BAD, because price was already through the decided stop; the live wide stop at about 28.60 was certain to fill, since the bar ran to 29.98, which is about -2.1R) |
| 100 | 10-20 14:04 | V4h | SNDK S | STOP_PROXIMITY | STOP_PROX | -0.26 | 1 | -18 | 0.47 | F | -0.812 | SF / -1.00 | +0.22 | 0.62 / -0.86 | -1.00 REV | +0.12 FLAT | GOOD |
| 102 | 10-21 08:49 | V4h | INTC L | STOP_PROXIMITY | STOP_PROX | -0.27 | 2 | -26 | 0.48 | F | -0.428 | SF / -1.02 | +0.63 | 0.54 / -0.56 | -0.57 REV | -5.42 REV | GOOD |
| 103 | 10-21 12:44 | V4h | HIMS S | STOP_PROXIMITY | STOP_PROX | -0.35 | 1 | -18 | 0.30 | F | -0.387 | SF / -1.02 | +0.66 | 0.21 / -1.61 | +0.08 FLAT | +2.66 PERS | GOOD |
| 104 | 10-21 22:32 | V4h | COIN L | STOP_PROXIMITY | STOP_PROX | -0.30 | 1 | -18 | 0.37 | F | -0.432 | SF / -1.06 | +0.66 | 0.43 / -0.44 | -2.42 REV | -4.50 REV | GOOD |
| 105 | 10-21 22:52 | V4h | CRCL L | STOP_PROXIMITY | STOP_PROX | -0.22 | 1 | -19 | 0.50 | F | -0.868 | SF / -1.16 | +0.32 | 0.92 / -0.84 | -2.20 REV | -4.04 REV | GOOD |
| 106 | 10-25 08:12 | V4h | MU L | TIME_STOP | TIME_STOP | +0.18 | 8 | 17.6 | 1.78 | F | +0.282 | NEI / +0.185 | +0.13 | 0.64 / -0.63 | +0.16 FLAT | pending | UNCLEAR (+0.10R vs plan) |
| 107 | 10-25 08:11 | TPO | BRENTOIL S | TIME_STOP | TIME_STOP | +0.27 | 8 | 9.0 | 2.17 | F | +0.385 | NEI / +0.417 | +0.02 | 0.63 / -0.01 | +0.23 FLAT | pending | UNCLEAR (-0.03R vs plan) |
| 108 | 10-25 09:31 | V4h | COIN L | STOP_PROXIMITY | STOP_PROX | -0.29 | 1 | -29 | 0.42 | F | -0.714 | RUNNING / -0.175 | n/a | 0.07 / -0.71 | +0.07 FLAT | pending | BAD so far (still running) |
| 109 | 10-25 17:16 | V4h | SNDK S | STOP_PROXIMITY | STOP_PROX | -0.28 | 1 | -28 | 0.46 | F | -0.536 | RUNNING / -0.287 | n/a | 0.08 / -0.60 | H1 -0.16 FLAT | pending | BAD so far (still running) |

Two cross-cutting facts:
- `direction_qualifies` was **false in 19 of 19**.
- Every LIVE dossier except #86, #106 and #107 offered only HOLD or CLOSE. The TIGHTEN guard drops TIGHTEN unless the position is already past break-even.

### Why planOutcome alone mis-grades some closes

The platform scores `planOutcome` against the **decided** stop, but the **live** stop on the exchange starts much wider and decays toward it.
- `SL_PLACED` is placed at 1.33x to 2.15x the decided stop distance. `SL_REPLACED` events with `repriceSource: TIME_DECAY` then pull it in step by step:
  - SNDK #109: 1294.0 to 1267.2 over about 5 h.
  - APT #95: starts decaying only after 1 h, in 5 bp steps.
- A STOP_FIRST hit within the first hours can therefore be a touch the live position would have survived.
- PUMP #91 is exactly that case. HIMS #99 is the reverse: price was already beyond the decided stop, so the plan's -1.04R was never available.
- I checked the six early-touch cases against 4h candles and corrected them in the table. The 4h resolution leaves APT ambiguous.

## 2. Grades and aggregate by reason

Grades are corrected with candles as described above. RUNNING counts as BAD so far.
- R is the platform's R: |entry fill - decided stop|.
- USD is estimated as (netR - holdR) x (netPnl / netR) per trade.
- "holdR" is planR, except for #91 (holding to the TP, about +1.94R after fees) and #99 (the live stop, about -2.11R).

| Reason | n | mean netR | mean planR | sum(netR - holdR) | approx. USD | GOOD | BAD | UNCLEAR |
|---|---|---|---|---|---|---|---|---|
| STOP_PROXIMITY | 8 | -0.613 | -0.845 | +1.86R (+2.65R on the 6 resolved; -0.79R on the 2 RUNNING) | +$0.59 | 6 | 2 (running) | 0 |
| THESIS_GATE_FALSE | 5 | -0.767 | -1.246 | +0.50R (plan alone says +2.39R) | about +$0.1 | 4 | 1 (PUMP) | 0 |
| REGIME_FLIP | 3 | +0.042 | -1.011 | +3.16R (understated: the live stops were wider than the plan's) | +$0.71 | 3 | 0 | 0 |
| TIME_STOP | 3 | +0.035 | -0.133 | +0.50R (+0.06R without the ambiguous APT) | +$0.14 | 0 | 0 | 3 |
| **All 19** | 19 | **-0.448** | **-0.864** | **about +6.0R** (plan alone says +7.9R) | **about +$1.5** | 13 | 3 | 3 |

Of the 17 resolved plans, 15 were STOP_FIRST, 0 TARGET_FIRST and 2 NEITHER. The base rate for trades the manager left alone is 43 STOP_FIRST, 22 TARGET_FIRST and 5 NEITHER out of 70. If the sentinel picked at random, about 5 of its 17 would be TARGET_FIRST, so it is **not** cutting obvious winners.

Post-exit moves:

| Horizon | REVERSED (exit was right) | FLAT | PERSISTED (money left on the table) | Pending |
|---|---|---|---|---|
| H4 | 7 | 8 | 3 | 1 |
| H24 | 9 | 1 | 5 | 4 |

The PERSISTED cases are #91, #95, #97, #86, #98 and #103. Of these, only #91 is a confirmed loss from the close. In #97 and #98 the price went on, but only after first taking out the live stop.

**Verdict on the "time-decay" closes the user asked about:**
- MU and BRENTOIL were roughly neutral: +0.10R and -0.03R against holding the plan, flat 4 h later, and both closed at a small profit.
- APT on 10-14 lost -0.56R against a plan that stopped out first. Whether the live stop would have held is ambiguous.
- None of the three was a bad decision on the evidence. None was clearly a good one either.

## 3. Compared with the platform's own exits

These are trades since manager LIVE (2026-09-27 22:20Z) that the manager did not close. There are 70, from list_agent_trades.

| Platform exit | n | mean netR | USD | plan mix |
|---|---|---|---|---|
| STOP_LOSS | 44 | -0.166 | -$1.40 | 23 SF / 16 TF |
| TAKE_PROFIT | 7 | +2.467 | +$3.92 | 6 TF |
| INVALIDATION (the platform's own early exit) | 19 | **-1.526** | -$4.37 | 19 SF |
| All | 70 | -0.272 | -$1.85 | 43 SF / 22 TF / 5 NEI; mean planR +0.057 |

By agent:

| Agent | mean netR |
|---|---|
| V4h | +0.68 |
| VS | -0.81 |
| PVM | -0.33 |

What happened to the similar trades that were left alone:
- **TIME_STOP candidates in SHADOW or REFUSED** (13 positions, first TIME_STOP CLOSE decision each, ran to the platform's exit):
  - 11 would have done better closed, 1 was even (SOL fd0cff15) and 1 worse (XRP 3e10a635: r_now -0.03 at bar 4, then +0.729 with plan TARGET_FIRST).
  - Estimated benefit of closing: about +6.6 to +8R. That is r_now at decision rescaled about 1.5x into platform R, minus about 0.1R in fees and latency each.
- **THESIS_GATE_FALSE candidates REFUSED or SHADOW** (PEPE ffd36cd3, XRP 65fa61c3, MOODENG 5133bd21, INTC 2b973907, AAVE 75f12702, UNI de5ed1b2):
  - All six ended at -1.08R to -1.97R, against -0.51R to -0.71R at the decision. Closing would have helped every time.
- **4h positions still open after 4 or more bars** (more than 16 h) and closed by the platform: 91bc8f12 COIN at 34 h, +0.47R, and d4fef250 COIN at 18 h, +0.30R.
  - That is about the same as the two 4h TIME_STOP closes (+0.28R and +0.39R). The sample is tiny.
- **The two LIVE HOLDs on STOP_PROXIMITY** (MET #92 and CRCL #94):
  - Both had TARGET_FIRST plans of +2.3R, and both were then stopped out early by the platform's own stop tightening, at +0.07R and +0.21R.

**Context that matters more than any single rule:**
- The strategies themselves have negative expectancy: -0.27R per trade on platform exits, and -0.81R for VS.
- Any early exit near entry tends to beat holding. That is why most sentinel closes grade GOOD.
- The sentinel's total contribution is about +6R. The platform's own stop management gave back about 38R:
  - 16 TARGET_FIRST plans ended at STOP_LOSS early: plan mean +2.59R, realized mean +0.87R.
  - The platform's INVALIDATION exits lose 1.5R on average, which is worse than the stop.

## 4. The rules, and where the judgement goes wrong

These are from `battlegrid-manager/hermes/skills/battlegrid-sentinel/SKILL.md` and `manager/triage/rules.py`. I did not find a copy of the skill under the live profile path `AppData/Local/hermes/profiles/sentinel/skills/`, so the repo copy is the one quoted.

- Thresholds: `THRESHOLDS = {"loss_r": 0.5, "profit_r": 1.0, "time_stop_bars": 3, "tp_progress_pct": 25.0, "stop_atr": 0.5}`.
- **TIME_STOP fires when** `bars_in_trade > 3 and tp_progress_pct < 25`, where `bars_in_trade = (now - opened) // bar_ms` at the strategy's timeframe.
  - The skill says: "open more than 3 bars and progress toward take-profit is under 25%."
  - When it is the only reason: r_now <= 0 means CLOSE; r_now > 0 with dq true means HOLD; r_now > 0 with dq false means "CLOSE, not TIGHTEN."
- **STOP_PROXIMITY fires when** `|mark - current_stop| < 0.5 * ATR`, with the ATR read at the strategy timeframe. The skill says "consider whether TIGHTEN ... or CLOSE ... fits".
- **THESIS_GATE_FALSE fires when** `r_now <= -0.5 and direction_qualifies is False`. The skill says it "Leans toward CLOSE".

The problems found:

1. **r_now uses the wrong R, so every R number the sentinel reasons with is off by 1.3x to 2.2x.**
   - The cause: `triage_initial_stops` caches the first `SL_PLACED` order, which is the platform's wide catastrophe stop, later pulled in by TIME_DECAY. It is not the decided stop the platform's own R uses.
   - Measured ratios of manager R to platform R:

     | Position | Ratio |
     |---|---|
     | APT | 1.33 |
     | UNI | 1.34 |
     | XRP | 1.33 and 1.36 |
     | SOL | 1.67 |
     | BRENTOIL | 1.82 |
     | SNDK | 2.0 |
     | MOODENG | 2.0 |
     | INTC | 2.04 |
     | CRCL | 2.15 |

   - Consequences:
     - THESIS_GATE_FALSE's "-0.5R" is really -0.7R to -1.0R, so it fires when the trade is at or through its decided stop (HIMS #99 closed at -1.77R).
     - The STOP_PROXIMITY rationales quote "preserves -0.28R rather than a -1R stop-out" while the fills were -0.54R (#109), -0.87R (#105) and -0.81R (#100). The "-1R" stop in those sentences is actually at -0.5 manager-R.
     - tp_progress and the sign of r_now are unaffected, so the TIME_STOP zones are still right.

2. **direction_qualifies carries no information, yet it decides outcomes.**
   - It is false in about 75% of triage rows since 10-19, and already false at bar 0 for 43 of 67 positions.
   - At the first triage row, dq=false trades went on to a mean of -0.32R with a 42% win rate; dq=true trades went on to -0.31R with 49% (n = 40 / 39).
   - It is the entry condition still being true, which for VWAP strategies naturally turns off after the move. It is not a thesis failure.
   - Yet the TIME_STOP "r_now > 0" branch turns on it, and the model closed five positions at bars 0 to 2 with r_now about 0 on "the thesis gate is shut" (#85, #86, #87, #90, #98). Those closes happened to be good only because most entries fail.

3. **TIME_STOP ignores the timeframe.**
   - Three bars is 1 h on the 15m agents (VS, PVM) and 16 h on 4h agents.
   - Time-to-target on resolved TARGET_FIRST plans:

     | Agents | Median minutes to target | In bars | Plans reaching target within 4 bars |
     |---|---|---|---|
     | 15m (VS, PVM) | 152 | about 10 bars | 2 of 18 |
     | V4h | about 200 | about 1 bar | — |

   - So the rule is aggressive on 15m and lenient on 4h. The one TIME_STOP miss found, XRP 3e10a635, is a 15m trade.
   - Even so, TIME_STOP has been net positive so far, because the 15m strategies mostly lose.

4. **STOP_PROXIMITY mostly reacts to the platform's own TIME_DECAY.**
   - The stop is pulled in mechanically toward the decided stop over about 5 h. So nearly every slightly negative V4h trade trips "within 0.5 ATR" at bar 1 or 2.
   - All 8 STOP_PROXIMITY closes were at bars 1 to 2 with r_now between -0.22 and -0.35.
   - It has paid off on the 6 resolved closes, but it is a mechanical trigger, not a judgement.

5. **The live and shadow mode is misread, and reason labels are misused.**
   - #90 says "Shadow only - no execution" and #95 says "Shadow: no execution". Both were LIVE and executed (actions 78 and 81).
   - #85 and #86 are labelled THESIS_GATE_FALSE although triage did not fire it and r_now was -0.37 and +0.008. #86 admits "r_now=0.008R is positive vs the -0.5R threshold".
   - #108 says "Regime flipped" with momentum_now = momentum_t1 = bearish.
   - The reason column therefore cannot be trusted for per-rule statistics.

6. **Latency.** From dossier build to fill takes 5 to 10 min. That is a third to two-thirds of a bar on 15m strategies, and part of why realized netR is below the quoted r_now.

On thresholds for 4h strategies: 3 bars (16 h before the rule can fire) is not too short. Targets on the 4h agent are usually hit within 1 to 4 bars, and the two 4h time stops were neutral. The real issue is the uniform bar count across timeframes and the dq coin-flip.

## 5. Improvements, ranked by expected impact

1. **Compute r_now from the decided stop, not the first SL order.**
   - Use the platform's R: |entry fill - decided stop|. The decided stop is where TIME_DECAY converges, or the `quality` R basis.
   - Data: the ratios in section 4.1.
   - Measure: on the next 20 closes, triage r_now x R_manager / R_platform should match netR within about 0.15R, and rationales should quote numbers that the fills confirm.
   - Re-tune THESIS_GATE_FALSE after the fix. -0.5R in true R will fire earlier. Check on the stored dossiers how often it would have fired, and at what eventual netR.
2. **Build a replay and backtest harness over the stored dossiers and triage rows**, about 3,000 rows since 10-12.
   - For each row, simulate hold vs. close vs. TIGHTEN using candles, the **live** stop schedule (SL_PLACED plus TIME_DECAY steps from the audit history) and the TP.
   - That fixes the planOutcome blind spot (#91, #99, #95) and lets every threshold below be tested on data instead of opinion.
   - Measure: R saved per rule, per agent and per timeframe, with bootstrap intervals.
3. **Remove direction_qualifies as a deciding input**, or replace it with something that predicts.
   - Candidates: momentum against the position over N bars, or an MAE path.
   - In the TIME_STOP r_now > 0 branch, use TIGHTEN to break-even. Its geometry passes when in profit, and #106 and #107 offered it.
   - Data: dq-true and dq-false outcomes are the same (section 4.2).
   - Measure in the harness: the TIME_STOP r_now > 0 cases closed vs. tightened, and how bar 0 to 2 "dq false" closes compare with holding.
4. **Make TIME_STOP timeframe-aware.**
   - Set the bar count per agent from its own median bars-to-target, for example 1.5x the median: about 15 bars on the 15m agents and 2 to 4 bars on 4h agents.
   - Alternatively, express it in hours.
   - Data: medians of 152 min (15m) and about 200 min (4h); the XRP 3e10a635 miss.
   - Measure: harness R by threshold. Do not loosen it blindly, because the current rule is net positive (+6.6 to 8R counterfactual) on loss-heavy strategies.
5. **Close the feedback loop automatically.**
   - After each manager CLOSE resolves, store the platform's netR, planOutcome, vsPlanR and postExitMove next to the decision. The `decisions.review` column is unused for #99 onward.
   - Flag cases where planOutcome is STOP_FIRST within the TIME_DECAY window as "plan unreliable".
   - Report the hit rate weekly per reason.
6. **Fix the rationale defects.**
   - Have the dossier state the mode prominently: #90 and #95 believed they were in shadow.
   - Require the chosen reason to be one that triage actually fired, or call out the override explicitly.
   - Quote R in one basis only.
7. **Outside the sentinel, and the bigger lever.**
   - The platform's own stop management (TIME_DECAY, break-even and trailing, INVALIDATION) cost about 38R on 16 TARGET_FIRST plans, and INVALIDATION exits average -1.53R.
   - Reviewing the agents' break-even and trailing configuration, and the entry quality (VS at -0.81R per trade), would move results far more than tuning the sentinel's close rules.
