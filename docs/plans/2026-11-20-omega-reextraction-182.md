# OMEGA v0.16.0 at contract 182.3.2: v181 served, R:R at three decimals, the side of an entry level

**Record, 2026-11-20.** Contract 182.3.2, build `b3969d0b` (`GET /mcp/version` read before and after every group of
calls below, 13:59:10Z first and 16:12:26Z last, and again around the review-fix draft, 18:40:43Z and 18:43:15Z;
182.3.2 / b3969d0b each time). battlegrid-manager's watch first saw
182.3.1 (build `86d5b983`) at 03:52Z and 182.3.2 at 13:32Z, with no tool it watches moved between the two. Previous
pin: v0.15.0 at 180.4.0. The vendor README documents v181 and v182; 182.1 - 182.3.2 are read from the served schemas,
the hints, the manager's drift events and the probes. One open PR on the vendor repository (#286, a skills export at
182.3.2): nothing announced that is not served.

Live record: `data/audit/reextraction_182_2026-11-20.json`, and the side sweep's 418 stage answers in
`data/audit/reextraction_182_side_sweep_2026-11-20.json` (both replayed by `tests/test_reextraction_182.py`). Corpus
moves: `data/contract/metrics/_moves_182.json`.

An independent review of the first pass found seven items; what each changed is under "Review fixes" below, and the
sections here are written as they stand after them.

## What was measured, and how

Every call but one went through a long-lived mcporter runtime (`scripts/mcporter_runtime.mjs`), serially, one request
in flight (the Ties row through a runtime started for it, after one `list_strategy_drafts` at 18:40:17Z to see it
start). Every time in the table and in the record is the HOST's clock, read just before the call; the sweep's logs show it at least
2.45 s ahead of the platform's (a stage's own `updatedAt` is up to 2.451 s earlier than the host instant read before
the stage was sent).

| Step | Tool, inputs | When (UTC) | Answer |
| --- | --- | --- | --- |
| Write surface | `scripts/capture_write_surface.py` (mcporter list, 167 tools) | 14:22Z | `schema_20261120T142253Z.json`; against the 180.4.0 capture only `preview_strategy_report.outputSchema` moved |
| Authoring tools | `capture_write_surface.py --authoring-only` (a second list) | 16:10Z | `authoring_tools_20261120T161029Z.json`: ten tools OMEGA never captured before; its six draft tools equal the 14:22Z capture's |
| Hints | `scripts/refresh_metric_contracts.py`, `EXTRACTION_STAMP=20261120` | 14:24 - 14:35Z | 586 of 586, 0 failed; 416 records moved, all of them v181's narrowing; the 180.4.0 batches archived as `archive_20261119b_extraction` |
| Vocabulary | `scripts/snapshot_vocabulary.py` | 14:35 - 14:36Z | 13 categories answered, `levels` RESULT_TOO_LARGE (as before); `_shared.json` and `categories.json`: nothing moved; one study gloss reworded (`momentum`) |
| A1 - A7, B, C, D | `preview_strategy_report`, BTC 4h, 24 previews | 13:59 - 14:00Z | v181: the refused forms, which prices are reference prices, the kept forms |
| H1 - H8 | `preview_strategy_report`, BTC 4h, 8 previews | 15:32Z | spreads chained around a reference price |
| V182 | `preview_strategy_report`, BTC + ETH 1h, detailed and concise | 14:36 - 14:37Z | `developingAsOf`, `asOf`, the inventory's `developingRead` |
| TF | `preview_strategy_report`, BTC, 13 timeframes | 14:38 - 14:39Z | the regime and lower rungs and seven columns' headers at the nine main candles; 1m, 3m, 3d, 1w refused |
| Draft E | 21 `stage_strategy_draft` into ONE new create draft `e2e843b9` | 14:42 - 14:44Z | when ENTRY_LEVEL_USUALLY_SKIPPED fires; R:R at three decimals; discarded at draftVersion 21, read null |
| Draft L | 18 stages into ONE new create draft `6848fb50`, 10 `preview_strategy_trade_levels` | 14:45 - 14:48Z | the level entry at a decision, the stop bounds on BTC / ETH / SOL, R:R; discarded at 18, read null |
| Draft S | 26 + 394 stages into two new create drafts (`8c48af82`, `6f2e32ee`) | 14:52 - 14:57Z, 15:33 - 16:09Z | the side sweep: all 418 price-unit level metrics, 24 answered on the first draft and 394 on the second; discarded at 26 and 394, each read null |
| COV | `preview_strategy_report`, BTC 4h | 16:20Z | the four operand-expanded shapes the narrowed hints opened, rendered as `omega.space` writes them |
| Proof | the `trend-continuation` preset body, a new create draft `68dc2339` | 16:11 - 16:12Z | errors [] warnings []; read back equal; previewed; discarded at draftVersion 1, read null |
| Ties | 15 stages into ONE new create draft `df02fef7`, 11 `preview_strategy_trade_levels` (BTC) | 18:40 - 18:43Z | R:R at an exact tie: 14 plans, 11 staged clean and 3 refused; read back at 15, discarded at 15, read null |

In all: 50 `preview_strategy_report`, 30 `preview_strategy_trade_levels`, 475 `stage_strategy_draft` into six NEW
create drafts (474 answers read: see Draft S below), 6 `discard_strategy_draft` (those six), 15 `get_strategy_draft`,
13 `list_strategy_drafts`. Nothing was committed. No existing strategy or draft was touched: `list_strategy_drafts`
before and after each draft showed the one VWAP Reject 15m draft (`c1fd5d4c`, version 9, 2026-10-23), untouched. No
agent, Radar, Arena, deployment, funding or visibility tool was called. One preview (A1's column) went through the
session's own connector at 13:54Z before the runtime was used; a group of previews at 14:59Z was not sent (the local
runtime did not start) and ran at 15:32Z.

**Draft S, as the probe's logs show it.** The first run staged one report reading all 418 levels (clean) and then one
ENTRY restage per metric; it was stopped after 24 metrics (ASIA_HIGH .. EMA8). The last answer it read stated version
25; `list_strategy_drafts` then stated version 26, so one more stage - by the script's order the next metric, EMA9 -
reached the platform as the run was stopped, and its answer was never read: **26 stages, 25 answers, 24 metrics**. The
draft was discarded at 26. The second run staged the other **394 metrics in 394 stages** (the first carried the whole
body and EMA9 again; the first of each batch of 30 carried the report that reads the batch) and was discarded at 394.
24 + 394 = 418. The first pass of this record said "25 + 394 stages" and kept only the sweep's three lists; the 418
stage answers were on disk in the probe's raw logs and are now in the repository.

## What the platform moved, item by item

1. **v181, served: price is the base of every spread over another reading.**
   - *The refusal* (A1 - A4, H4, H5, H7): `PRIOR_TPO_VAL x spread(CLOSE)`, `EMA20 x spread(CLOSE)`,
     `EMA20 x spread(LAST)`, `HL2 x ema(34) -> spread(CLOSE)` and three more are each `VALIDATION_ERROR` /
     `REPORT_COLUMN_OPERAND_UNSUPPORTED` on `sections[0].columns[0].inputs[0].metric`: "'close' is a reference price,
     and a spread comparing it with 'EMA20' takes it as the base, so price above the reading reads positive; write
     CLOSE x spread(EMA20)". Off the anchor rung the sentence names the form only where the server admits it: at
     `{abs: 1d}` it does for `EMA20 x spread(CLOSE)` (A5) and names none for `PRIOR_TPO_VAL` (A6, a session-profile
     level) or for `LAST` (A7). OMEGA's finding tells the same three cases apart from the corpus.
   - *The reference prices are CLOSE and LAST and no other price.* MARK, ORACLE, OPEN, HIGH, LOW, HL2, HLC3, OHLC4,
     SPOT_CLOSE_CB and SPOT_CLOSE_BN each render as EMA20's plain operand (B), and MARK, ORACLE, OPEN, HIGH, LOW and
     HL2 are each refused as the *base* of a spread over CLOSE (D): a price that is not a reference price is "another
     reading". The served text now names the set too (`spread`'s `inputs`: "never a reference price (CLOSE, LAST)
     unless the base is one"). v0.15.0's `{CLOSE, LAST}`, taken from the README, stands, measured.
   - *Kept* (C): `CLOSE x spread(LAST)`, `LAST x spread(CLOSE)`, an averaged price operand, price as the base.
   - *The base decides, averaged or not* (H1 - H3, COV): `CLOSE x ema(34) -> spread(LAST)` renders
     (`close_ema34_last_spread`), as do the aggregate, wma and rma chains and the `{abs: 1d}` one. v0.15.0 had read the
     README's one example (`HL2 x ema(34) x spread(CLOSE)`) as "an averaged base is never a reference price" and
     refused these; `price_operand_refused` no longer does, and `omega.space` holds the four shapes (515,961 ->
     515,965 operand-expanded; structural 27,424 unchanged).
   - *The hints carry the rule*: CLOSE and LAST left `spreadOperands` and `spreadOperandsOffAnchor` of all 416 other
     price bases, and every chained spread's operand lists; nothing else in any hint moved (`_moves_182.json`). So
     `omega.validate` refuses the form from extracted data, as v0.15.0 said it would: `OPERAND_NOT_ALLOWED`, an error,
     with the v181 sentence and the form to write. The rule's own finding (`REPORT_COLUMN_OPERAND_UNSUPPORTED`, a
     warning below contract 181, an error from it) remains only for a corpus that still serves the operand.
   - The spread pools are no longer symmetric: 832 one-way edges, every one from CLOSE or LAST
     (`data/derived/spread_operand_graph.json`; `docs/02`'s sentence is generated from them).
2. **v182, a Developing read states when it was read.** The only schema move of the six draft tools:
   `preview_strategy_report`'s output. A condition outcome lost `developingRead` and requires `developingAsOf` (an ISO
   instant or null); a rendered column gained an optional `asOf`. Measured (V182): outcomes over `RSI14_4h_dev` read
   `developingAsOf` `2026-11-20T14:37:00.000Z`; over a closed higher-timeframe column, an anchor column and `chg4h`
   they read null (`chg4h`'s inventory entry still says `developingRead: true`: the new field is narrower); `asOf` is
   on the two Developing columns and no other. The authoring inventory keeps `developingRead`. OMEGA reads no outcome
   (`tests/test_reextraction_182.py` holds `omega/` to that); the shapes are written down in `docs/09-conditions.md`.
3. **182.3.x, `preview_strategy_trade_levels`.** Its description moved (the manager's drift event has both texts); the
   three statements, measured on draft L:
   - *"bounds are inclusive", "an ATR option's own multiple"*: range 0.8 - 1.8, ATR stops 0.5 / 0.79 / 0.8 / 1 / 1.5 /
     1.8 / 1.81 / 2 on BTC, ETH and SOL, both directions: 0.79 BELOW_FLOOR, 0.8 and 1.8 SURVIVED, 1.81 ABOVE_CEILING.
     On SOL the 0.8 stop's distance in percent lies below the floor's and the 1.8 stop's above the ceiling's by
     floating-point rounding, and both survive: the case v0.14.3 recorded as unmeasured.
     `omega.trade_levels.outside_stop_range` already compared the decimals as written; **no modelled rule moved here.**
   - *"R:R - stated to three decimals"*: a plan paying 1.4996R, and one paying 1.4995R, stage clean under a minimum of
     1.5 and their pairs survive a decision with `riskRewardRatio` 1.5; 1.49949R and 1.4994R are refused "pays 1.499R";
     two legs behave as one; 2.2496R / 2.2494R under 2.25 the same. **This modelled rule did move** (or was never
     measured this close): OMEGA compared the exact pay and would have refused a plan the platform stages.
   - *R:R at the tie itself* (draft `df02fef7`, 18:40 - 18:43Z; the record's `ties`). Drafts E and L staged one tie,
     1.4995, whose binary double lies above it. Fourteen more plans, each beside a plan paying the minimum exactly:

     | Case | Plan (LONG and SHORT alike), minimum | Stage answer | At a decision (BTC) |
     | --- | --- | --- | --- |
     | K1 | 2.2496R, 2.25 | errors [] warnings [] | 4 setups a side, each `riskRewardRatio` 2.25 |
     | K2 | 2.2494R, 2.25 | "The LONG exit plan pays 2.249R, below this strategy's minimum risk-reward of 2.25: every pair it makes would be refused. Change the plan or lower the minimum." | not previewed |
     | K3 | 1.4995R, 1.5 | clean | each 1.5 |
     | A | 2.2495R, 2.25 | clean | each 2.25 |
     | B | 2.4995R, 2.5 | clean | each 2.5 |
     | C | 1R 50% + 1.999R 50%, 1.5 | clean | each 1.5 |
     | D1 | 0.8R 50% + 2.199R 50%, 1.5 | "The LONG exit plan pays 1.499R, below this strategy's minimum risk-reward of 1.5: every pair it makes would be refused. Change the plan or lower the minimum." | not previewed |
     | D2 | 0.1R 50% + 2.899R 50%, 1.5 | clean | each 1.5 |
     | D3 | 1R 30% + 2.785R 70%, 2.25 | clean | each 2.25 |
     | D4 | 0.9R 80% + 1.3975R 20%, 1 | clean | each 1 |
     | D5 | 2.55R 70% + 3.215R 30%, 2.75 | "The LONG exit plan pays 2.749R, below this strategy's minimum risk-reward of 2.75: every pair it makes would be refused. Change the plan or lower the minimum." | not previewed |
     | D6 | 2.7495R, 2.75 | clean | each 2.75 |
     | D7 | 2.9995R, 3 | clean | each 3 |
     | D8 | 0.4995R, 0.5 | clean | each 0.5 |

     A single leg at the tie passes whichever side of the tie its double lies on (above for 1.4995; below for 2.2495,
     2.4995, 2.7495, 2.9995 and 0.4995). Of the six two-leg plans that pay a tie exactly as written, four pass and two
     (D1, D5) are refused. One reading reproduces all fourteen and the ten R:R answers of drafts E and L (T2 - T4,
     G2 - G8): **the pay is a binary floating-point sum of R x (closePct / 100) over the legs; it is multiplied by
     1000, rounded to the nearest whole number, and compared with the minimum.** D1's sum is 1.4994999999999998, a
     unit in the last place under the 1.4995 it pays as written. The readings it was told apart from, and the cases that
     refuse each: the exact decimal pay rounded half up - v0.16.0's first pass - (D1, D5: it accepted two plans the
     platform refuses); `sum(R x closePct) / 100` (C, D2, D5); `sum(R x closePct / 100)` (D2, D5); the double's own
     value rounded to three decimals (A, B, D3, D6, D7, D8). Not told apart: the order of a two-term sum, and a half
     going up or to the even thousandth (a tie under a 0.25-step minimum rounds to the minimum either way).
     `TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR` judges `stated_rr(plan_pays_double(legs))`. Every tie staged was one leg, or
     two legs closing 100%: a plan that pays a tie exactly through a runner's share or more than two closing legs
     draws the warning `TRADE_MENU_EXIT_PLAN_RR_TIE_UNMEASURED` beside OMEGA's own reading of it.
   - *`distancePct`, `distanceAtr`, `validForMinutes`*: a level entry at a decision states them beside `levelPrice`,
     `mark`, `atr`, `placedPrice`, `placedSide` and `orderType` (TRIGGER under STOP_THROUGH_LEVEL, LIMIT under
     ON_RETEST); `validForMinutes` is `validForBars` x the strategy bar (240, 360, 1440 on 1h). An entry whose order
     cannot rest reads `WRONG_SIDE` with `requiredSide`, and that direction makes no setups. OMEGA parses no preview;
     recorded in the module's docstring.
4. **The items v0.15.0 left unmeasured.**
   - *ENTRY_LEVEL_USUALLY_SKIPPED* fires at the stage on a level that sits on one side of price **by definition** under
     a trigger whose order must rest on the other: STOP_THROUGH_LEVEL needs a buy stop above price and a sell stop
     below, ON_RETEST a buy limit below and a sell limit above; EITHER_SIDE_OF_LEVEL never warns (F4 - F7, E9). A level
     that is merely usually on one side does not warn (the Bollinger bands, EMA20, VWAP, PDH / PDL, the prior TPO value
     area: E1 - E14). Which metrics have a side is no served field, so it was swept (draft S): all 418 price-unit
     metrics with a legal value column, one stage each. **Nine sit below** (DONCHIAN_LOWER, DONCHIAN_BROKEN_HI,
     LIQUIDITY_POOL_BELOW, NAKED_POC_BELOW, NAKED_SINGLE_PRINT_BELOW, TPO_SINGLE_PRINT_BELOW, ZONE_SUPPORT_HIGH / LOW /
     MID), **nine above** (the mirror set), **400 neither** - a broken Donchian *high* sits below price and the prior
     bar's band has no side, so a name does not tell it. `data/derived/entry_level_sides.json`, derived from the 418
     stage answers (`data/audit/reextraction_182_side_sweep_2026-11-20.json`, replayed one by one);
     `omega.trade_levels.validate_entry_levels` now draws the warning (a small change: one table, one function). Every
     level entry staged - drafts E and L and the sweep - was ONE form: plain level references (`{rel: anchor}`, `bars`
     null, offset 0, no knobs, no window extreme) under `levelOffsetAtrMultiple` 0.2, and the warned ones under
     `validForBars` 4. OMEGA warns on that level form at that offset and says nothing of another. OMEGA's plans still
     stage ON_CANDLE_CLOSE only.
   - *The five newly authorable main candles* (TF): regime rung 30m -> 2h, 2h -> 8h, 8h -> 1d, 12h -> 1w, 1d -> 1w
     (and 5m 15m, 15m 1h, 1h 4h, 4h 12h re-measured unchanged); lower rung 30m -> 15m, 2h -> 1h, 8h -> 4h, 12h -> 8h,
     1d -> 12h, which the vocabulary also serves (`timeframeRefs.lower.resolvedByAnchor`; the regime rung it serves as
     null). The headers do not change with the main candle (`RSI14`, `RSI14_htf`, `RSI14_ltf`,
     `close_htf_EMA20_spread`, `EMA20_t3 .. _trend`, `atrPct`). 1m, 3m, 3d and 1w are refused
     `REPORT_TIMEFRAME_NOT_AUTHORABLE`. **The model is left as it is** (`ANCHOR_TIMEFRAMES` stays 5m / 15m / 1h / 4h):
     an anchor in OMEGA also carries a cadence, the hold ceilings and the chain depth limits, none of which was measured
     at the other five, so adding them is more than a small change. The measurements are in the record and in
     `docs/20-the-authoring-procedure.md`.
5. **Everything else.** Six draft tools: one output schema (item 2), no input, no description. Hints: item 1 and
   nothing else (170 of 586 records byte-equal, the other 416 exactly the price bases that are not reference prices).
   Vocabulary: nothing but one reworded study. Metric roster: 586, the same names. The ten other authoring tools
   (`preview_strategy_trade_levels`, `discard_strategy_draft`, `get_metric_construction_hints`,
   `list_strategy_vocabulary`, `list_strategy_categories`, `get_strategy_column_contract`,
   `get_strategy_section_template`, `list_strategies`, `save_report_section`, `remove_saved_report_section`) **could
   not be diffed**: no OMEGA capture of them existed, and battlegrid-manager's stored 180.4.0 row (62 tools, read from
   its 2026-11-20T01:33Z backup) does not hold them either. They are captured from this contract on
   (`capture_write_surface.py` writes the sidecar; the manifest names it).

## Also seen

- A stage naming `draftVersion: 0` against a draft the player's hand has not changed is accepted: draft E was staged 21
  times that way (the probe read the stage answer's `version` under the wrong key). Its eight trade level previews
  named version 0 for the same reason and were refused at input; draft L repeats them.
- A draft whose report reads 418 extra value columns stages clean, and `get_strategy_draft` then answers
  `RESULT_TOO_LARGE` (300,334 characters against a 150,000 cap). `list_strategy_drafts` states its version; that draft
  (`8c48af82`) was discarded at the listed version 26 - one more than the last answer read, see "Draft S" above - and
  read back null.
- A stage the caller stops waiting for is still applied: the 26th stage of `8c48af82` was sent as the probe was
  stopped and moved the draft to version 26 with no answer read.
- A draft holding a menu error still saves and still counts a version (K2, D1 and D5 each moved `df02fef7` on by one),
  as G4, G6 and G8 did on draft L.

## The proof

`omega.generate.plan(PRESETS["trend-continuation"]).axes()` (all eight axes, `bodySha256` `0d0160c1...`, the same body
as the 180.4.0 proof: the generator did not move) staged as a new create draft at 182.3.2: errors [], warnings []. Read
back through `get_strategy_draft`: equal to the sent body as values (the canonical sha differs only by number spelling,
10.0 read back 10: `93d0f8c6...` both ways). Previewed on the DRAFT: three sections rendered on BTC and ETH, no missing
condition column, no duplicate header; `preview_strategy_trade_levels` on BTC: three ATR stops SURVIVED, nine setups
per direction, R:R 1.5 / 2 / 3. Discarded at draftVersion 1, read null. OMEGA's own findings on all five presets: 0
errors.

## What the manager's `manager/authoring` uses

No signature or output shape it imports moved: `Thesis`, `validate_thesis`, `brief`, `plan` / `axes()` /
`axes_update()` / `preview_request()`, `body_sha256`, `outputs_for`, `Column`, `load().platform_templates`,
`header_since_123`, `PRESETS`, `plan_pays`, `vocabulary`, `wilson_interval`, `MIN_SAMPLE`, `NO_ENTRY_CONDITION`; the
manifest keeps `servedContractVersion`, `extractedOn`, `counts` and `writeSurface.{servedContractVersion, buildSha,
schema}` (now 182.3.2 / b3969d0b / `schema_20261120T142253Z.json`). Behaviour that moves under them:

- a column `X x spread(CLOSE | LAST)` whose base is not a reference price is an **error** (`OPERAND_NOT_ALLOWED`; a
  `REPORT_COLUMN_OPERAND_UNSUPPORTED` warning at v0.15.0);
- `CLOSE x <average> -> spread(LAST)` is **accepted** (refused at v0.15.0);
- an exit plan paying within 0.0005R under the minimum is **accepted** (an error at v0.15.0), and the finding's text
  states the pay at three decimals. AT 0.0005R under it the verdict follows the platform's floating-point sum: a single
  leg is accepted, two legs are accepted or refused as the platform does (D1 and D5 above are **errors**);
- `validate_menu` may return a `TRADE_MENU_EXIT_PLAN_RR_TIE_UNMEASURED` **warning** (never before): a plan paying a tie
  exactly through a runner's share or more than two closing legs;
- `validate_entry_levels` may return an `ENTRY_LEVEL_USUALLY_SKIPPED` **warning** (never before), on a plain level
  reference under `levelOffsetAtrMultiple` 0.2 only;
- `plan_pays` is unchanged: the exact pay as a float, for display. The rule no longer compares it;
- `compare_vocabulary`'s stored capture is `schema_20261120T142253Z.json` (the enums it compares did not move).

New names, none removed: `omega.trade_levels.stated_rr` (it takes the floating-point pay), `plan_pays_double`,
`rr_tie_unmeasured`, `entry_side_findings`, `entry_level_sides`, `ENTRY_ORDER_SIDE`, `ENTRY_LEVEL_SIDES`,
`ENTRY_SIDE_OFFSETS`, `RR_PROBES`, `RR_DECIMALS`; the finding code `TRADE_MENU_EXIT_PLAN_RR_TIE_UNMEASURED`;
`price_operand_refused` keeps its `chained` keyword and ignores it; `scripts.capture_write_surface.main` takes an
optional argument list (`main(argv)`; `sys.argv` when omitted).

## Not measured

- The cadence, the hold ceilings and the chain depths at 30m, 2h, 8h, 12h and 1d (so the model keeps four anchors).
- An entry level reference that is not plain: an `offset`, a `windowExtreme`, knobs, a timeframe off the anchor, `bars`
  "closed" or "all". The side table is for the form the sweep staged (`{rel: anchor}`, `bars` null, offset 0, no
  knobs, no window extreme); `entry_side_findings` says nothing of another.
- ENTRY_LEVEL_USUALLY_SKIPPED at a `levelOffsetAtrMultiple` other than 0.2 (the schema takes 0 - 2 on a 0.1 step):
  every level entry staged carried 0.2, so OMEGA draws the warning at 0.2 and nothing at 0, 0.1 or 0.3 - 2. Nor at a
  `validForBars` other than 4 on a level that has a side: the three warned stages and the sweep all carried 4 (6 and
  24 were staged on levels with no side); OMEGA does not gate the warning on it.
- Whether the stage still reports ENTRY_LEVEL_USUALLY_SKIPPED beside an entry level error: every warned stage was
  otherwise clean. OMEGA reports both.
- R:R at an exact tie through a sum that was not staged there: a runner's share (a plan closing less than 100%, a
  trail objective), and three or four closing legs (the order of the sum). Reachable ties are the minimum less
  0.0005 on the 0.25 step; one leg was staged at six of them (0.4995, 1.4995, 2.2495, 2.4995, 2.7495, 2.9995) and two
  legs closing 100% at four (0.9995, 1.4995, 2.2495, 2.7495). OMEGA judges such a plan by its own order of the sum
  (the legs in order, the runner last) and warns `TRADE_MENU_EXIT_PLAN_RR_TIE_UNMEASURED`.
- A minimum off the 0.25 step, or a single leg at a tie under a minimum other than the six above: the same arithmetic
  is applied, unmeasured there (an off-step minimum is refused on its own account).
- Which way a half rounds where it could matter (to the even thousandth or up): under a 0.25-step minimum both give
  the minimum. And the R:R a DECISION computes for a pair near a tie beyond the eleven previews read (each stated the
  minimum): a decision's ratio comes from prices, not from the plan's decimals.
- The per-stage answer of the one sweep stage whose answer was not read (the 26th of `8c48af82`, EMA9 by the script's
  order); EMA9's answer in the table is the second run's.
- How ON_RETEST and EITHER_SIDE_OF_LEVEL place an order when the offset carries it across the mark, beyond the two
  cases read (F2 LONG refused WRONG_SIDE; F3).
- The output schemas of the ten other authoring tools against 180.4.0 (not captured then).
- A sequence step over a Developing read (`DEVELOPING`, README v175): not staged, as at v0.15.0.
- The operand-expanded coverage beyond the four new shapes: the unrendered 462,135 are the same spread operand pairs
  as at 180.4.0 (the deliberate stop since 144). No structural shape moved, so no structural sweep was run: 24,399 of
  24,399 stay rendered.

## Review fixes

An independent review of the first pass (commit `b4d50da`) found seven items. Each, and what changed:

1. **`scripts/capture_write_surface.py`'s default run died after writing the schema** (the sidecar was built in the
   `--authoring-only` branch alone, so the default path met an unbound name): it never wrote the
   `authoring_tools_<stamp>.json` its docstring and this record promise. The 14:22Z capture in the repository was
   written by the script as it stood before the sidecar was added to it, and the 16:10Z sidecar by
   `--authoring-only`; the default run with the sidecar code had never completed. Fixed: the default
   run builds both documents from its one list before writing either; `main(argv)` is tested on both paths and on a
   contract that moves during the list, with the version read and the list stubbed and the output in a temporary
   directory.
2. **`stated_rr` rounded the exact decimal pay half up**, which no measurement at a real tie supported and which errs
   toward accepting. Measured (the Ties row; item 3 above) and re-modelled: the floating-point sum, times 1000,
   rounded. The first pass accepted two plans the platform refuses (D1, D5).
3. **`test_no_preset_and_no_tpo_suite_column_uses_a_refused_form` asserted nothing**: it filtered on
   `REPORT_COLUMN_OPERAND_UNSUPPORTED`, and on the 182.3.2 corpus the refused form draws `OPERAND_NOT_ALLOWED`. It now
   asserts the rule itself and no error at all on every preset and suite column, and a sibling plants the old form
   (`PRIOR_TPO_VAL x spread(CLOSE)` and three more) and shows both assertions catch it.
4. **`entry_side_findings` did not check the level's `bars` or the entry's `levelOffsetAtrMultiple`**, though every
   stage carried `bars` null and 0.2. Both are now part of the form it warns on (`ENTRY_SIDE_OFFSETS`).
5. **`entry_side_findings` raised on a malformed entry** called directly. It answers `[]` for anything that is not a
   well-formed level entry.
6. **No test reached the graded branch through `validate_column`** (`REPORT_COLUMN_OPERAND_UNSUPPORTED`: a warning
   below contract 181, an error from it). One does now, on a synthetic corpus that still serves CLOSE and LAST as
   plain, off-anchor and chained spread operands: exactly one finding each, at 180.4.0, 181.0.0 and 182.3.2.
7. **The record's sweep counts did not add up and the side table was checked against the sweep's own summary.** The
   counts are corrected from the probe's logs ("Draft S" above; `calls.createDrafts`), and the 418 stage answers,
   found in those logs, are stored and replayed.

## Outside the repository

The first two `capture_write_surface` attempts ran the real `npx` (the shim was not first on `PATH`), which began
upgrading the cached mcporter from 0.16.1 to 0.17.1 and died twice with `ECOMPROMISED`, leaving the npx cache
(`~/AppData/Local/npm-cache/_npx/bdbf2deecdd22bc5`) half-moved. It was put back together by hand (the retired files
moved back; the leftover 0.16.1 remnants removed): mcporter there is now 0.17.1, and its `package-lock.json` still
names 0.16.1, so the next real `npx mcporter` will reinstall it. Everything in this record ran on that 0.17.1.

The review-fix draft (Ties) ran on the same runtime, started by `node` with `MCPORTER_DIST` naming that cached
package: `npx` was not run, and nothing was written to the cache. The probe scripts and their raw call logs are
session scratch, not in the repository; what they measured is in the two audit files.
