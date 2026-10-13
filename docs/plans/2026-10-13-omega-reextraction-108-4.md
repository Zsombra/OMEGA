# The metric corpus re-extracted at contract 108.4.0 — record

**Status: DONE 2026-10-13** on branch `feat/reextract-108-4`. Baseline main (v0.5.3 + a docs merge): 1443 passed; after: **1444 passed**.

## Authorization and route

- The user, 2026-10-13: "ok aiprove all continu" in answer to a list whose item 1 was the read-only reads
  (`get_metric_construction_hints` for the 15 metrics, `get_strategy_column_contract` for `levelInteraction`, the
  previews, `list_strategy_vocabulary`). Every call below is a read; none stages, commits, binds or trades.
- The in-app BattleGrid connector was disconnected, so every call went over the `mcporter` CLI to `battlegrid-anbu` (the
  same server and account; doc 23), through a read-only allowlist (`scratchpad/bg.py`), raw responses saved before any
  parsing.
- Served contract at the start: **108.4.0**, build `21747aa97f06d537ac8cf7b85356d737d223abc4`
  (`GET /mcp/version`, 2026-10-13T03:05:58Z). battlegrid-manager's watch auto-acknowledged it at 03:08:31Z: seven
  tools changed, none of the six strategy-draft tools — so the saved 108.0.0 write surface still stands.

## Why a full re-extraction, not 15 metrics

The first 15 reads were the plan. Three spot checks of metrics already in the 61.2.0 corpus (CLOSE, BB_UPPER, RSI14)
then disagreed with it:

| metric | 61.2.0 corpus | live 108.4.0 |
|---|---|---|
| CLOSE | `distance` / `spread` chain into `[trajectory, aggregate, efficiency]`; `bandTouch` | chain into `[trajectory, aggregate]`; no `bandTouch` |
| BB_UPPER | as CLOSE | as CLOSE, plus **`levelInteraction`** |
| RSI14 | `efficiency` offered; `spread` chains into `efficiency` | no `efficiency`; `spread` chains into `[trajectory, aggregate]` |
| spread pools | 61 (price), 16 (oscillator) | 66, 17 |

So omega would accept columns the platform now refuses, and `levelInteraction` admissibility is served per metric by
the same tool. Re-reading all 171 is the same read, at the same rate limit, and the only way to know what else moved.

## Procedure (the 61.2.0 one, `2d3ec2e`, made portable)

1. `get_metric_construction_hints` × 171, verbatim, to `scratchpad/live/hints_all/` (two resumable workers).
2. `scripts/refresh_metric_contracts.py` (root from its own path; stamp, scratch and archive stamp required; roster from
   the derived 108 enum) writes the per-metric files, archives the 61.2.0 batches, writes new batches in platform order,
   refreshes the transform catalogue if — and only if — every authoring block is invariant.
3. `scripts/build_corpus.py` (its `METRIC_ENUM` now derived, not typed) regenerates the index, matrix, spread graph,
   privileged set and type system.
4. `list_strategy_categories` + `list_strategy_vocabulary` × 10 families: the family counts and the served budgets.
5. The render-coverage sweep over every shape the corpus newly enumerates (`scripts/sweep_render_coverage.py`, fixed for
   the v85 request shape and the v92 `authoring.conditionColumns` read).

## Results

**Reads:** 171 × `get_metric_construction_hints` (0 failed), `list_strategy_categories`, 10 × `list_strategy_vocabulary`,
3 × `get_strategy_column_contract` (levelInteraction), ~25 × `preview_strategy_report` (the sweep, incl. bisections).
Raw: `data/contract/metrics/_batch01-06.json` (the 61.2.0 batches archived to `archive_20260920_extraction/`),
`data/contract/vocabulary/20261013T0337Z/`, `data/contract/columns/levelInteraction_108_4_2026-10-13.json`,
`data/contract/columns/_coverage_sweep_2026-10-13.json` + `data/audit/coverage_sweep_2026-10-13.json`.

| | 61.2.0 (2026-09-20) | 108.4.0 (2026-10-13) |
|---|---|---|
| metrics | 156 | **171** (the 15 v100/v101.1 metrics, now measured; `_unmeasured_108.json` empty) |
| served transforms | 16 incl. `bandTouch` | 16 incl. **`levelInteraction`** (on 43 levels), no `bandTouch` |
| legal cells | 681 (bandTouch's 62 out on 10-12: 619) | **670** = 619 + 42 new-metric cells + 41 levelInteraction − 30 efficiency − 1 maxShare (BB_PCT_B) − 1 spread (SPOT_CVD) |
| chain successors of distance/spread | trajectory, aggregate, efficiency (+rank) | **trajectory, aggregate** (+rank) |
| structural / operand-expanded shapes | 982 / 8,429 (10-12: 920 / 8,367) | **899 / 8,575** |
| render coverage | complete | **complete**: 1,394 new shapes rendered, 2,672 headers, 0 refusals, 0 mispredicted |

**What moved, and what omega now does about it**

- **`efficiency` left the bounded oscillators and pressure ratios** (RSI14, BUY_PRESSURE and 28 more) and every
  `distance` / `spread` chain. omega refuses those columns (the pair or chain is no longer offered). No preset used one.
- **`levelInteraction` is extracted**: offered on 43 levels (the changelog's list plus the two swing fractals), refused on
  the price facts, TPO developing levels, naked POCs and Donchian rails exactly as README v100 says. Header measured live:
  `{code}{infix}_lvl` (+ `_b<buffer>`), classification, five labels, operators `is in enters exits`;
  `omega.fanout` predicts it and the sweep confirmed all 43.
- **A parameter's `maximum` is served per metric.** `value.offset` max is 31 on most candle metrics, 30/21/12/11 on the
  bar-geometry ones and 0 on a timeless one; series windows max 32. The transform catalogue's invariance claim held only
  once the maxima were set apart, so they live on each metric's transform entry (`maximums`) and `omega.validate`
  reads them. **This supersedes the 2026-08-26 24-bar floor (usable offset 8)**: offsets 9–31 on a candle `value`
  column are legal at 108.4. The floor stays as the fallback for a record without a served maximum.
- **The v103 shape arrived**: no transform entry carries `operandRequired` / `sideRequired`; v0.5.1 had already moved
  the requirement onto the catalogue, so nothing went silent.
- **`list_strategy_vocabulary`**: budgets unchanged; the served transform list replaced `bandTouch` with
  `levelInteraction`; **`conditionGrammar.maxGroupDepth` is 2** - the depth warning now cites the served value.
- **SPOT_CVD lost `spread`** and left CVD's operand pool; three census families were re-specified (`supersedes` kept):
  `scale-dependent-efficiency`, `flow-toxicity`, `perp-spot-cvd`.
- **Two script defects fixed on the way**: `sweep_render_coverage.py` still sent the compile-era preview request and read
  the pre-v92 top-level `conditionColumns` (it would have reported every shape unrendered); `refresh_metric_contracts.py`
  hard-coded a deleted worktree and wrote no batches.

**Not re-read** (each still a read, none needed for this slice): the 25 platform section templates
(`templates/platform/_all.json`, 61.2.0-era); the per-header operators and hold domain on a detailed preview of the
presets' own headers (the 2026-10-06 M2 read is the latest).
