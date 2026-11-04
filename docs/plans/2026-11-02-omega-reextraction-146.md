# OMEGA v0.11.0 at contract 146.0.1: the 24 metrics 146.0.0 added, re-extracted

**Status: DONE 2026-11-02.** Served contract **146.0.1** (build `a07740c0`, `GET /mcp/version` at 2026-11-02T05:54:31Z;
146.0.0 build `1cd4466a` was acknowledged by the battlegrid-manager watch 2026-11-01T07:56:45Z, and no tool moved between
the two: the six draft tools listed live at 05:54:05Z are byte-identical to the stored 146.0.0 capture
`data/contract/stage_strategy_draft/schema_20261101T061733Z.json`). 146.x is undocumented in the battlegrid-mcp README,
which stops at v143. Baseline main (v0.10.2, 10002d5): 1762 passed. This branch: **1800 passed** (the 38 of
`tests/test_v146_1.py` added).

## Why

OMEGA v0.10.2 (2026-11-01) stored the 24 metric keys contract 146.0.0 added to `$defs/metricKey` by name only
(`data/contract/metrics/_unmeasured_108.json`): the write surface accepted them, `omega.validate` refused every column
over them as `METRIC_UNMEASURED`, and `compare_vocabulary` reported them `storedUnmeasured`. Nothing about them was
measured - which section reads them, which transforms they offer, what their headers are, what a market section is.

This is the re-extraction: the v0.10.0 pipeline run again at 146.0.1 so the 24 move from "known by name" to corpus
cells like every other metric, plus the one new axis 146 introduced that the pipeline had never had to measure.

## Route

Every platform call read-only, over the `mcporter` CLI (`battlegrid-anbu`, account ANBUJEFF; the cached mcporter 0.14.3
through a scratch `npx.cmd` shim, since `npx mcporter` wants a download now). No stage, commit, bind, deploy or fund;
every render a `preview_strategy_report` of an unsaved draft. battlegrid-manager was not read and not written.

1. **Surface**: `mcporter list --schema --all-parameters` at 05:54:05Z (151 tools); `scripts/compare_vocabulary.py`
   against it: 326/326 metrics, 22/22 section keys, nothing moved, 24 `storedUnmeasured` at that moment
   (`data/audit/contract_146_0_1_vocabulary_unchanged_2026-11-02.json` is the same compare after the extraction: 0).
2. `list_strategy_categories` + `list_strategy_vocabulary` x 11 at 05:54:50-05:57:10Z
   (`data/contract/vocabulary/20261102T0555Z/`): **eleven categories - `market` added, 13 metrics, study
   `marketBreadth`**; the transform catalogue the same 23 ids with the served order moved (classifyZone now precedes
   maxShare and rank); platform templates: `includeRegimeContext` gained the two REGIME_WARNING_* x value,
   `includeCrowdIntelligence` the eight CROWD_*_Z x value (22 templates, 135 columns; the two 146.0.0 retired
   `includeMarketBreadth` / `includeReferencePairs` confirmed gone from the served block); custom template summary
   `volatility-trend` re-worded ("Bollinger width %"), three summaries now.
3. `get_metric_construction_hints` x 326 (0 failed) at 05:54-06:32Z, then `scripts/refresh_metric_contracts.py`
   (EXTRACTION_STAMP 20261102, archive 20261030): **24 added, none retired**; `scripts/build_corpus.py` 326/326 against
   the enum, family counts reconciled with the eleven categories; `_moves_146.json` with the served facts of each key.
4. `scripts/probe_market_section_146.py` at 06:03:40-06:16:11Z: **97 probes, 50 accepted, 47 refused, 44 headers**
   (`data/audit/market_section_probe_146_2026-11-02.json`, headers in `data/contract/columns/_probe_146_2026-11-02.json`):
   A the two subject domains, B each of the 24 on a coin section and on a market section, C `MKT_UP` at all nine
   scopes, D applicability (rank / relativeTo / distance / scope / offset / abs / lower timeframe / spread operands /
   chains / classifyZone / maxShare / efficiency), E mixed reports (a coin section and a market section side by side,
   two market sections at two scopes).
5. Two coverage sweeps, one per section subject (`scripts/sweep_render_coverage.py`, new `SWEEP_MARKET_SCOPE` and
   `SWEEP_METRICS`): **coin** (06:34:56-06:35:45Z, marketScope null, the ten coin-subject metrics plus CVD /
   CUM_VOLUME_DELTA / SPOT_CVD which gained classifyZone) 200 shapes, 268 headers, **0 refusals, 0 mispredicted**;
   **market** (06:35:25-06:38:25Z, marketScope crypto, the 13 MKT_*) 1,015 shapes, 1,419 headers, **0 refusals,
   0 mispredicted**. `python -m scripts.render_coverage`: structural **4,408 / 4,408**; operand-expanded 34,355
   rendered, 80,639 spread pairs never (below).
6. `tests/test_v146_1.py` (38) pins every stored measurement above; `docs/plans` (this file); version 0.11.0.

## What moved (measured)

**The axis: a custom section's `marketScope` selects its subject.** `null` is an evaluated-coin section, a named scope
(`all, crypto, l1, memes, defi, tradfi, stocks, indices, commodities`) a MARKET section. Each subject refuses a column
whose metric it does not read - `REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED`, "a evaluated-coin section cannot carry this
column — metric 'MKT_UP' is not read on a evaluated-coin section's bars" - and serves, in that refusal, the WHOLE domain
it does read (`details.allowedDomain.candidates`). Two refusals gave the partition (`data/contract/metrics/_subjects_146.json`):

| subject | marketScope | reads |
|---|---|---|
| evaluated-coin | null | 312 metrics (every metric of 144.0.0 plus the eight CROWD_*_Z and the two REGIME_WARNING_*) |
| market | a named scope | the 13 MKT_* and nothing else |
| (none) | - | PAR_DEV |

- **The 13 MKT_*** (family `market`, candle grid, `battleGridDerived`): MKT_UP / MKT_DOWN / MKT_NET / MKT_AVG_CHG /
  MKT_DISPERSION / MKT_PPO_UP / MKT_PPO_DOWN / MKT_PPO_NET / MKT_AVG_PPO / MKT_ABOVE_EMA (12 transforms each: value,
  trajectory, spread, aggregate, efficiency, maxShare and the six series statistics; MKT_ABOVE_EMA also classifyZone,
  risk-off / neutral / risk-on), MKT_STRETCH (11, no spread), MKT_VOL_NET and MKT_UNIVERSE (10, no spread). A market
  spread takes a market operand only (the served `spreadOperands`: the other nine). No rank, no relativeTo, no
  distance (refused by the subject rule, D probes). The header carries **no scope token**: `mktUp` on a crypto section
  and on an l1 section is the same header, and two market sections at two scopes in one report mint it twice with
  `duplicateHeaders []` (E). Timeframe knobs as on any candle metric: `mktUp_4h` (abs), `mktUp_ltf` (rel lower),
  `mktUp_o1` (offset).
- **The eight CROWD_*_Z / _Z_LIVE** (family `crowdIntelligence`, timeless, oscillator): value and rank only, orderings
  hi / lo / far / near, `rankScope` report (a `scope` on the rank refused); hold `NOT_REWINDABLE`.
- **REGIME_WARNING_CRASH / _DIVERGENCE** (family `regime`, timeless, classification `raised` / `clear`): value only;
  trajectory and classifyZone refused; hold timeframe 4h.
- **PAR_DEV**: hint and vocabulary served (candle grid, percent, 12 transforms including relativeTo and classifyZone), but
  **no section subject reads it** - refused on an evaluated-coin section and on a market section alike (B.PAR_DEV.coin /
  .market, both `REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED`), and every D probe over it likewise. Its hint speaks of "a
  section bound to a stablecoin pair", which the 146.0.0 write schema does not expose. Kept in the corpus as measured,
  `subject` None.
- **On existing metrics**: CVD, CUM_VOLUME_DELTA and SPOT_CVD gained classifyZone (bullish / bearish / neutral, banded
  at 0; rendered); REGIME_STATE's vocabulary is now bull trend / bear trend / bull range / bear range / fallback;
  authoring text moved on classifyZone and relativeTo. The 2026-08-26 timeless-timeframe rule holds offline on the ten
  new timeless metrics (`data/audit/timeless_column_timeframe.json` regenerated, 143).
- **Gone from the surface**: `derive_strategy_rule_view` (signal rules left at contract 108), so the signal-membership
  probe of the earlier records cannot run; "membership" at 146 is the subject partition above.

Counts (`data/contract/_manifest.json`): 326 metrics, 11 families, 23 authorable transforms, 7,498 composability cells
of which 2,607 legal (34.8 %), 6,122 structural shapes, 115,035 operand-expanded.

## What OMEGA changed

- `omega.contract`: `Metric.subject` (`evaluated-coin` / `market` / None) read from `_subjects_146.json`
  (`metric_subjects()`, fails closed when the file is missing or a metric sits under two subjects).
- `omega.validate`: `SECTION_SUBJECT_METRIC_UNSUPPORTED` (a column whose metric the section's subject does not read,
  quoting the platform's wording) and `METRIC_NO_SUBJECT` (PAR_DEV); `METRIC_UNMEASURED` has nothing left to fire on.
- `omega.fanout`: the zone vocabulary read from `zone_vocabulary_146_2026-11-02.json` (the 144 measurement carried
  forward plus MKT_ABOVE_EMA, CVD, CUM_VOLUME_DELTA, SPOT_CVD).
- `scripts/sweep_render_coverage.py`: `SWEEP_MARKET_SCOPE`, `SWEEP_METRICS`; `scripts/render_coverage.py`: the two
  2026-11-02 sweep caches and the probe headers; a no-subject metric's shapes are outside the renderable space (the same
  reasoning as QUARANTINED). `scripts/probe_market_section_146.py` new.
- Data: 326 metric files rewritten (stamp 20261102; the 20261030 files archived), `_index.json`, `_moves_146.json`,
  `_subjects_146.json`, `_unmeasured_108.json` (empty, `history146`), `categories.json`, `templates/platform/_all.json`,
  `vocabulary/_shared.json` + `20261102T0555Z/`, `transforms/_authoring.json` and `_chain_outer_parameters.json`, the
  derived matrix / graph / type system, the manifest (144.0.0 block nested under `supersedes`).
- Tests: `tests/test_v146_1.py`; the pins moved in test_v146 (the three "unmeasured" tests now pin the history),
  test_condition_vocabulary_108, test_metric_vocabulary_108, test_write_surface, test_membership, test_against_compiler,
  test_space, test_space_validate_agreement (a no-subject metric is an expected refusal), test_render_coverage,
  test_spread_chain_operand, test_timeless_timeframe, test_v103_transform_entry, test_v144.

## Not done

- **80,639 operand-expanded spread pairs are unrendered** (80,806 at 144.0.0; the coin sweep rendered the CVD-family
  pairs). The same deliberate stop as 2026-10-30: re-mints of a pattern rendered thousands of times, hours of read-only
  renders.
- PAR_DEV renders nowhere; whether a "section bound to a stablecoin pair" exists on some other surface is not known.
  If a later contract exposes it, `_subjects_146.json` is the file to re-measure.
- The eight market scopes other than `crypto` were probed on `MKT_UP` x value only (C); the sweep ran at `crypto`. The
  header carries no scope token, so a scope changes the row, not the column.
- `docs/01` / `docs/02` are not regenerated (`build_docs.py` stale since September; a separate change).
- The manager pins v0.10.2; moving it to v0.11.0 is the manager's change, not this one. Nothing on the platform was
  bound, deployed, funded or saved.

## What a consumer must change (battlegrid-manager)

Re-pin to the tag that carries this record (v0.11.0). v0.10.2 refuses every column over the 24 as `METRIC_UNMEASURED`
and its `compare_vocabulary` reports them `storedUnmeasured`; v0.11.0 reads them as measured, and refuses a market metric
on a per-coin section (and a coin metric on a market section) the way the platform does. A section that names a
`marketScope` may carry MKT_* columns and nothing else.
