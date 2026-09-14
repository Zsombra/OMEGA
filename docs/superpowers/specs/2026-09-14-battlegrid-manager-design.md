# BattleGrid Manager — design

**Date:** 2026-09-14 · **Status:** approved in conversation, awaiting written review ·
**Owner:** rafaelmorel809 · **Author:** Claude Fable 5.1 (brainstorming session in
`claude/battle-grid-bot-planning-9ed3c3`)

An autonomous manager for the ANBUJEFF BattleGrid account, operated through the Hermes
desktop app. It creates, revises, deploys and retires strategies and agents, watches every
open position, and may close or tighten a position on its own once it has earned that
authority — inside a risk policy it writes for itself and enforces in code.

This document is the spec. The implementation plan (the epic) is derived from it and lives
in `docs/superpowers/plans/`.

---

## 0. Decisions of record

Every item below was put to the user on 2026-09-14 and answered. None is inferred.

| # | Decision | User's words / choice |
|---|---|---|
| D1 | **Authority.** The manager is fully autonomous inside risk limits. | "Fully autonomous inside risk limits" |
| D2 | **Scope of fleet.** Everything on the account, whatever exists. | "Everything on the account, whatever exists" |
| D3 | **Close evidence.** Platform reads, OMEGA's TPO panel, external tape (Hyperliquid), and LLM judgement — all four. | "all of them" |
| D4 | **Surface.** Hermes desktop chat only; bot topology is the designer's choice. | "through the Hermes text app … one or multiple bots, however you decide" |
| D5 | **Risk limits.** No user-imposed caps; the manager governs itself "like a professional would". | "I don't want to put limitations, but he should take into consideration proper risk management" |
| D6 | **Model.** Agnostic. Default Solar (`upstage/solar-pro4:free`); free models preferred; switchable in-app. | "make it agnostic … As a default, let's use Solar" |
| D7 | **Write path.** Designer's recommendation: the Docker backend is the only write path. | "Follow your best recommendation" |
| D8 | **Repository.** Designer's recommendation: a new repo, OMEGA imported as a dependency. | "Have your honest recommendation here and follow that recommendation" → recommendation given, then "1: Docker backend + Hermes brain, new repo" |
| D9 | **Approach.** Deterministic Docker backend, Hermes as the brain. | "1: Docker backend + Hermes brain, new repo (Recommended)" |
| D10 | **Uptime.** This PC, never sleeps, keep-awake enforced, phases 0–3. | chosen |
| D11 | **Standing-rule change.** After the shadow phase the manager may deploy, close, revise and bind on its own within its policy, without per-instance approval. Supersedes the 2026-08-25 / 2026-09-10 rule for the manager only. Does NOT authorise a Claude session to deploy or bind by hand. | "Yes, confirmed as stated" |
| D12 | **Old fleet.** The manager adopts the MAEZTRO Cycle-1 agents and may re-model or archive them per its policy. | chosen |
| D13 | **Shadow exit.** ≥ 7 days and ≥ 20 reviewed AMBER decisions, none the user would have vetoed, before closes go live. | chosen |
| D14 | **UI.** A Hermes desktop plugin is in scope as its own phase. | "I want to know if you can actually create a UI plugin" → yes, phase 5 |

Designer's calls the user delegated (D4, D5, D7, D8): two Hermes profiles (`commander`,
`sentinel`); a self-derived risk policy with meta-bounds; single write path in the backend;
new repository `battlegrid-manager`; cadence = anchor-candle close + 5-minute safety poll.

---

## 1. What exists today (measured 2026-09-14, platform DOWN)

- **BattleGrid** returned HTTP 502 from nginx on the public `/mcp/version` endpoint during
  this session. Live account state could not be verified. Last recorded state (2026-09-12):
  three TPO strategies (`3d720de3`, `6c58dd38`, `430f9037`) each bound to its own agent,
  all unassigned; `56c08ef6` + TPO Alpha kept as a read-only surface; wallet ≈ 53 USDC;
  contract 54.1.0.
- **MAEZTRO** (`C:/Users/rafae/Documents/HERMES/PROJECT/MAEZTRO`, a Hermes project):
  five "Cycle-1" strategies and agents (`CTP/OSCW/VOLB/FUND/STRUCT Alpha`, platform LLM
  `anthropic/claude-opus-4.6`). Its own files disagree on deployment: `ORIGINAL_GOAL.md`
  says 20/20 Radar coins deployed; `HANDOFF_2026-09-06.md` says 0 deployed. **Unknown until
  measured.** A Hermes cron job "BattleGrid Daily Report (UTC 00:00)" runs from this folder
  via `bg_mcp.py` → `npx mcporter` (5–8 s per call).
- **grid-commander** (`C:/Users/rafae/grid-commander`): Next.js/Postgres workbench,
  Dockerised, read-only MCP server, last touched 2026-08-11 against surface v17. Not reused
  (D9); its docs on positionManagement and report grammar remain reference material.
- **OMEGA** (this repo): read-only-by-construction Python toolkit (`omega/`, 1050 tests),
  installable via `pyproject.toml` (deps: pydantic, pandas). Reused as a dependency.
- **Hermes** desktop v0.21.1 on the host. Terminal backend `local`; profiles `maezttro`,
  `openspec`; plugins `openspec`, `workspace-fence`; no `mcp_servers` configured; model
  `upstage/solar-pro4:free` via the Nous portal. Native MCP (HTTP + OAuth + `trust`
  tiers), cron (agent and no-agent), `delegate_task`, Kanban, `/heartbeat`, `/goal`,
  `/loop`, hooks, API server, and the Desktop Plugin SDK are all available.
- **Vendor skill pack** `.agents/skills/battlegrid/` (contract 55.0.0 export): nine skills
  incl. agent-management, trade-proposal, trade-analysis, radar-deployment,
  strategy-doctor, market-analysis. The platform already provides: position management
  (break-even, trailing giveback, time decay), Radar policies, Arena deployment policies,
  propose→accept entry decisions, `close_agent_position`, `override_agent_protection`,
  typed doctor reads. The capability the platform does NOT provide is a discretionary
  "the data says this is reversing — close it now" decision. That is what this manager adds.

---

## 2. Architecture

```
Hermes desktop (host, Windows)                Docker Compose (host, this PC)
┌────────────────────────────────┐            ┌──────────────────────────────────────┐
│ commander profile  (chat)      │ MCP/HTTP   │ manager    FastAPI + MCP + scheduler │
│ sentinel  profile  (cron only) │───────────▶│   platform/   BattleGrid client      │──▶ mcp.battlegrid.trade
│ desktop plugin     (phase 5)   │ REST       │   inventory/  fleet snapshots + diffs│──▶ api.hyperliquid.xyz (read)
└────────────────────────────────┘            │   risk/       policy + guards        │
                                              │   dossier/    evidence packs         │
                                              │   actions/    write pipeline         │
                                              │   authoring/  omega wrapper          │
                                              │   audit/      append-only ledger     │
                                              │   panel/      TPO panel logger       │
                                              │ postgres   (volume)                  │
                                              └──────────────────────────────────────┘
```

**Rule 1 — decide in the model, enforce in code.** Hermes profiles (any model) decide.
The backend guards, executes, verifies and records. The backend never calls an LLM.

**Rule 2 — one write path.** Only `manager/actions/` may call a BattleGrid write tool.
Hermes holds no BattleGrid credential. Reads reach Hermes through manager tools (cached
snapshots plus pass-through).

**Rule 3 — unreadable is not empty.** Any failed read is reported as UNDETERMINED with the
error; never as an absence.

### 2.1 Repository

New repository `battlegrid-manager` (location chosen at phase 0; sibling of OMEGA under
`Documents/GitHub/`). Python ≥ 3.12. Layout:

```
battlegrid-manager/
  compose.yaml            manager + postgres; volumes for tokens, db, panel data
  Dockerfile              multi-stage; runtime image carries no secrets
  manager/                the service (packages below)
  hermes/                 profile templates, skill, cron job specs, plugin package
  tests/                  unit + fixture-replay + guard property tests
  docs/                   ADRs, runbooks, phase records
  openspec/               spec-driven change tracking (same as OMEGA)
```

OMEGA is pinned: `omega @ git+https://github.com/Zsombra/OMEGA@<tag>`. OMEGA gets a tag
per contract version; the manager bumps deliberately.

### 2.2 Components

| Package | Responsibility | Interface | Depends on |
|---|---|---|---|
| `platform/` | One BattleGrid MCP session: OAuth 2.1 + PKCE, refresh, token volume; Streamable HTTP client; rate limiter ≤ 2 req/s sustained (measured cap 3/s, 120 bank); typed error envelopes; `/mcp/version` watch; SAFE mode on 5xx | `call(tool, args) → Result \| PlatformError`, `version()`, `health()` | httpx, mcp SDK |
| `inventory/` | Scheduled snapshots of account, agents, strategies, Radar policies, Arena policies, positions, pending approvals; row-level diffs; freshness stamps | `snapshot()`, `diff(since)`, `fleet()` | platform, db |
| `risk/` | The policy document (versioned), meta-bounds, guard evaluation, platform-side limit sync (`update_intelligence_agent` tradingConfig, `halt/resume`) | `policy()`, `propose_revision()`, `guards(action, ctx) → Verdict`, `sync_platform_limits()` | inventory, actions |
| `dossier/` | Evidence pack per open position (§4.2) | `build(position_id) → Dossier`, `hash` | platform, panel, tape |
| `actions/` | Every write as a command: describe → guard → perform → verify → log; idempotency; CAS revisions | `propose(kind, params) → ActionId`, `execute(ActionId, decision) → Outcome` | platform, risk, audit |
| `authoring/` | Thesis → `omega.generate` → `omega.validate`/`preflight` → compile → review → apply; revision with propagation check | `draft(thesis)`, `compile(plan)`, `apply(plan_token)` | omega, platform, actions |
| `audit/` | Append-only ledger: decisions, actions, dossier hashes, outcomes, alerts | `record()`, `query()` | db |
| `panel/` | The OMEGA TPO panel logger (`scripts/tpo_panel_pull.py`) moved in-process, hourly at :05 UTC | `latest(coin)`, `history(coin, n)` | platform, db |
| `tape/` | Hyperliquid public reads: candles, funding, OI (read-only, no key) | `candles(coin, tf, n)`, `funding(coin)` | httpx |
| `mcp/` | The tools Hermes sees (§5.3); REST twins for the plugin | Streamable HTTP MCP at `/mcp`; REST at `/api` | all above |
| `scheduler/` | APScheduler: triage cadence, snapshots, panel, daily review, keep-alive | jobs table | all above |

### 2.3 Data model (Postgres)

`snapshots`, `agents`, `strategies`, `radar_policies`, `arena_policies`, `positions`
(with `pricing_status`), `dossiers` (jsonb + sha256), `decisions` (who/model/outcome/
rationale/dossier_hash), `actions` (kind, params, guard verdicts, platform response,
verify result), `policy_versions`, `alerts`, `panel_rows`, `tape_cache`, `jobs`.
All timestamps UTC. Nothing is deleted; supersession is a new row.

---

## 3. Autonomy model

### 3.1 Four guard layers (all in code, all before any write)

1. **Risk policy guards** (§3.2).
2. **Evidence guard.** A close or tighten needs a dossier ≤ 300 s old for that position and
   a decision record naming the invalidation reason from a fixed enum
   (`THESIS_GATE_FALSE`, `REGIME_FLIP`, `MOMENTUM_STALL`, `STOP_PROXIMITY`, `TIME_STOP`,
   `STALE_PRICING`, `POLICY_BREACH`, `USER_INSTRUCTION`). No dossier → refused.
3. **Platform guards.** `expectedRevision` freshly read for every CAS write; rate limit;
   `contractVersion` equals the version recorded at last acknowledged start; position
   `pricingStatus` not STALE for price-dependent actions; open-position check before any
   strategy revision that propagates.
4. **Kill switch.** `PAUSED` flag (db row, settable from Hermes or plugin): all actions
   become propose-only; RED mechanical actions still execute (they only reduce risk).

### 3.2 Self-governing risk policy

Derived from wallet equity at each policy revision. Defaults are professional norms; the
manager may revise any value inside its meta-bound with a logged rationale (auto-applied);
outside the meta-bound a revision is a proposal the user approves. Meta-bounds are
user-editable only.

| Key | Default | Meta-bound | Enforced where |
|---|---|---|---|
| `risk_per_trade_pct` (equity at risk to the stop) | 1.0 | 0.25–2.0 | guard; agent config |
| `max_portfolio_heat_pct` (sum of open risk) | 5.0 | 2–8 | guard |
| `max_gross_exposure_pct` | 60 | 30–100 | agent `maxConcurrentExposureUsd` split across active agents; guard |
| `max_leverage` | 1 | 1–2 | agent config; guard |
| `daily_loss_halt_pct` | 3.0 | 1–5 | agent daily-loss limit; guard → `halt` all agents until next UTC day |
| `max_drawdown_pause_pct` | 10 | 5–15 | agent drawdown limit; guard → `PAUSED` until the user resumes |
| `max_open_positions` | 4 | 1–8 | guard |
| `max_same_direction_per_category` | 2 | 1–4 | guard |
| `actions_per_day` (close / tighten / deploy / revise / agent-config) | 8 / 12 / 6 / 3 / 6 | ×0.5–×2 | guard |
| `dossier_max_age_s` | 300 | 60–900 | evidence guard |
| `min_notional_usd` | **measured in phase 0** | — | guard; sizing |
| `platform_llm_budget_usd_per_day` (agents' own evaluations) | measured in phase 0 | — | guard on agent model changes |

Platform-side limits are written with `update_intelligence_agent` so the platform refuses
what the policy forbids even if the manager is down. The manager's guards are the second
layer.

### 3.3 Position loop

**Cadence.** Every open position is triaged at its book's anchor-candle close
(5m/15m/1h/4h) and by a 5-minute safety poll. The first 60 minutes of each UTC day carry
the TPO first-hour trap (developing-TPO columns null): TPO evidence is marked
`UNAVAILABLE`, never FALSE, during that window.

**Triage → one of three colours, deterministic:**

- **RED — mechanical, no model.** Any of: `pricingStatus == STALE_MARK_PRICE`; contract
  drift detected; daily-loss line crossed (→ halt all); drawdown line crossed (→ PAUSED);
  agent halted by platform with an open position (→ alert only). Actions: halt / alert /
  (never a market close on stale pricing).
- **AMBER — decision requested from `sentinel`.** Any of: in loss beyond 0.5 R and the
  entry-direction qualification verdict now fails; regime flipped against the position;
  required TPO gate no longer true (outside the first-hour window); in profit beyond 1 R
  with momentum stalling (PPO trajectory turning) and trailing not yet armed; time in
  trade > 3 anchor bars with TP progress < 25 %; distance to stop < 0.5 × ATR.
  Outcomes allowed: `HOLD`, `TIGHTEN(stop)` (via `override_agent_protection`, only toward
  entry), `CLOSE` (via `close_agent_position`). The backend validates the outcome through
  all four guards, executes, verifies with `get_position_audit_history`, records.
- **GREEN — nothing.** Logged as a triage row (cheap), no dossier built.

**Shadow phase (D13).** Until exit criteria are met, AMBER outcomes are recorded and shown
in Hermes as "would have …"; nothing executes except RED mechanical actions.

### 3.4 Strategy and deployment loop

- **Daily fleet review** (sentinel cron, 00:30 UTC after the session roll): per agent —
  `scan_agent_coins`, `get_agent_coin_qualification` on the shortlist,
  `get_radar_activity_summary`, `get_agent_budget`, `list_gate_blocks`; per strategy —
  signal performance where sample ≥ 20 closed trades (OMEGA `performance.py` gate).
  Proposals: new book (thesis), revision, re-model an agent, archive, deploy/undeploy.
- **Authoring.** Thesis → OMEGA generate → validate + preflight offline → `compile` once
  → review approved plan → `apply`. Revisions to bound strategies check open positions
  first (propagation is live). Market read text stays purely technical (user rule).
- **Deployment.** Radar per coin: `get_coin_metadata` → `preview_radar_resolution` →
  `upsert_radar_deployment` with the revision just read; respects the 20-coin cap and
  `radarPaused`. Arena deployment policies via `preview_deployment_resolution` →
  `upsert_deployment_policy`. Manual Market Grid submissions are a **non-goal** (§8).
- **Agent lifecycle.** Create only against a committed strategy; model from
  `list_approved_models` (`modelId`); may re-model Cycle-1 agents off Claude Opus 4.6 per
  the platform LLM budget (D12); archive underperformers per policy; never delete.

---

## 4. Evidence

### 4.1 Sources (D3)

1. Platform: `list_user_active_positions`, `get_agent_coin_qualification`,
   `get_signal_log` scorecard, `get_regime_snapshot`/`history`, `get_position_audit_history`,
   `get_agent_budget`, `get_market_context`, `preview_strategy_report` for the book's own
   sections on the coin.
2. OMEGA TPO panel: latest row + prior rows for the coin (value area, POC, width, room).
3. Hyperliquid tape: last N candles at the anchor, funding, OI.
4. LLM judgement: the sentinel reads the dossier and returns one outcome + reason enum +
   free-text rationale. The rationale is stored; only the enum is acted on.

### 4.2 Dossier (one JSON document, hashed)

`position` (entry, side, size, leverage, stop, TP, break-even/trailing status, R
multiple now, distance to stop in % and ATR), `platform_reads` (each with `generatedAtMs`
and UNDETERMINED on failure), `tpo` (row or UNAVAILABLE), `tape`, `policy_state` (heat,
exposure, actions used today), `allowed_outcomes` (computed by guards BEFORE the model
reads it — the model never learns an option the guards would refuse), `triage_reasons`.

---

## 5. Hermes side

### 5.1 Profiles

| Profile | Role | Model | Skills | Tools |
|---|---|---|---|---|
| `commander` | The bot you talk to. Explains fleet, runs scans, proposes and (post-shadow) orders actions, edits policy, pauses/resumes | profile default (Solar) — switch in Settings → Model | vendor pack (all nine) + `battlegrid-manager` skill | `mcp_servers.battlegrid_manager` |
| `sentinel` | Cron only. Triage decisions, daily review, daily report | per-job pins (`hermes cron edit --model`) | `battlegrid-manager` skill | same |

Each profile is its own Hermes home (memory isolation per Hermes docs). Both get
`mcp_servers.battlegrid_manager: {url: http://127.0.0.1:8790/mcp, headers:
{Authorization: "Bearer ${MANAGER_TOKEN}"}, trust: full, supports_parallel_tool_calls: false}`.

### 5.2 Cron jobs (sentinel)

| Job | Schedule | Mode | Delivery |
|---|---|---|---|
| `triage-poll` | every 5 min | **no-agent** script → `GET /api/triage/pending`; prints only when AMBER exists | `bot-chat` (sentinel acts on it) |
| `triage-decide` | fired by the above via bot-chat | agent turn: read dossier(s) via manager tools, return outcome per position | manager `execute` tool |
| `fleet-review` | 00:30 UTC daily | agent | `bot-chat` → proposals recorded; commander summarises to the user |
| `daily-report` | 00:05 UTC daily | no-agent → `/api/report/daily` | local file + commander bot-chat |

The MAEZTRO cron job and `bg_mcp.py` path are retired at phase 1 exit; the Windows task
"OMEGA TPO panel" is retired at phase 0 exit (logger moves in-process).

### 5.3 Manager MCP tools (what the bots see)

Reads: `fleet_overview`, `agent_detail`, `strategy_detail`, `positions`,
`position_dossier`, `scan_coin`, `coin_qualification`, `market_read`, `policy_get`,
`ledger_query`, `triage_pending`, `report_daily`.
Decisions/writes (all go through `actions/`): `decide_position` (outcome + reason enum +
rationale), `policy_propose`, `strategy_draft`, `strategy_compile`, `strategy_apply`,
`deploy_preview`, `deploy_apply`, `agent_configure`, `agent_lifecycle`, `pause`, `resume`.
Every write tool returns the guard verdicts verbatim when refused.

### 5.4 Model agnosticism (D6)

The backend never calls an LLM. A replay harness (`manager eval --dossiers <range>
--model <id>`) drives any model through recorded dossiers via the Hermes API server and
scores outcomes against recorded position results. Free models in the current catalog:
`upstage/solar-pro4:free`, `z-ai/glm-5.2:free`, `minimax/minimax-m3:free`,
`nvidia/nemotron-3-super-120b-a12b:free`, `nvidia/nemotron-3-ultra-550b-a55b:free`,
`nvidia/nemotron-3.5-lightning:free`, `thinkingmachines/inkling:free`. No ranking is
claimed until the harness has run.

### 5.5 Desktop plugin (phase 5)

Unified package `~/.hermes/plugins/battlegrid-manager/`: `desktop/plugin.js` (panes:
Fleet, Positions with distance-to-stop, Ledger, Risk policy, Epic progress),
`dashboard/plugin_api.py` proxying to the manager REST API. Opt-in in Settings → Plugins.

---

## 6. Availability (D10)

This PC, phases 0–3: Windows power plan never sleeps; Docker Desktop autostart; compose
`restart: unless-stopped`; the scheduler records a heartbeat row every minute and alerts on
any gap > 6 min; keep-awake enforced by the Hermes desktop `keep-awake.json` plus a
`powercfg` setting recorded in the runbook. A VPS migration is a candidate later phase,
not committed.

---

## 7. Error handling and testing

- Platform 5xx / version-probe failure → SAFE mode: no writes, exponential backoff, one
  alert per episode, reads reported UNDETERMINED. Exactly today's situation.
- Rate limit `-32000` → honour `retryAfter`; never batch faster than 2 req/s.
- CONFLICT on CAS → re-read, re-guard, re-propose; never bump-and-retry.
- Tool result over the size cap → paginate/stream to file; never truncate silently.
- Tests: unit tests on every guard (property-based over policy bounds); fixture replay of
  captured MCP responses for every tool the manager uses; contract-drift test in CI
  against a recorded `tools/list`; scheduler tests with a fake clock; an end-to-end
  shadow-mode test that runs a full triage cycle against fixtures and asserts zero writes.

---

## 8. Non-goals

- Manual Market Grid predictions (`submit_market_grid`, `random_submit_market_grid`).
  Raise if wanted; it is a different game with entry fees.
- Fund allocation / withdrawals (not writable over MCP; user's only).
- Telegram/Discord surfaces (D4).
- Replacing the platform's own position management; the manager overlays it.
- Any autonomous write before shadow exit (D13).

---

## 9. Phases (the epic's spine)

| Phase | Deliverable | Exit criterion |
|---|---|---|
| 0 Foundations | Repo, compose, Dockerfile, OAuth (DCR measured), platform client + rate limiter, inventory snapshots, audit ledger, panel logger in-process, **live inventory report** of the real roster incl. the Cycle-1 fleet, `min_notional_usd` and platform LLM cost measured | inventory report reviewed by user; Windows task retired |
| 1 Commander | `commander` profile wired; read tools; skill; "scan X against book Y" works in chat; MAEZTRO cron retired | user converses with the bot and gets platform answers |
| 2 Shadow sentinel | triage + dossiers + `sentinel` cron; decisions recorded as "would have" | ≥ 7 days, ≥ 20 AMBER decisions reviewed, none vetoed (D13) |
| 3 Guarded execution | risk policy v1 synced to agent configs; closes/tightens live behind all four guards; kill switch | first live close verified through audit history |
| 4 Fleet autonomy | daily review, authoring wrapper, Radar/Arena deployment, agent lifecycle incl. Cycle-1 re-modelling | one full autonomous cycle (review → revise → deploy) logged |
| 5 Desktop plugin | unified package, five panes | user uses it daily |
| 6 Model harness | replay eval; model comparison report | at least three free models compared on the same tape |

---

## 10. Phase-0 measurements (not assumptions)

1. Live roster and deployment state of every agent (resolves the MAEZTRO contradiction).
2. Whether BattleGrid OAuth dynamic client registration issues an independent client for
   the backend without revoking mcporter's, and whether `mcp:wager` is granted to it.
3. Exchange minimum notional per coin at the current wallet size.
4. Platform LLM cost per evaluation for the Cycle-1 agents on Claude Opus 4.6.
5. Whether `override_agent_protection` accepts a stop tightened toward entry on a
   position whose trailing is already armed (needed for `TIGHTEN`).
6. The Claude Code connector's "needs authentication" banner: outage or expiry.
