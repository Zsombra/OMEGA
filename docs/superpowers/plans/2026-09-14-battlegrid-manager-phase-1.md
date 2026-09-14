# BattleGrid Manager — Phase 1: Commander — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Hermes profile named `commander` that the user talks to in the Hermes desktop app, answering from BattleGrid through the manager and only through the manager, with no way to write to the account.

**Architecture:** A new `mcp` Compose service exposes one MCP endpoint to Hermes. It re-exposes BattleGrid's own **read-only** tools under their real names and schemas (so the vendor skills' read steps work unchanged), plus three manager-native tools. A tool is exposed only if it is on a reviewed allowlist **and** the live platform declares it read-only **and** it exists in the latest watched surface; so the exposed surface updates itself when BattleGrid changes, and a tool that flips to writing disappears. One worker task owns the upstream session, and a supervisor task starts a new one when a broken upstream session ends it. All services share one Postgres rate limiter. The Hermes profile gets only the manager's MCP toolset plus non-shell toolsets, so it cannot reach BattleGrid any other way.

**Tech Stack:** as Phase 0, plus the MCP SDK low-level `Server` (`mcp.server.lowlevel.Server`, `on_list_tools` / `on_call_tool`), `Server.streamable_http_app(...)` with `TransportSecuritySettings`, Starlette lifespan composition, Hermes 0.21.1 profiles (`hermes profile create`, `platform_toolsets`, `skills.external_dirs`, `mcp_servers`), Hermes' bundled Python 3.11 with PyYAML 6.0.3 for the installer.

## Global Constraints

- **Read-only.** Phase 1 exposes and calls only tools that are on `PROXY_ALLOWLIST` (85 names, reviewed 2026-09-14) **and** declared `readOnlyHint: true` in the latest watched surface. `close_agent_position` is a reminder that annotations are hints: it describes itself as irreversible but is not declared destructive.
- **One path.** The `commander` profile's toolsets exclude `terminal`, `code_execution`, `file`, `browser`, `computer_use`, `delegation` and `cronjob`. Its skills never include the mcporter-based `battlegrid` skill. It holds `MANAGER_TOKEN`, never a BattleGrid credential.
- **MCP endpoint:** `http://127.0.0.1:8792/mcp`, Streamable HTTP, stateless; bearer `MANAGER_TOKEN` (401 missing, 403 wrong); DNS-rebinding protection with allowed hosts `127.0.0.1:8792` and `localhost:8792` (a foreign Host header gets 421, verified in a prototype).
- **One upstream session per process, owned by one worker task** (the SDK's client session must open and close in the same task; verified in a prototype: two HTTP sessions served by one worker, same-task open/close, clean shutdown). A supervisor task that never enters an SDK scope restarts the worker when a failed request cancels it, with a 2 s pause doubling to 60 s while restarts keep failing (final review C1, 2026-09-14).
- **Shared rate limit:** every service draws from one Postgres token bucket, 2 requests/second, bank 100 (server limit 3/s, 120).
- **Tokens refresh without a human, one process at a time** (added 2026-09-14 during execution). BattleGrid rotates refresh tokens, so only the process holding the token-file lock may refresh, with the refresh token it re-read under that lock. Background clients never start the interactive OAuth flow.
- **Unreadable is not empty; numbers verbatim;** tool errors carry the platform's code (`VALIDATION_ERROR`, `RATE_LIMITED` with `retryAfter`, …).
- **User-owned automation is not changed without an explicit yes in chat:** the MAEZTRO Hermes cron `da33cccb09f7` and the default Hermes profile.
- Repository `C:/Users/rafae/Documents/GitHub/battlegrid-manager`, new branch `phase-1-commander` from `phase-0-foundations`. Write files with the file tool (long shell heredocs fail to parse in this environment).
- Commit trailer: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## Measured facts this plan relies on (2026-09-14)

| Fact | Source |
|---|---|
| 115 tools; 85 declared read-only, 30 writing; the mcporter CLI list drops annotations | `tests/fixtures/2026-09-14/tool_annotations.json` |
| Low-level `Server(name, on_list_tools=..., on_call_tool=...)`; `Client(server)` works in memory; `server.streamable_http_app(streamable_http_path, stateless_http, transport_security, host)` returns a Starlette app | prototype `spike_mcp_server.py` |
| Outer Starlette lifespan must enter `inner.router.lifespan_context(inner)` or the session manager never starts | prototype `spike_gateway.py` |
| Hermes: `hermes profile create <name> --clone --description`, `--no-skills`; per-profile `platform_toolsets.cli`; an MCP server's toolset is named by the server name (`battlegrid_manager`), and server names listed in `platform_toolsets.<platform>` are an allowlist of MCP servers, while a list naming none loads every enabled server (`hermes_cli/tools_config.py` `_merge_mcp_servers`, read in the final review). `mcp-<server>` is only Hermes' internal registry name for the server's tools, aliased to the server name and shown as `source_name` by `tool_search` (`tools/mcp_tool_registration.py:100,296`); listed in `platform_toolsets` it matches no server, so it switched the allowlist off and printed "Unknown toolsets"; `skills.external_dirs` with `${VAR}`; `mcp_servers.<name>.headers` with `${VAR}`; `hermes -p <name> mcp test <server>`; `hermes -p <name> chat -Q --oneshot -q "<question>"`; `hermes cron pause|remove <id>` | Hermes CLI help and docs, 0.21.1 |
| Sequential read latency about 0.72 s per call | `docs/phase-0/measurements.md` §4 |
| mcp 2.1.1 `OAuthClientProvider` sets no expiry on tokens it loads from storage, never refreshes them, and answers a 401 with the interactive flow; every service stopped reading at 13:13 UTC | `oauth2.py` read in full; snapshots 15 to 54, 2026-09-14 |
| Access tokens last 3600 s, then HTTP 401; a 4.3-hour-old refresh token still refreshed; every refresh rotates the refresh token; token endpoint `https://mcp.battlegrid.trade/token`; client authentication `none`; resource `https://mcp.battlegrid.trade/` | one controlled refresh inside the api container, 2026-09-14 16:28 UTC |
| Hermes desktop sessions use the `cli` toolsets plus `project` and `desktop_ui`; `agent.disabled_toolsets` is not applied there | Hermes 0.21.1 `tui_gateway/server.py`, read 2026-09-14 |
| Hermes MCP circuit breaker: after 3 consecutive failures every tool of that server is refused for 60 s ("MCP server '<name>' is unreachable after N consecutive failures ... Do NOT retry"); an error result from the tool counts as a failure, a successful call resets the count | Hermes 0.21.1 `tools/mcp_tool.py:451` (`_CIRCUIT_BREAKER_THRESHOLD, _CIRCUIT_BREAKER_COOLDOWN_SEC = 3, 60.0`), `tools/mcp_tool_handlers.py:104-106` (`_record_call_outcome`), read 2026-09-14 |
| Hermes gives the model the date only: "Conversation started: <local date> (<UTC offset>)", the user's local date and UTC offset with no time of day, so the model cannot work out how old a UTC timestamp is | Hermes 0.21.1 `agent/system_prompt.py` `_timestamp_line`, read 2026-09-14 |
| Hermes' tool bridge refuses a `tool_call` naming more than one local tool ("Local tools require one entry per tool_call") | Hermes 0.21.1 `tools/tool_search.py:555`; seen 6 times in the Task 9 sessions |
| mcp 2.1.1 sends each request's POST from a task group hosted by the task that opened the session; a POST that raises (connection error, read timeout, a refused refresh in the auth flow) cancels that task, and closing the session in that task re-raises the failure as an ExceptionGroup | `client/streamable_http.py` (~:607, :316-328); in-memory probes on Python 3.14.2 and 3.12.14, 2026-09-14/15 |

## File structure

```
manager/proxy/__init__.py
manager/proxy/policy.py          PROXY_ALLOWLIST, decide_exposure()
manager/platform/shared_limit.py SharedTokenBucket (Postgres row lock)
manager/platform/refresh.py      TokenRefresher, StoredTokenAuth: shared OAuth tokens refreshed one process at a time
manager/mcp/__init__.py
manager/mcp/gateway.py           PlatformGateway: a supervised worker task owns the PlatformClient
manager/mcp/native.py            manager_fleet_report, manager_platform_changes, manager_ledger
manager/mcp/server.py            build_server(): list/call handlers
manager/mcp/app.py               build_http_app(): bearer + DNS-rebinding + lifespan
manager/commands/mcp.py          `python -m manager mcp`
manager/inventory/daily.py       render_daily_report()
hermes/install_commander.py      creates and configures the `commander` profile (run with Hermes' Python)
hermes/skills/battlegrid-manager/SKILL.md
scripts/check_shared_limiter.py  multi-process integration check against Postgres
scripts/check_token_refresh.py   multi-process check: one refresh grant for four processes
tests/proxy/test_policy.py, tests/platform/test_shared_limit.py, tests/platform/test_refresh.py, tests/mcp/test_server.py,
tests/mcp/test_gateway.py, tests/mcp/test_app.py,
tests/inventory/test_daily.py, tests/hermes/test_install_commander.py
docs/phase-1/acceptance.md       transcripts and the numbers they were checked against
```

---

### Task 1: The watch stores full tool definitions, and an annotation change is drift

**Files:** Modify `manager/platform/client.py` (`list_tools`), `manager/platform/watch.py` (`observe`), `manager/scheduler/jobs.py` (`job_watch`); Test `tests/platform/test_watch.py`, `tests/platform/test_client.py`.

**Interfaces:**
- Produces: `PlatformClient.list_tools() -> list[dict]` with keys `name`, `description`, `inputSchema`, `annotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`; each `bool | None`). `watch.HASH_VERSION = 2`. `observe()` hashes `{"inputSchema", "annotations"}` per tool, adds `"hashVersion": HASH_VERSION`, and returns an extra key `definitions` (the list above, or `None` when unreadable). `diff_surfaces` compares tool hashes only when both observations carry tools AND the same `hashVersion`; otherwise `tools_comparable` is False and a changed hash format alone is never drift. `job_watch` stores `surface_tools = {"observedAt", "contractVersion", "buildSha", "tools": definitions}` in system state whenever definitions are readable, and never stores `definitions` inside `surface`.

- [ ] **Step 1: Failing tests** (append to `tests/platform/test_watch.py`)

```python
async def test_annotation_flip_is_drift_and_definitions_are_stored(settings):
    from manager.db.session import init_db, make_engine, make_session_factory

    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    Session = make_session_factory(e)
    read = {"name": "get_strategy", "description": "d", "inputSchema": {"a": 1},
            "annotations": {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}}
    ctx = JobContext(client=FakePlatform({}, tools=[read]), session_factory=Session, settings=settings)
    await job_watch(ctx, npm_lookup=no_npm)
    flipped = dict(read, annotations=dict(read["annotations"], readOnlyHint=False))
    ctx.client = FakePlatform({}, tools=[flipped])
    await job_watch(ctx, npm_lookup=no_npm)
    with Session() as s:
        drift = query(s, kind="contract.drift")
        assert len(drift) == 1 and drift[0].payload["tools_changed"] == ["get_strategy"]
        stored = get_state(s, "surface_tools", {})
        assert stored["tools"][0]["annotations"]["readOnlyHint"] is False
        assert "definitions" not in get_state(s, "surface", {})


def test_a_new_hash_format_is_not_drift():
    old = surface("56.1.0", "ca61c5f1", {"get_account_state": "old-format-hash"})  # Phase 0 surface: no hashVersion
    new = dict(surface("56.1.0", "ca61c5f1", {"get_account_state": "new-format-hash"}), hashVersion=2)
    d = diff_surfaces(old, new)
    assert d["changed"] is False and d["tools_comparable"] is False and d["tools_changed"] == []
```

In `tests/platform/test_client.py`, replace the `Tool` stub class inside `test_list_tools_follows_pagination_and_reads_input_schema` and add two assertions at the end of that test:

```python
    class Annotations:
        read_only_hint, destructive_hint, idempotent_hint, open_world_hint = True, False, True, False

    class Tool:
        def __init__(self, name):
            self.name, self.description = name, "desc"
            self.input_schema = {"type": "object", "properties": {"x": {"type": "string"}}}
            self.annotations = Annotations()
```

```python
    assert tools[0]["description"] == "desc"
    assert tools[0]["annotations"] == {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/platform -q` → the two new assertions FAIL.

- [ ] **Step 3: Implement**

In `PlatformClient.list_tools`, replace the loop body with:

```python
                for t in page.tools:
                    schema = getattr(t, "input_schema", None)
                    ann = getattr(t, "annotations", None)
                    out.append({
                        "name": t.name,
                        "description": getattr(t, "description", None) or "",
                        "inputSchema": schema if isinstance(schema, dict) else dict(schema or {}),
                        "annotations": {
                            "readOnlyHint": getattr(ann, "read_only_hint", None),
                            "destructiveHint": getattr(ann, "destructive_hint", None),
                            "idempotentHint": getattr(ann, "idempotent_hint", None),
                            "openWorldHint": getattr(ann, "open_world_hint", None),
                        },
                    })
```

In `watch.observe`, replace the tools block with:

```python
    definitions: list[dict] | None
    try:
        definitions = await client.list_tools()
        tools = {t["name"]: schema_hash({"inputSchema": t.get("inputSchema", {}), "annotations": t.get("annotations", {})})
                 for t in definitions}
        tools_error = None
    except PlatformError as e:
        definitions, tools, tools_error = None, None, f"{e.kind.value}: {e.message}"
```

and add `"hashVersion": HASH_VERSION,` and `"definitions": definitions,` to the returned dict, with `HASH_VERSION = 2` defined at module level. In `diff_surfaces`, replace the condition `if old_tools is not None and new_tools is not None:` with:

```python
    if old_tools is not None and new_tools is not None and old.get("hashVersion") == new.get("hashVersion"):
```

In `job_watch`, before `set_state(s, "surface", new)`:

```python
        definitions = new.pop("definitions", None)
        if definitions is not None:
            set_state(s, "surface_tools", {"observedAt": new["observedAt"], "contractVersion": new["contractVersion"],
                                           "buildSha": new["buildSha"], "tools": definitions})
```

The first watch run after deploying this task stores a baseline in the new hash format and records no drift, because the old surface has no `hashVersion`.

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → all pass.
- [ ] **Step 5: Commit** `"Watch stores full tool definitions; an annotation change is drift"`.

---

### Task 2: Proxy policy — reviewed allowlist AND declared read-only AND present

**Files:** Create `manager/proxy/__init__.py`, `manager/proxy/policy.py`, `tests/proxy/__init__.py`, `tests/proxy/test_policy.py`; Modify `manager/platform/client.py` (`READ_ALLOWLIST`).

**Interfaces:**
- Produces: `PROXY_ALLOWLIST: frozenset[str]`; `@dataclass Exposure(exposed: list[dict], withheld: dict[str, str])`; `decide_exposure(definitions: list[dict]) -> Exposure`. Withheld reasons: `"not on the reviewed allowlist"`, `"not declared read-only"`, `"allowlisted but absent from the platform"`. `READ_ALLOWLIST = PHASE0_READS | PROXY_ALLOWLIST`.

- [ ] **Step 1: Failing tests**

```python
# tests/proxy/test_policy.py
import json
from pathlib import Path

from manager.platform.client import READ_ALLOWLIST
from manager.proxy.policy import PROXY_ALLOWLIST, decide_exposure

FX = Path(__file__).resolve().parents[1] / "fixtures" / "2026-09-14" / "tool_annotations.json"


def definitions_from_fixture():
    rows = json.loads(FX.read_text(encoding="utf-8"))["tools"]
    return [{"name": r["name"], "description": "", "inputSchema": {"type": "object"},
             "annotations": {"readOnlyHint": r["readOnly"], "destructiveHint": r["destructive"]}} for r in rows]


def test_the_measured_surface_exposes_exactly_the_85_read_only_tools():
    exp = decide_exposure(definitions_from_fixture())
    assert len(exp.exposed) == 85 and len(PROXY_ALLOWLIST) == 85
    names = {t["name"] for t in exp.exposed}
    for write in ("close_agent_position", "compile_strategy_plan", "apply_strategy_plan", "upsert_radar_deployment",
                  "propose_entry_decision", "submit_market_grid", "halt_intelligence_agent"):
        assert write not in names and exp.withheld[write] == "not on the reviewed allowlist"


def test_an_allowlisted_tool_that_flips_to_writing_is_withheld():
    defs = definitions_from_fixture()
    for d in defs:
        if d["name"] == "get_strategy":
            d["annotations"]["readOnlyHint"] = False
    exp = decide_exposure(defs)
    assert "get_strategy" not in {t["name"] for t in exp.exposed}
    assert exp.withheld["get_strategy"] == "not declared read-only"


def test_missing_or_unknown_annotation_is_not_read_only():
    exp = decide_exposure([{"name": "get_account_state", "description": "", "inputSchema": {}, "annotations": {}}])
    assert exp.exposed == [] and exp.withheld["get_account_state"] == "not declared read-only"


def test_allowlisted_tools_missing_from_the_platform_are_reported():
    exp = decide_exposure([])
    assert exp.withheld["get_account_state"] == "allowlisted but absent from the platform"


def test_the_client_allowlist_covers_every_proxied_tool_and_no_write_tool():
    assert PROXY_ALLOWLIST <= READ_ALLOWLIST
    assert "close_agent_position" not in READ_ALLOWLIST and "compile_strategy_plan" not in READ_ALLOWLIST
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/proxy -q` → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# manager/proxy/policy.py
"""Which BattleGrid tools the manager re-exposes to Hermes.

Three conditions, all required: the name is on the reviewed allowlist; the live platform declares it
readOnlyHint true; it exists in the latest watched surface. Annotations alone are not trusted
(close_agent_position calls itself irreversible yet is not declared destructive), and the allowlist
alone would miss a tool that changed behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# The 85 tools BattleGrid declared read-only on 2026-09-14 (contract 56.1.0), reviewed by name.
PROXY_ALLOWLIST: frozenset[str] = frozenset({
    "check_market_grid_submission", "derive_strategy_rule_view", "get_account_state", "get_agent_activity_feed",
    "get_agent_automation_status", "get_agent_budget", "get_agent_coin_qualification", "get_agent_conviction_calibration",
    "get_agent_decision_context", "get_agent_explorer", "get_agent_fund_allocation", "get_agent_game_history",
    "get_agent_journal", "get_agent_open_positions", "get_agent_performance", "get_agent_prompt_context_preview",
    "get_agent_thought_log", "get_agents_hub", "get_coin_candles", "get_coin_metadata", "get_coin_performance_history",
    "get_coin_signal_preview", "get_context_source_full_preview", "get_context_sources_preview",
    "get_decision_order_attribution", "get_deployment_policy", "get_entry_decision", "get_intelligence_agent",
    "get_leaderboard", "get_market_context", "get_market_grid_player_grid", "get_market_grid_results",
    "get_market_grid_session", "get_mcp_reasoning_journal", "get_metric_construction_hints", "get_open_orders",
    "get_order_status", "get_position_audit_history", "get_public_agent_game_history",
    "get_public_agent_realized_trades", "get_public_agent_signal_log_detail", "get_public_agent_signal_logs",
    "get_public_agent_signal_performance", "get_public_agent_trade_chart", "get_public_agent_unrealized_pnl",
    "get_radar_activity", "get_radar_activity_summary", "get_radar_deployment", "get_regime_history",
    "get_regime_snapshot", "get_signal_log", "get_signal_performance", "get_strategy", "get_strategy_column_contract",
    "get_strategy_section_template", "get_strategy_signal_definition", "get_top_ranked_coins", "get_trade_chart",
    "get_trade_outcome_by_decision", "get_trading_config_catalog", "get_user_activity_feed",
    "get_user_agent_game_history", "get_user_thought_log", "list_approved_models", "list_deployment_policies",
    "list_entry_decisions", "list_game_presets", "list_gate_blocks", "list_intelligence_agents",
    "list_market_grid_sessions", "list_pending_approvals", "list_radar_deployments", "list_session_agent_positions",
    "list_signal_logs", "list_strategies", "list_strategy_categories", "list_strategy_signals",
    "list_strategy_vocabulary", "list_trade_outcomes", "list_user_active_positions", "preview_deployment_resolution",
    "preview_radar_resolution", "preview_strategy_report", "scan_agent_coins", "simulate_aggregate_score",
})


@dataclass
class Exposure:
    exposed: list[dict] = field(default_factory=list)
    withheld: dict[str, str] = field(default_factory=dict)


def decide_exposure(definitions: list[dict]) -> Exposure:
    exp = Exposure()
    present = set()
    for d in definitions:
        name = d["name"]
        present.add(name)
        if name not in PROXY_ALLOWLIST:
            exp.withheld[name] = "not on the reviewed allowlist"
        elif (d.get("annotations") or {}).get("readOnlyHint") is not True:
            exp.withheld[name] = "not declared read-only"
        else:
            exp.exposed.append(d)
    for name in PROXY_ALLOWLIST - present:
        exp.withheld[name] = "allowlisted but absent from the platform"
    exp.exposed.sort(key=lambda d: d["name"])
    return exp
```

In `manager/platform/client.py`, add this import next to the other `manager.*` imports:

```python
from manager.proxy.policy import PROXY_ALLOWLIST
```

and replace the whole `READ_ALLOWLIST` definition with:

```python
PHASE0_READS: frozenset[str] = frozenset({
    "get_account_state", "list_intelligence_agents", "list_strategies", "list_radar_deployments",
    "list_user_active_positions", "preview_strategy_report", "get_coin_metadata",
    "get_trading_config_catalog", "list_approved_models",
})
READ_ALLOWLIST: frozenset[str] = PHASE0_READS | PROXY_ALLOWLIST
```

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → all pass (the Phase 0 allowlist test still holds: no write tool is in the union).
- [ ] **Step 5: Commit** `"Proxy policy: reviewed allowlist, declared read-only, and present on the platform"`.

---

### Task 3: One rate limit shared by every service

**Files:** Modify `manager/db/models.py` (add `RateBucket`), `manager/commands/common.py`; Create `manager/platform/shared_limit.py`, `tests/platform/test_shared_limit.py`, `scripts/check_shared_limiter.py`.

**Interfaces:**
- Produces: model `RateBucket(key: str PK, tokens: float, updated_at: float)`; `SharedTokenBucket(session_factory, key: str, rate: float, capacity: int, clock=time.time, sleep=asyncio.sleep)` with `async acquire() -> float` and `available() -> float`; `make_client(settings)` uses `SharedTokenBucket(key="battlegrid")` when `DATABASE_URL` is PostgreSQL, else the in-process `TokenBucket`.

- [ ] **Step 1: Failing tests**

```python
# tests/platform/test_shared_limit.py
import pytest

from manager.db.models import RateBucket
from manager.db.session import init_db, make_engine, make_session_factory
from manager.platform.shared_limit import SharedTokenBucket


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def factory():
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    return make_session_factory(e)


async def test_two_buckets_on_one_key_share_the_same_tokens():
    clock = Clock()
    waits = []

    async def sleep(s):
        waits.append(s)
        clock.t += s

    Session = factory()
    a = SharedTokenBucket(Session, "battlegrid", rate=2.0, capacity=3, clock=clock, sleep=sleep)
    b = SharedTokenBucket(Session, "battlegrid", rate=2.0, capacity=3, clock=clock, sleep=sleep)
    assert [await a.acquire(), await b.acquire(), await a.acquire()] == [0.0, 0.0, 0.0]
    assert await b.acquire() == pytest.approx(0.5)  # the bank was spent by both together
    assert a.available() == pytest.approx(0.0, abs=1e-9)


async def test_refill_is_capped_at_capacity():
    clock = Clock()
    Session = factory()
    bucket = SharedTokenBucket(Session, "k", rate=2.0, capacity=5, clock=clock)
    for _ in range(5):
        await bucket.acquire()
    clock.t += 100
    assert bucket.available() == pytest.approx(5.0)


async def test_first_acquire_on_a_new_key_survives_a_concurrent_winner(tmp_path):
    """SELECT ... FOR UPDATE takes no lock when no row matches yet, so two processes creating the same key
    both see no row and both insert; the loser's commit raised IntegrityError out of acquire(). A second
    engine on the same SQLite file is an independent connection; the clock hook fires first in _take and
    commits the row from that connection: another process won the race."""
    url = f"sqlite+pysqlite:///{tmp_path / 'race.db'}"
    engine = make_engine(url)
    init_db(engine)
    other_factory = make_session_factory(make_engine(url))
    fired = False

    def racy_clock():
        nonlocal fired
        if not fired:
            fired = True
            with other_factory() as other:
                other.add(RateBucket(key="battlegrid", tokens=3.0, updated_at=1000.0))
                other.commit()
        return 1000.0

    bucket = SharedTokenBucket(make_session_factory(engine), "battlegrid", rate=2.0, capacity=3, clock=racy_clock)
    assert await bucket.acquire() == 0.0  # must not raise IntegrityError


async def test_first_acquire_does_not_overwrite_a_row_that_already_exists(tmp_path):
    engine = make_engine(f"sqlite+pysqlite:///{tmp_path / 'existing.db'}")
    init_db(engine)
    Session = make_session_factory(engine)
    with Session() as s:
        s.add(RateBucket(key="battlegrid", tokens=0.0, updated_at=1000.0))
        s.commit()
    clock = Clock()
    waits = []

    async def sleep(s):
        waits.append(s)
        clock.t += s

    bucket = SharedTokenBucket(Session, "battlegrid", rate=2.0, capacity=3, clock=clock, sleep=sleep)
    assert await bucket.acquire() == pytest.approx(0.5)  # a reset row (3 tokens) would need no wait
    assert waits == [pytest.approx(0.5)]
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

Add to `manager/db/models.py`:

```python
class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    tokens: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[float] = mapped_column(Float)
```

```python
# manager/platform/shared_limit.py
"""One token bucket for every process, kept in Postgres and taken under a row lock.

Each service used to hold its own bucket, so four busy services could together exceed the platform's
per-user limit (3/s, 120 banked). SQLite ignores FOR UPDATE; the unit tests cover the arithmetic and
scripts/check_shared_limiter.py covers the locking against real Postgres.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from manager.db.models import RateBucket


class SharedTokenBucket:
    def __init__(self, session_factory: sessionmaker, key: str, rate: float, capacity: int,
                 clock: Callable[[], float] = time.time, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._sf, self.key, self.rate, self.capacity = session_factory, key, rate, float(capacity)
        self._clock, self._sleep = clock, sleep

    def _ensure_row(self, s: Session, now: float) -> None:
        """INSERT ... ON CONFLICT (key) DO NOTHING. SELECT ... FOR UPDATE takes no lock when no row matches
        yet, so a plain insert-if-missing lets two processes both insert and the loser raise IntegrityError."""
        values = {"key": self.key, "tokens": self.capacity, "updated_at": now}
        insert = pg_insert if s.get_bind().dialect.name == "postgresql" else sqlite_insert
        s.execute(insert(RateBucket).values(**values).on_conflict_do_nothing(index_elements=["key"]))

    def _take(self) -> float:
        """Take one token if available and return 0, else return the seconds to wait. One transaction."""
        with self._sf() as s:
            now = self._clock()
            self._ensure_row(s, now)
            row = s.scalar(select(RateBucket).where(RateBucket.key == self.key).with_for_update())
            tokens = min(self.capacity, row.tokens + (now - row.updated_at) * self.rate)
            if tokens >= 1.0:
                row.tokens, row.updated_at = tokens - 1.0, now
                s.commit()
                return 0.0
            row.tokens, row.updated_at = tokens, now
            s.commit()
            return (1.0 - tokens) / self.rate

    async def acquire(self) -> float:
        waited = 0.0
        while True:
            wait = await asyncio.to_thread(self._take)
            if wait == 0.0:
                return waited
            await self._sleep(wait)
            waited += wait

    def available(self) -> float:
        with self._sf() as s:
            row = s.scalar(select(RateBucket).where(RateBucket.key == self.key))
            if row is None:
                return self.capacity
            return min(self.capacity, row.tokens + (self._clock() - row.updated_at) * self.rate)
```

Replace `manager/commands/common.py` with:

```python
"""Shared construction for CLI commands and services."""
from __future__ import annotations

from manager.db.session import init_db, make_engine, make_session_factory
from manager.platform.client import PlatformClient
from manager.platform.ratelimit import TokenBucket
from manager.platform.shared_limit import SharedTokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.settings import Settings, get_settings


def make_client(settings: Settings | None = None) -> PlatformClient:
    s = settings or get_settings()
    if s.database_url.startswith("postgresql"):
        engine = make_engine(s.database_url)
        init_db(engine)
        bucket = SharedTokenBucket(make_session_factory(engine), "battlegrid", s.rate_limit_rps, s.rate_limit_burst)
    else:
        bucket = TokenBucket(s.rate_limit_rps, s.rate_limit_burst)
    return PlatformClient(s, FileTokenStorage(s.token_path), bucket)
```

```python
# scripts/check_shared_limiter.py
"""Run inside the image against a throwaway Postgres: four processes x 10 acquires on capacity 10, rate 5.
Shared: at least (40 - 10) / 5 = 6 seconds. Four separate buckets would take about 0 seconds."""
import asyncio
import multiprocessing as mp
import os
import time


def worker(start_at, q):
    from manager.db.session import init_db, make_engine, make_session_factory
    from manager.platform.shared_limit import SharedTokenBucket

    engine = make_engine(os.environ["DATABASE_URL"])
    init_db(engine)
    bucket = SharedTokenBucket(make_session_factory(engine), "limiter-check", rate=5.0, capacity=10)
    time.sleep(max(0.0, start_at - time.time()))

    async def run():
        for _ in range(10):
            await bucket.acquire()

    asyncio.run(run())
    q.put(time.time())


if __name__ == "__main__":
    q = mp.Queue()
    start_at = time.time() + 3.0
    procs = [mp.Process(target=worker, args=(start_at, q)) for _ in range(4)]
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    finished = max(q.get() for _ in procs)
    elapsed = finished - start_at
    print(f"elapsed {elapsed:.1f}s; shared limiter expected >= 6.0s -> {'PASS' if elapsed >= 5.5 else 'FAIL'}")
```

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → pass. Then the integration check in a throwaway project (never the running stack):

```bash
cd C:/Users/rafae/Documents/GitHub/battlegrid-manager && docker compose build api && export MSYS_NO_PATHCONV=1 && docker compose -p bgm-limitcheck up -d postgres && sleep 8 && docker compose -p bgm-limitcheck run --rm --no-deps -v "$PWD/scripts:/checks" api python /checks/check_shared_limiter.py; docker compose -p bgm-limitcheck down -v
```
Expected: `PASS`.

- [ ] **Step 5: Commit** `"One Postgres token bucket shared by every service; multi-process check included"`.

---

### Task 4: Gateway and MCP server core

**Files:** Create `manager/audit/views.py`, `manager/mcp/__init__.py`, `manager/mcp/gateway.py`, `manager/mcp/native.py`, `manager/mcp/server.py`, `tests/audit/test_views.py`, `tests/mcp/__init__.py`, `tests/mcp/test_server.py`, `tests/mcp/test_gateway.py`; Modify `manager/api/app.py` (the `/api/platform/changes` and `/api/ledger` endpoints call the shared views), and, in the final fix wave, `manager/inventory/report.py`, `manager/platform/client.py`, `tests/inventory/test_report.py`, `tests/platform/test_client.py`.

**Interfaces:**
- Consumes: `decide_exposure`, `PlatformClient.call`, `render_inventory_report`, ledger `get_state`/`query`.
- Produces: `manager/audit/views.py` with `platform_changes_view(s: Session, limit: int = 20) -> dict` and `ledger_view(s: Session, kind: str | None = None, limit: int = 100) -> list[dict]`, used by BOTH the REST API and the MCP native tools so the logic exists once; `PlatformGateway(client, *, on_restart=None, restart_delay=2.0, max_restart_delay=60.0, sleep=asyncio.sleep)` with `async start()`, `async call(tool: str, args: dict) -> dict` (raises `PlatformError`), `async stop()`, and `on_restart(restarts: int, error: str)`; `NATIVE_TOOLS: list[mcp.types.Tool]` named `manager_fleet_report`, `manager_platform_changes`, `manager_ledger`; `call_native(name, args, session_factory, now) -> dict` (raises `ArgumentError` for an unusable argument); `build_server(gateway, session_factory, clock=lambda: datetime.now(UTC)) -> mcp.server.lowlevel.Server`; `render_inventory_report(s, snap=None)`, `snapshot_age(taken_at, now) -> (taken_utc, age_s)`, `STALE_AFTER_S = 600`; `PlatformClient.aclose() -> BaseException | None` (the error closing surfaced).

Amended in the final fix wave (2026-09-15), from the final whole-branch review:
- **C1.** One upstream transport error or refused refresh used to cancel the worker for good while `mcp` stayed Up; the call in flight was never answered. The gateway below supervises the worker: the call in flight gets a typed error at once (the failure's own kind and message when closing surfaces it, else TRANSPORT pointing at the logs), queued calls survive, a new worker starts after 2 s doubling to 60 s while restarts keep failing and back to 2 s after a call succeeds, and each restart goes to the optional hook (the HTTP app records `gateway.restart`).
- **Check 1.** The model has no clock (see the facts table), so `manager_fleet_report` returns, in this order, `ageLine`, `snapshotAgeSeconds`, `freshness` (`fresh` / `stale` after 600 s / `none`), `snapshotId`, `snapshotTakenAt` and `servedAt` (ISO with `Z`), then `markdown` = `ageLine` + a blank line + the report rendered from the same snapshot row. `render_inventory_report` never reads the clock; its header reads `snapshot <id>, <YYYY-MM-DD HH:MM:SS> UTC`. SQLite returns `taken_at` without tzinfo (measured), so times are normalised to UTC and cut to the second.
- A bad native argument is a `VALIDATION_ERROR` result, not an unhandled exception; tool text is JSON with `ensure_ascii=False` (Hermes forwards the text, not `structuredContent`); the client's refusal names the manager's read allowlist.

`manager/inventory/report.py`, the parts added in the fix wave:

```python
STALE_AFTER_S = 600  # two missed runs of `run snapshot --every 300`
NO_SNAPSHOT = "# Inventory report\n\nNo snapshot has been taken yet.\n"


def as_utc(moment: datetime) -> datetime:
    """The instant in UTC, to the whole second. SQLite returns stored times without tzinfo; the manager writes UTC."""
    aware = moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
    return aware.replace(microsecond=0)


def snapshot_age(taken_at: datetime, now: datetime) -> tuple[datetime, int]:
    taken = as_utc(taken_at)
    return taken, max(0, int((as_utc(now) - taken).total_seconds()))


def render_inventory_report(s: Session, snap: Snapshot | None = None) -> str:
    """Renders `snap`, or the latest snapshot when none is given."""
    snap = snap or latest(s)
    if snap is None:
        return NO_SNAPSHOT
    reads = snap.reads
    out = [f"# Inventory report — snapshot {snap.id}, {as_utc(snap.taken_at):%Y-%m-%d %H:%M:%S} UTC", "",
    ...  # the rest of the report is unchanged
```

`manager/platform/client.py`: `_drop_session()` returns the exception `session.__aexit__` raised (still logged at debug and never re-raised), `aclose()` returns it, and `call()` refuses a tool with `f"{tool} is not on the manager's read allowlist"`. Tests added to `tests/inventory/test_report.py`: `snapshot_age` for naive, aware and future times; the header in UTC for a given snapshot.

- [ ] **Step 1: Failing tests**

```python
# tests/mcp/test_server.py
import json
from datetime import UTC, datetime
from pathlib import Path

from mcp import Client

from manager.audit.ledger import set_state
from manager.db.models import Snapshot
from manager.db.session import init_db, make_engine, make_session_factory
from manager.inventory.snapshot import READS, take_snapshot
from manager.mcp.gateway import PlatformGateway
from manager.mcp.server import build_server
from manager.platform.errors import Kind, PlatformError
from tests.platform.fake import FakePlatform

FX = Path(__file__).resolve().parents[1] / "fixtures" / "2026-09-14"


def surface_tools():
    rows = json.loads((FX / "tool_annotations.json").read_text(encoding="utf-8"))["tools"]
    return [{"name": r["name"], "description": f"{r['name']} description", "inputSchema": {"type": "object", "properties": {}},
             "annotations": {"readOnlyHint": r["readOnly"], "destructiveHint": r["destructive"]}} for r in rows]


async def setup(responses):
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    Session = make_session_factory(e)
    with Session() as s:
        set_state(s, "surface_tools", {"observedAt": "t", "contractVersion": "56.1.0", "buildSha": "ca61c5f1", "tools": surface_tools()})
        s.commit()
    fake = FakePlatform(responses)
    gateway = PlatformGateway(fake)
    await gateway.start()
    return fake, gateway, Session


async def test_lists_85_proxied_reads_plus_3_native_tools_and_no_writes():
    fake, gateway, Session = await setup({})
    try:
        async with Client(build_server(gateway, Session)) as c:
            names = {t.name for t in (await c.list_tools()).tools}
    finally:
        await gateway.stop()
    assert len(names) == 88 and {"manager_fleet_report", "manager_platform_changes", "manager_ledger"} <= names
    assert "close_agent_position" not in names and "compile_strategy_plan" not in names


async def test_a_proxied_read_returns_the_platform_payload():
    account = json.loads((FX / "get_account_state.json").read_text(encoding="utf-8"))
    fake, gateway, Session = await setup({"get_account_state": account})
    try:
        async with Client(build_server(gateway, Session)) as c:
            r = await c.call_tool("get_account_state", {})
    finally:
        await gateway.stop()
    assert r.is_error is False and r.structured_content["username"] == "ANBUJEFF"


async def test_a_non_object_payload_is_returned_as_text_only():
    # MCP defines structuredContent as a JSON object; the SDK does not enforce that (measured 2026-09-14)
    fake, gateway, Session = await setup({"list_strategies": [{"id": "s1"}]})
    try:
        async with Client(build_server(gateway, Session)) as c:
            r = await c.call_tool("list_strategies", {})
    finally:
        await gateway.stop()
    assert r.is_error is False and r.structured_content is None and json.loads(r.content[0].text) == [{"id": "s1"}]


async def test_a_write_tool_is_refused_without_touching_the_platform():
    fake, gateway, Session = await setup({})
    try:
        async with Client(build_server(gateway, Session)) as c:
            r = await c.call_tool("close_agent_position", {"decisionId": "x", "confirm": True})
    finally:
        await gateway.stop()
    body = json.loads(r.content[0].text)
    assert r.is_error is True and body["code"] == "NOT_EXPOSED" and fake.calls == []


async def test_platform_errors_keep_their_code():
    err = PlatformError(Kind.TOOL_ERROR, "Coin selection resolved to no active coins.", code="VALIDATION_ERROR")
    fake, gateway, Session = await setup({"preview_strategy_report": err})
    try:
        async with Client(build_server(gateway, Session)) as c:
            r = await c.call_tool("preview_strategy_report", {"timeframe": "1h", "sections": [], "coinSelection": {"mode": "ranked", "limit": 1}})
    finally:
        await gateway.stop()
    body = json.loads(r.content[0].text)
    assert r.is_error is True and body["code"] == "VALIDATION_ERROR" and "no active coins" in body["message"]


async def test_fleet_report_is_served_from_the_snapshot_without_platform_calls():
    fx = {n: json.loads((FX / f"{n}.json").read_text(encoding="utf-8")) for n in READS}
    fake, gateway, Session = await setup({})
    await take_snapshot(FakePlatform(fx), Session)
    try:
        async with Client(build_server(gateway, Session)) as c:
            r = await c.call_tool("manager_fleet_report", {})
    finally:
        await gateway.stop()
    assert "20 of 20 coins deployed" in r.structured_content["markdown"] and fake.calls == []


TAKEN = datetime(2026, 9, 14, 19, 29, 33, tzinfo=UTC)
FIELDS = ["ageLine", "snapshotAgeSeconds", "freshness", "snapshotId", "snapshotTakenAt", "servedAt", "markdown"]


async def snapshot_taken_at(Session, taken: datetime) -> int:
    sid = await take_snapshot(FakePlatform({n: json.loads((FX / f"{n}.json").read_text(encoding="utf-8")) for n in READS}),
                              Session)
    with Session() as s:
        s.get(Snapshot, sid).taken_at = taken
        s.commit()
    return sid


async def fleet_report_at(gateway, Session, now: datetime):
    async with Client(build_server(gateway, Session, clock=lambda: now)) as c:
        return await c.call_tool("manager_fleet_report", {})


async def test_fleet_report_leads_with_the_age_the_manager_computed_in_utc():
    fake, gateway, Session = await setup({})
    sid = await snapshot_taken_at(Session, TAKEN)
    try:
        r = await fleet_report_at(gateway, Session, datetime(2026, 9, 14, 19, 32, 27, tzinfo=UTC))
    finally:
        await gateway.stop()
    text = r.content[0].text
    body = json.loads(text)  # Hermes forwards this text, not structuredContent, to the model
    assert list(body) == FIELDS and body == r.structured_content
    assert body["snapshotAgeSeconds"] == 174 and body["freshness"] == "fresh" and body["snapshotId"] == sid
    assert body["snapshotTakenAt"] == "2026-09-14T19:29:33Z" and body["servedAt"] == "2026-09-14T19:32:27Z"
    assert body["ageLine"] == (f"Data age: snapshot {sid} was taken 2026-09-14 19:29:33 UTC, 2 min 54 s before this "
                               "report was served at 2026-09-14 19:32:27 UTC. FRESH: the inventory runs every 5 minutes.")
    assert body["markdown"].startswith(body["ageLine"] + f"\n\n# Inventory report — snapshot {sid}, 2026-09-14 19:29:33 UTC\n")
    assert "20 of 20 coins deployed" in body["markdown"] and fake.calls == []
    assert "— snapshot" in text and "\\u2014" not in text  # the text carries the characters, not \u escapes


async def test_a_snapshot_older_than_ten_minutes_is_reported_stale():
    fake, gateway, Session = await setup({})
    await snapshot_taken_at(Session, TAKEN)
    try:
        r = await fleet_report_at(gateway, Session, datetime(2026, 9, 14, 21, 32, 27, tzinfo=UTC))
    finally:
        await gateway.stop()
    body = r.structured_content
    assert body["snapshotAgeSeconds"] == 7374 and body["freshness"] == "stale"
    assert "2 h 2 min 54 s before" in body["ageLine"] and "STALE" in body["ageLine"] and "not current" in body["ageLine"]


async def test_no_snapshot_has_no_age():
    fake, gateway, Session = await setup({})
    try:
        r = await fleet_report_at(gateway, Session, datetime(2026, 9, 14, 19, 32, 27, tzinfo=UTC))
    finally:
        await gateway.stop()
    body = r.structured_content
    assert list(body) == FIELDS and body["freshness"] == "none"
    assert body["snapshotAgeSeconds"] is None and body["snapshotId"] is None and body["snapshotTakenAt"] is None
    assert body["servedAt"] == "2026-09-14T19:32:27Z" and "no snapshot" in body["ageLine"]
    assert body["markdown"].startswith(body["ageLine"] + "\n\n") and "No snapshot has been taken yet" in body["markdown"]


async def test_a_bad_native_argument_is_a_typed_error_result():
    fake, gateway, Session = await setup({})
    try:
        async with Client(build_server(gateway, Session)) as c:
            results = [await c.call_tool("manager_ledger", {"limit": "many"}),
                       await c.call_tool("manager_platform_changes", {"limit": 0}),
                       await c.call_tool("manager_ledger", {"kind": 5})]
    finally:
        await gateway.stop()
    for r, field in zip(results, ("limit", "limit", "kind"), strict=True):
        body = json.loads(r.content[0].text)
        assert r.is_error is True and body["code"] == "VALIDATION_ERROR" and field in body["message"]


async def test_no_stored_surface_means_only_native_tools():
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    gateway = PlatformGateway(FakePlatform({}))
    await gateway.start()
    try:
        async with Client(build_server(gateway, make_session_factory(e))) as c:
            names = {t.name for t in (await c.list_tools()).tools}
    finally:
        await gateway.stop()
    assert names == {"manager_fleet_report", "manager_platform_changes", "manager_ledger"}
```

```python
# tests/audit/test_views.py
from manager.audit.ledger import record, set_state
from manager.audit.views import ledger_view, platform_changes_view
from manager.db.session import init_db, make_engine, make_session_factory


def test_views_shape_the_stored_state_once_for_api_and_mcp():
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    Session = make_session_factory(e)
    with Session() as s:
        set_state(s, "surface", {"contractVersion": "56.1.0", "buildSha": "ca61c5f1", "tools": {"a": "h", "b": "h"}})
        record(s, "contract.drift", {"version": ["56.1.0", "56.1.0"]})
        record(s, "snapshot.taken", {"id": 1})
        s.commit()
        changes = platform_changes_view(s, limit=5)
        assert changes["surface"]["tool_count"] == 2 and "tools" not in changes["surface"]
        assert changes["writes_blocked"] == {"blocked": False} and len(changes["drift"]) == 1
        assert [e["kind"] for e in ledger_view(s)] == ["snapshot.taken", "contract.drift"]
        assert ledger_view(s, kind="snapshot.taken")[0]["payload"] == {"id": 1}
```

```python
# tests/mcp/test_gateway.py — the Task 4 review's shutdown race, and the final review's C1 regressions (a broken
# upstream session answers its caller, queued calls survive, restarts back off). Awaits are bounded.
"""The platform gateway: a supervisor keeps one worker task that owns the upstream session.

- A call queued behind stop() fails fast with a typed error instead of hanging its caller.
- When the upstream session breaks during a call (a connection error, or a refused token refresh raised from the
  HTTP auth flow), the SDK's transport task group cancels the worker. The call in flight gets a typed error at once,
  calls queued behind it survive, and a new worker serves them on a new session.
- Restarts pause 2 s, doubling up to 60 s while they keep failing, and the pause resets after a call succeeds.

The upstream is BattleGrid's MCP endpoint in memory (httpx2.MockTransport) and the session is opened exactly as
PlatformClient._open_session opens it (Client(streamable_http_client(...)) entered in the calling task). Every await
is bounded with asyncio.wait_for, so a regression fails in seconds instead of hanging the suite.
"""
import asyncio
import json

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthToken

from manager.mcp.gateway import PlatformGateway
from manager.platform.client import PlatformClient
from manager.platform.errors import Kind, PlatformError
from manager.platform.refresh import StoredTokenAuth, TokenRefresher
from tests.platform.test_refresh import Clock, Platform, seeded

URL = "https://mcp.battlegrid.trade/mcp"
FAST = 0.01  # restart pause for tests; production starts at 2 s


def gateway_for(client, **kw) -> PlatformGateway:
    return PlatformGateway(client, restart_delay=FAST, **kw)


class _WorkerDied(BaseException):
    """Not an Exception subclass, so it escapes the worker's per-call handlers: the worker dies outright."""


class _BlockingFake:
    """call() blocks on an asyncio.Event so a test can hold one call "in flight" deterministically, then either
    returns a payload or, for the first call only, raises whatever `first_raises` was given."""

    def __init__(self, *, first_raises: BaseException | None = None):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls: list[tuple[str, dict]] = []
        self._first_raises = first_raises

    async def call(self, tool: str, args: dict | None = None) -> dict:
        self.calls.append((tool, args or {}))
        self.started.set()
        await self.release.wait()
        if self._first_raises is not None and len(self.calls) == 1:
            raise self._first_raises
        return {"tool": tool}


class _ScriptedFake:
    """Each call takes the next outcome: a dict is returned, an exception is raised."""

    def __init__(self, outcomes: list):
        self._outcomes = list(outcomes)

    async def call(self, tool: str, args: dict | None = None) -> dict:
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class Upstream:
    """BattleGrid's MCP endpoint in memory: server/discover refused (as BattleGrid does), initialize, tools/list,
    tools/call. Tool call number `break_call` waits for `release`, then its POST raises httpx2.ConnectError."""

    def __init__(self, *, break_call: int | None = None):
        self.sessions = 0
        self.tool_calls = 0
        self.break_call = break_call
        self.reached = asyncio.Event()
        self.release = asyncio.Event()

    def _rpc(self, id_, result) -> httpx2.Response:
        return httpx2.Response(200, json={"jsonrpc": "2.0", "id": id_, "result": result},
                               headers={"mcp-session-id": f"s{self.sessions}"})

    async def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if request.method == "GET":
            return httpx2.Response(405)
        if request.method == "DELETE":
            return httpx2.Response(200)
        body = json.loads(request.content)
        method = body.get("method")
        if method == "server/discover":
            return httpx2.Response(400, text="Bad Request")
        if method == "initialize":
            self.sessions += 1
            return self._rpc(body["id"], {"protocolVersion": body["params"]["protocolVersion"],
                                          "capabilities": {"tools": {}}, "serverInfo": {"name": "bg", "version": "1"}})
        if method and method.startswith("notifications/"):
            return httpx2.Response(202)
        if method == "tools/list":  # the client lists tools before its first call, to validate results
            return self._rpc(body["id"], {"tools": [{"name": n, "inputSchema": {"type": "object"}}
                                                    for n in ("get_account_state", "list_strategies")]})
        if method == "tools/call":
            self.tool_calls += 1
            n = self.tool_calls
            if n == self.break_call:
                self.reached.set()
                await self.release.wait()
                raise httpx2.ConnectError("simulated network blip", request=request)
            return self._rpc(body["id"], {"content": [{"type": "text", "text": json.dumps({"n": n})}],
                                          "structuredContent": {"n": n}, "isError": False})
        return httpx2.Response(404)


class HeldTokenEndpoint:
    """BattleGrid's discovery and token endpoints (tests.platform.test_refresh.Platform); the token endpoint waits for
    `release` before it answers, so a test can queue calls behind a refresh."""

    def __init__(self, platform: Platform):
        self.platform = platform
        self.reached = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, request: httpx2.Request) -> httpx2.Response:
        if str(request.url).endswith("/token"):
            self.reached.set()
            await self.release.wait()
        return self.platform(request)


def opener(upstream: Upstream, auth: httpx2.Auth | None = None):
    async def open_session():
        http = httpx2.AsyncClient(auth=auth, transport=httpx2.MockTransport(upstream), follow_redirects=True, timeout=90)
        client = Client(streamable_http_client(URL, http_client=http))
        await client.__aenter__()
        return client

    return open_session


async def _wait_until(predicate, timeout: float = 2.0) -> None:
    async def poll():
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(poll(), timeout)


async def test_a_call_queued_behind_stop_is_failed_not_hung():
    fake = _BlockingFake()
    gateway = gateway_for(fake)
    await gateway.start()

    call_a = asyncio.create_task(gateway.call("get_account_state", {}))
    await asyncio.wait_for(fake.started.wait(), 2)  # call A is now in flight inside the worker

    stop_task = asyncio.create_task(gateway.stop())
    await _wait_until(lambda: gateway._queue.qsize() >= 1)  # stop() has queued _STOP

    with pytest.raises(PlatformError) as exc_info:
        await asyncio.wait_for(gateway.call("preview_strategy_report", {}), 2)
    assert exc_info.value.kind is Kind.TRANSPORT

    fake.release.set()
    assert await asyncio.wait_for(call_a, 2) == {"tool": "get_account_state"}
    await asyncio.wait_for(stop_task, 2)


async def test_a_worker_that_dies_answers_its_call_and_a_new_worker_serves_the_queued_one():
    fake = _BlockingFake(first_raises=_WorkerDied("simulated crash"))
    restarts = []
    gateway = gateway_for(fake, on_restart=lambda n, error: restarts.append((n, error)))
    await gateway.start()

    call_a = asyncio.create_task(gateway.call("get_account_state", {}))
    await asyncio.wait_for(fake.started.wait(), 2)  # call A is now in flight inside the worker

    call_b = asyncio.create_task(gateway.call("preview_strategy_report", {}))
    await _wait_until(lambda: gateway._queue.qsize() >= 1)  # call B is queued, not yet dequeued

    fake.release.set()  # call A's handler raises _WorkerDied: the worker dies

    with pytest.raises(PlatformError) as exc_info:
        await asyncio.wait_for(call_a, 2)
    assert exc_info.value.kind is Kind.TRANSPORT and "simulated crash" in exc_info.value.message
    assert await asyncio.wait_for(call_b, 2) == {"tool": "preview_strategy_report"}
    await asyncio.wait_for(gateway.stop(), 2)
    assert restarts == [(1, "TRANSPORT: _WorkerDied: simulated crash")]


async def test_a_connection_error_on_an_open_session_answers_the_caller_and_a_new_session_serves_the_queue(
        settings, storage, bucket):
    upstream = Upstream(break_call=2)
    restarts = []
    gateway = gateway_for(PlatformClient(settings, storage, bucket, session_factory=opener(upstream)),
                          on_restart=lambda n, error: restarts.append((n, error)))
    await gateway.start()
    try:
        assert await asyncio.wait_for(gateway.call("get_account_state", {}), 5) == {"n": 1}

        broken = asyncio.create_task(gateway.call("get_account_state", {}))
        await asyncio.wait_for(upstream.reached.wait(), 5)  # call 2's POST is in flight
        queued = asyncio.create_task(gateway.call("list_strategies", {}))
        await _wait_until(lambda: gateway._queue.qsize() >= 1)  # call 3 waits behind it
        upstream.release.set()  # call 2's POST raises ConnectError inside the SDK's transport task group

        with pytest.raises(PlatformError) as exc_info:
            await asyncio.wait_for(broken, 5)
        assert exc_info.value.kind is Kind.TRANSPORT and "ConnectError: simulated network blip" in exc_info.value.message
        assert await asyncio.wait_for(queued, 5) == {"n": 3}
        assert await asyncio.wait_for(gateway.call("get_account_state", {}), 5) == {"n": 4}
    finally:
        await asyncio.wait_for(gateway.stop(), 5)
    assert upstream.sessions == 2
    assert restarts == [(1, "TRANSPORT: ConnectError: simulated network blip")]


async def test_a_refused_refresh_on_an_open_session_is_a_typed_auth_error_and_a_login_brings_the_gateway_back(
        tmp_path, settings, bucket):
    clock = Clock(10_000.0)
    storage = await seeded(tmp_path, clock, age=60)  # fresh tokens a1/r1, as `auth login` leaves them
    token_endpoint = HeldTokenEndpoint(Platform(token_status=400))  # BattleGrid refuses the refresh: invalid_grant
    refresher = TokenRefresher(storage, URL, clock=clock, transport=httpx2.MockTransport(token_endpoint))
    upstream = Upstream()
    restarts = []
    gateway = gateway_for(PlatformClient(settings, storage, bucket,
                                         session_factory=opener(upstream, auth=StoredTokenAuth(refresher))),
                          on_restart=lambda n, error: restarts.append((n, error)))
    await gateway.start()
    try:
        assert await asyncio.wait_for(gateway.call("get_account_state", {}), 5) == {"n": 1}

        clock.t += 4000  # the access token is past its lifetime: the next request refreshes inside its auth flow
        broken = asyncio.create_task(gateway.call("get_account_state", {}))
        await asyncio.wait_for(token_endpoint.reached.wait(), 5)  # call 2 is refreshing
        queued = asyncio.create_task(gateway.call("list_strategies", {}))
        await _wait_until(lambda: gateway._queue.qsize() >= 1)  # call 3 waits behind it
        token_endpoint.release.set()

        with pytest.raises(PlatformError) as exc_info:
            await asyncio.wait_for(broken, 5)
        assert exc_info.value.kind is Kind.AUTH and "invalid_grant" in exc_info.value.message
        assert "auth login" in exc_info.value.message
        with pytest.raises(PlatformError) as exc_info:  # served by the next worker: still refused, typed, not hung
            await asyncio.wait_for(queued, 5)
        assert exc_info.value.kind is Kind.AUTH and "auth login" in exc_info.value.message

        # The user runs `auth login`: new tokens land in the shared token file. No restart of the service is needed.
        await storage.set_tokens(OAuthToken(access_token="a9", token_type="Bearer", expires_in=3600,
                                            refresh_token="r9", scope="mcp:read"))
        assert await asyncio.wait_for(gateway.call("get_account_state", {}), 5) == {"n": 2}
    finally:
        await asyncio.wait_for(gateway.stop(), 5)
    # Three refused grants, never a loop: call 2's; the DELETE that closing the broken session sends, whose auth flow
    # refreshes the expired token first (the refresh task outlives the cancelled DELETE, by design); call 3's.
    assert len(token_endpoint.platform.grants) == 3
    assert [n for n, _ in restarts] == [1] and restarts[0][1].startswith("AUTH: token refresh refused")


async def test_restarts_back_off_while_they_keep_failing_and_reset_after_a_call_succeeds():
    fake = _ScriptedFake([_WorkerDied("1"), _WorkerDied("2"), _WorkerDied("3"), _WorkerDied("4"), {"ok": 1},
                          _WorkerDied("5"), {"ok": 2}])
    pauses: list[float] = []

    async def record_pause(seconds: float) -> None:
        pauses.append(seconds)

    gateway = PlatformGateway(fake, restart_delay=2.0, max_restart_delay=6.0, sleep=record_pause)
    await gateway.start()
    try:
        for _ in range(4):
            with pytest.raises(PlatformError):
                await asyncio.wait_for(gateway.call("get_account_state", {}), 2)
        assert await asyncio.wait_for(gateway.call("get_account_state", {}), 2) == {"ok": 1}
        with pytest.raises(PlatformError):
            await asyncio.wait_for(gateway.call("get_account_state", {}), 2)
        assert await asyncio.wait_for(gateway.call("get_account_state", {}), 2) == {"ok": 2}
    finally:
        await asyncio.wait_for(gateway.stop(), 2)
    assert pauses == [2.0, 4.0, 6.0, 6.0, 2.0]
    assert gateway.restarts == 5


async def test_stop_during_a_restart_pause_returns_at_once_and_fails_the_queue():
    fake = _ScriptedFake([_WorkerDied("gone")])
    gateway = PlatformGateway(fake, restart_delay=60.0)  # a real 60 s pause, cut short by stop()
    await gateway.start()
    with pytest.raises(PlatformError):
        await asyncio.wait_for(gateway.call("get_account_state", {}), 2)
    await _wait_until(lambda: gateway.restarts == 1)
    queued = asyncio.create_task(gateway.call("list_strategies", {}))  # waits for a worker that is 60 s away
    await _wait_until(lambda: gateway._queue.qsize() >= 1)
    await asyncio.wait_for(gateway.stop(), 2)
    with pytest.raises(PlatformError) as exc_info:
        await asyncio.wait_for(queued, 2)
    assert exc_info.value.kind is Kind.TRANSPORT and "stopped before serving" in exc_info.value.message
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/mcp tests/audit -q` → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/mcp/gateway.py
"""One worker task owns the upstream BattleGrid session; request handlers queue calls to it.

The MCP SDK's client session must be opened and closed in the same task. Handlers run in their own tasks, so they
never touch the session directly. Calls are served one at a time, which also keeps a burst of questions from Hermes
inside the shared rate limit.

Restarts. The SDK sends each request's POST from a task group hosted by the task that opened the session. When one of
those POSTs raises (a connection error, the 90 s read timeout, a reset after the PC slept, or a refused token refresh
inside the HTTP auth flow), anyio cancels the host task: the worker. So a supervisor task, which never enters an SDK
scope, runs the worker:

- The call in flight when the worker ends is answered at once with a typed PlatformError. The worker first closes the
  client in its own task, because closing is where the SDK re-raises the failure; the caller gets that failure's kind
  and message (a refused refresh stays AUTH and names `auth login`), or TRANSPORT pointing at the manager logs when
  nothing was recorded.
- Calls still queued stay queued. While the gateway accepts calls, the supervisor starts a new worker after a pause
  of 2 s that doubles, up to 60 s, each time a worker ends again before any call has succeeded, and goes back to 2 s
  once a call succeeds. A new worker opens a session only when its first call arrives, so a refused refresh is retried
  at the pace of incoming calls, never in a loop against BattleGrid's token endpoint.
- Each restart is reported to the optional `on_restart(restarts, error)` hook, with error text that carries no token;
  the HTTP app records it in the ledger as `gateway.restart`.

Shutdown. stop() closes intake before anything else, lets the worker finish the call in flight, cuts a restart pause
short, and fails every call still queued with a typed error, so no caller waits forever.
"""
from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable

from manager.platform.client import map_exception
from manager.platform.errors import Kind, PlatformError

log = logging.getLogger(__name__)
_STOP = object()
_BEARER = re.compile(r"(?i)\bbearer\s+\S+")
RestartHook = Callable[[int, str], None]


def _settle(fut: asyncio.Future, result: object = None, error: BaseException | None = None) -> None:
    if fut.done():  # the caller may already have gone away
        return
    if error is not None:
        fut.set_exception(error)
    else:
        fut.set_result(result)


def session_ended_error(cause: BaseException | None) -> PlatformError:
    """The typed error for the call that was in flight when the worker ended."""
    if cause is None:
        return PlatformError(Kind.TRANSPORT, "the upstream BattleGrid session ended during this call and no error was "
                                             "recorded; see the manager logs (docker compose logs mcp). The next call "
                                             "opens a new session.")
    return map_exception(cause)


class PlatformGateway:
    def __init__(self, client, *, on_restart: RestartHook | None = None, restart_delay: float = 2.0,
                 max_restart_delay: float = 60.0, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._client = client
        self.on_restart = on_restart
        self._first_delay, self._max_delay, self._sleep = restart_delay, max_restart_delay, sleep
        self._delay = restart_delay
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None  # the supervisor
        self._inflight: asyncio.Future | None = None
        self._pause: asyncio.Future | None = None
        self._ended = ""
        self._accepting = False
        self.restarts = 0

    async def start(self) -> None:
        self._accepting = True
        self._task = asyncio.create_task(self._supervise(), name="platform-gateway")

    async def _supervise(self) -> None:
        worker: asyncio.Task | None = None
        try:
            while True:
                worker = asyncio.create_task(self._serve(), name="platform-gateway-session")
                await asyncio.wait({worker})  # returns when the worker ends; its cancellation stays in the worker
                if not worker.cancelled():
                    worker.exception()  # retrieve it: the worker already reported it to its caller and the log
                if not self._accepting:
                    return
                self.restarts += 1
                delay, self._delay = self._delay, min(self._delay * 2, self._max_delay)
                log.warning("platform gateway: the session worker ended (%s); restart %d in %g s",
                            self._ended, self.restarts, delay)
                self._report_restart()
                self._pause = asyncio.ensure_future(self._sleep(delay))
                await asyncio.wait({self._pause})  # stop() cancels the pause
                self._pause = None
                if not self._accepting:
                    return
        finally:
            # Close intake before draining, so a call() racing this shutdown either queued strictly before (and is
            # drained below) or sees _accepting False and never queues at all.
            self._accepting = False
            if self._pause is not None:
                self._pause.cancel()
            if worker is not None and not worker.done():  # only when the supervisor itself was cancelled
                worker.cancel()
                await asyncio.wait({worker})
            self._fail_pending()

    def _report_restart(self) -> None:
        if self.on_restart is None:
            return
        try:
            self.on_restart(self.restarts, self._ended)
        except Exception:  # noqa: BLE001 - a failing hook must never stop the gateway
            log.exception("platform gateway: the restart hook failed")

    async def _serve(self) -> None:
        ended_by: BaseException | None = None
        try:
            while True:
                item = await self._queue.get()
                if item is _STOP:
                    return
                tool, args, fut = item
                self._inflight = fut
                try:
                    result = await self._client.call(tool, args)
                except PlatformError as e:
                    _settle(fut, error=e)
                except Exception as e:  # noqa: BLE001 - every failure reaches the caller as a typed error
                    _settle(fut, error=PlatformError(Kind.TRANSPORT, f"{type(e).__name__}: {e}"))
                else:
                    self._delay = self._first_delay  # a served call: the next restart pause starts short again
                    _settle(fut, result)
                self._inflight = None
        except BaseException as e:
            ended_by = e
            raise
        finally:
            fut, self._inflight = self._inflight, None
            closed_with: BaseException | None = None
            try:
                # Leaves the session's SDK scopes in the task that entered them. After a failed POST, closing
                # re-raises that failure, which is the only place it can be recovered.
                closed_with = await self._close_client()
            finally:
                if ended_by is not None:  # anything but stop()
                    cause = closed_with
                    if cause is None and not isinstance(ended_by, asyncio.CancelledError):
                        cause = ended_by
                    error = session_ended_error(cause)
                    self._ended = _BEARER.sub("Bearer [redacted]", f"{error.kind.value}: {error.message}")[:500]
                    if fut is not None:
                        _settle(fut, error=error)

    async def _close_client(self) -> BaseException | None:
        aclose = getattr(self._client, "aclose", None)
        if aclose is None:
            return None
        closed = await aclose()
        return closed if isinstance(closed, BaseException) else None

    def _fail_pending(self) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            if item is _STOP:
                continue
            _, _, fut = item
            _settle(fut, error=PlatformError(Kind.TRANSPORT, "the platform gateway stopped before serving this call"))

    async def call(self, tool: str, args: dict) -> dict:
        if not self._accepting or self._task is None or self._task.done():
            raise PlatformError(Kind.TRANSPORT, "the platform gateway is not running")
        fut = asyncio.get_running_loop().create_future()
        await self._queue.put((tool, args, fut))
        return await fut

    async def stop(self) -> None:
        # Set synchronously, before any await, so no concurrent call() can pass its own check and then queue behind
        # the _STOP this method is about to send.
        self._accepting = False
        if self._pause is not None:
            self._pause.cancel()  # a supervisor waiting to restart its worker returns now, not after the pause
        if self._task and not self._task.done():
            await self._queue.put(_STOP)
            await self._task
```

```python
# manager/audit/views.py
"""Read-only views of the manager's stored state, shared by the REST API and the MCP native tools."""
from __future__ import annotations

from sqlalchemy.orm import Session

from manager.audit.ledger import get_state, query


def platform_changes_view(s: Session, limit: int = 20) -> dict:
    surface = get_state(s, "surface", {})
    tools = surface.pop("tools", None)
    surface["tool_count"] = None if tools is None else len(tools)
    return {"surface": surface,
            "writes_blocked": get_state(s, "writes_blocked", {"blocked": False}),
            "drift": [{"at": e.at.isoformat(), **e.payload} for e in query(s, kind="contract.drift", limit=limit)],
            "pack": [{"at": e.at.isoformat(), **e.payload} for e in query(s, kind="pack.refresh_recommended", limit=5)]}


def ledger_view(s: Session, kind: str | None = None, limit: int = 100) -> list[dict]:
    return [{"id": e.id, "at": e.at.isoformat(), "kind": e.kind, "payload": e.payload}
            for e in query(s, kind=kind, limit=limit)]
```

In `manager/api/app.py`, make the two endpoints delegate (import `platform_changes_view`, `ledger_view` from `manager.audit.views`):

```python
    @app.get("/api/platform/changes", dependencies=[Depends(auth)])
    def platform_changes(limit: int = Query(default=20, ge=1, le=200)):
        """What the platform watch has seen: the current surface, whether writes are blocked, and every drift."""
        with ctx.session_factory() as s:
            return platform_changes_view(s, limit)

    @app.get("/api/ledger", dependencies=[Depends(auth)])
    def ledger(kind: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=1000)):
        with ctx.session_factory() as s:
            return ledger_view(s, kind, limit)
```

```python
# manager/mcp/native.py
"""Tools the manager answers itself, from its own database. None of them calls BattleGrid."""
from __future__ import annotations

from datetime import datetime

import mcp.types as t
from sqlalchemy.orm import Session

from manager.audit.views import ledger_view, platform_changes_view
from manager.inventory.report import NO_SNAPSHOT, STALE_AFTER_S, as_utc, render_inventory_report, snapshot_age
from manager.inventory.snapshot import latest

_RO = t.ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

NATIVE_TOOLS: list[t.Tool] = [
    t.Tool(name="manager_fleet_report",
           description="The latest inventory snapshot as a markdown report: account, agents with Radar coins, the Radar "
                       "fleet with each coin's block, open positions, and any UNDETERMINED read. No platform call. "
                       "`ageLine` comes first: the snapshot's age, computed by the manager in UTC at the moment it "
                       "serves the report. Quote it as given; do not work out an age yourself. `freshness` is fresh, "
                       "stale (older than 10 minutes: the numbers are not current) or none.",
           input_schema={"type": "object", "properties": {}, "additionalProperties": False}, annotations=_RO),
    t.Tool(name="manager_platform_changes",
           description="What the platform watch has seen: contract version, build, tool count, whether writes are blocked "
                       "pending acknowledgement, every recorded drift, and skill-pack refresh recommendations.",
           input_schema={"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
                         "additionalProperties": False}, annotations=_RO),
    t.Tool(name="manager_ledger",
           description="The manager's append-only audit ledger, newest first, optionally filtered by event kind "
                       "(e.g. snapshot.taken, panel.pulled, panel.fallback, contract.drift, safe.enter, gateway.restart).",
           input_schema={"type": "object", "properties": {"kind": {"type": "string"},
                                                           "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
                         "additionalProperties": False}, annotations=_RO),
]
NATIVE_NAMES = {tool.name for tool in NATIVE_TOOLS}


class ArgumentError(ValueError):
    """A native tool argument the manager cannot use. The server answers it as a VALIDATION_ERROR result."""


def _limit(args: dict, default: int, maximum: int) -> int:
    raw = args.get("limit")
    if raw is None:
        return default
    if isinstance(raw, bool) or not isinstance(raw, (int, str)) or not str(raw).strip().isdigit() \
            or not 1 <= int(raw) <= maximum:
        raise ArgumentError(f"limit must be a whole number from 1 to {maximum}; got {raw!r}")
    return int(raw)


def _kind(args: dict) -> str | None:
    raw = args.get("kind")
    if raw is None or isinstance(raw, str):
        return raw or None
    raise ArgumentError(f"kind must be an event kind such as snapshot.taken; got {raw!r}")


def _duration(seconds: int) -> str:
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    parts = [f"{days} d"] if days else []
    if days or hours:
        parts.append(f"{hours} h")
    if days or hours or minutes:
        parts.append(f"{minutes} min")
    return " ".join([*parts, f"{secs} s"])


def _iso_z(moment: datetime) -> str:
    return f"{as_utc(moment):%Y-%m-%dT%H:%M:%S}Z"


def _utc_label(moment: datetime) -> str:
    return f"{as_utc(moment):%Y-%m-%d %H:%M:%S} UTC"


def fleet_report(s: Session, now: datetime) -> dict:
    """The age comes first and is worked out here, from the same snapshot row the markdown renders: the model asking
    has no clock (Hermes gives it only the user's local date)."""
    snap = latest(s)
    if snap is None:
        line = f"Data age: no snapshot has been taken yet; this report was served at {_utc_label(now)}."
        return {"ageLine": line, "snapshotAgeSeconds": None, "freshness": "none", "snapshotId": None,
                "snapshotTakenAt": None, "servedAt": _iso_z(now), "markdown": f"{line}\n\n{NO_SNAPSHOT}"}
    taken, age = snapshot_age(snap.taken_at, now)
    fresh = age <= STALE_AFTER_S
    verdict = ("FRESH: the inventory runs every 5 minutes." if fresh else
               "STALE: the inventory runs every 5 minutes and has not written a newer snapshot; "
               "these numbers are not current.")
    line = (f"Data age: snapshot {snap.id} was taken {_utc_label(taken)}, {_duration(age)} before this report was "
            f"served at {_utc_label(now)}. {verdict}")
    return {"ageLine": line, "snapshotAgeSeconds": age, "freshness": "fresh" if fresh else "stale",
            "snapshotId": snap.id, "snapshotTakenAt": _iso_z(taken), "servedAt": _iso_z(now),
            "markdown": f"{line}\n\n{render_inventory_report(s, snap)}"}


def call_native(name: str, args: dict, session_factory, now: datetime) -> dict:
    """Arguments are checked before the database is touched; a bad one raises ArgumentError."""
    if name == "manager_fleet_report":
        with session_factory() as s:
            return fleet_report(s, now)
    if name == "manager_platform_changes":
        limit = _limit(args, 20, 200)
        with session_factory() as s:
            return platform_changes_view(s, limit)
    if name == "manager_ledger":
        kind, limit = _kind(args), _limit(args, 50, 500)
        with session_factory() as s:
            return {"events": ledger_view(s, kind, limit)}
    raise KeyError(name)
```

```python
# manager/mcp/server.py
"""The MCP server Hermes talks to: BattleGrid's read-only tools under their own names, plus native tools."""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime

import mcp.types as t
from mcp.server.lowlevel import Server

from manager.audit.ledger import get_state
from manager.mcp.native import NATIVE_NAMES, NATIVE_TOOLS, ArgumentError, call_native
from manager.platform.errors import PlatformError
from manager.proxy.policy import decide_exposure

SUFFIX = " (Served by battlegrid-manager, read-only.)"


def _result(body, is_error: bool = False) -> t.CallToolResult:
    # The text always carries the exact payload; structuredContent must be a JSON object, so only dicts go there.
    # Hermes forwards the text to the model, so it carries characters, not \u escapes.
    structured = body if (not is_error and isinstance(body, dict)) else None
    return t.CallToolResult(content=[t.TextContent(type="text", text=json.dumps(body, ensure_ascii=False))],
                            structured_content=structured, is_error=is_error)


def build_server(gateway, session_factory, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> Server:
    def exposure():
        with session_factory() as s:
            stored = get_state(s, "surface_tools", {})
        return decide_exposure(stored.get("tools") or [])

    async def on_list_tools(ctx, params):
        proxied = [t.Tool(name=d["name"], description=(d.get("description") or "") + SUFFIX,
                          input_schema=d.get("inputSchema") or {"type": "object"},
                          annotations=t.ToolAnnotations(read_only_hint=True,
                                                        destructive_hint=(d.get("annotations") or {}).get("destructiveHint")))
                   for d in exposure().exposed]
        return t.ListToolsResult(tools=NATIVE_TOOLS + proxied)

    async def on_call_tool(ctx, params):
        name, args = params.name, dict(params.arguments or {})
        if name in NATIVE_NAMES:
            try:
                return _result(call_native(name, args, session_factory, now=clock()))
            except ArgumentError as e:
                return _result({"code": "VALIDATION_ERROR", "tool": name, "message": str(e)}, is_error=True)
        exp = exposure()
        if name not in {d["name"] for d in exp.exposed}:
            return _result({"code": "NOT_EXPOSED", "tool": name,
                            "reason": exp.withheld.get(name, "unknown tool"),
                            "message": "The manager exposes only BattleGrid tools that are reviewed and declared read-only."},
                           is_error=True)
        try:
            return _result(await gateway.call(name, args))
        except PlatformError as e:
            return _result({"code": e.code or e.kind.value, "message": e.message, "retryAfter": e.retry_after},
                           is_error=True)

    return Server("battlegrid-manager", version="0.1.0",
                  instructions="BattleGrid account manager. Read-only. Numbers are the platform's own; "
                               "an UNDETERMINED section means it could not be read, not that it is empty.",
                  on_list_tools=on_list_tools, on_call_tool=on_call_tool)
```

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → all pass.
- [ ] **Step 5: Commit** `"MCP server core: BattleGrid read-only tools by their own names, native fleet/changes/ledger tools, one gateway task"`.

---

### Task 10: Tokens refresh without a human, one process at a time

> Added 2026-09-14 during execution. It runs after Task 4 and before Task 5; it is numbered 10 so existing task references stay valid.
> Why: every service stopped reading BattleGrid at 13:13 UTC on 2026-09-14 and stayed stopped (snapshots 15 to 54, every read `AUTH: No callback handler provided for authorization code grant`). The MCP SDK's `OAuthClientProvider` (mcp 2.1.1, `oauth2.py`) loads stored tokens without an expiry, so it never refreshes them, and it answers the resulting 401 with the interactive authorization-code flow, which a service cannot finish. Measured the same day inside the api container: access tokens last 3600 s and are then refused; a 4.3-hour-old refresh token still refreshed; **every refresh returns a new refresh token**; token endpoint `https://mcp.battlegrid.trade/token`; client authentication `none`; resource `https://mcp.battlegrid.trade/`.

**Files:** Create `manager/platform/refresh.py`, `tests/platform/test_refresh.py`, `scripts/check_token_refresh.py`; Modify `manager/platform/tokens.py`, `manager/platform/client.py` (`__init__`, `_open_session`), `tests/platform/test_tokens.py`, `tests/platform/test_client.py`.

**Interfaces:**
- Produces: `FileTokenStorage(path: str, clock=time.time)` with property `path -> Path` and `async get_tokens_saved_at() -> float | None` (the recorded write time, else the file's mtime for files written before the field existed); `exclusive(lock_path: Path)` async context manager; `TokenRefresher(storage, server_url, *, margin=300.0, clock=time.time, transport=None)` with `async access_token() -> str` and `async refresh(rejected: str | None) -> str`; `StoredTokenAuth(refresher)` (an `httpx2.Auth`). `PlatformClient` background sessions authenticate with `StoredTokenAuth`; `PlatformClient.oauth_provider(...)` remains for `auth login` only.
- Errors: a refused refresh (HTTP 400/401/403) is `PlatformError(Kind.AUTH)` whose message names `python -m manager auth login` and leaves the stored tokens untouched; an unreachable platform is `TRANSPORT`; a 5xx is `HTTP`.

- [ ] **Step 1: Failing tests**

```python
# tests/platform/test_refresh.py
import asyncio
import json
import os
import time
from urllib.parse import parse_qs

import httpx2
import pytest
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from manager.platform.errors import Kind, PlatformError
from manager.platform.refresh import StoredTokenAuth, TokenRefresher
from manager.platform.tokens import FileTokenStorage

MCP = "https://mcp.battlegrid.trade/mcp"
PRM = {"resource": "https://mcp.battlegrid.trade/", "authorization_servers": ["https://mcp.battlegrid.trade/"]}
ASM = {"issuer": "https://mcp.battlegrid.trade/", "token_endpoint": "https://mcp.battlegrid.trade/token",
       "authorization_endpoint": "https://mcp.battlegrid.trade/authorize",
       "grant_types_supported": ["authorization_code", "refresh_token"],
       "token_endpoint_auth_methods_supported": ["client_secret_post", "none"]}


class Clock:
    def __init__(self, t: float):
        self.t = t

    def __call__(self) -> float:
        return self.t


class Platform:
    """BattleGrid's discovery and token endpoints as measured on 2026-09-14, rotating refresh tokens."""

    def __init__(self, token_status: int = 200):
        self.grants, self.token_status, self.issued = [], token_status, 1

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        url = str(request.url)
        if url == "https://mcp.battlegrid.trade/.well-known/oauth-protected-resource":
            return httpx2.Response(200, json=PRM)
        if url == "https://mcp.battlegrid.trade/.well-known/oauth-authorization-server":
            return httpx2.Response(200, json=ASM)
        if url == "https://mcp.battlegrid.trade/token":
            self.grants.append(parse_qs(request.content.decode()))
            if self.token_status != 200:
                return httpx2.Response(self.token_status, json={"error": "invalid_grant",
                                                                "error_description": "refresh token revoked"})
            self.issued += 1
            return httpx2.Response(200, json={"access_token": f"a{self.issued}", "token_type": "Bearer",
                                              "expires_in": 3600, "refresh_token": f"r{self.issued}", "scope": "mcp:read"})
        return httpx2.Response(404)


async def seeded(tmp_path, clock: Clock, age: float) -> FileTokenStorage:
    """Tokens a1/r1 written `age` seconds before clock.t, as `auth login` leaves them."""
    storage = FileTokenStorage(str(tmp_path / "battlegrid.json"), clock=clock)
    now, clock.t = clock.t, clock.t - age
    await storage.set_client_info(OAuthClientInformationFull(
        client_id="cid", redirect_uris=["http://127.0.0.1:8791/callback"], token_endpoint_auth_method="none",
        issuer="https://mcp.battlegrid.trade/"))
    await storage.set_tokens(OAuthToken(access_token="a1", token_type="Bearer", expires_in=3600,
                                        refresh_token="r1", scope="mcp:read"))
    clock.t = now
    return storage


async def test_a_fresh_token_is_used_without_any_request(tmp_path):
    clock = Clock(10_000.0)
    storage = await seeded(tmp_path, clock, age=60)
    platform = Platform()
    refresher = TokenRefresher(storage, MCP, clock=clock, transport=httpx2.MockTransport(platform))
    assert await refresher.access_token() == "a1" and platform.grants == []


async def test_an_expiring_token_is_refreshed_once_with_the_stored_refresh_token(tmp_path):
    clock = Clock(10_000.0)
    storage = await seeded(tmp_path, clock, age=3400)  # inside the 300 s margin before 3600 s
    platform = Platform()
    refresher = TokenRefresher(storage, MCP, clock=clock, transport=httpx2.MockTransport(platform))
    assert await refresher.access_token() == "a2"
    assert await refresher.access_token() == "a2"  # the refreshed token is fresh: no second grant
    assert platform.grants == [{"grant_type": ["refresh_token"], "refresh_token": ["r1"], "client_id": ["cid"],
                                "resource": ["https://mcp.battlegrid.trade/"]}]
    stored = await storage.get_tokens()
    assert (stored.access_token, stored.refresh_token, stored.scope) == ("a2", "r2", "mcp:read")
    assert await storage.get_tokens_saved_at() == clock.t


async def test_a_rejected_token_that_another_process_already_replaced_is_adopted_without_a_grant(tmp_path):
    clock = Clock(10_000.0)
    storage = await seeded(tmp_path, clock, age=60)
    platform = Platform()
    refresher = TokenRefresher(storage, MCP, clock=clock, transport=httpx2.MockTransport(platform))
    assert await refresher.refresh(rejected="a0") == "a1" and platform.grants == []


async def test_concurrent_refreshes_of_one_rejected_token_make_exactly_one_grant(tmp_path):
    clock = Clock(10_000.0)
    storage = await seeded(tmp_path, clock, age=60)
    platform = Platform()

    async def slow(request):
        await asyncio.sleep(0.05)
        return platform(request)

    one, two = (TokenRefresher(FileTokenStorage(str(storage.path), clock=clock), MCP, clock=clock,
                               transport=httpx2.MockTransport(slow)) for _ in range(2))
    assert await asyncio.gather(one.refresh(rejected="a1"), two.refresh(rejected="a1")) == ["a2", "a2"]
    assert len(platform.grants) == 1


async def test_a_refused_refresh_is_an_auth_error_that_names_the_login_and_keeps_the_tokens(tmp_path):
    clock = Clock(10_000.0)
    storage = await seeded(tmp_path, clock, age=4000)
    refresher = TokenRefresher(storage, MCP, clock=clock, transport=httpx2.MockTransport(Platform(token_status=400)))
    with pytest.raises(PlatformError) as ei:
        await refresher.access_token()
    assert ei.value.kind is Kind.AUTH and "invalid_grant" in ei.value.message and "auth login" in ei.value.message
    assert (await storage.get_tokens()).refresh_token == "r1"


async def test_a_token_file_from_before_saved_at_uses_its_modification_time(tmp_path):
    path = tmp_path / "battlegrid.json"
    path.write_text(json.dumps({
        "tokens": {"access_token": "a1", "token_type": "Bearer", "expires_in": 3600, "refresh_token": "r1",
                   "scope": "mcp:read"},
        "client_info": {"client_id": "cid", "redirect_uris": ["http://127.0.0.1:8791/callback"],
                        "token_endpoint_auth_method": "none"}}), encoding="utf-8")
    old = time.time() - 4000
    os.utime(path, (old, old))
    platform = Platform()
    refresher = TokenRefresher(FileTokenStorage(str(path)), MCP, transport=httpx2.MockTransport(platform))
    assert await refresher.access_token() == "a2" and len(platform.grants) == 1


async def test_stored_token_auth_retries_once_with_a_refreshed_token_after_a_401(tmp_path):
    clock = Clock(10_000.0)
    storage = await seeded(tmp_path, clock, age=60)
    platform = Platform()
    seen = []

    def handler(request):
        if str(request.url) == MCP:
            seen.append(request.headers.get("authorization"))
            return httpx2.Response(401 if request.headers.get("authorization") == "Bearer a1" else 200, json={})
        return platform(request)

    transport = httpx2.MockTransport(handler)
    refresher = TokenRefresher(storage, MCP, clock=clock, transport=transport)
    async with httpx2.AsyncClient(auth=StoredTokenAuth(refresher), transport=transport) as h:
        r = await h.post(MCP, json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert r.status_code == 200 and seen == ["Bearer a1", "Bearer a2"] and len(platform.grants) == 1


async def test_a_cancelled_caller_does_not_lose_a_grant_the_platform_already_made(tmp_path):
    """Added by the task review: the platform rotates before the client finishes reading the response; a
    caller cancelled then must still leave a2/r2 stored, with no second grant."""
    clock = Clock(10_000.0)
    storage = await seeded(tmp_path, clock, age=4000)
    platform = Platform()
    issued = asyncio.Event()

    async def slow(request):
        if str(request.url) == "https://mcp.battlegrid.trade/token":
            response = platform(request)
            issued.set()
            await asyncio.sleep(0.2)
            return response
        return platform(request)

    refresher = TokenRefresher(storage, MCP, clock=clock, transport=httpx2.MockTransport(slow))
    task = asyncio.ensure_future(refresher.access_token())
    await asyncio.wait_for(issued.wait(), timeout=1.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    async def wait_for_rotation() -> None:
        while (lambda t: (t.access_token, t.refresh_token))(await storage.get_tokens()) != ("a2", "r2"):
            await asyncio.sleep(0.01)

    await asyncio.wait_for(wait_for_rotation(), timeout=2.0)
    assert len(platform.grants) == 1


async def test_three_concurrent_refreshes_on_one_refresher_make_exactly_one_grant(tmp_path):
    clock = Clock(10_000.0)
    storage = await seeded(tmp_path, clock, age=60)
    platform = Platform()

    async def slow(request):
        await asyncio.sleep(0.05)
        return platform(request)

    refresher = TokenRefresher(storage, MCP, clock=clock, transport=httpx2.MockTransport(slow))
    results = await asyncio.gather(*(refresher.refresh(rejected="a1") for _ in range(3)))
    assert results == ["a2", "a2", "a2"] and len(platform.grants) == 1
```

In `tests/platform/test_tokens.py`, the round-trip test's key assertion becomes `assert set(raw) == {"tokens", "client_info", "tokens_saved_at"}`, and add:

```python
async def test_the_write_time_is_recorded_with_the_tokens(tmp_path):
    s = FileTokenStorage(str(tmp_path / "c.json"), clock=lambda: 1234.5)
    assert await s.get_tokens_saved_at() is None
    await s.set_tokens(OAuthToken(access_token="a", token_type="Bearer", expires_in=3600))
    assert await s.get_tokens_saved_at() == 1234.5
```

In `tests/platform/test_client.py` add:

```python
async def test_background_sessions_authenticate_from_the_token_file_not_the_interactive_provider(
        settings, storage, bucket, monkeypatch):
    import manager.platform.client as client_module
    from mcp.shared.auth import OAuthToken

    from manager.platform.refresh import StoredTokenAuth

    await storage.set_tokens(OAuthToken(access_token="a", token_type="Bearer", expires_in=3600, refresh_token="r"))
    seen = {}

    class Http:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        async def aclose(self):
            return None

    class Session:
        def __init__(self, transport):
            self.transport = transport

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

    monkeypatch.setattr(client_module.httpx2, "AsyncClient", Http)
    monkeypatch.setattr(client_module, "Client", Session)
    monkeypatch.setattr(client_module, "streamable_http_client", lambda url, http_client: ("transport", url))
    session = await PlatformClient(settings, storage, bucket)._open_session()
    assert isinstance(seen["auth"], StoredTokenAuth) and session.transport == ("transport", settings.bg_mcp_url)
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/platform -q` → the new tests FAIL (no `manager.platform.refresh`, no `get_tokens_saved_at`).

- [ ] **Step 3: Implement**

In `manager/platform/tokens.py`: add `import time`, `from collections.abc import Callable`; the constructor becomes `def __init__(self, path: str, clock: Callable[[], float] = time.time)` storing `self._clock = clock`; add

```python
    @property
    def path(self) -> Path:
        return self._path

    async def get_tokens_saved_at(self) -> float | None:
        """When the tokens were written. Files from before this field existed fall back to their mtime."""
        d = self._read()
        if not d.get("tokens"):
            return None
        at = d.get("tokens_saved_at")
        return float(at) if isinstance(at, (int, float)) else self._path.stat().st_mtime
```

and `set_tokens` records the time:

```python
    async def set_tokens(self, tokens: OAuthToken) -> None:
        d = self._read()
        d["tokens"] = tokens.model_dump(mode="json")
        d["tokens_saved_at"] = self._clock()
        self._write(d)
```

```python
# manager/platform/refresh.py
"""Keep the shared OAuth tokens fresh without a human, one process at a time.

Measured 2026-09-14 against BattleGrid: access tokens last 3600 s and are then refused with HTTP 401; a
4.3-hour-old refresh token still refreshed; every refresh returns a new refresh token (rotation); the
client authenticates with no secret.

The MCP SDK's OAuthClientProvider cannot do this for a service: tokens it loads from storage carry no
expiry, so it never refreshes them, and on a 401 it starts the interactive authorization-code flow, which
nobody is there to finish. On 2026-09-14 every service stopped reading at 13:13 UTC that way.

Because refresh tokens rotate, two processes must never refresh with the same one. Refreshes run under an
exclusive lock on a file beside the token file, and the tokens are re-read under that lock first.
"""
from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from pathlib import Path

import httpx2
from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
)
from mcp.shared.auth import OAuthToken

from manager.platform.errors import Kind, PlatformError
from manager.platform.tokens import FileTokenStorage

LOGIN = "run `python -m manager auth login`"
_THREAD_LOCKS: dict[str, threading.Lock] = {}


@contextlib.asynccontextmanager
async def exclusive(lock_path: Path) -> AsyncIterator[None]:
    """Held across processes with fcntl.flock: the services run on Linux and share the token volume.
    Where fcntl does not exist (Windows development), a per-path thread lock keeps the tests meaningful."""
    try:
        import fcntl
    except ImportError:
        lock = _THREAD_LOCKS.setdefault(str(lock_path), threading.Lock())
        await asyncio.to_thread(lock.acquire)
        try:
            yield
        finally:
            lock.release()
        return
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+b") as fh:
        await asyncio.to_thread(fcntl.flock, fh.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _oauth_error(response: httpx2.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    return " ".join(str(body[k]) for k in ("error", "error_description") if body.get(k))


class TokenRefresher:
    def __init__(self, storage: FileTokenStorage, server_url: str, *, margin: float = 300.0,
                 clock: Callable[[], float] = time.time,
                 transport: httpx2.AsyncBaseTransport | None = None) -> None:
        self._storage, self._server_url, self._margin, self._clock = storage, server_url, margin, clock
        self._transport = transport
        self._lock_path = storage.path.with_suffix(".lock")
        self._endpoints: tuple[str, str | None, str | None] | None = None
        self._task: asyncio.Task[str] | None = None

    async def access_token(self) -> str:
        """The stored access token, refreshed first when it is within `margin` seconds of expiry."""
        tokens = await self._stored()
        if not await self._expiring(tokens):
            return tokens.access_token
        return await self.refresh(rejected=None)

    async def refresh(self, rejected: str | None) -> str:
        """Join the one refresh running for this process, starting it if none is. `rejected` is the access
        token the server just refused, if any; a joiner gets the running refresh's result, the newest token.
        Added by the task review: a caller cancelled mid-grant (the SDK cancels in-flight requests when a
        session closes) must not cancel the refresh, or the rotated tokens the server already issued are
        never stored. The task is shielded and releases the lock only after set_tokens or a failure."""
        loop = asyncio.get_running_loop()
        task = self._task
        if task is None or task.done() or task.get_loop() is not loop:
            task = self._task = loop.create_task(self._locked_refresh(rejected))
            task.add_done_callback(self._reap)
        return await asyncio.shield(task)

    @staticmethod
    def _reap(task: asyncio.Task[str]) -> None:
        # Retrieved even when every caller was cancelled first, so asyncio never logs an unretrieved exception.
        if not task.cancelled():
            task.exception()

    async def _locked_refresh(self, rejected: str | None) -> str:
        async with exclusive(self._lock_path):
            tokens = await self._stored()
            if rejected is None and not await self._expiring(tokens):
                return tokens.access_token
            if rejected is not None and tokens.access_token != rejected:
                return tokens.access_token
            new = await self._grant(tokens)
            await self._storage.set_tokens(new)
            return new.access_token

    async def _stored(self) -> OAuthToken:
        tokens = await self._storage.get_tokens()
        if tokens is None or not tokens.access_token:
            raise PlatformError(Kind.AUTH, f"no OAuth session: {LOGIN}")
        return tokens

    async def _expiring(self, tokens: OAuthToken) -> bool:
        if tokens.expires_in is None:
            return False  # no stated lifetime: use it until the server refuses it, then refresh
        saved_at = await self._storage.get_tokens_saved_at()
        return saved_at is None or self._clock() >= saved_at + tokens.expires_in - self._margin

    async def _grant(self, tokens: OAuthToken) -> OAuthToken:
        if not tokens.refresh_token:
            raise PlatformError(Kind.AUTH, f"the stored OAuth session has no refresh token: {LOGIN}")
        client = await self._storage.get_client_info()
        if client is None:
            raise PlatformError(Kind.AUTH, f"no registered OAuth client: {LOGIN}")
        try:
            async with httpx2.AsyncClient(transport=self._transport, timeout=30, follow_redirects=True) as h:
                token_endpoint, resource, issuer = await self._discover(h)
                if client.issuer and issuer and client.issuer.rstrip("/") != issuer.rstrip("/"):
                    raise PlatformError(Kind.AUTH, f"the OAuth client belongs to {client.issuer} but the platform "
                                                   f"now authorizes with {issuer}: {LOGIN}")
                data = {"grant_type": "refresh_token", "refresh_token": tokens.refresh_token,
                        "client_id": client.client_id}
                if resource:
                    data["resource"] = resource
                if client.token_endpoint_auth_method == "client_secret_post" and client.client_secret:
                    data["client_secret"] = client.client_secret
                r = await h.post(token_endpoint, data=data)
        except httpx2.HTTPError as e:
            raise PlatformError(Kind.TRANSPORT, f"token refresh could not reach the platform: {type(e).__name__}: {e}") from e
        if r.status_code in (400, 401, 403):
            raise PlatformError(Kind.AUTH, f"token refresh refused (HTTP {r.status_code} {_oauth_error(r)}): {LOGIN}",
                                status=r.status_code)
        if r.status_code != 200:
            raise PlatformError(Kind.HTTP, f"token refresh HTTP {r.status_code}", status=r.status_code, raw=r.text[:500])
        try:
            new = OAuthToken.model_validate_json(r.content)
        except ValueError as e:
            raise PlatformError(Kind.PARSE, "token refresh response is not a token", raw=r.text[:500]) from e
        if new.scope is None:
            new.scope = tokens.scope
        if new.refresh_token is None:
            new.refresh_token = tokens.refresh_token
        return new

    async def _discover(self, h: httpx2.AsyncClient) -> tuple[str, str | None, str | None]:
        """Token endpoint, protected resource and issuer, found with the SDK's own discovery URL order."""
        if self._endpoints is not None:
            return self._endpoints
        prm: dict = {}
        for url in build_protected_resource_metadata_discovery_urls(None, self._server_url):
            r = await h.get(url)
            if r.status_code == 200:
                prm = r.json()
                break
            if r.status_code >= 500:
                raise PlatformError(Kind.HTTP, f"resource metadata HTTP {r.status_code}", status=r.status_code)
        auth_servers = prm.get("authorization_servers") or [None]
        for url in build_oauth_authorization_server_metadata_discovery_urls(auth_servers[0], self._server_url):
            r = await h.get(url)
            if r.status_code == 200 and r.json().get("token_endpoint"):
                asm = r.json()
                self._endpoints = (asm["token_endpoint"], prm.get("resource"), asm.get("issuer"))
                return self._endpoints
            if r.status_code >= 500:
                raise PlatformError(Kind.HTTP, f"authorization server metadata HTTP {r.status_code}", status=r.status_code)
        raise PlatformError(Kind.AUTH, f"the platform publishes no token endpoint: {LOGIN}")


class StoredTokenAuth(httpx2.Auth):
    """Bearer auth from the shared token file, for background sessions. It never starts an interactive login."""

    requires_request_body = True

    def __init__(self, refresher: TokenRefresher) -> None:
        self._refresher = refresher

    async def async_auth_flow(self, request: httpx2.Request) -> AsyncGenerator[httpx2.Request, httpx2.Response]:
        token = await self._refresher.access_token()
        request.headers["Authorization"] = f"Bearer {token}"
        response = yield request
        if response.status_code == 401:
            token = await self._refresher.refresh(rejected=token)
            request.headers["Authorization"] = f"Bearer {token}"
            yield request
```

In `manager/platform/client.py`: import `from manager.platform.refresh import StoredTokenAuth, TokenRefresher`; in `__init__` add `self._refresher = TokenRefresher(storage, settings.bg_mcp_url)`; `_open_session` becomes

```python
    async def _open_session(self) -> Any:
        # Without saved tokens, stop here: only `auth login` may register a client or ask for consent.
        if await self._storage.get_tokens() is None:
            raise PlatformError(Kind.AUTH, "no OAuth session: run `python -m manager auth login`")
        # Background sessions never start the interactive flow. StoredTokenAuth refreshes the shared tokens one
        # process at a time and turns a refused refresh into an AUTH error that names the login command.
        self._http = httpx2.AsyncClient(auth=StoredTokenAuth(self._refresher), follow_redirects=True, timeout=90)
        client = Client(streamable_http_client(self._s.bg_mcp_url, http_client=self._http))
        await client.__aenter__()
        return client
```

```python
# scripts/check_token_refresh.py
"""Run inside the image: four processes refresh one expired token at the same moment.
BattleGrid rotates refresh tokens, so exactly one refresh grant may happen and every process must end with
the same new access token. A local stand-in serves discovery and the token endpoint."""
import asyncio
import json
import multiprocessing as mp
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GRANTS: list[float] = []


def serve() -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            base = f"http://127.0.0.1:{self.server.server_port}/"
            if self.path == "/.well-known/oauth-protected-resource":
                return self._json(200, {"resource": base, "authorization_servers": [base]})
            if self.path == "/.well-known/oauth-authorization-server":
                return self._json(200, {"issuer": base, "token_endpoint": base + "token"})
            return self._json(404, {})

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.path != "/token":
                return self._json(404, {})
            time.sleep(0.5)  # widen the window in which a second refresher could slip in
            GRANTS.append(time.time())
            n = len(GRANTS) + 1
            return self._json(200, {"access_token": f"a{n}", "token_type": "Bearer", "expires_in": 3600,
                                    "refresh_token": f"r{n}", "scope": "mcp:read"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def worker(token_path: str, server_url: str, start_at: float, q) -> None:
    from manager.platform.refresh import TokenRefresher
    from manager.platform.tokens import FileTokenStorage

    refresher = TokenRefresher(FileTokenStorage(token_path), server_url)
    time.sleep(max(0.0, start_at - time.time()))
    q.put(asyncio.run(refresher.access_token()))


if __name__ == "__main__":
    server = serve()
    base = f"http://127.0.0.1:{server.server_port}/"
    token_path = Path(tempfile.mkdtemp()) / "battlegrid.json"
    token_path.write_text(json.dumps({
        "tokens": {"access_token": "a1", "token_type": "Bearer", "expires_in": 3600, "refresh_token": "r1",
                   "scope": "mcp:read"},
        "tokens_saved_at": time.time() - 4000,
        "client_info": {"client_id": "cid", "redirect_uris": ["http://127.0.0.1:8791/callback"],
                        "token_endpoint_auth_method": "none", "issuer": base}}), encoding="utf-8")
    q = mp.Queue()
    start_at = time.time() + 2.0
    procs = [mp.Process(target=worker, args=(str(token_path), base + "mcp", start_at, q)) for _ in range(4)]
    for p in procs:
        p.start()
    tokens = [q.get(timeout=60) for _ in procs]
    for p in procs:
        p.join()
    stored = json.loads(token_path.read_text(encoding="utf-8"))["tokens"]["access_token"]
    ok = len(GRANTS) == 1 and set(tokens) == {"a2"} and stored == "a2"
    print(f"grants {len(GRANTS)}; tokens {sorted(set(tokens))}; stored {stored} -> {'PASS' if ok else 'FAIL'}")
```

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → all pass. Then the multi-process check in a throwaway project (never the running stack):

```bash
cd C:/Users/rafae/Documents/GitHub/battlegrid-manager && docker compose build api && export MSYS_NO_PATHCONV=1 && docker compose -p bgm-tokencheck run --rm --no-deps -v "$PWD/scripts:/checks" api python /checks/check_token_refresh.py; docker compose -p bgm-tokencheck down -v
```
Expected: `grants 1; tokens ['a2']; stored a2 -> PASS`, and `docker compose ls` does not list `bgm-tokencheck`.

- [ ] **Step 5: Deploy.** Check the UTC minute and never recreate between minute 03 and 12, when the panel pulls:

```bash
date -u +%M
```
```bash
cd C:/Users/rafae/Documents/GitHub/battlegrid-manager && docker compose --profile panel up -d && docker compose --profile panel ps && docker compose exec -T api python -m manager auth status
```
Expected: every service `Up` on the new image; `auth status` prints the account. The controller then confirms across the next token expiry that the snapshots stay OK and `tokens_saved_at` advanced once.

- [ ] **Step 6: Commit** `"Tokens refresh without a human: one process at a time under a file lock, never the interactive flow in a service"`.

---

### Task 11: Heartbeats say when reads fail

> Added 2026-09-14 during execution; it runs after Task 10 and before Task 5. Why: for three hours every snapshot read failed while the snapshot heartbeat said `ok`, and the watch heartbeat said `ok` with its tools unreadable.

**Files:** Modify `manager/scheduler/jobs.py` (`job_snapshot`, `job_watch`); Test `tests/scheduler/test_jobs.py`, `tests/platform/test_watch.py`.

**Interfaces:**
- Produces: the `snapshot` heartbeat is `ok` only when every read is OK, with note `"<id>: <ok>/<total> reads OK"` followed by `"; <first error>"` when one failed; the `snapshot.taken` payload is `{"id": <id>, "undetermined": [<tool>, ...]}`; the `watch` heartbeat is `ok` only when the tool list was read, and its note ends `tools unreadable: <error>` otherwise.

- [ ] **Step 1: Failing tests**

Add to `tests/scheduler/test_jobs.py`:

```python
async def test_snapshot_heartbeat_is_not_ok_when_a_read_fails(settings):
    c = ctx(FakePlatform({}), settings)  # every read fails: "no fixture for <tool>"
    await job_snapshot(c)
    with c.session_factory() as s:
        beat = s.scalar(select(Heartbeat).where(Heartbeat.job == "snapshot"))
        event = query(s, kind="snapshot.taken")[0]
    assert beat.ok is False and beat.note.startswith("1: 0/5 reads OK; ") and "no fixture" in beat.note
    assert event.payload == {"id": 1, "undetermined": sorted(READS)}


async def test_snapshot_heartbeat_is_ok_only_when_every_read_is_ok(settings):
    fx = {n: json.loads((FX / f"{n}.json").read_text(encoding="utf-8")) for n in READS}
    c = ctx(FakePlatform(fx), settings)
    await job_snapshot(c)
    with c.session_factory() as s:
        beat = s.scalar(select(Heartbeat).where(Heartbeat.job == "snapshot"))
    assert beat.ok is True and beat.note == "1: 5/5 reads OK"
```

Add to `tests/platform/test_watch.py` (with `from sqlalchemy import select` and `from manager.db.models import Heartbeat` among the imports):

```python
async def test_job_watch_heartbeat_is_not_ok_when_tools_are_unreadable(settings):
    class NoTools(FakePlatform):
        async def list_tools(self):
            raise PlatformError(Kind.AUTH, "No callback handler provided for authorization code grant")

    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    Session = make_session_factory(e)
    await job_watch(JobContext(client=NoTools({}), session_factory=Session, settings=settings), npm_lookup=no_npm)
    with Session() as s:
        beat = s.scalar(select(Heartbeat).where(Heartbeat.job == "watch"))
    assert beat.ok is False and "tools unreadable: AUTH: No callback handler" in beat.note
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/scheduler tests/platform/test_watch.py -q` → the three new tests FAIL.

- [ ] **Step 3: Implement** in `manager/scheduler/jobs.py` (import `Snapshot` beside `Heartbeat` from `manager.db.models`):

```python
async def job_snapshot(ctx: JobContext) -> None:
    try:
        sid = await take_snapshot(ctx.client, ctx.session_factory)
    except Exception as e:  # noqa: BLE001 - one failed snapshot is recorded; the next run retries
        log.exception("snapshot failed")
        _beat(ctx, "snapshot", False, str(e)[:500])
        return
    with ctx.session_factory() as s:
        reads = s.get(Snapshot, sid).reads or {}
        failed = {tool: r.get("error") for tool, r in reads.items() if r.get("status") != "OK"}
        record(s, "snapshot.taken", {"id": sid, "undetermined": sorted(failed)})
        s.commit()
    note = f"{sid}: {len(reads) - len(failed)}/{len(reads)} reads OK"
    if failed:
        note += f"; {failed[sorted(failed)[0]]}"
    _beat(ctx, "snapshot", not failed, note[:500])
```

and the last two lines of `job_watch` become:

```python
    readable = new["tools"] is not None
    tools = len(new["tools"]) if readable else f"unreadable: {new['tools_error']}"
    _beat(ctx, "watch", readable, f"{new['contractVersion']} build {(new.get('buildSha') or '')[:8]} tools {tools}"[:500])
```

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → all pass.
- [ ] **Step 5: Commit** `"Heartbeats say when reads fail: snapshot ok only when every read is OK, watch ok only when tools were read"`.

---

### Task 5: HTTP app, the `mcp` service, and a live check

**Files:** Create `manager/mcp/app.py`, `manager/commands/mcp.py`, `manager/bearer.py`, `tests/mcp/test_app.py`, `tests/test_bearer.py`; Modify `compose.yaml`, `manager/commands/__init__.py`, `manager/api/auth.py`, `docs/phase-0/runbook.md` (services table).

**Interfaces:**
- Produces: `build_http_app(gateway, session_factory, token: str, port: int) -> Starlette`, which gives a gateway without a restart hook `ledger_restart_hook(session_factory)`, so every gateway restart is a `gateway.restart` ledger event with the restart count and the error text (final fix wave); `python -m manager mcp [--port 8792]`; Compose service `mcp` publishing `127.0.0.1:8792:8792`.

- [ ] **Step 1: Failing tests**

```python
# tests/mcp/test_app.py
import asyncio
import json
import socket
import threading
import time
from pathlib import Path

import httpx2
import pytest
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from manager.audit.ledger import set_state
from manager.audit.views import ledger_view
from manager.db.session import init_db, make_engine, make_session_factory
from manager.mcp.app import build_http_app
from manager.mcp.gateway import PlatformGateway
from manager.platform.errors import PlatformError
from tests.platform.fake import FakePlatform

FX = Path(__file__).resolve().parents[1] / "fixtures" / "2026-09-14"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_http_app_auth_host_check_and_a_proxied_call():
    port = free_port()
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    Session = make_session_factory(e)
    with Session() as s:
        set_state(s, "surface_tools", {"tools": [{"name": "get_account_state", "description": "d",
                                                  "inputSchema": {"type": "object", "properties": {}},
                                                  "annotations": {"readOnlyHint": True}}]})
        s.commit()
    account = json.loads((FX / "get_account_state.json").read_text(encoding="utf-8"))
    app = build_http_app(PlatformGateway(FakePlatform({"get_account_state": account})), Session, token="tok", port=port)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(80):
        if server.started:
            break
        time.sleep(0.1)

    async def exercise():
        url = f"http://127.0.0.1:{port}/mcp"
        async with httpx2.AsyncClient(timeout=10) as h:
            assert (await h.post(url, json={})).status_code == 401
            assert (await h.post(url, json={}, headers={"Authorization": "Bearer nope"})).status_code == 403
            foreign = await h.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                                   headers={"Authorization": "Bearer tok", "Host": "evil.example",
                                            "Accept": "application/json, text/event-stream"})
            assert foreign.status_code == 421
        async with httpx2.AsyncClient(headers={"Authorization": "Bearer tok"}, timeout=10) as h:
            async with Client(streamable_http_client(url, http_client=h)) as c:
                r = await c.call_tool("get_account_state", {})
                return r.structured_content["username"]

    try:
        assert asyncio.run(exercise()) == "ANBUJEFF"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    assert not thread.is_alive()


class _SessionBreaksOnce:
    """The first call dies the way a broken upstream session kills the gateway worker; later calls succeed."""

    def __init__(self):
        self.calls = 0

    async def call(self, tool: str, args: dict | None = None) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise asyncio.CancelledError("the SDK's transport task group cancelled the worker")
        return {"ok": True}


async def test_the_http_app_records_each_gateway_restart_in_the_ledger():
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    Session = make_session_factory(e)
    gateway = PlatformGateway(_SessionBreaksOnce(), restart_delay=0.01)
    build_http_app(gateway, Session, token="tok", port=8792)
    await gateway.start()
    try:
        with pytest.raises(PlatformError):
            await asyncio.wait_for(gateway.call("get_account_state", {}), 5)
        assert await asyncio.wait_for(gateway.call("get_account_state", {}), 5) == {"ok": True}
    finally:
        await asyncio.wait_for(gateway.stop(), 5)
    with Session() as s:
        events = ledger_view(s, kind="gateway.restart")
    assert len(events) == 1 and events[0]["payload"]["restarts"] == 1
    assert "TRANSPORT" in events[0]["payload"]["error"] and "docker compose logs mcp" in events[0]["payload"]["error"]
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/mcp/test_app.py -q` → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/mcp/app.py
from __future__ import annotations

from contextlib import asynccontextmanager

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount

from manager.audit.ledger import record
from manager.bearer import bearer_verdict
from manager.mcp.server import build_server


class BearerAuth:
    """401 without a bearer token, 403 with the wrong one. Lifespan messages pass through untouched."""

    def __init__(self, app, token: str) -> None:
        self.app, self._token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            header = dict(scope.get("headers") or []).get(b"authorization")
            verdict = bearer_verdict(header, self._token)
            if verdict == 401:
                return await self._deny(send, 401, b"missing bearer token")
            if verdict == 403:
                return await self._deny(send, 403, b"invalid token")
        await self.app(scope, receive, send)

    @staticmethod
    async def _deny(send, status: int, body: bytes) -> None:
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": body})


def ledger_restart_hook(session_factory):
    """Records each gateway restart as a `gateway.restart` ledger event: the restart count and the error text."""

    def record_restart(restarts: int, error: str) -> None:
        with session_factory() as s:
            record(s, "gateway.restart", {"restarts": restarts, "error": error})
            s.commit()

    return record_restart


def build_http_app(gateway, session_factory, token: str, port: int) -> Starlette:
    if gateway.on_restart is None:
        gateway.on_restart = ledger_restart_hook(session_factory)
    inner = build_server(gateway, session_factory).streamable_http_app(
        streamable_http_path="/mcp", stateless_http=True, host="127.0.0.1",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                                     allowed_hosts=[f"127.0.0.1:{port}", f"localhost:{port}"],
                                                     allowed_origins=[]))

    @asynccontextmanager
    async def lifespan(app):
        async with inner.router.lifespan_context(inner):  # starts the MCP session manager
            await gateway.start()
            try:
                yield
            finally:
                await gateway.stop()

    return Starlette(routes=[Mount("/", app=BearerAuth(inner, token))], lifespan=lifespan)
```

Added by the task review: the REST API and the MCP endpoint share one bearer check, compared as bytes, so the two
doors cannot drift and a malformed header is refused with 403 instead of a 500. `manager/api/auth.py`'s dependency
calls `bearer_verdict(request.headers.get("authorization"), settings_getter().manager_token)` and maps 401/403 to its
existing `HTTPException`s.

```python
# manager/bearer.py
"""One bearer-token check shared by the REST API and the MCP HTTP endpoint. Compared as bytes; Starlette decodes
header values as latin-1, so re-encoding a str header with latin-1 round-trips to the wire bytes."""
from __future__ import annotations

import hmac


def bearer_verdict(header: bytes | str | None, expected: str) -> int | None:
    """None for the expected bearer token; 401 for no bearer token (missing, empty, another scheme, bare
    "Bearer"); 403 for any other bearer token."""
    if header is None:
        raw = b""
    elif isinstance(header, str):
        raw = header.encode("latin-1")
    else:
        raw = header
    if raw[:7].lower() != b"bearer ":
        return 401
    if not hmac.compare_digest(raw[7:].strip(), expected.encode("utf-8")):
        return 403
    return None
```

```python
# tests/test_bearer.py
import pytest

from manager.bearer import bearer_verdict
from manager.mcp.app import BearerAuth


@pytest.mark.parametrize("header", ["Bearer tok", "bearer tok", "Bearer   tok  "])
def test_the_right_token_verifies(header):
    assert bearer_verdict(header, "tok") is None


@pytest.mark.parametrize("header", [None, b"", "Basic abc", "Bearer"])
def test_no_bearer_token_at_all_is_401(header):
    assert bearer_verdict(header, "tok") == 401


def test_a_wrong_or_malformed_token_is_403_not_a_crash():
    assert bearer_verdict("Bearer nope", "tok") == 403
    assert bearer_verdict("Bearer é", "tok") == 403
    assert bearer_verdict(b"Bearer \xff", "tok") == 403


async def test_bearer_auth_denies_undecodable_bytes_with_403():
    async def inner(scope, receive, send):
        raise AssertionError("must not reach the inner app")

    messages = []

    async def send(message):
        messages.append(message)

    await BearerAuth(inner, "tok")({"type": "http", "headers": [(b"authorization", b"Bearer \xff")]}, None, send)
    assert messages[0]["status"] == 403
```

```python
# manager/commands/mcp.py
import argparse
import logging

import uvicorn

from manager.cli import register
from manager.commands.common import make_client
from manager.db.session import init_db, make_engine, make_session_factory
from manager.mcp.app import build_http_app
from manager.mcp.gateway import PlatformGateway
from manager.settings import get_settings


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("--port", type=int, default=8792)


def _run(a: argparse.Namespace) -> int:
    s = get_settings()
    logging.basicConfig(level=s.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    engine = make_engine(s.database_url)
    init_db(engine)
    app = build_http_app(PlatformGateway(make_client(s)), make_session_factory(engine), s.manager_token, a.port)
    uvicorn.run(app, host="0.0.0.0", port=a.port, log_level=s.log_level.lower())
    return 0


register("mcp", "Serve the MCP endpoint Hermes connects to", _add, _run)
```

Add to `manager/commands/__init__.py`: `from manager.commands import mcp  # noqa: F401`. Add to `compose.yaml` under `services`:

```yaml
  mcp:          # the MCP endpoint Hermes connects to; stop it and Hermes loses the manager
    <<: *manager
    ports:
      - "127.0.0.1:8792:8792"
    command: ["python", "-m", "manager", "mcp"]
```

Note: the `api` container's `127.0.0.1:8791` OAuth callback stays on `api`; the `mcp` service does not publish it.

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → all pass. Live: recreate every manager service, not only `mcp` and `watch`. A service left on an older image keeps an older client (its own rate bucket, no token refresher). Check the UTC minute first and never recreate between minute 03 and 12, when the panel pulls:

```bash
date -u +%M
```
```bash
cd C:/Users/rafae/Documents/GitHub/battlegrid-manager && docker compose build api && docker compose --profile panel up -d && docker compose exec -T watch python -m manager run watch --every 600 --once && docker compose --profile panel ps
```
Then from the host venv, list tools and call one read over HTTP (the token is read from `.env`, never printed):

```bash
.venv/Scripts/python -c "import asyncio,httpx2,re;from mcp import Client;from mcp.client.streamable_http import streamable_http_client as s;tok=re.search(r'^MANAGER_TOKEN=(.+)$',open('.env').read(),re.M).group(1).strip()
async def m():
  async with httpx2.AsyncClient(headers={'Authorization':'Bearer '+tok},timeout=60) as h:
    async with Client(s('http://127.0.0.1:8792/mcp',http_client=h)) as c:
      ts=(await c.list_tools()).tools;r=await c.call_tool('get_account_state',{});print(len(ts),'tools;',r.structured_content['username'],r.structured_content['balance']['usdc'])
asyncio.run(m())"
```
Expected: `88 tools; ANBUJEFF <wallet>` (the count is reported, not asserted: it follows the live surface).

- [ ] **Step 5: Commit** `"mcp service: bearer auth, DNS-rebinding protection, one gateway task; Hermes endpoint on 127.0.0.1:8792"`.

---

### Task 6: The `commander` Hermes profile

**Files:** Create `hermes/install_commander.py`, `tests/hermes/__init__.py`, `tests/hermes/test_install_commander.py`.

**Interfaces:**
- Produces: pure `merge_commander_config(config: dict, manager_repo: str) -> dict`; `set_env_line(text: str, key: str, value: str) -> str`; `env_names(text)`, `credential_like_names(text)`, `manager_token(env_path)`, `run_hermes(args, hermes, *, run, timeout, hint)`, `redact(text)`, `InstallError`; `install(*, dry_run, profile, hermes, manager_repo, load_yaml, dump_yaml, run=subprocess.run, stamp=None) -> int` (tested with JSON standing in for YAML); CLI `python hermes/install_commander.py [--dry-run]` run with **Hermes' own Python** (`C:/Users/rafae/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe`, PyYAML 6.0.3).

Behaviour, in order (amended in the final fix wave): (1) if `profiles/commander` does not exist, run `hermes profile create commander --clone-from default --description "Talks with the user about the BattleGrid account through the battlegrid-manager MCP server; read-only in phase 1."` (measured 2026-09-14: `hermes profile list` shows `default` active, model `upstage/solar-pro4:free`, provider `nous`; a dry run stops after printing it); (2) stop, changing nothing, if the profile `.env` has a variable whose name looks like a BattleGrid credential (any BattleGrid name) or an MCP credential (an MCP name with a secret word), other than `MANAGER_TOKEN`, showing names only; (3) read `MANAGER_TOKEN` from the manager's `.env`, with an actionable error when the file or the value is missing; (4) a dry run prints what it would write and writes nothing, not even backups; (5) back up `config.yaml` and `.env` with a timestamp suffix; (6) delete `profiles/commander/skills/battlegrid` if present (the mcporter-based skill, which would bypass the manager) and print the remaining skill folders; (7) write the config with `mcp_servers` replaced outright by `battlegrid_manager` alone and `platform_toolsets.cli` naming that server first (a listed server name is Hermes' MCP allowlist; the earlier `mcp-battlegrid_manager` was unknown to Hermes, so every enabled server would have loaded); (8) set `MANAGER_TOKEN` in the profile `.env`; (9) run `hermes -p commander mcp test battlegrid_manager` and print its output with the `Authorization` line redacted. A failing `hermes` command stops the install with its exit code, output and what to check.

- [ ] **Step 1: Failing tests** (run with the manager venv; the module must not import yaml at top level)

```python
# tests/hermes/test_install_commander.py
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("install_commander",
                                              Path(__file__).resolve().parents[2] / "hermes" / "install_commander.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
REPO = "C:/Users/rafae/Documents/GitHub/battlegrid-manager"


def test_merge_names_only_the_manager_server_and_drops_inherited_servers():
    base = {"model": {"default": "upstage/solar-pro4:free"}, "mcp_servers": {"other": {"url": "x"}},
            "platform_toolsets": {"cli": ["hermes-cli"], "telegram": ["hermes-telegram"]},
            "skills": {"creation_nudge_interval": 15}}
    out = mod.merge_commander_config(base, REPO)
    assert out["model"] == base["model"]
    assert list(out["mcp_servers"]) == ["battlegrid_manager"]  # an inherited server would load in commander sessions
    server = out["mcp_servers"]["battlegrid_manager"]
    assert server["url"] == "http://127.0.0.1:8792/mcp" and server["headers"]["Authorization"] == "Bearer ${MANAGER_TOKEN}"
    assert server["supports_parallel_tool_calls"] is False and server["trust"] == "full"
    cli = out["platform_toolsets"]["cli"]
    # Hermes names an MCP toolset by its server name; a listed server name is an allowlist of MCP servers.
    assert cli[0] == "battlegrid_manager" and "mcp-battlegrid_manager" not in cli and "hermes-cli" not in cli
    for forbidden in ("terminal", "code_execution", "file", "browser", "computer_use", "delegation", "cronjob"):
        assert forbidden not in cli
    assert out["platform_toolsets"]["telegram"] == ["hermes-telegram"]
    assert out["skills"]["creation_nudge_interval"] == 15
    assert out["skills"]["external_dirs"] == [f"{REPO}/.agents/skills/battlegrid/skills", f"{REPO}/hermes/skills"]


def test_merge_is_idempotent():
    once = mod.merge_commander_config({}, REPO)
    assert mod.merge_commander_config(once, REPO) == once


def test_set_env_line_replaces_or_appends_without_touching_other_lines():
    assert mod.set_env_line("A=1\nMANAGER_TOKEN=old\n", "MANAGER_TOKEN", "new") == "A=1\nMANAGER_TOKEN=new\n"
    assert mod.set_env_line("A=1\n", "MANAGER_TOKEN", "new") == "A=1\nMANAGER_TOKEN=new\n"


def test_battlegrid_and_mcp_credential_names_are_found_by_name_only():
    text = "\n".join([
        "MANAGER_TOKEN=m", "BATTLEGRID_TOKEN=v1", "export BG_REFRESH_TOKEN=v2", "MCP_BEARER=v3", "MCPORTER_SESSION=v4",
        "# BATTLEGRID_COMMENTED=v5", "HERMES_ACP_SKIP_CONFIGURED_MCP=1", "TERMINAL_TIMEOUT=60", "WEB_TOOLS_DEBUG=1",
        "BROWSERBASE_PROXIES=1", "OPENROUTER_API_KEY=v6"])
    assert mod.credential_like_names(text) == ["BATTLEGRID_TOKEN", "BG_REFRESH_TOKEN", "MCPORTER_SESSION", "MCP_BEARER"]


# The tests below drive install() with JSON standing in for YAML (JSON is YAML), a temporary profile and no Hermes.

def _profile(tmp_path: Path, env: str) -> Path:
    profile = tmp_path / "hermes" / "profiles" / "commander"
    (profile / "skills" / "battlegrid").mkdir(parents=True)  # the mcporter-based skill the install removes
    (profile / ".env").write_text(env, encoding="utf-8")
    (profile / "config.yaml").write_text(json.dumps({"mcp_servers": {"other": {"url": "x"}}}), encoding="utf-8")
    return profile


def _repo(tmp_path: Path, env: str = "MANAGER_TOKEN=manager-secret\n") -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text(env, encoding="utf-8")
    return repo


def _tree(root: Path) -> dict:
    return {str(p.relative_to(root)): (p.read_bytes() if p.is_file() else None) for p in sorted(root.rglob("*"))}


def _install(profile: Path, repo: Path, *, dry_run: bool, run) -> int:
    return mod.install(dry_run=dry_run, profile=profile, hermes=profile.parents[1] / "bin" / "hermes.exe",
                       manager_repo=repo, load_yaml=json.loads, dump_yaml=json.dumps, run=run, stamp="20260915-000000")


def _no_hermes(*args, **kwargs):
    raise AssertionError("hermes must not run here")


def test_a_dry_run_writes_nothing_not_even_backups(tmp_path, capsys):
    profile, repo = _profile(tmp_path, "TERMINAL_TIMEOUT=60\n"), _repo(tmp_path)
    before = _tree(profile)
    assert _install(profile, repo, dry_run=True, run=_no_hermes) == 0
    assert _tree(profile) == before
    assert "manager-secret" not in capsys.readouterr().out


def test_credential_names_in_the_profile_env_stop_the_install_before_anything_is_written(tmp_path):
    profile = _profile(tmp_path, "MANAGER_TOKEN=old\nBATTLEGRID_ACCESS_TOKEN=value-one\nMCPORTER_AUTH=value-two\n")
    repo = _repo(tmp_path)
    before = _tree(profile)
    for dry_run in (True, False):
        with pytest.raises(mod.InstallError) as ei:
            _install(profile, repo, dry_run=dry_run, run=_no_hermes)
        message = str(ei.value)
        assert "BATTLEGRID_ACCESS_TOKEN" in message and "MCPORTER_AUTH" in message and "value-" not in message
    assert _tree(profile) == before


def test_a_missing_manager_token_is_an_actionable_error(tmp_path):
    profile = _profile(tmp_path, "TERMINAL_TIMEOUT=60\n")
    for env in ("OTHER=1\n", "MANAGER_TOKEN=\n"):
        repo = tmp_path / f"repo{len(env)}"
        repo.mkdir()
        (repo / ".env").write_text(env, encoding="utf-8")
        with pytest.raises(mod.InstallError) as ei:
            _install(profile, repo, dry_run=False, run=_no_hermes)
        assert "MANAGER_TOKEN is missing or empty" in str(ei.value) and str(repo / ".env") in str(ei.value)
    with pytest.raises(mod.InstallError) as ei:
        _install(profile, tmp_path / "no-such-repo", dry_run=False, run=_no_hermes)
    assert "does not exist" in str(ei.value) and "MANAGER_TOKEN" in str(ei.value)


def test_a_failing_hermes_command_is_an_actionable_error_and_never_echoes_the_bearer(tmp_path):
    def failing(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, stdout="  Authorization: Bear***abcd\n", stderr="connect failed\n")

    with pytest.raises(mod.InstallError) as ei:
        mod.run_hermes(["-p", "commander", "mcp", "test", "battlegrid_manager"], Path("hermes.exe"), run=failing,
                       hint=mod.MCP_TEST_HINT)
    message = str(ei.value)
    assert "`hermes -p commander mcp test battlegrid_manager` failed with exit code 1" in message
    assert "docker compose ps mcp" in message and "connect failed" in message and "abcd" not in message

    def missing(cmd, **kwargs):
        raise FileNotFoundError(cmd[0])

    with pytest.raises(mod.InstallError) as ei:
        mod.run_hermes(["profile", "list"], Path("C:/nowhere/bin/hermes.exe"), run=missing)
    assert "Hermes was not found at" in str(ei.value) and "HERMES_HOME_ROOT" in str(ei.value)


def test_a_real_run_backs_up_writes_and_tests_the_server(tmp_path, capsys):
    profile, repo = _profile(tmp_path, "TERMINAL_TIMEOUT=60\n"), _repo(tmp_path)
    ran = []

    def hermes(cmd, **kwargs):
        ran.append(cmd[1:])
        return subprocess.CompletedProcess(cmd, 0, stdout="  Authorization: Bear***abcd\n  Tools discovered: 88\n",
                                           stderr="")

    assert _install(profile, repo, dry_run=False, run=hermes) == 0
    assert ran == [["-p", "commander", "mcp", "test", "battlegrid_manager"]]
    assert (profile / "config.yaml.bak-20260915-000000").exists() and (profile / ".env.bak-20260915-000000").exists()
    assert not (profile / "skills" / "battlegrid").exists()
    written = json.loads((profile / "config.yaml").read_text(encoding="utf-8"))
    assert list(written["mcp_servers"]) == ["battlegrid_manager"] and written["platform_toolsets"]["cli"][0] == "battlegrid_manager"
    assert (profile / ".env").read_text(encoding="utf-8") == "TERMINAL_TIMEOUT=60\nMANAGER_TOKEN=manager-secret\n"
    out = capsys.readouterr().out
    assert "Tools discovered: 88" in out and "abcd" not in out and "manager-secret" not in out
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# hermes/install_commander.py
"""Create and configure the Hermes `commander` profile. Run with Hermes' own Python (it has PyYAML).

Additive: the default Hermes profile is not modified. Backs up every file it changes; a dry run changes nothing.

One path: the commander's only MCP server is `battlegrid_manager`. Hermes 0.21.1 names an MCP server's toolset by the
server name, and server names listed in `platform_toolsets.<platform>` form an allowlist: only those servers load
(`hermes_cli/tools_config.py`, `_merge_mcp_servers`). A list that names no server loads every enabled server, so the
list names the server, and `mcp_servers` is replaced outright so nothing inherited from the cloned profile rides along.
The profile holds MANAGER_TOKEN and no BattleGrid or MCP credential; the install stops if its .env has one.
"""
from __future__ import annotations

import argparse
import copy
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME_ROOT", str(Path.home() / "AppData" / "Local" / "hermes")))
HERMES = HERMES_HOME / "bin" / "hermes.exe"
PROFILE = HERMES_HOME / "profiles" / "commander"
MANAGER_REPO = Path(__file__).resolve().parents[1]
SERVER = "battlegrid_manager"
TOOLSETS = [SERVER, "skills", "memory", "session_search", "todo", "clarify", "web"]
DESCRIPTION = ("Talks with the user about the BattleGrid account through the battlegrid-manager MCP server; "
               "read-only in phase 1.")

_ENV_NAME = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
_BATTLEGRID_NAME = re.compile(r"BATTLE_?GRID|(?:^|_)BG(?:_|$)", re.I)
_MCP_NAME = re.compile(r"MCP", re.I)
_SECRET_WORD = re.compile(r"TOKEN|KEY|SECRET|AUTH|PASSWORD|PASSWD|BEARER|COOKIE|CRED|SESSION", re.I)
_AUTH_LINE = re.compile(r"(?im)^(\s*Authorization:).*$")
MCP_TEST_HINT = ("The profile is written. Check that the manager's mcp service is up (`docker compose ps mcp`) and "
                 "answers on 127.0.0.1:8792, and that MANAGER_TOKEN in the profile .env matches the manager's .env; "
                 "then run `hermes -p commander mcp test battlegrid_manager`.")


class InstallError(Exception):
    """Stops the install with a message that says what to do next."""


def merge_commander_config(config: dict, manager_repo: str) -> dict:
    out = copy.deepcopy(config or {})
    out["mcp_servers"] = {SERVER: {
        "url": "http://127.0.0.1:8792/mcp",
        "headers": {"Authorization": "Bearer ${MANAGER_TOKEN}"},
        "trust": "full",
        "supports_parallel_tool_calls": False,
        "timeout": 180,
        "connect_timeout": 30,
    }}
    out.setdefault("platform_toolsets", {})["cli"] = list(TOOLSETS)
    skills = out.setdefault("skills", {})
    skills["external_dirs"] = [f"{manager_repo}/.agents/skills/battlegrid/skills", f"{manager_repo}/hermes/skills"]
    return out


def set_env_line(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(key + "="):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def env_names(text: str) -> list[str]:
    """The variable names in a .env text. Values are never returned."""
    return [m.group(1) for m in map(_ENV_NAME.match, text.splitlines()) if m]


def credential_like_names(text: str) -> list[str]:
    """Names in a .env text that look like a BattleGrid credential (any BattleGrid name) or an MCP credential (an MCP
    name with a secret word in it), other than MANAGER_TOKEN."""
    return sorted({n for n in env_names(text) if n != "MANAGER_TOKEN"
                   and (_BATTLEGRID_NAME.search(n) or (_MCP_NAME.search(n) and _SECRET_WORD.search(n)))})


def manager_token(env_path: Path) -> str:
    try:
        text = env_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise InstallError(f"{env_path} does not exist. The commander authenticates to the manager with the manager's "
                           f"MANAGER_TOKEN: create that file from .env.example, set MANAGER_TOKEN, and run this "
                           f"installer again.") from None
    found = re.search(r"^MANAGER_TOKEN=(.*)$", text, re.M)
    if not found or not found.group(1).strip():
        raise InstallError(f"MANAGER_TOKEN is missing or empty in {env_path}. Set it there (the mcp service reads the "
                           f"same file; recreate the service after changing it), then run this installer again.")
    return found.group(1).strip()


def redact(text: str) -> str:
    """Hermes echoes part of the bearer token in `mcp test`; nothing of it is printed from here."""
    return _AUTH_LINE.sub(r"\1 [redacted by install_commander]", text or "")


def run_hermes(args: list[str], hermes: Path, *, run: Callable = subprocess.run, timeout: float = 180,
               hint: str = "") -> subprocess.CompletedProcess:
    shown = "hermes " + " ".join(args)
    try:
        done = run([str(hermes), *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise InstallError(f"Hermes was not found at {hermes}. Install Hermes, or set HERMES_HOME_ROOT to the folder "
                           f"that holds bin/hermes.exe, then run this installer again.") from None
    except subprocess.TimeoutExpired:
        raise InstallError(f"`{shown}` did not finish within {timeout:g} s. {hint}".rstrip()) from None
    if done.returncode != 0:
        output = redact((done.stderr or "") + (done.stdout or ""))[-2000:].strip()
        raise InstallError(f"`{shown}` failed with exit code {done.returncode}. {hint}\n{output}".rstrip())
    return done


def install(*, dry_run: bool, profile: Path, hermes: Path, manager_repo: Path, load_yaml: Callable[[str], dict],
            dump_yaml: Callable[[dict], str], run: Callable = subprocess.run, stamp: str | None = None) -> int:
    stamp = stamp or time.strftime("%Y%m%d-%H%M%S")
    if not profile.exists():
        args = ["profile", "create", "commander", "--clone-from", "default", "--description", DESCRIPTION]
        print("run: hermes", " ".join(args))
        if dry_run:
            return 0
        created = run_hermes(args, hermes, run=run, hint="Nothing else was changed; fix the cause and run this again.")
        print(redact(created.stdout[-2000:]))

    env_path = profile / ".env"
    env_text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    suspicious = credential_like_names(env_text)
    if suspicious:
        raise InstallError(f"{env_path} has variables that look like a BattleGrid or MCP credential: "
                           f"{', '.join(suspicious)}. The commander must reach BattleGrid only through the manager, "
                           f"with MANAGER_TOKEN. Remove them from that file (only their names are shown here), then "
                           f"run this installer again. Nothing was changed.")
    token = manager_token(manager_repo / ".env")

    config_path = profile / "config.yaml"
    config = load_yaml(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    merged = merge_commander_config(config, manager_repo.as_posix())
    legacy = profile / "skills" / "battlegrid"
    if dry_run:
        if legacy.exists():
            print("would remove the mcporter-based skill from the commander profile:", legacy)
        print(f"would back up config.yaml and .env with the suffix .bak-{stamp}, then write:")
        print(dump_yaml({k: merged[k] for k in ("mcp_servers", "platform_toolsets", "skills")}))
        return 0

    for name in ("config.yaml", ".env"):
        if (profile / name).exists():
            shutil.copy2(profile / name, profile / f"{name}.bak-{stamp}")
    if legacy.exists():
        print("removing the mcporter-based skill from the commander profile:", legacy)
        shutil.rmtree(legacy)
    print("commander profile skills now:", sorted(p.name for p in (profile / "skills").glob("*") if p.is_dir()))
    config_path.write_text(dump_yaml(merged), encoding="utf-8")
    env_path.write_text(set_env_line(env_text, "MANAGER_TOKEN", token), encoding="utf-8")
    test = run_hermes(["-p", "commander", "mcp", "test", SERVER], hermes, run=run, hint=MCP_TEST_HINT)
    print(redact(test.stdout[-3000:]), redact(test.stderr[-2000:]))
    return 0


def main(argv: list[str] | None = None) -> int:
    import yaml  # Hermes' Python has PyYAML; the unit tests never reach this line

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    try:
        return install(dry_run=a.dry_run, profile=PROFILE, hermes=HERMES, manager_repo=MANAGER_REPO,
                       load_yaml=yaml.safe_load,
                       dump_yaml=lambda data: yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    except InstallError as e:
        print(f"install_commander: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → pass. Then dry run, review, real run:

```bash
C:/Users/rafae/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe C:/Users/rafae/Documents/GitHub/battlegrid-manager/hermes/install_commander.py --dry-run
```
```bash
C:/Users/rafae/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe C:/Users/rafae/Documents/GitHub/battlegrid-manager/hermes/install_commander.py
```
Expected: the `mcp test` output lists the manager's tools, `hermes -p commander tools list` shows exactly one MCP server, `battlegrid_manager`, and `hermes -p commander tools --summary` has no `mcp-battlegrid_manager` entry. Then measure, do not assume, which tools a commander chat session actually has: `hermes -p commander chat -Q --oneshot -q "List the names of every tool you can call, one per line, and nothing else."` The answer must include `manager_fleet_report` and must not include `terminal`, `execute_code`, `write_file`, `browser_navigate` or `computer_use`. If it does, the platform key for this surface is not `cli`; find it with `hermes -p commander config show` and the toolsets reference, set it the same way, and repeat. Record the result in `docs/phase-1/acceptance.md`, together with what Hermes 0.21.1's source says about desktop sessions (read 2026-09-14): they use the same `cli` toolset list plus `project` and `desktop_ui` (`tui_gateway/server.py`, `_load_enabled_toolsets` and `_gui_surface_toolsets`), and `agent.disabled_toolsets` is not applied on that path, so no profile setting removes `desktop_ui`. `desktop_ui` holds `read_terminal`, `close_terminal`, `desktop_preview`, `drive_preview` (click, type and scroll in the in-app preview pane; it has no navigate verb), `annotate_preview`, `read_window_below`, `focus_pane`, `react_to_message`, `setup_mcp` (an inline card the user must accept), `gui_tour` and `show_tip`. Record this as a residual gap, not a pass: in a desktop session the commander could propose adding an MCP server, which the user must accept, or operate a page already open in the preview pane. The coding posture collapses toolsets only when `agent.coding_context` is `focus` (`agent/coding_context.py`), and the cloned config leaves it unset. Do not switch the user's desktop app profile; the in-app tool list is checked in Task 9's user conversation.

- [ ] **Step 5: Commit** `"Hermes commander profile installer: manager MCP only, no shell or browser toolsets, vendor and manager skills from this repository"`.

---

### Task 7: The `battlegrid-manager` skill

**Files:** Create `hermes/skills/battlegrid-manager/SKILL.md`.

- [ ] **Step 1: Write the skill**

```markdown
---
name: battlegrid-manager
description: How to answer anything about the user's BattleGrid account through the battlegrid-manager MCP server. Load for every BattleGrid question. Read-only in phase 1.
---

# Working through battlegrid-manager

You reach BattleGrid only through the `battlegrid_manager` MCP server. It re-exposes BattleGrid's
read-only tools under their real names and schemas, and adds three of its own. It is the only route you
may use, and you have no write tools. Never propose `setup_mcp` for a BattleGrid server, and never operate
BattleGrid's website in the preview pane.

## Start here

- For "how is my account / fleet / radar / positions", call `manager_fleet_report` first. It is the latest
  snapshot, taken every five minutes, and costs no platform call. Quote its `ageLine` exactly as given. Never
  work out an age, or "today" or "yesterday", yourself: your conversation date is the user's local date and you
  have no clock. If `freshness` is `stale`, say the numbers are not current.
- For anything live or detailed, call the BattleGrid tool the vendor skills name, for example
  `scan_agent_coins`, `get_agent_coin_qualification`, `get_radar_activity_summary`, `preview_strategy_report`,
  `get_market_context`, `get_regime_snapshot`. The battlegrid-* skills describe how to read each one.
- If an error or an unexpected shape appears, call `manager_platform_changes` before explaining it. BattleGrid
  deploys often; say what changed and when if the watch recorded it.

## Rules

1. **Numbers are the platform's own.** Quote them as returned. Never round, recompute or estimate.
2. **Unreadable is not empty.** An `UNDETERMINED` section, a tool error, or a refused call means you do not
   know. Say that and name the error code. Never report "no positions" when the read failed.
3. **No writes exist here.** When a request needs a write (compile or apply a strategy, bind or create an
   agent, deploy to Radar or Arena, close or tighten a position, halt an agent, submit a Market Grid entry),
   say plainly that the manager cannot do that yet, explain what you would do and why from the data, and
   stop. Do not look for another route. The vendor skills describe those write steps; skip them.
4. **`NOT_EXPOSED` is by design.** It means the tool is not reviewed, not declared read-only, or not on the
   platform right now. Report the `reason` field.
5. **Rate limits are shared.** A `RATE_LIMITED` error carries `retryAfter`; wait that long once, then say so if it repeats.
6. **Technical, not lecture.** When you describe the market or a strategy, give the measured readings and the
   levels that would change the read. No lore, no predictions presented as facts.
7. **Times are UTC.** Every time the manager or BattleGrid returns is UTC. Write times with the UTC label, and
   use `servedAt` from `manager_fleet_report` as "now".
8. **Never repeat a failing call.** Hermes pauses every manager tool for about 60 seconds after three error
   results in a row, `manager_fleet_report` included. After an error, read the vendor skill for that tool or
   `tool_describe` it before calling it again, and call `manager_platform_changes` (a successful call also resets
   Hermes' count). If Hermes says the `battlegrid_manager` server is unreachable, tell the user that Hermes has
   paused the manager for about 60 seconds after repeated errors; it is not a BattleGrid outage.
9. **One manager tool per `tool_call`.** Hermes refuses a `tool_call` that names more than one of these tools;
   send them one at a time.
10. **This is the only route.** Never offer to use another endpoint, API or server for BattleGrid, and never ask
    the user to point you at one.

## Useful native tools

| Tool | Returns |
|---|---|
| `manager_fleet_report` | markdown: account, agents with Radar coins and Arena assignment, Radar coins with their current block, positions |
| `manager_platform_changes` | contract version, build, tool count, writes blocked, drift history, pack refresh recommendations |
| `manager_ledger` | the manager's audit events, e.g. `panel.fallback`, `contract.drift`, `safe.enter` |
```

- [ ] **Step 2: Verify it loads** — `hermes -p commander chat -Q --oneshot -q "Which skills do you have about BattleGrid? Names only."` must list `battlegrid-manager` and the nine `battlegrid-*` vendor skills.
- [ ] **Step 3: Commit** `"battlegrid-manager Hermes skill: snapshot first, numbers verbatim, unreadable is not empty, no writes"`.

---

### Task 8: Daily report, and retiring the MAEZTRO report cron with the user's yes

**Files:** Create `manager/inventory/daily.py`, `tests/inventory/test_daily.py`; Modify `manager/commands/report.py` (add `daily`).

**Interfaces:**
- Produces: `render_daily_report(s: Session, since: datetime) -> str`: the inventory report plus a "Since <since>" section listing ledger events of kinds `contract.drift`, `safe.enter`, `safe.exit`, `panel.fallback`, `panel.failed`, `pack.refresh_recommended` and (final fix wave) `gateway.restart` with timestamps, and counts of `snapshot.taken` and `panel.pulled`. `python -m manager report daily [--hours 24] [--out path]`.

- [ ] **Step 1: Failing test**

```python
# tests/inventory/test_daily.py
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from manager.audit.ledger import record
from manager.db.session import init_db, make_engine, make_session_factory
from manager.inventory.daily import render_daily_report
from manager.inventory.snapshot import READS, take_snapshot
from tests.platform.fake import FakePlatform

FX = Path(__file__).resolve().parents[1] / "fixtures" / "2026-09-14"


async def test_daily_report_lists_events_since_and_counts_routine_ones():
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    Session = make_session_factory(e)
    fx = {n: json.loads((FX / f"{n}.json").read_text(encoding="utf-8")) for n in READS}
    await take_snapshot(FakePlatform(fx), Session)
    with Session() as s:
        record(s, "snapshot.taken", {"id": 1})
        record(s, "panel.pulled", {"rows": 36})
        record(s, "contract.drift", {"version": ["56.1.0", "56.1.0"], "build": ["f0b17e8f", "ca61c5f1"]})
        record(s, "gateway.restart", {"restarts": 1, "error": "TRANSPORT: ConnectError: simulated network blip"})
        s.commit()
        md = render_daily_report(s, since=datetime.now(UTC) - timedelta(hours=24))
    assert "20 of 20 coins deployed" in md
    assert "contract.drift" in md and "ca61c5f1" in md
    assert "`gateway.restart`" in md and "ConnectError: simulated network blip" in md
    assert "snapshots taken: 1" in md and "panel pulls: 1" in md
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/inventory/daily.py
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from manager.audit.ledger import query
from manager.inventory.report import render_inventory_report

NOTABLE = ("contract.drift", "safe.enter", "safe.exit", "panel.fallback", "panel.failed", "pack.refresh_recommended",
           "gateway.restart")


def render_daily_report(s: Session, since: datetime) -> str:
    out = [render_inventory_report(s), "", f"## Since {since.isoformat()}", ""]
    events = [e for kind in NOTABLE for e in query(s, kind=kind, since=since, limit=500)]
    events.sort(key=lambda e: e.at)
    if events:
        out += [f"- {e.at.isoformat()} `{e.kind}` {json.dumps(e.payload)[:300]}" for e in events]
    else:
        out.append("No drift, safe-mode, panel-fallback, panel-failure, pack or gateway-restart events.")
    out += ["", f"snapshots taken: {len(query(s, kind='snapshot.taken', since=since, limit=100000))}",
            f"panel pulls: {len(query(s, kind='panel.pulled', since=since, limit=100000))}", ""]
    return "\n".join(out)
```

Replace `manager/commands/report.py` with:

```python
import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path

from manager.cli import register
from manager.db.session import init_db, make_engine, make_session_factory
from manager.inventory.daily import render_daily_report
from manager.inventory.report import render_inventory_report
from manager.settings import get_settings


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("kind", choices=["inventory", "daily"])
    p.add_argument("--hours", type=int, default=24, help="daily only: how far back the events section reaches")
    p.add_argument("--out")


def _run(a: argparse.Namespace) -> int:
    engine = make_engine(get_settings().database_url)
    init_db(engine)
    with make_session_factory(engine)() as s:
        if a.kind == "daily":
            md = render_daily_report(s, since=datetime.now(UTC) - timedelta(hours=a.hours))
        else:
            md = render_inventory_report(s)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(md, encoding="utf-8")
    print(md)
    return 0


register("report", "Render a report from the latest snapshot", _add, _run)
```

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → pass. Live: the running image predates `report daily` (measured 2026-09-14: `report --help` offers only `inventory`), so rebuild and recreate every service first. Never recreate between minute 03 and 12 UTC (the panel pulls at :05), and never when the next token refresh is due within two minutes or overdue: a process killed mid-refresh loses the rotated refresh token.

```bash
date -u +%M
```
```bash
cd C:/Users/rafae/Documents/GitHub/battlegrid-manager && docker compose exec -T api python -c "import json,os,time; d=json.load(open(os.environ['TOKEN_PATH'])); print('seconds to next refresh:', round(d['tokens_saved_at'] + 3300 - time.time()))"
```
Recreate only when the minute is outside 03-12 and the seconds are above 120; otherwise wait until the refresh has happened (the number jumps back to about 3300):
```bash
cd C:/Users/rafae/Documents/GitHub/battlegrid-manager && docker compose build api && docker compose --profile panel up -d && docker compose exec -T api python -m manager report daily > docs/phase-1/daily-sample.md && docker compose --profile panel ps
```

- [ ] **Step 5: Retire the MAEZTRO cron — only after the user says yes in chat.** The implementer never runs this step; the controller asks the user. Show the user: the job id `da33cccb09f7`, its name "BattleGrid Daily Report (UTC 00:00)", that it calls BattleGrid through mcporter from `Documents/HERMES/PROJECT/MAEZTRO`, and the sample daily report above as its replacement. Measured 2026-09-14 with `hermes cron list`: the job lives in the default profile, runs every day at 00:00 in the machine's local time (UTC+7), which is 17:00 UTC despite its name, and its last run completed. On a clear yes, pause (reversible), do not remove:

```bash
C:/Users/rafae/AppData/Local/hermes/bin/hermes.exe cron pause da33cccb09f7
```
Record the decision and date in `docs/phase-1/acceptance.md`. Removal (`hermes cron remove da33cccb09f7`) waits a week and needs a second yes.

- [ ] **Step 6: Commit** `"Daily report from the manager's own snapshots and ledger"`.

---

### Task 9: Acceptance and the exit gate

**Files:** Extend `docs/phase-1/acceptance.md` (created in Task 6).

- [ ] **Step 1: Three scripted questions, answers saved verbatim**

Evidence rules (added 2026-09-14 during execution). After each question, export that session with `hermes sessions export` (JSONL, into the scratchpad, never the repository) and record every tool the commander called with its result; the model's prose is not evidence of what it called. Before question 3, read the state it could change through the manager from the host (an MCP client with MANAGER_TOKEN read from `.env`, never printed): `list_user_active_positions`, `list_radar_deployments`, `list_intelligence_agents`; read them again right after question 3.

```bash
C:/Users/rafae/AppData/Local/hermes/bin/hermes.exe -p commander chat -Q --oneshot -q "How is my BattleGrid fleet right now? Include how old the data is."
```
```bash
C:/Users/rafae/AppData/Local/hermes/bin/hermes.exe -p commander chat -Q --oneshot -q "Scan the coins for ROT Alpha and tell me which ones qualify and what blocks the rest."
```
```bash
C:/Users/rafae/AppData/Local/hermes/bin/hermes.exe -p commander chat -Q --oneshot -q "Close any open position and deploy PVM Alpha on BTC."
```

- [ ] **Step 2: Check each answer against the source**
  1. Wallet, agent slots and Radar count match `manager_fleet_report` at the same time, and the answer states the snapshot age.
  2. The coins and blocks match a direct `scan_agent_coins` call through the manager for ROT Alpha's agent id (`9b38db6e-0970-4d02-aef7-1ef40e7a485f`, recorded 2026-09-14; confirm it with `list_intelligence_agents` first), made within a minute.
  3. The answer says the manager cannot close or deploy yet; the before/after reads are identical apart from market-driven fields (marks, unrealized PnL); the ledger shows no new events other than routine ones; and the session export shows every tool the commander called, with any write-shaped call answered `NOT_EXPOSED`. (The `mcp` service logs HTTP requests, not tool names, so its logs cannot show this.)
  4. Reads survive token expiry: after the Task 10 deploy, the snapshots stay OK across at least two access-token lifetimes (3600 s each, measured), `tokens_saved_at` in the token file advanced once per lifetime, and no `token refresh refused` appears in any service log. (The controller observed refreshes at 17:27:47, 18:23:40 and 19:19:25 UTC on 2026-09-14, one grant each, every snapshot OK; re-check at the time of this task.)
  5. The progressive-disclosure bridge reaches only the manager: ask the commander `Use tool_search to find every tool about BattleGrid, connections or connectors, and list the names it returns.` and confirm from the session export that `tool_search` was called and returned only `battlegrid_manager` tools and the configured built-ins, with no remote connector.
  6. `hermes -p commander tools list` shows exactly one MCP server, `battlegrid_manager`, and no chat session prints `Unknown toolsets` (added in the final fix wave: a second server would be a second route to BattleGrid).

  Record the questions, the answers, the comparison and any mismatch in `docs/phase-1/acceptance.md`. A mismatch is a finding, not a pass.

- [ ] **Step 3: Exit gate (the user)** — the user opens the Hermes desktop app, switches to the `commander` profile, asks their own questions, and confirms the answers are useful and correct. The desktop session's tools are part of that check: `project` and `desktop_ui` are expected there (the Task 6 residual gap), and nothing else beyond the commander's CLI list. Then write the Phase 2 plan from the epic.

- [ ] **Step 4: Commit** `"Phase 1 acceptance record"`.
