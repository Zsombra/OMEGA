# Arena stage examples

Complete `stage_deployment_policy_draft` inputs, one per construction in **Shaping an Arena rule**. Each is checked in
CI against the live stage schema and composed into a deployment the aggregate accepts, so its shape is current.

Every `<UPPER_SNAKE>` value is a placeholder. Replace it with the id a read returned:

- `<PRESET_ID>` comes from `list_game_presets`.
- `<AGENT_ID>` comes from your agent list.
- `<COIN_ID>` comes from the arena's coin pool.

Never send a placeholder as written, and never invent an id. `draftVersion` is the version
`get_deployment_policy_draft` returned: 0 when the arena has no draft. Each axis you send is written whole, and an
axis you omit keeps the value the draft already has.

## Play whenever no rule matches — the default slot

```json stage_deployment_policy_draft
{
  "request": {
    "presetId": "<PRESET_ID>",
    "draftVersion": 0,
    "axes": {
      "DEFAULT_SLOT": {
        "defaultSlot": { "agentId": "<AGENT_ID>", "minConfidence": null, "entryStrategy": "STANDARD" }
      }
    }
  }
}
```

## Play only in named regimes

```json stage_deployment_policy_draft
{
  "request": {
    "presetId": "<PRESET_ID>",
    "draftVersion": 0,
    "axes": {
      "RULES": {
        "rules": [
          {
            "agentId": "<AGENT_ID>",
            "minConfidence": null,
            "entryStrategy": "STANDARD",
            "conditions": [{ "kind": "regime", "regimes": ["bull_expansion", "bull_ranging"] }]
          }
        ]
      }
    }
  }
}
```

## Play only at named session starts

Start times are UTC `HH:MM:SS`. Days run 0 (Sunday) to 6. Each is listed once. A rule holds a session start or a
session occurrence, never both.

```json stage_deployment_policy_draft
{
  "request": {
    "presetId": "<PRESET_ID>",
    "draftVersion": 0,
    "axes": {
      "RULES": {
        "rules": [
          {
            "agentId": "<AGENT_ID>",
            "minConfidence": 0.6,
            "entryStrategy": "TWO_LOOK",
            "conditions": [
              { "kind": "session_start", "startTimes": ["14:00:00", "15:00:00"], "days": [1, 2, 3, 4, 5] }
            ]
          }
        ]
      }
    }
  }
}
```

## In named regimes at those sessions — a regime condition and one session condition

```json stage_deployment_policy_draft
{
  "request": {
    "presetId": "<PRESET_ID>",
    "draftVersion": 0,
    "axes": {
      "RULES": {
        "rules": [
          {
            "agentId": "<AGENT_ID>",
            "minConfidence": null,
            "entryStrategy": "STANDARD",
            "conditions": [
              { "kind": "regime", "regimes": ["volatile"] },
              { "kind": "session_start", "startTimes": ["14:00:00"], "days": [1, 2, 3, 4, 5] }
            ]
          }
        ]
      }
    }
  }
}
```

## Override the regime anchor on a deployed arena

This stages only `REGIME_ANCHOR`, so the deployed rules and default slot stay as they are. The coin and the timeframe
come together, or not at all.

```json stage_deployment_policy_draft
{
  "request": {
    "presetId": "<PRESET_ID>",
    "draftVersion": 2,
    "axes": {
      "REGIME_ANCHOR": { "regimeAnchor": { "regimeReferenceCoinId": "<COIN_ID>", "regimeTimeframe": "4h" } }
    }
  }
}
```

## Clear the regime anchor override

The arena's own anchor applies again.

```json stage_deployment_policy_draft
{
  "request": {
    "presetId": "<PRESET_ID>",
    "draftVersion": 2,
    "axes": {
      "REGIME_ANCHOR": { "regimeAnchor": null }
    }
  }
}
```
