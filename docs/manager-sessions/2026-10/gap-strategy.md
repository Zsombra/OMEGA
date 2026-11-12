# Gap analysis: the strategy and condition model, contract 110.10.0 to v123

Date: 2026-10-20. This was read-only research. No repo file was edited, no BattleGrid call was made, and no subagent was dispatched.

**Sources:**
- Vendor README: `C:/tmp-bg-gap/README.md`, sections v111 to v123.
- Vendor skills at contract 122.0.0: `C:/tmp-bg-gap/repo/skills/` (EXPORT.json `contractVersion: "122.0.0"`), and the proxy digest `C:/tmp-bg-gap/repo/src/__fixtures__/authoring-contract-digest.json` (122.0.0).
- Baseline: `battlegrid-manager/.agents/skills/battlegrid/skills` (EXPORT.json 110.10.0). OMEGA's copy `.agents/skills/battlegrid` is byte-identical to the manager's (`diff -rq`: no output).
- Code read:
  - **OMEGA:** the code pinned by the manager, `v0.8.2`, which is commit `10bdb67` (`manager/omega_pin.py:21-24`). The worktree HEAD `ac39055` does **not** contain `10bdb67`. It lacks v0.8.2's MFI change, but every line cited below is the same in both.
  - **Manager:** branch `main` at `efa7589`.

## 0. Headline

1. **The condition grammar itself did not move between 110.10.0 and 122.0.0.** I diffed the vendor's authoring digest at 110.10.0 against the one at 122.0.0. The only change is the version string. Everything else is identical:
   - the create, entry, condition, customSection, tradeLevels and positionManagement axis lists;
   - the entry-trigger domain;
   - the `columnBars` domain;
   - the verdict domain;
   - the 13 clause operators;
   - the entry bounds;
   - every dial;
   - all 177 metric keys.
2. **The "new condition base" is v123.** It renames eighteen report header stems so that a metric's code ends with its indicator's length. This is the one change since 110.10.0 that makes something we send get refused. **OMEGA emits three of the retired headers in its condition clauses**, so 3 of the 5 presets will be refused at stage.
3. **v117 adds a read-legality rule** that OMEGA's offline checker does not model. It is latent: no preset uses it today.
4. The **122.0.0 vendor skills predate v123**. They still print the old stems (`ADX_state`, `donchianHi increased`, `bbUpper_lvl`, `dist_donchianHiPrior`, `RVOL gte 1.5`, `pctB gte 0.85`). Do not copy header literals from them.

## 1. Every strategy/condition change since 110.10.0

### 1.1 v123: a metric's code states its indicator's length (BREAKING, refuses input)

The rule, quoted from README v123, "Rejected input":

> "A condition column or a `{…}` Market Read marker naming a retired header is refused. A metric's code now ends with its indicator's single length"

| Before (code) | v123 (code) | Metric key (unchanged) |
|---|---|---|
| `CCI` | `CCI20` | `CCI20` |
| `ADX` | `ADX14` | `ADX` |
| `ATR` | `ATR14` | `ATR` |
| `BBwidth` | `BBwidth20` | `BB_WIDTH` |
| `pctB` | `pctB20` | `BB_PCT_B` |
| `donchianHi` / `donchianLo` | `donchianHi20` / `donchianLo20` | `DONCHIAN_UPPER` / `DONCHIAN_LOWER` |
| `donchianHiPrior` / `donchianLoPrior` | `donchianHiPrior20` / `donchianLoPrior20` | `DONCHIAN_UPPER_PRIOR` / `DONCHIAN_LOWER_PRIOR` |
| `donchianBrkHi` / `donchianBrkLo` | `donchianBrkHi20` / `donchianBrkLo20` | `DONCHIAN_BROKEN_HI` / `DONCHIAN_BROKEN_LO` |
| `bbUpper` / `bbLower` | `bbUpper20` / `bbLower20` | `BB_UPPER` / `BB_LOWER` |
| `willR` | `willR14` | `WILLR14` |
| `stochRSI` | `stochRSI14` | `STOCH_RSI14` |
| `DIplus` / `DIminus` | `DIplus14` / `DIminus14` | `DI_PLUS` / `DI_MINUS` |
| `RVOL` | `RVOL20` | `RVOL` |

That is 18 stems. OMEGA's extracted corpus carries exactly these 18 old codes (checked: all 18 found, none missing).

Further rules from the same section:
- **Affixes are kept.** "Every suffix and prefix is kept (`ADX14_state`, `dist_donchianLo20`, `RVOL20_rank_hi`)". So the header grammar `<code>[_<tf>][_dev][_o<N>]` + transform suffix is unchanged; only `<code>` moved. For example, `ADX_now` becomes `ADX14_now`, `pctB_now` becomes `pctB20_now`, `ATR_trend` becomes `ATR14_trend`, and `bbUpper_4h_lvl_b25` becomes `bbUpper20_4h_lvl_b25`.
- **Keys do not move.** "Metric **keys** do not move (`ADX`, `RVOL`, `DONCHIAN_UPPER`), so a column you author by key is unchanged. Stored strategies, agents, drafts and open positions are rewritten on the server."
- **Reshaped output:** "Rendered headers, condition columns, glossary entries and catalog `code` values serve the new stems. A client that matches a header by its old text no longer finds it."
- **Market Read budget:** "`list_strategy_vocabulary`'s `budgets` gains required `marketReadChars` … A strategy's `marketReadText` now runs to 4,000 characters, where 2,000 was the bound."
- **Widened input:** "Seven metric keys are added: `CLOSE_LOCATION`, `PRIOR_SWING_FRACTAL_HIGH`, `PRIOR_SWING_FRACTAL_LOW`, `SWING_FRACTAL_HIGH_BARS_AGO`, `SWING_FRACTAL_LOW_BARS_AGO`, `CMF20` and `EMA8`." None of them is in OMEGA's corpus, and none is in the 122.0.0 digest.

### 1.2 v117: decided changes read at their horizon bar (BREAKING, behind unchanged schemas)

The rule, quoted:

> "A verdict carrier or hold that reads a change over a horizon above the strategy timeframe is refused. That is `chg4h` and `chg24h` on a `1h` strategy, and `oiRegime` (the `1h` change) below `1h`. Such a change is a developing read whatever its selector."

- **Where it is refused:** "a strategy save, draft stage or preview, refused `CONDITION_VERDICT_READ_ILLEGAL` or `CONDITION_HOLD_ILLEGAL`". Restoring an archived strategy that holds one is refused the same way.
- **Semantics:** "A change is the frame's price against its horizon bar's open … a horizon whose bar was not read is UNRESOLVED where it read FALSE."

The skill at 122.0.0 (`battlegrid-strategy-examples/SKILL.md` § verdict read rule and § holds) adds these lines:
- `DEVELOPING`: "a Developing candle column above the strategy timeframe, or a change over a horizon above it."
- `NOT_REWINDABLE` now lists "a change at or below the strategy timeframe" in place of "published rolling changes".
- "A change (`chg5m` … `chg24h`, and `oiRegime`'s `1h` change) carries its horizon in the metric, so above the strategy timeframe it is Developing at every rung and under every selector."
- The remedy: "Read a horizon at or below the strategy timeframe instead, or a Confirmed `CLOSE_CHANGE` on the higher timeframe."
- **Playbook 2 changed** (`references/playbooks.md`): `CHG_24H value` → `chg24h` became `CLOSE_CHANGE value @ {abs: 1d}` → `closeChg_1d`, with `FADE_SHORT` reading `closeChg_1d gte 5` and `SQUEEZE_LONG` reading `closeChg_1d lte -5`.

### 1.3 Event columns: a null reads FALSE (a documentation correction, no changelog entry)

At 110.10.0 the skill said event columns are null off-event, "which reads as UNRESOLVED". At 122.0.0 it says:

> "a null reads FALSE … A condition that treats an event column as a standing state reads FALSE on nearly every bar, so it is TRUE only on the crossing bar itself."

`recipes.md` was corrected the same way. The 110.10.0 skill already said "a bar with no value (a null) reads FALSE" for the prior-bar operators, so this fixes an internal contradiction; it is not a server change. The practical effect: an event column inside a `NOT` is TRUE on almost every bar.

### 1.4 v111: draft tools flat (already handled)

`stage_strategy_draft({ strategyId, draftVersion, axes })` replaces the `request` envelope (the skill diff in `SKILL.md` §4 and `strategy-stage-examples.md`). OMEGA v0.8.1+ and the manager already send it flat (`omega/generate.py:981`, `manager/authoring/preflight.py:107`).

### 1.5 What did NOT change (v111 to v123)

The digest diff and the skill diff are both empty for each of these:
- condition shape `{conditionKey, name, definition, verdict, required, exitSide}`;
- groups `ALL|ANY|NOT|N_OF`, depth ≤ 2;
- the required `hold {atLeast, of}`;
- `conditionRef`;
- verdict resolution (distinct verdicts; disagreeing carriers → `NEITHER`);
- the required/entry-gate rule (`NO_ENTRY_CONDITION`);
- the 13 operators;
- entry triggers (`ON_CANDLE_CLOSE | ON_RETEST | STOP_THROUGH_LEVEL`, `levelOffsetAtrMultiple` ≤ 2, `validForBars` ≤ 24);
- trade levels (`min/maxStopLossAtrMultiple`, `minRiskRewardRatio`, `minAtrPct`);
- the position-management dials (break-even, trailing, time decay, `decisionInvalidationExitEnabled`) and their bounds;
- sections (`benchmarkTicker`, `sectionKey` rules).

The other contract changes are outside the strategy model and only touch the manager's transport and read paths:
- v112: input renames;
- v113/v114: cursors;
- v116: SDK and protocol;
- v118/v118.1: error envelope;
- v119/v120: output reshapes;
- v122: officers.

The manager has already acked through 120.3.0. It still has to ack v122 and v123.

## 2. Where OMEGA and the manager are now wrong or stale

Each finding is labelled with what it causes: **REFUSED** (refused at stage or preview), **MEANS-DIFFERENT** (accepted, but it means something else), **STALE** (wrong text or prediction, nothing refused) or **UNAFFECTED**.

### 2.1 OMEGA hard-codes three retired headers in condition clauses (REFUSED)

`omega/generate.py` `MODULE_CLAUSES` (same lines at v0.8.2 `10bdb67` and in the worktree):

| Line | Clause | v123 header | Module → presets |
|---|---|---|---|
| 165 | `num("ADX_now", "gte", 25)` | `ADX14_now` | TREND_STRENGTH → `trend-continuation` |
| 166-169 | `num("pctB_now", …)` ×4 | `pctB20_now` | BOLLINGER → `mean-reversion`, `squeeze-breakout` |
| 174 | `is_("ATR_trend", "rising")` | `ATR14_trend` | VOLATILITY → `mean-reversion`, `squeeze-breakout` |

The presets are at `generate.py:304-339`.

- **Refused at stage.** Any thesis that weights BOLLINGER, TREND_STRENGTH or VOLATILITY is refused at `stage_strategy_draft` and at `preview_strategy_report`. That covers 3 of the 5 presets and any strategist-chat thesis that picks those modules. `flow-divergence` and `structure-reversal` are unaffected: their clause headers (`perpSpotFlow`, `CVD_trend`, `rate`, `OI_trend`, `zones_*_dist`, `zone`, `RSI14_now`) were not renamed.
- **Invisible offline.** OMEGA validates clauses against headers it predicts from the same stale codes (`omega/conditions.py:536-596` `report_headers` → `fanout.outputs_for`), so `validate_conditions` passes and the manager's verdict is PASS. The refusal appears only when the manager's STAGE_STRATEGY write runs (`manager/actions/strategy_send.py`).
- **A plain re-extraction is not enough.** Re-extracting the corpus alone would make OMEGA fail its own validation: it would predict `ADX14_now` while the clause still names `ADX_now`. `MODULE_CLAUSES` must change with the data, or be derived from `outputs_for`.
- **The free model sees the old names.** The same literals reach the model through `omega.authoring.vocabulary()` → `readings` (`omega/authoring.py:46-60`), which `manager/strategist/turn.py:113-115` (`_menu`) puts in the system prompt.
- **Tests assert the old headers:** `tests/test_conditions.py:344-345` (`pctB_now`) and `tests/test_axes_update_section_keys.py:135` (`ADX_now`).

### 2.2 OMEGA's metric catalog carries the old `code` values (STALE; the root of 2.1 and 2.3)

- **What is stale:**
  - `data/contract/metrics/*.json` `code` holds the 18 old codes (e.g. `ADX.json` `"code": "ADX"`, `CCI20.json` `"code": "CCI"`, `WILLR14.json` `"code": "willR"`).
  - `data/contract/_manifest.json` reads `servedContractVersion: "110.8.0"`, with `writeSurface.servedContractVersion: "110.13.0"`.
  - OMEGA's vendored skill pack and digest are at 110.10.0.
- **How headers are built:** `omega/contract.py:159` loads `code=rec["code"]`, and `omega/fanout.py:83` (`_token`) builds every header from it. Line 102 builds the spread operand from it too. So the builder is data-driven and correct in form; only its data is stale.
- **What it affects:**
  - Every predicted header for those 18 metrics is wrong: `RVOL_t3…RVOL_trend` (VOLUME recipe, `generate.py:79`), `ATR_*` (84), `pctB_*` (87), `ADX_*` (98), `dist_donchianHi` / `dist_donchianLo` (115-116).
  - These sit in REPORT only, and columns are authored by key, so the stage accepts them (**UNAFFECTED at stage**).
  - OMEGA's brief, its header list and the `cost()` header names are wrong (**STALE**). The header count and the budget estimate do not move.
- **Smaller stale data:**
  - `data/contract/columns/_observed_vocabulary.json` is keyed `ADX_zone` (read at `conditions.py:118,809`), so the vocabulary lookup for `ADX14_zone` misses.
  - About 20 measurement records in `data/contract/columns/*` cite old headers. They are history and need not be rewritten.

### 2.3 Revise flow: header-keyed carry-forward misses (STALE, a cosmetic diff)

The server has rewritten every live strategy and draft to the new stems. The revise chat passes `current_axes` (new stems) to `Thesis.axes_update` (`omega/generate.py:531-612`, rule text at 566-574). There, "a generated clause … takes the key the current clause with the same `conditionKey` and the same `header` carries". When OMEGA's header is `ADX_now` and the current one is `ADX14_now`, nothing matches, so `sectionKey` is left null. That is the 14-changes-of-no-substance diff of manager action 62 again. Once 2.1 is fixed, the stage is refused instead, so this goes away with the fix.

### 2.4 OMEGA does not model the v117 horizon rule (REFUSED; latent today)

`omega/conditions.py:588` sets `developing = above and column.bars == "all"`. The carrier check at `conditions.py:1073-1078` (`CONDITION_VERDICT_READ_ILLEGAL`) and the hold check `_holdable` (`614-637`) both key off it.

- **The gap:** under v117, a `CHG_4H` / `CHG_24H` (and `CHG_1H` below 1h, `CHG_15M` below 15m, …) and `OI_PX_REGIME` below `1h` are Developing at every selector. OMEGA marks them not developing, so a verdict carrier reading `chg24h` on a 1h anchor passes offline and is refused at stage. For holds, OMEGA only warns, because CHG_* are timeless (`moved=False`, so `_holdable` is False), while the server refuses.
- **Exposure today:** none of the 17 `MODULE_RECIPES` reads a CHG_* metric. `OI_PX_REGIME` (`generate.py:137`) is in OPEN_INTEREST, and its clause reads `OI_trend` (from `OI`), not `oiRegime`. So no preset is hit.
- **When it bites:** as soon as the assistant composes custom columns (see §3).

### 2.5 Market Read cap is 2,000 in OMEGA (STALE, too strict)

`omega/conditions.py:1179-1181` refuses `marketReadText` over 2,000 characters. The platform bound is now 4,000 and is served as `budgets.marketReadChars`. Nothing is refused that the platform would accept the other way round. The `{…}` markers OMEGA writes reference condition keys (`market_read_text`, `conditions.py:1192`), so v123's marker refusal does not hit the presets. A hand-written marker on a renamed header would be refused.

### 2.6 Manager drift guard is blind to header renames (STALE, a false PASS)

- **What the guard compares:** `manager/authoring/preflight.py:291-317` `pin_drift` → OMEGA `scripts/compare_vocabulary.py:83-119` compares metric keys and section keys only. v123 moved no key, so the guard reports no `storedNotLive` error.
- **What it will report:** the seven added keys become seven `VOCABULARY_MOVED metrics.liveNotStored` warnings (`preflight.py:268-288`, warning severity by the 2026-10-09 ruling). The plan's verdict stays PASS while its body carries refused headers.
- **What is missing:** a code-level comparison (catalog `code` from `get_metric_construction_hints`, or the glossary) would have caught v123.

### 2.7 Manager direction lines: glossary keyed by old headers (STALE, cosmetic)

`manager/strategist/direction.py:14-32` `GLOSSARY` has `"pctB_now"` (19), `"ADX_now"` (25) and `"ATR_trend"` (29). The direction-line headers come from the plan's own CONDITIONS, so the lines stay correct. After the fix, or on any live strategy (already rewritten), the three glosses are simply not shown. **MEANS-DIFFERENT: no. REFUSED: no.**

### 2.8 Stored plan bodies (REFUSED if sent)

- **Manager:** any `strategy_plans` row built by OMEGA v0.8.2 with BOLLINGER, TREND_STRENGTH or VOLATILITY carries `ADX_now` / `pctB_now` / `ATR_trend` in `request.axes.CONDITIONS`. Sending it is refused. The body sha (`manager/actions/strategy_describe.py:150`) pins the OMEGA tag, so after the fix the plan must be re-planned, not re-sent.
- **OMEGA:** its own `data/created/*.json` records are history.

### 2.9 Unaffected (checked)

- **Event-column null → FALSE (§1.3):** OMEGA's directional clauses never read an event column. `MACDhist_cross` and `ROC12_cross` are in REPORT only, and MACD gates on `MACDhist_trend`. The renderer in `direction.py` does not interpret nulls.
- **Untouched stems:** `MACDhist`, `PPOhist`, `K`, `MFI14`, `RSI14`, `OBV`, `CVD`, `MAalign`, `zone`, `rate`, `OI`, `regTrend`, `perpSpotFlow` and the ambient headers were not renamed.
- **Manager schema check:** `preflight.py:166-180` already validates on Draft 2020-12 with `$defs`, which is v116's dialect. The stage schema types `column.header` as a string, so the schema check cannot see a retired header. Only the stage sees it.
- **Manager prose:** `manager/strategist/brief.md` and `proof_prompts.json` name no renamed header. `turn.py:62` mentions "ATR trend" only in prose.
- **Research scripts:** `scripts/verify_conventions.py` (`CCI`) and `scripts/verify_tier_b.py` (`pctB`, `BBwidth`) are research that reads panel column names. They are STALE only if re-run against post-v123 panels.

## 3. What OMEGA's assistant should support but doesn't

The strategist composes only from 17 fixed modules with fixed clause factories (`MODULE_RECIPES` / `MODULE_CLAUSES`) and the five presets. Compared with the grammar the 122 skills document:

1. **Custom thesis columns.** The skill calls for "at least one custom section whose columns encode the thesis". OMEGA writes only recipe columns. There is no path from a user idea to an arbitrary `{metric, transformId, timeframe, …}` column plus a clause on its header. Once this exists, the v117 rule (§2.4) becomes live.
2. **Pinned higher-timeframe reads.** These are `{abs:"1d"}` columns, `bars:"closed"`, `_o<N>` offsets, and the skill's "daily-strategy pattern": anchor 4h, pinned-1d required conditions. `_token` already predicts them, but no recipe or thesis field emits them. This is also the v117 remedy (`CLOSE_CHANGE @ {abs:1d}` → `closeChg_1d`).
3. **Prior-bar operators in module clauses.** `conditions.py:263-298` has builders for `crossesAbove`, `crossesBelow`, `increased`, `decreased`, `enters` and `exits`, but no `MODULE_CLAUSES` entry uses them. The skill's recipes include `dist_SMA20 crossesAbove 0`, `RSI14_zone enters "overbought"`, `kcSqueeze exits "on"`, Donchian/Turtle `dist_donchianHiPrior20 crossesAbove 0` and failed breakout `donchianHiPrior20_lvl is "reject_from_below"`.
4. **Entry triggers.** `ENTRY_MIRROR = {"trigger": "ON_CANDLE_CLOSE"}` (`generate.py:349`) is the only trigger. `ON_RETEST` and `STOP_THROUGH_LEVEL` (`levelOffsetAtrMultiple` 0–2, `validForBars` 1–24) are not offered.
5. **Benchmark sections** (`benchmarkTicker: "BTC"`, the market-leader regime gate; playbooks 3 and 4). OMEGA always sends `benchmarkTicker: None` (`generate.py:809,871,876`).
6. **New metrics:**
   - v123 adds `CLOSE_LOCATION`, `PRIOR_SWING_FRACTAL_HIGH` / `_LOW`, `SWING_FRACTAL_HIGH_BARS_AGO` / `_LOW_BARS_AGO`, `CMF20` and `EMA8`;
   - the existing swing structure (`SWING_FRACTAL_HIGH`, `SWING_FRACTAL_LOW` and `SWING_FRACTAL_LABEL` `HH/HL/LH/LL`, with "bullish break of structure" = `dist_fractalHi`) has no module.
7. **Market Read at 4,000 characters,** read from `budgets.marketReadChars` instead of a constant.

## 4. Prioritised fix list

**BLOCKING** means it would be refused at stage. Order matters.

1. **BLOCKING: rename the three clause headers in OMEGA** (`omega/generate.py:165,166-169,174` → `ADX14_now`, `pctB20_now`, `ATR14_trend`) **together with** the corpus `code` values (2). Better: derive each module clause's header from `outputs_for(<the recipe column>)` instead of a literal, so the next rename moves it automatically. Update `tests/test_conditions.py:344-345` and `tests/test_axes_update_section_keys.py:135`. Without this, 3 of 5 presets and every BOLLINGER, TREND_STRENGTH or VOLATILITY chat thesis is refused at stage.
2. **BLOCKING-adjacent: move the 18 codes in `data/contract/metrics/*.json`.** Record the move as `data/contract/metrics/_moves_123.json` (the same pattern as `_moves_110.json`), quoting README v123. Then verify by re-extraction (`scripts/refresh_metric_contracts.py`, `get_metric_construction_hints` ×N, read-only) once the user allows platform reads. Re-stamp `_manifest.json`. Doing (1) without (2) makes OMEGA's own checker refuse the plan; doing (2) without (1) does the same.
3. **BLOCKING for the manager: re-pin and re-plan.** Tag OMEGA (v0.9.0) with 1+2, move `manager/omega_pin.py:21-24`, and re-plan any open `strategy_plans` row. Ack v122/v123 through `manager contract ack` after the drift review: writes are blocked until then (see memory "writes_blocked starves triage").
4. **STALE, but it hid this break: add a code check to the drift guard.** Compare catalog `code` (or the rendered glossary) between the pinned corpus and the live surface, in `compare_vocabulary.py` / `manager/authoring/preflight.py:pin_drift`. A renamed code should be an error, since OMEGA's clauses would be refused.
5. **REFUSED (latent): model v117 in `conditions.py:588`.** Mark a CHG_* column Developing when its horizon (5m/15m/1h/4h/24h) is above the anchor, and `OI_PX_REGIME` when the anchor is below 1h. Make the hold path an error for them, not a warning. Do this before (or with) any custom-column work (§3.1).
6. **STALE: refresh the vendored skill pack** in OMEGA and the manager to 122.0.0. It brings the flat stage args, null-reads-FALSE and the v117 text. Note in the vendoring commit that the 122 skills still print pre-v123 stems; when a 123 export ships, refresh again.
7. **STALE: raise the Market Read cap.** `conditions.py:1179-1181` should move from 2,000 to 4,000, or better, read `budgets.marketReadChars` from the stored vocabulary.
8. **STALE (cosmetic): update the direction glossary.** In `manager/strategist/direction.py:19,25,29`, add the new keys (`pctB20_now`, `ADX14_now`, `ATR14_trend`). Live strategies already render the new stems. Keep the old ones only if historical plans are shown.
9. **STALE (cosmetic): rename `_observed_vocabulary.json` `ADX_zone` → `ADX14_zone`.**
10. **NICE-TO-HAVE (assistant scope, §3), in suggested order:**
    1. prior-bar clauses (crossovers and enters/exits) in the module menu;
    2. pinned-1d columns and the daily pattern;
    3. custom thesis columns;
    4. `ON_RETEST` / `STOP_THROUGH_LEVEL` entry;
    5. benchmark sections;
    6. modules for the swing-structure metrics and the seven v123 keys, after they are extracted.
