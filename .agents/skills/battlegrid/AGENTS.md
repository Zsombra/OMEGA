# AGENTS.md — BattleGrid MCP Server

Machine-readable agent discovery file for `@battlegrid/mcp-server` (thin stdio proxy to BattleGrid's remote MCP server).

## Platform

| Field | Value |
|-------|-------|
| Name | BattleGrid |
| Website | https://battlegrid.trade |
| Protocol | Model Context Protocol (MCP) |
| Transport | stdio (npm package), streamable-http (remote) |
| Package version | The **proxy's own build identity**. It makes no claim about the server's contract and never needs to move when the contract does. |
| Contract version | Relayed from the upstream handshake on every connection, so it is always the contract you will actually reach. Read it from the stdio handshake (`battlegrid@<contract>`, printed to stderr at startup) or `GET https://mcp.battlegrid.trade/mcp/version`. The two versions differ by design — that is not drift. |

## Authentication

| Field | Value |
|-------|-------|
| Method | API Key (stdio) / OAuth 2.1 (remote, ChatGPT Desktop) |
| Format | `bg_live_*` |
| Header | `Authorization: Bearer <API_KEY>` |
| Obtain | https://battlegrid.trade → Profile → MCP tab |
| Scopes | `mcp:read` (discovery + non-financial config writes), `mcp:wager` (financial actions) |

## Connection

### Option A: npm / stdio

```bash
# Single account
BATTLEGRID_API_KEY=bg_live_xxx npx @battlegrid/mcp-server
# Multiple accounts
BATTLEGRID_API_KEYS=bg_live_aaa,bg_live_bbb npx @battlegrid/mcp-server
```

### Option B: Remote / streamable-http

```
URL: https://mcp.battlegrid.trade/mcp
Header: Authorization: Bearer bg_live_xxx
```

## Capabilities — discovered live

Tools, prompts, and resources are **discovered live** from the connected server via `tools/list`, `prompts/list`, and `resources/list`. This package does not hardcode the catalog, formulas, signal IDs, or defaults. After a server deployment, restart/reconnect the proxy and re-run discovery — a cached snapshot is not authoritative.

Capability areas exposed by the server include: Market Grid game play, market context, account state, leaderboards, intelligence agents + automation, strategy discovery/authoring, and trading signals/decisions.

## Multi-account request envelope

When multiple keys resolve, the proxy injects a required `account` enum into every tool as a **sibling** of the existing input. The strict strategy-authoring tools (`get_strategy_section_template`, `update_strategy_signal_rule`, `compile_strategy_plan`, `apply_strategy_plan`) publish `{ request: canonicalPayload }`; multi-account discovery makes that exactly `{ account, request }`. The proxy strips only `account` and forwards the unchanged `{ request }`. Never nest `account` inside `request`.

## Strategy authoring

Author strategies with the strict workflow: `compile_strategy_plan({ request })` (CREATE / UPDATE / RESTORE) → review the returned `approvedPlan` + `reviewContext` → `apply_strategy_plan({ request: { planToken, confirm: true } })` (the only write to the strategy).

**Apply carries no plan.** A `plan` member is rejected as an unknown key: the server keeps the plan its own compile approved and reads it back, so nothing is copied out of the compile response. Forward `planToken` byte-for-byte — it is an opaque signed value, and a mangled one addresses no approved plan and is refused. It lives five minutes; past that, recompile. `PLAN_APPROVAL_NOT_FOUND` means no approved plan answers to the token (already applied, lapsed, or never issued) and the recovery is to compile again; any other refusal — quota, name collision, a changed bound agent, a moved catalog — leaves the plan applicable, so clear the cause and confirm the same token again while it lives. Compile is **not read-only**: it parks the plan apply reads, and each call mints a distinct record, so compile once per reviewed payload rather than retrying or parallelising it.

The compile request carries the authored axes, including normalized `sections` and the required `conditions` axis (contract v5.0.0). Each condition is `{ conditionKey, name, definition, verdict }`, where `verdict` is required and nullable — `UP` | `DOWN` | `NEITHER`, or an explicit `null` for a building block — and declaration order is the precedence: the first condition that resolves TRUE and carries a non-null verdict decides. The separate `conditionVerdicts` array was retired in v5.0.0 and is rejected with a message naming this replacement. Every derived field (`diff`, `viability`, `mismatches`, `signalRules`, `creationSeed`, `proposedRevision`, `bindingImpact`, `authoringCatalogDigest`) is re-derived server-side and rejected as an unknown key if resubmitted. Bind a strategy to an agent at creation via `create_intelligence_agent({ …, strategyId })`. The direct `create_strategy` operation is **retired** and absent from discovery.

## Skills

```bash
npx skills add playbattlegrid/battlegrid-mcp
```

Nine skills ship from this repo (and inside the npm tarball, under `SKILL.md` + `skills/`):

| Skill | Teaches |
|---|---|
| `battlegrid` (repo root) | Connection, the `{ account, request }` envelope, scopes, and where the rest lives — authored here |
| `battlegrid-agent-management` | Commission and govern intelligence agents: interview and create one against a committed strategy and an approved model, change configuration and risk limits, rebind, halt, resume, archive, and act on live positions |
| `battlegrid-arena-play` | Enter Market Grid sessions: find an open session, read its coin pool and live market context, compose a grid with real per-coin reasoning or have an agent generate it, submit, then read results and the reasoning journal |
| `battlegrid-market-analysis` | Read the current crypto market — regime, funding and open interest, leaders and laggards, a deep-dive on any named coin — and close with the levels worth watching |
| `battlegrid-radar-deployment` | Put agents on standing duty: per-coin Radar policies that fire on confirmed regime flips, and per-preset Arena deployment policies, previewed before they are written and un-deployed with the blast radius stated |
| `battlegrid-strategy-authoring` | Build a strategy from a plain-English idea: gather evidence, lock the spec, compile against the platform grammar, review exactly what will run, apply only on confirmation. Also fork, tune, restore, archive, preview |
| `battlegrid-strategy-doctor` | Diagnose an agent that is not doing what was expected — why it has not traded, why it stopped, whether it is healthy — from typed fields, then rank the fixes with the exact lever each needs |
| `battlegrid-strategy-examples` | Full-surface composition patterns: custom report sections and header grammar, benchmark sections, condition trees with verdicts and enforcement gates, tiered signal weights and the aggregate gate math, routing gates, ATR trade levels, position management, plus validated desk-grade playbooks and TradingView process ports |
| `battlegrid-trade-analysis` | Read your own trading position: where the money is, whether each agent is doing its job, what is open and how close it sits to its protections, and whether the automation is actually running |
| `battlegrid-trade-proposal` | Find and stage a trade for one of your agents: check what is already held, scan every active coin against the agent's own gates, propose on one through the agent's own conversational turn, present the outcome with its conviction, and approve or decline only on your word |

The nine `skills/battlegrid-*` are exported from BattleGrid's server repository, so they describe
the same tools this proxy forwards. They are generated files: they are never edited in this
repository, and `skill-provenance.test.ts` fails CI on a hand edit.

## Rate limits

| Limit | Value |
|-------|-------|
| Operations | 50 ops/day |
| Wager spend | $500 USD/day |
