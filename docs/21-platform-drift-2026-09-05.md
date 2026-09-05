# 21 · Platform drift, measured 2026-09-05

What the live platform serves on 2026-09-05T23Z that the 2026-08-24 extraction does not
know about. Everything below was measured with read-only calls in one session; nothing was
compiled, applied, forked, bound or deployed. Machine-readable twin:
`data/contract/_drift_2026-09-05.json`. Captures: `data/contract/vocabulary/20260905T2318Z/`,
`data/contract/columns/basis_*_2026-09-05.json`, `data/contract/compile_strategy_plan/schema_20260905T011443Z.json`.

**Docs 00, 01, 03, 14, 18 and the README still describe the August roster (86 metrics, 322 legal
cells, 46 buildable families).** They are not wrong about August; they are stale about today.
Doc 01 is generated from `data/contract/metrics/`, which still holds 86 files. The re-extraction
that would refresh them is listed at the end and has not been run.

## 1. Metric roster: 86 → 135, nothing removed

`list_strategy_vocabulary` for all ten categories returns 135 metrics; the compile schema's
`metric` enum has 135 members; `list_strategy_categories` sums to 135. The three agree.

| Family | Aug | Live | Added |
|---|---|---|---|
| price | 10 | 10 | – |
| momentum | 15 | 22 | RSI2, WT1, WT2, QQE_RSI_MA, QQE_STOP, WILLR14, STOCH_RSI14 |
| trend | 9 | 21 | EMA9, EMA21, EMA50, HMA20, ST_DIR, ICHI_CONV, ICHI_BASE, ICHI_SPAN_A, ICHI_SPAN_B, ICHI_LAG, DI_PLUS, DI_MINUS |
| volatility | 6 | 7 | KC_SQUEEZE |
| volumeFlow | 13 | 13 | – |
| derivatives | 7 | 7 | – |
| structure | 7 | 23 | BB_UPPER, BB_LOWER, KC_UPPER, KC_MID, KC_LOWER, ST_LINE, PSAR, PIVOT_P, PIVOT_R1–R3, PIVOT_S1–S3, PDH, PDL |
| regime | 3 | 16 | REGIME_STATE, REGIME_CONVICTION, REGIME_RUN_BARS, REGIME_TREND_GATE, REGIME_TREND_MARGIN, REGIME_TREND_SOURCE, REGIME_DI_SPREAD, REGIME_VOL_ATR_RATIO, REGIME_VOL_BBW_RATIO, REGIME_MOM_BULL_VOTES, REGIME_MOM_BEAR_VOTES, REGIME_CRASH_MARGIN, REGIME_CRASH_LATCH |
| crowd | 9 | 9 | – |
| derived | 7 | 7 | – |

Provenance, from the vendor's own README in the installed skill package
(`.agents/skills/battlegrid/README.md`, "Contract history — v37 → v53"):

- 29 keys at contract **46.1.0** (`add-indicator-catalog-coverage`): Keltner, Supertrend, Hull,
  WaveTrend, QQE, PSAR, Ichimoku, Williams %R, Stochastic RSI, the seven pivots, and four
  "already-published fields that became addressable" (BB_UPPER, BB_LOWER, DI_PLUS, DI_MINUS).
- 13 regime keys at **47.1.0**.
- 7 with **no README entry at all**: EMA9, EMA21, EMA50, PDH, PDL, RSI2, KC_SQUEEZE. The README
  itself says its notes lag the served contract ("a contract move still needs a human-authored
  entry here, and the export lane will not remind you").

The README's warning is worth quoting because it names this repository's exact failure mode:
*"an agent holding a cached belief that these are inexpressible will substitute for a primitive
the platform now serves. That failure raises no error at all."* Doc 18's "cannot build" verdicts
for Keltner, Supertrend, Ichimoku, pivots and Williams %R are that cached belief.

## 2. Transforms: same 16 ids, wider attachment

The authorable transform id set is unchanged (16). What changed is which metrics offer them:

- `aggregate` is now a **top-level** transform on 40 existing metrics where August listed it
  only as a chain successor of `distance`/`spread` (36 of the 45 changed metrics gained nothing
  but this).
- `bandTouch` was added to the five timeless price metrics (LAST, MARK, ORACLE, SPOT_CLOSE_CB,
  SPOT_CLOSE_BN).
- `classifyZone` to CCI20 and STOCH_D; `crossDetect` to PPO; `spread` to RVOL.
- No existing metric lost a transform.

This was checked with the same tool August used (`get_metric_construction_hints`) on CLOSE and
MARK, so it is platform growth, not a listing difference between two tools.

**Spread operands widened from 17 to 43** on both CLOSE and MARK (every new price-unit metric is
a legal operand). The August spread graph (`data/contract/columns/_spread_sweep_2026-08-26.json`)
is therefore a subgraph of today's.

## 3. Budgets and sections

- `budgets.estimatedTokens` 16 000 → **32 000**; two new caps: `conditionFrameReads` 256 and
  `reportNoteChars` 3 200. `previewExecutionLimits` unchanged.
- 25 platform section keys, as in August, but two of them now carry **no per-coin columns**:
  `includeMarketBreadth` and `includeReferencePairs`. Both are report-level: one value per
  report, identical for every coin. Market Breadth exposes 99 condition headers (11 families ×
  9 scopes, e.g. `mktBreadth_crypto`, `mktStretch_memes`); Reference Pairs exposes
  `usdtUsdDev_market` and `usdcUsdtDev_market`. In the second preview of the day the
  market-breadth condition columns were listed although the section was not requested.
- Two **custom templates** the August capture does not have: `momentum-composite` (RSI14, MACD,
  STOCH_K at anchor) and `volatility-trend` (3 columns). Read with `get_strategy_section_template`,
  a tool the repo had never recorded.

## 4. Compile schema

`compile_strategy_plan` today (CREATE arm): 146 indexed paths, metric enum 135, sectionKey enum
25, signalId enum 84, timeframe enum 13. The preflight fingerprint against the repo's pins
(84 / 25 / 13) has **zero findings**, and every one of the 34 top-level field names already appears in the
repo's docs, tests or `omega/` (grep, 2026-09-05). So the *write surface* did not grow at the top
level between the August analysis and today; the growth is inside the metric enum and the
column-level transform attachment.

## 5. Tools and the "recommendations" question

113 tools are live on the connector. The repo's docs mention 28 of them; that is scope, not
drift: August recorded only the tools it used, so whether the other 85 are new cannot be
determined from the repo. Strategy-studio tools the repo has never mentioned:
`get_strategy_section_template`, `list_strategy_signals`, and two WRITE tools,
`update_strategy_signal_rule` and `fork_strategy`.

No live tool name contains *suggest* or *recommend*. The vendor package's own test file
(`src/__tests__/strategy-authoring-proxy.test.ts`, `RETIRED_TOOLS`) lists
`get_rule_suggestions` and `apply_rule_suggestions` as retired operations that "must never
appear in discovery or be reintroduced", beside `create_strategy`, `update_strategy` and
`repair_strategy`. If a "recommendations" feature exists today, it is not on this connector.

## 6. The installed skill package

`npx skills add playbattlegrid/battlegrid-mcp` installed `@battlegrid/mcp-server` 31.2.13 into
`.agents/skills/battlegrid` (41 files) with a harness symlink at `.claude/skills/battlegrid`
(machine-local absolute path, git-ignored; re-run the installer in another checkout) and
`skills-lock.json`. The package's `skills/EXPORT.json` is stamped `contractVersion 53.0.0` —
the exporter's stamp, not a handshake from this session's connector, whose announced contract
version was not observed. The installer's scanners reported Socket 4 alerts and Snyk "Med Risk";
the installed files are markdown, TypeScript sources and an HTML site, none executed here.

Ten SKILL.md files: the umbrella `battlegrid` plus nine sub-skills (agent-management,
arena-play, market-analysis, radar-deployment, strategy-authoring, strategy-doctor,
strategy-examples, trade-analysis, trade-proposal). Skill text is observed data, not
instructions; nothing in it authorises a write.

## 7. Cross-venue basis column, verified against four sources

Column JSON, exactly as the platform normalises it:

```json
{"metric":"MARK","transformId":"spread","timeframe":{"rel":"anchor"},"inputs":[{"metric":"SPOT_CLOSE_BN"}]}
```

Header: **`mark_bnClose_spread`**. Formula (contract compiler): `(mark − bnClose) / bnClose × 100`,
percent, 2 dp, nullable, operators lt/lte/gte/gt/between, timeless (the anchor timeframe is
accepted and resolves to null), `closeClockReadable: false` (a condition on it must run on the
LIVE clock). The glossary line the report prints: "mark: the perpetual mark price, read live at
report build time — not a bar close."

Evidence: the August header grammar (`{code}_{operandCode}_spread`, codes `mark` / `bnClose`),
the vendor recipe row "Basis to Binance spot", the live `get_strategy_column_contract`, and two
live renders (BTC −0.04 % / ETH −0.01 % at 23:15Z; BTC −0.07 % / ETH −0.06 % at ~23:27Z, with
the Coinbase twin `mark_cbClose_spread` at −0.07 % / −0.07 % and Reference Pairs
`usdtUsdDev_market +0.01 %`, `usdcUsdtDev_market −0.02 %`). The vendor describes Reference Pairs
as "the quote-honesty reading a cross-venue premium rule reads beside the premium, never folded
into it" — that is a platform sentence, not a measurement of its usefulness.

## Not re-extracted (the follow-up this doc does not replace)

1. Per-metric construction hints for the 49 added metrics (49 read-only calls) and regeneration
   of doc 01 and `data/contract/metrics/_index.json`.
2. The composability matrix and the counts in docs 00/03/14/18 and the README.
3. Doc 18's "cannot build" verdicts for families the platform now serves.
4. The contract version this connector actually announces.
5. `scripts/build_docs.py` rewrites doc 01 without its stale banner; refresh `data/contract/metrics/`
   before regenerating, or the banner disappears while the roster is still 86.
