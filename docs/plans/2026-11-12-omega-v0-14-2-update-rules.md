# OMEGA v0.14.2 at contract 171.0.0: the update rules and the last unmeasured items

**Record, 2026-11-12 (written 22:13Z).** Contract 171.0.0, build `588e449a`. Previous pin: v0.14.1 at the same
contract. This settles the six items `docs/plans/2026-11-12-omega-v0-14-1-limits.md` left under "Not measured".

| | |
| --- | --- |
| Measured | 21:46:40 - 21:54:05Z. `GET /mcp/version` read 171.0.0 / 588e449a before and after each of the 7 phases (14 reads) |
| Record | `data/audit/update_rules_171_2026-11-12.json` |
| Replay | `tests/test_update_rules_171.py` (26 tests) |
| Transport | the mcporter runtime (`scripts/mcporter_runtime.mjs`), one session, one call per 2.1 s or slower |
| Probe script | `C:/Users/rafae/omega-v012-hints/v171/probe_v0142.py`. Beside it: `rt2.py`; every call's arguments and answer in `calls.jsonl`; the raw run in `run_v0142.json`; `build_record.py`, which writes the record |

The contract did not move during the run.

## What was sent

| Kind | Count | Answer |
| --- | --- | --- |
| `preview_strategy_report` (FIELDS, BTC, 1h) | 4 | 1 rendered, 3 refused |
| CREATE stage, the v0.14.0 base plan | 2 | both refused at input, so no draft was made |
| UPDATE stage on the sandbox | 8, in 4 drafts | 7 staged, 1 refused at input |
| `preview_strategy_trade_levels` on a staged draft (BTC) | 5 | 1 rendered, 4 refused on the draft's error |

The **sandbox** is `OMEGA-TEST: 110.8 stage probe` (`87dac9ab`). It is archived, at revision 2. UPDATE stages may only
go on an OMEGA-TEST strategy that no agent is bound to. `list_strategies` (inactive included, 21:35Z) lists six
OMEGA-TEST strategies, all archived:

- three have an archived agent bound (TPO Alpha, BRK Alpha, ROT Alpha), so none of them was used;
- three have `boundAgentCount` 0. This one was created on 2026-10-23 for stage probes.

The platform takes a draft on an archived strategy. On A1, `get_strategy_draft` read `impact.operation` "RESTORE",
meaning a commit would restore the strategy. Nothing was committed.

Before each of the four drafts, the sandbox read:

- revision 2;
- `boundAgentCount` 0 and `openPositionCount` 0;
- no held draft.

Each draft went through the same steps:

1. read back with `get_strategy_draft`;
2. discarded at the version read;
3. read again: `draft: null` and `draftVersion` 0 every time.

`list_strategy_drafts` at 21:54Z listed one draft. It was not this run's: VWAP Reject 15m, last written by the
commander on 2026-10-23. Nothing was committed, bound, deployed, restored or archived.

## What the answers settle

| Item | Probes | Platform's answer |
| --- | --- | --- |
| (1) An UPDATE that switches Trailing off under a runner | A1, A2, A3 | **The stage judges the whole draft.** A1 drafted three runner plans (Trailing on) and was clean. A2 then staged POSITION_MANAGEMENT alone with Trailing off and got "The LONG exit plan leaves a runner, and Trailing is off" on `tradeLevelMenu.LONG.exitPlans[0]`, a menu the stage was not sent. A3 staged REPORT alone without the two Bollinger columns and got "A LONG stop level is not a level this strategy's report yields" on `tradeLevelMenu.LONG.stops[4].level`, the **committed** menu's Bollinger stop (no draft held a menu) |
| (2) An UPDATE that raises minRiskRewardRatio alone above a plan's pay | B1, B2 | **The minimum cannot be staged without the menu**: B1 (the four dials, no `tradeLevelMenu`) was refused at input, "Invalid input: expected object, received undefined", on `axes.TRADE_LEVEL_POLICY.tradeLevelMenu`. B2 restaged the axis whole, with the committed menu carried verbatim and the minimum at 2.5. It was judged as a create: "The LONG exit plan pays 1.5R, below this strategy's minimum risk-reward of 2.5: every pair it makes would be refused" |
| (3) An UPDATE restaging an off-step minimum carried from the strategy | C1, C2 | **A draft error on the dial, on an UPDATE as on a create.** C1 named 1.4. C2 carried the 1.4 the draft held, with the four dials and the menu exactly as `get_strategy_draft` read them after C1, and `minAtrPct` 0.5 -> 0.4. Both answered "minRiskRewardRatio must be a multiple of 0.25" on `minRiskRewardRatio` |
| (4) The 5% rule on a non-first leg and a 1% runner | S3, S4 | **Refused at input with S1 / S2's sentences.** S3 (1.5R 50%, then 3R 3%) answered "A target closes at least 5%" on `targets[1].closePct`, LONG and SHORT. S4 (2R 99%) answered "A runner holds 0% or at least 5% of the position; this plan leaves 1%" on `targets` |
| (5) A deep chain in a market, reference or benchmark section | P1 - P4 | **The same joint bound as a per-coin section** (see below) |
| (6) A runner after a LEVEL leg | A1's preview, L1 | **At a decision, it rides at that level's R** (see below). **It is refused while Trailing is off**: L1 staged a band level closing 50% as the only plan, with Trailing off, and got the runner's draft error on `exitPlans[0]` |

### The stage names only the first menu error it meets

- **A2:** three plans per side leave a runner. The draft error names `LONG.exitPlans[0]` alone.
- **A3:** two Bollinger stops and two Bollinger plans lost their column. The draft error names the LONG stop alone.
- **Earlier probes:** they named LONG alone and never SHORT. That is the same behaviour.

omega names every error, so the replay checks two things:

- the platform's field is among omega's fields;
- every omega error is of that probe's rule.

### (5) Deep chains off the per-coin subject

P1 rendered the per-coin last fits on all three subjects in one preview:

| Subject | Section | Column | conditionHold.maxWindow | Value |
| --- | --- | --- | --- | --- |
| market | marketScope `all` | MKT_NET x ema 14 -> aggregate 2385 | 64 | null |
| reference | benchmarkTicker `USDT_USD` | CLOSE x aggregate 10 -> zscore 2427 | 64 | -0.938 |
| reference | benchmarkTicker `USDT_USD` | PAR_DEV x ema 14 -> aggregate 2385 | 64 | null |
| benchmark | benchmarkTicker `ETH` | RSI14 x ema 14 -> aggregate 2385 | 50 | 50.27 |
| benchmark | benchmarkTicker `ETH` | CLOSE x aggregate 10 -> zscore 2427 | 64 | -1.407 |

P2 (market, 2386), P3 (reference, 2428) and P4 (benchmark, 2386) were each refused with the per-coin sentence:

- the column "reads 2437 bars for one value - at most 2436 of the 2500 readable bars, leaving the lookback budget 64";
- the largest fit is 2385 / 2427 (`REPORT_COLUMN_DEPTH_EXCEEDED`, path `sections[0].columns[0].chainedWindow`).

The hold rooms match the per-coin ones in `tests/test_v0_14_1.py`: 50 on the RSI14 chain, 64 on the others.

The bound is the authoring rule only. At this depth, the market breadth and PAR_DEV values come back null. PAR_DEV's own
gloss explains why: "a lookback beyond the history the store holds reads absent". omega predicts no values, and does
not model this.

### (6) What a runner after a level leg pays

A1 drafted two level plans per side, using the sandbox's own "Trade levels" columns:

- **LONG:** a band level closing 50%, and 1R 30% + the band level 30%. The band is DONCHIAN_UPPER.
- **SHORT:** the same two plans on DONCHIAN_LOWER.

At 1.5 they staged **clean**, as Z1 - Z3 did: the stage does not judge a level plan's pay.

The preview (entry 71,575, ATR 478.90; DONCHIAN_UPPER 74,057, DONCHIAN_LOWER 71,227) read every pair as
`plan_pays` with each level leg at the R its price makes from that pair's stop:

| LONG plan | stop ATR 1 | ATR 1.5 | ATR 2 |
| --- | --- | --- | --- |
| the level's R | 5.183 | 3.455 | 2.591 |
| level 50% (runner 50%) | **5.183** | **3.455** | **2.591** |
| 1R 30% + level 30% (runner 40%) | **3.928** = 0.3 + 0.7 x 5.183 | **2.719** | **2.114** |

The mean over the share the plan closes (v0.14.0's reading) would give 3.091 for the first cell of the last row. So
the runner rides at the last closing leg's R, whether that leg is an R or a level.

The SHORT band sat 0.73R from entry at stop ATR 1, so the preview refused all six SHORT level pairs:

- "RISK_REWARD_TOO_LOW" for the level alone: 0.7267, 0.4844, 0.3633;
- "TARGETS_OUT_OF_ORDER" for 1R then the level, because the level is nearer than 1R: 0.8087, 0.6391, 0.5543.

Each `computedRR` is the same share-weighted sum.

The runner trail read the farthest target's distance x 0.45 again: 2.33 ATR on the level plans, 1.35 R on the 3R plan.
Only one giveback was sent, so the trail is recorded, not modelled.

## Where OMEGA holds it

| Rule | v0.14.1 | v0.14.2 |
| --- | --- | --- |
| A menu the update does not stage, against the report and Trailing the update does stage | warning, "whether the stage re-judges it is unmeasured" | **error**, the same code (`omega/generate.py` `StrategyPlan.update_menu_findings`; probes A2, A3) |
| A minimum off its 0.25 step that the draft would hold and the thesis does not name | warning `EXECUTION_CARRIED_OFF_STEP`, only when the update restaged the axis | **error** `EXECUTION_CARRIED_OFF_STEP` on `<AXIS>.<dial>`, whether the update carries it in a restaged axis (C2) or leaves it in an axis it does not stage (the whole-draft judgment, A2 / A3) (`StrategyPlan._carried_off_step`). A **committed** off-step value is unmeasured, and refused, failing closed |
| The minimum raised alone | judged as the staged axis (unmeasured) | the same, now measured (B2). omega's update never stages the axis without a menu (`update_menu` raises): B1's refusal is the write schema's `MISSING_REQUIRED` on `tradeLevelMenu`, which omega's walk names too |
| The 5% leg / runner minimums | extended from S1 / S2 by the message text | measured at a 3% second leg (S3) and a 1% runner (S4). Same codes; the messages name the probes |
| A runner after a LEVEL leg with Trailing off | `TRADE_MENU_EXIT_PLAN_RUNNER_WITHOUT_TRAILING`, any runner | the same, now measured (L1) |
| What a plan with a level leg pays at a decision | not computed (`plan_pays` None) | `plan_pays(legs, level_r)` / `plan_pays_exact(legs, level_r)`. `level_r` gives each level leg's R from one pair's stop. The stage reading is unchanged: without `level_r` a level plan is None and not judged |
| The joint chain depth bound | applied to every column whatever its section | unchanged; the docstring of `omega/validate.py` `_rolling_chain_depth` records the market, reference and benchmark measurements |

`omega/trade_levels.py` names the record `UPDATE_PROBES` and carries these rules in its module docstring.
`omega/execution.py` `ENFORCED_STEPS` records the step measured on an UPDATE.

### Tests whose v0.14.1 assertions changed

Three tests asserted the v0.14.1 warnings that these probes replaced:

- `tests/test_trade_level_menu_168.py::test_an_update_carries_the_live_menu_and_never_invents_one` now expects an error
  on the unstaged live menu;
- `tests/test_exit_plan_runner_171.py::test_an_update_that_switches_trailing_off_under_a_live_runner_is_refused` was
  `..._is_warned`;
- `tests/test_exit_plan_runner_171.py::test_an_update_carrying_a_live_minimum_off_its_step_is_refused` was
  `..._is_warned`. It now also refuses an off-step minimum held in an axis the update does not stage.

**For whoever pins v0.14.2 in battlegrid-manager:** these warnings are now errors, so a pipeline that blocks on errors
will block where v0.14.1 let an update through with a warning.

## Not measured

- **A committed off-step minRiskRewardRatio.**
  - Why there is no measurement: no unbound sandbox holds one (all three read 1.5), none of the 105 strategies
    `list_strategies` listed at 21:35Z did, and committing one is closed.
  - What omega does: refuses it, failing closed (`EXECUTION_CARRIED_OFF_STEP`).
- **A committed runner under an update that switches Trailing off.** A runner can only be committed by a commit, which
  is closed, so A2's runner was held by the draft. That the stage re-judges an unsent committed axis is A3's
  measurement on the level rule. omega applies the two together.
- **How the runner's trail is sized.** It was read at `trailingGivebackPct` 45 only, so it is not modelled. The 2.33 ATR
  on the level plans and 1.35 R on the 3R plan fit the farthest target x 0.45 again.
- **The step on any dial other than minRiskRewardRatio.**
- **The bottom of the chain window off the per-coin subject.** P1 - P4 measured the top (the joint bound) only.
- **Whether a deep chain's value is ever non-null on market breadth or PAR_DEV.** At 2385 it reads null. The depth at
  which the stored history fills it is unknown, and omega does not predict values.

## Suite

2488 passed, 1 skipped. The last run took 251 s (22:16 - 22:20Z). That is v0.14.1's 2462 plus the 26 tests of
`tests/test_update_rules_171.py`; the three rewritten tests keep their count. The version assertions in
`tests/test_v146.py` and `tests/test_v146_1.py` read 0.14.2.
