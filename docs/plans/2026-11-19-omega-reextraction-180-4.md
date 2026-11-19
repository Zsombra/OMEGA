# OMEGA v0.15.0 at contract 180.4.0: price is the base, a Developing read decides, the level entry on either side

**Record, 2026-11-19.** Contract 180.4.0, build `d66d4f98` (`GET /mcp/version` read 20:19:16Z, before and after the
surface list, at the first and every 40th hint, before and after the sweep, and 21:12:01Z after the last probe).
180.4.0 was first served 2026-11-18 ~18:45Z at build `fa339cf2`; the six draft tools of this capture equal
battlegrid-manager's stored 180.4.0 row of that build byte for byte. Previous pin: v0.14.3 at 171.0.0. The vendor README
documents v175, v176, v179 and v181 (v181 announced, not served); 172 - 174, 177, 178 and 180 are read from the served
schemas and hints only.

Live record: `data/audit/reextraction_180_4_2026-11-19.json` (replayed by `tests/test_reextraction_180_4.py`). Corpus
moves: `data/contract/metrics/_moves_180_4.json`. Sweep: `data/audit/coverage_sweep_2026-11-19.json`.

## What was measured, and how

| Step | Tool, inputs | When (UTC) | Answer |
| --- | --- | --- | --- |
| Write surface | `scripts/capture_write_surface.py` (mcporter list, 167 tools) | 20:24Z | `schema_20261119T202415Z.json`; the six draft tools equal the manager's 180.4.0 row (fa339cf2) on description / input / output |
| Hints | `scripts/refresh_metric_contracts.py`, one mcporter runtime, `EXTRACTION_STAMP=20261119b` | 20:36 - 20:50Z | 586 of 586, 0 failed; 20 batches; the 171 batches archived as `archive_20261112c_extraction`. A first read (stamp `20261119`, 20:32Z) stopped at 160 on a local socket error (WinError 10055 on the version GET); nothing of it is in the corpus |
| Vocabulary | `scripts/snapshot_vocabulary.py` | 20:58 - 20:59Z | 13 categories answered, `levels` RESULT_TOO_LARGE (as before); `levels` 274 -> 279; `_shared.json` moved `transforms` (labels), `timeframes`, `timeframeRefs`, `rankedTimeframes` |
| Structural sweep | `scripts/sweep_render_coverage.py`, `SWEEP_SCOPE=structural` | 21:07 - 21:08Z | 160 uncovered shapes, 172 headers, 0 refusals, 0 mispredicted; contract unmoved. Structural coverage 24,399 / 24,399; expanded 53,806 rendered, the 462,135 unrendered all spread operand pairs (the deliberate stop since 144) |
| P1 | `preview_strategy_report`, BTC 4h, 14 columns (below) | 20:34Z | every column rendered |
| R1 - R3 | `preview_strategy_report`, RSI14 at `{rel: regime}` / `{rel: lower}` on 1h / 15m / 5m | 20:34 - 20:35Z | regime 4h / 1h / 15m, lower 30m / 5m / 1m |
| D1 - D7 | `stage_strategy_draft` x7 into ONE new create draft `cdd309e5`, `get_strategy_draft`, `discard_strategy_draft` | 20:35:40 - 20:38Z | below; discarded at draftVersion 7, read null |
| Proof S1 - S3 | the `trend-continuation` preset body, a new create draft `2e7014ec`; two TIMEFRAME_PROFILE restages | 21:10:18 - 21:11:27Z | S1 errors [] warnings []; read back equal; discarded at draftVersion 3, read null |

Nothing was committed. No existing strategy or draft was touched (`list_strategy_drafts` before and after: the one
VWAP Reject 15m draft of 2026-10-23, untouched). No agent, Radar, Arena, deployment or visibility tool was called.

## What the platform moved, item by item

1. **v175, a Developing read decides at the decided close.** Measured (D1, D4, D7): a verdict carrier over
   `RSI14_4h_dev` (an `{abs: 4h}` column read Developing on a 1h strategy), a verdict carrier over `chg4h` on 1h (a
   change above the strategy timeframe), and an exit rule over `RSI14_4h_dev` stage with no error. A hold of 2 over
   the Developing read is refused `CONDITION_HOLD_ILLEGAL` (maxWindow 1). OMEGA: `omega.conditions` no longer raises
   `CONDITION_VERDICT_READ_ILLEGAL` (both branches, Developing and v117 horizon) and the exit rule is refused only when
   a closure operand is not moved by a completed bar; a hold above 1 over a Developing read is now an error (it was a
   warning). The v117 hold error on a horizon above the anchor stands.
2. **v176, private or published.** `visibility` lost `PROTECTED` on `get_strategy` / `commit_strategy_draft` output.
   OMEGA stages no visibility (the stage input has none) and reads none: nothing to change.
3. **v177, level entries** (`stage_strategy_draft` input). The only input change in the six draft tools between 171
   and 180.4.0: the level ENTRY arm's trigger enum gains `EITHER_SIDE_OF_LEVEL`; the draft warning enum gains
   `ENTRY_LEVEL_USUALLY_SKIPPED`. Measured (D5 - D7): `EITHER_SIDE_OF_LEVEL` judges its levels by the 168 level rule
   (an unread SHORT level refused on `entry.levels.SHORT`; read levels stage clean), and `ON_RETEST` still refuses an
   unread level (D4, as E2 at 168.2.0). OMEGA: `omega.trade_levels.level_triggers()` reads the arm's trigger enum
   off the write schema; `LEVEL_TRIGGERS` carries the three. OMEGA's plans still stage `ON_CANDLE_CLOSE` only.
4. **v179, Radar names a coin by `coinTicker`.** OMEGA calls no Radar tool (`omega/` imports no transport; the
   scripts' allowlists hold no Radar tool). `omega/registry.py`'s hand checklist still names `upsert_radar_deployment`
   as text for a person (left as it was; it is not a call).
5. **180.4.0: `DAY_HIGH`, `DAY_LOW`, `WEEK_HIGH`, `WEEK_LOW`** (and `ATH`, undocumented, by 177) are extracted: 586
   metrics. Headers `dayHi`, `dayLo`, `weekHi`, `weekLo` (P1: unit price, family levels). ATH joined every price
   operand list (plain, averaged, chained, on and off the anchor); the four day / week levels are plain spread operands
   on the anchor rung only. **The regime rung:** `REGIME_TF_FOR_ANCHOR["4h"]` is `12h` (P1; 1d before), the other three
   re-measured unchanged (R1 - R3).
6. **v181 (announced, not served): price is the base of every spread over another reading.** At 180.4.0 the old form
   still renders and the hints still list CLOSE / LAST (P1, the refreshed corpus); the new form renders already (P1:
   `close_pTpo{VAL,VAH,POC}_spread`, `close_EMA20_spread`, `close_hl2_ema34_spread`). OMEGA refuses the old form now:
   `omega.contract.price_operand_refused` (a reference price - CLOSE, LAST - as the plain operand of a spread whose base
   is not one, and of every spread chained after an average) is a `REPORT_COLUMN_OPERAND_UNSUPPORTED` error in
   `omega.validate` that names the form to write where the corpus admits it; `omega.space` enumerates none of them
   (3,068 operand-expanded shapes fewer, 562 of which earlier sweeps had rendered; structural unchanged). Replays of
   older probes that sent the form (seven previews of the 149.1.0 authoring probe, three of the 161.0.0 one) now read
   that refusal, and the tests say so. Two reference prices keep both orders and an averaged
   price operand stays legal. `omega.contract.flipped_price_spread_clause` maps a clause on the old column onto the new
   one (operator flipped, threshold `100 x (100 / (100 + t) - 1)`): P1's pair reproduces it exactly (1.20636 ->
   -1.19198), so the flip is not a negation. The hand-run `scripts/tpo_suite_build.py`, `tpo_ladder_preview.py` and
   `tpo_panel_pull.py` now write `CLOSE x spread(PRIOR_TPO_*)` with flipped clauses; `build_pvm_strategy.py` is a
   retired record of what was sent and is annotated, not rewritten. `omega/fanout.py` needed no change (it spells
   `{token}_{operand}_spread` for any base). No preset uses the form. **v182** (condition outcomes lose
   `developingRead`, serve `developingAsOf`): OMEGA reads no condition outcome; the two probe scripts that copy
   `developingRead` read it from `authoring.conditionColumns[].outputs[]`, the inventory v182 keeps.

## Also moved, found by the extraction

- **`provenance` left every hint** (581 records carried it at 171; none at 180.4.0). `Metric.provenance` reads None;
  the archived batches keep the values. 63 glosses, several knob descriptions and seven transforms' authoring text lost
  their TradingView / TA-Lib / LuxAlgo attributions (wording only; `_moves_180_4.json`).
- **The authorable main candles are nine:** 5m, 15m, 30m, 1h, 2h, 4h, 8h, 12h, 1d (S3's `allowedDomain`, the
  vocabulary's `timeframes`); the preset staged clean at 12h (S2). OMEGA keeps the four whose cadence and regime rung
  are measured (`omega.types.ANCHOR_TIMEFRAMES`).
- **A stage's diagnostics come in stages:** while a condition error stands, no entry-level or menu-level error is
  reported, and one level error is reported at a time (D1 - D6). A probe of one rule must leave every earlier rule
  clean.

## The proof

`omega.generate.plan(PRESETS["trend-continuation"]).axes()` (all eight axes, `bodySha256` `0d0160c1...`) staged as a
new create draft at 180.4.0: errors [], warnings []. Read back through `get_strategy_draft`: equal to the sent body as
values; the canonical sha differs only by number spelling (10.0 read back 10, as `draft_echo_2026-11-13.json` found).
Discarded at draftVersion 3, read null. OMEGA's own findings on all five presets: 0 errors.

## What the manager's `manager/authoring` uses

No signature or output shape it imports moved: `Thesis`, `validate_thesis`, `brief`, `plan` / `axes()` /
`axes_update()` / `preview_request()`, `body_sha256`, `outputs_for`, `Column`, `load().platform_templates`,
`header_since_123`, `PRESETS`, `plan_pays`, `vocabulary`, `wilson_interval`, `MIN_SAMPLE`; the manifest keeps
`servedContractVersion`, `extractedOn`, `counts` and `writeSurface.{servedContractVersion, buildSha, schema}` (now
180.4.0 / d66d4f98 / `schema_20261119T202415Z.json`). Behaviour that moves under them: a plan or column with
`X x spread(CLOSE|LAST)` is now an error; a verdict carrier or exit rule over a Developing read is no longer one; a
Developing hold above 1 is; the 4h brief and vocabulary name a 12h regime rung; `compare_vocabulary`'s stored metric
enum is 586.

## Not measured

- `ENTRY_LEVEL_USUALLY_SKIPPED`: in the warning enum, drawn by no probe; its condition is unmeasured.
- The five new anchors (30m, 2h, 8h, 12h, 1d): their cadence and regime rung, and every header and limit at them.
- v181 and v182 themselves: not served; designed from the README and the manager's forecast, to be re-read when they
  land (the hints should drop CLOSE / LAST from the price operand lists; OMEGA's rule then agrees with the corpus).
- A sequence step over a Developing read (`DEVELOPING`, README v175): not staged.
- The operand-expanded coverage of the new operands (ATH and the four levels against 413 bases): the structural
  sweep covers every new header pattern; the expansions re-mint it with another operand code, as in every release
  since 144.
