# The metric corpus re-extracted at contract 110.2.0 — record

**Status: DONE 2026-10-14** on branch `feat/reextract-110-2`. Baseline main (v0.6.3): 1458 passed; after: **1459 passed**.

## Why

BattleGrid moved 109.0.0 → 110.1.0 (2026-10-13 19:06Z) → 110.2.0 (20:06Z). README "Contract history — v110: a metric
names the one line it reads": the metric keys `MACD`, `PPO` and `KC_MID` are **refused** (author `MACD_HIST`,
`PPO_HIST`, `EMA20`), seven keys are added (`MACD_LINE`, `MACD_SIGNAL`, `PPO_LINE`, `PPO_SIGNAL`, `ROC15`,
`DONCHIAN_BROKEN_HI`, `DONCHIAN_BROKEN_LO`; with the two `_HIST` keys, nine new), and the header codes `MACD`, `PPO`,
`ROC` render as `MACDhist`, `PPOhist`, `ROC12`. omega v0.6.3 still offered the refused keys and predicted the old codes.
battlegrid-manager reviewed the drift the same night (its `docs/status/2026-10-14-battlegrid-110-2-0-review.md`): its
preflight refuses omega-planned authoring on a moved vocabulary, so nothing was sent - but the corpus was stale.

## Route

Every call read-only, over the `mcporter` CLI to `battlegrid-anbu` through the allowlisted `bg.py` (the user's 10-13
"approve all" covered the read-only reads). No stage, commit, bind or trade.

1. The write surface: the 110.2.0 `stage_strategy_draft` family copied from the manager's stored surface (its fixture
   `tests/fixtures/2026-10-14-surface-110.2.0/manager_schemas.json`) to
   `data/contract/stage_strategy_draft/schema_20261013T200621Z.json`; the manifest names it; the condition vocabulary
   re-derived (`scripts/derive_condition_vocabulary.py`): **177** column metrics.
2. `get_metric_construction_hints` × 177 (two workers, 0 failed), then `scripts/refresh_metric_contracts.py`
   (EXTRACTION_STAMP 20261014, archive 20261013): **retired `KC_MID`, `MACD`, `PPO`**; every transform's authoring block
   invariant; catalogue unchanged.
3. `list_strategy_categories` + `list_strategy_vocabulary` × 10 (saved to `data/contract/vocabulary/20261014T0156Z/`):
   momentum 22 → 27, structure 47 → 48; `_shared.json`'s blocks identical; two platform templates moved
   (`includeMacd`: MACD → MACD_HIST, `includeRelativeStrength`: PPO → PPO_HIST); the custom templates unchanged.
4. `scripts/build_corpus.py`; the render-coverage sweep (`SWEEP_DATE=2026-10-14`): **924 shapes, 1,804 headers, 0
   refusals, 0 predicted-but-not-rendered** - omega.fanout named every new header (`MACDhist_cross`, `PPOhist_trend`,
   `ROC12_cross`, `donchianBrkHi_lvl` ...) right on the first pass.

## What moved (measured, and only what v110 says)

- **Records of surviving metrics:** 83 of 168 changed, every one in `spreadOperands` only, and every pool change adds or
  removes a v110 key; the single other change is `ROC12`'s code (`ROC` → `ROC12`).
- **Cells** 670 → **705** (− 18: MACD 5, PPO 6, KC_MID 7; + 53 new). **Structural shapes** 899 → **947** (atoms 705,
  chained 242). **Operand-expanded** 8,575 → **9,103**. **Rank chains** 84 → 80 (KC_MID's distance → rank left with it).
- **`levelInteraction`** on 43 → **44** levels: − KC_MID, + both Donchian break levels (the rails themselves still refuse).

## What omega does about it

- `data/contract/metrics/_moves_110.json` records the move: retired → what to author, `sameSeries` (true for MACD and PPO:
  "the same histograms"; false for KC_MID → EMA20, a different metric), the added keys, and the header codes before/since.
- `omega.validate` refuses a retired key **naming its replacement** (`METRIC_RETIRED`), not as an unknown metric.
- `omega.generate`: the MACD module reads `MACD_HIST` (trajectory + crossDetect - the signal-line cross) and the relative
  strength module `PPO_HIST`; their conditions read `MACDhist_trend` / `PPOhist_trend`.
- History stays history, replayed under the roster of its date: `omega.membership` reads a same-series replacement through
  the key the pre-108 signal map measured; the probe-render replay and the recorded Trend Continuation body are compared as
  the server holds them since 110 (`tests/moves_110.py`, README v110: stored strategies are rewritten by the server).
