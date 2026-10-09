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
| Method | OAuth 2.1 with Dynamic Client Registration (default, remote) / API key (fallback — headless, no remote transport, or multi-account). Authentication is a property of the PATH, not of the client. |
| Format | `bg_live_*` (API key path only) |
| Header | `Authorization: Bearer <API_KEY>` (API key path only; OAuth carries its own token) |
| Obtain | OAuth needs nothing to obtain — authorize in the browser. For a key: https://battlegrid.trade → Profile → MCP tab |
| Scopes | `mcp:read` (discovery + non-financial config writes), `mcp:wager` (financial actions) |

## Connection

### Option A: Remote / streamable-http over OAuth — the default

```
URL: https://mcp.battlegrid.trade/mcp
```

Register the URL on a streamable-http transport and authorize: the client registers itself by Dynamic Client Registration and BattleGrid's consent page opens in the browser. No npm package, no API key. Grants are listed and revocable under Profile → MCP → OAuth Sessions.

### Option B: API key — headless, no remote transport, or multi-account

Use a key when the runtime cannot open a browser to consent, when the client speaks stdio only, or when one process drives several BattleGrid accounts (OAuth grants one account each).

```
URL: https://mcp.battlegrid.trade/mcp
Header: Authorization: Bearer bg_live_xxx
```

```bash
# npm / stdio, single account
BATTLEGRID_API_KEY=bg_live_xxx npx @battlegrid/mcp-server
# npm / stdio, multiple accounts
BATTLEGRID_API_KEYS=bg_live_aaa,bg_live_bbb npx @battlegrid/mcp-server
```

## Capabilities — discovered live

Tools, prompts, and resources are **discovered live** from the connected server via `tools/list`, `prompts/list`, and `resources/list`. This package does not hardcode the catalog, formulas, signal IDs, or defaults. After a server deployment, restart/reconnect the proxy and re-run discovery — a cached snapshot is not authoritative.

Capability areas exposed by the server include: Market Grid game play, market context, account state, leaderboards, intelligence agents + automation, strategy discovery/authoring, and trading signals/decisions.

## Multi-account request envelope

When multiple keys resolve, the proxy injects a required `account` enum into every tool as a **sibling** of the existing input. The draft lifecycle tools (`stage_`, `get_`, `commit_`, `discard_<kind>_draft` and `list_<kind>_drafts`, for the `strategy` and `agent` kinds) and `get_strategy_section_template` publish `{ request: canonicalPayload }`; multi-account discovery makes that exactly `{ account, request }`. The proxy strips only `account` and forwards the unchanged `{ request }`. Never nest `account` inside `request`.

## Strategy and agent authoring

Strategies and intelligence agents change only through their drafts, with one tool family per kind: `stage_<kind>_draft({ request: { <id>?, draftVersion, axes } })` → `get_<kind>_draft({ request: { <id> } })` → `commit_<kind>_draft({ request: { <id>, draftVersion, expectedRevision } })`, where `<kind>` is `strategy` or `agent`.

**Stage reports; commit enforces.** A stage writes the proposed axes into the player's unsaved draft, commits nothing, and returns the composed draft's `diagnostics`; omit the id to open a new create draft, whose minted id the response carries. The read returns the draft, its `draftVersion` (0 when none is held), the live `committedRevision` (null for an entity not created yet), a per-axis `diff` against live, `diagnostics` and `impact`. Show the player the diff and impact, and on their explicit word commit exactly the `draftVersion` and `committedRevision` that read returned — `expectedRevision: null` creates the entity at revision 1. `discard_<kind>_draft({ request: { <id>, draftVersion } })` takes the same fence.

**Refusals name the next act.** `DRAFT_VERSION_MOVED` (the draft moved after the read, or no draft is held — `details.draftVersion` is then null) and `DRAFT_AXIS_CONTESTED` (the player's own form changed `details.contestedAxes` after the version staged against) carry `details.nextAct: "get_draft"` from every tool. From `stage_<kind>_draft` and `commit_<kind>_draft` only, a revision `CONFLICT` also carries `"get_draft"` and a validation refusal `"stage"`; every other refusal carries no hint. After reading the draft again, show the player what it now holds and commit only on their word. A commit is idempotent on `{ id, draftVersion }`, so a retried commit replays its outcome.

`fork_strategy` copies one revision into a new create draft and creates nothing until that draft commits. An agent binds to a strategy through its draft's `STRATEGY_BINDING` axis, on a create or as a rebind. The plan tools (`compile_strategy_plan`, `stage_strategy_plan`, `apply_strategy_plan`), `update_strategy_signal_rule`, `create_intelligence_agent`, `update_intelligence_agent`, `rebind_intelligence_agent` and `create_strategy` are **retired** and absent from discovery.

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
| `battlegrid-strategy-authoring` | Build a strategy from a plain-English idea: gather evidence, lock the spec, stage it into the strategy's draft, review the diff, diagnostics and impact, commit only on confirmation. Also fork, tune, restore, archive, preview |
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
