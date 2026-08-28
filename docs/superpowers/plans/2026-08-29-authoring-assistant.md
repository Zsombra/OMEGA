# Authoring Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the authoring surface that turns a Claude session into the strategy-creation assistant: the vocabulary catalog, the `validate_thesis` guardrails, the one-page `brief`, the advisor-ready creation registry with its prepare-never-execute checklist, and doc 20 — the conversation protocol itself.

**Architecture:** Per the approved design (`2026-08-29-authoring-assistant-design.md`): the generator is already thesis-generic (verified 2026-08-29), so nothing in `plan()`/`wire()` changes. Two small new modules — `omega/authoring.py` (vocabulary / validation / brief, everything derived from the measured maps except 17 hand-written module descriptions) and `omega/registry.py` (creation records + checklist) — plus `docs/20-the-authoring-procedure.md`. The conversational layer is Claude following doc 20; no Python NL parsing.

**Tech Stack:** Python 3 (stdlib + pydantic via omega.types), pytest, git. **ZERO live calls** — this plan needs no MCP budget and no per-instance authorizations; nothing here touches the platform.

## Global Constraints

- **This build is offline end to end.** No `compile_strategy_plan`, no applies, no lifecycle calls, no MCP calls of any kind — in code, in tests, or in execution. If a step seems to need one, the plan is wrong: STOP and surface.
- **NEVER bind anything to an agent. NEVER create radar or arena deployments.** Standing. The checklist *names* those steps for the user; nothing executes them.
- **Everything derived, one exception:** every number and vocabulary item comes from the measured maps/constants (`MODULE_RECIPES`, `MODULE_CLAUSES`, `CADENCE_FOR_ANCHOR`, `REGIME_TF_FOR_ANCHOR`, `RANKED_LIMIT_MEASURED_MAX`, `omega.execution`); the ONLY hand-written data is `MODULE_DESCRIPTIONS` (plain-language one-liners, marked as such in the code).
- Honesty rules carry into generated text: the checklist labels unexecuted/unverified steps as such; the brief includes findings verbatim; no performance language anywhere.
- Baseline: `main` at `359af3b`, **857 tests passing**. `python -m pytest -q` before every commit; commit messages end with the Claude co-author line.
- Windows: Write/Edit tools for committed files, not shell heredocs.

## Context an executor needs (read these first)

| file | why |
|---|---|
| `docs/superpowers/specs/2026-08-29-authoring-assistant-design.md` | the approved design and its eight decisions |
| `docs/superpowers/specs/2026-08-28-assistant-phase-decisions.md` | the four phase decisions (builder advisor-ready / auto-archive / full menu / prepare-never-execute) |
| `omega/generate.py` (`MODULE_RECIPES`, `MODULE_CLAUSES`, `Thesis`, `plan`, maps) | everything `authoring.py` derives from |
| `omega/execution.py` | defaults/bounds/enforcement the vocabulary re-exports |
| `omega/membership.py` (`_map`) | `moduleSignals` for per-module signal lists |
| `data/audit/first_generated_apply_2026-08-28.json`, `data/audit/first_generated_update_2026-08-29.json` | the records the registry backfill (Task 4) cites |
| `docs/16-the-write-path.md` §§ generated create/revise | the proven loop patterns doc 20 references |

Key verified facts (do not re-derive, do not contradict):

- `plan()` is thesis-generic. Two verified footguns motivate `validate_thesis`: an unknown module in `Thesis.weights` is **silently dropped** (`MODULE_RECIPES.get(module, [])`), and fewer than 2 directional modules makes `_build_conditions` return `[]` — **no conditions, no verdicts, silently**.
- `MODULE_CLAUSES`: 17 modules; 15 carry `up`/`down` (directional), `TREND_STRENGTH` and `VOLATILITY` carry only `filter`; `BOLLINGER`/`MFI`/`RSI`/`STOCHASTIC` also carry `fade_up`/`fade_down`. Every value is a zero-arg lambda returning a clause dict `{kind, column: {header, sectionKey}, op, value|label|labels|low+high}`.
- The measured constants: anchors exactly `{5m, 15m, 1h, 4h}` with measured cadence/regime; `RANKED_LIMIT_MEASURED_MAX == 4`; explicit tickers ≤50 (schema); execution defaults/bounds/enforcement per `omega/execution.py` (R:R catalog bound enforced both edges, minAtrPct not).
- `6a8bca67-45a3-428e-85ba-71ec2cd2218e` "Trend Continuation": created 2026-08-28 (revision 1), archived (2), restored (3), updated with the R:R 2.0 override (4), archived (5). The registry backfill encodes exactly this from the two audit records.
- `Thesis` is a plain dataclass — `dataclasses.asdict` serializes it (`execution`/`coin_selection` are dicts or None).

---

### Task 0: Execution-day preflight

**Files:** none modified.

- [ ] **Step 0.1:** Isolated workspace (superpowers:using-git-worktrees): branch at current `origin/main` (`git fetch origin`; expect `359af3b` or a descendant). `python -m pytest -q` → **857 passed** (drift → read the new commits first).
- [ ] **Step 0.2:** Confirm the zero-live-call nature of this plan needs no authorizations; nothing to gate. Proceed.

### Task 1: `vocabulary()` — the complete menu

**Files:**
- Create: `omega/authoring.py`
- Test: `tests/test_authoring.py` (new)

**Interfaces:**
- Produces: `vocabulary() -> dict` with keys `modules` (17 entries: `measures`, `directional`, `readings`, `signals`), `anchors`, `universe`, `execution`, `stances`; `MODULE_DESCRIPTIONS: dict`; `_clause_text(clause: dict) -> str`.

- [ ] **Step 1.1: Write the failing tests** — create `tests/test_authoring.py`:

```python
"""The authoring surface (design 2026-08-29): the menu, the guardrails, the brief.
Everything derived from the measured maps; MODULE_DESCRIPTIONS is the one
hand-written table and these tests pin it complete."""
from __future__ import annotations

from omega.authoring import MODULE_DESCRIPTIONS, vocabulary
from omega.execution import PLATFORM_EXECUTION_DEFAULTS
from omega.generate import MODULE_CLAUSES, MODULE_RECIPES, RANKED_LIMIT_MEASURED_MAX


def test_the_vocabulary_covers_every_module_exactly():
    v = vocabulary()
    assert set(v["modules"]) == set(MODULE_RECIPES) == set(MODULE_DESCRIPTIONS)
    for m, entry in v["modules"].items():
        assert entry["measures"] == MODULE_DESCRIPTIONS[m]
        assert entry["directional"] == ("up" in MODULE_CLAUSES[m])
        assert set(entry["readings"]) == set(MODULE_CLAUSES[m])
        assert all(isinstance(t, str) and t for t in entry["readings"].values())


def test_directional_split_matches_the_clause_map():
    v = vocabulary()
    directional = {m for m, e in v["modules"].items() if e["directional"]}
    assert len(directional) == 15
    assert {"TREND_STRENGTH", "VOLATILITY"} == set(v["modules"]) - directional


def test_the_measured_constants_flow_through():
    v = vocabulary()
    assert set(v["anchors"]) == {"5m", "15m", "1h", "4h"}
    assert v["anchors"]["4h"] == {"cadence": "SWING", "regimeTimeframe": "1d"}
    assert v["universe"]["rankedMaxLimit"] == RANKED_LIMIT_MEASURED_MAX == 4
    assert v["universe"]["explicitMaxTickers"] == 50
    assert v["execution"]["defaults"] == PLATFORM_EXECUTION_DEFAULTS
    assert v["execution"]["catalogEnforced"] == {"minRiskRewardRatio": True,
                                                 "minAtrPct": False}


def test_clause_text_renders_every_op():
    from omega.authoring import _clause_text
    col = {"sectionKey": None, "header": "H"}
    assert _clause_text({"kind": "clause", "column": col, "op": "is", "label": "x"}) == "H is 'x'"
    assert _clause_text({"kind": "clause", "column": col, "op": "gte", "value": 25}) == "H gte 25"
    assert _clause_text({"kind": "clause", "column": col, "op": "between",
                         "low": -1, "high": 1}) == "H between -1 and 1"
```

- [ ] **Step 1.2:** Run `python -m pytest tests/test_authoring.py -q` — expect FAIL (module missing).
- [ ] **Step 1.3: Implement** — create `omega/authoring.py`:

```python
"""The authoring surface: what can be said, whether a Thesis says it legally, and
the one-page honest brief (design 2026-08-29). Everything here is DERIVED from the
measured maps and constants, with one exception: MODULE_DESCRIPTIONS, the
plain-language one-liners, which exist nowhere machine-readable and are hand-written."""
from __future__ import annotations

from .execution import (CATALOG_BOUND_ENFORCED, CATALOG_BOUNDS,
                        PLATFORM_EXECUTION_DEFAULTS, SCHEMA_BOUNDS,
                        validate_execution)
from .generate import (CADENCE_FOR_ANCHOR, MODULE_CLAUSES, MODULE_RECIPES,
                       RANKED_LIMIT_MEASURED_MAX, REGIME_TF_FOR_ANCHOR, Thesis)
from .membership import _map
from .validate import Finding

# The one hand-written table: what each module's columns measure, in plain language.
MODULE_DESCRIPTIONS = {
    "BOLLINGER": "price position against the volatility bands (%B, width, touches)",
    "CVD": "cumulative volume delta - net aggressor buying vs selling (crypto-only)",
    "FLOW_DIVERGENCE": "perp-vs-spot flow agreement or divergence (crypto-only)",
    "FUNDING": "perp funding rate level and direction",
    "MACD": "MACD momentum: histogram trend and signal-line crosses",
    "MFI": "money flow index - volume-weighted overbought/oversold",
    "MOVING_AVERAGES": "EMA/SMA stack alignment and distance from the SMA200",
    "OPEN_INTEREST": "open interest level and trend",
    "PRICE_STRUCTURE": "swing highs/lows and position within the recent range",
    "REGIME": "the platform's own trend/volatility/momentum regime labels",
    "RELATIVE_STRENGTH": "PPO/ROC momentum relative to the market",
    "RSI": "RSI level, zone and trajectory",
    "STOCHASTIC": "stochastic %K/%D zone and crosses",
    "SUPPORT_RESISTANCE": "distance to structural support/resistance zones",
    "TREND_STRENGTH": "ADX trend-strength filter (carries no direction of its own)",
    "VOLATILITY": "ATR level and expansion/contraction (filter, no direction)",
    "VOLUME": "volume surges, dry-ups and the OBV trend",
}


def _clause_text(c: dict) -> str:
    col = c["column"]["header"]
    if c["op"] == "is":
        return f"{col} is '{c['label']}'"
    if c["op"] == "in":
        return f"{col} in {c['labels']}"
    if c["op"] == "between":
        return f"{col} between {c['low']} and {c['high']}"
    return f"{col} {c['op']} {c['value']}"


def vocabulary() -> dict:
    """The assistant's complete menu - every module, anchor, universe rule and
    execution knob the platform was MEASURED to accept."""
    sigs = _map()["moduleSignals"]
    modules = {}
    for m in sorted(MODULE_RECIPES):
        spec = MODULE_CLAUSES[m]
        modules[m] = {
            "measures": MODULE_DESCRIPTIONS[m],
            "directional": "up" in spec,
            "readings": {k: _clause_text(spec[k]()) for k in sorted(spec)},
            "signals": sorted(sigs.get(m, [])),
        }
    return {
        "modules": modules,
        "anchors": {a: {"cadence": CADENCE_FOR_ANCHOR[a],
                        "regimeTimeframe": REGIME_TF_FOR_ANCHOR[a]}
                    for a in CADENCE_FOR_ANCHOR},
        "universe": {
            "explicitMaxTickers": 50,
            "rankedMaxLimit": RANKED_LIMIT_MEASURED_MAX,
            "_why": "ranked limit measured 2026-08-28 against BG-14's preview cap for "
                    "the standard report shape; wider reports refuse earlier",
        },
        "execution": {
            "defaults": dict(PLATFORM_EXECUTION_DEFAULTS),
            "schemaBounds": dict(SCHEMA_BOUNDS),
            "catalogBounds": dict(CATALOG_BOUNDS),
            "catalogEnforced": dict(CATALOG_BOUND_ENFORCED),
        },
        "stances": {"ALIGN": "the tape should agree with the direction",
                    "FADE": "the crowd should be leaning the other way"},
    }
```

(`Thesis`, `Finding` and `validate_execution` are imported now because Tasks 2–3 use them from this module; if the linter flags them before then, that is expected and resolves in Task 2.)
- [ ] **Step 1.4:** `python -m pytest -q` — green (857 + 4 = 861). Commit `The authoring vocabulary: every measured menu item, derived` → push.

### Task 2: `validate_thesis` — the guardrails

**Files:**
- Modify: `omega/authoring.py`
- Test: `tests/test_authoring.py` (append)

**Interfaces:**
- Produces: `validate_thesis(thesis: Thesis) -> list[Finding]`, codes `THESIS_UNKNOWN_MODULE`, `THESIS_BAD_WEIGHT`, `THESIS_TOO_FEW_DIRECTIONAL`, `THESIS_BAD_STANCE`, `THESIS_UNMEASURED_ANCHOR`, `THESIS_UNIVERSE_TOO_WIDE`, `THESIS_UNFEEDABLE_REQUIRED`, plus everything `validate_execution` returns.

- [ ] **Step 2.1: Write the failing tests** — append to `tests/test_authoring.py`:

```python
from dataclasses import replace

from omega.generate import PRESETS
from omega.authoring import validate_thesis


def _codes(thesis):
    return {f.code for f in validate_thesis(thesis)}


def test_the_presets_pass_clean():
    for p in PRESETS.values():
        assert not [f for f in validate_thesis(p) if f.severity == "error"]


def test_unknown_module_is_an_error_not_a_silent_drop():
    t = replace(PRESETS["trend-continuation"],
                weights={**PRESETS["trend-continuation"].weights, "ELON_TWEETS": 3})
    assert "THESIS_UNKNOWN_MODULE" in _codes(t)


def test_too_few_directional_modules_is_an_error():
    """plan() silently emits NO conditions below 2 directional modules (verified
    2026-08-29) - the assistant must refuse before that happens."""
    t = replace(PRESETS["trend-continuation"],
                weights={"TREND_STRENGTH": 2, "VOLATILITY": 1, "RSI": 2})
    assert "THESIS_TOO_FEW_DIRECTIONAL" in _codes(t)
    t2 = replace(t, weights={"RSI": 2, "MACD": 2})
    assert "THESIS_TOO_FEW_DIRECTIONAL" not in _codes(t2)


def test_bad_weight_stance_and_anchor():
    base = PRESETS["trend-continuation"]
    assert "THESIS_BAD_WEIGHT" in _codes(replace(base, weights={"RSI": 5, "MACD": 2}))
    assert "THESIS_BAD_STANCE" in _codes(replace(base, stance="YOLO"))
    assert "THESIS_UNMEASURED_ANCHOR" in _codes(replace(base, anchor="1d"))


def test_universe_bounds_are_the_measured_ones():
    base = PRESETS["trend-continuation"]
    wide = replace(base, coin_selection={"mode": "ranked", "category": "ALL", "limit": 9})
    assert "THESIS_UNIVERSE_TOO_WIDE" in _codes(wide)
    fat = replace(base, coin_selection={"mode": "explicit",
                                        "tickers": [f"T{i}" for i in range(51)]})
    assert "THESIS_UNIVERSE_TOO_WIDE" in _codes(fat)


def test_unfeedable_required_signal_is_an_error():
    t = replace(PRESETS["trend-continuation"], required=["cvd_bullish"])  # CVD unweighted
    assert "THESIS_UNFEEDABLE_REQUIRED" in _codes(t)


def test_execution_findings_flow_through():
    t = replace(PRESETS["trend-continuation"], execution={"minRiskRewardRatio": 9})
    assert "EXECUTION_OUTSIDE_CATALOG_BOUND" in _codes(t)
```

- [ ] **Step 2.2:** Run — expect FAIL (`validate_thesis` not defined).
- [ ] **Step 2.3: Implement** — append to `omega/authoring.py`:

```python
DIRECTIONAL_MODULES = frozenset(m for m, s in MODULE_CLAUSES.items() if "up" in s)


def validate_thesis(thesis: Thesis) -> list[Finding]:
    """The guardrails plan() lacks. Each check is a verified footgun or a measured
    bound; nothing here is a style opinion."""
    out: list[Finding] = []
    for m in thesis.modules:
        if m not in MODULE_RECIPES:
            out.append(Finding("error", "THESIS_UNKNOWN_MODULE", f"weights.{m}",
                               f"{m} is not one of the {len(MODULE_RECIPES)} modules - "
                               f"plan() would silently drop it (verified 2026-08-29)"))
    for m, tier in thesis.weights.items():
        if not isinstance(tier, int) or not 0 <= tier <= 3:
            out.append(Finding("error", "THESIS_BAD_WEIGHT", f"weights.{m}",
                               f"allocation tier must be an int 0-3, got {tier!r}"))
    directional = [m for m in thesis.weights if m in DIRECTIONAL_MODULES]
    if len(directional) < 2:
        out.append(Finding("error", "THESIS_TOO_FEW_DIRECTIONAL", "weights",
                           f"only {len(directional)} directional module(s) weighted - "
                           f"below 2, plan() silently emits NO conditions and NO "
                           f"verdicts (verified 2026-08-29)"))
    if thesis.stance not in ("ALIGN", "FADE"):
        out.append(Finding("error", "THESIS_BAD_STANCE", "stance",
                           f"stance must be ALIGN or FADE, got {thesis.stance!r}"))
    if thesis.anchor not in CADENCE_FOR_ANCHOR:
        out.append(Finding("error", "THESIS_UNMEASURED_ANCHOR", "anchor",
                           f"{thesis.anchor!r} is not authorable - the platform's "
                           f"complete anchor set is {sorted(CADENCE_FOR_ANCHOR)} "
                           f"(REPORT_TIMEFRAME_NOT_AUTHORABLE, measured 2026-08-28)"))
    sel = thesis.resolved_coin_selection()
    if sel.get("mode") == "explicit" and len(sel.get("tickers", [])) > 50:
        out.append(Finding("error", "THESIS_UNIVERSE_TOO_WIDE", "coin_selection",
                           f"{len(sel['tickers'])} tickers - the schema caps explicit "
                           f"lists at 50"))
    if sel.get("mode") == "ranked" and sel.get("limit", 0) > RANKED_LIMIT_MEASURED_MAX:
        out.append(Finding("error", "THESIS_UNIVERSE_TOO_WIDE", "coin_selection",
                           f"ranked limit {sel['limit']} exceeds the measured BG-14 "
                           f"boundary {RANKED_LIMIT_MEASURED_MAX} - the compile "
                           f"preview refuses above it (measured 2026-08-28)"))
    feedable = {sid for m, tier in thesis.weights.items() if tier > 0
                for sid in _map()["moduleSignals"].get(m, [])}
    for sid in thesis.required:
        if sid not in feedable:
            out.append(Finding("error", "THESIS_UNFEEDABLE_REQUIRED", f"required.{sid}",
                               f"{sid} is marked required but no weighted module "
                               f"feeds it - it could never fire"))
    out += validate_execution(thesis.execution or {})
    return out
```

- [ ] **Step 2.4:** `python -m pytest -q` — green (861 + 7 = 868). Commit `validate_thesis: the guardrails the generator lacks` → push.

### Task 3: `brief()` — the offline deliverable

**Files:**
- Modify: `omega/authoring.py`
- Test: `tests/test_authoring.py` (append)

**Interfaces:**
- Produces: `brief(p: StrategyPlan) -> str` — one honest page: identity line, thesis-finding lines, critique lines, wire vitals.

- [ ] **Step 3.1: Write the failing tests** — append:

```python
def test_the_brief_is_one_honest_page():
    from omega.authoring import brief
    from omega.generate import plan
    text = brief(plan(PRESETS["trend-continuation"]))
    assert "Trend Continuation" in text
    assert "stance ALIGN" in text and "anchor 1h" in text
    assert "platform defaults" in text            # the execution profile line
    assert "84 rules" in text and "24 weighted" in text
    assert "thesis findings: none" in text        # presets pass clean


def test_the_brief_carries_findings_verbatim():
    from omega.authoring import brief
    from omega.generate import plan
    t = replace(PRESETS["trend-continuation"],
                weights={**PRESETS["trend-continuation"].weights, "ELON_TWEETS": 3})
    assert "THESIS_UNKNOWN_MODULE" in brief(plan(t))
```

- [ ] **Step 3.2:** Run — expect FAIL (`brief` not defined).
- [ ] **Step 3.3: Implement** — append to `omega/authoring.py`:

```python
def brief(p) -> str:
    """The offline deliverable (decision 4, 2026-08-29): everything the user needs
    to judge the thesis, zero live calls. p is a StrategyPlan."""
    t = p.thesis
    findings = validate_thesis(t)
    w = p.wire()
    lines = [
        f"{t.name}" + (f" - {t.tagline}" if t.tagline else ""),
        f"stance {t.stance} | anchor {t.anchor} "
        f"({CADENCE_FOR_ANCHOR.get(t.anchor, '?')}/"
        f"{REGIME_TF_FOR_ANCHOR.get(t.anchor, '?')}) | gate {t.gate} | "
        f"universe {t.resolved_coin_selection()}",
        "weighted modules: " + (", ".join(
            f"{m}:{tier}" for m, tier in sorted(t.weights.items()) if tier) or "none"),
        "",
        "thesis findings:" + ("" if findings else " none"),
        *[f"  {f}" for f in findings],
        "",
        "critique:",
        *[f"  {line}" for line in p.critique()],
        "",
        f"wire body: {len(w['sections'])} sections, {len(w['rules'])} rules "
        f"({sum(1 for r in w['rules'] if r['allocation'] > 0)} weighted), "
        f"{len(w['conditions'])} conditions",
    ]
    return "\n".join(lines)
```

- [ ] **Step 3.4:** `python -m pytest -q` — green (868 + 2 = 870). Commit `brief(): the one-page offline deliverable` → push.

### Task 4: The registry and the prepare-never-execute checklist

**Files:**
- Create: `omega/registry.py`, `data/created/6a8bca67-45a3-428e-85ba-71ec2cd2218e.json` (the backfill), `data/created/6a8bca67-45a3-428e-85ba-71ec2cd2218e.checklist.md`
- Test: `tests/test_registry.py` (new)

**Interfaces:**
- Produces: `new_entry(strategy_id, created_date, thesis, audit_record, disposition) -> dict`; `add_revision(entry, date, revision, change, audit_record) -> dict`; `save(entry) -> Path`; `load(strategy_id) -> dict`; `checklist(entry) -> str`; `CREATED_DIR: Path`.

- [ ] **Step 4.1: Write the failing tests** — create `tests/test_registry.py`:

```python
"""The advisor-ready creation registry and the prepare-never-execute checklist
(design 2026-08-29). The backfilled entry for 6a8bca67 is the registry's first
citizen - the strategy whose create (2026-08-28) and revise (2026-08-29) loops are
already on the record."""
from __future__ import annotations

import json
from pathlib import Path

from omega.registry import CREATED_DIR, checklist, load, new_entry, add_revision

ROOT = Path(__file__).resolve().parents[1]
SIX_A = "6a8bca67-45a3-428e-85ba-71ec2cd2218e"


def test_entry_roundtrip(tmp_path, monkeypatch):
    import omega.registry as R
    monkeypatch.setattr(R, "CREATED_DIR", tmp_path)
    e = new_entry("test-id", "2026-08-29", None, "data/audit/x.json", "archived")
    e = add_revision(e, "2026-08-29", 2, "archived after verification",
                     "data/audit/x.json")
    p = R.save(e)
    assert p.parent == tmp_path
    assert R.load("test-id") == e
    assert e["auditRecords"] == ["data/audit/x.json"]     # deduped


def test_the_backfilled_entry_matches_the_audit_records():
    e = load(SIX_A)
    assert e["id"] == SIX_A
    assert e["createdDate"] == "2026-08-28"
    assert e["disposition"] == "archived"
    assert [r["revision"] for r in e["revisions"]] == [2, 3, 4, 5]
    assert "data/audit/first_generated_apply_2026-08-28.json" in e["auditRecords"]
    assert "data/audit/first_generated_update_2026-08-29.json" in e["auditRecords"]
    assert e["thesis"]["execution"] == {"minRiskRewardRatio": 2.0}


def test_the_checklist_prepares_and_never_executes():
    text = checklist(load(SIX_A))
    assert SIX_A in text
    assert "restore_strategy" in text
    assert "rebind_intelligence_agent" in text
    assert "upsert_radar_deployment" in text
    assert "real capital" in text
    assert "never executes" in text
    assert "unverified" in text        # app-UI specifics labeled, not invented


def test_the_committed_checklist_matches_the_generator():
    committed = (CREATED_DIR / f"{SIX_A}.checklist.md").read_text(encoding="utf-8")
    assert committed == checklist(load(SIX_A))
```

- [ ] **Step 4.2:** Run — expect FAIL (module missing).
- [ ] **Step 4.3: Implement** — create `omega/registry.py`:

```python
"""The advisor-ready creation registry and the prepare-never-execute checklist
(design 2026-08-29). One committed JSON per assistant-created strategy so that IF
the user ever lets one trade, performance can attach later without rework. The
checklist NAMES the capital-bearing steps for the user; nothing here executes them."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path

CREATED_DIR = Path(__file__).resolve().parents[1] / "data" / "created"


def new_entry(strategy_id: str, created_date: str, thesis,
              audit_record: str, disposition: str) -> dict:
    return {"id": strategy_id, "createdDate": created_date,
            "thesis": asdict(thesis) if is_dataclass(thesis) else thesis,
            "revisions": [], "disposition": disposition,
            "auditRecords": [audit_record]}


def add_revision(entry: dict, date: str, revision: int, change: str,
                 audit_record: str) -> dict:
    entry["revisions"].append({"date": date, "revision": revision, "change": change})
    if audit_record not in entry["auditRecords"]:
        entry["auditRecords"].append(audit_record)
    return entry


def save(entry: dict) -> Path:
    CREATED_DIR.mkdir(parents=True, exist_ok=True)
    p = CREATED_DIR / f"{entry['id']}.json"
    p.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    return p


def load(strategy_id: str) -> dict:
    return json.loads((CREATED_DIR / f"{strategy_id}.json").read_text(encoding="utf-8"))


def checklist(entry: dict) -> str:
    """The prepare-never-execute checklist (phase decision 4, 2026-08-28): the exact
    manual steps the USER would take to let this strategy trade. The assistant never
    executes any of them - these steps move real capital."""
    sid = entry["id"]
    return "\n".join([
        f"# Letting {sid} trade - the steps YOU would take",
        "",
        "> Binding and deployment move **real capital**. The assistant prepares this",
        "> list and never executes it; no general 'go ahead' authorises these steps.",
        "",
        f"1. Review the registry entry (`data/created/{sid}.json`), its audit",
        "   records, and the latest brief. Confirm this is the revision you mean.",
        f"2. If archived (disposition: {entry['disposition']}): restore it yourself -",
        f"   `restore_strategy` with strategyId `{sid}` and the CURRENT revision",
        "   (read it first with `get_strategy includeInactive:true`; never assume).",
        "3. Bind it to an agent yourself: `rebind_intelligence_agent` with an agentId",
        "   you choose and this strategyId. The agent's capital settings (exposure,",
        "   drawdown, daily-loss caps) live on the agent, not the strategy - review",
        "   them first. Exact request fields: read the tool's schema at call time",
        "   (unverified here - no bind has ever been executed from this repo).",
        "4. Give it per-coin trade authority yourself: `upsert_radar_deployment` per",
        "   coin. Also unverified here, for the same reason.",
        "5. Watch the first sessions (`get_agent_activity_feed`, open positions) and",
        "   record outcomes back into the registry entry so performance attaches to",
        "   this strategy's history.",
        "",
        "The assistant never executes steps 2-4. This list prepares; you decide.",
    ])
```

- [ ] **Step 4.4: The backfill** — write `data/created/6a8bca67-45a3-428e-85ba-71ec2cd2218e.json` by script (Python, using `new_entry`/`add_revision`/`save` with the facts from the two audit records — read them, do not retype): created 2026-08-28 revision 1 (create+verify), revisions `[{2026-08-28, 2, "archived after verification"}, {2026-08-29, 3, "restored for the revision loop"}, {2026-08-29, 4, "R:R override 1.5 -> 2.0 via wire_update"}, {2026-08-29, 5, "archived after verification"}]`, disposition `archived`, both audit record paths, thesis = the trend-continuation preset asdict with `coin_selection` explicit BTC/ETH/SOL and `execution {"minRiskRewardRatio": 2.0}` (the post-revision truth). Then write the committed checklist beside it: `(CREATED_DIR / f"{SIX_A}.checklist.md").write_text(checklist(load(SIX_A)), encoding="utf-8")`.
- [ ] **Step 4.5:** `python -m pytest -q` — green (870 + 4 = 874). Commit `The creation registry and its prepare-never-execute checklist` → push.

### Task 5: Doc 20 — the authoring procedure

**Files:**
- Create: `docs/20-the-authoring-procedure.md`
- Modify: `README.md` (index line + masthead sentence)

- [ ] **Step 5.1:** Write `docs/20-the-authoring-procedure.md` with exactly these sections (prose to write, grounded in the modules built above — every claim must trace to a measured record or a built function; no performance language anywhere):
  1. **What this is** — the assistant = a Claude session following this procedure; the four phase decisions and four design decisions, each named with its date.
  2. **Intake** — the questions to ask the user (what do you believe moves price; which of the 17 modules measure that — show `vocabulary()`; direction with or against the crowd → stance; how fast → anchor from the 4; which coins → universe within measured bounds; any trade-shape overrides → execution).
  3. **The honesty gate** — the refuse-and-offer-nearest policy verbatim: name what the platform cannot measure and why (cite the vocabulary), offer the nearest expressible thesis clearly labeled as different, never silently substitute.
  4. **Build and iterate** — construct the `Thesis`; run `validate_thesis` (errors block; each code explained); `plan()` + `brief()` is the deliverable; iterate on the user's reactions. Zero live calls in this loop.
  5. **Live steps, each per-authorized** — the exact authorization sentence templates and the proven procedures, by reference: compile dry-run (doc 16 compile discipline; record verbatim, redact tokens), create+verify+auto-archive (the 2026-08-28 loop, `first_generated_apply` record as the template), revise (the 2026-08-29 loop, `wire_update`, pre-apply diff inspection, the sectionKey-churn caveat).
  6. **After every create or revise** — update the registry entry and regenerate its checklist; both are committed files.
  7. **What the assistant never does** — bind, deploy, predict performance; the checklist prepares those steps for the user.
- [ ] **Step 5.2:** README: add the index row `| [20 · The authoring procedure](docs/20-the-authoring-procedure.md) | how a session turns intent into a strategy — the vocabulary, the guardrails, the honesty gate, and the per-authorized live loops |` and one masthead sentence stating the assistant surface exists as of the execution date.
- [ ] **Step 5.3:** `python -m pytest -q` — green (874, no new tests). Commit `Doc 20: the authoring procedure` → push.

### Task 6: Finish

- [ ] **Step 6.1:** Full suite; reconcile this plan's baseline note (857 → final) with a dated line; verify by grep that no test or module added in this plan imports the MCP connector or makes network calls.
- [ ] **Step 6.2:** Integrate: `git fetch origin && git merge-base --is-ancestor origin/main HEAD && git push origin HEAD:main` (STOP on non-FF).
- [ ] **Step 6.3:** Update memory (`next-session-compile-bridge.md` or successor): the assistant surface is built; what exists (vocabulary/guardrails/brief/registry/checklist/doc 20); the first real authoring conversation is the natural next session; binding/deployment stay user-gated, always.
- [ ] **Step 6.4:** Final report: what was built, test count, the zero-live-call confirmation, and what the user does next (open a session, state an intent, follow doc 20).

## Deliberately absent (lean by the user's instruction)

- Python NL parsing, CLI wizards, second conversational layers.
- Performance or outcome claims anywhere, including generated text.
- Executing binds/deployments; the checklist names them for the user only.
- New platform measurement, new presets, generator changes.

## Self-review checklist (run before calling the plan done)

- Zero live calls anywhere — code, tests, execution transcript?
- Every vocabulary item derived from a measured map/constant except the flagged descriptions table?
- Both verified footguns covered by failing-first tests?
- The backfilled registry entry built FROM the audit records, not retyped?
- Checklist language: prepares, names, warns — never executes, never predicts?
