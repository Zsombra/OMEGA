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
   configuration that is replaced. State the reach from the reads BEFORE the confirm form. And a
   configuration change is staged into the agent's draft and committed only on the player's
   explicit pick. → steps 3 and 4.
3. **Mis-lever'd halt recovery.** *Cue: "why is it stopped", "start it again", any halted agent.*
   The halt reason says why the agent stopped, not what clears it. Offering an exit the server's
   resume verdict does not offer is offering something that cannot work. → step 5.
4. **Driving strategy writes from this arc.** *Cue: the answer to an agent problem turns out to be
   "change the strategy".* You can SEE strategies here because you must name what you bind. That is
   not permission to author them. → the cross-skill rule below.

## Cross-skill rule: strategy changes are not yours

`list_strategies` and `get_strategy` are yours — the binding lookup is part of commissioning, and
which strategy an agent is bound to is the agent's own STRATEGY_BINDING axis (step 4).
`stage_strategy_draft`, `commit_strategy_draft`, `discard_strategy_draft`, `fork_strategy`,
`archive_strategy` and `restore_strategy` are **not**, even though activating this skill makes them
visible in the conversation.

When the work is a strategy change, activate `strategy-authoring` and let its arc run — its
evidence, spec-lock, stage-review and confirm rules bind from that point. Do not drive a strategy
write from this arc's own steps. (Visibility is not authority: those tools keep their own server
fences — the draft version, the revision, ownership — and this rule is about which arc's discipline
governs the change, not about what the server would accept.)

## Sequence

### 1. Discover before you propose

- `list_intelligence_agents` — the roster, and what slots are already spent.
- `list_approved_models` — the models that may be **selected right now**. This serves only
  currently-available models; a model you remember from another agent may be deprecated, which
  keeps serving agents already bound to it while refusing a new selection. Never name a model
  from memory. **Send the row's `modelId`** — the `provider/name` string, e.g. `z-ai/glm-5.3` —
  never its `id`. The `id` UUID identifies the catalogue row; the draft's MODEL axis,
  `{ modelId }`, keys on `modelId` and accepts nothing else.
- `list_strategies` — the binding candidates.
- `list_agent_drafts` — what the player is already part-way through. **Mention an existing draft
  before starting new work** — "you have an unsaved <agent / new agent>, last touched from
  <surface> at <time>" — and offer to continue it rather than opening a second one beside it.

Read each thing once. A roster or agent you already fetched in this conversation is still in front
of you; re-fetching costs the player the same payload twice and it rides every later step.

### 2. Commission: interview, restate, draft, confirm, commit

**No strategy, no agent.** If the player has no committed strategy they could bind, say so and
offer the `strategy-authoring` arc first. Do not fabricate a binding, do not pick one on their
behalf from a name you have not read, and do not create an agent "to fill in later".

One interview with the player covering: **mandate** (what is this agent for), **risk posture**,
**model**, **strategy**. Put the one-line reason for each option beside it — the model's own
scores and the strategy's own description, as the tools returned them.

When the picks come back, restate in one line: *"Commissioning: <name>, bound to <strategy>, on
<model>, <risk posture>."*

**Build it in a create draft.** As the picks come back, stage them with `stage_agent_draft` —
omit `agentId` and send `draftVersion: 0` on the first call, then reuse the id it mints and the
`version` it returns — each axis WHOLE: IDENTITY `{ displayName }`, BEHAVIOR
`{ behavior: { risk, outlook, conviction } }`, MODEL `{ modelId }` and STRATEGY_BINDING
`{ strategyId }`, all four required to create, plus TRADING_CONFIG with every agent-owned field —
or no TRADING_CONFIG at all, to take the platform seed. The build then survives a refresh, lists in
the Agents Hub as *not yet created*, and opens on the create screen, where **the player's own
Create creates it**. Staging creates nothing and spends no slot.

**Then read it, confirm it, and commit it.** `get_agent_draft` serves the draft, its
`draftVersion`, a `committedRevision` of `null` and the diagnostics: a missing or invalid axis is
an error there, named, before anything is spent. Its impact is `operation: CREATE` with the
create's capital reading: the smallest order its configuration — drafted, or the platform seed —
places, against the order floor, and whether that is `feasible`. Then one confirmation naming **the
strategy, the model, and the budget posture** — the capital ceiling and stops the trading
configuration will carry, or that it will take the platform seed, with the smallest order against
the floor — and on the player's explicit pick call `commit_agent_draft` with the `agentId`, that
read's `draftVersion` and `expectedRevision: null`. A reading with `feasible: false` is a create the
commit will refuse: say so, and stage a larger ceiling or a looser configuration first. Where the player has the create screen open, their own Create is the
other way to commit it.

A create spends an agent slot against the player's rank quota, decided by the commit itself: a
full quota is refused there, with the draft unchanged. A retry of the same draft version after a
dropped response replays the original receipt, so an ambiguous retry never spends a second slot.

**When the mandate names the arena, read `get_account_state` in the same breath.** The arena needs
Agent Wagers: `mcpWagerEnabled: false` means every entry will be refused at the fee, so say the
arena needs it and offer the switch — **in a conversation a web Commander surface hosts, the switch
renders beneath the account card just shown, so offer it there**, and in every other host name the
Profile → Wallet tab path instead, because no control renders there. **Create the agent either
way**: the consent gates entering a game, never commissioning one. A `true` flag is consent alone
and not readiness — the pipeline's own refusal at the fee is the authority.

### 3. Stage, read, confirm, commit — every change goes through the draft

Before proposing any change to an existing agent, `get_agent_draft`. **A draft means the player is
mid-edit in their form**, and every change you make joins it. Then:

- **Stage** the change with `stage_agent_draft`, naming as `draftVersion` the `draftVersion` the
  read you proposed against returned (0 when it found no draft): it lands in their open form,
  labelled as yours. Each axis you send is written WHOLE — BEHAVIOR carries all three of risk,
  outlook and conviction, TRADING_CONFIG the complete configuration (step 6) — and the axes you
  omit keep their values.
- **Read the stage's diagnostics.** Its `errors` are the refusals the commit would raise, each
  naming its field: fix the axis and stage again before you ask for anything.
- A staging call refused **`DRAFT_AXIS_CONTESTED`** names an axis the player changed after the
  version you named: read again and propose against what they now have — never re-send the same
  values. One refused **`DRAFT_VERSION_MOVED`** names a version the draft never reached, or a draft
  that is gone: read again. Never raise the number to get past either refusal.
- **Commit** through step 4: read the draft with `get_agent_draft`, state the radius from its diff
  and impact, confirm, and on the player's explicit pick call `commit_agent_draft` with the
  `agentId` and exactly the `draftVersion` and, as `expectedRevision`, the `committedRevision` that
  read returned. The commit publishes every axis the draft holds — the player's own unsaved edits
  included — so the confirmation reads out the whole diff, not only your proposal. Where their form
  is open, their own Save is the other way to commit it.
- **Discard** only on the player's word. `get_agent_draft` is the read of what a discard destroys:
  tell them what the draft holds, when it was last written and from which surface, ask, and call
  `discard_agent_draft` with the `agentId` and the `draftVersion` you read. There is no dry run and
  no confirmation parameter: a draft written since your read is refused with `DRAFT_VERSION_MOVED`
  and nothing is removed — read again and show them.

**In a conversation the agent console hosts** — your context names the agent console and an agent
id — the player's form is open on that agent whether or not a draft exists yet. Stage every change
into that agent's draft, naming that id as `agentId`, create or edit alike: the create recipe's
omitted id does not apply there, because the screen already holds the id the agent will be created
at. Their own Create or Save commits it; commit it yourself only when they explicitly confirm
through `ask_user`. On an existing agent a strategy change is staged into the draft's
STRATEGY_BINDING like any other axis, and lands in their Strategy step as a proposed binding. An
axis their form rewrote after your proposal — typed over or undone — is their answer: propose it
again only on their word.

### 4. Lifecycle verbs: read first, state the radius, then confirm

Every one of a draft commit (an edit or a rebind), halt, resume, activate and archive runs this
shape. The reads (`get_agent_budget`, `get_agent_fund_allocation`, `get_agent_open_positions`,
`get_agent_automation_status`, `get_agent_performance`, `get_agent_journal`) need no confirm and
cost nothing but a call — do them first, always.

State the blast radius **from server fields, as numbers**, before the confirm form:

- **Halt** — the open-position count (they keep running; halting opens no exit) and the deployment
  coverage that stops producing entries.
- **Archive** — the same, plus that the agent stops entering games and signal evaluations, that
  `activate_intelligence_agent` reverses it, and that the player's draft of it is kept.
- **Rebind** — a strategy change is the draft's STRATEGY_BINDING axis: stage `{ strategyId }`, read
  `get_agent_draft`, and take both strategies from its `impact.rebind` — the strategy it replaces
  (`fromStrategyName`) and the one it binds (`toStrategyName`, at `toStrategyRevision`). Say that
  the target strategy's context modules, signal rules, prose and timeframe **replace** the ones
  materialized on the agent (this is not a merge), naming both strategies. Agent-owned settings are
  untouched. The commit checks the new strategy against the coins the radar acts on for this agent;
  a refusal names the coin and the condition — surface it, never retry it unchanged.
- **Any other draft commit** — the concrete diff from the read: each field, from what, to what. And
  the read's `impact`: the presets it is deployed to (`deployedPresetCount`), its open positions,
  the coins its radar is armed on (`radarArmedCoinCount`), and the capital reading — its smallest
  order (`smallestOrderUsd`) against the order floor (`orderFloorUsd`). `feasible: false` means the
  agent could not place an order at those limits; say so before the form.

Then one confirmation. Act only on an explicit pick — one of the options you offered. Free text
while a confirmation is open is not consent, whether it arrives in chat or in the form's own
answer-in-your-own-words box — answer what they said and re-present the same confirmation.

**The numbers a write names come from the latest read** — a commit's `draftVersion` and
`expectedRevision`, an archive's or activation's `expectedRevision`. A `CONFLICT` means the stored
agent moved since you read it, and a commit refused `DRAFT_VERSION_MOVED` means the draft did — the
player's form saved an edit, or another surface staged. Both carry `nextAct: get_draft`: re-read,
re-state the radius against the NEW state, and re-confirm. Never retry with a bumped number — that
is voting on a state you have not seen. A commit refused with `nextAct: stage` names the field the
diagnostics named: fix it in a stage, read, and confirm again.

**A refused archive names its own blockers.** The refusal carries typed `archiveBlockers[]` —
DEPLOYED / OPEN_TRADES / ACTIVE_SESSION, each with a count. Report each blocker and its count as
the reason, and name what would clear it (un-deploy via the radar/deployment tools, close or let
the positions resolve, wait for the session to settle). Never paraphrase the refusal into "it
didn't work", and never retry it unchanged.

### 5. Halt recovery: offer exactly the served verdict's exits

`get_agent_budget` serves `haltReason` — why the agent stopped — and `haltResumeEligibility`, the
server's resume verdict. **The verdict decides the recovery**; the reason only explains the stop.

- **`haltResumeEligibility` is null** — the agent is not halted. Every halt carries a verdict, one
  the player set by hand included, and is recovered through it.
- **`eligible: true`** — nothing is still breached, and a resume will succeed. Offer
  `resume_intelligence_agent`.
- **`eligible: false`** — `breachedStop` names the stop still breached, with `breachingFigureUsd`
  against `limitUsd`. Present that stop and exactly the exits the verdict marks open:
  - `canRaiseTriggeringStop` — raise that stop above the figure through the agent's draft (step 6:
    `maxCumulativeDrawdownUsd` for the drawdown stop, `maxDailyLossUsd` for the daily loss limit).
    The commit's receipt carries the new `haltResumeEligibility` when it moved a stop the resume
    reads;
  - `canResetBaseline` — `reset_agent_drawdown_baseline`, which acknowledges the loss and re-arms
    the drawdown stop from today (it erases no history and journals the acknowledgement);
  - a `breachedStop` of `DAILY_LOSS` also clears at the UTC-day rollover.

  Then resume. An exit the verdict does not mark open is never offered.

After any resume, read the response's `haltedAt`. The server re-checks every stop once the halt is
cleared, so a set `haltedAt` means the agent was halted again at once: a loss settled, or a stop was
lowered, while the resume ran. Read `get_agent_budget` again and present its `haltReason` and
verdict; never report that agent as trading.

**A resume attempted while a stop is still breached is refused by the server**, naming the same
stop, figure and exits. Surface them as served. Do not retry the resume; after a raise or a reset,
read the verdict again rather than assuming it cleared.

### 6. Risk limits are a whole object

The draft's TRADING_CONFIG axis is `{ tradingConfig }`, a **complete** configuration: what you
stage replaces the drafted one whole, and every agent-owned field is required in it.

So: **read the current configuration — the draft's TRADING_CONFIG when it holds one, otherwise the
agent's — and stage the complete object with your change applied**, then name **every changed
value** in the confirm, from what to what, as the draft read's diff serves it. Never assemble a
partial config and never echo a read config back unchanged: the agent's read shape is wider than
the axis (`strategyTimeframe` and `regimeTimeframe` are strategy-derived and refused as unknown
keys). The commit holds the configuration to the same risk rules the agent form's Save applies.

### 7. Live positions: present the served state, name the bypass

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

An interrupted or timed-out write may have landed.

**A draft commit recovers by being sent again.** `commit_agent_draft` replays the original receipt
for the same draft version, so a create that landed is reported once and spends one slot. If the
retry is refused as moved, read the agent — or the roster, for a create — and reconcile with the
player before anything else.

For every other write, **read current state first** — the agent (`get_intelligence_agent`), the
budget, the positions — and report the committed outcome. If it committed, that is a success, not a
failure to retry. Never re-issue a state-changing call over an unverified outcome, and never
re-create over an unread roster.

## Reporting discipline

- Report numbers exactly as the tools return them. Never recompute, re-derive, or round.
- Reads and stages are free of confirms — a stage changes only the draft. Every commit and every
  state verb has one, and the radius is stated before the form.
- A tool that fails is reported as failed, with what could not be checked. Never convert a failed
  read into "no issue".
- Be concise. Every write on this surface points real capital somewhere, or takes it away.
