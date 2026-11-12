# Rule Versions (lever D, design step 6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the lever D loop end to end (spec 4.6, 4.7, 4.8, 5; sequencing step 6): the close-rule thresholds move from a code constant into a versioned `rule_versions` table with meta-bounds, an ACCEPTED experiment can be taken by the user into a new version that applies when inside bounds and waits for the user when outside, the live triage reads the version in force on every tick, the sentinel's skill text and the dossier carry those thresholds instead of quoting stale numbers, an AMBER dossier gains an evidence-only scorecard section, and an hourly job verifies each applied version forward and proposes a revert when the observed effect leaves the experiment's confidence interval.

**Architecture:** One new table `rule_versions` modelled on `policy_versions` (a revision is a new row; the previous APPLIED row is flipped to SUPERSEDED, never edited) and one new module `manager/learn/rule_versions.py` that owns bounds, the spec-to-thresholds mapping, `current`, `init_version`, `propose`, `apply_version`, `take_experiment` and `verify_forward`. Rule proposals keep living on the `experiments` row (lever D's decision: `review_proposals` is keyed to a Radar review run), so the user's take is `manager experiments take`, beside the existing `dismiss`; versions get their own `manager rules` command. The triage tick reads `current_thresholds(s)` once in its top session and passes the dict to `triage(...)`, which already records `metrics["thresholds"]` on every row. The experiment grid's baseline becomes the version in force, and an apply supersedes every standing proposal because their deltas were measured against the old baseline. The sentinel skill is not rendered from the table (the image has no `hermes/`, and Hermes reads the file from the host repo): it stops quoting numbers and reads them from the dossier's `triage.metrics.thresholds`, which the triage poll also shows.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (`Mapped` / `mapped_column`, generic `JSON`), pytest (sqlite in memory), the replay kernel `manager/replay/{rules,simulate,history,trades}.py`, `manager/learn/experiments.py` (`deltas`, `split`, `verdict`, `window_key`), `manager/risk/policy.py` as the pattern for bounds and versions, `manager/audit/ledger.py` (`record`, `get_state`, `set_state`).

**Spec:** `docs/superpowers/specs/2026-10-27-decision-learning-loop-design.md` (this OMEGA worktree), sections 4.6, 4.7, 4.8, 5 (the `scorecard` dossier section), 6 (`rule_versions`), 8 (decision 2: apply autonomy is decided when there is a verified proposal; this plan builds the gate, the user's take), 9, 10 (step 6). Lever D's plan `docs/superpowers/plans/2026-10-31-close-rule-experiments.md` and its records (`battlegrid-manager/docs/status/2026-10-30-experiments-first-run.md`) describe what this plan builds on. The code lives in `C:\Users\rafae\Documents\GitHub\battlegrid-manager` at `ea26ac5` or later on `main`; work on a branch `feat/rule-versions-6` there. All paths below are relative to that repo unless they start with `OMEGA/`.

## Global Constraints

- **The user's take is the only gate that applies a rule (spec 4.6, 4.7).** No job, no tick and no API route creates a version with status APPLIED. `init_version`, `take_experiment`, `propose` and `apply_version` run only from the CLI (`manager rules`, `manager experiments take`), on the user's word. A version outside the meta-bounds is NEEDS_USER until `manager rules apply <id>`.
- **Nothing here touches the platform or a model:** no BattleGrid write tool, no `actions` row, no LLM call, no `agent_config` change. A rule version changes what the manager's own triage decides; the sentinel skill's wording changes; nothing else.
- **Thresholds keep triage's key names and types:** `{"loss_r": float, "profit_r": float, "time_stop_bars": int, "tp_progress_pct": float, "stop_atr": float}` (`manager/triage/rules.py:54`, `THRESHOLDS`). `RuleSet.tp_line` is `tp_progress_pct`; `RuleSet.time_stop.bars` (an int) is `time_stop_bars`. A spec whose `basis` is not `"decided"`, whose `time_stop.bars` is a map, or whose `tighten_in_profit` / `defer_to_decay` is true has no live counterpart and cannot become a version.
- **Meta-bounds (inclusive, the builder's call from the grid's own range and the 10-26 rulings):** `loss_r` 0.25–1.0, `profit_r` 1.0–4.0, `time_stop_bars` 1–8, `tp_progress_pct` 10.0–50.0, `stop_atr` 0.25–1.0. Every one-knob grid variant of `manager/learn/experiments.py:53-55` sits inside them.
- **`THRESHOLDS` stays the code default and the fallback** (`tests/triage/test_rules.py:567,581` pin it): with no APPLIED row, `current_thresholds` returns it and `metrics["rule_version"]` is `None`; the tick never fails for want of a version.
- **Acceptance rule and floors are lever D's, unchanged:** `N_AFFECTED_MIN = 30`, `LEVEL = 0.90`, `SLIPPAGE_R = 0.05`, `STRESS_SLIPPAGE_R = 0.10`. The forward check uses `N_VERIFY = 20` affected positions (`MIN_SAMPLE`) and `VERIFY_MIN_DAYS = 7` (the shadow-to-live gate's shape, spec 4.8).
- **Evidence floor for the dossier section:** `EVIDENCE_MIN = 5` decisions in a cell before a mean delta is shown; counts are always shown; below one decision the section is absent and the dossier hashes as today.
- **Tables use generic `sqlalchemy.JSON`, never JSONB**; JSON columns are reassigned, never mutated; timestamps `DateTime(timezone=True)`, UTC. A new table needs no `_ADDED_COLUMNS` entry; a column added to a deployed table does (`manager/db/session.py:36`, `_ADDED_COLUMNS`), and `experiments`, `decision_outcomes` are deployed.
- **Job name `rules`** (5 characters), state key `learn.rules` (11). Every job beats on every path (`manager/scheduler/jobs.py:102` `_beat`, `:346` `_learn_failed`). One Compose service per job (the user's standing rule). Pins to move with a new job: `manager/commands/run.py:23-27` (`JOBS`), `tests/scheduler/test_jobs.py` (`set(JOBS)`), `tests/scheduler/test_silence.py` if it lists jobs, `tests/test_compose.py`, `docs/phase-0/runbook.md:20-24`.
- **The replay reads the database READ ONLY** (`manager/replay/history.py:export_read_only`); `verify_forward` writes its result in a separate session after the replay, as `run_experiments` does.
- **Ledger events** for every state change: `rules.init`, `rules.applied`, `rules.needs_user`, `rules.taken`, `rules.take_refused`, `rules.verified`, `rules.revert_proposed` (`manager/audit/ledger.py:record`).
- **Tests:** sqlite in memory via `tests/learn/support.py:db()`; replay fixtures via `tests/replay/test_replay.py` helpers; run with `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider <path>`. The full suite takes ~28 min: run it in the background once, before the merge. Files written from Python on Windows must be LF (`git ls-files --eol`; `sed -i 's/\r$//'`).
- **Commit after every task** with a `feat(rules): ...` / `test(rules): ...` / `docs(rules): ...` subject and the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- **The deploy (Task 8) goes through `scripts/gated_deploy.sh` and its guards**; `manager rules init` runs once after it, from the api container, on the user's word already given for this plan.

## Review Focus

1. **A taken proposal the live triage cannot express** (a `timestop_v2_*` row with per-timeframe bars, or a hand spec with `basis: hard`): the take must be refused naming the knob, the row must stay OPEN, no version row written. Test in Task 3.
2. **A tick with no rule version** (a fresh database, or the hour between the deploy and `rules init`): triage runs on `THRESHOLDS`, every row's `metrics["rule_version"]` is `None`, nothing raises. Test in Task 2.
3. **A version applied while proposals stand** (two OPEN rows from the Monday build, one taken): the other becomes SUPERSEDED with the note naming the version, and the next canonical build on the same positions re-runs every candidate under the new baseline instead of skipping them as already judged. Tests in Task 2.
4. **A version with no prediction** (version 1 from `rules init`, a user's `rules propose`): the forward check reads NONE and never proposes a revert; a version that fails the check proposes a revert exactly once, never again on the next hour. Tests in Task 4.
5. **An evidence cell below the floor** (3 decisions on this agent and reason): the section shows the counts and no mean, never a rate; with no decisions at all the section is absent and the dossier's sha256 equals today's. Tests in Task 6.

---

### Task 1: The `rule_versions` table and the version module

**Files:**
- Create: `manager/learn/rule_versions.py`
- Modify: `manager/db/models.py` (append `RuleVersion` after `Experiment`, `:941-988`)
- Modify: `tests/learn/test_models.py:6-7` (`EXPECTED` gains `"rule_versions"`)
- Test: `tests/learn/test_rule_versions.py`

**Interfaces:**
- Consumes: `manager/triage/rules.py:THRESHOLDS`; `manager/replay/rules.py:RuleSet, TimeStop, spec_hash`; `manager/risk/policy.py` as the pattern (`META_BOUNDS`, `inside_bounds`, `propose`, `apply_version`, `_current_applied_row`); `manager/audit/ledger.py:record`.
- Produces (every later task relies on these names):
  - Model `RuleVersion` (table `rule_versions`): `id` pk; `created_at` DateTime tz, index; `status` String(12), index (`APPLIED | NEEDS_USER | SUPERSEDED`); `thresholds` JSON (the five keys above); `outside_bounds` JSON default list (strings like `"loss_r 1.5 outside 0.25–1.0"`); `experiment_id` ForeignKey("experiments.id") nullable, index; `proposed_by` String(32) (`"init" | "user" | "take" | "verify"`); `rationale` Text; `applied_at` DateTime tz nullable; `superseded_by` ForeignKey("rule_versions.id") nullable; `predicted_delta_r` Float nullable (the experiment's `mean_delta_r`); `predicted_ci_low`, `predicted_ci_high` Float nullable; `observed_delta_r` Float nullable; `n_observed` Integer nullable; `verify_status` String(8) (`NONE | PENDING | HOLDS | OUTSIDE`), default `NONE`; `verified_at` DateTime tz nullable; `revert_version_id` ForeignKey("rule_versions.id") nullable.
  - Module constants: `KEYS = ("loss_r", "profit_r", "time_stop_bars", "tp_progress_pct", "stop_atr")`, `META_BOUNDS: dict[str, tuple[float, float]]` with the values in Global Constraints, `APPLIED, NEEDS_USER, SUPERSEDED`, `VERIFY_NONE, VERIFY_PENDING, VERIFY_HOLDS, VERIFY_OUTSIDE`, `N_VERIFY = 20`, `VERIFY_MIN_DAYS = 7`, `STATE_KEY = "learn.rules"`.
  - `class RuleError(ValueError)`.
  - `to_thresholds(spec: dict) -> dict`: a `RuleSet.to_spec()` dict to the five-key dict; raises `RuleError` naming the first knob with no live counterpart (`basis`, `time_stop.bars` as a map, `tighten_in_profit`, `defer_to_decay`). Unknown keys raise through `RuleSet.from_spec`.
  - `to_rule_set(thresholds: dict, name: str) -> RuleSet` (basis `"decided"`, `tp_line=tp_progress_pct`, `TimeStop(bars=time_stop_bars)`), the inverse used for the grid's baseline and the forward replay.
  - `validate(thresholds: dict) -> dict`: exactly `KEYS`, ints for `time_stop_bars` (a float with no fraction is accepted and cast), floats elsewhere; raises `RuleError`.
  - `inside_bounds(thresholds: dict) -> tuple[str, ...]` (empty = inside).
  - `current(s: Session) -> RuleVersion | None` (newest APPLIED by id), `current_thresholds(s) -> dict` (a copy of `current(s).thresholds`, or of `THRESHOLDS`).
  - `init_version(s, *, by: str, now: datetime) -> RuleVersion`: refuses (`RuleError`) when any row exists; writes version 1 APPLIED from `THRESHOLDS`, `proposed_by="init"`, rationale `"the code constant THRESHOLDS at <sha of to_rule_set(...).to_spec()>"`, ledger `rules.init`; flushes, does not commit.
  - `propose(s, thresholds: dict, *, rationale: str, by: str, now: datetime, experiment: Experiment | None = None, proposed_by: str = "user") -> RuleVersion`: validates, computes `outside_bounds`; status `APPLIED` when empty else `NEEDS_USER`; an APPLIED row sets `applied_at=now` and flips the previous APPLIED row to SUPERSEDED with `superseded_by`; copies `predicted_*` from `experiment` when given (`mean_delta_r`, `ci_low`, `ci_high`) and sets `verify_status=VERIFY_PENDING` for a row with a prediction, else `VERIFY_NONE`; ledger `rules.applied` / `rules.needs_user`; flushes, does not commit. A thresholds dict equal to the current version's is refused (`RuleError("already in force as version N")`).
  - `apply_version(s, version_id: int, *, by: str, now: datetime, note: str | None = None) -> RuleVersion`: the user's word on a NEEDS_USER row whatever its bounds; refuses an APPLIED or SUPERSEDED row; supersedes the previous APPLIED row; ledger `rules.applied`.
  - `supersede_open_experiments(s, version: RuleVersion, *, now) -> int`: every `Experiment` with `status == "OPEN"` and `id != version.experiment_id` becomes SUPERSEDED, `settled_at=now`, `settled_by="rules"`, note `f"baseline moved to rule version {version.id}"`; returns the count. Called by `propose` and `apply_version` when the result is APPLIED.

- [ ] **Step 1: Write the failing tests** in `tests/learn/test_rule_versions.py` (use `tests/learn/support.py:db()`; build an `Experiment` row with the fields `tests/learn/test_experiments.py` uses):

```python
def test_to_thresholds_maps_a_grid_spec_and_refuses_what_triage_cannot_run():
    spec = replace(CURRENT_FIXED, name="loss_r_0.3", loss_r=0.3).to_spec()
    assert to_thresholds(spec) == {"loss_r": 0.3, "profit_r": 2.0, "time_stop_bars": 3, "tp_progress_pct": 25.0, "stop_atr": 0.5}
    for bad, knob in ((timestop_v2(...)[0].to_spec(), "time_stop.bars"), ({**spec, "basis": "hard"}, "basis"),
                      ({**spec, "time_stop": {**spec["time_stop"], "tighten_in_profit": True}}, "tighten_in_profit")):
        with pytest.raises(RuleError, match=knob): to_thresholds(bad)

def test_to_rule_set_round_trips_the_live_thresholds():
    assert to_rule_set(THRESHOLDS, "live").to_spec() == {**CURRENT_FIXED.to_spec(), "name": "live"}

def test_init_writes_version_1_from_the_constant_and_only_once():
    # init -> status APPLIED, thresholds == THRESHOLDS, proposed_by "init", verify_status NONE; a second init raises RuleError
    # current_thresholds(s) == THRESHOLDS before init (and rule version None), == version 1's after

def test_propose_inside_bounds_applies_and_supersedes_the_current_version():
    # v2 = propose({**THRESHOLDS, "loss_r": 0.3}, ...) -> APPLIED, applied_at set; v1.status SUPERSEDED, v1.superseded_by == v2.id; current(s).id == v2.id

def test_propose_outside_bounds_is_needs_user_until_applied_on_the_users_word():
    # propose({**THRESHOLDS, "loss_r": 1.5}) -> NEEDS_USER, outside_bounds == ["loss_r 1.5 outside 0.25–1.0"], current unchanged;
    # apply_version(id) -> APPLIED and current; apply_version again -> RuleError

def test_propose_the_thresholds_in_force_is_refused():
    # propose(THRESHOLDS) after init -> RuleError match "already in force as version 1"

def test_an_applied_version_supersedes_every_other_open_experiment():
    # two OPEN experiments a, b; propose(..., experiment=a) -> b SUPERSEDED with note "baseline moved to rule version 2",
    # a untouched (its status is the take's business, Task 3); predicted_delta_r == a.mean_delta_r, verify_status PENDING
```

- [ ] **Step 2: Run them**: `pytest tests/learn/test_rule_versions.py -v` → FAIL (`ImportError: manager.learn.rule_versions`).
- [ ] **Step 3: Add `RuleVersion` to `manager/db/models.py`** with the columns above and a docstring saying a revision is a new row and which later tasks read `verify_*`; add `"rule_versions"` to `EXPECTED` in `tests/learn/test_models.py`.
- [ ] **Step 4: Write `manager/learn/rule_versions.py`** with the interfaces above. `inside_bounds` formats like `policy.inside_bounds` (`f"{key} {value:g} outside {lo:g}–{hi:g}"`).
- [ ] **Step 5: Run** `pytest tests/learn/test_rule_versions.py tests/learn/test_models.py tests/db -q` → PASS.
- [ ] **Step 6: Commit** `feat(rules): rule_versions table and the version module (bounds, init, propose, apply)`.

---

### Task 2: The tick and the grid read the version in force

**Files:**
- Modify: `manager/triage/cycle.py:93-111` (read once), `:203-212` (`_triage_position` gains `thresholds: dict | None = None`, `rule_version: int | None = None`), `:261` (`triage(Inputs(...), thresholds=...)`), and where `row.metrics` is written: `metrics["rule_version"] = rule_version`
- Modify: `manager/learn/experiments.py:98` (`grid(ttt, baseline: RuleSet)`), `:211` (`window_key(..., rule_version: int | None = None)`), `:251` (`run_experiments(..., baseline: RuleSet | None = None)`)
- Modify: `manager/learn/views.py:69-73` (the Baseline line reads the version in force, not `CURRENT_FIXED`)
- Test: `tests/triage/test_cycle.py`, `tests/learn/test_experiments.py`, `tests/learn/test_views.py`

**Interfaces:**
- Consumes: Task 1 `current`, `current_thresholds`, `to_rule_set`.
- Produces: `window_key(positions, slippage_r=SLIPPAGE_R, *, canonical=True, rule_version=None) -> str` = `<first>..<last>/<n>/s<slippage>[/r<id>][/hand]` (`/r<id>` only when a version exists, before `/hand`; `is_hand` and `_experiment_origin` keep working because `/hand` stays the tail; 48 characters hold it: a key is at most 41). `run_experiments` reads `current(s)` when `baseline` is None: the baseline `RuleSet` is `to_rule_set(version.thresholds, f"live r{id}")` and `rule_version=version.id`; with no version it is `CURRENT_FIXED` and the key has no `/r` segment, exactly as today. `grid(ttt, baseline)` builds its one-knob variants with `replace(baseline, ...)`. `baseline_spec` on each row is the baseline's spec (already stored). The report's Baseline line prints `"Baseline: rule version N (loss_r …)"` or `"Baseline: THRESHOLDS (no rule version yet) (…)"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/triage/test_cycle.py (beside the existing tick tests; same fakes)
def test_the_tick_runs_on_the_applied_rule_version_and_records_it():
    # init_version then propose loss_r 0.3 (APPLIED) -> run one tick with a position at r_now -0.4R and
    # direction_qualifies False: with loss_r 0.3 the row carries THESIS_GATE_FALSE; metrics["thresholds"]["loss_r"] == 0.3;
    # metrics["rule_version"] == 2
def test_the_tick_without_any_rule_version_runs_on_the_constant():
    # no rows -> metrics["thresholds"] == THRESHOLDS and metrics["rule_version"] is None (Review Focus 2)

# tests/learn/test_experiments.py
def test_the_window_key_carries_the_rule_version_before_the_hand_tail():
    # window_key(positions, rule_version=2) endswith "/30/s0.05/r2"; canonical=False -> "/30/s0.05/r2/hand"; is_hand() true
def test_the_grid_and_baseline_follow_the_version_in_force_and_a_new_version_reruns_the_window():
    # init (v1): run_experiments -> rows keyed /r1, baseline_spec == CURRENT_FIXED spec, loss_r_0.3 row written
    # propose loss_r 0.3 (v2, APPLIED): run_experiments on the same positions -> every candidate RUN again (not skipped),
    # keyed /r2, baseline_spec loss_r == 0.3, and the grid has no "loss_r_0.3" candidate (it equals the baseline) (Review Focus 3)

# tests/learn/test_views.py
def test_the_baseline_line_names_the_rule_version_in_force():
    # after init -> "Baseline: rule version 1 (loss_r 0.5, ..."; before -> "Baseline: THRESHOLDS (no rule version yet)"
```

- [ ] **Step 2: Run them** → FAIL (`window_key() got an unexpected keyword 'rule_version'`, metrics lacks `rule_version`).
- [ ] **Step 3: Implement.** In `cycle.py` read `version = rule_versions.current(s)` in the top session next to `guard`; `thresholds = dict(version.thresholds) if version else None`; pass both down; call `triage(Inputs(...), thresholds=thresholds or THRESHOLDS)`; write `metrics["rule_version"]` right after `metrics["thresholds"]` is set (it is `rules.py:233`, so set it on the verdict's metrics in `cycle.py` before the row is written). In `experiments.py` thread `baseline`; `grid` skips a variant whose spec hash equals the baseline's. In `views.py` compute the Baseline line in a function `baseline_line(s) -> str` (the constant `EXPERIMENTS_BASELINE` becomes a format with the acceptance sentence unchanged).
- [ ] **Step 4: Run** `pytest tests/triage tests/learn tests/replay -q` → PASS (the lever D tests keep passing with no version: no `/r` segment).
- [ ] **Step 5: Commit** `feat(rules): the triage tick and the experiment grid read the rule version in force`.

---

### Task 3: Taking a proposal, and the `rules` CLI

**Files:**
- Modify: `manager/learn/rule_versions.py` (append `take_experiment`)
- Modify: `manager/learn/experiments.py:340` (`dismiss` unchanged; add `TAKEN = "TAKEN"` to the status constants and the `Experiment` docstring)
- Modify: `manager/commands/experiments.py` (action `take`)
- Create: `manager/commands/rules.py` (`register("rules", ...)` as `manager/commands/policy.py:135` does; actions `init | show | list | apply | propose`)
- Modify: `manager/commands/__init__.py` or wherever `policy` is registered (follow the pattern)
- Test: `tests/learn/test_rule_versions.py`, `tests/commands/test_rules.py`, `tests/commands/test_experiments.py`

**Interfaces:**
- Consumes: Task 1; `manager/commands/policy.py` (`_run` calls `init_db`, prints `policy version N: STATUS — outside: ...`, exit 2 on refusal); `manager/commands/experiments.py:45-56` (which must not call `init_db`; `take` is allowed to, as `review`/`policy` do, since it writes a table the service may not have created yet).
- Produces: `take_experiment(s, experiment_id: int, *, by: str, note: str, now: datetime) -> RuleVersion`: the row must exist, be `status == "OPEN"` and `verdict == "ACCEPTED"` (else `RuleError` naming the state); `thresholds = to_thresholds(e.rule_spec)` (a `RuleError` here is re-raised after ledger `rules.take_refused` with the knob; the row stays OPEN, Review Focus 1); then `propose(s, thresholds, rationale=f"experiment {e.id} {e.name}: Δ{total}R over {n_affected} affected, CI [..]; {note}", by=by, now=now, experiment=e, proposed_by="take")`; the experiment row becomes `status=TAKEN, settled_at=now, settled_by=f"cli:{by}"[:32], note=note`; ledger `rules.taken` with `{experimentId, versionId, status}`; flushes, does not commit. CLI: `manager experiments take --id N --note "..." [--by cli]` prints `rule version M: APPLIED` or `rule version M: NEEDS_USER — outside: loss_r 1.5 outside 0.25–1.0; apply with: manager rules apply M --note ...`, exit 2 with `refused: ...` on `RuleError`. `manager rules init [--by]`, `manager rules show` (the version in force: id, thresholds, bounds, provenance, verify line; and every NEEDS_USER row with its apply command), `manager rules list [--limit 20]`, `manager rules apply <id> --note [--by]`, `manager rules propose --key loss_r=0.3 [--key ...] --rationale "..." [--by]` (keys merge over the current thresholds; `proposed_by="user"`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/learn/test_rule_versions.py
def test_taking_an_accepted_experiment_inside_bounds_applies_a_version_and_settles_the_row():
    # OPEN ACCEPTED loss_r_0.3 -> take -> version APPLIED, experiment_id == row id, predicted_delta_r == row.mean_delta_r;
    # row.status == "TAKEN", settled_by == "cli:cli", note kept; current_thresholds(s)["loss_r"] == 0.3
def test_taking_a_timestop_v2_row_is_refused_naming_the_knob_and_leaves_it_open():
    # OPEN ACCEPTED row whose rule_spec has time_stop.bars as a map -> RuleError match "time_stop.bars"; row still OPEN; no RuleVersion row
def test_taking_a_row_that_is_not_open_or_not_accepted_is_refused():
    # DISMISSED row -> RuleError match "DISMISSED"; an OPEN row whose verdict was edited to REJECTED -> RuleError match "REJECTED"
def test_taking_an_out_of_bounds_hand_spec_waits_for_the_user():
    # OPEN ACCEPTED hand row loss_r 1.5 (hand runs can accept anything) -> NEEDS_USER; row TAKEN; current unchanged; apply -> current

# tests/commands/test_rules.py (file-backed sqlite under tmp_path, monkeypatch get_settings as tests/commands/test_policy.py does)
def test_cli_rules_init_show_and_propose_out_of_bounds_then_apply():
    # init prints "rule version 1: APPLIED"; show names loss_r 0.5 and the bounds; propose --key loss_r=1.5 prints NEEDS_USER with
    # the apply command; apply 2 --note ok prints APPLIED; show names version 2
# tests/commands/test_experiments.py
def test_cli_experiments_take_prints_the_version_and_refuses_a_second_take():
    # take --id N --note why -> "rule version 2: APPLIED"; again -> exit 2 "refused: experiment N is TAKEN"
```

- [ ] **Step 2: Run them** → FAIL.
- [ ] **Step 3: Implement** `take_experiment`, the `take` action, and `manager/commands/rules.py`. `show` renders through one function `render_show(s) -> str` reused by Task 5's report.
- [ ] **Step 4: Run** `pytest tests/learn tests/commands -q` → PASS.
- [ ] **Step 5: Commit** `feat(rules): manager experiments take and the manager rules CLI (init, show, list, apply, propose)`.

---

### Task 4: Verify forward, the `rules` job and its service

**Files:**
- Modify: `manager/learn/rule_versions.py` (append `verify_forward`)
- Modify: `manager/scheduler/jobs.py` (append `job_rules` after `job_experiments`, `:444-464`)
- Modify: `manager/commands/run.py:14-27` (import, `JOBS["rules"]`)
- Modify: `compose.yaml` (service `rules` after `experiments`, `--every 3600`), `docs/phase-0/runbook.md:20-24`
- Modify: `tests/scheduler/test_jobs.py` (`set(JOBS)`), `tests/scheduler/test_silence.py` (if it lists jobs), `tests/test_compose.py`
- Test: `tests/learn/test_rule_versions.py`, `tests/learn/test_jobs.py`

**Interfaces:**
- Consumes: Task 1 (`current`, `to_rule_set`, `propose`), `manager/learn/experiments.py:deltas` (`deltas(candidate: Summary, baseline: Summary, *, opened)`), `manager/replay/history.positions_from_db(s, *, since)` and the replay run `run_experiments` uses to get a `Summary` per rule set (`manager/replay/simulate`; copy the call), `manager/learn/stats.py:bootstrap_mean_ci`.
- Produces: `verify_forward(s, *, now: datetime) -> dict`: for the version in force `v`: if `v.verify_status == NONE` (no prediction) → `{"version": v.id, "status": "NONE"}`; if `v.verify_status == OUTSIDE` already → return it unchanged (a revert is proposed once, Review Focus 4); else replay the positions opened at or after `v.applied_at` under `to_rule_set(v.thresholds)` (candidate) and under the superseded version's thresholds (the row whose `superseded_by == v.id`; baseline), `affected = [d for d in deltas(...) if d.delta_r != 0]`; `n_observed = len(affected)`, `observed_delta_r = mean` (None below 2); writes `n_observed`, `observed_delta_r`, `verified_at=now`; status stays `PENDING` while `n_observed < N_VERIFY` or `now - applied_at < VERIFY_MIN_DAYS`; else `HOLDS` when `predicted_ci_low <= observed_delta_r <= predicted_ci_high`, else `OUTSIDE`, in which case `propose(s, baseline thresholds, rationale=f"forward check of version {v.id}: observed {obs:+.3f}R over {n} affected, outside the predicted [{lo:+.2f}, {hi:+.2f}]", by="verify", now=now, proposed_by="verify")` is written with status forced to `NEEDS_USER` even inside bounds (a revert is always the user's word: pass `force_needs_user=True`, a new keyword on `propose`), `v.revert_version_id` set, ledger `rules.revert_proposed`; ledger `rules.verified` on every status change; `set_state(STATE_KEY, {"at", "version", "status", "nObserved"})`. Returns `{"version", "status", "nObserved", "observed"}`. The job: `job_rules(ctx)` runs `verify_forward` hourly, commits, beats `rules` with `f"version {id} {status} n={n}"` or `"no rule version"`; `_learn_failed(ctx, "rules", e)` on error.

- [ ] **Step 1: Write the failing tests**

```python
def test_verify_forward_on_a_version_without_prediction_is_none_and_proposes_nothing()      # Review Focus 4
def test_verify_forward_is_pending_until_the_floor_and_the_week_have_passed()
    # v2 taken from an experiment (ci -0.1..+0.3); 10 affected forward positions after applied_at -> PENDING, n_observed 10
def test_verify_forward_holds_inside_the_interval_and_proposes_a_revert_once_outside():
    # 20 forward positions, applied_at 8 days ago: observed +0.1 -> HOLDS; observed -0.5 -> OUTSIDE, one NEEDS_USER row with
    # v1's thresholds, proposed_by "verify", v2.revert_version_id == its id; a second verify_forward writes no second row
# tests/learn/test_jobs.py
def test_job_rules_beats_on_every_path():   # no version -> "no rule version"; with a version -> "version 1 NONE n=0"
```

- [ ] **Step 2: Run them** → FAIL.
- [ ] **Step 3: Implement** `verify_forward`, `job_rules`, the `JOBS` entry, the compose block (`rules:  # learn (6): hourly forward check of the rule version in force; proposes a revert, never applies one`), the runbook row; move the pins.
- [ ] **Step 4: Run** `pytest tests/learn tests/scheduler tests/test_compose.py -q` → PASS.
- [ ] **Step 5: Commit** `feat(rules): verify forward (hourly job rules), a revert proposal on an effect outside the predicted interval`.

---

### Task 5: The report, the API and the triage poll

**Files:**
- Modify: `manager/learn/views.py` (`_experiment_status` take command; new section `### Rule versions (lever D, step 6)`; `learn_view` keys)
- Modify: `manager/api/app.py` (`GET /api/rules/current`; `/api/triage/pending` carries `rules`)
- Modify: `manager/triage/views.py:225` (`pending_view` adds `"rules": {"version": id|None, "thresholds": {...}}`)
- Modify: `hermes/scripts/battlegrid_triage_poll.py:219` (`render` adds one line `Rules in force: version N — loss_r 0.5R, profit_r 2R, time stop 3 bars, tp line 25 %, stop 0.5 ATR` after the stale notice, before the dossier lines; `version none (THRESHOLDS)` when None)
- Test: `tests/learn/test_views.py`, `tests/api/...` (the existing learn/triage API tests), `tests/hermes/test_triage_poll.py` (or where `render` is tested)

**Interfaces:**
- Consumes: Tasks 1–4; `render_show` (Task 3).
- Produces: in the report, an OPEN row's status reads `(OPEN, #N: manager experiments take --id N --note ... | dismiss --id N --note ...)`; a TAKEN row `(taken -> rule version M)`. The new section, after the experiments section: the version in force (id, thresholds, applied_at, provenance `from experiment N` / `init` / `user`), its forward line (`forward check: PENDING n=7 of 20, 3 of 7 days` / `HOLDS: observed +0.12R (n=24) inside [−0.05, +0.31]` / `OUTSIDE: ... revert proposed as version K: manager rules apply K --note ...`), and every NEEDS_USER row with its apply command. `learn_view` gains `ruleVersion` (id or None), `ruleVerify` (status), `needsUser` (count). `GET /api/rules/current` returns `{"version", "status", "thresholds", "bounds", "appliedAt", "verify": {...}}` (THRESHOLDS with `version: None` before init).

- [ ] **Step 1: Write the failing tests** (names): `test_the_report_offers_take_and_dismiss_on_an_open_row_and_names_the_version_on_a_taken_one`, `test_the_rule_versions_section_shows_the_version_in_force_and_needs_user_rows`, `test_learn_view_carries_rule_version_keys`, `test_api_rules_current_before_and_after_init`, `test_pending_view_and_the_poll_show_the_rules_in_force`.
- [ ] **Step 2: Run them** → FAIL.
- [ ] **Step 3: Implement.** Keep `EXPERIMENTS_*` constants; add `RULES_TITLE = "### Rule versions (lever D, step 6)"`.
- [ ] **Step 4: Run** `pytest tests/learn tests/api tests/triage tests/hermes -q` → PASS.
- [ ] **Step 5: Commit** `feat(rules): report section, /api/rules/current, rules in force on the triage poll`.

---

### Task 6: The dossier's evidence section

**Files:**
- Modify: `manager/db/models.py:795-816` (`DecisionOutcome` gains `agent_id` String(36) nullable, index; `bars_in_trade` Integer nullable), `manager/db/session.py:36` (`_ADDED_COLUMNS` entries for both), `:98` (`_ADDED_INDEXES` for `ix_decision_outcomes_agent_id`)
- Modify: `manager/learn/label.py:83-152` (`grade_decision` returns the two new values; `label_decisions` writes them)
- Create: `manager/learn/evidence.py`
- Modify: `manager/dossier/build.py:53` (`build_document(..., scorecard: dict | None = None)`; key `scorecard` written only when given), `manager/triage/cycle.py:257-259` (gather it beside `read_close_history`), `:356` (pass it)
- Modify: the `manager learn` command (`manager/commands/learn.py`): action `relabel-meta` (fills `agent_id` and `bars_in_trade` on existing `decision_outcomes` rows from the replay history, prints the count)
- Test: `tests/learn/test_label.py`, `tests/learn/test_evidence.py`, `tests/dossier/test_build.py`, `tests/triage/test_cycle.py`, `tests/db/test_init_db_locks.py`

**Interfaces:**
- Consumes: `manager/replay/history.Position` (`agent_id`, `steps`), `rules.bars_in_trade(pos, step)` as `label.py` already uses, `DecisionOutcome.grade` / `delta_r` / `reason`.
- Produces: `EVIDENCE_MIN = 5`, `BANDS = ((1, 2), (3, 5), (6, None))` (bars 1–2, 3–5, 6 and more; a `None`/0 bars decision counts in no band), `band_of(bars: int | None) -> str | None` (`"1-2" | "3-5" | "6+"`); `evidence_for(s, *, agent_id: str, reasons: list[str], bars_in_trade: int | None) -> dict | None`: for each reason in `reasons` (the dossier's) and this agent, the CLOSE decisions (`outcome == "CLOSE"`) graded GOOD/BAD/UNCLEAR: `{"agent": {"n", "good", "bad", "unclear", "mean_delta_r"}, "band": {"band": "1-2", "n", ..., "mean_delta_r"}}` per reason under `"reasons": {reason: {...}}`, `mean_delta_r` None below `EVIDENCE_MIN`; plus `"note": "evidence only: CLOSE decisions on this agent and reason, graded against the hold counterfactual; weigh, not obey"`, `"floor": EVIDENCE_MIN`; returns None when no reason has a decision (Review Focus 5). The dossier key `scorecard` holds exactly this dict.

- [ ] **Step 1: Write the failing tests**

```python
def test_label_writes_the_agent_and_the_bars_of_each_decision()           # tests/learn/test_label.py
def test_evidence_counts_below_the_floor_and_means_above_it():             # tests/learn/test_evidence.py
    # 3 CLOSE decisions on agent A reason STOP_PROXIMITY bars 2 (2 GOOD 1 BAD) -> band "1-2" n 3, good 2, bad 1, mean_delta_r None;
    # 6 on bars 4 with deltas -> band "3-5" mean == statistics.mean; "agent" n 9; another agent's rows never counted
def test_evidence_is_none_without_decisions()
def test_build_document_writes_the_scorecard_only_when_given_and_hashes_as_before_without_it()   # tests/dossier/test_build.py
def test_the_tick_attaches_the_evidence_to_an_amber_dossier()              # tests/triage/test_cycle.py
def test_added_columns_cover_decision_outcomes_agent_and_bars()            # tests/db/test_init_db_locks.py
```

- [ ] **Step 2: Run them** → FAIL.
- [ ] **Step 3: Implement.** In `cycle.py` the evidence is read in the existing `with session_factory() as s:` block and passed as `scorecard=`; only an AMBER verdict builds a document, so no GREEN/RED path pays the query. `relabel-meta` reuses `label_decisions`' pairing of decisions to steps (factor the pairing into `decision_meta(pos, rec) -> tuple[str, int | None]`).
- [ ] **Step 4: Run** `pytest tests/learn tests/dossier tests/triage tests/db -q` → PASS.
- [ ] **Step 5: Commit** `feat(rules): evidence-only scorecard section in AMBER dossiers (agent x reason x bars band)`.

---

### Task 7: The sentinel skill reads the thresholds instead of quoting them

**Files:**
- Modify: `hermes/skills/battlegrid-sentinel/SKILL.md:96-124` (the reason definitions), plus one new paragraph after the reasons: `## The scorecard section (evidence, not instruction)`
- Modify: `tests/hermes/test_persona_files.py:92-135`
- Test: `tests/hermes/test_persona_files.py`

**Interfaces:**
- Consumes: the dossier's `triage.metrics.thresholds` (already present on every dossier, `manager/triage/rules.py:233`) and `triage.metrics.rule_version` (Task 2); the `scorecard` key (Task 6); the poll's `Rules in force` line (Task 5).
- Produces: wording. THESIS_GATE_FALSE reads `r_now <= -loss_r` with `loss_r` named as `triage.metrics.thresholds.loss_r` ("0.5R at the time of writing; the dossier's value is the one in force"); MOMENTUM_STALL `profit_r`; TIME_STOP `time_stop_bars` and `tp_progress_pct`; STOP_PROXIMITY `stop_atr`. The TIME_STOP zones (`r_now <= 0`, `> 0`, `direction_qualifies`) are unchanged and the pinned phrases of `test_sentinel_skill_makes_a_pure_time_stop_deterministic` stay intact. The new paragraph: the `scorecard` key, when present, is the manager's own graded history for this agent and reason; cite it in the rationale when it bears on the choice; it never fixes an outcome and never overrides the pure TIME_STOP rule; below the floor it shows counts only, which are not a rate.

- [ ] **Step 1: Write the failing tests**

```python
def test_sentinel_skill_quotes_no_threshold_number_in_the_reason_definitions():
    section = text[text.index("## What each triage reason means"):text.index("**EVIDENCE_UNDETERMINED**")]
    for literal in ("-0.5R", "beyond 2R", "more than 3 bars", "under 25%", "0.5 ATR"): assert literal not in section
    for key in ("thresholds.loss_r", "thresholds.profit_r", "thresholds.time_stop_bars", "thresholds.tp_progress_pct", "thresholds.stop_atr"): assert key in section
def test_sentinel_skill_treats_the_scorecard_as_evidence_only():
    assert "## The scorecard section" in text and "weigh" in text and "never fixes an outcome" in text
```

- [ ] **Step 2: Run them** → FAIL; **Step 3:** edit the skill; **Step 4:** `pytest tests/hermes -q` → PASS (the existing pins included).
- [ ] **Step 5: Commit** `docs(rules): the sentinel skill reads the thresholds from the dossier and treats the scorecard as evidence`.

---

### Task 8: Whole-branch review, the suite, the deploy, `rules init`, the records

**Files:**
- Create: `docs/status/2026-11-XX-rule-versions.md` (the manager's record; date = the deploy day)
- Modify: `OMEGA/docs/manager-sessions/2026-10/experiments-verification.md` ("What is not done": step 6 off the list) or a new `OMEGA/docs/manager-sessions/2026-11/rule-versions-verification.md`

- [ ] **Step 1:** Full suite in the background: `.venv/Scripts/python -m pytest -q --no-header -p no:cacheprovider tests` → `N passed, 6 skipped`, exit 0 (N ≥ 5737 + the new tests).
- [ ] **Step 2:** Fast-forward `feat/rule-versions-6` to `main`, push. `docker ps` + `manager contract status` first (writes open, acked). Build `docker build -t battlegrid-manager:main-<sha> .`; `bash scripts/gated_deploy.sh main-<sha> 24`; DEPLOY DONE with all 21 services on the new image, restarts 0 (the `rules` container created new; `init_db` on service start creates `rule_versions` and adds the two `decision_outcomes` columns).
- [ ] **Step 3:** `docker compose exec -T api python -m manager rules init --by "user (plan 2026-10-31-rule-versions)"` → `rule version 1: APPLIED`; `manager rules show` prints THRESHOLDS; `manager learn relabel-meta` prints the count of filled rows (expect ~114).
- [ ] **Step 4:** Live checks (quote stored instants, `date -u` before writing any time): the next triage tick's row carries `metrics.rule_version == 1`; `GET /api/rules/current` reads version 1; `GET /api/triage/pending` carries `rules`; the poll script's render (run on the host against the API) shows `Rules in force: version 1 ...`; `rules` job beat `version 1 NONE n=0`; `experiments` beat `not due`; `/api/learn/latest` has `ruleVersion: 1`; one AMBER dossier, when one exists, carries `scorecard` (or note that none was built).
- [ ] **Step 5:** Records: the manager status doc (what landed, the deploy instants, the live checks, the rulings), the OMEGA verification record, memory. Commit and push both repos.

---

## Self-review (done while writing)

- **Spec coverage.** 4.6 (an accepted experiment becomes a takeable PROPOSE_RULE_VERSION with its evidence attached; the user takes or dismisses): Tasks 3, 5. 4.7 (thresholds in `rule_versions` with meta-bounds, inside applies / outside NEEDS_USER; skill text and rules cannot drift): Tasks 1, 2, 7. 4.8 (`predicted_delta_r`, `observed_delta_r`, `n_observed`; revert proposed outside the CI after N): Task 4. 5 (the evidence-only `scorecard` section; weigh, not obey): Tasks 6, 7. 6 (`rule_versions` grain and purpose): Task 1. 8.2 (apply autonomy left to the user's take): Global Constraints. Protection changes, pair changes and strategy revisions of 4.7 are other levers' apply paths (B, C, A) and are not step 6.
- **Spec deviation, stated:** "sentinel skill text rendered from `rule_versions`" is implemented as the skill reading the thresholds the dossier and the poll carry, not as a rendered file: the container image has no `hermes/`, Hermes reads the file from the host checkout, and a rendered copy would be stale the moment a version applies. The drift the spec guards against (a prompt quoting a number the rules no longer use) is closed by Task 7's test that the skill quotes no threshold number.
- **Step scan.** Every code step names its file, signature and the values it pins; bodies are left to the implementer except the forward-check decision order in Task 4, which the tests do not fully determine.
- **Type consistency.** `to_thresholds(spec) -> dict`, `to_rule_set(thresholds, name) -> RuleSet`, `current(s) -> RuleVersion | None`, `current_thresholds(s) -> dict`, `propose(s, thresholds, *, rationale, by, now, experiment=None, proposed_by="user", force_needs_user=False) -> RuleVersion` (the keyword added in Task 4 is used only there), `apply_version(s, version_id, *, by, now, note=None) -> RuleVersion`, `take_experiment(s, experiment_id, *, by, note, now) -> RuleVersion`, `verify_forward(s, *, now) -> dict`, `evidence_for(s, *, agent_id, reasons, bars_in_trade) -> dict | None`, `window_key(positions, slippage_r=SLIPPAGE_R, *, canonical=True, rule_version=None) -> str`, `run_experiments(..., baseline: RuleSet | None = None)`, `grid(ttt, baseline)`. Experiment statuses: `OPEN | NONE | DISMISSED | SUPERSEDED | TAKEN`. Version statuses: `APPLIED | NEEDS_USER | SUPERSEDED`. Verify statuses: `NONE | PENDING | HOLDS | OUTSIDE`.
- **Review Focus.** 1 → Task 3 (`test_taking_a_timestop_v2_row_is_refused_naming_the_knob_and_leaves_it_open`); 2 → Task 2 (`test_the_tick_without_any_rule_version_runs_on_the_constant`); 3 → Tasks 1 and 2 (`test_an_applied_version_supersedes_every_other_open_experiment`, `..._a_new_version_reruns_the_window`); 4 → Task 4 (`..._is_none_and_proposes_nothing`, `..._proposes_a_revert_once_outside`); 5 → Task 6 (`test_evidence_counts_below_the_floor_and_means_above_it`, `test_evidence_is_none_without_decisions`, `test_build_document_writes_the_scorecard_only_when_given_and_hashes_as_before_without_it`).
- **Proportion.** The plan is shorter than the spec's section it implements plus lever D's plan it extends; the code blocks are test names and assertions, not bodies.
- **Known limits, for the record:** `_reusable_dossier` (`cycle.py:~480`) reuses an AMBER dossier for an hour, so the evidence section refreshes at most hourly per position; a version applied mid-week is first re-tested by the next canonical build (the `/r<id>` key), not immediately; the forward check's "observed" delta is replay-based on the positions opened under the new version (the same simulator as the prediction, so the two are comparable), not the graded decision outcomes, which measure a different counterfactual.
