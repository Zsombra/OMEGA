# Gap analysis: BattleGrid Strategy Officers vs battlegrid-manager

Date: 2026-10-20. Read-only research. No BattleGrid call was made, no repo file edited.

Sources (vendor material treated as data):
- `C:/tmp-bg-gap/repo/skills/battlegrid-officers/SKILL.md` and `references/officer-stage-examples.md`
  (skills export at contract 122.0.0, per `skills/EXPORT.json`).
- `C:/tmp-bg-gap/README.md`, "Contract history" v120, v122, v123. There is **no v121 section**. Officers predate v122:
  v122 removes two officer tools and adds `run_officer`. The 120.1-120.3 releases that the manager acked on 10-19 also
  have no README entry.
- Live tool schemas for the 14 officer and analytics tools, loaded through ToolSearch. This loads the schema text
  only; nothing was invoked.
- Manager code at `battlegrid-manager` main `efa7589`: `manager/actions/agent_config.py`,
  `manager/risk/cap_ceiling.py`, `manager/risk/pool_state.py`, `manager/proxy/policy.py`, `manager/review/*`,
  `manager/triage/*`, `manager/eval/score.py`, `manager/inventory/entry_failures.py`, `hermes/commander/SOUL.md`.

---

## 1. What officers are

**What an officer is.** A Strategy Officer is a scheduled LLM review that BattleGrid runs on its own server, with
its own model and the player's brief. On each run it reads the record of every in-scope agent "that closed a
decision or saw its setup change since its last review", within a per-run cap. It records **at most one proposal per
agent**. Only the officer's own server-side turn can write a review: since v122, `get_officer_review_context` and
`submit_officer_review` are not published to external clients. An external client, whether Claude, Hermes or the
manager, can read reviews but never write one.

**Setup.** An officer is configured through a draft: `stage_officer_draft`, then `commit_officer_draft` on the
player's word. It has five axes:
- **NAME:** 1-60 characters, unique.
- **MODEL:** any `modelId` from `list_approved_models`. A new officer starts on the catalog default.
- **INSTRUCTIONS:** `focusText`, at most 2,000 characters, naming no tool and no id.
- **SCHEDULE:** `OFF`, `DAILY` or `WEEKLY`, with `hourUtc` and, for `WEEKLY`, `weekdayUtc`. The default is `DAILY`
  at 03:00 UTC.
- **SCOPE:** the agents it reviews (`'ALL'` or a list of ids) and its `levers`. Levers are a non-empty subset of
  `strategy`, `agent` and `radar-deployment`. The default is all active agents and all three levers.

The roster is limited: a create's `admission` reports `officersRemaining`. `list_officers` serves `presets` to start
from.

**What it reads.** The agent's own record: decisions, outcomes and stops. The schema descriptions point at the same
figures the new analytics tools serve: premature stops, exit quality, rail refusals and the condition slices. The
platform exposes the officer's actual context tool only to the officer.

**What it can write.** Only proposals. A proposal targets one of three drafts:
- **`agent` lever.** The agent draft's axes: IDENTITY, BEHAVIOR, MODEL, STRATEGY_BINDING (a rebind) and
  **TRADING_CONFIG**. TRADING_CONFIG is the complete nine-field config: caps, loss lines, leverage, presets,
  `maxDailyTrades`, slippage and balance threshold.
- **`strategy` lever.** The bound strategy: conditions and report. A committed strategy revision propagates to the
  bound agent.
- **`radar-deployment` lever.** The coin's Radar rules.

An officer has **no halt, resume or close path**. It never touches positions, funds or Arena. Halts appear only as
data: `get_agent_review_analytics.halt` and `railRefusals`, where a halt row maps to "ends on the owner's resume".

**From proposal to live.** Every step happens on the player's word:
- **Apply** (`apply_officer_proposal`). This pushes the proposal into the target's **empty** draft and commits it
  through the target's own commit. That commit is fenced on the proposal's base revision, so exactly the proposal is
  published live. Apply needs `mcp:wager`. The skill requires an `ask_user` confirmation naming the review, the
  target and the axis.
- **Refusals.** Each refusal writes nothing:
  - `DRAFT_NOT_EMPTY`: any draft is held.
  - `BASE_MOVED`: the target was committed since the review.
  - `TARGET_NOT_OWNED`: for example, the agent was rebound away from the strategy.
  - `PROPOSAL_INVALID`: the target's own validation now refuses the proposal.
  - Commit refused after the push: the review is left as `pushed`, with its axes still in the draft.
- **Push** (`push_officer_proposal`). This places the axes in the target's draft, stamped "Proposed by Strategy
  Officer", for the player to save in the editor. It is refused as `AXIS_HELD` when the draft already holds one of
  those axes.
- **Dismiss** (`dismiss_officer_review`). This closes the review and touches no draft. A dismissed agent is not
  reviewed again until it closes a new decision or the officer's setup changes.
- **Review statuses:** `open`, `pushed`, `applied`, `dismissed`, `superseded`. Each review carries `applyAvailable`,
  `heldAxes` (each held axis and who wrote it) and `baseMoved`.

Nothing is auto-applied. There is no setting that lets an officer apply its own proposals.

**Schedule.** Yes, an officer runs on its own:
- It runs DAILY or WEEKLY at its UTC hour. `OFF` keeps the setup and runs nothing.
- `run_officer` runs one now. It answers `QUEUED` with `agentCount`, `NOTHING_TO_REVIEW` (nothing queued or billed)
  or `ALREADY_QUEUED`.
- `list_officers` and `get_officer` serve `pendingRun`, `lastRunAt` and `nextRunAt`.

**Cost.**
- "Every officer run is billed to the player's LLM credit". "Each review turn spends your LLM credit like a Commander
  turn": one turn per in-scope agent with a new decision, up to the per-run cap.
- The gate is `commanderAccess`, not `llmAccess`.
- The model is chosen from the platform's approved catalog, so the spend is **platform credit**, not the user's free
  Hermes models.
- No per-run price is published. The cost is visible afterwards in `get_agent_review_analytics.llm` and
  `get_account_review_analytics` (LLM spend from platform credit and `netAfterLlmUsd`).
- **Unverified:** whether officer spend is counted inside the per-agent `last24h_cost_usd` that the manager's LLM
  budget guard sums (`manager/risk/lifecycle.py:221`, `actions/arena_describe.py:228`).

**Doc inconsistency.** On archiving:
- The skill says "an archived officer runs no more, and its open reviews stay in the inbox".
- The live `archive_officer` schema says its open and pushed reviews **read dismissed**.

Trust the live schema, and verify before relying on either.

---

## 2. Overlap and conflict with the manager

### 2.1 Component by component

| Manager component | Does an officer do the same job? | Conflict risk |
|---|---|---|
| **SYNC_LIMITS / exposure pool** (`agent_config.py`, `risk/pool*.py`): writes all 9 `tradingConfig` fields from policy and pool share | No. The officer is per-agent and evidence-driven, with no fleet pool and no policy. It proposes TRADING_CONFIG changes per agent. | **HIGH.** See 2.2. |
| **Cap ceiling** (`risk/cap_ceiling.py`): "outside edit = ceiling" | No | **HIGH.** It misreads an officer edit as the user's. See 2.2. |
| **Halt / resume / close actions, halt watch** | No. The officer has no halt or close path, and it does not resume. | Low. It may propose loosening loss lines on a halted agent. The platform still needs a RESUME, and the manager keeps the halt-watch path. |
| **Entry-fail watch** (`inventory/entry_failures.py`) | Partly. Analytics give the population view, and an officer could propose a preset or cap fix. | Medium. The watch says "the fix is the user's". An officer could propose that fix (presets or cap), which then collides with SYNC (2.2). |
| **Triage + dossiers + Sentinel shadow review** (`manager/triage/*`) | No. Triage works per open position, in real time (RED/AMBER), and the Sentinel judges positions. An officer runs daily on closed decisions. | Low. Different horizon. |
| **Daily fleet review 4F** (`manager/review/*`): deterministic Radar pause/deploy/resume proposals, taken by `manager review take` | **Yes, closest overlap.** Both are a daily review that proposes, with the user deciding. 4F uses no model and covers only Radar kinds. The officer is an LLM and covers strategy, agent and radar. | Medium. Two inboxes can propose contradictory Radar moves. An applied officer radar change can stale a 4F proposal, and vice versa. |
| **Eval harness** (`manager/eval/*`): compares Hermes models on Sentinel decisions, with excursions in R | No. The harness scores *our* decision models. | None. The analytics could supply ground truth (2.3). |
| **Strategist / strategy assistant tab** (plan `ac39055`) | **Yes, overlapping goal.** The strategy lever is "revise a live strategy from its record". The officer is scheduled and server-side on a paid catalog model. The strategist is chat-driven on a free model. | Medium. The two inboxes can target the same strategy draft (`AXIS_HELD` / `DRAFT_NOT_EMPTY` either way), and the strategist's revise flow should see open officer proposals. |
| **Commander** (`hermes/commander/SOUL.md`): read-only reporter that prepares decisions | Partly. Officers "prepare decisions" too. | None functionally, but the Commander cannot see officers. No officer or analytics tool is on `PROXY_ALLOWLIST` (`manager/proxy/policy.py`). `get_agents_hub` has carried `openOfficerReviewCount` since 120.3.0. |

### 2.2 How an applied officer proposal fights the manager

These follow from the code. None was observed live, because the account holds no officer (unverified; nothing was
read).

**Mechanism 1: TRADING_CONFIG is written whole, and SYNC owns four of its fields.** `build_trading_config` writes:
- `maxConcurrentExposureUsd` as the pool share, `min(share, ceiling)`;
- `maxDailyLossUsd` and `maxCumulativeDrawdownUsd` as the policy split;
- `maxLeverage` as `values.max_leverage`;
- `minAllocationUsd` clamped.

It carries the agent's own `maxDailyTrades`, `maxSlippageBps`, `balanceThresholdUsd` and `positionSizePresets`.

So when an officer changes:
- **The cap.** The tick that follows records it as an outside edit (see Mechanism 2), and the pool targets
  `min(share, ceiling)`. A **raise** is lowered back to the share. A **lowering** becomes a standing ceiling.
- **Leverage or a loss line.** `pool_resync_targets` compares these only for agents that were left out or halted by
  the pool. For any other agent the officer's value stands until the next `fleet_moved` (a policy version change, or
  a deployed-set change). Then SYNC **silently overwrites** it, with no alert. The officer may then propose the same
  thing again.
- **Presets above `max_risk_preset_pct`.** Every later SYNC for that agent **refuses** (`ConfigError ... exceeds
  max_risk_preset_pct`), so its cap stops following the pool. The fleet sync record (`sync_fleet`) is written only
  when every agent's sync is DONE, so one refused agent keeps the fleet resync retrying.
- **`maxDailyTrades`, slippage or balance threshold.** These persist, because SYNC carries them forward. No conflict.

**Mechanism 2: the cap-ceiling rule attributes every outside edit to "someone", and its rule text says the user.**
`record_outside_edits` treats any stored cap that differs from the baseline by a cent or more as an outside edit. It
records that cap as the agent's ceiling, **replacing the previous ceiling**, and files `CAP_SET_OUTSIDE_MANAGER` with
the user's 2026-10-16 ruling as its rationale. Two hazards follow:
- **The officer lowers the cap.** The manager now protects the officer's value as if the user had set it, until
  `manager pool ceiling clear`.
- **The officer raises the cap above a user ceiling.** Example: the user's ceiling is $13 and the officer applies $20
  while the share is $18.09. The new ceiling of $20 **erases the user's $13**. The pool then targets $18.09 and writes
  it. The manager raises exposure above the user's hand-set value, which is the exact 10-16 incident that
  `cap_ceiling.py` exists to prevent. The user did click Apply, but a proposal that touches the cap does not say "this
  replaces your ceiling".

The manager cannot tell who made an edit: it compares snapshots and does not read who committed the agent revision.
The officer's own audit trail is in `list_officer_reviews(includeClosed)` as `applied`.

**Mechanism 3: the manager's writes stale the officer's reviews.** Every DONE SYNC_LIMITS commits the agent, so its
revision moves. The pool resyncs whenever another agent opens or closes a position and the cap gap is at least $1,
which is often with two concurrent trades. So officer reviews on the **agent** lever will frequently read
`baseMoved` and refuse `BASE_MOVED`. The skill's recovery is "dismiss it for a re-review": wasted LLM spend and inbox
churn. Strategy-lever reviews are not affected, because SYNC never commits the strategy.

**Mechanism 4: drafts lock both sides.**
- A **pushed** officer proposal sits in the agent's draft. `held_draft_verdict` makes every SYNC_LIMITS refuse ("the
  manager never stages over a draft it did not write") until the user saves or discards it. In the meantime the pool
  cannot lower that agent's cap, so its exposure is stuck at the pre-push value.
- In the other direction, a leftover failed SYNC draft (P4-D2) makes `apply_officer_proposal` refuse
  `DRAFT_NOT_EMPTY`.
- The same applies to Radar drafts against 4C's radar actions, and strategy drafts against the strategist.

**Mechanism 5: the radar lever moves the fleet.** An officer applying a radar-deployment change that deploys or
undeploys an agent moves `deployed_agent_ids`. `fleet_moved` then re-divides the loss lines across the fleet and
resyncs every agent. That works as designed, but it means an officer can move every agent's limits in one Apply.

**Mechanism 6: model and rebind.** An agent-lever MODEL axis can move an agent to a costlier catalog model. The manager
guards model changes only on its own lifecycle path (`lifecycle_describe.py`, `--allow-costlier`). An Apply bypasses
that guard. STRATEGY_BINDING changes are allowed too. Rebinding a live agent is something the user's rules gate per
instance.

---

## 3. The new analytics tools: what they could replace or feed

All are single reads, carry `readiness` / `minSampleSize` (no value below the floor), and are owner-scoped. None is on
the manager's `PROXY_ALLOWLIST` today.

| Tool | What it serves | Manager feature it could feed or replace |
|---|---|---|
| `get_agent_entry_discipline(agentId, window <= 90 d)` | Share of gate reads taken from a still-forming bar, the "confirmation tax" (anchor to fill slippage, USD), fast stop-outs, adverse-before-favourable excursions, multi-bar holds, and a labelled pre-change baseline (not like for like). | **Not a replacement for the entry-fail watch.** The watch detects *refused* ENTERs (FAILED streaks, e.g. BELOW_EXCHANGE_MINIMUM). Entry discipline measures entries that *filled*. It **complements** the watch, and could feed the eval harness excursion layer (`eval/score.py`) and strategy revisions. |
| `get_agent_decision_quality(agentId)` | `filterValue` (ENTER vs SKIP forward return per horizon), `exitQuality.prematureStop`, verdict mix, conviction band vs return, exit outcomes, in-trade excursion and exit efficiency. | Feeds 4F review rules (today's PROVEN/LOSING is a 20-trade net test, `Perf.readiness`). It could replace part of OMEGA's own allocation performance read, and the 10-08 reversed-signal study computed by hand ("~0R edge either way" = `filterValue`). It gives the strategist ground truth for "is this strategy's gate worth anything". |
| `get_agent_cost_economics(agentId)` | Closed positions by how they ended (no stop fill, original stop, which repricer moved the stop), gross / fees / net, fees as % of gross, `costErodedCount`, `unreconciledCount`. | Replaces the hand fee analysis (10-08: fees 16.34 > gross edge 14.24). It feeds the review's observations, and answers "did break-even / trailing help" per repricer. |
| `get_agent_review_analytics(agentId)` | Sliced by regime, UTC hour, weekday, coin and cited condition (WON/LOST/SKIPPED/**UNFILLED**/PENDING). `llm` spend vs net. `railRefusals` for the four rail codes, each mapped to its `tradingConfigMember` (`maxConcurrentExposureUsd`, `maxDailyTrades`, `balanceThresholdUsd`) or null for a halt. The current halt. | The rail refusals are exactly what the pool deliberately causes (exposure-cap refusals), so they are a direct read on "is the pool starving this agent". The coin and regime slices feed 4F Radar rules (pause a losing coin pair). The `llm` block feeds the policy's `platform_llm_budget_usd_per_day` observation (`review.llm_spend_over_budget`). |
| `get_account_review_analytics()` | One row per active agent: net, fees, platform LLM spend, `netAfterLlmUsd`, closed trades, win rate, halt, `openReviewIds` / `openReviewCount`, plus totals. | The cheapest fleet read. It could serve a Commander "fleet scorecard" and the morning status. It is also the manager's **only way to see officer activity** without reading officer tools. |

**Expiring limit entries (what the user saw).**
- Under contract 26.0.0, the unfilled lifetime of a resting limit entry is a **platform_config TTL**, not agent
  config. No agent, officer or manager setting moves it.
- The entry-fail watch deliberately treats `EXPIRED` as neither counted nor streak-ending, so expiries are invisible
  to it today.
- Where they appear:
  - `get_agent_review_analytics.condition` counts **UNFILLED** outcomes per cited condition. This is the best fleet
    read of "how many decided entries never filled".
  - `get_agent_entry_discipline`'s confirmation tax shows the slippage cost when entries do fill.
  - Per decision, `list_entry_decisions` (status EXPIRED), which the manager already reads, and the activity
    `eventType` `ENTRY_EXPIRED_UNCONFIRMED`.
- A second watch rule ("N EXPIRED in a row") would be a small extension of `entry_failures.py`. It is detection only,
  like the existing one.

---

## 4. Recommendation

**Read-only adoption now. Do not let officers write to agents the manager governs. Do not replace manager parts yet.**

1. **Read-only adoption (low risk, recommended).**
   - Add `get_account_review_analytics`, `get_agent_review_analytics`, `get_agent_decision_quality`,
     `get_agent_cost_economics`, `get_agent_entry_discipline`, `list_officers`, `get_officer` and
     `list_officer_reviews` to `PROXY_ALLOWLIST`. All are reads, so the Commander can report them and quote officer
     proposals.
   - Each one needs the manager's usual review: read-only hint check, surface baseline, contract watch. Adding a tool
     also widens what drift reviews must cover.
2. **Feed, don't replace.**
   - Pipe decision quality, cost economics and review analytics into the 4F review document as observations: no new
     rule without a user ruling.
   - Pipe them into the strategist's revise context, and into the eval harness as ground truth.
   - Keep the entry-fail watch: the analytics do not detect refused-entry streaks in real time.
   - Optionally add the EXPIRED-streak observation.
3. **Make the manager officer-aware before any officer touches a deployed agent.** This is code work. Three changes:
   - (a) Snapshot `list_officer_reviews(includeClosed)`. When a cap change coincides with an `applied` agent-lever
     review, record it as `OFFICER_EDIT`, not as a user ceiling. At minimum, never let an officer-applied **raise**
     replace a lower user ceiling: keep `min(old ceiling, new)`.
   - (b) Treat a held draft whose axes are stamped "Proposed by Strategy Officer" as its own named verdict. Alert, so a
     pushed proposal does not silently freeze the pool for that agent.
   - (c) Alert, don't silently overwrite, when SYNC is about to revert a leverage or loss-line value that differs
     from the policy.
4. **Do not integrate officer writes into the manager** (calling apply/push from the manager). It would put a
   platform-model decision into the write path, against the user's free-models-only and per-instance gating rules. It
   also needs `mcp:wager`.
5. **Replace nothing.** 4F (deterministic, no model, Radar only) and officers (LLM, daily, three levers) overlap the
   most. Run them side by side read-only, and only then decide.

**Risks if the user creates an officer today with the defaults** (all agents, all three levers, DAILY at 03:00 UTC):
- Daily platform LLM spend on a catalog model.
- Agent-lever reviews often staled by pool resyncs.
- An Apply that touches TRADING_CONFIG can be reverted by SYNC, frozen as a false "user" ceiling, or, if it raises
  the cap, erase a user ceiling. That last case is the 10-16 failure.
- Presets above the policy maximum break SYNC for that agent.
- A rebind, a model change or a radar change bypasses the manager's own guards.

**Decisions for the user:**
1. Whether to create any officer at all, and if so its scope. The safest is levers `['strategy']` only, or
   `agent`/`radar-deployment` excluded for pool-governed agents, with cadence WEEKLY or OFF plus Run now.
2. Whether officer platform-LLM spend is acceptable, and whether it counts against `platform_llm_budget_usd_per_day`.
3. The ownership rule for `tradingConfig`. Either the manager owns the caps, loss lines and leverage, so officer
   agent-lever proposals on those fields are only advice, or an officer-applied value becomes a ceiling the manager
   honours. The current code does neither: it reverts some fields and freezes others.
4. Whether an applied officer proposal counts as "the user's word" for the cap-ceiling rule.
5. Approval to add the eight read tools to the allowlist, and to the officer-aware changes in item 3, which are code
   in battlegrid-manager.

Open checks before acting (unverified here):
- Whether the account holds an officer now (`list_officers`).
- Whether officer spend appears in `last24h_cost_usd`.
- The archive behaviour (skill vs schema).
- What `lastSource` a pushed officer axis carries on `get_agent_draft`.
