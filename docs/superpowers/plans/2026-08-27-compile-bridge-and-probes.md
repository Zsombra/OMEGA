# Compile Bridge and Final Probes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `omega.generate` emit the exact CREATE request the write API accepts, prove it with one live `compile_strategy_plan` dry-run (NO apply), close the last untested probe (`BAR_FORMING` at an offset), and update every document and artifact the results touch.

**Architecture:** Three independent workstreams. (1) `StrategyPlan.wire()` is reshaped to the `compile_strategy_plan` CREATE request schema and the pinned gap-tests are flipped deliberately. (2) One compile dry-run converts the schema-derived key-mismatch claim into a measurement. (3) One preview render settles `BAR_FORMING`'s offset behaviour. Docs/artifacts update at the end from whatever the live steps found.

**Tech Stack:** Python 3 (stdlib + pydantic via omega.types), pytest, the BattleGrid MCP connector (`mcp__c330236a-...`), the Artifact tool for republishing.

## Global Constraints

- **NEVER call `apply_strategy_plan`.** Compile is the ceiling of this plan. A compile parks a plan and mints a 5-minute token; the token is left to expire. Nothing is created, updated, forked, or archived.
- **NEVER bind anything to an agent.** Standing user rule; no general "go ahead" authorises it.
- **Compile once per reviewed payload.** The tool's own doc says each call mints a distinct record — do not retry a successful compile, do not fan out two compiles for one payload.
- **Re-verify the schema on execution day before coding (Task 0).** The connector's own instructions say cached capability lists are not authoritative after a deployment. Every field-set in this plan was read from the live schema on **2026-08-26** and may be stale by execution time.
- **Record every live response verbatim** into `data/audit/` before interpreting it. A refusal is a finding, not a failure — capture the typed error exactly.
- **Repo conventions:** commits go straight to `main` and are pushed; commit messages end with the Claude co-author line; run `python -m pytest -q` (currently **782 passing**) before every commit.
- Windows environment: write files with the Write/Edit tools, not bash heredocs (quoting has bitten repeatedly). Large MCP results overflow to a file — verify them by script (see `scripts/record_spread_batch.py` for the pattern), never by eye.

## Context an executor needs (read these first)

| file | why |
|---|---|
| `data/audit/write_surface_gap.json` | the measured gap this plan closes; its `keyMismatch` block is the spec |
| `tests/test_write_surface.py` | the pinned gap-tests that must flip **in the same commit** as the code |
| `omega/generate.py` (`Thesis`, `StrategyPlan.wire()`, `emit_plan`) | the code being changed |
| `data/audit/offset_ignored.json` | BG-13; `scope.untested == ["BAR_FORMING"]` is what Task 5 resolves |
| `docs/16-the-write-path.md` § "What omega does not emit" | the doc that must reflect the outcome |
| `docs/06-cookbook.md` traps 11, 20, 21, 26, 27 | null-reads-FALSE, duplicate-header section drop, crypto-only accumulators, timeless timeframes, offset floor |

Key facts already measured (do not re-derive, do not contradict):
- API CREATE request **requires** `operation, intentSummary, assumptions, coinSelection, name, timeframe, sections`; the rules array is called **`rules`** (not `signalRules`); `cadence`/`regimeTimeframe` do not exist in the API; `name` max **50** chars, `intentSummary` 1–2000, `assumptions` ≤20 items × ≤500 chars; `rules` maxItems 84.
- Crypto-only modules among those the presets use: **`CVD` and `FLOW_DIVERGENCE`** — `FLOW_DIVERGENCE` measured directly ("Perp/spot flow data unavailable" on GOOGL/GOLD, doc 12); `CVD` because its metrics are daily-anchored accumulators, null off-crypto (trap 21). `FUNDING` and `OPEN_INTEREST` are **NOT** crypto-only — synthetic perps carry both everywhere.
- `columnLookback` floor is 24, so `offset` ≤ 8 on a `value` column (`data/audit/lookback_floor.json`).
- Duplicate headers inside ONE section silently drop the section from `conditionColumns` — the Task 5 probe must put each offset in its **own section**.
- The `LOOKBACK_FLOOR`, `OFFSET_NOT_HONOURED`, and series-chain validators in `omega/validate.py` are all newer than doc 08's prose; do not "fix" them to match older docs.

---

### Task 0: Re-verify the live schema (execution-day preflight)

**Files:** none modified — this task only confirms the plan's premises.

- [ ] **Step 0.1:** Load the schema: `ToolSearch` with `select:mcp__c330236a-7aee-4d07-ae11-e487c8cbc894__compile_strategy_plan`.
- [ ] **Step 0.2:** Diff the CREATE branch against `API_ACCEPTS` / `API_REQUIRES` in `tests/test_write_surface.py`. If they differ, STOP: update those two sets and `data/audit/write_surface_gap.json` first, in their own commit, then resume.
- [ ] **Step 0.3:** Confirm the `rules[].signalId` enum still has 84 entries and `mcp_result_bytes` / token budgets are unchanged in the tool description. Note any drift in the eventual commit message.

### Task 1: Reshape `wire()` to the CREATE request

**Files:**
- Modify: `omega/generate.py` (`Thesis`, `StrategyPlan.wire()`, `emit_plan`)
- Test: `tests/test_write_surface.py` (existing, flipped), `tests/test_generated_plans_audit.py` (key rename only if it references `signalRules` — grep)

**Interfaces:**
- Produces: `StrategyPlan.wire() -> dict` returning the exact CREATE request body; `Thesis.coin_selection: dict | None` field; `Thesis.resolved_coin_selection() -> dict`.
- Consumes: existing `_map()`, `CADENCE_FOR_ANCHOR`, `REGIME_TF_FOR_ANCHOR` (kept, moved to emit metadata).

- [ ] **Step 1.1: Write the failing tests** — in `tests/test_write_surface.py`, replace the three gap tests with their closed forms:

```python
@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_wire_is_a_complete_create_request(preset):
    """CLOSED 2026-08-XX (was: 3 rejected keys, 4 missing required ones). wire() now
    emits the exact CREATE body. The old pinned-gap form of this test is preserved in
    git history at a233ec0."""
    emitted = set(plan(PRESETS[preset]).wire())
    assert emitted - API_ACCEPTS == set(), "wire() emits keys the API refuses"
    assert API_REQUIRES - emitted == set(), "wire() omits keys the API requires"

def test_rules_is_now_the_name():
    w = plan(PRESETS["trend-continuation"]).wire()
    assert "rules" in w and "signalRules" not in w
    assert len(w["rules"]) == 84

@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_wire_respects_api_bounds(preset):
    w = plan(PRESETS[preset]).wire()
    assert w["operation"] == "CREATE"
    assert len(w["name"]) <= 50
    assert 1 <= len(w["intentSummary"]) <= 2000
    assert 1 <= len(w["assumptions"]) <= 20
    assert all(1 <= len(a) <= 500 for a in w["assumptions"])
    assert w["coinSelection"]["mode"] in ("ranked", "explicit")

def test_coin_selection_default_is_class_aware():
    """CVD and FLOW_DIVERGENCE are crypto-only (doc 12 + trap 21); FUNDING and
    OPEN_INTEREST are NOT - synthetic perps carry both everywhere. A thesis touching a
    crypto-only module must not default to a universe where its columns render null,
    because null reads FALSE (trap 11)."""
    assert plan(PRESETS["mean-reversion"]).wire()["coinSelection"] == {
        "mode": "ranked", "category": "CRYPTO", "limit": 30}      # weights CVD
    assert plan(PRESETS["trend-continuation"]).wire()["coinSelection"] == {
        "mode": "ranked", "category": "ALL", "limit": 30}         # no crypto-only module
```
Keep `test_the_execution_surface_is_still_unmodelled` and `test_plans_are_still_stamped_local_only` unchanged — both must still pass (the 16 execution params stay unemitted; compile-without-apply does not count as submission).

- [ ] **Step 1.2:** Run `python -m pytest tests/test_write_surface.py -q` — expect the new tests to FAIL (wire still emits the old shape).
- [ ] **Step 1.3: Implement.** In `omega/generate.py`:

```python
# Modules whose columns are null outside crypto. FLOW_DIVERGENCE measured directly
# (doc 12: "Perp/spot flow data unavailable" on GOOGL/GOLD); CVD via trap 21 (its
# metrics are daily-00:00-UTC accumulators, absent off-crypto, and null reads FALSE).
# FUNDING and OPEN_INTEREST are deliberately NOT here - synthetic perps carry both.
CRYPTO_ONLY_MODULES = {"CVD", "FLOW_DIVERGENCE"}
```

In `Thesis`: add field `coin_selection: dict | None = None` and:

```python
    def resolved_coin_selection(self) -> dict:
        """Explicit selection wins; otherwise class-aware ranked-30 (see the test)."""
        if self.coin_selection is not None:
            return self.coin_selection
        cat = "CRYPTO" if CRYPTO_ONLY_MODULES & set(self.modules) else "ALL"
        return {"mode": "ranked", "category": cat, "limit": 30}
```

In `StrategyPlan.wire()`: rename `signalRules` → `rules`; delete the `cadence` and `regimeTimeframe` entries; add:

```python
            "operation": "CREATE",
            "intentSummary": (f"{self.thesis.name}: {self.thesis.description} "
                              f"Stance {self.thesis.stance}, gate {self.thesis.gate}. "
                              f"Generated by omega.generate; compile dry-run only.")[:2000],
            "assumptions": self._assumptions(),
            "coinSelection": self.thesis.resolved_coin_selection(),
```

Add `_assumptions()` on `StrategyPlan` (each string ≤500 chars, list ≤20):

```python
    def _assumptions(self) -> list[str]:
        sel = self.thesis.resolved_coin_selection()
        return [
            f"coinSelection {sel} - default is class-aware: CRYPTO when the thesis "
            f"weights a crypto-only module (CVD, FLOW_DIVERGENCE), else ALL",
            "signal params are the platform defaults captured in the signal map",
            "no execution parameters set (stops, trailing, break-even, time decay) - "
            "the execution surface is not yet modelled; platform defaults apply",
            "dry-run: compiled for viability only, never applied",
        ]
```

In `emit_plan`: keep the `LOCAL ONLY` stamp; preserve the dropped info as metadata: `payload["_cadence"] = CADENCE_FOR_ANCHOR[plan_obj.thesis.anchor]` and `payload["_regimeTimeframe"] = REGIME_TF_FOR_ANCHOR[plan_obj.thesis.anchor]` (underscore keys never go to the API; strip `_`-prefixed keys before any submission — say this in a comment).

- [ ] **Step 1.4:** `grep -rn "signalRules\|\"cadence\"\|regimeTimeframe" omega/ scripts/ tests/ docs/` — update every consumer the grep finds (expected: `tests/test_write_surface.py`, possibly `tests/test_generated_plans_audit.py`, doc 08/16 prose handled in Task 6). Nothing may silently keep reading the old key.
- [ ] **Step 1.5:** Update `data/audit/write_surface_gap.json`: inside `keyMismatch` add `"_resolved": {"date": "<execution date>", "how": "wire() reshaped to the CREATE request; signalRules renamed to rules; cadence/regimeTimeframe moved to emit_plan metadata; operation/intentSummary/assumptions/coinSelection now emitted"}` — keep the original lists in place as history. Leave `executionSurfaceNotModelled` untouched.
- [ ] **Step 1.6:** Run the full suite: `python -m pytest -q` — expect ~787 passing, 0 failures.
- [ ] **Step 1.7:** Commit: `Reshape wire() to the CREATE request the write API accepts` (+ co-author line). Push.

### Task 2: Compile dry-run scaffolding (offline half)

**Files:**
- Create: `scripts/compile_dry_run.py`
- Test: none (the script is the harness; its output is verified in Task 3)

**Interfaces:**
- Produces: `python -m scripts.compile_dry_run` prints `{"request": <wire() of trend-continuation>}` as compact JSON for pasting into the tool call; `python -m scripts.compile_dry_run record <result-file>` verifies + records a response.

- [ ] **Step 2.1:** Write `scripts/compile_dry_run.py`:

```python
"""Build, print, and record the first-ever compile of a GENERATED plan.

Print mode emits the exact request body; the executor pastes it into ONE
mcp compile_strategy_plan call. Record mode reads the (possibly file-overflowed)
response, checks it is for OUR payload, and writes it VERBATIM to
data/audit/compile_dry_run_<date>.json with an interpretation stub.

HARD RULES: compile once; never call apply_strategy_plan; a refusal is recorded
exactly like a success. The minted token is left to expire.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from omega.generate import PRESETS, plan

ROOT = Path(__file__).resolve().parents[1]
PRESET = "trend-continuation"   # audit-clean (see scripts/audit_generated_plans.py)

def request() -> dict:
    return {"request": plan(PRESETS[PRESET]).wire()}

def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "record":
        raw = Path(sys.argv[2]).read_text(encoding="utf-8")
        resp = json.loads(raw)
        out = ROOT / "data/audit" / f"compile_dry_run_{sys.argv[3]}.json"
        out.write_text(json.dumps({
            "_what": "First compile of an omega-GENERATED plan. Dry-run: no apply.",
            "preset": PRESET,
            "requestKeys": sorted(request()["request"].keys()),
            "responseVerbatim": resp,
            "_interpretation": "FILL IN: viable? refused? which rule? next action?",
        }, indent=2) + "\n", encoding="utf-8")
        print(f"recorded {out}")
        return 0
    print(json.dumps(request(), separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2.2:** Run `python -m scripts.compile_dry_run` locally; sanity-check the printed JSON has `operation`, `coinSelection`, `rules` (84), and no `_`-prefixed keys. Commit: `Add the compile dry-run harness`.

### Task 3: The live compile (the measurement)

**Files:**
- Create: `data/audit/compile_dry_run_<date>.json`
- Test: `tests/test_compile_dry_run.py`

- [ ] **Step 3.1:** Preflight the account: `get_account_state` / `list_strategies` — confirm quota has a free ACTIVE slot *conceptually* (a CREATE compile pre-allocates an id but commits nothing; if the platform refuses compile on quota grounds, that itself is the finding — record it).
- [ ] **Step 3.2:** Call `mcp__c330236a-...__compile_strategy_plan` ONCE with the printed request. If the result overflows to a file, do NOT read it inline — pass the file to `python -m scripts.compile_dry_run record <file> <date>`.
- [ ] **Step 3.3:** Fill `_interpretation` honestly. Branches:
  - **viable: true** → the generator is proven submit-ready end-to-end. Note `proposedRevision`, the normalized plan echo, and any server rewrites (e.g., `sectionKey: null` → minted keys, as seen in the 2026-08-24 conditions write).
  - **typed refusal** → a rule nobody published. Encode it in `omega/validate.py` (same pattern as the series-chain rule: measured comment + Finding), add a guard test, and decide platform-defect vs omega-gap. If platform-side, it becomes BG-14 in the defects artifact (Task 6).
  - Either way: **no second compile** unless the payload materially changed to fix a refusal — then one more, and say so in the record.
- [ ] **Step 3.4:** Write `tests/test_compile_dry_run.py` pinning what was measured (existence of the record, `requestKeys` matching current `wire()` output so drift fails loudly, and the verdict field being filled — not the string "FILL IN").
- [ ] **Step 3.5:** Full suite green → commit `First compile of a generated plan: <verdict>` → push.

### Task 4: (deliberately absent)

The execution surface (16 parameters) is **out of scope** — it needs the user's design decisions first. See `docs/superpowers/specs/2026-08-27-execution-surface-decisions.md`. Do not model it opportunistically.

### Task 5: `BAR_FORMING` at an offset (closes BG-13's untested entry)

**Files:**
- Modify: `data/audit/offset_ignored.json`, `tests/test_offset_ignored.py`, possibly `omega/validate.py`

- [ ] **Step 5.1:** One `preview_strategy_report` call, 1h anchor, explicit `["BTC","ETH","SOL"]`, **two sections** (never one — duplicate headers drop the section, trap 20): section "f0" columns `[BAR_FORMING×value offset 0, CLOSE×value offset 0]`, section "f8" the same at offset 8 (8 is the max under the 24-bar floor). `CLOSE` is the control: it must differ between sections or the probe is void.
- [ ] **Step 5.2:** Interpret with both branches pre-committed:
  - **BAR_FORMING identical at 0 and 8 while CLOSE moved** → it ignores offset like the other four candle-categoricals. For a "is this bar forming" flag, answering about a *closed* past bar should be `false`, so an unchanging `true`-ish answer is the same defect class. Move it from `scope.untested` to `scope.ignoresOffset` in `offset_ignored.json`; the existing `OFFSET_NOT_HONOURED` warning already covers it (it is candle+vocab) — no validator change.
  - **BAR_FORMING differs** → it honours offset and the warning wrongly fires on it. Add an exemption set `OFFSET_HONOURED_EXCEPTIONS = {"BAR_FORMING"}` in `omega/validate.py` with the measurement in the comment, and update the audit record.
- [ ] **Step 5.3:** Update `tests/test_offset_ignored.py`: the assertion `rec["scope"]["untested"] == ["BAR_FORMING"]` becomes `== []`, plus a test for whichever branch was measured. Suite green → commit → push.

### Task 6: Documentation and artifacts

**Files:**
- Modify: `docs/16-the-write-path.md`, `docs/08-strategy-generation.md`, `README.md`, `data/audit/write_surface_gap.json` (done in 1.5), `artifact/battlegrid-defects.html` (only if Task 3/5 produced a platform defect), `artifact/README.md`

- [ ] **Step 6.1:** Doc 16 § "What omega does not emit": retitle to "What omega emits now — and what it still does not", state the key-mismatch is **closed and measured** (compile verdict, date, one-line result), keep the 16-execution-parameter table as the remaining gap, and remove the "schema-derived, not measured" caveat only if Task 3 actually ran.
- [ ] **Step 6.2:** Doc 08: update the guarantees list ("**submit-shaped** — `wire()` is the exact CREATE request; compiled viable on <date>" or the refusal, whichever happened) and the `coinSelection` default rule with its class-aware rationale.
- [ ] **Step 6.3:** README doc-index lines for 08/16 if their one-liners changed.
- [ ] **Step 6.4:** Artifacts — the three watches died (connection loss), so republish **must pass the `url` parameter** or it forks a new page (URLs + favicons are in `artifact/README.md`: defects `a0ed53c1-...` 🐛, column-algebra `877253ff-...` 🧮). Republish the defects page only if BG-14 or a BAR_FORMING scope change landed; record any favicon/URL rows touched in `artifact/README.md`.
- [ ] **Step 6.5:** Full suite, commit `Document the compile bridge outcome`, push.

## Execution log — 2026-08-28 (all tasks run; corrections dated, not silent)

- **Task 0:** zero drift. The live CREATE schema matched `API_ACCEPTS` (30 keys),
  `API_REQUIRES` (7), the 84-entry signalId enum, and every bound this plan pinned.
- **Task 1:** done as written, except the grep found the old-key consumer to be
  `tests/test_generate.py`, not `tests/test_generated_plans_audit.py` as guessed above —
  updated in the same commit. Suite 782 → 788.
- **Task 3:** two compiles, the plan's cap, **both refused** — neither for the key
  mismatch this plan closed. (1) `REPORT_CUSTOM_SECTION_NOT_OWNED`: CREATE accepts no
  client `sectionKey` (allowedDomain enum []) — omega gap, fixed in `wire()` same day.
  (2) `mcp_result_bytes 395404 > 256000`: the plan-cap is enforced against the compile's
  own preview across coinSelection ranked/ALL/30 — platform doc/behaviour mismatch,
  filed as **BG-14**. Deviation from step 3.3's letter: neither rule was encoded in
  `omega/validate.py` — rule 1 lives in `wire()` by construction plus a guard test
  (better home than a column validator), and rule 2 is not honestly encodable from one
  data point (cannot separate per-coin scaling from fixed overhead); it is pinned in
  `tests/test_compile_dry_run.py` and recorded in the audit files instead. Viability
  remains unproven; next compile needs a materially smaller preview footprint.
- **Task 5:** BAR_FORMING **ignores offset** (branch 1): "forming" at offsets 0 and 8 on
  all of BTC/ETH/SOL while CLOSE moved. `scope.untested` now empty; no validator change.
- **Task 6:** docs 08/16, README index lines, `artifact/README.md` updated; defects page
  republished to the same URL (🐛) with BG-14 and the BG-13 closure — fourteen findings.
- **Addendum, 2026-08-28 (user-authorized, beyond the plan's two-compile cap):** one
  further compile of the identical plan at an explicit BTC/ETH/SOL selection — the only
  fields changed from the refused payload were `coinSelection` and its assumption
  string — returned **`viable: true`**: the first generated plan ever to compile
  viable. BG-14's workaround confirmed at that size (cap boundary still unmeasured);
  server-minted sectionKeys, server-derived cadence/regimeTimeframe (matching omega's
  1h mapping), read-back `signalRules`, absent postState `coinSelection`, and the
  16 non-blocking advisories all recorded in
  `data/audit/compile_dry_run_2026-08-28-small.json` (planToken redacted to
  length+sha256). Token left to expire; nothing applied.

## Self-review checklist (run before calling the plan done)

- Every live response recorded verbatim in `data/audit/` before interpretation?
- `apply_strategy_plan` never called; exactly ≤2 compile calls total, second only after a material payload fix?
- All pinned tests flipped in the same commit as the code they pin?
- Docs/artifacts state what was **measured**, with "schema-derived" caveats removed only where a live call replaced them?
- Anything the plan asserted that execution contradicted → corrected in the plan's own file with a dated note, not silently.
