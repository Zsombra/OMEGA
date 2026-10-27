# Decision Learning Loop, First Build (collect, label, score, cross-agent) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give battlegrid-manager the collect, label and score stages of the learning loop (section 10, steps marked "first" in the spec): trade outcomes and an entry-time feature matrix for every position, hindsight grades for every decision, weekly scorecards with a Commander report, per-condition statistics the strategist can read, and a daily pull of other agents' public trades.

**Architecture:** One new package `manager/learn/` with one module per stage, each a pure "build rows" function plus a thin "collect/write" function, wired as four Docker jobs through the existing `run.py` registry and one CLI command `manager learn`. Everything is report-only: no job calls a model, writes to the platform, or writes a `review_proposals` row. Tables are plain SQLAlchemy models in `manager/db/models.py`, created by `init_db`'s `create_all`; platform reads go through `ctx.client.call` with the existing allowlist, rate bucket and narrowing helpers.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (`Mapped` / `mapped_column`, generic `JSON`), pytest + pytest-asyncio (sqlite in-memory), the BattleGrid MCP read client (`manager/platform/client.py`), OMEGA's `omega.performance` (`MIN_SAMPLE`, `wilson_interval`), Hyperliquid candle cache (`manager/tape/hyperliquid.py`).

**Spec:** `docs/superpowers/specs/2026-10-27-decision-learning-loop-design.md` (this OMEGA worktree). The code lives in `C:\Users\rafae\Documents\GitHub\battlegrid-manager` at `6e12804` or later on `main`; work on a branch `feat/learn-loop-1` there. All paths below are relative to that repo unless they start with `OMEGA/`.

## Global Constraints

- **Report-only.** No task writes `review_proposals`, `actions`, `policy_versions`, or calls any BattleGrid write tool or any LLM (spec 8.2, 8.4, 10.1).
- **Every platform read goes through `client.call(tool, args)`** and the tool name must be on `PROXY_ALLOWLIST` (`manager/proxy/policy.py`), listed in `MANAGER_TOOLS` (`manager/platform/watch.py:178`) and have its read paths in `READ_SETS` (`manager/platform/reads.py:59`); paged reads use `call_narrowing` (`manager/platform/cap.py:118`). The rate budget is the shared bucket (2 rps); never add a second limiter.
- **Below `MIN_SAMPLE` (20, from `omega.performance`) a slice reports `INSUFFICIENT`, never a rate** (spec 9, 11.3).
- **Every job beats on every path** (`_beat(ctx, job, ok, note)`), including the blind path (AUTH failure): beat `ok=False` with the error's first 500 characters, write nothing else, and return. The silence guard kills a job whose beats stand still for three intervals.
- **Job names are at most 22 characters** (`system_state.key` is `String(32)` with the `run.sched.` prefix). The four names are `outcomes`, `label`, `scorecards`, `platform`.
- **Tables use generic `sqlalchemy.JSON`, never JSONB**, and JSON columns are reassigned, never mutated in place (sqlite tests, `type_annotation_map`).
- **New tables need no `_ADDED_COLUMNS` entry**; `create_all` creates them. A column added to an existing table does.
- **Timestamps are `DateTime(timezone=True)` in UTC**; strings from the platform are ISO-8601 with offset and parsed with `datetime.fromisoformat`.
- **No model-visible threshold moves.** `manager/triage/rules.py` and the sentinel skill are untouched by this build.
- **The user's standing rules** apply: one Compose service per job; free models only (none are called here); nothing binds, deploys or funds an agent.
- **Tests:** sqlite in memory via `tests/review/support.py:db()` style helpers, `FakePlatform` from `tests/platform/fake.py` for reads, run with `.venv/Scripts/python -m pytest -q`. Compose and job-registry tests (`tests/scheduler/test_jobs.py:287`, `tests/scheduler/test_silence.py:96`, `tests/test_compose.py`) must be updated whenever a job is added.
- **Commit after every task** with a `feat(learn): ...` or `test(learn): ...` subject and the attribution trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. **A trade whose `quality` is null** (R is zero; `list_agent_trades` says so): the outcome row must still be written with NULL R columns and the scorer must count it in `n_trades_unscored`, not crash or drop the trade silently. Test in Task 4.
2. **A decision whose position has no trade outcome yet** (still open, or the trade list has not served it): the labeller writes nothing for it and reports it in `pending`, and a later run labels it. Test in Task 6.
3. **A candle window that is still forming or missing bars** (`candles_between` raises `TapeError`, or the evaluation is younger than five bars): the observation is written with `outcome_kind = "none"` and NULL `outcome_r`, and the next run fills it. Test in Task 8.
4. **The platform refuses an oversized explorer page** (`nextAct: narrow`): the pull narrows to 50, then 25, and the leaderboard rank is NULL for agents the leaderboard does not list. Test in Task 10.
5. **Running any collector twice** adds no duplicate rows and does not re-read trades it already stored, except the 48-hour refresh of `debrief_verdict` and post-exit moves. Tests in Tasks 4, 5, 10.

---

### Task 1: The eight tables

**Files:**
- Modify: `manager/db/models.py` (append after `ReviewProposal`)
- Create: `manager/learn/__init__.py` (empty, docstring only)
- Test: `tests/learn/__init__.py` (empty), `tests/learn/support.py`, `tests/learn/test_models.py`

**Interfaces:**
- Produces the ORM classes `TradeOutcome`, `TradeContext`, `DecisionOutcome`, `ConditionObservation`, `ConditionStat`, `Scorecard`, `PlatformAgent`, `PlatformTrade`, with the columns below. Later tasks import them from `manager.db.models`.
- Produces `tests/learn/support.py: db() -> sessionmaker` (copy of `tests/review/support.py:db`).

Columns (type → `Mapped[...]` with `mapped_column`; `?` means nullable; `DT` means `DateTime(timezone=True)`; `S(n)` means `String(n)`):

- `trade_outcomes` (PK `position_id S(64)`): `agent_id S(64)` idx, `agent8 S(8)`, `coin S(20)`, `direction S(8)`, `opened_at DT`, `closed_at DT` idx, `entry Float`, `exit Float`, `close_reason S(32)`, `closed_by S(16)?`, `exit_reprice_source S(32)?`, `duration_min Float?`, `net_pnl Float`, `is_win Boolean`, `net_r Float?`, `gross_r Float?`, `fees_r Float?`, `mfe_r Float?`, `mae_r Float?`, `plan_state S(16)?`, `plan_r Float?`, `first_hit_min Float?`, `vs_plan_r Float?`, `debrief_verdict S(32)?`, `post_exit_1h Float?`, `post_exit_4h Float?`, `post_exit_24h Float?`, `signal_log_id S(64)?`, `decision_id S(64)?`, `raw dict` (JSON), `fetched_at DT`, `enriched_at DT?`.
- `trade_context` (PK `position_id S(64)`): `agent_id S(64)` idx, `agent_name S(128)?`, `strategy_id S(64)?`, `strategy_revision Integer?`, `strategy_label S(128)?`, `timeframe S(8)?`, `regime_timeframe S(8)?`, `coin S(20)`, `direction S(8)`, `opened_at DT` idx, `entry Float?`, `hard_stop Float?`, `decided_stop Float?`, `stop_ratio Float?`, `take_profit Float?`, `leverage Float?`, `size_usd Float?`, `conviction Float?`, `risk_reward Float?`, `regime S(32)?`, `momentum_now S(16)?`, `momentum_t1 S(16)?`, `structural_bias S(16)?`, `atr Float?`, `atr_pct Float?`, `funding Float?`, `open_interest Float?`, `tpo dict?` (JSON), `scan_rank Integer?`, `hour_utc Integer`, `weekday Integer`, `open_positions Integer?`, `sources dict` (JSON: group → source name or `"missing"`), `built_at DT`.
- `decision_outcomes` (PK `decision_id Integer` FK `decisions.id`): `position_id S(64)` idx, `outcome S(16)`, `reason S(32)`, `mode S(8)`, `executed Boolean`, `decided_at DT`, `r_at_decision Float?`, `realized_r Float?`, `counterfactual_r Float?`, `counterfactual_basis S(16)?`, `delta_r Float?`, `grade S(10)` (`GOOD|BAD|UNCLEAR|UNGRADED`), `plan_unreliable Boolean`, `post_exit_4h Float?`, `latency_s Float?`, `method_version Integer`, `graded_at DT`.
- `condition_observations` (PK `id`): `source S(16)` (`trade|signal_log|gate_block`), `source_id S(64)`, `position_id S(64)?`, `agent_id S(64)` idx, `strategy_id S(64)?`, `strategy_revision Integer?`, `coin S(20)`, `direction S(8)?`, `evaluated_at DT` idx, `condition_key S(128)`, `metric_code S(64)?`, `required Boolean?`, `value_true Boolean?`, `outcome_kind S(16)` (`net_r|fwd_atr_4|none`), `outcome_r Float?`, `built_at DT`; `UniqueConstraint("source", "source_id", "condition_key", name="uq_condition_obs")`.
- `condition_stats` (PK `id`): `built_at DT` idx, `strategy_id S(64)` idx, `strategy_revision Integer?`, `condition_key S(128)`, `metric_code S(64)?`, `outcome_kind S(16)`, `n_true Integer`, `n_false Integer`, `mean_true Float?`, `mean_false Float?`, `lift Float?`, `ci_low Float?`, `ci_high Float?`, `status S(16)` (`EDGE|NO_EDGE|INSUFFICIENT`).
- `scorecards` (PK `id`): `built_at DT` idx, `period_start DT`, `period_end DT`, `source S(16)` (`trades|decisions|platform`), `slice_kind S(32)`, `slice_key S(128)`, `n Integer`, `wins Integer?`, `mean_r Float?`, `ci_low Float?`, `ci_high Float?`, `win_low Float?`, `win_high Float?`, `break_even_wr Float?`, `good Integer?`, `bad Integer?`, `unclear Integer?`, `mean_delta_r Float?`, `status S(16)` (`EDGE|NO_EDGE|INSUFFICIENT`); `Index("ix_scorecards_built_slice", "built_at", "source", "slice_kind")`.
- `platform_agents` (PK `id`): `day DT` idx, `agent_id S(64)`, `name S(128)?`, `owner S(128)?`, `strategy_name S(128)?`, `timeframe S(8)?`, `status S(16)?`, `net_pnl Float?`, `win_rate Float?`, `trade_count Integer?`, `rank_explorer Integer?`, `rank_leaderboard Integer?`, `config_spec dict?` (JSON), `signal_performance dict?` (JSON), `raw dict` (JSON); `UniqueConstraint("day", "agent_id", name="uq_platform_agents_day")`.
- `platform_trades` (PK `id`): `agent_id S(64)` idx, `trade_id S(64)`, `coin S(20)`, `direction S(8)?`, `opened_at DT?`, `closed_at DT?` idx, `net_pnl Float?`, `is_win Boolean?`, `price_move_pct Float?`, `roe_pct Float?`, `leverage Float?`, `conviction Float?`, `duration_min Float?`, `close_reason S(32)?`, `closed_by S(16)?`, `regime_at_decision S(32)?`, `regime_conviction Float?`, `raw dict` (JSON), `fetched_at DT`; `UniqueConstraint("agent_id", "trade_id", name="uq_platform_trades")`.

- [ ] **Step 1: Write the failing test**

```python
# tests/learn/test_models.py
from sqlalchemy import inspect
from tests.learn.support import db
from manager.db.models import (TradeOutcome, TradeContext, DecisionOutcome, ConditionObservation, ConditionStat,
                               Scorecard, PlatformAgent, PlatformTrade)

EXPECTED = {"trade_outcomes", "trade_context", "decision_outcomes", "condition_observations", "condition_stats",
            "scorecards", "platform_agents", "platform_trades"}

def test_learn_tables_exist():
    Session = db()
    with Session() as s:
        names = set(inspect(s.get_bind()).get_table_names())
    assert EXPECTED <= names

def test_trade_outcome_columns():
    cols = {c.name for c in TradeOutcome.__table__.columns}
    assert {"position_id", "net_r", "plan_state", "debrief_verdict", "post_exit_4h", "signal_log_id", "decision_id",
            "raw", "fetched_at", "enriched_at"} <= cols
    assert TradeOutcome.__table__.primary_key.columns.keys() == ["position_id"]

def test_unique_constraints():
    assert {c.name for c in ConditionObservation.__table__.constraints if c.name} >= {"uq_condition_obs"}
    assert {c.name for c in PlatformTrade.__table__.constraints if c.name} >= {"uq_platform_trades"}
    assert {c.name for c in PlatformAgent.__table__.constraints if c.name} >= {"uq_platform_agents_day"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_models.py`
Expected: FAIL with `ImportError: cannot import name 'TradeOutcome'`

- [ ] **Step 3: Add the eight model classes to `manager/db/models.py` with the columns above**, each with a two-line docstring naming the spec section (6) and the grain. Create `manager/learn/__init__.py` with a module docstring: "The learning loop's collect, label and score stages (spec 2026-10-27, first build). Report-only."

- [ ] **Step 4: Run the test and the DB suite**

Run: `.venv/Scripts/python -m pytest -q tests/learn tests/db`
Expected: PASS. If `tests/db/test_init_db_locks.py` asserts a statement count that moved, the count moved because of new `CREATE TABLE`s only; update the expected number and say so in the commit.

- [ ] **Step 5: Commit**

```bash
git add manager/db/models.py manager/learn/__init__.py tests/learn
git commit -m "feat(learn): the eight learning-loop tables (spec section 6)"
```

---

### Task 2: Sample-size statistics

**Files:**
- Create: `manager/learn/stats.py`
- Test: `tests/learn/test_stats.py`

**Interfaces:**
- Produces, in `manager/learn/stats.py`:
  - `MIN_SAMPLE` re-exported from `omega.performance` (import lazily inside functions is NOT needed here: `omega` is installed in the image and the test venv; `manager/allocation/performance.py` imports it at module top already).
  - `LEVEL = 0.90`, `ITERS = 2000`, `SEED = 20261027`.
  - `bootstrap_mean_ci(values: Sequence[float], *, level: float = LEVEL, iters: int = ITERS, seed: int = SEED) -> tuple[float, float] | None` — percentile bootstrap of the mean using `random.Random(seed)`; `None` when `len(values) < 2`.
  - `break_even_win_rate(values: Sequence[float]) -> float | None` — `avg_loss / (avg_win + avg_loss)` with `avg_win` the mean of values `> 0` and `avg_loss` the mean of `-v` for values `<= 0`; `None` when either side is empty.
  - `two_halves(values: Sequence[float]) -> tuple[float, float] | None` — means of the first and second half in the given order; `None` below 4 values.
  - `classify(n: int, ci: tuple[float, float] | None) -> str` — `"INSUFFICIENT"` when `n < MIN_SAMPLE` or `ci is None`, `"EDGE"` when `ci[0] > 0`, else `"NO_EDGE"`.
  - `wilson(wins: int, n: int) -> tuple[float, float] | None` — `omega.performance.wilson_interval(wins, n)` when `n >= MIN_SAMPLE`, else `None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/learn/test_stats.py
from manager.learn.stats import bootstrap_mean_ci, break_even_win_rate, two_halves, classify, wilson, MIN_SAMPLE

def test_bootstrap_constant_series_is_degenerate():
    assert bootstrap_mean_ci([0.5] * 30) == (0.5, 0.5)

def test_bootstrap_is_deterministic_and_brackets_the_mean():
    xs = [1.0, -1.0, 2.0, -0.5, 0.25, 3.0, -2.0, 0.5, 1.5, -0.25] * 3
    lo, hi = bootstrap_mean_ci(xs)
    assert bootstrap_mean_ci(xs) == (lo, hi)
    assert lo < sum(xs) / len(xs) < hi

def test_bootstrap_needs_two_values():
    assert bootstrap_mean_ci([1.0]) is None

def test_break_even_win_rate():
    assert break_even_win_rate([2.0, 2.0, -1.0, -1.0]) == 1.0 / 3.0
    assert break_even_win_rate([1.0, 1.0]) is None

def test_two_halves():
    assert two_halves([1.0, 1.0, 3.0, 3.0]) == (1.0, 3.0)
    assert two_halves([1.0, 2.0, 3.0]) is None

def test_classify():
    assert classify(MIN_SAMPLE - 1, (0.1, 0.2)) == "INSUFFICIENT"
    assert classify(MIN_SAMPLE, None) == "INSUFFICIENT"
    assert classify(MIN_SAMPLE, (0.1, 0.5)) == "EDGE"
    assert classify(MIN_SAMPLE, (-0.1, 0.5)) == "NO_EDGE"

def test_wilson_respects_min_sample():
    assert wilson(5, MIN_SAMPLE - 1) is None
    lo, hi = wilson(10, MIN_SAMPLE)
    assert 0.0 < lo < 0.5 < hi < 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_stats.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'manager.learn.stats'`

- [ ] **Step 3: Implement `manager/learn/stats.py`** with the signatures above. The bootstrap resamples `len(values)` draws with replacement `iters` times, collects the means, sorts them, and returns the values at the `(1-level)/2` and `1-(1-level)/2` quantile positions (nearest-rank).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_stats.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manager/learn/stats.py tests/learn/test_stats.py
git commit -m "feat(learn): bootstrap CI, break-even win rate, two halves, classify"
```

---

### Task 3: The probe (`manager learn probe`)

The first live calls to the public reads (spec 8.3, 11.6). It also captures one page of every own-scope read the collectors use, so Tasks 4 to 10 have real fixtures. It needs the manager unblind; its tests use `FakePlatform`.

**Files:**
- Create: `manager/learn/probe.py`, `manager/commands/learn.py`
- Modify: `manager/commands/__init__.py` (add `from manager.commands import learn  # noqa: F401`), `manager/platform/watch.py:178` (`MANAGER_TOOLS` gains the four public reads and `get_trade_outcome_by_decision`, `get_signal_log`, `list_signal_logs`, `get_regime_history`, each with a comment `# learn (2026-10-27)`), `manager/platform/reads.py` (`READ_SETS` entries for the same tools; the paths are the ones the later tasks read, listed in their Interfaces blocks; a tool whose paths are not yet pinned gets `None`, which `check_read` accepts as "no declared set")
- Test: `tests/learn/test_probe.py`, update `tests/platform/test_watch.py` if it asserts the exact `MANAGER_TOOLS` set

**Interfaces:**
- Produces `manager/learn/probe.py`:
  - `PROBE_CALLS: tuple[tuple[str, dict], ...]` — in order: `("get_agent_explorer", {"limit": 25, "timeframe": "MONTHLY", "sortBy": "NET_PNL"})`, `("get_leaderboard", {"metric": "PROFIT", "timeframe": "MONTHLY", "limit": 25})`, then, for the first agent id the explorer returned (`entries[0].agentId` or whatever the served key is; the probe prints the key it used): `("get_public_agent_realized_trades", {"agentId": ..., "window": "30D", "limit": 20})`, `("get_public_agent_signal_performance", {"agentId": ...})`, `("get_public_agent_signal_logs", {"agentId": ..., "limit": 20})`, `("get_public_agent_signal_log_detail", {"agentId": ..., "logId": <first log id>})`; then own scope: `("list_agent_trades", {"limit": 5, "window": "LIFETIME"})`, `("get_trade_outcome_by_decision", {"decisionId": <first trade's decisionId>})`, `("get_signal_log", {"agentId": <first trade's agentId>, "logId": <its signalLogId>})`, `("list_signal_logs", {"limit": 20})`, `("get_regime_history", {"coinTicker": <first trade's coinTicker>, "timeframe": "4h", "bars": 50})`.
  - `async def probe(client, out_dir: Path, *, now: datetime) -> list[dict]` — runs the calls through `measured_call` (`manager/platform/cap.py:169`), writes each result to `out_dir / f"{tool}.json"` (pretty JSON, UTF-8), and returns one row per call: `{"tool", "args", "chars", "ms", "status": "OK" | "ERROR", "error": str | None, "topKeys": list[str]}`. A `PlatformError` is recorded as ERROR and the probe continues; a dependent call whose input is missing is recorded as `SKIPPED` with the reason.
  - `def render(rows: list[dict]) -> str` — a markdown table of tool, status, chars, ms, topKeys.
- Produces `manager/commands/learn.py` registered as `register("learn", "The learning loop (collect, label, score, platform pull): read-only", _add, _run)` with `p.add_argument("action", choices=["probe", "backfill", "collect", "label", "score", "platform", "show"])` and flags `--out`, `--trades`, `--since`, `--now` (force a gated run), `--limit`. Only `probe` is implemented in this task; the others print `not built` and return 2 until their tasks land.
  - `probe` refuses (`refused: the manager is blind: <error>`, exit 2) when the latest snapshot's `reads["list_intelligence_agents"]["status"] != "OK"` (use `manager.inventory.snapshot.latest`), otherwise runs `asyncio.run(probe(make_client(get_settings()), Path(a.out), now=datetime.now(UTC)))`, prints `render(rows)`, exits 0 when every row is OK, 1 otherwise. `--out` defaults to `tests/fixtures/<YYYY-MM-DD>-learn`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/learn/test_probe.py
import json
from datetime import UTC, datetime
from manager.learn.probe import probe, render, PROBE_CALLS
from tests.platform.fake import FakePlatform
from manager.platform.errors import PlatformError, Kind

AGENT = "11111111-1111-1111-1111-111111111111"
RESP = {
    "get_agent_explorer": {"entries": [{"agentId": AGENT, "name": "A"}]},
    "get_leaderboard": {"entries": []},
    "get_public_agent_realized_trades": {"trades": [], "nextCursor": None},
    "get_public_agent_signal_performance": {"evaluationCount": 3},
    "get_public_agent_signal_logs": {"logs": [{"id": "22222222-2222-2222-2222-222222222222"}], "nextCursor": None},
    "get_public_agent_signal_log_detail": {"log": {}},
    "list_agent_trades": {"trades": [{"agentId": AGENT, "decisionId": "33333333-3333-3333-3333-333333333333",
                                      "signalLogId": "44444444-4444-4444-4444-444444444444", "coinTicker": "BTC"}],
                          "nextCursor": None},
    "get_trade_outcome_by_decision": {"outcome": None},
    "get_signal_log": {"log": {}},
    "list_signal_logs": {"logs": [], "nextCursor": None},
    "get_regime_history": PlatformError(Kind.TOOL_ERROR, "boom"),
}

async def test_probe_writes_one_file_per_call_and_continues_on_error(tmp_path):
    rows = await probe(FakePlatform(RESP), tmp_path, now=datetime(2026, 10, 27, tzinfo=UTC))
    assert [r["tool"] for r in rows] == [t for t, _ in PROBE_CALLS]
    assert (tmp_path / "get_agent_explorer.json").exists()
    assert json.loads((tmp_path / "list_agent_trades.json").read_text(encoding="utf-8"))["trades"][0]["coinTicker"] == "BTC"
    by = {r["tool"]: r for r in rows}
    assert by["get_regime_history"]["status"] == "ERROR" and "boom" in by["get_regime_history"]["error"]
    assert by["get_public_agent_realized_trades"]["args"]["agentId"] == AGENT
    assert "get_regime_history" in render(rows)

async def test_probe_skips_dependents_when_explorer_is_empty(tmp_path):
    resp = dict(RESP, get_agent_explorer={"entries": []})
    rows = await probe(FakePlatform(resp), tmp_path, now=datetime(2026, 10, 27, tzinfo=UTC))
    by = {r["tool"]: r for r in rows}
    assert by["get_public_agent_realized_trades"]["status"] == "SKIPPED"
```

Also in this file, a registry test: `from manager.platform.watch import MANAGER_TOOLS` and assert the eight tool names are in it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_probe.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'manager.learn.probe'`

- [ ] **Step 3: Implement `manager/learn/probe.py` and `manager/commands/learn.py`**, add the tools to `MANAGER_TOOLS` and `READ_SETS` (`None` sets for now), import the command module in `manager/commands/__init__.py`. The explorer entry key for the agent id is read from the served payload: try `entries`, then `agents`, then `items`; the probe records which key matched in the row's `error` field as `note: used key 'entries'` when it is not `entries`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q tests/learn tests/platform tests/commands`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manager/learn/probe.py manager/commands/learn.py manager/commands/__init__.py manager/platform/watch.py manager/platform/reads.py tests/learn/test_probe.py tests/platform
git commit -m "feat(learn): manager learn probe captures one page of every read the loop uses"
```

- [ ] **Step 6: Run the probe live (needs the user's `manager auth login` first)**

Run: `docker compose exec -T api python -m manager learn probe --out /tmp/learn-probe` then copy the folder out (`docker compose cp api:/tmp/learn-probe tests/fixtures/2026-10-XX-learn`). If the manager is still blind, record `refused: the manager is blind` in the commit message of the next task and continue with the stored surface schema (`tests/fixtures/2026-10-23-surface-132.0.0/manager_schemas_132.0.0.json`) for field names. **Every later task that names a served field must confirm it against the probe fixture when it exists, and against the schema file otherwise.**

```bash
git add tests/fixtures/2026-10-XX-learn
git commit -m "test(learn): probe fixtures from the first live public reads"
```

---

### Task 4: Outcomes collector and backfill (`trade_outcomes`)

**Files:**
- Create: `manager/learn/outcomes.py`
- Modify: `manager/commands/learn.py` (`backfill`, `collect` actions), `manager/platform/reads.py` (`READ_SETS["list_agent_trades"]` already exists; add the paths below to `get_trade_outcome_by_decision`)
- Test: `tests/learn/test_outcomes.py`

**Interfaces:**
- Consumes `TradeOutcome` (Task 1), `call_narrowing` (`manager/platform/cap.py`), `insert_ignoring_conflict` (`manager/db/session.py:161`), `replay.trades.COLUMNS / from_row / Trade`.
- Produces, in `manager/learn/outcomes.py`:
  - `TOOL = "list_agent_trades"`, `PAGE_LIMIT = 50`, `PAGE_FLOOR = 5`, `MAX_PAGES = 40`, `REFRESH_WINDOW_H = 48`, `SINCE_DEFAULT = "2026-09-19T00:00:00+00:00"`.
  - `def outcome_row(trade: dict, *, fetched_at: datetime) -> dict` — maps one served trade to `TradeOutcome` column values. Served keys: `positionId, agentId, coinTicker, direction, entryAvgPrice, exitAvgPrice, closeReason, openedAt, closedAt, netPnl (decimal string), isWin, signalLogId, decisionId, debriefVerdict, quality{netR, grossR, feesR, mfeR, maeR, vsPlanR, planOutcome{state, planR, firstHitAfterMinutes}}, postExitMove` (the per-horizon `signedReturnPct` for 1h/4h/24h; the exact nesting under `postExitMove` is read from the probe fixture or the schema file and pinned in a module constant `POST_EXIT_PATHS`). `quality` null → every R column `None`. `agent8 = agentId[:8]`.
  - `def row_from_fixture(row: list) -> dict` — a `replay.trades.COLUMNS` row (the 10-26 fixture) to the same dict, with the columns the fixture lacks set `None` and `fetched_at` the fixture's `fetchedAt`.
  - `def upsert_outcome(s: Session, values: dict) -> str` — returns `"new"`, `"updated"` (only `debrief_verdict`, `post_exit_*`, `raw`, `fetched_at` may change) or `"same"`.
  - `def as_trade(row: TradeOutcome) -> Trade` — the replay's `Trade`, for the labeller.
  - `def since_for(s: Session, *, now: datetime) -> str` — the newest `closed_at` minus `REFRESH_WINDOW_H` hours, else `SINCE_DEFAULT`, ISO-8601 with `+00:00`.
  - `async def collect_outcomes(client, session_factory, *, now: datetime) -> dict` — pages `list_agent_trades` with `{"limit", "window": "LIFETIME", "since": since_for(...), "cursor"?}` via `call_narrowing(..., floor=PAGE_FLOOR)`, stops at `nextCursor is None` or `MAX_PAGES`, upserts, then for every row with `decision_id` set and `enriched_at` null calls `get_trade_outcome_by_decision` and fills `closed_by, exit_reprice_source, duration_min` from `outcome.closedBy, outcome.exitRepriceSource, outcome.durationMinutes` (names pinned from the probe/schema; `outcome` null → `enriched_at` set, columns stay null). Returns `{"pages", "new", "updated", "same", "enriched", "errors": [...]}`. A `PlatformError` on the list read raises; one on an enrichment is appended to `errors` and the loop continues.
  - `def backfill_from_fixture(session_factory, path: Path) -> dict` — loads the 10-26 file (`replay.trades.load_trades` shape: `columns`, `rows`, `decidedStops`) and upserts every row; returns the counts.

- [ ] **Step 1: Write the failing tests**

```python
# tests/learn/test_outcomes.py
from datetime import UTC, datetime
from pathlib import Path
from manager.db.models import TradeOutcome
from manager.learn.outcomes import (outcome_row, row_from_fixture, upsert_outcome, as_trade, since_for,
                                    collect_outcomes, backfill_from_fixture, SINCE_DEFAULT)
from tests.learn.support import db
from tests.platform.fake import FakePlatform

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "2026-10-26-replay" / "trades.json"
NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)

def served(**over):
    base = {"positionId": "p1", "agentId": "aaaaaaaa-0000-0000-0000-000000000000", "coinTicker": "BTC",
            "direction": "LONG", "entryAvgPrice": "100", "exitAvgPrice": "110", "closeReason": "TAKE_PROFIT",
            "openedAt": "2026-10-20T00:00:00+00:00", "closedAt": "2026-10-20T04:00:00+00:00", "netPnl": "1.50",
            "isWin": True, "signalLogId": "log1", "decisionId": "dec1", "debriefVerdict": None,
            "quality": {"netR": 1.8, "grossR": 2.0, "feesR": 0.2, "mfeR": 2.1, "maeR": -0.3, "vsPlanR": 0.0,
                        "planOutcome": {"state": "TARGET_FIRST", "planR": 2.0, "firstHitAfterMinutes": 90}},
            "postExitMove": None}
    base.update(over)
    return base

def test_outcome_row_maps_quality_and_nulls_when_absent():
    r = outcome_row(served(), fetched_at=NOW)
    assert (r["position_id"], r["agent8"], r["net_r"], r["plan_state"], r["first_hit_min"]) == ("p1", "aaaaaaaa", 1.8, "TARGET_FIRST", 90)
    assert r["net_pnl"] == 1.5 and r["is_win"] is True and r["decision_id"] == "dec1"
    r0 = outcome_row(served(quality=None), fetched_at=NOW)
    assert r0["net_r"] is None and r0["plan_state"] is None and r0["position_id"] == "p1"

def test_backfill_from_fixture_loads_every_row_once():
    Session = db()
    counts = backfill_from_fixture(Session, FIXTURE)
    assert counts["new"] == 128
    assert backfill_from_fixture(Session, FIXTURE)["new"] == 0
    with Session() as s:
        row = s.get(TradeOutcome, s.query(TradeOutcome).first().position_id)
        t = as_trade(row)
        assert t.position_id == row.position_id and t.net_r == row.net_r

def test_upsert_updates_only_the_late_fields():
    Session = db()
    with Session() as s:
        assert upsert_outcome(s, outcome_row(served(), fetched_at=NOW)) == "new"
        assert upsert_outcome(s, outcome_row(served(), fetched_at=NOW)) == "same"
        assert upsert_outcome(s, outcome_row(served(debriefVerdict="CORRECT"), fetched_at=NOW)) == "updated"
        assert upsert_outcome(s, outcome_row(served(netPnl="9.99"), fetched_at=NOW)) == "same"
        s.commit()
        assert s.get(TradeOutcome, "p1").net_pnl == 1.5

def test_since_for_defaults_then_trails_the_newest_close():
    Session = db()
    with Session() as s:
        assert since_for(s, now=NOW) == SINCE_DEFAULT
        upsert_outcome(s, outcome_row(served(), fetched_at=NOW)); s.commit()
        assert since_for(s, now=NOW) == "2026-10-18T04:00:00+00:00"

async def test_collect_pages_and_enriches():
    Session = db()
    pages = iter([{"trades": [served()], "nextCursor": "c2"}, {"trades": [served(positionId="p2", decisionId=None)], "nextCursor": None}])
    fake = FakePlatform({"list_agent_trades": lambda args: next(pages),
                         "get_trade_outcome_by_decision": {"outcome": {"closedBy": "SYSTEM", "exitRepriceSource": "TIME_DECAY", "durationMinutes": 240}}})
    out = await collect_outcomes(fake, Session, now=NOW)
    assert (out["pages"], out["new"], out["enriched"]) == (2, 2, 1)
    with Session() as s:
        assert s.get(TradeOutcome, "p1").closed_by == "SYSTEM"
        assert s.get(TradeOutcome, "p2").enriched_at is None
    assert [c[0] for c in fake.calls].count("get_trade_outcome_by_decision") == 1
```

(`FakePlatform` accepts a callable per tool; confirm its `calls` attribute shape in `tests/platform/fake.py` and adjust the last assertion to it.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_outcomes.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'manager.learn.outcomes'`

- [ ] **Step 3: Implement `manager/learn/outcomes.py`** per the Interfaces block, then wire `backfill` (`--trades`, default the 10-26 fixture path from `replay.trades.DEFAULT_PATH`) and `collect` (runs `collect_outcomes` then Task 5's `collect_context` once it exists; for now outcomes only) in `manager/commands/learn.py`. Add `READ_SETS["get_trade_outcome_by_decision"] = frozenset({"outcome"})` and keep `list_agent_trades`' existing set (extend it with `trades[].quality`, `trades[].debriefVerdict`, `trades[].postExitMove`, `trades[].signalLogId`, `trades[].decisionId` only if the file's path grammar supports list elements; otherwise leave it).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q tests/learn tests/platform tests/replay`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manager/learn/outcomes.py manager/commands/learn.py manager/platform/reads.py tests/learn/test_outcomes.py
git commit -m "feat(learn): trade_outcomes collector, enrichment and the 10-26 backfill"
```

---

### Task 5: Context collector (`trade_context`, the data matrix)

**Files:**
- Create: `manager/learn/context.py`
- Modify: `manager/commands/learn.py` (`collect` also runs context), `manager/platform/reads.py` (`READ_SETS["get_regime_history"] = frozenset({"points"})` or the served key)
- Test: `tests/learn/test_context.py`

**Interfaces:**
- Consumes `Position` rows (`manager/db/models.py:212`, `raw` keys listed in the spec scout: `conviction, riskRewardRatio, effectiveLeverage, effectiveStopLoss, effectiveTakeProfit, strategyLabel, strategyTimeframe, agentName, openedAt`), `Agent` rows (`strategy_id`, `strategy_revision`, `trading_config["regimeTimeframe"]`), `TriageRow.metrics` (`atr, decided_stop, hard_stop, momentum_now, momentum_t1`), `Dossier.document["platform_reads"]["regime"]["data"]["regime"]` and `["structural_bias"]`, `Dossier.document["tape"]` (`funding, open_interest`), `PanelRow` (the hourly TPO row for the coin at or before `opened_at`; column names from the model), `AgentScan` (the rank of `(agent_id, coin)` in the newest scan at or before `opened_at`; column names from the model), `Snapshot` (the count of positions in the snapshot that first listed the position).
- Produces, in `manager/learn/context.py`:
  - `GROUPS = ("position", "agent", "triage", "regime", "tape", "tpo", "scan", "snapshot")` — the keys of `sources`.
  - `def first_sighting(s: Session, position_id: str) -> Position | None` — the earliest `positions` row for the id (by `snapshot_id`).
  - `def context_row(s: Session, pos: Position, *, now: datetime) -> dict` — pure DB; fills every column it can and records in `sources[group]` the table it used or `"missing"`. `stop_ratio = |entry - hard_stop| / |entry - decided_stop|` when both are present; `atr_pct = atr / entry * 100`; `hour_utc`/`weekday` from `opened_at`.
  - `def regime_at(points: list[dict], at: datetime) -> dict | None` — the newest point with `timestamp <= at` from a `get_regime_history` payload (keys `timestamp, regime, conviction`), `None` when none.
  - `async def fill_regime(client, row: dict, *, now: datetime) -> dict` — when `row["regime"]` is `None` and `row["regime_timeframe"]` is set: one `get_regime_history` call `{"coinTicker": coin, "timeframe": regime_timeframe, "bars": 500}`, sets `regime` and `sources["regime"] = "get_regime_history"`, or `"out_of_range"` when `opened_at` is older than the first point, or `"error: ..."` on a `PlatformError` (never raises).
  - `async def collect_context(client, session_factory, *, now: datetime, limit: int = 200) -> dict` — for up to `limit` distinct `positions.position_id` without a `trade_context` row, oldest first: `context_row`, `fill_regime`, insert. Returns `{"new", "regime_calls", "errors"}`. With `client is None` it skips `fill_regime` (the pure backfill path).

- [ ] **Step 1: Write the failing tests**

```python
# tests/learn/test_context.py
from datetime import UTC, datetime, timedelta
from manager.db.models import Snapshot, Position, Agent, TriageRow, TradeContext
from manager.learn.context import context_row, regime_at, fill_regime, collect_context, first_sighting
from tests.learn.support import db
from tests.platform.fake import FakePlatform

T0 = datetime(2026, 10, 20, 13, 30, tzinfo=UTC)

def seed(Session):
    """One agent, two snapshots, one position first seen in snapshot 1 (with raw), one triage row."""
    with Session() as s:
        s.add(Agent(agent_id="A", name="V4h", strategy_id="S", strategy_revision=3, trading_config={"regimeTimeframe": "4h"}, ...))  # fill the model's required columns from models.py:34
        snap = Snapshot(at=T0, reads={}, ...); s.add(snap); s.flush()
        s.add(Position(snapshot_id=snap.id, position_id="p1", agent_id="A", coin="BTC", side="LONG", direction="LONG",
                       entry=100.0, stop=90.0, take_profit=120.0, mark=101.0, size_usd=50.0, opened_at=T0.isoformat(),
                       strategy_timeframe="4h", raw={"conviction": 0.7, "riskRewardRatio": 2.0, "effectiveLeverage": 3,
                                                     "strategyLabel": "VWAP", "agentName": "V4h"}, ...))
        s.add(TriageRow(position_id="p1", at=T0 + timedelta(minutes=5), colour="GREEN", reasons=[],
                        metrics={"atr": 2.0, "decided_stop": 95.0, "hard_stop": 90.0, "momentum_now": "BULL", "momentum_t1": "FLAT"}, ...))
        s.commit()

def test_context_row_fills_from_position_agent_and_triage():
    Session = db(); seed(Session)
    with Session() as s:
        row = context_row(s, first_sighting(s, "p1"), now=T0)
    assert (row["strategy_id"], row["strategy_revision"], row["timeframe"], row["regime_timeframe"]) == ("S", 3, "4h", "4h")
    assert (row["conviction"], row["leverage"], row["atr"], row["decided_stop"], row["hard_stop"]) == (0.7, 3.0, 2.0, 95.0, 90.0)
    assert row["stop_ratio"] == 2.0 and row["atr_pct"] == 2.0 and (row["hour_utc"], row["weekday"]) == (13, 1)
    assert row["sources"]["triage"] == "triage_rows" and row["sources"]["tpo"] == "missing" and row["regime"] is None

def test_regime_at_picks_the_newest_point_at_or_before():
    pts = [{"timestamp": "2026-10-20T08:00:00+00:00", "regime": "TREND_UP", "conviction": 0.6},
           {"timestamp": "2026-10-20T12:00:00+00:00", "regime": "RANGE", "conviction": 0.5},
           {"timestamp": "2026-10-20T16:00:00+00:00", "regime": "TREND_DOWN", "conviction": 0.7}]
    assert regime_at(pts, T0)["regime"] == "RANGE"
    assert regime_at(pts, T0 - timedelta(days=2)) is None

async def test_collect_context_is_idempotent_and_calls_regime_once_per_position():
    Session = db(); seed(Session)
    fake = FakePlatform({"get_regime_history": {"points": [{"timestamp": "2026-10-20T12:00:00+00:00", "regime": "RANGE", "conviction": 0.5}]}})
    out = await collect_context(fake, Session, now=T0 + timedelta(hours=1))
    assert (out["new"], out["regime_calls"]) == (1, 1)
    assert (await collect_context(fake, Session, now=T0 + timedelta(hours=1)))["new"] == 0
    with Session() as s:
        row = s.get(TradeContext, "p1")
        assert row.regime == "RANGE" and row.sources["regime"] == "get_regime_history"

async def test_collect_context_without_client_marks_regime_missing():
    Session = db(); seed(Session)
    await collect_context(None, Session, now=T0)
    with Session() as s:
        assert s.get(TradeContext, "p1").sources["regime"] == "missing"
```

(The `...` in `seed` stand for the model's other required columns; read `models.py` for `Agent`, `Snapshot`, `Position`, `TriageRow` and fill them with placeholder values. The served key for the regime points is `points` unless the probe fixture says otherwise; pin it in a module constant `POINTS_KEY`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_context.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `manager/learn/context.py`** and extend the `collect` action to run `collect_outcomes` then `collect_context`. The dossier lookup takes the earliest dossier for the position (by `built_at`) only when the triage metrics lack what the dossier adds (`regime`, `structural_bias`, `funding`, `open_interest`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q tests/learn`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manager/learn/context.py manager/commands/learn.py manager/platform/reads.py tests/learn/test_context.py
git commit -m "feat(learn): trade_context, the entry-time feature matrix, with provenance per group"
```

---

### Task 6: The labeller (`decision_outcomes`)

**Files:**
- Create: `manager/learn/label.py`
- Modify: `manager/commands/learn.py` (`label` action)
- Test: `tests/learn/test_label.py`

**Interfaces:**
- Consumes `manager/replay/history.py`: `load_from_db(s) -> dict`, `build_positions(tables, trades, signal_log_stops=None, *, since=None) -> Built` (`Built.positions: list[Position]`), `Position.r_at(price, stop=None)`, `Position.steps: list[Step]` (`Step.dossier_id, mark, at`), `Position.decisions: list[DecisionRecord]` (`id, at, dossier_id, outcome, reason, mode, executed`), `Position.manager_closed`, `Position.executed_dossier_id`, `Position.trade: Trade`; `manager/replay/simulate.py`: `hold_outcome(pos) -> tuple[float, str]`, `SLIPPAGE_R`; Task 4's `as_trade`; `Action.performed_at` for latency.
- Produces, in `manager/learn/label.py`:
  - `GRADE_MARGIN_R = 0.25`, `DECAY_WINDOW_MIN = 300`, `METHOD_VERSION = 1`.
  - `@dataclass(frozen=True) class Graded`: the `decision_outcomes` columns except `decision_id` and `graded_at`.
  - `def close_at(pos: Position, step: Step) -> float | None` — `pos.r_at(step.mark) - pos.trade.fees_r - SLIPPAGE_R`, `None` when `r_at` is `None`.
  - `def plan_unreliable(pos: Position) -> bool` — `pos.trade.plan_state == "STOP_FIRST" and pos.trade.first_hit_min is not None and pos.trade.first_hit_min <= DECAY_WINDOW_MIN`.
  - `def grade(delta: float | None) -> str` — `UNGRADED` for `None`, `GOOD` when `delta > GRADE_MARGIN_R`, `BAD` when `delta < -GRADE_MARGIN_R`, else `UNCLEAR`.
  - `def grade_decision(pos: Position, rec: DecisionRecord, step: Step | None, *, latency_s: float | None) -> Graded`:
    - `realized_r = pos.trade.net_r` always (the path that actually happened).
    - `rec.outcome == "CLOSE" and rec.executed`: `counterfactual_r, basis = hold_outcome(pos)` (`"plan"` or `"real"`); `delta = realized_r - counterfactual_r`.
    - `rec.outcome == "CLOSE"` and not executed (SHADOW or refused): `counterfactual_r = close_at(pos, step)`, basis `"mark"`; `delta = counterfactual_r - realized_r` (the decision is graded on what closing would have earned).
    - `rec.outcome in ("HOLD", "TIGHTEN")`: `counterfactual_r = close_at(pos, step)`, basis `"mark"`; `delta = realized_r - counterfactual_r`.
    - `step is None` or `counterfactual_r is None` → `delta = None`, grade `UNGRADED`.
    - `r_at_decision = pos.r_at(step.mark)` when the step exists; `post_exit_4h` from the trade outcome row (passed in by the caller as `pos.trade` has none: add a `post_exit_4h: float | None` parameter).
  - `def label_decisions(session_factory, *, now: datetime, since: datetime | None = None) -> dict` — `tables = load_from_db(s)`; `trades = {row.position_id: as_trade(row) for row in trade_outcomes}`; `built = build_positions(tables, trades, since=since)`; for every `DecisionRecord` without a `decision_outcomes` row at `METHOD_VERSION`, find its step by `dossier_id`, the latency from the DONE action with that `decision_id` (`performed_at - rec.at`), grade, upsert. Returns `{"graded", "pending": [decision ids whose position has no trade outcome], "skipped_excluded": built.excluded}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/learn/test_label.py
from datetime import UTC, datetime, timedelta
from manager.replay.history import Position, Step, DecisionRecord
from manager.replay.trades import Trade
from manager.replay.simulate import SLIPPAGE_R
from manager.learn.label import grade_decision, grade, plan_unreliable, close_at, GRADE_MARGIN_R, DECAY_WINDOW_MIN

T = datetime(2026, 10, 14, 2, tzinfo=UTC)

def trade(**over):
    base = dict(position_id="p", agent8="aaaaaaaa", coin="PUMP", direction="SHORT", entry=100.0, exit=104.0,
                close_reason="MARKET_CLOSE", opened_at="2026-10-14T00:00:00+00:00", closed_at="2026-10-14T02:12:00+00:00",
                net_r=-0.44, gross_r=-0.40, fees_r=0.04, mfe_r=-0.23, mae_r=-1.17, plan_state="STOP_FIRST", plan_r=-1.02,
                first_hit_min=6.0, net_pnl=-0.5)
    base.update(over); return Trade(**base)

def position(t, *, manager_closed, mark=104.0):
    step = Step(at=T, colour="AMBER", reasons=["THESIS_GATE_FALSE"], metrics={}, dossier_id=7, mark=mark, stop=112.0, take_profit=80.0, trailing_engaged=False)
    return Position(position_id="p", agent_id="A", coin="PUMP", direction="SHORT", timeframe="15m", opened_at=T - timedelta(hours=2),
                    entry=100.0, decided_stop=110.0, decided_stop_source="triage_decided_stops", hard_stop=120.0, trade=t,
                    steps=[step], decisions=[], manager_closed=manager_closed, executed_dossier_id=7 if manager_closed else None), step

def test_executed_close_against_a_stop_first_plan_is_good_but_plan_unreliable():
    pos, step = position(trade(), manager_closed=True)
    rec = DecisionRecord(id=91, at=T, dossier_id=7, outcome="CLOSE", reason="THESIS_GATE_FALSE", mode="LIVE", executed=True)
    g = grade_decision(pos, rec, step, latency_s=30.0, post_exit_4h=1.71)
    assert g.counterfactual_basis == "plan" and g.counterfactual_r == -1.02 - 0.04
    assert g.delta_r == (-0.44) - (-1.06) and g.grade == "GOOD" and g.plan_unreliable is True

def test_shadow_close_is_graded_on_what_closing_would_have_earned():
    t = trade(net_r=-1.0, close_reason="STOP_LOSS", plan_state="STOP_FIRST", first_hit_min=600.0)
    pos, step = position(t, manager_closed=False, mark=101.0)
    rec = DecisionRecord(id=50, at=T, dossier_id=7, outcome="CLOSE", reason="REGIME_FLIP", mode="SHADOW", executed=False)
    g = grade_decision(pos, rec, step, latency_s=None, post_exit_4h=None)
    expected_close = pos.r_at(101.0) - 0.04 - SLIPPAGE_R
    assert g.counterfactual_basis == "mark" and g.counterfactual_r == expected_close
    assert g.delta_r == expected_close - (-1.0) and g.grade == "GOOD" and g.plan_unreliable is False

def test_hold_that_ran_to_target_beats_closing_at_the_mark():
    t = trade(net_r=2.0, close_reason="TAKE_PROFIT", plan_state="TARGET_FIRST", plan_r=2.0, first_hit_min=400.0)
    pos, step = position(t, manager_closed=False, mark=99.0)
    rec = DecisionRecord(id=60, at=T, dossier_id=7, outcome="HOLD", reason="TIME_STOP", mode="LIVE", executed=False)
    g = grade_decision(pos, rec, step, latency_s=None, post_exit_4h=None)
    assert g.grade == "GOOD" and g.delta_r == 2.0 - g.counterfactual_r

def test_missing_step_or_r_is_ungraded():
    pos, step = position(trade(), manager_closed=True)
    rec = DecisionRecord(id=1, at=T, dossier_id=99, outcome="HOLD", reason="TIME_STOP", mode="LIVE", executed=False)
    assert grade_decision(pos, rec, None, latency_s=None, post_exit_4h=None).grade == "UNGRADED"

def test_grade_margin():
    assert grade(GRADE_MARGIN_R + 0.01) == "GOOD" and grade(-GRADE_MARGIN_R - 0.01) == "BAD" and grade(0.1) == "UNCLEAR" and grade(None) == "UNGRADED"
```

Plus one DB test `test_label_decisions_grades_each_decision_once_and_reports_pending` that seeds, through the ORM, one dossier + decision + triage rows + snapshot positions for a position that has a `trade_outcomes` row and one that does not, runs `label_decisions(Session, now=...)` twice, and asserts `graded == 1` then `0`, `pending == [<the other decision id>]`, and that the `decision_outcomes` row has `method_version == 1`. Use `manager/replay/history.py`'s `export_tables` field list (lines 103-124) to know which columns `build_positions` needs.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_label.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `manager/learn/label.py`** and the `label` action (`manager learn label [--since ISO]` prints the returned dict as one line per key).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q tests/learn tests/replay`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manager/learn/label.py manager/commands/learn.py tests/learn/test_label.py
git commit -m "feat(learn): decision_outcomes, hindsight grades against the plan or the mark"
```

---

### Task 7: Scorecards and the weekly report

**Files:**
- Create: `manager/learn/score.py`, `manager/learn/views.py`
- Modify: `manager/commands/learn.py` (`score`, `show` actions), `manager/api/app.py` (one GET)
- Test: `tests/learn/test_score.py`, `tests/learn/test_views.py`, `tests/api/...` (one endpoint test in the existing API test module's style)

**Interfaces:**
- Consumes Tasks 1, 2, 4, 5, 6 tables; `get_state` / `set_state` (`manager/audit/ledger.py`); `dossier_hash` is not needed.
- Produces, in `manager/learn/score.py`:
  - `PERIOD_START = datetime(2026, 9, 19, tzinfo=UTC)`, `SCORE_WEEKDAY = 0` (Monday), `SCORE_AT = time(1, 0)`, `STATE_KEY = "learn.scorecards"` (≤ 32 chars).
  - `HOUR_BANDS = ((0, 4), (4, 8), (8, 12), (12, 16), (16, 20), (20, 24))`; `hour_band(hour: int) -> str` like `"08-12"`.
  - `TRADE_SLICES: dict[str, Callable[[TradeOutcome, TradeContext], str | None]]` with keys `agent`, `strategy_rev` (`f"{strategy_id}@{strategy_revision}"`), `timeframe`, `coin`, `regime`, `hour_band`, `direction`, `agent|timeframe`, `agent|regime`, `close_reason`; a slice function returning `None` leaves the trade out of that slice.
  - `DECISION_SLICES` with keys `reason`, `outcome`, `reason|outcome`, `agent|reason` over `DecisionOutcome` joined to `TradeContext`; graded rows only.
  - `PLATFORM_SLICES` with keys `strategy_name`, `coin`, `regime_at_decision`, `close_reason`, `direction` over `PlatformTrade` joined to the newest `PlatformAgent` row per agent; the R-like value is `roe_pct / 100` per trade (the public read has no R; the report says so).
  - `def trade_cards(s, *, since, until) -> list[dict]`, `decision_cards`, `platform_cards` — each returns `scorecards` row dicts: `n`, `wins` (`net_r > 0`, or `delta_r > 0` for decisions, `is_win` for platform), `mean_r`, `ci_low/ci_high` via `bootstrap_mean_ci`, `win_low/win_high` via `wilson`, `break_even_wr`, and for decisions `good/bad/unclear/mean_delta_r`; `status = classify(n, ci)`. Trades with `net_r is None` are counted in a separate `("trades", "unscored", "all")` row with `n` only.
  - `def build_scorecards(s, *, now: datetime) -> list[dict]` — all three, `period_start = PERIOD_START`, `period_end = now`.
  - `def write_scorecards(s, rows: list[dict], *, now: datetime) -> int` — inserts with `built_at = now`, returns the count, and `set_state(s, STATE_KEY, {"builtAt": now.isoformat(), "rows": count})`.
  - `def score_due(s, now: datetime) -> bool` — true when `now.weekday() == SCORE_WEEKDAY and now.time() >= SCORE_AT` and the state's `builtAt` is older than 6 days; `--now` forces.
  - `def latest_built_at(s) -> datetime | None`.
- Produces, in `manager/learn/views.py`:
  - `WATCH_KEY = "learn.watch"`.
  - `def render_scorecards(s, *, now: datetime) -> str` — markdown: `## Learning scorecards built {builtAt}` and the age line; `### Edges (trades)` listing EDGE rows `- {slice_kind}={slice_key}: n={n}, mean {mean_r:+.2f}R, CI [{lo:+.2f}, {hi:+.2f}], win {wins}/{n} (break-even {be:.0%})`; `### No edge` the NO_EDGE rows the same way; `### Insufficient` as `- {slice_kind}={slice_key}: n={n} (needs {MIN_SAMPLE})`; `### Decisions` the decision rows with `GOOD/BAD/UNCLEAR` counts and `mean delta`; `### Other agents (public, ROE-based)` the platform rows; `### Unscored trades` the count. Status lines use the words `EDGE`, `NO_EDGE`, `INSUFFICIENT` verbatim.
  - `def learn_view(s, now) -> dict` — `{"builtAt", "ageLine", "freshness": "fresh"|"stale"` (stale after 8 days) `, "markdown"}`.
  - `def watch_view(s, now) -> dict` — `learn_view` plus `mention: bool`, true once per `builtAt` (state `WATCH_KEY = {"builtAt"}`), the same pattern as `manager/review/views.py:216`.
- Produces `GET /api/learn/latest?watch=0|1` in `manager/api/app.py` next to `review_latest` (`app.py:449`), `dependencies=[Depends(auth)]`.

- [ ] **Step 1: Write the failing tests**

`tests/learn/test_score.py`: seed 25 `trade_outcomes` + `trade_context` rows for agent `A` on `4h` with `net_r` alternating `+2.0, -0.5` (an edge), 5 rows for agent `B` (insufficient), 3 graded `decision_outcomes` with `delta_r` `+0.5, +0.4, -0.1`; then:

```python
def test_trade_cards_classify_edge_and_insufficient():
    rows = {(r["slice_kind"], r["slice_key"]): r for r in trade_cards(s, since=PERIOD_START, until=NOW)}
    a = rows[("agent", "A")]; b = rows[("agent", "B")]
    assert a["n"] == 25 and a["status"] == "EDGE" and a["ci_low"] > 0 and a["wins"] == 13
    assert b["status"] == "INSUFFICIENT" and b["mean_r"] is None and b["ci_low"] is None
    assert rows[("agent|timeframe", "A|4h")]["n"] == 25

def test_decision_cards_count_grades():
    r = {(x["slice_kind"], x["slice_key"]): x for x in decision_cards(s, since=PERIOD_START, until=NOW)}[("outcome", "CLOSE")]
    assert (r["good"], r["bad"], r["unclear"], r["status"]) == (2, 0, 1, "INSUFFICIENT")

def test_unscored_trades_are_counted_not_dropped():  # one more trade with net_r None
    ...
    assert rows[("unscored", "all")]["n"] == 1 and rows[("agent", "A")]["n"] == 25

def test_score_due_is_weekly_monday_0100_and_forced_by_now():
    assert score_due(s, datetime(2026, 11, 2, 1, 0, tzinfo=UTC)) is True       # a Monday
    write_scorecards(s, build_scorecards(s, now=datetime(2026, 11, 2, 1, 5, tzinfo=UTC)), now=...)
    assert score_due(s, datetime(2026, 11, 3, 1, 0, tzinfo=UTC)) is False
    assert score_due(s, datetime(2026, 11, 9, 0, 30, tzinfo=UTC)) is False and score_due(s, datetime(2026, 11, 9, 1, 0, tzinfo=UTC)) is True
```

`tests/learn/test_views.py`: after `write_scorecards`, `render_scorecards` contains `### Edges (trades)`, the line for `agent=A` with `n=25`, the word `INSUFFICIENT` for `B`, and `watch_view` returns `mention True` once then `False`. `tests/api`: `GET /api/learn/latest` with the bearer returns 200 and the `markdown` key, 401 without.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_score.py tests/learn/test_views.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `score.py`, `views.py`, the endpoint, and the CLI actions** (`score [--now]` builds and writes when due or forced and prints the count; `show` prints `render_scorecards`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q tests/learn tests/api`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manager/learn/score.py manager/learn/views.py manager/api/app.py manager/commands/learn.py tests/learn tests/api
git commit -m "feat(learn): weekly scorecards by slice with bootstrap CIs, the report and its endpoint"
```

---

### Task 8: Condition observations with forward returns

**Files:**
- Create: `manager/learn/conditions.py`
- Modify: `manager/settings.py` (`LEARN_SIGNAL_LOG_BUDGET: int = Field(default=200, alias="LEARN_SIGNAL_LOG_BUDGET")`), `manager/commands/learn.py` (`collect` runs this too), `manager/platform/reads.py` (`READ_SETS["get_signal_log"]`: add `log.conditionEvaluation`, `log.strategyRevision` or the served paths; `READ_SETS["list_signal_logs"] = frozenset({"logs", "nextCursor"})` or the served keys)
- Test: `tests/learn/test_conditions.py`

**Interfaces:**
- Consumes `TradeOutcome.signal_log_id / agent_id / net_r`, `get_signal_log(agentId, logId)` whose `conditionEvaluation` lists the strategy's condition readings (pin the item keys from the probe fixture or `manager_schemas_132.0.0.json` in module constants: `CONDITION_ITEMS_PATH`, `KEY_FIELD`, `TRUTH_FIELD`, `REQUIRED_FIELD`, `METRIC_FIELD`), `list_signal_logs` rows (`id, agentId, coinTicker, direction/assessment, terminalStatus, evaluatedAt` or the served names, pinned the same way), `cached_candles_between` (`manager/tape/hyperliquid.py:244`), `atr` (`manager/tape/indicators.py:5`), `INTERVAL_MS`, `Agent.strategy_id / strategy_revision / trading_config` for the timeframe.
- Produces, in `manager/learn/conditions.py`:
  - `FWD_BARS = 4`, `ATR_BARS = 15`, `OUTCOME_FWD = "fwd_atr_4"`, `OUTCOME_NET_R = "net_r"`, `OUTCOME_NONE = "none"`.
  - `def observations_from_log(log: dict, *, source: str, source_id: str, position_id: str | None, agent_id: str, coin: str, direction: str | None, evaluated_at: datetime, strategy_id: str | None, strategy_revision: int | None, outcome_kind: str, outcome_r: float | None, built_at: datetime) -> list[dict]` — one dict per condition item; an empty `conditionEvaluation` returns `[]`.
  - `async def forward_return_atr(session_factory, http, coin: str, timeframe: str, evaluated_at: datetime, direction: str, *, now: datetime) -> float | None` — bars from `evaluated_at - ATR_BARS*step` to `evaluated_at + FWD_BARS*step` through `cached_candles_between`; `atr` over the bars up to and including the evaluation bar; return `sign * (close[+FWD_BARS] - close[eval]) / atr`; `None` when the window's last bar is still forming (`evaluated_at + (FWD_BARS+1)*step > now`), when `TapeError` is raised, or when `atr` is `None`.
  - `async def collect_entered(client, session_factory, *, now) -> dict` — for each `trade_outcomes` row with `signal_log_id` and no observation with `source="trade"`: one `get_signal_log`, write observations with `outcome_kind="net_r"`, `outcome_r=net_r` (also when `net_r` is `None`: then `outcome_kind="none"`). Returns `{"logs", "observations", "errors"}`.
  - `async def collect_evaluated(client, session_factory, http, *, now, budget: int) -> dict` — pages `list_signal_logs` (`limit 50`, `since` = newest `evaluated_at` stored for `source="signal_log"` or `PERIOD_START`), skips rows whose `id` already has observations or whose log produced an entered trade (`terminalStatus` in the entered set, or a `trade_outcomes.signal_log_id` match), and for up to `budget` newest rows: one `get_signal_log`, `forward_return_atr`, write with `outcome_kind` `fwd_atr_4` or `none`. Returns `{"pages", "logs", "observations", "unresolved", "errors"}`.
  - `async def refill_unresolved(session_factory, http, *, now, limit: int = 200) -> int` — observations with `outcome_kind="none"` and `source="signal_log"` whose window has now closed: recompute and update the whole `(source, source_id)` group; returns the number resolved.

- [ ] **Step 1: Write the failing tests**

```python
# tests/learn/test_conditions.py (sketch of the assertions; build fixtures by hand)
def test_observations_from_log_one_row_per_condition():
    log = {"conditionEvaluation": {"items": [{"key": "rsi_oversold", "result": True, "required": True, "metric": "RSI_14"},
                                             {"key": "vwap_below", "result": False, "required": False, "metric": "VWAP"}]}}
    rows = observations_from_log(log, source="trade", source_id="log1", position_id="p1", agent_id="A", coin="BTC", direction="LONG",
                                 evaluated_at=T, strategy_id="S", strategy_revision=3, outcome_kind="net_r", outcome_r=1.2, built_at=T)
    assert [(r["condition_key"], r["value_true"], r["required"], r["metric_code"]) for r in rows] == [("rsi_oversold", True, True, "RSI_14"), ("vwap_below", False, False, "VWAP")]
    assert rows[0]["outcome_r"] == 1.2 and observations_from_log({"conditionEvaluation": {"items": []}}, ...) == []

async def test_forward_return_is_signed_and_in_atr_units(monkeypatch):
    # 20 synthetic 15m bars: flat closes at 100 with range 2 (ATR 2), then close 104 four bars after the evaluation bar
    ...
    assert await forward_return_atr(Session, None, "BTC", "15m", T_EVAL, "LONG", now=T_EVAL + timedelta(hours=3)) == 2.0
    assert await forward_return_atr(Session, None, "BTC", "15m", T_EVAL, "SHORT", now=...) == -2.0

async def test_forward_return_is_none_while_the_window_is_forming():
    assert await forward_return_atr(Session, None, "BTC", "15m", T_EVAL, "LONG", now=T_EVAL + timedelta(minutes=30)) is None

async def test_collect_evaluated_respects_budget_and_skips_entered():
    # 3 listed logs: one entered (has a trade_outcomes row), two not; budget 1 -> exactly one get_signal_log call for a non-entered log
    ...
    assert fake_call_count("get_signal_log") == 1 and out["logs"] == 1

async def test_unresolved_is_refilled_later():
    ...
    assert (await refill_unresolved(Session, None, now=T_EVAL + timedelta(hours=3))) == 1
```

(`monkeypatch` `manager.learn.conditions.cached_candles_between` with an async function returning the synthetic bars so no HTTP happens. Replace the `...` with the seeded rows; the shapes of `conditionEvaluation` and the list rows are the probe's when it exists; the test's literal keys then change to match and the module constants are the single place that knows them.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_conditions.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `manager/learn/conditions.py`**, the setting, and extend `collect` (`collect_entered`, `collect_evaluated` with `budget=settings.learn_signal_log_budget`, `refill_unresolved`). The `http` client is an `httpx.AsyncClient()` opened by the caller and closed in `finally`, as `triage/inputs.read_candles` does.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q tests/learn tests/tape`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manager/learn/conditions.py manager/settings.py manager/commands/learn.py manager/platform/reads.py tests/learn/test_conditions.py
git commit -m "feat(learn): condition_observations from entered and non-entered evaluations, forward return in ATR"
```

---

### Task 9: Condition statistics and the strategist's block

**Files:**
- Create: `manager/learn/condition_stats.py`
- Modify: `manager/learn/score.py` (the scorer also builds condition stats), `manager/strategist/turn.py:120` (`build_messages`), `manager/strategist/brief.md`
- Test: `tests/learn/test_condition_stats.py`, `tests/strategist/test_turn.py` (one new test in the existing module)

**Interfaces:**
- Consumes `ConditionObservation`, `ConditionStat`, Task 2 stats, `turn.build_messages(chat, history, user_text)` and the chat's strategy id (read from the `chat` argument: the builder confirms the attribute in `manager/strategist/turn.py` / the `strategy_chats` model).
- Produces, in `manager/learn/condition_stats.py`:
  - `def build_condition_stats(s, *, now: datetime) -> list[dict]` — per `(strategy_id, strategy_revision, condition_key, outcome_kind)` with `outcome_r` not null: `n_true`, `n_false`, `mean_true`, `mean_false`, `lift = mean_true - mean_false`, `ci` = `bootstrap_mean_ci` over the pairwise difference proxy: bootstrap each side's mean and take the difference per iteration (write `bootstrap_lift_ci(true_values, false_values)` in `stats.py` with the same seed/iters, returning `None` when either side has fewer than 2), `status = classify(min(n_true, n_false), ci)`; `metric_code` from any observation in the group.
  - `def write_condition_stats(s, rows, *, now) -> int`.
  - `STRATEGIST_CAP = 4000`; `def render_for_strategist(s, strategy_id: str) -> str` — `""` when no rows; otherwise `CONDITION STATS (measured on your own agents' evaluations; INSUFFICIENT = fewer than 20 on a side):` then one line per newest-built row for that strategy, `- rev {rev} {condition_key} [{metric_code}] {outcome_kind}: true n={n_true} mean {mean_true:+.2f}, false n={n_false} mean {mean_false:+.2f}, lift {lift:+.2f} {status}`, truncated to `STRATEGIST_CAP` characters at a line boundary.
- Modifies `build_messages` so the system prompt is `BRIEF + MENU block + ("\n\n" + render_for_strategist(s, chat.strategy_id) if non-empty)`; `brief.md` gains one sentence: "A CONDITION STATS block, when present, is measured on the user's own agents' past evaluations; INSUFFICIENT means fewer than 20 readings on one side, never evidence either way."

- [ ] **Step 1: Write the failing tests**

```python
# tests/learn/test_condition_stats.py
def test_lift_and_status():  # seed 25 true (mean +0.5) and 25 false (mean -0.5) for S@3/rsi_oversold, 3 true/2 false for vwap_below
    rows = {(r["condition_key"]): r for r in build_condition_stats(s, now=NOW)}
    r = rows["rsi_oversold"]
    assert (r["n_true"], r["n_false"], r["lift"], r["status"]) == (25, 25, 1.0, "EDGE")
    assert rows["vwap_below"]["status"] == "INSUFFICIENT" and rows["vwap_below"]["lift"] is None

def test_render_for_strategist_caps_and_names_insufficient():
    write_condition_stats(s, build_condition_stats(s, now=NOW), now=NOW)
    text = render_for_strategist(s, "S")
    assert text.startswith("CONDITION STATS") and "rsi_oversold [RSI_14]" in text and "INSUFFICIENT" in text and len(text) <= STRATEGIST_CAP
    assert render_for_strategist(s, "OTHER") == ""
```

`tests/strategist/test_turn.py`: `build_messages` includes `CONDITION STATS` when rows exist for the chat's strategy and does not when none do.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_condition_stats.py tests/strategist`
Expected: FAIL with `ModuleNotFoundError` / `AssertionError`

- [ ] **Step 3: Implement `condition_stats.py`, `bootstrap_lift_ci`, the scorer hook (`build_scorecards` also calls `build_condition_stats` + `write_condition_stats`), the `build_messages` change and the brief sentence.** `build_messages` gets a session the way it gets the chat today; if it has none, add a `session_factory` keyword the relay passes (the builder reads `manager/strategist/turn.py` and the relay call site).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q tests/learn tests/strategist`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manager/learn/condition_stats.py manager/learn/stats.py manager/learn/score.py manager/strategist/turn.py manager/strategist/brief.md tests/learn/test_condition_stats.py tests/strategist
git commit -m "feat(learn): condition_stats with lift CIs; the strategist reads them as a context block"
```

---

### Task 10: The cross-agent pull (`platform_agents`, `platform_trades`)

**Files:**
- Create: `manager/learn/platform.py`
- Modify: `manager/settings.py` (`LEARN_PLATFORM_AGENTS: int = Field(default=50, alias=...)`, `LEARN_PLATFORM_PAGES: int = Field(default=4, ...)`), `manager/commands/learn.py` (`platform [--now]`), `manager/platform/reads.py` (sets for the four public reads, from the probe)
- Test: `tests/learn/test_platform.py`

**Interfaces:**
- Consumes `call_narrowing`, `measured_call`, `PlatformAgent`, `PlatformTrade`, `insert_ignoring_conflict`, `get_state/set_state`.
- Produces, in `manager/learn/platform.py`:
  - `STATE_KEY = "learn.platform"`, `PULL_AT = time(2, 0)`, `EXPLORER_ARGS = {"limit": 100, "timeframe": "MONTHLY", "sortBy": "NET_PNL"}`, `LEADERBOARD_ARGS = {"metric": "PROFIT", "timeframe": "MONTHLY", "limit": 100}`, `TRADES_WINDOW = "30D"`, `TRADES_LIMIT = 50`.
  - `def agent_rows(explorer: dict, leaderboard: dict, *, day: datetime) -> list[dict]` — one dict per explorer entry (`agent_id, name, owner, strategy_name, timeframe, status, net_pnl, win_rate, trade_count, rank_explorer` = 1-based position, `rank_leaderboard` = the entry's 1-based position in the leaderboard or `None`, `config_spec` = the public config spec object, `raw` = the entry). Served key names pinned in module constants from the probe fixture.
  - `def trade_rows(agent_id: str, page: dict, *, fetched_at) -> list[dict]` — per served trade: `trade_id` (`positionId`, else `id`), `coin, direction, opened_at, closed_at, net_pnl, is_win, price_move_pct, roe_pct, leverage, conviction, duration_min, close_reason, closed_by, regime_at_decision` (`regimeAtDecision.regime`), `regime_conviction`, `raw`.
  - `def pull_due(s, now) -> bool` — once per UTC day after `PULL_AT`.
  - `async def pull_platform(client, session_factory, *, now: datetime, agents: int, pages: int) -> dict` — explorer via `call_narrowing(client, "get_agent_explorer", EXPLORER_ARGS, floor=10)`; leaderboard via `measured_call`; insert agent rows (ignore conflicts on the day); for the first `agents` entries: `get_public_agent_realized_trades` `{"agentId", "window": TRADES_WINDOW, "limit": TRADES_LIMIT}` paged with `cursor` up to `pages` pages, trade rows inserted ignoring conflicts; `get_public_agent_signal_performance` stored in the agent row's `signal_performance`. A `PlatformError` on one agent is appended to `errors` and the loop continues; one on the explorer raises. Returns `{"agents", "trades_new", "pages", "errors", "calls"}` and `set_state(STATE_KEY, {"day", "at", ...})`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/learn/test_platform.py
def test_agent_rows_rank_from_both_lists_and_null_when_unlisted():
    ex = {"entries": [{"agentId": "a1", "name": "One", "strategyName": "VWAP", "netPnl": 10.0}, {"agentId": "a2", "name": "Two"}]}
    lb = {"entries": [{"agentId": "a2"}]}
    rows = agent_rows(ex, lb, day=DAY)
    assert [(r["agent_id"], r["rank_explorer"], r["rank_leaderboard"]) for r in rows] == [("a1", 1, None), ("a2", 2, 1)]

def test_trade_rows_read_regime_at_decision():
    page = {"trades": [{"positionId": "t1", "coinTicker": "BTC", "direction": "UP", "netPnl": "1.0", "isWin": True,
                        "regimeAtDecision": {"regime": "TREND_UP", "conviction": 0.6}}], "nextCursor": None}
    r = trade_rows("a1", page, fetched_at=NOW)[0]
    assert (r["trade_id"], r["regime_at_decision"], r["regime_conviction"], r["is_win"]) == ("t1", "TREND_UP", 0.6, True)

async def test_pull_narrows_the_explorer_and_is_idempotent_per_day():
    calls = []
    def explorer(args):
        calls.append(args["limit"])
        if args["limit"] > 50:
            raise PlatformError(Kind.TOOL_ERROR, "RESULT_TOO_LARGE", code="RESULT_TOO_LARGE")   # whatever call_narrowing keys on; read cap.py
        return {"entries": [{"agentId": "a1", "name": "One"}]}
    fake = FakePlatform({"get_agent_explorer": explorer, "get_leaderboard": {"entries": []},
                         "get_public_agent_realized_trades": {"trades": [], "nextCursor": None},
                         "get_public_agent_signal_performance": {"evaluationCount": 1}})
    out = await pull_platform(fake, Session, now=NOW, agents=50, pages=4)
    assert calls == [100, 50] and out["agents"] == 1
    assert (await pull_platform(fake, Session, now=NOW, agents=50, pages=4))["agents"] == 0   # same day: rows exist
    with Session() as s:
        assert s.query(PlatformAgent).count() == 1 and s.query(PlatformAgent).one().signal_performance == {"evaluationCount": 1}

async def test_one_agent_error_does_not_stop_the_pull():
    ...
    assert out["errors"] and out["agents"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_platform.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `manager/learn/platform.py`, the two settings, the `platform` action, and the `READ_SETS` entries.**

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q tests/learn tests/platform`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add manager/learn/platform.py manager/settings.py manager/commands/learn.py manager/platform/reads.py tests/learn/test_platform.py
git commit -m "feat(learn): daily pull of the explorer, leaderboard and public realized trades"
```

---

### Task 11: The four jobs, Compose services and the blind path

**Files:**
- Modify: `manager/scheduler/jobs.py` (four job functions), `manager/commands/run.py:14,23-26` (`JOBS`), `compose.yaml` (four services + the header comment), `tests/scheduler/test_jobs.py:287` (the exact `JOBS` set), `tests/scheduler/test_silence.py` (name lengths pass as is), `tests/test_compose.py` (if it lists services)
- Test: `tests/learn/test_jobs.py`

**Interfaces:**
- Produces, in `manager/scheduler/jobs.py`, each lazy-importing its cycle:
  - `async def job_outcomes(ctx: JobContext) -> None` — `collect_outcomes`, `collect_context`, `collect_entered`, `collect_evaluated(budget=ctx.settings.learn_signal_log_budget)`, `refill_unresolved`; beats `"outcomes"` with `ok=True` and a note `f"outcomes {new}/{updated} context {n} conditions {m}"`; on `PlatformError` with `kind is Kind.AUTH` beats `ok=False, note=str(e)[:500]` and returns; on any other exception `log.exception` and beats `ok=False`.
  - `async def job_label(ctx)` — `label_decisions`; beats `"label"` with `graded`/`pending` counts.
  - `async def job_scorecards(ctx)` — when `score_due(s, now)`: `build_scorecards` + `write_scorecards` (+ condition stats via Task 9's hook), beat `ok=True, note=f"{count} rows"`; else beat `ok=True, note="not due"`.
  - `async def job_platform(ctx)` — when `pull_due`: `pull_platform(agents=..., pages=...)`, beat with counts; AUTH → `ok=False`; else `"not due"`.
- `JOBS` gains `"outcomes": job_outcomes, "label": job_label, "scorecards": job_scorecards, "platform": job_platform`.
- `compose.yaml` gains, after `review`:

```yaml
  outcomes:     # learn (1): trade outcomes, entry context and condition observations; reads only
    <<: *manager
    command: ["python", "-m", "manager", "run", "outcomes", "--every", "900"]
  label:        # learn (2): hindsight grades for every decision, from the database only
    <<: *manager
    command: ["python", "-m", "manager", "run", "label", "--hourly-at", "10"]
  scorecards:   # learn (3): weekly scorecards and condition stats (Monday 01:00Z); report-only
    <<: *manager
    command: ["python", "-m", "manager", "run", "scorecards", "--every", "3600"]
  platform:     # learn (4): daily pull of other agents' public trades (02:00Z); reads only
    <<: *manager
    command: ["python", "-m", "manager", "run", "platform", "--every", "3600"]
```

- [ ] **Step 1: Write the failing tests**

```python
# tests/learn/test_jobs.py  (pattern: tests/review/test_job.py)
async def test_job_outcomes_beats_false_on_auth_and_writes_nothing(monkeypatch):
    async def blind(*a, **k): raise PlatformError(Kind.AUTH, "token refresh refused")
    monkeypatch.setattr("manager.learn.outcomes.collect_outcomes", blind)
    await job_outcomes(JobContext(client=FakePlatform({}), session_factory=Session, settings=settings))
    with Session() as s:
        hb = s.query(Heartbeat).one()
        assert (hb.job, hb.ok) == ("outcomes", False) and "refused" in hb.note
        assert s.query(TradeOutcome).count() == 0

async def test_job_scorecards_not_due_still_beats():
    await job_scorecards(JobContext(client=FakePlatform({}), session_factory=Session, settings=settings))
    assert [(h.job, h.ok, h.note) for h in heartbeats()] == [("scorecards", True, "not due")]

def test_jobs_registered_and_names_fit():
    assert {"outcomes", "label", "scorecards", "platform"} <= set(JOBS) and all(len(n) <= 22 for n in JOBS)
```

Update `tests/scheduler/test_jobs.py:287`'s exact set and any compose service list test.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/learn/test_jobs.py tests/scheduler`
Expected: FAIL (`ImportError: cannot import name 'job_outcomes'`, and the exact-set assertion)

- [ ] **Step 3: Implement the four jobs, register them, add the Compose services and the header-comment line.**

- [ ] **Step 4: Run the whole suite**

Run: `.venv/Scripts/python -m pytest -q`
Expected: PASS (the number printed; record it in the commit message)

- [ ] **Step 5: Commit**

```bash
git add manager/scheduler/jobs.py manager/commands/run.py compose.yaml tests/learn/test_jobs.py tests/scheduler tests/test_compose.py
git commit -m "feat(learn): outcomes, label, scorecards and platform as Docker jobs; blind path beats ok=False"
```

---

### Task 12: Commander delivery of the scorecards

**Files:**
- Create: `hermes/scripts/battlegrid_learn_watch.py`
- Modify: `hermes/install_commander.py` (constants `LEARN_JOB_NAME = "[bot:commander] BattleGrid learning scorecards"`, `LEARN_SCRIPT = "battlegrid_learn_watch.py"`, `LEARN_EVERY = "every 6h"`, a `--learn-watch` flag that calls `install_watch_job` the way `--review-watch` does)
- Test: `tests/hermes/test_learn_watch.py`, `tests/hermes/test_install_commander.py` (one new case)

**Interfaces:**
- Consumes `GET /api/learn/latest?watch=1` (Task 7) and `hermes/scripts/battlegrid_review_watch.py`'s structure (`read_token`, `http_get_json`, `main(argv=None, *, environ=None, get=..., env_file=None) -> int`).
- Produces the same `main` contract: stale → print the age line, exit 1; `mention` true → print `markdown`, exit 0; otherwise print nothing, exit 0.

- [ ] **Step 1: Write the failing tests** — copy `tests/hermes/test_review_watch.py`'s three cases against `/api/learn/latest?watch=1`, and in `test_install_commander.py` assert that `--learn-watch` creates the cron job with `LEARN_EVERY` and `--no-agent --script battlegrid_learn_watch.py --deliver local`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python -m pytest -q tests/hermes/test_learn_watch.py tests/hermes/test_install_commander.py`
Expected: FAIL with `ModuleNotFoundError` / the missing flag

- [ ] **Step 3: Implement the script and the installer flag.**

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q tests/hermes`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hermes/scripts/battlegrid_learn_watch.py hermes/install_commander.py tests/hermes
git commit -m "feat(learn): the Commander receives each new weekly scorecard once (learn watch)"
```

---

### Task 13: Verification against the real database and the 10-26 report

This is the "done looks like" check of spec 10.1. It needs the running stack; the platform parts need the user's `manager auth login`.

- [ ] **Step 1: Backfill and label from the database alone** (no platform):

```bash
docker compose exec -T api python -m manager learn backfill
docker compose exec -T api python -m manager learn label
docker compose exec -T api python -m manager learn score --now
docker compose exec -T api python -m manager learn show
```

Expected: `backfill` reports 128 new; `label` reports `graded` ≥ 100 and names the pending ones; `score --now` writes rows; `show` prints the report with at least one `agent` slice.

- [ ] **Step 2: Compare the grades with the 10-26 report.** Query `decision_outcomes` for decisions 85 to 103 (the 19 LIVE closes in `close-decisions-report.md` section 1) and write a 19-row table (decision, report grade, our grade, plan_unreliable, delta_r) to `OMEGA/docs/manager-sessions/2026-10/learn-first-build-verification.md`. Pass condition (spec 11.1): every decision the report graded from plan data matches; the six re-graded by hand (#87, #91, #95, #97, #98, #99) carry `plan_unreliable = true` or are UNCLEAR. A mismatch outside those six is a bug in Task 6: fix it there and re-run.

- [ ] **Step 3: After the user's login, run the probe and the collectors live:**

```bash
docker compose exec -T api python -m manager learn probe --out /tmp/learn-probe
docker compose exec -T api python -m manager learn collect
docker compose exec -T api python -m manager learn platform --now
```

Expected: the probe table shows every row OK with sizes under 150k chars; `collect` reports regime calls ≤ the number of positions; `platform --now` reports agents ≥ 1 and trades_new ≥ 1 within a few minutes. Record the probe table and the counts in the verification file. If any served key differed from the one a task pinned, fix the constant in that task's module, add the probe fixture to its test, and commit `fix(learn): ...`.

- [ ] **Step 4: Deploy the image** through the existing guarded chain (`gated_deploy.sh <tag> <hours> learn-loop-1`, the user's deploy rulings apply: open positions need an exchange stop), then confirm the four heartbeats:

```bash
docker compose exec -T postgres sh -c "psql -U manager -d manager -c \"select job, ok, note, at from heartbeats where job in ('outcomes','label','scorecards','platform') order by at desc limit 8\""
```

Expected: one row per job, `ok = t` (or `f` with an AUTH note while blind).

- [ ] **Step 5: Commit the verification record in OMEGA** and open the PR in battlegrid-manager (`feat/learn-loop-1` → `main`) with the verification file linked; the PR description ends with `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

---

## Self-review (done while writing)

- **Spec coverage.** 4.1 collect → Tasks 4, 5, 8, 10 (stop schedules deferred by 8.5). 4.2 label → Task 6. 4.3 score → Tasks 7, 9. 4.4 to 4.8 → later builds (spec 10). 5 → nothing per 8.4. 6 tables → Task 1 (eight of the eleven; `stop_schedules`, `experiments`, `rule_versions` are later). 7 cross-agent → Task 10 with the explorer/leaderboard/realized-trades/signal-performance reads only (11.6). 8.3 probe → Task 3. 10.1 done criteria → Task 13. 11.1 to 11.6 → Tasks 6, 8, 7, (no proposals anywhere), 9, 10 respectively.
- **Served field names** are the one thing the plan cannot pin with certainty before the probe runs; every task that reads a served payload keeps those names in module constants and Task 13 step 3 is the correction loop.
- **Type consistency.** `as_trade` (Task 4) is what Task 6 feeds to `build_positions`; `Graded` carries the `decision_outcomes` columns of Task 1; `classify`/`bootstrap_mean_ci`/`wilson` (Task 2) are used by Tasks 7 and 9 with the same signatures; `score_due`/`pull_due` take `(s, now)` in both Task 7 and Task 10; job names match between Task 11's `JOBS`, `compose.yaml` and the heartbeat assertions.
- **Review Focus** items 1 to 5 map to tests in Tasks 4, 6, 8, 10, and 4/5/10.
- **Proportion.** About 13 tasks for roughly 1,500 lines of code and tests; bodies appear only for the grading rules, the slice definitions and the Compose block.
