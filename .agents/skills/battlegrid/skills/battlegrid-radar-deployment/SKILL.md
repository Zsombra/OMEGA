---
name: battlegrid-radar-deployment
description: Deploy the player's agents to standing duty — per-coin Radar policies that put every matching rule's agent on duty and fire real trades at confirmed closes, and per-preset Arena deployment policies that enter sessions automatically. Reads what is deployed now, stages a change into the player's draft, previews what it would actually resolve to, commits it only after the player has seen that preview, and un-deploys with the blast radius stated. Activate whenever the player wants an agent put on duty, wants to change or pause a deployment, asks what would fire right now or why nothing is firing, or wants to stop a coin or a preset being traded automatically.
---

# Radar & Deployment

You are handing agents **standing authority**. A Radar policy puts EVERY rule whose conditions match
on duty at once — each rule's regime read at its own agent's regime timeframe — and fires real trades
at their confirmed closes with no further human action, at most one per coin per pass, offered in rule
priority; a deployment policy enters real sessions the same way.
Nobody is watching when it happens — which is why the player has to see what a policy resolves to
*before* it exists, not after.

Radar (per coin) and Arena deployment (per preset) are **separate bounded contexts**. They share
no slot shape, no condition union and no resolution type. Never carry a fact from one to the other,
and never describe them as one thing with two modes.

**Deployments are the autonomous trading switches.** An agent has no trading mode of its own: it
trades a coin on its own only where a Radar policy puts it on duty, and a proposal the player
approves needs no deployment. An Arena deployment enters an agent into a preset's sessions and grants
**no** trade permission — to have an agent trade a coin on its own, deploy it on Radar.

## The five failures this flow exists to prevent

1. **A write with no fresh preview.** *Cue: any `commit_radar_deployment_draft`,
   `resume_radar_deployment`, `commit_deployment_policy_draft` or `resume_deployment_policy`.* The preview is the only place the
   player sees which agents actually go on duty and why. → steps 2–3.
2. **A blind retry.** *Cue: a CONFLICT on a write.* Something moved under you — the stored policy,
   or the player's draft. Retrying overwrites an edit you never read. → step 3.
3. **Previewing one thing and writing another.** *Cue: the player adjusts a slot, a bar, a window
   or a regime after you previewed.* A preview vouches only for what it resolved. → step 2.
4. **A replacement that silently drops rules.** *Cue: a `RULES` axis staged over a deployed coin or
   a deployed arena.* `RULES` is the COMPLETE ordered rule list on both: a rule you did not resend is
   deleted. → step 3.
5. **Answering "why isn't it firing?" by paging the journal.** *Cue: any question about why a
   deployed agent has been quiet — "is it working?", "it hasn't traded all day", "what's blocking
   it?".* `get_radar_activity_summary` now answers the whole question in one small call — which
   cause recurs, how often the pair qualified, and what just happened — so paging the journal for it
   tallies an aggregate the server already computed and re-derives a reading it already serves. The journal read is for ONE occurrence, or for more rows than the summary's ten.
   → step 5.

## Sequence

### 1. Resolve the target, then read current state

**Radar is keyed on `coinId` — a text `coins.id`, not a ticker and not a UUID.** Resolve it
through `get_coin_metadata`. Never derive a `coinId` from the player's ticker text, however
obvious it looks: the identifier the tools take is the coin table's own, and a guessed one either
misses or hits the wrong coin.

Arena deployment is keyed on `presetId` (a UUID) — from `list_game_presets`.

Then read what exists:

- `get_radar_deployment` (one coin) or `list_radar_deployments` (the fleet, plus the platform
  `radarPaused` kill-switch — if that is set, say so up front: nothing will fire whatever you
  write). A `SCANNING` card whose reason is `ENTRIES_PAUSED` is the platform's **entry pause**: new
  entries are paused platform-wide while market data is missing across many coins. Say that up front
  too — the radar takes no new entry on any coin until it lifts, which it does by itself once the
  data is back, and nothing the player changes on a deployment clears it.
- **For Radar, also read the player's draft of the coin** with `get_radar_deployment_draft` — or
  `list_radar_deployment_drafts` when no coin is named yet. The player may be part-way through a
  change in their radar builder. **If a draft exists, say so** — what it holds, and when and from
  where it was last written — and propose against it rather than starting over beside it.
- `get_deployment_policy` / `list_deployment_policies` for Arena, and **the player's draft of the
  arena** with `get_deployment_policy_draft` — or `list_deployment_policy_drafts` when no arena is
  named yet, which also lists arenas the player started but never deployed. Mention an existing draft
  the same way: what it holds, and when and from where it was last written.

`get_regime_snapshot` / `get_regime_history` when the policy turns on regime conditions.

If the question is *why did my radar agent not fire*, do not start from the journal — **go to step
5**, which reads state first and pattern second.

**In a conversation the radar builder hosts** — your context names the radar builder and a coin id —
the player's builder is open on that coin whether or not a draft exists yet. Stage every change into
that coin's draft, naming that `coinId`; it lands in their builder as a proposal. Their own Save
commits it; commit it yourself only when they explicitly confirm through `ask_user`, after the
preview this flow requires. The builder's state — its rules, the default agent, who is on duty now —
arrives as the turn's attached scope. An axis their form rewrote after your proposal is their answer:
propose it again only on their word.

**In a conversation the Arena deploy editor hosts** — your context names the Arena deploy editor and a
preset id — the same, for that arena's deployment draft, naming that `presetId`. Its scope carries the
rules, the default agent and what the next session resolves to, marked `simulated` while the player
is test-routing a regime. Never carry a fact from a radar conversation into it, or the reverse.

### 2. Stage the change, then preview exactly what would be written

**Radar** — the change goes into the player's draft of the coin, never straight to the policy:

1. `stage_radar_deployment_draft` with `draftVersion` = the `version` you read (0 when there was
   no draft) and only the axes you are changing, each WHOLE: `RULES` (the complete ordered rule list
   — first is highest priority; every rule that matches is on duty, so priority decides only which
   agent is offered the coin's one fire on a pass) and `DEFAULT_SLOT` (the catch-all, on duty only
   when no rule is, or null for none). A Radar policy has **no timeframe**: each rule's regime
   condition is read at its agent's own regime timeframe, which every slot reports as
   `agentRegimeTimeframe`. Staging writes nothing live and shows the change in the player's builder as
   a proposal. A refusal naming axes means the player changed them after your read: read again and
   propose against what they now have.
2. `get_radar_deployment_draft` — the draft as it now stands: its `draftVersion`, the
   `committedRevision` it would be published over (null for a coin with no policy yet), the diff
   against the deployed policy, the `diagnostics` a commit would refuse, and the `impact` — who goes
   on duty, whether it trades once committed, and for a first deployment the coin cap
   (`admission.coinCapReached` true means the commit will be refused until a coin is un-deployed).
   Do not confirm a draft whose diagnostics carry an error: stage a fix.
3. `preview_radar_resolution` with `request: { kind: "DRAFT", draftVersion }` at the version that read
   returned. It composes the draft over the deployed policy **exactly as the commit will write it**,
   and refuses a draft no longer at that version with `DRAFT_VERSION_MOVED`.

To try a slot set without touching the draft, preview `{ kind: "SLOTS", slots }` — it resolves
explicit slots and nothing can commit it.

**Shaping a Radar rule.** A rule carries one or two conditions — never none. Pick the construction
from what the player asked for:

| The player wants the agent on duty… | Construction |
|---|---|
| whenever no rule matches | `DEFAULT_SLOT` — on duty only while no rule matches, so on a coin with no rules it is on duty at every instant |
| only in named regimes | a rule with a regime condition |
| only in named hours and days | a rule with an hours condition |
| in named regimes during named hours | a rule with one hours condition and one regime condition |

When the ask maps to no single row, or a refusal rules out the construction the player asked for,
ask the player which construction they mean, naming the rows that fit — never stage one they did not
choose. Complete stage payloads for every row are in `references/radar-stage-examples.md`.

**Arena** — the same shape, keyed on `presetId`:

1. `stage_deployment_policy_draft` with `draftVersion` = the `version` you read (0 when there was no
   draft) and only the axes you are changing, each WHOLE: `RULES` (the complete ordered rule list —
   first is highest priority; a rule's regime condition names a set), `DEFAULT_SLOT` (the catch-all, or null for none)
   and `REGIME_ANCHOR` (the anchor override, or null to inherit the arena's). Pausing is never staged.
2. `get_deployment_policy_draft` — its `draftVersion`, `committedRevision`, diff, `diagnostics` and
   `impact` (the next session's resolution and whether it will play), exactly as for Radar.
3. `preview_deployment_resolution` with `request: { kind: "DRAFT", draftVersion }` at the version
   that read returned.

A draft that would hold no rule and no catch-all is a withdrawal, which a commit never does — that is
`delete_deployment_policy` (step 4).

**Shaping an Arena rule.** A rule needs at least one condition by the time it is committed — a draft
may hold a rule with none while the player is still choosing, and the draft read's diagnostics flag
it. Pick the construction from what the player asked for:

| The player wants the agent to play… | Construction |
|---|---|
| whenever no rule matches | `DEFAULT_SLOT` — plays only when no rule wins the session |
| only in named regimes | a rule with a regime condition |
| only at named session starts, or one scheduled occurrence | a rule with one session condition — a start or an occurrence |
| in named regimes at those sessions | a rule with a regime condition and one session condition |

When the ask maps to no single row, or a refusal rules out the construction the player asked for,
ask the player which construction they mean, naming the rows that fit — never stage one they did not
choose. Complete stage payloads for every row are in `references/arena-stage-examples.md`.

Both previews run the **same resolver the live sweep runs**, so the preview is the real outcome, not
an estimate. Neither writes anything and neither costs the player an LLM call — so previewing
repeatedly while iterating is free and correct.

Render the preview as a card and read it out. For **Radar**: the coin's `section` and any typed idle
or blocked reason, then every row of `resolvesNow.onDuty` in the order served — each agent, the slot
and priority that put it on duty, its regime reading at its own `regimeTimeframe` with conviction, its
qualification verdict and its close clock — and `readings`, one entry per on-duty agent in the same
order: what that agent reads on the coin right now (below). For **Arena**: which agent goes on duty,
which slot matched and at what priority, the regime and conviction used, and the qualification
verdict, under the resolution's `status` as served — RESOLVED (an agent plays the next session),
IDLE (the rules ran and none matched), WARMING, NO_SESSION or PAUSED. **Render `section` as the server sends it — never re-derive it, and never pick, rank or drop
rows yourself.** A non-null reason does not mean idle (`ON_DUTY_BUT_POSITION_BLOCKED` carries a reason
and is not idle), so deciding the headline yourself gets it wrong. `enabledAfterCommit` says whether
the policy will play once committed — a paused policy stays paused, and a first Arena deployment
always plays. A Radar preview simulates a running platform, so it never reports the kill switch or an
entry pause: those come from step 1's read.

**If anything changes after a preview, re-preview.** A preview never vouches for what it did not
resolve.

**A Radar preview refuses an agent the scan cannot read on the coin.** Every slot agent, on duty now
or not, must have every condition the radar acts on — its required conditions, the ones carrying a
verdict, its exit rules, and every condition they reference — readable by the radar scan on this
coin. When one is not, the preview itself is refused, and the draft read reports the same refusal in
its diagnostics: `CONDITION_UNREADABLE_BY_RADAR_SCAN`, whose `details.context.reachReason` says why
(`INSTRUMENT` — the market-data profile of the coin, or of a benchmark section's own instrument, carries
no such data, or the market-data service publishes no profile for it at all: the refusal names the kind
of data the profile lacks, or says there is none; `AGENT_TIMEFRAME` — the agent has no such rung;
`FEED` — the radar scan never reads that data for this agent), or
`CONDITION_OPERAND_UNSERVED_IN_LANE` for a session-field scalar. Read the player the refusal as served:
it names the agent, the condition, the column and the fixes — stop the radar acting on the condition,
make it read a column the radar scan has on that coin, or take the agent off the coin. A commit
re-checks the same rule, so a strategy edit landing after the preview can still refuse it.

**`readings` is each on-duty agent's requirements, read now.** A `READ` entry carries the agent's
`reading` — the same one `get_agent_coin_qualification` returns with `reading: true`, through the same
resolver:

- `reading.live` is the reading its qualification verdict was built from: the gates with their margins
  (`qualification`); every entry-lane condition — required, direction-setting, and the ones they
  reference — with its outcome and its clause values against their thresholds
  (`conditions.entries[]`); and the data it lacked
  (`missingData`). An `UNEVALUATED` entry is a condition this tick could not read, with its
  `reachReason`. A pair the scan can never read was refused above, so every such cause is one the next
  sweep can change — report it as the current reading, never as a reason the deployment will not
  work. `anchorBarStatus` says which bar the conditions read (`live` while it is still forming), and
  `scoredBarStart` names the bar the gates were read on. **A live reading decides
  nothing**: the radar decides at the close, on the closed bar, so say what it reads right now, never
  that it will fire.
- `reading.lastClose` is the one decision the agent's on-duty row names as its last close: `RECORDED`
  with that bar's close-decision record — the reading it was decided on, or why it was missed —
  `PENDING` while that record is still being written, or `NONE` when the pair remembers no decision.
  For the decisions before it, call `get_radar_close_decisions` (step 5). Name a close by the served
  `barCloseAt` — on a record's `bar`, on a `PENDING` close and on the on-duty row's
  `closeDecision.last` — and a `DEFERRED` row's bar being decided by `closeDecision.decidingBarStart`;
  never add a timeframe to `barStart`.
- `reading.sinceClose` is how the live reading moved since the deciding reading, computed by the
  server: the ATR reading's move (`UP`, `DOWN`, `UNCHANGED`), whether the required conditions, the
  trade levels, the condition verdict and the first failing gate changed, and each live condition
  against the deciding entry for its key (`ABSENT`, `NOT_READ`, `UNCHANGED`, `CHANGED`). It is `null` unless `lastClose` is `RECORDED`
  on a reading. Quote it; never compare the two readings yourself.

An `UNSCORABLE` entry is an on-duty agent the preview could not read on the coin, with
`coinDataStopped` when the coin's data explains why; it never fails the preview. `readings` is null
under a simulated regime: duty is simulated there, and every reading would judge the real one.

There is no `conditionReach` list and no `blocksScanGate` flag (contract 74.0.0). A condition's reach
reason is its `UNEVALUATED` entry's `reachReason` in
`readings[].reading.live.reading.conditions.entries[]`, and whether the conditions hold the coin is the
reading's own conditions gate, `qualification.gates.requiredConditions` — never a verdict of your own.

### 3. Confirm against the preview, then commit

One confirmation whose question **references what the preview showed** — the agents it put on duty and
the reason — and **names what the change does to the stored policy**, read from step 1:

- every rule or slot the change **removes** (by agent and priority), because `RULES` and `slots` are
  the whole set;
- a bar, window or regime that **changes** on a rule or slot that survives;
- whether it will play once committed, from `enabledAfterCommit` — a commit never changes a pause.

Then:

- **Radar** → `commit_radar_deployment_draft({ request: { coinId, draftVersion, expectedRevision } })`,
  naming exactly the `draftVersion` and `committedRevision` your draft read returned — the version
  your preview resolved. Ask with `ask_user` first and commit only after an explicit confirming pick.
  The axes it published leave the draft.
- **Arena** → `commit_deployment_policy_draft({ request: { presetId, draftVersion, expectedRevision } })`,
  the same way.

**On `DRAFT_VERSION_MOVED` or a CONFLICT: re-read, re-preview, re-confirm.** In that order, and all
three. The draft or the deployment changed under you, so the state your preview resolved and the
radius you stated are both stale. A retry with a bumped number commits something the player was not
shown — the server refuses a version or revision you did not read, and the confirmation is yours to
ask for again.

### 4. Pause, resume, discard, delete

**Pause a coin's Radar** → `pause_radar_deployment({ coinId })`. No preview and no revision: stopping
never waits on a read. The player's draft keeps its content and is re-based onto the paused revision.
**Resume** → preview the deployed policy with `request: { kind: "COMMITTED" }`, tell the player which
agents will go on duty again, and on their word
`resume_radar_deployment({ coinId, expectedPolicyId, expectedRevision })` naming the `policyId` and
`revision` that preview returned — so it re-arms the policy the player was shown, or nothing.

**Pause an arena** → `pause_deployment_policy({ presetId })`, and **resume** it the Radar way: preview
`{ kind: "COMMITTED" }`, then `resume_deployment_policy({ presetId, expectedPolicyId, expectedRevision })`
with the pair it returned, on the player's word. Both touch only the pause, never the rules; the
player's draft keeps its content.

**Entries already made stand.** A pause or a delete of an arena returns `openEntries` — the sessions
the player's agent already entered that have not locked, each with its lock time and entry fee. They
play out unless the player cancels them. Name each one, ask whether to cancel it, and call
`cancel_market_grid_submission({ sessionId, confirm: true })` only for the entries they pick — the
same cancellation and refund as their own Cancel button. Say nothing is cancelled when they decline.

**Discard a draft** only on the player's word. Read it first and tell the player what it holds and
when and from where it was last written; then
`discard_radar_deployment_draft({ request: { coinId, draftVersion } })` or
`discard_deployment_policy_draft({ request: { presetId, draftVersion } })` at **the version you read**.
If the draft moved since, it is refused with `DRAFT_VERSION_MOVED` and nothing is removed — read it
again and show them.

**Deletes** — `delete_radar_deployment` / `delete_deployment_policy` remove the **entire** policy —
every slot and condition — and revoke the standing authority. Un-deploying **also ends the player's
draft** of the coin or the arena. There is no preview here, and correctly so: there is no resolution
to preview once the policy is gone. The evidence is **the deployment's own read**, which supplies the
`expectedPolicyId` and `expectedRevision` both deletes carry — a policy removed and redeployed since
your read is refused rather than removed.

State what stops, from that read: which agents were on duty (every row of `resolvesNow.onDuty`) or
eligible, what the policy was firing on, and that the slots are not recoverable — and delete only after
an explicit confirming pick.

**If the player wants to stop trading without losing the slots, that is not a delete** — it is
`pause_radar_deployment` for Radar and `pause_deployment_policy` for Arena. Offer that
whenever the ask sounds like "pause", "stop for now", or "take it off duty for a while".

### 5. "Why isn't it firing?" — state, then pattern, then the bar, then rows

Four reads, cheapest first. Stop as soon as the player's question is answered.

1. **`get_radar_deployment` → `resolvesNow`** for what is true **right now**: the coin's section and
   reason, and one `onDuty` row per agent — its blocked reason and since when, its qualification
   block, its cooldown, whether its edge is spent, its last fire and its close clock. A row whose last
   close reads `CLAIMED` qualified but lost the coin's one fire that pass to a higher-priority agent;
   its edge is preserved and it fires at a later close only if it still qualifies there. A `SCANNING`
   coin whose reason is `ENTRIES_PAUSED` is under the entry pause (step 1): its agents still decide and
   record every close, and a close that qualifies is held — its fire refused, its edge preserved,
   journaled and recorded as `EDGE_PRESERVED_ENTRIES_PAUSED` with `scanBlockReason` `ENTRIES_PAUSED` —
   so it fires at a later close only if that close qualifies on its own data after the pause lifts. A
   lower-priority agent behind that fire reads `CLAIMED` on the same bar: the coin's one fire went to
   the agent the pause refused, not to a trade. That is the whole answer while the pause lasts; never
   send the player to change an agent or a policy for it. Most "is it working?" questions end here.
   When the question is what ONE on-duty agent of a scanning coin needs to fire — which condition
   reads false, how far the ATR reading sits from its floor — drill into its row
   with `get_agent_coin_qualification({ agentId, coinTickers: [<the coin's ticker>], reading: true })`
   and read the verdict's `reading` as step 2 of the deploy flow describes it: `live` is what the
   agent reads now, and `lastClose` is the decision its row names as its last close, with the reading
   that bar was decided on.
2. **`get_radar_activity_summary`** for everything else about "why is it quiet", in ONE call. It
   carries three parts and they answer three different questions, each on its own scope:
   - `groups` — which cause recurs and how often, over the window the response names. Quote the
     counts with that window; never sum them across calls.
   - `curveDigest` — how often the pair qualified, over the FIRST on-duty agent's ring (the
     lowest-numbered slot on duty now, named in `curveAgentName`): `qualifiedCount` of
     `sampleCount`, and the latest ATR% with how many samples read one. A pair that qualified on no
     sample is one whose strategy does not fit this coin as it trades now; the `groups` above name the
     gate that blocked it. Its `ringStartAt` / `ringEndAt` describe the ring, NOT the cause window
     above.
   - `recentEvents` — the last ten key events, lean. Deliberately NOT bounded by the cause window, so
     a pair quiet for longer returns no groups beside populated older rows. That is correct, not a
     contradiction; each row carries its own `occurredAt`.

   The groups and rows span every on-duty agent — each row names its own — while the digest describes
   the first one. For about one sweep after the on-duty set changes the digest can name the new first
   agent while the rows still show the old one — the two halves are read from different stores. Say
   "duty just changed" rather than reporting a contradiction. Joins and departures are journaled as
   `ON_DUTY_JOINED` / `ON_DUTY_LEFT`, one row per agent, and a lost coin as
   `EDGE_PRESERVED_COIN_CLAIMED`.
3. **`get_radar_close_decisions`** when the question is about ONE close — "why didn't the 14:00 bar
   fire?", "why did it fire there?", "what did it see at that close?". Every bar the close step
   decided has one record, whether a policy's agent or a manual request's watch decided it: its
   `outcome` (`FIRED`, `NOT_QUALIFIED`, `CLAIMED` or `MISSED`), the fire's `fireDisposition` as
   arbitration settled it, and the `evidence` the bar was decided on — the closed-bar reading's gates
   with their margins, every condition's outcome with its clause evidence, each condition the scan
   could not evaluate with its reach reason, and `missingData` — or, for a
   `MISSED` bar, the close step's own answer: the bar never settled, an input was not on its due bar,
   or the window passed. An `outcome` of `FIRED` says the bar qualified and its agent was offered the
   coin's fire; `fireDisposition` says what the fire came to — `FIRED` when a decision was enqueued,
   `EDGE_PRESERVED_ENTRIES_PAUSED` beside `scanBlockReason` `ENTRIES_PAUSED` when the entry pause
   refused it and nothing was traded. It is the only history of not-qualifying closes: the journal
   writes no row for one, and `resolvesNow` keeps only each agent's last decision — the one
   `reading.lastClose` (step 1) carries; this read holds every decision before it. Narrow with
   `agentId`; page back by passing the oldest returned `bar.barStart` as `before`. A bar still
   waiting inside its window has no record yet (`resolvesNow` shows its `closeDecision.state` as
   `DEFERRED`), and records are kept 90 days.
4. **`get_radar_activity`** only for what steps 2 and 3 cannot do: more rows than its ten, a
   FIRES-only view, paging back through history, or ONE occurrence's full margins. Rows are lean by
   default — pass `detail: 'FULL'` for the margin surface, and `includeCurve: true` only if something
   will actually plot the points.

**Neither of the first two substitutes for the other, and the reason is structural.** The journal is
a TRANSITION log, not a state log: a gate that has blocked continuously without crossing again
inside the window produces no group in the rollup at all. It shows up in `resolvesNow` and nowhere
else. So an empty or quiet rollup NEVER means "nothing is blocking it" — check step 1 before saying
anything of the sort.

Three negatives, all checkable:

- **Never page journal rows in order to count causes yourself.** The counts are served. Re-deriving
  them spends the player's op budget on work the server already did and floods the transcript.
- **Never sum counts across pages, and never report a windowed count as a lifetime one.** The
  rollup's counts span every matching row inside `windowStartAt`–`windowEndAt` — quote them with
  that window ("41 times in the last 7 days"), never as a total.
- **Never explain one close from the live verdict or the journal.** A not-qualifying close writes no
  journal row, and the live reading is not the reading the close was decided on — at the same moment
  the two can sit on opposite sides of a gate. Read the bar's record — `reading.lastClose` for the
  last decision a row names, `get_radar_close_decisions` for any other — and quote it as stored;
  never recompute it.

## Preview-before-commit: your discipline, fenced by the server

The preview card and the confirming pick are yours to show and ask for, every time. What the server
enforces is the fence under them: a commit names the draft version and committed revision its read
returned, and a resume or a delete names the deployment and revision it read. A draft that moved after
your preview is refused with `DRAFT_VERSION_MOVED`; a deployment whose revision moved, or that was
withdrawn and redeployed, is refused as a CONFLICT. So a commit never publishes a draft version your
preview did not resolve — provided you previewed the version you commit.

## When a write's outcome is unknown

An interrupted or timed-out commit, pause, resume, delete or cancel may have landed. **Read the
deployment first** (`get_radar_deployment` / `get_deployment_policy`) and report what is actually
stored. A committed change is a success to report, not a call to repeat. Never blind-retry a write
whose outcome you did not see.

## `test_generate_deployment_grid`

This one runs a **billed LLM generation** against the player's intelligence credits and writes
thought and activity records. It is a composition aid for tuning an Arena deployment — say that it
is billed **before** invoking it, and only invoke it when the player is actually iterating on slots
and wants to see what the resolved agent would produce. It is never a diagnostic read.

## Reporting discipline

- Report the preview's fields exactly as served — the section, the reason, the verdicts. Never
  recompute or soften them.
- Radar facts and Arena facts stay separate. Never present one policy's resolution as the other's.
- A tool that fails is reported as failed, naming what could not be checked.
- Be concise. Everything written here trades without asking again.
