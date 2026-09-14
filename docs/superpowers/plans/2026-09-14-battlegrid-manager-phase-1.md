# BattleGrid Manager — Phase 1: Commander — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Hermes profile named `commander` that the user talks to in the Hermes desktop app, answering from BattleGrid through the manager and only through the manager, with no way to write to the account.

**Architecture:** A new `mcp` Compose service exposes one MCP endpoint to Hermes. It re-exposes BattleGrid's own **read-only** tools under their real names and schemas (so the vendor skills' read steps work unchanged), plus three manager-native tools. A tool is exposed only if it is on a reviewed allowlist **and** the live platform declares it read-only **and** it exists in the latest watched surface; so the exposed surface updates itself when BattleGrid changes, and a tool that flips to writing disappears. One worker task owns the upstream session. All services share one Postgres rate limiter. The Hermes profile gets only the manager's MCP toolset plus non-shell toolsets, so it cannot reach BattleGrid any other way.

**Tech Stack:** as Phase 0, plus the MCP SDK low-level `Server` (`mcp.server.lowlevel.Server`, `on_list_tools` / `on_call_tool`), `Server.streamable_http_app(...)` with `TransportSecuritySettings`, Starlette lifespan composition, Hermes 0.21.1 profiles (`hermes profile create`, `platform_toolsets`, `skills.external_dirs`, `mcp_servers`), Hermes' bundled Python 3.11 with PyYAML 6.0.3 for the installer.

## Global Constraints

- **Read-only.** Phase 1 exposes and calls only tools that are on `PROXY_ALLOWLIST` (85 names, reviewed 2026-09-14) **and** declared `readOnlyHint: true` in the latest watched surface. `close_agent_position` is a reminder that annotations are hints: it describes itself as irreversible but is not declared destructive.
- **One path.** The `commander` profile's toolsets exclude `terminal`, `code_execution`, `file`, `browser`, `computer_use`, `delegation` and `cronjob`. Its skills never include the mcporter-based `battlegrid` skill. It holds `MANAGER_TOKEN`, never a BattleGrid credential.
- **MCP endpoint:** `http://127.0.0.1:8792/mcp`, Streamable HTTP, stateless; bearer `MANAGER_TOKEN` (401 missing, 403 wrong); DNS-rebinding protection with allowed hosts `127.0.0.1:8792` and `localhost:8792` (a foreign Host header gets 421, verified in a prototype).
- **One upstream session per process, owned by one worker task** (the SDK's client session must open and close in the same task; verified in a prototype: two HTTP sessions served by one worker, same-task open/close, clean shutdown).
- **Shared rate limit:** every service draws from one Postgres token bucket, 2 requests/second, bank 100 (server limit 3/s, 120).
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
| Hermes: `hermes profile create <name> --clone --description`, `--no-skills`; per-profile `platform_toolsets.cli`; dynamic MCP toolset `mcp-<server>`; `skills.external_dirs` with `${VAR}`; `mcp_servers.<name>.headers` with `${VAR}`; `hermes -p <name> mcp test <server>`; `hermes -p <name> chat -Q --oneshot -q "<question>"`; `hermes cron pause|remove <id>` | Hermes CLI help and docs, 0.21.1 |
| Sequential read latency about 0.72 s per call | `docs/phase-0/measurements.md` §4 |

## File structure

```
manager/proxy/__init__.py
manager/proxy/policy.py          PROXY_ALLOWLIST, decide_exposure()
manager/platform/shared_limit.py SharedTokenBucket (Postgres row lock)
manager/mcp/__init__.py
manager/mcp/gateway.py           PlatformGateway: one worker task owns the PlatformClient
manager/mcp/native.py            manager_fleet_report, manager_platform_changes, manager_ledger
manager/mcp/server.py            build_server(): list/call handlers
manager/mcp/app.py               build_http_app(): bearer + DNS-rebinding + lifespan
manager/commands/mcp.py          `python -m manager mcp`
manager/inventory/daily.py       render_daily_report()
hermes/install_commander.py      creates and configures the `commander` profile (run with Hermes' Python)
hermes/skills/battlegrid-manager/SKILL.md
scripts/check_shared_limiter.py  multi-process integration check against Postgres
tests/proxy/test_policy.py, tests/platform/test_shared_limit.py, tests/mcp/test_server.py, tests/mcp/test_app.py,
tests/inventory/test_daily.py, tests/hermes/test_install_commander.py
docs/phase-1/acceptance.md       transcripts and the numbers they were checked against
```

---

### Task 1: The watch stores full tool definitions, and an annotation change is drift

**Files:** Modify `manager/platform/client.py` (`list_tools`), `manager/platform/watch.py` (`observe`), `manager/scheduler/jobs.py` (`job_watch`); Test `tests/platform/test_watch.py`, `tests/platform/test_client.py`.

**Interfaces:**
- Produces: `PlatformClient.list_tools() -> list[dict]` with keys `name`, `description`, `inputSchema`, `annotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`; each `bool | None`). `observe()` hashes `{"inputSchema", "annotations"}` per tool and returns an extra key `definitions` (the list above, or `None` when unreadable). `job_watch` stores `surface_tools = {"observedAt", "contractVersion", "buildSha", "tools": definitions}` in system state whenever definitions are readable, and never stores `definitions` inside `surface`.

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

and add `"definitions": definitions,` to the returned dict. In `job_watch`, before `set_state(s, "surface", new)`:

```python
        definitions = new.pop("definitions", None)
        if definitions is not None:
            set_state(s, "surface_tools", {"observedAt": new["observedAt"], "contractVersion": new["contractVersion"],
                                           "buildSha": new["buildSha"], "tools": definitions})
```

Note for the operator: the first watch run after deploying this task records one `contract.drift` event, because every tool hash now includes annotations. That event is expected; acknowledge it with `contract ack`.

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
from sqlalchemy.orm import sessionmaker

from manager.db.models import RateBucket


class SharedTokenBucket:
    def __init__(self, session_factory: sessionmaker, key: str, rate: float, capacity: int,
                 clock: Callable[[], float] = time.time, sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self._sf, self.key, self.rate, self.capacity = session_factory, key, rate, float(capacity)
        self._clock, self._sleep = clock, sleep

    def _take(self) -> float:
        """Take one token if available and return 0, else return the seconds to wait. One transaction."""
        with self._sf() as s:
            row = s.scalar(select(RateBucket).where(RateBucket.key == self.key).with_for_update())
            now = self._clock()
            if row is None:
                row = RateBucket(key=self.key, tokens=self.capacity, updated_at=now)
                s.add(row)
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

**Files:** Create `manager/mcp/__init__.py`, `manager/mcp/gateway.py`, `manager/mcp/native.py`, `manager/mcp/server.py`, `tests/mcp/__init__.py`, `tests/mcp/test_server.py`.

**Interfaces:**
- Consumes: `decide_exposure`, `PlatformClient.call`, `render_inventory_report`, ledger `get_state`/`query`.
- Produces: `PlatformGateway(client)` with `async start()`, `async call(tool: str, args: dict) -> dict` (raises `PlatformError`), `async stop()`; `NATIVE_TOOLS: list[mcp.types.Tool]` named `manager_fleet_report`, `manager_platform_changes`, `manager_ledger`; `async call_native(name, args, session_factory) -> dict`; `build_server(gateway, session_factory) -> mcp.server.lowlevel.Server`.

- [ ] **Step 1: Failing tests**

```python
# tests/mcp/test_server.py
import json
from pathlib import Path

from mcp import Client

from manager.audit.ledger import set_state
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

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/mcp -q` → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/mcp/gateway.py
"""One worker task owns the upstream BattleGrid session; request handlers queue calls to it.

The MCP SDK's client session must be opened and closed in the same task. Handlers run in their own
tasks, so they never touch the session directly. Calls are served one at a time, which also keeps a
burst of questions from Hermes inside the shared rate limit.
"""
from __future__ import annotations

import asyncio
import logging

from manager.platform.errors import Kind, PlatformError

log = logging.getLogger(__name__)
_STOP = object()


class PlatformGateway:
    def __init__(self, client) -> None:
        self._client = client
        self._queue: asyncio.Queue = asyncio.Queue()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._serve(), name="platform-gateway")

    async def _serve(self) -> None:
        try:
            while True:
                item = await self._queue.get()
                if item is _STOP:
                    return
                tool, args, fut = item
                try:
                    result = await self._client.call(tool, args)
                except PlatformError as e:
                    if not fut.done():
                        fut.set_exception(e)
                except Exception as e:  # noqa: BLE001 - every failure reaches the caller as a typed error
                    if not fut.done():
                        fut.set_exception(PlatformError(Kind.TRANSPORT, f"{type(e).__name__}: {e}"))
                else:
                    if not fut.done():
                        fut.set_result(result)
        finally:
            aclose = getattr(self._client, "aclose", None)
            if aclose:
                await aclose()

    async def call(self, tool: str, args: dict) -> dict:
        if self._task is None or self._task.done():
            raise PlatformError(Kind.TRANSPORT, "the platform gateway is not running")
        fut = asyncio.get_running_loop().create_future()
        await self._queue.put((tool, args, fut))
        return await fut

    async def stop(self) -> None:
        if self._task and not self._task.done():
            await self._queue.put(_STOP)
            await self._task
```

```python
# manager/mcp/native.py
"""Tools the manager answers itself, from its own database. None of them calls BattleGrid."""
from __future__ import annotations

import mcp.types as t

from manager.audit.ledger import get_state, query
from manager.inventory.report import render_inventory_report
from manager.inventory.snapshot import latest

_RO = t.ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)

NATIVE_TOOLS: list[t.Tool] = [
    t.Tool(name="manager_fleet_report",
           description="The latest inventory snapshot as a markdown report: account, agents with Radar coins, the Radar "
                       "fleet with each coin's block, open positions, and any UNDETERMINED read. No platform call.",
           input_schema={"type": "object", "properties": {}, "additionalProperties": False}, annotations=_RO),
    t.Tool(name="manager_platform_changes",
           description="What the platform watch has seen: contract version, build, tool count, whether writes are blocked "
                       "pending acknowledgement, every recorded drift, and skill-pack refresh recommendations.",
           input_schema={"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 200}},
                         "additionalProperties": False}, annotations=_RO),
    t.Tool(name="manager_ledger",
           description="The manager's append-only audit ledger, newest first, optionally filtered by event kind "
                       "(e.g. snapshot.taken, panel.pulled, panel.fallback, contract.drift, safe.enter).",
           input_schema={"type": "object", "properties": {"kind": {"type": "string"},
                                                           "limit": {"type": "integer", "minimum": 1, "maximum": 500}},
                         "additionalProperties": False}, annotations=_RO),
]
NATIVE_NAMES = {tool.name for tool in NATIVE_TOOLS}


def call_native(name: str, args: dict, session_factory) -> dict:
    with session_factory() as s:
        if name == "manager_fleet_report":
            snap = latest(s)
            return {"markdown": render_inventory_report(s),
                    "snapshotTakenAt": snap.taken_at.isoformat() if snap else None}
        if name == "manager_platform_changes":
            limit = int(args.get("limit") or 20)
            surface = get_state(s, "surface", {})
            tools = surface.pop("tools", None)
            surface["tool_count"] = None if tools is None else len(tools)
            return {"surface": surface, "writes_blocked": get_state(s, "writes_blocked", {"blocked": False}),
                    "drift": [{"at": e.at.isoformat(), **e.payload} for e in query(s, kind="contract.drift", limit=limit)],
                    "pack": [{"at": e.at.isoformat(), **e.payload} for e in query(s, kind="pack.refresh_recommended", limit=5)]}
        if name == "manager_ledger":
            return {"events": [{"id": e.id, "at": e.at.isoformat(), "kind": e.kind, "payload": e.payload}
                               for e in query(s, kind=args.get("kind"), limit=int(args.get("limit") or 50))]}
    raise KeyError(name)
```

```python
# manager/mcp/server.py
"""The MCP server Hermes talks to: BattleGrid's read-only tools under their own names, plus native tools."""
from __future__ import annotations

import json

import mcp.types as t
from mcp.server.lowlevel import Server

from manager.audit.ledger import get_state
from manager.mcp.native import NATIVE_NAMES, NATIVE_TOOLS, call_native
from manager.platform.errors import PlatformError
from manager.proxy.policy import decide_exposure

SUFFIX = " (Served by battlegrid-manager, read-only.)"


def _result(body: dict, is_error: bool = False) -> t.CallToolResult:
    return t.CallToolResult(content=[t.TextContent(type="text", text=json.dumps(body))],
                            structured_content=None if is_error else body, is_error=is_error)


def build_server(gateway, session_factory) -> Server:
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
            return _result(call_native(name, args, session_factory))
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

### Task 5: HTTP app, the `mcp` service, and a live check

**Files:** Create `manager/mcp/app.py`, `manager/commands/mcp.py`, `tests/mcp/test_app.py`; Modify `compose.yaml`, `manager/commands/__init__.py`, `docs/phase-0/runbook.md` (services table).

**Interfaces:**
- Produces: `build_http_app(gateway, session_factory, token: str, port: int) -> Starlette`; `python -m manager mcp [--port 8792]`; Compose service `mcp` publishing `127.0.0.1:8792:8792`.

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
import uvicorn
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from manager.audit.ledger import set_state
from manager.db.session import init_db, make_engine, make_session_factory
from manager.mcp.app import build_http_app
from manager.mcp.gateway import PlatformGateway
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
```

- [ ] **Step 2: Run** `.venv/Scripts/python -m pytest tests/mcp/test_app.py -q` → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/mcp/app.py
from __future__ import annotations

import hmac
from contextlib import asynccontextmanager

from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.routing import Mount

from manager.mcp.server import build_server


class BearerAuth:
    """401 without a bearer token, 403 with the wrong one. Lifespan messages pass through untouched."""

    def __init__(self, app, token: str) -> None:
        self.app, self._token = app, token

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            header = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
            if not header.lower().startswith("bearer "):
                return await self._deny(send, 401, b"missing bearer token")
            if not hmac.compare_digest(header.split(" ", 1)[1].strip(), self._token):
                return await self._deny(send, 403, b"invalid token")
        await self.app(scope, receive, send)

    @staticmethod
    async def _deny(send, status: int, body: bytes) -> None:
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": body})


def build_http_app(gateway, session_factory, token: str, port: int) -> Starlette:
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

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → all pass. Live:

```bash
cd C:/Users/rafae/Documents/GitHub/battlegrid-manager && docker compose build api && docker compose up -d mcp watch && docker compose exec -T watch python -m manager run watch --every 600 --once && docker compose ps
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
- Produces: pure `merge_commander_config(config: dict, manager_repo: str) -> dict`; `set_env_line(text: str, key: str, value: str) -> str`; CLI `python hermes/install_commander.py [--dry-run]` run with **Hermes' own Python** (`C:/Users/rafae/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe`, PyYAML 6.0.3).

Behaviour, in order: (1) if `profiles/commander` does not exist, run `hermes profile create commander --clone --description "Talks with the user about the BattleGrid account through the battlegrid-manager MCP server; read-only in phase 1."`; (2) back up `config.yaml` and `.env` with a timestamp suffix; (3) delete `profiles/commander/skills/battlegrid` if present (the mcporter-based skill, which would bypass the manager) and print the remaining skill folders; (4) merge the config; (5) set `MANAGER_TOKEN` in the profile `.env` from the manager's `.env`; (6) run `hermes -p commander mcp test battlegrid_manager` and print its output.

- [ ] **Step 1: Failing tests** (run with the manager venv; the module must not import yaml at top level)

```python
# tests/hermes/test_install_commander.py
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("install_commander",
                                              Path(__file__).resolve().parents[2] / "hermes" / "install_commander.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)
REPO = "C:/Users/rafae/Documents/GitHub/battlegrid-manager"


def test_merge_adds_the_manager_server_toolsets_and_skill_dirs_without_losing_keys():
    base = {"model": {"default": "upstage/solar-pro4:free"}, "mcp_servers": {"other": {"url": "x"}},
            "platform_toolsets": {"cli": ["hermes-cli"], "telegram": ["hermes-telegram"]},
            "skills": {"creation_nudge_interval": 15}}
    out = mod.merge_commander_config(base, REPO)
    assert out["model"] == base["model"] and out["mcp_servers"]["other"] == {"url": "x"}
    server = out["mcp_servers"]["battlegrid_manager"]
    assert server["url"] == "http://127.0.0.1:8792/mcp" and server["headers"]["Authorization"] == "Bearer ${MANAGER_TOKEN}"
    assert server["supports_parallel_tool_calls"] is False and server["trust"] == "full"
    cli = out["platform_toolsets"]["cli"]
    assert "mcp-battlegrid_manager" in cli and "hermes-cli" not in cli
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
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# hermes/install_commander.py
"""Create and configure the Hermes `commander` profile. Run with Hermes' own Python (it has PyYAML).

Additive: the default Hermes profile is not modified. Backs up every file it changes.
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
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME_ROOT", str(Path.home() / "AppData" / "Local" / "hermes")))
HERMES = HERMES_HOME / "bin" / "hermes.exe"
PROFILE = HERMES_HOME / "profiles" / "commander"
MANAGER_REPO = Path(__file__).resolve().parents[1]
TOOLSETS = ["mcp-battlegrid_manager", "skills", "memory", "session_search", "todo", "clarify", "web"]


def merge_commander_config(config: dict, manager_repo: str) -> dict:
    out = copy.deepcopy(config or {})
    out.setdefault("mcp_servers", {})["battlegrid_manager"] = {
        "url": "http://127.0.0.1:8792/mcp",
        "headers": {"Authorization": "Bearer ${MANAGER_TOKEN}"},
        "trust": "full",
        "supports_parallel_tool_calls": False,
        "timeout": 180,
        "connect_timeout": 30,
    }
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


def main() -> int:
    import yaml  # Hermes' Python has PyYAML; the unit tests never reach this line

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if not PROFILE.exists():
        cmd = [str(HERMES), "profile", "create", "commander", "--clone", "--description",
               "Talks with the user about the BattleGrid account through the battlegrid-manager MCP server; "
               "read-only in phase 1."]
        print("run:", " ".join(cmd))
        if a.dry_run:
            return 0
        subprocess.run(cmd, check=True)
    for name in ("config.yaml", ".env"):
        if (PROFILE / name).exists():
            shutil.copy2(PROFILE / name, PROFILE / f"{name}.bak-{stamp}")
    legacy = PROFILE / "skills" / "battlegrid"
    if legacy.exists():
        print("removing the mcporter-based skill from the commander profile:", legacy)
        if not a.dry_run:
            shutil.rmtree(legacy)
    print("commander profile skills now:", sorted(p.name for p in (PROFILE / "skills").glob("*") if p.is_dir()))
    config_path = PROFILE / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    merged = merge_commander_config(config, MANAGER_REPO.as_posix())
    manager_env = (MANAGER_REPO / ".env").read_text(encoding="utf-8")
    token = re.search(r"^MANAGER_TOKEN=(.+)$", manager_env, re.M).group(1).strip()
    env_path = PROFILE / ".env"
    if a.dry_run:
        print(yaml.safe_dump({k: merged[k] for k in ("mcp_servers", "platform_toolsets", "skills")}, sort_keys=False))
        return 0
    config_path.write_text(yaml.safe_dump(merged, sort_keys=False, allow_unicode=True), encoding="utf-8")
    env_path.write_text(set_env_line(env_path.read_text(encoding="utf-8") if env_path.exists() else "", "MANAGER_TOKEN", token),
                        encoding="utf-8")
    test = subprocess.run([str(HERMES), "-p", "commander", "mcp", "test", "battlegrid_manager"],
                          capture_output=True, text=True, timeout=180)
    print(test.stdout[-3000:], test.stderr[-2000:])
    return test.returncode


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
Expected: the `mcp test` output lists the manager's tools. Then measure, do not assume, which tools a commander chat session actually has: `hermes -p commander chat -Q --oneshot -q "List the names of every tool you can call, one per line, and nothing else."` The answer must include `manager_fleet_report` and must not include `terminal`, `execute_code`, `write_file`, `browser_navigate` or `computer_use`. If it does, the platform key for this surface is not `cli`; find it with `hermes -p commander config show` and the toolsets reference, set it the same way, and repeat. Record the result in `docs/phase-1/acceptance.md`. Also open the Hermes desktop app, switch to the `commander` profile, and ask the same question, because desktop sessions may use a different platform key.

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
read-only tools under their real names and schemas, and adds three of its own. You have no other way to
reach the platform, and you have no write tools.

## Start here

- For "how is my account / fleet / radar / positions", call `manager_fleet_report` first. It is the latest
  snapshot, taken every five minutes, and costs no platform call. Say how old it is (`snapshotTakenAt`).
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
- Produces: `render_daily_report(s: Session, since: datetime) -> str`: the inventory report plus a "Since <since>" section listing ledger events of kinds `contract.drift`, `safe.enter`, `safe.exit`, `panel.fallback`, `panel.failed`, `pack.refresh_recommended` with timestamps, and counts of `snapshot.taken` and `panel.pulled`. `python -m manager report daily [--hours 24] [--out path]`.

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
        s.commit()
        md = render_daily_report(s, since=datetime.now(UTC) - timedelta(hours=24))
    assert "20 of 20 coins deployed" in md
    assert "contract.drift" in md and "ca61c5f1" in md
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

NOTABLE = ("contract.drift", "safe.enter", "safe.exit", "panel.fallback", "panel.failed", "pack.refresh_recommended")


def render_daily_report(s: Session, since: datetime) -> str:
    out = [render_inventory_report(s), "", f"## Since {since.isoformat()}", ""]
    events = [e for kind in NOTABLE for e in query(s, kind=kind, since=since, limit=500)]
    events.sort(key=lambda e: e.at)
    if events:
        out += [f"- {e.at.isoformat()} `{e.kind}` {json.dumps(e.payload)[:300]}" for e in events]
    else:
        out.append("No drift, safe-mode, panel-fallback, panel-failure or pack events.")
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

- [ ] **Step 4: Run** `.venv/Scripts/python -m pytest -q` → pass. Live: `docker compose exec -T api python -m manager report daily > docs/phase-1/daily-sample.md`.

- [ ] **Step 5: Retire the MAEZTRO cron — only after the user says yes in chat.** Show the user: the job id `da33cccb09f7`, its name "BattleGrid Daily Report (UTC 00:00)", that it calls BattleGrid through mcporter from `Documents/HERMES/PROJECT/MAEZTRO`, and the sample daily report above as its replacement. On a clear yes, pause (reversible), do not remove:

```bash
C:/Users/rafae/AppData/Local/hermes/bin/hermes.exe cron pause da33cccb09f7
```
Record the decision and date in `docs/phase-1/acceptance.md`. Removal (`hermes cron remove da33cccb09f7`) waits a week and needs a second yes.

- [ ] **Step 6: Commit** `"Daily report from the manager's own snapshots and ledger"`.

---

### Task 9: Acceptance and the exit gate

**Files:** Create `docs/phase-1/acceptance.md`.

- [ ] **Step 1: Three scripted questions, answers saved verbatim**

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
  2. The coins and blocks match a direct `scan_agent_coins` call through the manager for ROT Alpha's agent id (`9b38db6e-0970-4d02-aef7-1ef40e7a485f`), made within a minute.
  3. The answer says the manager cannot close or deploy yet, and the ledger shows no new events other than routine ones; `docker compose logs mcp` shows no call to any write tool.

  Record the questions, the answers, the comparison and any mismatch in `docs/phase-1/acceptance.md`. A mismatch is a finding, not a pass.

- [ ] **Step 3: Exit gate (the user)** — the user opens the Hermes desktop app, switches to the `commander` profile, asks their own questions, and confirms the answers are useful and correct. Then write the Phase 2 plan from the epic.

- [ ] **Step 4: Commit** `"Phase 1 acceptance record"`.
