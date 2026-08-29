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

- [ ] Re-read the `compile_strategy_plan` schema from the live connection. Diff
      against this plan's "known" list — if `notes`/`clock`/`closes` are now
      published, or `entry` appeared, update this plan before coding.
- [ ] `get_strategy(6a8bca67, includeInactive: true)` again. Confirm clock/closes/
      notes/entry read the same; note any new axes. If the shape moved again,
      record first, plan second.
- [ ] `list_strategy_vocabulary()` / `get_strategy_signal_definition` spot-checks
      for new condition or entry documentation.

## Step 1 · Omega code (offline; tests green before any live call)

- [ ] `omega/types.py`: `CustomSection.notes: str | None` — emit a string on
      wire-out (provenance text) until null-acceptance is measured.
- [ ] `omega/conditions.py`: `condition()` gains `clock` and `closes`; wire shape
      carries both on every condition.
- [ ] `omega/generate.py` `_build_conditions`: clock policy —
      ambient conditions (`RISK_ON`, `CTX_UP`, `CTX_DOWN`) and the composite
      verdict conditions **LIVE**; candle-only `CORE_UP`/`CORE_DOWN` **CLOSE**
      (stable reads, matches the closed-bar research; the platform migration
      default of LIVE-everywhere is also legal — decision recorded here, revisit
      if the compile refuses composites-referencing-mixed-clocks). `closes: 1`
      everywhere (>1 unmeasured).
- [ ] `omega/validate.py` (or conditions validation): new offline guardrail
      mirroring `CONDITION_CLOCK_OPERAND_ILLEGAL` — a CLOSE condition whose
      clause columns are not all custom-candle-section headers at offset 0 is an
      error; a condition referencing a LIVE condition must itself be LIVE.
- [ ] `wire()` must **not** emit `entry` (unmeasured axis).
- [ ] Tests: new cases for the emitted fields + the clock-legality rule; update
      pinned wire-shape tests; full suite green (874 + new).
- [ ] Docs: doc 09 (conditions — clock/closes), doc 16 (drift instance #3,
      required-but-unpublished form), doc 18/20 untouched unless Step 0 moved.

## Step 2 · Regenerate and re-validate Deep-Tail Fade (offline)

- [ ] Rebuild from `data/research/2026-08-29-deep-tail-fade/deep_tail_fade_thesis.json`
      via the patched generator; `validate_thesis` + `brief()` — zero errors.
- [ ] Diff the new body against `compile_body_deep_tail_fade_v2.json` — the only
      deltas should be the clock policy and native field emission.

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
