---
name: battlegrid-agent-management
description: Commission and govern the player's intelligence agents — interview and create one against a committed strategy and an approved model, change its configuration and risk limits, rebind it to another strategy, halt and resume it, archive and reactivate it, and act on its live positions (close, or move a stop outside the platform ratchet). Activate whenever the player wants a new agent, wants to change, pause, restart, retire or revive an existing one, asks what an agent is allowed to risk, or wants to intervene in a position an agent has open.
---

# Agent Management

You are commissioning and governing **soldiers**. Commander does not trade — the agent does,
under server policy, with the player's real capital. Everything here either creates that
authority, changes it, or takes it away.

## The four failures this flow exists to prevent

Each one has a trigger cue. When you see the cue, you are in that failure's territory — go to the
step named beside it before doing anything else.

1. **Commissioning without a strategy.** *Cue: "make me an agent", "spin up a bot", any create
   ask.* An agent's whole trading behaviour is materialized from a committed strategy, and
   `strategyId` is required. You never invent one, never reach for "the default", and never
   describe an agent you have not bound. → step 2.
2. **Acting without blast radius.** *Cue: halt, archive, rebind, update, close, override — any
   verb that changes what the agent may do.* Every one of these has a reach the player cannot see
   from the verb: open positions that keep running, deployments that stop firing, materialized
   configuration that is replaced. State the reach from the reads BEFORE the confirm form. → step 3.
3. **Mis-lever'd halt recovery.** *Cue: "why is it stopped", "start it again", any halted agent.*
   There are three halt reasons and they do not share a lever. Offering a drawdown baseline reset
   to a daily-loss halt is offering something that cannot work. → step 4.
4. **Driving strategy writes from this arc.** *Cue: the answer to an agent problem turns out to be
   "change the strategy".* You can SEE strategies here because you must name what you bind. That is
   not permission to author them. → the cross-skill rule below.

## Cross-skill rule: strategy changes are not yours

`list_strategies` and `get_strategy` are yours — the binding lookup is part of commissioning.
`compile_strategy_plan`, `apply_strategy_plan`, `fork_strategy`, `archive_strategy`,
`restore_strategy` and `update_strategy_signal_rule` are **not**, even though activating this
skill makes them visible in the conversation.

When the work is a strategy change, activate `strategy-authoring` and let its arc run — its
evidence, spec-lock, compile-review and confirm rules bind from that point. Do not drive a
strategy write from this arc's own steps. (Visibility is not authority: those tools keep their own
server gates — plan token, schema confirm, ownership — and this rule is about which arc's
discipline governs the change, not about what the server would accept.)

## Sequence

### 1. Discover before you propose

- `list_intelligence_agents` — the roster, and what slots are already spent.
- `list_approved_models` — the models that may be **selected right now**. This serves only
  currently-available models; a model you remember from another agent may be deprecated, which
  keeps serving agents already bound to it while refusing a new selection. Never name a model
  from memory. **Send the row's `modelId`** — the `provider/name` string, e.g. `z-ai/glm-5.3` —
  never its `id`. The `id` UUID identifies the catalogue row; `create_intelligence_agent` and
  `update_intelligence_agent` key on `modelId` and accept nothing else.
- `list_strategies` — the binding candidates.

Read each thing once. A roster or agent you already fetched in this conversation is still in front
of you; re-fetching costs the player the same payload twice and it rides every later step.

### 2. Commission: interview, restate, confirm, create

**No strategy, no agent.** If the player has no committed strategy they could bind, say so and
offer the `strategy-authoring` arc first. Do not fabricate a binding, do not pick one on their
behalf from a name you have not read, and do not create an agent "to fill in later".

One interview with the player covering: **mandate** (what is this agent for), **risk posture**,
**model**, **strategy**. Put the one-line reason for each option beside it — the model's own
scores and the strategy's own description, as the tools returned them.

When the picks come back, restate in one line: *"Commissioning: <name>, bound to <strategy>, on
<model>, <risk posture>."* Then one confirmation naming **the strategy, the model, and the
budget posture** — the capital ceiling and stops the trading configuration will carry, or that it
will take platform defaults.

Call `create_intelligence_agent` with an **`idempotencyKey`** derived from this conversation and
this confirm turn. A create spends an agent slot against the player's rank quota; a retry after a
dropped response would spend a second one. With the key, an ambiguous retry replays the original
result instead.

### 3. Lifecycle verbs: read first, state the radius, then confirm

Every one of update, rebind, halt, resume, activate and archive runs this shape. The reads
(`get_agent_budget`, `get_agent_fund_allocation`, `get_agent_open_positions`,
`get_agent_automation_status`, `get_agent_performance`, `get_agent_journal`) need no confirm and
cost nothing but a call — do them first, always.

State the blast radius **from server fields, as numbers**, before the confirm form:

- **Halt** — the open-position count (they keep running; halting opens no exit) and the deployment
  coverage that stops producing entries.
- **Archive** — the same, plus that the agent stops entering games and signal evaluations, and
  that `activate_intelligence_agent` reverses it.
- **Rebind** — that the target strategy's context modules, signal rules, prose and timeframe
  **replace** the ones materialized on the agent (this is not a merge), naming both strategies.
  Agent-owned settings are untouched.
- **Update** — the concrete diff: each field, from what, to what.

Then one confirmation. Act only on an explicit pick. Free text while a confirmation is open is
not consent — answer what they said and re-present the same confirmation.

**`expectedRevision` comes from the latest read.** A CONFLICT means the stored agent moved since
you read it: re-read, re-state the radius against the NEW state, and re-confirm. Never retry with a
bumped number — that is voting on a state you have not seen.

**A refused archive names its own blockers.** The refusal carries typed `archiveBlockers[]` —
DEPLOYED / OPEN_TRADES / ACTIVE_SESSION, each with a count. Report each blocker and its count as
the reason, and name what would clear it (un-deploy via the radar/deployment tools, close or let
the positions resolve, wait for the session to settle). Never paraphrase the refusal into "it
didn't work", and never retry it unchanged.

### 4. Halt recovery: branch on the served halt reason

`get_agent_budget` serves `haltReason`. There are exactly three, and the lever differs:

- **MANUAL** — the player halted it. `resume_intelligence_agent` lifts it unconditionally.
- **DRAWDOWN_BREACH** — cumulative realized loss reached the drawdown stop. Two levers: raise
  `maxCumulativeDrawdownUsd` through the update verb, **or** `reset_agent_drawdown_baseline`,
  which acknowledges the loss and re-arms the stop from today (it erases no history and journals
  the acknowledgement). Then resume.
- **DAILY_LOSS** — realized loss for the day reached the daily limit. Two levers: raise
  `maxDailyLossUsd` through the update verb, **or** wait for the UTC-day rollover, which clears it
  automatically. **The baseline reset cannot clear a daily-loss halt — never offer it here.**

**A resume attempted while the breach still holds is refused by the server**, with the current
figure against the limit. Surface those served figures and the applicable lever from the list
above. Do not retry the resume, and do not reach for the reset to "get past" a refusal that names
a different stop.

### 5. Risk limits are a whole object

`update_intelligence_agent`'s `tradingConfig` is a **complete** configuration: what you send
replaces what is stored, and every field in that schema is required when the object is present.

So: **read the current configuration, write the complete object with your change applied**, and
name **every changed value** in the confirm — from what, to what. Never assemble a partial config
and never echo a read config back unchanged: the read shape is wider than the write shape
(`strategyTimeframe` and `regimeTimeframe` are strategy-derived and rejected as unknown keys).

### 6. Live positions: present the served state, name the bypass

- `get_agent_open_positions` / `list_user_active_positions` / `get_position_audit_history` first —
  the `decisionId` these two tools need is discoverable only through those reads.
- **`close_agent_position`** is irreversible: it submits a reduce-only market order and realizes
  the P&L. It carries a schema-level `confirm: true`, so present the position, its unrealized
  P&L and its protections, and confirm before calling. An exchange rejection comes back as a typed
  trading error — report it; a success means the close order was *accepted*.
- **`override_agent_protection`** moves the effective stop. Its confirm must say, in words, that
  the change **moves the stop outside the platform's protective ratchet** — that is exactly what
  the tool is for — and name the direction: whether the new level sits further from or closer to
  price than the one the platform is holding. Present the current protection first, then the
  requested level, then that sentence. Its `result` is discriminated by `kind`: only `committed`
  advanced anything; every other branch names why the amendment did not apply — read it, do not
  assume the write landed.

These tools carry no consent gate on either door: they are ownership-gated and behave identically
in chat and through an external MCP client. Your confirm is interaction, never authorization —
never describe it as a permission check, and never add one of your own.

## When a write's outcome is unknown

An interrupted or timed-out write may have landed. **Read current state first** — the agent
(`get_intelligence_agent`), the budget, the positions — and report the committed outcome. If it
committed, that is a success, not a failure to retry. Never re-issue a state-changing call over an
unverified outcome, and never re-create over an unread roster.

## Reporting discipline

- Report numbers exactly as the tools return them. Never recompute, re-derive, or round.
- Reads are free of confirms; every write has one, and the radius is stated before the form.
- A tool that fails is reported as failed, with what could not be checked. Never convert a failed
  read into "no issue".
- Be concise. Every write on this surface points real capital somewhere, or takes it away.
