# OMEGA v0.13.0 at contract 168.3.0: the author defines the trade levels

**Record, 2026-11-11.** Contract 168.3.0, build `af8b2c96` (`GET /mcp/version`, read before, during and after every
live step). Previous pin: v0.12.2 at 161.0.0. Contracts 157 - 168 are not in the vendor README (newest entry v156), so
the served schemas and hints are the source throughout.

## What the platform moved

| Move | Where OMEGA holds it |
| --- | --- |
| `stage_strategy_draft` REQUIRES `TRADE_LEVEL_POLICY.tradeLevelMenu`: per direction 1 - 8 stops (ATR / LEVEL / PERCENT) and 1 - 8 targets (R_MULTIPLE / LEVEL); a level-triggered entry REQUIRES `entry.levels` | `omega/trade_levels.py`, `StrategyPlan.axes()` / `axes_update()` |
| a metric is named by pattern; the roster left the write schema | `omega/condition_vocabulary.py`: the roster is `get_strategy` outputSchema `$defs/metricKey` (581) |
| 47 metric keys added, none retired; 347 metrics re-homed into the new `channels`, `vwapProfile`, `levels` categories | `data/contract/metrics/`, `_moves_168.json` |
| hint shape: operand lists served once per response (`operandSets`) and named by id | `scripts/refresh_metric_contracts.py` `operand_list` |
| three column knobs: `supplyDemandThreshold`, `supplyDemandResolution`, `usedUpOnClose` | `omega/types.py`; spellings in `omega/fanout.py` (`_vt10.5`, `_res51`, both `_vt10.5res51`, `_close`) |
| `spread` as a chain outer after `aggregate` / `ema` / `rma` / `wma`; a spread operand under an average; the group op `SEQUENCE` | recorded, NOT modelled: `data/contract/metrics/_unmeasured_108.json` |
| served text: `bars` unset reads Confirmed at every timeframe; `nearestZoneDist` is measured from the zone's near edge, 0 inside it | `data/contract/transforms/_authoring.json` |

## What was measured, and how

1. **Hints**, 581 of 581, 21:24 - 21:36Z, over ONE mcporter runtime (`EXTRACTION_TRANSPORT=runtime`,
   `scripts/mcporter_runtime.mjs`): 13 minutes with the corpus build. The first read of the day, through the CLI at
   168.2.0, took 162 minutes for 240 hints and stopped when 168.3.0 deployed under it; nothing of it is in the corpus.
   235 of 235 hints read by both transports are identical.
2. **Write surface**, 21:32Z: `scripts/capture_write_surface.py`; the six draft tools equal battlegrid-manager's stored
   168.3.0 row and the 168.2.0 capture of 18:32Z byte for byte.
3. **The menu's rules**, which the tool description does not state: 30 create drafts (15 at 168.2.0, 15 at 168.3.0),
   each staged, read back and discarded, none committed (`data/audit/trade_level_menu_168_2026-11-11.json`; replayed
   one by one in `tests/test_trade_level_menu_168.py`). The last nine isolate what the first 21 confounded.
   - ATR stops and R targets stage on any report. An R target below `minRiskRewardRatio` is refused.
   - A LEVEL must be a price metric that a per-coin custom section holds as a reading: the same metric at the same
     timeframe, knobs and offset. The transform does not matter; a spread yields its base and its plain operand.
     `{abs: <anchor>}` equals `{rel: anchor}` both ways; another timeframe matches like for like. The level's
     `bars` unset equals `closed` and matches a column whatever its own bars are; a level asking `all` against a
     column that does not is refused.
   - One level cannot be a stop and a target of one direction. More than eight entries is refused at input.
   - Not judged at stage: an ATR stop outside the strategy's stop range, a repeated entry.
   - The menu's shape is judged by walking it against the write schema itself, so nothing about shape is re-typed.
4. **Vocabulary**, 22:32Z: 13 categories answered, `levels` refused RESULT_TOO_LARGE (stored as its refusal); the
   shared blocks and the 22 platform templates are as stored.
5. **Structural coverage sweep**, 22:19 - 22:20Z: 557 shapes, 673 headers, 0 refusals, 0 mispredicted
   (`data/audit/coverage_sweep_2026-11-11.json`), and a non-spread pass over the three remaining expansions at 23:25Z.
   Structural coverage 23,579 / 23,579; every unrendered expansion is a spread operand pair.
6. **Knob spellings**, 23:29 - 23:30Z: the 85 served (metric, knob) cells 168 opened, 88 columns, 0 refusals
   (`data/audit/knob_spelling_probe_168_2026-11-11-{a,b,c}.json`). The known knobs spell on the added keys as on the old
   ones; the two supply / demand knobs share one token when both are off. 191 of 191 served cells are rendered.
7. **The timeless rule** on the added timeless metrics, 23:34Z: six previews
   (`data/audit/timeless_column_timeframe.json`): refused off the anchor with the 2026-08-26 wording; HIGH_DEV and
   LOW_DEV, served `candle` at 168, now render off it.

## What a plan stages now

Every preset stages the ATR / R part of the platform's own migration default: stops ATR 1 / 1.5 / 2, targets R 1.5 / 2
/ 3 from the thesis's `minRiskRewardRatio` up (read from three live strategies; their band LEVEL entries are left out
because they stage only on a report that reads the bands). A thesis can name its own menu (`Thesis.trade_level_menu`).

An UPDATE stages `TRADE_LEVEL_POLICY` only when the thesis names one of its dials or a menu, and then carries the live
strategy's menu verbatim. A live strategy's migrated menu names the Donchian and Bollinger bands whatever its report
reads, so restaging the axis is refused unless the report reads them: `StrategyPlan.update_menu_findings(current)`
says so offline.

## Not measured, refused offline

- the chained `spread` (TRANSFORM_UNMEASURED; in no enumerated shape);
- a spread operand under an average (`omega.types.Operand` admits `metric` alone);
- `SEQUENCE` (not a group `omega.conditions` builds or accepts; the schema states no semantics for it);
- on a menu level: a `windowExtreme`; `bars: "all"` where a column also reads `all`; a metric the report holds only
  in a market, reference or platform section, or only as the operand of a spread with a knob, an offset or an average
  (TRADE_MENU_LEVEL_UNMEASURED);
- whether a stage that omits TRADE_LEVEL_POLICY re-judges the live menu against a restaged REPORT (every probe was a
  create; `update_menu_findings` warns);
- what a decision does with an ATR stop outside the strategy's stop range (a warning).

Measuring these is the next release's authoring probe.

**After the last measurement** (00:24Z on 2026-11-12, still 168.3.0) the platform deployed 168.4.0 (build `ec7fb906`, observed by the battlegrid-manager watch at 00:32Z): one read tool added, `preview_strategy_trade_levels`; no tool changed or removed, so the six draft tools this release mirrors are as captured. The new tool is not extracted here.

## The independent review (2026-11-12)

A fresh reader went through the branch before the release. Fixed from it: the menu validator accepted readings no probe
had measured (nine more drafts measured them, and the rest is refused); malformed menus slipped through or raised (the
write schema judges shape now); the roster check missed a metric reached through a union arm or a `$ref` chain, used
Python's `$` and Unicode `\d` where the platform's regex differs, and passed NaN; the command line gave no roster to
a `parameters`-shaped definition and now warns when none applies; an operand set that is not a list, an operand-set id
left unresolved and a hint for another metric each stop the corpus build; the surface capture claims agreement only
over all six tools. On the manager side the menu's findings are structured checks, per operation.

## Found while re-pinning

At 168 the offline schema walk no longer refused a metric key the platform does not serve: the write schema names a
metric by pattern, and the walker reported every pattern as unchecked. `omega.preflight` now judges a plain pattern
(PATTERN) and checks every pattern-named metric against the read schema's roster (ENUM, `read_roster`); a walk given no
roster says the key was not checked.
