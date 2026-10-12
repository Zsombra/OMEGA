# The REPORT surface at contract 108 — plan and record

**Status: IN PROGRESS 2026-10-12** on branch `feat/report-surface-108` (offline: no platform call of any kind). Baseline
main `b1bd433` / tag v0.4.1: 1357 passed. Follows
[`2026-10-11-omega-condition-vocabulary-108.md`](2026-10-11-omega-condition-vocabulary-108.md), whose "Gaps recorded
and not closed" this works through — every item below has a source on disk.

## Sources (all on disk)

- The saved 108 write schema, `data/contract/stage_strategy_draft/schema_20261010T215326Z.json` (contract 108.0.0,
  build `1076c4e7`): the REPORT axis's custom-section arm and column arm.
- The `get_strategy_column_contract` input schema at **104.1.0**, copied today from battlegrid-manager
  `tests/fixtures/2026-10-08-surface-104.1.0/tool_definitions.json` (with that file's sha256) to
  `data/contract/get_strategy_column_contract/schema_104.1.0.json`. The manager's 108 fixture stores only the six
  draft tools, so 104.1.0 is the newest capture of this tool; README v104–v108 name no change to it.
- The vendored README "Contract history" (`.agents/skills/battlegrid/README.md`, pack 31.2.94): 48.0.0
  (`remove-section-anchor-override`), v100 (`bandTouch` retired, `levelInteraction`, `buffer`), v103 (the fixed 64
  maximums leave authoring; `sideRequired` / `operandRequired` leave the served transform entry).

## What drifted, and the fix

| # | drift | source | fix |
|---|---|---|---|
| 1 | `CustomSection.timeframe` — the section anchor override. The 108 custom-section arm has no `timeframe` and `additionalProperties: false`; 48.0.0 removed it ("no section can be overridden") and `REPORT_COLUMN_SECTION_TIMEFRAME_UNSUPPORTED` left the vocabulary | schema + README 48.0.0 | `validate_section` errs `SECTION_TIMEFRAME_RETIRED`; the column-level `REPORT_COLUMN_SECTION_TIMEFRAME_UNSUPPORTED` and section-level `SECTION_MIXES_INERT_METRICS` retire with it. The field stays on the model so older records still load |
| 2 | `bandTouch` — in the 61.2.0 corpus on 62 metrics, not in the 108 `transformId` enum | schema enum; README v100 | **derived**: `Contract.retired_transforms` = corpus transforms − served enum; they leave every `Metric.transforms`, so `omega.space` shrinks and `validate_column` errs `TRANSFORM_RETIRED` naming the replacement |
| 3 | `levelInteraction` — served, never extracted | schema enum; README v100 | **derived**: `Contract.unmeasured_transforms` = served − corpus − platform-privileged; `validate_column` errs `TRANSFORM_UNMEASURED` (as `METRIC_UNMEASURED` does for the 15 metrics) |
| 4 | `buffer` — a served column field (0–500) not on `Column` | schema; README v100 | `Column.buffer` with the schema's bounds; on any transform but `levelInteraction` it errs `BUFFER_UNDECLARED` ("refused as an undeclared parameter") |
| 5 | `le=64` on `window` / `offset`, `max_length=64` on a section's `columns` and on `Report.sections` | schema (no maximum); README v103 | dropped from the model; the served budgets (`columnLookback`, `sectionColumns`, `sections`) keep judging them in `validate_*` |
| 6 | `benchmarkTicker` free string | schema: 1–20, `^[A-Za-z0-9][A-Za-z0-9._:-]*$` | bounds and pattern on the model |
| 7 | `omega.probe.contract_request` sends `sectionTimeframe` | 104.1.0 capture: `anchorTimeframe`; README 48.0.0 | sends `anchorTimeframe` |
| 8 | the derived inventory knows the column, not the section | — | `derive` gains `reportSection` (fields, required, the `columns` bounds) and the column's integer bounds; `gaps()` gains `sectionFields` |

## Docs hygiene (from the 2026-10-12 doc sweep)

- Docs 01 / 02 are generated and still show the 54.1.0 roster (144 metrics); the corpus is 61.2.0 (156). Regenerate
  with `scripts/build_docs.py`.
- Docs 05, 10, 12, 13 describe the retired signal model with no contract-108 banner (07 and 11 have one).
- Docs 03, 04, 06 describe the section override and `bandTouch` as live.

## Not in this slice (each needs a live read: the user's word)

- `levelInteraction`'s admissible levels, header and vocabulary (`get_strategy_column_contract` per level).
- The 15 metrics (`get_metric_construction_hints`), the per-header operators and hold domain, the condition refusals,
  `list_strategy_vocabulary` at 108 — the list in the 2026-10-11 record, unchanged.
- `conditionFrameReads` (256): the vendor states one rule ("a clause held 'within 3 closes' reads four bars") but not
  how reads sum across clauses, groups and references. Encoding a sum would be inventing it.
- A re-extraction at 108 meets the v103 shape: a served transform entry no longer carries `sideRequired` /
  `operandRequired` (read `authoring.parameters.side.required` / `inputs.required`). `validate_column` reads the old
  flags from the 61.2.0 corpus; the refresh script must map them, or the checks go silent.
