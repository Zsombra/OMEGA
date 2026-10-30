# OMEGA at contract 144 (v136 - v142.3): re-extraction record

**Status: DONE 2026-10-30.** Served contract **144.0.0** (build `beb6b930`, acknowledged by the battlegrid-manager watch
2026-10-29T16:26Z). The vendor changelog read is battlegrid-mcp README "Contract history" v136, v136.1, v137, v137.1-5,
v138, v139, v140, v142.3 and v143 (v141, v142, v142.1-2 and 144.0.0 itself are not documented there). Baseline main
(v0.9.0, e1b4c39): 1661 passed. This branch: 1731 passed.

## Why

OMEGA v0.9.0 authored against the 135.2.0 capture of 2026-10-26. Between it and 144.0.0:

- **v136** gave a `rank` column a category `scope` that lands in the header (`RSI14_rank_hi_crypto`), retired
  `get_top_ranked_coins` and gave the ranked `coinSelection` a `rankBy`.
- **v136.1** added six spot metrics and the `spotFlow` study; **v139** and **v140** then retired the two Bybit ones.
- **v137** retired `STOCH_RSI14` into `STOCH_RSI_K` / `STOCH_RSI_D`, added the `points` unit, and made a spread over a
  comparable unit a difference. **v137.2** added 66 metrics (the anchored VWAP family with +-1/2/3 sigma bands, the week
  and month profiles, `PWH`/`PWL`/`PMH`/`PML`) and named the metric vocabulary once per schema (`$defs/metricKey`).
  **v137.3** added the three USD-notional volumes.
- **v138** retired `BB_WIDTH` for `BB_WIDTH_PCT`, refused OBV's level reads behind an unchanged schema, added
  `CUM_VOLUME_DELTA` and `provenance` on every catalog metric.
- **v142.3** added the `relativeTo` transform, the `instrument` column knob and the `priceRatio` unit.
- **v143** is Radar-only (a deployment is one team's watch on one coin); nothing OMEGA models.

v0.9.0 accepted `STOCH_RSI14` and `BB_WIDTH`, knew none of the 78 metrics, no `relativeTo`, no `instrument`, no
`scope`, and its stored write schema was the 135.2.0 capture.

## Route

Every platform call read-only, over the `mcporter` CLI (`battlegrid-anbu`, account ANBUJEFF). No stage, commit, bind or
trade. battlegrid-manager was read (one fixture file), never written.

1. **Write surface**: the 144.0.0 draft-tool family copied from battlegrid-manager's stored
   `tests/fixtures/2026-10-29-surface-144.0.0/manager_schemas_144.0.0.json` (the surface its watch read
   2026-10-29T15:29Z, sha256 `e879fcfb...`) to `data/contract/stage_strategy_draft/schema_20261029T152942Z.json`; the
   manifest names it, the 135.2.0 capture nested under `supersedes`; the condition vocabulary re-derived: **302** column
   metrics (now read at `$defs/metricKey`), **24** transform ids, `instrument` and `scope` among the column fields.
2. `get_metric_construction_hints` x 302 (0 failed), then `scripts/refresh_metric_contracts.py` (EXTRACTION_STAMP
   20261030, archive 20261026): **retired `BB_WIDTH`, `STOCH_RSI14`; 78 added**; `relativeTo` added to the catalogue;
   `provenance` and `rankScope` recorded on every metric.
3. `list_strategy_categories` + `list_strategy_vocabulary` x 10 (`data/contract/vocabulary/20261030T0345Z/`); platform
   templates, categories and the shared blocks refreshed from them.
4. `scripts/build_corpus.py` (302/302 reconcile; 2,429 / 6,946 cells legal), then the render-coverage sweep
   (`SWEEP_DATE=2026-10-30`, `data/audit/coverage_sweep_2026-10-30.json`: structural scope, 2,631 shapes, 3,639 headers, 0 refusals, 0
   mispredicted; a second pass `-expanded.json` for the 35 non-spread expansions).
5. Targeted renders (`preview_strategy_report`, read-only, SOL 1h): `relativeTo` on a comparable unit and a price, with
   and without an instrument, at each timeframe reference, in every instrument spelling, as a chain inner; `scope` on
   an exchange-wide and a report-scoped rank; the v137 / v138 replacements; OBV's refused level reads; the retired keys
   (`data/audit/relative_to_probe_144_2026-10-30.json`, `_144b_`, `_144c_`); every classifyZone header's served
   vocabulary (`data/contract/columns/zone_vocabulary_144_2026-10-30.json`).

## What moved (measured)

- **Metrics** 226 -> **302** (`data/contract/metrics/_moves_144.json`): retired `STOCH_RSI14` (v137) and `BB_WIDTH`
  (v138), each refused live; added 4 at v136.1, 2 at v137, 66 at v137.2, 3 at v137.3, 1 at v138, and `ROC9` and
  `SQZ_MOM`, which no changelog entry names. `SPOT_CLOSE_BYB` and `BUY_PRES_BYB` were added (v136.1) and retired
  (v140, v139) between the two captures and were never in a corpus. Timeless 120 -> 133 (16 v137.2 period levels in; `SPOT_CLOSE_CB`,
  `SPOT_CLOSE_BN`, `SPOT_CVD` out - v136.1 "spot reads are per bar", served `timeframeMode` candle).
- **`relativeTo`** (v142.3): header `<token>_<INSTRUMENT>_rel`, the timeframe and `_dev` infixes inside the token, a
  chain outer after it: `RSI14_ETH_rel`, `close_BTC_rel` (BTC when omitted), `RSI14_ltf_ETH_rel`, `RSI14_4h_ETH_rel`,
  `close_dev_ETH_rel`, `close_htf_ETH_rel`, `close_BTC_rel_z20`, `close_ETH_rel_t3..close_ETH_rel_trend`,
  `close_ETH_rel_er`, `close_ETH_rel_mean12`. The instrument prints in the roster's spelling: `eth` -> `ETH`, `kPEPE`
  and `kpepe` -> `PEPE`, `xyz:BRENTOIL` -> `BRENTOIL`, `AAPL` -> `AAPL`. Units: `points` on a comparable base
  (SOL RSI14 - ETH RSI14 = 7.0 pts), `priceRatio` on a price (SOL / BTC). Refused: `inputs`, `window`, `rank` as the
  outer, `instrument` on any other transform, an unknown symbol (`REPORT_COLUMN_INSTRUMENT_UNKNOWN`).
- **`scope`** (v136): `RSI14_rank_hi_crypto`, `RSI14_rank_lo` for `all`, `EMA5_EMA13_spread_rank_hi_l1` on a chained
  rank. Refused off rank, on a report-scoped rank (`CROWD_UPBIAS`: "ranks this report's coins, so it takes no category
  scope"), and `bars` on rank.
- **v137 spreads**: `DIplus14_DIminus14_spread` renders in `points`.
- **OBV** (v138): `value` and `rank` refused ("reads only its changes"); `zscore` renders `OBV_z20`; the served hint lists exactly `trajectory`, `efficiency`, `zscore`, `stddev`,
  `linregSlope`, `pctl` (the README's "behind unchanged schemas" is the stage schema; the hint moved).
- **A knob the transform does not declare is refused** (`[column-grammar] transform 'value' does not accept
  params.window`): `window` on value and rank, `offset` on trajectory and relativeTo, `bars` on rank - where the
  platform read past them before (OMEGA warned `*_IGNORED`). `bars` is accepted on value (`RSI14_dev`),
  classifyZone and relativeTo.
- **Platform templates** 24 -> **24**: `venue-dislocation` serves six columns (its `CLOSE x spread(SPOT_CLOSE_BYB)`
  column gone, v140); `includeBollingerBands` lost its `BB_WIDTH` column.
- **Shapes** 2,604 -> **5,845** structural (2,429 atoms), 30,761 -> **113,934** operand-expanded (the 78 added metrics as
  spread operands). Live coverage: every structural mechanism (4,252 / 4,252) and every non-spread expansion rendered;
  the 80,806 spread operand pairs the additions opened are left unrendered by decision (five hours of renders that re-mint
  `<code>_<operandCode>_spread[_<outer>]`, a pattern rendered thousands of times) - the coverage test pins the measured
  state (33,108 rendered, 80,806 never, all spread).
- **The catalogue's authoring text** moved on `rank` (the `scope` parameter) and `spread` (a comparable unit is a
  difference); every other transform's authoring block is invariant across the 302 metrics.
- **Budgets**: unchanged (`columnLookback` 64, `strategyConditions` 32, `conditionClauses` 32, `marketReadChars` 4000).

## What OMEGA changed

- `omega.types`: `Column.instrument` (the schema's shape: 1-20 chars, `^[A-Za-z0-9][A-Za-z0-9._:-]*$`) and
  `Column.scope` (the schema's nine-value enum).
- `omega.contract`: `Metric.rank_scope` and `Metric.provenance`; `retired_metrics` is read from every
  `metrics/_moves_*.json`, each entry naming its record.
- `omega.validate`: `INSTRUMENT_UNDECLARED` (instrument off relativeTo), `SCOPE_UNDECLARED` (scope off a rank stage),
  `OPERAND_REFUSED` (inputs on relativeTo), `REPORT_COLUMN_PAIR_UNSUPPORTED` for a scope on a rank whose served
  `rankScope` is not `exchangeWide`; `METRIC_RETIRED` names the record and the README entry; `WINDOW_IGNORED` /
  `OFFSET_IGNORED` warnings become `WINDOW_REFUSED` / `OFFSET_REFUSED` errors, `BARS_REFUSED` on rank, `BARS_IGNORED`
  no longer fires on the transforms measured to accept it.
- `omega.fanout`: `relativeTo` headers (`instrument_token`: the measured roster spellings), `scope_token` on an atom
  and a chained rank; the zone vocabulary read from the 144 measurement.
- `scripts/refresh_metric_contracts.py`: records `provenance` and `rankScope`.
- `scripts/sweep_render_coverage.py`: `SWEEP_SCOPE` (`structural` / `nonspread` / `all`); `scripts/render_coverage.py`
  reads the two 2026-10-30 sweep caches and the probe headers (`data/contract/columns/_probe_144_2026-10-30.json`).
- `omega.generate`: the retired history path (`plan_pre_108`) reads a rung-map metric the platform has since retired
  at what it says to author instead (BB_WIDTH -> BB_WIDTH_PCT), as the platform migrated stored strategies.
- `data/audit/timeless_column_timeframe.json`: `affectedMetrics` regenerated (133).
- `scripts/build_docs.py`: `relativeTo` in the transform order.
- `data/derived/indicator_families.json`: `relative-strength` (the coin-vs-coin ratio / difference line with its
  z-score and trajectory) is buildable from rendered columns; `stoch-rsi` re-specified on `STOCH_RSI_K` / `STOCH_RSI_D`.
- `data/audit/transform_formula_audit.json`: `relativeTo` recorded `notVerified` (served formula, headers, units and
  refusals measured; the other coin's bars are not in the render).
- `docs/03-column-compilation.md`: the two knobs and the two header patterns.
- Tests: `tests/test_v144.py`; the pins moved in test_condition_vocabulary_108, test_write_surface,
  test_report_surface_108, test_compare_vocabulary, test_membership, test_v123_header_codes (a retired key's code
  move is skipped), test_against_compiler, test_metric_vocabulary_108, test_space, test_render_coverage,
  test_spread_chain_operand, test_timeless_timeframe, test_v103_transform_entry.

## Not done

- `relativeTo`'s values are not recomputed from two tapes (`notVerified`); the ratio's `priceRatio` significant-digit
  rendering is recorded, not modelled.
- An unknown `instrument` is refused by the platform only (`REPORT_COLUMN_INSTRUMENT_UNKNOWN`): OMEGA holds no coin
  roster, so `omega.validate` passes any symbol of the schema's shape. A roster spelling outside the four measured
  (`ETH`, `PEPE` from `kPEPE`, `BRENTOIL` from `xyz:BRENTOIL`, `AAPL`) is a header OMEGA cannot predict offline.
- v136's `rankBy` on a ranked `coinSelection` and v143's `teamId` are compile-time / Radar inputs OMEGA does not model;
  v137.4 / v137.5 / v138 served-value changes (flat windows, Keltner defaults, Stochastic (14, 1, 3)) move no schema.
- The 80,806 operand-expanded spread shapes are unrendered (above).
- `docs/01` / `docs/02` are not regenerated (`build_docs.py` has been stale since September; a separate change).
- The manager still pins v0.9.0 (v0.8.3 per its own record); bumping it is the manager's change, not this one.

## What a consumer must change (battlegrid-manager)

Re-pin to the tag that carries this record (v0.10.0). v0.9.0 accepts `STOCH_RSI14` and `BB_WIDTH`, knows none of the
78 metrics, refuses `relativeTo`, `instrument` and `scope` as unknown, and its stored write schema is the 135.2.0
capture, so its pin-drift check reads the 144.0.0 surface as moved. A manager preset naming `STOCH_RSI14` or `BB_WIDTH`
must move to `STOCH_RSI_K` / `BB_WIDTH_PCT` (the platform migrated stored strategies itself, README v138).
