# Market Grid entry stage examples

Complete `stage_market_grid_entry_draft` inputs for the player's entry draft. Each is checked in CI against the live
stage schema, and the grid it composes is judged by the commit's own grid and reasoning checks, so its shape is
current.

Every `<UPPER_SNAKE>` value is a placeholder. Replace it with the id a read returned:

- `<SESSION_ID>` comes from `list_market_grid_sessions`.
- `<COIN_ID>`, `<SECOND_COIN_ID>` and `<THIRD_COIN_ID>` are three different coins' `id`s from the pool
  `get_market_grid_session` returns.

Never send a placeholder as written, and never invent an id. `draftVersion` is the version
`get_market_grid_entry_draft` returned: 0 when the session has no draft. These examples are a three-cell session; a
real session's grid has its own `gridSize`, and the commit needs every position from `CELL_0` up to it filled.

## Fill the whole grid, with its reasoning

`CELL_0` is the captain. The `RATIONALE` carries one `pickReasoning` entry per cell of the grid the commit will
enter, each citing the market context you read.

```json stage_market_grid_entry_draft
{
  "request": {
    "sessionId": "<SESSION_ID>",
    "draftVersion": 0,
    "axes": {
      "CELL_0": { "cell": { "coinId": "<COIN_ID>", "prediction": "UP" } },
      "CELL_1": { "cell": { "coinId": "<SECOND_COIN_ID>", "prediction": "DOWN" } },
      "CELL_2": { "cell": { "coinId": "<THIRD_COIN_ID>", "prediction": "UP" } },
      "RATIONALE": {
        "reasoning": "The leader is breaking out on rising volume while the second coin rejects its range high.",
        "confidenceScore": 0.7,
        "modelName": "your-model-name",
        "pickReasoning": [
          { "coinId": "<COIN_ID>", "reasoning": "Breaking resistance on rising volume.", "confidence": 0.8 },
          { "coinId": "<SECOND_COIN_ID>", "reasoning": "Bearish divergence at the range high.", "confidence": 0.6 },
          { "coinId": "<THIRD_COIN_ID>", "reasoning": "Holding its trend above the session open.", "confidence": 0.6 }
        ]
      }
    }
  }
}
```

## Change one call, keeping every other pick

A cell you do not stage keeps the player's own pick. Here the second position's call flips while its coin stays,
so the reasoning the draft already holds still covers every coin; stage a new `RATIONALE` when your reasoning for
that coin changed.

```json stage_market_grid_entry_draft
{
  "request": {
    "sessionId": "<SESSION_ID>",
    "draftVersion": 4,
    "axes": {
      "CELL_1": { "cell": { "coinId": "<SECOND_COIN_ID>", "prediction": "UP" } }
    }
  }
}
```

## Change a call and its reasoning together

```json stage_market_grid_entry_draft
{
  "request": {
    "sessionId": "<SESSION_ID>",
    "draftVersion": 5,
    "axes": {
      "CELL_1": { "cell": { "coinId": "<SECOND_COIN_ID>", "prediction": "UP" } },
      "RATIONALE": {
        "reasoning": "The second coin reclaimed its range high, so it now runs with the leader.",
        "confidenceScore": 0.65,
        "modelName": "your-model-name",
        "pickReasoning": [
          { "coinId": "<COIN_ID>", "reasoning": "Breaking resistance on rising volume.", "confidence": 0.8 },
          { "coinId": "<SECOND_COIN_ID>", "reasoning": "Reclaimed the range high on the last close.", "confidence": 0.6 },
          { "coinId": "<THIRD_COIN_ID>", "reasoning": "Holding its trend above the session open.", "confidence": 0.6 }
        ]
      }
    }
  }
}
```

`{ "cell": null }` empties a position. The draft holds it while the player is still choosing, but the commit
refuses a grid with an empty position, so stage it only when the player asked to clear that pick.
