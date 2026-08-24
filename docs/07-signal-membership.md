# 07 · Signal Membership

Which of the 84 signals can your report actually feed — answered offline.

[05](05-signal-aggregation-math.md) established the coupling: allocation converts evidence
into influence but cannot manufacture evidence. A `NOT_IN_REPORT` signal never fires, and
the aggregate's denominator counts **only signals that fired** — so it costs nothing
arithmetically. What it costs is **evidence**: you believe you have allocated weight to a
module and you have not. Your scorecard is narrower than it looks. Until now the only way
to check was `derive_strategy_rule_view`. This is the offline model, derived from 24 probes.

> **Corrected 2026-08-24.** This document previously said such a signal "actively
> suppresses your aggregate". It does not — see [12](12-routing-feasibility.md) for the
> four measurements that settled the denominator question.

---

## The rule

**Membership is module-level, not column-level** — and there are two ways in.

```
report metrics    →  signal modules  →  signals
platform sections →  signal modules  →  signals
```

Both routes reach the same **77 of 84** signals. Neither reaches CONFLUENCE or
COMPARISON.

Any **one** satisfying metric puts the module's **entire** signal set in report.
`RSI14` alone and `RSI7` alone unlock the identical 8 signals.

Three consequences worth internalising:

**The transform is irrelevant.** `RSI14 × value @ anchor` and `RSI14 × trajectory @ regime,
window 8` produce identical membership. Only *which metrics appear* matters — not how you
read them, not at what timeframe, not with what window.

**Rung variants come free.** A single `RSI14` column at `rel: anchor` unlocks `rsi_*`,
**`htf_rsi_*` and `ltf_rsi_*`** — with no regime or lower column anywhere in the report. The
platform provisions the other rungs itself. This is why a report can show signals you can't
account for from the column list.

**Membership is a union.** No probe showed a conjunctive requirement. Metrics never combine
to unlock something neither unlocks alone.

## The map

| Module | Signals | Satisfied by any one of |
|---|---:|---|
| RSI | 8 | `RSI14` `RSI7` |
| MACD | 4 | `MACD` |
| STOCHASTIC | 4 | `STOCH_K` `STOCH_D` |
| VOLUME | 4 | `VOLUME` `VOL_SMA20` `OBV` `RVOL` |
| VOLATILITY | 2 | `ATR` `ATR_PCT` |
| BOLLINGER | 5 | `BB_PCT_B` `BB_WIDTH` `BB_WIDTH_PCT` `BB_TOUCH` `CCI20` |
| MOVING_AVERAGES | 10 | `SMA20` `SMA50` `SMA200` `EMA5` `EMA13` `EMA20` `EMA_CROSS` `MA_ALIGN` |
| TREND_STRENGTH | 6 | `ADX` |
| FUNDING | 3 | `FUNDING_RATE` `FUNDING_ANN` `FUNDING_LABEL` |
| OPEN_INTEREST | 3 | `OI` `OI_CHG` `OI_VELOCITY` `OI_PX_REGIME` |
| RELATIVE_STRENGTH | 4 | `PPO` `ROC12` |
| SUPPORT_RESISTANCE | 4 | `SWING_HIGH` `SWING_LOW` `PRICE_ZONE` |
| MFI | 6 | `MFI14` |
| REGIME | 4 | `REGIME_TREND` `REGIME_VOL` `REGIME_MOM` |
| PRICE_STRUCTURE | 4 | `STRUCT_ZONES` |
| CVD | 4 | `CVD` `BUY_PRESSURE` `BUY_VOLUME` `SELL_VOLUME` `BUY_TRADES` `SELL_TRADES` |
| FLOW_DIVERGENCE | 2 | `SPOT_CVD` `PERP_SPOT_FLOW` `PERP_SPOT_STRENGTH` `PERP_SPOT_CONFIRMS` |
| **CONFLUENCE** | 4 | **unreachable — see below** |
| **COMPARISON** | 3 | **unreachable — see below** |

**52 of 86 metrics** feed a module. **34 feed nothing.**

## The 34 metrics that feed no signal

```
OPEN HIGH LOW CLOSE LAST MARK ORACLE SPOT_CLOSE_CB SPOT_CLOSE_BN BAR_FORMING
CLOSE_CHANGE CHG_5M CHG_15M CHG_1H CHG_4H CHG_24H
HIGH_DEV LOW_DEV
VWAP
TRADES NOTIONAL_VOLUME_1D
CROWD_PICK CROWD_UPBIAS CROWD_ACC CROWD_CAPT
CROWD_PICK_LIVE CROWD_UPBIAS_LIVE CROWD_ACC_LIVE CROWD_CAPT_LIVE SETTLED_AT
FLOW_ALIGN SMART_RETAIL CAPTAIN_CONF CONFIDENCE
```

These are not useless — they are **context the agent reads**, and price feeds the divergence
signals implicitly (every `*_divergence` signal lists `price` among its indicators). But
they unlock no scorecard signal. Budget them as narrative, not as evidence.

## Five results that contradict intuition

**`VWAP` feeds nothing.** The canonical mean-reversion reference does *not* satisfy
SUPPORT_RESISTANCE. Probe G5 contained `VWAP` and `sr_*` stayed out; probe G1 contained
`SWING_HIGH` and `sr_*` went in. **A VWAP-only mean-reversion panel feeds zero signals.**
Add `SWING_HIGH`, `SWING_LOW` or `PRICE_ZONE`.

**`BUY_VOLUME` and `SELL_VOLUME` feed CVD, not VOLUME.** Probes G6/G7 lit `cvd_*` and left
`volume_*` out. Participation and tape aggression are different modules — a buy/sell volume
panel gives you the second, not the first.

**`TRADES` feeds nothing, but `BUY_TRADES`/`SELL_TRADES` feed CVD.** Total trade count is
decorative for signal purposes; only the directional split counts.

**`CLOSE_CHANGE` feeds nothing.** RELATIVE_STRENGTH needs `PPO` or `ROC12` specifically.

**Every crowd and derived metric feeds nothing.** All 9 `CROWD_*` plus `FLOW_ALIGN`,
`SMART_RETAIL`, `CAPTAIN_CONF`, `CONFIDENCE`. The entire `includeCrowdIntelligence` and
`includeCvdCrowdConvergence` surface is read-only context.

## The boundary: 7 signals unreachable *through column design*

Two modules never went `IN_REPORT` in any probe.

> **Amended after reading a live signal log.** `comparison_sector_momentum` was observed
> **firing at runtime** — `triggered: true, score: 1.0, effectiveAllocation: 1`, contributing
> 7% attribution to a real trade. So these signals are not inert; they are simply not fed by
> report **columns**. COMPARISON is fed by the *comparison coin set* (benchmarks and sector
> peers, which the log carries with correlations), which is why a tool that derives
> membership from columns correctly reports it absent. See
> [10 · Outcome Feedback](10-outcome-feedback.md). The statement below is accurate for
> column design, which is what this document is about — but "unreachable" means "you cannot
> feed it by choosing columns", not "it never evaluates".

**CONFLUENCE** (`mtf_aligned_bull/bear`, `mtf_pullback_long/short`). These are
`kind: "synthesis"` — they fire off *other signals* firing, not off columns. Probe MTF
supplied `MA_ALIGN` at all three rungs plus `RSI14` and `ADX`; `ma_*`, `htf_ma_*`, `ltf_ma_*`,
`rsi_*` and `trend_adx_*` all went in, and all four `mtf_*` stayed out.

**COMPARISON** (`comparison_sector_divergence`, `comparison_btc_decorrelation`,
`comparison_sector_momentum`). Probe CMP set `benchmarkTicker: "BTC"` alongside `PPO`/`ROC12`;
`rel_*` went in, all three `comparison_*` stayed out. Setting a benchmark ticker is not
sufficient. These likely need the `includeReferencePairs` / `includeMarketBreadth`
machinery — both of which ship with **zero columns**.

The toolkit reports these as unreachable rather than guessing. **Don't budget allocation for
them from column design alone.**

## Platform sections — measured 2026-08-25

> **This section replaces an earlier claim that platform sections "behave
> inconsistently" and are "not modelled".** Both were wrong, and the second one was
> expensive. `omega.membership.analyse` iterated a report's sections but only
> `CustomSection` contributed metrics, so a platform-built report measured as **zero
> metrics** and `check_allocations` returned a confident `error` — *"the RSI module has
> no feeding column … Add one of: RSI14, RSI7"* — for a report the connector reports as
> having all 8 RSI signals in report. Every one of the 25 private strategies on this
> account is platform-sections-only, so the tool was wrong for **every strategy that
> exists**. All 25 sections have now been probed one at a time.

A platform section feeds **exactly one signal module, or none.** There is nothing
inconsistent about it:

| section | signals | module |
|---|---:|---|
| `includeRsi` | 8 | RSI |
| `includeMovingAverages` | 10 | MOVING_AVERAGES |
| `includeMfi` | 6 | MFI |
| `includeTrendStrength` | 6 | TREND_STRENGTH |
| `includeBollingerBands` | 5 | BOLLINGER |
| `includeMacd` `includeVolume` `includeStochastic` `includeRelativeStrength` `includeSupportResistance` `includeCvd` `includeRegimeContext` `includeStructureZones` | 4 each | MACD, VOLUME, STOCHASTIC, RELATIVE_STRENGTH, SUPPORT_RESISTANCE, CVD, REGIME, PRICE_STRUCTURE |
| `includeFundingRates` `includeOpenInterest` | 3 each | FUNDING, OPEN_INTEREST |
| `includeVolatility` `includePerpSpotFlow` | 2 each | VOLATILITY, FLOW_DIVERGENCE |

Seventeen sections, seventeen modules, no overlap. **Every count equals its module's
full size**, rung variants included — which is why `includeMovingAverages` measures 10
and not 6. And `includeRsi` alone gives membership *byte-identical* to a single `RSI14`
column: a section and its metric are interchangeable.

### The eight that feed nothing

```
includePriceAction   includeSubTimeframe   includeHigherTimeframe   includeMtfConfluence
includeCrowdIntelligence   includeCvdCrowdConvergence   includeMarketBreadth   includeReferencePairs
```

The earlier "inconsistency" was `includeMtfConfluence` yielding zero despite carrying
`MA_ALIGN`, `RSI14` and `ADX`. That is not inconsistency — CONFLUENCE is
`kind: "synthesis"`, so it fires off *other signals firing* and no section can feed it.
Same for COMPARISON, which is fed by the comparison coin set. The column list a section
carries was never the thing that determines membership.

**`includeHigherTimeframe` is the trap.** The section named for the higher timeframe
feeds **no `htf_*` signal at all**. Those come free with RSI, MOVING_AVERAGES and
TREND_STRENGTH. Enable `includeHigherTimeframe`, allocate 3 to `htf_rsi_oversold`, and
you have allocated to a signal that never fires. `check_allocations` now names this
case specifically.

### When a section is not in the map

If the platform adds a 26th section, `analyse` marks the report **incomplete** and
`check_allocations` degrades to `warn` — *"cannot determine … confirm with
`derive_strategy_rule_view`"* — instead of asserting NOT_IN_REPORT. A tool that says
"I don't know" is safe; one that invents a remedy is the bug this document is about.

## Using it

```python
from omega.membership import analyse, check_allocations, suggest_columns_for
from omega.types import Rule

print(analyse(report).render())
```

```
modules in report    5 / 19
signals in report   15 / 84   (18% coverage)

  CVD                 4 signals   via BUY_PRESSURE
  FUNDING             3 signals   via FUNDING_RATE
  RSI                 8 signals   via RSI14

  metrics feeding no signal (context only):
    CLOSE, VWAP
```

Catch wasted allocation before it costs you:

```python
for f in check_allocations(report, rules):
    print(f)
```

```
[error] bollinger_lower_touch: NOT_IN_REPORT - the BOLLINGER module has no feeding
        column or section, so this signal never fires and allocation 2 is inert.
        You have less evidence than the scorecard suggests. To fix, add a column
        on one of: BB_PCT_B, BB_WIDTH, BB_WIDTH_PCT, BB_TOUCH, CCI20, or enable
        the includeBollingerBands platform section.
```

Or work backwards from the signals you want:

```python
suggest_columns_for(["cvd_bullish", "mtf_aligned_bull"])
# {'cvd_bullish': ['CVD', 'BUY_PRESSURE', 'BUY_VOLUME', ...], 'mtf_aligned_bull': []}
```

An empty list means unreachable. `suggest_sections_for` answers the same question in
platform-section terms:

```python
suggest_sections_for(["cvd_bullish", "mtf_aligned_bull"])
# {'cvd_bullish': 'includeCvd', 'mtf_aligned_bull': None}
```

## Verification

All 22 metric probes replay against the predictor in `tests/test_membership.py`, and all
25 platform-section probes replay in `tests/test_platform_sections.py`, matching
the connector's module set and signal set exactly. The section tests check the
**measured** signal count against the derived module size, so they cross-check
measurement against derivation rather than derivation against itself. The 7-column panel from
`examples/build_section.py` reproduces the connector's recorded 15 signals. The map is also
checked for internal consistency: 84 distinct signals, no metric feeding two modules, and
mapped ∪ dead = all 86 metrics.
