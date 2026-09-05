---
name: battlegrid-strategy-authoring
description: Build a trading strategy with the player from a plain-English idea — gather evidence, lock the spec with them, compile it against the platform grammar, show them exactly what will run, and apply it only once they confirm. Also forks, tunes, restores, archives and previews existing strategies. Activate whenever the player wants to create, change, copy, retire or inspect a strategy, or describes a trading idea they want built.
---

# Strategy Authoring

You are turning an idea into a strategy that will trade real money on the player's live agents.
The whole point of this flow is that **nothing exists until they have seen what will actually
run and said yes to it.**

## The three failures this flow exists to prevent

All three come from real authoring sessions, and all three were discovered only after the strategy
was already built. None of them is allowed to happen here.

1. **Built ≠ picked.** The player selected a "≥ +10%" trigger and a +5% trigger was implemented.
   Nobody noticed until the results looked wrong. You prevent this by showing the *compiled*
   rules next to their *locked* picks, before applying, and naming any contradiction yourself.
2. **Silent zero-trigger.** A strategy was built that could never fire, and produced nothing for
   days before anyone diagnosed it. You prevent this by reading the compile's own preview and the
   per-signal preview before applying, and flagging a plan that shows no passing conditions.

3. **Silent substitution.** A player asked for a strategy that triggers on the daily chart and
   executes on the 4-hour. The grammar carries no such semantics. Instead of saying so, the flow
   asked *what they meant by it* and offered four readings — one of which was the nearest
   expressible thing, presented as an equal alternative rather than as a substitute. They picked
   it, and got a confluence strategy labelled as the thing they asked for. **They had no way to
   learn otherwise.** You prevent this by testing expressibility BEFORE the spec lock, and by
   naming the gap in the question itself — see step 2.

A strategy that reaches apply without all three checks having been made and reported is a failure
of this skill, even if the player is happy with it.

## Sequence

### 1. Evidence first — never propose from the idea alone

Before you propose any shape, measure: `get_regime_snapshot` (and `get_regime_history` when the
idea depends on how we got here), then `get_coin_candles` and `get_coin_performance_history` for
the coins in scope.

If what you fetched contradicts the player's stated direction, do **not** proceed on their
premise and do **not** silently substitute your own. Put the evidence in front of them and ask
them to choose the direction again, with your recommendation stated in the question itself. They
may know something you cannot measure — the point is that they choose with the contradiction
visible.

**Read each thing once.** A strategy, agent or signal log you have already fetched in this
conversation is still in front of you — do not fetch it again unless something in this
conversation has changed it. A re-read returns the same bytes, and both copies then ride every
later step, so the player pays for the same payload twice and keeps paying for it. If you need a
detail you did not keep, scroll back rather than re-fetching.

### 2. Lock the spec before you build anything

**First, check the ask is expressible at all — and note that you cannot know until you have looked.**
Expressibility is a fact about the vocabulary, which step 3 discovers. So when the ask names
anything the grammar might not carry, **do step 3 before this one** and lock the spec against what
you found. The cues, none of them subtle:

- **two timeframes in one rule** — "trigger on the daily, execute on the 4-hour"
- **a relation between assets** — "when BTC leads and ETH lags"
- **an ordering between events** — "after X fires, then wait for Y"
- **anything phrased as a sequence, a delay, or a dependency**

Locking first and discovering second is how the third failure happens: the form goes out while the
gap is still invisible, so the ask arrives as a product question — *what did you mean?* — when the
honest answer was *the grammar cannot do that*. The arc reads 1 → 2 → 3 for an ordinary ask; for
one of these it reads 1 → 3 → 2.

If the gap is real, **the question text itself names it**, and the nearest expressible option is
labelled as the substitute it is — never as one reading among several. A player choosing between
four equal-looking options cannot tell that none of them is what they asked for.

One round of questions to the player, at most five, covering: **direction, trigger definition,
exit policy, universe, sizing.** Put the one-line reason for each option beside it so they are
choosing between real alternatives, not guessing.

When the picks come back, restate the locked spec in one line before any build call — literally
"Locked in. Building: …". That line is what the review is later checked against.

The answered form is the record of what they picked. Do not write a second copy of the spec
anywhere; if the two ever disagree, you have created the exact ambiguity this step removes.

### 3. Discover the grammar — never guess it

`list_strategy_categories` → `list_strategy_vocabulary` → `get_strategy_column_contract` and
`get_strategy_section_template` → `list_strategy_signals`, plus
`get_strategy_signal_definition` for each signal you intend to use.

Compose sections, columns, conditions and rules **only** from vocabulary returned in this
conversation. A field you remember from another strategy is not discovery.

**Read the answer, not just the call.** Each of these returns one field that decides a composition
question you would otherwise guess — and a refusal you would otherwise earn:

- **A CREATE omits `sectionKey`.** It is derived from the section itself, so the same submitted
  section at the same position yields the same key on every compile. Minting a `custom:<uuid>`
  yourself on a CREATE is refused with a hint telling you to omit `sectionKey` on CREATE; on an
  UPDATE, send back the key the compile returned. This is the one composition field whose right
  answer is "leave it out".
- **The `entry` axis is required on every CREATE**, all six keys, no defaults — `trigger`,
  `confirmTf`, `closes`, `bandAtrMultiple`, `levelOffsetAtrMultiple`, `validForBars`. It decides
  when an entry is taken; for the level triggers the level itself is derived from the trigger and
  the trade's direction, never named. The `strategy-examples` skill carries the vocabulary and the
  one-directional legality matrix; a CREATE without it is refused outright.
- `get_strategy_column_contract` → `outputs[].conditionOperators`. An empty array means that
  rendered header has no comparison semantics and cannot appear in a condition clause at all.
  Legality is per rendered header, not per column: a trajectory's slot header and its `_trend`
  header answer differently.
- `get_metric_construction_hints` → `rankOrderings`. Present only when rank is composable on that
  metric, already range-gated server-side — read the offered set rather than deriving one from
  the metric's native output.

For full-surface composition patterns — custom and benchmark sections, condition trees with
verdicts and enforcement gates, weight pyramids and gate math, trade-level and
position-management presets, worked desk-grade playbooks — activate `strategy-examples`. It
teaches what to compose; this skill stays the authority on the flow.

`derive_strategy_rule_view` belongs here, at composition time, and only here: it reports report
membership and registry-default allocations for a draft. It does **not** return a compiled plan's
values, so it can never stand in for the review in step 5.

`simulate_aggregate_score` does **not** belong here. It is a review tool (step 5) and running it
now answers a question about your draft, not about the plan the player will be asked to approve.

### 4. Compile, and iterate on the diagnostics

**An UPDATE carries only the axes that change.** The server preserves every axis you omit and
every signal you do not name, and it re-derives the complete post-state, the dense scorecard and
the diff itself. Restating the whole post-state is never required, changes nothing about the
result, and the player pays for every byte of it on this call and on every later step of the
conversation. Send the axes you are changing; send no other axis.

**Three fields are not axes, and every compile requires all three:** `intentSummary`,
`assumptions` and `coinSelection`. They describe *this call*, not the strategy, so "send no other
axis" never reaches them — omitting one is a typed error, not a saving.

`coinSelection` is the cohort the report preview renders over, so the player can read the plan
against live values. It is non-authoritative, never persisted, and **not recoverable from
`get_strategy`**: it is not strategy state, and no strategy has one. Do not go looking for it —
choose it. For a single-gate edit, a short explicit list of the tickers the change is about is
right; for a broad change, a `ranked` cohort is. Any reasonable cohort is correct, and searching
for "the strategy's" cohort is a search that cannot end.

`compile_strategy_plan` changes no strategy, agent or revision, and a failed compile has cost the
player nothing. It is not read-only, though: a successful compile parks the plan it approved in
server-side custody so its own apply can read it back. Compile once per reviewed payload — do not
retry a compile that succeeded, and never fire two in parallel for the same edit.

On a typed authoring error, the response names the offending path, the value it received and the
domain it allows. Fix the payload and recompile. On advisory `mismatches[]` or a `viability` that
is not viable, do the same.

**Stop after three consecutive autonomous recompiles.** A fourth means you are guessing — show
the player the diagnostics and ask. Never present a plan for confirmation while it still carries
diagnostics you have not explained to them.

### 5. Review — show the compiled truth, not your summary of it

Everything here comes from the compile response you just received. Render:

- **What will actually run.** `approvedPlan.postState.signalRules`, `approvedPlan.diff` and the
  review columns — the rules as the server will execute them — beside the picks they locked in
  step 2. **If any compiled rule or diff entry contradicts a locked pick, say so in words before
  you ask for anything.** Do not make them spot it.
- **Whether it can fire.** `reviewContext.reportPreview` is the server's own preview, rendered
  over this compiled draft against live market. Support it with `get_coin_signal_preview` on the
  locked universe's main coin(s).
- **A routing what-if**, optionally, via `simulate_aggregate_score` — **after the compile, never
  before it.** This is a calculator, not a verdict: it computes over whatever inputs you hand it,
  so a draft-fed simulation reports on something the player is not being asked to approve. Feed it
  the compiled values — the gate from `approvedPlan.postState.minAggregateScore`, the allocations
  from `approvedPlan.postState.signalRules`, the per-signal scores from the preview you just read
  — and show those inputs beside its output so a copy slip is visible on the card itself.

**Flag before confirming** if the preview shows no passing conditions, the coin preview shows
zero triggered signals, or the simulation reports `wouldRoute: false`. Any one of those means the
plan probably never fires — ask whether to revise rather than presenting it as healthy.

State the blast radius too: the bound-agent count and the open-position observation the compile
returned, as numbers, not buried in prose.

There is no backtest here and no expected-frequency figure. Do not imply one. What you have is a
point-in-time reading, and you say so.

### 6. Confirm, then apply

One confirmation carrying the plan's own `confirmationSummary`, offering Apply / Revise / Cancel.

On **Apply**, call `apply_strategy_plan` with two values and nothing else:

- the compile's `planToken`
- `confirm: true`

There is no `plan` member, and one is rejected as an unrecognized key. The server keeps the plan your
compile approved and reads it back, so **nothing is copied from the compile response** — the whole
class of mis-transcription is gone rather than guarded against.

`planToken` is opaque: forward it byte-for-byte exactly as received. Never retype, abbreviate or
reconstruct it. A mangled token addresses no approved plan and is refused with the real one intact.

On **Revise**, return to step 4. On **Cancel**, stop and let the token lapse.

If the player types free text while the confirm form is open, that is **not** consent and not a
cancellation. Answer what they said, then present the same plan's confirmation again, unchanged.
Prose never triggers an apply.

Do not pre-check expiry, digests, ownership, viability or quota before calling. The server is the
only authority on all of them; your job is to react to what it returns.

### 7. Lifecycle

`fork_strategy`, `update_strategy_signal_rule`, `restore_strategy`, `archive_strategy` and
`preview_strategy_report` are part of this flow.

Before any destructive one, state the blast radius from the server's own fields and confirm it
with the player:

- **Archiving** — how many agents are bound, and that their configuration stays byte-identical
  and open positions are unaffected.
- **Tuning a single rule** — how many agents are bound, and that the change reaches every one of
  them immediately.

**Your `ask_user` is the explanation, not the mechanism.** For single-rule tuning the server
independently requires `confirm:true` whenever the strategy has bound agents, so stating the radius
and calling anyway is refused, not committed. Send `confirm:true` only on a turn where the player
made an explicit confirming pick — never because you judged the edit safe. Free text typed while a
confirmation is open is not consent: answer it, then present the same confirmation again.

**Send only the fields you were asked to change.** `allocation`, `required` and `params` are each
optional and each preserves on omission. "Raise volume_surge to Critical" is
`{ signalId, allocation: 3 }` — nothing else. Do not read the current rule merely to restate a value
you are not changing, and never supply `required` unless the player asked about the Required flag.
Restating a remembered value is how a scoring signal silently becomes a mandatory trade gate.

**Report the change from the response.** The success payload carries `ruleChanges` with the server's
own `before` and `after` for the edited signal. State those. Never describe the prior value from
memory or from an earlier read — the response is the only record that cannot be stale.

## When apply is refused

Each of these is a specific typed code. Read it and take the cheapest correct step — never retry
the same call blindly.

- **`TOKEN_EXPIRED`** — a plan token lives five minutes and a human-paced review often outlives
  it. Recompile, present the review again, and **ask for confirmation again.** Never apply a
  recompiled plan on your own judgement that it matches the one they already approved; they
  approve the plan that will actually be applied.
- **`PLAN_APPROVAL_NOT_FOUND`** — no approved plan answers to this token. It was already applied, it
  lapsed, or it was never issued; these are deliberately one code, because the recovery is the same
  in each case. **Read the committed state first** with `get_strategy` — if the change is already
  there, the apply succeeded and this is a duplicate confirmation, so report success rather than
  rebuilding. Otherwise recompile, re-present, re-confirm.
- **A refusal that is not about the token at all** — quota, a name collision, a bound agent that
  moved, a shifted catalog. The approved plan **survives** these: clear the cause and confirm again
  with the same token while it still lives. Recompiling works too, but costs the player a second
  review they did not need.
- **A single-rule tuning refused for missing confirmation** — the strategy has bound agents and the
  server will not write without `confirm:true`. The refusal names the count. Present *that* count to
  the player and re-issue the identical call only after an explicit confirming pick. **Never add
  `confirm:true` and retry on your own judgement** — the refusal exists precisely because the
  decision is not yours, and a retry that supplies it unasked is the defect this rule was written
  for. Nothing was written, so there is no partial state to reconcile.
- **`TOKEN_BINDING_MISMATCH` while the token is still fresh** — there is nothing left to mis-copy,
  so this is real drift: a bound agent moved, the catalog changed, or the signing key rotated. Do
  not resubmit. Recompile, re-present, re-confirm.
- **An apply whose outcome you never saw** (interrupted or timed out) — read the committed state
  first with `get_strategy` or `list_strategies`. If it committed, report success. **Never
  re-apply and never recompile over an unverified outcome** — a blind retry duplicates the
  strategy or dies on the name check.
- **A run that ended on a budget guard mid-build** — when they nudge you, recompile and re-enter
  at the review. Never apply a plan compiled in a run that was cut short; treat it as stale.

## When the grammar cannot express the ask

The gate is step 2, and it is a step rather than advice for a reason: this rule lived here alone
once, as a section after the sequence, and a real arc walked 1 → 2 → 3 straight past it.

Say so, and name the exact capability that is missing — for example multi-timeframe trigger
semantics the discovered vocabulary does not carry. Then offer the nearest thing it *can* express,
**labelled as the substitute**, never as one option among equals.

Never approximate an inexpressible ask and present it as the thing they asked for. Three things
make that concrete, and all three have to hold:

- the gap is named in the **question you put to the player**, not only in prose around it
- the nearest expressible option says what it gives up
- nothing is compiled for the original ask, because there is nothing to compile

## Keep the strategy small enough to apply

Apply carries only a token, so a large authored surface no longer blocks it. The compiled plan is
still capped at 256,000 UTF-8 bytes, which compile enforces and reports; splitting a build into a
lean strategy plus follow-up edits is now a choice about reviewability, not a workaround for a limit
apply used to impose.

## Reporting discipline

- Report numbers exactly as the tools return them. Never recompute or re-derive.
- Compile changes no strategy, agent or revision — it does park the plan its own apply will read.
  Apply is the only write to the strategy itself. Say which one you are about to do.
- A tool that fails is reported as failed. Never fill a gap with a plausible value.
- Be concise. They are deciding whether to point real money at this.
