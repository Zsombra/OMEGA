---
name: battlegrid-radar-deployment
description: Deploy the player's agents to standing duty — per-coin Radar policies that fire real trades on confirmed regime flips, and per-preset Arena deployment policies that enter sessions automatically. Reads what is deployed now, previews what a draft would actually resolve to, writes it only after the player has seen that preview, and un-deploys with the blast radius stated. Activate whenever the player wants an agent put on duty, wants to change or pause a deployment, asks what would fire right now or why nothing is firing, or wants to stop a coin or a preset being traded automatically.
---

# Radar & Deployment

You are handing an agent **standing authority**. A Radar policy fires real trades on confirmed
regime flips with no further human action; a deployment policy enters real sessions the same way.
Nobody is watching when it happens — which is why the player has to see what a policy resolves to
*before* it exists, not after.

Radar (per coin) and Arena deployment (per preset) are **separate bounded contexts**. They share
no slot shape, no condition union and no resolution type. Never carry a fact from one to the other,
and never describe them as one thing with two modes.

## The five failures this flow exists to prevent

1. **A write with no fresh preview.** *Cue: any `upsert_radar_deployment` or
   `upsert_deployment_policy`.* The preview is the only place the player sees which agent actually
   goes on duty and why. → steps 2–3.
2. **A blind CAS retry.** *Cue: a CONFLICT on a write.* The revision moved because the stored
   policy changed. Bumping the number and retrying overwrites an edit you never read. → step 3.
3. **Previewing one thing and writing another.** *Cue: the player adjusts a slot, a bar, a window,
   a regime, or the enabled flag after you previewed.* A preview vouches only for the parameters it
   was given. → step 2.
4. **A replacement that silently drops slots.** *Cue: any upsert on a coin or preset that already
   has a policy.* `slots` is the COMPLETE set and replaces what is stored — a slot you did not
   resend is deleted. → step 3.
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
- `get_deployment_policy` / `list_deployment_policies` for Arena.

The read is what supplies `expectedRevision` for the write. **`null` only for a first deploy** —
a coin or preset with no policy at all. Anything else carries the revision you just read.

`get_regime_snapshot` / `get_regime_history` when the policy turns on regime conditions.

If the question is *why did my radar agent not fire*, do not start from the journal — **go to step
5**, which reads state first and pattern second.

### 2. Preview the exact parameters under discussion

- **Radar** → `preview_radar_resolution` with the draft slots.
- **Arena** → `preview_deployment_resolution` with the draft slots.

Both run the **same resolver the live sweep runs**, so the preview is the real outcome, not an
estimate. Neither writes anything, neither needs a revision, and neither costs the player an LLM
call — so previewing repeatedly while iterating is free and correct.

Render the preview as a card and read it out: which agent goes on duty, which slot matched and at
what priority, the regime and conviction used, the qualification verdict, and any typed idle or
blocked reason. **Render `section` as the server sends it — never re-derive it.** A non-null reason
does not mean idle (`ON_DUTY_BUT_POSITION_BLOCKED` carries a reason and is not idle), so deciding
the headline yourself gets it wrong.

**If any parameter changes after a preview, re-preview.** A preview never vouches for parameters
it did not see. That includes a changed conviction bar, an added or removed slot, an edited time
window or regime set, and flipping `enabled`.

### 3. Confirm against the preview, then write

One confirmation whose question **references what the preview showed** — the agent it put on duty and
the reason — and **names what the replacement changes about the stored policy**, read from step 1:

- every slot the replacement **removes** (by agent and priority), because `slots` is the whole set;
- a bar, window or regime that **changes** on a slot that survives;
- `enabled` going false (**paused, slots kept — nothing fires**) or true (**resumed — it can fire
  again from the next confirmed flip**).

Then `upsert_radar_deployment` / `upsert_deployment_policy` with the revision from step 1.

**On a typed CONFLICT: re-read, re-preview, re-confirm.** In that order, and all three. The policy
changed under you, so the state your preview resolved and the radius you stated are both stale.
Never retry with a bumped revision.

### 4. Deletes: read, state what stops, confirm

`delete_radar_deployment` / `delete_deployment_policy` remove the **entire** policy — every slot and
condition — and revoke the standing authority. There is no preview here, and correctly so: there is
no resolution to preview once the policy is gone. The evidence is **the deployment's own read**.

State what stops, from that read: which agents were on duty or eligible, what the policy was
firing on, and that the slots are not recoverable. Both tools carry a schema-level `confirm: true`.

**If the player wants to stop trading without losing the slots, that is not a delete** — it is an
upsert with `enabled: false`. Offer that whenever the ask sounds like "pause", "stop for now", or
"take it off duty for a while".

### 5. "Why isn't it firing?" — state, then pattern, then rows

Three reads, cheapest first. Stop as soon as the player's question is answered.

1. **`preview_radar_resolution` → `resolvesNow`** for what is true **right now**: the section, the
   blocked reason and since when, the qualification block, the cooldown, the last fire, and which
   agent is on duty. Most "is it working?" questions end here.
2. **`get_radar_activity_summary`** for everything else about "why is it quiet", in ONE call. It
   carries three parts and they answer three different questions, each on its own scope:
   - `groups` — which cause recurs and how often, over the window the response names. Quote the
     counts with that window; never sum them across calls.
   - `curveDigest` — how FAR the score sits from firing, over the on-duty agent's ring. This is what
     separates "lower the minimum two points and it fires" from "this strategy does not fit this
     coin": `bestUnqualifiedScorePercent` against `latestThresholdPercent`. Its `ringStartAt` /
     `ringEndAt` describe the ring, NOT the cause window above.
   - `recentEvents` — the last ten key events, lean. Deliberately NOT bounded by the cause window, so
     a pair quiet for longer returns no groups beside populated older rows. That is correct, not a
     contradiction; each row carries its own `occurredAt`.

   For about one sweep after an agent rotation the digest can name the incoming agent while the rows
   still show the outgoing one — the two halves are read from different stores. Say "just rotated"
   rather than reporting a contradiction.
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

## Preview-before-commit is a rule of this flow, and only that

There is no server-side preview receipt: the upsert takes no token proving a preview happened, and
the CAS revision is the only cross-call state. So the sequence above is what holds the invariant —
not a mechanism that could refuse you. Treat it as binding anyway. A write that reaches the player's
confirm with no preview in the conversation is a failure of this skill even if the server accepts it.

## When a write's outcome is unknown

An interrupted or timed-out upsert or delete may have landed. **Read the deployment first**
(`get_radar_deployment` / `get_deployment_policy`) and report what is actually stored. A committed
change is a success to report, not a call to repeat. Never blind-retry a write whose outcome you
did not see.

## `test_generate_deployment_grid`

This one runs a **billed LLM generation** against the player's intelligence credits and writes
thought and activity records. It is a composition aid for tuning a draft deployment — say that it
is billed **before** invoking it, and only invoke it when the player is actually iterating on slots
and wants to see what the resolved agent would produce. It is never a diagnostic read.

## Reporting discipline

- Report the preview's fields exactly as served — the section, the reason, the verdicts. Never
  recompute or soften them.
- Radar facts and Arena facts stay separate. Never present one policy's resolution as the other's.
- A tool that fails is reported as failed, naming what could not be checked.
- Be concise. Everything written here trades without asking again.
