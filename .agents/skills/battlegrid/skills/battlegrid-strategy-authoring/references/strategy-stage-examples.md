# Strategy stage examples

`strategyId` and `draftVersion` sit beside `axes`, inside `request` — never inside `axes`. Every example below is
checked in CI against the live `stage_strategy_draft` schema; a create example is also checked for the axes a new
strategy needs. Its shape is current.

These examples show the envelope and the small axes. A full composition (report sections, conditions, signal
rules) is in `strategy-examples`' playbooks, which have their own compile gate.

Every `<UPPER_SNAKE>` value is a placeholder: `<STRATEGY_ID>` is the id a read returned. Never send a placeholder as
written, and never invent an id. `draftVersion` is the version `get_strategy_draft` returned: 0 when there was no
draft, and for a new create draft. Each axis you send is written whole, and an axis you omit keeps the value the draft
already has.

## Open a create draft

Omit `strategyId`. The response carries the minted id, which every later call names. A new strategy needs IDENTITY
and TIMEFRAME_PROFILE before it can be created.

```json stage_strategy_draft
{
  "request": {
    "draftVersion": 0,
    "axes": {
      "IDENTITY": {
        "name": "Squeeze Breakout",
        "description": "Enters when a volatility squeeze resolves upward on rising volume.",
        "tagline": "Buys the release of a tight range"
      },
      "TIMEFRAME_PROFILE": { "timeframe": "1h" }
    }
  }
}
```

## Change an existing strategy's setup gates

SETUP_GATES is sent whole: all three gates, even when only one changes.

```json stage_strategy_draft
{
  "request": {
    "strategyId": "<STRATEGY_ID>",
    "draftVersion": 2,
    "axes": {
      "SETUP_GATES": { "minAggregateScore": 60, "minRequiredCount": 1, "minAtrPct": 0.5 }
    }
  }
}
```
