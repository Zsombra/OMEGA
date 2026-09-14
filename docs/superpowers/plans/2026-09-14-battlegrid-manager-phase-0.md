# BattleGrid Manager — Phase 0: Foundations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `battlegrid-manager` repository and Docker stack with an OAuth-authenticated, rate-limited BattleGrid client, a database, inventory snapshots with diffs, an append-only audit ledger, the TPO panel logger in-process, a bearer-guarded REST API, a **platform watch** that detects drift (the platform moved 54.1.0 → 56.1.0 on planning day), and the **inventory report** of the real roster — plus the three phase-0 measurements recorded.

**Architecture:** One Python package `manager/` in a new repo, run by Docker Compose beside Postgres. `manager/platform/` is the only module that talks to BattleGrid (reads only in this phase). `manager/inventory/` turns five read tools into normalised rows and diffs. `manager/audit/` records everything. `manager/scheduler/` runs heartbeat/health/snapshot/panel jobs inside the FastAPI lifespan. No LLM anywhere. No BattleGrid write tool is called in this phase.

**Tech Stack:** Python 3.12, `mcp>=2.1` (Streamable HTTP client + `OAuthClientProvider`), `httpx`, FastAPI + uvicorn, SQLAlchemy 2.0 + psycopg (sqlite in unit tests), APScheduler 3.x, pydantic-settings, pytest + pytest-asyncio + respx, Docker Compose v2, Postgres 16.

## Global Constraints

- Rule 2 (one write path): this phase calls **only** these BattleGrid tools, all reads:
  `get_account_state`, `list_intelligence_agents`, `list_strategies`, `list_radar_deployments`,
  `list_user_active_positions`, `preview_strategy_report`, `get_coin_metadata`,
  `get_trading_config_catalog`, `list_approved_models`. The client enforces an allowlist;
  anything else raises before any network call.
- Rule 3: a failed read is recorded as `UNDETERMINED` with the error; never as empty.
- Rate limit: token bucket **2.0 requests/second, capacity 100**. On JSON-RPC `-32000` honour
  `retryAfter` (seconds) then retry once.
- Python `>=3.12`; Docker image `python:3.12-slim`; Postgres `16`.
- **Every backend job is its own Compose service** (one image; `python -m manager serve` or `python -m manager run <job>`), so any part of the backend is switched on or off with `docker compose stop|start <service>` or a profile. Nothing backend runs on the host. Hermes and the desktop app are not backend and stay on the host.
- Ports: manager API **8790**, OAuth callback listener **8791**, Hermes MCP **8792** (phase 1), Postgres internal only.
- Token store path inside the container: `/data/tokens/battlegrid.json`, mode `0600`, on a
  named volume. Never logged, never in the image.
- Contract version watched: `GET https://mcp.battlegrid.trade/mcp/version` →
  `{"name":"battlegrid","contractVersion":"54.1.0"}` today.
- All timestamps UTC ISO-8601 with `Z`.
- Repository location: `C:/Users/rafae/Documents/GitHub/battlegrid-manager` (sibling of
  OMEGA). Windows host; shell commands below are for Git Bash unless marked PowerShell.
- Commits: end messages with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

---

## File structure (locked in by this plan)

```
battlegrid-manager/
  pyproject.toml                 package + deps + pytest config
  compose.yaml                   postgres + one service per backend job (api, watch, inventory, panel)
  Dockerfile                     multi-stage, non-root, no secrets
  .env.example                   every variable the service reads
  .gitignore
  README.md
  manager/__init__.py
  manager/__main__.py            `python -m manager …` → cli.main()
  manager/cli.py                 argparse commands: auth, db, snapshot, report, panel, serve, measure, fixtures
  manager/settings.py            Settings (pydantic-settings)
  manager/platform/__init__.py
  manager/platform/errors.py     PlatformError(kind) and Kind enum
  manager/platform/ratelimit.py  TokenBucket
  manager/platform/tokens.py     FileTokenStorage (mcp TokenStorage protocol)
  manager/platform/client.py     PlatformClient: call(), version(), allowlist
  manager/platform/oauth_login.py  interactive login with callback listener
  manager/db/__init__.py
  manager/db/models.py           SQLAlchemy models
  manager/db/session.py          engine + session factory + init_db()
  manager/inventory/__init__.py
  manager/inventory/normalize.py five pure normalisers (dict → rows)
  manager/inventory/snapshot.py  take_snapshot(), latest(), diff()
  manager/inventory/report.py    render_inventory_report() → markdown
  manager/audit/__init__.py
  manager/audit/ledger.py        record(), query(); SystemState get/set
  manager/panel/__init__.py
  manager/panel/columns.py       COLUMNS, build_request, parse_table, to_number
  manager/panel/pull.py          pull_panel()
  manager/scheduler/__init__.py
  manager/scheduler/jobs.py      job functions; build_scheduler() = heartbeat + health only
  manager/commands/run.py        `run <job>`: one job as one process = one Compose service
  manager/api/__init__.py
  manager/api/app.py             FastAPI app + lifespan
  manager/api/auth.py            bearer dependency
  manager/measure/__init__.py
  manager/measure/notional.py    min-notional + LLM cost measurements
  tests/conftest.py
  tests/fixtures/2026-09-14/     recorded live responses (task 8)
  tests/test_settings.py … one test file per module
  docs/phase-0/oauth.md          DCR measurement record
  docs/phase-0/measurements.md   notional, LLM cost, rate headroom
  docs/phase-0/runbook.md        keep-awake, autostart, task retirement
  docs/phase-0/inventory-report.md  the deliverable
```

---

### Task 1: Repository scaffold, Compose, Dockerfile, smoke test

**Files:**
- Create: `pyproject.toml`, `compose.yaml`, `Dockerfile`, `.env.example`, `.gitignore`, `README.md`, `manager/__init__.py`, `manager/__main__.py`, `manager/cli.py`, `tests/conftest.py`, `tests/test_smoke.py`

**Interfaces:**
- Produces: package `manager` importable; `python -m manager --help` exits 0; `docker compose config` valid.

- [ ] **Step 1: Create the repository**

```bash
mkdir -p /c/Users/rafae/Documents/GitHub/battlegrid-manager && cd /c/Users/rafae/Documents/GitHub/battlegrid-manager && git init -b main
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "battlegrid-manager"
version = "0.0.1"
description = "Autonomous manager for a BattleGrid account, driven from Hermes; the only write path."
requires-python = ">=3.12"
dependencies = [
  "mcp>=2.1,<3",
  "httpx>=0.28",
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "sqlalchemy>=2.0",
  "psycopg[binary]>=3.2",
  "apscheduler>=3.10,<4",
  "pydantic>=2.7",
  "pydantic-settings>=2.4",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.24", "respx>=0.21", "ruff>=0.6"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["manager*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
line-length = 100
```

- [ ] **Step 3: Write `manager/__init__.py`, `manager/__main__.py`, `manager/cli.py`**

```python
# manager/__init__.py
"""battlegrid-manager: the only write path to the BattleGrid account (reads only in phase 0)."""
__version__ = "0.0.1"
```

```python
# manager/__main__.py
from manager.cli import main

raise SystemExit(main())
```

```python
# manager/cli.py
"""Command-line entry point. Subcommands are registered by later tasks via register()."""
from __future__ import annotations

import argparse
from collections.abc import Callable

_REGISTRY: dict[str, tuple[str, Callable[[argparse.ArgumentParser], None], Callable[[argparse.Namespace], int]]] = {}


def register(name: str, help_text: str, add_args: Callable[[argparse.ArgumentParser], None],
             run: Callable[[argparse.Namespace], int]) -> None:
    _REGISTRY[name] = (help_text, add_args, run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="manager", description="BattleGrid Manager")
    sub = parser.add_subparsers(dest="command")
    for name, (help_text, add_args, run) in _REGISTRY.items():
        p = sub.add_parser(name, help=help_text)
        add_args(p)
        p.set_defaults(_run=run)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Import command modules for their register() side effects.
    import manager.commands  # noqa: F401

    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "_run", None):
        parser.print_help()
        return 0
    return int(args._run(args))
```

```python
# manager/commands/__init__.py
"""Each module here calls manager.cli.register(...) at import time."""
```

- [ ] **Step 4: Write `compose.yaml`, `Dockerfile`, `.env.example`, `.gitignore`**

```yaml
# compose.yaml — one image, one service per backend job. Every job is switched on/off from Docker:
#   docker compose up -d                      core: postgres, api, watch, inventory
#   docker compose --profile panel up -d      also the TPO panel logger
#   docker compose stop watch                 switch one job off; `docker compose start watch` back on
#   docker compose ps                         what is running right now
# Later phases add: mcp (P1), triage [profile shadow] (P2), executor [profile live] (P3),
# review [profile live] (P4), eval [profile eval] (P6).
x-manager: &manager
  build: .
  image: battlegrid-manager:local
  env_file: .env
  environment:
    DATABASE_URL: postgresql+psycopg://manager:${POSTGRES_PASSWORD}@postgres:5432/manager
    TOKEN_PATH: /data/tokens/battlegrid.json
    PANEL_DIR: /data/panel
    PACK_DIR: /pack
  volumes:
    - tokens:/data/tokens
    - panel:/data/panel
    - ${PACK_HOST_DIR}:/pack:ro
  depends_on:
    postgres:
      condition: service_healthy
  restart: unless-stopped

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: manager
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: manager
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U manager -d manager"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped
  api:          # REST API + OAuth callback; heartbeat and health run inside this process
    <<: *manager
    ports:
      - "127.0.0.1:8790:8790"
      - "127.0.0.1:8791:8791"
    command: ["python", "-m", "manager", "serve"]
  watch:        # platform watch: version, build, per-tool schema hashes, pack freshness
    <<: *manager
    command: ["python", "-m", "manager", "run", "watch", "--every", "600"]
  inventory:    # account snapshots and diffs
    <<: *manager
    command: ["python", "-m", "manager", "run", "snapshot", "--every", "300"]
  panel:        # TPO panel logger, hourly at :05 UTC; opt-in
    <<: *manager
    profiles: ["panel"]
    command: ["python", "-m", "manager", "run", "panel", "--hourly-at", "5"]

volumes:
  tokens:
  panel:
  pgdata:
```

```dockerfile
# Dockerfile — one image for every service; the service's `command` picks the job.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN addgroup --system manager && adduser --system --ingroup manager manager \
 && mkdir -p /data/tokens /data/panel && chown -R manager:manager /data
COPY pyproject.toml ./
COPY manager ./manager
RUN pip install --no-cache-dir .
USER manager
EXPOSE 8790 8791 8792
CMD ["python", "-m", "manager", "serve"]
```

```bash
# .env.example  — copy to .env; never commit .env
POSTGRES_PASSWORD=change-me
MANAGER_TOKEN=change-me-long-random
BG_MCP_URL=https://mcp.battlegrid.trade/mcp
BG_VERSION_URL=https://mcp.battlegrid.trade/mcp/version
OAUTH_REDIRECT_URI=http://127.0.0.1:8791/callback
RATE_LIMIT_RPS=2.0
RATE_LIMIT_BURST=100
LOG_LEVEL=INFO
# Host folder of the vendor skill pack, mounted read-only for the platform watch
PACK_HOST_DIR=C:/Users/rafae/Documents/GitHub/OMEGA/.agents/skills/battlegrid
```

```gitignore
.env
__pycache__/
*.pyc
.pytest_cache/
.venv/
data/
```

- [ ] **Step 5: Write the smoke test**

```python
# tests/conftest.py
import os

os.environ.setdefault("MANAGER_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("POSTGRES_PASSWORD", "x")
```

```python
# tests/test_smoke.py
import manager
from manager.cli import main


def test_package_has_version():
    assert manager.__version__ == "0.0.1"


def test_cli_help_exits_zero(capsys):
    assert main([]) == 0
    assert "BattleGrid Manager" in capsys.readouterr().out
```

- [ ] **Step 6: Install and run**

```bash
python -m venv .venv && source .venv/Scripts/activate && pip install -e ".[dev]" && pytest -q
```
Expected: `2 passed`.

- [ ] **Step 7: Validate Compose and build the image**

```bash
cp .env.example .env && docker compose config --services && docker compose --profile panel config --services && docker compose build
```
Expected: the first list is `postgres api watch inventory`, the second adds `panel`; the image builds. (Services other than `postgres` fail to start until later tasks add `serve` and `run`; that is expected.)

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "Scaffold battlegrid-manager: package, CLI registry, Compose, Dockerfile

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Settings

**Files:**
- Create: `manager/settings.py`, `tests/test_settings.py`

**Interfaces:**
- Produces: `Settings` (pydantic-settings) with fields `database_url: str`, `manager_token: str`, `bg_mcp_url: str`, `bg_version_url: str`, `oauth_redirect_uri: str`, `token_path: str`, `panel_dir: str`, `rate_limit_rps: float`, `rate_limit_burst: int`, `log_level: str`; `get_settings() -> Settings` (cached).

- [ ] **Step 1: Failing test**

```python
# tests/test_settings.py
import pytest
from pydantic import ValidationError

from manager.settings import Settings


def test_defaults_and_required(monkeypatch):
    monkeypatch.setenv("MANAGER_TOKEN", "abc")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    s = Settings()
    assert s.bg_mcp_url == "https://mcp.battlegrid.trade/mcp"
    assert s.rate_limit_rps == 2.0 and s.rate_limit_burst == 100
    assert s.token_path.endswith("battlegrid.json")


def test_token_required(monkeypatch):
    monkeypatch.delenv("MANAGER_TOKEN", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
```

- [ ] **Step 2: Run** `pytest tests/test_settings.py -v` → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# manager/settings.py
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(alias="DATABASE_URL")
    manager_token: str = Field(alias="MANAGER_TOKEN", min_length=1)
    bg_mcp_url: str = Field(default="https://mcp.battlegrid.trade/mcp", alias="BG_MCP_URL")
    bg_version_url: str = Field(default="https://mcp.battlegrid.trade/mcp/version", alias="BG_VERSION_URL")
    oauth_redirect_uri: str = Field(default="http://127.0.0.1:8791/callback", alias="OAUTH_REDIRECT_URI")
    token_path: str = Field(default="./data/tokens/battlegrid.json", alias="TOKEN_PATH")
    panel_dir: str = Field(default="./data/panel", alias="PANEL_DIR")
    rate_limit_rps: float = Field(default=2.0, alias="RATE_LIMIT_RPS", gt=0, le=3.0)
    rate_limit_burst: int = Field(default=100, alias="RATE_LIMIT_BURST", gt=0, le=120)
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run** `pytest tests/test_settings.py -v` → PASS.
- [ ] **Step 5: Commit** `git add -A && git commit -m "Settings from environment, rate limit bounded below the measured server cap"` (with trailer).

---

### Task 3: Platform errors and the token-bucket rate limiter

**Files:**
- Create: `manager/platform/__init__.py`, `manager/platform/errors.py`, `manager/platform/ratelimit.py`, `tests/platform/test_ratelimit.py`, `tests/platform/test_errors.py`

**Interfaces:**
- Produces: `class Kind(str, Enum)`: `TRANSPORT, HTTP, RPC, RATE_LIMITED, AUTH, TOOL_ERROR, PARSE, NOT_ALLOWED, SAFE_MODE`; `class PlatformError(Exception)` with `.kind: Kind`, `.message: str`, `.status: int | None`, `.retry_after: float | None`, `.raw: str`; `class TokenBucket(rate: float, capacity: int, clock=time.monotonic)` with `async acquire() -> float` (seconds waited) and `available() -> float`.

- [ ] **Step 1: Failing tests**

```python
# tests/platform/test_errors.py
from manager.platform.errors import Kind, PlatformError


def test_error_carries_kind_and_retry_after():
    e = PlatformError(Kind.RATE_LIMITED, "Rate limited", status=None, retry_after=1.0, raw="{}")
    assert e.kind is Kind.RATE_LIMITED and e.retry_after == 1.0
    assert "RATE_LIMITED" in str(e)
```

```python
# tests/platform/test_ratelimit.py
import pytest

from manager.platform.ratelimit import TokenBucket


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


async def test_burst_then_wait():
    clock = FakeClock()
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)
        clock.t += s

    b = TokenBucket(rate=2.0, capacity=3, clock=clock, sleep=fake_sleep)
    for _ in range(3):
        assert await b.acquire() == 0.0
    waited = await b.acquire()
    assert waited == pytest.approx(0.5)
    assert b.available() == pytest.approx(0.0, abs=1e-9)


async def test_refills_over_time():
    clock = FakeClock()
    b = TokenBucket(rate=2.0, capacity=100, clock=clock)
    for _ in range(100):
        await b.acquire()
    clock.t += 10.0
    assert b.available() == pytest.approx(20.0)
```

- [ ] **Step 2: Run** `pytest tests/platform -v` → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/platform/__init__.py
"""The only module that talks to BattleGrid."""
```

```python
# manager/platform/errors.py
from __future__ import annotations

from enum import Enum


class Kind(str, Enum):
    TRANSPORT = "TRANSPORT"        # could not reach the URL
    HTTP = "HTTP"                  # server answered with a non-2xx
    RPC = "RPC"                    # JSON-RPC error other than rate limit
    RATE_LIMITED = "RATE_LIMITED"  # JSON-RPC -32000
    AUTH = "AUTH"                  # 401/403 or OAuth failure
    TOOL_ERROR = "TOOL_ERROR"      # CallToolResult.is_error
    PARSE = "PARSE"                # result could not be decoded
    NOT_ALLOWED = "NOT_ALLOWED"    # tool not in the allowlist
    SAFE_MODE = "SAFE_MODE"        # writes disabled (unused in phase 0)


class PlatformError(Exception):
    def __init__(self, kind: Kind, message: str, *, status: int | None = None,
                 retry_after: float | None = None, raw: str = "") -> None:
        super().__init__(f"[{kind.value}] {message}")
        self.kind, self.message, self.status, self.retry_after, self.raw = kind, message, status, retry_after, raw
```

```python
# manager/platform/ratelimit.py
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class TokenBucket:
    """Sustained `rate` tokens/second, at most `capacity` banked. Stays under the server's 3/s, 120."""

    def __init__(self, rate: float, capacity: int, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
        self.rate, self.capacity, self._clock, self._sleep = rate, float(capacity), clock, sleep
        self._tokens = float(capacity)
        self._last = clock()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
        self._last = now

    def available(self) -> float:
        self._refill()
        return self._tokens

    async def acquire(self) -> float:
        async with self._lock:
            self._refill()
            waited = 0.0
            if self._tokens < 1.0:
                waited = (1.0 - self._tokens) / self.rate
                await self._sleep(waited)
                self._refill()
            self._tokens -= 1.0
            return waited
```

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `"Platform error kinds and a token-bucket limiter at 2 r/s, bank 100"`.

---

### Task 4: File token storage

**Files:**
- Create: `manager/platform/tokens.py`, `tests/platform/test_tokens.py`

**Interfaces:**
- Consumes: `mcp.shared.auth.OAuthToken`, `OAuthClientInformationFull` (pydantic models from the SDK).
- Produces: `class FileTokenStorage(path: str)` implementing the SDK `TokenStorage` protocol: `async get_tokens() -> OAuthToken | None`, `async set_tokens(t)`, `async get_client_info() -> OAuthClientInformationFull | None`, `async set_client_info(c)`; file JSON `{"tokens": {...}|null, "client_info": {...}|null}`, mode 0600.

- [ ] **Step 1: Failing test**

```python
# tests/platform/test_tokens.py
import json
import os

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from manager.platform.tokens import FileTokenStorage


async def test_roundtrip_and_mode(tmp_path):
    p = tmp_path / "t" / "battlegrid.json"
    s = FileTokenStorage(str(p))
    assert await s.get_tokens() is None
    await s.set_tokens(OAuthToken(access_token="a", token_type="Bearer", refresh_token="r", expires_in=3600))
    await s.set_client_info(OAuthClientInformationFull(client_id="cid", redirect_uris=["http://127.0.0.1:8791/callback"]))
    again = FileTokenStorage(str(p))
    assert (await again.get_tokens()).refresh_token == "r"
    assert (await again.get_client_info()).client_id == "cid"
    raw = json.loads(p.read_text())
    assert set(raw) == {"tokens", "client_info"}
    if os.name != "nt":
        assert oct(p.stat().st_mode & 0o777) == "0o600"
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/platform/tokens.py
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.shared.auth import OAuthClientInformationFull, OAuthToken


class FileTokenStorage:
    """SDK TokenStorage protocol backed by one JSON file on the tokens volume."""

    def __init__(self, path: str) -> None:
        self._path = Path(path)

    def _read(self) -> dict:
        if not self._path.exists():
            return {"tokens": None, "client_info": None}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, self._path)

    async def get_tokens(self) -> OAuthToken | None:
        t = self._read()["tokens"]
        return OAuthToken.model_validate(t) if t else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        d = self._read(); d["tokens"] = tokens.model_dump(mode="json"); self._write(d)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        c = self._read()["client_info"]
        return OAuthClientInformationFull.model_validate(c) if c else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        d = self._read(); d["client_info"] = client_info.model_dump(mode="json"); self._write(d)
```

- [ ] **Step 4: Run** → PASS. If `OAuthToken`/`OAuthClientInformationFull` field names differ in the installed `mcp` version, run `python -c "from mcp.shared.auth import OAuthToken; print(OAuthToken.model_fields.keys())"` and use the printed names in the test; record the version in `docs/phase-0/oauth.md`.
- [ ] **Step 5: Commit** `"File-backed OAuth token storage on the tokens volume, mode 0600"`.

---

### Task 5: Platform client

**Files:**
- Create: `manager/platform/client.py`, `tests/platform/test_client.py`

**Interfaces:**
- Consumes: `TokenBucket`, `FileTokenStorage`, `PlatformError`, `Settings`.
- Produces: `class PlatformClient(settings: Settings, storage: FileTokenStorage, bucket: TokenBucket, http_client_factory=None)`; `READ_ALLOWLIST: frozenset[str]`; `async call(tool: str, args: dict | None = None) -> dict` (parsed JSON result); `async version() -> dict` (`{"name","contractVersion"}`); `async aclose()`. Also a `FakePlatform` test double in `tests/platform/fake.py`: `FakePlatform(responses: dict[str, dict | Exception])` with the same `call`/`version` signatures, used by every later task.

- [ ] **Step 1: Failing tests** (first create empty `tests/__init__.py`, `tests/platform/__init__.py`, and an empty `__init__.py` in every later `tests/<sub>/` folder, so `from tests.platform.fake import FakePlatform` resolves)

```python
# tests/platform/fake.py
from manager.platform.errors import Kind, PlatformError


class FakePlatform:
    """Test double for PlatformClient. responses maps tool name -> dict or Exception."""

    def __init__(self, responses: dict, version: dict | None = None):
        self.responses, self.calls = responses, []
        self._version = version or {"name": "battlegrid", "contractVersion": "54.1.0"}

    async def call(self, tool: str, args: dict | None = None) -> dict:
        self.calls.append((tool, args or {}))
        r = self.responses.get(tool)
        if r is None:
            raise PlatformError(Kind.TOOL_ERROR, f"no fixture for {tool}")
        if isinstance(r, Exception):
            raise r
        return r

    async def version(self) -> dict:
        return self._version
```

```python
# tests/platform/test_client.py
import json

import pytest

from manager.platform.client import READ_ALLOWLIST, PlatformClient, parse_call_result
from manager.platform.errors import Kind, PlatformError


def test_allowlist_is_reads_only():
    assert "get_account_state" in READ_ALLOWLIST
    assert "close_agent_position" not in READ_ALLOWLIST
    assert "apply_strategy_plan" not in READ_ALLOWLIST


async def test_call_refuses_non_allowlisted_before_network(settings, storage, bucket):
    c = PlatformClient(settings, storage, bucket)
    with pytest.raises(PlatformError) as ei:
        await c.call("close_agent_position", {"decisionId": "x", "confirm": True})
    assert ei.value.kind is Kind.NOT_ALLOWED


class _Content:
    def __init__(self, text): self.type, self.text = "text", text


class _Result:
    def __init__(self, text, is_error=False, structured=None):
        self.content, self.is_error, self.structured_content = [_Content(text)], is_error, structured


def test_parse_prefers_structured_content():
    assert parse_call_result(_Result('{"a":1}', structured={"a": 2})) == {"a": 2}


def test_parse_text_json():
    assert parse_call_result(_Result('{"a":1}')) == {"a": 1}


def test_parse_tool_error_raises_tool_error():
    with pytest.raises(PlatformError) as ei:
        parse_call_result(_Result("boom", is_error=True))
    assert ei.value.kind is Kind.TOOL_ERROR


def test_parse_rate_limit_text_raises_rate_limited():
    text = json.dumps({"code": -32000, "message": "Rate limited: 3 requests/second sustained, up to 120 banked. Retry after 1s"})
    with pytest.raises(PlatformError) as ei:
        parse_call_result(_Result(text, is_error=True))
    assert ei.value.kind is Kind.RATE_LIMITED and ei.value.retry_after == 1.0
```

```python
# tests/conftest.py  (append)
import pytest

from manager.platform.ratelimit import TokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.settings import Settings


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("MANAGER_TOKEN", "t")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("TOKEN_PATH", str(tmp_path / "battlegrid.json"))
    monkeypatch.setenv("PANEL_DIR", str(tmp_path / "panel"))
    return Settings(_env_file=None)


@pytest.fixture
def storage(settings):
    return FileTokenStorage(settings.token_path)


@pytest.fixture
def bucket():
    return TokenBucket(rate=100.0, capacity=100)
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/platform/client.py
"""The one BattleGrid session. Reads only in phase 0; the allowlist is enforced, not advisory."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx
from mcp import Client
from mcp.client.auth import OAuthClientProvider
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.auth import OAuthClientMetadata
from pydantic import AnyUrl

from manager.platform.errors import Kind, PlatformError
from manager.platform.ratelimit import TokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.settings import Settings

log = logging.getLogger(__name__)

READ_ALLOWLIST: frozenset[str] = frozenset({
    "get_account_state", "list_intelligence_agents", "list_strategies", "list_radar_deployments",
    "list_user_active_positions", "preview_strategy_report", "get_coin_metadata",
    "get_trading_config_catalog", "list_approved_models",
})

_RETRY_AFTER = re.compile(r"[Rr]etry after (\d+(?:\.\d+)?)s")


def parse_call_result(result: Any) -> dict:
    """Turn a CallToolResult into a dict, or raise the typed error the server encoded."""
    if getattr(result, "is_error", False):
        text = "".join(getattr(c, "text", "") for c in result.content)
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = {}
        code = body.get("code") if isinstance(body, dict) else None
        message = body.get("message", text) if isinstance(body, dict) else text
        if code == -32000 or "Rate limited" in message:
            m = _RETRY_AFTER.search(message)
            raise PlatformError(Kind.RATE_LIMITED, message, retry_after=float(m.group(1)) if m else 1.0, raw=text)
        raise PlatformError(Kind.TOOL_ERROR, message, raw=text)
    structured = getattr(result, "structured_content", None)
    if isinstance(structured, dict):
        return structured
    text = "".join(getattr(c, "text", "") for c in result.content)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise PlatformError(Kind.PARSE, f"result is not JSON: {e}", raw=text[:2000]) from e


class PlatformClient:
    def __init__(self, settings: Settings, storage: FileTokenStorage, bucket: TokenBucket,
                 http_client_factory=None) -> None:
        self._s, self._storage, self._bucket = settings, storage, bucket
        self._http_client_factory = http_client_factory or self._default_http
        self._http: httpx.AsyncClient | None = None
        self._client: Client | None = None
        self._lock = asyncio.Lock()

    def oauth_provider(self, redirect_handler=None, callback_handler=None) -> OAuthClientProvider:
        return OAuthClientProvider(
            server_url=self._s.bg_mcp_url,
            client_metadata=OAuthClientMetadata(
                client_name="battlegrid-manager",
                redirect_uris=[AnyUrl(self._s.oauth_redirect_uri)],
                scope="mcp:read mcp:wager",
            ),
            storage=self._storage,
            redirect_handler=redirect_handler,
            callback_handler=callback_handler,
        )

    def _default_http(self) -> httpx.AsyncClient:
        async def _no_interactive(_url: str) -> None:
            raise PlatformError(Kind.AUTH, "no OAuth session; run `python -m manager auth login`")
        return httpx.AsyncClient(auth=self.oauth_provider(redirect_handler=_no_interactive), follow_redirects=True, timeout=90)

    async def _session(self) -> Client:
        async with self._lock:
            if self._client is None:
                self._http = self._http_client_factory()
                transport = streamable_http_client(self._s.bg_mcp_url, http_client=self._http)
                self._client = Client(transport)
                await self._client.__aenter__()
            return self._client

    async def call(self, tool: str, args: dict | None = None) -> dict:
        if tool not in READ_ALLOWLIST:
            raise PlatformError(Kind.NOT_ALLOWED, f"{tool} is not on the phase-0 read allowlist")
        await self._bucket.acquire()
        try:
            client = await self._session()
            result = await client.call_tool(tool, args or {})
        except PlatformError:
            raise
        except httpx.HTTPStatusError as e:
            kind = Kind.AUTH if e.response.status_code in (401, 403) else Kind.HTTP
            raise PlatformError(kind, str(e), status=e.response.status_code, raw=e.response.text[:2000]) from e
        except httpx.HTTPError as e:
            raise PlatformError(Kind.TRANSPORT, str(e)) from e
        try:
            return parse_call_result(result)
        except PlatformError as e:
            if e.kind is Kind.RATE_LIMITED:
                await asyncio.sleep(e.retry_after or 1.0)
                await self._bucket.acquire()
                client = await self._session()
                return parse_call_result(await client.call_tool(tool, args or {}))
            raise

    async def version(self) -> dict:
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(self._s.bg_version_url)
        if r.status_code != 200:
            raise PlatformError(Kind.HTTP, f"version probe HTTP {r.status_code}", status=r.status_code, raw=r.text[:500])
        try:
            return r.json()
        except json.JSONDecodeError as e:
            raise PlatformError(Kind.PARSE, "version probe not JSON", raw=r.text[:500]) from e

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None
        if self._http is not None:
            await self._http.aclose()
            self._http = None
```

- [ ] **Step 4: Run** `pytest tests/platform -v` → PASS. If `from mcp import Client` or `streamable_http_client` do not import under the installed SDK, run `python -c "import mcp, inspect; print(mcp.__version__); import mcp.client.streamable_http as m; print([n for n in dir(m) if 'client' in n])"` and use the printed name; record the SDK version and the names used in `docs/phase-0/oauth.md`.
- [ ] **Step 5: Commit** `"Platform client: one OAuth session, read allowlist, typed errors, rate-limit retry"`.

---

### Task 6: OAuth login CLI and the DCR measurement

**Files:**
- Create: `manager/platform/oauth_login.py`, `manager/commands/auth.py`, `tests/platform/test_oauth_login.py`, `docs/phase-0/oauth.md`

**Interfaces:**
- Produces: `python -m manager auth login` (prints the authorization URL, listens on `0.0.0.0:8791/callback`, completes the flow, stores tokens); `python -m manager auth status` (prints whether tokens exist, expiry, client_id, and the live `version()`); `async wait_for_callback(port: int, timeout: float) -> AuthorizationCodeResult`.

- [ ] **Step 1: Failing test (the callback listener, no network to BattleGrid)**

```python
# tests/platform/test_oauth_login.py
import asyncio

import httpx

from manager.platform.oauth_login import wait_for_callback


async def test_listener_captures_code_and_state():
    task = asyncio.create_task(wait_for_callback(port=18791, timeout=5))
    await asyncio.sleep(0.2)
    async with httpx.AsyncClient() as h:
        r = await h.get("http://127.0.0.1:18791/callback?code=abc&state=xyz")
    assert r.status_code == 200 and "You can close this tab" in r.text
    result = await task
    assert result.code == "abc" and result.state == "xyz"
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/platform/oauth_login.py
from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlparse

from mcp.client.auth import AuthorizationCodeResult

_PAGE = b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n<h3>battlegrid-manager: login received. You can close this tab.</h3>"


async def wait_for_callback(port: int, timeout: float = 300.0) -> AuthorizationCodeResult:
    fut: asyncio.Future[AuthorizationCodeResult] = asyncio.get_running_loop().create_future()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        line = await reader.readline()
        path = line.split(b" ")[1].decode() if len(line.split(b" ")) > 1 else "/"
        params = parse_qs(urlparse(path).query)
        writer.write(_PAGE); await writer.drain(); writer.close()
        if "code" in params and not fut.done():
            fut.set_result(AuthorizationCodeResult(code=params["code"][0], state=params.get("state", [""])[0],
                                                   iss=params.get("iss", [None])[0]))

    server = await asyncio.start_server(handle, host="0.0.0.0", port=port)
    try:
        return await asyncio.wait_for(fut, timeout)
    finally:
        server.close(); await server.wait_closed()


async def login(client, port: int) -> None:
    """Drive the SDK's OAuth flow once; tokens land in FileTokenStorage."""
    import httpx
    from mcp import Client
    from mcp.client.streamable_http import streamable_http_client

    async def show(url: str) -> None:
        print("\nOpen this URL in your browser and approve access:\n\n  " + url + "\n")

    async def callback() -> AuthorizationCodeResult:
        return await wait_for_callback(port)

    provider = client.oauth_provider(redirect_handler=show, callback_handler=callback)
    async with httpx.AsyncClient(auth=provider, follow_redirects=True, timeout=300) as http:
        async with Client(streamable_http_client(client._s.bg_mcp_url, http_client=http)) as c:
            tools = await c.list_tools()
            print(f"authenticated; server exposes {len(tools.tools)} tools")
```

```python
# manager/commands/auth.py
from __future__ import annotations

import argparse
import asyncio

from manager.cli import register
from manager.platform.client import PlatformClient
from manager.platform.oauth_login import login
from manager.platform.ratelimit import TokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.settings import get_settings


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("action", choices=["login", "status"])
    p.add_argument("--port", type=int, default=8791)


def _run(a: argparse.Namespace) -> int:
    s = get_settings()
    storage = FileTokenStorage(s.token_path)
    client = PlatformClient(s, storage, TokenBucket(s.rate_limit_rps, s.rate_limit_burst))

    async def go() -> int:
        if a.action == "login":
            await login(client, a.port)
            return 0
        t = await storage.get_tokens(); ci = await storage.get_client_info()
        print("tokens:", "present" if t else "absent", "| client_id:", ci.client_id if ci else None)
        print("version:", await client.version())
        if t:
            acct = await client.call("get_account_state")
            print("account:", acct.get("username"), "| wallet:", acct.get("balance", {}).get("usdc"))
        await client.aclose()
        return 0

    return asyncio.run(go())


register("auth", "OAuth login / status against BattleGrid", _add, _run)
```

```python
# manager/commands/__init__.py  (replace)
from manager.commands import auth  # noqa: F401
```

- [ ] **Step 4: Run** `pytest tests/platform/test_oauth_login.py -v` → PASS.

- [ ] **Step 5: Live login (user at the keyboard; read-only)**

```bash
docker compose up -d postgres && docker compose run --rm --service-ports manager python -m manager auth login
```
Open the printed URL in the browser, approve. Expected last line: `authenticated; server exposes N tools`.
Then: `docker compose run --rm manager python -m manager auth status` → prints `account: ANBUJEFF | wallet: <number>`.

- [ ] **Step 6: The DCR measurement (does the new client revoke mcporter's?)**

```bash
cd /c/Users/rafae/Documents/GitHub/OMEGA && npx --no-install mcporter call battlegrid-anbu.get_account_state --output json --args '{}' | head -c 300
```
Record in `docs/phase-0/oauth.md`: the manager's `client_id` (from `auth status`), the granted `scope` (from the token file, secrets redacted), whether the mcporter call above still succeeds after the manager's login (**revoked: yes/no**), the SDK version, and the redirect URI registered. This is the phase-0 measurement #2 of the spec.

- [ ] **Step 7: Commit** `"OAuth login with an in-container callback listener; DCR measurement recorded"` (commit `docs/phase-0/oauth.md`; never the token file).

---

### Task 7: Database models and session

**Files:**
- Create: `manager/db/__init__.py`, `manager/db/models.py`, `manager/db/session.py`, `manager/commands/db.py`, `tests/db/test_models.py`

**Interfaces:**
- Produces: `Base`; models `Snapshot(id, taken_at, contract_version, reads: JSON)`, `AgentRow(snapshot_id, agent_id, display_name, status, model_id, strategy_id, strategy_revision, strategy_name, binding_state, has_active_assignments, trades, wins, losses, last24h_cost_usd, trading_config: JSON)`, `StrategyRow(snapshot_id, strategy_id, scope, name, timeframe, revision, is_active, bound_agent_count)`, `RadarPolicyRow(snapshot_id, policy_id, coin_id, timeframe, enabled, revision, agent_ids: JSON, section, qualification_block, last_fire_at)`, `PositionRow(snapshot_id, position_id, agent_id, coin, side, size_usd, entry, stop, take_profit, mark, unrealized_pnl_usd, pricing_status)`, `AuditEvent(id, at, kind, payload: JSON, dossier_hash)`, `Heartbeat(id, at, job, ok, note)`, `PanelRow(id, captured_at, coin, timeframe, raw_file, values: JSON)`, `SystemState(key, value: JSON, updated_at)`; `make_engine(url)`, `SessionLocal`, `init_db(engine)`; CLI `python -m manager db init`.

- [ ] **Step 1: Failing test**

```python
# tests/db/test_models.py
from datetime import UTC, datetime

from sqlalchemy import select

from manager.db.models import AgentRow, Snapshot, SystemState
from manager.db.session import init_db, make_engine, make_session_factory


def test_tables_create_and_roundtrip():
    engine = make_engine("sqlite+pysqlite:///:memory:")
    init_db(engine)
    Session = make_session_factory(engine)
    with Session() as s:
        snap = Snapshot(taken_at=datetime.now(UTC), contract_version="54.1.0", reads={"get_account_state": {"status": "OK"}})
        s.add(snap); s.flush()
        s.add(AgentRow(snapshot_id=snap.id, agent_id="a1", display_name="PVM Alpha", status="ACTIVE", model_id="z-ai/glm-5.3",
                       strategy_id="s1", strategy_revision=8, strategy_name="TPO", binding_state="BOUND",
                       has_active_assignments=False, trades=1, wins=1, losses=0, last24h_cost_usd=0.0, trading_config={"maxLeverage": 1}))
        s.add(SystemState(key="mode", value={"mode": "SHADOW"}, updated_at=datetime.now(UTC)))
        s.commit()
        assert s.scalar(select(AgentRow).where(AgentRow.agent_id == "a1")).trading_config["maxLeverage"] == 1
        assert s.get(SystemState, "mode").value["mode"] == "SHADOW"
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/db/__init__.py
```

```python
# manager/db/models.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    type_annotation_map = {dict: JSON, list: JSON}


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    contract_version: Mapped[str | None] = mapped_column(String(32))
    reads: Mapped[dict] = mapped_column(JSON)  # {tool: {"status": "OK"|"UNDETERMINED", "error": str|None, "generatedAt": str}}


class AgentRow(Base):
    __tablename__ = "agents"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"), index=True)
    agent_id: Mapped[str] = mapped_column(String(36), index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))
    model_id: Mapped[str | None] = mapped_column(String(64))
    strategy_id: Mapped[str | None] = mapped_column(String(36))
    strategy_revision: Mapped[int | None] = mapped_column(Integer)
    strategy_name: Mapped[str | None] = mapped_column(String(256))
    binding_state: Mapped[str | None] = mapped_column(String(16))
    has_active_assignments: Mapped[bool] = mapped_column(Boolean, default=False)
    trades: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)
    last24h_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    trading_config: Mapped[dict] = mapped_column(JSON, default=dict)


class StrategyRow(Base):
    __tablename__ = "strategies"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"), index=True)
    strategy_id: Mapped[str] = mapped_column(String(36), index=True)
    scope: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(256))
    timeframe: Mapped[str | None] = mapped_column(String(8))
    revision: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean)
    bound_agent_count: Mapped[int] = mapped_column(Integer, default=0)


class RadarPolicyRow(Base):
    __tablename__ = "radar_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"), index=True)
    policy_id: Mapped[str] = mapped_column(String(36))
    coin_id: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    enabled: Mapped[bool] = mapped_column(Boolean)
    revision: Mapped[int] = mapped_column(Integer)
    agent_ids: Mapped[list] = mapped_column(JSON)
    section: Mapped[str | None] = mapped_column(String(32))
    qualification_block: Mapped[str | None] = mapped_column(String(64))
    last_fire_at: Mapped[str | None] = mapped_column(String(40))


class PositionRow(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_id: Mapped[int] = mapped_column(ForeignKey("snapshots.id"), index=True)
    position_id: Mapped[str] = mapped_column(String(36), index=True)
    agent_id: Mapped[str] = mapped_column(String(36))
    coin: Mapped[str] = mapped_column(String(32))
    side: Mapped[str] = mapped_column(String(8))
    size_usd: Mapped[float | None] = mapped_column(Float)
    entry: Mapped[float | None] = mapped_column(Float)
    stop: Mapped[float | None] = mapped_column(Float)
    take_profit: Mapped[float | None] = mapped_column(Float)
    mark: Mapped[float | None] = mapped_column(Float)
    unrealized_pnl_usd: Mapped[float | None] = mapped_column(Float)
    pricing_status: Mapped[str | None] = mapped_column(String(32))
    raw: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    dossier_hash: Mapped[str | None] = mapped_column(String(64))


class Heartbeat(Base):
    __tablename__ = "heartbeats"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    job: Mapped[str] = mapped_column(String(32))
    ok: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(Text)


class PanelRow(Base):
    __tablename__ = "panel_rows"
    id: Mapped[int] = mapped_column(primary_key=True)
    captured_at: Mapped[str] = mapped_column(String(24), index=True)
    coin: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(8))
    raw_file: Mapped[str] = mapped_column(String(64))
    values: Mapped[dict] = mapped_column(JSON)


class SystemState(Base):
    __tablename__ = "system_state"
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

```python
# manager/db/session.py
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from manager.db.models import Base


def make_engine(url: str) -> Engine:
    kw = {"future": True}
    if url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool
        kw.update(connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, **kw)


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
```

```python
# manager/commands/db.py
import argparse

from manager.cli import register
from manager.db.session import init_db, make_engine
from manager.settings import get_settings


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("action", choices=["init"])


def _run(a: argparse.Namespace) -> int:
    init_db(make_engine(get_settings().database_url))
    print("db: tables ensured")
    return 0


register("db", "Database maintenance", _add, _run)
```
Add `from manager.commands import db  # noqa: F401` to `manager/commands/__init__.py`.

- [ ] **Step 4: Run** → PASS. Then `docker compose run --rm manager python -m manager db init` → `db: tables ensured`.
- [ ] **Step 5: Commit** `"Database models for snapshots, rows, audit, heartbeats, panel, system state"`.

---

### Task 8: Record live fixtures and write the normalisers

**Files:**
- Create: `manager/commands/fixtures.py`, `tests/fixtures/2026-09-14/{get_account_state,list_intelligence_agents,list_strategies,list_radar_deployments,list_user_active_positions}.json`, `manager/inventory/__init__.py`, `manager/inventory/normalize.py`, `tests/inventory/test_normalize.py`

**Interfaces:**
- Produces: `python -m manager fixtures record --out tests/fixtures/<date>` (five reads, raw JSON to disk, read-only); pure functions `normalize_agents(payload) -> list[dict]`, `normalize_strategies(payload) -> list[dict]`, `normalize_radar(payload) -> tuple[list[dict], dict]` (rows, summary), `normalize_positions(payload) -> tuple[list[dict], dict]` (rows, totals), `normalize_account(payload) -> dict` (`username, wallet_usdc, slots_used, slots_limit, wager_enabled, llm_allowed`). Each returned dict's keys match the model columns of Task 7 exactly.

- [ ] **Step 1: Write the fixture recorder and record (live, read-only)**

```python
# manager/commands/fixtures.py
import argparse
import asyncio
import json
from pathlib import Path

from manager.cli import register
from manager.platform.client import PlatformClient
from manager.platform.ratelimit import TokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.settings import get_settings

FIVE = ["get_account_state", "list_intelligence_agents", "list_strategies", "list_radar_deployments", "list_user_active_positions"]


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("action", choices=["record"])
    p.add_argument("--out", required=True)


def _run(a: argparse.Namespace) -> int:
    s = get_settings()
    client = PlatformClient(s, FileTokenStorage(s.token_path), TokenBucket(s.rate_limit_rps, s.rate_limit_burst))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

    async def go() -> int:
        for tool in FIVE:
            data = await client.call(tool)
            (out / f"{tool}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
            print("recorded", tool)
        await client.aclose()
        return 0

    return asyncio.run(go())


register("fixtures", "Record read-only fixtures from the live platform", _add, _run)
```
Add to `manager/commands/__init__.py`. Then:
```bash
docker compose run --rm -v "$PWD/tests:/app/tests" manager python -m manager fixtures record --out tests/fixtures/2026-09-14
```
Expected: five files. Inspect `list_intelligence_agents.json`: nine agents, all `modelId` `z-ai/glm-5.3`; `list_radar_deployments.json` `summary.coinsDeployed == 20`.

- [ ] **Step 2: Failing tests against the fixtures**

```python
# tests/inventory/test_normalize.py
import json
from pathlib import Path

import pytest

from manager.inventory.normalize import (normalize_account, normalize_agents, normalize_positions,
                                         normalize_radar, normalize_strategies)

FX = Path(__file__).resolve().parents[1] / "fixtures" / "2026-09-14"


def load(name):
    return json.loads((FX / f"{name}.json").read_text(encoding="utf-8"))


def test_account():
    a = normalize_account(load("get_account_state"))
    assert a["username"] == "ANBUJEFF" and a["slots_limit"] == 24 and a["wager_enabled"] is True
    assert a["wallet_usdc"] == pytest.approx(float(load("get_account_state")["balance"]["usdc"]))


def test_agents_nine_rows_all_glm():
    rows = normalize_agents(load("list_intelligence_agents"))
    assert len(rows) == 9 and {r["model_id"] for r in rows} == {"z-ai/glm-5.3"}
    struct = next(r for r in rows if r["display_name"] == "STRUCT Alpha")
    assert struct["trades"] == 15 and struct["wins"] == 9 and struct["losses"] == 6
    assert struct["trading_config"]["maxConcurrentExposureUsd"] == 100


def test_strategies_split_system_private():
    rows = normalize_strategies(load("list_strategies"))
    assert sum(r["scope"] == "SYSTEM" for r in rows) == 12
    assert any(r["strategy_id"].startswith("3d720de3") and r["revision"] == 8 for r in rows)


def test_radar_twenty_policies_and_summary():
    rows, summary = normalize_radar(load("list_radar_deployments"))
    assert len(rows) == 20 and summary["coinsDeployed"] == 20 and summary["coinCap"] == 20
    assert all(r["qualification_block"] == "AGGREGATE_BELOW_MIN" for r in rows)
    assert all(len(r["agent_ids"]) == 1 for r in rows)


def test_positions_empty_but_priced():
    rows, totals = normalize_positions(load("list_user_active_positions"))
    assert rows == [] and totals["pricingStatus"] == "LIVE"
```

- [ ] **Step 3: Run** → FAIL.

- [ ] **Step 4: Implement**

```python
# manager/inventory/__init__.py
```

```python
# manager/inventory/normalize.py
"""Pure functions: raw tool payload -> row dicts whose keys match manager.db.models columns."""
from __future__ import annotations


def _f(x):
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def normalize_account(p: dict) -> dict:
    slots = p.get("agentSlots", {})
    return {
        "username": p.get("username"),
        "wallet_usdc": _f(p.get("balance", {}).get("usdc")),
        "slots_used": slots.get("used"), "slots_limit": slots.get("limit"),
        "wager_enabled": bool(p.get("mcpWagerEnabled")),
        "llm_allowed": bool(p.get("llmAccess", {}).get("allowed")),
    }


def normalize_agents(p: dict) -> list[dict]:
    rows = []
    for a in p.get("agents", []):
        ts = a.get("performance", {}).get("tradeStats", {})
        wl = ts.get("winLoss", {})
        rows.append({
            "agent_id": a["id"], "display_name": a.get("displayName", ""), "status": a.get("status", ""),
            "model_id": a.get("modelId"), "strategy_id": a.get("strategyId"),
            "strategy_revision": a.get("strategyRevision"), "strategy_name": a.get("strategyName"),
            "binding_state": a.get("bindingState"), "has_active_assignments": bool(a.get("hasActiveAssignments")),
            "trades": int(ts.get("trades") or 0), "wins": int(wl.get("wins") or 0), "losses": int(wl.get("losses") or 0),
            "last24h_cost_usd": float(a.get("last24hCostUsd") or 0.0), "trading_config": a.get("tradingConfig") or {},
        })
    return rows


def normalize_strategies(p: dict) -> list[dict]:
    return [{
        "strategy_id": s["id"], "scope": s.get("scope", ""), "name": s.get("name", ""),
        "timeframe": s.get("timeframe"), "revision": int(s.get("revision") or 0),
        "is_active": bool(s.get("isActive")), "bound_agent_count": int(s.get("boundAgentCount") or 0),
    } for s in p.get("strategies", [])]


def normalize_radar(p: dict) -> tuple[list[dict], dict]:
    rows = []
    for pol in p.get("policies", []):
        rn = pol.get("resolvesNow", {}) or {}
        rows.append({
            "policy_id": pol["policyId"], "coin_id": pol["coinId"], "timeframe": pol.get("deploymentTimeframe", ""),
            "enabled": bool(pol.get("enabled")), "revision": int(pol.get("revision") or 0),
            "agent_ids": [s["agentId"] for s in pol.get("slots", [])],
            "section": rn.get("section"), "qualification_block": rn.get("qualificationBlock"),
            "last_fire_at": rn.get("lastFireAt"),
        })
    return rows, p.get("summary", {})


def normalize_positions(p: dict) -> tuple[list[dict], dict]:
    rows = []
    for pos in p.get("positions", []):
        rows.append({
            "position_id": pos.get("positionId") or pos.get("id") or "", "agent_id": pos.get("agentId", ""),
            "coin": pos.get("coinTicker") or pos.get("coin", ""), "side": pos.get("side", ""),
            "size_usd": _f(pos.get("currentNotionalUsd") or pos.get("notionalUsd")), "entry": _f(pos.get("entryPrice")),
            "stop": _f(pos.get("effectiveStopLoss") or pos.get("stopLoss")), "take_profit": _f(pos.get("takeProfit")),
            "mark": _f(pos.get("markPrice")), "unrealized_pnl_usd": _f(pos.get("unrealizedPnlUsd")),
            "pricing_status": pos.get("pricingStatus"), "raw": pos,
        })
    return rows, p.get("totals", {})
```
The position field names above are the ones the spec's tool descriptions name (`unrealizedPnlUsd`, `roePct`, `markPrice`, `pricingStatus`); the entry/stop/TP keys are **not yet observed** because no position was open on 2026-09-14. `raw` keeps the whole row so nothing is lost; the first open position seen in phase 2 fixes the names (record it as a fixture then).

- [ ] **Step 5: Run** → PASS.
- [ ] **Step 6: Commit** `"Live fixtures 2026-09-14 (read-only) and pure normalisers for the five inventory reads"`.

---

### Task 9: Inventory snapshot, diff, UNDETERMINED reads

**Files:**
- Create: `manager/inventory/snapshot.py`, `manager/commands/snapshot.py`, `tests/inventory/test_snapshot.py`

**Interfaces:**
- Consumes: `PlatformClient.call/version`, normalisers, models.
- Produces: `async take_snapshot(client, session_factory) -> int` (snapshot id); `latest(session) -> Snapshot | None`; `diff(session, older_id: int, newer_id: int) -> dict` with keys `agents_added, agents_removed, agents_changed, radar_added, radar_removed, positions_opened, positions_closed` (lists of ids); CLI `python -m manager snapshot`.

- [ ] **Step 1: Failing tests**

```python
# tests/inventory/test_snapshot.py
import json
from pathlib import Path

from sqlalchemy import select

from manager.db.models import AgentRow, RadarPolicyRow, Snapshot
from manager.db.session import init_db, make_engine, make_session_factory
from manager.inventory.snapshot import diff, latest, take_snapshot
from manager.platform.errors import Kind, PlatformError
from tests.platform.fake import FakePlatform

FX = Path(__file__).resolve().parents[1] / "fixtures" / "2026-09-14"


def fixtures():
    return {n: json.loads((FX / f"{n}.json").read_text(encoding="utf-8")) for n in
            ["get_account_state", "list_intelligence_agents", "list_strategies", "list_radar_deployments", "list_user_active_positions"]}


def db():
    e = make_engine("sqlite+pysqlite:///:memory:"); init_db(e); return make_session_factory(e)


async def test_snapshot_writes_rows_and_read_status():
    Session = db()
    sid = await take_snapshot(FakePlatform(fixtures()), Session)
    with Session() as s:
        snap = s.get(Snapshot, sid)
        assert snap.contract_version == "54.1.0"
        assert all(v["status"] == "OK" for v in snap.reads.values())
        assert s.scalar(select(AgentRow).where(AgentRow.snapshot_id == sid, AgentRow.display_name == "PVM Alpha")) is not None
        assert len(s.scalars(select(RadarPolicyRow).where(RadarPolicyRow.snapshot_id == sid)).all()) == 20


async def test_failed_read_is_undetermined_not_empty():
    fx = fixtures(); fx["list_radar_deployments"] = PlatformError(Kind.HTTP, "502", status=502)
    Session = db()
    sid = await take_snapshot(FakePlatform(fx), Session)
    with Session() as s:
        snap = s.get(Snapshot, sid)
        assert snap.reads["list_radar_deployments"]["status"] == "UNDETERMINED"
        assert "502" in snap.reads["list_radar_deployments"]["error"]
        assert s.scalars(select(RadarPolicyRow).where(RadarPolicyRow.snapshot_id == sid)).all() == []


async def test_diff_detects_removed_agent():
    fx = fixtures(); Session = db()
    a = await take_snapshot(FakePlatform(fx), Session)
    fx2 = json.loads(json.dumps(fx)); fx2["list_intelligence_agents"]["agents"].pop()
    b = await take_snapshot(FakePlatform(fx2), Session)
    with Session() as s:
        d = diff(s, a, b)
        assert len(d["agents_removed"]) == 1 and d["agents_added"] == []
        assert latest(s).id == b
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/inventory/snapshot.py
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from manager.db.models import AgentRow, PositionRow, RadarPolicyRow, Snapshot, StrategyRow
from manager.inventory.normalize import (normalize_agents, normalize_positions, normalize_radar,
                                         normalize_strategies)
from manager.platform.errors import PlatformError

READS = ["get_account_state", "list_intelligence_agents", "list_strategies", "list_radar_deployments", "list_user_active_positions"]


async def _read(client, tool: str) -> tuple[dict | None, dict]:
    at = datetime.now(UTC).isoformat()
    try:
        return await client.call(tool), {"status": "OK", "error": None, "generatedAt": at}
    except PlatformError as e:
        return None, {"status": "UNDETERMINED", "error": f"{e.kind.value}: {e.message}", "generatedAt": at}


async def take_snapshot(client, session_factory: sessionmaker) -> int:
    payloads: dict[str, dict | None] = {}
    reads: dict[str, dict] = {}
    for tool in READS:
        payloads[tool], reads[tool] = await _read(client, tool)
    try:
        version = (await client.version()).get("contractVersion")
    except PlatformError:
        version = None
    with session_factory() as s:
        snap = Snapshot(taken_at=datetime.now(UTC), contract_version=version, reads=reads)
        if payloads["get_account_state"]:
            snap.reads["get_account_state"]["account"] = payloads["get_account_state"].get("balance", {})
        s.add(snap); s.flush()
        if payloads["list_intelligence_agents"]:
            s.add_all(AgentRow(snapshot_id=snap.id, **r) for r in normalize_agents(payloads["list_intelligence_agents"]))
        if payloads["list_strategies"]:
            s.add_all(StrategyRow(snapshot_id=snap.id, **r) for r in normalize_strategies(payloads["list_strategies"]))
        if payloads["list_radar_deployments"]:
            rows, summary = normalize_radar(payloads["list_radar_deployments"])
            snap.reads["list_radar_deployments"]["summary"] = summary
            s.add_all(RadarPolicyRow(snapshot_id=snap.id, **r) for r in rows)
        if payloads["list_user_active_positions"]:
            rows, totals = normalize_positions(payloads["list_user_active_positions"])
            snap.reads["list_user_active_positions"]["totals"] = totals
            s.add_all(PositionRow(snapshot_id=snap.id, **r) for r in rows)
        s.commit()
        return snap.id


def latest(s: Session) -> Snapshot | None:
    return s.scalar(select(Snapshot).order_by(Snapshot.id.desc()).limit(1))


def _ids(s: Session, model, key, sid: int) -> dict:
    return {getattr(r, key): r for r in s.scalars(select(model).where(model.snapshot_id == sid)).all()}


def diff(s: Session, older_id: int, newer_id: int) -> dict:
    a, b = _ids(s, AgentRow, "agent_id", older_id), _ids(s, AgentRow, "agent_id", newer_id)
    ra, rb = _ids(s, RadarPolicyRow, "coin_id", older_id), _ids(s, RadarPolicyRow, "coin_id", newer_id)
    pa, pb = _ids(s, PositionRow, "position_id", older_id), _ids(s, PositionRow, "position_id", newer_id)
    changed = [k for k in a.keys() & b.keys() if (a[k].strategy_revision, a[k].status, a[k].model_id, a[k].trading_config)
               != (b[k].strategy_revision, b[k].status, b[k].model_id, b[k].trading_config)]
    return {
        "agents_added": sorted(b.keys() - a.keys()), "agents_removed": sorted(a.keys() - b.keys()), "agents_changed": sorted(changed),
        "radar_added": sorted(rb.keys() - ra.keys()), "radar_removed": sorted(ra.keys() - rb.keys()),
        "positions_opened": sorted(pb.keys() - pa.keys()), "positions_closed": sorted(pa.keys() - pb.keys()),
    }
```

```python
# manager/commands/snapshot.py
import argparse
import asyncio

from manager.cli import register
from manager.db.session import make_engine, make_session_factory
from manager.inventory.snapshot import take_snapshot
from manager.platform.client import PlatformClient
from manager.platform.ratelimit import TokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.settings import get_settings


def _add(p: argparse.ArgumentParser) -> None:
    pass


def _run(a: argparse.Namespace) -> int:
    s = get_settings()
    client = PlatformClient(s, FileTokenStorage(s.token_path), TokenBucket(s.rate_limit_rps, s.rate_limit_burst))
    Session = make_session_factory(make_engine(s.database_url))

    async def go() -> int:
        sid = await take_snapshot(client, Session)
        await client.aclose()
        print("snapshot", sid)
        return 0

    return asyncio.run(go())


register("snapshot", "Take one inventory snapshot now", _add, _run)
```
Register in `manager/commands/__init__.py`.

- [ ] **Step 4: Run** → PASS; then `docker compose run --rm manager python -m manager snapshot` → `snapshot 1`.
- [ ] **Step 5: Commit** `"Inventory snapshots with per-read UNDETERMINED status and diffs"`.

---

### Task 10: Audit ledger and system state

**Files:**
- Create: `manager/audit/__init__.py`, `manager/audit/ledger.py`, `tests/audit/test_ledger.py`

**Interfaces:**
- Produces: `record(session, kind: str, payload: dict, dossier_hash: str | None = None) -> int`; `query(session, kind: str | None = None, since: datetime | None = None, limit: int = 100) -> list[AuditEvent]`; `get_state(session, key: str, default: dict) -> dict`; `set_state(session, key: str, value: dict) -> None`. Keys used in phase 0: `"mode"` (`{"mode": "SHADOW"}`), `"safe"` (`{"safe": bool, "reason": str|None, "since": str|None}`), `"paused"` (`{"paused": bool}`), `"contract"` (`{"acknowledged": "54.1.0"}`).

- [ ] **Step 1: Failing test**

```python
# tests/audit/test_ledger.py
from datetime import UTC, datetime, timedelta

from manager.audit.ledger import get_state, query, record, set_state
from manager.db.session import init_db, make_engine, make_session_factory


def test_record_query_and_state():
    e = make_engine("sqlite+pysqlite:///:memory:"); init_db(e); Session = make_session_factory(e)
    with Session() as s:
        record(s, "snapshot.taken", {"id": 1}); record(s, "safe.enter", {"reason": "502"}); s.commit()
        assert [x.kind for x in query(s)] == ["safe.enter", "snapshot.taken"]
        assert query(s, kind="safe.enter")[0].payload["reason"] == "502"
        assert query(s, since=datetime.now(UTC) + timedelta(seconds=1)) == []
        assert get_state(s, "mode", {"mode": "SHADOW"})["mode"] == "SHADOW"
        set_state(s, "safe", {"safe": True, "reason": "502", "since": "x"}); s.commit()
        assert get_state(s, "safe", {})["safe"] is True
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/audit/__init__.py
```

```python
# manager/audit/ledger.py
"""Append-only. There is no update or delete function here on purpose."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from manager.db.models import AuditEvent, SystemState


def record(s: Session, kind: str, payload: dict, dossier_hash: str | None = None) -> int:
    ev = AuditEvent(at=datetime.now(UTC), kind=kind, payload=payload, dossier_hash=dossier_hash)
    s.add(ev); s.flush()
    return ev.id


def query(s: Session, kind: str | None = None, since: datetime | None = None, limit: int = 100) -> list[AuditEvent]:
    q = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if kind:
        q = q.where(AuditEvent.kind == kind)
    if since:
        q = q.where(AuditEvent.at >= since)
    return list(s.scalars(q).all())


def get_state(s: Session, key: str, default: dict) -> dict:
    row = s.get(SystemState, key)
    return dict(row.value) if row else dict(default)


def set_state(s: Session, key: str, value: dict) -> None:
    row = s.get(SystemState, key)
    if row is None:
        s.add(SystemState(key=key, value=value, updated_at=datetime.now(UTC)))
    else:
        row.value, row.updated_at = value, datetime.now(UTC)
```

- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `"Append-only audit ledger and system state flags"`.

---

### Task 11: TPO panel logger in-process

**Files:**
- Create: `manager/panel/__init__.py`, `manager/panel/columns.py`, `manager/panel/pull.py`, `manager/commands/panel.py`, `tests/panel/test_columns.py`, `tests/panel/test_pull.py`, `tests/fixtures/panel/preview_strategy_report.json` (recorded live)

**Interfaces:**
- Consumes: `PlatformClient.call("preview_strategy_report", request)` (allowlisted).
- Produces: `COLUMNS` (the 17 column tuples from OMEGA's `scripts/tpo_panel_pull.py`, copied verbatim), `build_request(timeframe: str, category: str, limit: int) -> dict`, `parse_table(text: str) -> tuple[list[str] | None, list[dict]]`, `to_number(cell) -> float | str | None`; `async pull_panel(client, session_factory, panel_dir: str, timeframe="1h", category="CRYPTO", limit=50) -> int` (rows written; raw response saved to `<panel_dir>/raw/<stamp>.json` BEFORE parsing; a failed pull writes zero rows and records `panel.failed` in the ledger); CLI `python -m manager panel pull`.

- [ ] **Step 1: Copy the column list and parsers from OMEGA**

Source: OMEGA branch `claude/tpo-strategy-brainstorm-796f15`, file `scripts/tpo_panel_pull.py` (`git show origin/claude/tpo-strategy-brainstorm-796f15:scripts/tpo_panel_pull.py`). Copy `COLUMNS`, `NULL_SENTINEL`, `build_request`, `parse_table`, `to_number` into `manager/panel/columns.py` unchanged, with a header comment `# Copied verbatim from OMEGA scripts/tpo_panel_pull.py @ 5c6a064 (2026-09-14).`

- [ ] **Step 2: Failing tests**

```python
# tests/panel/test_columns.py
from manager.panel.columns import COLUMNS, build_request, parse_table, to_number


def test_request_shape():
    r = build_request("1h", "CRYPTO", 50)
    assert r["coinSelection"] == {"mode": "ranked", "limit": 50, "category": "CRYPTO"}
    assert len(r["sections"][0]["columns"]) == len(COLUMNS) == 17
    assert r["sections"][0]["columns"][6] == {"metric": "PRIOR_TPO_VAL", "transformId": "spread", "timeframe": {"rel": "anchor"}, "inputs": [{"metric": "OPEN"}]}


def test_parse_and_numbers():
    text = "| coin | a | b |\n|---|---|---|\n| BTC | +1.5% | — |\n| ETH | $2,000 | p-shape |\n"
    headers, rows = parse_table(text)
    assert headers == ["coin", "a", "b"] and rows[0]["coin"] == "BTC"
    assert to_number(rows[0]["a"]) == 1.5 and to_number(rows[0]["b"]) is None and to_number(rows[1]["b"]) == "p-shape"
```

```python
# tests/panel/test_pull.py
import json
from pathlib import Path

from sqlalchemy import select

from manager.db.models import AuditEvent, PanelRow
from manager.db.session import init_db, make_engine, make_session_factory
from manager.panel.pull import pull_panel
from manager.platform.errors import Kind, PlatformError
from tests.platform.fake import FakePlatform

FX = Path(__file__).resolve().parents[1] / "fixtures" / "panel" / "preview_strategy_report.json"


def db():
    e = make_engine("sqlite+pysqlite:///:memory:"); init_db(e); return make_session_factory(e)


async def test_pull_writes_rows_and_raw(tmp_path):
    fx = json.loads(FX.read_text(encoding="utf-8"))
    Session = db()
    n = await pull_panel(FakePlatform({"preview_strategy_report": fx}), Session, str(tmp_path))
    assert n > 0 and list((tmp_path / "raw").glob("*.json"))
    with Session() as s:
        row = s.scalars(select(PanelRow)).first()
        assert row.coin and any("pTpoPOC" in k for k in row.values)


async def test_failed_pull_writes_nothing(tmp_path):
    Session = db()
    n = await pull_panel(FakePlatform({"preview_strategy_report": PlatformError(Kind.HTTP, "502", status=502)}), Session, str(tmp_path))
    assert n == 0
    with Session() as s:
        assert s.scalars(select(PanelRow)).all() == []
        assert s.scalars(select(AuditEvent).where(AuditEvent.kind == "panel.failed")).first() is not None
```

- [ ] **Step 3: Record the panel fixture (live, read-only, one call)**

```bash
docker compose run --rm -v "$PWD/tests:/app/tests" manager python - <<'EOF'
import asyncio, json
from manager.panel.columns import build_request
from manager.platform.client import PlatformClient
from manager.platform.ratelimit import TokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.settings import get_settings
s = get_settings(); c = PlatformClient(s, FileTokenStorage(s.token_path), TokenBucket(2, 100))
async def go():
    d = await c.call("preview_strategy_report", build_request("1h", "CRYPTO", 50))
    open("tests/fixtures/panel/preview_strategy_report.json", "w", encoding="utf-8").write(json.dumps(d, indent=1))
    await c.aclose(); print("keys:", list(d)[:8])
asyncio.run(go())
EOF
```
Expected: `keys:` includes `renderedSections` and `budgetUsage`. (Create `tests/fixtures/panel/` first.)

- [ ] **Step 4: Implement**

```python
# manager/panel/__init__.py
```

```python
# manager/panel/pull.py
from __future__ import annotations

import json
import time
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from manager.audit.ledger import record
from manager.db.models import PanelRow
from manager.panel.columns import build_request, parse_table, to_number
from manager.platform.errors import PlatformError


async def pull_panel(client, session_factory: sessionmaker, panel_dir: str, timeframe: str = "1h",
                     category: str = "CRYPTO", limit: int = 50) -> int:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    fstamp = stamp.replace(":", "").replace("-", "")
    raw_dir = Path(panel_dir) / "raw"; raw_dir.mkdir(parents=True, exist_ok=True)
    req = build_request(timeframe, category, limit)
    data = None
    for attempt in (1, 2):
        try:
            data = await client.call("preview_strategy_report", req); break
        except PlatformError as e:
            last = f"attempt {attempt}: {e.kind.value}: {e.message}"
    if data is None:
        with session_factory() as s:
            record(s, "panel.failed", {"at": stamp, "error": last}); s.commit()
        return 0
    raw_path = raw_dir / f"{fstamp}.json"
    raw_path.write_text(json.dumps(data), encoding="utf-8")
    sections = data.get("renderedSections") or []
    if not sections:
        with session_factory() as s:
            record(s, "panel.failed", {"at": stamp, "error": "no renderedSections"}); s.commit()
        return 0
    headers, rows = parse_table(sections[0]["section"]["text"])
    written = 0
    with session_factory() as s:
        for r in rows:
            coin = r.get("coin")
            if not coin:
                continue
            values = {h: to_number(r.get(h)) for h in headers if h != "coin"}
            s.add(PanelRow(captured_at=stamp, coin=coin, timeframe=timeframe, raw_file=raw_path.name, values=values))
            written += 1
        record(s, "panel.pulled", {"at": stamp, "rows": written, "budget": data.get("budgetUsage", {})})
        s.commit()
    return written
```

```python
# manager/commands/panel.py
import argparse
import asyncio

from manager.cli import register
from manager.db.session import make_engine, make_session_factory
from manager.panel.pull import pull_panel
from manager.platform.client import PlatformClient
from manager.platform.ratelimit import TokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.settings import get_settings


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("action", choices=["pull"])


def _run(a: argparse.Namespace) -> int:
    s = get_settings()
    client = PlatformClient(s, FileTokenStorage(s.token_path), TokenBucket(s.rate_limit_rps, s.rate_limit_burst))
    Session = make_session_factory(make_engine(s.database_url))

    async def go() -> int:
        n = await pull_panel(client, Session, s.panel_dir); await client.aclose()
        print("panel rows:", n); return 0 if n else 1

    return asyncio.run(go())


register("panel", "TPO panel logger", _add, _run)
```
Register in `manager/commands/__init__.py`.

- [ ] **Step 5: Run** → PASS; live: `docker compose run --rm manager python -m manager panel pull` → `panel rows: 36` (or the cohort size the platform returns).
- [ ] **Step 6: Commit** `"TPO panel logger moved in-process: raw saved before parse, failures never become rows"`.

---

### Task 12: Jobs as processes (API scheduler + `run` for every other job)

**Files:**
- Create: `manager/scheduler/__init__.py`, `manager/scheduler/jobs.py`, `manager/commands/run.py`, `tests/scheduler/test_jobs.py`

**Interfaces:**
- Produces: `async job_heartbeat(ctx)`, `async job_health(ctx)` (calls `client.version()`; on `PlatformError` sets `safe={"safe": True, "reason": ..., "since": ...}` and records `safe.enter`; on success clears it and records `safe.exit` if it was set), `async job_snapshot(ctx)`, `async job_panel(ctx)`; `build_scheduler(ctx) -> AsyncIOScheduler` with ONLY heartbeat and health (60 s each), for the `api` process; `seconds_until_hourly(minute: int, now: datetime | None = None) -> float`; CLI `python -m manager run <job> (--every N | --hourly-at M) [--once]` runs one job as its own process. The Compose services `inventory` (`run snapshot --every 300`) and `panel` (`run panel --hourly-at 5`) from Task 1 use it, so each job is switched on or off from Docker. `ctx` is a `JobContext(client, session_factory, settings)` dataclass.

- [ ] **Step 1: Failing tests**

```python
# tests/scheduler/test_jobs.py
from sqlalchemy import select

from manager.audit.ledger import get_state
from manager.db.models import Heartbeat
from manager.db.session import init_db, make_engine, make_session_factory
from manager.platform.errors import Kind, PlatformError
from manager.scheduler.jobs import JobContext, build_scheduler, job_health, job_heartbeat
from manager.settings import Settings
from tests.platform.fake import FakePlatform


def ctx(platform, settings):
    e = make_engine("sqlite+pysqlite:///:memory:"); init_db(e)
    return JobContext(client=platform, session_factory=make_session_factory(e), settings=settings)


async def test_heartbeat_row(settings):
    c = ctx(FakePlatform({}), settings)
    await job_heartbeat(c)
    with c.session_factory() as s:
        assert s.scalars(select(Heartbeat)).first().job == "heartbeat"


class Down(FakePlatform):
    async def version(self):
        raise PlatformError(Kind.HTTP, "502", status=502)


async def test_health_enters_and_exits_safe(settings):
    c = ctx(Down({}), settings)
    await job_health(c)
    with c.session_factory() as s:
        assert get_state(s, "safe", {})["safe"] is True
    c.client = FakePlatform({})
    await job_health(c)
    with c.session_factory() as s:
        assert get_state(s, "safe", {})["safe"] is False


def test_scheduler_has_only_the_api_jobs(settings):
    sched = build_scheduler(ctx(FakePlatform({}), settings))
    assert {j.id for j in sched.get_jobs()} == {"heartbeat", "health"}


def test_seconds_until_hourly():
    from datetime import UTC, datetime

    from manager.commands.run import seconds_until_hourly

    now = datetime(2026, 9, 14, 6, 20, tzinfo=UTC)
    assert seconds_until_hourly(5, now) == 45 * 60
    assert seconds_until_hourly(30, now) == 10 * 60
    assert seconds_until_hourly(20, now) == 60 * 60
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/scheduler/__init__.py
```

```python
# manager/scheduler/jobs.py
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.orm import sessionmaker

from manager.audit.ledger import get_state, record, set_state
from manager.db.models import Heartbeat
from manager.inventory.snapshot import take_snapshot
from manager.panel.pull import pull_panel
from manager.platform.errors import PlatformError
from manager.settings import Settings

log = logging.getLogger(__name__)


@dataclass
class JobContext:
    client: object
    session_factory: sessionmaker
    settings: Settings


def _beat(ctx: JobContext, job: str, ok: bool, note: str | None = None) -> None:
    with ctx.session_factory() as s:
        s.add(Heartbeat(at=datetime.now(UTC), job=job, ok=ok, note=note)); s.commit()


async def job_heartbeat(ctx: JobContext) -> None:
    _beat(ctx, "heartbeat", True)


async def job_health(ctx: JobContext) -> None:
    now = datetime.now(UTC).isoformat()
    try:
        v = await ctx.client.version()
        with ctx.session_factory() as s:
            was = get_state(s, "safe", {"safe": False})
            if was.get("safe"):
                record(s, "safe.exit", {"at": now, "version": v})
            set_state(s, "safe", {"safe": False, "reason": None, "since": None})
            set_state(s, "contract_live", {"contractVersion": v.get("contractVersion"), "at": now})
            s.commit()
        _beat(ctx, "health", True, v.get("contractVersion"))
    except PlatformError as e:
        with ctx.session_factory() as s:
            was = get_state(s, "safe", {"safe": False})
            if not was.get("safe"):
                record(s, "safe.enter", {"at": now, "reason": f"{e.kind.value}: {e.message}"})
                set_state(s, "safe", {"safe": True, "reason": f"{e.kind.value}: {e.message}", "since": now})
            s.commit()
        _beat(ctx, "health", False, e.message)


async def job_snapshot(ctx: JobContext) -> None:
    try:
        sid = await take_snapshot(ctx.client, ctx.session_factory)
        with ctx.session_factory() as s:
            record(s, "snapshot.taken", {"id": sid}); s.commit()
        _beat(ctx, "snapshot", True, str(sid))
    except Exception as e:  # a snapshot must never kill the scheduler
        log.exception("snapshot failed"); _beat(ctx, "snapshot", False, str(e)[:500])


async def job_panel(ctx: JobContext) -> None:
    n = await pull_panel(ctx.client, ctx.session_factory, ctx.settings.panel_dir)
    _beat(ctx, "panel", n > 0, f"rows={n}")


def build_scheduler(ctx: JobContext) -> AsyncIOScheduler:
    """Only the jobs the api process itself needs. Every other job is its own Compose service."""
    sched = AsyncIOScheduler(timezone="UTC")
    sched.add_job(job_heartbeat, IntervalTrigger(seconds=60), id="heartbeat", args=[ctx], max_instances=1)
    sched.add_job(job_health, IntervalTrigger(seconds=60), id="health", args=[ctx], max_instances=1)
    return sched
```

```python
# manager/commands/run.py — one job, one process, one Compose service. Switch it off from Docker.
from __future__ import annotations

import argparse
import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

from manager.cli import register
from manager.db.session import init_db, make_engine, make_session_factory
from manager.platform.client import PlatformClient
from manager.platform.ratelimit import TokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.scheduler.jobs import JobContext, job_panel, job_snapshot
from manager.settings import get_settings

log = logging.getLogger(__name__)
JOBS = {"snapshot": job_snapshot, "panel": job_panel}  # Task 17 adds "watch"


def seconds_until_hourly(minute: int, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    target = now.replace(minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(hours=1)
    return (target - now).total_seconds()


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("job", choices=sorted(JOBS))
    when = p.add_mutually_exclusive_group(required=True)
    when.add_argument("--every", type=int, help="seconds between runs; the first run is immediate")
    when.add_argument("--hourly-at", type=int, help="minute past every hour, UTC")
    p.add_argument("--once", action="store_true", help="run one time and exit")


def _run(a: argparse.Namespace) -> int:
    s = get_settings()
    engine = make_engine(s.database_url)
    init_db(engine)
    client = PlatformClient(s, FileTokenStorage(s.token_path), TokenBucket(s.rate_limit_rps, s.rate_limit_burst))
    ctx = JobContext(client=client, session_factory=make_session_factory(engine), settings=s)
    job = JOBS[a.job]

    async def loop() -> int:
        try:
            while True:
                if a.hourly_at is not None and not a.once:
                    await asyncio.sleep(seconds_until_hourly(a.hourly_at))
                started = time.monotonic()
                try:
                    await job(ctx)
                except Exception:  # noqa: BLE001 - one failed run is logged; the next tick retries
                    log.exception("job %s failed", a.job)
                if a.once:
                    return 0
                if a.every is not None:
                    await asyncio.sleep(max(1.0, a.every - (time.monotonic() - started)))
        finally:
            await client.aclose()

    return asyncio.run(loop())


register("run", "Run one background job as its own process (one Compose service each)", _add, _run)
```
Register it: add `from manager.commands import run  # noqa: F401` to `manager/commands/__init__.py`.

- [ ] **Step 4: Run** → PASS. Then `docker compose up -d --build && docker compose ps` lists `postgres`, `api`, `watch`, `inventory` running; `docker compose stop inventory && docker compose ps` shows only `inventory` stopped; `docker compose start inventory` brings it back.
- [ ] **Step 5: Commit** `"Jobs as processes: api keeps heartbeat and health; snapshot and panel run as their own Compose services"`.

---

### Task 13: REST API with bearer auth and `serve`

**Files:**
- Create: `manager/api/__init__.py`, `manager/api/auth.py`, `manager/api/app.py`, `manager/commands/serve.py`, `tests/api/test_app.py`

**Interfaces:**
- Produces: `create_app(ctx: JobContext | None = None) -> FastAPI`; routes `GET /health` (no auth: `{"ok": true, "safe": bool, "contract": str|null, "last_heartbeat": str|null}`), `GET /api/inventory/latest` (auth: snapshot id, taken_at, reads status map, counts), `GET /api/inventory/report` (auth: markdown from Task 14), `GET /api/ledger?kind=&limit=` (auth). Bearer = `Authorization: Bearer <MANAGER_TOKEN>`. `python -m manager serve` runs uvicorn on `0.0.0.0:8790` with only heartbeat and health in its lifespan; every other job is a separate Compose service (Task 12).

- [ ] **Step 1: Failing tests**

```python
# tests/api/test_app.py
import json
from pathlib import Path

from fastapi.testclient import TestClient

from manager.api.app import create_app
from manager.db.session import init_db, make_engine, make_session_factory
from manager.inventory.snapshot import take_snapshot
from manager.scheduler.jobs import JobContext
from tests.platform.fake import FakePlatform

FX = Path(__file__).resolve().parents[1] / "fixtures" / "2026-09-14"


def make_ctx(settings):
    e = make_engine("sqlite+pysqlite:///:memory:"); init_db(e)
    fx = {n: json.loads((FX / f"{n}.json").read_text(encoding="utf-8")) for n in
          ["get_account_state", "list_intelligence_agents", "list_strategies", "list_radar_deployments", "list_user_active_positions"]}
    return JobContext(client=FakePlatform(fx), session_factory=make_session_factory(e), settings=settings)


def test_health_is_public_and_inventory_needs_token(settings):
    ctx = make_ctx(settings)
    app = create_app(ctx, start_scheduler=False)
    with TestClient(app) as c:
        assert c.get("/health").json()["ok"] is True
        assert c.get("/api/inventory/latest").status_code == 401
        assert c.get("/api/inventory/latest", headers={"Authorization": "Bearer wrong"}).status_code == 403


async def test_latest_after_snapshot(settings):
    ctx = make_ctx(settings)
    await take_snapshot(ctx.client, ctx.session_factory)
    app = create_app(ctx, start_scheduler=False)
    with TestClient(app) as c:
        r = c.get("/api/inventory/latest", headers={"Authorization": f"Bearer {settings.manager_token}"})
        assert r.status_code == 200 and r.json()["counts"]["agents"] == 9 and r.json()["counts"]["radar"] == 20
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/api/__init__.py
```

```python
# manager/api/auth.py
from fastapi import Depends, HTTPException, Request

from manager.settings import Settings


def require_bearer(settings_getter):
    def dep(request: Request, settings: Settings = Depends(settings_getter)) -> None:
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            raise HTTPException(401, "missing bearer token")
        if auth.split(" ", 1)[1].strip() != settings.manager_token:
            raise HTTPException(403, "invalid token")
    return dep
```

```python
# manager/api/app.py
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Query
from sqlalchemy import func, select

from manager.api.auth import require_bearer
from manager.audit.ledger import get_state, query
from manager.db.models import AgentRow, Heartbeat, PositionRow, RadarPolicyRow, StrategyRow
from manager.inventory.report import render_inventory_report
from manager.inventory.snapshot import latest
from manager.scheduler.jobs import JobContext, build_scheduler


def create_app(ctx: JobContext, start_scheduler: bool = True) -> FastAPI:
    def settings_getter():
        return ctx.settings
    auth = require_bearer(settings_getter)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        sched = build_scheduler(ctx) if start_scheduler else None
        if sched:
            sched.start()
        try:
            yield
        finally:
            if sched:
                sched.shutdown(wait=False)
            aclose = getattr(ctx.client, "aclose", None)
            if aclose:
                await aclose()

    app = FastAPI(title="battlegrid-manager", lifespan=lifespan)

    @app.get("/health")
    def health():
        with ctx.session_factory() as s:
            safe = get_state(s, "safe", {"safe": False})
            live = get_state(s, "contract_live", {})
            hb = s.scalar(select(Heartbeat).where(Heartbeat.job == "heartbeat").order_by(Heartbeat.id.desc()).limit(1))
        return {"ok": True, "safe": bool(safe.get("safe")), "contract": live.get("contractVersion"),
                "last_heartbeat": hb.at.isoformat() if hb else None}

    @app.get("/api/inventory/latest", dependencies=[Depends(auth)])
    def inventory_latest():
        with ctx.session_factory() as s:
            snap = latest(s)
            if snap is None:
                return {"snapshot": None}
            counts = {name: s.scalar(select(func.count()).select_from(m).where(m.snapshot_id == snap.id))
                      for name, m in [("agents", AgentRow), ("strategies", StrategyRow), ("radar", RadarPolicyRow), ("positions", PositionRow)]}
            return {"snapshot": snap.id, "taken_at": snap.taken_at.isoformat(), "contract": snap.contract_version,
                    "reads": {k: v["status"] for k, v in snap.reads.items()}, "counts": counts}

    @app.get("/api/inventory/report", dependencies=[Depends(auth)])
    def inventory_report():
        with ctx.session_factory() as s:
            return {"markdown": render_inventory_report(s)}

    @app.get("/api/ledger", dependencies=[Depends(auth)])
    def ledger(kind: str | None = Query(default=None), limit: int = Query(default=100, le=1000)):
        with ctx.session_factory() as s:
            return [{"id": e.id, "at": e.at.isoformat(), "kind": e.kind, "payload": e.payload} for e in query(s, kind=kind, limit=limit)]

    return app
```

```python
# manager/commands/serve.py
import argparse

import uvicorn

from manager.api.app import create_app
from manager.cli import register
from manager.db.session import init_db, make_engine, make_session_factory
from manager.platform.client import PlatformClient
from manager.platform.ratelimit import TokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.scheduler.jobs import JobContext
from manager.settings import get_settings


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("--port", type=int, default=8790)


def _run(a: argparse.Namespace) -> int:
    s = get_settings()
    engine = make_engine(s.database_url); init_db(engine)
    client = PlatformClient(s, FileTokenStorage(s.token_path), TokenBucket(s.rate_limit_rps, s.rate_limit_burst))
    ctx = JobContext(client=client, session_factory=make_session_factory(engine), settings=s)
    uvicorn.run(create_app(ctx), host="0.0.0.0", port=a.port, log_level=s.log_level.lower())
    return 0


register("serve", "Run the API and scheduler", _add, _run)
```
Register in `manager/commands/__init__.py`. (Task 14 supplies `render_inventory_report`; until then create `manager/inventory/report.py` with `def render_inventory_report(s): return ""`.)

- [ ] **Step 4: Run** → PASS. Then `docker compose up -d --build && sleep 5 && curl -s http://127.0.0.1:8790/health` → `{"ok":true,"safe":false,"contract":"54.1.0",...}`.
- [ ] **Step 5: Commit** `"REST API with bearer auth; serve runs API plus scheduler"`.

---

### Task 14: Inventory report (the phase deliverable)

**Files:**
- Create/replace: `manager/inventory/report.py`, `manager/commands/report.py`, `tests/inventory/test_report.py`, `docs/phase-0/inventory-report.md`

**Interfaces:**
- Produces: `render_inventory_report(s: Session) -> str` (markdown: header with snapshot time, contract, read statuses; **Account**; **Agents** table: name, status, model, strategy@rev, binding, trades W/L, 24h cost, exposure/leverage/dailyLoss/drawdown; **Radar** table: coin, tf, agent(s), section, block, last fire, and the summary line `coinsDeployed/coinCap`; **Positions** table or the literal line `No open positions (pricingStatus: LIVE)`; any `UNDETERMINED` read printed as a warning block, never omitted); CLI `python -m manager report inventory [--out path]`.

- [ ] **Step 1: Failing test**

```python
# tests/inventory/test_report.py
import json
from pathlib import Path

from manager.db.session import init_db, make_engine, make_session_factory
from manager.inventory.report import render_inventory_report
from manager.inventory.snapshot import take_snapshot
from manager.platform.errors import Kind, PlatformError
from tests.platform.fake import FakePlatform

FX = Path(__file__).resolve().parents[1] / "fixtures" / "2026-09-14"


def fx():
    return {n: json.loads((FX / f"{n}.json").read_text(encoding="utf-8")) for n in
            ["get_account_state", "list_intelligence_agents", "list_strategies", "list_radar_deployments", "list_user_active_positions"]}


async def test_report_contents():
    e = make_engine("sqlite+pysqlite:///:memory:"); init_db(e); Session = make_session_factory(e)
    await take_snapshot(FakePlatform(fx()), Session)
    with Session() as s:
        md = render_inventory_report(s)
    assert "ANBUJEFF" in md and "STRUCT Alpha" in md and "15 (9W/6L)" in md
    assert "20/20" in md and "No open positions (pricingStatus: LIVE)" in md
    assert "UNDETERMINED" not in md


async def test_report_flags_undetermined():
    f = fx(); f["list_radar_deployments"] = PlatformError(Kind.HTTP, "502", status=502)
    e = make_engine("sqlite+pysqlite:///:memory:"); init_db(e); Session = make_session_factory(e)
    await take_snapshot(FakePlatform(f), Session)
    with Session() as s:
        md = render_inventory_report(s)
    assert "UNDETERMINED" in md and "list_radar_deployments" in md and "## Radar" not in md
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Implement**

```python
# manager/inventory/report.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from manager.db.models import AgentRow, PositionRow, RadarPolicyRow, StrategyRow
from manager.inventory.snapshot import latest


def render_inventory_report(s: Session) -> str:
    snap = latest(s)
    if snap is None:
        return "# Inventory\n\nNo snapshot yet.\n"
    L = [f"# Inventory report — snapshot {snap.id} at {snap.taken_at.isoformat()}", "",
         f"Contract: `{snap.contract_version}` · reads: " + ", ".join(f"{k}={v['status']}" for k, v in snap.reads.items()), ""]
    und = {k: v for k, v in snap.reads.items() if v["status"] != "OK"}
    if und:
        L += ["> **UNDETERMINED reads** — these sections are NOT empty, they could not be read:", ""]
        L += [f"> - `{k}`: {v['error']}" for k, v in und.items()] + [""]
    acct = snap.reads.get("get_account_state", {})
    if acct.get("status") == "OK":
        L += ["## Account", "", f"- wallet: {acct.get('account', {}).get('usdc')} USDC", ""]
    agents = s.scalars(select(AgentRow).where(AgentRow.snapshot_id == snap.id).order_by(AgentRow.display_name)).all()
    names = {r.strategy_id: r.name for r in s.scalars(select(StrategyRow).where(StrategyRow.snapshot_id == snap.id)).all()}
    if snap.reads["list_intelligence_agents"]["status"] == "OK":
        L += ["## Agents", "", "| agent | status | model | strategy @ rev | binding | trades | 24h cost | exposure / lev / dailyLoss / drawdown |", "|---|---|---|---|---|---|---|---|"]
        for a in agents:
            tc = a.trading_config or {}
            L.append(f"| {a.display_name} | {a.status} | {a.model_id} | {a.strategy_name or names.get(a.strategy_id, a.strategy_id)} @ {a.strategy_revision} | {a.binding_state} | "
                     f"{a.trades} ({a.wins}W/{a.losses}L) | {a.last24h_cost_usd:.4f} | {tc.get('maxConcurrentExposureUsd')} / {tc.get('maxLeverage')} / {tc.get('maxDailyLossUsd')} / {tc.get('maxCumulativeDrawdownUsd')} |")
        L.append("")
    if snap.reads["list_radar_deployments"]["status"] == "OK":
        summ = snap.reads["list_radar_deployments"].get("summary", {})
        agent_name = {a.agent_id: a.display_name for a in agents}
        L += [f"## Radar — {summ.get('coinsDeployed')}/{summ.get('coinCap')} coins deployed, {summ.get('inPosition')} in position, radarPaused={summ.get('radarPaused')}", "",
              "| coin | tf | agents | section | block | last fire |", "|---|---|---|---|---|---|"]
        for r in s.scalars(select(RadarPolicyRow).where(RadarPolicyRow.snapshot_id == snap.id).order_by(RadarPolicyRow.coin_id)).all():
            L.append(f"| {r.coin_id} | {r.timeframe} | {', '.join(agent_name.get(x, x[:8]) for x in r.agent_ids)} | {r.section} | {r.qualification_block} | {r.last_fire_at or '—'} |")
        L.append("")
    if snap.reads["list_user_active_positions"]["status"] == "OK":
        rows = s.scalars(select(PositionRow).where(PositionRow.snapshot_id == snap.id)).all()
        totals = snap.reads["list_user_active_positions"].get("totals", {})
        L += ["## Positions", ""]
        if not rows:
            L.append(f"No open positions (pricingStatus: {totals.get('pricingStatus')})")
        else:
            L += ["| position | agent | coin | side | size USD | entry | stop | TP | mark | uPnL | pricing |", "|---|---|---|---|---|---|---|---|---|---|---|"]
            L += [f"| {p.position_id[:8]} | {p.agent_id[:8]} | {p.coin} | {p.side} | {p.size_usd} | {p.entry} | {p.stop} | {p.take_profit} | {p.mark} | {p.unrealized_pnl_usd} | {p.pricing_status} |" for p in rows]
        L.append("")
    return "\n".join(L)
```

```python
# manager/commands/report.py
import argparse
from pathlib import Path

from manager.cli import register
from manager.db.session import make_engine, make_session_factory
from manager.inventory.report import render_inventory_report
from manager.settings import get_settings


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("kind", choices=["inventory"])
    p.add_argument("--out")


def _run(a: argparse.Namespace) -> int:
    Session = make_session_factory(make_engine(get_settings().database_url))
    with Session() as s:
        md = render_inventory_report(s)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(md, encoding="utf-8")
    print(md)
    return 0


register("report", "Render reports from the latest snapshot", _add, _run)
```
Register in `manager/commands/__init__.py`.

- [ ] **Step 4: Run** → PASS. Then, with the stack up: `docker compose exec manager python -m manager report inventory --out /tmp/r.md && docker compose cp manager:/tmp/r.md docs/phase-0/inventory-report.md`.
- [ ] **Step 5: Commit** `"Inventory report: the phase-0 deliverable, UNDETERMINED never rendered as empty"` and hand `docs/phase-0/inventory-report.md` to the user for the exit-gate review.

---

### Task 15: Phase-0 measurements

**Files:**
- Create: `manager/measure/__init__.py`, `manager/measure/notional.py`, `manager/commands/measure.py`, `docs/phase-0/measurements.md`

**Interfaces:**
- Produces: `python -m manager measure notional --coins BTC,ETH,SOL,PEPE` (calls `get_coin_metadata` per coin and `get_trading_config_catalog` once; prints every key whose name contains `min`, `notional`, `size`, `lot`, `step`, `tick`; saves raw under `docs/phase-0/raw/`); `python -m manager measure llm-cost` (from the last 7 daily snapshots: per agent `last24h_cost_usd` series); `python -m manager measure rate-headroom` (fires 40 `get_account_state` calls through the limiter and reports elapsed time and any `RATE_LIMITED`).

- [ ] **Step 1: Implement**

```python
# manager/measure/__init__.py
```

```python
# manager/measure/notional.py
from __future__ import annotations

import json
import time
from pathlib import Path

KEYS = ("min", "notional", "size", "lot", "step", "tick", "leverage")


def interesting(obj, path=""):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            if any(x in k.lower() for x in KEYS) and not isinstance(v, (dict, list)):
                out.append((p, v))
            out += interesting(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:5]):
            out += interesting(v, f"{path}[{i}]")
    return out


async def measure_notional(client, coins: list[str], raw_dir: str) -> dict:
    Path(raw_dir).mkdir(parents=True, exist_ok=True)
    result = {}
    cat = await client.call("get_trading_config_catalog")
    (Path(raw_dir) / "get_trading_config_catalog.json").write_text(json.dumps(cat, indent=1), encoding="utf-8")
    result["catalog"] = interesting(cat)
    for c in coins:
        meta = await client.call("get_coin_metadata", {"ticker": c})
        (Path(raw_dir) / f"get_coin_metadata_{c}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        result[c] = interesting(meta)
    return result


async def measure_rate_headroom(client, n: int = 40) -> dict:
    t0 = time.monotonic(); limited = 0
    for _ in range(n):
        try:
            await client.call("get_account_state")
        except Exception as e:  # noqa: BLE001 — we are measuring, and we report the kind
            limited += 1 if "RATE_LIMITED" in str(e) else 0
    return {"calls": n, "seconds": round(time.monotonic() - t0, 1), "rate_limited": limited}
```

```python
# manager/commands/measure.py
import argparse
import asyncio
import json

from sqlalchemy import select

from manager.cli import register
from manager.db.models import AgentRow, Snapshot
from manager.db.session import make_engine, make_session_factory
from manager.measure.notional import measure_notional, measure_rate_headroom
from manager.platform.client import PlatformClient
from manager.platform.ratelimit import TokenBucket
from manager.platform.tokens import FileTokenStorage
from manager.settings import get_settings


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("what", choices=["notional", "llm-cost", "rate-headroom"])
    p.add_argument("--coins", default="BTC,ETH,SOL,PEPE")


def _run(a: argparse.Namespace) -> int:
    s = get_settings()
    client = PlatformClient(s, FileTokenStorage(s.token_path), TokenBucket(s.rate_limit_rps, s.rate_limit_burst))
    Session = make_session_factory(make_engine(s.database_url))

    async def go() -> int:
        if a.what == "notional":
            print(json.dumps(await measure_notional(client, a.coins.split(","), "docs/phase-0/raw"), indent=1))
        elif a.what == "rate-headroom":
            print(json.dumps(await measure_rate_headroom(client), indent=1))
        else:
            with Session() as db:
                snaps = db.scalars(select(Snapshot).order_by(Snapshot.id.desc()).limit(7 * 288)).all()
                by_day = {}
                for sn in snaps:
                    day = sn.taken_at.date().isoformat()
                    for r in db.scalars(select(AgentRow).where(AgentRow.snapshot_id == sn.id)).all():
                        by_day.setdefault(day, {})[r.display_name] = max(by_day.get(day, {}).get(r.display_name, 0.0), r.last24h_cost_usd)
                print(json.dumps(by_day, indent=1))
        await client.aclose(); return 0

    return asyncio.run(go())


register("measure", "Phase-0 measurements", _add, _run)
```
Register in `manager/commands/__init__.py`. If `get_coin_metadata` refuses `{"ticker": ...}`, run `python -c "..."` printing the tool's input schema from `client.list_tools()` and use the declared key; record it.

- [ ] **Step 2: Run the three measurements (live, read-only)** and write `docs/phase-0/measurements.md` with: the exact keys and values found for minimum order size per coin (or the statement "no minimum-size field is exposed by these two tools; measured at first live order in phase 3"), the 7-day LLM cost table (fill daily), and the rate-headroom result (expected: 40 calls in about 20 s, `rate_limited: 0`).
- [ ] **Step 3: Commit** `"Phase-0 measurements: minimum notional, platform LLM cost, rate headroom"`.

---

### Task 16: Runbook — keep-awake, autostart, retire the Windows task

**Files:**
- Create: `docs/phase-0/runbook.md`

- [ ] **Step 1: Apply and record the host settings (PowerShell, as the user)**

```powershell
powercfg /change standby-timeout-ac 0; powercfg /change hibernate-timeout-ac 0; powercfg /change monitor-timeout-ac 20
```
Docker Desktop → Settings → General → "Start Docker Desktop when you sign in" = on. Compose services already carry `restart: unless-stopped`.

- [ ] **Step 2: Verify the in-process panel logger for 24 h** — `curl -s -H "Authorization: Bearer $MANAGER_TOKEN" "http://127.0.0.1:8790/api/ledger?kind=panel.pulled&limit=30"` shows one row per hour at :05Z.

- [ ] **Step 3: Retire the Windows task only after step 2 passes**

```powershell
schtasks /Query /TN "OMEGA TPO panel" /FO LIST | Select-Object -First 5; schtasks /Change /TN "OMEGA TPO panel" /DISABLE
```
(Disable, do not delete, for one week; then `schtasks /Delete /TN "OMEGA TPO panel" /F`.) Note in the runbook that OMEGA's `data/panel/tpo_panel.jsonl` stops growing from this date and the manager's `panel_rows` table continues the series.

- [ ] **Step 4: Write `docs/phase-0/runbook.md`** with: start/stop (`docker compose up -d` / `down`), login renewal (`auth login`), where the token lives (volume `tokens`, never in the repo), how to read health, the heartbeat-gap rule (a gap > 6 minutes = the PC slept or Docker stopped; check `/api/ledger?kind=safe.enter`), and the disabled Windows task name.

- [ ] **Step 5: Commit** `"Runbook: keep-awake, autostart, Windows panel task retired in favour of the in-process logger"`.

---

---

### Task 17: Platform watch — self-monitoring for drift

**Why this task exists (measured 2026-09-14):** the live contract went 54.1.0 → 56.1.0 between 09:00 and 13:34 local with **115 tools before and after**. Semantics changed (verdict resolution, direction binding, settled-bar rule, timeless session levels, ten new TPO metrics). A tool count is not a freshness signal; per-tool schema hashes and the version/build pair are.

**Files:**
- Modify: `manager/platform/client.py` (add `list_tools()`), `manager/scheduler/jobs.py` (add `job_watch`), `manager/commands/run.py` (add `watch` to `JOBS`), `manager/api/app.py` (add `GET /api/platform/changes`), `manager/settings.py` (add `pack_dir`), `tests/platform/fake.py` (add `tools`)
- Create: `manager/platform/watch.py`, `manager/commands/contract.py`, `tests/platform/test_watch.py`

**Interfaces:**
- Produces: `PlatformClient.list_tools() -> list[dict]` (each `{"name": str, "inputSchema": dict}`); `observe(client, pack_dir: str | None) -> dict` = `{"contractVersion", "buildSha", "tools": {name: sha256_of_canonical_inputSchema}, "pack": {"version": str|None, "contractVersion": str|None}, "npmLatest": str|None, "observedAt": iso}`; `diff_surfaces(old: dict | None, new: dict) -> dict` = `{"changed": bool, "version": [from, to], "build": [from, to], "tools_added": [...], "tools_removed": [...], "tools_changed": [...], "pack_stale": bool, "pack_update_available": bool}`; `job_watch(ctx)` every 600 s; system-state keys `"surface"` (last observation) and `"writes_blocked"` (`{"blocked": bool, "reason": str|None, "since": str|None, "acknowledged": str|None}`); CLI `python -m manager contract ack <version>` and `contract status`; `GET /api/platform/changes?limit=` (auth) returns the surface, the block flag, the last `contract.drift` events and the last `pack.refresh_recommended` events.

- [ ] **Step 1: Failing tests**

```python
# tests/platform/test_watch.py
from manager.audit.ledger import get_state, query
from manager.db.session import init_db, make_engine, make_session_factory
from manager.platform.watch import diff_surfaces, observe
from manager.scheduler.jobs import JobContext, job_watch
from tests.platform.fake import FakePlatform


def surface(v, build, tools):
    return {"contractVersion": v, "buildSha": build, "tools": tools, "pack": {"version": "31.2.22", "contractVersion": v},
            "npmLatest": "31.2.22", "observedAt": "2026-09-14T06:34:00Z"}


def test_diff_flags_version_and_schema_change_with_same_tool_count():
    old = surface("54.1.0", "aaa", {"get_account_state": "h1", "compile_strategy_plan": "h2"})
    new = surface("56.1.0", "bbb", {"get_account_state": "h1", "compile_strategy_plan": "h9"})
    d = diff_surfaces(old, new)
    assert d["changed"] and d["version"] == ["54.1.0", "56.1.0"] and d["tools_changed"] == ["compile_strategy_plan"]
    assert d["tools_added"] == [] and d["tools_removed"] == []


def test_diff_first_observation_is_not_drift():
    assert diff_surfaces(None, surface("56.1.0", "bbb", {}))["changed"] is False


def test_pack_stale_when_pack_contract_differs():
    new = surface("56.1.0", "bbb", {})
    new["pack"] = {"version": "31.2.17", "contractVersion": "54.0.0"}
    d = diff_surfaces(new, new)
    assert d["pack_stale"] is True and d["pack_update_available"] is True


async def test_observe_hashes_schemas(settings):
    fake = FakePlatform({}, tools=[{"name": "get_account_state", "inputSchema": {"type": "object", "properties": {}}}])
    obs = await observe(fake, pack_dir=None)
    assert obs["contractVersion"] == "54.1.0" and len(obs["tools"]["get_account_state"]) == 64


async def test_job_watch_records_drift_and_blocks_writes(settings):
    e = make_engine("sqlite+pysqlite:///:memory:"); init_db(e); Session = make_session_factory(e)
    ctx = JobContext(client=FakePlatform({}, tools=[{"name": "get_account_state", "inputSchema": {"a": 1}}],
                                         version={"name": "battlegrid", "contractVersion": "54.1.0", "buildSha": "aaa"}),
                     session_factory=Session, settings=settings)
    await job_watch(ctx)  # first observation: baseline, no drift
    ctx.client = FakePlatform({}, tools=[{"name": "get_account_state", "inputSchema": {"a": 2}}],
                              version={"name": "battlegrid", "contractVersion": "56.1.0", "buildSha": "bbb"})
    await job_watch(ctx)  # second: drift
    with Session() as s:
        ev = query(s, kind="contract.drift")
        assert len(ev) == 1 and ev[0].payload["version"] == ["54.1.0", "56.1.0"]
        assert get_state(s, "writes_blocked", {})["blocked"] is True
```

Replace the test double so it can serve a tool list:

```python
# tests/platform/fake.py  (replace the class)
from manager.platform.errors import Kind, PlatformError


class FakePlatform:
    def __init__(self, responses: dict, version: dict | None = None, tools: list[dict] | None = None):
        self.responses, self.calls = responses, []
        self._version = version or {"name": "battlegrid", "contractVersion": "54.1.0", "buildSha": "aaa"}
        self._tools = tools or []

    async def call(self, tool: str, args: dict | None = None) -> dict:
        self.calls.append((tool, args or {}))
        r = self.responses.get(tool)
        if r is None:
            raise PlatformError(Kind.TOOL_ERROR, f"no fixture for {tool}")
        if isinstance(r, Exception):
            raise r
        return r

    async def version(self) -> dict:
        return self._version

    async def list_tools(self) -> list[dict]:
        return self._tools
```

- [ ] **Step 2: Run** `pytest tests/platform/test_watch.py -v` → FAIL.

- [ ] **Step 3: Implement**

Add to `PlatformClient` in `manager/platform/client.py`:

```python
    async def list_tools(self) -> list[dict]:
        await self._bucket.acquire()
        client = await self._session()
        result = await client.list_tools()
        out = []
        for t in result.tools:
            schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", None) or {}
            out.append({"name": t.name, "inputSchema": schema if isinstance(schema, dict) else dict(schema)})
        return out
```

```python
# manager/platform/watch.py
"""Self-monitoring: observe the platform surface, diff it, never trust a tool count."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_pack(pack_dir: str | None) -> dict:
    if not pack_dir:
        return {"version": None, "contractVersion": None}
    p = Path(pack_dir)
    try:
        version = json.loads((p / "package.json").read_text(encoding="utf-8")).get("version")
    except (OSError, json.JSONDecodeError):
        version = None
    try:
        contract = json.loads((p / "skills" / "EXPORT.json").read_text(encoding="utf-8")).get("contractVersion")
    except (OSError, json.JSONDecodeError):
        contract = None
    return {"version": version, "contractVersion": contract}


def npm_latest(package: str = "@battlegrid/mcp-server") -> str | None:
    npm = shutil.which("npm")
    if not npm:
        return None
    try:
        out = subprocess.run([npm, "view", package, "version"], capture_output=True, text=True, timeout=30)
        return out.stdout.strip() or None
    except (subprocess.SubprocessError, OSError):
        return None


async def observe(client, pack_dir: str | None) -> dict:
    version = await client.version()
    tools = await client.list_tools()
    return {
        "contractVersion": version.get("contractVersion"), "buildSha": version.get("buildSha"),
        "tools": {t["name"]: _h(t.get("inputSchema", {})) for t in tools},
        "pack": read_pack(pack_dir), "npmLatest": npm_latest(),
        "observedAt": datetime.now(UTC).isoformat(),
    }


def diff_surfaces(old: dict | None, new: dict) -> dict:
    pack = new.get("pack", {})
    d = {
        "changed": False, "version": [None, new.get("contractVersion")], "build": [None, new.get("buildSha")],
        "tools_added": [], "tools_removed": [], "tools_changed": [],
        "pack_stale": bool(pack.get("contractVersion")) and pack.get("contractVersion") != new.get("contractVersion"),
        "pack_update_available": bool(new.get("npmLatest")) and new.get("npmLatest") != pack.get("version"),
    }
    if old is None:
        return d
    ot, nt = old.get("tools", {}), new.get("tools", {})
    d["version"] = [old.get("contractVersion"), new.get("contractVersion")]
    d["build"] = [old.get("buildSha"), new.get("buildSha")]
    d["tools_added"] = sorted(nt.keys() - ot.keys())
    d["tools_removed"] = sorted(ot.keys() - nt.keys())
    d["tools_changed"] = sorted(k for k in ot.keys() & nt.keys() if ot[k] != nt[k])
    d["changed"] = (d["version"][0] != d["version"][1] or d["build"][0] != d["build"][1]
                    or bool(d["tools_added"] or d["tools_removed"] or d["tools_changed"]))
    return d
```

Add to `manager/scheduler/jobs.py` (import `diff_surfaces, observe` from `manager.platform.watch`):

```python
async def job_watch(ctx: JobContext) -> None:
    try:
        new = await observe(ctx.client, ctx.settings.pack_dir)
    except PlatformError as e:
        _beat(ctx, "watch", False, e.message)
        return
    with ctx.session_factory() as s:
        old = get_state(s, "surface", {}) or None
        d = diff_surfaces(old, new)
        if d["changed"]:
            record(s, "contract.drift", d | {"observedAt": new["observedAt"]})
            set_state(s, "writes_blocked", {
                "blocked": True, "since": new["observedAt"], "acknowledged": None,
                "reason": f"contract {d['version'][0]} -> {d['version'][1]}, build {d['build'][0]} -> {d['build'][1]}"})
        if d["pack_stale"] or d["pack_update_available"]:
            record(s, "pack.refresh_recommended", {
                "installed": new["pack"], "npmLatest": new["npmLatest"], "live": new["contractVersion"],
                "command": "npx skills add playbattlegrid/battlegrid-mcp  (host action: the container has no node)"})
        set_state(s, "surface", new)
        s.commit()
    _beat(ctx, "watch", True, f"{new['contractVersion']}@{(new.get('buildSha') or '')[:7]} tools={len(new['tools'])}")
```

Register it as a process: in `manager/commands/run.py` import `job_watch` and add `"watch": job_watch` to `JOBS`. The `watch` service from Task 1 (`run watch --every 600`) runs it; `docker compose stop watch` switches it off.

In `manager/settings.py` add `pack_dir: str | None = Field(default=None, alias="PACK_DIR")`. Task 1's `compose.yaml` already mounts the pack read-only at `/pack` (from `PACK_HOST_DIR`) and sets `PACK_DIR`.

```python
# manager/commands/contract.py
import argparse
from datetime import UTC, datetime

from manager.audit.ledger import get_state, record, set_state
from manager.cli import register
from manager.db.session import make_engine, make_session_factory
from manager.settings import get_settings


def _add(p: argparse.ArgumentParser) -> None:
    p.add_argument("action", choices=["ack", "status"])
    p.add_argument("version", nargs="?")


def _run(a: argparse.Namespace) -> int:
    Session = make_session_factory(make_engine(get_settings().database_url))
    with Session() as s:
        surface = get_state(s, "surface", {})
        blocked = get_state(s, "writes_blocked", {"blocked": False})
        if a.action == "status":
            print("live:", surface.get("contractVersion"), surface.get("buildSha"), "| writes_blocked:", blocked)
            return 0
        if a.version != surface.get("contractVersion"):
            print(f"refusing: live contract is {surface.get('contractVersion')}, you acknowledged {a.version}")
            return 2
        record(s, "contract.acknowledged", {"version": a.version, "build": surface.get("buildSha")})
        set_state(s, "writes_blocked", {"blocked": False, "reason": None, "since": None, "acknowledged": a.version})
        set_state(s, "contract", {"acknowledged": a.version, "at": datetime.now(UTC).isoformat()})
        s.commit()
        print("acknowledged", a.version)
    return 0


register("contract", "Acknowledge a platform contract version (unblocks writes)", _add, _run)
```

Register it in `manager/commands/__init__.py`. Add to `manager/api/app.py`:

```python
    @app.get("/api/platform/changes", dependencies=[Depends(auth)])
    def platform_changes(limit: int = Query(default=20, le=200)):
        with ctx.session_factory() as s:
            return {"surface": get_state(s, "surface", {}),
                    "writes_blocked": get_state(s, "writes_blocked", {"blocked": False}),
                    "drift": [{"at": e.at.isoformat(), **e.payload} for e in query(s, kind="contract.drift", limit=limit)],
                    "pack": [{"at": e.at.isoformat(), **e.payload} for e in query(s, kind="pack.refresh_recommended", limit=5)]}
```

- [ ] **Step 4: Run** `pytest -q` → all green.
- [ ] **Step 5: Live check** — `docker compose up -d --build` (the `watch` service observes once at start), then `curl -s -H "Authorization: Bearer $MANAGER_TOKEN" http://127.0.0.1:8790/api/platform/changes` shows `surface.contractVersion` equal to the live `/mcp/version` and a `tools` map with one entry per live tool (115 today; the number is reported, never asserted).
- [ ] **Step 6: Commit** `"Platform watch: version, build, per-tool schema hashes, pack freshness; drift blocks writes until acknowledged"`.

## Exit gate for Phase 0

- `docs/phase-0/inventory-report.md` reviewed by the user (the real roster: 9 agents, 20/20 Radar on Cycle-1, open positions, wallet).
- `docs/phase-0/oauth.md` states whether the manager's OAuth client coexists with mcporter's.
- `docs/phase-0/measurements.md` filled (notional, LLM cost, rate headroom).
- Windows task "OMEGA TPO panel" disabled; `panel.pulled` rows hourly for 24 h.
- `pytest -q` green; `docker compose up -d` healthy; `/health` reports `safe:false` and the live contract.
- `docker compose ps` lists `postgres`, `api`, `watch`, `inventory` (and `panel` under its profile), and `docker compose stop <service>` stops exactly that job and nothing else.
- `/api/platform/changes` shows a baseline surface and, after any deployment, a `contract.drift` event with the per-tool diff.

Then write `2026-09-14-battlegrid-manager-phase-1.md` from the epic's Phase 1 table.
