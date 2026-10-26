# OMEGA at contract 135 (v134, v135, v135.1): re-extraction record

**Status: DONE 2026-10-26.** Served contract **135.2.0** (build `98d29c45`, acknowledged by the battlegrid-manager watch
2026-10-26T06:27Z). The vendor changelog read is battlegrid-mcp README "Contract history" v134, v135 and v135.1 (135.2.0
itself is not documented there). Baseline main (v0.8.3, a5634c2): 1588 passed.

## Why

OMEGA v0.8.3 authored against a write schema captured at 110.13.0 and a metric corpus extracted at 110.8.0. Between
those and 135.2.0:

- **v134** retired the Multi-Timeframe Confluence platform section (`includeMtfConfluence` refused wherever a section is
  named). OMEGA's template capture still listed it, so `omega.validate` accepted a section the platform refuses.
- **v135** re-specified `efficiency` windows (a window counts bar-to-bar changes and reads `window + 1` bars), replaced
  `rankableSpreadOperands` with `chainedOuters`, added `chainOuterParameters`, six transforms and `columnLookback` 64.
- **v135.1** added 35 metrics (bar clock, trading sessions, opening ranges, IB extensions) and 5 studies.
- **v123** (handled in v0.8.3 for its header renames only) had also added seven metrics OMEGA never extracted.
- **v115.1** (between the two captures) publishes a discriminated union as `oneOf` and an integer's bounds at
  +-9,007,199,254,740,991; v116 names shared shapes under `$defs`.

## Route

Every platform call read-only, over the `mcporter` CLI (`battlegrid-anbu`, account ANBUJEFF). No stage, commit, bind or
trade.

1. **Write surface**: the 135.2.0 draft-tool family copied from battlegrid-manager `system_state.manager_schemas`
   (read-only SELECT) to `data/contract/stage_strategy_draft/schema_20261026T062718Z.json`; the manifest names it, the
   110.13.0 capture nested under `supersedes`; the condition vocabulary re-derived: **226** column metrics, **23**
   transform ids.
2. `get_metric_construction_hints` x 226 (0 failed), then `scripts/refresh_metric_contracts.py` (EXTRACTION_STAMP
   20261026, archive 20261015): **retired none, 43 added**; six transforms added to the catalogue.
3. `list_strategy_categories` + `list_strategy_vocabulary` x 10 (`data/contract/vocabulary/20261026T0708Z/`); platform
   templates, categories and the shared blocks refreshed from them.
4. `scripts/build_corpus.py` (226/226 reconcile; 1,449 / 4,972 cells legal), then the render-coverage sweep
   (`SWEEP_DATE=2026-10-26`, `data/audit/coverage_sweep_2026-10-26.json`).
5. Targeted renders (`preview_strategy_report`, read-only): the six statistics on an atom and as a chain outer, the
   MTF replacement columns (`data/audit/statistics_probe_135_2026-10-26.json`); every classifyZone header's served
   vocabulary and a condition preview over the formerly disjoint zone headers
   (`data/contract/columns/zone_vocabulary_135_2026-10-26.json`).

## What moved (measured)

- **Metrics** 183 -> **226** (`data/contract/metrics/_moves_135.json`): seven at v123 (`CLOSE_LOCATION`, `CMF20`,
  `EMA8`, `PRIOR_SWING_FRACTAL_HIGH/LOW`, `SWING_FRACTAL_HIGH/LOW_BARS_AGO`), `PERP_SPOT_GAP` at v134, 35 at v135.1.
  Timeless 87 -> 120.
- **Transforms** + `zscore`, `stddev`, `linregSlope`, `pctl`, `rollingMin`, `rollingMax`, on an atom and as chain
  outers. Headers measured: `<base>_z|sd|slope|pctl|min|max<window>` (default window 20): `RSI14_z20`,
  `dist_EMA20_slope10`, `EMA5_EMA13_spread_max10`.
- **Chains**: every distance / spread atom chains into nine series outers (efficiency is back over distance and spread),
  21 into rank too. `chainedOuters.<outer>` serves `operands` and `windowMaximum` (63 for efficiency and pctl, 64 for the
  rest). RVOL x spread serves no chain successors any more (its operands have no per-bar value).
- **Shapes** 981 -> **2,604** structural (1,449 atoms), 10,257 -> **30,761** operand-expanded.
- **Budgets** (served): `columnLookback` 32 -> 64, `strategyConditions` 16 -> 32, `conditionClauses` 16 -> 32,
  `marketReadChars` 4000. Per-metric `value.offset` maximum 31 -> 63 on candle metrics.
- **Platform templates** 25 -> **24**: `includeMtfConfluence` gone; `includeSubTimeframe`'s CLOSE efficiency window
  5 -> 4 (the server's own w - 1 migration, the same bars); `includePerpSpotFlow` + `PERP_SPOT_GAP`.
- **The MTF replacements render**: `MA_ALIGN x value`, `RSI14 x classifyZone`, `ADX x classifyZone` at `{rel: lower}`
  -> `MAalign_ltf`, `RSI14_ltf_zone`, `ADX14_ltf_zone`.
- **The 2026-08-24 zone trap is gone**: `ADX14_zone` serves weak / developing / trending / extreme and `MFI14_zone`
  overbought / oversold / bullish / bearish / neutral; a preview read `ADX14_zone is trending` TRUE on 9 of 12 coins and
  every emitted label sat inside the served vocabulary.

## What OMEGA changed

- `omega.preflight` / `omega.condition_vocabulary`: a `oneOf` union is walked like `anyOf` (`union_key`); `$defs` is a
  modelled container.
- `omega.validate`: the six statistics are series transforms and series chains; a chain's operands and window maximum
  are read from `chainedOuters` (`chained_operands`, `chained_window_maximum`), `rankableSpreadOperands` only on a
  pre-135 corpus.
- `omega.space`: enumerates with the same served operand lists.
- `omega.fanout`: the statistics' headers; a classifyZone header's vocabulary per metric from the 135 measurement.
- `omega.conditions`: the disjoint-zone refusal no longer applies to a header the 135 measurement covers.
- `scripts/refresh_metric_contracts.py`: records `chainedOuters`, `chainOuterParameters`
  (`data/contract/transforms/_chain_outer_parameters.json`) and a series window's per-metric own-length sentence
  (`windowOwnLength`).
- `data/derived/indicator_families.json`: five operator-absent families (zscore, vol-of-vol, ls-slope, ts-percentile,
  rolling-minmax) are buildable; bollinger-derived, sharpe and vol-cones stay blocked on the composition still missing.
- `examples/build_section.py`: the CLOSE efficiency window 6 -> 5 (the same 6 bars under v135).
- The generator (`omega.generate`) never emitted MTF, efficiency or a zone clause on ADX / MFI: no preset changes.

## Not done

- The six statistics' formulas are recorded `notVerified` in `data/audit/transform_formula_audit.json` (served formula,
  header and kind measured; values not recomputed from candles).
- v135.1's roll rule (a period level read across its roll is `null`) is a served-value change behind an unchanged
  schema: OMEGA models no value, so nothing changes offline; a required condition over a spread / levelInteraction on a
  UTC-day or session level fails closed on the roll bar.

## What a consumer must change (battlegrid-manager)

Re-pin to the tag that carries this record. v0.8.3 accepts `includeMtfConfluence` as a platform section, predicts
`overbought/oversold/neutral` for `ADX14_zone`, knows none of the 43 metrics or six transforms, and its stored write
schema is the 110.13.0 capture, so its pin-drift check reads the 135.2.0 surface as moved.
