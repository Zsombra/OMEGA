# Contract 61 Authoring Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every body `omega.generate` emits passes the schema-drift preflight against the live compile definition (contract 61.0.1) with zero FAIL and zero UNSUPPORTED findings, so a compile is no longer refused on the condition and entry axes.

**Architecture:** Three axes of the wire body move to what the platform serves today, each mirrored from a capture committed with this plan and never invented: conditions lose the retired `clock` key and gain the published hold and read rules in the offline type-check; the entry object becomes the three-key form the platform migrated every stored record to; the preflight walker models `multipleOf`, its mirror lists follow the new shapes, and the execution bounds follow the changelog the walker itself computed between the 09-09 and 09-18 captures. Docs and a drift record close the loop.

**Tech Stack:** Python 3.14 (`python -m pytest tests/ -q`, 1009 passing at `ccbe6b1`), pydantic models in `omega/types.py`, the preflight walker in `omega/preflight.py` and its CLI `scripts/preflight.py`.

**Requested by the user 2026-09-18:** "continue with this. Make sure that we follow the plan that we have. Make sure we don't assume anything." The plan being followed is `battlegrid-manager/docs/status/2026-09-18-where-we-stand.md` § 4 decision #20 ("OMEGA generator emits the retired `clock` key; every compile is refused since 61.0.0 — fix before the next authoring run"). Measuring the scope showed it is wider than `clock`: the entry axis is refused too.

## Measured facts this plan relies on (2026-09-18, contract 61.0.1, build `7296172b`)

| Fact | Value | Evidence |
|---|---|---|
| Preflight of every preset body against the live compile definition | **FAIL.** Per body: 7 × `UNDECLARED conditions[i].clock`; `ENUM entry.trigger 'AT_SIGNAL' not in the declared enum (3 values)`; `UNDECLARED entry.confirmTf`, `entry.closes`, `entry.bandAtrMultiple`; `WARN MIRROR entry.trigger body 'AT_SIGNAL' vs record 'ON_CANDLE_CLOSE'`; ~93 × `WARN UNSUPPORTED … ['multipleOf']` (every `closes`, every `rules[i].allocation`, `minAggregateScore`, `minRequiredCount`, `entry.levelOffsetAtrMultiple`) | `scripts/preflight.py run` 08:40 UTC on the five `plan(PRESETS[...]).wire()` bodies |
| Schema capture | `data/contract/compile_strategy_plan/schema_20260918T083359Z.json` — the `tools/list` definition stored by the manager's watch at 08:33:59 UTC (contract 61.0.1), exported read-only; preflight fingerprint `ok` | committed with this plan |
| CREATE arm today | required `[operation, intentSummary, assumptions, coinSelection, name, timeframe, sections, entry]`; `entry` = `{trigger ∈ [ON_CANDLE_CLOSE, STOP_THROUGH_LEVEL, ON_RETEST], levelOffsetAtrMultiple 0–2 multipleOf 0.1, validForBars 1–24}`, all three required, `additionalProperties: false`; condition required keys `[conditionKey, name, definition, verdict, required, exit, closes]`, `closes` 1–5 multipleOf 1; column properties `[bars, chainedTransformId, inputs, metric, offset, ordering, side, timeframe, transformId, window]` | same capture |
| Changelog 09-09 → 09-18 (computed by `omega.preflight.changelog` over the two captures) | `conditions[]`: `clock` removed; `entry`: `bandAtrMultiple`, `closes`, `confirmTf` removed, `trigger` enum loses `AT_SIGNAL`; `maxStopLossAtrMultiple` gains `maximum 3`; `minAtrPct` loses its bounds (`{minimum 0.01, maximum 50}` → `{}`); `timeDecayGracePeriodMinutes` minimum 1 → 5; `timeDecayIntervalMinutes` minimum 1 → 5; `timeDecayTightenPct` minimum 0.1 → 0.5; column `metric` enum gains **twelve** keys: the nine TPO keys `PRIOR_TPO_SHAPE, PRIOR_TPO_IB_HIGH, PRIOR_TPO_IB_LOW, TPO_VPOC, TPO_VVAH, TPO_VVAL, PRIOR_TPO_VPOC, PRIOR_TPO_VVAH, PRIOR_TPO_VVAL` and `NAKED_POC_ABOVE, NAKED_POC_BELOW, PDO` (corrected 2026-09-18 by Task 4: the plan first listed nine from a truncated changelog line; the committed receipt carries the full list) | `--previous-schema schema_20260909T080307Z.json`, 08:50 UTC; `data/audit/compile_preflight_2026-09-18-trend-continuation.json` |
| What the platform migrated the entry axis TO | Strategy `824f4343` (created 2026-09-03 with `AT_SIGNAL` and six keys, still revision 1) reads back `entry: {trigger: "ON_CANDLE_CLOSE", levelOffsetAtrMultiple: 0, validForBars: 4}` and seven-key conditions with no `clock` | `data/contract/get_strategy/824f4343-e51f-4e5a-87b1-6b44d0bc547f_20260918T084500Z.json` (committed) |
| A strategy authored on 60.x | `43d11467` (created 2026-09-16): the same three-key entry, seven-key conditions | `data/contract/get_strategy/43d11467-637c-42b1-b88b-8a71ed8c32c3_20260918T083500Z.json` (committed; the preflight read-back) |
| The vendor's words on the entry axis | "`{ trigger, levelOffsetAtrMultiple, validForBars }` — all three required on every CREATE, no defaults … There is no confirm-timeframe key either: the bar whose close decides an entry is the strategy's OWN timeframe." "`ON_CANDLE_CLOSE` — the entry is taken AT the qualifying close, at market." "`levelOffsetAtrMultiple` ≠ 0 and `validForBars` ≠ 4 are refused under a non-level trigger. Leave a dial at its inert value rather than setting one the platform will ignore." "A multi-bar hold belongs to the CONDITION that needs it. Declare that condition's own `closes`" | vendor pack 31.2.28 `skills/battlegrid-strategy-examples/SKILL.md` § Entry; README "Contract history — v60" |
| The vendor's words on conditions | "`{ conditionKey, name, definition, verdict, required, exit, closes }` — all seven required, no defaults. A `clock` key is REFUSED." "`closes` is how many consecutive COMPLETED strategy bars must read TRUE (1–5). … Above `1` it is legal only where a completed bar changes the reading: over a header resolved from this coin's own candle series, at offset 0, at or above the strategy timeframe, read Confirmed. Everything else is refused (`CONDITION_HOLD_OPERAND_ILLEGAL`) … A hold also needs a clause of the condition's OWN (`CONDITION_HOLD_ILLEGAL`): a referenced condition is resolved once". "A verdict carrier must read no DEVELOPING bar. A verdict is refused over any closure that reads a column selecting Developing above the strategy timeframe (`CONDITION_VERDICT_READ_ILLEGAL`)." "`exit: true` … Legal only over a closure every operand of which a completed bar MOVES (`CONDITION_EXIT_READ_ILLEGAL`), which rules out a developing read … and rules out a frame-inert operand". "`bars`: `"closed"` is Confirmed … `"all"` is Developing … Left unset the default is a rule, not a value: Confirmed for a column ABOVE the strategy timeframe, and at or below it the series as the frame carries it." | same skill § Conditions (pack 31.2.28, contract 61.0.1) |
| omega today | `conditions.condition()` emits `clock` and validates `CLOCKS`; `_walk`/`validate_conditions` enforce the retired CLOSE rules; `generate._build_conditions` runs a "clock policy" through `_candle_module`; `StrategyPlan.wire()` emits the six-key `AT_SIGNAL` entry; `preflight.MIRROR_ENTRY_FIELDS` / `MIRROR_CONDITION_FIELDS` name the removed keys; `execution.SCHEMA_BOUNDS` holds the 08-28 bounds; the walker's `_MODELED_KEYWORDS` lacks `multipleOf` | `omega/conditions.py`, `omega/generate.py:447-449, 600-636`, `omega/preflight.py:100-108, 366-374`, `omega/execution.py:26-32` |
| `report_headers` already knows per header | `candle` (custom-section, non-timeless metric, offset 0), `ops`, `vocab`, `sectionKey`; platform-section headers are `candle: False` (the offline check is conservative there) | `omega/conditions.py` `report_headers` |
| Column timeframe vocabulary | a column's `timeframe` is `{"rel": "anchor" | "lower" | "regime"}` or `{"abs": <tf>}`; absolute timeframes are ordered in `data/contract/vocabulary/_shared.json` `absoluteTimeframes` (`1m … 1w`) | `omega/types.py`, `scripts/preflight.py` `repo_timeframes` |
| Out of scope, recorded, not assumed | the metric/transform/vocabulary EXTRACTION (`data/contract/_manifest.json`) is the 09-09 one at contract 54.1.0 — the nine TPO metric keys the changelog shows are in the enum but the extraction's metric catalogue is not refreshed by this plan; the TPO branch `claude/tpo-strategy-brainstorm-796f15` pins `builder.ENTRY_MIRROR` with `confirmTf` in `tests/test_tpo_suite_wire.py` and must be brought to the three-key entry when it is merged (Phase 4 prerequisite) | `git diff main..claude/tpo-strategy-brainstorm-796f15 -- tests` |

## Global Constraints

- Extract, never infer: every value the generator emits and every rule the type-check enforces is quoted from a committed capture or the vendor skill text named in the facts table; error messages name the platform's own code (`CONDITION_HOLD_OPERAND_ILLEGAL`, `CONDITION_HOLD_ILLEGAL`, `CONDITION_VERDICT_READ_ILLEGAL`, `CONDITION_EXIT_READ_ILLEGAL`) and the pack version.
- omega never calls BattleGrid (`omega/probe.py:3`); nothing in this plan compiles, applies or reads live. The preflight runs offline against the committed captures.
- The entry mirror is `{"trigger": "ON_CANDLE_CLOSE", "levelOffsetAtrMultiple": 0, "validForBars": 4}` — what the platform wrote onto the pre-60 record and what both 60.x-authored records carry; no other trigger is emitted (level triggers rest orders whose semantics omega has not measured).
- `closes` stays `1` everywhere the generator emits; a hold above 1 is legal to author by hand only where the vendor says, and the offline check refuses it elsewhere.
- Key order of a condition mirrors the read-back: `conditionKey, name, definition, verdict, required, exit, closes`.
- No test is weakened to pass: tests that pinned the retired shape are replaced by tests that pin the served shape and cite the capture.
- Every schema keyword the compile definition uses is modelled or reported; after this plan a preset body's receipt has no UNSUPPORTED finding.
- Commit messages are plain sentences ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`; branch `claude/omega-contract-61-authoring` from `ccbe6b1`.

---

### Task 1: Conditions carry seven keys; the hold and read rules replace the clock rules

**Files:**
- Modify: `omega/conditions.py` (`CLOCKS` removed; `condition()`; `report_headers` adds `above_anchor`, `below_anchor`, `developing` per header; `_walk`; `validate_conditions`)
- Test: `tests/test_conditions.py` (the block from "the condition clock" through `test_live_referencing_a_close_condition_is_legal` is replaced; `test_condition_emits_exit_with_the_migration_default` key-order assertion updated; `CORE_CLOCK`/`test_preset_clock_policy` replaced in Task 2)

**Interfaces:**
- Produces:

```python
# omega/conditions.py
HOLD_MIN, HOLD_MAX = 1, 5     # closes: consecutive completed strategy bars (schema 1..5, multipleOf 1)

def condition(key: str, name: str, definition: dict, *,
              verdict: str | None = None, required: bool = False,
              exit: bool = False, closes: int = 1) -> dict:
    """One wire-shaped condition, contract 61.0.1: exactly the seven keys the platform reads back
    (data/contract/get_strategy/43d11467-..._20260918T083500Z.json), in that order. `closes` is the hold:
    how many consecutive COMPLETED strategy bars must read TRUE (1..5). The per-condition clock was retired
    in 61.0.0 and a `clock` key is refused (vendor pack 31.2.28, strategy-examples § Conditions)."""

# report_headers(report)[header] gains three booleans beside `candle`:
#   "above_anchor": the column's timeframe is above the report anchor ({"rel": "regime"}, or an {"abs"} above it)
#   "below_anchor": {"rel": "lower"} or an {"abs"} below the anchor
#   "developing":   above_anchor and column.bars == "all"   (a Developing read of a higher-timeframe bar)
# Ambient and platform-section headers: all three False (not from a column omega can inspect).
```

**Behaviour of `validate_conditions` (replaces every clock check):**
1. `closes` must be an int 1..5 (not bool) — as today, message names the schema.
2. `closes > 1` (`CONDITION_HOLD_OPERAND_ILLEGAL`): every clause in the condition's OWN definition (not through `conditionRef`) must read a header with `candle` True, `below_anchor` False and `developing` False; otherwise an error at the clause path: `"{header!r} cannot hold {closes} closes: a hold above 1 is legal only over a header resolved from this coin's own candle series at offset 0, at or above the strategy timeframe, read Confirmed (CONDITION_HOLD_OPERAND_ILLEGAL, vendor pack 31.2.28, contract 61.0.1)"`.
3. `closes > 1` with no clause of its own (a definition that is a `conditionRef`, or a group whose members are all `conditionRef`s at any depth) — error at `.definition`: `"a hold of {closes} closes needs a clause of the condition's own; a referenced condition is resolved once and contributes the same answer to every bar (CONDITION_HOLD_ILLEGAL)"`.
4. Verdict carrier (`verdict` in UP/DOWN/NEITHER) whose closure (its own clauses plus everything reached through `conditionRef`, transitively) contains a clause over a header with `developing` True — error at the clause path: `"{header!r} reads a Developing higher-timeframe bar; a verdict carrier may not read one, at any depth (CONDITION_VERDICT_READ_ILLEGAL)"`.
5. `exit: true` whose closure contains a clause over a header with `candle` False or `developing` True — error at the clause path: `"{header!r} is not moved by a completed bar (or is a developing read); exit: true needs a closure every operand of which a completed bar moves (CONDITION_EXIT_READ_ILLEGAL)"`.
6. A condition carrying a `clock` key — error at `.clock`: `"clock was retired in contract 61.0.0 and is refused by the compile schema; drop the key (the hold is `closes`)"`.

> Ruling recorded 2026-09-18 after Task 1's review: a column AT the anchor with `bars: "all"` is NOT a developing read
> (`developing` is `above_anchor and bars == "all"`), so a hold or an exit over it is legal offline. That is the
> vendor's own sentence — "At or below the strategy timeframe the choice therefore sets only what the live lane shows —
> no bar is in progress at the anchor's own close — so Developing there is legal and changes no decision" (pack
> 31.2.28, strategy-examples § Conditions, now committed in this repo at `.agents/skills/battlegrid`, refreshed from
> 31.2.17 for exactly this reason: every rule the code quotes must be checkable here).
7. Everything else (`_walk`'s header/op/vocab checks, cycles, budgets, key/name/verdict/exit checks) unchanged. `_walk` loses its `clock`/`clock_by_key` parameters and gains a `mode` describing what to check for the current condition; closure walking for rules 4 and 5 uses `_reference_edges` plus a per-key clause collector.

- [ ] **Step 1: Write the failing tests** (replace the clock block in `tests/test_conditions.py`; `_report`, `RSI_REPORT`, `num`, `ref`, `all_of`, `condition`, `validate_conditions` are already imported there):

```python
# --- contract 61.0.1: seven keys, the hold, the read rules (2026-09-18) ---------------
# Captures: data/contract/compile_strategy_plan/schema_20260918T083359Z.json (condition required keys
# [conditionKey, name, definition, verdict, required, exit, closes]; closes 1..5) and the two read-backs under
# data/contract/get_strategy/*_20260918T*.json. Rules quoted from vendor pack 31.2.28, strategy-examples § Conditions.

def test_condition_emits_exactly_the_seven_read_back_keys_in_order():
    c = condition("CHK", "n", num("mktBreadth_all", "gt", 10))
    assert list(c) == ["conditionKey", "name", "definition", "verdict", "required", "exit", "closes"]
    assert c["closes"] == 1 and c["exit"] is False and "clock" not in c


def test_condition_refuses_the_retired_clock_keyword():
    with pytest.raises(TypeError):
        condition("CHK", "n", num("mktBreadth_all", "gt", 10), clock="LIVE")


@pytest.mark.parametrize("closes", [0, 6, 1.5, True])
def test_condition_refuses_a_hold_outside_one_to_five(closes):
    with pytest.raises(ValueError):
        condition("CHK", "n", num("mktBreadth_all", "gt", 10), closes=closes)


def test_a_hand_built_condition_with_clock_is_an_error_naming_the_retirement():
    bare = dict(condition("CHK", "n", num("mktBreadth_all", "gt", 10)), clock="LIVE")
    [f] = [f for f in validate_conditions(RSI_REPORT, [bare]) if f.path == ".clock"]
    assert f.severity == "error" and "61.0.0" in f.message


def test_a_hold_over_a_custom_candle_header_at_the_anchor_is_legal():
    cond = condition("CHK", "n", num("RSI14_now", "gt", 50), closes=3)
    assert not [f for f in validate_conditions(RSI_REPORT, [cond]) if f.severity == "error"]


def test_a_hold_over_an_ambient_header_is_refused():
    from omega.conditions import stables_at_par
    cond = condition("CHK", "n", stables_at_par(), closes=2)
    errs = [f for f in validate_conditions(RSI_REPORT, [cond]) if f.severity == "error"]
    assert errs and all("CONDITION_HOLD_OPERAND_ILLEGAL" in f.message for f in errs)


def test_a_hold_over_an_offset_column_is_refused():
    rep = _report({"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "anchor"}, "offset": 4})
    cond = condition("CHK", "n", num("RSI14", "gt", 50), closes=2)
    assert any("CONDITION_HOLD_OPERAND_ILLEGAL" in f.message
               for f in validate_conditions(rep, [cond]) if f.severity == "error")


def test_a_hold_over_an_inert_custom_header_is_refused():
    rep = _report({"metric": "FUNDING_RATE", "transformId": "value", "timeframe": {"rel": "anchor"}})
    cond = condition("CHK", "n", num("rate", "gt", 0), closes=2)
    assert any("CONDITION_HOLD_OPERAND_ILLEGAL" in f.message
               for f in validate_conditions(rep, [cond]) if f.severity == "error")


def test_a_hold_over_a_column_below_the_anchor_is_refused():
    rep = _report({"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "lower"}})
    [header] = [h for h in report_headers(rep) if h.startswith("RSI14")]
    cond = condition("CHK", "n", num(header, "gt", 50), closes=2)
    assert any("CONDITION_HOLD_OPERAND_ILLEGAL" in f.message
               for f in validate_conditions(rep, [cond]) if f.severity == "error")


def test_a_hold_reached_only_through_a_reference_is_refused():
    core = condition("CORE", "n", num("RSI14_now", "gt", 50))
    held = condition("HELD", "n", ref("CORE"), closes=2)
    errs = [f for f in validate_conditions(RSI_REPORT, [core, held]) if f.severity == "error"]
    assert any("CONDITION_HOLD_ILLEGAL" in f.message and f.condition_key == "HELD" for f in errs)


def test_a_verdict_carrier_may_not_read_a_developing_higher_timeframe_bar_even_through_a_reference():
    rep = _report({"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "regime"}, "bars": "all"})
    [header] = [h for h in report_headers(rep) if h.startswith("RSI14")]
    block = condition("BLOCK", "n", num(header, "gt", 50))                       # verdict None: legal
    carrier = condition("TOP", "n", ref("BLOCK"), verdict="UP")
    findings = validate_conditions(rep, [block, carrier])
    assert not [f for f in findings if f.condition_key == "BLOCK" and f.severity == "error"]
    assert any("CONDITION_VERDICT_READ_ILLEGAL" in f.message and f.condition_key == "TOP" for f in findings)


def test_a_confirmed_higher_timeframe_read_admits_a_verdict():
    rep = _report({"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "regime"}, "bars": "closed"})
    [header] = [h for h in report_headers(rep) if h.startswith("RSI14")]
    carrier = condition("TOP", "n", num(header, "gt", 50), verdict="UP")
    assert not [f for f in validate_conditions(rep, [carrier]) if f.severity == "error"]


def test_exit_true_needs_operands_a_completed_bar_moves():
    # keys are two characters: the published conditionKey pattern is ^[A-Z][A-Z0-9_]{1,39}$ (corrected during
    # execution 2026-09-18; the plan first wrote "X"/"Y", which the pattern refuses)
    inert = condition("XX", "n", num("mktBreadth_all", "gt", 10), exit=True)
    errs = [f for f in validate_conditions(RSI_REPORT, [inert]) if f.severity == "error"]
    assert any("CONDITION_EXIT_READ_ILLEGAL" in f.message for f in errs)
    moved = condition("YY", "n", num("RSI14_now", "gt", 50), exit=True)
    assert not [f for f in validate_conditions(RSI_REPORT, [moved]) if f.severity == "error"]
```

  (`report_headers` needs importing in the test module if it is not already; `_report` builds a one-column custom report as the existing tests do — reuse it.) Update `test_condition_emits_exit_with_the_migration_default`'s key list to the seven keys and delete the eight clock tests it replaces (`test_condition_emits_the_clock_fields_with_migration_defaults`, `test_condition_refuses_a_bad_clock_or_closes`, `test_a_condition_without_clock_or_closes_is_an_error`, `test_close_may_not_read_an_ambient_header`, `test_close_may_read_a_custom_candle_header_at_offset_zero`, `test_close_may_not_read_an_offset_column`, `test_close_may_not_read_an_inert_custom_header`, `test_close_referencing_a_live_condition_is_an_error`, `test_live_referencing_a_close_condition_is_legal`); `test_a_condition_without_exit_is_an_error`'s `bare` dict loses `clock`.
- [ ] **Step 2: Run and watch them fail** — `python -m pytest tests/test_conditions.py -q`.
- [ ] **Step 3: Implement** as specified. In `report_headers`, compute `above_anchor`/`below_anchor` from the column's `timeframe` (`rel: regime` → above; `rel: lower` → below; `rel: anchor` → neither; `abs` compared with the report's anchor by the index in `absoluteTimeframes` from `data/contract/vocabulary/_shared.json`, loaded through `contract.load()` if it exposes it, else read once with `lru_cache`), and `developing = above_anchor and column.bars == "all"`.
- [ ] **Step 4: Run the focused tests, then the full suite.** `test_generate.py` and the preset policy test will fail until Task 2 — note them, do not fix them here.
- [ ] **Step 5: Commit** — `Conditions: the seven keys of contract 61.0.1; the hold and read rules replace the retired clock, mirrored from the vendor's text and the 09-18 captures`.

---

### Task 2: The generator emits the migrated entry and no clock policy

**Files:**
- Modify: `omega/generate.py` (`wire()` entry; `_build_conditions` loses the clock policy and `_candle_module`)
- Test: `tests/test_generate.py` (`test_wire_emits_the_platform_migration_entry`, `test_wire_conditions_all_carry_clock_and_closes`), `tests/test_conditions.py` (`CORE_CLOCK` + `test_preset_clock_policy` replaced)

**Interfaces:**
- Produces: `StrategyPlan.wire()["entry"] == {"trigger": "ON_CANDLE_CLOSE", "levelOffsetAtrMultiple": 0, "validForBars": 4}` for every preset; every emitted condition has the seven keys with `closes == 1`. A module-level constant:

```python
# omega/generate.py
# The entry axis, contract 60.0.0/61.0.1. Mirrored, not interpreted: the platform migrated the pre-60 record
# 824f4343 (AT_SIGNAL, six keys) to exactly this (data/contract/get_strategy/824f4343-..._20260918T084500Z.json),
# and both 60.x-authored records carry it. ON_CANDLE_CLOSE takes the entry AT the qualifying close, at market;
# 0 and 4 are the inert values for a non-level trigger ("levelOffsetAtrMultiple != 0 and validForBars != 4 are
# refused under a non-level trigger", vendor pack 31.2.28). The level triggers rest orders omega has not measured.
ENTRY_MIRROR: dict = {"trigger": "ON_CANDLE_CLOSE", "levelOffsetAtrMultiple": 0, "validForBars": 4}
```

- [ ] **Step 1: Write the failing tests.** Replace `test_wire_emits_the_platform_migration_entry`'s assertion with `assert p.wire()["entry"] == ENTRY_MIRROR` and a docstring that cites the two captures; rename `test_wire_conditions_all_carry_clock_and_closes` to `test_wire_conditions_carry_the_seven_keys_with_a_one_close_hold` asserting `list(c) == [the seven]` and `c["closes"] == 1` for every emitted condition; in `tests/test_conditions.py` replace `CORE_CLOCK`/`test_preset_clock_policy` with:

```python
@pytest.mark.parametrize("name", PRESET_IDS)
def test_presets_hold_one_close_everywhere_and_carry_no_clock(name):
    """61.0.0 retired the per-condition clock; a hold above 1 is unmeasured for the presets, so every emitted
    condition holds one completed strategy bar (vendor pack 31.2.28: `closes` is the hold)."""
    for c in plan(PRESETS[name]).conditions:
        assert "clock" not in c and c["closes"] == 1, c["conditionKey"]
```

- [ ] **Step 2: Run and watch them fail.**
- [ ] **Step 3: Implement**: `wire()` emits `ENTRY_MIRROR` (a copy) with the comment above replacing the six-key history comment (keep one sentence pointing at git history for the 08-30/09-09 forms); `_build_conditions` drops `core_close`/`core_clock` and every `clock=` argument; delete `_candle_module` and the "Clock policy" comment; update the docstring of `_build_conditions` if it mentions the clock.
- [ ] **Step 4: Full suite** — `python -m pytest tests/ -q`. Expected: everything but the preflight/write-surface tests touched in Task 3 passes; if `tests/test_write_surface.py` or `tests/test_execution.py` fail here, note which and continue (Task 3 owns them).
- [ ] **Step 5: Commit** — `Generator: the three-key entry the platform migrated every record to (ON_CANDLE_CLOSE, 0, 4); the clock policy is gone with the clock`.

---

### Task 3: The preflight models `multipleOf`, mirrors the new shapes, and the execution bounds follow the changelog

**Files:**
- Modify: `omega/preflight.py` (`_MODELED_KEYWORDS`, numeric branch of `_walk`, `MIRROR_ENTRY_FIELDS`, `MIRROR_CONDITION_FIELDS`), `omega/execution.py` (`SCHEMA_BOUNDS` + its provenance comment)
- Test: `tests/test_preflight.py`, `tests/test_execution.py` (whichever asserts `SCHEMA_BOUNDS`), `tests/fixtures/preflight/schema_walker_min.json` (add one `multipleOf` to the miniature's `entry.levelOffsetAtrMultiple` and to `conditions.items.closes`), and `tests/test_write_surface.py::test_wire_entry_keys_match_the_live_schema_capture` — it pins the emitted entry keys against `SCHEMA_CAPTURE_2026_09_09`; point it (and the constant) at `data/contract/compile_strategy_plan/schema_20260918T083359Z.json`, keeping its two-direction assertion and its `levelSource` guard, and add the guard `assert "confirmTf" not in allowed, "capture predates the 60.0.0 removal - re-capture"` (added 2026-09-18 during execution: Task 2 made this test fail as the plan expected but had not named it)

**Behaviour:**
1. `multipleOf` joins `_MODELED_KEYWORDS`; in the numeric branch: a value `v` with `multipleOf: m` where `abs(round(v / m) - v / m) > 1e-9` is `BOUNDS` FAIL `f"{v} is not a multiple of {m}"`.
2. `MIRROR_ENTRY_FIELDS = ("trigger", "levelOffsetAtrMultiple", "validForBars")` with the comment rewritten: `confirmTf`, `closes` and `bandAtrMultiple` left the entry object in 60.0.0 (captured 2026-09-18); `MIRROR_CONDITION_FIELDS = ("closes", "exit")` (clock retired in 61.0.0).
3. `SCHEMA_BOUNDS` becomes what the 09-18 capture declares: `maxStopLossAtrMultiple: (None, 3)` if the structure allows an open lower bound — otherwise add a separate `SCHEMA_MAXIMA` entry; `minAtrPct` removed from `SCHEMA_BOUNDS` (unbounded in the schema now; the catalog bound stays where it is); `timeDecayIntervalMinutes: (5, 480)`, `timeDecayGracePeriodMinutes: (5, 1440)`, `timeDecayTightenPct: (0.5, 50)`; the comment cites the changelog line and the capture. Check `PLATFORM_EXECUTION_DEFAULTS` against the new minima (60, 15, 5 are all inside) and say so in the comment.

- [ ] **Step 1: Write the failing tests** in `tests/test_preflight.py`:

```python
def test_walker_models_multiple_of():
    """The 61.0.1 definition declares multipleOf on closes (1), rules[].allocation (1), minAggregateScore (0.05),
    minRequiredCount (1) and entry.levelOffsetAtrMultiple (0.1); a preset body's receipt carried ~93 UNSUPPORTED
    warnings for it on 2026-09-18. Modelled: a non-multiple is a BOUNDS FAIL, a multiple passes, no UNSUPPORTED."""
    arm, root = _create_arm()
    body = _good_body()
    body["entry"]["levelOffsetAtrMultiple"] = 0.15
    findings = P.diff_schema(body, arm, root)
    assert ("BOUNDS", "entry.levelOffsetAtrMultiple") in _fails(findings)
    assert not [f for f in findings if f.cls == "UNSUPPORTED" and "multipleOf" in f.detail]
    body["entry"]["levelOffsetAtrMultiple"] = 0.3
    assert ("BOUNDS", "entry.levelOffsetAtrMultiple") not in _fails(P.diff_schema(body, arm, root))


def test_mirror_fields_are_the_61_shapes():
    assert P.MIRROR_ENTRY_FIELDS == ("trigger", "levelOffsetAtrMultiple", "validForBars")
    assert P.MIRROR_CONDITION_FIELDS == ("closes", "exit")


def test_every_preset_body_passes_the_preflight_against_the_2026_09_18_captures():
    """The gate this plan exists for: zero FAIL and zero UNSUPPORTED against the committed 61.0.1 capture and the
    09-18 read-back, for every preset."""
    from omega.generate import PRESETS, plan
    schema = json.loads((ROOT / "data/contract/compile_strategy_plan/schema_20260918T083359Z.json").read_text(encoding="utf-8"))["response"]
    arms, root = P.resolve_arms(schema)
    record = json.loads((ROOT / "data/contract/get_strategy/43d11467-637c-42b1-b88b-8a71ed8c32c3_20260918T083500Z.json").read_text(encoding="utf-8"))["response"]
    for name in sorted(PRESETS):
        body = plan(PRESETS[name]).wire()
        findings = P.diff_schema(body, arms["CREATE"], root) + P.diff_record(body, record, arms["CREATE"], root) \
            + P.mirror_findings(body, record)
        assert _fails(findings) == [], (name, _fails(findings))
        assert [f for f in findings if f.cls == "UNSUPPORTED"] == [], name
        assert [f for f in findings if f.cls == "MIRROR"] == [], name
```

  (`ROOT` exists in that module or is `Path(__file__).resolve().parents[1]`.) Also change `test_mirror_warns_never_fails_on_a_differing_mirror_value` so the differing condition field is `closes` (`{"closes": 2, "exit": False}` against a record carrying 1) and expects `("MIRROR", "conditions[0].closes", "WARN")`; drop `clock` from the bodies in `test_mirror_is_quiet_when_values_match_and_ignores_confirmTf` and `test_mirror_findings_handles_a_list_valued_body_condition_field_without_raising`. `_migrated_record()` and the drift-#3 replay stay as history (they replay a 2026-09-04 record); if `test_replay_drift3_clock_and_closes_missing_vs_record` still passes it stays; if it fails only because the mirror list changed, adjust its docstring, not its assertion. For the execution bounds, find the test that pins `SCHEMA_BOUNDS` (grep `SCHEMA_BOUNDS` under `tests/`) and update its expectations to the new values with the changelog cited.
- [ ] **Step 2: Run and watch them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Full suite.** Expected: all pass.
- [ ] **Step 5: Commit** — `Preflight: multipleOf modelled, mirror lists follow contract 61, execution bounds follow the measured changelog; every preset passes against the 09-18 captures`.

---

### Task 4: Receipts, the drift record, and the docs

**Files:**
- Create: `data/audit/compile_preflight_2026-09-18-trend-continuation.json` (a real `scripts/preflight.py run` receipt, PASS), `data/contract/_drift_2026-09-18.json`
- Modify: `docs/09-conditions.md` (§ "The condition clock" → "The hold count (the clock was retired in contract 61.0.0)"), `docs/16-the-write-path.md` (new § "Drift instance #6 (2026-09-18): the entry axis shrank to three keys and the clock left"), `README.md` (test count)
- Test: none new (the receipt is produced by the CLI; `tests/test_preflight_cli.py` already covers the CLI)

- [ ] **Step 1: The receipt.** From the repo root: write the trend-continuation body to `data/audit/compile_body_trend_continuation_2026-09-18.json` (`{"request": plan(PRESETS["trend-continuation"]).wire()}`), then `python scripts/preflight.py run data/audit/compile_body_trend_continuation_2026-09-18.json --schema data/contract/compile_strategy_plan/schema_20260918T083359Z.json --readback data/contract/get_strategy/43d11467-637c-42b1-b88b-8a71ed8c32c3_20260918T083500Z.json --previous-schema data/contract/compile_strategy_plan/schema_20260909T080307Z.json --slug trend-continuation --now <the UTC time of the run>`. It must print PASS. (The gate's expiry is measured from the captures' `capturedAt`, so pass `--now` within 60 minutes of 08:35 UTC or, if that has passed, pass `--expires-minutes` large enough and say so in the drift record: the captures are the ones committed with the plan and were not re-taken.)
- [ ] **Step 2: The drift record** `data/contract/_drift_2026-09-18.json`, in the shape of `_drift_2026-09-05.json` (`_what`, `measuredAt`, `evidence`, then the measured lists), written by a small script from the receipt's CHANGELOG findings — every list in it comes from that receipt, none typed by hand: the removed condition key, the removed entry keys and enum member, the moved bounds, the nine metric keys added to the enum, the contract versions (54.1.0 → 61.0.1, builds `37cb29b6` → `7296172b`), and a `notResolved` block stating that the metric/transform/vocabulary extraction is still the 09-09 one and that the TPO branch's wire test pins the old entry.
- [ ] **Step 3: Docs.** `docs/09-conditions.md`: replace the clock section with the hold count and the three read rules, each quoted from the vendor with the pack version, plus one paragraph on what omega checks offline (`candle`, `above_anchor`, `developing`) and what it cannot (platform-section headers are conservative). `docs/16-the-write-path.md`: the new drift-instance section states what was refused (the preflight's findings of 08:40 UTC, counts included), what the platform migrated the stored records to (the 824f4343 read-back), what changed in omega, and that the receipt PASSes. `README.md` test count updated to the suite's number.
- [ ] **Step 4: Full suite once more; commit** — `Contract 61 on the authoring surface: PASS receipt, the 09-18 drift record, and the docs follow the hold count and the three-key entry`.

---

## Self-review

- **Coverage of #20 as measured:** conditions (Task 1), entry (Task 2), the preflight noise that would hide the next drift (Task 3), the record and docs (Task 4). The gate test in Task 3 is the plan's own acceptance criterion.
- **Not assumed:** the entry mirror comes from the platform's migration of a pre-60 record; the condition rules are the vendor's sentences; the bounds come from the walker's changelog; the nine metric keys are in the changelog but the extraction refresh is explicitly out of scope and recorded.
- **Types:** `condition(..., closes=)` without `clock`; `ENTRY_MIRROR`; `HOLD_MIN/HOLD_MAX`; `report_headers()[h]["above_anchor"|"below_anchor"|"developing"]`; `MIRROR_ENTRY_FIELDS`, `MIRROR_CONDITION_FIELDS` as tuples — used with the same names across tasks.
