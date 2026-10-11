# Radar stage examples

Complete `stage_radar_deployment_draft` inputs, one per construction in **Shaping a Radar rule**. Each is
checked in CI against the live stage schema and composed into a policy the aggregate accepts, so its
shape is current.

Every `<UPPER_SNAKE>` value is a placeholder. Replace it with the id a read returned:

- `<COIN_ID>` comes from `get_coin_metadata`.
- `<AGENT_ID>` comes from your agent list.
- `<OTHER_AGENT_ID>` is a second agent from your agent list, where an example deploys two.

Never send a placeholder as written, and never invent an id. `draftVersion` is the version
`get_radar_deployment_draft` returned: 0 when the coin has no draft. Each axis you send is written whole, and an axis
you omit keeps the value the draft already has.

## On duty whenever no rule matches — the default slot

On a coin with no rules, the default slot is on duty at every instant. This is the construction for "put this agent
on this coin" with no condition named.

```json stage_radar_deployment_draft
{
  "request": {
    "coinId": "<COIN_ID>",
    "draftVersion": 0,
    "axes": {
      "DEFAULT_SLOT": { "defaultSlot": { "agentId": "<AGENT_ID>", "minConviction": null } }
    }
  }
}
```

## On duty only in named regimes

`minConviction` on the rule is the trade bar (0–1, or null to inherit the agent's). `minConviction` inside the
regime condition is the regime-reading floor, and must be a level one of the selected regimes can emit.

```json stage_radar_deployment_draft
{
  "request": {
    "coinId": "<COIN_ID>",
    "draftVersion": 0,
    "axes": {
      "RULES": {
        "rules": [
          {
            "agentId": "<AGENT_ID>",
            "minConviction": null,
            "conditions": [
              { "kind": "regime", "regimes": ["bull_expansion", "bull_ranging"], "minConviction": "high" }
            ]
          }
        ]
      }
    }
  }
}
```

## On duty only in named hours and days

Hours are UTC, 0–23. Days run 0 (Sunday) to 6. Each is listed once.

```json stage_radar_deployment_draft
{
  "request": {
    "coinId": "<COIN_ID>",
    "draftVersion": 0,
    "axes": {
      "RULES": {
        "rules": [
          {
            "agentId": "<AGENT_ID>",
            "minConviction": null,
            "conditions": [
              { "kind": "hours", "hours": [13, 14, 15, 16, 17, 18, 19, 20], "days": [1, 2, 3, 4, 5] }
            ]
          }
        ]
      }
    }
  }
}
```

## In named regimes during named hours — one condition of each kind

```json stage_radar_deployment_draft
{
  "request": {
    "coinId": "<COIN_ID>",
    "draftVersion": 0,
    "axes": {
      "RULES": {
        "rules": [
          {
            "agentId": "<AGENT_ID>",
            "minConviction": 0.6,
            "conditions": [
              { "kind": "hours", "hours": [13, 14, 15, 16], "days": [1, 2, 3, 4, 5] },
              { "kind": "regime", "regimes": ["volatile"] }
            ]
          }
        ]
      }
    }
  }
}
```

## Rules plus a default slot

Every rule that matches is on duty, and the first rule listed is offered the coin's fire first. The default slot is
on duty only while no rule matches, so here the second agent is on duty whenever the coin is in neither of the
first agent's regimes.

```json stage_radar_deployment_draft
{
  "request": {
    "coinId": "<COIN_ID>",
    "draftVersion": 0,
    "axes": {
      "RULES": {
        "rules": [
          {
            "agentId": "<AGENT_ID>",
            "minConviction": null,
            "conditions": [{ "kind": "regime", "regimes": ["bear_expansion", "bear_ranging"] }]
          }
        ]
      },
      "DEFAULT_SLOT": { "defaultSlot": { "agentId": "<OTHER_AGENT_ID>", "minConviction": null } }
    }
  }
}
```

## Clear the default slot on a deployed coin

This stages only `DEFAULT_SLOT`, so the deployed rules stay as they are. Send `RULES` only when the rules change, and
then send the complete list: a rule you do not resend is deleted. `draftVersion` here is the version your read
returned.

```json stage_radar_deployment_draft
{
  "request": {
    "coinId": "<COIN_ID>",
    "draftVersion": 3,
    "axes": {
      "DEFAULT_SLOT": { "defaultSlot": null }
    }
  }
}
```
