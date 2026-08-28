# Measurement Campaign — Full-Menu Surface — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Measure everything the "full menu" assistant surface depends on — platform behaviour at all 11 unmeasured anchors, the BG-14 ranked-universe cap boundary, and the two unprobed bounds edges — and fold every measured value into omega, so the assistant phase starts with zero known-unmeasured ground it would stand on.

**Architecture:** Pure measurement, then build-from-measurement. One probe = one compile with exactly ONE field changed from a known body, so every verdict is attributable. Three probe families (anchors / cap / bounds) feed three build steps (widen the anchor model, encode the cap boundary, settle the bounds severities). **This plan contains ZERO `apply_strategy_plan` calls** — nothing is created, nothing binds, nothing deploys; every minted token is left to expire.

**Tech Stack:** Python 3 (stdlib + pydantic via omega.types), pytest, the BattleGrid MCP connector (`mcp__c330236a-…`), git.

## Global Constraints

- **Compile budget: at most 20 `compile_strategy_plan` calls, authorized once at kickoff** (user's decision 2026-08-28: "One campaign, ≤20 compiles"). Family sub-budgets: anchors exactly 11 (Task 2), cap at most 6 (Task 4), bounds exactly 2 (Task 5), plus 1 contingency usable in any family ONLY for a material, fixable refusal (e.g. transport error) — say so in the record. Never re-compile a success.
- **NO `apply_strategy_plan` in this plan. NEVER bind anything to an agent. NEVER create radar or arena deployments.** Standing rules; no general "go ahead" authorises any of them.
- **Record every live response verbatim into `data/audit/` before interpreting it.** A refusal is a finding, not a failure. **Redact `planToken`** to `{length, sha256}` (pattern: `compile_dry_run_2026-08-28-small.json`). Every token is left to expire.
- **State every prediction BEFORE measuring; a failed prediction is a finding.** Where omega has no prior (most anchors' cadence), record "no prior — unmeasured", never a guess. Corrections to omega happen in the same commit as the record that proves them; contradictions of THIS plan get a dated note in this file — never silent.
- **Re-verify the live compile schema before any compile** (Task 0). Cached capability lists are not authoritative after a deployment.
- Baseline: `main` at `f5e8510`, **828 tests passing**. Run `python -m pytest -q` before every commit; commit messages end with the Claude co-author line.
- Windows: write files with Write/Edit tools, not shell heredocs, for anything committed. Large MCP results overflow to a file — verify by script (python/jq), never by eye.
- MCP compile calls are made by the EXECUTOR (the session), not by scripts: the harness prints exact bodies; the executor pastes ONE body per call and records the response (overflow file → record modes).

## Context an executor needs (read these first)

| file | why |
|---|---|
| `docs/superpowers/specs/2026-08-28-assistant-phase-decisions.md` | the four decisions this campaign serves; Decision 3 ("full menu") forces it |
| `data/audit/compile_dry_run_2026-08-28-small.json` | the known-viable small body every probe derives from |
| `data/audit/compile_dry_run_2026-08-28.json` | the BG-14 refusal: ranked/ALL/30 preview measured **395,404 > 256,000** — the cap family's first datapoint, already paid for |
| `data/audit/bounds_probe_2026-08-28.json` | Probe A: R:R **upper** edge enforced at input validation ("must be <= 3"); the pattern the new bounds probes follow |
| `data/audit/defaults_4h_probe_2026-08-28.json` | defaults identical at 1h/4h; the cadence prediction that FAILED (SWING, not INTRADAY) — why this plan never guesses cadence |
| `scripts/compile_dry_run.py` | the probe harness Task 1 extends |
| `omega/types.py` (`ANCHOR_TIMEFRAMES`, `Report.anchor`) | the 4-anchor Literal Task 3 widens FROM MEASUREMENT |
| `omega/generate.py` (`CADENCE_FOR_ANCHOR`, `REGIME_TF_FOR_ANCHOR`, `resolved_coin_selection`, `critique`) | maps and defaults Tasks 3–4 extend |
| `omega/execution.py` (`CATALOG_BOUNDS`, `validate_execution`) | the severity Task 5's verdicts may change |

Key measured facts (do not re-derive, do not contradict):

- The compile CREATE `timeframe` enum (live, re-verified 2026-08-28): `1m 3m 5m 15m 30m 1h 2h 4h 8h 12h 1d 3d 1w` — 13 values. Measured: **1h** (viable; INTRADAY/4h) and **4h** (viable; SWING/1d). **Unmeasured: the other 11.**
- `omega.types.ANCHOR_TIMEFRAMES` is `Literal["5m","15m","1h","4h"]` — omega cannot even EXPRESS the other 9 anchors today. Whether the platform accepts them for a CREATE is exactly what Task 2 measures; the Literal is widened only afterward, only to the anchors that proved creatable.
- The 16 execution defaults measured identical at 1h and 4h. Prediction for Task 2 (stated here, before measuring): identical at every anchor. A deviation is a finding with a pre-committed branch (Task 3 Step 3.4).
- Cadence priors: 15m → SCALPER (every live 15m strategy) and 5m → SCALPER (omega's map only — NEVER verified against the server). No prior exists for 1m/3m/30m/2h/8h/12h/1d/3d/1w. regimeTimeframe priors: 5m/15m → "1h" (map only). The 4h probe proved these maps CAN be wrong — priors are predictions, not facts.
- BG-14: the 256,000-byte cap binds the compile's internal report preview. Refusal messages name the measured size (`"… 395404 > 256000"`) — every cap refusal is a free datapoint. The boundary is **report-relative**: it was and will be measured FOR the trend-continuation report shape (11 custom columns); a wider report refuses earlier.
- Bounds: R:R upper edge (3) proven enforced at the connector's input-validation layer, below the published schema. R:R lower edge (catalog 0.5) and minAtrPct (catalog 0.1–10 vs schema 0.01–50) are UNPROBED — Task 5 settles both.
- Quota is 24/25 with 1 free — irrelevant here (no applies), checked in preflight only so any drift is on record.

---

### Task 0: Execution-day preflight

**Files:** none modified.

- [ ] **Step 0.1:** Ensure an isolated workspace (superpowers:using-git-worktrees): fresh worktree/branch cut from current `origin/main` (`git fetch origin` first; expect `f5e8510` or a descendant). `python -m pytest -q` → **828 passed** (reconcile any drift before proceeding — it means main moved; read the new commits).
- [ ] **Step 0.2:** `ToolSearch` `select:mcp__c330236a-7aee-4d07-ae11-e487c8cbc894__compile_strategy_plan`. Diff by script (pattern: the 2026-08-28 preflight): the CREATE branch's key set vs `API_ACCEPTS`/`API_REQUIRES` in `tests/test_write_surface.py`, the numeric bounds vs `SCHEMA_BOUNDS` in `omega/execution.py`, and the `timeframe` enum vs the 13 values in Key facts. Any drift → STOP, update the pinned sets in their own commit first.
- [ ] **Step 0.3:** `list_strategies` — note quota verbatim in the Task 2 commit message if ≠ 24/25. Confirm the kickoff prompt authorizes the ≤20-compile budget in the user's own words; absent → STOP and ask.

### Task 1: Probe harness — one-changed-field by construction

**Files:**
- Modify: `scripts/compile_dry_run.py`
- Test: `tests/test_compile_dry_run.py` (append)

**Interfaces:**
- Produces: `probe(field: str, value, base: str = "small") -> dict` — the known body (`base="small"`: explicit BTC/ETH/SOL viable body; `base="full"`: the ranked/ALL/30 body) with exactly one top-level field replaced. `_redact(resp: dict) -> dict` — in-place planToken redaction, shared by all record modes. CLI modes `tf <anchor>`, `ranked <limit> [category]`, `rrlow <value>`, `atr <value>`, `record-into <respfile> <key> <auditfile>`.

- [ ] **Step 1.1: Write the failing tests** — append to `tests/test_compile_dry_run.py`:

```python
# --- the 2026-08-28 measurement-campaign harness --------------------------------

def test_probe_changes_exactly_one_field_from_the_small_body():
    from scripts.compile_dry_run import probe
    base = request(small=True)["request"]
    p = probe("timeframe", "2h")["request"]
    assert {k for k in set(base) | set(p) if base.get(k) != p.get(k)} == {"timeframe"}
    assert p["timeframe"] == "2h"


def test_probe_full_base_is_the_ranked_body():
    from scripts.compile_dry_run import probe
    base = request()["request"]
    sel = {"mode": "ranked", "category": "ALL", "limit": 19}
    p = probe("coinSelection", sel, base="full")["request"]
    assert {k for k in set(base) | set(p) if base.get(k) != p.get(k)} == {"coinSelection"}
    assert p["coinSelection"] == sel


def test_redact_replaces_the_token_with_length_and_sha256():
    import hashlib
    from scripts.compile_dry_run import _redact
    resp = {"planToken": "tok123", "other": 1}
    _redact(resp)
    assert resp["planToken"]["length"] == 6
    assert resp["planToken"]["sha256"] == hashlib.sha256(b"tok123").hexdigest()
    assert resp["other"] == 1
```

- [ ] **Step 1.2:** Run `python -m pytest tests/test_compile_dry_run.py -q` — expect FAIL (`probe`/`_redact` not defined).
- [ ] **Step 1.3: Implement.** In `scripts/compile_dry_run.py`: extract the existing record-mode redaction into `_redact`, add `probe`, add the modes. The existing `request`, `small`/`bounds`/`tf4h`/`record` modes stay byte-identical (pinned tests reference them).

```python
# The compile CREATE timeframe enum, re-verified live in this campaign's preflight.
ALL_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "3d", "1w"]


def _redact(resp: dict) -> dict:
    if isinstance(resp.get("planToken"), str):
        t = resp["planToken"]
        resp["planToken"] = {"_redacted": "credential-bound 5-minute token, left to "
                                          "expire; never applied",
                             "length": len(t),
                             "sha256": hashlib.sha256(t.encode()).hexdigest()}
    return resp


def probe(field: str, value, base: str = "small") -> dict:
    """A known body with exactly ONE top-level field replaced - one variable per
    compile keeps every verdict attributable. base="small": the viable explicit
    BTC/ETH/SOL body. base="full": the ranked/ALL/30 body (the BG-14 refusal's
    payload - the cap family's own baseline)."""
    req = request(small=(base == "small"))["request"]
    req[field] = value
    return {"request": req}
```

In `main()`, replace the record-mode inline redaction with `_redact(resp)` and add before the final fallback:

```python
    if len(sys.argv) > 2 and sys.argv[1] == "tf":
        assert sys.argv[2] in ALL_TIMEFRAMES, f"not a platform timeframe: {sys.argv[2]}"
        print(json.dumps(probe("timeframe", sys.argv[2]), separators=(",", ":")))
        return 0
    if len(sys.argv) > 2 and sys.argv[1] == "ranked":
        sel = {"mode": "ranked",
               "category": sys.argv[3] if len(sys.argv) > 3 else "ALL",
               "limit": int(sys.argv[2])}
        print(json.dumps(probe("coinSelection", sel, base="full"), separators=(",", ":")))
        return 0
    if len(sys.argv) > 2 and sys.argv[1] == "rrlow":
        print(json.dumps(probe("minRiskRewardRatio", float(sys.argv[2])), separators=(",", ":")))
        return 0
    if len(sys.argv) > 2 and sys.argv[1] == "atr":
        print(json.dumps(probe("minAtrPct", float(sys.argv[2])), separators=(",", ":")))
        return 0
    if len(sys.argv) > 4 and sys.argv[1] == "record-into":
        # record-into <respfile> <key> <auditfile>: redact and append one probe
        # response under "probes"[key] in data/audit/<auditfile>, creating the file
        # with an empty scaffold if absent. Verbatim-before-interpretation.
        resp = _redact(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
        out = ROOT / "data/audit" / sys.argv[4]
        doc = (json.loads(out.read_text(encoding="utf-8")) if out.exists()
               else {"_what": "FILL IN", "probes": {}, "_interpretation": "FILL IN"})
        doc["probes"][sys.argv[3]] = resp
        out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(f"recorded probes[{sys.argv[3]}] -> {out}")
        return 0
```

- [ ] **Step 1.4:** `python -m pytest -q` — all green (existing 828 + 3 new = 831). Commit `Probe harness: one-changed-field probes, shared redaction` → push.

### Task 2: Anchor sweep — 11 compiles, verbatim, no model changes yet

**Files:**
- Create: `data/audit/anchor_sweep_2026-XX-XX.json` (execution date; ONE file, all 11 responses under `probes`)
- Test: `tests/test_anchor_sweep.py` (new)

**Interfaces:**
- Produces: the sweep record — `{"probes": {"<anchor>": <verbatim redacted response-or-error>}, "extract": {"<anchor>": {"viable": bool, "cadence": str|null, "regimeTimeframe": str|null, "defaultsIdentical": bool|null}}, ...}` — which Tasks 3 and 6 consume.

**Predictions (stated now, before any call):** every viable anchor's 16 defaults equal `PLATFORM_EXECUTION_DEFAULTS`; 15m cadence SCALPER (live-strategy prior), 5m cadence SCALPER and 5m/15m regimeTimeframe "1h" (omega-map prior only); **all other anchors: no prior — whatever comes back is the first measurement.** Any anchor may be refused outright; a refusal is a finding that the anchor is not creatable, and it is excluded from Task 3's widening.

- [ ] **Step 2.1:** For each anchor in `1m 3m 5m 15m 30m 2h 8h 12h 1d 3d 1w` (exactly 11 — 1h and 4h are measured; do NOT respend them): `python -m scripts.compile_dry_run tf <anchor>` → sanity-check by script that only `timeframe` differs from the small body → ONE `compile_strategy_plan` call with the printed body → save the response (overflow file, or paste an inline error verbatim into a scratch file) → `python -m scripts.compile_dry_run record-into <respfile> <anchor> anchor_sweep_2026-XX-XX.json`. Record refusals exactly like successes. 11 calls total, no retries without the contingency justification.
- [ ] **Step 2.2:** Fill the record's `_what` (what was probed, from which base body, predictions restated) and build `extract` by script from `probes`: viable flag, `postState.cadence`, `postState.regimeTimeframe`, and `defaultsIdentical` = (the 16 postState values == `PLATFORM_EXECUTION_DEFAULTS`); `null`s for refused anchors. Fill `_interpretation` honestly — including which predictions held and which had no prior.
- [ ] **Step 2.3: Pin it** — `tests/test_anchor_sweep.py`:

```python
"""The 2026-XX-XX anchor sweep: 11 unmeasured platform timeframes, one compile each,
recorded verbatim. Priors existed only for 5m/15m (SCALPER, map-only) - everything
else was measured blind, which is the point."""
import json
from pathlib import Path

from omega.execution import PLATFORM_EXECUTION_DEFAULTS

ROOT = Path(__file__).resolve().parents[1]
SWEEP = json.loads(
    (ROOT / "data/audit/anchor_sweep_2026-XX-XX.json").read_text(encoding="utf-8"))
SWEPT = ["1m", "3m", "5m", "15m", "30m", "2h", "8h", "12h", "1d", "3d", "1w"]


def test_all_eleven_anchors_are_recorded_and_interpreted():
    assert sorted(SWEEP["probes"]) == sorted(SWEPT)
    assert sorted(SWEEP["extract"]) == sorted(SWEPT)
    assert "FILL IN" not in SWEEP["_what"] and "FILL IN" not in SWEEP["_interpretation"]


def test_the_extract_matches_the_verbatim_probes():
    for anchor, ex in SWEEP["extract"].items():
        resp = SWEEP["probes"][anchor]
        ap = resp.get("approvedPlan")
        if ex["viable"]:
            ps = ap["postState"]
            assert ap["viability"]["viable"] is True
            assert ps["timeframe"] == anchor
            assert ex["cadence"] == ps["cadence"]
            assert ex["regimeTimeframe"] == ps["regimeTimeframe"]
            assert ex["defaultsIdentical"] == (
                {k: ps[k] for k in PLATFORM_EXECUTION_DEFAULTS}
                == PLATFORM_EXECUTION_DEFAULTS)
        else:
            assert ap is None or ap["viability"]["viable"] is False


def test_every_viable_probe_has_a_redacted_token():
    for resp in SWEEP["probes"].values():
        tok = resp.get("planToken")
        if tok is not None:
            assert set(tok) == {"_redacted", "length", "sha256"}
```

- [ ] **Step 2.4:** `python -m pytest -q` — green. Commit `Anchor sweep: <n> viable, <m> refused, defaults <identical|VARY - see record>` → push. If ANY viable anchor's defaults are NOT identical, also add a dated note to THIS plan file naming the anchor and the differing values (Task 3 Step 3.4 consumes it).

### Task 3: Widen the anchor model to exactly what measured

**Files:**
- Modify: `omega/types.py` (`ANCHOR_TIMEFRAMES`), `omega/generate.py` (`CADENCE_FOR_ANCHOR`, `REGIME_TF_FOR_ANCHOR` + their provenance comment)
- Test: `tests/test_anchor_sweep.py` (append)

**Interfaces:**
- Consumes: `SWEEP["extract"]` from Task 2.
- Produces: `ANCHOR_TIMEFRAMES` = the measured-creatable set; both maps defined for exactly that set with measured values.

- [ ] **Step 3.1: Write the failing tests** — append to `tests/test_anchor_sweep.py`:

```python
def test_the_anchor_literal_is_exactly_the_measured_creatable_set():
    from typing import get_args
    from omega.types import ANCHOR_TIMEFRAMES
    measured = {"1h", "4h"} | {a for a, ex in SWEEP["extract"].items() if ex["viable"]}
    assert set(get_args(ANCHOR_TIMEFRAMES)) == measured


def test_the_maps_cover_the_literal_with_measured_values_only():
    from typing import get_args
    from omega.generate import CADENCE_FOR_ANCHOR, REGIME_TF_FOR_ANCHOR
    from omega.types import ANCHOR_TIMEFRAMES
    anchors = set(get_args(ANCHOR_TIMEFRAMES))
    assert set(CADENCE_FOR_ANCHOR) == set(REGIME_TF_FOR_ANCHOR) == anchors
    for a, ex in SWEEP["extract"].items():
        if ex["viable"]:
            assert CADENCE_FOR_ANCHOR[a] == ex["cadence"]
            assert REGIME_TF_FOR_ANCHOR[a] == ex["regimeTimeframe"]


def test_emit_plan_works_at_every_measured_anchor():
    from dataclasses import replace
    from typing import get_args
    from omega.generate import PRESETS, emit_plan, plan
    from omega.types import ANCHOR_TIMEFRAMES
    for a in get_args(ANCHOR_TIMEFRAMES):
        t = replace(PRESETS["trend-continuation"], anchor=a,
                    coin_selection={"mode": "explicit", "tickers": ["BTC"]})
        emit_plan(plan(t), f"sweep-{a}", out_dir=None)  # must not raise
```

(Adapt the `emit_plan` call to its real signature — it writes a file; use a tmp_path fixture as `out_dir` if it requires a real directory. The intent is: no KeyError at any measured anchor.)
- [ ] **Step 3.2:** Run them — expect FAIL (Literal too narrow, maps incomplete).
- [ ] **Step 3.3: Implement:** widen `ANCHOR_TIMEFRAMES` to the measured-creatable set (in the enum's canonical order), extend both maps with the sweep's measured values, and rewrite the provenance comment to cite `anchor_sweep_2026-XX-XX.json` per anchor (keeping the note that 4h once falsified a guessed cadence). Refused anchors stay OUT of the Literal, with a comment naming them and the record.
- [ ] **Step 3.4 (branch, only if a viable anchor's defaults differed):** reshape `PLATFORM_EXECUTION_DEFAULTS` to `{anchor: {...16...}}` keyed by measured anchors ONLY (the previous plan's pre-committed contingency shape), update `omega/execution.py` consumers (`EXECUTION_PARAMS` derives from the 1h entry; `critique`'s effective-profile lookup takes the thesis anchor), and adjust `tests/test_execution.py` lookups. If defaults were identical everywhere (the prediction), this step is a no-op — say so in the commit message.
- [ ] **Step 3.5:** Full suite — if any pre-existing test pinned the 4-anchor Literal, flip it in this commit with a CLOSED-dated docstring (grep `ANCHOR_TIMEFRAMES` and `"5m", "15m", "1h", "4h"` across `tests/`). Commit `Widen the anchor model to the measured set` → push.

### Task 4: The BG-14 cap boundary — ≤6 compiles, model-guided search

**Files:**
- Create: `data/audit/cap_boundary_2026-XX-XX.json`
- Modify: `omega/generate.py` (`RANKED_LIMIT_MEASURED_MAX`, `resolved_coin_selection`, `critique`), `tests/test_write_surface.py` (flip `test_coin_selection_default_is_class_aware`)
- Test: `tests/test_cap_boundary.py` (new)

**Interfaces:**
- Produces: `RANKED_LIMIT_MEASURED_MAX: int` in `omega/generate.py`; ranked defaults capped to it; a critique warning for ranked limits above it.

**Prediction (stated now):** preview bytes ≈ linear in coin count. One datapoint exists (395,404 @ ranked/ALL/30 → ~13,180/coin) → predicted boundary **19**. The linearity itself is unmeasured — the search corrects the model with every refusal, because refusal messages carry the measured size.

- [ ] **Step 4.1: Search loop (≤5 calls on ranked/ALL).** Maintain `L_viable` (largest limit that compiled; starts unknown) and `L_refused` (smallest refused; starts 30, from the already-paid BG-14 datapoint — do NOT respend it). First probe: limit **19**. After each call: if refused, parse the measured bytes from the message, refit the linear model on all refusal datapoints, next probe = the refit's predicted boundary (clamped inside the open bracket); if viable, next probe = midpoint of (that limit, L_refused). Every response → `record-into <respfile> ALL-<limit> cap_boundary_2026-XX-XX.json`. STOP when `L_refused == L_viable + 1` (exact boundary) or the 5 calls are spent (record the honest bracket instead — "boundary in [L_viable+1, L_refused]", never a point estimate).
- [ ] **Step 4.2 (1 call): category transfer check.** `ranked L_viable CRYPTO` → one compile, recorded under key `CRYPTO-<limit>`. Viable → the ALL boundary transfers to CRYPTO at least at `L_viable`; refused → category-dependence is REAL, record the CRYPTO refusal's bytes, and the record's `_honestLimits` must say the boundary is per-category and only ALL was bracketed. (If Step 4.1 found no viable limit at all — possible if even small ranked previews blow the cap — spend this call on `ranked 5 ALL` instead and say so.)
- [ ] **Step 4.2b (pre-committed escape):** if after all cap calls ZERO ranked limit compiled viable, do NOT invent a `RANKED_LIMIT_MEASURED_MAX` and do NOT change the defaults — record the refusals, add a dated note to THIS plan file ("ranked universes unusable at any measured size for this report shape"), skip Steps 4.4's code changes entirely, and STOP after committing the record: that outcome invalidates part of the full-menu decision and the user must re-decide (Decision 3 revisit).
- [ ] **Step 4.3:** Fill `_what` / `_interpretation` / `_honestLimits` (report-relative caveat verbatim: "measured FOR the trend-continuation report shape — 11 custom columns; a wider report refuses earlier"). Write the failing tests — `tests/test_cap_boundary.py`:

```python
"""BG-14's missing number: the largest ranked selection whose compile preview fits
the 256,000-byte cap - measured 2026-XX-XX by model-guided search, for the
trend-continuation report shape. Report-relative: a wider report refuses earlier."""
import json
from pathlib import Path

from omega.generate import RANKED_LIMIT_MEASURED_MAX, PRESETS, plan

ROOT = Path(__file__).resolve().parents[1]
CAP = json.loads(
    (ROOT / "data/audit/cap_boundary_2026-XX-XX.json").read_text(encoding="utf-8"))


def test_the_boundary_matches_the_record():
    assert RANKED_LIMIT_MEASURED_MAX == CAP["boundary"]["largestViableLimit"]
    assert "FILL IN" not in CAP["_interpretation"]
    assert "report" in " ".join(CAP["_honestLimits"]).lower()


def test_the_bracket_is_proven_by_adjacent_probes_or_declared_open():
    b = CAP["boundary"]
    if b["exact"]:
        assert f"ALL-{b['largestViableLimit']}" in CAP["probes"]
        assert f"ALL-{b['smallestRefusedLimit']}" in CAP["probes"]
        assert b["smallestRefusedLimit"] == b["largestViableLimit"] + 1
    else:
        assert b["smallestRefusedLimit"] > b["largestViableLimit"] + 1


def test_ranked_defaults_now_fit_the_measured_boundary():
    for preset in PRESETS:
        sel = plan(PRESETS[preset]).wire()["coinSelection"]
        if sel["mode"] == "ranked":
            assert sel["limit"] <= RANKED_LIMIT_MEASURED_MAX


def test_an_oversized_ranked_selection_draws_a_critique_warning():
    from dataclasses import replace
    t = replace(PRESETS["trend-continuation"],
                coin_selection={"mode": "ranked", "category": "ALL",
                                "limit": RANKED_LIMIT_MEASURED_MAX + 5})
    text = " ".join(plan(t).critique())
    assert "BG-14" in text and str(RANKED_LIMIT_MEASURED_MAX) in text
```

(The record's `boundary` object: `{"largestViableLimit": int, "smallestRefusedLimit": int, "exact": bool}`.)
- [ ] **Step 4.4: Implement.** In `omega/generate.py`:

```python
# Measured 2026-XX-XX (cap_boundary_2026-XX-XX.json): the largest ranked selection
# whose compile preview fits BG-14's 256,000-byte cap, FOR THE TREND-CONTINUATION
# REPORT SHAPE (11 custom columns). Report-relative - a wider report refuses
# earlier. The compile is the authority; this number only steers defaults and
# warnings.
RANKED_LIMIT_MEASURED_MAX = <the measured largestViableLimit>
```

`resolved_coin_selection`: the derived default becomes `{"mode": "ranked", "category": cat, "limit": min(30, RANKED_LIMIT_MEASURED_MAX)}`. **This is a deliberate behavioral change** — doc 08 guarantees "compile-viable", and a default that cannot compile breaks that guarantee; the old limit 30 is preserved in git history and the flipped test. In `critique()`, after the execution block, append:

```python
        sel = self.thesis.resolved_coin_selection()
        if sel.get("mode") == "ranked" and sel.get("limit", 0) > RANKED_LIMIT_MEASURED_MAX:
            out.append(
                f"coinSelection warning: ranked limit {sel['limit']} exceeds the measured "
                f"compile-preview boundary {RANKED_LIMIT_MEASURED_MAX} (BG-14) - expect a "
                f"byte-cap refusal (measured for the trend-continuation report shape; "
                f"wider reports refuse earlier)")
```

Flip `test_coin_selection_default_is_class_aware` in `tests/test_write_surface.py` IN THIS COMMIT: same class-aware categories, limits now `min(30, RANKED_LIMIT_MEASURED_MAX)`, docstring gains "limit capped to the measured BG-14 boundary, 2026-XX-XX".
- [ ] **Step 4.5:** Full suite green → commit `Measure the BG-14 boundary: ranked limit <N><, or bracket>` → push.

### Task 5: Bounds edges — 2 compiles, both branches pre-committed

**Files:**
- Create: `data/audit/bounds_edges_2026-XX-XX.json`
- Modify: `omega/execution.py` (comments always; code only per the ATR branch), `tests/test_execution.py` (only per the ATR branch)
- Test: `tests/test_bounds_edges.py` (new)

**Predictions (stated now):** both refused at the input-validation layer naming the catalog edge (consistent with Probe A's upper-edge finding) — R:R 0.3 → "must be >= 0.5", minAtrPct 0.05 → "must be >= 0.1". Either outcome is a finding.

- [ ] **Step 5.1:** `python -m scripts.compile_dry_run rrlow 0.3` → verify one-changed-field by script → ONE compile → `record-into <respfile> rr-0.3 bounds_edges_2026-XX-XX.json`. Then `atr 0.05` → verify → ONE compile → `record-into <respfile> atr-0.05 …`. (0.05 is legal per the published schema's 0.01–50 — that is what makes the probe informative.) Tokens, if any minted, are left to expire.
- [ ] **Step 5.2: Interpret, per pre-committed branches.**
  - **R:R 0.3 refused naming the edge** → lower edge enforced; `CATALOG_BOUNDS` comment in `omega/execution.py` updated to "both R:R edges measured enforced"; no code change. **R:R 0.3 viable** → asymmetric enforcement: in `validate_execution`, the `minRiskRewardRatio` catalog check becomes error ONLY above the upper edge and a warning below the lower edge, each message citing its measurement date; add a matching case to `tests/test_execution.py::test_override_validation`.
  - **minAtrPct 0.05 refused naming the edge** → catalog enforced for ATR too; comment update only. **minAtrPct 0.05 viable with `postState.minAtrPct == 0.05`** → schema governs ATR: in `validate_execution`, `minAtrPct`'s catalog finding becomes `"warning"` (legal on the write, outside the agent catalog), citing the record; adjust `tests/test_execution.py` accordingly. **Viable but postState ≠ 0.05** → silent clamp: a NEW platform defect (BG-15 candidate) — record both numbers, and Task 6 gains the defects-artifact addendum.
- [ ] **Step 5.3: Pin** — `tests/test_bounds_edges.py`:

```python
"""The two bounds edges Probe A left unprobed, measured 2026-XX-XX: the R:R lower
edge and minAtrPct's catalog-vs-schema conflict. One changed field per compile."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDGES = json.loads(
    (ROOT / "data/audit/bounds_edges_2026-XX-XX.json").read_text(encoding="utf-8"))


def test_both_probes_are_recorded_with_verdicts():
    assert set(EDGES["probes"]) == {"rr-0.3", "atr-0.05"}
    assert "FILL IN" not in EDGES["_interpretation"]
    for key in ("rrLowerEdge", "minAtrPct"):
        assert EDGES["verdicts"][key] in (
            "ENFORCED", "NOT_ENFORCED_SCHEMA_GOVERNS", "SILENT_CLAMP")


def test_the_code_severity_matches_the_measured_verdict():
    from omega.execution import validate_execution
    atr = [f for f in validate_execution({"minAtrPct": 0.05})]
    if EDGES["verdicts"]["minAtrPct"] == "NOT_ENFORCED_SCHEMA_GOVERNS":
        assert atr and all(f.severity == "warning" for f in atr)
    else:
        assert any(f.severity == "error" for f in atr)
    rr = [f for f in validate_execution({"minRiskRewardRatio": 0.3})]
    if EDGES["verdicts"]["rrLowerEdge"] == "NOT_ENFORCED_SCHEMA_GOVERNS":
        assert rr and all(f.severity == "warning" for f in rr)
    else:
        assert any(f.severity == "error" for f in rr)
```

(The record carries `verdicts: {rrLowerEdge, minAtrPct}` filled from the measured branch.)
- [ ] **Step 5.4:** Full suite green → commit `Bounds edges: R:R lower <verdict>, minAtrPct <verdict>` → push.

### Task 6: Documentation and the defects artifact

**Files:**
- Modify: `docs/16-the-write-path.md`, `docs/08-strategy-generation.md`, `README.md`, `docs/superpowers/specs/2026-08-28-assistant-phase-decisions.md`; `artifact/battlegrid-defects.html` + `artifact/README.md` (BG-14 boundary addendum always; BG-15 article ONLY if Task 5 measured a silent clamp).

- [ ] **Step 6.1:** Doc 16: in the BG-14/compile section, add the measured boundary sentence (number or bracket, the report-relative caveat verbatim); in the anchors/cadence material, replace "confirmed at 1h only" with the sweep's coverage (a small anchor→cadence/regime table sourced from the record). Doc 08: the "compile-viable" guarantee line gains "ranked defaults capped to the measured BG-14 boundary"; the execution-transparent line gains the bounds-edge verdicts if the severities changed.
- [ ] **Step 6.2:** Spec `2026-08-28-assistant-phase-decisions.md`: mark the measurement-campaign item **EXECUTED <date>** with one line per family verdict. README masthead: one sentence — the full-menu surface is measured (anchors count, boundary, bounds) — and index one-liners for 08/16 if their claims changed.
- [ ] **Step 6.3:** Defects artifact: update the BG-14 article with the measured boundary (and the per-category note from Step 4.2); add BG-15 (summary row + article, masthead count bump) ONLY if the silent-clamp branch fired. Republish to `https://claude.ai/code/artifact/a0ed53c1-f6d3-4abf-9225-c4abf3dfd71a` with favicon 🐛; note the republish in `artifact/README.md`.
- [ ] **Step 6.4:** Full suite → commit `Document the measured full-menu surface` → push.

### Task 7: Finish

- [ ] **Step 7.1:** Full suite one last time; reconcile the test count in this plan's baseline note with a dated line (828 + Task-by-task additions).
- [ ] **Step 7.2:** Compile-call audit against the budget: count every `compile_strategy_plan` actually made (grep the audit records), assert ≤20 and per-family caps honoured, state the count in the final commit message.
- [ ] **Step 7.3:** Integrate to `main`: `git fetch origin && git merge-base --is-ancestor origin/main HEAD && git push origin HEAD:main` — STOP on non-fast-forward, surface to the user.
- [ ] **Step 7.4:** Update memory (`next-session-compile-bridge.md` or successor): campaign executed, per-family verdicts, what the assistant phase may now rely on, and the roadmap remainder (UPDATE-for-generated-plans, then the assistant brainstorm). Binding/deployment stay user-gated, always.
- [ ] **Step 7.5:** Final report to the user: the anchor table (cadence/regime/defaults per anchor, refusals named), the boundary (or bracket) with its caveat, both bounds verdicts, prediction outcomes (held/failed/no-prior), budget actually spent, and any plan corrections made along the way.

## Deliberately absent from this plan

- **Any `apply_strategy_plan` call** — nothing here needs a write; the campaign is compile-only.
- **The 72 unmeasured scoring-input pairs** — they need a different probe design (per-signal report manipulation), and the assistant can ship with the honest-partial map; a later campaign if wanted.
- **UPDATE for generated plans** — roadmap step 2, its own plan.
- **Archiving/reviewing the existing 24 strategies** — the user explicitly did not choose "clean house".

## Self-review checklist (run before calling the plan done)

- Budget ≤20 with per-family caps, authorized in the kickoff, audited in Task 7.2?
- Zero applies, zero binds, zero deployments anywhere in the transcript?
- Every probe one-changed-field, verified by script BEFORE its compile?
- Every response recorded verbatim (tokens redacted) BEFORE interpretation; refusals recorded like successes?
- Predictions stated before measuring; no-prior anchors never given invented priors; failed predictions corrected in the same commit and noted here with a date?
- Pinned tests flipped in the same commit as the behavior they pin (coin-selection default, any 4-anchor Literal pin)?
- Data-driven tests read the record files rather than hard-coding unmeasured values?
