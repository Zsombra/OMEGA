# 18 · Indicator census

Which named indicator families this platform can build, which it cannot, and — the
part that matters — **why not**.

Source of truth: `data/derived/indicator_families.json`.
Guard: `tests/test_indicator_families.py`.

Every buildable entry carries a real column spec, and the test suite builds each one
and runs it through `omega.validate` and `omega.space`. The census cannot rot into a
lie quietly: if the platform's contract moves so a family stops being constructible,
a test fails.

```
python -m omega.table families              # everything
python -m omega.table families --domain institutional
python -m omega.table families --blocked
```

## The one-line characterisation

The system computes **first-moment, ratio, ordinal and path** statistics. It computes
**no second moment, no joint moment, no transform**. Nearly every entry in both lists
follows from that sentence.

| supported | absent |
|---|---|
| mean — `aggregate` | variance, σ |
| ratio — `spread`, `distance` | covariance, ρ, β |
| ordinal — `rank` | least squares, slope |
| path efficiency — `efficiency` | time-series percentile |
| concentration — `maxShare` | log, exp, Fourier |
| sequence — `trajectory` | cumulative sums, exponential weighting |
| counting — `N_OF` (layer 3) | skew, kurtosis, autocorrelation |

## Blocked how, exactly?

This is the distinction worth carrying. "Blocked" hides four very different situations:

| cause | families | meaning |
|---|---:|---|
| `operator-absent` | 22 | **the data is present, the equation is not** |
| `guard-refuses` | 2 | the operator exists; the unit-clique rule rejects the pair |
| `needs-state` | 2 | requires recursive evaluation, not a new function |
| `data-absent` | 1 | the input genuinely does not exist |

Only **one** family — historical cross-sectional rank — is a real data gap. Everything
else is arithmetic the engine declines to do on numbers it already has.

### The proof

A 12-slot return trajectory on an unbound section, beside the same column on a
BTC-bound section, returns two time-aligned return vectors in one render:

```
SOL   0.48 -1.33  1.13  0.35 -0.42 -0.73  0.55  0.61  0.01  1.02 -0.01  0.46
BTC   0.89 -0.72  1.17 -0.57 -0.06 -0.39  0.22 -0.24  0.23  0.06 -0.31  0.04
```

From those rows: σ = 0.717 / 0.557, cov = 0.256, **ρ = 0.642**, **β = 0.827**. Every
one is unavailable in the column layer. Every one is computable from data the platform
had already printed.

### Which layer needs the number?

- **For a deterministic gate** — it must be a column, because conditions read headers,
  not reasoning. The `operator-absent` families genuinely cannot gate anything.
- **For the agent's reasoning** — ship the `trajectory` slots and let the model compute
  it. Costs header width and tokens, nothing else.

That matches the platform's own framing: conditions are *"deterministic reads …
advisory: they may make you more selective, never less."* The reasoning was always the
agent's job.

**Highest-leverage single addition:** `stddev` as a stage-2 operator. It unlocks
z-scores, Sharpe, vol-of-vol, historical-vol cones and Bollinger-on-derived in one
change, and the data for all of them already flows.

## Two rules gate the buildable side

1. **`spread` is within-unit-class only.** Eight cliques, 608 ordered pairs. Price
   (306) and percent (210) are 85% of the surface. Cross-clique constructions cannot
   exist — which is exactly why Amihud illiquidity (`percent ÷ largeCount`) and average
   trade size (`largeCount ÷ count`) are unreachable.
2. **A spread chains only when its base metric has a stored bar series.** The
   non-chaining ones are the point-in-time reads: `MARK`, `LAST`, `ORACLE`,
   `SPOT_CLOSE_*`, `CHG_*`, `FUNDING_*`, `OI_CHG`, `HIGH_DEV`, `LOW_DEV`.

Both are documented with evidence in [14 · Column space](14-column-space.md).

## Three ordering groups

`rank` does not offer the same orderings everywhere, and asking for the wrong one is
refused:

| orderings | metrics | meaning |
|---|---:|---|
| `hi` / `lo` | 19 | magnitude sort |
| all four | 11 | magnitude *and* distance-from-zero |
| `far` / `near` only | 1 | `CLOSE_CHANGE` — a signed bar change, so distance from zero is the sort offered |

This is how the census's original cross-sectional-reversal entry was caught: it asked
for `CLOSE_CHANGE rank ordering=lo`, which does not exist.

## Corrections this census carries

Two claims published earlier and since disproved, kept visible rather than edited away:

- **`CHG_24H rank` does not exist.** The whole `CHG_*` family is unrankable. Only 31 of
  86 metrics rank at all, and among momentum only `ROC12`, `PPO` and `CLOSE_CHANGE`.
- **Basis momentum is not buildable.** `MARK spread SPOT_CLOSE_CB → trajectory` fails
  because `MARK`'s spread does not chain. The basis is a single read.

Both are now pinned by tests, so neither can quietly return.

## Reading the JSON

```json
{
  "id": "carry-factor",
  "name": "Cross-sectional carry factor",
  "attribution": "Koijen, Moskowitz, Pedersen & Vrugt 2018",
  "domain": "institutional",
  "columns": [{"metric": "FUNDING_RATE", "transformId": "rank", "ordering": "hi"}],
  "note": "In perpetuals the funding rate IS the carry."
}
```

`domain` is one of `classical`, `oscillator`, `factor`, `microstructure`,
`derivatives`, `statistical`, `structure`, `sentiment`, `institutional`. Blocked
entries carry `cause` and, where the cause is `operator-absent`, a `needs` naming the
missing operator.
