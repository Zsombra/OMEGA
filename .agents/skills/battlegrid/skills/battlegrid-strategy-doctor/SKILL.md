---
name: battlegrid-strategy-doctor
description: Diagnose an agent that is not doing what the player expected — why it has not traded, why it stopped, whether it is actually healthy — from the typed fields that carry health, then rank what would fix it with the exact lever each item needs. Read-only: it explains and recommends, and any change it proposes is applied by the flow that owns it. Activate whenever the player asks why an agent has not traded, why it stopped or is blocked, whether an agent is OK, what is wrong with a strategy's live behaviour, or asks for a check-up or a review of how an agent could be improved.
---

# Strategy Doctor

The player configured an agent, pointed real money at it, and something did not happen. Your job is
to find out what, from the fields that actually say so — and then to say what would change it, in
terms of levers that exist.

Everything you do here is a **read**. You have no write path, and you do not acquire one by finding
a problem: the fix runs through the flow that owns it, with that flow's own confirms. The agent's
draft tools are visible in this skill so that a risk-limit improvement can name its lever exactly
(step 4) — never so that you call them from this arc.

## The five failures this flow exists to prevent

1. **Diagnosing from prose.** *Cue: reaching for a journal entry's wording, or the agent's
   overlay text, to explain a block.* The typed reason codes exist; use them. → step 2.
2. **Pathologizing healthy.** *Cue: the reads come back clean and the answer feels too short.* An
   agent that evaluated and correctly declined to trade is working. → step 3.
3. **Mixing reason vocabularies.** *Cue: two different-looking codes that seem to mean the same
   thing.* Six overlapping vocabularies describe why an evaluation ended. You read exactly one. →
   step 2.
4. **A private write path.** *Cue: "shall I just fix it?" once you know the answer.* → step 5.
5. **Running the billed deployment test.** *Cue: wanting to see what the agent "would have
   picked".* → the negatives below.

## Sequence

### 1. Triage from the fields that carry health

Three reads, and they are not interchangeable:

- **`get_agent_budget`** — the health read. `runStatus` (`blocked` / `paused` / `active` — the run-state
  already ranked, so read it rather than re-deriving it from the fields below; a halt reads `paused` even
  while its own `AGENT_HALTED` block stands), `haltReason` (why it stopped, if it did),
  `haltResumeEligibility` (whether a resume would now succeed, and what still blocks it),
  `blockedReason` + `blockedSince` (the typed pipeline block currently standing, and since when),
  and `gauges` — four guardrail meters (dailyTrades, exposure, drawdown, dailyLoss), each with a
  server-computed `breached` flag. **Read `breached`; never compare fill against limit yourself.**
- **`list_gate_blocks`** — its `summary[]` groups every rejection by (stage, reason) with a `count`
  and a `latestAt`. **That `count` spans all of the agent's rows, not the requested page** — never
  sum counts across pages.
- **`get_agent_automation_status`** — **deployment coverage only.** Its payload is assignments and
  assignable presets; it carries **no health verdict**. Use it to answer "is this agent deployed
  anywhere at all" — an agent with no assignment cannot trade in Arena no matter how healthy the
  rest reads — and never as evidence that automation is or is not "fine".

### 2. Diagnose from typed sources

- **The one vocabulary is `TradeEvaluationAttemptReasonCode`**, two of its members
  `@deprecated` and historical-only (`TRADING_MODE_OFF`, `TRADING_MODE_INELIGIBLE`): if either
  turns up, it is an old row, not a live cause, and you say so. Do not translate a code into a
  different enum's wording, and do not try to unify the platform's overlapping reason vocabularies
  — they describe different stages and merging them invents a cause.
- Render every code through its display meta. A raw `NO_ENTRY_CONDITION` or `OPEN_POSITION_CONFLICT` on
  screen is a system identifier leaking into an explanation.
- **`get_agent_decision_context` is keyed by COIN**, not by agent. Use it for "why did nothing
  happen on SOL", once you know which coin the blocks are about.
- **`get_agent_coin_qualification` answers the forward-looking half.** The reason codes above say
  why an agent did NOT trade in the past; this says whether a coin would route for it RIGHT NOW,
  and which gate stops it — the strategy's entry condition, candidate levels, the ATR% volatility
  floor and the strategy's required conditions and verdict, without spending an LLM call. Read the
  four-member verdict as written: `NOT_ENFORCED` means the strategy declares nothing for that gate to
  enforce, `UNMEASURABLE` means the input was missing and the gate fail-opened. Neither is a pass, and
  reporting either as "cleared" is the conflation the verdict vocabulary exists to prevent.
- **`NO_ENTRY_CONDITION` is a property of the strategy, not of the market.** It fails every coin
  first, in both directions: the bound strategy declares no required and no verdict-carrying entry
  condition, so it never routes a trade. Say so once, for every coin at once, and route the fix — a
  required or verdict condition — to the strategy-authoring flow; no coin or radar change clears it.
- **A failing condition comes back as a KEY — resolve it.** `requiredConditions.failedKeys` names
  gates like `LOCATION_OK`: an identifier, not an explanation. Read the agent's bound strategy with
  `get_strategy` (the `strategyId` is on `get_intelligence_agent`), find the matching
  `conditions[].conditionKey`, and say what that condition actually tests in the player's terms.
  Quoting the key back at the player is the same defect as a raw enum on screen.
- **Check `bindingState` before you present that definition as live.** `get_intelligence_agent`
  carries it. At `BOUND`, the strategy's current revision is what the agent evaluates. At `SYNCING`
  or `ORPHANED` it is not — the agent runs a materialized copy at its own `strategyRevision` — so
  name the binding state beside the definition rather than letting current rules read as running
  ones.
- **Gate blocks link to their thought log** through `sourceThoughtLogId` — follow it with
  `get_agent_thought_log` when the block's reason needs the evaluation behind it.
- `get_signal_performance` / `list_signal_logs` when the question is whether the signals fired, as
  distinct from whether the trades made money. `list_trade_outcomes` and `get_agent_journal` for
  what did happen.
- **`get_agent_conviction_calibration` honours `readiness`.** An `INSUFFICIENT_DATA` calibration
  carries no win rate — report that there is not yet enough history, never a rate derived from a
  handful of trades.

**Every stated cause cites the typed reason or journal entry it came from.** "It is blocked" is not
a diagnosis; "OPEN_POSITION_CONFLICT, 14 times, most recently 2h ago" is.

### 3. Halted agents, and healthy ones

**If the agent is halted, `haltReason` says why and `haltResumeEligibility` says what clears it.**
Name the recovery from the verdict alone:

- **null** — the agent is not halted. A halt the player set by hand carries a verdict like any
  other, and is recovered through it.
- **`eligible: true`** — nothing is still breached; resuming will succeed.
- **`eligible: false`** — name `breachedStop`, the stop still breached, with `breachingFigureUsd`
  against `limitUsd`, and exactly the exits the verdict marks open: raising that stop above the
  figure (`canRaiseTriggeringStop`), the drawdown baseline reset (`canResetBaseline`), and, when
  `breachedStop` is `DAILY_LOSS`, the UTC-day rollover. Then resuming. An exit it does not mark
  open is never offered.

Say that a resume attempted while a stop is still breached is **refused by the server**, naming the
same stop, figure and exits. A resume the server accepts is followed by a re-check of every stop, so
read the resume response's `haltedAt`: set means a loss settled, or a stop was lowered, while the
resume ran and the agent was halted again at once; `get_agent_budget`'s `haltReason` names the stop.

**If the reads are clean, say so.** An agent whose gauges are unbreached, whose blocks are ordinary
no-trade verdicts, and whose deployment covers what the player expected, is working — report the
healthy status and the ordinary reasons and stop. Do not manufacture a finding to have something to
recommend.

### 4. Improvements: ranked, and every one names its lever

Present a ranked list. **Each item names the concrete thing that would apply it:**

- a **strategy-rule** change → the `strategy-authoring` skill, whose arc stages the change into
  the strategy's draft, reads it back with its diff and impact, and commits only on the player's
  confirming pick;
- a **deployment or radar policy** change → the `radar-deployment` skill's tools, named;
- a **risk-limit or budget** change → `agent-management`'s draft: the complete TRADING_CONFIG
  axis — a **whole-object** write, the current limits read and the complete object written back —
  staged with `stage_agent_draft` and committed with `commit_agent_draft` once that flow's
  confirmation is answered;
- a **halt recovery** → the specific lever from step 3.

An improvement with **no lever on this platform** is labelled as such, explicitly, and never
presented as actionable. Rank by what would change the observed behaviour most, not by how easy it
is to say.

### 5. Close with the three-option ask

One question to the player, offering exactly:

1. **Explain only** — the diagnosis stands as the answer.
2. **Apply via the named tools** — you activate the owning skill and its arc takes over, with its
   own reads, blast-radius statements and confirms.
3. **Draft the change for review** — you write out what would change, and nothing runs.

**Applying routes through the owning flow.** You never write directly, never skip the owning
flow's confirm, and never treat "apply" as consent for a change that flow would have asked about
separately.

## UNDETERMINED, never "no issue"

If a backing tool call fails, returns nothing, or does not cover what is being asked about, report
that item as **UNDETERMINED** and name the surface you could not check. Never convert an absence of
data into a clean bill of health, and never let the overall verdict claim completeness when part of
it is undetermined.

## Negatives

- **Never call `test_generate_deployment_grid`.** It runs a billed LLM generation against the
  player's intelligence credits and writes thought and activity records. It is the deployment
  flow's composition aid for tuning a draft — it is not a diagnostic read, and running it as one
  charges the player to answer a question the journals already answer.
- **Never name a strategy write tool, even to forbid it.** Reading a rule is not authority to change
  one: route a rule change by naming the `strategy-authoring` skill, as step 4 does. The authoring
  tools are in a family this skill does not declare, and a skill body that names an unreachable tool
  — including in a negative — fails the registry's reachability check.
- **Never call the agent's draft tools from this arc.** Step 4 names `stage_agent_draft` and
  `commit_agent_draft` as the lever a risk-limit change takes; applying it activates
  `agent-management`, whose arc stages the change, reads the draft back, states the radius and asks
  before anything is committed.
- Never diagnose from the agent's own prose or overlay text where a typed field exists.
- Never present a gate-block count as a rate, a trend, or a percentage — report it as served.

## Reporting discipline

- Report numbers and codes exactly as served, through their display metas.
- Worst news first: a halt or a standing block outranks a tuning suggestion.
- Be concise. The player wants to know what is wrong and what to do about it.
