---
name: battlegrid
description: MCP skill for BattleGrid — play crypto prediction games (Market Grid), author trading strategies and intelligence agents through their drafts (stage → read the diff → commit on the player's word), and manage strategy-bound agents from AI agents.
---

# BattleGrid

BattleGrid is a real-time cryptocurrency prediction gaming and trading platform. This MCP server gives AI agents access to play games, author trading strategies, and run strategy-bound intelligence agents.

## The other nine skills

This skill covers **connection**: how to reach BattleGrid, the `account` argument, and what each scope
grants. Everything about *using* the platform lives in the nine skills installed beside it, exported
from BattleGrid's own server so they name exactly the tools you reach here:

| For | Activate |
|---|---|
| Playing Market Grid sessions | `battlegrid-arena-play` |
| Building or changing a strategy | `battlegrid-strategy-authoring` |
| Composing beyond a bare template — report sections, conditions, trade levels, playbooks | `battlegrid-strategy-examples` |
| Creating and governing intelligence agents | `battlegrid-agent-management` |
| Putting an agent on standing duty (Radar, Arena presets) | `battlegrid-radar-deployment` |
| Reading the market — regime, funding, leaders, a coin deep-dive | `battlegrid-market-analysis` |
| Reading your own position, agents, and open trades | `battlegrid-trade-analysis` |
| Finding and staging a trade for one of your agents — scan its coins, propose on one, approve or decline on your word | `battlegrid-trade-proposal` |
| Working out why an agent has not traded or has stopped | `battlegrid-strategy-doctor` |

Those nine carry the working arcs and the exact contracts. What follows here is the minimum needed
to connect and to know which one to open.

## Discover the live surface first

**Tools, prompts, and resources are discovered live from this MCP connection.** Always read the current `tools/list`, `prompts/list`, and `resources/list` before acting — a cached capability list is not authoritative after a server deployment. This skill teaches the workflows and the strict request contracts; it deliberately does not copy the server's tool catalog, metric/transform vocabulary, formulas, or default values. Discover those from the live tools (`list_strategy_categories`, `list_strategy_vocabulary`, `list_strategy_signals`, `get_strategy_signal_definition`, …). Never guess a metric, transform, parameter, template, signal, or enabled-timeframe fact.

## Single-account vs multi-account arguments

Call every tool with the arguments its live `tools/list` schema publishes. This skill states no tool's arguments; the exported skills below carry each workflow's calls, and discovery is the authority.

- **Single account:** send exactly the published arguments.
- **Multiple accounts (proxy):** live discovery adds a required `account` beside each tool's own published arguments. Select the account there. The proxy strips only `account` and forwards every other argument unchanged — it never unwraps, moves or rebuilds one.

Never put `account` inside another argument.

## Scopes

- `mcp:read` — strategy discovery **and** non-financial configuration writes (stage and commit strategy and agent drafts). Treat it as configuration authority, not view-only.
- `mcp:wager` — financial actions (submit paid entries, accept/cancel entry decisions, deployment policies). Enable **Server-Signed Wagers** in Profile → MCP to grant it. Pending entry decisions come from the conversational surface, which waits for approval; an agent deployed to a radar coin or a trading-enabled arena slot executes without one.

## Author a strategy or an agent, and bind them

**The arc lives in `battlegrid-strategy-authoring` and `battlegrid-agent-management`** — activate the
one you need, and `battlegrid-strategy-examples` alongside the first when the strategy goes beyond a
bare template. Do not compose a draft from this document; it states only what the *proxy* adds to
that arc.

Four facts about transport, which are this skill's to state because they are about the wire rather
than about authoring:

- **A tool's arguments are what discovery publishes, plus `account` on a multi-account proxy** (see
  above).
- **Every change goes through the entity's draft** — an agent's, a strategy's, and an Arena or radar
  deployment's. `stage_<kind>_draft` writes proposed axes into the player's unsaved draft and commits
  nothing. For an agent or a strategy, omit the id to open a new create draft, whose minted id the
  response carries; a deployment draft is keyed by its `presetId` or `coinId`, which every call names.
  `get_<kind>_draft` returns the draft, its `draftVersion`, the live `committedRevision`, a per-axis
  `diff`, `diagnostics` and `impact`.
- **A commit names exactly the two numbers that read returned.** `commit_<kind>_draft` takes that
  `draftVersion` and, as `expectedRevision`, that `committedRevision` — `null` for an entity not
  created yet. Commit only after the player has seen the diff and impact and said yes.
  `discard_<kind>_draft` is the same fence on the `draftVersion`. The two
  deployment commits arm wagers and require `mcp:wager`; a deployment's resume and delete name the
  `expectedPolicyId` and `expectedRevision` a `COMMITTED` preview returned.
- **The proxy forwards numbers and `null` unchanged.** It never fills in a version, never retries a
  refused call and never rebuilds a request. A `DRAFT_VERSION_MOVED` or `DRAFT_AXIS_CONTESTED` refusal
  carries `details.nextAct` from every tool, and a revision `CONFLICT` or validation refusal carries it
  from a stage or commit; the next act is the caller's.

`fork_strategy` copies a revision into a new create draft and creates nothing until that draft is
committed. An agent binds to a strategy through its draft's `STRATEGY_BINDING` axis, on a create or
as a rebind. **`battlegrid-radar-deployment`** carries putting an agent on standing duty;
**`battlegrid-strategy-doctor`** carries diagnosing one that is not trading.

## Play a game (Market Grid)

Predict UP or DOWN for each coin in the pool; exactly one coin is your **Captain** (2x score
multiplier). **The arc lives in `battlegrid-arena-play`** — activate it to find a session, read its
market context, stage picks with real per-coin reasoning into the player's entry draft (the same draft
their builder writes), read it back, commit it on the player's word, and read the results.
**`battlegrid-market-analysis`** carries the market read that informs the picks, and
**`battlegrid-trade-analysis`** carries reading back how you have done.

The `play-market-grid` prompt (discover via `prompts/list`) provides a guided end-to-end workflow.

## Retired operations

`create_strategy`, the plan tools (`compile_strategy_plan`, `stage_strategy_plan`, `apply_strategy_plan`), `update_strategy_signal_rule`, the signal-rule tools (`simulate_aggregate_score`, `list_strategy_signals`, `get_strategy_signal_definition`, `derive_strategy_rule_view`, `get_coin_signal_preview`), the direct agent writers (`create_intelligence_agent`, `update_intelligence_agent`, `rebind_intelligence_agent`), and the direct grid writers (`submit_market_grid`, `update_market_grid`) are **retired** — they are absent from discovery and cannot be invoked. Stage into the entity's draft, read it back, and commit the version you read; a strategy's entry gate is its conditions (a required or verdict-carrying condition — a strategy with none never trades, and its draft warns `NO_ENTRY_CONDITION`), its ATR floor `minAtrPct` is part of the `TRADE_LEVEL_POLICY` axis, a strategy binding is the agent draft's `STRATEGY_BINDING` axis, and a player's Market Grid picks are the entry draft's `CELL_n` and `RATIONALE` axes. A deployment preview's `previewToken`, and the `confirm` on a deployment commit, resume, delete or draft discard, are retired the same way: a strict input refuses either key. Do not attempt a retired argument shape; the server's strict inputs refuse it, and the proxy never reconstructs one.

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `BATTLEGRID_API_KEY is required` | Missing API key | Set `BATTLEGRID_API_KEY` (or `BATTLEGRID_API_KEYS`) |
| `API key must start with "bg_live_"` | Invalid key format | Generate a new key at battlegrid.trade → Profile → MCP |
| Authentication failed (401/403) | Key revoked/rotated | Generate a new key and **restart** the proxy (keys read once at startup) |
| `"account" parameter is required` | Multi-account call missing `account` | Add `account` beside the tool's own arguments; keep them unchanged |
| `DRAFT_VERSION_MOVED` | The draft changed after you read it, or no draft is held (`details.draftVersion` null) | Call `get_<kind>_draft` again, show the player what it now holds, and commit only on their word |
| `DRAFT_AXIS_CONTESTED` | The player changed `details.contestedAxes` in their open form after the version you staged against | Read the draft again and propose against what they now have |
| `CONFLICT` on a commit | The live revision moved after the draft read | Read the draft again, show the player the new diff and impact, and commit at the new `committedRevision` only on their word |
| Method not found | Calling a retired/unknown tool | Re-run `tools/list`; stage, read and commit through the entity's draft |
| `Wager scope required` | `mcp:wager` not enabled | Enable Server-Signed Wagers in Profile → MCP |
