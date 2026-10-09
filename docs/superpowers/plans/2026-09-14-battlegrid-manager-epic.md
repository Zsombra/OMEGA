# BattleGrid Manager — Epic (master implementation plan)

> **For agentic workers:** this is the EPIC. It decomposes the spec
> (`docs/superpowers/specs/2026-09-14-battlegrid-manager-design.md`) into seven phase plans.
> Execute one phase plan at a time with superpowers:subagent-driven-development or
> superpowers:executing-plans. **Phase 0 is written in full** at
> `docs/superpowers/plans/2026-09-14-battlegrid-manager-phase-0.md`. Phases 1–6 are
> specified here at task level; each gets its own full plan when its predecessor's exit gate
> is met, because each depends on what the previous phase measured.

**Goal:** An autonomous manager of the ANBUJEFF BattleGrid account, driven from Hermes
desktop, that creates/revises/deploys/retires strategies and agents and watches every open
position, executing closes and tightens on its own inside a self-governing, code-enforced
risk policy, after a shadow phase proves its judgement.

**Architecture:** A new repository `battlegrid-manager` runs a Python service in Docker
Compose (FastAPI + MCP server + APScheduler + Postgres) that owns the ONLY BattleGrid
session and the only write path, keeps an append-only audit ledger, and exposes manager
tools to two Hermes profiles (`commander` chat, `sentinel` cron). The backend never calls
an LLM; Hermes profiles decide, the backend guards/executes/verifies/records. OMEGA is
imported as a pinned dependency for authoring.

**Tech Stack:** Python 3.12 (Docker `python:3.12-slim`), `mcp` 2.x (client + server),
`httpx`, FastAPI, SQLAlchemy 2.0, APScheduler 3.x, Postgres 16, pytest, Docker Compose v2,
Hermes 0.21.x (profiles, cron, `mcp_servers`, Desktop Plugin SDK), OMEGA (git dependency).

## Global Constraints (from the spec; every task inherits these)

- **Rule 1:** decide in the model, enforce in code. The backend never calls an LLM.
- **Rule 2:** one write path — only `manager/actions/` may call a BattleGrid write tool. Hermes
  holds no BattleGrid credential.
- **Rule 3:** unreadable is not empty — a failed read is `UNDETERMINED` with its error, never
  an absence.
- Rate limit: never exceed **2 requests/second sustained, bank 100** (measured server cap:
  3 r/s, 120 banked; JSON-RPC `-32000` on breach, honour `retryAfter`).
- Every compare-and-swap write carries the `expectedRevision` read in the same action; a
  `CONFLICT` is re-read and re-proposed, never bump-and-retried.
- No autonomous write before the shadow gate: **≥ 7 days AND ≥ 20 reviewed AMBER decisions,
  none the user would have vetoed** (D13). RED mechanical actions excepted.
- Contract version at last acknowledged start must equal the live `/mcp/version`
  `contractVersion` for any write (54.1.0 in the morning of 2026-09-14, **56.1.0 by 13:34**; the
  tool count did not move — never use it as the freshness signal).
- TPO evidence is `UNAVAILABLE` (never FALSE) during the first 60 min of each UTC day.
- Market read text stays purely technical; cap 2000 chars; condition names cap 80 chars.
- Radar cap is 20 coins per user and is **full today** (all Cycle-1). Radar slots are a
  scarce resource the manager allocates; `enabled:false` keeps slots, a replacement upsert
  drops any slot not resent.
- **Every backend job is its own Compose service** (one image; `serve` or `run <job>`), switched on or off from Docker, never from the host. Services by phase: `postgres api watch inventory panel` (P0), `mcp` (P1), `triage` (P2, profile `shadow`), `executor` (P3, profile `live`; the only write path, so stopping it makes writes impossible), `review` (P4, profile `live`), `eval` (P6, profile `eval`). Hermes and the desktop app are not backend.
- Timestamps UTC everywhere. Nothing deleted; supersession is a new row.
- Deployment (Radar/Arena assignment) and fund allocation by a **Claude session by hand**
  remain forbidden; only the manager after shadow (D11) may deploy.

---

## Phase map

```
P0 Foundations ──▶ P1 Commander ──▶ P2 Shadow sentinel ──▶ P3 Guarded execution ──▶ P4 Fleet autonomy
                                          │                                              │
                                          └──────────────▶ P6 Model harness ◀────────────┘
                                                                     P5 Desktop plugin (after P2, parallel to P3/P4)
```

| Phase | Plan file | Depends on | Exit gate (from spec §9) |
|---|---|---|---|
| 0 Foundations | `2026-09-14-battlegrid-manager-phase-0.md` (full) | — | inventory report reviewed by user; Windows task retired |
| 1 Commander | `2026-09-14-battlegrid-manager-phase-1.md` (full) | P0 | user converses with the bot and gets platform answers |
| 2 Shadow sentinel | `…-phase-2.md` | P1 | ≥ 7 days, ≥ 20 AMBER decisions reviewed, none vetoed |
| 3 Guarded execution | `…-phase-3.md` | P2 | first live close verified through `get_position_audit_history` |
| 4 Fleet autonomy | `…-phase-4.md` | P3 + OMEGA tagged | one full review → revise → deploy cycle logged |
| 5 Desktop plugin | `…-phase-5.md` | P2 (reads exist) | user uses it daily |
| 6 Model harness | `…-phase-6.md` | P2 (dossiers exist) | ≥ 3 free models compared on the same tape |

---

## Phase 0 — Foundations (full plan in its own file)

Deliverable: the repository, Compose stack, an OAuth-authenticated rate-limited platform
client, database, inventory snapshots with diffs, audit ledger, the TPO panel logger moved
in-process, a REST API with bearer auth, the **inventory report** of the real roster, and
the phase-0 measurements recorded.

Tasks (each fully specified in the phase-0 file):

1. Repository scaffold, `pyproject.toml`, Compose, Dockerfile, `.env.example`, smoke test.
2. Settings (`manager/settings.py`) from environment, validated.
3. Platform errors + token-bucket rate limiter (2 r/s, bank 100).
4. File token storage for OAuth (volume, mode 0600).
5. Platform client: Streamable HTTP + `OAuthClientProvider`, `call()`, `version()`, typed
   errors, SAFE-mode signal.
6. OAuth login CLI with an in-container callback listener (port 8791) — and the DCR
   measurement (does a second client revoke mcporter's?).
7. Database models + session factory + `db init`.
8. Inventory: normalisers for the five reads (fixtures recorded from the live account).
9. Inventory snapshot + diff + `UNDETERMINED` reads.
10. Audit ledger (append-only) + system state (SAFE / PAUSED flags).
11. Panel logger port (`preview_strategy_report`, allowlisted) + hourly job.
12. Jobs as processes: `api` keeps heartbeat and health; `run <job>` powers the `inventory` and `panel` services.
13. REST API (`/health`, `/api/inventory/latest`, `/api/inventory/report`) + bearer auth.
14. Inventory report CLI (markdown) — the phase deliverable.
15. Measurements: min notional, platform LLM cost per evaluation, rate-limit headroom.
16. Runbook: keep-awake, Docker Desktop autostart, retire the Windows task.
17. **Platform watch**: surface observation (version, build, per-tool schema hash, pack version,
    npm latest), diff, `contract.drift` ledger event, writes-blocked flag + `contract ack`,
    pack-refresh recommendation, `platform_changes` read for Hermes.

---

## Phase 1 — Commander (full plan: `2026-09-14-battlegrid-manager-phase-1.md`)

Design change recorded 2026-09-14 while writing the full plan: instead of eight hand-written read tools, the `mcp` service re-exposes BattleGrid's own tools that are on a reviewed allowlist AND declared read-only AND present on the platform (85 of 115 on 2026-09-14), under their real names and schemas, plus three native tools (`manager_fleet_report`, `manager_platform_changes`, `manager_ledger`). The vendor skills' read steps then work unchanged, the exposed surface follows platform changes, and a tool that flips to writing disappears. The commander profile gets no shell, file, browser, code-execution, delegation or cron toolsets. All services share one Postgres rate limiter. The task table below is the original outline, superseded by the full plan.

Goal: talk to a bot in Hermes desktop that answers from the platform through the manager.

| # | Task | Files | Test / exit |
|---|---|---|---|
| 1.1 | `mcp` Compose service, same image (`mcp` 2.x server, Streamable HTTP at `:8792/mcp`, bearer-guarded; `docker compose stop mcp` cuts Hermes off) exposing read tools `fleet_overview`, `agent_detail`, `strategy_detail`, `positions`, `scan_coin`, `coin_qualification`, `market_read`, `ledger_query` | `manager/mcp/server.py`, `manager/mcp/tools_read.py` | `tests/mcp/test_read_tools.py` with the SDK `Client` against the ASGI app; each tool returns `UNDETERMINED` shape on platform failure |
| 1.2 | Pass-through read cache: snapshot-backed answers with `generatedAt`, live pass-through for `scan_agent_coins`, `get_agent_coin_qualification`, `preview_strategy_report` (rate-limited) | `manager/inventory/reads.py` | cache hit/miss tests; rate limiter honoured under a 30-call burst |
| 1.3 | Hermes profile `commander`: `hermes profile create commander --description "..."`, `mcp_servers.battlegrid_manager` (url `http://127.0.0.1:8792/mcp`, bearer via `${MANAGER_TOKEN}`, `trust: full`, `supports_parallel_tool_calls: false`), skills symlink for the vendor pack (nine skills) | `hermes/profiles/commander/config.yaml.tmpl`, `hermes/install.ps1` | `hermes -p commander mcp list` shows the tools |
| 1.4 | `battlegrid-manager` Hermes skill (SKILL.md): what each manager tool returns, the UNDETERMINED discipline, "scan X against book Y" recipe, never-invent-numbers rule | `hermes/skills/battlegrid-manager/SKILL.md` | skill loads; a scripted chat transcript test via Hermes API server returns platform numbers verbatim |
| 1.5 | Retire MAEZTRO's daily-report cron (job `da33cccb09f7`) after `manager report daily` exists; `python -m manager report daily` writes the same sections (account, radar) from snapshots | `manager/inventory/report.py` | report matches the snapshot; cron removed with `hermes cron remove` |
| 1.6 | Phase-1 record: transcript of the first commander conversation committed under `docs/phase-1/` | docs | user confirms exit gate |

## Phase 2 — Shadow sentinel

| # | Task | Files | Test / exit |
|---|---|---|---|
| 2.1 | Alembic introduced; tables `dossiers`, `decisions`, `triage_rows`, `alerts` | `manager/db/migrations/` | migration up/down on Postgres in CI |
| 2.2 | Tape client: Hyperliquid public `candleSnapshot`, `metaAndAssetCtxs` (funding/OI), cached | `manager/tape/hyperliquid.py` | fixture tests; no key required |
| 2.3 | Triage engine (deterministic): inputs = position row + platform reads + panel row + tape; output = colour + reasons; first-hour TPO rule; R-multiple and ATR distance maths | `manager/triage/rules.py` | property tests over the spec §3.3 thresholds; golden fixtures |
| 2.4 | Dossier builder + hash; `allowed_outcomes` computed by guards BEFORE the model reads (guards from P3 are stubbed as "all allowed" in shadow, but the field exists) | `manager/dossier/build.py` | dossier JSON schema test; hash stable across key order |
| 2.5 | `triage` Compose service (profile `shadow`): anchor-close triggers (5m/15m/1h/4h) + 5-min poll; only builds dossiers for AMBER | `manager/scheduler/triage.py`, `compose.yaml` | fake-clock tests; `docker compose stop triage` halts it |
| 2.6 | REST + MCP: `triage_pending`, `position_dossier`, `decide_position(outcome, reason, rationale)` — in shadow, `decide_position` records a `decisions` row with `executed=false, mode=SHADOW` | `manager/mcp/tools_decide.py` | decision persisted, nothing else called (assert zero write-tool calls) |
| 2.7 | Hermes profile `sentinel`; cron `triage-poll` (no-agent script `python -m manager triage pending --if-any`, every 5 min, deliver `bot-chat`), `triage-decide` prompt, `fleet-review` 00:30 UTC (read-only in shadow), `daily-report` 00:05 UTC | `hermes/profiles/sentinel/*`, `hermes/cron/*.json` | jobs fire; decisions appear in the ledger |
| 2.8 | Shadow review surface: `manager shadow review` lists AMBER decisions with dossier summary; user marks `agree/veto` (stored) | `manager/cli.py`, `manager/audit/review.py` | exit gate counter: ≥ 7 days AND ≥ 20 reviewed AND 0 vetoed |

## Phase 3 — Guarded execution

| # | Task | Files | Test / exit |
|---|---|---|---|
| 3.1 | Risk policy document v1 (spec §3.2 keys, defaults, meta-bounds), derived from wallet equity; `policy_versions` table; `policy_propose` with auto-apply inside meta-bounds | `manager/risk/policy.py` | property tests: every default inside its meta-bound; revision outside bound → status `NEEDS_USER` |
| 3.2 | Guards: risk (heat, exposure, leverage, daily loss, drawdown, counts, action caps), evidence (dossier age ≤ `dossier_max_age_s`, reason enum), platform (revision, rate, contract version, pricing), kill switch | `manager/risk/guards.py` | one test per guard, refusal returns verdict list |
| 3.3 | Platform limit sync: `update_intelligence_agent` tradingConfig from policy (exposure split, leverage, daily loss, drawdown, trades/day); `halt/resume` on daily-loss/drawdown lines | `manager/actions/agent_config.py` | fixture tests; live once under user-named authorization |
| 3.4 | Action pipeline in its own `executor` Compose service (profile `live`; MCP `decide_position` only enqueues; `docker compose stop executor` makes any write impossible): `propose(kind, params) → ActionId`; `execute(ActionId, decision)` = describe → guard → perform → verify → log; idempotency keys; kinds `CLOSE`, `TIGHTEN` (`override_agent_protection`, toward entry only, needs `effectiveStopLossOrderId` from audit history), `HALT`, `RESUME` | `manager/actions/pipeline.py`, `manager/actions/kinds.py` | zero-write assertion when any guard fails; verify step reads `get_position_audit_history` |
| 3.5 | RED mechanical actions wired (stale pricing → alert only; daily loss → halt all; drawdown → PAUSED) | `manager/triage/red.py` | fake-clock tests |
| 3.6 | Mode switch `SHADOW → LIVE` requires the P2 gate counter to pass AND a user command `manager mode live --i-reviewed-the-shadow-log` | `manager/cli.py` | refuses without gate |
| 3.7 | First live close recorded with dossier hash + audit-history verification under `docs/phase-3/` | docs | exit gate |

## Phase 4 — Fleet autonomy

Prerequisite: merge `claude/tpo-strategy-brainstorm-796f15` into OMEGA `main` (PR only on the
user's explicit ask) and tag OMEGA `v0.2.0`; pin it in `battlegrid-manager/pyproject.toml`.

| # | Task | Files | Test / exit |
|---|---|---|---|
| 4.1 | Authoring wrapper: Thesis → `omega.generate` → `omega.validate` + `omega.preflight` (captures saved per contract version) → `compile_strategy_plan` once → review → `apply_strategy_plan {request:{planToken, confirm:true}}`; UPDATE path with propagation check (`list_intelligence_agents` open positions) | `manager/authoring/*` | offline: generated bodies pass preflight; live: one create+archive cycle under authorization |
| 4.2 | Radar allocation: rank (agent, coin) by qualification proximity (`scan_agent_coins`, `get_agent_coin_qualification`) and realised performance (≥ 20 closed trades gate via `omega.performance`); decide deploy/pause/replace/share (RULE slots with regime/hours) under the 20-coin cap; `preview_radar_resolution` → `upsert_radar_deployment` with fresh revision | `manager/actions/radar.py`, `manager/review/allocate.py` | CAS conflict test; preview-before-write assertion; slot-drop protection (never send fewer slots than stored unless explicitly `replace`) |
| 4.3 | Arena deployment policies: `preview_deployment_resolution` → `upsert_deployment_policy` | `manager/actions/arena.py` | same discipline |
| 4.4 | Agent lifecycle: create (strategy required, `modelId` from `list_approved_models`), rebind, archive/reactivate, re-model under the platform LLM budget | `manager/actions/agents.py` | fixture tests |
| 4.5 | `review` Compose service (profile `live`): daily fleet review at 00:30 UTC: reads → proposals → `sentinel` decides → `executor` executes; report to commander | `manager/review/daily.py`, `compose.yaml` | one full cycle logged |
| 4.6 | Cycle-1 adoption decision recorded (keep/re-model/archive per agent, with the STRUCT 15-trade record and the 20-trade sample rule) | docs/phase-4 | exit gate |

## Phase 5 — Desktop plugin

| # | Task | Files | Test / exit |
|---|---|---|---|
| 5.1 | Unified package `~/.hermes/plugins/battlegrid-manager/` with `plugin.yaml`, `dashboard/manifest.json`, `dashboard/plugin_api.py` (FastAPI router proxying to `http://127.0.0.1:8790/api/*` with the bearer token from `.env`) | `hermes/plugin/*` | `curl /api/plugins/battlegrid-manager/fleet` returns the fleet |
| 5.2 | `desktop/plugin.js` (ESM, `@hermes/plugin-sdk`): panes Fleet, Positions (distance to stop), Ledger, Risk policy (edit meta-bounds → `policy_propose`), Epic progress (reads `docs/` phase records via API) | `hermes/plugin/desktop/plugin.js` | loads in Settings → Plugins; hot reload |
| 5.3 | Pause/Resume button → `pause`/`resume` tools; confirm dialog states blast radius | same | manual test recorded |

## Phase 6 — Model harness

| # | Task | Files | Test / exit |
|---|---|---|---|
| 6.1 | `eval` Compose service (profile `eval`, on demand): `manager eval --dossiers <from> <to> --model <id>`: replays recorded dossiers through the Hermes API server (`POST /v1/chat/completions`, model pinned) with the sentinel prompt; scores outcome vs recorded position result (MFE/MAE from tape) | `manager/eval/replay.py` | deterministic scoring tests on fixtures |
| 6.2 | Comparison report for ≥ 3 free models (`upstage/solar-pro4:free`, `z-ai/glm-5.2:free`, `minimax/minimax-m3:free`, Nemotron 3 sizes) | `docs/phase-6/` | exit gate |

---

## Cross-cutting risks and how the epic handles them

| Risk | Handling |
|---|---|
| OAuth DCR for a second client revokes mcporter's session | P0 task 6 measures it first; if it does, the manager becomes the single client and Hermes/MAEZTRO stop using mcporter (they were to be retired anyway) |
| Minimum notional exceeds professional sizing at 54 USDC | P0 task 15 measures; the risk policy's sizing refuses orders below `min_notional_usd` and reports "fund more or fewer books" honestly |
| PC sleep / Docker Desktop down | P0 task 16 runbook; heartbeat gap alert; SAFE mode on restart until a fresh snapshot |
| Contract drift (happened today: 54.1.0 → 56.1.0 in hours, semantics changed, tool count unmoved) | P0 task 17 platform watch: version + build + per-tool schema hash + pack version every 10 min; drift ⇒ `contract.drift` event, writes disabled until `manager contract ack <version>`, pack refresh recommended, fixtures re-recorded; Hermes gets `platform_changes` to explain sudden errors |
| Rate-limit bank exhaustion on a full-fleet triage | limiter at 2 r/s / bank 100; triage staggers reads; P0 task 15 measures headroom |
| Free model quality | shadow gate + P6 harness; model switchable per job without code change |
| Two OMEGA branches | P4 prerequisite: merge TPO branch to main (PR on explicit ask), tag `v0.2.0` |

## Open user asks recorded for later phases

- Whether Arena (Market Grid) manual play is ever in scope (spec non-goal today).
- Whether to move to a VPS after P3 (D10 keeps this PC for P0–P3).
