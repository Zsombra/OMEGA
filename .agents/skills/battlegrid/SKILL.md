---
name: battlegrid
description: MCP skill for BattleGrid — play crypto prediction games (Market Grid), author trading strategies with the strict compile → review → apply workflow, and manage strategy-bound intelligence agents from AI agents.
---

# BattleGrid

BattleGrid is a real-time cryptocurrency prediction gaming and trading platform. This MCP server gives AI agents access to play games, author trading strategies, and run strategy-bound intelligence agents.

## The other nine skills

This skill covers **connection**: how to reach BattleGrid, the request envelope, and what each scope
grants. Everything about *using* the platform lives in the nine skills installed beside it, exported
from BattleGrid's own server so they name exactly the tools you reach here:

| For | Activate |
|---|---|
| Playing Market Grid sessions | `battlegrid-arena-play` |
| Building or changing a strategy | `battlegrid-strategy-authoring` |
| Composing beyond a bare template — conditions, weights, gates, trade levels, playbooks | `battlegrid-strategy-examples` |
| Creating and governing intelligence agents | `battlegrid-agent-management` |
| Putting an agent on standing duty (Radar, Arena presets) | `battlegrid-radar-deployment` |
| Reading the market — regime, funding, leaders, a coin deep-dive | `battlegrid-market-analysis` |
| Reading your own position, agents, and open trades | `battlegrid-trade-analysis` |
| Finding and staging a trade for one of your agents — scan its coins, propose on one, approve or decline on your word | `battlegrid-trade-proposal` |
| Working out why an agent has not traded or has stopped | `battlegrid-strategy-doctor` |

Those nine carry the working arcs and the exact contracts. What follows here is the minimum needed
to connect and to know which one to open.

## Discover the live surface first

**Tools, prompts, and resources are discovered live from this MCP connection.** Always read the current `tools/list`, `prompts/list`, and `resources/list` before acting — a cached capability list is not authoritative after a server deployment. This skill teaches the workflows and the strict request contracts; it deliberately does not copy the server's tool catalog, metric/transform vocabulary, signal IDs, formulas, or default values. Discover those from the live tools (`list_strategy_categories`, `list_strategy_vocabulary`, `list_strategy_signals`, `get_strategy_signal_definition`, …). Never guess a metric, transform, parameter, template, signal, or enabled-timeframe fact.

## Single-account vs multi-account request shape

The strategy-authoring tools — `get_strategy_section_template`, `update_strategy_signal_rule`, `compile_strategy_plan`, `apply_strategy_plan` — use one strict server-owned envelope, `{ request: canonicalPayload }`.

- **Single account:** call them as the server publishes them, e.g. `compile_strategy_plan({ request })`.
- **Multiple accounts (proxy):** live discovery adds a sibling `account`, so the shape is exactly `{ account, request }`. Select the account in the outer field; keep `request` exactly as discovered. The proxy strips only `account` and forwards the unchanged `{ request }`.

Never put `account` inside `request`, and never flatten request fields beside it. Other tools keep whatever input shape live discovery reports for them.

## Scopes

- `mcp:read` — strategy discovery **and** non-financial configuration writes (author strategies, edit agents, customize signals). Treat it as configuration authority, not view-only.
- `mcp:wager` — financial actions (submit paid entries, accept/cancel entry decisions, deployment policies). Enable **Server-Signed Wagers** in Profile → MCP to grant it. Pending entry decisions come from the conversational surface, which waits for approval; an agent deployed to a radar coin or a trading-enabled arena slot executes without one.

## Author a strategy, and bind it to an agent

**The arc lives in `battlegrid-strategy-authoring`** — activate it, and `battlegrid-strategy-examples`
alongside it when the strategy goes beyond a bare template. Do not compose a plan from this document;
it states only what the *proxy* adds to that arc.

Three facts about transport, which are this skill's to state because they are about the wire rather
than about authoring:

- **The envelope is `{ request }`, or `{ account, request }` on a multi-account proxy** (see above).
  It applies to `get_strategy_section_template`, `update_strategy_signal_rule`,
  `compile_strategy_plan` and `apply_strategy_plan`.
- **`planToken` is opaque and is forwarded byte-for-byte.** Never retype, paraphrase, abbreviate or
  rebuild it from memory — the proxy passes the bytes through unchanged, and a mangled token
  addresses no approved plan and is refused. It lives five minutes.
- **`apply_strategy_plan` carries no `plan` member.** One is rejected as an unknown key: the server
  reads back the plan its own compile approved, so nothing is copied out of the compile response and
  nothing can be truncated or half-reconstructed in transit. Send
  `{ request: { planToken, confirm: true } }` and nothing else.

Agents bind to a strategy at creation (`create_intelligence_agent({ …, modelId, strategyId })`);
there is no direct strategy-creation tool. **`battlegrid-agent-management`** carries commissioning,
reconfiguration, rebinding and intervention; **`battlegrid-radar-deployment`** carries putting an
agent on standing duty; **`battlegrid-strategy-doctor`** carries diagnosing one that is not trading.

## Play a game (Market Grid)

Predict UP or DOWN for each coin in the pool; exactly one coin is your **Captain** (2x score
multiplier). **The arc lives in `battlegrid-arena-play`** — activate it to find a session, read its
market context, compose a grid with real per-coin reasoning, submit it, and read the results.
**`battlegrid-market-analysis`** carries the market read that informs the picks, and
**`battlegrid-trade-analysis`** carries reading back how you have done.

The `play-market-grid` prompt (discover via `prompts/list`) provides a guided end-to-end workflow.

## Retired operations

`create_strategy` (and other legacy direct-authoring/agent-scoped rule tools) are **retired** — they are absent from discovery and cannot be invoked. Author strategies with compile → review → apply, edit rules with `update_strategy_signal_rule`, and bind strategies to agents at agent creation. Do not attempt flat legacy payloads; the server enforces a closed-world request root and the proxy never reconstructs them.

## Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `BATTLEGRID_API_KEY is required` | Missing API key | Set `BATTLEGRID_API_KEY` (or `BATTLEGRID_API_KEYS`) |
| `API key must start with "bg_live_"` | Invalid key format | Generate a new key at battlegrid.trade → Profile → MCP |
| Authentication failed (401/403) | Key revoked/rotated | Generate a new key and **restart** the proxy (keys read once at startup) |
| `"account" parameter is required` | Multi-account call missing `account` | Add the outer `account`; keep `request` unchanged |
| Plan token expired / revision drift | >5 min since compile, or upstream changed | Recompile, review the fresh plan, then apply |
| Required at allocation Off | A rule flags `required` on a signal weighted `0` (contract 34) | Read `details.inertRequiredSignalIds`; per signal either raise `allocation` or set `required: false` |
| Method not found | Calling a retired/unknown tool | Re-run `tools/list`; use the compile → review → apply flow |
| `Wager scope required` | `mcp:wager` not enabled | Enable Server-Signed Wagers in Profile → MCP |
