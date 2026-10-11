# Agent stage examples

Complete `stage_agent_draft` inputs. Each is checked in CI against the live stage schema; a create example is also
checked for every axis a new agent needs. Its shape is current.

Every `<UPPER_SNAKE>` value is a placeholder. Replace it with the id a read returned:

- `<AGENT_ID>` comes from the draft or the agent you are editing.
- `<MODEL_ID>` is the row's `modelId` from `list_approved_models`.
- `<STRATEGY_ID>` comes from the player's strategies.

Never send a placeholder as written, and never invent an id. `draftVersion` is the version `get_agent_draft`
returned: 0 when there was no draft, and for a new create draft. Each axis you send is written whole, and an axis
you omit keeps the value the draft already has.

## Create a new agent

Omit `agentId` to open a create draft. The response carries the minted id, which every later call names. A new agent
needs all four of IDENTITY, BEHAVIOR, MODEL and STRATEGY_BINDING. TRADING_CONFIG is optional: omit it to take the
platform seed.

```json stage_agent_draft
{
  "request": {
    "draftVersion": 0,
    "axes": {
      "IDENTITY": { "displayName": "Breakout Scout" },
      "BEHAVIOR": { "behavior": { "risk": "MODERATE", "outlook": "REALIST", "conviction": "MEASURED" } },
      "MODEL": { "modelId": "<MODEL_ID>" },
      "STRATEGY_BINDING": { "strategyId": "<STRATEGY_ID>" }
    }
  }
}
```

## Change an existing agent's behavior

BEHAVIOR is sent whole: all three of risk, outlook and conviction, even when only one changes.

```json stage_agent_draft
{
  "request": {
    "agentId": "<AGENT_ID>",
    "draftVersion": 4,
    "axes": {
      "BEHAVIOR": { "behavior": { "risk": "CONSERVATIVE", "outlook": "REALIST", "conviction": "CAUTIOUS" } }
    }
  }
}
```

## Rebind an existing agent to another strategy

```json stage_agent_draft
{
  "request": {
    "agentId": "<AGENT_ID>",
    "draftVersion": 4,
    "axes": {
      "STRATEGY_BINDING": { "strategyId": "<STRATEGY_ID>" }
    }
  }
}
```
