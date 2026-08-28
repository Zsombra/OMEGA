# Generated UPDATE — Design

Approved 2026-08-29, brainstormed interactively; the three shaping decisions are the
user's, quoted where they chose from explicit options. This is roadmap step 2 of the
assistant phase (`2026-08-28-assistant-phase-decisions.md`): omega can only CREATE,
and a conversational builder needs revision.

## What this builds

`StrategyPlan.wire_update(strategy_id, expected_revision)` — the exact `wire()` body
with `operation: "UPDATE"` plus `strategyId` and `expectedRevision` — and ONE proven
live revision loop on the strategy omega itself created.

## The three decisions (user's choices)

1. **Update model: "Full body from Thesis."** The Thesis stays the single source of
   truth: apply the change to the Thesis, regenerate the complete body, send it all;
   the server computes the diff. No delta emitter (explicitly rejected as YAGNI plus
   an unmeasured omitted-means-keep dependency); no dual path.
2. **Live proof: "Full loop on 6a8bca67."** `restore_strategy` the archived Trend
   Continuation (revision 2, never bound) → ONE gated UPDATE apply → read back →
   `archive_strategy` again. Compile-only proof rejected (leaves the loop unproven);
   fresh-CREATE-then-UPDATE rejected (two applies, proves nothing more).
3. **Proof change: "Execution override: R:R 2.0."** `Thesis.execution =
   {"minRiskRewardRatio": 2.0}` — legal on every measured bound, and it gives
   Decision 1(a)'s override path (built 2026-08-28, never exercised on a real write)
   its end-to-end proof: default 1.5 → persisted 2.0.

## The emitter

- `wire_update` reuses `wire()` verbatim and patches exactly three things: the
  operation, `strategyId`, `expectedRevision`. The UPDATE schema arm accepts every
  CREATE field plus those two (re-verified live 2026-08-28; re-verify at execution).
- The proof Thesis: trend-continuation preset, `coin_selection` explicit BTC/ETH/SOL
  (matching the body that created `6a8bca67` — the persisted strategy carries no
  coinSelection, the field only scopes the compile's review), `execution` as above.
  Name stays "Trend Continuation" — same strategy, no collision question.
- Validation: `expected_revision >= 1`; the id is the server's to refuse.

## The measurement inside the proof

The compile that mints the apply token IS the probe. Its `diff` / blast-radius
answers what is UNMEASURED about the UPDATE arm for generated bodies:

- Does re-sending an identical report (sections without `sectionKey`s — CREATE
  refuses client keys; whether UPDATE does is itself part of the measurement) re-mint
  the keys, and if so are the conditions' resolved references re-resolved
  consistently or broken?
- What axes does the diff report for a body identical except one execution field?
  Expected: the execution axis; everything else stable or consistently re-resolved.

**Pre-committed branches:** apply ONLY if the compile is viable AND the scripted diff
inspection matches the expectation above. Anything alarming — report re-mint with
broken condition references, unexpected axes, non-viable — is recorded verbatim, the
token is left to expire, and execution STOPS for the user. A refusal is a finding.

## The live loop (execution order)

1. `restore_strategy` 6a8bca67 (direct lifecycle tool; reversible).
2. `get_strategy` — capture the full pre-state verbatim and the current revision
   (restore may advance it; use what the read-back says, never an assumed number).
3. One compile of `wire_update(...)` at that revision → scripted diff inspection.
4. ONE `apply_strategy_plan` `{confirm, planToken}` within the token window.
5. Read back: revision advanced by the apply, `minRiskRewardRatio == 2.0`, every
   other content field byte-equal to the pre-state (timestamps/revision excepted),
   conditions referencing sections that exist.
6. `archive_strategy` — quota returns to 24/25, strategy restorable as before.

Budgets for the kickoff to authorize: **compiles ≤2** (1 + contingency for a
material, fixable refusal), **exactly 1 apply** (per-instance sentence naming the
generated Trend Continuation UPDATE), **1 restore, 1 archive**. Never bind, never
deploy — standing.

## Records, tests, docs

- `data/audit/first_generated_update_2026-XX-XX.json`: pre-state, compile (token
  redacted to length+sha256), diff verdicts, apply impact, read-back, archive —
  verbatim before interpretation.
- `tests/test_first_update.py`: pins the record and the wire_update shape
  (body == wire() plus exactly the three patched fields; UPDATE-required keys
  present).
- Doc 16: short section "A generated strategy can be revised". Doc 08: a
  "revisable" guarantee line. Spec `2026-08-28-assistant-phase-decisions.md`:
  step 2 marked EXECUTED. Memory updated.

## Deliberately absent

- A wrong-`expectedRevision` probe — conflict behavior is documented platform
  business, not the builder's happy path.
- The delta emitter and any omitted-means-keep measurement (decision 1).
- Anything touching agents, radar, or arena deployments — permanently user-gated.
