# 04 · Sections, Timeframes and Budgets

---

## Two kinds of section

**Platform** — one of 25 preset `sectionKey`s. You get its columns as-authored, including
pairs you could not build yourself.

```json
{"kind": "platform", "sectionKey": "includeRsi"}
```

**Custom** — your own columns. This is where "your own data point" lives.

```json
{
  "kind": "custom",
  "title": "MR Stretch Panel",     // 1–60 chars, no control characters
  "benchmarkTicker": null,          // required key, may be null
  "timeframe": "15m",               // OPTIONAL override — see the trap below
  "columns": [ … ]
}
```

The 25 platform sections between them use **124 columns over 74 distinct metrics** — they
are the best worked examples available, and `data/contract/templates/platform/_all.json`
holds all of them.

Two platform sections ship with **zero** columns: `includeMarketBreadth` and
`includeReferencePairs`. They are presumably populated by other machinery; as far as column
composition goes they contribute nothing.

## The timeframe-override trap

A custom section may pin `timeframe`. But a **timeframe-inert** metric may not appear in a
section that does:

```
REPORT_COLUMN_SECTION_TIMEFRAME_UNSUPPORTED
metric 'FUNDING_RATE' is timeframe-inert (a bundle read) and is not allowed
in a section with a timeframe override — it accepts only the section anchor
```

The compiled contract exposes this as two flags:

| `timeframeMode` | `requiresSectionTimeframe` | `sectionTimeframeOverrideAllowed` |
|---|---|---|
| `candle` | `true` | `true` |
| `timeless` | `false` | `false` |

**Practical rule:** to pin a section to an explicit timeframe, every column in it must be
candle-backed. Funding, open interest, crowd, regime, derived and the spot-price metrics all
force the section onto the strategy anchor. If you want both, split them into two sections.

`omega.validate` reports this twice on purpose — once per offending column, and once at
section level as `SECTION_MIXES_INERT_METRICS`, because the fix is a section-level decision.

## Timeframe resolution

Anchors are `5m | 15m | 1h | 4h`. Relative references resolve against the strategy anchor:

| `rel` | 5m | 15m | 1h | 4h |
|---|---|---|---|---|
| `anchor` | 5m | 15m | 1h | 4h |
| `lower` | 1m | 5m | 15m | 1h |
| `regime` | null | null | null | null |

`regime` resolves to `null` in the authoring contract — it is bound later, from strategy
configuration rather than from the anchor. Platform sections lean on it heavily
(`includeHigherTimeframe`, `includeStructureZones`, `includeMtfConfluence`), so it clearly
resolves at execution; just don't expect the authoring compiler to tell you to what.

The full absolute set is 13 values (`1m 3m 5m 15m 30m 1h 2h 4h 8h 12h 1d 3d 1w`), but the
**ranked** universe only covers `1m 5m 15m 1h 4h 1d` — a `rank` column outside those is
asking for an ordinal that isn't computed.

## The budgets

| Budget | Limit |
|---|---|
| sections | 32 |
| columns per section | 32 |
| column lookback (`window`/`offset`) | 32 |
| distinct timeframes | 8 |
| strategy conditions | 16 |
| condition clauses | 16 |
| **estimated tokens** | **~16,000** |

Preview execution is separately capped at 256,000 result bytes and a 15,000 ms deadline.

### Which budget actually binds

Almost never the column count. Consider a section of 32 `trajectory` columns at `window: 8`:

```
32 columns  ×  (8 + 1 headers)  =  288 output headers
```

You are still legal on columns (32/32) but you have spent a large fraction of the token
budget on one section. **Headers, not columns, are the currency.** `omega.fanout.cost_report`
reports both and flags the token estimate:

```
sections                1 / 32
columns                 7
output headers         14   <- the real cost driver
distinct timeframes     2 / 8  ['15m', '1h']
estimated tokens      277 / 16000
```

The token figure is an estimate calibrated against observed contract payloads
(~18 tokens/header + ~25/section). Treat it as a planning aid; the platform's own
`estimatedTokens` is authoritative.

### Spending the distinct-timeframe budget

Only 8 distinct resolved timeframes are allowed across the whole report. Note that a
`rel: lower` column silently adds a second timeframe — a 1h-anchored report with one
`rel:lower` column already occupies 2 of 8. Timeless metrics cost nothing here, since they
resolve to `null`.

## Ordering a report

Sections render in array order and the agent reads them top to bottom. A defensible default:

1. **Context first** — regime, higher timeframe
2. **Level** — price action, structure, moving averages
3. **State** — momentum, volatility
4. **Confirmation** — volume/flow, derivatives
5. **Crowd last** — so consensus is read *against* evidence already formed, not before it
