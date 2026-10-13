---
name: battlegrid-strategy-authoring
description: Build a trading strategy with the player from a plain-English idea — gather evidence, lock the spec with them, stage it into the strategy's draft against the platform grammar, show them exactly what will run, and commit it only once they confirm. Also forks, tunes, restores, archives and previews existing strategies. Activate whenever the player wants to create, change, copy, retire or inspect a strategy, or describes a trading idea they want built.
---

# Strategy Authoring

You are turning an idea into a strategy that will trade real money on the player's live agents.
The whole point of this flow is that **nothing is committed until they have seen what will actually
run and said yes to it.**

## The three failures this flow exists to prevent

All three come from real authoring sessions, and all three were discovered only after the strategy
was already built. None of them is allowed to happen here.

1. **Built ≠ picked.** The player selected a "≥ +10%" trigger and a +5% trigger was implemented.
   Nobody noticed until the results looked wrong. You prevent this by showing the *drafted* conditions,
   as the server's own draft read serves them, next to their *locked* picks, before committing, and
   naming any contradiction yourself.
2. **Silent zero-trigger.** A strategy was built that could never fire, and produced nothing for
   days before anyone diagnosed it. You prevent this by reading the draft's own report preview and
   its diagnostics before committing, and flagging a draft that shows no passing conditions or
   warns `NO_ENTRY_CONDITION`.

3. **Silent substitution.** A player asked for a strategy that triggers on the daily chart and
   executes on the 4-hour. The grammar carries no such semantics. Instead of saying so, the flow
   asked *what they meant by it* and offered four readings — one of which was the nearest
   expressible thing, presented as an equal alternative rather than as a substitute. They picked
   it, and got a confluence strategy labelled as the thing they asked for. **They had no way to
   learn otherwise.** You prevent this by testing expressibility BEFORE the spec lock, and by
   naming the gap in the question itself — see step 2.

A strategy that reaches a commit without all three checks having been made and reported is a
failure of this skill, even if the player is happy with it.

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

**Drafts are carved out of that rule.** A draft is the player's unsaved work, and another surface —
their builder, another device, an earlier stage of yours — can change it while you work. Read it
again whenever you are about to act on it.

**Start from what they are already part-way through.**

- Holding no strategy id? Call `list_strategy_drafts` first. If a draft comes back, say what it is,
  when it was last touched and which surface touched it, and offer to continue it — never start a
  second edit beside one the player has open. A draft whose strategy does not exist yet is a new
  strategy they began; continuing it means staging into its id.
- Holding an id? Call `get_strategy_draft` before you propose anything. A draft means the player is
  mid-edit, and the `draftVersion` it returns (0 when there is none) is what your first stage names.

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
`get_strategy_section_template`.

Compose sections, columns and conditions **only** from vocabulary returned in this conversation. A
field you remember from another strategy is not discovery.

**Conditions are the only deterministic entry gate.** A condition gates an entry when it is
`required` or carries a verdict (UP, DOWN or NEITHER); a building block — neither required nor a
verdict carrier — gates nothing, and an exit rule never counts. A strategy whose entry conditions
include no required and no verdict-carrying condition never routes a trade: every coin fails first
with `NO_ENTRY_CONDITION`, and its draft carries the warning of the same name. It stays a valid
strategy — Market Grid reads it as context — so a strategy the player means to trade needs at least
one. Before any condition is read, a coin must clear the ATR floor, `minAtrPct`, the
TRADE_LEVEL_POLICY dial beside the stop-loss band.

**Read the answer, not just the call.** Each of these returns one field that decides a composition
question you would otherwise guess — and a refusal you would otherwise earn:

- **A CREATE omits `sectionKey`.** It is derived from the section itself, so the same submitted
  section at the same position yields the same key on every validation — each stage's diagnostics
  and the commit alike. Minting a `custom:<uuid>` yourself on a CREATE is refused with a hint
  telling you to omit `sectionKey` on CREATE; on an UPDATE, send back the key the strategy's REPORT
  carries for each section you keep — from `get_strategy`, or from the draft's REPORT when it holds
  one — and omit it on a section you add. This is the one composition field whose right answer is
  "leave it out".
- **The `entry` axis is a union keyed by its trigger.** `ON_CANDLE_CLOSE` is sent alone —
  `{ "entry": { "trigger": "ON_CANDLE_CLOSE" } }` — and a `levelOffsetAtrMultiple` or
  `validForBars` beside it is refused as an unrecognized key. A level trigger (`STOP_THROUGH_LEVEL`,
  `ON_RETEST`) sends both of them, with no defaults. A CREATE that stages no entry takes the
  platform's seed entry, so the axis is not required on every CREATE — stage it whenever the locked
  spec names an entry. Every trigger is decided at the close of the strategy's OWN bar, so there is
  no confirm-timeframe key; for the level triggers the level itself is derived from the trigger and
  the trade's direction, never named. A multi-bar hold belongs to the clause or group that needs
  it — its own `hold: { atLeast, of }`, which the editor calls **Hold** (Once, In a row, Within, At
  least), counted in completed bars of the column's own timeframe — not to this axis. Every clause
  and group carries `hold`; `{ "atLeast": 1, "of": 1 }` is Once. The `strategy-examples` skill
  carries the vocabulary, the served hold domain (a crossover or an edge operator — `crossesAbove`,
  `crossesBelow`, `enters`, `exits` — is held "within" only; a Developing column cannot be held) and
  the per-column Confirmed / Developing read.
- **What a bar did is its own vocabulary.** A touch or a rejection of a level, a candle pattern, a
  gap and a run of bars are composed from the `strategy-examples` skill's **Bar geometry** section —
  `levelInteraction` over a level with its `buffer` knob, and the pattern, gap, run and price-source
  metrics. A level BREAK is a `distance` crossing over the same level, never a `levelInteraction`
  label.
- **Swing structure is its own section.** Swing highs and lows, the `HH`/`HL`/`LH`/`LL` label and the
  break-of-structure recipes are in the `strategy-examples` skill's **Swing structure** section.
- `get_strategy_column_contract` → `outputs[].conditionOperators`. An empty array means that
  rendered header has no comparison semantics and cannot appear in a condition clause at all.
  Legality is per rendered header, not per column: a trajectory's slot header and its `_trend`
  header answer differently.
- `get_strategy_column_contract` → `lookback`, `measurement` and `seriesHome`. `lookback.used` is
  the bars the column reads against `lookback.cap`, the column-lookback budget a save holds it to —
  a column past the cap is refused with `REPORT_COLUMN_LOOKBACK_EXCEEDED` by this tool exactly as by
  the save, so shrink its window or offset rather than staging it. `measurement` names how the
  transform (and a chained transform) reads its series: the read shape, the window's unit, the price
  basis and what an absent bar does. `seriesHome` says where the metric's series is kept — `candle`,
  `history`, or `null` when the metric has no series, which is why a series transform does not
  compose on it. Window and offset carry a declared `minimum` and a served `maximum` on each metric's
  transform entry — the largest value whose read size fits the lookback cap, or `null` when none
  does. Stage at most that maximum.
- `get_metric_construction_hints` → `rankOrderings`. Present only when rank is composable on that
  metric, already range-gated server-side — read the offered set rather than deriving one from
  the metric's native output.

For full-surface composition patterns — custom and benchmark sections, condition trees with
verdicts and `required` enforcement, the trade-level policy with its ATR floor, position-management
presets, worked desk-grade playbooks — activate `strategy-examples`. It teaches what to compose; this
skill stays the authority on the flow.

### 4. Stage, and iterate on the diagnostics

**Every change goes through the strategy's draft.** `stage_strategy_draft` takes, inside its
`request`, the `strategyId`, the `draftVersion` your last read returned (0 when there was none) and
the `axes` you propose. It writes those axes into the player's draft — attributed to you, landing in
their builder as unsaved changes — and commits nothing. Each stage returns the draft's new
`version`: that is the `draftVersion` your next stage names. Stage each change once, and never fire
two stages in parallel against one draft. Complete stage payloads showing the envelope are in
`references/strategy-stage-examples.md`.

**A new strategy is a create draft.** Omit `strategyId` and send `draftVersion: 0` on the first
stage; the response carries the id minted for it, which every later call names. A create needs
IDENTITY (`{ name, description, tagline }`) and TIMEFRAME_PROFILE (`{ timeframe }`). A create with
no REPORT starts from the platform's starting report (Price Action, RSI, MACD and Moving Averages),
and one with no ENTRY takes the seed entry. A create with no CONDITIONS declares no entry gate and
will not trade until one is staged.

**An UPDATE carries only the axes that change.** Axes you omit keep the values the draft has, and
an axis the draft does not hold is the committed strategy's. Each axis you send is written WHOLE —
a REPORT is the complete section list, CONDITIONS the complete set. Restating an axis
you are not changing is never required, changes nothing about the result, and the player pays for
every byte of it on this call and on every later step of the conversation. Send the axes you are
changing; send no other axis.

**A whole axis restates what it keeps.** "Raise the ATR floor to 0.8%" is one TRADE_LEVEL_POLICY
stage carrying all four of its dials — `minStopLossAtrMultiple`, `maxStopLossAtrMultiple`,
`minRiskRewardRatio` and `minAtrPct` — the three you are not changing exactly as they stand now:
read them from the draft's TRADE_LEVEL_POLICY when the draft holds it, otherwise from
`get_strategy`. The same holds for a condition: CONDITIONS carries every condition, each with its
`required` flag and verdict as they stand. Never set `required` or a verdict from memory, and never
change either unless the player asked: a wrong value there is how a building block silently becomes
a mandatory trade gate, or a gate silently disappears.

**Read the diagnostics every stage returns.** Past its checks of shape — an undeclared key, a
parameter beside `ON_CANDLE_CLOSE`, a coin that names nothing — a stage refuses nothing for being
incomplete or invalid, because the draft is the player's unsaved work. The stage's `diagnostics`
are where you learn what the commit would do:

- `errors` — the refusals the commit would raise, each with its `field` and `details` naming the
  `path`, the value it received and the `allowedDomain` it accepts. Fix the axis and stage again.
- `warnings` — observations that never refuse. `NO_ENTRY_CONDITION` means the strategy declares no
  required and no verdict-carrying entry condition, so it will never route a trade. Fix it, or carry
  it into the review as something to explain.

An empty `errors` is not a promise: the strategy quota, the name and capital feasibility are
decided only by the commit itself.

**Stop after three consecutive autonomous restages.** A fourth means you are guessing — show the
player the diagnostics and ask. Never present a draft for confirmation while it still carries
diagnostics you have not explained to them.

**When a stage is refused**, nothing was written:

- **`DRAFT_AXIS_CONTESTED`** names the axes the player's own hand changed after the version you
  named. Their edit is newer than your proposal: read the draft, tell them so, and propose again
  only when they ask. Never re-send the same values.
- **`DRAFT_VERSION_MOVED`** — the version you named is one the draft never reached: it was read from
  a draft since committed or discarded. Read it again and propose against what the player now has.

Never raise the number to get past either refusal.

### 5. Review — show the drafted truth, not your summary of it

Once the stage's diagnostics carry nothing you cannot explain, read the draft with
`get_strategy_draft`. Everything here comes from that read:

- **What will actually run.** Its `diff` — every drafted axis with its `live` and drafted value
  and the field-level `changes` between them, the drafted conditions among them — beside the
  picks they locked in step 2. **If any drafted row or diff entry contradicts a locked pick, say so
  in words before you ask for anything.** Do not make them spot it.
- **All of what the commit publishes.** The diff names every axis the draft holds, including
  unsaved work the player had in it before you staged. Read that list out in the confirmation as
  the commit's own: the player is approving all of it, not only what you proposed.
- **Whether it can fire.** `preview_strategy_report` with
  `source: { "kind": "DRAFT", strategyId, draftVersion }`, at the version the read returned,
  renders the draft against live market composed exactly as its commit would compose it. Its default
  `detail: "concise"` is exactly what the agent will read — the sections, each surface's conditions
  register with every coin's verdict, and the verdict tally; ask for `"detailed"` only when you need
  each coin's full evaluation or the addressable headers (`authoring`). A preview is bounded by a
  deadline and a result-character cap, both served by discovery as `previewExecutionLimits`
  (`deadlineMs`, `maxResultChars`); one over either is refused whole, never truncated, and the
  refusal carries `nextAct: narrow` — preview again asking for less, in the order the tool's
  description gives. The preview's `coinSelection` is its cohort, never strategy state: no strategy
  has one and `get_strategy` will not return one, so choose it — a short explicit list of the
  tickers the change is about for a single-condition edit, a `ranked` cohort for a broad one. Any
  reasonable cohort is correct.

**Flag before confirming** if the preview shows no passing conditions or the diagnostics warn
`NO_ENTRY_CONDITION`. Either one means the strategy probably never fires — ask whether to revise
rather than presenting it as healthy.

**State the impact as numbers, not buried in prose.** The read's `impact` carries:

- `operation` — CREATE, UPDATE or RESTORE. A RESTORE is a draft over an archived strategy: say
  that committing it also restores the strategy and moves its bound agents, by count, from
  ORPHANED to BOUND.
- `boundAgentCount`, `openPositionCount` and `timeframeChanged`. A committed change reaches every
  bound agent the moment it commits, while a position already open keeps the exit rules it opened
  under — say so.
- `admission` — for a create draft or an archived strategy, the quota and whether the name is
  free. It is advisory: the commit decides.
- `capital` — each bound agent the drafted stop band would leave unable to place an order, with its
  smallest order against the order floor. Name every one.

There is no backtest here and no expected-frequency figure. Do not imply one. What you have is a
point-in-time reading, and you say so.

### 6. Commit — only on the player's explicit pick

**In a conversation the Strategy Builder hosts**, each stage is already on the player's rail as
attributed unsaved changes, and their own Create, Save or Restore is one way to commit it. Report
that the change is staged and name the axes; offer to commit it yourself only through the same
confirmation as below.

One `ask_user` confirmation carrying the diff, the impact and the remaining warnings, offering
Commit / Revise / Cancel.

On **Commit**, call `commit_strategy_draft` with the `strategyId` and exactly two numbers from the
`get_strategy_draft` read the confirmation showed, and nothing else:

- `draftVersion` — that read's `draftVersion`
- `expectedRevision` — that read's `committedRevision`, which is `null` for a strategy not
  created yet

Never reconstruct either from prose or memory, and never take them from a stage response: the
player approved one read, and the commit names that read. It publishes exactly that draft over
exactly that revision, through the same committer the builder's Save runs.

On **Revise**, return to step 4. On **Cancel**, stop: the draft stays as staged and nothing is
committed.

If the player types free text while the confirm form is open, that is **not** consent and not a
cancellation. Answer what they said, then present the same read's confirmation again, unchanged.
Prose never triggers a commit. The same holds for an answer typed into the form's own
answer-in-your-own-words box: it is the player's words in an answer slot, not a confirming pick,
so treat it exactly as you would free text in the chat.

Do not pre-check ownership, validity, quota or the name before calling. The server is the only
authority on all of them; your job is to react to what it returns.

**Report the change from the read and the receipt.** The commit returns the committed `strategy`.
State each change as its live value in the read the player confirmed against its value in the
receipt's strategy. Never describe a value from memory or from any other read — those two are the
only records that cannot be stale.

**Offer to discard a draft only on the player's explicit word**, never on your own judgement that
it looks stale, and never batched into another act. `get_strategy_draft` is the read of what a
discard destroys: say what the draft holds, when it was last touched and which surface touched it,
ask, and only if they say so call `discard_strategy_draft` with the `strategyId` and the
`draftVersion` you read. There is no dry run and no confirmation parameter — the version is the
fence, and a draft written since your read is refused with `DRAFT_VERSION_MOVED` and nothing is
removed. The unsaved values are gone afterwards and there is no other copy.

### 7. Lifecycle

`fork_strategy`, `restore_strategy`, `archive_strategy`, `discard_strategy_draft` and
`preview_strategy_report` are part of this flow. Every change to a strategy's content — a single
tuned condition or dial included — is a staged draft committed with `commit_strategy_draft`; none of
the other verbs writes content.

- **Tuning a single condition or dial** is its axis staged whole (step 4), read, confirmed and
  committed. State how many agents are bound, and that the change reaches every one of them
  immediately.
- **Forking** — `fork_strategy` takes the `strategyId`, the exact `sourceRevision` to copy and an
  optional `name`, and returns a NEW create draft's `strategyId` and `draftVersion`. **No strategy
  exists yet.** Read the draft with `get_strategy_draft` — every authored axis equals the source
  revision's, and ORIGIN names the source — stage any change into it, review it as above, and on the
  player's word commit it with `expectedRevision: null`. Forking spends no strategy slot; the
  commit does, and a full quota or a name already in use is refused there.
- **Archiving** — `archive_strategy` with the `strategyId` and the `expectedRevision` you read.
  State how many agents are bound, that their configuration stays byte-identical, that open
  positions are unaffected and that the player's draft is kept, re-based onto the revision the
  archive produces.
- **Restoring** — find the archived strategy with `list_strategies` and `get_strategy` with
  `includeInactive: true`, which add the player's own strategies in any state; another player's
  PRIVATE strategy stays hidden either way. `restore_strategy` with the `strategyId` and
  `expectedRevision` brings back the unchanged content and keeps the player's draft, re-based onto
  the restored revision. To change the content as it comes back, stage the change into the
  strategy's draft and commit it — that commit restores it, and its read says `operation: RESTORE`.

**Your `ask_user` is the approval, and the server does not repeat it.** No strategy verb takes a
confirmation flag. So never call `commit_strategy_draft`, `archive_strategy`, `restore_strategy` or
`discard_strategy_draft` on a turn where the player has not made an explicit confirming pick —
never because you judged the change safe. Free text typed while a confirmation is open is not
consent: answer it, then present the same confirmation again. That covers words typed into the
form's own answer box as well as words sent in chat — a confirming pick is one of the options you
offered, and nothing else is.

## When the server refuses

Each refusal is a specific typed code, and a refusal of a draft's stage or commit names its next
act in `details.nextAct` — `get_draft` or `stage`; a moved or contested draft names `get_draft`
from any tool, and a refused preview names `narrow`. Read it and take the cheapest correct step —
never retry the same call blindly.

- **`DRAFT_VERSION_MOVED`** (`nextAct: get_draft`) — the draft changed after your read: the
  player's form saved an edit, another surface staged, or a human-paced review outlived it. Read
  it again, present the new diff and impact, and **ask for confirmation again.** Never commit a
  newer version on your own judgement that it matches the one they already approved; they approve
  the draft that will actually be committed.
- **`CONFLICT`** (`nextAct: get_draft`) — the strategy committed a newer revision after your read;
  the details carry `expectedRevision` and `actualRevision`. The same recovery: read, re-present,
  re-confirm.
- **A commit already in progress** (`nextAct: get_draft`) — a commit of this draft version is in
  flight or was interrupted. Read the draft: if its version moved, the commit landed, so read the
  strategy and report it; otherwise commit again once the refusal's wait has passed, or stage again.
- **A validation error** (`nextAct: stage`) — the error the diagnostics named, with its own
  `field` and `details`. Nothing was written. Return to step 4: fix the axis, stage, read, and
  confirm again.
- **A refusal with no `nextAct`** — the strategy quota (`FORBIDDEN`), a name already in use, or a
  `CONFLICT` whose `details.reason` is `RADAR_DEPLOYMENT_MOVED`. The draft is
  untouched. Clear the cause with the player — a rename is an IDENTITY stage, which makes a new
  version to read and confirm — then commit the draft they confirmed. A moved radar deployment is
  a race, not a decision: read and commit again.
- **A commit whose outcome you never saw** (interrupted or timed out) — send the same commit again
  first: the server replays the original receipt for the same draft version, so a commit that
  landed is reported once and never doubled. If that retry is refused as moved, verify the
  committed state with `get_strategy` or `list_strategies` and reconcile with the player before
  anything else. **Never stage or commit anything new over an unverified outcome.**
- **A run that ended on a budget guard mid-build** — when they nudge you, read the draft again
  with `get_strategy_draft` and re-enter at the review with the version and revision you just read.
  Never trust a draft version, diagnostics or a confirmation from a run that was cut short.
- **An unknown coin** — a `benchmarkTicker` in a staged REPORT, a `coinSelection` ticker or the
  `marketReadLensTicker` that names no catalogued coin is refused as a validation error naming that
  field (`Unknown coin symbol: '<input>'`), with nothing written. Symbols are case-insensitive and
  exchange symbols resolve (`btc`, `kPEPE`, `xyz:BRENTOIL` all reach their coin, and the draft
  stores the canonical ticker), so the refusal means the coin is not tracked: never retry with
  another casing — ask the player which coin they meant.

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
- nothing is staged for the original ask, because there is nothing to stage

## Keep each stage within the draft cap

The axes one stage carries are capped at 256,000 UTF-8 bytes — the same cap the builder's own
draft write enforces — and a stage past it is refused at the boundary naming the cap, with nothing
written. Splitting a build into a lean strategy plus follow-up edits is also a choice about
reviewability: each commit is one diff the player can read.

## Reporting discipline

- Report numbers exactly as the tools return them. Never recompute or re-derive.
- A stage changes the player's draft and nothing else — no strategy, agent or revision. A commit is
  the write that reaches the strategy and every agent bound to it. Say which one you are about to
  do.
- A tool that fails is reported as failed. Never fill a gap with a plausible value.
- Be concise. They are deciding whether to point real money at this.
