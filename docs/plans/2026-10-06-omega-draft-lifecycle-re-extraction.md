# OMEGA on the strategy draft lifecycle (contract 84 → 91) — re-extraction plan

**Status: PROPOSED 2026-10-06** (R4 of battlegrid-manager `docs/plans/2026-10-05-v85-replan.md`: offline, no
platform call). Sources, all on disk:

- `data/contract/stage_strategy_draft/schema_20261005T194629Z.json`: the input schemas of `stage_strategy_draft`,
  `get_strategy_draft`, `commit_strategy_draft`, `discard_strategy_draft`, `list_strategy_drafts` and
  `preview_strategy_report` at contract **91.0.0** (build `7026bafd`'s predecessor `c8a39a0c`; the later builds moved
  no tool), from battlegrid-manager's stored surface.
- `.agents/skills/battlegrid/README.md` (pack 31.2.73): the contract history for v84, v85, v88, v88.1 and v89.

## Why

Since v85, `compile_strategy_plan` no longer exists, and every body `omega/generate.py` emits is refused:

- **v85:** strategies change only through drafts. `get_strategy_draft` → `stage_strategy_draft {strategyId?,
  draftVersion, axes}` → `commit_strategy_draft`. The flat `CREATE`/`UPDATE` plan is split into ten axes.
- **v84:** a condition no longer carries `closes`. **Every clause and every group requires `hold: {atLeast, of}`.**
- **v88:** a condition no longer carries `exit`. **Every condition requires `exitSide`**: `LONG | SHORT | BOTH` for
  an exit rule, `null` for an entry condition.

## The mapping (each line from the changelog or the schema; nothing inferred)

### Body → axes

| Old flat field(s) | Axis (each staged WHOLE, except SIGNAL_RULES) |
|---|---|
| `name`, `tagline`, `description` | `IDENTITY {name, tagline, description}`, all required |
| `timeframe` | `TIMEFRAME_PROFILE {timeframe}` |
| `sections` | `REPORT {sections}` (same section union; the 64-item caps are gone from the schema) |
| `conditions` | `CONDITIONS {conditions}` (new grammar below) |
| `marketReadText` | `MARKET_READ {marketReadText}` |
| `rules` | `SIGNAL_RULES {rules}`: `allocation` is now an **integer** 0..3 and **required**, as is `required`. The axis replaces only the rules for the signals named |
| `minAggregateScore`, `minAtrPct`, `minRequiredCount` | `SETUP_GATES` (all three required) |
| `min/maxStopLossAtrMultiple`, `minRiskRewardRatio` | `TRADE_LEVEL_POLICY` (all three required) |
| the 13 trailing / break-even / time-decay / invalidation dials | `POSITION_MANAGEMENT` (all 13 required) |
| `entry` | `ENTRY {entry}`: a union on `trigger`. `{trigger: "ON_CANDLE_CLOSE"}` **alone** (naming either dial is refused), or a level trigger with `levelOffsetAtrMultiple` and `validForBars` |
| `operation`, `intentSummary`, `assumptions` | gone: the draft is the intent; a create is a stage with no `strategyId` |
| `coinSelection` | gone from the strategy; it is an input of `preview_strategy_report` only |

The numeric bounds the 09-18 compile schema published (`trailingGivebackPct` 25..55 etc.) are **absent** from the
v91 axis schemas. Since v89 a create judges every dial against the operator bounds configured now, in the draft's
`diagnostics` and at commit. `omega/execution.py`'s `SCHEMA_BOUNDS` becomes a record of a retired schema, never a
gate.

### Conditions

- **`closes: n` → `hold: {atLeast: n, of: n}`** ("n closes in a row"). `{1,1}` is one read, what every pre-v84
  condition with `closes: 1` did. `{1,n}` is "within n closes"; anything else is "at least m of n".
- The hold sits on **each clause and each group**. A `conditionRef` carries none. OMEGA places a condition's hold on
  its definition's root node, and every nested node reads `{1,1}`. The builder refuses "a group hold over members
  that hold their own bars", so a group above 1 requires its members at `{1,1}`.
- **No fixed ceiling.** The 1..5 limit (`HOLD_MIN`/`HOLD_MAX`) is retired: each column admits up to
  `conditionHold.maxWindow` / `maxAtLeast` (1 for an event). Those are served by `preview_strategy_report` and
  `list_strategy_vocabulary` at v84+. **No v84+ vocabulary read is on disk**, so OMEGA checks only the schema
  (`atLeast`, `of` ≥ 1 and `atLeast` ≤ `of`), and the builder judges the window. The 61.2.0 `closesReadable` flag
  is kept as a warning for a hold above 1 on a column it marked unreadable, never as an error.
- **`exit: false` → `exitSide: null`.** An entry condition.
- **`exit: true` → two conditions**, exactly as the platform migrated stored strategies (v88): the entry condition
  keeps its verdict with `exitSide: null`, plus an exit rule `CLOSE_ON_<conditionKey>`: `definition {kind:
  "conditionRef", conditionKey}`, `verdict: null`, `required: false`, and `exitSide` set to the side the verdict
  opposes (`UP` → `SHORT`, `DOWN` → `LONG`, `NEITHER` or `null` → `BOTH`). The key must still fit
  `^[A-Z][A-Z0-9_]{1,39}$`; a key too long for the prefix is an error, never truncated silently.
- New builder rules to mirror as findings: an exit rule carries `verdict: null` and `required: false`
  (`CONDITION_EXIT_RULE_CARRIES_VERDICT`, `CONDITION_EXIT_RULE_REQUIRED`); an entry condition cannot reference an
  exit rule (`CONDITION_ENTRY_REFERENCES_EXIT_RULE`).

### Dry run

The compile dry run becomes `preview_strategy_report {coinSelection, source: {kind: "FIELDS", timeframe, sections,
conditions, marketReadText, marketReadLensTicker?}}`, a read-only call that judges the report and the conditions
with the v84/v88 grammar. It does **not** judge signal rules, gates or dials: only a stage does, and a stage is a
write. A live run of either stays the user's call, as before.

## Work (test-first, one commit per step, suite green after each)

1. **Contract data.** Keep the saved schema; add a `data/contract/_manifest.json` note pointing to it and marking
   `compile_strategy_plan/` and the pre-v84 `get_strategy/` records as retired (kept, never read as current).
2. **`omega/conditions.py`.** `condition(..., exit_side=None)`; the clause and group builders (`num`, `is_`,
   `all_of`, `n_of`, ...) take `hold=(atLeast, of)` (default `(1, 1)`); a `held(n)` helper for `(n, n)`;
   `exit_rule(key, name, definition, side)`; `close_on(cond)` (the v88 split). `validate_conditions` drops the
   `exit`/`closes` checks and gains: `exitSide` present and in the enum; `hold` on every clause and group, absent
   on a ref; `atLeast` ≤ `of`; a group above `{1,1}` over members above `{1,1}` → error; the three exit-rule
   findings above; `closesReadable` → warning only.
3. **`omega/generate.py`.** `StrategyPlan.axes()` returns the ten-axis dict for a create. `axes_update()` returns
   the same without `ENTRY` (the old UPDATE rule: never touch an existing strategy's entry axis). `preview_request()`
   returns the FIELDS preview body with the thesis's `coinSelection`. `wire()`/`wire_update()` are removed, not
   aliased. Rules are emitted with integer allocations. `_build_conditions` uses the new builders. The `assumptions`
   text moves into `render()`'s output only.
4. **`omega/preflight.py`.** Resolve the axis schemas instead of the `operation` arms; walk each axis value against
   its schema; `MIRROR_CONDITION_FIELDS` becomes `("exitSide",)` plus the per-node `hold` check; the read-back
   mirror against `data/contract/get_strategy/` records is **retired** (pre-v84 records carry `closes`/`exit`)
   until a v91 read-back is captured.
5. **Scripts.** `scripts/compile_dry_run.py` → `preview_dry_run.py` (builds the FIELDS body, never calls without
   `--live`); `scripts/compare_vocabulary.py` reads `sectionKey` from `REPORT` on the new schema; `scripts/preflight.py`
   follows step 4.
6. **Docs.** `docs/09-conditions.md` and `docs/08-strategy-generation.md` gain a short "at contract 91" section; the
   old text stays as history.

## Owed measurements (each a platform call, so each is the user's word)

- **M1: the seeded dials of a create draft.** Whole axes force OMEGA to send every dial. Until a create draft's
  seeded `SETUP_GATES` / `TRADE_LEVEL_POLICY` / `POSITION_MANAGEMENT` are read, OMEGA sends its 08-28
  `PLATFORM_EXECUTION_DEFAULTS`, which v89 may refuse. One stage into a sandbox draft plus one `get_strategy_draft`,
  then `discard_strategy_draft`.
- **M2: the hold ceilings.** One `list_strategy_vocabulary` read for `conditionHold` per header.
- **M3: one FIELDS preview** of a generated body, to prove the conditions are accepted.
