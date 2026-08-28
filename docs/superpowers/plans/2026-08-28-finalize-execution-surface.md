# Finalize the Execution Surface — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the last structural gap between "omega generates" and "a real strategy exists": integrate the compile-bridge branch, record the user's execution-surface decisions, run the two remaining compile measurements, model the execution surface per Decision 1, and — with explicit per-instance user approval — apply ONE generated strategy end to end.

**Architecture:** Five user-approved steps, executed in dependency order (measure-before-build): (0) merge the finished branch to `main`; (1) record the user's decisions from the kickoff prompt into the spec, STOP if any answer diverges from what this plan encodes; (2) execution-day preflight; (3–4) two single-compile probes — bounds enforcement and defaults-at-4h — that the build consumes; (5–6) model the measured defaults/overrides and the partial scoring-inputs relation; (7) docs; (8) the gated apply + read-back verification; (9) integrate and hand off.

**Tech Stack:** Python 3 (stdlib + pydantic via omega.types), pytest, the BattleGrid MCP connector (`mcp__c330236a-…`), git.

## Global Constraints

- **Compile budget: exactly 4 `compile_strategy_plan` calls** — Task 3 (1), Task 4 (1), Task 8 (1 fresh for the apply token, +1 ONLY if the first is refused for a material, fixable reason; say so in the record). Never re-compile a success.
- **`apply_strategy_plan` runs at most ONCE, in Task 8 only, and only under the user's explicit per-instance authorization** (the kickoff prompt sentence naming the trend-continuation CREATE). Without that sentence in the user's own words, STOP at Task 8 and ask.
- **NEVER bind anything to an agent. NEVER create radar or arena deployments.** Standing rule; no general "go ahead" authorises either.
- **Record every live response verbatim into `data/audit/` before interpreting it.** A refusal is a finding, not a failure. **Redact `planToken`** in committed records to `{length, sha256}` (pattern: `compile_dry_run_2026-08-28-small.json`).
- **Decisions belong to the user.** Tasks 5 and 6 are written for Decision 1 = (a) and Decision 4 = leave-as-is. If the kickoff prompt answers differently, STOP after Task 1 and revise this plan with a dated note — do not improvise the other branch.
- **Re-verify the live compile schema before any compile** (Task 2). Cached capability lists are not authoritative after a deployment.
- Baseline: branch `claude/compile-bridge-probes-plan-2140a5` at `767cf36`, **810 tests passing**. Run `python -m pytest -q` before every commit; commit messages end with the Claude co-author line.
- Windows: write files with Write/Edit tools, not bash heredocs. Large MCP results overflow to a file — verify by script (jq/python), never by eye.
- If any measurement contradicts something this plan asserts, correct the plan file itself with a dated note — never silently.

## Context an executor needs (read these first)

| file | why |
|---|---|
| `data/audit/execution_surface_ownership_2026-08-28.json` | the measured defaults, bounds discrepancy, and ownership verdict this plan builds on |
| `data/audit/compile_dry_run_2026-08-28-small.json` | the viable compile; its `postState` is the defaults source and the apply target's expected shape |
| `docs/superpowers/specs/2026-08-27-execution-surface-decisions.md` | the decisions Task 1 records; Decision 2 already answered |
| `omega/generate.py` (`Thesis`, `StrategyPlan.wire()`, `_assumptions`, `critique`) | the code Tasks 5–6 modify |
| `scripts/compile_dry_run.py` | the compile harness Tasks 3/4/8 extend and use |
| `tests/test_write_surface.py` | pinned tests that flip in Task 5 (same commit as the code) |
| `docs/16-the-write-path.md` §§ compile outcome + execution surface | docs Task 7/8 update |

Key measured facts (do not re-derive, do not contradict):
- Platform defaults at 1h (from the viable compile's `postState`, none sent): minAtrPct **0.5**, minRiskRewardRatio **1.5**, stop **1–2×ATR**, trailing **on** (1R / 45% / 0.25), break-even **on** at **1.08R**, time decay **on** (15 min interval / 60 min grace / 5% tighten / 50% max / stale at 25% TP).
- Agent `tradingConfig` carries capital controls only; the 16 execution params are strategy fields; the tradable universe lives in per-coin radar deployments.
- Bounds conflict: agent catalog says ATR 0.1–10 and R:R 0.5–3; the compile schema says minAtrPct 0.01–50 and leaves R:R unbounded. **Which is enforced on a strategy write is unmeasured — Task 3 settles it.**
- BG-14: keep every probe's `coinSelection` small (explicit BTC/ETH/SOL) or the compile's own preview blows the 256,000-byte cap.
- The apply shape (doc 16, proven 3×): `{request: {confirm: true, planToken}}` — **omit `plan`**. Token lives 5 minutes. `INTERNAL_ERROR` → resend identical. Timeout → `get_strategy` on the token's pre-allocated id before any retry.
- 12 measured scoring-input pairs from the viable compile's advisories (signalId → metric@rung): htf_ma_aligned_bull/bear → MA_ALIGN@signalHigher; htf_trend_adx_trending/ranging → ADX@signalHigher; ltf_ma_aligned_bull/bear → MA_ALIGN@lower; ltf_trend_adx_trending/ranging → ADX@lower; ma_ema_aligned_bull/bear → EMA20@anchor; ma_ema_bull/bear_cross → EMA_CROSS@anchor. A report carrying MA_ALIGN and ADX **at rel:anchor** still tripped the higher/lower-rung entries, so an anchor column does NOT satisfy a non-anchor rung.

---

### Task 0: Integrate the finished branch into `main`

**Files:** none modified — git only.

- [x] **Step 0.1:** `git fetch origin`, then confirm the merge is a fast-forward: `git merge-base --is-ancestor origin/main claude/compile-bridge-probes-plan-2140a5 && echo FF-OK`. If it prints nothing, origin/main moved since `a136cff` — STOP and surface to the user; do not force anything.
- [x] **Step 0.2:** `git push origin claude/compile-bridge-probes-plan-2140a5:main` (worktree-safe fast-forward of remote main; no local `main` checkout needed).
- [x] **Step 0.3:** If this session's worktree was cut from the *old* main: `git fetch origin && git merge origin/main` to bring the finished work into the session branch. Verify: `python -m pytest -q` → **810 passed** (plus this plan file present).

### Task 1: Record the user's decisions (gate)

**Files:**
- Modify: `docs/superpowers/specs/2026-08-27-execution-surface-decisions.md`

- [x] **Step 1.1:** Read the kickoff prompt's decision block. Required answers: **Decision 1** (execution emission policy), **Decision 4** (flow-divergence label), **quota path** for Task 8 (free 25th slot vs archive an OMEGA-TEST first), **post-apply disposition** (keep vs archive the created strategy), and the **apply authorization sentence**. Any missing → STOP, ask the user, end turn if unanswered.
- [x] **Step 1.2:** In the spec, mark Decision 1 and Decision 4 **ANSWERED <date>** with the user's exact words quoted, same style as the Decision 2 entry. Decision 3: mark "moot under 1(a)" if 1(a) was chosen, else STOP (plan revision needed).
- [x] **Step 1.3:** If Decision 1 ≠ (a) or Decision 4 ≠ leave-as-is: add a dated note to THIS plan file stating the divergence, and stop for plan revision. Otherwise commit: `Record the execution-surface decisions` → push.

### Task 2: Execution-day preflight

**Files:** none modified.

- [x] **Step 2.1:** `ToolSearch` `select:mcp__c330236a-7aee-4d07-ae11-e487c8cbc894__compile_strategy_plan`. Diff the CREATE branch against `API_ACCEPTS`/`API_REQUIRES` in `tests/test_write_surface.py` and the 16-param bounds in the plan's Key facts. Drift → STOP, update the pinned sets in their own commit first (pattern: Task 0 of the 2026-08-27 plan).
- [x] **Step 2.2:** `list_strategies` — note quota (expect 24/25; any change goes in the Task 3 commit message). `get_account_state` optional.

### Task 3: Probe A — which R:R bound is enforced (1 compile)

**Files:**
- Modify: `scripts/compile_dry_run.py`
- Create: `data/audit/bounds_probe_2026-XX-XX.json` (execution date)
- Test: `tests/test_compile_dry_run.py` (append)

**Interfaces:**
- Produces: `request(small=True, rr=5.0)` — the small viable payload with exactly one field changed: `minRiskRewardRatio: 5.0` (outside catalog 0.5–3, unbounded in schema). One variable, so the result is attributable.

- [x] **Step 3.1:** Extend the harness. In `scripts/compile_dry_run.py` replace the `request` function and add redaction to record mode:

```python
def request(*, small: bool = False, rr: float | None = None,
            anchor: str | None = None) -> dict:
    thesis = PRESETS[PRESET]
    if small or rr is not None or anchor is not None:
        thesis = replace(thesis, coin_selection={"mode": "explicit",
                                                 "tickers": SMALL_TICKERS})
    if anchor is not None:
        thesis = replace(thesis, anchor=anchor)
    req = plan(thesis).wire()
    if rr is not None:
        # Probe: catalog says R:R 0.5-3, schema says unbounded. One changed field.
        req["minRiskRewardRatio"] = rr
    return {"request": req}
```

In `main()`, add modes `small`, `bounds` (prints `request(small=True, rr=5.0)`), `tf4h` (prints `request(small=True, anchor="4h")`); in record mode, before writing, redact: `if isinstance(resp.get("planToken"), str): t = resp["planToken"]; resp["planToken"] = {"_redacted": "credential-bound 5-minute token, left to expire; never applied", "length": len(t), "sha256": hashlib.sha256(t.encode()).hexdigest()}` (add `import hashlib`).
- [x] **Step 3.2:** `python -m pytest -q` — the existing suite must stay green (810; `request()` default unchanged). `python -m scripts.compile_dry_run bounds` → sanity-check by script: only `minRiskRewardRatio` differs from the recorded small request.
- [x] **Step 3.3:** ONE `compile_strategy_plan` call with the printed body. Record verbatim (overflow → record mode). Branches pre-committed:
  - **typed refusal naming a bound** → that bound is enforced on strategy writes; record `allowedDomain` exactly; `CATALOG_BOUNDS` become errors in Task 5.
  - **viable and `postState.minRiskRewardRatio == 5.0`** → schema governs; catalog bounds are agent-side residue; they become advisory warnings in Task 5.
  - **viable but postState value ≠ 5.0** → silent clamp: new platform defect (BG-15 candidate — defects artifact addendum in Task 7), record both numbers.
- [x] **Step 3.4:** Append a pinning test to `tests/test_compile_dry_run.py` (record exists, verdict filled — not "FILL IN", and the measured branch's key fact asserted). Suite green → commit `Bounds probe: <verdict>` → push.

### Task 4: Probe B — defaults at a 4h anchor (1 compile)

**Files:**
- Create: `data/audit/defaults_4h_probe_2026-XX-XX.json`
- Test: `tests/test_compile_dry_run.py` (append)

- [x] **Step 4.1:** `python -m scripts.compile_dry_run tf4h`; verify by script: `timeframe == "4h"`, explicit 3 tickers, no `minRiskRewardRatio` override. **Prediction stated before measuring:** postState `cadence == "INTRADAY"`, `regimeTimeframe == "1d"` (omega's `CADENCE_FOR_ANCHOR`/`REGIME_TF_FOR_ANCHOR` at 4h) — the probe tests omega's mapping at a second anchor.
- [x] **Step 4.2:** ONE compile. Record verbatim (redacting token). Extract the 16 postState values + cadence/regimeTimeframe by script; diff against the 1h defaults in `execution_surface_ownership_2026-08-28.json`.
- [x] **Step 4.3:** Pin: defaults identical at both anchors (then `PLATFORM_EXECUTION_DEFAULTS` in Task 5 is anchor-independent, say "measured at 1h and 4h") OR they differ (then Task 5's constant becomes `{anchor: {...}}` keyed by measured anchors ONLY, with unmeasured anchors explicitly unknown). Also pin the cadence/regimeTimeframe prediction outcome. Suite green → commit `Defaults probe at 4h: <identical|differs>` → push.

> **Correction, 2026-08-28 (measured during execution):** Step 4.1's cadence
> prediction was WRONG — the server derives `SWING` for a 4h anchor, not `INTRADAY`.
> The `regimeTimeframe` prediction (`1d`) held. `CADENCE_FOR_ANCHOR["4h"]` was
> corrected to the measured value in the Task 4 commit and the outcome pinned. The
> 16 defaults themselves measured IDENTICAL at both anchors, so Task 5's constant
> stays flat (anchor-independent as measured); where the INTRADAY/SWING boundary
> lies between 1h and 4h is unmeasured.

**Deliberately absent from this plan:** the BG-14 cap-boundary probe (largest `coinSelection`
that still compiles). The small-selection workaround suffices for every task here; do not
measure the boundary opportunistically — it spends compile budget this plan needs.

### Task 5: Model the execution surface (Decision 1a)

**Files:**
- Create: `omega/execution.py`, `tests/test_execution.py`
- Modify: `omega/generate.py` (`Thesis`, `wire()`, `_assumptions`, `critique`), `tests/test_write_surface.py` (flip one pinned test), `data/audit/write_surface_gap.json` (`executionSurfaceNotModelled._resolved`)

**Interfaces:**
- Produces: `PLATFORM_EXECUTION_DEFAULTS: dict`, `EXECUTION_PARAMS: frozenset`, `SCHEMA_BOUNDS: dict`, `CATALOG_BOUNDS: dict`, `validate_execution(overrides: dict) -> list[Finding]`; `Thesis.execution: dict | None = None`; `wire()` merges overrides last.

- [x] **Step 5.1: Write the failing tests** — `tests/test_execution.py`:

```python
"""Decision 1(a), recorded <date>: omega emits NO execution parameters by default and
says exactly what the platform will therefore do - the defaults are measured, not
invented (execution_surface_ownership_2026-08-28.json + the Task 3/4 probes)."""
from dataclasses import replace

from omega.execution import (
    EXECUTION_PARAMS, PLATFORM_EXECUTION_DEFAULTS, SCHEMA_BOUNDS, validate_execution,
)
from omega.generate import PRESETS, plan


def test_the_defaults_are_the_measured_ones():
    assert len(EXECUTION_PARAMS) == 16
    assert PLATFORM_EXECUTION_DEFAULTS["minRiskRewardRatio"] == 1.5
    assert PLATFORM_EXECUTION_DEFAULTS["trailingEnabled"] is True
    assert PLATFORM_EXECUTION_DEFAULTS["breakEvenTriggerR"] == 1.08


def test_presets_emit_no_execution_parameters():
    for preset in PRESETS:
        assert not EXECUTION_PARAMS & set(plan(PRESETS[preset]).wire())


def test_an_explicit_override_reaches_the_wire():
    t = replace(PRESETS["trend-continuation"], execution={"minRiskRewardRatio": 2.0})
    w = plan(t).wire()
    assert w["minRiskRewardRatio"] == 2.0
    assert EXECUTION_PARAMS & set(w) == {"minRiskRewardRatio"}


def test_override_validation():
    assert any(f.code == "EXECUTION_UNKNOWN_PARAM"
               for f in validate_execution({"minRiskReward": 2}))       # typo'd key
    lo, hi = SCHEMA_BOUNDS["breakEvenTriggerR"]
    assert any(f.code == "EXECUTION_OUT_OF_BOUNDS" and f.severity == "error"
               for f in validate_execution({"breakEvenTriggerR": hi + 1}))
    assert not [f for f in validate_execution({"breakEvenTriggerR": 1.5})
                if f.severity == "error"]


def test_critique_states_the_effective_profile():
    text = " ".join(plan(PRESETS["trend-continuation"]).critique())
    assert "platform defaults" in text and "R:R 1.5" in text
```

- [x] **Step 5.2:** Run `python -m pytest tests/test_execution.py -q` — expect FAIL (module missing).
- [x] **Step 5.3: Implement `omega/execution.py`:**

```python
"""The execution surface: measured platform defaults and override validation.

Nothing here is designed - every number is measured. Defaults: the viable CREATE
compile's postState (data/audit/execution_surface_ownership_2026-08-28.json), confirmed
<identical|per-anchor> at 4h by data/audit/defaults_4h_probe_<date>.json. Bounds
enforcement: data/audit/bounds_probe_<date>.json.
"""
from __future__ import annotations

from .validate import Finding

PLATFORM_EXECUTION_DEFAULTS: dict = {
    "minAtrPct": 0.5, "minRiskRewardRatio": 1.5,
    "minStopLossAtrMultiple": 1, "maxStopLossAtrMultiple": 2,
    "trailingEnabled": True, "trailingTriggerR": 1,
    "trailingGivebackPct": 45, "trailingBufferPct": 0.25,
    "breakEvenEnabled": True, "breakEvenTriggerR": 1.08,
    "timeDecayEnabled": True, "timeDecayIntervalMinutes": 15,
    "timeDecayGracePeriodMinutes": 60, "timeDecayTightenPct": 5,
    "timeDecayMaxTightenPct": 50, "timeDecayStaleThresholdTpProgressPct": 25,
}
EXECUTION_PARAMS = frozenset(PLATFORM_EXECUTION_DEFAULTS)

# Bounds the compile schema publishes (re-verified in Task 2). Params absent here are
# unbounded in the schema.
SCHEMA_BOUNDS: dict = {
    "minAtrPct": (0.01, 50), "trailingTriggerR": (0, 2),
    "trailingGivebackPct": (25, 55), "trailingBufferPct": (0.01, 1),
    "breakEvenTriggerR": (0.5, 2), "timeDecayIntervalMinutes": (1, 480),
    "timeDecayGracePeriodMinutes": (1, 1440), "timeDecayTightenPct": (0.1, 50),
    "timeDecayMaxTightenPct": (1, 100), "timeDecayStaleThresholdTpProgressPct": (0, 100),
}
# Bounds the AGENT-facing catalog publishes for two of the knobs. Task 3 measured
# <verdict>: <encode the probe verdict here with the date>.
CATALOG_BOUNDS: dict = {"minAtrPct": (0.1, 10), "minRiskRewardRatio": (0.5, 3)}


def validate_execution(overrides: dict) -> list[Finding]:
    out: list[Finding] = []
    for k, v in overrides.items():
        if k not in EXECUTION_PARAMS:
            out.append(Finding("error", "EXECUTION_UNKNOWN_PARAM", f"execution.{k}",
                               f"{k} is not one of the 16 execution parameters"))
            continue
        if k in SCHEMA_BOUNDS and isinstance(v, (int, float)):
            lo, hi = SCHEMA_BOUNDS[k]
            if not (lo <= v <= hi):
                out.append(Finding("error", "EXECUTION_OUT_OF_BOUNDS", f"execution.{k}",
                                   f"{k}={v} outside the schema bound {lo}-{hi}"))
        if k in CATALOG_BOUNDS and isinstance(v, (int, float)):
            lo, hi = CATALOG_BOUNDS[k]
            if not (lo <= v <= hi):
                # Severity per the Task 3 measurement: "warning" if the schema governed
                # (5.0 compiled), "error" if the catalog bound was enforced. Set it from
                # the probe record and cite it in this comment.
                out.append(Finding("warning", "EXECUTION_OUTSIDE_CATALOG_BOUND",
                                   f"execution.{k}",
                                   f"{k}={v} is legal on the strategy write but outside "
                                   f"the agent catalog's {lo}-{hi}"))
    return out
```

(If Task 4 measured per-anchor defaults, shape the constant `{anchor: {...}}` for measured anchors only and adjust the tests' lookups accordingly — unmeasured anchors stay absent, not guessed.)
- [x] **Step 5.4:** In `omega/generate.py`: add `execution: dict | None = None` to `Thesis`; in `wire()`, build the dict into a variable `out` and before `return out` add:

```python
        if self.thesis.execution:
            out.update(self.thesis.execution)   # validated in critique(); keys are API fields
```

In `_assumptions()`, make the third entry conditional: `"no execution parameters set - the MEASURED platform defaults apply (see omega/execution.py)"` when `self.thesis.execution` is falsy, else `f"execution overrides set: {sorted(self.thesis.execution)}"`. In `critique()`, append execution findings and one effective-profile line:

```python
        from .execution import PLATFORM_EXECUTION_DEFAULTS, validate_execution
        ov = self.thesis.execution or {}
        out += [f"execution {f.severity}: {f}" for f in validate_execution(ov)]
        eff = {**PLATFORM_EXECUTION_DEFAULTS, **ov}
        out.append(
            f"execution: {'platform defaults' if not ov else f'{len(ov)} override(s)'}"
            f" - R:R {eff['minRiskRewardRatio']}, ATR gate {eff['minAtrPct']}%, stop "
            f"{eff['minStopLossAtrMultiple']}-{eff['maxStopLossAtrMultiple']}xATR, "
            f"trailing {'on' if eff['trailingEnabled'] else 'off'}, break-even "
            f"{'on' if eff['breakEvenEnabled'] else 'off'} at {eff['breakEvenTriggerR']}R, "
            f"time decay {'on' if eff['timeDecayEnabled'] else 'off'}")
```

- [x] **Step 5.5:** Flip the pinned test in `tests/test_write_surface.py` **in this same commit**: replace `test_the_execution_surface_is_still_unmodelled` with

```python
def test_presets_still_emit_no_execution_parameters():
    """CLOSED <date> (was: the 16-parameter gap). Decision 1(a): presets emit none and
    the critique states the measured defaults; overrides are explicit per-thesis. The
    old pinned form is preserved in git history."""
    from omega.execution import EXECUTION_PARAMS
    emitted = set(plan(PRESETS["trend-continuation"]).wire())
    assert not (EXECUTION_PARAMS & emitted)
    assert EXECUTION_PARAMS < API_ACCEPTS
    assert "_resolved" in GAP["executionSurfaceNotModelled"]
```

and add to `write_surface_gap.json` inside `executionSurfaceNotModelled`: `"_resolved": {"date": "<date>", "how": "Decision 1(a): presets emit nothing; measured platform defaults stated in the critique; explicit Thesis.execution overrides validated against measured bounds (omega/execution.py)"}` — keep everything else in place as history.
- [x] **Step 5.6:** `python -m pytest -q` — all green (~816). Commit `Model the execution surface: measured defaults, explicit overrides` → push.

### Task 6: Partial scoring-inputs warnings (the 12 measured pairs)

**Files:**
- Create: `data/derived/scoring_inputs_measured.json`, `tests/test_scoring_inputs.py`
- Modify: `omega/membership.py` (add one function; do NOT restructure), `omega/generate.py` (`critique` — one loop)

**Interfaces:**
- Produces: `scoring_gaps(report, rules) -> list[Finding]` in `omega/membership.py` — warning code `SCORING_INPUT_NOT_RENDERED`.

- [x] **Step 6.1:** Write `data/derived/scoring_inputs_measured.json`:

```json
{
  "_what": "signalId -> the scoring input the compile advisory named, MEASURED from the 12 ACTIVE_SIGNAL_DATA_NOT_IN_REPORT entries in compile_dry_run_2026-08-28-small.json. PARTIAL: 12 of 84 signals measured; absence of a signal here means UNMEASURED, not satisfied.",
  "_rungFact": "a rel:anchor column does NOT satisfy a signalHigher/lower rung - the probe report carried MA_ALIGN and ADX at rel:anchor and the htf/ltf entries still fired. Whether a rel:regime or rel:lower column satisfies them is UNMEASURED.",
  "pairs": {
    "htf_ma_aligned_bull": {"metric": "MA_ALIGN", "rung": "signalHigher"},
    "htf_ma_aligned_bear": {"metric": "MA_ALIGN", "rung": "signalHigher"},
    "htf_trend_adx_trending": {"metric": "ADX", "rung": "signalHigher"},
    "htf_trend_adx_ranging": {"metric": "ADX", "rung": "signalHigher"},
    "ltf_ma_aligned_bull": {"metric": "MA_ALIGN", "rung": "lower"},
    "ltf_ma_aligned_bear": {"metric": "MA_ALIGN", "rung": "lower"},
    "ltf_trend_adx_trending": {"metric": "ADX", "rung": "lower"},
    "ltf_trend_adx_ranging": {"metric": "ADX", "rung": "lower"},
    "ma_ema_aligned_bull": {"metric": "EMA20", "rung": "anchor"},
    "ma_ema_aligned_bear": {"metric": "EMA20", "rung": "anchor"},
    "ma_ema_bull_cross": {"metric": "EMA_CROSS", "rung": "anchor"},
    "ma_ema_bear_cross": {"metric": "EMA_CROSS", "rung": "anchor"}
  }
}
```

- [x] **Step 6.2: Failing tests** — `tests/test_scoring_inputs.py`:

```python
"""Membership (IN_REPORT) is not 'all scoring inputs rendered' - measured 2026-08-28
via the 12 non-blocking compile advisories. This warns on the MEASURED pairs only;
the other 72 signals are unmeasured, and unmeasured means silent, not satisfied."""
from omega.generate import PRESETS, plan
from omega.membership import scoring_gaps


def test_trend_continuation_reproduces_the_12_measured_advisories():
    p = plan(PRESETS["trend-continuation"])
    gaps = scoring_gaps(p.report, p.rules)
    assert len(gaps) == 12
    assert all(f.code == "SCORING_INPUT_NOT_RENDERED" and f.severity == "warning"
               for f in gaps)


def test_presets_without_measured_signals_stay_silent():
    """mean-reversion allocates none of the 12 measured signals (its htf/ltf_rsi rungs
    are UNMEASURED, and unmeasured means silent) - so zero warnings, not guessed ones."""
    p = plan(PRESETS["mean-reversion"])
    assert not scoring_gaps(p.report, p.rules)


def test_an_anchor_column_satisfies_an_anchor_rung():
    """ma_ema_aligned_bull wants EMA20@anchor (measured). A report that actually
    renders EMA20 at rel:anchor must not warn for it."""
    from omega.types import Column, CustomSection, Report, Rule
    report = Report(anchor="1h", sections=[CustomSection(
        title="t", benchmarkTicker=None,
        columns=[Column.model_validate({"metric": "EMA20", "transformId": "value",
                                        "timeframe": {"rel": "anchor"}})])])
    rules = [Rule(signalId="ma_ema_aligned_bull", allocation=2, required=False)]
    assert not scoring_gaps(report, rules)
    # and the same rule against a report WITHOUT EMA20 does warn
    bare = Report(anchor="1h", sections=[CustomSection(
        title="t", benchmarkTicker=None,
        columns=[Column.model_validate({"metric": "CLOSE", "transformId": "value",
                                        "timeframe": {"rel": "anchor"}})])])
    assert len(scoring_gaps(bare, rules)) == 1
```

- [x] **Step 6.3: Implement** in `omega/membership.py`:

```python
SCORING_INPUTS = json.loads(
    (DERIVED_DIR / "scoring_inputs_measured.json").read_text(encoding="utf-8"))["pairs"]
# (reuse membership.py's existing json/DERIVED_DIR imports - it already loads
# signal_module_map.json the same way; add `import json` / `from .contract import
# DERIVED_DIR` only if genuinely absent)


def scoring_gaps(report, rules) -> list:
    """Warn when an allocated signal's MEASURED scoring input is not rendered.
    PARTIAL map (12 of 84 measured); an anchor column satisfies only the anchor rung -
    the 2026-08-28 compile proved rel:anchor does not cover signalHigher/lower."""
    from .validate import Finding

    def _rel(tf):
        # Column.timeframe validates from {"rel": "anchor"} dicts; handle both the
        # dict and the pydantic-model representation without caring which it is.
        return tf.get("rel") if isinstance(tf, dict) else getattr(tf, "rel", None)

    anchored = {c.metric for s in report.sections if getattr(s, "columns", None)
                for c in s.columns if _rel(c.timeframe) == "anchor"}
    out = []
    for r in rules:
        if r.allocation <= 0 or r.signalId not in SCORING_INPUTS:
            continue
        want = SCORING_INPUTS[r.signalId]
        if want["rung"] == "anchor" and want["metric"] in anchored:
            continue
        out.append(Finding(
            "warning", "SCORING_INPUT_NOT_RENDERED", f"rules.{r.signalId}",
            f"{r.signalId} scores on {want['metric']} @ {want['rung']}, which the "
            f"report does not render (measured 2026-08-28; whether a rel:regime/lower "
            f"column satisfies a non-anchor rung is unmeasured)"))
    return out
```

Adapt the `anchored` comprehension to the real `Column.timeframe` type (it is a pydantic model — check `omega/types.py` and use the actual attribute access; the intent is "columns whose timeframe is rel:anchor").
- [x] **Step 6.4:** In `StrategyPlan.critique()` append: `out += [f"scoring {f.severity}: {f}" for f in scoring_gaps(self.report, self.rules)]` (import `scoring_gaps` at the top of `generate.py` from `.membership`). Check whether `tests/test_generated_plans_audit.py` KNOWN lists need the new warnings — if the audit script surfaces critique lines, add the trend-continuation entries to `KNOWN` deliberately, with a comment. Full suite green → commit `Warn on measured scoring-input gaps` → push.

### Task 7: Documentation

**Files:**
- Modify: `docs/16-the-write-path.md`, `docs/08-strategy-generation.md`, `README.md`, `docs/superpowers/specs/2026-08-27-execution-surface-decisions.md`; `artifact/battlegrid-defects.html` + republish ONLY if Task 3 produced the silent-clamp defect.

- [x] **Step 7.1:** Doc 16: in the execution-surface section, replace the "it simply has not been modelled" close with the Decision 1(a) outcome (modelled <date>: defaults stated, overrides validated, bounds enforcement per Task 3's verdict). Doc 08: extend the guarantees list — "**execution-transparent** — every plan's critique states the effective trade-management profile; presets emit no execution parameters (Decision 1a, <date>)".
- [x] **Step 7.2:** Spec: confirm Decisions 1/3/4 all read ANSWERED/moot with dates. README index lines for 08/16 if their one-liners changed.
- [x] **Step 7.3:** If (and only if) Task 3 measured a silent clamp: add BG-15 to the defects artifact (summary row + article, same structure as BG-14), bump the masthead count, republish to `https://claude.ai/code/artifact/a0ed53c1-f6d3-4abf-9225-c4abf3dfd71a` with favicon 🐛, and note it in `artifact/README.md`.
- [x] **Step 7.4:** Full suite → commit `Document the execution-surface closure` → push.

### Task 8: Apply ONE generated strategy (HARD GATE)

**Files:**
- Create: `data/audit/first_generated_apply_2026-XX-XX.json`, `tests/test_first_apply.py`
- Modify: `docs/16-the-write-path.md` (new short section), `README.md` masthead note

- [x] **Step 8.1 (gate):** Confirm the kickoff prompt contains the user's explicit per-instance apply authorization for the trend-continuation CREATE. Absent or ambiguous → STOP, ask, end turn if no answer. Restate in your own message what is about to happen before doing it.
- [x] **Step 8.2 (quota path, per the user's choice):** free-slot path — verify `list_strategies` quota shows ≥1 remaining. Archive-first path — `list_strategies includeInactive:true`, locate the OMEGA-TEST object the user named, `archive_strategy` it, re-check quota. Record whichever path ran.
- [x] **Step 8.3:** ONE fresh compile: `python -m scripts.compile_dry_run small` → `compile_strategy_plan` with that body. Must be `viable: true` (it was on 2026-08-28). Extract `planToken` (keep in session only — NEVER into a committed file) and `postState.id`. If refused: record verbatim, STOP — a changed platform is a finding, not a retry loop.
- [x] **Step 8.4:** Within the token's 5 minutes: `apply_strategy_plan({request: {confirm: true, planToken: "<verbatim>"}})` — no `plan` key. On `INTERNAL_ERROR`: resend identical (doc 16 rule). On timeout: `get_strategy` on `postState.id` — NOT_FOUND → safe to retry the same token if still fresh, else recompile (counts against the +1 contingency); found → the apply landed, proceed.
- [x] **Step 8.5:** Read back `get_strategy` on the new id. Verify by script: revision 1, name "Trend Continuation", `forkedFromStrategyId: null`, 2 custom sections with server-minted keys, `signalRules` dense 84 with exactly 24 non-zero allocations, the 16 execution params equal to the measured defaults, 7 conditions. Record request-summary + read-back verbatim (no token) into the audit file with an honest `_interpretation`.
- [x] **Step 8.6 (disposition, per the user's choice):** keep the strategy active, or `archive_strategy` it immediately after verification — record which. **Do not bind it to any agent; do not deploy it.**
- [x] **Step 8.7:** `tests/test_first_apply.py` pins the record (exists, interpretation filled, roundTrip.revision == 1, rules count 84/24, execution params == `PLATFORM_EXECUTION_DEFAULTS`). Doc 16: short section "A generated strategy exists" with the date, id, and disposition. Full suite → commit `Apply the first generated strategy: <id-prefix>, <kept|archived>` → push.

### Task 9: Finish

- [ ] **Step 9.1:** Full suite one last time; reconcile the test count in this plan's baseline note if it moved.
- [ ] **Step 9.2:** Integrate to `main` (same fast-forward-push pattern as Task 0; STOP on non-FF).
- [ ] **Step 9.3:** Update the memory file `next-session-compile-bridge.md` (or successor): plan executed, decisions recorded, probes' verdicts, apply outcome + strategy id + disposition, and what remains user-gated (binding, deployment — always).
- [ ] **Step 9.4:** Final report to the user: verdicts of both probes, the apply outcome, and any plan corrections made along the way.

## Self-review checklist (run before calling the plan done)

- Kickoff decisions recorded verbatim in the spec before any dependent task ran?
- Compile calls ≤ 4, apply ≤ 1, apply only under the explicit per-instance authorization?
- Every live response recorded verbatim (tokens redacted) BEFORE interpretation?
- Pinned tests flipped in the same commit as the code they pin?
- Nothing bound, nothing deployed, disposition honoured?
- Anything measured that contradicts this plan → corrected here with a dated note?
