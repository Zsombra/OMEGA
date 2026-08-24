# 11 · Signal Scoring

How a raw indicator reading becomes the 0–1 number that [05](05-signal-aggregation-math.md)
aggregates.

---

## The layer this fills in

Doc 05 established the aggregation:

```
aggregate = Σ(scoreᵢ × allocᵢ) / Σ(allocᵢ)
```

and treated `scoreᵢ` as given. It isn't given — it's computed, by 84 separate small
functions, and until now this project had the arithmetic *above* the score and the
arithmetic *below* the column, with a hole in between. This document closes it.

Every formula here was reproduced **bit-exact** against a live `get_coin_signal_preview`
reading before being written down. Not approximately — to the last floating-point digit.
That standard is not pedantry: it is the only way to tell a correct formula from a
plausible one, and it caught a real bug (below).

## The clamp

**Every score is clamped to [0, 1].**

The published signal definitions actively mislead here. `ma_sma200_above` documents
*"price 10% above SMA200 → score 2.0"*. Measured live:

| reading | raw formula | engine reports |
|---|---:|---:|
| price +10.23% above SMA200 | 2.047 | **1** |
| price +24.71% above SMA200 | 4.94 | **1** |
| ADX 62.69 vs threshold 25 | 1.508 | **1** |
| EMA5/EMA20 gap 2.660% | 2.660 | **1** |

Four independent proofs. The definitions publish *raw formula output*; the engine clamps.

The clamp matters because the aggregate is a **mean**: a score of 1.0 is the most any one
signal can pull the mean upward, and there is no way to buy extra leverage with an
unusually strong reading.

> **Corrected 2026-08-24.** This section originally continued: *"a strategy's maximum
> possible aggregate is Σ(allocation of signals that CAN fire together) / Σ(all
> allocations)"*. That is wrong. It assumed the denominator counts every allocated
> signal; it counts only signals that **fired**. There is no structural ceiling — the
> maximum aggregate is 1.0 for any scorecard. See
> [12 · Routing Feasibility](12-routing-feasibility.md) for the four measurements that
> settled it.

## The twelve families

| family | formula | signals |
|---|---|---:|
| `linear_below` | `clamp((thr − v) / norm)` | 16 |
| `unspecified_magnitude` | *not published* | 16 |
| `linear_above` | `clamp((v − thr) / norm)` | 15 |
| `pct_gap_scaled` | `clamp(gap% / divisor)` | 10 |
| `two_state` | `high if <test> else low` | 6 |
| `count_ratio` | `count / denominator` | 4 |
| `synthesis` | `f(component scores)` | 4 |
| `proximity` | `1 − dist / proximityPct` | 4 |
| `fixed` | a constant | 3 |
| `flow_rate_gap` | `rate(leader) − rate(follower)` | 2 |
| `midline_scaled` | `clamp(\|v − 50\| / 30)` | 2 |
| `break_magnitude` | `clamp(breakDist%)` | 2 |

### Choosing the normaliser

The threshold families look like one rule but are two, and the split is the interesting
part:

- **Bounded metrics normalise by the distance to the bound.** RSI at threshold 70 divides
  by `100 − 70 = 30`. `%B` at 0.95 divides by `1 − 0.95 = 0.05`. Oversold-side thresholds
  divide by the threshold itself, because the lower bound is 0 and `thr − 0 = thr`.
- **Unbounded ratios normalise by the threshold.** `volume_ratio`, ATR ratio, funding
  rate, OI change — all divide by their own threshold, so the score reads as a *relative*
  excess.

**ADX breaks the pattern.** It is bounded 0–100, yet `trend_adx_trending` divides by the
threshold (25), not by `100 − 25`. Verified: ADX 33.479 → `(33.479−25)/25` = 0.3391498224,
matching the engine exactly. Had it used the bounded rule the answer would be 0.113.

### The reference level is always the denominator

`pct_gap_scaled` cost me a bug worth recording. I wrote the bear variant as
`(sma50 − price) / price`, mirroring the bull case by swapping both operands. The engine
divides by **SMA50 in both directions**:

```
score = |value − reference| / reference × 100 / divisor
```

The wrong version gave 0.11033157635084212 against an observed 0.10972626277389559 — a
0.5% error, invisible to `pytest.approx`, entirely plausible on inspection. Only bit-exact
assertion surfaced it.

### `flow_rate_gap`, decoded

The two `flow_perp_spot_*` signals were the last ones I had marked "unspecified". They
aren't:

```python
rate(x) = clamp((x − prev_x) / abs(prev_x), −1, +1)
score   = rate(perp) − rate(spot)          # bear; bull swaps the operands
```

BTC's perp CVD went −209.443 → 114.196, a raw rate of **1.545**, and the engine's own
details string printed *"perp rate 1.00 outpacing spot 0.70"*. The clamp left its
fingerprint in the prose. Score: 0.30359968751644006, reproduced exactly.

### Synthesis consumes exact component scores

`mtf_aligned_bull` = the arithmetic mean of the three rung alignment scores — at full float
precision, not rounded:

```
(0.0705425369855601 + 1.0 + 1.0) / 3 = 0.6901808456618533   ← exact match
```

That first term is `ltf_ma_aligned_bull`'s own post-clamp score. Second-order signals read
first-order *outputs*, which is why [07](07-signal-membership.md) finds CONFLUENCE
unreachable through column design: it isn't fed by columns at all.

## What the toolkit refuses to compute

17 of 84 signals return `computable=False` rather than a number.

**16 divergence and cross signals** — `rsi_bull_divergence`, `macd_bear_cross`,
`cvd_bull_divergence` and their kin. The platform documents these only qualitatively
("scales with the gap"). The *direction* of the relationship is known; the curve is not.
Five live firings have now been observed and **every one returned exactly 1.0** — see
*Open*, below. Suggestive, and still not sufficient.

**`regime_alignment`** — the one outright contradiction. Its definition states plainly:

> Score = alignedCount / 3

with examples 3/3 → 1.00 and 2/3 → 0.67. A Dunkirk log recorded 0.667, consistent. But two
independent live previews (BTC 1h, ETH 4h) both returned **0.7** for the same regime triple
`trend=trending_up, mom=bullish, vol=normal` — and no integer count over 3 yields 0.7.

`0.7 == 2.1/3`, which would imply fractional credit for a non-directional volatility state.
That is a hypothesis fitted to two identical samples, not a measurement, so it is recorded
as a hypothesis and the function refuses to run.

### Why refusal is a separate flag

```python
score("rsi_oversold", {"rsi14": 55.0}, {"threshold": 30})
# Score(value=0.0, computable=True)      -> did not fire

score("rsi_bull_divergence", {}, {})
# Score(value=None, computable=False)    -> cannot be modelled
```

Collapsing these into `None` would make "the signal was quiet" and "this toolkit is
guessing" the same value at the call site. `omega.performance` already set this house rule:
a win rate below the minimum sample is `None` *deliberately, not as a missing value*.

## Using it

```python
from omega.scoring import score

score("trend_adx_ranging", {"adx_value": 11.68241454}, {"threshold": 20}).value
# 0.415879273

s = score("ma_sma200_above", {"price": 77103, "sma200": 69944.975}, {})
print(s)
# ma_sma200_above: 1.0000000000  (raw 2.046759, clamped)
```

`Score` carries `raw` and `clamped` alongside `value`, so you can see when a reading was
pinned at the ceiling — useful when a signal looks maxed out and you want to know by how
much it overshot.

## Verification

`tests/test_scoring.py` — 59 tests. Most replay real (`indicatorValues` → `score`) pairs
from `data/performance/score_probes.json`, captured from live previews, and assert
**exact** float equality. The rest pin the clamp, the refusal behaviour, and the
corpus/code agreement.

| | |
|---|---|
| signals covered | 84 / 84 |
| verified | 73 |
| inferred from a fetched mirror | 10 |
| documented mismatch | 1 |
| **bit-exact against live data** | **29** |

The probe set deliberately spans asset classes — BTC and ETH (crypto), GOOGL (equity),
GOLD (commodity). That breadth is what verified the families that crypto never exercised
in the sample: PRICE_STRUCTURE fired only on GOOGL and GOLD, both CCI directions only on
GOOGL and GOLD, and `stoch_oversold` only on GOOGL.

Each stored scorecard is also checked against the platform's own reported
`aggregateScorePercent` — all five reproduce exactly, which catches any transcription
error in the fixtures.

A completeness test asserts `SCORERS ∪ UNCOMPUTABLE` equals exactly the 84 signals in
`signal_module_map.json` — no silent gaps in either direction — and a drift test asserts
the JSON corpus and the Python module agree on which signals are unmodellable.

## Signal availability differs by asset class

The BattleGrid universe is not crypto-only — `get_top_ranked_coins` returns equities,
indices and commodities alongside it. That matters for scoring:

| module | availability |
|---|---|
| `FLOW_DIVERGENCE` | **crypto only.** GOOGL and GOLD both returned *"Perp/spot flow data unavailable"* |
| `FUNDING`, `OPEN_INTEREST` | **available everywhere** — these are synthetic perp markets. GOOGL carried funding `0.0000044395` and OI `123.1M` |
| `COMPARISON` | **intermittent everywhere**, returning *"Comparison data unavailable"* even with peers listed in the same payload |

Under fired-set semantics an unavailable module is costless, but a crypto-tuned scorecard
silently carries less evidence off-crypto.

## Open

- **`bollinger_cci_*` — RESOLVED.** Both directions are now verified bit-exact:
  `bollinger_cci_oversold` on GOOGL (CCI −179.617 → 0.7961719428) and
  `bollinger_cci_overbought` on GOLD (CCI 248.718 → raw 1.487, clamped to 1). The earlier
  claim of a live 0.269 against a computed 0.538 could not be reproduced and is recorded
  as my transcription error, not engine behaviour.
- `regime_alignment`, above — still unresolved.
- **The 16 divergence magnitudes — PARTLY RESOLVED.** The earlier claim here was that
  every observed firing returned exactly 1.0, which pointed at a fixed score. Three
  captures now hold **26** divergence firings, and **8 are not 1.0** — including in the
  very signal named above:

  | signal | coin | score |
  |---|---|---|
  | `oi_divergence_bull` | ETH | `0.20133736400835542` |
  | `flow_perp_spot_bear_divergence` | ETH | `0.2392909896129719` |
  | `flow_perp_spot_bull_divergence` | SOL | `0.2421094388008913` |
  | `flow_perp_spot_bear_divergence` | BTC | `0.30359968751644006` |
  | `flow_perp_spot_bear_divergence` | SOL | `0.3098538385810036` |
  | `comparison_sector_divergence` | GOLD | `0.6666666666666666` (2 of 3 peers — a ratio) |

  So magnitude **is not fixed**, which matches the 0.50 example the `oi_divergence_bull`
  definition publishes. Six signals have still only ever been seen at 1.0
  (`macd_bear_divergence`, `macd_bull_divergence`, `cvd_bull_divergence`,
  `mfi_bull_divergence`, `oi_divergence_bear`, `regime_divergence`) — that is now a
  statement about a small sample, not evidence of a constant.

  Knowing the magnitude varies is not the same as knowing the formula. The scorers stay
  refused, and `test_divergence_magnitude_is_not_fixed_at_one` pins both halves: that a
  counterexample exists, and that `omega.scoring` still declines to guess.
