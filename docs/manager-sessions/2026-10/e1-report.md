# E1 report: OMEGA v123 header codes

Date 2026-10-20, written 11:12Z. Worktree `C:/tmp-omega-e1`, branch `fix/v123-header-codes`, based on `10bdb67` (v0.8.2). Not tagged, not merged, not pushed. No BattleGrid call was made.

## Status

Done. The suite passes: **1588 passed** (baseline 1541; 47 new tests).

## Commits

| sha | what |
|---|---|
| `9d79f9b` | Every `MODULE_CLAUSES` header is now derived from the column builder by `recipe_header()`. No header changes in this commit; it was tested on its own and passed 1541. |
| `69d7116` | The 18 code renames: data, a loader guard, history replay, and tests. |
| `7cfccd5` | The Market Read cap goes from 2000 to 4000. |
| `ccd8a9d` | The v117 horizon check. |
| `4f03c77` | Docs: `09-conditions.md` and `06-cookbook.md` now use the new codes. |

## What changed

1. **The rename table is recorded in a data file.** `data/contract/metrics/_moves_123.json` holds all 18 stems from the README v123 section, copied verbatim, with the quote. It follows the same pattern as `_moves_110.json`.
2. **The metric files and their sources carry the new codes.**
   - All 18 `data/contract/metrics/<KEY>.json` files now have the new `code`.
   - So do the `_batch0[2-5].json` extraction sources. I re-ran `scripts/build_corpus.py`, and it reproduced the metric files with no other diff.
   - `omega.contract.load` now refuses to load a corpus whose code disagrees with the moves file. A half-applied rename fails closed.
3. **Clause headers come from the builder.** `omega.generate.recipe_header(module, slot, **match)` builds each header through `fanout.outputs_for`. It raises unless exactly one header matches. The three formerly hand-typed headers are now `ADX14_now`, `pctB20_now` and `ATR14_trend`. Every other clause header comes out byte-identical to before. The model's menu, `authoring.vocabulary()`, now shows the new names.
4. **Old recordings are replayed under the new codes.**
   - `omega.contract.header_since_123()` rewrites a header captured before v123, swapping whole tokens only (README: "Every suffix and prefix is kept").
   - It is used by the history tests (compiler probes, live renders, header tokens, the stored-strategy fixture) and by `scripts/render_coverage.rendered_headers()`.
   - It is also used by `observed_vocabulary()`: the `ADX_zone` record is looked up as `ADX14_zone`, and its replacement text now reads "ADX14 gte 25".
   - The recording files themselves stay verbatim.
5. **Market Read.** `market_read_cap()` uses the served `budgets.marketReadChars` if a re-extraction brings it in, otherwise `MARKET_READ_CHARS = 4000`. The README quote is in a comment.
6. **v117 check.**
   - `CHANGE_HORIZON` maps CHG_5M…CHG_24H to 5m…1d and OI_PX_REGIME to 1h. The README rule and the skill sentence are quoted in a comment.
   - `report_headers` marks a column as Developing when its horizon is above the anchor (`horizon_above`), whatever its selector. This applies in both custom and platform sections.
   - A verdict carrier whose closure reads such a column is an **error**, `CONDITION_VERDICT_READ_ILLEGAL`. A hold over more than one bar on one is also an **error**, `CONDITION_HOLD_ILLEGAL`; it used to be only a warning.
   - Both messages name the carrier, the column and the remedy. No preset is affected.

## Tests

- **Updated:**
  - `tests/test_conditions.py:344-345` now expects `pctB20_now`.
  - `tests/test_axes_update_section_keys.py:135` now expects `ADX14_now`. The fixture is rewritten at v123 because the server rewrote stored strategies.
  - The ADX_zone trap tests now use `ADX14_zone`. Before, they were passing only because the header was unknown. They now also check the refusal reason.
  - Seven history tests replay their old recordings under the new codes.
  - The TPO wire test checks against the new cap.
- **Added:**
  - `tests/test_v123_header_codes.py`: the README table pin, corpus codes, the loader refusing a stale code, token rewriting, every preset emitting only new codes (report, clauses, Market Read), and the model's menu. It also checks that no clause header in the source is a string literal, that a renamed code moves the derived header with it, and that an ambiguous match raises.
  - `tests/test_v117_horizon_reads.py`: a 13-case matrix, plus selector, closure laundering, non-carrier, clause and group hold, and preset cases.
  - Market Read cap tests: 4000 passes, 4001 is refused, and a served value wins. Another test checks that a `{ADX_now}` marker is refused.

## Concerns

- **No re-extraction yet.** The new codes come from the README, not from a fresh `get_metric_construction_hints` extraction. Once platform reads are allowed, `refresh_metric_contracts.py` should reproduce them. If it doesn't, the loader guard will refuse to load, which is the intended fail-closed behaviour.
- **Render coverage is inferred.** It now counts old renders under the new codes by the README rule. No sweep has been run since v123.
- **Old codes left on purpose:**
  - in measurement and history records: `_observed_vocabulary.json`, `columns/*`, `_moves_110_8.json`, `data/created/*`;
  - in a quoted record in docs line 202;
  - in the research scripts `verify_conventions.py` and `verify_tier_b.py`, which read old panel names.
- **Not done here:**
  - `_manifest.json` still says 110.8.0; the stamp should move with a real re-extraction.
  - The seven new v123 metric keys are not in the corpus.
  - The vendored skill pack is still at 110.10.0.
  - `OI_CHG` is not in `CHANGE_HORIZON`, because the README names only chg* and oiRegime.
- **Line endings.** The edited files were written with LF and git warns it will convert them to CRLF. The diffs contain only content changes.
- **For E2:** OMEGA plans built at v0.8.2 that use BOLLINGER, TREND_STRENGTH or VOLATILITY carry retired headers and must be re-planned. Also, the manager's `direction.py` glossary is keyed by the old headers.
