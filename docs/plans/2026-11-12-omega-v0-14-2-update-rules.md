# OMEGA v0.14.2 at contract 171.0.0: the update rules and the last unmeasured items

**Record, 2026-11-12 (written 22:13Z; revised 23:19Z after the v0.14.2 review).** Contract 171.0.0, build `588e449a`.
Previous pin: v0.14.1 at the same contract. This settles the six items `docs/plans/2026-11-12-omega-v0-14-1-limits.md`
left under "Not measured".

The review revision made no platform call. It changed five things:

- `current` is now defined as the committed strategy overlaid by the held draft. A `current` without the menu is
  refused (`TRADE_MENU_LIVE_UNKNOWN`).
- A rule none of whose axes an update stages is labelled unmeasured.
- Each probe's `sentAt` is now the call log's own time.
- `counts.committed` is derived from a tally of the call log.
- The deep-chain nulls are recorded as observed.

| | |
| --- | --- |
| Measured | 21:46:40 - 21:54:05Z. `GET /mcp/version` read 171.0.0 / 588e449a before and after each of the 7 phases (14 reads) |
| Record | `data/audit/update_rules_171_2026-11-12.json` |
| Replay | `tests/test_update_rules_171.py` (29 tests) |
| Transport | the mcporter runtime (`scripts/mcporter_runtime.mjs`), one runtime process (one MCP session) per phase, one call per 2.1 s or slower |
| Probe script | `C:/Users/rafae/omega-v012-hints/v171/probe_v0142.py`. Beside it: `rt2.py`; every call's arguments and answer in `calls.jsonl`; the raw run in `run_v0142.json`; `build_record.py`, which writes the record. It takes each probe's `sentAt` and each discard's time from `calls.jsonl`, and tallies the log into the record's `calls` |

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

The call log `calls.jsonl` holds 56 calls: the 9 read-only discovery calls before the run (21:35:09 - 21:38:15Z) and
the 47 calls of the run. By tool: 22 `get_strategy_draft`, 10 `stage_strategy_draft`, 7 `get_strategy`, 5
`preview_strategy_trade_levels`, 4 `preview_strategy_report`, 4 `discard_strategy_draft`, 2 `list_strategy_drafts`, 1
`list_strategies`, 1 `list_intelligence_agents`. There is no commit, restore, archive or bind. The record carries this
tally (`calls.byTool`), and its `counts.committed` is the log's commit count, not a literal.

**Times.** A probe's `sentAt` is the time `calls.jsonl` stamped on its call: after the runtime's pacing wait,
immediately before the request was written. As first built, the record took the probe script's own clock, read before
that wait, so the times ran up to 3 s early: A2 21:48:48Z became 21:48:50Z, A3 21:52:17Z became 21:52:19Z, and L1
21:53:22Z became 21:53:25Z.

## What the answers settle

| Item | Probes | Platform's answer |
| --- | --- | --- |
| (1) An UPDATE that switches Trailing off under a runner | A1, A2, A3 | **A rule tying two axes is re-judged when an update stages one of them**, against the other as the draft holds it, or else as committed. Each probe staged one axis of the rule it measured; no probe left every axis of a rule unsent. A1 drafted three runner plans (Trailing on) and was clean. A2 then staged POSITION_MANAGEMENT alone with Trailing off and got "The LONG exit plan leaves a runner, and Trailing is off" on `tradeLevelMenu.LONG.exitPlans[0]`, a menu the stage was not sent. A3 staged REPORT alone without the two Bollinger columns and got "A LONG stop level is not a level this strategy's report yields" on `tradeLevelMenu.LONG.stops[4].level`, the **committed** menu's Bollinger stop (no draft held a menu) |
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

### A held draft holds only the axes it staged

`get_strategy_draft` read back `draft.content` with only the axes the draft had staged:

- `TRADE_LEVEL_POLICY` alone after A1, B2, C1 and C2;
- `REPORT` alone after A3;
- `TRADE_LEVEL_POLICY` and `POSITION_MANAGEMENT` after A2 and L1.

So the strategy an UPDATE is judged against is the committed one overlaid, axis by axis, by the held draft's axes.
That is the `current` that `StrategyPlan.axes_update` and `update_menu_findings` take, and what the replay's
`_composed` builds. The draft's content alone is not `current`. Given A3's content alone (`REPORT`), the first v0.14.2
build (e52f745) found no menu, returned nothing, and so passed silently the refusal A3 drew on the committed menu.

### (5) Deep chains off the per-coin subject

P1 rendered the per-coin last fits on all three subjects in one preview:

| Subject | Section | Column | conditionHold.maxWindow | Value |
| --- | --- | --- | --- | --- |
| market | marketScope `all` | MKT_NET x ema 14 -> aggregate 2385 | 64 | null |
| reference | benchmarkTicker `USDT_USD` | CLOSE x aggregate 10 -> zscore 2427 | 64 | -0.938 |
| reference | benchmarkTicker `USDT_USD` | PAR_DEV x ema 14 -> aggregate 2385 | 64 | null |
| benchmark | benchmarkTicker `ETH` | RSI14 x ema 14 -> aggregate 2385 | 50 | 50.27 |
| benchmark | benchmarkTicker `ETH` | CLOSE x aggregate 10 -> zscore 2427 | 64 | -1.407 |

One column per subject was then sent one past the fit, and each was refused with the per-coin sentence:

| Probe | Subject | Column sent |
| --- | --- | --- |
| P2 | market | MKT_NET x ema 14 -> aggregate 2386 |
| P3 | reference | CLOSE x aggregate 10 -> zscore 2428 |
| P4 | benchmark | RSI14 x ema 14 -> aggregate 2386 |

- the column "reads 2437 bars for one value - at most 2436 of the 2500 readable bars, leaving the lookback budget 64";
- the largest fit is 2385 / 2427 (`REPORT_COLUMN_DEPTH_EXCEEDED`, path `sections[0].columns[0].chainedWindow`).

PAR_DEV at 2386 (reference) and the benchmark's CLOSE x aggregate 10 -> zscore at 2428 were not sent one past the fit.

The hold rooms match the per-coin ones in `tests/test_v0_14_1.py`: 50 on the RSI14 chain, 64 on the others.

The bound is the authoring rule only. At this depth, the market breadth and PAR_DEV values come back null:

- **PAR_DEV:** its own gloss gives a reason: "a lookback beyond the history the store holds reads absent".
- **Market breadth:** the cause is not established. MKT_NET's gloss says nothing about stored history, and v0.14.1
  recorded the 161 nulls the same way.

omega predicts no values, and models neither null.

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
| A menu the update does not stage, against the report and Trailing the update does stage | warning, "whether the stage re-judges it is unmeasured" | **error**, the same code (`omega/generate.py` `StrategyPlan.update_menu_findings`; probes A2, A3). The message names the probe |
| A menu the update does not stage, under a rule none of whose axes the update stages: a runner beside a Trailing it does not stage either, or a plan against the minimum beside it | warning, as above | **error**, the same code, **unmeasured**: refused, failing closed, and the message says so. `omega/trade_levels.py` `RULE_AXIS` names the axis each menu rule reads beside TRADE_LEVEL_POLICY |
| No menu in `current` while the update does not stage TRADE_LEVEL_POLICY (a partial `current`, e.g. a held draft's content alone) | nothing | **error** `TRADE_MENU_LIVE_UNKNOWN` on `TRADE_LEVEL_POLICY.tradeLevelMenu`, failing closed: the stage judges the menu omega was not given (A3) |
| No POSITION_MANAGEMENT in `current` under a live runner, neither axis staged | nothing | **warning** `TRADE_MENU_EXIT_PLAN_RUNNER_TRAILING_UNKNOWN`, as on a staged menu. This update changes neither axis of that rule |
| A minimum off its 0.25 step that the draft would hold and the thesis does not name | warning `EXECUTION_CARRIED_OFF_STEP`, only when the update restaged the axis | **error** `EXECUTION_CARRIED_OFF_STEP` on `<AXIS>.<dial>` (`StrategyPlan._carried_off_step`). **Measured** when the update restages the axis and carries the value as the draft held it (C2; named, C1). **Unmeasured, refused, failing closed** in two cases, because C1 and C2 both sent the value: carried from the committed strategy, and held in an axis the update does not stage, by the draft or committed. The message says which |
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
  `..._is_warned`. It now also refuses an off-step minimum held in an axis the update does not stage, and checks that
  the message calls this case unmeasured.

`tests/test_trade_level_menu_168.py` also asserted that a `current` without a menu gave no finding (`[]`). It now
expects `TRADE_MENU_LIVE_UNKNOWN`.

**For whoever pins v0.14.2 in battlegrid-manager:**

- These warnings are now errors, so a pipeline that blocks on errors will block where v0.14.1 let an update through
  with a warning.
- **`read_current` must merge.** `manager/authoring/current.py` `read_current` returns `get_strategy_draft`'s
  `draft.content` alone whenever a draft is held. The revise chat stores that as the plan's `current`
  (`manager/api/strategy_routes.py:102`; `_foreign_draft` lets the manager's own draft through), and
  `manager strategy current` writes it too. That content holds only the axes the draft staged. When a draft is held,
  `read_current` must overlay `draft.content` on `get_strategy`'s axes (`axes_of_strategy`).
- Until it does, an UPDATE planned from a held draft that holds no TRADE_LEVEL_POLICY, and that does not stage the
  axis, FAILs on `TRADE_MENU_LIVE_UNKNOWN`. That is the intended fail-closed outcome. e52f745 passed such an update
  silently, even when the committed menu would be refused, as A3's was.

## Not measured

- **A committed off-step minRiskRewardRatio.**
  - Why there is no measurement: no unbound sandbox holds one (all three read 1.5), none of the 105 strategies
    `list_strategies` listed at 21:35Z did, and committing one is closed.
  - What omega does: refuses it, failing closed (`EXECUTION_CARRIED_OFF_STEP`).
- **An off-step minRiskRewardRatio held in an axis the update does not stage**, whether the draft holds it or the
  committed strategy does. C1 and C2 both sent the value in a restaged TRADE_LEVEL_POLICY. omega refuses it, failing
  closed, and its message says it is unmeasured.
- **A rule none of whose axes an update stages.** A2 and A3 each staged one of the two axes of the rule they measured.
  No probe left every axis unsent. Two examples:
  - a runner held with Trailing off when neither TRADE_LEVEL_POLICY nor POSITION_MANAGEMENT is staged;
  - a held plan against the held minimum when TRADE_LEVEL_POLICY is not staged.

  omega refuses these, failing closed, and labels them unmeasured.
- **A committed runner under an update that switches Trailing off.** A runner can only be committed by a commit, which
  is closed, so A2's runner was held by the draft. That the stage re-judges an unsent committed axis is A3's
  measurement on the level rule. omega applies the two together.
- **How the runner's trail is sized.** It was read at `trailingGivebackPct` 45 only, so it is not modelled. The 2.33 ATR
  on the level plans and 1.35 R on the 3R plan fit the farthest target x 0.45 again.
- **The step on any dial other than minRiskRewardRatio.**
- **The bottom of the chain window off the per-coin subject.** P1 - P4 measured the top (the joint bound) only.
- **One past the fit for PAR_DEV and for the benchmark's CLOSE x aggregate 10 -> zscore.** P2 - P4 sent one column
  per subject.
- **Why a deep chain reads null on market breadth, and whether it or PAR_DEV is ever non-null at that depth.** At 2385
  both read null. PAR_DEV's gloss names stored history; MKT_NET's says nothing. omega does not predict values.

## Suite

2491 passed, 1 skipped. The last run took 254 s (23:15 - 23:20Z), after the review revision. That is v0.14.1's 2462
plus the 29 tests of `tests/test_update_rules_171.py`; the rewritten tests keep their count. The first build ran 2488:
the revision added three tests and renamed one.

- **Added:** `test_a_partial_current_is_never_read_as_a_clean_menu`,
  `test_a_rule_none_of_whose_axes_the_update_stages_is_refused_as_unmeasured` and
  `test_one_column_per_subject_was_sent_one_past_the_fit`.
- **Renamed:** `..._are_a_matter_of_stored_history` is now
  `test_the_deep_chain_values_off_the_coin_read_null_on_market_breadth_and_par_dev`.

Run against the first build's `omega/` (e52f745), the first two new tests fail. That is the defect the review found.
The version assertions in `tests/test_v146.py` and `tests/test_v146_1.py` read 0.14.2.
