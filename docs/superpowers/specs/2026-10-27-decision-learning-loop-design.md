# A learning loop for the manager's decisions (brainstorm draft, 2026-10-27)

Status: APPROVED in direction 2026-10-27 (the user: "Build the collect and label stages first, then
target entry quality (lever A) with the cross-agent pulls, as recommended."). Section 8 records the
decisions and the calls made in the user's absence; section 10 scopes the first build. Nothing is
built yet. The code lives in `battlegrid-manager`; this document lives in OMEGA with the other
manager session records.

Evidence gathered 2026-10-27 07:00-08:00Z, read-only: the manager's Postgres (42 tables, row counts
below), the manager code at `6e12804`, the sentinel skill and persona, the 10-26 close-decision reports
(`close-decisions-report.md`, `close-improve-report.md`), the BattleGrid tool surface fixtures through
132.0.0 and the v136 README, Hermes' own memory and curator modules.

---

## 1. The problem, in the user's words and in the data's

The user: the Hermes agent is "pretty automatic" in its decisions. The wish: a loop that teaches
itself to make better decisions on closing a trade and on optimizing a strategy, learning not only
from its own trades but from the whole platform and other agents' trades.

What the data says the "automatic" feeling actually is:

1. **The sentinel is automatic by design.** Colour (RED/AMBER/GREEN) and the AMBER reasons come from
   five fixed thresholds in `manager/triage/rules.py` (`loss_r 0.5, profit_r 2.0, time_stop_bars 3,
   tp_progress_pct 25, stop_atr 0.5`). The LLM is asked one thing: HOLD, TIGHTEN or CLOSE on an AMBER
   dossier. Even there, the skill fixes the pure TIME_STOP outcome by zones, LIVE `allowed_outcomes`
   drop TIGHTEN on almost every losing position, and the model is stateless: no memory, no history, no
   outcomes of its past decisions. A deterministic rule set reproduces 100% of triage's stored reasons
   and 87% of the sentinel's recorded outcomes (`manager replay closes`).
2. **The close decision is a small lever.** Over 19 LIVE closes the sentinel added about +6R against
   holding. In the same period the platform's own stop management (TIME_DECAY, break-even, trailing,
   INVALIDATION exits) gave back about 38R on 16 TARGET_FIRST plans, and the strategies themselves
   run at -0.27R per trade on platform exits (VWAP Sentinel 15m: -0.81R). "Any early exit near entry
   beats holding" is why most sentinel closes grade GOOD. A smarter close rule cannot fix a losing
   entry.
3. **The sample is tiny.** 128 closed trades since 09-19, 117 positions, 112 decisions, 19 LIVE closes,
   3 TIME_STOP closes. 77 of the 114 replayed positions are on two retired 15m agents. Anything that
   "learns" here must be built for n of about 100, with out-of-sample checks, not for machine
   learning.
4. **Nothing closes the feedback loop.** Trade outcomes (`netR`, `planOutcome`, `postExitMove`,
   `mfeR/maeR`) are read live from `list_agent_trades` and never written to the database; the one copy
   is a fixture JSON from 10-26. `decisions.review` is unused since #99. The eval harness feeds
   nothing. `allocate` and `review` only propose. No table aggregates by regime. Every improvement so
   far was a person reading a one-off report and committing a code change (the 10-26 `loss_r` fix).
5. **Cross-agent data exists and has never been called.** `get_agent_explorer`, `get_leaderboard`,
   `get_public_agent_realized_trades` (with `regimeAtDecision`, conviction, duration, closeReason),
   `get_public_agent_signal_logs` / `_detail` (per-condition outcomes), `get_public_agent_signal_performance`,
   `get_market_grid_results`. Neither OMEGA nor the manager has a single fixture of any of them.

So the honest reframing: **the system does not need a smarter per-tick model. It needs a loop that
turns outcomes into measured rule changes, aimed at the levers that actually move R, with the LLM
moved from "decider every 5 minutes" to "hypothesis generator every week".**

## 2. What exists already (do not rebuild)

| Piece | Where | State |
|---|---|---|
| Per-tick metric matrix, every open position, 5 min | `triage_rows.metrics` (5,606 rows, 118 positions) | r_now, tp_progress, bars, stop_distance_atr, ATR, PPO slopes, momentum now/t1, direction_qualifies, budget flags |
| Evidence pack per AMBER tick | `dossiers.document` (225) | position geometry, 6 platform reads (regime, qualification, budget, excursion, close_history, decided_stop), TPO panel row, tape (ATR, funding, OI, PPO hist) |
| Decisions with rationale | `decisions` (112), `actions` (217) | outcome, reason, rationale, mode, executed, review (unused) |
| 5-min path of every open position | `positions` (5,953 rows, 127 positions) incl. platform `raw` (conviction, riskRewardRatio, excursion, geometry) | |
| Entry attempts and rejections | `entry_decisions` (75), `gate_blocks` (481, pruned at 90 d) | failure_reason, gate_stage, reason_code, decisionRecord |
| Hourly TPO panel per coin | `panel_rows` (32,112) | prior/developing POC/VAH/VAL, distances, shape |
| Candle cache | `tape_bars` (7,924; 1m/5m/15m/1h/4h; 29 coins) + `manager/tape/hyperliquid.py` `candles_between` with startTime | |
| Scan ranks and allocation record | `agent_scans` (92k), `allocation_proposals` (105k, Wilson intervals per agent x coin) | |
| Strategy condition definitions per revision | `strategy_details` (24) | conditions JSON; nothing reads it |
| **Replay harness for close rules** | `manager/replay/*`, `manager replay closes` | rule sets as code, bootstrap 90% CI, both halves, slippage sensitivity; this is the prototype of the whole loop |
| Hindsight grading method | `close-decisions-report.md` | GOOD/BAD/UNCLEAR vs hold, with the TIME_DECAY caveat on planOutcome |
| Eval harness (model comparison) | `eval_*` tables, `manager/eval/` | Layers 1-3; Layer 4 (counterfactual value) designed, not adopted |
| Sample-size discipline | OMEGA `docs/10-outcome-feedback.md`, `allocation/performance.py` | MIN_SAMPLE 20, Wilson, lift; refuse to answer below the sample |
| Policy versioning with meta-bounds | `policy_versions`, `risk/policy.py` | auto-apply inside bounds, NEEDS_USER outside; the pattern for rule versions |

## 3. The levers, ranked by what the data says they are worth

| Lever | Evidence of size | Data needed | Who acts today |
|---|---|---|---|
| A. Entry quality: which strategy conditions, coins, timeframes, regimes, hours have edge | strategies at -0.27R/trade; VS -0.81R; 70 platform exits -$1.85 | per-condition outcomes (`get_signal_log.conditionEvaluation`, `gate_blocks.decisionRecord`, `get_radar_close_decisions.evidence`), entry-time context, cross-agent trades | nobody; strategist reads no trades |
| B. Protection config: break-even, trailing, TIME_DECAY, INVALIDATION | about 38R given back on 16 TARGET_FIRST plans; INVALIDATION exits -1.53R mean | stop schedules from `get_position_audit_history`, 1m/5m candles, a stop-schedule simulator | the user, by hand on the platform |
| C. Allocation: which agent x coin (x regime) gets capital | allocator ranks by lifetime Wilson only; no regime slice | `trade_outcomes` joined to `trade_context` | `allocate` proposes, `review` proposes, user takes |
| D. Close rules: thresholds and the HOLD/TIGHTEN/CLOSE policy | +6R total; `loss_r` 0.5 was +3.28R on replay, CI [+1.24, +5.66] | already in the replay | code commits |
| E. Risk presets and sizing | presets moved on rulings; BELOW_EXCHANGE_MINIMUM 42 of 75 entries | wallet, headroom, proven edge | user |

D has the harness and is the cheapest to close end-to-end. A and B are where the money is. C is
half-built. E is user-gated by ruling and stays so.

## 4. The loop

Eight stages. Every stage is a Docker job or a CLI command that writes a table; the LLM appears in
exactly one of them.

```
 collect -> label -> score -> hypothesize -> test (replay) -> propose -> apply (gated) -> verify forward
    ^                                                                                        |
    +----------------------------------------------------------------------------------------+
```

### 4.1 Collect (continuous, new jobs)

- **Outcomes after close.** A job that reads `list_agent_trades` (quality block, postExitMove,
  `debriefVerdict`, `signalLogId`, `decisionId`) and `get_trade_outcome_by_decision` (closedBy,
  exitRepriceSource, duration). Writes `trade_outcomes`. Backfill from the 10-26 fixture plus a
  LIFETIME read. (`get_signal_debrief` is not needed: the trade list carries the verdict, and the
  tool is not on the manager's allowlist.)
- **Context at entry.** When a new position first appears, write `trade_context`: agent, strategy id
  and revision, timeframe, coin, direction, regime / momentum / structural_bias (from the dossier
  reads or `get_regime_snapshot`), ATR%, funding, OI, nearest `panel_rows` TPO columns, scan rank
  for the pair, conviction and riskRewardRatio (from `positions.raw`), hour UTC, weekday, leverage,
  size, open-position count, wallet, hard-stop / decided-stop ratio. About 40 columns, one row per
  trade. **This is the "data matrix" the user asked for.**
- **Stop schedule.** From `get_position_audit_history`: every SL_PLACED / SL_REPLACED with
  `repriceSource`, so lever B can be simulated.
- **Condition outcomes.** From `get_signal_log.conditionEvaluation` per entered trade and the
  `decisionRecord` of each gate block: which clauses were true/false at the decision. Writes
  `condition_observations`.
- **Cross-agent pulls (daily, lever A and C).** `get_agent_explorer` (top 100 by window P&L),
  `get_leaderboard`, then per public agent `get_public_agent_realized_trades` (window 30D) and
  `get_public_agent_signal_performance`. Writes `platform_agents`, `platform_trades`. Budget: a few
  hundred calls a day under the 2 rps limiter. First a probe spike, since no read has ever been made.

### 4.2 Label (daily)

- **Hindsight grade per decision**, automated from the report's method: realized netR vs the hold
  counterfactual (replay's `simulate`), postExitMove direction, a `plan_unreliable` flag when the plan's
  STOP_FIRST fell inside the TIME_DECAY window, latency (dossier built_at to fill). Writes
  `decision_outcomes`. Also grades the counterfactuals: SHADOW and REFUSED CLOSE decisions, which run
  to the platform's exit, are free "hold" labels.
- **Trade labels**: `planOutcome`, win, R buckets, "stopped by decay before target".

### 4.3 Score (weekly, materialized)

`scorecards`: per agent, reason, timeframe, regime, coin, hour-band; n, mean netR, hold-vs-close
delta, GOOD/BAD/UNCLEAR counts, Wilson bounds. Below MIN_SAMPLE the row says INSUFFICIENT, never a
rate (OMEGA doc 10's rule). `condition_stats`: per strategy condition, lift (win rate when true minus
when false), n. Platform scorecards from `platform_trades`: expectancy by strategy name / timeframe /
coin / regimeAtDecision / closeReason across other agents.

### 4.4 Hypothesize (weekly)

Three sources, all producing the same artifact, a **rule-set spec** the replay can run:

1. **Grid**: automatic sweeps over the existing thresholds and over the TIME_STOP variants already
   coded (`timestop_v2` knobs), per timeframe.
2. **The LLM as analyst.** The Commander (or a new weekly `analyst` profile, free model) gets the
   scorecards and the last experiments, and must answer in a constrained schema: `{hypothesis,
   lever, rule_spec, expected_effect, evidence_rows}`. It never touches a position. This is where the
   user's wish "make it smarter" lands: judgement about *what to test*, not per-tick execution.
3. **The user**, through the Commander chat ("test closing at 1 bar on 4h").

### 4.5 Test (replay, extended)

`manager replay closes` is the kernel. Extensions needed, in order:
- rule-set specs from the database (`experiments.rule_spec`) instead of only from code;
- **forward holdout**: tune on trades before a cut date, score on trades after it; the current
  "two halves" check becomes mandatory;
- lever B: a stop-schedule simulator over 1m/5m `tape_bars` (grace, step, floor as the audit history
  shows them) so break-even / trailing / decay variants can be scored;
- lever A/C: not a replay but a scorecard comparison (which pairs or conditions to deploy, pause,
  resize), with the same acceptance rule.

Acceptance rule (proposal): n >= 30 affected positions, positive in both halves, bootstrap 90% CI
excludes 0, holds at 0.10R slippage, and does not change the picture on any single agent by more
than the fleet effect. Writes `experiments` with the full result, win or lose. Losing experiments are
kept: they stop the same hypothesis being re-proposed.

### 4.6 Propose

An accepted experiment becomes a `review_proposals`-style row with its evidence attached
(`PROPOSE_RULE_VERSION`, `PROPOSE_PROTECTION_CHANGE`, `PROPOSE_PAIR_CHANGE`, `PROPOSE_STRATEGY_REVISION`).
The Commander reports it in chat. The user `take`s or `dismiss`es, as with the 4F review today.

### 4.7 Apply (gated)

- Close-rule thresholds move from a code constant to `rule_versions` with meta-bounds, exactly as
  `policy_versions` works: a taken proposal inside bounds applies; outside bounds it is NEEDS_USER.
- Protection changes are `agent_config` actions under the existing budget (12 a day) and the
  platform-first hold rule (a user change on the platform wins until the next close).
- Pair changes are the existing 4F Radar kinds.
- Strategy revisions go to the strategist as a brief, then through stage -> preview -> commit on the
  user's word. **Never auto-committed.**
- Sentinel skill text that quotes a threshold is rendered from `rule_versions`, so the prompt and the
  rules cannot drift apart again.

### 4.8 Verify forward

After an apply, the next N decisions under the new version are compared with the experiment's
prediction. A `rule_versions` row carries `predicted_delta_r`, `observed_delta_r`, `n_observed`. If the
observed effect is outside the CI after N, the loop proposes a revert. This is the same shape as the
shadow -> live gate (7 days, 20 reviewed, 0 vetoes).

## 5. What the LLM does, and does not do, after this

- Per tick: unchanged for now. The sentinel keeps deciding AMBER dossiers, but the dossier gains one
  small, evidence-only `scorecard` section: "on this agent, STOP_PROXIMITY closes at bars 1-2: 6 GOOD /
  2 BAD, mean delta +0.31R (n=8)". The skill tells it to weigh, not obey. Memory stays off: the user's
  ruling that the sentinel is stateless by design stands, and the learning lives in Postgres.
- Weekly: the LLM reads scorecards and proposes experiments in a schema. Judgement moves to where
  one wrong call costs nothing.
- Open decision 8.4: whether to go further and let the deterministic rule set decide per tick (it
  matches the sentinel 87%, never misreports its mode or reason, and costs no model turn), with the
  LLM kept for the weekly role only.

## 6. Tables to create (candidate list)

| Table | Grain | Purpose |
|---|---|---|
| `trade_outcomes` | one per closed trade | the platform's quality block, post-exit moves, debrief verdict, closedBy, duration |
| `trade_context` | one per trade, at entry | about 40 features; the data matrix |
| `stop_schedules` | one per stop event per position | SL_PLACED / SL_REPLACED, source, price, time |
| `condition_observations` | one per (trade or gate block) x condition | clause truth at decision; feeds lift |
| `decision_outcomes` | one per decision | realized vs hold counterfactual, grade, flags, latency |
| `scorecards` | per slice per week | n, mean R, delta R, Wilson bounds, INSUFFICIENT below sample |
| `condition_stats` | per strategy condition per week | lift, n |
| `experiments` | one per hypothesis tested | lever, rule_spec, window, results, verdict, proposed_by |
| `rule_versions` | one per applied rule set | thresholds, bounds, provenance experiment, predicted and observed delta |
| `platform_agents` | one per public agent per day | explorer KPIs, public config spec, leaderboard rank |
| `platform_trades` | one per public realized trade | entry/exit, netPnl, regimeAtDecision, conviction, duration, closeReason |

Retention: none of these are pruned (the 90-day prune stays on scans and gate blocks; gate block
`decisionRecord`s worth keeping are copied into `condition_observations` first).

## 7. How deep "learning from the whole platform" can go

- **Yes, cheaply:** expectancy by strategy name, timeframe, coin, regime, hour and close reason across
  other agents' realized trades; which public config specs (modules, trading spec) the top of the
  leaderboard uses; conviction calibration across agents. Multiplies n by 10 to 100 for lever A and C,
  and is the natural input to OMEGA's end goal, the strategy-creation assistant.
- **Yes, with care:** per-condition outcomes of other agents' signal logs (`get_public_agent_signal_log_detail`
  gives each condition's name and outcome). This is the richest cross-agent signal and the most calls.
- **No:** other agents' private edge (overlay, sizing, daily cap) is hidden; their stop schedules are
  readable only for ACTIVE agents; no point-in-time market read exists, so their trades can be joined
  to regime only through `regimeAtDecision` and to our own accumulated `panel_rows` / `tape_bars`.
- **Biases to write down before trusting it:** survivorship (explorer lists what is active), the
  platform's own protection applies to everyone (so "closeReason" statistics describe the platform's
  stops as much as the strategies), and a public agent's "strategy name" is a label, not its
  conditions.
- **Market Grid** (crowd consensus, session results) is a different game and is left out unless the
  user wants it.

## 8. Decisions (2026-10-27)

1. **Which lever first. The user's decision:** collect + label stages (4.1, 4.2) first, then lever A
   (entry quality) with the cross-agent pulls. Close-rule tuning (lever D) and the sentinel's
   per-tick path are not touched by the first build.
2. **Autonomy of apply. Claude's call for the first build:** report-only. The first build produces
   scorecards and a weekly report; it writes no `review_proposals` rows and nothing in it applies a
   change (proposal rows arrive with the experiments stage, step 5). Whether to auto-apply inside
   meta-bounds later is decided when there is a verified proposal to point at, not before.
3. **Cross-agent reads. The user's decision**, implied by "with the cross-agent pulls": live calls to
   the public reads are in scope. **Claude's call:** the first live calls are a bounded probe (one
   explorer page, one leaderboard page, one agent's realized trades and signal performance), stored
   as fixtures and reviewed for shape, size and rate cost before the daily pull is switched on.
4. **The sentinel's per-tick role. Claude's call:** unchanged. The LLM keeps deciding AMBER
   dossiers exactly as today; the `scorecard` dossier section (5) is deferred with lever D. The
   first build adds no model turn anywhere: the analyst role (4.4) comes with the experiments stage.
5. **Lever B scope. Claude's call:** deferred. `stop_schedules` and the simulator are not in the
   first build. The audit-history read that would feed them is already in every dossier, so nothing
   is lost by waiting.

Calls 2, 4 and 5 keep the first build to tables and jobs that read, grade and report. The user can
overrule any of them; none changes what the first build writes.

## 9. Constraints carried over (not up for debate here)

- Binding, deployment and funding are user-gated per instance. Strategy commits are on the user's word.
- A change the user makes on the platform wins until that agent's next close; automation may lower a
  user-set limit, never raise it.
- Free models only for every Hermes profile.
- The sentinel is stateless between ticks; nothing learned is injected as memory.
- Read-only platform calls stay under 2 rps with the shared bucket; a result over 150k characters is
  refused, so list reads page at 50.
- Below MIN_SAMPLE the loop reports INSUFFICIENT, never a rate.
- Everything that proposes a change writes the losing experiments too.

## 10. Sequencing

| Step | Delivers | Depends on | Build |
|---|---|---|---|
| 1 | `trade_outcomes`, `trade_context`, `decision_outcomes`, backfill since 09-19 | nothing | **first** |
| 2 | `scorecards` job (lever A slices only: agent, strategy revision, timeframe, coin, regime, hour band) + weekly Commander report | 1 | **first** |
| 3 | cross-agent probe, then `platform_agents` / `platform_trades` daily pull + platform scorecards | decision 8.3 | **first** |
| 4 | `condition_observations`, `condition_stats`; the strategist brief includes them | 1, 3 | **first** |
| 5 | `experiments` + replay reads rule specs from the DB + forward holdout + acceptance rule | 1 | later |
| 6 | `rule_versions` with meta-bounds; thresholds and skill text rendered from it; dossier scorecard section | 5 | later |
| 7 | stop-schedule collection and simulator (lever B) | decision 8.5 | later |
| 8 | weekly analyst turn proposing experiments in schema | 2, 5 | later |

### 10.1 What the first build is, in one paragraph

Four new Docker jobs and a backfill command in `battlegrid-manager`: an outcomes collector that
writes `trade_outcomes` and `trade_context` for every position the snapshot has seen; a daily
labeller that writes `decision_outcomes`; a daily cross-agent pull that writes `platform_agents`,
`platform_trades` and `condition_observations`; and a weekly scorer that writes `scorecards` and
`condition_stats` and hands the Commander a report. Every rate is INSUFFICIENT below MIN_SAMPLE 20.
No job applies anything, calls a model, writes a proposal row, or writes to the platform. Done looks
like: the backfill reproduces the 10-26 report's grade for every CLOSE decision the report graded on
plan data and sets `plan_unreliable` on the ones it re-graded by hand; the first weekly scorecard
names which agent x timeframe x regime slices show an edge under the rule in section 11 (or says
INSUFFICIENT); and the strategist can read `condition_stats` for every live strategy through a
manager tool.

### 10.2 Left to the builder

- Exact column lists and types; the feature list in 4.1 is the minimum, not the ceiling.
- Which existing module hosts each job (the snapshot, allocation and review services are the
  patterns; one Compose service per job is the user's standing rule).
- How `trade_context` is filled for positions that opened before the collector existed (backfill
  from `positions.raw`, `triage_rows`, `panel_rows` and `tape_bars` at the entry minute; mark the
  columns that cannot be recovered as NULL rather than estimated).
- The report's shape in the Commander chat, within the existing review-report conventions.

## 11. Builder check (2026-10-27): the calls made

A fresh reviewer read sections 1-10 and the manager code and asked six questions. None needs the
user; each is settled here as Claude's call and can be overruled.

1. **Hindsight grades.** `decision_outcomes` grades against the plan-based hold counterfactual
   (`replay.simulate`, the decided stop), with `plan_unreliable = true` whenever the plan's
   STOP_FIRST fell inside the TIME_DECAY window or the live stop was never re-priced after the
   close. The six 10-26 decisions the report re-graded by hand against 4h candles are expected to
   carry that flag, not to match; a faithful live-stop path is lever B. HOLD and TIGHTEN decisions
   get the mirror grade: realized netR against a close at the decision's mark, GOOD above the
   report's margin, BAD below it, UNCLEAR between.
2. **The false side of lift.** Since contract 108 every entered trade has its gating conditions
   true, so lift on them cannot come from entered trades. `condition_observations` therefore also
   takes the manager's own agents' non-entered signal logs (`failedConditionKeys`, NEITHER verdicts)
   and labels them with a forward return from `tape_bars`: the move over 4 bars of the strategy's
   timeframe from the evaluation close, in ATR units at that time, NULL where the bars are missing.
   `condition_stats` then has a false population. A row with no false side says INSUFFICIENT.
3. **What "edge" means on a scorecard.** Every slice stores n, win rate (win = netR > 0) with
   Wilson bounds, mean netR with a bootstrap 90% CI, and the slice's break-even win rate
   (avgLoss / (avgWin + avgLoss)). The report calls a slice an edge only when n >= MIN_SAMPLE and
   the bootstrap CI on mean netR excludes zero; the Wilson lower bound against break-even is shown
   beside it, never alone.
4. **Report, not proposals.** The first build writes no `review_proposals` rows (see 8.2), so
   nothing it produces can reach `manager review take` or the executor.
5. **How the strategist sees condition stats.** The strategist profile has no tools, no MCP server
   and no skills by design (`hermes/install_strategist.py`), so a read tool cannot reach it.
   Instead `manager/strategist/turn.py`'s `build_messages` appends a `CONDITION STATS` block for
   the chat's strategy after the module menu it already injects, rendered from `condition_stats`,
   capped at 4000 characters and omitted when there are no rows; each row names the `conditionKey`
   and the metric code stem so the model can map it to OMEGA's modules. The brief gains one
   sentence saying the block is measured on the user's own agents and what INSUFFICIENT means.
   (Corrected 2026-10-27 after reading the code: the earlier text assumed a tool allowlist.)
6. **Public per-condition signal logs** are not in the daily pull. The probe (8.3) takes one page of
   `get_public_agent_signal_logs` and one `_detail` so their size and shape are on record for a
   later step; the daily pull is explorer, leaderboard, realized trades and signal performance.
