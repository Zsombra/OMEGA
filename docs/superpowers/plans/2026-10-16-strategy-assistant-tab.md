# Strategy Assistant Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Strategy tab in the Hermes BattleGrid plugin where the user chats with a free model that builds or revises
a BattleGrid strategy as an OMEGA thesis, previews it, stages it, and commits it after one approval in the tab.

**Architecture:**
- A new manager job, `strategist`, runs as its own compose service. It takes queued chat turns, asks a free Nous model
  for a thesis in JSON, and runs each thesis through the existing `manager.authoring.pipeline`, which does OMEGA
  planning and every existing check.
- New bearer-protected `/api/strategy/*` routes expose chats, plans, the read-only preview, stage, commit, and a
  commit-only approve.
- The plugin proxies those routes, and a new `StrategyTab` in `desktop/plugin.js` renders them.
- No new write path: stage and commit are the existing STAGE_STRATEGY and COMMIT_STRATEGY action rows.

**Tech Stack:**
- Python 3.12, FastAPI, SQLAlchemy 2 (sqlite in tests, Postgres live) and `httpx2` for the model call.
- React through `@hermes/plugin-sdk` for the tab.
- pytest with `asyncio_mode=auto`.

**Spec:** `OMEGA/docs/superpowers/specs/2026-10-16-strategy-assistant-tab-design.md` (approved 2026-10-16).

**Repo for every path below:** `C:/Users/rafae/Documents/GitHub/battlegrid-manager` (call it `$BGM`). Work in a
worktree on the branch `feat/strategy-assistant-tab`. Run tests with
`$BGM/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <paths>`. Plain `python` lacks the `omega` package,
so always use the venv's.

## Global Constraints

- FREE models only. Every id in `STRATEGIST_FREE_MODELS` ends `:free`, and any other id is refused at call time.
  The initial list is `("poolside/laguna-s-2.1:free",)`.
- The model endpoint is `https://inference-api.nousresearch.com/v1/chat/completions`. The key is read from the
  environment variable `NOUS_API_KEY`, which the user sets in `$BGM/.env`. Never copy, print or log the key.
- The model never calls BattleGrid and gets no tool definitions. It emits one JSON object:
  `{"reply": str, "thesis": {...} | null, "unmappable": [str]}`.
- Every thesis goes through `manager.authoring.pipeline.build` and then `pipeline.store`. There is exactly ONE repair
  round after a FAIL.
- `manager/strategist/*` must not import `manager.actions.write_client`.
- The approve route accepts only COMMIT_STRATEGY rows; any other kind gets a 400.
- The tab never binds, deploys, funds or creates an agent.
- API conventions:
  - a refusal is a 400 with `{"error": text}`, never a 422;
  - `by` is optional, defaults to `"plugin"` and is at most 32 characters;
  - a note is required on stage, commit and approve.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **The model wraps its JSON in prose or ```json fences.** It should still be parsed (Task 4,
   `test_extract_json_*`). If no JSON object is present at all, that counts as a repair-round failure, not a crash.
2. **A second message sent while a turn is QUEUED or RUNNING** should get a 400 ("wait for the reply"), not run two
   turns that both write the chat's thesis (Task 6, `test_message_refused_while_turn_pending`).
3. **Revising a strategy the player is editing in the web app** (a draft the manager did not write) should be refused
   when the chat opens, with the platform's reason (Task 6, `test_revise_refused_on_foreign_draft`).
4. **A stale approval:** the commit row changed after the dialog's dry describe, so its `params_sha` no longer
   matches. Approve should be refused with `approve`'s own text, and nothing sent (Task 7,
   `test_approve_refused_on_params_sha_mismatch`).
5. **Very long or empty user text.** Empty is a 400. More than 4000 characters is a 400 that says the limit, so a
   pasted document can't blow the model's context (Task 6, `test_message_text_bounds`).

---

## File structure

| File | Responsibility |
|---|---|
| `manager/authoring/live.py` (new) | `live_contract(s)`, extracted from `commands/strategy.py::_live` |
| `manager/authoring/current.py` (new) | `async read_current(client, strategy_id) -> dict`, extracted from `commands/strategy.py::_current` |
| `manager/db/models.py` (modify) | `StrategyChat`, `StrategyChatTurn` |
| `manager/strategist/__init__.py` (new) | empty |
| `manager/strategist/store.py` (new) | create/read chats and turns, claim the next queued turn |
| `manager/strategist/model.py` (new) | `complete(messages, *, model, post=...) -> str`, free-model allowlist |
| `manager/strategist/brief.md` (new) | the system brief |
| `manager/strategist/turn.py` (new) | `extract_json`, `build_messages`, `run_turn` |
| `manager/scheduler/jobs.py` (modify) | `job_strategist` |
| `manager/commands/run.py` (modify) | register `strategist` |
| `compose.yaml` (modify) | the `strategist` service |
| `manager/api/strategy_routes.py` (new) | `add_strategy_routes(app, ctx, auth)` |
| `manager/actions/dry.py` (new) | `async dry_lines(client, session_factory, action_id, *, now)`, extracted from `commands/actions.py::_dry` |
| `manager/api/app.py` (modify) | call `add_strategy_routes` |
| `hermes/plugin/battlegrid-manager/dashboard/plugin_api.py` (modify) | proxy routes |
| `hermes/plugin/battlegrid-manager/desktop/plugin.js` (modify) | `StrategyTab` |
| `manager/commands/strategist.py` (new) | `manager strategist proof` (the 10-prompt model proof) |
| `tests/fixtures/strategist/prompts.json` (new) | the 10 intake prompts |
| tests | `tests/authoring/test_live_current.py`, `tests/strategist/test_store.py`, `test_model.py`, `test_turn.py`, `test_job.py`, `tests/api/test_strategy_routes.py`, `tests/hermes/test_plugin_api.py` (+), `tests/hermes/test_plugin_js.py` (+), `tests/risk/test_import_boundary.py` (+), `tests/actions/test_strategy_propose.py` (amend) |

---

### Task 1: Extract the live-contract and current-strategy readers

**Files:**
- Create: `manager/authoring/live.py`, `manager/authoring/current.py`
- Modify: `manager/commands/strategy.py` (`_live` at ~119-136, `_current` at ~422-466), so both call the new modules
- Test: `tests/authoring/test_live_current.py`

**Interfaces:**
- Produces:
  - `live_contract(s: Session) -> tuple[str, str] | None`, the exact behaviour of today's `_live`;
  - `async read_current(client, strategy_id: str) -> dict`, which returns the `get_strategy_draft`-shaped answer that
    `_current` builds today (the `draft`, `draftVersion`, `committedRevision`, `source` and `revision` keys) and
    lets `PlatformError` propagate.

- [ ] **Step 1: Write the failing tests**

```python
# tests/authoring/test_live_current.py
import pytest
from datetime import UTC, datetime
from manager.audit.ledger import set_state
from manager.authoring.current import read_current
from manager.authoring.live import live_contract
from manager.db.session import init_db, make_engine, make_session_factory
from tests.platform.fake import FakePlatform


def _factory():
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    return make_session_factory(e)


def test_live_contract_none_when_unread():
    with _factory()() as s:
        assert live_contract(s) is None


async def test_read_current_falls_back_to_get_strategy_when_no_draft():
    strategy = {"id": "s1", "revision": 3, "name": "X", "timeframe": "1h"}
    client = FakePlatform({"get_strategy_draft": {"draft": None, "draftVersion": 0, "committedRevision": 3},
                           "get_strategy": {"strategy": strategy}})
    answer = await read_current(client, "s1")
    assert answer["source"] == "get_strategy" and answer["revision"] == 3
    assert answer["draft"]["strategyId"] == "s1" and answer["draft"]["version"] == 0
    assert [c[0] for c in client.calls] == ["get_strategy_draft", "get_strategy"]


async def test_read_current_returns_the_draft_when_one_exists():
    held = {"draft": {"strategyId": "s1", "content": {"IDENTITY": {"name": "X"}}, "version": 4},
            "draftVersion": 4, "committedRevision": 3}
    client = FakePlatform({"get_strategy_draft": held})
    assert (await read_current(client, "s1"))["draftVersion"] == 4
```

`strategy` must carry at least one `AXIS_FIELDS` field, or `axes_of_strategy` raises. Before running, read
`AXIS_FIELDS` in `manager/commands/strategy.py:389-402` and set `strategy`'s keys to real field names from it.

- [ ] **Step 2: Run the tests and watch them fail**

Run: `... -m pytest -q tests/authoring/test_live_current.py`
Expected: FAIL with `ModuleNotFoundError: manager.authoring.live`.

- [ ] **Step 3: Implement the two modules**

Move the body of `_live` verbatim into `live.py` as `live_contract(s)`, together with the constants and imports it
uses (`CONTRACT_LIVE_MAX_AGE_S`, `get_state`). Move `axes_of_strategy`, `AXIS_FIELDS` and the inner `go()` of
`_current` into `current.py`:

```python
# manager/authoring/current.py
"""The strategy a revision starts from: the player's draft if there is one, else the committed strategy as axes.
Extracted from `manager strategy current` (2026-10-16) so the Strategy tab's revise chat reads it the same way."""
from __future__ import annotations

AXIS_FIELDS: dict[str, tuple[str, ...]] = ...   # moved verbatim from manager/commands/strategy.py


def axes_of_strategy(strategy: dict) -> dict:
    ...                                          # moved verbatim


async def read_current(client, strategy_id: str) -> dict:
    answer = await client.call("get_strategy_draft", {"strategyId": strategy_id})
    if isinstance(answer, dict) and answer.get("draft") is None:
        read = await client.call("get_strategy", {"strategyId": strategy_id})
        strategy = read.get("strategy") if isinstance(read, dict) else None
        answer = {"draft": {"strategyId": strategy_id, "content": axes_of_strategy(strategy), "version": 0},
                  "draftVersion": answer.get("draftVersion", 0),
                  "committedRevision": answer.get("committedRevision"),
                  "source": "get_strategy", "revision": (strategy or {}).get("revision")}
    return answer
```

In `commands/strategy.py`:
- re-export the moved names (`from manager.authoring.current import AXIS_FIELDS, axes_of_strategy, read_current`),
  so that existing imports and tests keep working;
- make `_live = live_contract`, as a one-line alias or a thin wrapper;
- make `_current`'s `go()` call `answer = await read_current(client, a.strategy_id)` inside its existing
  `try/except PlatformError`.

- [ ] **Step 4: Run the new tests and the existing strategy tests**

Run: `... -m pytest -q tests/authoring/test_live_current.py tests/commands/test_strategy.py`
Expected: all PASS, with no change in `tests/commands/test_strategy.py`.

- [ ] **Step 5: Commit**

```bash
git add manager/authoring/live.py manager/authoring/current.py manager/commands/strategy.py tests/authoring/test_live_current.py
git commit -m "Extract live_contract and read_current from manager strategy, for the Strategy tab's revise chat"
```

---

### Task 2: Chat tables and store

**Files:**
- Modify: `manager/db/models.py` (append two models)
- Create: `manager/strategist/__init__.py` (empty), `manager/strategist/store.py`
- Test: `tests/strategist/__init__.py` (empty), `tests/strategist/test_store.py`

**Interfaces:**
- Produces:
  - the models `StrategyChat` and `StrategyChatTurn` (fields below);
  - `create_chat(s, *, kind: str, by: str, now, strategy_id: str | None = None, current_axes: dict | None = None,
    current_meta: dict | None = None) -> StrategyChat`;
  - `add_user_turn(s, chat_id: int, text: str, *, now) -> StrategyChatTurn`, which raises `ChatBusy` if a turn is
    QUEUED or RUNNING;
  - `claim_next(s, *, now) -> StrategyChatTurn | None`, which moves the oldest QUEUED turn to RUNNING;
  - `finish_turn(s, turn, *, outcome: dict, now)`;
  - `fail_turn(s, turn, *, error: str, now)`;
  - `chat_view(s, chat_id: int) -> dict`.
- `ChatBusy` is a subclass of `ValueError`. No function commits; the caller does.

- [ ] **Step 1: Write the failing tests**

```python
# tests/strategist/test_store.py
import pytest
from datetime import UTC, datetime
from manager.db.session import init_db, make_engine, make_session_factory
from manager.strategist.store import ChatBusy, add_user_turn, chat_view, claim_next, create_chat, finish_turn

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


@pytest.fixture
def s():
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    with make_session_factory(e)() as session:
        yield session


def test_a_user_turn_queues_and_is_claimed_once(s):
    chat = create_chat(s, kind="new", by="plugin", now=NOW)
    add_user_turn(s, chat.id, "fade funding extremes on 1h", now=NOW)
    turn = claim_next(s, now=NOW)
    assert turn.status == "RUNNING" and turn.text == "fade funding extremes on 1h"
    assert claim_next(s, now=NOW) is None


def test_message_refused_while_turn_pending(s):
    chat = create_chat(s, kind="new", by="plugin", now=NOW)
    add_user_turn(s, chat.id, "one", now=NOW)
    with pytest.raises(ChatBusy):
        add_user_turn(s, chat.id, "two", now=NOW)


def test_finish_writes_the_assistant_turn_and_the_chat_thesis(s):
    chat = create_chat(s, kind="new", by="plugin", now=NOW)
    add_user_turn(s, chat.id, "x", now=NOW)
    turn = claim_next(s, now=NOW)
    finish_turn(s, turn, now=NOW, outcome={"reply": "built", "thesis": {"name": "T"}, "planId": 7,
                                           "verdict": "PASS", "checks": [], "unmappable": [], "model": "m:free"})
    view = chat_view(s, chat.id)
    assert view["chat"]["thesis"] == {"name": "T"} and view["chat"]["planId"] == 7
    assert [t["role"] for t in view["turns"]] == ["user", "assistant"]
    assert view["turns"][0]["status"] == "DONE"
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `... -m pytest -q tests/strategist/test_store.py`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the models and the store**

```python
# manager/db/models.py (append)
class StrategyChat(Base):
    """A Strategy-tab conversation (2026-10-16 spec): a new strategy, or a revision of `strategy_id` starting from
    `current_axes` (read by manager.authoring.current.read_current when the chat opened)."""
    __tablename__ = "strategy_chats"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(8))                       # new|revise
    strategy_id: Mapped[str | None] = mapped_column(String(36), index=True)
    current_axes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # source, revision, draftVersion
    thesis: Mapped[dict | None] = mapped_column(JSON, nullable=True)   # the latest thesis that PASSED
    plan_id: Mapped[int | None] = mapped_column(Integer)
    stage_action_id: Mapped[int | None] = mapped_column(Integer)
    commit_action_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_by: Mapped[str] = mapped_column(String(32))


class StrategyChatTurn(Base):
    __tablename__ = "strategy_chat_turns"
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(Integer, index=True)
    role: Mapped[str] = mapped_column(String(10))                      # user|assistant
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(8), index=True)         # QUEUED|RUNNING|DONE|FAILED
    model: Mapped[str | None] = mapped_column(String(80))
    thesis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    plan_id: Mapped[int | None] = mapped_column(Integer)
    verdict: Mapped[str | None] = mapped_column(String(4))
    findings: Mapped[list] = mapped_column(JSON, default=list)
    unmappable: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

```python
# manager/strategist/store.py
"""The Strategy tab's chats (2026-10-16 spec, section 6). Storage only: no model, no BattleGrid, no commit."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from manager.db.models import StrategyChat, StrategyChatTurn, StrategyPlanRow

PENDING = ("QUEUED", "RUNNING")


class ChatBusy(ValueError):
    """A turn of this chat is still QUEUED or RUNNING."""


def create_chat(s: Session, *, kind: str, by: str, now: datetime, strategy_id: str | None = None,
                current_axes: dict | None = None, current_meta: dict | None = None) -> StrategyChat:
    chat = StrategyChat(kind=kind, strategy_id=strategy_id, current_axes=current_axes, current_meta=current_meta,
                        created_at=now, created_by=by)
    s.add(chat)
    s.flush()
    return chat


def add_user_turn(s: Session, chat_id: int, text: str, *, now: datetime) -> StrategyChatTurn:
    busy = s.scalar(select(StrategyChatTurn.id).where(StrategyChatTurn.chat_id == chat_id,
                                                      StrategyChatTurn.status.in_(PENDING)))
    if busy is not None:
        raise ChatBusy("the strategist is still answering this chat: wait for the reply")
    turn = StrategyChatTurn(chat_id=chat_id, role="user", text=text, status="QUEUED", findings=[], unmappable=[],
                            created_at=now)
    s.add(turn)
    s.flush()
    return turn


def claim_next(s: Session, *, now: datetime) -> StrategyChatTurn | None:
    turn = s.scalars(select(StrategyChatTurn).where(StrategyChatTurn.status == "QUEUED")
                     .order_by(StrategyChatTurn.id).limit(1)).first()
    if turn is None:
        return None
    turn.status = "RUNNING"
    s.flush()
    return turn


def finish_turn(s: Session, turn: StrategyChatTurn, *, outcome: dict, now: datetime) -> StrategyChatTurn:
    turn.status, turn.finished_at = "DONE", now
    reply = StrategyChatTurn(chat_id=turn.chat_id, role="assistant", text=outcome.get("reply") or "", status="DONE",
                             model=outcome.get("model"), thesis=outcome.get("thesis"), plan_id=outcome.get("planId"),
                             verdict=outcome.get("verdict"), findings=outcome.get("checks") or [],
                             unmappable=outcome.get("unmappable") or [], created_at=now, finished_at=now)
    s.add(reply)
    chat = s.get(StrategyChat, turn.chat_id)
    if outcome.get("planId") is not None:
        chat.plan_id = outcome["planId"]
    if outcome.get("verdict") == "PASS" and outcome.get("thesis"):
        chat.thesis = outcome["thesis"]
    s.flush()
    return reply


def fail_turn(s: Session, turn: StrategyChatTurn, *, error: str, now: datetime) -> None:
    turn.status, turn.error, turn.finished_at = "FAILED", error[:2000], now
    s.flush()


def _turn(t: StrategyChatTurn) -> dict:
    return {"id": t.id, "role": t.role, "text": t.text, "status": t.status, "model": t.model, "planId": t.plan_id,
            "verdict": t.verdict, "findings": t.findings or [], "unmappable": t.unmappable or [], "error": t.error,
            "createdAt": t.created_at.isoformat() if t.created_at else None}


def chat_view(s: Session, chat_id: int) -> dict:
    chat = s.get(StrategyChat, chat_id)
    if chat is None:
        raise ValueError(f"chat {chat_id} is not known")
    turns = list(s.scalars(select(StrategyChatTurn).where(StrategyChatTurn.chat_id == chat_id)
                           .order_by(StrategyChatTurn.id)))
    plan = s.get(StrategyPlanRow, chat.plan_id) if chat.plan_id else None
    return {"chat": {"id": chat.id, "kind": chat.kind, "strategyId": chat.strategy_id, "thesis": chat.thesis,
                     "planId": chat.plan_id, "stageActionId": chat.stage_action_id,
                     "commitActionId": chat.commit_action_id, "currentMeta": chat.current_meta,
                     "createdAt": chat.created_at.isoformat()},
            "turns": [_turn(t) for t in turns],
            "plan": None if plan is None else {"id": plan.id, "operation": plan.operation, "name": plan.name,
                                               "verdict": plan.verdict, "checks": plan.checks, "brief": plan.brief},
            "pending": any(t.status in PENDING for t in turns)}
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `... -m pytest -q tests/strategist/test_store.py`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add manager/db/models.py manager/strategist tests/strategist
git commit -m "Strategy tab: the chat and turn tables and their store"
```

---

### Task 3: Free-model client

**Files:**
- Create: `manager/strategist/model.py`
- Test: `tests/strategist/test_model.py`

**Interfaces:**
- Produces:
  - `STRATEGIST_FREE_MODELS: tuple[str, ...]`;
  - `NOUS_CHAT_URL`;
  - `class ModelError(RuntimeError)`;
  - `complete(messages: list[dict], *, model: str, api_key: str | None, post=httpx2.post, sleep=time.sleep) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/strategist/test_model.py
import pytest
from manager.strategist.model import STRATEGIST_FREE_MODELS, ModelError, complete


class _R:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers, self.text = status, body or {}, headers or {}, str(body)

    def json(self):
        return self._body


def _ok(text):
    return _R(200, {"choices": [{"message": {"content": text}}]})


def test_every_allowed_model_is_free():
    assert STRATEGIST_FREE_MODELS and all(m.endswith(":free") for m in STRATEGIST_FREE_MODELS)


def test_a_paid_model_is_refused_before_any_call():
    calls = []
    with pytest.raises(ModelError, match="not a free model"):
        complete([], model="anthropic/claude", api_key="k", post=lambda *a, **k: calls.append(1))
    assert calls == []


def test_a_missing_key_is_named():
    with pytest.raises(ModelError, match="no model key"):
        complete([], model=STRATEGIST_FREE_MODELS[0], api_key=None, post=lambda *a, **k: _ok("x"))


def test_one_retry_on_429_then_the_content():
    answers = iter([_R(429, headers={"Retry-After": "2"}), _ok("hello")])
    slept = []
    out = complete([{"role": "user", "content": "hi"}], model=STRATEGIST_FREE_MODELS[0], api_key="k",
                   post=lambda *a, **k: next(answers), sleep=slept.append)
    assert out == "hello" and slept == [2.0]


def test_a_second_429_is_an_error():
    with pytest.raises(ModelError, match="429"):
        complete([], model=STRATEGIST_FREE_MODELS[0], api_key="k", post=lambda *a, **k: _R(429), sleep=lambda s: None)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `... -m pytest -q tests/strategist/test_model.py`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the client**

```python
# manager/strategist/model.py
"""The strategist's model call (2026-10-16 spec, D5): Nous's OpenAI-compatible chat API, FREE models only. The
manager's first direct LLM call; it sends text and gets text - no tools, no BattleGrid."""
from __future__ import annotations

import time

import httpx2

NOUS_CHAT_URL = "https://inference-api.nousresearch.com/v1/chat/completions"
STRATEGIST_FREE_MODELS: tuple[str, ...] = ("poolside/laguna-s-2.1:free",)
TIMEOUT_S = 90.0
MAX_RETRY_AFTER_S = 120.0


class ModelError(RuntimeError):
    """The model call failed; the message is what the tab shows (never carries the key)."""


def complete(messages: list[dict], *, model: str, api_key: str | None, post=httpx2.post, sleep=time.sleep) -> str:
    if model not in STRATEGIST_FREE_MODELS:
        raise ModelError(f"{model!r} is not a free model on the strategist's allowlist")
    if not api_key:
        raise ModelError("the strategist has no model key: add NOUS_API_KEY=... to battlegrid-manager/.env")
    body = {"model": model, "messages": messages, "temperature": 0.2}
    headers = {"Authorization": f"Bearer {api_key}"}
    for attempt in (1, 2):
        try:
            r = post(NOUS_CHAT_URL, json=body, headers=headers, timeout=TIMEOUT_S)
        except Exception as e:  # noqa: BLE001 - transport errors become the turn's error text
            raise ModelError(f"the model call failed: {type(e).__name__}") from None
        if r.status_code == 429 and attempt == 1:
            try:
                wait = float(r.headers.get("Retry-After", "10"))
            except ValueError:
                wait = 10.0
            sleep(min(wait, MAX_RETRY_AFTER_S))
            continue
        if r.status_code != 200:
            raise ModelError(f"the model answered HTTP {r.status_code}")
        try:
            return r.json()["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError, ValueError):
            raise ModelError("the model's answer had no message content") from None
    raise ModelError("the model answered HTTP 429 twice")
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `... -m pytest -q tests/strategist/test_model.py`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add manager/strategist/model.py tests/strategist/test_model.py
git commit -m "Strategy tab: the free-model client (allowlist, named missing key, one 429 retry)"
```

---

### Task 4: The brief and the turn runner

**Files:**
- Create: `manager/strategist/brief.md`, `manager/strategist/turn.py`
- Test: `tests/strategist/test_turn.py`

**Interfaces:**
- Consumes:
  - from Task 1, `live_contract(s)`;
  - from Task 2, `StrategyChat`;
  - `pipeline.build(thesis_dict, *, update, current, current_source, surface_tools, live) -> dict`;
  - `pipeline.store(s, built, *, thesis_dict, update, replace, by, now) -> int`;
  - `get_state(s, "surface_tools", {})`;
  - `canonical_sha` from `manager.authoring.definitions`.
- Produces:
  - `extract_json(text: str) -> dict | None`;
  - `build_messages(chat, history: list[dict], user_text: str) -> list[dict]`;
  - `run_turn(s, chat, user_text: str, *, history: list[dict], complete, now) -> dict`.

  The `outcome` dict that `run_turn` returns has the keys `reply`, `thesis`, `planId`, `verdict`, `checks`,
  `unmappable`, `model` and `repaired`. `complete` is a callable `(messages) -> str`.

- [ ] **Step 1: Write the brief**

```markdown
<!-- manager/strategist/brief.md -->
You are the BattleGrid strategy assistant inside the user's Hermes plugin. You turn the user's trading idea into ONE
OMEGA thesis. You never trade, bind, deploy or fund; the user stages and commits from the tab.

How BattleGrid strategies work now (contract 108 and later):
- A strategy's entry gate is its CONDITIONS. There are no signal scores and no score gate. OMEGA builds the
  conditions for you from the modules you choose; the module tier (0-3) is shown to the user and changes nothing.
- `anchor` is the timeframe: exactly one of "5m", "15m", "1h", "4h".
- `stance`: "ALIGN" (the tape should agree with the direction: trend ideas) or "FADE" (the crowd should be leaning
  the other way: contrarian ideas). BOLLINGER, MFI, RSI and STOCHASTIC read inverted under FADE.
- `weights`: {MODULE: tier} for the modules whose readings decide entries. `context`: modules shown in the report
  as reading material only. Use only modules from the MENU below.
- `exits`: condition roles whose entry condition is also an exit (leave empty unless the user asks for it).
- `execution` and `coin_selection`: leave null unless the user names a value; null means the measured defaults.

Rules:
1. Ask at most one short question when the idea is missing what moves price, the timeframe, or the stance; otherwise
   build.
2. You choose MODULES, not exact clauses. If the user states an exact rule ("RSI below 30 and close crosses VWAP"),
   build the nearest thesis and say plainly in `reply` that the exact rule is approximated by the modules you chose.
3. If no module measures part of the idea, list that part in `unmappable` and offer the nearest expressible thesis,
   labelled as different from what was asked.
4. Check the meaning, not just the shape: a mean-reversion idea must not end up buying strength.
5. When you receive FINDINGS from the checker, fix the thesis so they go away, or explain why you cannot.

Answer with exactly one JSON object and nothing else:
{"reply": "<what you built and why, plain English, short>", "thesis": {"name": "...", "tagline": "...",
 "description": "...", "anchor": "1h", "weights": {}, "stance": "ALIGN", "context": [], "coin_selection": null,
 "execution": null, "exits": []} or null, "unmappable": []}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/strategist/test_turn.py
import json
from datetime import UTC, datetime
from manager.db.session import init_db, make_engine, make_session_factory
from manager.strategist import turn as T
from manager.strategist.store import create_chat

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
GOOD = {"name": "Funding Fade", "anchor": "1h", "weights": {"FUNDING": 2}, "stance": "FADE"}


def _s():
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    return make_session_factory(e)()


def _answer(thesis, reply="ok", unmappable=()):
    return json.dumps({"reply": reply, "thesis": thesis, "unmappable": list(unmappable)})


def test_extract_json_plain_and_fenced_and_prosed():
    assert T.extract_json('{"a": 1}') == {"a": 1}
    assert T.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert T.extract_json('Here you go: {"a": {"b": 2}} hope it helps') == {"a": {"b": 2}}
    assert T.extract_json("no json here") is None


def test_a_passing_thesis_is_planned_and_stored(monkeypatch):
    s = _s()
    chat = create_chat(s, kind="new", by="plugin", now=NOW)
    monkeypatch.setattr(T, "_build", lambda s, chat, thesis: {"verdict": "PASS", "checks": [], "brief": "b", "request": {"axes": {}}})
    monkeypatch.setattr(T, "_store", lambda s, chat, built, thesis, now: 11)
    out = T.run_turn(s, chat, "fade funding", history=[], complete=lambda m: _answer(GOOD), now=NOW)
    assert out["verdict"] == "PASS" and out["planId"] == 11 and out["repaired"] is False


def test_one_repair_round_with_the_findings(monkeypatch):
    s = _s()
    chat = create_chat(s, kind="new", by="plugin", now=NOW)
    verdicts = iter(["FAIL", "PASS"])
    monkeypatch.setattr(T, "_build", lambda s, chat, thesis: {"verdict": next(verdicts), "brief": "b", "request": {"axes": {}},
                        "checks": [{"code": "NO_ENTRY_CONDITION", "message": "no gate", "severity": "error"}]})
    monkeypatch.setattr(T, "_store", lambda s, chat, built, thesis, now: 12)
    seen = []
    out = T.run_turn(s, chat, "x", history=[], complete=lambda m: seen.append(m) or _answer(GOOD), now=NOW)
    assert out["repaired"] is True and out["verdict"] == "PASS"
    assert "NO_ENTRY_CONDITION" in seen[1][-1]["content"]


def test_two_failures_stop_and_report(monkeypatch):
    s = _s()
    chat = create_chat(s, kind="new", by="plugin", now=NOW)
    monkeypatch.setattr(T, "_build", lambda s, chat, thesis: {"verdict": "FAIL", "brief": "b", "request": {"axes": {}},
                        "checks": [{"code": "X", "message": "bad", "severity": "error"}]})
    monkeypatch.setattr(T, "_store", lambda s, chat, built, thesis, now: 13)
    calls = []
    out = T.run_turn(s, chat, "x", history=[], complete=lambda m: calls.append(1) or _answer(GOOD), now=NOW)
    assert len(calls) == 2 and out["verdict"] == "FAIL" and out["checks"][0]["code"] == "X"


def test_no_json_twice_is_an_error_outcome():
    s = _s()
    chat = create_chat(s, kind="new", by="plugin", now=NOW)
    out = T.run_turn(s, chat, "x", history=[], complete=lambda m: "I think you should buy", now=NOW)
    assert out["verdict"] is None and out["thesis"] is None and "no JSON" in out["reply"]


def test_a_question_without_thesis_plans_nothing(monkeypatch):
    s = _s()
    chat = create_chat(s, kind="new", by="plugin", now=NOW)
    monkeypatch.setattr(T, "_build", lambda *a: (_ for _ in ()).throw(AssertionError("must not build")))
    out = T.run_turn(s, chat, "x", history=[], complete=lambda m: _answer(None, reply="Which timeframe?"), now=NOW)
    assert out["reply"] == "Which timeframe?" and out["planId"] is None


def test_unmappable_is_passed_through(monkeypatch):
    s = _s()
    chat = create_chat(s, kind="new", by="plugin", now=NOW)
    monkeypatch.setattr(T, "_build", lambda s, chat, thesis: {"verdict": "PASS", "checks": [], "brief": "b", "request": {"axes": {}}})
    monkeypatch.setattr(T, "_store", lambda s, chat, built, thesis, now: 14)
    out = T.run_turn(s, chat, "x", history=[], now=NOW,
                     complete=lambda m: _answer(GOOD, unmappable=["news sentiment"]))
    assert out["unmappable"] == ["news sentiment"]
```

- [ ] **Step 3: Run the tests and watch them fail**

Run: `... -m pytest -q tests/strategist/test_turn.py`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement the turn runner**

```python
# manager/strategist/turn.py
"""One Strategy-tab turn (2026-10-16 spec, sections 4-5): the model writes a thesis as JSON, the existing authoring
pipeline plans and checks it, ONE repair round on FAIL. No BattleGrid call here; the model is `complete`."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from manager.audit.ledger import get_state

BRIEF = (Path(__file__).with_name("brief.md")).read_text(encoding="utf-8")
HISTORY_TURNS = 10
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> dict | None:
    """The first JSON object in the model's text: bare, fenced, or embedded in prose."""
    if not isinstance(text, str):
        return None
    candidates = [m.group(1) for m in _FENCE.finditer(text)] + [text]
    for chunk in candidates:
        start = chunk.find("{")
        while start != -1:
            depth = 0
            for i in range(start, len(chunk)):
                if chunk[i] == "{":
                    depth += 1
                elif chunk[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            got = json.loads(chunk[start:i + 1])
                            if isinstance(got, dict):
                                return got
                        except ValueError:
                            pass
                        break
            start = chunk.find("{", start + 1)
    return None


def _menu() -> str:
    from omega.authoring import vocabulary   # lazy, as manager.authoring.pipeline imports omega
    return json.dumps(vocabulary(), default=str)[:20000]


def build_messages(chat, history: list[dict], user_text: str) -> list[dict]:
    system = BRIEF + "\n\nMENU (the measured modules):\n" + _menu()
    if chat.kind == "revise":
        system += ("\n\nYou are REVISING strategy " + str(chat.strategy_id) + ". Its current axes (anything your "
                   "thesis does not name is kept from these):\n" + json.dumps(chat.current_axes, default=str)[:12000])
    if chat.thesis:
        system += "\n\nThe current thesis of this chat:\n" + json.dumps(chat.thesis)
    msgs = [{"role": "system", "content": system}]
    for h in history[-HISTORY_TURNS:]:
        msgs.append({"role": "user" if h["role"] == "user" else "assistant", "content": h["text"]})
    msgs.append({"role": "user", "content": user_text})
    return msgs


def _build(s, chat, thesis: dict) -> dict:
    from manager.authoring import pipeline
    from manager.authoring.definitions import canonical_sha
    from manager.authoring.live import live_contract
    current = chat.current_axes if chat.kind == "revise" else None
    source = None if current is None else {"kind": "chat", "name": f"strategy chat {chat.id}",
                                           "sha256": canonical_sha(current), "axes": sorted(current)}
    return pipeline.build(thesis, update=chat.strategy_id if chat.kind == "revise" else None, current=current,
                          current_source=source, surface_tools=get_state(s, "surface_tools", {}),
                          live=live_contract(s))


def _store(s, chat, built: dict, thesis: dict, now: datetime) -> int:
    from manager.authoring import pipeline
    update = chat.strategy_id if chat.kind == "revise" else None
    return pipeline.store(s, built, thesis_dict=thesis, update=update, replace=update is not None,
                          by=f"strategist:{chat.created_by}"[:32], now=now)


def _findings_text(checks: list[dict]) -> str:
    lines = [f"- {c.get('severity')} {c.get('code')} at {c.get('path')}: {c.get('message')}" for c in checks
             if c.get("severity") in ("error", "ERROR", "warning", "WARNING")]
    return "FINDINGS from the checker; fix the thesis so they go away and answer with the JSON object again:\n" + \
        "\n".join(lines or ["- (the plan FAILED with no listed finding)"])


def run_turn(s, chat, user_text: str, *, history: list[dict], complete, now: datetime) -> dict:
    messages = build_messages(chat, history, user_text)
    out = {"reply": "", "thesis": None, "planId": None, "verdict": None, "checks": [], "unmappable": [],
           "model": None, "repaired": False}
    for attempt in (1, 2):
        raw = complete(messages)
        answer = extract_json(raw)
        if answer is None:
            if attempt == 1:
                messages += [{"role": "assistant", "content": raw},
                             {"role": "user", "content": "Answer with exactly one JSON object, nothing else."}]
                out["repaired"] = True
                continue
            out["reply"] = "The model answered with no JSON object twice; nothing was built. Send again."
            return out
        out["reply"] = str(answer.get("reply") or "")
        out["unmappable"] = [str(u) for u in (answer.get("unmappable") or []) if u]
        thesis = answer.get("thesis")
        if not isinstance(thesis, dict):
            return out                                     # a question or a refusal: nothing to plan
        try:
            built = _build(s, chat, thesis)
        except ValueError as refused:                      # thesis_from_dict: unknown/retired key, no name
            built = {"verdict": "FAIL", "brief": "", "checks": [{"source": "thesis", "severity": "error",
                     "code": "THESIS_REFUSED", "path": "", "message": str(refused)}]}
        out.update(thesis=thesis, verdict=built["verdict"], checks=built.get("checks") or [])
        if built["verdict"] == "PASS" or attempt == 2:
            if "request" in built:                         # only a real plan is stored (a refusal has no body)
                out["planId"] = _store(s, chat, built, thesis, now)
            return out
        messages += [{"role": "assistant", "content": raw}, {"role": "user", "content": _findings_text(out["checks"])}]
        out["repaired"] = True
    return out
```

- [ ] **Step 5: Run the tests and watch them pass**

Run: `... -m pytest -q tests/strategist/test_turn.py`
Expected: 7 PASS.

- [ ] **Step 6: Commit**

```bash
git add manager/strategist/brief.md manager/strategist/turn.py tests/strategist/test_turn.py
git commit -m "Strategy tab: the brief and the turn runner (JSON thesis, one repair round, pipeline-checked)"
```

---

### Task 5: The strategist job and compose service

**Files:**
- Modify:
  - `manager/scheduler/jobs.py`: add `job_strategist`;
  - `manager/commands/run.py`: add `"strategist": job_strategist` to `JOBS`;
  - `compose.yaml`: the service.
- Test: `tests/strategist/test_job.py`

**Interfaces:**
- Consumes: Task 2's `claim_next`, `finish_turn`, `fail_turn`; Task 3's `complete`; Task 4's `run_turn`.
- Produces: `async def job_strategist(ctx: JobContext, *, complete=None, now=None) -> None`.
  - It handles at most one turn per tick and always calls `_beat(ctx, "strategist", ok, note)`.
  - `complete=None` means it uses `model.complete` with `STRATEGIST_FREE_MODELS[0]` and
    `os.environ.get("NOUS_API_KEY")`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/strategist/test_job.py
from datetime import UTC, datetime
from manager.db.models import StrategyChatTurn
from manager.db.session import init_db, make_engine, make_session_factory
from manager.scheduler.jobs import JobContext, job_strategist
from manager.strategist import turn as T
from manager.strategist.model import ModelError
from manager.strategist.store import add_user_turn, chat_view, create_chat

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


def _ctx(settings):
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    return JobContext(client=None, session_factory=make_session_factory(e), settings=settings)


async def test_the_job_answers_one_queued_turn(settings, monkeypatch):
    ctx = _ctx(settings)
    with ctx.session_factory() as s:
        chat = create_chat(s, kind="new", by="plugin", now=NOW)
        add_user_turn(s, chat.id, "hello", now=NOW)
        s.commit()
        chat_id = chat.id
    monkeypatch.setattr(T, "run_turn", lambda s, chat, text, **k: {"reply": "hi", "thesis": None, "planId": None,
                        "verdict": None, "checks": [], "unmappable": [], "model": None, "repaired": False})
    await job_strategist(ctx, complete=lambda m: "", now=NOW)
    with ctx.session_factory() as s:
        view = chat_view(s, chat_id)
    assert [t["role"] for t in view["turns"]] == ["user", "assistant"] and view["pending"] is False


async def test_a_model_error_fails_the_turn_with_its_text(settings, monkeypatch):
    ctx = _ctx(settings)
    with ctx.session_factory() as s:
        chat = create_chat(s, kind="new", by="plugin", now=NOW)
        add_user_turn(s, chat.id, "hello", now=NOW)
        s.commit()

    def boom(*a, **k):
        raise ModelError("the strategist has no model key: add NOUS_API_KEY=... to battlegrid-manager/.env")
    monkeypatch.setattr(T, "run_turn", boom)
    await job_strategist(ctx, complete=lambda m: "", now=NOW)
    with ctx.session_factory() as s:
        t = s.query(StrategyChatTurn).one()
    assert t.status == "FAILED" and "NOUS_API_KEY" in t.error


async def test_an_empty_queue_is_a_quiet_tick(settings):
    await job_strategist(_ctx(settings), complete=lambda m: "", now=NOW)
```

- [ ] **Step 2: Run the tests and watch them fail**

Run: `... -m pytest -q tests/strategist/test_job.py`
Expected: FAIL with `ImportError: job_strategist`.

- [ ] **Step 3: Implement the job**

Append the job to `manager/scheduler/jobs.py`, beside the other jobs. Read `_beat`'s signature in this file first,
and match how `job_review` calls it.

```python
async def job_strategist(ctx: JobContext, *, complete=None, now: datetime | None = None) -> None:
    """The Strategy tab's turns (2026-10-16 spec): one QUEUED turn per tick -> the free model -> the authoring
    pipeline -> the reply. Model errors fail the turn with their text; nothing here calls BattleGrid."""
    import asyncio
    import os
    from manager.strategist import model as M
    from manager.strategist import turn as T
    from manager.strategist.store import chat_view, claim_next, fail_turn, finish_turn
    from manager.db.models import StrategyChat
    now = now or datetime.now(UTC)
    if complete is None:
        key = os.environ.get("NOUS_API_KEY")
        complete = lambda messages: M.complete(messages, model=M.STRATEGIST_FREE_MODELS[0], api_key=key)  # noqa: E731
    with ctx.session_factory() as s:
        turn = claim_next(s, now=now)
        s.commit()
        if turn is None:
            _beat(ctx, "strategist", True, "no queued turn")
            return
        chat = s.get(StrategyChat, turn.chat_id)
        history = [t for t in chat_view(s, chat.id)["turns"] if t["id"] != turn.id and t["status"] == "DONE"]
        try:
            outcome = await asyncio.to_thread(T.run_turn, s, chat, turn.text, history=history, complete=complete,
                                              now=now)
            outcome["model"] = outcome.get("model") or M.STRATEGIST_FREE_MODELS[0]
            finish_turn(s, turn, outcome=outcome, now=now)
            s.commit()
            _beat(ctx, "strategist", True, f"turn {turn.id} answered")
        except Exception as e:  # noqa: BLE001 - the turn carries the error; the service keeps running
            s.rollback()
            turn = s.merge(turn)
            fail_turn(s, turn, error=str(e) if isinstance(e, M.ModelError) else f"{type(e).__name__}: {e}"[:500],
                      now=now)
            s.commit()
            _beat(ctx, "strategist", True, f"turn {turn.id} failed")
```

If `asyncio.to_thread` runs into sqlite's same-thread issue, the `StaticPool`/`check_same_thread=False` engine already
allows it. If the session object still can't be shared across threads, run `T.run_turn` directly with no thread. The
job is the service's only work, so blocking its loop for one turn is acceptable.

Register the job in `manager/commands/run.py`:
- `from manager.scheduler.jobs import job_strategist`;
- `"strategist": job_strategist` in `JOBS`.

Add the service to `compose.yaml`, after `review`:

```yaml
  strategist:   # the Strategy tab's chat turns (2026-10-16): free model + the authoring pipeline; no write token
    <<: *manager
    profiles: ["live"]
    command: ["python", "-m", "manager", "run", "strategist", "--every", "5"]
```

Add `strategist` to the service list in `scripts/gated_deploy.sh`. Find the line that lists `excursions` and add it
next to it.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `... -m pytest -q tests/strategist tests/commands/test_run.py`
Expected: all PASS. If `tests/commands/test_run.py` asserts the exact `JOBS` keys, add `strategist` there.

- [ ] **Step 5: Commit**

```bash
git add manager/scheduler/jobs.py manager/commands/run.py compose.yaml scripts/gated_deploy.sh tests/strategist/test_job.py
git commit -m "Strategy tab: the strategist job and compose service (one turn per tick, errors stay on the turn)"
```

---

### Task 6: Chat, plan, preview, stage and commit routes

**Files:**
- Create: `manager/api/strategy_routes.py`
- Modify:
  - `manager/api/app.py`: call `add_strategy_routes(app, ctx, auth)` inside `create_app` after the policy routes;
  - `tests/actions/test_strategy_propose.py:276-286`: name the new caller.
- Test: `tests/api/test_strategy_routes.py`

**Interfaces:**
- Consumes:
  - Task 1's `read_current`;
  - Task 2's store;
  - `propose_user_stage(s, plan_id, *, by, note, now) -> dict` and
    `propose_user_commit(s, stage_action_id, *, by, note, allow_live, now) -> dict`, both raising `ProposeRefused`
    (a `ValueError`).
- Produces these routes. Every body is a dict, and every refusal is a 400 with `{"error": ...}`:
  - `GET /api/strategy/strategies` returns `{"strategies": [{"id", "name", "revision", "bound"}]}`, from
    `list_strategies`;
  - `POST /api/strategy/chats {kind, strategy_id?, by?}` returns `chat_view`;
  - `GET /api/strategy/chats` returns `{"chats": [{"id", "kind", "strategyId", "createdAt"}]}`, the latest 20;
  - `GET /api/strategy/chats/{chat_id}` returns `chat_view`;
  - `POST /api/strategy/chats/{chat_id}/messages {text}` returns `chat_view` with status 202;
  - `POST /api/strategy/plans/{plan_id}/preview` returns `{"planId", "preview": <platform answer>}`;
  - `POST /api/strategy/plans/{plan_id}/stage {note, by?, chat_id?}` returns
    `{"actionId", "plan", **chat_view if chat_id}`;
  - `POST /api/strategy/stages/{action_id}/commit {note, by?, allow_live?, chat_id?}` returns
    `{"actionId", "stage", "review"}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/api/test_strategy_routes.py
from fastapi.testclient import TestClient
from manager.api.app import create_app
from manager.db.session import init_db, make_engine, make_session_factory
from manager.scheduler.jobs import JobContext
from tests.platform.fake import FakePlatform
from manager.platform.errors import Kind, PlatformError


def _ctx(settings, responses=None):
    e = make_engine("sqlite+pysqlite:///:memory:")
    init_db(e)
    return JobContext(client=FakePlatform(responses or {}), session_factory=make_session_factory(e), settings=settings)


def H(settings):
    return {"Authorization": f"Bearer {settings.manager_token}"}


def test_routes_need_the_bearer(settings):
    with TestClient(create_app(_ctx(settings), start_scheduler=False)) as c:
        assert c.post("/api/strategy/chats", json={"kind": "new"}).status_code == 401


def test_a_new_chat_and_a_message_queue_a_turn(settings):
    with TestClient(create_app(_ctx(settings), start_scheduler=False)) as c:
        chat = c.post("/api/strategy/chats", json={"kind": "new"}, headers=H(settings)).json()
        r = c.post(f"/api/strategy/chats/{chat['chat']['id']}/messages", json={"text": "fade funding on 1h"},
                   headers=H(settings))
    assert r.status_code == 202 and r.json()["pending"] is True


def test_message_refused_while_turn_pending(settings):
    with TestClient(create_app(_ctx(settings), start_scheduler=False)) as c:
        cid = c.post("/api/strategy/chats", json={"kind": "new"}, headers=H(settings)).json()["chat"]["id"]
        c.post(f"/api/strategy/chats/{cid}/messages", json={"text": "one"}, headers=H(settings))
        r = c.post(f"/api/strategy/chats/{cid}/messages", json={"text": "two"}, headers=H(settings))
    assert r.status_code == 400 and "wait for the reply" in r.json()["error"]


def test_message_text_bounds(settings):
    with TestClient(create_app(_ctx(settings), start_scheduler=False)) as c:
        cid = c.post("/api/strategy/chats", json={"kind": "new"}, headers=H(settings)).json()["chat"]["id"]
        assert c.post(f"/api/strategy/chats/{cid}/messages", json={"text": "  "}, headers=H(settings)).status_code == 400
        r = c.post(f"/api/strategy/chats/{cid}/messages", json={"text": "x" * 4001}, headers=H(settings))
    assert r.status_code == 400 and "4000" in r.json()["error"]


def test_a_bad_kind_is_a_400_not_a_422(settings):
    with TestClient(create_app(_ctx(settings), start_scheduler=False)) as c:
        r = c.post("/api/strategy/chats", json={"kind": "delete"}, headers=H(settings))
    assert r.status_code == 400


def test_revise_reads_the_strategy_into_the_chat(settings):
    strategy = {"id": "s1", "revision": 2, "name": "VWAP Reject 15m"}   # add one AXIS_FIELDS field, as in Task 1
    ctx = _ctx(settings, {"get_strategy_draft": {"draft": None, "draftVersion": 0, "committedRevision": 2},
                          "get_strategy": {"strategy": strategy}})
    with TestClient(create_app(ctx, start_scheduler=False)) as c:
        r = c.post("/api/strategy/chats", json={"kind": "revise", "strategy_id": "s1"}, headers=H(settings))
    assert r.status_code == 200 and r.json()["chat"]["strategyId"] == "s1"
    assert r.json()["chat"]["currentMeta"]["revision"] == 2


def test_revise_refused_on_foreign_draft(settings):
    held = {"draft": {"strategyId": "s1", "content": {}, "version": 3, "source": "player"}, "draftVersion": 3,
            "committedRevision": 2}
    ctx = _ctx(settings, {"get_strategy_draft": held})
    with TestClient(create_app(ctx, start_scheduler=False)) as c:
        r = c.post("/api/strategy/chats", json={"kind": "revise", "strategy_id": "s1"}, headers=H(settings))
    assert r.status_code == 400 and "draft" in r.json()["error"]


def test_a_platform_error_on_revise_is_a_400(settings):
    ctx = _ctx(settings, {"get_strategy_draft": PlatformError(Kind.TOOL_ERROR, "strategy not found")})
    with TestClient(create_app(ctx, start_scheduler=False)) as c:
        r = c.post("/api/strategy/chats", json={"kind": "revise", "strategy_id": "nope"}, headers=H(settings))
    assert r.status_code == 400


def test_stage_needs_a_note_and_passes_propose_refusals_verbatim(settings):
    with TestClient(create_app(_ctx(settings), start_scheduler=False)) as c:
        assert c.post("/api/strategy/plans/999/stage", json={}, headers=H(settings)).status_code == 400
        r = c.post("/api/strategy/plans/999/stage", json={"note": "try"}, headers=H(settings))
    assert r.status_code == 400 and "999" in r.json()["error"]
```

**What counts as a "foreign draft" on revise.** The manager already decides this in `strategy_describe.py`, which
refuses a draft the manager did not write. Before implementing, read how it does that (search for "did not write").
Then use the same predicate in the route, imported from where it lives, and set up `held` in the test to match it.
If the predicate needs the manager's own `StrategyStage` rows, treat any draft with `version > 0` and no
`StrategyStage` row for that `(strategy_id, staged_version)` as foreign.

- [ ] **Step 2: Run the tests and watch them fail**

Run: `... -m pytest -q tests/api/test_strategy_routes.py`
Expected: FAIL with 404s.

- [ ] **Step 3: Implement the routes**

```python
# manager/api/strategy_routes.py
"""The Strategy tab's routes (2026-10-16 spec, sections 3-4). Thin: validate, then the store, the authoring
pipeline's stored plans, and the existing strategy proposers - never the write client."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Body, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select

from manager.actions.strategy_propose import propose_user_commit, propose_user_stage
from manager.authoring.current import read_current
from manager.db.models import StrategyChat, StrategyPlanRow
from manager.platform.errors import PlatformError
from manager.strategist.store import ChatBusy, add_user_turn, chat_view, create_chat

TEXT_MAX = 4000
BY_MAX = 32


def _refused(text: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": text})


def _by(body: dict):
    by = body.get("by")
    if by is not None and not isinstance(by, str):
        return None, _refused("by must be a string or null")
    by = (by.strip() if by else "") or "plugin"
    return (None, _refused(f"by must be at most {BY_MAX} characters")) if len(by) > BY_MAX else (by, None)


def _note(body: dict):
    note = body.get("note")
    if not isinstance(note, str) or not note.strip():
        return None, _refused("a note is required: say why")
    return note.strip(), None


def add_strategy_routes(app, ctx, auth) -> None:
    @app.get("/api/strategy/strategies", dependencies=[Depends(auth)])
    async def strategies():
        try:
            read = await ctx.client.call("list_strategies", {})
        except PlatformError as e:
            return _refused(f"refused: {e}")
        rows = read.get("strategies", []) if isinstance(read, dict) else []
        return {"strategies": [{"id": r.get("id"), "name": r.get("name"), "revision": r.get("revision"),
                                "bound": r.get("boundAgentCount") or r.get("agents")} for r in rows
                               if isinstance(r, dict)]}

    @app.post("/api/strategy/chats", dependencies=[Depends(auth)])
    async def new_chat(body: dict = Body(default={})):
        by, refused = _by(body)
        if refused is not None:
            return refused
        kind = body.get("kind")
        if kind not in ("new", "revise"):
            return _refused('kind must be "new" or "revise"')
        axes = meta = None
        strategy_id = body.get("strategy_id")
        if kind == "revise":
            if not isinstance(strategy_id, str) or not strategy_id:
                return _refused("a revise chat needs strategy_id")
            try:
                answer = await read_current(ctx.client, strategy_id)
            except PlatformError as e:
                return _refused(f"refused: the strategy could not be read: {e}")
            except ValueError as e:
                return _refused(f"refused: {e}")
            foreign = _foreign_draft(ctx, strategy_id, answer)
            if foreign:
                return _refused(foreign)
            axes = (answer.get("draft") or {}).get("content")
            meta = {"source": answer.get("source", "get_strategy_draft"), "revision": answer.get("revision"),
                    "committedRevision": answer.get("committedRevision"), "draftVersion": answer.get("draftVersion")}
        with ctx.session_factory() as s:
            chat = create_chat(s, kind=kind, by=by, now=datetime.now(UTC), strategy_id=strategy_id if kind == "revise"
                               else None, current_axes=axes, current_meta=meta)
            s.commit()
            return chat_view(s, chat.id)

    @app.get("/api/strategy/chats", dependencies=[Depends(auth)])
    def list_chats():
        with ctx.session_factory() as s:
            rows = s.scalars(select(StrategyChat).order_by(StrategyChat.id.desc()).limit(20))
            return {"chats": [{"id": c.id, "kind": c.kind, "strategyId": c.strategy_id,
                               "createdAt": c.created_at.isoformat()} for c in rows]}

    @app.get("/api/strategy/chats/{chat_id}", dependencies=[Depends(auth)])
    def get_chat(chat_id: int):
        with ctx.session_factory() as s:
            try:
                return chat_view(s, chat_id)
            except ValueError as e:
                return _refused(str(e))

    @app.post("/api/strategy/chats/{chat_id}/messages", dependencies=[Depends(auth)])
    def post_message(chat_id: int, body: dict = Body(default={})):
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            return _refused("a message needs text")
        if len(text) > TEXT_MAX:
            return _refused(f"a message is at most {TEXT_MAX} characters")
        with ctx.session_factory() as s:
            if s.get(StrategyChat, chat_id) is None:
                return _refused(f"chat {chat_id} is not known")
            try:
                add_user_turn(s, chat_id, text.strip(), now=datetime.now(UTC))
            except ChatBusy as e:
                return _refused(str(e))
            s.commit()
            return JSONResponse(status_code=202, content=chat_view(s, chat_id))

    @app.post("/api/strategy/plans/{plan_id}/preview", dependencies=[Depends(auth)])
    async def preview(plan_id: int):
        with ctx.session_factory() as s:
            plan = s.get(StrategyPlanRow, plan_id)
            body = None if plan is None else (plan.request or {}).get("preview")
        if not body:
            return _refused(f"plan {plan_id} has no preview body")
        try:
            return {"planId": plan_id, "preview": await ctx.client.call("preview_strategy_report", body)}
        except PlatformError as e:
            return _refused(f"refused: {e}")

    @app.post("/api/strategy/plans/{plan_id}/stage", dependencies=[Depends(auth)])
    def stage(plan_id: int, body: dict = Body(default={})):
        by, refused = _by(body)
        note, refused2 = _note(body)
        if refused or refused2:
            return refused or refused2
        with ctx.session_factory() as s:
            try:
                out = propose_user_stage(s, plan_id, by=by, note=note, now=datetime.now(UTC))
            except ValueError as e:
                return _refused(f"refused: {e}")
            chat_id = body.get("chat_id")
            if isinstance(chat_id, int) and (chat := s.get(StrategyChat, chat_id)) is not None:
                chat.stage_action_id = out["actionId"]
                s.commit()
            return out

    @app.post("/api/strategy/stages/{action_id}/commit", dependencies=[Depends(auth)])
    def commit(action_id: int, body: dict = Body(default={})):
        by, refused = _by(body)
        note, refused2 = _note(body)
        if refused or refused2:
            return refused or refused2
        with ctx.session_factory() as s:
            try:
                out = propose_user_commit(s, action_id, by=by, note=note, allow_live=body.get("allow_live") is True,
                                          now=datetime.now(UTC))
            except ValueError as e:
                return _refused(f"refused: {e}")
            chat_id = body.get("chat_id")
            if isinstance(chat_id, int) and (chat := s.get(StrategyChat, chat_id)) is not None:
                chat.commit_action_id = out["actionId"]
                s.commit()
            return out


def _foreign_draft(ctx, strategy_id: str, answer: dict) -> str | None:
    """A draft the player holds that the manager did not write refuses the revise chat (the rule
    strategy_describe.py applies before a stage). The manager's own drafts are its StrategyStage rows."""
    from manager.db.models import StrategyStage
    version = answer.get("draftVersion") or 0
    if answer.get("source") == "get_strategy" or not version:
        return None                                    # no draft held: the committed strategy is the start
    with ctx.session_factory() as s:
        ours = s.scalar(select(StrategyStage.id).where(StrategyStage.strategy_id == strategy_id,
                                                       StrategyStage.staged_version == version))
    if ours is not None:
        return None
    return (f"refused: the player holds a draft of this strategy (version {version}) that the manager did not "
            f"write; save or discard it in the BattleGrid editor first")
```

If `strategy_describe.py` already exposes a predicate for "a draft the manager did not write", call it from
`_foreign_draft` instead of the StrategyStage query, so the two can't drift apart.

In `manager/api/app.py`, at the end of `create_app`'s route definitions, add:

```python
    from manager.api.strategy_routes import add_strategy_routes
    add_strategy_routes(app, ctx, auth)
```

Amend `tests/actions/test_strategy_propose.py`. The test asserts that only `strategy_propose.py` and `strategy.py`
call the proposers. Name the new file explicitly (do NOT rename it to `strategy.py` to slip through):

```python
        if path.name not in ("strategy_propose.py", "strategy.py", "strategy_routes.py"):
            assert "propose_user_stage(" not in text and "propose_user_commit(" not in text, path
```

Also update `strategy_propose.py`'s module docstring at lines 21-22 to say that the Strategy tab's routes
(`manager/api/strategy_routes.py`) call it too.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `... -m pytest -q tests/api tests/actions/test_strategy_propose.py`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add manager/api/strategy_routes.py manager/api/app.py manager/actions/strategy_propose.py tests/api/test_strategy_routes.py tests/actions/test_strategy_propose.py
git commit -m "Strategy tab: chat, plan preview, stage and commit routes (the tab is a second caller of the existing proposers)"
```

---

### Task 7: Dry-describe and commit-only approve routes

**Files:**
- Create: `manager/actions/dry.py`
- Modify:
  - `manager/commands/actions.py`: `_dry` at ~78 delegates to `dry.py`;
  - `manager/api/strategy_routes.py`: add two routes.
- Test: append to `tests/api/test_strategy_routes.py`.

**Interfaces:**
- Consumes: `approve(s, action_id, *, note, by, now, params_sha=None) -> dict`, which raises `ValueError`.
- Produces:
  - `async def dry_lines(client, session_factory, action_id: int, *, now) -> dict`. It returns exactly what `_dry`
    returns today (at least the `paramsSha` key), plus `lines: list[str]`, the human lines `manager actions approve`
    prints before approving.
  - `GET /api/actions/{action_id}/dry` returns `dry_lines(...)` for a QUEUED COMMIT_STRATEGY row, and a 400 for any
    other row.
  - `POST /api/actions/{action_id}/approve {note, by?, params_sha}` returns `approve`'s dict. It is a 400 for a
    non-COMMIT_STRATEGY row, a 400 with `approve`'s own text on any `ValueError`, and a 400 when `params_sha` is
    missing.

- [ ] **Step 1: Read `_dry` and extract it**

Open `manager/commands/actions.py:78` and its caller at lines 806-826.
1. Move `_dry`'s body into `manager/actions/dry.py` as `async def dry_lines(client, session_factory, action_id, *,
   now)`. Take the client as a parameter instead of building one, and return the same dict.
2. Add `"lines"`: the list of strings the CLI prints for that dry describe. Find where the CLI renders the dry result
   and move that rendering into `dry.py` as `def dry_text(dry: dict) -> list[str]`, which the CLI then calls too.
3. `_dry` becomes `asyncio.run(dry_lines(make_client(settings), session_factory, action_id, now=now))`, with the
   client closed afterwards as today.
4. Run `... -m pytest -q tests/commands/test_actions.py`. Expected: PASS, unchanged.

- [ ] **Step 2: Write the failing route tests**

```python
# append to tests/api/test_strategy_routes.py
from datetime import UTC, datetime
from manager.db.models import ActionRow


def _queued(ctx, kind):
    with ctx.session_factory() as s:
        row = ActionRow(kind=kind, status="QUEUED", target_id="s1", params={}, proposed_by="plugin",
                        proposed_at=datetime.now(UTC))
        s.add(row)
        s.commit()
        return row.id


def test_approve_refuses_any_kind_but_commit_strategy(settings):
    ctx = _ctx(settings)
    row_id = _queued(ctx, "SYNC_LIMITS")
    with TestClient(create_app(ctx, start_scheduler=False)) as c:
        r = c.post(f"/api/actions/{row_id}/approve", json={"note": "ok", "params_sha": "x"}, headers=H(settings))
    assert r.status_code == 400 and "COMMIT_STRATEGY" in r.json()["error"]


def test_approve_needs_note_and_params_sha(settings):
    ctx = _ctx(settings)
    row_id = _queued(ctx, "COMMIT_STRATEGY")
    with TestClient(create_app(ctx, start_scheduler=False)) as c:
        assert c.post(f"/api/actions/{row_id}/approve", json={"params_sha": "x"}, headers=H(settings)).status_code == 400
        assert c.post(f"/api/actions/{row_id}/approve", json={"note": "ok"}, headers=H(settings)).status_code == 400


def test_approve_refused_on_params_sha_mismatch(settings):
    ctx = _ctx(settings)
    row_id = _queued(ctx, "COMMIT_STRATEGY")
    with TestClient(create_app(ctx, start_scheduler=False)) as c:
        r = c.post(f"/api/actions/{row_id}/approve", json={"note": "ok", "params_sha": "stale"}, headers=H(settings))
    assert r.status_code == 400
    with ctx.session_factory() as s:
        assert s.get(ActionRow, row_id).status == "QUEUED"
```

`ActionRow`'s required columns may differ from those in `_queued`. Before running, read `ActionRow` in
`manager/db/models.py` and fill every non-nullable column. Copy a helper if `tests/actions/support.py` already has
one; it does, under a name such as `queued_row`, so search there first and reuse it.

- [ ] **Step 3: Run the tests and watch them fail**

Run: `... -m pytest -q tests/api/test_strategy_routes.py -k approve`
Expected: FAIL with 404.

- [ ] **Step 4: Implement the two routes in `add_strategy_routes`**

```python
    from manager.actions.dry import dry_lines
    from manager.actions.pipeline import approve as approve_row
    from manager.db.models import ActionRow

    def _commit_row(s, action_id: int):
        row = s.get(ActionRow, action_id)
        if row is None:
            return None, _refused(f"action {action_id} is not known")
        if row.kind != "COMMIT_STRATEGY":
            return None, _refused("the Strategy tab approves only COMMIT_STRATEGY rows; approve others with "
                                  "`manager actions approve`")
        return row, None

    @app.get("/api/actions/{action_id}/dry", dependencies=[Depends(auth)])
    async def dry(action_id: int):
        with ctx.session_factory() as s:
            _, refused = _commit_row(s, action_id)
        if refused is not None:
            return refused
        try:
            return await dry_lines(ctx.client, ctx.session_factory, action_id, now=datetime.now(UTC))
        except (ValueError, PlatformError) as e:
            return _refused(f"refused: {e}")

    @app.post("/api/actions/{action_id}/approve", dependencies=[Depends(auth)])
    def approve_route(action_id: int, body: dict = Body(default={})):
        by, refused = _by(body)
        note, refused2 = _note(body)
        if refused or refused2:
            return refused or refused2
        params_sha = body.get("params_sha")
        if not isinstance(params_sha, str) or not params_sha:
            return _refused("params_sha is required: approve what the dry describe showed")
        with ctx.session_factory() as s:
            _, refused = _commit_row(s, action_id)
            if refused is not None:
                return refused
            try:
                return approve_row(s, action_id, note=note, by=by, now=datetime.now(UTC), params_sha=params_sha)
            except ValueError as e:
                return _refused(f"refused: {e}")
```

Add `manager/actions/dry.py` to the exemptions of any test that forbids importing `manager.actions` from
`manager/api`. Run `... -m pytest -q tests/risk/test_import_boundary.py` to find out.

- [ ] **Step 5: Run the tests and watch them pass**

Run: `... -m pytest -q tests/api tests/commands/test_actions.py`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add manager/actions/dry.py manager/commands/actions.py manager/api/strategy_routes.py tests/api/test_strategy_routes.py
git commit -m "Strategy tab: dry-describe and a commit-only approve route (bound to the params sha the dialog showed)"
```

---

### Task 8: Import boundary for the strategist

**Files:**
- Modify: `tests/risk/test_import_boundary.py`

**Interfaces:**
- Consumes: the helper `_imported_top_level_packages(path)` already in that file.

- [ ] **Step 1: Write the test**

```python
STRATEGIST_DIR = pathlib.Path(__file__).resolve().parents[2] / "manager" / "strategist"


def test_the_strategist_never_imports_the_write_client():   # 2026-10-16 Strategy tab spec, section 7
    for path in STRATEGIST_DIR.glob("*.py"):
        imports = _imported_top_level_packages(path)
        assert not any(n == "manager.actions.write_client" or n.startswith("manager.actions.write_client.")
                       for n in imports), path
        assert not any(n.startswith("manager.actions") for n in imports), path   # it needs nothing from actions
```

- [ ] **Step 2: Run the test**

Run: `... -m pytest -q tests/risk/test_import_boundary.py`
Expected: PASS. The strategist imports `manager.authoring`, `manager.audit`, `manager.db` and `httpx2` only. If it
fails, a strategist module imports from `manager.actions`; move that use into the routes.

- [ ] **Step 3: Commit**

```bash
git add tests/risk/test_import_boundary.py
git commit -m "Strategy tab: the strategist may not import the write path"
```

---

### Task 9: Plugin proxy routes

**Files:**
- Modify: `hermes/plugin/battlegrid-manager/dashboard/plugin_api.py`
- Test: `tests/hermes/test_plugin_api.py` (append)

**Interfaces:**
- Produces plugin routes under `/api/plugins/battlegrid-manager/`:
  - `GET /strategy/strategies`
  - `POST /strategy/chats`
  - `GET /strategy/chats`
  - `GET /strategy/chats/{chat_id}`
  - `POST /strategy/chats/{chat_id}/messages`
  - `POST /strategy/plans/{plan_id}/preview`
  - `POST /strategy/plans/{plan_id}/stage`
  - `POST /strategy/stages/{action_id}/commit`
  - `GET /actions/{action_id}/dry`
  - `POST /actions/{action_id}/approve`

  Every route proxies to the same path with `/api` in front, and every id is typed `int`.

- [ ] **Step 1: Write the failing test**

Read how `tests/hermes/test_plugin_api.py` checks the existing `/policy/propose` proxy. It loads the router and stubs
`http_json` or `_proxy`. Add one test in that same style asserting that `POST /strategy/chats/5/messages` with
`{"text": "hi"}` reaches the manager as `POST /api/strategy/chats/5/messages` with the same body, and one asserting
that `/strategy/chats/abc` is a 422 from FastAPI's `int` typing, so a non-number never reaches the manager.

```python
def test_strategy_message_is_proxied_verbatim(monkeypatch):
    sent = {}
    module = _load()          # the existing loader helper in this file
    monkeypatch.setattr(module, "_proxy", lambda method, path, **k: sent.update(method=method, path=path, **k) or {})
    client = TestClient(_app(module))   # the existing app wrapper helper
    client.post("/strategy/chats/5/messages", json={"text": "hi"})
    assert sent == {"method": "POST", "path": "/api/strategy/chats/5/messages", "json_body": {"text": "hi"}}
```

Rename `_load` and `_app` to whatever helpers the file actually defines. If it builds a client per test without
helpers, copy that setup.

- [ ] **Step 2: Run the test and watch it fail**

Run: `... -m pytest -q tests/hermes/test_plugin_api.py -k strategy`
Expected: FAIL with 404.

- [ ] **Step 3: Implement the proxies**

```python
# hermes/plugin/battlegrid-manager/dashboard/plugin_api.py (append after the policy routes)
@router.get("/strategy/strategies")
def get_strategy_strategies():
    """The Strategy tab's 'Open existing' list (2026-10-16)."""
    return _proxy("GET", "/api/strategy/strategies")


@router.post("/strategy/chats")
def post_strategy_chat(body: dict = Body(default={})):
    return _proxy("POST", "/api/strategy/chats", json_body=body)


@router.get("/strategy/chats")
def get_strategy_chats():
    return _proxy("GET", "/api/strategy/chats")


@router.get("/strategy/chats/{chat_id}")
def get_strategy_chat(chat_id: int):
    return _proxy("GET", f"/api/strategy/chats/{chat_id}")


@router.post("/strategy/chats/{chat_id}/messages")
def post_strategy_message(chat_id: int, body: dict = Body(default={})):
    return _proxy("POST", f"/api/strategy/chats/{chat_id}/messages", json_body=body)


@router.post("/strategy/plans/{plan_id}/preview")
def post_strategy_preview(plan_id: int):
    return _proxy("POST", f"/api/strategy/plans/{plan_id}/preview", json_body={})


@router.post("/strategy/plans/{plan_id}/stage")
def post_strategy_stage(plan_id: int, body: dict = Body(default={})):
    return _proxy("POST", f"/api/strategy/plans/{plan_id}/stage", json_body=body)


@router.post("/strategy/stages/{action_id}/commit")
def post_strategy_commit(action_id: int, body: dict = Body(default={})):
    return _proxy("POST", f"/api/strategy/stages/{action_id}/commit", json_body=body)


@router.get("/actions/{action_id}/dry")
def get_action_dry(action_id: int):
    return _proxy("GET", f"/api/actions/{action_id}/dry")


@router.post("/actions/{action_id}/approve")
def post_action_approve(action_id: int, body: dict = Body(default={})):
    """Commit-only in v1: the manager refuses any other kind."""
    return _proxy("POST", f"/api/actions/{action_id}/approve", json_body=body)
```

The plugin's `_envelope` turns a 202 or a 400 into its `{ok, ...}` shape. Check that a 202 counts as ok: read
`_envelope`. If it treats only 200 as ok, change its check to `200 <= status < 300`, and add a test for a 202.

- [ ] **Step 4: Run the tests and watch them pass**

Run: `... -m pytest -q tests/hermes`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add hermes/plugin/battlegrid-manager/dashboard/plugin_api.py tests/hermes/test_plugin_api.py
git commit -m "Strategy tab: plugin proxy routes"
```

---

### Task 10: The Strategy tab

**Files:**
- Modify: `hermes/plugin/battlegrid-manager/desktop/plugin.js`, which gets the TABS entry, the API one-liners, the
  `StrategyTab` components and the `tabBody` case.
- Test: `tests/hermes/test_plugin_js.py` (append)

**Interfaces:**
- Consumes: the plugin routes from Task 9, and the existing `read`, `rest`, `usePoll`, `Section`, `Loaded`,
  `errorText`, `linesDescription`, `refreshEverything`, `host`, `ConfirmDialog`, `Button`, `Input` and `Badge`.
  Read each one's definition in `plugin.js` before using it.

- [ ] **Step 1: Write the failing JS lint tests**

```python
# append to tests/hermes/test_plugin_js.py
def test_the_strategy_tab_is_listed_and_routed():
    assert re.search(r"\{\s*id:\s*'strategy',\s*label:\s*'Strategy'\s*\}", SRC)
    assert re.search(r"if \(tab === 'strategy'\) return jsx\(StrategyTab, \{\}\)", SRC)


_APPROVE_POST = re.compile(r"rest\(\s*`/actions/\$\{[^}]+\}/approve`\s*,\s*\{(?P<options>(?:[^{}]|\{[^{}]*\})*)\}\s*\)")


def test_the_approve_post_sends_note_and_params_sha():
    found = _APPROVE_POST.search(SRC)
    assert found, "no rest(`/actions/${id}/approve`, {...}) call found"
    body = re.search(r"body:\s*\{(?P<fields>[^{}]*)\}", found.group("options"))
    assert body and all(re.search(rf"\b{f}\b", body.group("fields")) for f in ("note", "params_sha"))


def test_the_commit_dialog_shows_the_managers_dry_lines():
    assert "linesDescription(dry.lines" in SRC
```

`test_every_rest_path_is_a_backend_route` already exists. It turns template paths such as `/strategy/chats/${id}`
into regexes; check that its `rest_paths` helper handles backtick templates. If it doesn't, extend `rest_paths` to
capture `` rest(`...`) `` paths with `${...}` replaced by a `[^/]+` pattern.

- [ ] **Step 2: Run the tests and watch them fail**

Run: `... -m pytest -q tests/hermes/test_plugin_js.py`
Expected: the 3 new tests FAIL.

- [ ] **Step 3: Implement the tab**

Add `{ id: 'strategy', label: 'Strategy' }` to `TABS` after `risk`, and
`if (tab === 'strategy') return jsx(StrategyTab, {})` to `tabBody` before the fleet fallback.

Add the API one-liners next to the policy ones:

```js
const fetchStrategies = () => read(() => rest('/strategy/strategies'))
const postChat = (kind, strategyId) =>
  read(() => rest('/strategy/chats', { method: 'POST', body: { kind, strategy_id: strategyId } }))
const fetchChat = (id) => read(() => rest(`/strategy/chats/${id}`))
const postMessage = (id, text) => read(() => rest(`/strategy/chats/${id}/messages`, { method: 'POST', body: { text } }))
const postPreview = (planId) => read(() => rest(`/strategy/plans/${planId}/preview`, { method: 'POST', body: {} }))
const postStage = (planId, note, chatId) =>
  read(() => rest(`/strategy/plans/${planId}/stage`, { method: 'POST', body: { note, chat_id: chatId } }))
const postCommit = (actionId, note, chatId, allowLive) =>
  read(() => rest(`/strategy/stages/${actionId}/commit`,
    { method: 'POST', body: { note, chat_id: chatId, allow_live: allowLive } }))
const fetchDry = (actionId) => read(() => rest(`/actions/${actionId}/dry`))
const postApprove = (actionId, note, paramsSha) =>
  read(() => rest(`/actions/${actionId}/approve`, { method: 'POST', body: { note, params_sha: paramsSha } }))
```

Add the components. Follow the file's style: `jsx(...)` with `children` arrays, no JSX syntax, no hard-coded colours.

```js
// 2026-10-16 spec: chat on the left, the manager's strategy card on the right. Renders only; every verdict, finding
// and dialog line is the manager's text verbatim.
function StrategyTab() {
  const [chatId, setChatId] = useState(null)
  return chatId === null
    ? jsx(StrategyStart, { onOpen: setChatId })
    : jsx(StrategyChat, { chatId, onClose: () => setChatId(null) })
}

function StrategyStart({ onOpen }) {
  const list = usePanel('strategy-strategies', fetchStrategies)
  const open = async (kind, strategyId) => {
    const body = await postChat(kind, strategyId)
    if (body.ok === false) return host.notify({ kind: 'error', message: errorText(body) })
    onOpen(body.chat.id)
  }
  return jsx(Section, {
    title: 'Strategy',
    hint: 'Describe an idea to build a new strategy, or open one of yours to explain and revise it.',
    children: [
      jsx(Button, { key: 'new', onClick: () => open('new', null), children: 'New strategy' }),
      jsx(Loaded, {
        key: 'list', query: list,
        render: (data) => jsx('ul', {
          children: (data.strategies || []).map((s) => jsx('li', {
            key: s.id,
            children: jsx(Button, { variant: 'ghost', onClick: () => open('revise', s.id),
              children: `Revise ${txt(s.name, s.id)} (revision ${txt(s.revision, '?')})` })
          }))
        })
      })
    ]
  })
}

function StrategyChat({ chatId, onClose }) {
  const [text, setText] = useState('')
  const chat = usePoll(`strategy-chat-${chatId}`, () => fetchChat(chatId), CHAT_POLL_MS)
  const send = async () => {
    const t = text.trim()
    if (!t) return
    const body = await postMessage(chatId, t)
    if (body.ok === false) return host.notify({ kind: 'error', message: errorText(body) })
    setText('')
    chat.refetch()
  }
  return jsx(Loaded, {
    query: chat,
    render: (view) => jsx('div', {
      className: 'bgm-strategy',
      children: [
        jsx('div', {
          key: 'chat', className: 'bgm-strategy-chat',
          children: [
            jsx(Button, { key: 'back', variant: 'ghost', onClick: onClose, children: 'All strategies' }),
            ...view.turns.map((t) => jsx(ChatTurn, { key: t.id, turn: t })),
            view.pending ? jsx('p', { key: 'wait', children: pendingText(view) }) : null,
            jsx(Input, {
              key: 'in', value: text, disabled: view.pending, placeholder: 'Describe the idea or the change…',
              onChange: (e) => setText(e.target.value),
              onKeyDown: (e) => { e.stopPropagation(); if (e.key === 'Enter') send() }
            }),
            jsx(Button, { key: 'send', disabled: view.pending || !text.trim(), onClick: send, children: 'Send' })
          ]
        }),
        jsx(StrategyCard, { key: 'card', view, chatId })
      ]
    })
  })
}

function pendingText(view) {
  const queued = view.turns.find((t) => t.status === 'QUEUED')
  const age = queued ? (Date.now() - Date.parse(queued.createdAt)) / 1000 : 0
  return age > 60 ? 'Still waiting: the strategist service may not be running.' : 'The strategist is answering…'
}

function ChatTurn({ turn }) {
  return jsx('div', {
    className: `bgm-turn bgm-turn-${turn.role}`,
    children: [
      jsx('p', { key: 't', children: turn.text }),
      turn.status === 'FAILED' ? jsx('p', { key: 'e', className: 'bgm-error', children: txt(turn.error, 'failed') }) : null,
      (turn.unmappable || []).length
        ? jsx('p', { key: 'u', children: `Not expressible: ${turn.unmappable.join('; ')}` }) : null
    ]
  })
}

function StrategyCard({ view, chatId }) {
  const [preview, setPreview] = useState(null)
  const [note, setNote] = useState('')
  const [commit, setCommit] = useState(null)       // {actionId, dry}
  const plan = view.plan
  if (!plan) return jsx(Section, { title: 'No strategy yet', hint: 'The card fills in after the first reply.' })
  const doPreview = async () => {
    const body = await postPreview(plan.id)
    if (body.ok === false) return host.notify({ kind: 'error', message: errorText(body) })
    setPreview(body.preview)
  }
  const doStage = async () => {
    const body = await postStage(plan.id, note.trim(), chatId)
    if (body.ok === false) return host.notify({ kind: 'error', message: errorText(body) })
    host.notify({ kind: 'success', message: `Stage queued as action ${body.actionId}.` })
    refreshEverything()
  }
  const doCommit = async () => {
    const body = await postCommit(view.chat.stageActionId, note.trim(), chatId, false)
    if (body.ok === false) return host.notify({ kind: 'error', message: errorText(body) })
    const dry = await fetchDry(body.actionId)
    if (dry.ok === false) return host.notify({ kind: 'error', message: errorText(dry) })
    setCommit({ actionId: body.actionId, dry })
  }
  const approveCommit = async () => {
    if (!note.trim()) throw new Error('A note is required to approve the commit.')
    const body = await postApprove(commit.actionId, note.trim(), commit.dry.paramsSha)
    if (body.ok === false) throw new Error(errorText(body))
    host.notify({ kind: 'success', message: `Commit ${commit.actionId} approved; the executor sends it next.` })
    setCommit(null)
    refreshEverything()
  }
  const dry = commit ? commit.dry : null
  return jsx(Section, {
    title: `${txt(plan.name, 'Strategy')} · ${plan.operation} · ${plan.verdict}`,
    hint: plan.verdict === 'PASS' ? 'Checked by the manager.' : 'The manager found problems; ask the assistant to fix them.',
    children: [
      jsx(Badge, { key: 'v', children: plan.verdict }),
      jsx('pre', { key: 'brief', className: 'bgm-brief', children: plan.brief }),
      jsx('ul', { key: 'checks', children: (plan.checks || []).filter((c) => c.severity !== 'info')
        .map((c, i) => jsx('li', { key: i, children: `${c.severity} ${c.code}: ${c.message}` })) }),
      jsx(Button, { key: 'p', disabled: plan.verdict !== 'PASS', onClick: doPreview, children: 'Preview report' }),
      preview ? jsx('pre', { key: 'pv', className: 'bgm-brief', children: JSON.stringify(preview, null, 2).slice(0, 8000) }) : null,
      jsx(Input, { key: 'note', value: note, placeholder: 'Note (why) — required to stage, commit and approve',
        onChange: (e) => setNote(e.target.value), onKeyDown: (e) => e.stopPropagation() }),
      jsx(Button, { key: 's', disabled: plan.verdict !== 'PASS' || !note.trim(), onClick: doStage, children: 'Stage to BattleGrid' }),
      view.chat.stageActionId
        ? jsx(Button, { key: 'c', disabled: !note.trim(), onClick: doCommit, children: `Commit stage ${view.chat.stageActionId}…` })
        : null,
      dry
        ? jsx(ConfirmDialog, {
            open: true,
            onClose: () => setCommit(null),
            onConfirm: approveCommit,
            destructive: true,
            confirmLabel: 'Approve commit',
            busyLabel: 'Approving…',
            title: `Approve commit ${commit.actionId}? This saves the strategy on BattleGrid.`,
            description: linesDescription(dry.lines, null)
          })
        : null
    ]
  })
}
```

- Add `const CHAT_POLL_MS = 3000` beside the other poll constants.
- `txt`, `Loaded`, `linesDescription` and `errorText` are existing helpers. Confirm each one's signature by reading
  its definition. If `Loaded` takes different props (`query`/`render`), adapt the three call sites to match.
- `StrategyTab` uses `useState` and the SDK components already imported. Add no new imports, because the import-lint
  test allows only the three existing specifiers and requires every imported name to be used.
- Style the classes `bgm-strategy` (a two-column grid that becomes one column under 900 px), `bgm-strategy-chat`,
  `bgm-turn-*` and `bgm-brief` (`white-space: pre-wrap`) in the plugin's existing style block, using the file's CSS
  variables only.

- [ ] **Step 4: Run the plugin tests and the node parse**

Run: `... -m pytest -q tests/hermes`
Expected: all PASS, including the `node --check` parse when node is installed.

- [ ] **Step 5: Commit**

```bash
git add hermes/plugin/battlegrid-manager/desktop/plugin.js tests/hermes/test_plugin_js.py
git commit -m "Strategy tab: chat + live card (brief, verdict, findings, preview), stage, commit with the manager's dry lines"
```

---

### Task 11: The model proof

**Files:**
- Create: `tests/fixtures/strategist/prompts.json`, `manager/commands/strategist.py`
- Modify: `manager/cli.py` registration, if commands are imported explicitly. Follow how `manager/commands/eval.py`
  is registered.
- Test: `tests/commands/test_strategist_proof.py`

**Interfaces:**
- Produces `python -m manager strategist proof [--model M] [--out FILE]`. It runs each prompt through `run_turn` with
  the real `complete` on a throwaway chat, then writes a JSON report with, per prompt: `prompt`, `reply`, `thesis`,
  `verdict`, `repaired`, `unmappable`, `seconds`, `error`. It stages nothing, and its plans are recorded with
  `by="strategist-proof"`.

- [ ] **Step 1: Write the prompts**

```json
[
  "Fade funding extremes on the 1h: when longs pay a lot, I want to be short.",
  "Trend following on 4h: buy strength when moving averages and trend strength agree.",
  "Mean reversion on 15m: buy when RSI and Stochastic are oversold and price is below the lower Bollinger band.",
  "Breakout on 1h: enter when price breaks the prior 20-bar high with rising volume.",
  "Follow the flow on 5m: go with CVD and open interest when they agree.",
  "I want to trade news sentiment on Twitter.",
  "Short relative weakness: coins underperforming BTC on 4h.",
  "Enter when RSI < 30 AND close crosses above VWAP, exit at RSI 50.",
  "Contrarian on 1h: when the money flow index shows heavy buying, fade it.",
  "Something safe for a small account, 4h, only when volatility is low."
]
```

Prompt 6 should come back with `unmappable`. Prompt 8 should come back approximated, saying so (D6). Prompt 3 must not
buy strength (the semantic check).

- [ ] **Step 2: Write the failing test, using a fake model**

```python
# tests/commands/test_strategist_proof.py
import json
from manager.commands import strategist as P


def test_proof_writes_one_row_per_prompt(tmp_path, monkeypatch, settings):
    monkeypatch.setattr(P, "_complete_for", lambda model: (lambda m: json.dumps({"reply": "r", "thesis": None,
                                                                                  "unmappable": []})))
    out = tmp_path / "proof.json"
    assert P.run_proof(prompts=["a", "b"], model="poolside/laguna-s-2.1:free", out=out, settings=settings) == 0
    rows = json.loads(out.read_text(encoding="utf-8"))
    assert [r["prompt"] for r in rows["results"]] == ["a", "b"] and rows["model"].endswith(":free")
```

- [ ] **Step 3: Run the test and watch it fail**

Run: `... -m pytest -q tests/commands/test_strategist_proof.py`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement the proof command**

```python
# manager/commands/strategist.py
"""`manager strategist proof` (2026-10-16 spec, section 5): the 10-prompt proof a free model must pass before the
strategist service is enabled. Plans are recorded (by "strategist-proof"); nothing is staged."""
from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from manager.cli import register
from manager.db.session import init_db, make_engine, make_session_factory
from manager.settings import get_settings
from manager.strategist import model as M
from manager.strategist.store import create_chat
from manager.strategist.turn import run_turn

PROMPTS = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "strategist" / "prompts.json"


def _complete_for(model: str):
    key = os.environ.get("NOUS_API_KEY")
    return lambda messages: M.complete(messages, model=model, api_key=key)


def run_proof(*, prompts: list[str], model: str, out: Path, settings) -> int:
    engine = make_engine(settings.database_url)
    init_db(engine)
    factory = make_session_factory(engine)
    complete = _complete_for(model)
    results = []
    for prompt in prompts:
        started = time.monotonic()
        row = {"prompt": prompt}
        with factory() as s:
            chat = create_chat(s, kind="new", by="strategist-proof", now=datetime.now(UTC))
            try:
                outcome = run_turn(s, chat, prompt, history=[], complete=complete, now=datetime.now(UTC))
                row.update({k: outcome[k] for k in ("reply", "thesis", "verdict", "repaired", "unmappable", "planId")})
                s.commit()
            except Exception as e:  # noqa: BLE001 - one prompt's failure is a row, not the end of the proof
                s.rollback()
                row["error"] = f"{type(e).__name__}: {e}"[:500]
        row["seconds"] = round(time.monotonic() - started, 1)
        results.append(row)
    out.write_text(json.dumps({"model": model, "at": datetime.now(UTC).isoformat(), "results": results}, indent=2),
                   encoding="utf-8")
    passed = sum(1 for r in results if r.get("verdict") == "PASS")
    print(f"{passed}/{len(results)} PASS; report {out} - read every thesis against its prompt (the semantic check)")
    return 0


def _add(p):
    sub = p.add_subparsers(dest="action", required=True)
    proof = sub.add_parser("proof", help="run the 10-prompt free-model proof")
    proof.add_argument("--model", default=M.STRATEGIST_FREE_MODELS[0])
    proof.add_argument("--out", default="data/strategist-proof.json")


def _run(a) -> int:
    prompts = json.loads(PROMPTS.read_text(encoding="utf-8"))
    return run_proof(prompts=prompts, model=a.model, out=Path(a.out), settings=get_settings())


register("strategist", "the Strategy tab's strategist (proof)", _add, _run)
```

Copy `register`'s exact argument order and the module-import mechanism from an existing command file, such as
`manager/commands/eval.py`. The image excludes `tests/`, so `PROMPTS` won't be found inside the container. Fix this by
moving `prompts.json` to `manager/strategist/proof_prompts.json` (shipped in the image) and pointing both `PROMPTS`
and the test at that path.

- [ ] **Step 5: Run the test and watch it pass**

Run: `... -m pytest -q tests/commands/test_strategist_proof.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add manager/commands/strategist.py manager/strategist/proof_prompts.json tests/commands/test_strategist_proof.py manager/cli.py
git commit -m "Strategy tab: the 10-prompt free-model proof command"
```

---

### Task 12: Full suite, merge, deploy, proof, live check

This task touches the live system. Every step is under the guards. Steps marked **USER** wait for the user.

- [ ] **Step 1: Run the full suite**

Run: `$BGM/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: everything passes. The count is the previous total (4082 passed, 5 skipped) plus the new tests.

- [ ] **Step 2: Record the feature**

Add a dated section to `docs/phase-0/runbook.md` covering:
- the `strategist` service;
- `NOUS_API_KEY`;
- `manager strategist proof`;
- how to stop the service (`docker compose stop strategist`).

- [ ] **Step 3: Merge**

Merge with `--no-ff`, push, then build the image: `docker build -t battlegrid-manager:main-<sha> .`.

- [ ] **Step 4: USER — add the key**

The user adds `NOUS_API_KEY=...` to `$BGM/.env`. Claude never copies or reads the key; check only that the line
exists, with `grep -c '^NOUS_API_KEY=' .env`.

- [ ] **Step 5: Deploy under the guards**

Run `bash scripts/gated_deploy.sh main-<sha> 2`, and confirm `data/gated_deploy.log` shows 15/15 services with 0
restarts (`strategist` is the new one). Then run `manager contract status`, and check that no drift event appears
in it.

- [ ] **Step 6: The proof**

Run `docker compose exec -T api python -m manager strategist proof --out /data/panel/strategist-proof.json`.
1. Read all 10 rows against their prompts.
2. Record each verdict, repair count and time, plus the semantic check for each, in
   `docs/phase-6/reports/2026-10-16-strategist-proof.md`.
3. If fewer than 8 of 10 reach PASS, or any thesis contradicts its prompt, stop the service
   (`docker compose stop strategist`) and report the result instead of enabling the tab.

- [ ] **Step 7: USER — rescan the plugin**

Install the plugin with `hermes/install_plugin.py`. Then the user opens Hermes, goes to Capabilities → Plugins →
Rescan, and reopens the profile.

- [ ] **Step 8: Read-only live check**

1. In the tab, start one new-strategy chat ("Fade funding extremes on the 1h").
2. Confirm the card reaches PASS.
3. Confirm Preview renders.
4. Stage and commit only on the user's word in the tab. **Never** bind or deploy.

- [ ] **Step 9: Update the records**

Update the morning-review status doc and the START HERE memory pointer with what shipped, the proof result and the
live check.
