# Assistant Phase — the Four Decisions, Answered

Recorded 2026-08-28, immediately after the finalize-execution-surface plan completed
(first generated strategy applied and archived, suite at 828). The user asked for the
phase-gap assessment, then answered each decision interactively, one at a time, from
explicitly presented options. These four answers scope the NEXT phase — the
strategy-creation assistant — and the measurement work that must precede it.

## Decision 1 — the assistant's contract

**ANSWERED 2026-08-28 — "Builder, advisor-ready."** The assistant promises only
"built correctly, everything explained": valid strategies the platform accepts, every
setting stated, every unknown declared. It does NOT claim any strategy will perform —
no outcome data exists, and nobody can honestly make that claim today. But every
strategy it creates is recorded (id, thesis, full config, date) so that IF the user
ever lets one trade, performance can be attached and the assistant can grow into an
advisor without rework. The trap this avoids: sounding like promise #2 while only
able to keep promise #1.

## Decision 2 — quota lifecycle

**ANSWERED 2026-08-28 — "Create, verify, auto-archive."** The account holds 25
strategies; 24 slots are occupied by pre-existing strategies, most bound to live
agents. Every assistant creation follows the pattern proven by the first apply:
create into the free slot, verify by read-back, archive immediately. The slot is
always returned; archived strategies stay restorable. The existing 24 are NOT
touched — archiving strategies bound to live agents would be an operational change
and was deliberately not chosen.

## Decision 3 — target surface

**ANSWERED 2026-08-28 — "Full menu."** All 13 platform timeframes and all coin
universe modes (explicit lists AND ranked categories) must be supported on day one.
This is the longest-runway option and it front-loads a measurement campaign, because
the repo's rule is measure-before-support:

- defaults + server-derived cadence/regimeTimeframe at every unmeasured anchor
  (~11 compiles: everything except the measured 1h and 4h);
- the BG-14 universe-size boundary — the largest coinSelection that compiles under
  the 256,000-byte preview cap (a few binary-search compiles) — without this, ranked
  universes cannot be created at all;
- the remaining bounds edges while we are at it: R:R lower edge, minAtrPct
  catalog-vs-schema (the upper R:R edge is already proven enforced).

All of this is compile-only (no writes, no capital), but every compile stays
user-budgeted per the standing rules.

## Decision 4 — binding and deployment boundary

**ANSWERED 2026-08-28 — "Prepare, never execute."** The assistant's flow ends with a
verified strategy PLUS a precise, reviewable checklist of the exact binding /
deployment steps, which the user executes personally in the app. The assistant never
calls bind/deploy tools. This is a UX decision layered ON TOP of the standing safety
rule (never bind, never deploy without per-instance authorization) — the standing
rule is not weakened by it and survives regardless.

## What now stands between here and the assistant phase

1. **The measurement campaign** Decision 3 requires (anchors sweep + BG-14 cap
   boundary + bounds edges) — one plan, compile-only.
2. **UPDATE for generated plans.** `wire()` emits CREATE only; a conversational
   builder ("make the stop tighter") is an UPDATE at `expectedRevision`. The UPDATE
   emitter is unbuilt and no generated UPDATE has ever been applied.
3. **The assistant itself** — the intent → Thesis authoring layer, scoped by these
   four answers: builder contract, auto-archive lifecycle, full measured menu,
   prepare-don't-execute at the capital gate. This gets its own brainstorm → spec →
   plan cycle.

Standing constraints that survive into every one of these: never bind, never deploy
(user-gated per instance, always); record live responses verbatim before
interpreting; planTokens never committed (length+sha256 only); unmeasured means
declared-unknown, never guessed.
