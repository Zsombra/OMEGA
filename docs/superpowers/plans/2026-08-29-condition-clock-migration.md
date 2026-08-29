# 2026-08-29 · Condition-clock migration plan

**Goal:** bring omega up to the platform surface that shipped on 2026-08-29 (the
condition-clock feature and its neighbors), then compile the Deep-Tail Fade CREATE
viable. Written mid-drift: the developer said multiple updates were going out, so
**Step 0 re-verifies everything before any code is written**. Execute in a fresh
session; nothing below is done until its box is checked.

## What is known (measured this session — re-verify at Step 0)

- The connector's **runtime input validator** requires, on every compile request:
  `sections[].notes` (string), `conditions[].clock` (`'LIVE' | 'CLOSE'`),
  `conditions[].closes` (number). The **published schema declares none of them**
  (read fresh 2026-08-29, this session, before the first call).
- **Compiler rule** `CONDITION_CLOCK_OPERAND_ILLEGAL`: *a CLOSE-clocked condition
  may only read headers resolved from the coin's own candle series, at offset 0.*
  Ambient headers (`reference-pairs.*`, `session-field.*`, `market-breadth.*`)
  must sit in LIVE conditions, referenced from LIVE conditions.
- **Migration defaults** (read-only `get_strategy` on `6a8bca67`): every existing
  condition got `clock: "LIVE", closes: 1`; sections got `notes: null`; a new
  **`entry` axis** appeared (`{trigger: "AT_SIGNAL", confirmTf, closes,
  bandAtrMultiple}`) that the compile schema does not expose. No revision bump —
  storage migration vs read-time defaulting indistinguishable.
- Open questions: `closes` semantics (>1 unmeasured); whether `notes: null`
  passes input validation (absent ≠ null); whether the published schema has since
  caught up; `entry` semantics and writability.

Full verbatim records: `data/audit/compile_dry_run_2026-08-29-deep-tail-fade.json`.

## Step 0 · Re-discover (read-only, no authorization needed)

- [x] Re-read the `compile_strategy_plan` schema from the live connection. Diff
      against this plan's "known" list — if `notes`/`clock`/`closes` are now
      published, or `entry` appeared, update this plan before coding.
- [x] `get_strategy(6a8bca67, includeInactive: true)` again. Confirm clock/closes/
      notes/entry read the same; note any new axes. If the shape moved again,
      record first, plan second.
- [x] `list_strategy_vocabulary()` / `get_strategy_signal_definition` spot-checks
      for new condition or entry documentation.

### Step 0 verdict (measured 2026-08-30, executing session)

The published schema **caught up and moved past** the 2026-08-29 record — drift
instance #3 (required-but-unpublished) has resolved:

- `conditions[].clock` (`'LIVE' | 'CLOSE'`) and `conditions[].closes` are now
  **published and required** on every condition. `closes` is declared
  `integer, 1..5` — bounds now known; >1 behavior still unmeasured.
- `sections[].notes` is now **published and required** on custom sections as
  `string (1..400, no control chars) | null` — **null is explicitly legal per
  schema**, settling the absent-vs-null open question at the schema level
  (behavioral confirmation still pends the compile).
- `entry` is now **published and REQUIRED on CREATE**
  (`{trigger: 'AT_SIGNAL' | 'ON_CANDLE_CLOSE', confirmTf, closes: 1..5,
  bandAtrMultiple > 0}`); optional on UPDATE/RESTORE. The original Step 1 rule
  "`wire()` must not emit `entry`" is therefore impossible for CREATE.
  **Amended decision:** emit `entry` on CREATE mirroring the platform's own
  migration default as read from `6a8bca67` — `{trigger: "AT_SIGNAL",
  confirmTf: <anchor timeframe>, closes: 1, bandAtrMultiple: 1}` — extract,
  never infer; semantics remain unmeasured, so we copy exactly what the
  platform assigned to existing records and nothing else.
- `get_strategy(6a8bca67)` re-read is **byte-identical in shape** to the
  2026-08-29 mid-drift read: all 7 conditions `clock: LIVE, closes: 1`, both
  sections `notes: null`, `entry` default as above, revision still 5,
  `updatedAt` unchanged. Mechanical key-diff against the stored pre-update
  read (`first_generated_update_2026-08-29.json` preState): `entry` is the
  only new top-level axis.
- Spot-checks surfaced two previously unrecorded fields (nowhere in the
  repo): `priceBasis: "LIVE"` on signal definitions (seen on
  `bollinger_lower_touch`), and vocabulary budget `conditionFrameReads: 256`
  (alongside known `strategyConditions: 16`, `conditionClauses: 16`).
  Read-only documentation surface; recorded here, no code consequence yet.

## Step 1 · Omega code (offline; tests green before any live call)

- [x] `omega/types.py`: `CustomSection.notes: str | None` — emit a string on
      wire-out (provenance text) until null-acceptance is measured.
- [x] `omega/conditions.py`: `condition()` gains `clock` and `closes`; wire shape
      carries both on every condition.
- [x] `omega/generate.py` `_build_conditions`: clock policy —
      ambient conditions (`RISK_ON`, `CTX_UP`, `CTX_DOWN`) and the composite
      verdict conditions **LIVE**; candle-only `CORE_UP`/`CORE_DOWN` **CLOSE**
      (stable reads, matches the closed-bar research; the platform migration
      default of LIVE-everywhere is also legal — decision recorded here, revisit
      if the compile refuses composites-referencing-mixed-clocks). `closes: 1`
      everywhere (>1 unmeasured). Implemented as: CORE gets CLOSE iff every
      contributing directional/filter module is candle-backed (`_candle_module`);
      a checklist touching an inert module (FUNDING, OPEN_INTEREST, REGIME,
      FLOW_DIVERGENCE) stays LIVE — the "candle-only" qualifier is load-bearing.
- [x] Conditions validation (`omega/conditions.py`, where the header machinery
      lives): offline guardrail mirroring `CONDITION_CLOCK_OPERAND_ILLEGAL` — a
      CLOSE condition whose clause columns are not all custom-candle-section
      headers at offset 0 is an error; a CLOSE condition referencing a LIVE
      condition is an error; missing/invalid `clock`/`closes` are errors.
- [x] `wire()` emits `entry` on CREATE (schema now requires it — see Step 0
      verdict) mirroring the platform migration default:
      `{trigger: "AT_SIGNAL", confirmTf: <anchor timeframe>, closes: 1,
      bandAtrMultiple: 1}`. No other values until semantics are measured.
      `wire_update()` deletes `entry` — optional on UPDATE, semantics
      unmeasured, never touch an existing strategy's entry axis.
- [x] Tests: new cases for the emitted fields + the clock-legality rule; update
      pinned wire-shape tests; full suite green — **908 passed** (874 baseline
      re-verified green before any change, then 9 pinned wire-shape tests
      updated with dated notes, audit records untouched, plus the new coverage).
- [x] Docs: doc 09 (conditions — clock/closes section), doc 16 (drift instance
      #3, required-but-unpublished form, resolved 2026-08-30), doc 18/20
      untouched (checked: no stale entry/clock claims). Step 0 record:
      `data/audit/step0_rediscovery_2026-08-30.json`.

## Step 2 · Regenerate and re-validate Deep-Tail Fade (offline)

- [x] Rebuild from `data/research/2026-08-29-deep-tail-fade/deep_tail_fade_thesis.json`
      via the patched generator; `validate_thesis` + `brief()` — zero errors.
      (`regenerate_v3.py` in the corpus dir; emits
      `compile_body_deep_tail_fade_v3.json` + `deep_tail_fade_brief_v3.txt`.)
- [x] Diff the new body against `compile_body_deep_tail_fade_v2.json` — the only
      deltas should be the clock policy and native field emission. **Measured
      2026-08-30, exactly three delta classes and nothing else:** clock CLOSE→LIVE
      on the three ambient conditions and both verdicts (the CORE pair stays
      CLOSE, matching v2); `entry` added (required on CREATE); `notes` provenance
      text (generator-composed vs v2's hand-written amendment).

## Step 3 · The compile (live; per-instance authorization REQUIRED)

- [ ] Obtain, verbatim from the user in that session: *"I authorize ONE
      compile_strategy_plan call for Deep-Tail Fade in this session — compile
      only, nothing applied."*
- [ ] ONE compile. Record verbatim into `data/audit/` (extend the existing
      dry-run file; planToken as length+sha256 only; token left to expire).
- [ ] If refused: the refusal is the finding; update this plan, stop.
- [ ] If viable: check `postState` — cadence INTRADAY/4h, minted sectionKeys,
      13 weighted rules, execution defaults, and what the server did with
      `clock`/`closes`/`notes`/`entry`. Settle the open questions in doc 16.

## Step 4 · Beyond the compile (each its own user authorization)

- [ ] Create + verify + auto-archive per P2 (doc 20 §5 template), then registry
      `new_entry` + checklist per doc 20 §6, commit both.
- [ ] Out-of-sample research re-pull (read-only, cheap): same 12+10 candle pulls
      on a later date; rerun `test_c_wide.py` against the new window; record
      whether the >90th-pct 1h reversion cell survives. The funding-side
      confound resolves only in a window with mixed funding signs.
- [ ] Binding/deployment: **never** — user-only, always (P4).

## Session hand-off state (2026-08-29, session 1d58af07)

Committed alongside this plan: the research record
(`docs/superpowers/specs/2026-08-29-deep-tail-fade-research.md`), the preserved
corpus (`data/research/2026-08-29-deep-tail-fade/` — 22 irreplaceable candle
series, funding history, thesis, brief, both compile bodies, analysis scripts),
and the dry-run audit record. Nothing was created on the platform; quota
untouched; no tokens outstanding.
