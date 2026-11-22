# OMEGA v0.17.0 at contract 184.3.2: nothing the model uses moved; a decision's prices are on the venue's grid

**Record, 2026-11-22.** Contract 184.3.2, build `8a695c4f` (`GET /mcp/version` read before and after every group of
calls below, 04:54:16Z first and 05:24:10Z last; 184.3.2 / 8a695c4f each time). Previous pin: v0.16.0 at 182.3.2. The
vendor README documents v183 (two output fields left the trade-level preview) and v184 (a radar refusal lost a detail;
`propose_entry_decision` and `get_trade_conversation` lost an error code neither served); 182.4.0, 184.1.x and 184.3.x
are read from battlegrid-manager's contract watch (its `docs/status/2026-11-21-contract-*.md`), the served schemas, the
hints and the probes.

**The result in one line:** no input schema, no draft tool, no metric, transform, operand list, vocabulary block or
modelled rule moved. Five glosses, one tool's description and output schema, one refusal's wording and what a decision
does with its prices did. The code change is docstrings and one constant.

Live record: `data/audit/reextraction_184_2026-11-22.json` (replayed by `tests/test_reextraction_184.py`). Corpus moves:
`data/contract/metrics/_moves_184.json`.

## What was measured, and how

Every tool call went through a long-lived mcporter runtime (`scripts/mcporter_runtime.mjs`, started by node with
`MCPORTER_DIST` naming the cached mcporter 0.17.1), serially, one request in flight. The surface list ran the same cached
package's CLI through a scratch `npx.cmd` first on `PATH` (it adds `--no-oauth`). The real `npx` did not run, nothing was
written to the npx cache, and no OAuth prompt appeared. Every time is the HOST's clock, read just before the call.

| Step | Tool, inputs | When (UTC) | Answer |
| --- | --- | --- | --- |
| Runtime check | one `list_strategy_drafts` | 04:54Z | the one VWAP Reject 15m draft |
| Write surface + authoring sidecar | `scripts/capture_write_surface.py` (one `mcporter list`, 167 tools) | 04:55Z | `schema_20261122T045517Z.json`, `authoring_tools_20261122T045517Z.json` |
| Hints | `scripts/refresh_metric_contracts.py`, `EXTRACTION_STAMP=20261122` | 04:55 - 05:04Z | 586 of 586, 0 failed; 5 records moved (glosses); the 182.3.2 batches archived as `archive_20261120_extraction` |
| Vocabulary | `scripts/snapshot_vocabulary.py` | 05:07Z | 13 categories answered, `levels` RESULT_TOO_LARGE (as before); `_shared.json` and `categories.json`: nothing moved; the same five glosses |
| Draft R | 26 stages into ONE new create draft `68e9d692`, 29 `preview_strategy_trade_levels` on seven coins | 05:08 - 05:12Z | the R:R cases, the stop range, levels at a decision, the level entry, the side warning; discarded at 26, read null |
| Proof | the `trend-continuation` preset body, a new create draft `8d07df2f` | 05:13 - 05:14Z | errors [] warnings []; read back equal; previewed; discarded at draftVersion 1, read null |
| Draft X | 7 stages into ONE new create draft `f7325af3`, 8 previews | 05:22 - 05:24Z | legs and stops nearer than a tick, runners, the wording of the minimum; discarded at 7, read null |

In all: 586 `get_metric_construction_hints`, 14 `list_strategy_vocabulary`, 1 `list_strategy_categories`, 1
`preview_strategy_report`, 38 `preview_strategy_trade_levels`, 34 `stage_strategy_draft` into three NEW create drafts, 3
`discard_strategy_draft` (those three), 6 `get_strategy_draft`, 7 `list_strategy_drafts`, one tool list. Nothing was
committed. No existing strategy or draft was touched: `list_strategy_drafts` before and after each draft showed the one
VWAP Reject 15m draft (`c1fd5d4c`, version 9, 2026-10-23), untouched. No agent, Radar, Arena, deployment, funding or
visibility tool was called.

## What the platform moved, item by item

1. **The six draft tools: nothing.** Every description, input schema, output schema and annotation is byte-identical to
   the 182.3.2 capture (`schema_20261120T142253Z.json`).
2. **The ten other authoring tools (their first diff): `preview_strategy_trade_levels` alone.** Its input schema and
   annotations are byte-identical; nine tools are byte-identical whole. What moved in it:
   - *output, removed* (README v183): `setups[].stopLossDistanceAtrMultiple` and
     `rejectedPairs[].slDistanceAtrMultiple`, both required before. No OMEGA source file names either.
   - *description*: the stop's ATR distance is stated once, on its stop row; refused pairs' ratio "stated to 3 decimals";
     and the price-grid sentences (the manager's watch saw them arrive at 184.3.1): "Every price is on the venue's price
     grid, rounded once the way its order rests - a stop toward entry, a target away from it, a resting entry away from
     the mark. Each pair's stop and target distances and the entry's distance from the mark are measured between those
     grid prices and stated to 4 decimals; a stop row's distance is its option's own figure."
   - *field descriptions*: `entryLevel.stage`, `rejectedTakeProfits[].stage`, `stopCandidates[].verdict` and
     `stopBand.requestedMaxPct` reworded; `rejectedPairs`, `rejectedPairs[].reason`, `rejectedPairs[].computedRR` and
     `rejectedTakeProfits[].price` gained one; the `rejectedPairs` row's own went. A verdict names the dial that
     recovers it. A nearest level (a zone edge or midpoint, a pool, a naked POC, a single print) "looks past its own pick
     to the next of its kind" and is refused only when none sits there; seen on SOL (draft R): the naked POC above read
     70.603 at the 69.185 market entry and 72.664 with the short resting at 71.443.
3. **The hints: five glosses.** SPOT_AVG_TRADE, SPOT_CLOSE_BN, SPOT_CLOSE_CB, SPOT_CVD and SPOT_DOMINANCE: "this coin's
   own unit" became "the unit the coin's perp is quoted in (Hyperliquid's kPEPE is 1,000 PEPE)". The other 581 records
   are equal, and so is every derived artefact `scripts/build_corpus.py` writes (`composability_matrix.csv`,
   `spread_operand_graph.json`, `platform_privileged.json`, `type_system.json`). Roster 586, the same names. Counts as
   at 182.3.2: 27,424 structural shapes, 515,965 operand-expanded.
4. **The vocabulary: the same five glosses.** Every category-invariant block and every category count as stored.
5. **The stage's refusal words the minimum to two decimals** (undocumented; arrived between 182.3.2 and 184.3.2): "below
   this strategy's minimum risk-reward of 1.50" where the same body drew "of 1.5" ("of 1.00", "of 2.00": X5, X6). No
   verdict moved with it. OMEGA quotes the platform's sentence in no rule.
6. **At a decision, prices are on the grid** (item 2's sentence). Measured on drafts R and X, previews on BTC, ETH, SOL,
   DOGE, XRP, kPEPE and PUMP, all fitting one reading:
   - *rounding*: 235 stop prices (214 ATR, 21 level) lie on the grid, rounded toward entry by less than a tick; 380 R
     target legs away from it, each R times the distance to the ROUNDED stop; 8 resting entries away from the mark. An
     at-market entry is the mark as it stands and is not on the grid (BTC 59073.8 beside whole-dollar stops).
   - *distances*: a pair's `stopLossDistancePct` / `takeProfitDistancePct` are between grid prices to 4 decimals (273
     setups); a stop row's `distancePct` is its grid price's distance in full; a level entry's `distancePct` is to 4
     decimals and its `distanceAtr` in full.
   - *a setup is one set of prices*: two plans at one set of prices are one setup with both under `exitPlans` (28 rows;
     K1 on BTC makes 2 setups a side where 182.3.2 made 4), two surviving stops at one price one setup with both under
     `stopLossMethods` (0.8 and 0.801 ATR on PUMP: X2). The output schema already had both lists.
   - *a new way to lose a pair*: two R legs of one plan that price at one tick are refused TARGETS_OUT_OF_ORDER at that
     decision, though the stage accepts the plan: 1.5R 50% + 1.5001R 50% stages clean and survives on BTC (59890 and
     59891), and on kPEPE is refused, computedRR 1.5 (X1). Whether 182.3.2 did the same was not measured.

## The questions asked of this pass

**Do the modelled R:R rules (`stated_rr`, `plan_pays_double`, the exit-plan minimum) hold? Yes, at the stage and at a
decision; no answer moved.**

| Case (sent verbatim from the 182.3.2 record) | Minimum | Stage answer at 184.3.2 | At a decision |
| --- | --- | --- | --- |
| K1 2.2496R; K3 1.4995R; A 2.2495R; B 2.4995R; D6 2.7495R; D7 2.9995R; D8 0.4995R | 2.25; 1.5; 2.25; 2.5; 2.75; 3; 0.5 | errors [] warnings [] (as at 182.3.2) | every setup states the minimum |
| C 1R 50% + 1.999R 50%; D2 0.1R 50% + 2.899R 50%; G5 1R 50% + 1.9992R 50%; T4 1.49996R | 1.5 | errors [] warnings [] (as at 182.3.2) | C, D2, G5: every setup 1.5; T4 not previewed |
| D3 1R 30% + 2.785R 70%; D4 0.9R 80% + 1.3975R 20% | 2.25; 1 | errors [] warnings [] (as at 182.3.2) | every setup 2.25; 1 |
| D1 0.8R 50% + 2.199R 50%; G4 1.49949R; G6 1R 50% + 1.9988R 50% | 1.5 | "The LONG exit plan pays 1.499R, below this strategy's minimum risk-reward of 1.50: every pair it makes would be refused. Change the plan or lower the minimum." | not previewed |
| K2 2.2494R | 2.25 | "The LONG exit plan pays 2.249R, below this strategy's minimum risk-reward of 2.25: ..." | not previewed |
| D5 2.55R 70% + 3.215R 30% | 2.75 | "The LONG exit plan pays 2.749R, below this strategy's minimum risk-reward of 2.75: ..." | not previewed |

The stage knows no price. At a decision a pair's `riskRewardRatio` is still the plan's own arithmetic: an R leg pays its
own multiple and not the ratio of the rounded prices (on 56 of 301 plans the two differ: PUMP at ATR 1 states 1.5 where
the prices make 1.512), and a LEVEL leg pays the R between the grid prices (BTC 3.157; against the unrounded stop it is
3.154); a runner rides at that R of the last leg that closes a share (X3, X4; the trail objective's 6R trails 2.7R = 6 x
the 45% giveback, as at 171.0.0). All 301 plans of the 273 setups and all eleven refused pairs' `computedRR` equal
`stated_rr(plan_pays_double(legs, level_r))`. Rounding a stop toward entry and a target away from it can only raise the
ratio of prices, so no pair is lost to it.

**The stop range on SOL.** 0.8 - 1.8 with ATR 0.5 / 0.79 / 0.8 / 1 / 1.5 / 1.8 / 1.81 / 2 (G1 again, seven coins, both
directions): 0.5 and 0.79 BELOW_FLOOR, 0.8 - 1.8 SURVIVED, 1.81 and 2 ABOVE_CEILING, as before. SOL's 0.8 stop reads
`distancePct` 0.8530326031952626 against a floor of 0.8543510272536688 and survives - now by the grid, and on all seven
coins; the 1.8 stop's distance lies under the ceiling everywhere (1.921492084146617 against 1.9222898113207547), so the
other half of the 182.3.2 case cannot occur any more. The sharper case: on kPEPE and PUMP 0.79 and 0.8 are ONE price and
ONE `distancePct` (kPEPE 0.003292, 1.1708195737016032) and read BELOW_FLOOR and SURVIVED; 1.81 reads ABOVE_CEILING at the
price 1.8 survives at, its distance (2.6718703092164544) under the threshold it is refused by (2.6737916541579105).
`outside_stop_range` compares the multiples as written: 214 of 214 ATR stops.

**Are `stopCandidates` distances still the option's own figure?** `distanceAtrMultiple`: yes, an ATR option's is its
multiple exactly (214 of 214). `distancePct`: no longer the multiple x ATR% (0.7951998846186452 for 0.8 x 0.9939998557732999
at 182.3.2); it is the grid price's distance (BTC 0.8178262415550551 where 0.8 x ATR% is 0.8186119050982916). A LEVEL stop's
two distances are its grid price's, not its `levelReading`'s. OMEGA reads none of them.

**The side warning** (not asked, modelled): F4 (Donchian) and a nearest level (N1: NAKED_POC_BELOW / ABOVE under
STOP_THROUGH_LEVEL) warn word for word as `entry_side_findings` draws it; F1, F2 and N2 do not.

## The proof

`omega.generate.plan(PRESETS["trend-continuation"]).axes()` (all eight axes, `bodySha256` `0d0160c1...`, the same body as
the 182.3.2 proof) staged as a new create draft (`8d07df2f`): errors [], warnings []. Read back through
`get_strategy_draft`: equal to the sent body as values (`93d0f8c6...`, as at 182.3.2; 10.0 read back 10). Previewed on the
DRAFT: three sections rendered on BTC and ETH, no missing condition column, no duplicate header;
`preview_strategy_trade_levels` on BTC: three ATR stops SURVIVED, nine setups per direction, R:R 1.5 / 2 / 3. Discarded at
draftVersion 1, read null.

## What changed in the repository

- Corpus: the two captures, 586 records re-read, the vocabulary snapshot, the manifest (182.3.2 under `supersedes`),
  `_moves_184.json`, the audit record, `data/derived/condition_vocabulary_108.json` (its source block only).
- `omega/trade_levels.py`: the 184.3.2 section of the module docstring, three docstring sentences, and the constant
  `GRID_PROBES`. No function changed.
- `docs/02-transform-layer.md` regenerated (it names the capture and its contract); `docs/01` regenerated unchanged.
- Tests: `tests/test_reextraction_184.py`; eleven test files that pin the manifest, the captures or the version moved
  as they did for 182; `tests/test_reextraction_182.py` reads its blocks by version from here on.
- `pyproject.toml`: 0.17.0.

## What the manager's `manager/authoring` uses

Nothing it imports was removed or changed signature or behaviour: `Thesis`, `validate_thesis`, `brief`, `plan` / `axes()` /
`axes_update()` / `preview_request()`, `body_sha256`, `outputs_for`, `Column`, `load().platform_templates`,
`header_since_123`, `PRESETS`, `plan_pays`, `vocabulary`, `wilson_interval`, `MIN_SAMPLE`, `NO_ENTRY_CONDITION` (the import
statements of `manager/` were listed again this day: the same names). The manifest keeps `servedContractVersion`,
`extractedOn`, `counts` and `writeSurface.{servedContractVersion, buildSha, schema}` (now 184.3.2 / 8a695c4f /
`schema_20261122T045517Z.json`). `compare_vocabulary`'s stored capture is that file; the enums it compares did not move. One
new name: `omega.trade_levels.GRID_PROBES`.

For the manager's own reading of a preview (`manager/risk/trade_levels.py`), from item 6: a setup may list two
`exitPlans` or two `stopLossMethods` far more often than before (its card lists a merged row apart and matches any of its
methods), and a pair's price joins its stop row's price exactly (every priced setup here did).

## Not measured

- Which contract between 182.4.0 and 184.3.2 moved the refusal's wording, and whether the two-decimal minimum rounds an
  off-step value (an off-step minimum is refused on its own account).
- The grid itself: the price step of each coin was taken from the prices served (seven coins), not from a served field;
  nothing in OMEGA uses it. A coin whose step changes inside a preview's range of prices was not seen.
- Whether two R legs at one price were refused before the grid (item 6). OMEGA does not warn on near-equal R legs: the
  tick is the coin's, and no threshold was measured. A level leg and an R leg at one tick, two level legs at one tick,
  and a TARGET_LEG_BELOW_ORDER_FLOOR (never served by the preview) were not probed.
- What a merged setup states when its two plans' stated R:R differ: all 28 merged rows' two plans state the same three
  decimals.
- R:R at an exact tie through a runner's share or more than two closing legs: unmeasured as at 182.3.2
  (`TRADE_MENU_EXIT_PLAN_RR_TIE_UNMEASURED` stands). Draft R replayed one- and two-leg ties only. Of the 418
  side-sweep metrics six were staged again (BB, Donchian, the naked POCs); the seven v181 refusals, the rungs of the nine main candles and v182's output shapes were not re-run (no schema,
  hint or vocabulary they rest on moved).
- PERCENT stops, a `bufferAtrMultiple` other than 0, EITHER_SIDE_OF_LEVEL and a WRONG_SIDE entry at a decision on the grid.
- Everything 182.3.2 listed and this pass did not touch: the cadence, hold ceilings and chain depths at 30m, 2h, 8h, 12h
  and 1d; an entry level reference that is not plain; `levelOffsetAtrMultiple` other than 0.2; a warning beside an entry
  level error; a sequence step over a Developing read; the unrendered 462,135 operand-expanded pairs (the deliberate stop
  since 144). No structural shape moved, so no sweep was run.
- battlegrid-manager's stored `manager_schemas` row was not compared with the capture (no MANAGER_ROW was passed).
- The vendor README's v184 narrowings (`stage_radar_deployment_draft` and three more) concern tools OMEGA does not capture.

## Outside the repository

The mcporter credential was refreshed by the runtime's own token refresh at the first call (no interactive step). The
probe scripts, the `npx.cmd` shim and the raw call logs are session scratch, not in the repository; what they measured is in
the audit file, the trade level answers verbatim.
