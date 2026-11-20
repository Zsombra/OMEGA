# OMEGA v0.16.0 at contract 182.3.2: v181 served, R:R at three decimals, the side of an entry level

**Record, 2026-11-20.** Contract 182.3.2, build `b3969d0b` (`GET /mcp/version` read before and after every group of
calls below, 13:59:10Z first and 16:12:26Z last; 182.3.2 / b3969d0b each time). battlegrid-manager's watch first saw
182.3.1 (build `86d5b983`) at 03:52Z and 182.3.2 at 13:32Z, with no tool it watches moved between the two. Previous
pin: v0.15.0 at 180.4.0. The vendor README documents v181 and v182; 182.1 - 182.3.2 are read from the served schemas,
the hints, the manager's drift events and the probes. One open PR on the vendor repository (#286, a skills export at
182.3.2): nothing announced that is not served.

Live record: `data/audit/reextraction_182_2026-11-20.json` (replayed by `tests/test_reextraction_182.py`). Corpus
moves: `data/contract/metrics/_moves_182.json`.

## What was measured, and how

Every call but one went through one long-lived mcporter runtime (`scripts/mcporter_runtime.mjs`), serially.

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
| Draft S | 25 + 394 stages into two new create drafts (`8c48af82`, `6f2e32ee`) | 14:52 - 14:57Z, 15:33 - 16:09Z | the side sweep: all 418 price-unit level metrics; discarded at 26 and 394, each read null |
| COV | `preview_strategy_report`, BTC 4h | 16:20Z | the four operand-expanded shapes the narrowed hints opened, rendered as `omega.space` writes them |
| Proof | the `trend-continuation` preset body, a new create draft `68dc2339` | 16:11 - 16:12Z | errors [] warnings []; read back equal; previewed; discarded at draftVersion 1, read null |

In all: 50 `preview_strategy_report`, 19 `preview_strategy_trade_levels`, 459 `stage_strategy_draft` into five NEW
create drafts, 5 `discard_strategy_draft` (those five), 13 `get_strategy_draft`, 10 `list_strategy_drafts`. Nothing was
committed. No existing strategy or draft was touched: `list_strategy_drafts` before and after each draft showed the one
VWAP Reject 15m draft (`c1fd5d4c`, version 9, 2026-10-23), untouched. No agent, Radar, Arena, deployment, funding or
visibility tool was called. One preview (A1's column) went through the session's own connector at 13:54Z before the
runtime was used; a group of previews at 14:59Z was not sent (the local runtime did not start) and ran at 15:32Z.

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
     `TRADE_MENU_EXIT_PLAN_BELOW_MIN_RR` now judges `stated_rr(pays)`, the pay at three decimals, half up.
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
     bar's band has no side, so a name does not tell it. `data/derived/entry_level_sides.json`;
     `omega.trade_levels.validate_entry_levels` now draws the warning (a small change: one table, one function). OMEGA's
     plans still stage ON_CANDLE_CLOSE only.
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
  (`8c48af82`) was discarded at the listed version 26 and read back null.

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
  states the pay at three decimals;
- `validate_entry_levels` may return an `ENTRY_LEVEL_USUALLY_SKIPPED` **warning** (never before);
- `compare_vocabulary`'s stored capture is `schema_20261120T142253Z.json` (the enums it compares did not move).

New names, none removed: `omega.trade_levels.stated_rr`, `entry_side_findings`, `entry_level_sides`,
`ENTRY_ORDER_SIDE`, `ENTRY_LEVEL_SIDES`, `RR_PROBES`, `RR_DECIMALS`; `price_operand_refused` keeps its `chained`
keyword and ignores it.

## Not measured

- The cadence, the hold ceilings and the chain depths at 30m, 2h, 8h, 12h and 1d (so the model keeps four anchors).
- An entry level reference that is not plain: an `offset`, a `windowExtreme`, knobs, a timeframe off the anchor. The
  side table is for the form the sweep staged (`{rel: anchor}`, offset 0, no knobs, no window extreme);
  `entry_side_findings` says nothing of another.
- Whether the stage still reports ENTRY_LEVEL_USUALLY_SKIPPED beside an entry level error: every warned stage was
  otherwise clean. OMEGA reports both.
- The R:R tie whose double lies below it (1.0005): the one tie staged, 1.4995, lies a hair above in binary floating
  point and was accepted.
- How ON_RETEST and EITHER_SIDE_OF_LEVEL place an order when the offset carries it across the mark, beyond the two
  cases read (F2 LONG refused WRONG_SIDE; F3).
- The output schemas of the ten other authoring tools against 180.4.0 (not captured then).
- A sequence step over a Developing read (`DEVELOPING`, README v175): not staged, as at v0.15.0.
- The operand-expanded coverage beyond the four new shapes: the unrendered 462,135 are the same spread operand pairs
  as at 180.4.0 (the deliberate stop since 144). No structural shape moved, so no structural sweep was run: 24,399 of
  24,399 stay rendered.

## Outside the repository

The first two `capture_write_surface` attempts ran the real `npx` (the shim was not first on `PATH`), which began
upgrading the cached mcporter from 0.16.1 to 0.17.1 and died twice with `ECOMPROMISED`, leaving the npx cache
(`~/AppData/Local/npm-cache/_npx/bdbf2deecdd22bc5`) half-moved. It was put back together by hand (the retired files
moved back; the leftover 0.16.1 remnants removed): mcporter there is now 0.17.1, and its `package-lock.json` still
names 0.16.1, so the next real `npx mcporter` will reinstall it. Everything in this record ran on that 0.17.1.
