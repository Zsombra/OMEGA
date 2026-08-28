# Generated UPDATE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give omega the UPDATE half of the write path — `wire_update`, the full-body-from-Thesis emitter — and prove it with ONE live revision loop on strategy `6a8bca67` (restore → gated UPDATE apply → read-back → archive), which also gives Decision 1(a)'s execution-override path its first real-write proof.

**Architecture:** Per the approved design (`2026-08-29-generated-update-design.md`): the Thesis is the single source of truth — `wire_update` is `wire()` plus exactly three patched fields (`operation`, `strategyId`, `expectedRevision`); the server computes the diff. The compile that mints the apply token doubles as the measurement of the UPDATE arm's unmeasured behaviors (which diff axis carries `minRiskRewardRatio`; whether identical re-sent sections keep their `sectionKey`s), with pre-committed apply/STOP branches.

**Tech Stack:** Python 3 (stdlib + pydantic via omega.types), pytest, the BattleGrid MCP connector (`mcp__c330236a-…`), git.

## Global Constraints

- **Write budget, authorized once at kickoff:** compiles **≤2** (1 + 1 contingency, contingency ONLY for a material fixable refusal — say so in the record); **exactly 1 `apply_strategy_plan`**, under a per-instance sentence naming the generated Trend Continuation UPDATE; **1 `restore_strategy`**; **1 `archive_strategy`**. Missing or ambiguous authorization → STOP at Task 0 and ask.
- **NEVER bind anything to an agent. NEVER create radar or arena deployments.** Standing; no general "go ahead" authorises either.
- **Record every live response verbatim into the audit file BEFORE interpreting it** (refusals exactly like successes). **Redact `planToken`** to `{length, sha256}`; the token is used only for the one authorized apply, never committed.
- **Predictions stated before measuring; no-prior facts declared as such, never guessed.** Failed predictions are findings, corrected in the same commit as the record; contradictions of THIS plan get a dated note here.
- **Re-verify the live compile schema (CREATE + UPDATE arms) before any compile** (Task 0).
- Baseline: `main` at `8c292db`, **849 tests passing**. `python -m pytest -q` before every commit; commit messages end with the Claude co-author line.
- Windows: Write/Edit tools for committed files, not shell heredocs. Large MCP results overflow to a file — verify by script, never by eye.
- MCP calls are made by the EXECUTOR (the session): the harness prints exact bodies; the executor pastes ONE body per call and records the response via the harness's `record-into` mode.

## Context an executor needs (read these first)

| file | why |
|---|---|
| `docs/superpowers/specs/2026-08-29-generated-update-design.md` | the approved design; the three user decisions this plan implements |
| `data/audit/first_generated_apply_2026-08-28.json` | how `6a8bca67` was created; the read-back shape; the apply/token discipline |
| `data/audit/compile_dry_run_2026-08-28-small.json` → `approvedPlan.diff` | the MEASURED diff shape the Task 2 inspection script parses |
| `scripts/compile_dry_run.py` | the harness (`probe`, `_redact`, `record-into`) Task 1 extends |
| `omega/generate.py` (`StrategyPlan.wire`) | `wire_update` wraps this |
| `tests/test_write_surface.py` (`API_ACCEPTS`) | the pinned CREATE key set the UPDATE pins build on |

Key measured facts (do not re-derive, do not contradict):

- **UPDATE schema arm** (re-verified live 2026-08-28; re-verify at execution): requires `{operation, intentSummary, assumptions, coinSelection, strategyId, expectedRevision}`; accepts the CREATE arm's 30 keys plus `strategyId` and `expectedRevision` (32 total). `coinSelection` is required even though persisted strategies carry none — it scopes the compile's review only.
- **`restore_strategy`**: `{strategyId, expectedRevision}` — direct lifecycle tool for *unchanged, already-viable* content; invalid content stays inactive with `REPAIR_REQUIRED` (would need the compile RESTORE arm — a STOP-and-surface finding here, since `6a8bca67`'s content compiled viable).
- **`6a8bca67-45a3-428e-85ba-71ec2cd2218e`**: "Trend Continuation", archived 2026-08-28 at revision 2, `boundAgentCount` 0, all 16 execution params at the measured platform defaults (`minRiskRewardRatio` 1.5). Verify live in Step 2.1 — never assume the current revision.
- **The compile `diff` shape** (measured from the viable CREATE): `changedAxes` + per-axis before/after objects `identity, timeframeProfile, report, marketRead, conditions, setupGates, signalRules, lifecycle, positionManagement, tradeLevelPolicy`. `setupGates` carries `{minAggregateScore, minRequiredCount, minAtrPct}`; `positionManagement` and `tradeLevelPolicy` were **null** on the CREATE (no execution params were sent), so **which axis carries `minRiskRewardRatio` is UNMEASURED** — this plan's compile answers it. `signalRules` diffs as a list of per-signal before/after entries.
- **Apply shape** (proven 4×): `{request: {confirm: true, planToken}}`, no `plan` key; token lives 5 minutes; `INTERNAL_ERROR` → resend identical; timeout → `get_strategy` before any retry.
- The proof Thesis: trend-continuation preset + `coin_selection {"mode": "explicit", "tickers": ["BTC","ETH","SOL"]}` (matching the body that created the strategy) + `execution {"minRiskRewardRatio": 2.0}` (legal on every measured bound: catalog 0.5–3 enforced both edges).

**Predictions (stated now, before any live call):**
- restore advances the revision by 1 (analogous to archive's measured 1→2; no direct prior for restore).
- the diff shows `minRiskRewardRatio` 1.5→2.0 under `positionManagement` or `tradeLevelPolicy` (the two null-on-CREATE axes); every other axis reads before==after.
- re-sent identical sections keep their `sectionKey`s (expected, NOT backed by measurement — CREATE re-mints; UPDATE has no prior).
- quota is untouched throughout (restore consumes the free slot, archive returns it: 24/25 → 25/25 → 24/25).

---

### Task 0: Execution-day preflight

**Files:** none modified.

- [x] **Step 0.1:** Isolated workspace (superpowers:using-git-worktrees): branch at current `origin/main` (`git fetch origin`; expect `8c292db` or a descendant). `python -m pytest -q` → **849 passed** (drift → read the new commits before proceeding).
- [x] **Step 0.2:** `ToolSearch` `select:…compile_strategy_plan` (and `…restore_strategy` if not loaded). Diff by script: CREATE keys/bounds vs the pinned sets (pattern: the 2026-08-28 preflights), PLUS the UPDATE arm — its required set vs the Key facts above, its accepted keys vs `API_ACCEPTS ∪ {strategyId, expectedRevision}`. Drift → STOP, update pins in their own commit.
- [x] **Step 0.3:** `list_strategies` — quota (expect 24/25 with the free slot the restore will use) and `6a8bca67` ABSENT from the active list. Confirm the kickoff authorizes, in the user's own words: 1 restore, ≤2 compiles, 1 UPDATE apply (per-instance), 1 archive. Any missing → STOP and ask.

### Task 1: The emitter and the harness mode

**Files:**
- Modify: `omega/generate.py` (add `wire_update` to `StrategyPlan`), `scripts/compile_dry_run.py` (add `update_request` + `update` mode)
- Test: `tests/test_first_update.py` (new — emitter-shape half; the record pins arrive in Task 2)

**Interfaces:**
- Produces: `StrategyPlan.wire_update(strategy_id: str, expected_revision: int) -> dict`; `update_request(strategy_id: str, revision: int) -> dict` and CLI `update <strategyId> <revision>` in the harness; `UPDATE_EXECUTION = {"minRiskRewardRatio": 2.0}`.

- [x] **Step 1.1: Write the failing tests** — create `tests/test_first_update.py`:

```python
"""The generated UPDATE (design 2026-08-29): wire_update is wire() plus exactly three
patched fields - the Thesis stays the single source of truth and the server computes
the diff. The record pins for the live loop are appended by the execution task."""
from __future__ import annotations

import pytest

from omega.generate import PRESETS, plan
from tests.test_write_surface import API_ACCEPTS

NIL_ID = "00000000-0000-0000-0000-000000000000"
API_UPDATE_REQUIRES = {"operation", "intentSummary", "assumptions", "coinSelection",
                       "strategyId", "expectedRevision"}


def test_wire_update_is_wire_plus_exactly_three_fields():
    p = plan(PRESETS["trend-continuation"])
    w, u = p.wire(), p.wire_update(NIL_ID, 3)
    assert u["operation"] == "UPDATE"
    assert u["strategyId"] == NIL_ID and u["expectedRevision"] == 3
    assert {k for k in set(w) | set(u) if w.get(k) != u.get(k)} == {
        "operation", "strategyId", "expectedRevision"}


def test_wire_update_refuses_a_nonpositive_revision():
    with pytest.raises(ValueError):
        plan(PRESETS["trend-continuation"]).wire_update(NIL_ID, 0)


def test_wire_update_satisfies_the_update_arm():
    u = plan(PRESETS["trend-continuation"]).wire_update(NIL_ID, 1)
    assert API_UPDATE_REQUIRES <= set(u)
    assert set(u) <= API_ACCEPTS | {"strategyId", "expectedRevision"}


def test_update_mode_body_differs_from_small_in_exactly_the_declared_fields():
    """The proof body: the known-viable small body re-targeted, with the ONE thesis
    change (the R:R override). assumptions moves too - its third entry flips to the
    overrides wording, which is Decision 1(a) working as designed."""
    from scripts.compile_dry_run import request, update_request
    small = request(small=True)["request"]
    up = update_request(NIL_ID, 3)["request"]
    assert {k for k in set(small) | set(up) if small.get(k) != up.get(k)} == {
        "operation", "strategyId", "expectedRevision", "minRiskRewardRatio",
        "assumptions"}
    assert up["minRiskRewardRatio"] == 2.0
    assert "execution overrides set: ['minRiskRewardRatio']" in up["assumptions"][2]
```

- [x] **Step 1.2:** `python -m pytest tests/test_first_update.py -q` — expect FAIL (`wire_update` / `update_request` not defined).
- [x] **Step 1.3: Implement.** In `omega/generate.py`, after `wire()`:

```python
    def wire_update(self, strategy_id: str, expected_revision: int) -> dict:
        """The exact compile_strategy_plan UPDATE request body: the full CREATE body
        re-targeted at an existing strategy (design 2026-08-29 - the Thesis is the
        single source of truth; the server computes the diff)."""
        if expected_revision < 1:
            raise ValueError(f"expectedRevision must be >= 1, got {expected_revision}")
        out = self.wire()
        out["operation"] = "UPDATE"
        out["strategyId"] = strategy_id
        out["expectedRevision"] = expected_revision
        return out
```

In `scripts/compile_dry_run.py`, next to `probe`:

```python
# The proof change (design 2026-08-29, user's choice): one execution override, legal
# on every measured bound, giving Decision 1(a)'s override path its real-write proof.
UPDATE_EXECUTION = {"minRiskRewardRatio": 2.0}


def update_request(strategy_id: str, revision: int) -> dict:
    thesis = replace(PRESETS[PRESET],
                     coin_selection={"mode": "explicit", "tickers": SMALL_TICKERS},
                     execution=dict(UPDATE_EXECUTION))
    return {"request": plan(thesis).wire_update(strategy_id, revision)}
```

and in `main()`, before the `record-into` mode:

```python
    if len(sys.argv) > 3 and sys.argv[1] == "update":
        print(json.dumps(update_request(sys.argv[2], int(sys.argv[3])),
                         separators=(",", ":")))
        return 0
```

- [x] **Step 1.4:** `python -m pytest -q` — all green (849 + 4 = 853). Commit `wire_update: the full body from the Thesis, re-targeted` → push.

### Task 2: The live loop — one restore, one compile, one apply, one archive

**Files:**
- Create: `data/audit/first_generated_update_2026-XX-XX.json` (execution date; every live response under `probes` via `record-into`)
- Modify: `tests/test_first_update.py` (append the record pins)

**Interfaces:**
- Consumes: `update_request` / CLI `update` from Task 1; `record-into <respfile> <key> <auditfile>` from the harness.
- Produces: the audit record with `probes: {preState, restore, compile, apply, readBack, archive}`, `verdicts: {restoreRevisionDelta, rrDiffAxis, sectionKeysOnUpdate}`, and the `_what`/`_predictionsStatedBeforeMeasuring`/`_interpretation`/`_honestLimits` blocks the pins assert on.

- [x] **Step 2.1 (read the archived state):** `get_strategy {strategyId: "6a8bca67-45a3-428e-85ba-71ec2cd2218e", includeInactive: true}`. Save the response to a scratch file, `record-into … preState first_generated_update_2026-XX-XX.json`. Verify by script: `isActive` false, `boundAgentCount` 0, `openPositionCount` 0, name "Trend Continuation", `minRiskRewardRatio` 1.5; capture the CURRENT revision as **R** (expect 2 — if it differs, use the measured value and say so in the record). Bound or active → STOP and surface.
- [x] **Step 2.2 (restore):** `restore_strategy {strategyId, expectedRevision: R}` → record under `restore`. Verify: `isActive` true; capture the post-restore revision **R′** (prediction: R+1 — record held/failed). `REPAIR_REQUIRED` → record, STOP, surface (the content compiled viable; that refusal would be a platform finding).
- [x] **Step 2.3 (the compile, 1 of ≤2):** `python -m scripts.compile_dry_run update 6a8bca67-45a3-428e-85ba-71ec2cd2218e <R′>` → sanity by script (the five declared fields vs `small`, correct id and revision) → ONE `compile_strategy_plan` with the printed body → record under `compile` (token auto-redacted by `record-into`; keep the raw token ONLY in session for Step 2.5).
- [x] **Step 2.4 (scripted diff inspection — pre-committed):** parse `approvedPlan` from the overflow file. **Apply only if ALL hold:**
  - `viability.viable` is true and `operation == "UPDATE"` and `expectedRevision == R′`;
  - exactly one diff axis shows `minRiskRewardRatio` before 1.5 → after 2.0 — record WHICH under `verdicts.rrDiffAxis` (the unmeasured fact this compile settles);
  - `identity`, `timeframeProfile`, `marketRead`, `setupGates` read before==after; the `signalRules` diff list is empty or every entry reads before==after; `lifecycle` reads active→active;
  - `report` before==after (`verdicts.sectionKeysOnUpdate = "PRESERVED"`), **or** a lockstep re-mint: keys changed AND every condition column reference in `conditions.after` names a key present in `report.after` (`= "LOCKSTEP_REMINT"` — proceed, and record the churn as a named finding).
  Anything else — non-viable, an unexpected axis, an inconsistent re-mint — record verbatim, let the token expire, add a dated note to THIS plan, STOP and surface. A refusal is a finding, not a retry loop.
- [x] **Step 2.5 (the ONE authorized apply):** within the token's 5 minutes: `apply_strategy_plan {request: {confirm: true, planToken}}`. `INTERNAL_ERROR` → resend identical. Timeout → `get_strategy` on the id first; only recompile (the contingency, say so) if the token is dead and the apply did NOT land. Record the response under `apply` — `appliedImpact.changedAxes`, `committedRevision`, `boundAgentCount`/`propagatedAgentCount` (both must be 0).
- [x] **Step 2.6 (read-back):** `get_strategy` on the id → record under `readBack`. Verify by script against `preState`: `minRiskRewardRatio` 1.5→**2.0**; the other 15 execution params byte-equal; `signalRules`, `marketReadText`, name/tagline/description, `minAggregateScore`, `minRequiredCount`, `timeframe/cadence/regimeTimeframe` all equal; `sections`+`conditions` equal (or, under LOCKSTEP_REMINT, internally consistent — every condition reference resolves); revision == the apply's `committedRevision` (capture as **R″**); `isActive` true, `boundAgentCount` 0.
- [x] **Step 2.7 (re-archive, the user's standing disposition):** `archive_strategy {strategyId, expectedRevision: R″, confirm: true}` → record under `archive`. Verify: `isActive` false, revision R″+1. `list_strategies` → quota back to 24/25, noted in the record.
- [x] **Step 2.8 (finalize + pin):** fill `_what` (the loop, the design decisions it proves), `_predictionsStatedBeforeMeasuring` (restore delta, rr axis, sectionKeys — copied from this plan), `verdicts` (all three), `_interpretation` (honest: what the loop proves — generate → revise → verify works end to end; what it does not — one field, one strategy, conflict handling untouched), `_honestLimits` (single data point per verdict; token redacted; nothing bound). Append the record pins to `tests/test_first_update.py`:

```python
# --- the live loop, 2026-XX-XX: pinned record ---------------------------------

import json
from pathlib import Path

from omega.execution import PLATFORM_EXECUTION_DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
REC = json.loads(
    (ROOT / "data/audit/first_generated_update_2026-XX-XX.json").read_text(encoding="utf-8"))


def test_the_loop_is_recorded_end_to_end():
    assert set(REC["probes"]) >= {"preState", "restore", "compile", "apply",
                                  "readBack", "archive"}
    assert "FILL IN" not in REC["_interpretation"]
    assert REC["verdicts"]["sectionKeysOnUpdate"] in ("PRESERVED", "LOCKSTEP_REMINT")
    assert isinstance(REC["verdicts"]["rrDiffAxis"], str) and REC["verdicts"]["rrDiffAxis"]


def test_the_override_landed_and_nothing_else_moved():
    pre = REC["probes"]["preState"]["strategy"]
    post = REC["probes"]["readBack"]["strategy"]
    assert pre["minRiskRewardRatio"] == 1.5 and post["minRiskRewardRatio"] == 2.0
    for k in PLATFORM_EXECUTION_DEFAULTS:
        if k != "minRiskRewardRatio":
            assert post[k] == pre[k]
    assert post["signalRules"] == pre["signalRules"]
    assert post["marketReadText"] == pre["marketReadText"]
    if REC["verdicts"]["sectionKeysOnUpdate"] == "PRESERVED":
        assert post["sections"] == pre["sections"]
        assert post["conditions"] == pre["conditions"]


def test_the_lifecycle_ends_where_it_started():
    assert REC["probes"]["readBack"]["strategy"]["isActive"] is True
    assert REC["probes"]["archive"]["strategy"]["isActive"] is False
    assert REC["probes"]["apply"]["appliedImpact"]["boundAgentCount"] == 0
    assert REC["probes"]["apply"]["appliedImpact"]["propagatedAgentCount"] == 0
    tok = REC["probes"]["compile"].get("planToken")
    assert tok is not None and set(tok) == {"_redacted", "length", "sha256"}
```

- [x] **Step 2.9:** `python -m pytest -q` — green (853 + 3 = 856). Commit `Apply the first generated UPDATE: <rr axis verdict>, <sectionKeys verdict>` → push. Failed predictions (restore delta, axis, keys) get their honest sentence in the commit message.

### Task 3: Documentation and finish

**Files:**
- Modify: `docs/16-the-write-path.md`, `docs/08-strategy-generation.md`, `docs/superpowers/specs/2026-08-28-assistant-phase-decisions.md`, `README.md`.

- [ ] **Step 3.1:** Doc 16: new short section "A generated strategy can be revised (2026-XX-XX)" — the loop, the measured rr-axis and sectionKey verdicts, the record link; and fix the now-stale sentence that generated plans have only ever been CREATEd. Doc 08: guarantee line "**revisable** — `wire_update` re-targets the full body at `strategyId`/`expectedRevision`; the Thesis stays the single source of truth and the server computes the diff (proven live <date>)".
- [ ] **Step 3.2:** Spec `2026-08-28-assistant-phase-decisions.md`: roadmap item 2 marked **EXECUTED <date>** with the verdicts, one line each. README masthead sentence + 08/16 index one-liners if their claims changed.
- [ ] **Step 3.3:** Budget audit by script from the record: compiles ≤2 (count `compile` probes + any contingency), applies == 1, restore == 1, archive == 1; state the counts in the commit message. Reconcile this plan's baseline note (849 → the final count) with a dated line.
- [ ] **Step 3.4:** Full suite → commit `Document the revision loop` → push → integrate: `git fetch origin && git merge-base --is-ancestor origin/main HEAD && git push origin HEAD:main` (STOP on non-FF).
- [ ] **Step 3.5:** Update memory (`next-session-compile-bridge.md`): step 2 executed, verdicts, what remains (the assistant itself — brainstorm → spec → plan; binding/deployment user-gated always). Final report: the three verdicts, prediction outcomes, budget spent, any plan corrections.

## Deliberately absent (from the approved design)

- A wrong-`expectedRevision` probe — conflict behavior is documented platform business, not the builder's happy path.
- The delta emitter and any omitted-means-keep measurement — decision 1 chose full-body.
- Anything touching agents, radar, or arena deployments — permanently user-gated.

## Self-review checklist (run before calling the plan done)

- Kickoff authorization present for all four writes, apply sentence per-instance?
- Every live response recorded verbatim (token redacted) BEFORE interpretation; refusals like successes?
- Predictions (restore delta, rr axis, sectionKeys) stated before the calls; outcomes recorded held/failed; failures corrected in the same commit?
- The diff inspection ran BEFORE the apply, against the pre-committed criteria, by script?
- Quota ends at 24/25; nothing bound, nothing deployed; budget audit says compiles ≤2, applies 1, restore 1, archive 1?
