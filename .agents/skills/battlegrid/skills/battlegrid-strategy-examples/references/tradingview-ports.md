# TradingView ports — familiar processes in studio vocabulary

Per-script port recipes. Each ports the PROCESS (regime filter -> setup state -> trigger -> stop
engine) and names its substitutions where the catalog lacks a primitive.

**Contents**
- Squeeze Momentum [LazyBear] / TTM Squeeze
- Supertrend / UT Bot / Chandelier Exit
- MACD + 200 MA filter
- Golden / Death Cross
- RSI-2 (Connors)
- VWAP reversion
- Donchian / Turtle breakout
- ICT / SMC (FVG + order blocks)
- Now native, formerly substituted

## TradingView ports — familiar processes, studio vocabulary

Players often ask for strategies by the name of a popular TradingView script. Port the
**process** (regime filter → setup state → trigger → stop engine), and where the catalog lacks
the primitive, name the substitution in the spec-lock question — never present a substitute as
the thing itself. Most TV strategies run on the daily chart: carry that with the
daily-strategy pattern above (pinned-1d thesis at `offset: 1` on an intraday anchor), which
binds decisions to daily closes while the studio keeps managing risk intraday.

Event-column behaviour, state-vs-event, `PDH`/`PDL` binding and the squeeze's anchor calibration are
rules about the columns themselves, not about porting — they live in the skill body's
`## Header grammar` and `## Conditions`. Read those first; this document is the per-script recipes.

- **Squeeze Momentum [LazyBear] / TTM Squeeze** → `KC_SQUEEZE is "on"` is the native one-condition
  read: the Bollinger pair sitting inside the Keltner channel, at the script's own multiplier.
  The four boundaries stay addressable, so `BB_UPPER spread KC_UPPER` and
  `BB_LOWER spread KC_LOWER` still express the same reading at a threshold you choose. Release
  direction from the MACD trajectory, `bollinger_squeeze` Critical-required.
  Its selectivity is anchor-dependent — see `## Conditions` in the skill body before gating on it.
  (`bbWidthPct_rank_lo` + `ADX lt 20` remains a serviceable board-relative compression proxy, but it
  is no longer the only option.)
- **Supertrend / UT Bot / Chandelier Exit** → `ST_LINE` and `ST_DIR` are native, so the regime
  half is a direct port: `ST_DIR is "bullish"` as the persistent state, `dist_ST_LINE` for
  distance to the plotted stop. The plotted trailing line is still best executed by the studio's
  own stop engine — `trailingTriggerR: 0` (trail from entry), giveback ~30–40 (tight factor) or
  45–55 (loose/chandelier) — because a trailing stop is a position-management mechanism, not a
  column. `ST_DIR` is a persisting state and not a flip event — see `## Conditions` in the
  skill body — so the FLIP needs an event column beside it. Name that as a substitution.
- **MACD + 200 MA filter** → `ABOVE_200` building block (`dist_SMA200 gt 0`) referenced by a
  carrier with `MACD_cross is "Bullish"`; rules `macd_bull/bear_cross` 3 required +
  `ma_sma200_above/below` 2 required; swing-trend geometry.
- **Golden / Death Cross** → `SMA50 spread SMA200 × trajectory` gives state and freshness:
  `SMA50_SMA200_spread_now gt 0` AND `_trend is "rising"`; optional breadth gate on
  `mktBreadth_crypto gte 0` — every published scope resolves, not only `all`, because the leg reads
  the `(timeframe, scope)` pairs a condition names; position-persona geometry. `SMA50 × SMA200` is
  the canonical definition and stays the default port; `EMA50` is available as the crypto variant
  when a player asks for it by name.
- **RSI-2 (Connors)** → `RSI2` is native, so this ports exactly: `RSI2 lte 10` gated by required
  `ABOVE_200`; the source's fast exit is time — timeDecay ON (180/60, 15→50, stale 20);
  `rsi_oversold` 3 required with a tuned threshold. Keep the literal `lte 10` as the GATE:
  `RSI2 × classifyZone` exists and reads on the same Connors bands, but a zone label is a fixed
  reading while the literal is a threshold the author can see and tune. Use the zone as a report
  column, never as the substitute for the gate.
- **VWAP reversion** → `dist_VWAP` band + `dist_VWAP_rank_far lte 5` for board-relative
  stretch; required `NOT [ADX_state in ["trending","extreme"]]` veto; scalp geometry +
  aggressive timeDecay (VWAP anchors daily at 00:00 UTC).
- **Donchian / Turtle breakout** → `zone is "breakout high"` + `dist_donchianHi gte 0` +
  `RVOL gte 1.5`; `sr_resistance_break` 3 required; turtle exits = trend preset (trail from
  1R, giveback 50). Mirror with `"breakdown low"`. **Daily-breakout variant on any anchor:**
  pin the structure at 1d — `zone_1d is "breakout high"`, `dist_donchianHi_1d gte 0` (validated).
  **Literal previous-day levels are native**: `dist_PDH gte 0` composes directly. Their `{abs: '1d'}`
  binding is stated in `## Header grammar` in the skill body.
- **ICT / SMC (FVG + order blocks)** → `STRUCT_ZONES` is the native zone engine:
  `zones_htf_support_type` (`bullish FVG`/`bullish order block`), `zones_htf_support_dist
  between -1.5 0`, `_age_h gte 12`, HTF bias required via `MAalign_htf`; rules
  `structure_fvg_approach`/`structure_ob_approach` required (their `proximityPct` is the
  in-zone dial). Liquidity sweeps, displacement, killzones and event *sequencing* are shapes the
  grammar does not have — a clause compares one column against a literal, so an ordered sequence
  of events cannot be stated at all. That is a grammar limit, not a missing metric; name it as
  one.
- **Now native, formerly substituted** — WaveTrend (`WT1`/`WT2`), QQE (`QQE_RSI_MA`/`QQE_STOP`),
  Hull (`HMA20`), Ichimoku (`ICHI_CONV`/`ICHI_BASE`/`ICHI_SPAN_A`/`ICHI_SPAN_B`/`ICHI_LAG`),
  Parabolic SAR (`PSAR`), Keltner (`KC_UPPER`/`KC_MID`/`KC_LOWER`), daily pivots
  (`PIVOT_P`/`PIVOT_R1`–`R3`/`PIVOT_S1`–`S3`), Williams %R (`WILLR14`), Stochastic RSI
  (`STOCH_RSI14`), the TTM squeeze (`KC_SQUEEZE`), Connors RSI-2 (`RSI2`), the 9/21/50 EMAs
  (`EMA9`/`EMA21`/`EMA50`), and literal previous-day levels (`PDH`/`PDL`). Port these directly —
  do not offer a substitute for a primitive the catalog serves.
