# The condition vocabulary at contract 108 — record

**Status: DONE 2026-10-11** on branch `feat/condition-vocabulary-108` (offline: no platform call of any kind, no push,
no merge). Baseline main `ce3cb13` / tag v0.4.0: 1280 passed. Follows
[`2026-10-11-omega-v108-conditions-only.md`](2026-10-11-omega-v108-conditions-only.md), whose "Open" item this closes
for the conditions.

## Sources (all on disk)

- The saved 108 write schema, `data/contract/stage_strategy_draft/schema_20261010T215326Z.json` (contract 108.0.0,
  build `1076c4e7`, from battlegrid-manager `tests/fixtures/2026-10-11-surface-108.0.0/manager_schemas_108.0.0.json`).
- README "Contract history" v98 (prior-bar operators), v100 (bar geometry, `levelInteraction`, `bandTouch` retired,
  `buffer`), v101.1 (swing structure), v103 (64 maxima removed, `conditionGrammar`), from the fixture's
  `README_battlegrid-mcp_main_v108.md`.
- The vendor `battlegrid-strategy-examples` skill (pack 31.2.94, exported at 105.0.0), § Conditions.
- The 104.0.0 / 104.1.0 `get_metric_construction_hints` input schemas in battlegrid-manager
  `tests/fixtures/2026-10-08-surface-104.*/tool_definitions.json` (171 metrics; identical to the 108 column enum).

## What is modelled

| | where | test |
|---|---|---|
| The inventory: 13 clause operators in 5 arms, operands and bounds, hold, column, ref, group, condition object, conditions-array bounds (none), preview grammar = stage grammar, per-header `conditionOperators` / `conditionHold` fields, column `metric` (171) / `transformId` (17) / `chainedTransformId` (5) enums — each with its JSON Pointer | `omega/condition_vocabulary.py` → `data/derived/condition_vocabulary_108.json` (`scripts/derive_condition_vocabulary.py`) | `tests/test_condition_vocabulary_108.py` re-derives it from the schema file |
| Builders `crosses_above`, `crosses_below`, `increased`, `decreased`, `enters`, `exits`, `hold` on every clause | `omega/conditions.py` | `tests/test_conditions_prior_bar.py` |
| `validate_conditions` errs exactly where the schema refuses (operator, required operand, undeclared key, operand type and bounds), read from the derived arm | `omega/conditions.py` `_check_arm` | positive and negative bodies, each also walked by `omega.preflight` against the saved schema |
| Description rules as warnings with the quoted source: header kind vs operator (README v98), one-bar history (`conditionHold.maxWindow` 1, vendor skill), edge held in a row (v98), `ALL` held over an edge (vendor skill), transition label outside the vocabulary | `omega/conditions.py` `_check_prior_bar` and the hold checks | same |
| 171 metrics: 156 measured + 15 known by name (`METRIC_UNMEASURED` on any column over one; never generated) | `data/contract/metrics/_unmeasured_108.json`, `omega.contract.Contract.unmeasured_metrics`, `omega.validate` | `tests/test_metric_vocabulary_108.py` |
| `compare_vocabulary`: stored metrics = 171; `storedUnmeasured` lists the 15 | `scripts/compare_vocabulary.py` | same |

Gaps closed (`omega.condition_vocabulary.gaps()`): clause operators 6 → 0; metrics 15 missing → 0 missing, 15
unmeasured.

## Gaps recorded and not closed (each a REPORT re-extraction, not the condition grammar)

- `bandTouch` is no longer served (retired at v100) and is still in the 61.2.0 corpus and `omega.space`'s 681-cell
  space; refusing it in `validate_column` moves that space. The generator never emits it; the preflight's schema walk
  refuses it (ENUM).
- `levelInteraction` (v100) and `classifyState` are served transforms omega does not author.
- `buffer` (v100) is a served column field not on `omega.types.Column`; the `le=64` maxima on `window` / `offset` and
  a section's columns, removed at v103, are still on the model.
- `conditionFrameReads` (256) is not checked; a prior-bar clause reads one bar more ("a clause held 'within 3 closes'
  reads four bars", vendor skill).

## Presets

None changed: no preset's description asks for a cross, a flip or a change on the bar before (all five describe
states). TPO S6 "POC Cross-Recross" is a single bar crossing and returning, which `crossesAbove` does not express (it
compares two completed closes); the README's reading for it is a `levelInteraction` reject, unmeasured on
`PRIOR_TPO_POC`. Pinned by `test_no_preset_changed_because_no_preset_description_asks_for_a_prior_bar_read`.

## Unmeasured, and the live reads that would measure it (each a platform call: the user decides)

1. **The 15 metrics' contracts** — `get_metric_construction_hints {metric}` for each of `BAR_CONTAINMENT, CANDLE_DOJI,
   CANDLE_ENGULFING, CANDLE_PIN, CANDLE_RUN, CLOSE_RUN, GAP, GAP_PCT, GAP_RANGE_CLEAR, HL2, HLC3, OHLC4,
   SWING_FRACTAL_HIGH, SWING_FRACTAL_LABEL, SWING_FRACTAL_LOW` (15 reads): transforms, native output kind and
   vocabulary, timeframe mode, code. Then the 61.2.0 procedure for the new cells (`scripts/refresh_metric_contracts.py`,
   `scripts/build_corpus.py`, the render-coverage sweep): one `get_strategy_column_contract` per new (metric, transform)
   cell for its headers, `conditionOperators`, `lookback`, `measurement` and `seriesHome`.
2. **Which header admits which prior-bar operator, and its hold domain** — one `preview_strategy_report` at
   `detail: "detailed"` over a report carrying one header of each kind (numeric candle, e.g. `RSI14_now`; timeless
   numeric, e.g. `chg24h`; classification, `RSI14_zone`; direction, `RSI14_trend`; boolean, `CAPTAIN_CONF`; event,
   `EMA_CROSS`; rank, `RSI14_rank_hi`; date, `SETTLED_AT`; plus the ambient `mktBreadth_all`): the served
   `conditionOperators` and `conditionHold {maxWindow, maxAtLeast, refusal}` per header. That turns the kind and
   one-bar-history warnings into measured rules (and is measurement M2 of the 2026-10-06 plan for the hold).
3. **The refusals themselves** — the same preview carrying conditions that use each new operator, including an edge
   held `{2,2}`, an `ALL` held `{2,3}` over an edge, `increased` on `chg24h`, `crossesAbove` on `RSI14_zone`, and
   `enters` with a label outside the vocabulary: which are refused (`CONDITION_OPERATOR_UNSUPPORTED`,
   `CONDITION_HOLD_ILLEGAL`, `CONDITION_LITERAL_UNSUPPORTED`) and which read FALSE.
4. **`list_strategy_vocabulary`** at 108 — the v103 `conditionGrammar` (group depth: the vendor says ≤ 2, omega does
   not check it), the served budgets, and the per-column hold domain.
5. **`levelInteraction`** — `get_strategy_column_contract` over the levels the README names (bands, `VWAP`, moving
   averages, `ST_LINE`, `PSAR`, Ichimoku lines, `PDH`/`PDL`/`PDO`, floor pivots, `PRIOR_TPO_*`) for its header
   (`{code}_lvl`, `_b<buffer>`) and vocabulary — needed before S6 or any touch/reject thesis can use it.

None of these needs a write: `preview_strategy_report` renders "without saving or mutating strategy state".

## What battlegrid-manager must follow (not done here)

1. **`manager/authoring/preflight.py` `pin_drift`** — on re-pinning to this OMEGA, `script.stored_enums()["metrics"]`
   holds all 171 names, so `_moved("metrics", liveNotStored, …)` returns nothing: the 15 `VOCABULARY_MOVED` warnings
   at path `metrics.liveNotStored` disappear. Nothing else in `pin_drift` changes (`sectionKeys` identical,
   `storedNotLive` empty). To keep the unmeasured names visible, pass `script.stored_unmeasured()` as `compare`'s third
   argument (guard with `hasattr` for older pins) and emit one `info` check per `metrics.storedUnmeasured`.
2. **Its tests that pin the old answer** — `tests/authoring/test_preflight.py`
   `test_the_pin_is_behind_on_the_fifteen_metrics_104_0_0_and_on_nothing_else` (expects the 15 warnings) and
   `test_the_fifteen_metrics_are_served_since_104_0_0_and_not_before` (asserts `len(stored) == 156` and no overlap)
   will fail against this pin; both describe the drift this slice closes.
3. **`_omega_checks`** — `condition_findings()` may now carry warnings on prior-bar clauses (quoted descriptions, never
   errors), and `validate_report` may carry `METRIC_UNMEASURED` (an error) for a hand-written column over one of the
   15. A generated plan carries neither.
4. **`schema_checks`** is unchanged: it already validates the CONDITIONS axis with `jsonschema`, so the new operators
   pass it.
