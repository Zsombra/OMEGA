# OMEGA v0.12.0 at contract 148.1.0: the 146.1 - 146.14 authoring widening, re-extracted

**Status: STOPPED 2026-11-05T16:32Z - the served contract MOVED to 149.0.0 (build `5ec52a81`, GET /mcp/version 16:31:50Z) at the end of a 502 outage (~14:43Z - 16:31Z), with step 3 at 383 / 532 hints. Everything measured here is at 148.1.0 and the hint set is incomplete, so nothing from step 3 on was written under data/; steps 3 (rest), 4, 5, 6 and the v0.12.0 version bump are NOT done (see "Resumed 2026-11-05 13:36Z" below). The 149.0.0 drift is unreviewed. Earlier: BLOCKED ~10:18Z - 13:36Z on the lost mcporter OAuth credential (re-authorized by the user 13:36:07Z).** Plan as written below. Served contract
**148.1.0** (build `d02121ec`, `GET /mcp/version` at 2026-11-05T09:18:34Z). Pinned corpus: OMEGA v0.11.0 (main
`dc06373`) at 146.0.1, 326 metrics measured. Baseline of this branch (`feat/omega-v0.12`, cut from `dc06373`):
`python -m pytest -q` **1800 passed** (re-run 2026-11-05, 132 s). Vendor changelog: battlegrid-mcp README "Contract
history" v146.1 - v146.12, v146.13, v146.14 and v147 - v147.2 (fetched 2026-11-05; byte-identical to the copy the
manager session read the same day). 148.x has no README entry.

## Why

v0.11.0 authors against the 146.0.0 stage capture. Since then the platform:

- **v146.5 / .8 / .10** added TradingView's six Pivot Points Standard types (Traditional R4/R5/S4/S5, Fibonacci,
  Classic, Camarilla, Woodie, DM) on five periods: the previous UTC day (34 keys), ISO week, UTC month, UTC quarter and
  UTC year (41 keys each), studies `weeklyPivots`, `monthlyPivots`, `quarterlyPivots`, `yearlyPivots`; the existing
  level set `Pivots` is renamed `Traditional`.
- **v146.11** added LuxAlgo Smart Money Concepts market structure (study `marketStructure`): `INTERNAL_` /
  `SWING_STRUCTURE_EVENT`, `_TREND`, `_LEVEL`, and `EQH` / `EQL`; **v146.12** narrowed the two TREND vocabularies to
  `bullish` / `bearish` and `swingLength` to 100; **v146.13 / v146.14** moved their served values (LuxAlgo `leg()`
  alternation, then the after-bars-only pivot) and the `equalBars` depth maximum (467 -> 935 at the shipped cap 64).
- **v146.1** raised the readable history to 1,000 bars per timeframe (hold domain `maxWindow` 195 -> 985 on
  `RSI14 x value`); **v146.4** `conditionFrameReads` 256 -> 2,048; **v146.7** an `aggregate` over a short series
  reads `null`, `aggregate`'s window maximum widens to the depth maximum (936), every bounded window serves `bound`
  (`lookback` | `depth`), and `REPORT_COLUMN_DEPTH_EXCEEDED` is a new refusal.
- **v146.6** `rollingMax` / `rollingMin` take an `offset` and chain into `distance` (`high_o1_max55`); `distance`
  joins the chain-outer vocabulary with `chainedOuters[outer].offsetMinimum`.
- **v146.7** the `ema` transform (`ta.ema`, header `_ema{n}`, window unit `smoothingLength`).
- **v146.9 / v146.11** six author-set column knobs: `leftBars` / `rightBars` (the seven swing metrics, header
  `_l<L>r<R>` off 2/2), `swingLength`, `confluenceFilter`, `equalBars`, `equalThreshold` (the structure metrics,
  `_s<n>`, `_cf`, `_e<m>`, `_atr<t>` off their defaults). Every served metric carries `parameters`, every transform
  entry `metricParametersAccepted`. A pair off 2/2 or a structure metric is refused under `rank`, `relativeTo`,
  `aggregate` and `ema`.
- **v147 - v148.1** moved arena / Radar / budget tools only (below, measured).

v0.11.0 refuses all 206 new keys as `UNKNOWN_METRIC` (they are neither measured nor in `_unmeasured_108.json`), refuses `ema`
and the `distance` chain outer, and its `Column` (pydantic `extra="forbid"`) cannot carry any of the six knobs. Its
`compare_vocabulary` exits 1 on the live surface.

## Measured 2026-11-05 (read-only; the delta this plan is built on)

Route as below. Calls made: one `mcporter list`, one version GET, `list_strategy_categories` x 1,
`get_metric_construction_hints` x 7 (EQH, SWING_STRUCTURE_LEVEL, PIVOT_WEEK_P, RSI14, SWING_FRACTAL_HIGH, PAR_DEV,
MKT_UP), 09:18:34 - 09:26:28Z. Raw files in the session scratchpad `v012/` (not committed; step 1 re-records them).

1. **Surface**: `mcporter list battlegrid-anbu --schema --all-parameters --json` at **2026-11-05T09:18:42Z**:
   **154 tools** (151 at 146.0.1). Every `inputSchema` identical to battlegrid-manager's stored
   `system_state.surface_tools` (148.1.0; read twice, observedAt 2026-11-04T17:51:58Z and 2026-11-05T08:26:25Z - the
   two copies are 389,664 bytes each and identical but for `observedAt`; the capture's `readFrom` names the first,
   see Executed step 1), and the ten authoring tools' input schemas
   identical to the manager fixture `tests/fixtures/2026-11-04-surface-146.14.0/surface_tools_146.14.0.json`:
   **147.0 - 148.1.0 moved no authoring input**. Tool moves since that fixture: `get_agent_radar_holdings`,
   `withdraw_agent_from_radar` (v147.1), `deploy_agent_to_radar`, `preview_agent_radar_deploy` (148, undocumented)
   added; `set_agent_per_trade_push` gone (148). None is modelled by OMEGA.
2. **`scripts/compare_vocabulary.py` against it: exit 1.** metrics live **532** / stored 326: **206 liveNotStored,
   0 storedNotLive, 0 storedUnmeasured**. sectionKeys 22 / 22, nothing moved.
   The 206 = 34 day pivots (`PIVOT_R4 R5 S4 S5`, `PIVOT_FIB_*` 4, `PIVOT_CLASSIC_*` 4, `PIVOT_CAM_*` 10,
   `PIVOT_WOODIE_*` 9, `PIVOT_DM_*` 3) + 41 x 4 period pivots (`PIVOT_{WEEK,MONTH,QUARTER,YEAR}_` P, R1-R5, S1-S5
   and the same five types) + 6 structure (`INTERNAL_` / `SWING_STRUCTURE_EVENT`, `_TREND`, `_LEVEL`) + `EQH`, `EQL`.
   No metric retired.
3. **Path diff of the six draft tools, stored 146.0.0 capture vs live** (scratchpad `v012/schema_diff.py`):
   `stage_strategy_draft` and `preview_strategy_report` input: **15 paths added, 0 removed, 0 changed**, all on the
   custom-section column: `leftBars`, `rightBars`, `swingLength`, `equalBars` (integer >= 1), `equalThreshold`
   (number >= 0), `confluenceFilter` (boolean); enum moves `$defs/metricKey` +206, `transformId` +`ema` (25 ids),
   `chainedTransformId` +`distance`, +`ema` (13 ids). Custom section fields unchanged (`benchmarkTicker`,
   `marketScope`, `notes` required). CONDITIONS axis: no schema move. `get_strategy_draft`, `list_strategy_drafts`:
   identical. Output schemas: `commit_strategy_draft` / `get_strategy` carry the same column widening;
   `preview_strategy_report` gains `ema` in `role` / `chainedRole` and a `spanFragments` description that defines
   the `_l<L>r<R>` and `_s<N>` header tokens. `stage_strategy_draft` description: one v147 wording ("never enters the
   arena"). `window`, `buffer`, `ordering`, `side` are NOT new: they were in the 144 / 146 schema already.
4. **Categories** (`list_strategy_categories` 09:22:27Z): eleven, the same ids and texts; only **`structure` 156 ->
   362** moved (sum 532). Modules: the same 22 section keys, byte-identical.
5. **Hint shapes** (samples): every metric now serves `gloss`, `subjectKinds` and `parameters`; every transform entry
   `metricParametersAccepted`. `EQH`: `value` only, boolean, `parameters` `equalBars` {default 3, min 1, max 935,
   bound depth}, `equalThreshold` {default 0.1, 0 - 0.5, step 0.1, bound range}. `SWING_STRUCTURE_LEVEL`: 12
   transforms (no relativeTo / aggregate / ema / rank), `swingLength` {default 50, 10 - 100, bound depth}.
   `PIVOT_WEEK_P`: timeless, `value distance spread levelInteraction`, no parameters. `RSI14` and
   `SWING_FRACTAL_HIGH`: `ema` added to the stored transform set; `SWING_FRACTAL_HIGH` `leftBars` / `rightBars`
   {default 2, min 1, max 933, bound depth}. PAR_DEV and MKT_UP: `ema` added.
6. **A v0.11.0 finding is wrong**: `subjectKinds` is served on every metric (README v146: "so a client can tell which
   sections a metric can be placed on"), and it names FOUR subjects: `evaluated-coin` + `benchmark` (RSI14, EQH,
   pivots), `market` (MKT_UP), `reference` (PAR_DEV). v0.11.0 inferred two subjects from refusal domains and stored
   PAR_DEV with no subject (`METRIC_NO_SUBJECT`); README v146 says a section with `benchmarkTicker` `USDT_USD` or
   `USDC_USDT` is a pair section that reads OPEN / HIGH / LOW / CLOSE / PAR_DEV. The 146 probes never set a
   `benchmarkTicker`. v0.12 records the served `subjectKinds` and measures the pair section.

## Route

As 2026-11-02: every platform call read-only over the `mcporter` CLI, server `battlegrid-anbu` (account ANBUJEFF),
through the scratch shim `<scratchpad>/npxshim/npx.cmd` (recreated 2026-11-05: drops `--no-install` / `--yes`,
refuses anything but `mcporter`, calls the cached 0.14.3
`%USERPROFILE%\AppData\Local\npm-cache\_npx\bdbf2deecdd22bc5\node_modules\.bin\mcporter.cmd`), put first on `PATH` so
the scripts' `cmd /c npx mcporter call ...` run unchanged. Tools used: `list` (surface), `list_strategy_categories`,
`list_strategy_vocabulary`, `get_metric_construction_hints`, `preview_strategy_report` (renders an unsaved draft
"without saving or mutating strategy state"). Never `stage_*`, `commit_*`, bind, deploy, fund, archive, delete.
battlegrid-manager is read only for its stored surfaces (fixtures, `system_state.surface_tools`), never written. One
worker everywhere; the live manager shares the account's ~3 req/s.

**Before every step and after the last: `GET /mcp/version`.** If the served contract moves off 148.1.0 mid-run, stop,
re-list the surface and re-run `compare_vocabulary` before continuing (three drifts landed on 2026-11-04).

## Steps

1. **Write surface at 148.1.0.** Re-list (`mcporter list battlegrid-anbu --schema --all-parameters --json`); write
   `data/contract/stage_strategy_draft/schema_<observedAt>.json` in the existing capture shape (the six draft tools'
   `description` / `inputSchema` / `outputSchema` / `annotations`, `readFrom` the live list, `sourceSha256`), and
   check it equal to the manager's `system_state.surface_tools` and
   `tests/fixtures/2026-11-04-contract-148.1.0/manager_schemas_148.1.0.json` entries. Manifest `writeSurface` names
   it (146.0.0 capture under `supersedes`). Re-derive `data/derived/condition_vocabulary_108.json`
   (`scripts/derive_condition_vocabulary.py`): **532** metrics, **25** transform ids, **13** chain outers, the six knobs
   with their schema bounds. This MUST precede step 3: `refresh_metric_contracts.py` reads its roster from this file
   (or from `vocab_live_flat.json` in the scratch dir, which the run writes from the surface to be explicit).
   `data/audit/contract_148_1_0_vocabulary_2026-11-05.json`: the compare before (206 liveNotStored) and after (0).
2. **Vocabulary.** `list_strategy_categories` + `list_strategy_vocabulary` x 11 ->
   `data/contract/vocabulary/20261105T<HHMM>Z/`; refresh `categories.json`, `vocabulary/_shared.json`,
   `templates/platform/_all.json`. Expected moves to confirm, not assume: `budgets.conditionFrameReads` 256 -> 2,048
   (v146.4; the stored 146.0.1 block still reads 256); the five new studies; the `floorPivots` level set label
   `Pivots` -> `Traditional` (v146.5); the transform catalogue +`ema`; `conditionGrammar` (v146.11: "a condition's
   level reference carries `swingLength` and `confluenceFilter`"); any platform template that now carries a pivot type
   or the 1,000-bar windows; the state vocabularies of the four TREND / EVENT keys (`bullish` / `bearish`; `BOS↑`
   `BOS↓` `CHoCH↑` `CHoCH↓`).
3. **Hints x 532** (`get_metric_construction_hints`, all metrics: the 326 stored ones moved too - `ema`, `parameters`,
   `metricParametersAccepted`, `subjectKinds`, `bound`, depth maxima), then `scripts/refresh_metric_contracts.py` with
   `EXTRACTION_STAMP=20261105 EXTRACTION_ARCHIVE=20261102 EXTRACTION_SCRATCH=<scratchpad>/v012`. Script changes first:
   - record per metric `parameters` (each knob's `defaultValue`, `minimum`, `maximum`, `step`, `bound`, `required`,
     `description`), `subjectKinds` and `gloss`; per transform entry `metricParametersAccepted`;
   - `bound` beside `maximum` in an authoring parameter is per metric (as `maximum` has been since 108.4.0): pop it
     into a `bounds` sibling of the entry's `maximums`, so the invariance check keeps measuring only the invariant
     rest. If any transform still shows more than one authoring variant the script exits before writing the catalogue
     (as designed): inspect `authoring_invariance_20261105.json`, never relax the check;
   - `chainOuterParameters` must stay invariant with `ema` / `distance` / `offsetMinimum` in it.
   Then `scripts/build_corpus.py` (532 / 532 reconcile; families 11, structure 362);
   `data/contract/metrics/_moves_148.json` (each added key with its README entry v146.5 / .8 / .10 / .11, each existing
   metric that gained `ema` or a `parameters` block, the `Traditional` rename);
   `data/contract/metrics/_subjects_148.json` **from the served `subjectKinds`** (four subjects), cross-checked
   against the 146 refusal domains (312 evaluated-coin, 13 market).
4. **New probe, `scripts/probe_authoring_148.py`** (the `probe_market_section_146.py` pattern:
   `preview_strategy_report` only, `_MIN_INTERVAL` 0.45 s, retry with back-off, BTC at a 1h anchor, `detail`
   detailed; one column per preview where a refusal is expected, batched columns where acceptance is expected).
   Record `data/audit/authoring_probe_148_2026-11-05.json` (every refusal verbatim), headers
   `data/contract/columns/_probe_148_2026-11-05.json`. Groups, about 140 previews:
   - **A `ema`**: on an oscillator, a price and a volume metric; window 1, 14, the depth maximum (**269**: amended
     2026-11-05, served on every ema-serving metric read; 936 is `aggregate`'s, first written here by mistake) and
     one over (`REPORT_COLUMN_DEPTH_EXCEEDED`); as a chain outer (`RSI14 x zscore -> ema`) and as an inner
     (`CLOSE x ema -> trajectory`); its `smoothingLength` unit; `bars` and `offset` accepted or refused.
   - **B `distance` as chain outer / rolling offset**: `HIGH x rollingMax(55, offset 1) -> distance`
     (`high_o1_max55`), offset 0 into distance (below `offsetMinimum`), `rollingMin` likewise, `offset` on an
     unchained rollingMax.
   - **C swing pairs**: `leftBars` / `rightBars` on each of the seven swing metrics at 2/2 (no token), 3/5
     (`_l3r5`), the served maximum and one over; a knob on a non-swing metric (undeclared-parameter refusal); a pair
     off 2/2 under `rank`, `relativeTo`, `aggregate`, `ema` (refused) and under `trajectory` / `distance` (accepted).
   - **D market structure**: the six keys x every served transform; `swingLength` 9, 10, 50 (no token), 100, 101;
     `confluenceFilter` true (`_cf`) / false; header order when several tokens combine; each key under `rank`,
     `relativeTo`, `aggregate`, `ema` (refused); LEVEL into `distance` and `levelInteraction`; the knob on an
     INTERNAL key vs a SWING key.
   - **E `EQH` / `EQL`**: `equalBars` 1, 3 (no token), 935, 936; `equalThreshold` 0, 0.1, 0.25 (off-step), 0.5, 0.6;
     the `_e<m>` / `_atr<t>` spelling.
   - **F pivots** (timeframe-inert bundles): each of the six types on each of the five periods x `value`, plus
     `distance`, `spread` (pivot vs pivot, pivot vs CLOSE) and `levelInteraction` on a sample; the timeless rule
     (`{abs: "4h"}` refused, `{rel: "anchor"}` only, `offset` the only free knob); QUARTER / YEAR read absent until
     2027-01-01 / 2028-01-01, so their header mints and the cell is null - recorded, not a refusal.
   - **G section subjects**: `benchmarkTicker` `USDT_USD` and `USDC_USDT` with PAR_DEV x value / classifyZone and
     OPEN / HIGH / LOW / CLOSE (the pair section); RSI14 on a pair section (the refusal's served domain = the
     `reference` subject's metrics); a benchmark section (`benchmarkTicker` ETH) with RSI14 and a pivot (the
     `benchmark` subject); `benchmarkTicker` + `marketScope` together (refused: one subject).
   - **H 1,000-bar history**: `aggregate` window 64 / 65 / 936 / 937; `zscore` / `pctl` / `efficiency` window maxima
     (lookback- or depth-bound per the served `bound`); `value` offset maximum; one header's served `conditionHold`
     (`maxWindow` 985 on `RSI14 x value`). The value offset maximum is per metric (63 / 62 / 53 / 44 / 43 / 0, see
     "Resumed"), not a uniform 63.
   - **I combinations**: a knob plus `offset` and a pinned / lower timeframe on the same column (header order).
5. **Coverage sweeps** (`scripts/sweep_render_coverage.py`, one worker, 4 sections per preview, **one `SWEEP_DATE`
   per pass** - the script names both outputs from `SWEEP_DATE` alone and refuses to overwrite an existing pair - and
   `SWEEP_CONTRACT` = the served contract on every pass, so the version is re-read every 25 previews):
   (a) **coin**, `SWEEP_DATE=2026-11-05-structural`, `SWEEP_SCOPE=structural`, `SWEEP_METRICS` = the 206 added keys
   plus every existing metric that gained `ema` (from `_moves_148.json`), default knobs; (b)
   `SWEEP_DATE=2026-11-05-nonspread`, `SWEEP_SCOPE=nonspread` over the same metrics; (c) **reference**,
   `SWEEP_DATE=2026-11-05-reference`, a new `SWEEP_BENCHMARK` (e.g. `USDT_USD`) beside `SWEEP_MARKET_SCOPE`, PAR_DEV's
   13 transforms (the date part is the run's own day if later). Knob variants are not structural shapes: the space
   counts each metric x transform at its default parameters, and groups A - E of step 4 are the knob coverage. The
   three `_coverage_sweep_2026-11-05-*.json` caches are added to `render_coverage.SEEN_FILES` (a fixed list, not a
   glob), then `python -m scripts.render_coverage` reads them and `_probe_148_*`; the operand-expanded spread pairs are
   left unrendered by decision as at 144 and 146. A sweep stops at the first OAuth prompt, platform 5xx or failed
   version GET and writes a partial record (`complete` false) that judges header agreement on the shapes it sent.
6. **OMEGA changes, tests, version.**
   - `omega.types.Column`: the six knobs at the schema's bounds (`leftBars`, `rightBars`, `swingLength`,
     `equalBars` int >= 1; `equalThreshold` float >= 0; `confluenceFilter` bool).
   - `omega.contract`: `Metric.parameters`, `Metric.subject_kinds`, transform `metric_parameters_accepted`; subjects
     read from `_subjects_148.json` (fails closed as `metric_subjects()` does now).
   - `omega.validate`: `PARAMETER_UNDECLARED` (a knob the metric's `parameters` does not serve),
     `PARAMETER_OUT_OF_RANGE` (served minimum / maximum / step, e.g. `swingLength` 10 - 100),
     `PARAMETER_NOT_ACCEPTED` (`metricParametersAccepted` false: an off-default pair or a structure metric under
     rank / relativeTo / aggregate / ema), `DEPTH_EXCEEDED` (a window over the served depth maximum, read per metric
     from the hint's `maximum`, never a constant: `ema` **269**, `aggregate` 936 on every metric read 2026-11-05 -
     amended, this line first said 936 for both); the `ema` transform and the `distance` chain outer with
     `offsetMinimum`;
     `SECTION_SUBJECT_METRIC_UNSUPPORTED` over four subjects (`benchmarkTicker` a declared pair -> `reference`, another
     ticker -> `benchmark`, `marketScope` named -> `market`, else `evaluated-coin`); `METRIC_NO_SUBJECT` retired
     (PAR_DEV reads on a pair section) - each rule quoting the measured platform wording.
   - `omega.fanout`: `_ema{n}`, `_l<L>r<R>`, `_s<n>`, `_cf`, `_e<m>`, `_atr<t>` (off defaults only), `_o<N>` before a
     rolling extreme's window (`high_o1_max55`), in the order step 4 measures.
   - `omega.conditions`: the TREND (`bullish` / `bearish`), EVENT and EQH / EQL vocabularies; budgets from the
     served block (`conditionFrameReads` 2,048).
   - Data: 532 metric files (stamp 20261105; 20261102 archived), `_index.json`, `_moves_148.json`,
     `_subjects_148.json`, categories / vocabulary / templates, `transforms/_authoring.json` (+`ema`, rollingMin/Max
     offset) and `_chain_outer_parameters.json`, `data/audit/timeless_column_timeframe.json` regenerated (143 + the
     timeless pivots), derived matrix / graph / type system, the manifest (146.0.1 block under `supersedes`).
   - `pyproject.toml` **0.12.0** (`omega/__init__.py` carries no version); this file rewritten as the DONE record.

## What the tests will pin (`tests/test_v148.py`, new)

- the write surface: capture 148.1.0, build `d02121ec`, equal to the manager's stored surface; the six knobs with
  their schema types / minima; `transformId` 25 ids incl. `ema`; `chainedTransformId` 13 incl. `distance`, `ema`;
- `compare_vocabulary` on the stored 148.1.0 surface: 532 / 532, 22 / 22, nothing moved, nothing unmeasured;
- the corpus: 532 metrics, 11 families, structure 362, 24 authorable transforms; the 206 in `_moves_148.json` by README
  entry (34 / 82 / 82 / 8); `ema` on the metrics that serve it; every metric's `parameters` and `subjectKinds`;
- subjects: four, PAR_DEV `reference` (the v0.11.0 `None` corrected), MKT_* `market`, the rest
  `evaluated-coin` + `benchmark`, as served and as group G rendered;
- validate: each new code fires on its measured refusal and stays silent on its measured acceptance (groups A - H);
- fanout: every header of groups A - F minted, predicted exactly;
- coverage: structural every mechanism rendered; the measured counts of rendered / never-rendered spread pairs;
- the timeless audit's `affectedMetrics` and the budgets (`conditionFrameReads` 2,048).

Pins that move in existing tests (as in the 146 record): test_v146_1 (PAR_DEV's subject, METRIC_NO_SUBJECT),
test_v146, test_v144, test_compare_vocabulary, test_condition_vocabulary_108, test_metric_vocabulary_108,
test_write_surface, test_membership, test_against_compiler, test_space, test_space_validate_agreement,
test_render_coverage, test_spread_chain_operand, test_timeless_timeframe, test_v103_transform_entry. Target: 1800 +
the new file, 0 failed, nothing newly skipped.

## Platform-call budget and pacing

| step | calls | pacing | wall time (est.) |
|---|---|---|---|
| version checks | ~8 GETs | before / after each step | - |
| 1 surface | 1 `list` | - | 10 s |
| 2 vocabulary | 1 + 11 | sequential | 5 min |
| 3 hints | 532 | sequential, one process per call | 1.5 - 3.5 h (12 - 39 s per call measured today, ~7 s on 11-02) |
| 4 probe | ~140 previews | >= 0.45 s apart, one worker | 30 - 60 min |
| 5 sweeps | ~60 - 120 previews | 4 sections per preview, one worker | 30 - 60 min |
| **total** | **~750 - 820** | never above ~0.5 req/s from this run | **3 - 6 h** |

`refresh_metric_contracts.py` is resumable (a raw hint already in `hints_20261105/` is not re-read), so a long run can
be split; the sweeps cache per shape. Run steps 3 - 5 when the manager is quiet if possible.

## Risks

- **The contract moves mid-run** (three drifts on 2026-11-04): the version gate stops the run; a 148.x that moves an
  authoring enum means repeating steps 1 - 3 for the delta only.
- **Slow hints**: today's reads took 12 - 39 s each; 532 may take the larger part of a working session. Resumable;
  one worker is not negotiable (the live manager shares the account's rate limit).
- **Authoring-block invariance may not hold** with `bound`, the rolling `offset` and `ema`: the refresh then refuses to
  write the catalogue (by design). The fix is to move the per-metric field beside `maximums`, measured, never to drop
  the check.
- **Roster ordering**: running step 3 before step 1's re-derive silently re-reads the stale 326 roster.
- **Operand-expanded explosion**: ~200 new price-unit levels become spread operands of every price metric; the
  operand-expanded count may grow by an order of magnitude (115,035 today). `build_corpus` / `render_coverage` time
  and the tests that load the space must be watched; the expanded pairs stay unrendered by decision.
- **Values are not verified**: v146.1 recomputed EMA-family values over 1,000 bars, v146.13 / v146.14 moved structure
  values, quarterly / yearly pivots read absent until 2027 / 2028. OMEGA pins schema, headers and refusals; `ema` may
  be verified offline against candles (`ta.ema`), the LuxAlgo structure is recorded `notVerified`.
- **Conditions cannot be rendered without staging** (forbidden here): the condition level reference with
  `swingLength` / `confluenceFilter` is modelled from the served `conditionGrammar` only, and flagged so.
- **Consumer behaviour change**: v0.12.0 accepts what v0.11.0 refused (206 keys, `ema`, six knobs, PAR_DEV on a pair
  section) and adds refusals; battlegrid-manager pins v0.11.0 and must re-pin deliberately (its change, not this one).
- **Brief vs measurement**: "session levels", "VWAP families", `window` / `buffer` / `ordering` / `side` are not part
  of the 146.1 - 148.1 delta (in the corpus since 135.1 / 137.2 / 144); the delta is exactly 206 keys, `ema`, the
  `distance` chain outer and six knobs.

## Not in scope

battlegrid-manager (read-only fixtures only); the 147 / 148 arena, Radar and budget tools; `docs/01` / `docs/02`
regeneration; anything on the platform beyond the read-only calls above.

## Executed 2026-11-05 (what was measured)

Clock: GET /mcp/version 148.1.0 / build d02121ec at 09:38:29Z, at every 40th hint (09:49:48Z, 09:57:58Z, 10:07:10Z,
10:15:44Z) and at 10:40:48Z - the contract did not move during the run. Every call read-only over mcporter
(`battlegrid-anbu`) through the scratch npx shim; no stage, commit, bind, deploy, fund, archive or delete.

1. **Step 1 - write surface: DONE.** `mcporter list --schema --all-parameters --json` at **2026-11-05T09:38:43Z**:
   154 tools, every tool entry identical to the 09:18:42Z list. The six draft tools' description / inputSchema /
   outputSchema are identical to battlegrid-manager's fixture `tests/fixtures/2026-11-04-contract-148.1.0/
   manager_schemas_148.1.0.json`, and description / inputSchema to the manager's stored `surface_tools` row (148.1.0,
   observed 2026-11-04T17:51:58Z; the same row re-read at 2026-11-05T08:26:25Z for the Measured section is
   byte-identical but for `observedAt`, so either observation is the same surface). Written as `data/contract/stage_strategy_draft/schema_20261105T093843Z.json` (the
   fixture's entries - the list serves no `annotations` - so `sourceSha256` is the fixture's); manifest `writeSurface`
   names it, with `liveCheckedAt`, the 146.0.0 block under `supersedes`. `data/derived/condition_vocabulary_108.json`
   re-derived: metric enum **532**, transformId **25** (+`ema`), chainedTransformId **13** (+`distance`, +`ema`),
   column fields +6 knobs; `omega/condition_vocabulary.py` now derives `number` bounds too (`equalThreshold` minimum 0)
   and each column field's served JSON type (`confluenceFilter` boolean). `compare_vocabulary` against the live list:
   **exit 1 before** (532 live / 326 stored, 206 liveNotStored, 0 storedNotLive; sectionKeys 22 / 22), **exit 0 after**
   the 206 were listed by name (206 storedUnmeasured) - `data/audit/contract_148_1_0_vocabulary_2026-11-05.json`.
2. **Step 2 - vocabulary: DONE** (09:43:20-09:45:48Z, `data/contract/vocabulary/20261105T0943Z/`).
   `list_strategy_categories`: eleven, ids and texts unchanged, **structure 156 -> 362** (sum 532); the 22 modules
   byte-identical. `list_strategy_vocabulary`: ten categories read; **`structure` is REFUSED `RESULT_TOO_LARGE`**
   ("The result is 224226 characters, over the 150000-character cap; ask for less."), and the tool takes only
   `category`, so the structure category's metric / study listing (the five new studies, the `floorPivots` level-set
   label `Pivots` -> `Traditional`) is not readable through it. Across the ten read, the category-invariant blocks are
   identical; against the 146.0.1 read: transforms **+`ema`** after aggregate ("Exponential average (EMA)", 24 ids),
   **`budgets.conditionFrameReads` 256 -> 2048**; conditionGrammar, timeframeRefs, previewExecutionLimits, timeframes,
   rankedTimeframes, the 22 platform templates, the 3 custom template summaries and the scalar families: unchanged
   (no platform template carries a pivot type, a structure metric or a 1,000-bar window; conditionGrammar carries no
   v146.11 level-reference wording). `categories.json`, `vocabulary/_shared.json`, `templates/platform/_all.json`
   refreshed with `_refreshed` blocks (the 146.0.1 ones under `previous`).
3. **Step 3 - hints: STOPPED at 170 / 532** (resumed 13:36Z to 383 / 532, see "Resumed 2026-11-05 13:36Z"). `get_metric_construction_hints` read in roster order 09:40:01Z-10:17:58Z
   for OPEN ... PRIOR_LONDON_LOW_SWEPT (indices 1-170), 0 failures, ~7-24 s per call. The next call (NEW_YORK_HIGH,
   started ~10:18Z) and the two after it each failed three times with mcporter's "If the browser did not open,
   visit https://mcp.battlegrid.trade/authorize?..." - `~/.mcporter/credentials.json` holds the client registration but
   no `tokens` since 10:29:57Z, and `~/.mcporter/battlegrid-anbu/server_url.txt` was rewritten at 10:18Z by a process
   other than this run. The fetcher was stopped at 10:30Z. Each failed call began an OAuth authorization (new dynamic
   client ids d1196f2a, a6be72d3, 49c9f9b4 among them; up to nine attempts) and may have opened a browser tab on the
   authorize page; nothing was approved. Re-authorizing is the user's step.
   Measured on the 170 read (raw responses in the session scratchpad `v012/hints_20261105/`, not committed): every
   metric serves `gloss`, `subjectKinds` and `parameters` (null on all 170 - the swing metrics, indices 193-199, were
   not reached); every transform entry serves `metricParametersAccepted`; the authoring blocks stay invariant per
   transform once `maximum` and `bound` are moved to the metric entry (`authoring_invariance` dry check: 1 variant per
   transform, `chainOuterParameters` 1 variant); `ema` is served on 103 of the 170, window maximum **269** on every
   one (`bound` depth, unit smoothingLength - NOT the 936 the plan expected; `aggregate`'s is 936); `subjectKinds`:
   165 `evaluated-coin` + `benchmark`, 4 (OPEN, HIGH, LOW, CLOSE) + `reference`, PAR_DEV `reference` only.
   `scripts/refresh_metric_contracts.py` is extended for the new served fields (gloss, subjectKinds, parameters,
   metricParametersAccepted, a `bounds` sibling of `maximums`) and NOT run: it needs all 532.
4. **Step 4 - probe: NOT RUN.** `scripts/probe_authoring_148.py` (groups A - I, ~150 previews) is written and
   committed; it reads each new key's transforms from the same day's hints, so it waits on step 3.
5. **Step 5 - sweeps / render_coverage: NOT RUN** (they need the corpus and the probe).
6. **Step 6: partial.** Offline only what was measured: the write surface, the vocabulary, the 206 keys listed by name
   in `data/contract/metrics/_unmeasured_108.json` (the v0.10.2 pattern: refused offline as `METRIC_UNMEASURED`;
   `compare_vocabulary` reads them `storedUnmeasured`, so a consumer's pin-drift gate reads nothing moved), `ema`
   derived `TRANSFORM_UNMEASURED`, the six knobs NOT on `omega.types.Column` (a column carrying one is refused by the
   model). `tests/test_v148_surface.py` (17) pins it; pins moved in nine existing test files. **`pyproject.toml` stays 0.11.0**:
   v0.12.0 is the full re-extraction, which this is not.

## Resumed 2026-11-05 13:36Z (after the user re-authorized mcporter at 13:36:07Z)

Clock: GET /mcp/version 148.1.0 / build d02121ec at 13:38:09Z, at the fetch start 13:38:40Z and every 40th hint
(13:48:03Z, 13:56:10Z, 14:04:23Z, 14:12:44Z, 14:29:51Z). Every call read-only over mcporter (`battlegrid-anbu`) through
the scratch npx shim, one worker; no stage, commit, bind, deploy, fund, archive or delete. No OAuth prompt this time.

- **Step 3 - hints: 383 / 532 on disk, then STOPPED.** The session's `fetch_hints.py` (now stopping at once on an OAuth
  prompt or a platform 5xx) read roster indices 171 - 383 (NEW_YORK_HIGH ... PIVOT_QUARTER_CAM_R1) at
  13:39:17Z - 14:42:30Z, 213 hints, 0 failures, **7.0 - 144.5 s per call**: 7 - 41 s through index 360 (14:19:08Z),
  then a slowdown from PIVOT_MONTH_DM_P (index 361, 14:20:20Z) to the outage - indices 361 - 383 took 14.5 - 144.5 s
  (mean ~60 s), 19 calls over 41 s, PIVOT_QUARTER_S2 144.5 s, PIVOT_MONTH_DM_S1 83.5 s, PIVOT_QUARTER_R4 82.8 s,
  PIVOT_QUARTER_R5 82.7 s (`fetch_hints_resume_stdout.txt`). A timeout or rate budget for the next read is sized from
  the 145 s, not 41 s; the slowdown may have been the 149 deploy beginning. From 14:43:32Z every call answered "HTTP 502
  (Version negotiation failed: the server answered the probe with HTTP 502)" - PIVOT_QUARTER_CAM_R2 .. _S2 (indices
  384 - 389), three attempts each - and GET /mcp/version answered nginx 502 too; the fetch was stopped at 14:48Z. The
  version GET was then polled once a minute (no MCP call) until it answered at **16:31:50Z: contract 149.0.0, build
  5ec52a81589047437f7e7c59a613a1839499daee**. The run stopped there, as the route requires.
- **Measured on the 383 (raw hints in the session scratchpad `v012/hints_20261105/`, not committed).** Version: 370
  of them (indices 1 - 370) were read between two GET /mcp/version reads of 148.1.0 / d02121ec. The last 13 (indices
  371 - 383, PIVOT_QUARTER_S2 .. PIVOT_QUARTER_CAM_R1, read 14:32:15Z - 14:42:30Z) came after the last 148.1.0 read
  (14:29:51Z) with none after them - the next read was 149.0.0 at 16:31:50Z, the 502 began a minute after the last
  hint, and a raw hint carries no `contractVersion` or build field. **148.1.0 is inferred for those 13, not
  measured** (a review compared four of them with siblings read before 14:29:51Z, name masked: top-level keys, metric
  keys and transforms match, which fits 148.1.0 but does not settle it); see "To resume". The authoring blocks stay invariant per transform with `maximum` / `bound` moved to the metric entry
  (dry check over all 383: 1 variant per transform, `chainOuterParameters` 1 variant). The 14 new structure keys read:
  `SWING_FRACTAL_*` (7) serve `leftBars` / `rightBars` {default 2, 1 - 933, bound depth}; `metricParametersAccepted`
  true on value / trajectory / distance / spread / efficiency / the six statistics / levelInteraction and **false on
  relativeTo, aggregate and ema**. `INTERNAL_STRUCTURE_EVENT` / `_TREND` / `_LEVEL` serve `swingLength` {default 50,
  10 - 100, bound depth} AND `confluenceFilter` {default false, bound flag}; **`SWING_STRUCTURE_*` serve `swingLength`
  only** (no `confluenceFilter`). EVENT: kind event, vocab `BOS↑ BOS↓ CHoCH↑ CHoCH↓`, value only; TREND: classification
  `bullish` / `bearish`, value only; LEVEL: price, 12 transforms (no relativeTo / aggregate / ema / rank), 368 spread
  operands. `EQH` / `EQL`: boolean, value only, `equalBars` {default 3, 1 - 935, depth}, `equalThreshold` {default 0.1,
  0 - 0.5, step 0.1, bound range}. Pivots (day and the four periods): timeless, value / distance / spread /
  levelInteraction, 368 spread operands, no `anchor`; day pivots keep study `floorPivots`, periods `weeklyPivots` etc.
  `value.offset` maximum **did not move**: served 63 on 145 metrics, 0 on the 228 timeless ones, and lower on nine
  candle / gap metrics - BAR_CONTAINMENT, CANDLE_ENGULFING, GAP, GAP_PCT, GAP_RANGE_CLEAR 62; CANDLE_DOJI, CANDLE_PIN
  53; CANDLE_RUN 44; CLOSE_RUN 43 (STRUCT_ZONES serves no value offset maximum). The pinned 146.0.1 corpus stores the
  same per-metric values (63 since the 135.2.0 re-extraction, 6dccb6b; 31 was the 108.4.0 corpus), so there is no
  31 -> 63 move to record, and probe group H checks each metric's served maximum, not one uniform 63 (CANDLE_RUN
  offset 50 is over its 44). Every metric read serves `subjectKinds`;
  `ema` window maximum 269 on every metric that serves it, `aggregate` 936.
- **Nothing under data/ moved**: `refresh_metric_contracts.py` writes only once all 532 raw hints are on disk, and a
  149.0.0 surface must be compared before any 148.1.0 hint is mixed with 149.0.0 ones.
- **Offline, prepared and NOT applied** (session scratchpad `v012/edits/`, each an exact-substring edit script):
  `e_types.py` (the six knobs on `omega.types.Column` at the schema bounds), `e_contract.py` (`Metric.subjects` /
  `parameters` / `gloss`, `metric_subjects()` from `_subjects_148.json` over four subjects), `e_validate.py` (ema in the
  series sets, offset declared per transform, DEPTH_EXCEEDED by the served `bound`, CHAIN_OFFSET_BELOW_MINIMUM,
  PARAMETER_UNDECLARED / _OUT_OF_RANGE / _NOT_ACCEPTED, four-subject SECTION_SUBJECT_METRIC_UNSUPPORTED and
  SECTION_SUBJECT_CONFLICT, METRIC_NO_SUBJECT retired - the `{Q:...}` markers wait for the probe's verbatim wording),
  `e_fanout.py` (`_ema{n}`, the rolling `_o<N>`, the knob tokens - their position in the header is a guess until group
  I renders), `e_space.py` (a shape carries `offsetMinimum` into the rolling -> distance chain). `build_moves.py` writes
  `_moves_148.json` / `_subjects_148.json` after the refresh. Committed: `scripts/sweep_render_coverage.py`
  SWEEP_BENCHMARK, an OAuth stop, a version gate and a partial record (3ac741a).

## What moved (measured)

| axis | 146.0.1 (OMEGA v0.11.0) | 148.1.0 (measured 2026-11-05) |
|---|---|---|
| tools listed | 151 | 154 |
| `$defs/metricKey` | 326 | 532 (+206, none retired) |
| transformId / chainedTransformId | 24 / 11 | 25 (+ema) / 13 (+distance, +ema) |
| column fields | 13 | 19 (+leftBars, rightBars, swingLength, equalBars: integer >= 1; equalThreshold: number >= 0; confluenceFilter: boolean) |
| sectionKeys | 22 | 22 |
| categories | 11, structure 156 | 11, structure 362 |
| served transform catalogue | 23 | 24 (+ema) |
| `budgets.conditionFrameReads` | 256 | 2048 |
| `list_strategy_vocabulary {structure}` | read | refused RESULT_TOO_LARGE (224,226 chars > 150,000) |

## Numbers

Metrics in the corpus 326 (measured at 146.0.1), served 532, unmeasured 206 (34 v146.5 + 82 v146.8 + 82 v146.10 +
8 v146.11). Hints read: 383 / 532 (370 between two 148.1.0 version reads, 13
after the last one - see "Resumed"; 144 of the 206 added keys among them); the served contract is 149.0.0 since
16:31:50Z. Probes 0 / ~150. Sweeps 0. Tests: 1818 passed (1800 + 18: the 17 of tests/test_v148_surface.py and one 148-enum test in tests/test_condition_vocabulary_108.py), 0 failed; after the review fixes below **1841 passed** (+23), 0 failed; after the second review pass **1856 passed** (+15,
tests/test_sweep_render_coverage.py), 0 failed.

## Review fixes 2026-11-05 (offline, after 8182fa1)

Seven confirmed review findings, each reproduced by a test that failed at 8182fa1:

1. **The unmeasured gate covered only a column's own metric and transformId.** An unmeasured key as a spread operand
   (`CLOSE x spread [PIVOT_WEEK_P]`), as a chain outer (`HIGH x distance -> ema`, `RSI14 x spread -> ema`,
   `HIGH x rollingMax -> distance`) or the rolling `offset` (v146.6) fell through to the 146.0.1 corpus and got
   OPERAND_NOT_ALLOWED / REPORT_COLUMN_CHAIN_UNSUPPORTED / OFFSET_REFUSED stated as fact, while the 148.1.0 hints serve
   all of them. `_unmeasured_108.json` now lists `chainOuters` (distance, ema) and `transformParameters`
   (rollingMax / rollingMin `offset`); omega.validate refuses them METRIC_UNMEASURED / TRANSFORM_UNMEASURED /
   PARAMETER_UNMEASURED before any corpus rule, and validate_section no longer raises KeyError predicting the header
   of a column over an operand the corpus does not hold.
2. **`probe_authoring_148.py` recorded transport / OAuth failures as refusals** and kept calling (247 calls, exit 0,
   all "refused" with the credential lost). It now stops on the first non-platform answer (an OAuth prompt is never
   retried), re-reads GET /mcp/version every 25 probes, and writes a PARTIAL record (`complete` false, `aborted`).
3. **`_unmeasured_108.json` `_what` still said EMPTY**, and the manifest / a test comment named an uncut "OMEGA
   v0.12.0": fixed, and a test refuses "v0.12.0" in those records until pyproject is cut.
4. **The plan contradicted itself**: the manager row's two observations (now both stated: identical but for
   `observedAt`) and ema's depth maximum in steps 4 / 6 (amended 936 -> 269).
5. **`refresh_metric_contracts.py` wrote a short `_index.json` on a partial run** (170 / 532 would have left
   omega.contract.load() raising "corpus incomplete"): it now reads every raw hint before writing anything under
   data/, and stops the fetch on an OAuth prompt.
6. **`build_corpus.py` exited "roster mismatch"** (532 served, 326 measured): it reconciles against the measured roster
   (served minus the names-only list; family shortfall = the unmeasured count, structure 206), and the matrix gets no
   column for `ema` (served, never extracted). It reproduces every committed artefact unchanged.
7. **A chained `ema` / `distance` was refused as "not a composable chain"**: covered by 1.

## Review fixes 2026-11-05, second pass (offline, after 1743bcb; recorded 16:56Z)

Ten confirmed findings (seven distinct defects; three were raised twice), no platform call. Code, each reproduced first by tests/test_sweep_render_coverage.py (14 of
its 15 tests failed at 5c09f34, the refactor that made the script importable without running a sweep):

1. **The sweep recorded a platform 5xx as per-column refusals and kept calling** (two findings): it stopped only on
   an OAuth marker, so the 14:43Z 502 text was bisected to every leaf (~383 previews per 128-column batch) and stored
   as each column's refusal, `complete` true. It now stops after the first 5xx (stderr or a gateway page on stdout).
2. **A failing version GET crashed the sweep before any output was written** (two findings): an nginx 502, a timeout
   or a non-JSON body is now a stop like the others, so the partial record is written.
3. **An aborted sweep listed every never-sent shape as predicted-but-not-rendered** (two findings), and
   `shapesRequested` was the target count: agreement is judged on the completed batches' shapes; the record carries
   `shapesTargeted` and `shapesRequested` (= sent); headers minted inside an interrupted bisect are kept.
4. **Step 5 ran three sweeps under one `SWEEP_DATE`**, each overwriting the last pair: one `SWEEP_DATE` per pass,
   `SWEEP_CONTRACT` set, the three caches added to `SEEN_FILES`; the script refuses an existing output pair
   (`SWEEP_OVERWRITE=1` to replace on purpose).

Record only:

5. **`value.offset` maximum "now 63 (was 31)"**: nothing moved; the per-metric maxima (63 / 62 / 53 / 44 / 43 / 0)
   are the 146.0.1 corpus's, counted from the 383 raw hints.
6. **"Hints read at 148.1.0: 170 / 532"** in Numbers, Not measured and To resume: 383, with the 144 of the 206 added
   keys among them.
7. **"~7 - 41 s per call"**: 7.0 - 144.5 s, with the slowdown from index 361 that ran into the outage.
8. **"all read at 148.1.0"**: 370 measured between two 148.1.0 reads; 371 - 383 inferred, and the 149 re-read sample
   must include them.

## Resumed 2026-11-07 (offline, contract 149.1.0; recorded 03:22Z)

No OMEGA platform call. The served contract has been **149.1.0 / build aa4ab640** since 2026-11-05 18:19Z (the user
acknowledged it on the manager at 20:31:47Z). 149 is undocumented in the README; what moved was read from the schemas.
On the custom column:
- the transforms `rma`, `wma`, `rsi` and `cci` were added to transformId (29) and chainedTransformId (17);
- thirteen optional knobs were added: atrPeriod, dSmoothing, fast, kSmoothing, period, rsiPeriod, signal and slow (each
  a `$ref` to the new root `$defs/barCount`, integer 1 - 2^53-1), multiplier and stdDev, and PSAR's
  accelerationStart / Increment / Maximum;
- leftBars, rightBars, swingLength and equalBars became the same `$ref`;
- equalThreshold lost its minimum 0.

No metric key, section key or tool moved.

1. **`condition_vocabulary._column_enums` follows `$ref`.**
   - The defect: the derive read each column field's own keys. On 149 that dropped the type and bounds of the twelve
     bar-count knobs, so 9 of the 21 numeric fields kept their bounds.
   - The fix: each field is read through its `$ref`. The inventory also records `refs`, the field -> pointer map.
   - `tests/test_condition_vocabulary_108.py::test_a_column_field_named_by_ref_keeps_its_type_and_bounds` failed
     first (KeyError 'leftBars').
2. **The write surface moved to `data/contract/stage_strategy_draft/schema_20261105T181932Z.json`.**
   - It is battlegrid-manager's fixture `tests/fixtures/2026-11-05-contract-149.1.0/manager_schemas_149.1.0.json`:
     the watch's stored row, hash 656c9bf6, `sourceSha256` the fixture's, `liveListSha256` null.
   - Manifest `writeSurface` names it, with the 148.1.0 block under `supersedes`.
   - Cross-checked against the manager's own live observation. Its watch re-listed the surface at
     **2026-11-07T03:16:53Z**, when the stack came back from a host reboot: 154 tools, 149.1.0 / aa4ab640, and the six
     draft tools' description and inputSchema identical to the capture. The stored manager_schemas row equals the
     capture on all four keys.
   - `compare_vocabulary` against that surface: **exit 0**. Metrics 532 / 532 (206 storedUnmeasured, as at 148.1.0),
     sectionKeys 22 / 22. Recorded in `data/audit/contract_149_1_0_vocabulary_2026-11-07.json`.
3. **Vocabulary re-derived** (`data/derived/condition_vocabulary_108.json`): 532 metrics, transformId 29,
   chainedTransformId 17, 32 column fields, all 21 numeric fields bounded as served. The conditions grammar is
   unchanged since 148.1.0.
4. **The four new transforms are unmeasured.**
   - `omega.contract` derives `rma`, `wma`, `rsi` and `cci` as unmeasured transforms (served, not extracted), beside
     `ema`.
   - `_unmeasured_108.json` lists them as chain outers too.
   - A column using one, as its transform or as a chain outer, is refused TRANSFORM_UNMEASURED.
   - The thirteen knobs are not on `omega.types.Column`, so the model refuses them.
5. **The 532 hints read at 149.1.0 (C13, 2026-11-06 15:35 - 17:04Z, 0 failed, every one bracketed by two 149.1.0
   version reads) are summarized, NOT folded into the corpus** (`data/audit/hints_149_1_0_2026-11-06.json`).
   - A dry run of `refresh_metric_contracts.py` over them in a scratch copy wrote 532 with no failures.
   - Every transform's authoring block is invariant, and `chainOuterParameters` is invariant.
   - The catalogue would gain cci / ema / rma / rsi / wma and change aggregate / rollingMax / rollingMin.
   - 165 metrics serve all five smoothers. Window maxima: ema 269, rma and rsi 118, wma and cci 936. The same maxima
     apply as chain outers on 387 successor positions.
   - The nineteen knobs are served per metric (e.g. leftBars / rightBars on the 7 swing metrics, `period` on 12).
   - subjectKinds come in four subjects (489 coin + benchmark, 25 coin only, 13 market, 4 OHLC + reference,
     PAR_DEV reference only).
   - **Ruling (Claude's): the refresh lands with stage 2, not here.** A refreshed catalogue makes the five smoothers and
     the 206 keys authorable, while their headers, knob tokens and refusals are unrendered (no probe has run). Landing
     it alone would have OMEGA predict headers it never saw.
   - **Cost if wrong:** one step of the re-extraction waits a session. The raw hints stay at
     C:/Users/rafae/omega-v012-hints/hints_20261106/ (not committed, sha256 in the record).
6. **Tests: 1887 passed, 0 failed.** That is 1856 + 1 `$ref` test + 30 in the new `tests/test_v149_surface.py`. Pins moved in test_condition_vocabulary_108, test_report_surface_108, test_compare_vocabulary, test_v146,
   test_v146_1 and test_write_surface. test_v148_surface now reads the 148.1.0 capture's own derivation, so it holds
   as history. `pyproject.toml` stays 0.11.0.

**Next (stage 2, needs the platform):**
- re-target `probe_authoring_148.py` to 149.1.0, adding a group for rma / wma / rsi / cci and the thirteen knobs;
- the sweeps;
- then the refresh above, `build_corpus`, `_moves_149` / `_subjects_149`, the model changes, two review passes, and
  the 0.12.0 cut.

## Stage 2 begun 2026-11-07: the authoring probe at 149.1.0 (recorded 11:40Z)

Clock: `manager contract status` 149.1.0 / aa4ab640, writes open, at 10:53Z; GET /mcp/version 149.1.0 at the start
(10:58:34Z), every 25 previews and at the end (11:32:02Z). Every call `preview_strategy_report` over mcporter
(`battlegrid-anbu`, the npx shim at `C:/Users/rafae/omega-v012-hints/npxshim/`), one worker, read-only: no stage,
commit, bind, deploy, fund, archive or delete. The manager was PAUSED (the user's word) with one position open.

1. **The probe re-targeted** (`scripts/probe_authoring_148.py`, bc0a78a): `PROBE_CONTRACT` default 149.1.0, outputs
   named by the major (`_probe_149_<DATE>`), and **group J**: rma / wma / rsi / cci (accepted windows, the served
   maximum and one over, chain outers, offset, an inner chain, an unserved metric, a pinned timeframe) and the thirteen
   knobs (accepted, explicit defaults, each kind at its served maximum and one step past, minima, off-step,
   non-integer, fast > slow, undeclared knobs, knobs under history transforms, combinations). Every bound is read from
   the 149.1.0 hints. Groups A - I unchanged.
2. **Run: complete, 225 previews, 104 rendered, 121 refused, 254 headers minted** (10:58:34Z - 11:32:02Z, ~9 s per
   preview). `data/audit/authoring_probe_149_2026-11-07.json` (every refusal verbatim),
   `data/contract/columns/_probe_149_2026-11-07.json` (headers only). Two answers were the preview's 15 s deadline
   (`SERVICE_UNAVAILABLE`, F.PIVOT_CAM_R1.served and J.rma.chainOuter): platform answers, not authoring refusals; every
   column of both batches rendered when re-probed alone. The script now marks such an entry `transient` and counts it;
   the record was annotated the same way offline (`transientNote`).
3. **Measured** (pinned in `tests/test_probe_149_record.py`, 21 tests):
   - **Smoothers.** Default windows ema 20, rma 14, wma 20, rsi 14, cci 20, spelled in the header (`RSI14_rma14`).
     Maxima as served: ema 269, rma / rsi 118, wma / cci 936; one over is `REPORT_COLUMN_DEPTH_EXCEEDED` ("at most 936
     of the 1000 readable bars"). cci needs window >= 2 (the hint's minimum). All five refuse `offset`; none is a chain
     inner (`CLOSE x rma -> trajectory` CHAIN_UNSUPPORTED); as outers of distance / spread / relativeTo they render
     `dist_close_rma10`, `RSI14_RSI7_spread_rma10`, `close_BTC_rel_rma10`; `zscore -> rma` is refused. A pinned
     timeframe goes before the smoother (`RSI14_4h_cci20`).
   - **Knobs.** Once any knob of a metric is off its default, the metric's whole set is spelled, in a fixed order:
     `MACDline_fast8slow21sig5`, `PPOline_fast12slow30sig9`, `K_p21s5d5`, `stochRsiK_rsi21_p14s3d3`,
     `bbUpper20_p30sd2.5`, `kcUpper_p30atr14mult1.5`, `stLine_atr14mult2`, `PSAR_start0.01inc0.01max0.3`, `CMF20_p30`,
     `MFI14_p21`, `willR14_p21`. Explicit defaults mint no token. Order with the rest: knobs, then timeframe, then
     offset (`bbUpper20_p30sd2.5_ltf_o2`), then the transform suffix (`MACDline_fast8slow26sig9_trend`).
     Bar-count knobs are bound by depth (one past the served maximum is DEPTH_EXCEEDED, the message counting the
     bars the whole indicator reads); range knobs by the served range and step ("requires params.stdDev from 0.1 to 5
     in steps of 0.1 (got 5.1)"); a non-integer bar count is a schema VALIDATION_ERROR. No ordering rule between fast
     and slow (fast 30 / slow 10 renders). An undeclared knob: "metric 'RSI14' does not accept params.period". Under
     aggregate / ema / rma / zscore and as an inner of a smoother chain, an off-default knob is refused ("its window
     reaches slots older than the history ..."); under relativeTo too (the other coin reads the default); under
     trajectory / crossDetect / spread / efficiency / distance / levelInteraction / classifyZone it renders.
   - **equalThreshold** lost its schema minimum at 149, but the column grammar still refuses -0.1 (from 0 to 0.5 in
     steps of 0.1).
   - **The 148.1.0 widening** renders as the hints serve it: `dist_high_o1_max55` (offset 0 into distance refused),
     `fractalHi_l3r5` / `fractalLo_l4r2` (the pair is spelled once either bar is off 2/2), `structLvl_s10` /
     `iStructTrend_cf`, `SWING_STRUCTURE_*` refuse `confluenceFilter`, `eqh_e5_atr0.2` / `eqh_atr0`, the 35 pivot
     headers (`pivotWeekP`, `pivotQuarterCamR1` ...), timeless pivots refuse a timeframe or offset.
   - **Four subjects** as rendered: a pair section (`USDT_USD`) carries PAR_DEV and OHLC; a benchmark section (ETH)
     carries RSI14, pivots and structure; each mismatch is SUBJECT_METRIC_UNSUPPORTED ("a reference section cannot
     carry this column - metric 'RSI14' is not read on a reference section's bars"); `benchmarkTicker` + `marketScope`
     is a VALIDATION_ERROR; PAR_DEV x relativeTo on a pair section needs an `instrument`.
   - Platform wording recorded as served, not corrected: the swing `rightBars` over-refusal says "the largest left that
     fits is 1", and the MACD `signal` over-refusal names "slow 26".

4. **Tests: 1912 passed, 0 failed** (1887 + 4 in `tests/test_probe_authoring_148.py`: the 149.1.0 target, every
   column sent is a 149 column, every smoother and knob is sent, the bounds come from the hints + the 21 record pins).
   `pyproject.toml` stays 0.11.0; `_unmeasured_108.json` unchanged (the smoothers and knobs stay refused offline until
   the model changes land).

**Next:** the sweeps (step 5, at 149.1.0, `SWEEP_CONTRACT=149.1.0`, the probe's caches added to
`render_coverage.SEEN_FILES` then), the refresh over the 2026-11-06 hints, `build_corpus`, `_moves_149` /
`_subjects_149`, the model changes (knobs on `Column`, the five smoothers, the codes above with this wording), two
review passes, the 0.12.0 cut.

## Not measured, and why

- **The 206 added keys as rendered** (headers, refusals, subjects): no probe or sweep ran. Their hints: 144 of the 206
  are among the 383 read (roster indices 200 - 383); the other 62 (indices 384 - 445) were not reached - the hint step
  stopped at index 383 on the 502 outage and then the contract move to 149.0.0.
- **The 149 roster metrics after index 383** at 148.1.0 (their `ema`, `parameters`, `subjectKinds`): same reason.
  The stored records are the 146.0.1 ones.
- **`ema`, the `distance` chain outer and the six knobs** (headers `_ema{n}`, `_l<L>r<R>`, `_s<n>`, `_cf`, `_e<m>`,
  `_atr<t>`, `high_o1_max55`; refusals; depth maxima beyond the 269 above): the probe needs the hints and the
  platform.
- **The four section subjects** as rendered (group G) and the corrected PAR_DEV subject: served `subjectKinds` read
  for 383 metrics only; `_subjects_148.json` not written; `omega.contract` still reads `_subjects_146.json`.
- **The structure category's vocabulary listing**: refused `RESULT_TOO_LARGE` by the platform (not a transport
  failure); the per-metric hints carry the same metric facts.

## To resume

**Superseded 2026-11-07: see "Resumed 2026-11-07" above - the 149.1.0 surface is captured, all 532 hints are re-read at 149.1.0, the probe is next.** (Earlier note:) **Since 2026-11-05T16:31:50Z the served contract is 149.0.0 (build 5ec52a81), not 148.1.0.** Before anything below:
read the battlegrid-mcp README "Contract history" for 149, re-list the surface, run `compare_vocabulary` against it and
diff the six draft tools' schemas against the 148.1.0 capture (step 1 again). If 149 moved no authoring input, the 383
raw hints can be kept only after re-reading a sample of them at 149 and finding them identical - the sample includes
all 13 of indices 371 - 383 (PIVOT_QUARTER_S2 .. PIVOT_QUARTER_CAM_R1, no 148.1.0 read after them); otherwise re-read
all 532 at 149 (new stamp) and re-run steps 1 - 2. Size the per-call timeout from the 144.5 s measured, not 41 s. The 148.1.0 steps below are the earlier resume note.

1. The user re-authorizes mcporter for `battlegrid-anbu` (interactive browser consent).
2. `GET /mcp/version`; if still 148.1.0, re-run the session's `fetch_hints.py` (or `refresh_metric_contracts.py`
   directly) with `EXTRACTION_SCRATCH` pointing at a dir holding `hints_20261105/` - the 383 raw hints are in this
   session's scratchpad `v012/hints_20261105/` and are skipped on a resume; if the scratchpad is gone, re-read all 532.
   If the contract moved, redo step 1 first.
3. Then steps 3 - 6 as planned: `_unmeasured_108.json` empties again (history148; its `chainOuters` and
   `transformParameters` too, once groups A and B render them), the knobs go on `Column`, the version goes to 0.12.0.
   `refresh_metric_contracts.py` now writes nothing until all 532 raw hints are on disk, and both it and the probe
   stop at the first OAuth prompt, so a lapsed credential costs one call, not hundreds.
