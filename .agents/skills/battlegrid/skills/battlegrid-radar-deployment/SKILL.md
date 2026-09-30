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
   cause recurs, how far the score sits from firing, and what just happened — so paging the journal
   for it tallies an aggregate the server already computed and re-derives a proximity reading it
   already serves. The journal read is for ONE occurrence, or for more rows than the summary's ten.
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
  write).
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
2. `preview_radar_resolution` with `request: { kind: "DRAFT", draftVersion }` at the version staging
   returned. It composes the draft over the deployed policy **exactly as the commit will write it**.

To try a slot set without touching the draft, preview `{ kind: "SLOTS", slots }` — it certifies
nothing and cannot be committed.

**Arena** — the same shape, keyed on `presetId`:

1. `stage_deployment_policy_draft` with `draftVersion` = the `version` you read (0 when there was no
   draft) and only the axes you are changing, each WHOLE: `RULES` (the complete ordered rule list —
   first is highest priority; a rule's regime condition names a set), `DEFAULT_SLOT` (the catch-all, or null for none)
   and `REGIME_ANCHOR` (the anchor override, or null to inherit the arena's). Pausing is never staged.
2. `preview_deployment_resolution` with `request: { kind: "DRAFT", draftVersion }` at the version
   staging returned.

A draft that would hold no rule and no catch-all is a withdrawal, which a commit never does — that is
`delete_deployment_policy` (step 4).

Both previews run the **same resolver the live sweep runs**, so the preview is the real outcome, not
an estimate. Neither writes anything and neither costs the player an LLM call — so previewing
repeatedly while iterating is free and correct.

Render the preview as a card and read it out. For **Radar**: the coin's `section` and any typed idle
or blocked reason, then every row of `resolvesNow.onDuty` in the order served — each agent, the slot
and priority that put it on duty, its regime reading at its own `regimeTimeframe` with conviction, its
qualification verdict and its close clock — and, for a draft, `conditionReach`, which names each
on-duty agent's required conditions. For **Arena**: which agent goes on duty, which slot matched and at
what priority, the regime and conviction used, and the qualification verdict. **Render `section` as
the server sends it — never re-derive it, and never pick, rank or drop rows yourself.** A non-null
reason does not mean idle (`ON_DUTY_BUT_POSITION_BLOCKED` carries a reason and is not idle), so
deciding the headline yourself gets it wrong. `enabledAfterCommit` says whether the policy will play
once committed — a paused policy stays paused, and a first Arena deployment always plays.

**If anything changes after a preview, re-preview.** A preview never vouches for what it did not
resolve.

### 3. Confirm against the preview, then commit

One confirmation whose question **references what the preview showed** — the agents it put on duty and
the reason — and **names what the change does to the stored policy**, read from step 1:

- every rule or slot the change **removes** (by agent and priority), because `RULES` and `slots` are
  the whole set;
- a bar, window or regime that **changes** on a rule or slot that survives;
- whether it will play once committed, from `enabledAfterCommit` — a commit never changes a pause.

Then:

- **Radar** → `commit_radar_deployment_draft({ coinId, previewToken, confirm: true })`, with the
  `previewToken` the **live** DRAFT preview returned — no `simulatedRegime`, within five minutes. The
  draft ends when it commits.
- **Arena** → `commit_deployment_policy_draft({ presetId, previewToken, confirm: true })`, the same
  way: the live DRAFT preview's token, within five minutes. The draft ends when it commits.

**On a typed CONFLICT: re-read, re-preview, re-confirm.** In that order, and all three. The draft or
the policy changed under you, so the state your preview resolved and the radius you stated are both
stale. A certificate is bound to the draft version, the deployment and its content, so a retry
with the old one is refused again — only a fresh preview earns a new one.

### 4. Pause, resume, discard, delete

**Pause a coin's Radar** → `pause_radar_deployment({ coinId })`. No preview and no revision: stopping
never waits on a read. The player's draft is kept. **Resume** → preview the deployed policy with
`request: { kind: "COMMITTED" }`, tell the player which agents will go on duty again, and on their word
`resume_radar_deployment({ coinId, previewToken, confirm: true })` with the token that preview
returned.

**Pause an arena** → `pause_deployment_policy({ presetId })`, and **resume** it the Radar way: preview
`{ kind: "COMMITTED" }`, then `resume_deployment_policy({ presetId, previewToken, confirm: true })` on
the player's word. Both touch only the pause, never the rules or the player's draft.

**Entries already made stand.** A pause or a delete of an arena returns `openEntries` — the sessions
the player's agent already entered that have not locked, each with its lock time and entry fee. They
play out unless the player cancels them. Name each one, ask whether to cancel it, and call
`cancel_market_grid_submission({ sessionId, confirm: true })` only for the entries they pick — the
same cancellation and refund as their own Cancel button. Say nothing is cancelled when they decline.

**Discard a draft** only on the player's word. Call `discard_radar_deployment_draft` or
`discard_deployment_policy_draft` with
`confirm: false` first: the answer names what the draft holds, its version, and when and from where
it was last written. Tell the player, ask, and call with `confirm: true` and `expectedVersion` set to
**the version you were shown**. If the draft moved since, nothing is removed and the answer names what
it now holds — show them again.

**Deletes** — `delete_radar_deployment` / `delete_deployment_policy` remove the **entire** policy —
every slot and condition — and revoke the standing authority. Un-deploying **also ends the player's
draft** of the coin or the arena. There is no preview here, and correctly so: there is no resolution
to preview once the policy is gone. The evidence is **the deployment's own read**, which supplies the
`expectedRevision` the delete carries — and for Arena the `expectedPolicyId` beside it.

State what stops, from that read: which agents were on duty (every row of `resolvesNow.onDuty`) or
eligible, what the policy was firing on, and that the slots are not recoverable. Both tools carry a schema-level `confirm: true`.

**If the player wants to stop trading without losing the slots, that is not a delete** — it is
`pause_radar_deployment` for Radar and `pause_deployment_policy` for Arena. Offer that
whenever the ask sounds like "pause", "stop for now", or "take it off duty for a while".

### 5. "Why isn't it firing?" — state, then pattern, then rows

Three reads, cheapest first. Stop as soon as the player's question is answered.

1. **`get_radar_deployment` → `resolvesNow`** for what is true **right now**: the coin's section and
   reason, and one `onDuty` row per agent — its blocked reason and since when, its qualification
   block, its cooldown, whether its edge is spent, its last fire and its close clock. A row whose last
   close reads `CLAIMED` qualified but lost the coin's one fire that pass to a higher-priority agent;
   its edge is preserved and it fires at a later close only if it still qualifies there. Most "is it
   working?" questions end here.
2. **`get_radar_activity_summary`** for everything else about "why is it quiet", in ONE call. It
   carries three parts and they answer three different questions, each on its own scope:
   - `groups` — which cause recurs and how often, over the window the response names. Quote the
     counts with that window; never sum them across calls.
   - `curveDigest` — how FAR the score sits from firing, over the FIRST on-duty agent's ring (the
     lowest-numbered slot on duty now, named in `curveAgentName`). This is what
     separates "lower the minimum two points and it fires" from "this strategy does not fit this
     coin": `bestUnqualifiedScorePercent` against `latestThresholdPercent`. Its `ringStartAt` /
     `ringEndAt` describe the ring, NOT the cause window above.
   - `recentEvents` — the last ten key events, lean. Deliberately NOT bounded by the cause window, so
     a pair quiet for longer returns no groups beside populated older rows. That is correct, not a
     contradiction; each row carries its own `occurredAt`.

   The groups and rows span every on-duty agent — each row names its own — while the digest describes
   the first one. For about one sweep after the on-duty set changes the digest can name the new first
   agent while the rows still show the old one — the two halves are read from different stores. Say
   "duty just changed" rather than reporting a contradiction. Joins and departures are journaled as
   `ON_DUTY_JOINED` / `ON_DUTY_LEFT`, one row per agent, and a lost coin as
   `EDGE_PRESERVED_COIN_CLAIMED`.
3. **`get_radar_activity`** only for what step 2 cannot do: more rows than its ten, a FIRES-only
   view, paging back through history, or ONE occurrence's full margins. Rows are lean by default —
   pass `detail: 'FULL'` for the margin surface, and `includeCurve: true` only if something will
   actually plot the points.

**Neither of the first two substitutes for the other, and the reason is structural.** The journal is
a TRANSITION log, not a state log: a gate that has blocked continuously without crossing again
inside the window produces no group in the rollup at all. It shows up in `resolvesNow` and nowhere
else. So an empty or quiet rollup NEVER means "nothing is blocking it" — check step 1 before saying
anything of the sort.

Two negatives, both checkable:

- **Never page journal rows in order to count causes yourself.** The counts are served. Re-deriving
  them spends the player's op budget on work the server already did and floods the transcript.
- **Never sum counts across pages, and never report a windowed count as a lifetime one.** The
  rollup's counts span every matching row inside `windowStartAt`–`windowEndAt` — quote them with
  that window ("41 times in the last 7 days"), never as a total.

## Preview-before-commit: enforced for both

A deployment arms only with a certificate. `commit_radar_deployment_draft` and
`commit_deployment_policy_draft` take the certificate a live preview of that draft returned, and
`resume_radar_deployment` and `resume_deployment_policy` one from a live preview of the deployed
policy. Each is bound to your credential, the player, the coin or arena, the subject previewed, the
deployment and its revision, the draft version and the content the preview resolved, and expires after
five minutes. A simulated preview returns none. So a commit of anything the player was not shown is
refused by the server — but the player's confirmation is still yours to ask for, against the preview.

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
