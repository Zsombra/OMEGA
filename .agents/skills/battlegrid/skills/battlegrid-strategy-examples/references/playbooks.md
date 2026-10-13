# Playbooks — validated desk-grade compositions

Worked compositions for the strategy studio, each validated against the live grammar. Shapes are
binding; the tokens are illustrations and stay live-discovered.

**Contents**
- Playbooks (validated compositions)
- Using a playbook

Read `## Header grammar` and `## Conditions` in the skill body first — the rules about how columns
behave live there, not here.

## Playbooks (validated compositions)

*Validated* is a gate, not a claim: every playbook below is compiled against the live catalog by
`strategy-playbooks.compile.test.ts`, which fails the build if one stops assembling or if a header
its conditions name stops resolving. Edit a playbook and the gate re-checks it; move the grammar
underneath one and the gate catches that too.

### 1 · Volatility Compression Breakout — 4h swing

Custom `Squeeze Scan` (no `sectionKey` — this is a CREATE): `BB_WIDTH_PCT value` + `rank lo`, `ADX value`,
`RVOL value`, `BB_PCT_B value`, `CLOSE_CHANGE value`, `NOTIONAL_VOLUME_1D value`; plus platform
`includeStructureZones`. (No `includeBollingerBands`: it renders `bbWidthPct` and
`bbWidthPct_rank_lo` a second time, which makes both of `SQUEEZE_ON`'s clauses ambiguous, and the
custom section already carries them.) Conditions: `LIQUID_FLOOR` (required —
`vol24hUsd gte 25000000`); `SQUEEZE_ON` building block (`bbWidthPct_rank_lo lte 10` AND
`ADX lt 20`); `BREAK_UP` verdict UP (ref SQUEEZE_ON + `closeChg gt 0` + `RVOL gte 1.5` +
`pctB gte 0.85`); `BREAK_DOWN` verdict DOWN (mirror with `pctB lte 0.15`). Levels 0.75–1.75 ATR,
RR 2, ATR floor 0.8% — a compression play needs the expansion to be worth the stop. PM: BE 1R; trail 1.2R giveback 35 buffer 0.3.
Market Read: "Trade only expansions out of compression: {SQUEEZE_ON} must read TRUE… skip
anything failing {LIQUID_FLOOR}."

### 2 · Crowded-Positioning Fade — 1h intraday

Custom `Positioning`: `FUNDING_RATE value`→`rate`, `aggregate w24`→`rate_mean24`,
`FUNDING_ANN value`→`ann`, `OI_CHG value`→`oiChg`, `OI_PX_REGIME value`→`oiRegime` (vocab:
new longs / new shorts / short covering / long liquidation), `MARK spread ORACLE`→
`mark_oracle_spread`, `RSI14 value`, `CHG_24H value`→`chg24h`; plus `includeCvd`. Conditions:
`NO_LIQUIDATION_TAPE` required NOT-veto (`NOT [oiRegime is "long liquidation"]`);
`CROWDED_LONGS` building block (`ann gte 25` + `oiChg gte 3` + `oiRegime is "new longs"`);
`FADE_SHORT` verdict DOWN (ref + `RSI14 gte 65` + `chg24h gte 5`); mirrored `SQUEEZED_SHORTS`
/ `SQUEEZE_LONG` verdict UP. Levels 1.0–2.5 ATR, RR 1.5, ATR floor 0.5%. PM: BE 0.8R, no trail, timeDecay ON (120/60, 10→40, stale 25).

### 3 · Relative-Strength Rotation with a Benchmark Gate — 4h cross-sectional

Custom `Leadership`: `ROC12 rank hi` + `rank lo`, `RVOL rank hi`,
`EMA5 spread EMA13 × trajectory w4`, `NOTIONAL_VOLUME_1D value`. **Rank `ROC12`, not
`CLOSE_CHANGE`:** `closeChg` is the one magnitude-only rankable code, so `hi`/`lo` on it are
refused, and its legal `far` ordering sorts by |change| — which would put the session's biggest
losers in a "leaders" cohort. Custom `BTC Regime` with
`"benchmarkTicker": "BTC"`: `MA_ALIGN value`→`MAalign`, `ADX value`, `REGIME_TREND value` —
every row reads BTC. Conditions: `BTC_RISK_ON` building block (`MAalign is "bullish"` +
`ADX gte 20` — both read bare, since only this section renders them); `BTC_RISK_OFF`
(`MAalign is "bearish"`); `LEADER` (`roc12_rank_hi lte 5` + `RVOL_rank_hi lte 10` +
`vol24hUsd gte 100000000`); `ROTATE_IN` verdict UP (`ALL[ref BTC_RISK_ON, ref LEADER]`);
`ROTATE_OUT` verdict DOWN (`ALL[ref BTC_RISK_OFF, roc12_rank_lo lte 5]`). Levels 1–2 ATR, RR 1.8,
ATR floor 0.6%. PM: BE 1R; trail 1R giveback 45. Ranked cohort ≥ 40 —
rank conditions need a cohort wider than their thresholds.

### 4 · HTF Trend Pullback — 1h, multi-timeframe confluence

Platform `includeMtfConfluence` (`MAalign_ltf/…/_htf`, `RSI14_*_zone`, `ADX_*_state` vocab
weak/developing/trending/extreme), `includeMovingAverages` (`dist_EMA20`, …), `includeRsi`
(`RSI14_now`, `RSI14_zone`). These three render `MAalign` and `RSI14_zone` twice between them, so
every condition below reads a suffixed form — never bare `MAalign` or bare `RSI14_zone`, which
would be ambiguous. Conditions: `HTF_UP` building block (`MAalign_htf is "bullish"` +
`ADX_htf_state in ["trending","extreme"]`); `HTF_DOWN` mirror; `TREND_PRESENT` **required**
`ANY[ref HTF_UP, ref HTF_DOWN]` — chop blocks compose-trade entirely, before billing;
`PULLBACK_LONG` verdict UP (ref HTF_UP + `RSI14_now between 35 55` +
`dist_EMA20 between -3 0.5`); `PULLBACK_SHORT` verdict DOWN (mirror, 45–65 / −0.5–3). Levels
1–2.5 ATR, RR 2, ATR floor 0.7%. PM: BE 1R; trail 1.5R giveback 30 buffer 0.3.

### 5 · Perp/Spot Flow Divergence at Structure — 15m scalp

Platform `includePerpSpotFlow` (`perpSpotFlow` vocab: confirmed_bull / confirmed_bear /
perp_led_fragile / spot_led_accumulation / neutral), `includeStructureZones`
(`zones_htf_support_dist` signed % of price from the zone midpoint, positive above a support zone; `_age_h`), custom `Tape`
(`BUY_PRESSURE value`→`buyPres` 0–1, `RVOL value`, `CLOSE_CHANGE value`). Conditions:
`SPOT_ACCUM` (`perpSpotFlow is "spot_led_accumulation"`); `NEAR_SUPPORT`
(`zones_htf_support_dist between 0 2` + `zones_htf_support_age_h gte 12`); `DIP_BID` verdict
UP — refs plus an `N_OF(2)` quorum over `buyPres gte 0.55` / `RVOL gte 1.2` / `closeChg gt 0`
(quorum beats a brittle ALL); `FRAGILE_POP` verdict DOWN (`perp_led_fragile` +
`zones_htf_resist_dist between -2 0` + `RVOL gte 1.3`). Levels 0.5–1.2 ATR, RR 1.5, ATR floor
0.4%. PM: BE 0.7R; trail 0.9R
giveback 30 buffer 0.15; timeDecay ON aggressive (45/15, 15→60, stale 30).

## Using a playbook

Discover → confirm headers (`get_strategy_column_contract`, or one `preview_strategy_report` at
`detail: "detailed"`, whose `authoring.conditionColumns` lists every addressable header with
operators and vocabulary) → calibrate literals against the previewed live values → stage the draft
and fix what its diagnostics name → read it back and review the drafted conditions, then the draft's
own report preview — the conditions register (`gridConditions`), verdict tally, and
`marketReadMarkers` (fix `unknown` / `ambiguous` markers) → commit per the strategy-authoring flow. Coin selection is call context, not strategy
state: explicit tickers for focused work, `ranked` (with an optional category) for scanning books.
