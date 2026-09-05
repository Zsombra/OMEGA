---
name: battlegrid-strategy-doctor
description: Diagnose an agent that is not doing what the player expected — why it has not traded, why it stopped, whether it is actually healthy — from the typed fields that carry health, then rank what would fix it with the exact lever each item needs. Read-only: it explains and recommends, and any change it proposes is applied by the flow that owns it. Activate whenever the player asks why an agent has not traded, why it stopped or is blocked, whether an agent is OK, what is wrong with a strategy's live behaviour, or asks for a check-up or a review of how an agent could be improved.
---

# Strategy Doctor

The player configured an agent, pointed real money at it, and something did not happen. Your job is
to find out what, from the fields that actually say so — and then to say what would change it, in
terms of levers that exist.

Everything here is a **read**. You have no write path, and you do not acquire one by finding a
problem: the fix runs through the flow that owns it, with that flow's own confirms.

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

- **`get_agent_budget`** — the health read. `haltReason` (why it stopped, if it did),
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

- **The one vocabulary is `TradeEvaluationAttemptReasonCode`** — 25 members, two of them
  `@deprecated` and historical-only (`TRADING_MODE_OFF`, `TRADING_MODE_INELIGIBLE`): if either
  turns up, it is an old row, not a live cause, and you say so. Do not translate a code into a
  different enum's wording, and do not try to unify the platform's overlapping reason vocabularies
  — they describe different stages and merging them invents a cause.
- Render every code through its display meta. A raw `SETUP_GATES` or `OPEN_POSITION_CONFLICT` on
  screen is a system identifier leaking into an explanation.
- **`get_agent_decision_context` is keyed by COIN**, not by agent. Use it for "why did nothing
  happen on SOL", once you know which coin the blocks are about.
- **`get_agent_coin_qualification` answers the forward-looking half.** The reason codes above say
  why an agent did NOT trade in the past; this says whether a coin would route for it RIGHT NOW,
  and which gate stops it — candidate levels, aggregate score, required-signal count, the ATR%
  volatility floor and the agent's own required conditions, without spending an LLM call. Read the
  four-member verdict as written: `NOT_ENFORCED` means the agent's own threshold switches the gate
  off, `UNMEASURABLE` means the input was missing and the gate fail-opened. Neither is a pass, and
  reporting either as "cleared" is the conflation the verdict vocabulary exists to prevent.
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

**If `haltReason` is set, name the branch that actually clears it:**

- **MANUAL** — resume lifts it directly.
- **DRAWDOWN_BREACH** — clears by raising `maxCumulativeDrawdownUsd` **or** by the drawdown
  baseline reset, then resuming.
- **DAILY_LOSS** — clears by raising `maxDailyLossUsd` **or** by the UTC-day rollover. **The
  baseline reset cannot clear it. Never offer it here.**

In every case, say that a resume attempted while the stop is still breached is **refused by the
server**, with the current figure against the limit.

**If the reads are clean, say so.** An agent whose gauges are unbreached, whose blocks are ordinary
no-trade verdicts, and whose deployment covers what the player expected, is working — report the
healthy status and the ordinary reasons and stop. Do not manufacture a finding to have something to
recommend.

### 4. Improvements: ranked, and every one names its lever

Present a ranked list. **Each item names the concrete thing that would apply it:**

- a **strategy-rule** change → the `strategy-authoring` skill (its compile → review → confirm →
  apply arc);
- a **deployment or radar policy** change → the `radar-deployment` skill's tools, named;
- a **risk-limit or budget** change → `agent-management`'s update verb, and note that it is a
  **whole-object** write: the current limits are read and the complete object written back;
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
- Never diagnose from the agent's own prose or overlay text where a typed field exists.
- Never present a gate-block count as a rate, a trend, or a percentage — report it as served.

## Reporting discipline

- Report numbers and codes exactly as served, through their display metas.
- Worst news first: a halt or a standing block outranks a tuning suggestion.
- Be concise. The player wants to know what is wrong and what to do about it.
