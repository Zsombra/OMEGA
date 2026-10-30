# Close-Rule Experiments (lever D, design step 5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give battlegrid-manager the test-and-propose stages of the learning loop for the close rules (spec 4.4 grid, 4.5, 4.6; sequencing step 5): a weekly job replays a grid of close-rule variants over every position the database holds, scores each against the rule set that runs live under a forward holdout and the spec's acceptance rule, stores every experiment win or lose in a new `experiments` table, and surfaces the accepted ones as `PROPOSE_RULE_VERSION` proposals in the weekly learning report, where the user dismisses or leaves them. Nothing applies.

**Architecture:** One new module `manager/learn/experiments.py` (pure functions: grid, holdout split, per-position deltas, the acceptance verdict; then one `run_experiments` writer) on top of the existing replay kernel (`manager/replay`), which gains a JSON rule-spec round trip and a way to build its trades from `trade_outcomes` instead of a cached file. One Docker job `experiments` (hourly check, weekly build after the scorecards), one CLI command `manager experiments`, one section in the learning report. Proposals live on the experiment row itself (`verdict`, `proposal_kind`, `status`), not in `review_proposals`, whose `review_id` is a NOT NULL foreign key to a Radar review run and whose `coin` is a Radar policy coin; a rule proposal has neither. `manager review take` is untouched: a taken rule proposal needs `rule_versions`, which is step 6.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (`Mapped` / `mapped_column`, generic `JSON`), pytest (sqlite in-memory), the replay kernel `manager/replay/{rules,simulate,history,trades}.py`, `manager/learn/stats.py` (`bootstrap_mean_ci`, `two_halves`, `MIN_SAMPLE`, `LEVEL`).

**Spec:** `docs/superpowers/specs/2026-10-27-decision-learning-loop-design.md` (this OMEGA worktree), sections 4.4 (source 1, the grid; source 3, the user's spec), 4.5, 4.6, 6 (`experiments`), 8 (decision 2), 9, 10 (step 5). The code lives in `C:\Users\rafae\Documents\GitHub\battlegrid-manager` at `436abf0` or later on `main`; work on a branch `feat/experiments-d` there. All paths below are relative to that repo unless they start with `OMEGA/`.

## Global Constraints

- **Report-only (spec 8.2, 10 step 5).** No task writes `review_proposals`, `actions`, `policy_versions` or `rule_versions`, calls a BattleGrid write tool or any LLM, or changes `manager/triage/rules.py:THRESHOLDS`, the sentinel skill or any live rule. The only new writes are rows in `experiments` and one `system_state` key.
- **The database is read READ ONLY for the replay** (`manager/replay/history.py:export_read_only`, `SET TRANSACTION READ ONLY` on Postgres); the experiment rows are written in a separate session after the replay. The CLI never calls `init_db` (`manager/commands/replay.py:_tables` says why); the job's process runs it at start like every service.
- **Acceptance rule, verbatim from spec 4.5:** "n >= 30 affected positions, positive in both halves, bootstrap 90% CI excludes 0, holds at 0.10R slippage, and does not change the picture on any single agent by more than the fleet effect." Constants: `N_AFFECTED_MIN = 30`, `LEVEL = 0.90` (from `manager/learn/stats.py`), `SLIPPAGE_R = 0.05` (`manager/replay/simulate.py`, the base run), `STRESS_SLIPPAGE_R = 0.10`.
- **Losing experiments are kept** (spec 4.5, 9): every grid row is written, verdict `ACCEPTED | REJECTED | INSUFFICIENT`. An identical spec on an identical window is never re-run.
- **Below the floors nothing is a rate:** fewer than `N_AFFECTED_MIN` affected positions, or a half with fewer than two affected positions (no interval), is `INSUFFICIENT`, never `REJECTED`.
- **Baseline = the rule set that runs live** = `manager/replay/rules.py:CURRENT_FIXED` (triage `THRESHOLDS`: loss_r 0.5, profit_r 2.0, time_stop_bars 3, tp_progress_pct 25.0, stop_atr 0.5, basis `decided`). A delta is `candidate.sim_r - baseline.sim_r` per position. The total against the actual outcomes is stored for the report, never used in the verdict.
- **Job name `experiments`** (11 characters; the limit is 22), state key `learn.experiments` (17; `system_state.key` is `String(32)`). Every job beats on every path through `_beat` / `_learn_failed` (`manager/scheduler/jobs.py:102,346`).
- **Tables use generic `sqlalchemy.JSON`, never JSONB**; JSON columns are reassigned, never mutated. A new table needs no `_ADDED_COLUMNS` entry. Timestamps `DateTime(timezone=True)`, UTC.
- **The job-set pins must move with the job:** `tests/scheduler/test_jobs.py:287` (`set(JOBS)`), `tests/scheduler/test_silence.py` (if it lists the learn jobs), `tests/test_compose.py`.
- **Tests:** sqlite in memory via `tests/learn/support.py:db()`; replay fixtures via the helpers in `tests/replay/test_replay.py` (`trade`, `metrics`, `history`, `merge`, `trades_of`, `T0`, `ENTRY 100`, `DECIDED 98`, `HARD 96`, `TP 104`); run with `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider <path>`. The full suite takes ~20 min: run it in the background once, before the merge.
- **Commit after every task** with a `feat(experiments): ...` or `test(experiments): ...` subject and the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- **The user's standing rules:** one Compose service per job; free models only (none are called); nothing binds, deploys or funds an agent; the deploy in Task 7 goes through `scripts/gated_deploy.sh` and its guards.

## Review Focus

1. **A trade the loop could not score** (`trade_outcomes.net_r` NULL: the platform served no `quality`): it must be left out of the replay with the exclusion named, never simulated with a zero R. Test in Task 2.
2. **One agent is the whole fleet** (every affected position belongs to the same agent, as the retired `c8ca25c7` was in October): the agent check must pass, since the agent's move equals the fleet effect; and an agent whose loss exceeds the fleet's gain must fail it. Tests in Task 3.
3. **A half with too few affected positions** (a candidate that fires on 31 positions, 29 of them in the first 70%): the halves check reads a two-position holdout; the verdict must be `INSUFFICIENT`, not `ACCEPTED` on a lucky pair. Test in Task 3.
4. **The same hypothesis submitted twice** (the grid and a user `--spec` file naming the same thresholds, or two runs in one week): one row, the second attempt reported as already run, so a losing experiment keeps stopping its re-proposal. Test in Task 4.
5. **The job wakes before this week's scorecards exist** (the host slept through Monday 01:00Z, scorecards build at 09:00Z, the experiments tick at 08:30Z): "not due" until the cards are built, so the report never pairs this week's experiments with last week's cards; and a mid-week `--now` run never pushes Monday's build out. Test in Task 5.

---

### Task 1: Rule specs as JSON

**Files:**
- Modify: `manager/replay/rules.py` (`TimeStop`, `RuleSet`; append `spec_hash`)
- Test: `tests/replay/test_rules_spec.py`

**Interfaces:**
- Consumes: `RuleSet`, `TimeStop`, `CURRENT_FIXED`, `timestop_v2` as they are (`manager/replay/rules.py:40-200`).
- Produces: `RuleSet.to_spec(self) -> dict`, `RuleSet.from_spec(spec: dict) -> RuleSet` (classmethod), `spec_hash(spec: dict) -> str` (16 hex characters; the `name` key is ignored, `time_stop.bars` as a map is key-sorted, floats are written as given: `json.dumps(..., sort_keys=True, separators=(",", ":"))` of the spec without `name`, sha256, first 16).

The spec shape (the only shape `from_spec` accepts; a missing key takes the dataclass default, an unknown key raises `ValueError` naming it):

```json
{"name": "loss_r_1.0", "basis": "decided", "loss_r": 1.0, "profit_r": 2.0, "tp_line": 25.0, "stop_atr": 0.5,
 "time_stop": {"bars": 3, "tighten_in_profit": false, "defer_to_decay": false}}
```

`time_stop.bars` is an integer or a `{timeframe: bars}` map (`TimeStop.bars` as a tuple of pairs, sorted by timeframe).

- [ ] **Step 1: Write the failing tests**

```python
from manager.replay import rules as R

def test_a_rule_set_round_trips_through_its_spec():
    rs = R.RuleSet("x", loss_r=1.0, time_stop=R.TimeStop(bars=(("15m", 4), ("1h", 3)), tighten_in_profit=True))
    spec = rs.to_spec()
    assert spec["time_stop"] == {"bars": {"15m": 4, "1h": 3}, "tighten_in_profit": True, "defer_to_decay": False}
    assert R.RuleSet.from_spec(spec) == rs
    assert R.RuleSet.from_spec(R.CURRENT_FIXED.to_spec()) == R.CURRENT_FIXED

def test_a_spec_with_an_unknown_key_is_refused_and_a_missing_key_takes_the_default():
    with pytest.raises(ValueError, match="slippage"):
        R.RuleSet.from_spec({"name": "x", "slippage": 0.1})
    assert R.RuleSet.from_spec({"name": "x"}) == R.RuleSet("x")

def test_the_spec_hash_ignores_the_name_and_the_key_order():
    a = R.spec_hash({"name": "a", "loss_r": 1.0, "time_stop": {"bars": {"1h": 3, "15m": 4}}})
    b = R.spec_hash({"time_stop": {"bars": {"15m": 4, "1h": 3}}, "loss_r": 1.0, "name": "b"})
    assert a == b and len(a) == 16
    assert R.spec_hash({"loss_r": 0.5}) != a
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/replay/test_rules_spec.py`
Expected: FAIL with `AttributeError: ... 'to_spec'`.

- [ ] **Step 3: Implement `to_spec`, `from_spec` and `spec_hash` in `manager/replay/rules.py`**

`from_spec` validates keys against `{"name", "basis", "loss_r", "profit_r", "tp_line", "stop_atr", "time_stop"}` and `time_stop`'s against `TimeStop`'s fields; `basis` must be `decided` or `hard`.

- [ ] **Step 4: Run the replay tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/replay`
Expected: all PASS (the existing 24 plus the 3 new).

- [ ] **Step 5: Commit**

```bash
git add manager/replay/rules.py tests/replay/test_rules_spec.py
git commit -m "feat(experiments): rule sets round-trip through a JSON spec, with a name-blind hash"
```

---

### Task 2: The replay's inputs from the database

**Files:**
- Modify: `manager/replay/trades.py` (append `trade_from_outcome`), `manager/replay/history.py` (append `positions_from_db`)
- Test: `tests/replay/test_from_db.py`

**Interfaces:**
- Consumes: `TradeOutcome` (`manager/db/models.py:715`), `Trade` / `from_row` / `COLUMNS` (`manager/replay/trades.py`), `export_read_only`, `build_positions(tables, trades, signal_log_stops=None, *, since=None) -> Built(positions, excluded)`.
- Produces:
  - `trades.trade_from_outcome(row: TradeOutcome) -> Trade | None`: None when `net_r`, `gross_r`, `entry` or `exit` is None; `opened_at` / `closed_at` as `.isoformat()`; `fees_r` 0.0 when None; `first_hit_min` as `int` when not None.
  - `history.positions_from_db(s: Session, *, since: datetime | None = None) -> tuple[Built, dict[str, str], dict[str, Trade]]`: `(built, tf_of_agent, trades)` where the tables come from `export_read_only(s)`, the trades from every `TradeOutcome` (`trade_from_outcome`; unscored rows are counted in `built.excluded[position_id] = "unscored trade (no R)"` and nowhere else), `tf_of_agent = {agent_id[:8]: strategy_timeframe}` from the exported positions exactly as `manager/commands/replay.py:62` builds it, and `signal_log_stops` is `None` (the export's `decided_stops` carry the triage stops).

- [ ] **Step 1: Write the failing tests**

```python
from tests.learn.support import db
from tests.replay.test_replay import ENTRY, T0, history, trade, trades_of

def _outcome(pid, **over):     # a TradeOutcome row from a `trade()` row; the builder writes the same columns
    ...                        # (position_id, agent_id "agent000-x", agent8 "agent000", coin "TEST", ... raw {})

def test_a_trade_outcome_becomes_the_replays_trade_and_an_unscored_one_is_none():
    t = trade_from_outcome(_outcome("p1", net_r=1.96, gross_r=2.0, fees_r=None))
    assert (t.position_id, t.agent8, t.net_r, t.fees_r, t.opened_at) == ("p1", "agent000", 1.96, 0.0, T0.isoformat())
    assert trade_from_outcome(_outcome("p2", net_r=None, gross_r=None)) is None

def test_positions_from_the_database_join_the_triage_history_and_name_the_unscored():
    Session = db()
    # seed: the triage rows / snapshot positions of `history("p1", [(1, 98.6, HARD), (2, 103.0, HARD)])` written
    # through the models export_tables reads (see tests/replay/test_replay.py::test_the_cli_reads_the_database...
    # for the seeding pattern), plus TradeOutcome rows p1 (scored) and p2 (net_r None, with its own triage rows)
    with Session() as s:
        built, tf_of_agent, trades = positions_from_db(s)
    assert [p.position_id for p in built.positions] == ["p1"]
    assert built.excluded["p2"] == "unscored trade (no R)"
    assert tf_of_agent == {"agent000": "1h"} and set(trades) == {"p1"}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/replay/test_from_db.py`
Expected: FAIL with `ImportError: cannot import name 'trade_from_outcome'`.

- [ ] **Step 3: Implement `trade_from_outcome` in `manager/replay/trades.py` and `positions_from_db` in `manager/replay/history.py`**

`positions_from_db` reads `TradeOutcome` rows in the same read-only session, after the export, before the transaction ends.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/replay`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add manager/replay/trades.py manager/replay/history.py tests/replay/test_from_db.py
git commit -m "feat(experiments): the replay builds its trades and positions from trade_outcomes, read only"
```

---

### Task 3: Grid, holdout, deltas and the verdict (pure)

**Files:**
- Create: `manager/learn/experiments.py`
- Modify: `tests/replay/test_replay.py:26-57` (`trade()` and `history()` gain keyword parameters `agent: str = "agent000"` and `opened: datetime = T0`; `history` writes `agent_id = f"{agent}-x"`, `opened_at = opened`, and its points at `opened + hours`; `trade` writes `agent` and `opened`/`opened + 9 h`; defaults keep every existing test unchanged)
- Test: `tests/learn/test_experiments.py` (part 1)

**Interfaces:**
- Consumes: `RuleSet`, `CURRENT_FIXED`, `timestop_v2(ttt, k=, tighten=, defer=)`, `TimeStop` (Task 1 shapes); `simulate.run(positions, rules, *, slippage_r) -> Summary` with `Summary.results: list[Result(position_id, coin, agent8, timeframe, actual_r, sim_r, action, reason, at, basis)]`; `stats.bootstrap_mean_ci`, `stats.LEVEL`.
- Produces, all in `manager/learn/experiments.py`:
  - `N_AFFECTED_MIN = 30`, `HOLDOUT_FRACTION = 0.3`, `STRESS_SLIPPAGE_R = 0.10`, `LEVER = "D"`, `PROPOSAL_KIND = "PROPOSE_RULE_VERSION"`.
  - `grid(ttt: dict[str, dict]) -> list[RuleSet]`: one knob at a time from `CURRENT_FIXED`, named `<knob>_<value>`: `loss_r` in (0.3, 0.75, 1.0), `profit_r` in (1.0, 1.5, 3.0), `tp_line` in (10.0, 50.0), `stop_atr` in (0.25, 0.75, 1.0), `time_stop.bars` in (2, 4, 6), plus `timestop_v2` with `k` in (1.0, 1.5, 2.0) x `(tighten, defer)` in ((False, False), (True, False), (True, True)) when `ttt` is non-empty (names from `timestop_v2`). 14 fixed-threshold variants, up to 9 time-to-target variants. `CURRENT_FIXED` itself is not in the grid.
  - `split(positions: list[Position]) -> tuple[list[Position], list[Position]]`: sorted by `opened_at`; the holdout is the last `max(round(HOLDOUT_FRACTION * n), 1)` positions (the whole list when `n < 2`), tune the rest.
  - `deltas(candidate: Summary, baseline: Summary) -> list[Delta]` with `Delta(position_id, agent8, opened_at: str, delta_r, candidate_action, candidate_reason, baseline_action, baseline_reason, affected: bool)`; `affected = (c.action, c.reason, c.at) != (b.action, b.reason, b.at)`; the two summaries are matched by `position_id` and must cover the same positions (`ValueError` otherwise); order = the candidate's.
  - `verdict(all_deltas: list[Delta], holdout_ids: set[str], stress_deltas: list[Delta]) -> Verdict` with `Verdict(verdict: str, n_affected, tune_n, holdout_n, tune_mean, holdout_mean, total_delta_r, mean_delta_r, ci_low, ci_high, stress_total, stress_ci_low, stress_ci_high, per_agent: dict[str, float], agent_max_abs, failed: list[str])`:
    - the affected deltas only; `n_affected < N_AFFECTED_MIN` or either half with fewer than 2 affected → `INSUFFICIENT` (`failed = ["n_affected"]` or `["halves"]`), the numbers that exist still filled;
    - checks, in this order, every failing one named in `failed`: `halves` (tune mean > 0 and holdout mean > 0), `ci` (`bootstrap_mean_ci(affected deltas)` low > 0), `stress` (the same on the stress deltas' affected set: low > 0), `agent` (`max(abs(v) for v in per_agent.values()) <= total_delta_r`, per-agent totals over affected deltas);
    - `ACCEPTED` when `failed` is empty, else `REJECTED`.

- [ ] **Step 1: Add the fleet helper to `tests/learn/test_experiments.py` and write the failing tests**

```python
from tests.replay.test_replay import HARD, T0, history, merge, trade, trades_of
from manager.replay.history import build_positions
from manager.replay import rules as R
from manager.replay.simulate import run
from manager.learn import experiments as X

def recovering(pid, *, agent="agent000", opened=T0):
    """At hour 1 the mark is 98.6 (r -0.7 on the decided stop 98) with the direction gone: the live rules close
    (THESIS_GATE_FALSE, -0.79 after fees and slippage); a loss line at -1.0 holds, and the trade hit the target."""
    return (history(pid, [(1, 98.6, HARD), (2, 103.0, HARD)], agent=agent, opened=opened),
            trade(pid, exit_price=104.0, net_r=1.96, close_reason="TAKE_PROFIT", plan_state="TARGET_FIRST",
                  plan_r=2.0, agent=agent, opened=opened))

def failing(pid, *, agent="agent000", opened=T0):
    """The same first step, then the stop: the live rules save 0.25R by closing early."""
    return (history(pid, [(1, 98.6, HARD)], agent=agent, opened=opened),
            trade(pid, exit_price=98.0, net_r=-1.04, agent=agent, opened=opened))

def untouched(pid, *, agent="agent000", opened=T0):
    """One in-profit step (mark 102, r +1.0, direction intact): no rule in the grid fires; the trade hit the target."""
    return (history(pid, [(1, 102.0, HARD)], dq=True, agent=agent, opened=opened),
            trade(pid, exit_price=104.0, net_r=1.96, close_reason="TAKE_PROFIT", plan_state="TARGET_FIRST",
                  plan_r=2.0, agent=agent, opened=opened))

KINDS = {"recover": recovering, "fail": failing, "hold": untouched}

def fleet(seq, candidate=None):
    """`seq` = [(kind, agent)] in opening order, one position per hour from T0, ids `<kind><i>`: returns
    (positions, baseline summary, candidate summary) with baseline CURRENT_FIXED and candidate LOSS_1 by default."""
    ...   # merge(*tables), trades_of(*rows), build_positions(...).positions, run(...) twice
def mixed(n_recover, n_fail, agent="agent000"):
    """Interleaved: recover, fail, recover, ... until both counts are spent (the plain fleet of most tests)."""
    ...
LOSS_1 = R.RuleSet("loss_r_1.0", loss_r=1.0)

def test_the_grid_moves_one_knob_at_a_time_from_the_live_rules():
    sets = X.grid({})
    assert len(sets) == 14 and len({s.name for s in sets}) == 14
    assert all(s.basis == "decided" for s in sets)
    for s in sets:
        moved = [k for k in ("loss_r", "profit_r", "tp_line", "stop_atr") if getattr(s, k) != getattr(R.CURRENT_FIXED, k)]
        moved += ["time_stop"] if s.time_stop != R.CURRENT_FIXED.time_stop else []
        assert len(moved) == 1, s.name
    with_ttt = X.grid({"1h": {"n": 10, "median_min": 120.0, "median_bars": 2.0}})
    assert len(with_ttt) == 23 and "timestop_v2" in {s.name for s in with_ttt}

def _verdict(positions, base, cand, candidate=LOSS_1):
    stress = run(positions, candidate, slippage_r=X.STRESS_SLIPPAGE_R)
    return X.verdict(X.deltas(cand, base), {p.position_id for p in X.split(positions)[1]}, X.deltas(stress, base))

def test_the_holdout_is_the_last_thirty_percent_by_opening():
    positions, _, _ = mixed(7, 3)
    tune, hold = X.split(positions)
    assert len(hold) == 3 and len(tune) == 7
    assert max(p.opened_at for p in tune) < min(p.opened_at for p in hold)

def test_deltas_are_candidate_minus_baseline_and_name_the_affected():
    positions, base, cand = fleet([("recover", "agent000"), ("fail", "agent000"), ("hold", "agent000")])
    d = {x.position_id: x for x in X.deltas(cand, base)}
    assert d["recover0"].delta_r == pytest.approx(1.96 + 0.79) and d["recover0"].affected
    assert d["fail1"].delta_r == pytest.approx(-0.25) and d["fail1"].affected
    assert d["hold2"].delta_r == 0.0 and not d["hold2"].affected
    assert (d["recover0"].baseline_reason, d["recover0"].candidate_action) == ("THESIS_GATE_FALSE", "HOLD")

def test_thirty_affected_positive_in_both_halves_is_accepted():
    positions, base, cand = mixed(25, 5)
    v = _verdict(positions, base, cand)
    assert v.verdict == "ACCEPTED" and v.failed == [] and v.n_affected == 30
    assert v.holdout_n == 9 and v.tune_n == 21 and v.ci_low > 0 and v.stress_ci_low > 0
    assert v.total_delta_r == pytest.approx(25 * 2.75 - 5 * 0.25)              # +67.50
    assert v.per_agent == {"agent000": pytest.approx(67.5)} and v.agent_max_abs == pytest.approx(67.5)

def test_fewer_than_thirty_affected_is_insufficient_not_rejected():
    positions, base, cand = mixed(20, 5)
    v = _verdict(positions, base, cand)
    assert v.verdict == "INSUFFICIENT" and v.failed == ["n_affected"] and v.n_affected == 25

def test_a_holdout_with_one_affected_position_is_insufficient():
    # 44 positions, holdout = round(0.3 * 44) = 13: the tune set is 29 affected then 2 untouched; the holdout is 1
    # affected then 12 untouched. 30 affected in all, one of them in the holdout: no interval on that side.
    seq = [("recover", "agent000")] * 29 + [("hold", "agent000")] * 2 + [("recover", "agent000")] + [("hold", "agent000")] * 12
    v = _verdict(*fleet(seq))
    assert v.n_affected == 30 and v.verdict == "INSUFFICIENT" and v.failed == ["halves"]

def test_a_candidate_that_loses_the_second_half_is_rejected_with_the_check_named():
    # 25 recovering first, then 10 failing: the tune half is positive, the holdout (the last 11) negative
    v = _verdict(*fleet([("recover", "agent000")] * 25 + [("fail", "agent000")] * 10))
    assert v.verdict == "REJECTED" and "halves" in v.failed and v.holdout_mean < 0 < v.tune_mean

def test_an_agent_whose_move_exceeds_the_fleet_effect_fails_the_agent_check():
    # agent A 20 recovering (+55.0), agent B 20 failing (-5.0), agent C 60 failing (-15.0): fleet +35.0 (mean +0.35,
    # the interval above zero on 100 positions), but agent A moved by 55.0 > 35.0. Interleaved A, B, C, C, C, ...
    seq = []
    for i in range(20):
        seq += [("recover", "agentA"), ("fail", "agentB"), ("fail", "agentC"), ("fail", "agentC"), ("fail", "agentC")]
    v = _verdict(*fleet(seq))
    assert v.total_delta_r == pytest.approx(35.0) and v.per_agent["agentA"] == pytest.approx(55.0)
    assert v.verdict == "REJECTED" and v.failed == ["agent"]

def test_one_agent_that_is_the_whole_fleet_passes_the_agent_check():
    v = _verdict(*mixed(25, 5, agent="agentA"))
    assert v.agent_max_abs == pytest.approx(v.total_delta_r) and "agent" not in v.failed
```

Build `recovering` first and confirm by hand (`run([pos], R.CURRENT_FIXED)`) that the baseline's result is `CLOSE THESIS_GATE_FALSE` with `sim_r == -0.79` and `LOSS_1`'s is `HOLD` with `sim_r == 1.96`; adjust the mark if `r_at` differs (r = (mark - 100) / (100 - 98) on the decided stop). The agent names must be at most 8 characters: `Result.agent8` is `agent_id[:8]` and `history` writes `agent_id = f"{agent}-x"`.

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/learn/test_experiments.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'manager.learn.experiments'`.

- [ ] **Step 3: Implement `grid`, `split`, `deltas`, `verdict` and the two dataclasses in `manager/learn/experiments.py`**

The module docstring states the acceptance rule verbatim from spec 4.5 and the baseline. The halves are tune vs holdout by `holdout_ids` (two means computed directly), not `stats.two_halves`, which splits a list down the middle.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/learn/test_experiments.py tests/replay`
Expected: PASS (the replay suite still green with the helpers' new defaults).

- [ ] **Step 5: Commit**

```bash
git add manager/learn/experiments.py tests/learn/test_experiments.py tests/replay/test_replay.py
git commit -m "feat(experiments): the close-rule grid, the forward holdout and the acceptance verdict"
```

---

### Task 4: The `experiments` table and the writer

**Files:**
- Modify: `manager/db/models.py` (append `Experiment` after `PlatformTrade`), `manager/learn/experiments.py` (append `run_experiments`, `experiments_due`, `latest_built_at`, `dismiss`)
- Test: `tests/learn/test_experiments.py` (part 2)

**Interfaces:**
- Consumes: Task 3's functions; `positions_from_db` (Task 2); `time_to_target(trades, tf_of_agent)` (`manager/replay/rules.py:162`); `get_state` / `set_state` (`manager/audit/ledger.py`); `score.latest_built_at(s)` and `score.week_start(now)` (`manager/learn/score.py:184,189`).
- Produces:
  - ORM `Experiment`, `__tablename__ = "experiments"`, `UniqueConstraint("spec_hash", "window_key", name="uq_experiments_spec_window")`, columns (`?` nullable; `DT` = `DateTime(timezone=True)`; `S(n)` = `String(n)`): `id` PK; `built_at DT` idx; `lever S(8)`; `name S(64)`; `spec_hash S(16)`; `window_key S(48)`; `rule_spec dict` JSON; `baseline_spec dict` JSON; `proposed_by S(16)` (`grid | user`); `n_positions Integer`; `n_affected Integer`; `tune_n Integer`; `holdout_n Integer`; `cut_at DT?` (the holdout's first opening); `tune_mean Float?`; `holdout_mean Float?`; `total_delta_r Float?`; `mean_delta_r Float?`; `ci_low Float?`; `ci_high Float?`; `stress_total Float?`; `stress_ci_low Float?`; `stress_ci_high Float?`; `vs_actual_total Float?` (candidate total sim R minus the actual total); `per_agent dict` JSON; `failed list` JSON; `results list` JSON (one `{position_id, agent8, delta_r, candidate_action, candidate_reason, baseline_action, baseline_reason}` per affected position); `verdict S(12)` (`ACCEPTED | REJECTED | INSUFFICIENT`); `proposal_kind S(24)?` (`PROPOSE_RULE_VERSION` on ACCEPTED, else NULL); `status S(12)` (`OPEN` on ACCEPTED, `NONE` otherwise, then `DISMISSED | SUPERSEDED`); `settled_at DT?`; `settled_by S(32)?`; `note Text?`.
  - `STATE_KEY = "learn.experiments"`; `latest_built_at(s) -> datetime | None` (from the state's `builtAt`).
  - `window_key(positions) -> str`: `f"{first:%Y-%m-%d}..{last:%Y-%m-%d}/{n}"` over `opened_at`.
  - `run_experiments(s: Session, *, now: datetime, candidates: list[RuleSet] | None = None, proposed_by: str = "grid", since: datetime | None = None, slippage_r: float = SLIPPAGE_R) -> dict`: `{"built_at", "n_positions", "window", "run": int, "skipped": int, "accepted": int, "ids": [...]}`. Reads `positions_from_db(s, since=since)`; `candidates` default `grid(time_to_target(trades, tf_of_agent))`; runs the baseline once at `slippage_r` and once at `STRESS_SLIPPAGE_R`; for each candidate whose `(spec_hash, window_key)` row exists → `skipped`, else runs it at both slippages, writes the row with `built_at = now`; an ACCEPTED row supersedes every earlier `OPEN` row of the same `spec_hash` (status `SUPERSEDED`, `settled_at = now`, `settled_by = "experiments"`); sets the state `{"builtAt": now.isoformat(), "window": ..., "n": ...}`; `s.commit()` is the caller's (like `write_scorecards`). The function must not run inside the read-only export: `positions_from_db` opens and closes its own transaction first (`s.rollback()` after it, before any write).
  - `experiments_due(s, now) -> bool`: `week_start(now) <= now`, no experiments build at or after `week_start(now)`, AND `score.latest_built_at(s)` is not None and `>= week_start(now)` (the cards of this week exist).
  - `dismiss(s, experiment_id: int, *, note: str, now: datetime) -> Experiment`: `OPEN` → `DISMISSED` with `settled_by = "user"`; any other status raises `ValueError("experiment N is <status>, not OPEN")`.

- [ ] **Step 1: Write the failing tests**

```python
def _seed(Session, seq):  # writes fleet(seq)'s tables and trades through the models (as Task 2's seed)
    ...

def test_the_run_writes_every_grid_row_and_accepts_the_loss_line():
    Session = db(); _seed(Session, MIXED_25_5)      # the sequence `mixed(25, 5)` builds
    with Session() as s:
        out = X.run_experiments(s, now=NOW, candidates=[LOSS_1, R.RuleSet("loss_r_0.3", loss_r=0.3)])
        s.commit()
        rows = s.scalars(select(Experiment).order_by(Experiment.id)).all()
    assert out["run"] == 2 and out["skipped"] == 0 and out["accepted"] == 1
    a, b = rows
    assert (a.name, a.verdict, a.status, a.proposal_kind) == ("loss_r_1.0", "ACCEPTED", "OPEN", "PROPOSE_RULE_VERSION")
    assert a.rule_spec == LOSS_1.to_spec() and a.baseline_spec == R.CURRENT_FIXED.to_spec()
    assert a.window_key == f"{T0:%Y-%m-%d}..{T0 + timedelta(hours=29):%Y-%m-%d}/30" and a.lever == "D"
    assert len(a.results) == 30 and a.failed == [] and a.n_positions == 30
    # loss_r 0.3 fires on the same step as the live 0.5 (r -0.7 is below both): nothing is affected
    assert (b.verdict, b.status, b.proposal_kind, b.n_affected) == ("INSUFFICIENT", "NONE", None, 0)
    with Session() as s:
        assert X.latest_built_at(s) == NOW

def test_the_same_spec_on_the_same_window_is_skipped_and_kept():
    ... second run with the same candidates -> out["skipped"] == 2, still 2 rows

def test_a_new_acceptance_supersedes_the_open_row_of_the_same_spec():
    ... run on 30, add 10 more positions, run again -> the old row SUPERSEDED (settled_by "experiments"), new OPEN

def test_dismiss_settles_an_open_proposal_once():
    ... dismiss(id, note="not now") -> DISMISSED, settled_by "user", note; a second dismiss raises ValueError

def test_experiments_are_due_once_a_week_after_the_scorecards():
    Session = db()
    monday_0130 = datetime(2026, 11, 2, 1, 30, tzinfo=UTC)
    with Session() as s:
        assert X.experiments_due(s, monday_0130) is False           # no cards this week yet
        set_state(s, "learn.scorecards", {"builtAt": datetime(2026, 11, 2, 9, 0, tzinfo=UTC).isoformat()})
        assert X.experiments_due(s, monday_0130) is False           # the tick before the cards: not due
        assert X.experiments_due(s, datetime(2026, 11, 2, 9, 30, tzinfo=UTC)) is True
        set_state(s, X.STATE_KEY, {"builtAt": datetime(2026, 11, 2, 9, 30, tzinfo=UTC).isoformat()})
        assert X.experiments_due(s, datetime(2026, 11, 5, 12, 0, tzinfo=UTC)) is False
        assert X.experiments_due(s, datetime(2026, 11, 9, 1, 0, tzinfo=UTC)) is False   # next Monday: cards first
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/learn/test_experiments.py`
Expected: FAIL with `ImportError: cannot import name 'Experiment'`.

- [ ] **Step 3: Implement the model and the four functions**

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/learn/test_experiments.py tests/learn/test_models.py tests/db`
Expected: PASS (if `tests/learn/test_models.py` or `tests/db` pins the table list, add `experiments`).

- [ ] **Step 5: Commit**

```bash
git add manager/db/models.py manager/learn/experiments.py tests/learn/test_experiments.py
git commit -m "feat(experiments): the experiments table, the weekly writer, supersession and dismissal"
```

---

### Task 5: The job, the Compose service and `manager experiments`

**Files:**
- Modify: `manager/scheduler/jobs.py` (append `job_experiments` after `job_platform`), `manager/commands/run.py:15-27` (`JOBS["experiments"]`), `compose.yaml:147` (service `experiments` after `platform`)
- Create: `manager/commands/experiments.py`
- Modify: `tests/scheduler/test_jobs.py:287` (the job set), `tests/test_compose.py` (if it pins the service list), `tests/scheduler/test_silence.py` (if it pins the learn jobs)
- Test: `tests/scheduler/test_jobs.py` (two tests appended), `tests/commands/test_experiments.py`

**Interfaces:**
- Consumes: `run_experiments`, `experiments_due`, `dismiss`, `latest_built_at` (Task 4); `RuleSet.from_spec` (Task 1); `_beat`, `_learn_failed`, `JobContext` (`manager/scheduler/jobs.py`); `register(name, help, add, run)` (`manager/commands/__init__.py`, as `manager/commands/learn.py:230` uses it); `render_experiments` (Task 6; until then `show` prints the rows' `verdict` lines, replaced in Task 6).
- Produces:
  - `job_experiments(ctx: JobContext) -> None`: `experiments_due` → `run_experiments(s, now=now)`, `s.commit()`, beat `"{run} run, {skipped} skipped, {accepted} accepted over {n_positions} positions"`; not due → `"not due"`; any exception → `_learn_failed(ctx, "experiments", e)`.
  - Compose: `experiments:   # learn (5): weekly close-rule experiments after the scorecards (Monday); report-only` with `command: ["python", "-m", "manager", "run", "experiments", "--every", "3600"]`, the `*manager` anchor, no `profiles` (like `scorecards`).
  - CLI `manager experiments <action>` with `action` in `run | show | dismiss`; `--now` (run: force when not due); `--spec FILE` (run: a JSON rule spec, `proposed_by "user"`, run instead of the grid); `--since ISO`; `--slippage FLOAT` (default `SLIPPAGE_R`); `--id INT` and `--note TEXT` (dismiss, both required); `--all` (show: every build, not only the latest). Exit 0; 2 on a refused spec (`ValueError` → `refused: ...`) or a dismiss of a non-OPEN row.

- [ ] **Step 1: Write the failing tests**

```python
# tests/scheduler/test_jobs.py (append; `ctx(platform, settings)` and `settings` fixtures exist at the top)
def test_every_background_job_is_runnable_as_its_own_process():   # the existing pin gains "experiments"
    ...

async def test_the_experiments_job_beats_not_due_before_the_cards_and_runs_after_them(settings, monkeypatch):
    c = ctx(FakePlatform({}), settings)
    await job_experiments(c)
    beat = _last_beat(c, "experiments")
    assert beat.ok is True and beat.note == "not due"
    monkeypatch.setattr("manager.learn.experiments.experiments_due", lambda s, now: True)
    monkeypatch.setattr("manager.learn.experiments.run_experiments",
                        lambda s, *, now: {"run": 3, "skipped": 1, "accepted": 1, "n_positions": 40})
    await job_experiments(c)
    assert _last_beat(c, "experiments").note == "3 run, 1 skipped, 1 accepted over 40 positions"

async def test_the_experiments_job_beats_not_ok_on_a_failure(settings, monkeypatch):
    ... run_experiments raises RuntimeError("boom") -> beat ok False, note "boom"
```

```python
# tests/commands/test_experiments.py
def test_run_with_a_user_spec_writes_one_row_proposed_by_the_user(tmp_path, capsys, monkeypatch):
    ... monkeypatch `_factory` to the sqlite db seeded as Task 4; write {"name": "loss_r_1.0", "loss_r": 1.0} to a file;
    ... main(["experiments", "run", "--now", "--spec", str(path)]) == 0; the row's proposed_by == "user"
def test_a_spec_with_an_unknown_key_is_refused_with_exit_2(...)
def test_dismiss_needs_an_open_row(...)
```

Also update `tests/test_compose.py` with `test_the_experiments_service_runs_hourly_without_a_profile_after_platform` in the style of `test_the_review_service_is_under_the_live_profile_and_runs_every_900_s` (`tests/test_compose.py:67`).

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/scheduler/test_jobs.py tests/commands/test_experiments.py tests/test_compose.py`
Expected: FAIL (`experiments` missing from `JOBS`; `job_experiments` undefined; the service absent).

- [ ] **Step 3: Implement the job, the registry entry, the Compose service and the command**

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/scheduler tests/commands/test_experiments.py tests/test_compose.py tests/learn`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add manager/scheduler/jobs.py manager/commands/run.py manager/commands/experiments.py compose.yaml tests/scheduler/test_jobs.py tests/commands/test_experiments.py tests/test_compose.py tests/scheduler/test_silence.py
git commit -m "feat(experiments): the weekly experiments job, its Compose service and manager experiments run|show|dismiss"
```

---

### Task 6: The report section

**Files:**
- Modify: `manager/learn/views.py` (`_markdown`, `learn_view`; append `render_experiments`)
- Test: `tests/learn/test_views.py` (append)

**Interfaces:**
- Consumes: `Experiment`, `latest_built_at` from `manager/learn/experiments.py` (Task 4); `_section(title, lines)` and `utc_label` (`manager/learn/views.py`).
- Produces:
  - `_experiment_lines(s: Session) -> list[str]`: the rows of the latest experiments build (`experiments.latest_built_at`), ACCEPTED first (then REJECTED, then INSUFFICIENT), within a verdict by `ci_low` descending (None last); one line each, exactly: `- **{name}** {verdict}{status}: n={n_affected} affected of {n_positions}, Δ{total_delta_r:+.2f}R (mean {mean_delta_r:+.3f}, CI [{ci_low:+.2f}, {ci_high:+.2f}]), halves {tune_mean:+.2f}/{holdout_mean:+.2f}, stress Δ{stress_total:+.2f}R; vs actual {vs_actual_total:+.2f}R` with `{status}` = ` (OPEN, #{id}: \`manager experiments dismiss --id {id} --note ...\`)` on an OPEN row, ` (dismissed)` / ` (superseded)` otherwise, nothing on NONE; a failed check list appended as ` — failed: halves, agent` when non-empty; None numbers printed as `n/a`.
  - `_markdown` appends `_section("### Close-rule experiments (lever D, vs the live rules)", lines)` after the Decisions section (only on the branch where scorecards exist: experiments are never built before the cards, Task 4), with a first line `"Baseline: current_fixed (loss_r 0.5, profit_r 2.0, time stop 3 bars, tp line 25 %, stop 0.5 ATR); accepted = n ≥ 30 affected, positive in both halves, 90 % CI above 0, holds at 0.10R slippage, no agent moved more than the fleet. Nothing applies: an OPEN row is a proposal for step 6 (rule_versions)."`, or, when no experiments build exists, the single line `"No experiments built yet (the first build follows the first Monday scorecards)."`.
  - `learn_view` gains `"experimentsBuiltAt": iso_z(...) | None` and `"openProposals": int`.
  - `render_experiments(s: Session, *, now: datetime, all_builds: bool = False) -> str`: `"## Close-rule experiments built {label}"`, the same lines; `all_builds` lists every build newest first with its own heading.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_report_carries_the_experiments_accepted_first_with_the_dismiss_command():
    ... seed one ACCEPTED OPEN (id 1), one REJECTED, one INSUFFICIENT at built_at B; scorecards built at B too
    text = render_scorecards(s, now=NOW)
    i = text.index("### Close-rule experiments")
    lines = [l for l in text[i:].splitlines() if l.startswith("- **")]
    assert lines[0].startswith("- **loss_r_1.0** ACCEPTED (OPEN, #1: `manager experiments dismiss --id 1 --note ...`): n=30 affected of 30, Δ+67.50R")
    assert "— failed: halves" in lines[1] and lines[2].split("**")[2].startswith(" INSUFFICIENT")

def test_the_report_without_experiments_says_so_and_the_view_counts_open_proposals():
    assert "No experiments built yet" in render_scorecards(s, now=NOW)
    assert learn_view(s, NOW)["openProposals"] == 0 and learn_view(s, NOW)["experimentsBuiltAt"] is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/learn/test_views.py`
Expected: FAIL (`### Close-rule experiments` not in the text).

- [ ] **Step 3: Implement the lines, the section, the view keys and `render_experiments`; point `manager experiments show` at `render_experiments`**

- [ ] **Step 4: Run the tests to verify they pass**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests/learn tests/api tests/commands/test_experiments.py`
Expected: PASS (`/api/learn/latest` serves the new keys through `learn_view` unchanged; if `tests/api` pins the view's keys, add the two).

- [ ] **Step 5: Commit**

```bash
git add manager/learn/views.py manager/commands/experiments.py tests/learn/test_views.py
git commit -m "feat(experiments): the close-rule experiments section of the weekly learning report"
```

---

### Task 7: Verification on the real database, the record and the deploy

**Files:**
- Create: `docs/status/2026-11-0X-experiments-first-run.md` (the date of the run)
- Modify: `docs/phase-0/runbook.md` (the learn jobs table gains `experiments`; the CLI list gains `manager experiments`)
- OMEGA: `docs/manager-sessions/2026-11/experiments-verification.md` (the verification record, OMEGA branch `claude/hermes-decision-learning-caa1c4`)

No new code. Every number in the record is read from the command that produced it, with its stored UTC instant (`date -u` right before writing a time).

- [ ] **Step 1: Run the full suite in the background on the branch**

Run: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests > /tmp/suite.log 2>&1` (background, ~20 min)
Expected: the last line `NNNN passed, 5 skipped` with no `failed`; quote it in the record.

- [ ] **Step 2: Merge and build the image**

```bash
git checkout main && git merge --ff-only feat/experiments-d && git push
docker build -t battlegrid-manager:main-$(git rev-parse --short HEAD) .
```

- [ ] **Step 3: Deploy under the guards**

The CLI never calls `init_db`, so the `experiments` table exists only after a service start has run `init_db`'s `create_all`: the deploy comes before any CLI run against the live database.

```bash
bash scripts/gated_deploy.sh main-$(git rev-parse --short HEAD) 24
```
Expected: `DEPLOY DONE` in the deploy log; `docker compose ps` lists `experiments` running; its first beat `not due` (the week's scorecards exist but the experiments build does not: on a Monday after 01:00Z with the cards built, the job makes the week's build itself and beats the counts line instead); `manager contract status` unchanged (no platform read was added: the job reads the database only).

- [ ] **Step 4: Dry-run against the live database from a one-off container, after the deploy**

The DB-only learn steps ran from a one-off container on 10-29 (the image carries no tests dir; the host's Python is not on the Compose network). The run writes `experiments` rows and one state key only, after a read-only replay; it is the first week's build, made by hand unless the job already made it:

```bash
docker run --rm --network battlegrid-manager_default --env-file .env -e DATABASE_URL=<the compose DATABASE_URL> battlegrid-manager:main-<sha> python -m manager experiments run --now
```
Expected: `experiments: N run, 0 skipped, A accepted over P positions (window ...)` (or `N skipped` when the job built the week already). Record P against `trade_outcomes` (138 rows on 10-30, minus the unscored) and the excluded reasons. Then the same container with `python -m manager experiments show`; keep the text in the record. The 10-26 replay said `loss_r` moved +3.28R over 114 positions: say whether the `loss_r_*` rows agree in sign, and what every verdict is (expect INSUFFICIENT on most: a one-knob change fires on few positions). A second `run --now` must print `N skipped`.

- [ ] **Step 5: Verify the deploy live**

Run: `docker compose exec -T postgres psql -U manager -d manager -At -F ' | ' -c "select job, at, ok, note from heartbeats where job='experiments' order by at desc limit 3"`
Expected: an ok beat on the new image. `curl -s -H "Authorization: Bearer $MANAGER_TOKEN" http://127.0.0.1:8790/api/learn/latest | python -c "import json,sys; v=json.load(sys.stdin); print(v['experimentsBuiltAt'], v['openProposals'])"` prints Step 4's build and the count `show` printed.

- [ ] **Step 6: Write the records and commit both repos**

The status record: what ran, the table of verdicts, the excluded positions, the deploy instants, and the two follow-ups the plan leaves (step 6 `rule_versions` + `take`; step 8 the analyst). The OMEGA record: the same from the design's side (spec sections covered, decisions made in this plan, what step 6 needs).

```bash
git add docs/status/2026-11-0X-experiments-first-run.md docs/phase-0/runbook.md
git commit -m "Record: close-rule experiments first run and deploy"
```

---

## Self-review (done while writing)

**Spec coverage.** 4.4 source 1 (grid) → Task 3; source 3 (the user's spec) → Task 5's `--spec`; source 2 (the analyst) is step 8, not here. 4.5 rule specs from the DB → Tasks 1, 2, 4 (`rule_spec` stored, `from_spec` runs it); forward holdout → Task 3 `split`; acceptance rule → Task 3 `verdict`, every clause mapped to a named check; "writes `experiments` with the full result, win or lose" → Task 4 (`results`, `failed`, every verdict written); lever B and A/C are steps 7 and later. 4.6 → the `PROPOSE_RULE_VERSION` proposal is the ACCEPTED row (`proposal_kind`, `status OPEN`), reported in the weekly report (Task 6, the Commander already delivers that report through the learn watch), dismissable (Tasks 4, 5); `take` deferred to step 6 with the reason in the header. 4.7, 4.8 → step 6. Section 6's `experiments` row ("lever, rule_spec, window, results, verdict, proposed_by") → Task 4's columns, every one present. 8.2 report-only → Global Constraints. 9 → the losing rows are kept; MIN_SAMPLE is a floor below `N_AFFECTED_MIN`.

**Step scan.** Every test step carries its assertions with the spec's values (30, 0.90, 0.10, 0.3); every code step carries the signature and file. Task 3's fleet arithmetic (+2.75 / −0.25 per position) is derived from the kernel's constants and must be checked by hand in Step 1 before the counts are trusted; the agent-check test states its own arithmetic.

**Type consistency.** `Delta` and `Verdict` fields are named once (Task 3) and used by name in Task 4's columns; `Summary.results` / `Result` fields match `manager/replay/simulate.py:31`; `experiments_due` and `latest_built_at` match `score.py`'s shapes; `run_experiments`'s return keys are the ones Task 5's beat formats.

**Review Focus.** Each of the five has its test in the task named.

**Proportion.** About a third of the length of the first-build plan for seven tasks; the code blocks are tests and signatures, not bodies.
