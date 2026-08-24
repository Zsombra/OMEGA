# 07 · Signal Membership

Which of the 84 signals can your report actually feed — answered offline.

[05](05-signal-aggregation-math.md) established the coupling: allocation converts evidence
into influence but cannot manufacture evidence. A `NOT_IN_REPORT` signal at allocation 3
adds 3 to the aggregation denominator and ~0 to the numerator, **actively suppressing your
aggregate**. Until now the only way to check was `derive_strategy_rule_view`. This is the
offline model, derived from 24 probes.

---

## The rule

**Membership is module-level, not column-level.**

```
report metrics  →  signal modules  →  signals
```

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

## Platform sections are not modelled

They behave inconsistently:

- `includeRsi` alone → **8 signals**
- `includeMtfConfluence` alone → **zero**, despite carrying `MA_ALIGN`, `RSI14` and `ADX` columns

So a platform section does *not* reliably feed the modules its columns suggest.
`omega.membership` reads custom sections only. If your report uses platform sections,
confirm with `derive_strategy_rule_view`.

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
        column. Allocation 2 adds 2 to the denominator and ~0 to the numerator.
        Add one of: BB_PCT_B, BB_WIDTH, BB_WIDTH_PCT, BB_TOUCH, CCI20
```

Or work backwards from the signals you want:

```python
suggest_columns_for(["cvd_bullish", "mtf_aligned_bull"])
# {'cvd_bullish': ['CVD', 'BUY_PRESSURE', 'BUY_VOLUME', ...], 'mtf_aligned_bull': []}
```

An empty list means unreachable.

## Verification

All 22 metric probes replay against the predictor in `tests/test_membership.py`, matching
the connector's module set and signal set exactly. The 7-column panel from
`examples/build_section.py` reproduces the connector's recorded 15 signals. The map is also
checked for internal consistency: 84 distinct signals, no metric feeding two modules, and
mapped ∪ dead = all 86 metrics.
