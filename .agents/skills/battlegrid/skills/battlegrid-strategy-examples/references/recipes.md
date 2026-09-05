# Recipes — copy-adaptable fragments

Column objects for a custom section's `columns[]`, condition fragments for `conditions[]`, and the
coin-selection and discovery shapes an author reaches for while writing a payload.

**Shapes are binding. Tokens are illustrations** — re-discover every metric, transform and parameter
against the live tools (`list_strategy_categories`, `list_strategy_vocabulary`,
`get_metric_construction_hints`, `get_strategy_column_contract`) before compiling. A recipe is a
worked shape, never a substitute for discovery.

Read `## Header grammar` and `## Conditions` in the skill body first: how a column's header is
generated, how event columns resolve, what `{abs: …}` binds, and which classifications are states
rather than events all live there. This document assumes them.

**Contents**
- Column recipes
- Cross detection
- Board-relative rank recipes
- Cross-venue and perp/spot basis
- Crowd positioning
- Coin selection
- Discovery fields worth reading

## Column recipes

| Intent | Column | Header it generates |
|---|---|---|
| Live traded price | `{ "metric": "LAST", "transformId": "value", "timeframe": { "rel": "anchor" } }` | `last` |
| Momentum build-up | `{ "metric": "RSI14", "transformId": "trajectory", "timeframe": { "rel": "anchor" }, "window": 4 }` | `RSI14_t3…_now`, `RSI14_trend` |
| Closed-bar-only trajectory | add `"bars": "closed"` to any trajectory | same, drawn from closed bars |
| Extension from trend | `{ "metric": "SMA50", "transformId": "distance", "timeframe": { "rel": "anchor" } }` | `dist_SMA50` (signed %) |
| Funding paid over a day | `{ "metric": "FUNDING_RATE", "transformId": "aggregate", "timeframe": { "rel": "anchor" }, "window": 24 }` | `rate_mean24` |
| Chop filter on the entry rung | `{ "metric": "CLOSE", "transformId": "efficiency", "timeframe": { "rel": "lower" }, "window": 5, "bars": "closed" }` | `close_ltf_er` (≥0.6 directional) |
| One-bar volume concentration | `{ "metric": "VOLUME", "transformId": "maxShare", "timeframe": { "rel": "lower" }, "window": 4, "bars": "closed" }` | `volBase_ltf_maxShare` |
| Room to structure | `{ "metric": "STRUCT_ZONES", "transformId": "nearestZoneDist", "timeframe": { "rel": "regime" }, "side": "resistance" }` | `zones_htf_resist_dist` |
| Last **closed** daily read | `{ "metric": "RSI14", "transformId": "value", "timeframe": { "abs": "1d" }, "offset": 1 }` | `RSI14_1d` — `RSI14[t - 1]` |

## Cross detection

`crossDetect` is the transform that turns a pair into an EVENT column — it prints on the crossing bar
and is null otherwise:

```json
{ "metric": "MACD", "transformId": "crossDetect", "timeframe": { "rel": "anchor" } }
```

An event column is a trigger inside a carrier, never a standing state; pair it with a persistent
state for regime. The skill body's `## Header grammar` states that rule and is the authority on it —
a condition that reads a `crossDetect` column as a state is UNRESOLVED on nearly every bar.

## Board-relative rank recipes

`rank` turns any column into an ordinal across the scanned board. Ordering semantics: `hi` most
positive, `lo` most negative, `far`/`near` by magnitude (offered only where sign matters), and
`lte N` reads as "top N".

| Intent | Column | Header |
|---|---|---|
| Most volatile on the board | `{ "metric": "ATR_PCT", "transformId": "rank", "timeframe": { "rel": "anchor" }, "ordering": "hi" }` | `atrPct_rank_hi` (1 = most volatile) |
| Biggest movers, sign-agnostic | `{ "metric": "CLOSE_CHANGE", "transformId": "rank", "timeframe": { "rel": "anchor" }, "ordering": "far" }` | `closeChg_rank_far` |
| Most extended from VWAP | `{ "metric": "VWAP", "transformId": "distance", "chainedTransformId": "rank", "timeframe": { "rel": "anchor" }, "ordering": "far" }` | `dist_VWAP_rank_far` |

Confirm every rank ordering against `get_metric_construction_hints({ metric }).rankOrderings` — it is
present only where rank is composable on that metric, and is already range-gated server-side. Read
the offered set; never derive one from the metric's native output.

## Cross-venue and perp/spot basis

| Intent | Column | Header |
|---|---|---|
| Perp premium to oracle | `{ "metric": "MARK", "transformId": "spread", "timeframe": { "rel": "anchor" }, "inputs": [{ "metric": "ORACLE" }] }` | `mark_oracle_spread` |
| Basis to Binance spot | `{ "metric": "MARK", "transformId": "spread", "timeframe": { "rel": "anchor" }, "inputs": [{ "metric": "SPOT_CLOSE_BN" }] }` | `mark_bnClose_spread` |
| Basis to Coinbase spot | same with `{ "metric": "SPOT_CLOSE_CB" }` | `mark_cbClose_spread` |

A positive basis that is widening while price stalls is perp-led; the flow playbooks use it as the
fragility read.

## Crowd positioning

`CROWD_UPBIAS` is the platform's own crowd read — the share of recent settled sessions predicting UP,
as a percentage:

```json
{ "metric": "CROWD_UPBIAS", "transformId": "value", "timeframe": { "rel": "anchor" } }
```

Header `upBias`. It is a fade input, not a trend input: it says what the board expects, which is the
thing a crowded-positioning playbook trades against.

## Coin selection

`coinSelection` is required on every compile and is discriminated on `mode`:

```json
{ "mode": "ranked", "limit": 25, "category": "DEFI" }
{ "mode": "explicit", "tickers": ["BTC", "ETH", "SOL"] }
```

`ranked` is top-N by 24h volume with an optional sector filter; `explicit` names a ticker set
validated against the active universe. The sector vocabulary is
`ALL` / `CRYPTO` / `L1` / `MEMES` / `DEFI` / `TRADFI` / `STOCKS` / `INDICES` / `COMMODITIES` —
discover the live set rather than assuming this list has not moved. An explicit set is capped; the
refusal names the cap.

## Discovery fields worth reading

Two answers are frequently fetched and then left unread, and each has cost a refusal that a
single already-served field would have prevented:

- `get_strategy_column_contract({ column }).outputs[].conditionOperators` — an empty array means that
  rendered header has no comparison semantics and **cannot appear in a condition clause at all**.
  Legality is per rendered header, not per column: a trajectory's slot header and its `_trend` header
  answer differently.
- `get_metric_construction_hints({ metric }).rankOrderings` and `.qualifiedForms` — the composable
  rank orderings, and the section-qualified forms available when a header is duplicated report-wide.
- `get_trading_config_catalog()` carries the platform defaults an omitted dial inherits, including
  `defaultMaxEntryDeviationAtrMultiple` — the band an entry is still admitted within. Read it before
  authoring an entry band, rather than restating a number the platform already owns.
