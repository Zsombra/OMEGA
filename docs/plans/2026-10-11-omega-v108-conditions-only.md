# OMEGA on a conditions-only platform (contract 108) — re-extraction record

**Status: DONE 2026-10-11** on branch `feat/v108-conditions-only` (offline: no platform call, no push, no merge).
Baseline main `dd67593` / tag v0.3.2: 1231 passed. The pattern is the last re-extraction,
[`2026-10-06-omega-draft-lifecycle-re-extraction.md`](2026-10-06-omega-draft-lifecycle-re-extraction.md).

## Sources (all on disk; nothing typed from memory)

- **The changelog.** README "Contract history — v108 (conditions are the only entry gate; signal rules are
  removed)", in the vendored pack `.agents/skills/battlegrid/README.md` (refreshed to playbattlegrid/battlegrid-mcp
  main `b4020743`, package 31.2.94, `skills-lock.json` hash recomputed with the `skills` CLI's own
  `computeSkillFolderHash`) and saved by battlegrid-manager beside its fixture. The pack's skills are exported at
  contract **105.0.0** (`skills/EXPORT.json`): the strategy-authoring and strategy-examples skills still describe
  `SIGNAL_RULES`, `SETUP_GATES` and the gate math. The README changelog is the only vendor text at 108.
- **The schemas.** battlegrid-manager `tests/fixtures/2026-10-11-surface-108.0.0/manager_schemas_108.0.0.json`
  (manager commit `d7889bb`; contract 108.0.0, build `1076c4e7…`, observed 2026-10-10T21:53:26Z), copied for six
  tools (`stage_strategy_draft`, `get_strategy_draft`, `commit_strategy_draft`, `list_strategy_drafts`,
  `preview_strategy_report`, `get_strategy`; input **and** output schemas) to
  `data/contract/stage_strategy_draft/schema_20261010T215326Z.json`, with the fixture's sha256. The manifest's
  `writeSurface` names it; the 91.0.0 capture is its `supersedes`. `discard_strategy_draft` is not in the
  manager's stored subset. `manager_schemas_acked_106.0.0.json` was the diff base.

## What moved 106 → 108 on the five tools (schema diff)

- `stage_strategy_draft` input: `axes.SIGNAL_RULES` and `axes.SETUP_GATES` deleted; `TRADE_LEVEL_POLICY` gains
  `minAtrPct`, and `required` becomes `[minAtrPct, minStopLossAtrMultiple, maxStopLossAtrMultiple,
  minRiskRewardRatio]`; the axes description loses the SIGNAL_RULES merge exception. Output: `stagedAxes` and
  `axesMeta` lose the two axes; `diagnostics.mismatches` deleted; `diagnostics.warnings[].code` enum becomes
  `[NO_ENTRY_CONDITION]` (was `NO_SIGNAL_ACTIVE`, `MODULE_WEIGHTED_OUTSIDE_REPORT`,
  `MODULE_IN_REPORT_SCORES_NOTHING`); `REPAIR_REQUIRED` leaves the error codes; `inertRequiredSignalIds` leaves
  error details.
- `get_strategy_draft` output: the same diagnostics change; `diff[].axis` and the draft's `content` / `axesMeta`
  lose the two axes.
- `commit_strategy_draft` / `get_strategy` output: `strategy` loses `signalRules`, `signalRuleTally`,
  `minAggregateScore`, `minRequiredCount`; commit loses `ruleChanges`. `minAtrPct` stays on the strategy.
- `preview_strategy_report`: input and output identical at 106 and 108.

Between 91 and 106 (not this contract, and not followed here — see "Open"): the REPORT column `metric` enum
grew (`CANDLE_DOJI`, `GAP`, `HL2`, …), `transformId` / `chainedTransformId` became enums, a column gained
`buffer`, the 64-item and offset/window maxima went, and the clause arms gained `crossesAbove`/`crossesBelow`,
`enters`/`exits` and a fifth `increased`/`decreased` arm (v98).

## The mapping

| v91 (OMEGA v0.3.2) | at 108 |
|---|---|
| ten axes | eight: `IDENTITY, TIMEFRAME_PROFILE, REPORT, MARKET_READ, CONDITIONS, ENTRY, TRADE_LEVEL_POLICY, POSITION_MANAGEMENT` (`omega.generate.AXES`; the ten are `AXES_91`) |
| `SETUP_GATES {minAggregateScore: thesis.gate, minRequiredCount, minAtrPct}` | gone; `minAtrPct` is the first of four required `TRADE_LEVEL_POLICY` dials (`execution.TRADE_LEVEL_DIALS`) |
| `SIGNAL_RULES {rules: 84 rows}` | gone (`StrategyPlan._rules()` retired) |
| `axes_update`: `SETUP_GATES` always staged | no gate axis: a dial axis only when the thesis names one of its dials; a pre-108 `current` is accepted, its `SETUP_GATES`/`SIGNAL_RULES` ignored, `minAtrPct` taken from the old `SETUP_GATES` when `TRADE_LEVEL_POLICY` lacks it (tested on the real read `current_7534b2ee_…`) |
| the gate: `minAggregateScore` over the scorecard | the conditions: an entry condition that is `required` or carries a verdict; none → `NO_ENTRY_CONDITION` (draft warning; **OMEGA error**: `conditions.validate_entry_gate`, `authoring.validate_thesis`) |
| `Thesis.gate`, `Thesis.required`, `Thesis.show_scoring_data` | retired (removed, `TypeError` if passed) |
| `Thesis.weights` | kept: keys choose the report's modules and the checklist's readings; the tier has no platform meaning |
| preflight fingerprint: ten axes + 84 signalIds | eight axes; no signal check |
| `compare_vocabulary`: metrics, signals, sectionKeys | metrics, sectionKeys |
| `preview_request()` | unchanged |

**Presets.** All five already carried two verdict carriers (`{P}_UP` / `{P}_DOWN`): MR, TC, SB, SA, SR. Nothing
changed in any thesis's market logic. Each lost exactly its 2026-10-10 scoring-data columns (docs/08 table):
mean-reversion 17→12 columns, trend-continuation 14→8, squeeze-breakout 12→10, flow-divergence 11→10,
structure-reversal 13→10; every preset now reads one distinct timeframe.

## Retired (history, importable, dated, off the generation path)

`StrategyPlan._rules`, `.rules`, `.simulate(score, gate=)`, `.membership()`, `.allocation_findings()` (returns
`[]`; the manager calls it); `generate.signal_rules`, `plan_pre_108`, `_scoring_data_columns`,
`plan_for_signals`, `AXES_91`, `RETIRED_AXES`; `execution.SETUP_GATE_DIALS`; `preflight.AXES_91`;
`omega.membership` (module map, rung map `RUNG_REL` over `data/derived/signal_data_rungs_91.json`,
`scoring_gaps`, `report_data_signal_off`, `modules_scoring_nothing`, `predicted_diagnostics`); `omega.scoring`,
`omega.aggregate`; `authoring.vocabulary()`'s per-module `signals` list; `THESIS_UNFEEDABLE_REQUIRED`; the
manifest's `retired` gains `data/contract/signals/`. `scripts/build_pvm_strategy.py` is a compile-era body and
was already history. The TPO suite's `GATE_MIRROR` is retired; each member's design record now lists its
`entryGate`.

## What battlegrid-manager must change to follow (not done here)

1. `manager/authoring/pipeline.py` `THESIS_KEYS` → `("name", "tagline", "description", "anchor", "weights",
   "stance", "context", "coin_selection", "execution", "exits")` (drop `gate`, `required`,
   `show_scoring_data`); stored theses carrying those keys must lose them (`Thesis(**d)` raises).
2. `_omega_checks`: the `ALLOCATION_FINDING` line is now always empty (keep or drop it); the
   `NO_ENTRY_CONDITION` finding arrives twice — as `CONDITION_FINDING` from `condition_findings()` and as code
   `NO_ENTRY_CONDITION` from `validate_thesis`.
3. `manager/authoring/preflight.py`: `param_checks` (the `SIGNAL_RULES.rules` params against `paramSchemaJson`)
   and the `defaultParams` half of `pin_drift` have nothing to check — no axis carries a rule and no signal
   definition is served; `RULES_UNREADABLE` would fire on every 108 request. `pin_drift`'s vocabulary half
   now gets two kinds (`metrics`, `sectionKeys`) from `compare_vocabulary.compare`.
4. The definitions capture (`signal_definitions`, from the removed `get_strategy_signal_definition`) cannot be
   refreshed; `freshness_checks` must stop requiring it.
5. Any `current` it hands `axes_update` may be pre-108 — accepted as is.

## Measured 2026-10-15 at contract 110.8.0 (the user's yes, A7/A8; manager actions 86 and two executor stages)

The probe: OMEGA v0.8.0's `trend-continuation` preset renamed "OMEGA-TEST: 110.8 stage probe", staged as a CREATE
draft (`87dac9ab-e86d-4304-9845-74a4e14c49de`), **never committed, bound to nothing**.

- **An eight-axis stage draws no errors and no `NO_ENTRY_CONDITION`:** version 1, `diagnostics {errors: [], warnings: []}`
  (and the same on the draft read after it). MEASURED.
- **A strategy whose only verdict carriers are `NEITHER` is counted as gated:** the CONDITIONS axis restaged with
  `O1_UP` and `O1_DOWN` both `NEITHER` - version 2, `{errors: [], warnings: []}`, no `NO_ENTRY_CONDITION`. MEASURED.
  Whether it can ever enter is NOT measured - that needs a live evaluation on a bound agent.
- **A refused stage:** the REPORT axis with two `MACD_HIST` columns written as the retired `MACD` - refused at schema
  validation (`MCP -32602`, `invalid_enum_value`, the served enum listed), the replacement NOT named; the draft stayed at
  version 2. omega's own `METRIC_RETIRED` is what names `MACD_HIST`. MEASURED.
- **`minAtrPct` across the 106 -> 108 migration is kept:** "Trend Continuation" (`7534b2ee`, revision 3) reads
  `minAtrPct = 0.5` (first seen moved into TRADE_LEVEL_POLICY on 2026-10-11, `battlegrid-manager docs/phase-4/4a-first-live.md:71`).
  MEASURED.
- **How the gate treats a required condition that reads UNRESOLVED:** still NOT measured - a stage cannot show it; it
  needs a bound agent's qualification read.

## Still unmeasured (each a platform call, so each is the user's word)

- That a stage of the eight axes draws no `errors` and no `NO_ENTRY_CONDITION` warning (the 108 analogue of M1).
- Whether a strategy whose only verdict carriers are `NEITHER` is counted as gated by the platform (the wording
  says yes) and whether it can ever enter (a resolved NEITHER admits no side) — TPO S1, S7.
- How the gate treats a required condition that reads UNRESOLVED.
- Whether the platform re-seeds or keeps a strategy's `minAtrPct` across the 106→108 migration (the changelog
  says only where it is staged).

## Open

- The clause operators added at v98 (`crossesAbove`, `crossesBelow`, `enters`, `exits`, `increased`,
  `decreased`) and the metrics/transforms added between 91 and 106 are not modelled by `omega.conditions` /
  the 61.2.0 metric extraction. Nothing generated uses them; a re-extraction is its own slice.
  **Closed for the conditions on 2026-10-11** by
  [`2026-10-11-omega-condition-vocabulary-108.md`](2026-10-11-omega-condition-vocabulary-108.md): the six operators are
  modelled and validated against the schema; the 15 metrics are known by name and refused until measured.
