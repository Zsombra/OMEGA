# Schema-Drift Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Before any authorized `compile_strategy_plan` call is spent, detect offline that the platform's expectations have drifted from what `omega.generate.StrategyPlan.wire()` emits, and make the compile authorization depend on a dated, sha-bound receipt.

**Architecture:** A read-only session procedure saves two verbatim captures (the compile tool definition from ToolSearch, and one `get_strategy` read-back) under `data/contract/`; a pure-Python module `omega/preflight.py` diffs the wire body against both with a fixed finding vocabulary and writes a receipt to `data/audit/`; a CLI `scripts/preflight.py` prints the recipe, runs the diff, and gates on the receipt. Nothing stored in the repo is ever the truth for a verdict.

**Tech Stack:** Python ≥ 3.10, stdlib only (`json`, `hashlib`, `dataclasses`, `datetime`, `pathlib`); pytest. No `jsonschema`, no `regex`, no network client.

**Spec:** `docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md` — read it first; every rule below is the spec's.

## Global Constraints

- omega never calls the connector (`omega/probe.py:3`); `omega/preflight.py` imports nothing from the network. `tests/test_probe.py::test_module_imports_no_network_client` shows the enforcement pattern; Task 1 adds the same check for the new module.
- No new dependency. `pyproject.toml` stays at `pydantic>=2.0`, `pandas>=2.0`.
- The preflight never compiles, applies, restores, binds or deploys, and never chooses a value for a missing field.
- Finding classes are exactly: `UNDECLARED`, `MISSING_REQUIRED`, `MISSING_VS_RECORD`, `ENUM`, `BOUNDS`, `UNSUPPORTED`, `MIRROR`, `CHANGELOG`, `TRANSCRIPTION_SUSPECT`, `INFO`. Verdicts are exactly `FAIL`, `WARN`, `INFO`.
- Every PASS carries the disclaimer verbatim: `covers the published schema and the reference record only; the runtime validator is not observed by this check`.
- Receipts live in `data/audit/compile_preflight_<YYYY-MM-DD>[-<slug>].json`; captures in `data/contract/compile_strategy_plan/` and `data/contract/get_strategy/`, in probe.py's `{capturedAt, how, request, response}` shape.
- Expiry default 60 minutes. `MIRROR` is WARN, never FAIL. `confirmTf` is excluded from `MIRROR` (it is derived from the thesis anchor by design).
- Two named structural deltas and nothing else: body `rules` ↔ record `signalRules`; custom-section `sectionKey` is server-minted.
- Run `python -m pytest -q` from the repo root before and after every task; baseline **925 passed**. Commit after every task.
- Work on a branch, never directly on `main`.

## File structure

| File | Responsibility |
|---|---|
| `omega/preflight.py` (create) | Pure functions: `$ref` resolution and arm selection; schema walker; record diff; mirrors; changelog; fingerprints; verdict; receipt; gate check. No I/O beyond `json.loads` of strings handed in. |
| `scripts/preflight.py` (create) | CLI: `recipe`, `run`, `gate`. The only place that reads/writes files and knows repo paths. |
| `tests/test_preflight.py` (create) | Walker, record diff, mirrors, changelog, fingerprints, verdict, gate — against inline fixtures and the real records named below. |
| `tests/test_preflight_cli.py` (create) | The three CLI modes end to end in `tmp_path`. |
| `tests/fixtures/preflight/schema_walker_min.json` (create) | A small hand-built tool definition in the real structure (`parameters.properties.request.anyOf[...]`, local `$ref`). **Walker fixture only, never a regression oracle for `wire()`.** |
| `docs/20-the-authoring-procedure.md` (modify, §5) | The gate line becomes a precondition of the compile authorization. |
| `docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md` (modify, status line) | Mark implemented, name the first live run's captures. |

Real records used as fixtures (read-only, already committed):
- `data/research/2026-08-29-deep-tail-fade/compile_body_deep_tail_fade_v4.json` — the 08-30 body with the **4-field** `entry` (the shape refused as drift #4).
- `data/research/2026-08-29-deep-tail-fade/compile_body_deep_tail_fade_v5.json` — the 7-field `entry` body that compiled viable; conditions carry `clock`/`closes` but **not** `exit`.
- `data/audit/first_generated_update_2026-08-29.json` → `probes.preState.strategy` — a genuine full read-back (40 keys, 84 `signalRules`, 7 conditions without `clock`/`closes`, no `entry`).
- `data/audit/drift5_exit_rediscovery_2026-09-04.json` — the migrated shape (`exit` on every condition, 7-field `entry`), used to build the post-migration record fixture in tests, labelled as built.
- `data/derived/signal_module_map.json` (`moduleSignals`, union = 84 ids), `data/contract/templates/platform/_all.json` (`templates`, 25 entries with `sectionKey`), `data/contract/vocabulary/_shared.json` (`absoluteTimeframes`, 13) — fingerprint sources.

---

### Task 1: Module skeleton, `Finding`, `$ref` resolution and arm selection

**Files:**
- Create: `omega/preflight.py`
- Create: `tests/fixtures/preflight/schema_walker_min.json`
- Create: `tests/test_preflight.py`

**Interfaces:**
- Produces: `Finding(cls: str, path: str, detail: str, verdict: str)` frozen dataclass; `deref(node: dict, root: dict) -> dict`; `resolve_arms(definition: dict) -> tuple[dict[str, dict], dict]` returning `({"CREATE": arm, "UPDATE": arm, "RESTORE": arm}, root)` where `root` is `definition["parameters"]` (the object every local `$ref` is relative to); `class UnsupportedSchema(ValueError)`.

- [ ] **Step 1: Write the walker fixture**

The real definition nests `request.anyOf[CREATE, UPDATE, RESTORE]` under `parameters.properties`, discriminates arms by `properties.operation.const`, and uses local `$ref`s of the form `#/properties/request/anyOf/0/properties/timeframe` relative to `parameters`. Mirror exactly that structure, small:

```json
{
  "name": "compile_strategy_plan",
  "description": "walker fixture - a hand-built miniature of the real definition; never a regression oracle",
  "parameters": {
    "additionalProperties": false,
    "type": "object",
    "required": ["request"],
    "properties": {
      "request": {
        "anyOf": [
          {
            "additionalProperties": false,
            "type": "object",
            "required": ["operation", "name", "timeframe", "sections", "entry"],
            "properties": {
              "operation": {"const": "CREATE", "type": "string"},
              "name": {"type": "string", "minLength": 1, "maxLength": 50},
              "timeframe": {"enum": ["1h", "4h"], "type": "string"},
              "minAtrPct": {"type": "number", "minimum": 0.01, "maximum": 50},
              "decisionInvalidationExitEnabled": {"type": "boolean"},
              "sections": {
                "type": "array", "maxItems": 3,
                "items": {"anyOf": [
                  {"additionalProperties": false, "type": "object",
                   "required": ["kind", "sectionKey"],
                   "properties": {"kind": {"const": "platform", "type": "string"},
                                  "sectionKey": {"enum": ["includeRsi", "includeMacd"], "type": "string"}}},
                  {"additionalProperties": false, "type": "object",
                   "required": ["kind", "title", "benchmarkTicker", "notes", "columns"],
                   "properties": {"kind": {"const": "custom", "type": "string"},
                                  "title": {"type": "string", "minLength": 1, "maxLength": 60},
                                  "benchmarkTicker": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                                  "notes": {"anyOf": [{"type": "string", "minLength": 1, "maxLength": 400}, {"type": "null"}]},
                                  "sectionKey": {"type": "string", "pattern": "^custom:[0-9a-fA-F-]{36}$"},
                                  "columns": {"type": "array", "minItems": 1, "items": {
                                    "additionalProperties": false, "type": "object",
                                    "required": ["metric", "transformId", "timeframe"],
                                    "properties": {"metric": {"enum": ["RSI14", "CLOSE"], "type": "string"},
                                                   "transformId": {"type": "string"},
                                                   "window": {"type": "integer", "minimum": 1, "maximum": 64},
                                                   "timeframe": {"anyOf": [
                                                     {"additionalProperties": false, "type": "object", "required": ["rel"],
                                                      "properties": {"rel": {"enum": ["anchor", "lower", "regime"], "type": "string"}}},
                                                     {"additionalProperties": false, "type": "object", "required": ["abs"],
                                                      "properties": {"abs": {"$ref": "#/properties/request/anyOf/0/properties/timeframe"}}}]}}}}}}
                ]}
              },
              "conditions": {
                "type": "array", "maxItems": 64,
                "items": {"additionalProperties": false, "type": "object",
                          "required": ["conditionKey", "name", "definition", "verdict", "required", "exit", "clock", "closes"],
                          "properties": {"conditionKey": {"type": "string", "pattern": "^[A-Z][A-Z0-9_]{1,39}$"},
                                         "name": {"type": "string", "minLength": 1, "maxLength": 80},
                                         "definition": {"type": "object"},
                                         "verdict": {"anyOf": [{"enum": ["UP", "DOWN", "NEITHER"], "type": "string"}, {"type": "null"}]},
                                         "required": {"type": "boolean"},
                                         "exit": {"type": "boolean"},
                                         "clock": {"enum": ["LIVE", "CLOSE"], "type": "string"},
                                         "closes": {"type": "integer", "minimum": 1, "maximum": 5}}}
              },
              "rules": {"type": "array", "items": {"additionalProperties": false, "type": "object",
                        "required": ["signalId", "allocation", "required"],
                        "properties": {"signalId": {"enum": ["rsi_oversold", "rsi_overbought"], "type": "string"},
                                       "allocation": {"type": "integer", "minimum": 0, "maximum": 3},
                                       "required": {"type": "boolean"},
                                       "params": {"type": "object"}}}},
              "entry": {"additionalProperties": false, "type": "object",
                        "required": ["trigger", "confirmTf", "closes", "bandAtrMultiple", "levelSource", "levelOffsetAtrMultiple", "validForBars"],
                        "properties": {"trigger": {"enum": ["AT_SIGNAL", "ON_CANDLE_CLOSE"], "type": "string"},
                                       "confirmTf": {"$ref": "#/properties/request/anyOf/0/properties/timeframe"},
                                       "closes": {"type": "integer", "minimum": 1, "maximum": 5},
                                       "bandAtrMultiple": {"type": "number", "exclusiveMinimum": 0},
                                       "levelSource": {"enum": ["SWING_HIGH", "SWING_LOW"], "type": "string"},
                                       "levelOffsetAtrMultiple": {"type": "number", "minimum": 0, "maximum": 2},
                                       "validForBars": {"type": "integer", "minimum": 1, "maximum": 24}}}
            }
          },
          {
            "additionalProperties": false,
            "type": "object",
            "required": ["operation", "strategyId", "expectedRevision"],
            "properties": {
              "operation": {"const": "UPDATE", "type": "string"},
              "strategyId": {"type": "string"},
              "expectedRevision": {"type": "integer", "minimum": 1},
              "name": {"$ref": "#/properties/request/anyOf/0/properties/name"},
              "timeframe": {"$ref": "#/properties/request/anyOf/0/properties/timeframe"},
              "entry": {"$ref": "#/properties/request/anyOf/0/properties/entry"},
              "conditions": {"$ref": "#/properties/request/anyOf/0/properties/conditions"}
            }
          }
        ]
      }
    }
  }
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_preflight.py
"""Schema-drift preflight (design 2026-09-04). Pure functions; the fixtures are a
hand-built walker miniature and the REAL records named in the plan. The miniature is a
walker fixture only - never a regression oracle for wire()."""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from omega import preflight as P

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "preflight"
MINI = json.loads((FIX / "schema_walker_min.json").read_text(encoding="utf-8"))


def test_module_imports_no_network_client():
    """The house rule (omega/probe.py:3), enforced against the import graph."""
    tree = ast.parse(inspect.getsource(P))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"requests", "httpx", "urllib", "aiohttp", "socket", "http"}


def test_finding_is_frozen_and_has_the_four_fields():
    f = P.Finding("ENUM", "entry.trigger", "x", "FAIL")
    assert (f.cls, f.path, f.detail, f.verdict) == ("ENUM", "entry.trigger", "x", "FAIL")
    with pytest.raises(Exception):
        f.cls = "INFO"  # type: ignore[misc]


def test_resolve_arms_selects_by_operation_const_and_returns_root():
    arms, root = P.resolve_arms(MINI)
    assert set(arms) == {"CREATE", "UPDATE"}
    assert arms["CREATE"]["properties"]["operation"]["const"] == "CREATE"
    assert root is MINI["parameters"]


def test_deref_follows_local_refs_relative_to_parameters():
    arms, root = P.resolve_arms(MINI)
    tf = P.deref(arms["UPDATE"]["properties"]["timeframe"], root)
    assert tf["enum"] == ["1h", "4h"]
    # a ref inside a ref target
    entry = P.deref(arms["UPDATE"]["properties"]["entry"], root)
    assert P.deref(entry["properties"]["confirmTf"], root)["enum"] == ["1h", "4h"]


def test_deref_refuses_non_local_refs():
    with pytest.raises(P.UnsupportedSchema):
        P.deref({"$ref": "https://example.invalid/schema#/x"}, MINI["parameters"])
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest tests/test_preflight.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'omega.preflight'`.

- [ ] **Step 4: Write the minimal implementation**

```python
# omega/preflight.py
"""Schema-drift preflight (design: docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md).

omega CANNOT CALL MCP TOOLS (omega/probe.py:3). The session saves two verbatim captures -
the compile_strategy_plan tool definition (a ToolSearch definition load, not a call) and
one get_strategy read-back - and hands them here as dicts. This module diffs a wire body
against both and returns findings; scripts/preflight.py does the file I/O and prints the
receipt. Nothing here decides a value for a missing field: a FAIL names the field and a
human mirrors it from a record, exactly as was done for drift instances #3, #4 and #5.

The walker covers only the JSON-Schema subset the compile definition uses: properties /
required / additionalProperties:false / enum / const / type / minimum / maximum /
exclusiveMinimum / exclusiveMaximum / minLength / maxLength / minItems / maxItems / items /
anyOf (discriminated by a const on operation|kind|mode, else by type) / local $ref.
Anything else is reported as UNSUPPORTED, never silently skipped.
"""
from __future__ import annotations

from dataclasses import dataclass

CLASSES = ("UNDECLARED", "MISSING_REQUIRED", "MISSING_VS_RECORD", "ENUM", "BOUNDS",
           "UNSUPPORTED", "MIRROR", "CHANGELOG", "TRANSCRIPTION_SUSPECT", "INFO")
VERDICTS = ("FAIL", "WARN", "INFO")
DISCLAIMER = ("covers the published schema and the reference record only; "
              "the runtime validator is not observed by this check")


class UnsupportedSchema(ValueError):
    """A construct the walker does not model (non-local $ref, unknown shape)."""


@dataclass(frozen=True)
class Finding:
    cls: str
    path: str
    detail: str
    verdict: str

    def __post_init__(self) -> None:
        if self.cls not in CLASSES:
            raise ValueError(f"unknown finding class {self.cls!r}")
        if self.verdict not in VERDICTS:
            raise ValueError(f"unknown verdict {self.verdict!r}")


def deref(node: dict, root: dict) -> dict:
    """Follow local JSON-pointer $refs ('#/a/b/0/c') relative to `root`, which for the
    compile definition is definition['parameters']. Non-local refs are refused."""
    seen = 0
    while isinstance(node, dict) and "$ref" in node:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            raise UnsupportedSchema(f"non-local $ref {ref!r}")
        cur: object = root
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]  # type: ignore[index]
        node = cur  # type: ignore[assignment]
        seen += 1
        if seen > 32:
            raise UnsupportedSchema(f"$ref chain too deep at {ref!r}")
    return node


def resolve_arms(definition: dict) -> tuple[dict[str, dict], dict]:
    """The operation arms of a compile_strategy_plan definition, keyed by the
    `operation` const, plus the root every local $ref is relative to."""
    root = definition["parameters"]
    request = deref(root["properties"]["request"], root)
    branches = request.get("anyOf", [request])
    arms: dict[str, dict] = {}
    for branch in branches:
        arm = deref(branch, root)
        op = deref(arm["properties"]["operation"], root).get("const")
        if not isinstance(op, str):
            raise UnsupportedSchema("request arm without an operation const")
        arms[op] = arm
    return arms, root
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_preflight.py -v`
Expected: 5 passed.

- [ ] **Step 6: Run the full suite and commit**

Run: `python -m pytest -q` — expected `930 passed`.

```bash
git add omega/preflight.py tests/test_preflight.py tests/fixtures/preflight/schema_walker_min.json
git commit -m "preflight: Finding, local \$ref resolution, arm selection (design 2026-09-04, task 1)"
```

---

### Task 2: The schema walker (`diff_schema`)

**Files:**
- Modify: `omega/preflight.py` (append)
- Modify: `tests/test_preflight.py` (append)

**Interfaces:**
- Consumes: `deref`, `resolve_arms`, `Finding` from Task 1.
- Produces: `diff_schema(body: dict, arm: dict, root: dict) -> list[Finding]` with classes `UNDECLARED`, `MISSING_REQUIRED`, `ENUM`, `BOUNDS`, `UNSUPPORTED`, `INFO` (one `pattern-unchecked` INFO per pattern-bearing path); and `_join(path: str, key: str) -> str` (path syntax: `a.b[3].c`).

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_preflight.py

def _create_arm():
    arms, root = P.resolve_arms(MINI)
    return arms["CREATE"], root


def _good_body():
    return {
        "operation": "CREATE", "name": "walker", "timeframe": "1h",
        "sections": [{"kind": "platform", "sectionKey": "includeRsi"},
                     {"kind": "custom", "title": "t", "benchmarkTicker": None, "notes": "n",
                      "columns": [{"metric": "RSI14", "transformId": "value", "timeframe": {"rel": "anchor"}, "window": 4}]}],
        "conditions": [{"conditionKey": "A_ONE", "name": "n", "definition": {"kind": "clause"},
                        "verdict": None, "required": False, "exit": False, "clock": "LIVE", "closes": 1}],
        "rules": [{"signalId": "rsi_oversold", "allocation": 2, "required": False, "params": {}}],
        "entry": {"trigger": "AT_SIGNAL", "confirmTf": "1h", "closes": 1, "bandAtrMultiple": 1,
                  "levelSource": "SWING_HIGH", "levelOffsetAtrMultiple": 0, "validForBars": 4},
    }


def _fails(findings):
    return [(f.cls, f.path) for f in findings if f.verdict == "FAIL"]


def test_walker_passes_a_conforming_body():
    arm, root = _create_arm()
    assert _fails(P.diff_schema(_good_body(), arm, root)) == []


def test_walker_flags_missing_required_at_nested_paths():
    arm, root = _create_arm()
    body = _good_body()
    del body["conditions"][0]["exit"]           # drift #5's exact shape
    del body["entry"]["validForBars"]           # drift #4's exact shape
    fails = _fails(P.diff_schema(body, arm, root))
    assert ("MISSING_REQUIRED", "conditions[0].exit") in fails
    assert ("MISSING_REQUIRED", "entry.validForBars") in fails


def test_walker_flags_undeclared_keys_and_says_it_is_schema_derived():
    arm, root = _create_arm()
    body = _good_body(); body["plan"] = {}      # the 2026-08-24 write-path key
    [f] = [f for f in P.diff_schema(body, arm, root) if f.cls == "UNDECLARED"]
    assert f.path == "plan" and "not measured" in f.detail


def test_walker_flags_enum_const_and_bounds():
    arm, root = _create_arm()
    body = _good_body()
    body["entry"]["trigger"] = "ON_RETEST"      # not in the miniature's enum
    body["entry"]["validForBars"] = 25          # > maximum 24
    body["entry"]["bandAtrMultiple"] = 0        # exclusiveMinimum 0
    body["sections"][1]["columns"][0]["window"] = 0
    body["name"] = ""                           # minLength 1
    fails = _fails(P.diff_schema(body, arm, root))
    assert ("ENUM", "entry.trigger") in fails
    assert ("BOUNDS", "entry.validForBars") in fails
    assert ("BOUNDS", "entry.bandAtrMultiple") in fails
    assert ("BOUNDS", "sections[1].columns[0].window") in fails
    assert ("BOUNDS", "name") in fails


def test_walker_type_mismatch_is_a_bounds_finding():
    arm, root = _create_arm()
    body = _good_body(); body["conditions"][0]["closes"] = "1"
    assert ("BOUNDS", "conditions[0].closes") in _fails(P.diff_schema(body, arm, root))


def test_walker_anyof_by_kind_const_and_by_type():
    arm, root = _create_arm()
    body = _good_body()
    body["sections"][1]["notes"] = None         # null branch of notes
    body["sections"][1]["columns"][0]["timeframe"] = {"abs": "4h"}   # second branch, via $ref
    assert _fails(P.diff_schema(body, arm, root)) == []
    body["sections"][1]["columns"][0]["timeframe"] = {"abs": "1d"}   # not in the ref'd enum
    assert ("ENUM", "sections[1].columns[0].timeframe.abs") in _fails(P.diff_schema(body, arm, root))


def test_walker_reports_unmatched_anyof_as_unsupported_not_silence():
    arm, root = _create_arm()
    body = _good_body(); body["sections"].append({"kind": "mystery"})
    [f] = [f for f in P.diff_schema(body, arm, root) if f.cls == "UNSUPPORTED"]
    assert f.path == "sections[2]" and f.verdict == "WARN"


def test_walker_reports_pattern_unchecked_once_per_path_as_info():
    arm, root = _create_arm()
    infos = [f for f in P.diff_schema(_good_body(), arm, root) if f.cls == "INFO"]
    assert any(f.path == "conditions[0].conditionKey" and "pattern" in f.detail for f in infos)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_preflight.py -v -k walker`
Expected: FAIL with `AttributeError: module 'omega.preflight' has no attribute 'diff_schema'`.

- [ ] **Step 3: Write the implementation**

```python
# append to omega/preflight.py

def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


_NUM = (int, float)


def _is_num(v: object) -> bool:
    return isinstance(v, _NUM) and not isinstance(v, bool)


def _type_ok(t: str | None, v: object) -> bool:
    if t is None:
        return True
    return {"object": isinstance(v, dict), "array": isinstance(v, list),
            "string": isinstance(v, str), "boolean": isinstance(v, bool),
            "null": v is None, "number": _is_num(v),
            "integer": isinstance(v, int) and not isinstance(v, bool)}.get(t, True)


def _pick_branch(value: object, branches: list, root: dict) -> dict | None:
    cands = [deref(b, root) for b in branches]
    if isinstance(value, dict):
        for b in cands:
            props = b.get("properties", {})
            for disc in ("operation", "kind", "mode"):
                if disc in props:
                    d = deref(props[disc], root)
                    if "const" in d and value.get(disc) == d["const"]:
                        return b
        for b in cands:                                   # no discriminator: required-keys fit
            if b.get("type", "object") == "object" and all(k in value for k in b.get("required", [])) \
                    and not any(disc in b.get("properties", {}) and "const" in deref(b["properties"][disc], root)
                                for disc in ("operation", "kind", "mode")):
                return b
        return None
    for b in cands:
        if "enum" in b and value in b["enum"]:
            return b
        if "const" in b and value == b["const"]:
            return b
        if "type" in b and _type_ok(b["type"], value) and "enum" not in b and "const" not in b:
            return b
    return None


def _walk(value: object, schema: dict, root: dict, path: str, out: list[Finding]) -> None:
    schema = deref(schema, root)
    if "anyOf" in schema:
        branch = _pick_branch(value, schema["anyOf"], root)
        if branch is None:
            out.append(Finding("UNSUPPORTED", path, "no anyOf branch matches the value", "WARN"))
            return
        schema = branch
    if "const" in schema and value != schema["const"]:
        out.append(Finding("ENUM", path, f"{value!r} is not the declared const {schema['const']!r}", "FAIL"))
        return
    if "enum" in schema and value not in schema["enum"]:
        out.append(Finding("ENUM", path, f"{value!r} not in the declared enum ({len(schema['enum'])} values)", "FAIL"))
        return
    t = schema.get("type")
    if isinstance(t, str) and not _type_ok(t, value):
        out.append(Finding("BOUNDS", path, f"expected type {t}, got {type(value).__name__}", "FAIL"))
        return
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                out.append(Finding("MISSING_REQUIRED", _join(path, k), "required by the published schema", "FAIL"))
        for k, v in value.items():
            if k in props:
                _walk(v, props[k], root, _join(path, k), out)
            elif schema.get("additionalProperties") is False:
                out.append(Finding("UNDECLARED", _join(path, k),
                                   "not declared by the published schema (additionalProperties:false is "
                                   "schema-derived, not measured - write_surface_gap.json)", "FAIL"))
            elif isinstance(schema.get("additionalProperties"), dict):
                _walk(v, schema["additionalProperties"], root, _join(path, k), out)
    elif isinstance(value, list):
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            out.append(Finding("BOUNDS", path, f"{len(value)} items > maxItems {schema['maxItems']}", "FAIL"))
        if "minItems" in schema and len(value) < schema["minItems"]:
            out.append(Finding("BOUNDS", path, f"{len(value)} items < minItems {schema['minItems']}", "FAIL"))
        if "items" in schema:
            for i, v in enumerate(value):
                _walk(v, schema["items"], root, f"{path}[{i}]", out)
    elif _is_num(value):
        v = value
        if "minimum" in schema and v < schema["minimum"]:
            out.append(Finding("BOUNDS", path, f"{v} < minimum {schema['minimum']}", "FAIL"))
        if "maximum" in schema and v > schema["maximum"]:
            out.append(Finding("BOUNDS", path, f"{v} > maximum {schema['maximum']}", "FAIL"))
        if "exclusiveMinimum" in schema and v <= schema["exclusiveMinimum"]:
            out.append(Finding("BOUNDS", path, f"{v} <= exclusiveMinimum {schema['exclusiveMinimum']}", "FAIL"))
        if "exclusiveMaximum" in schema and v >= schema["exclusiveMaximum"]:
            out.append(Finding("BOUNDS", path, f"{v} >= exclusiveMaximum {schema['exclusiveMaximum']}", "FAIL"))
    elif isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            out.append(Finding("BOUNDS", path, f"length {len(value)} < minLength {schema['minLength']}", "FAIL"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            out.append(Finding("BOUNDS", path, f"length {len(value)} > maxLength {schema['maxLength']}", "FAIL"))
        if "pattern" in schema:
            out.append(Finding("INFO", path, f"pattern-unchecked: {schema['pattern']!r} (no regex engine "
                                             "for \\p classes; validated by the platform, not here)", "INFO"))


def diff_schema(body: dict, arm: dict, root: dict) -> list[Finding]:
    """Walk `body` against one operation arm of the published definition."""
    out: list[Finding] = []
    _walk(body, arm, root, "", out)
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_preflight.py -v`
Expected: 13 passed.

- [ ] **Step 5: Commit**

Run: `python -m pytest -q` — expected `938 passed`.

```bash
git add omega/preflight.py tests/test_preflight.py
git commit -m "preflight: schema walker - UNDECLARED / MISSING_REQUIRED / ENUM / BOUNDS / UNSUPPORTED (task 2)"
```

---

### Task 3: The record diff (`diff_record`) — replays of drift #4 and #5

**Files:**
- Modify: `omega/preflight.py` (append)
- Modify: `tests/test_preflight.py` (append)

**Interfaces:**
- Consumes: `Finding`, `_join`.
- Produces: `diff_record(body: dict, record: dict, arm: dict, root: dict) -> list[Finding]`; constants `RECORD_ALIASES = {"rules": "signalRules"}` and `KNOWN_DELTAS = {"sections[].sectionKey": "..."}`; helper `record_request_view(record: dict) -> dict` (the record's top-level `strategy` object if wrapped, else the record itself).

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_preflight.py

RESEARCH = ROOT / "data" / "research" / "2026-08-29-deep-tail-fade"
V4 = json.loads((RESEARCH / "compile_body_deep_tail_fade_v4.json").read_text(encoding="utf-8"))
V5 = json.loads((RESEARCH / "compile_body_deep_tail_fade_v5.json").read_text(encoding="utf-8"))
PRESTATE = json.loads((ROOT / "data/audit/first_generated_update_2026-08-29.json").read_text(encoding="utf-8"))["probes"]["preState"]["strategy"]
DRIFT5 = json.loads((ROOT / "data/audit/drift5_exit_rediscovery_2026-09-04.json").read_text(encoding="utf-8"))


def _body(doc):
    return doc.get("request", doc)


def _migrated_record():
    """The 2026-08-29 genuine read-back, migrated the way drift #3/#4/#5 records read
    back on 2026-09-04 (drift5_exit_rediscovery_2026-09-04.json): every condition gains
    exit=false, clock=LIVE, closes=1 in the platform's key order; entry gains the seven
    mirrored fields; decisionInvalidationExitEnabled=true. BUILT from records, labelled
    as such - the first live run replaces it with a verbatim capture."""
    rec = json.loads(json.dumps(PRESTATE))
    rec["conditions"] = [
        {"conditionKey": c["conditionKey"], "name": c["name"], "definition": c["definition"],
         "verdict": c["verdict"], "required": c["required"], "exit": False, "clock": "LIVE", "closes": 1}
        for c in rec["conditions"]]
    rec["entry"] = dict(DRIFT5["readbacks"]["6a8bca67-45a3-428e-85ba-71ec2cd2218e"]["entry_verbatim"])
    rec["decisionInvalidationExitEnabled"] = True
    return rec


def test_replay_drift4_three_entry_fields_missing_vs_record():
    arm, root = _create_arm()
    fails = _fails(P.diff_record(_body(V4), _migrated_record(), arm, root))
    assert {("MISSING_VS_RECORD", "entry.levelSource"), ("MISSING_VS_RECORD", "entry.levelOffsetAtrMultiple"),
            ("MISSING_VS_RECORD", "entry.validForBars")} <= set(fails)


def test_replay_drift5_exit_missing_on_every_condition_vs_record():
    arm, root = _create_arm()
    fails = _fails(P.diff_record(_body(V5), _migrated_record(), arm, root))
    assert ("MISSING_VS_RECORD", "conditions[*].exit") in fails
    [f] = [f for f in P.diff_record(_body(V5), _migrated_record(), arm, root) if f.path == "conditions[*].exit"]
    assert "7/7" in f.detail


def test_record_diff_is_quiet_when_the_body_carries_everything_the_record_does():
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    for c in body["conditions"]:
        c["exit"] = False
    assert _fails(P.diff_record(body, _migrated_record(), arm, root)) == []


def test_record_diff_top_level_optional_and_server_keys_are_info_not_fail():
    """The 16 platform-defaulted execution parameters (measured 2026-08-27) and the
    optional decisionInvalidationExitEnabled are INFO; id/revision/createdAt are INFO."""
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    for c in body["conditions"]:
        c["exit"] = False
    finds = P.diff_record(body, _migrated_record(), arm, root)
    assert all(f.verdict != "FAIL" for f in finds)
    infos = {f.path for f in finds if f.verdict == "INFO"}
    assert {"minAtrPct", "decisionInvalidationExitEnabled", "id", "revision"} <= infos


def test_record_diff_uses_intersection_for_arrays_and_knows_the_two_deltas():
    """signalRules<->rules alias and the server-minted custom sectionKey never fire;
    a column key present on only SOME record columns never fires."""
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    for c in body["conditions"]:
        c["exit"] = False
    rec = _migrated_record()
    rec["sections"][0]["sectionKey"] = "custom:00000000-0000-4000-8000-000000000000"
    rec["sections"][0]["columns"][0]["window"] = 4      # only on one record column
    paths = {f.path for f in P.diff_record(body, rec, arm, root) if f.verdict == "FAIL"}
    assert not any(p.endswith("sectionKey") for p in paths)
    assert not any("columns" in p for p in paths)
    assert not any("signalRules" in p or p.startswith("rules") for p in paths)


def test_record_diff_top_level_object_the_body_lacks_is_a_warn():
    arm, root = _create_arm()
    body = _body(json.loads(json.dumps(V5)))
    del body["entry"]
    for c in body["conditions"]:
        c["exit"] = False
    [f] = [f for f in P.diff_record(body, _migrated_record(), arm, root) if f.path == "entry"]
    assert f.cls == "MISSING_VS_RECORD" and f.verdict == "WARN"


def test_record_request_view_unwraps_the_get_strategy_envelope():
    assert P.record_request_view({"strategy": {"id": "x"}}) == {"id": "x"}
    assert P.record_request_view({"id": "x"}) == {"id": "x"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_preflight.py -v -k "record or replay"`
Expected: FAIL with `AttributeError: ... 'diff_record'`.

- [ ] **Step 3: Write the implementation**

```python
# append to omega/preflight.py

# Two structural deltas between a wire body and a read-back, each measured, and nothing
# else is allowlisted: the record names `rules` `signalRules` (2026-08-29 read-back), and
# the platform mints `sectionKey` on custom sections (custom:<uuid>, never sent).
RECORD_ALIASES: dict[str, str] = {"rules": "signalRules"}
KNOWN_DELTAS: dict[str, str] = {
    "sections[].sectionKey": "server-minted on CREATE (custom:<uuid>), never sent - measured 2026-08-28",
}
# Request-shaped nested objects: a record key the body lacks here is a FAIL whether or not
# the schema declares it - drift #3 and #4 were exactly undeclared-but-present-in-the-record.
NESTED_REQUEST_OBJECTS = ("entry",)
NESTED_REQUEST_ARRAYS = ("conditions", "sections", "rules")


def record_request_view(record: dict) -> dict:
    """get_strategy wraps the record as {"strategy": {...}}; captures may hold either."""
    inner = record.get("strategy")
    return inner if isinstance(inner, dict) else record


def _intersection_keys(elems: list) -> set[str]:
    dicts = [e for e in elems if isinstance(e, dict)]
    if not dicts:
        return set()
    keys = set(dicts[0])
    for d in dicts[1:]:
        keys &= set(d)
    return keys


def _missing_in_elements(body_elems: list, rec_elems: list, path: str, out: list[Finding],
                         kinds: tuple[str, ...] | None = None) -> None:
    """One finding per record key absent from body elements, aggregated as
    '<path>[*].<key>' with a 'missing in k/n' count. `kinds` restricts the comparison to
    elements sharing a `kind` (custom sections vs custom sections)."""
    if kinds:
        body_elems = [e for e in body_elems if isinstance(e, dict) and e.get("kind") in kinds]
        rec_elems = [e for e in rec_elems if isinstance(e, dict) and e.get("kind") in kinds]
    exemplar = _intersection_keys(rec_elems)
    body_dicts = [e for e in body_elems if isinstance(e, dict)]
    if not exemplar or not body_dicts:
        return
    for key in sorted(exemplar):
        delta_key = f"{path}[].{key}"
        if delta_key in KNOWN_DELTAS:
            continue
        missing = sum(1 for e in body_dicts if key not in e)
        if missing:
            out.append(Finding("MISSING_VS_RECORD", f"{path}[*].{key}",
                               f"present on every record element, missing in {missing}/{len(body_dicts)} "
                               f"body elements", "FAIL"))
        # one level down: columns inside sections, params inside rules are objects whose
        # key sets vary by design; columns are compared by intersection too
        if key == "columns":
            rec_cols = [c for e in rec_elems if isinstance(e, dict) for c in e.get("columns", [])]
            body_cols = [c for e in body_dicts for c in e.get("columns", [])]
            _missing_in_elements(body_cols, rec_cols, f"{path}[].columns", out)


def diff_record(body: dict, record: dict, arm: dict, root: dict) -> list[Finding]:
    """Compare a wire body against a verbatim read-back of an existing record."""
    rec = record_request_view(record)
    arm = deref(arm, root)
    props = arm.get("properties", {})
    required = set(arm.get("required", []))
    out: list[Finding] = []
    body_key_of = {v: k for k, v in RECORD_ALIASES.items()}
    for rk, rv in rec.items():
        bk = body_key_of.get(rk, rk)
        if bk in body:
            continue
        if bk in required:
            continue                       # already MISSING_REQUIRED from diff_schema
        if isinstance(rv, dict) and bk in NESTED_REQUEST_OBJECTS:
            out.append(Finding("MISSING_VS_RECORD", bk, "the record carries this object; the body omits it "
                               "entirely (a human decides whether to mirror it)", "WARN"))
        elif bk in props:
            out.append(Finding("INFO", bk, "declared optional; the record carries a value the body omits "
                               "(platform default or deliberate omission)", "INFO"))
        else:
            out.append(Finding("INFO", bk, "server-derived key on the record, not part of the request", "INFO"))
    for name in NESTED_REQUEST_OBJECTS:
        if isinstance(body.get(name), dict) and isinstance(rec.get(name), dict):
            for key in sorted(set(rec[name]) - set(body[name])):
                out.append(Finding("MISSING_VS_RECORD", _join(name, key),
                                   "the record carries this field; the body omits it", "FAIL"))
    for name in NESTED_REQUEST_ARRAYS:
        rec_name = RECORD_ALIASES.get(name, name)
        b, r = body.get(name), rec.get(rec_name)
        if not (isinstance(b, list) and isinstance(r, list)):
            continue
        if name == "sections":
            _missing_in_elements(b, r, name, out, kinds=("custom",))
            _missing_in_elements(b, r, name, out, kinds=("platform",))
        else:
            _missing_in_elements(b, r, name, out)
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_preflight.py -v`
Expected: 20 passed.

- [ ] **Step 5: Commit**

```bash
git add omega/preflight.py tests/test_preflight.py
git commit -m "preflight: record diff replays drift #4 and #5 from real records (task 3)"
```

---

### Task 4: Mirrors, changelog and fingerprints

**Files:**
- Modify: `omega/preflight.py` (append)
- Modify: `tests/test_preflight.py` (append)

**Interfaces:**
- Produces: `mirror_findings(body: dict, record: dict) -> list[Finding]` (WARN only; entry fields except `confirmTf`; conditions' `clock`/`closes`/`exit` against the set of record values); `schema_index(arm: dict, root: dict) -> dict[str, dict]` mapping a path to `{"enum": [...] | None, "required": [...], "properties": [...], "bounds": {...}}`; `changelog(previous: dict[str, dict], current: dict[str, dict]) -> list[Finding]` (INFO only); `fingerprint_schema(arm: dict, root: dict, *, signal_ids: set[str], template_keys: set[str], timeframes: list[str]) -> list[Finding]`; `fingerprint_readback(record: dict, strategy_id: str) -> list[Finding]` (both `TRANSCRIPTION_SUSPECT`, FAIL).

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_preflight.py

MIRROR_ENTRY = {"trigger": "AT_SIGNAL", "confirmTf": "1h", "closes": 1, "bandAtrMultiple": 1,
                "levelSource": "SWING_HIGH", "levelOffsetAtrMultiple": 0, "validForBars": 4}


def test_mirror_is_quiet_when_values_match_and_ignores_confirmTf():
    rec = _migrated_record()
    body = {"entry": dict(MIRROR_ENTRY, confirmTf="4h"),
            "conditions": [{"clock": "LIVE", "closes": 1, "exit": False}]}
    assert P.mirror_findings(body, rec) == []


def test_mirror_warns_never_fails_on_a_differing_mirror_value():
    rec = _migrated_record()
    body = {"entry": dict(MIRROR_ENTRY, validForBars=6),
            "conditions": [{"clock": "CLOSE", "closes": 1, "exit": False}]}
    finds = P.mirror_findings(body, rec)
    assert {(f.cls, f.path, f.verdict) for f in finds} == {
        ("MIRROR", "entry.validForBars", "WARN"), ("MIRROR", "conditions[0].clock", "WARN")}


def test_schema_index_and_changelog_see_enum_growth_and_new_optional_keys():
    arm, root = _create_arm()
    cur = json.loads(json.dumps(MINI))
    cur_arm, cur_root = P.resolve_arms(cur)
    cur_arm["properties"]["entry"]["properties"]["trigger"]["enum"] += ["STOP_THROUGH_LEVEL", "ON_RETEST"]
    cur_arm["properties"]["newOptional"] = {"type": "boolean"}
    cur_arm["properties"]["entry"]["properties"]["validForBars"]["maximum"] = 48
    prev_idx, cur_idx = P.schema_index(arm, root), P.schema_index(cur_arm, cur_root)
    log = P.changelog(prev_idx, cur_idx)
    assert all(f.cls == "CHANGELOG" and f.verdict == "INFO" for f in log)
    details = " | ".join(f"{f.path}: {f.detail}" for f in log)
    assert "entry.trigger" in details and "STOP_THROUGH_LEVEL" in details
    assert "newOptional" in details
    assert "validForBars" in details and "48" in details


def test_schema_index_terminates_on_a_recursive_definition():
    arm, root = _create_arm()
    arm = json.loads(json.dumps(arm))
    arm["properties"]["conditions"]["items"]["properties"]["definition"] = {
        "anyOf": [{"type": "object", "properties": {"members": {"type": "array", "items": {
            "$ref": "#/properties/request/anyOf/0/properties/conditions/items/properties/definition"}}}}]}
    root2 = json.loads(json.dumps(root)); root2["properties"]["request"]["anyOf"][0] = arm
    idx = P.schema_index(arm, root2)
    assert "conditions[].definition" in idx


def test_fingerprint_schema_flags_a_truncated_enum_as_transcription_suspect():
    arm, root = _create_arm()
    ok = P.fingerprint_schema(arm, root, signal_ids={"rsi_oversold", "rsi_overbought"},
                              template_keys={"includeRsi", "includeMacd"}, timeframes=["1h", "4h"])
    assert ok == []
    bad = P.fingerprint_schema(arm, root, signal_ids={"rsi_oversold", "rsi_overbought", "macd_bull_cross"},
                               template_keys={"includeRsi", "includeMacd"}, timeframes=["1h", "4h"])
    assert [f.cls for f in bad] == ["TRANSCRIPTION_SUSPECT"] and bad[0].verdict == "FAIL"
    assert "rules[].signalId" in bad[0].path


def test_fingerprint_readback_checks_id_rules_and_conditions():
    rec = {"strategy": _migrated_record()}
    assert P.fingerprint_readback(rec, "6a8bca67-45a3-428e-85ba-71ec2cd2218e") == []
    wrong = P.fingerprint_readback(rec, "00000000-0000-4000-8000-000000000000")
    assert wrong and wrong[0].cls == "TRANSCRIPTION_SUSPECT"
    short = json.loads(json.dumps(rec)); short["strategy"]["signalRules"] = short["strategy"]["signalRules"][:83]
    assert any("signalRules" in f.path for f in P.fingerprint_readback(short, rec["strategy"]["id"]))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_preflight.py -v -k "mirror or changelog or fingerprint or index"`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Write the implementation**

```python
# append to omega/preflight.py

# Values omega hardcodes as platform mirrors. confirmTf is excluded: it is the thesis
# anchor by design (Step 0 amendment, 2026-08-30). sections[].notes is excluded: omega sends a
# provenance string on purpose while null acceptance is unmeasured.
MIRROR_ENTRY_FIELDS = ("trigger", "closes", "bandAtrMultiple", "levelSource",
                       "levelOffsetAtrMultiple", "validForBars")
MIRROR_CONDITION_FIELDS = ("clock", "closes", "exit")


def mirror_findings(body: dict, record: dict) -> list[Finding]:
    """WARN when a hardcoded mirror differs from what the reference record carries."""
    rec = record_request_view(record)
    out: list[Finding] = []
    be, re_ = body.get("entry"), rec.get("entry")
    if isinstance(be, dict) and isinstance(re_, dict):
        for k in MIRROR_ENTRY_FIELDS:
            if k in be and k in re_ and be[k] != re_[k]:
                out.append(Finding("MIRROR", _join("entry", k),
                                   f"body {be[k]!r} vs record {re_[k]!r} - the user decides whether to re-mirror", "WARN"))
    rconds = [c for c in rec.get("conditions", []) if isinstance(c, dict)]
    for k in MIRROR_CONDITION_FIELDS:
        seen = {c[k] if not isinstance(c.get(k), (list, dict)) else None for c in rconds if k in c}
        if not seen:
            continue
        for i, c in enumerate(body.get("conditions", [])):
            if isinstance(c, dict) and k in c and c[k] not in seen:
                out.append(Finding("MIRROR", f"conditions[{i}].{k}",
                                   f"body {c[k]!r}; the record's conditions carry {sorted(map(repr, seen))}", "WARN"))
    return out


_BOUND_KEYS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
               "minLength", "maxLength", "minItems", "maxItems")


def schema_index(arm: dict, root: dict) -> dict[str, dict]:
    """Flatten an arm to {path: {enum, required, properties, bounds}} for changelog diffs.
    Recursion is cut on a schema node already on the current path."""
    out: dict[str, dict] = {}

    def visit(node: dict, path: str, stack: tuple[int, ...]) -> None:
        node = deref(node, root)
        if id(node) in stack:
            return
        stack = stack + (id(node),)
        if "anyOf" in node:
            for i, b in enumerate(node["anyOf"]):
                visit(b, f"{path}|{i}" if path else f"|{i}", stack)
            return
        entry = out.setdefault(path, {"enum": None, "required": [], "properties": [], "bounds": {}})
        if "enum" in node:
            entry["enum"] = list(node["enum"])
        if "const" in node:
            entry["enum"] = [node["const"]]
        entry["required"] = sorted(set(entry["required"]) | set(node.get("required", [])))
        entry["properties"] = sorted(set(entry["properties"]) | set(node.get("properties", {})))
        for k in _BOUND_KEYS:
            if k in node:
                entry["bounds"][k] = node[k]
        for k, sub in node.get("properties", {}).items():
            visit(sub, _join(path, k), stack)
        if "items" in node:
            visit(node["items"], f"{path}[]", stack)

    visit(arm, "", ())
    return out


def changelog(previous: dict[str, dict], current: dict[str, dict]) -> list[Finding]:
    """INFO-only differences between two schema indexes (enum growth, new/removed keys,
    required-list and bound changes)."""
    out: list[Finding] = []
    for path in sorted(set(previous) | set(current)):
        p, c = previous.get(path), current.get(path)
        if p is None:
            out.append(Finding("CHANGELOG", path, "new in the current schema", "INFO")); continue
        if c is None:
            out.append(Finding("CHANGELOG", path, "removed from the current schema", "INFO")); continue
        if (p["enum"] or []) != (c["enum"] or []):
            added = [v for v in (c["enum"] or []) if v not in (p["enum"] or [])]
            removed = [v for v in (p["enum"] or []) if v not in (c["enum"] or [])]
            out.append(Finding("CHANGELOG", path, f"enum added {added} removed {removed}", "INFO"))
        if p["required"] != c["required"]:
            out.append(Finding("CHANGELOG", path, f"required {p['required']} -> {c['required']}", "INFO"))
        if p["properties"] != c["properties"]:
            out.append(Finding("CHANGELOG", path,
                               f"properties added {sorted(set(c['properties']) - set(p['properties']))} "
                               f"removed {sorted(set(p['properties']) - set(c['properties']))}", "INFO"))
        if p["bounds"] != c["bounds"]:
            out.append(Finding("CHANGELOG", path, f"bounds {p['bounds']} -> {c['bounds']}", "INFO"))
    return out


def _enum_at(arm: dict, root: dict, *keys: str) -> list | None:
    node = deref(arm, root)
    for k in keys:
        node = deref(node, root)
        if k == "[]":
            node = node.get("items", {})
        elif k.startswith("anyOf:"):
            want = k.split(":", 1)[1]
            for b in node.get("anyOf", []):
                b = deref(b, root)
                kind = deref(b.get("properties", {}).get("kind", {}), root)
                if kind.get("const") == want:
                    node = b
                    break
            else:
                return None
        else:
            node = node.get("properties", {}).get(k, {})
    node = deref(node, root)
    return node.get("enum")


def fingerprint_schema(arm: dict, root: dict, *, signal_ids: set[str], template_keys: set[str],
                       timeframes: list[str]) -> list[Finding]:
    """Fidelity of an agent-transcribed schema capture against data the repo holds
    independently (union of moduleSignals, platform templates, absoluteTimeframes)."""
    out: list[Finding] = []
    checks = (
        ("rules[].signalId", _enum_at(arm, root, "rules", "[]", "signalId"), signal_ids),
        ("sections[].platform.sectionKey", _enum_at(arm, root, "sections", "[]", "anyOf:platform", "sectionKey"), template_keys),
        ("timeframe", _enum_at(arm, root, "timeframe"), set(timeframes)),
    )
    for path, got, want in checks:
        if got is None:
            out.append(Finding("TRANSCRIPTION_SUSPECT", path, "enum not found in the capture", "FAIL"))
        elif set(got) != set(want) or len(got) != len(set(got)):
            out.append(Finding("TRANSCRIPTION_SUSPECT", path,
                               f"enum has {len(got)} values, repo data has {len(want)}; "
                               f"missing {sorted(set(want) - set(got))[:5]} extra {sorted(set(got) - set(want))[:5]}", "FAIL"))
    if not deref(arm, root).get("required"):
        out.append(Finding("TRANSCRIPTION_SUSPECT", "", "arm has no required list", "FAIL"))
    return out


def fingerprint_readback(record: dict, strategy_id: str) -> list[Finding]:
    rec = record_request_view(record)
    out: list[Finding] = []
    if rec.get("id") != strategy_id:
        out.append(Finding("TRANSCRIPTION_SUSPECT", "id", f"record id {rec.get('id')!r} != requested {strategy_id!r}", "FAIL"))
    rules = rec.get("signalRules")
    if not isinstance(rules, list) or len(rules) != 84:
        out.append(Finding("TRANSCRIPTION_SUSPECT", "signalRules",
                           f"expected 84 signalRules (every read-back since 2026-08-28), got "
                           f"{len(rules) if isinstance(rules, list) else type(rules).__name__}", "FAIL"))
    conds = rec.get("conditions")
    if not isinstance(conds, list) or not conds:
        out.append(Finding("TRANSCRIPTION_SUSPECT", "conditions", "expected a non-empty conditions list", "FAIL"))
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_preflight.py -v`
Expected: 26 passed.

- [ ] **Step 5: Commit**

```bash
git add omega/preflight.py tests/test_preflight.py
git commit -m "preflight: mirrors (WARN), changelog (INFO), transcription fingerprints (task 4)"
```

---

### Task 5: Verdict, receipt, gate check

**Files:**
- Modify: `omega/preflight.py` (append)
- Modify: `tests/test_preflight.py` (append)

**Interfaces:**
- Produces: `body_sha256(body: dict) -> str` (sha256 of `json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`); `verdict(findings: list[Finding]) -> str` (`"PASS"`|`"FAIL"`); `build_receipt(*, body: dict, body_path: str, operation: str, schema_meta: dict, readback_meta: dict, findings: list[Finding], now: datetime, expires_minutes: int = 60, unmeasured: list[str] | None = None) -> dict`; `gate_check(receipt: dict, body: dict, now: datetime) -> tuple[bool, str]`; `GATE_LINE_PREFIX = "PREFLIGHT PASS"`; `gate_line(receipt: dict) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_preflight.py
from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 9, 4, 9, 0, tzinfo=timezone.utc)
SCHEMA_META = {"path": "data/contract/compile_strategy_plan/schema_20260904T085500Z.json",
               "capturedAt": "2026-09-04T08:55:00Z", "fingerprint": "ok"}
READBACK_META = {"path": "data/contract/get_strategy/b9438519_20260904T085800Z.json",
                 "capturedAt": "2026-09-04T08:58:00Z", "strategyId": "b9438519-8223-4ef1-a3c3-6f4592bb823d",
                 "revision": 2, "fingerprint": "ok"}


def test_body_sha256_is_canonical():
    a = P.body_sha256({"b": 1, "a": [1, 2]}); b = P.body_sha256({"a": [1, 2], "b": 1})
    assert a == b and len(a) == 64


def test_verdict_fails_only_on_fail_class_findings():
    assert P.verdict([]) == "PASS"
    assert P.verdict([P.Finding("MIRROR", "entry.closes", "d", "WARN"), P.Finding("INFO", "id", "d", "INFO")]) == "PASS"
    assert P.verdict([P.Finding("ENUM", "entry.trigger", "d", "FAIL")]) == "FAIL"


def test_receipt_carries_sha_expiry_disclaimer_and_findings():
    body = _good_body()
    r = P.build_receipt(body=body, body_path="x.json", operation="CREATE", schema_meta=SCHEMA_META,
                        readback_meta=READBACK_META, findings=[], now=NOW, unmeasured=["runtime enforcement of exit"])
    assert r["verdict"] == "PASS" and r["body"]["sha256"] == P.body_sha256(body)
    assert r["expiresAt"] == "2026-09-04T09:55:00Z"          # 60 min from the OLDER capture
    assert r["disclaimer"] == P.DISCLAIMER and r["voided"] is None
    assert r["unmeasured"] == ["runtime enforcement of exit"]
    assert P.gate_line(r).startswith("PREFLIGHT PASS") and "b9438519" in P.gate_line(r) and "rev 2" in P.gate_line(r)


def test_gate_check_passes_then_fails_on_expiry_sha_mismatch_fail_and_void():
    body = _good_body()
    r = P.build_receipt(body=body, body_path="x.json", operation="CREATE", schema_meta=SCHEMA_META,
                        readback_meta=READBACK_META, findings=[], now=NOW)
    assert P.gate_check(r, body, NOW) == (True, "PASS")
    assert P.gate_check(r, body, NOW + timedelta(hours=2))[0] is False
    other = dict(body, name="edited")
    ok, why = P.gate_check(r, other, NOW); assert not ok and "sha" in why
    failed = P.build_receipt(body=body, body_path="x.json", operation="CREATE", schema_meta=SCHEMA_META,
                             readback_meta=READBACK_META, findings=[P.Finding("ENUM", "p", "d", "FAIL")], now=NOW)
    assert P.gate_check(failed, body, NOW)[0] is False
    voided = dict(r, voided={"at": "2026-09-04T09:10:00Z", "reason": "refused", "refusalRecord": "x.json"})
    ok, why = P.gate_check(voided, body, NOW); assert not ok and "void" in why
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_preflight.py -v -k "sha or verdict or receipt or gate"`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Write the implementation**

```python
# append to omega/preflight.py
import hashlib
import json
from datetime import datetime, timedelta, timezone

GATE_LINE_PREFIX = "PREFLIGHT PASS"
_ISO = "%Y-%m-%dT%H:%M:%SZ"


def body_sha256(body: dict) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def verdict(findings: list[Finding]) -> str:
    return "FAIL" if any(f.verdict == "FAIL" for f in findings) else "PASS"


def _parse_iso(s: str) -> datetime:
    return datetime.strptime(s, _ISO).replace(tzinfo=timezone.utc)


def build_receipt(*, body: dict, body_path: str, operation: str, schema_meta: dict, readback_meta: dict,
                  findings: list[Finding], now: datetime, expires_minutes: int = 60,
                  unmeasured: list[str] | None = None) -> dict:
    oldest = min(_parse_iso(schema_meta["capturedAt"]), _parse_iso(readback_meta["capturedAt"]))
    return {
        "_what": "Schema-drift preflight receipt: the wire body diffed against a fresh compile "
                 "definition capture and a fresh read-back. A PASS is a precondition of the compile "
                 "authorization, not the authorization. Nothing here was interpreted.",
        "when": now.strftime(_ISO),
        "body": {"path": body_path, "sha256": body_sha256(body), "operation": operation},
        "captures": {"schema": dict(schema_meta), "readback": dict(readback_meta)},
        "findings": [f.__dict__ for f in findings],
        "verdict": verdict(findings),
        "expiresAt": (oldest + timedelta(minutes=expires_minutes)).strftime(_ISO),
        "disclaimer": DISCLAIMER,
        "unmeasured": list(unmeasured or []),
        "voided": None,
    }


def gate_line(receipt: dict, receipt_path: str = "<receipt>") -> str:
    rb = receipt["captures"]["readback"]
    return (f"{GATE_LINE_PREFIX} · {receipt_path} · body {receipt['body']['sha256'][:8]} · "
            f"schema {receipt['captures']['schema']['capturedAt']} · ref {rb['strategyId']} rev {rb['revision']} · "
            f"expires {receipt['expiresAt']}")


def gate_check(receipt: dict, body: dict, now: datetime) -> tuple[bool, str]:
    if receipt.get("voided"):
        return False, f"receipt voided: {receipt['voided']}"
    if receipt.get("verdict") != "PASS":
        return False, f"receipt verdict is {receipt.get('verdict')!r}"
    if receipt["body"]["sha256"] != body_sha256(body):
        return False, "body sha256 does not match the receipt (the body changed after the preflight)"
    if now >= _parse_iso(receipt["expiresAt"]):
        return False, f"receipt expired at {receipt['expiresAt']}; re-run the preflight"
    return True, "PASS"
```

Move the three `import` lines to the top of the module with the existing imports (keep the module's imports stdlib-only).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_preflight.py -v`
Expected: 30 passed.

- [ ] **Step 5: Commit**

Run: `python -m pytest -q` — expected `955 passed`.

```bash
git add omega/preflight.py tests/test_preflight.py
git commit -m "preflight: verdict, sha-bound expiring receipt, gate check (task 5)"
```

---

### Task 6: The CLI — `recipe`, `run`, `gate`

**Files:**
- Create: `scripts/preflight.py`
- Create: `tests/test_preflight_cli.py`

**Interfaces:**
- Consumes: everything in `omega.preflight`.
- Produces: `python scripts/preflight.py recipe <body.json> --reference <strategyId>`; `python scripts/preflight.py run <body.json> --schema <capture> --readback <capture> [--previous-schema <capture>] [--expires-minutes 60] [--out <receipt path>] [--now <ISO Z>]`; `python scripts/preflight.py gate <receipt> --body <body.json> [--now <ISO Z>]`. Exit 0 on PASS, 1 otherwise. `main(argv: list[str]) -> int` for tests.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_preflight_cli.py
"""End-to-end CLI in tmp_path: recipe text, run -> receipt, gate exit codes."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("preflight_cli", ROOT / "scripts" / "preflight.py")
cli = importlib.util.module_from_spec(spec); spec.loader.exec_module(cli)  # type: ignore[union-attr]

MINI = json.loads((ROOT / "tests/fixtures/preflight/schema_walker_min.json").read_text(encoding="utf-8"))
V5 = json.loads((ROOT / "data/research/2026-08-29-deep-tail-fade/compile_body_deep_tail_fade_v5.json").read_text(encoding="utf-8"))
PRESTATE = json.loads((ROOT / "data/audit/first_generated_update_2026-08-29.json").read_text(encoding="utf-8"))["probes"]["preState"]["strategy"]


def _captures(tmp_path):
    """A schema capture whose fingerprint enums are REPLACED by the repo's real sets, so the
    fingerprint passes; still the walker miniature otherwise."""
    schema = json.loads(json.dumps(MINI))
    arm = schema["parameters"]["properties"]["request"]["anyOf"][0]["properties"]
    arm["rules"]["items"]["properties"]["signalId"]["enum"] = sorted(cli.repo_signal_ids())
    arm["sections"]["items"]["anyOf"][0]["properties"]["sectionKey"]["enum"] = sorted(cli.repo_template_keys())
    arm["timeframe"]["enum"] = cli.repo_timeframes()
    arm["entry"]["properties"]["trigger"]["enum"] = ["AT_SIGNAL", "ON_CANDLE_CLOSE", "STOP_THROUGH_LEVEL", "ON_RETEST"]
    arm["entry"]["properties"]["levelSource"]["enum"] = ["SWING_HIGH", "SWING_LOW", "BOLLINGER_UPPER", "BOLLINGER_LOWER"]
    arm["sections"]["items"]["anyOf"][1]["properties"]["columns"]["items"]["properties"]["metric"] = {"type": "string"}
    arm["sections"]["items"]["anyOf"][1]["properties"]["columns"]["items"]["additionalProperties"] = True
    arm["conditions"]["items"]["properties"]["definition"] = {"type": "object"}
    sp = tmp_path / "schema_20260904T085500Z.json"
    sp.write_text(json.dumps({"capturedAt": "2026-09-04T08:55:00Z", "how": "ToolSearch (test)", "request": None,
                              "response": schema}), encoding="utf-8")
    rec = json.loads(json.dumps(PRESTATE))
    rec["conditions"] = [dict(c, exit=False, clock="LIVE", closes=1) for c in rec["conditions"]]
    rec["entry"] = {"trigger": "AT_SIGNAL", "confirmTf": "1h", "closes": 1, "bandAtrMultiple": 1,
                    "levelSource": "SWING_HIGH", "levelOffsetAtrMultiple": 0, "validForBars": 4}
    rp = tmp_path / "6a8bca67-45a3-428e-85ba-71ec2cd2218e_20260904T085800Z.json"
    rp.write_text(json.dumps({"capturedAt": "2026-09-04T08:58:00Z", "how": "get_strategy (test)",
                              "request": {"strategyId": rec["id"], "includeInactive": True},
                              "response": {"strategy": rec}}), encoding="utf-8")
    return sp, rp


def test_recipe_prints_numbered_steps_with_the_capture_paths(tmp_path, capsys):
    body = tmp_path / "body.json"; body.write_text(json.dumps(V5), encoding="utf-8")
    assert cli.main(["recipe", str(body), "--reference", "b9438519-8223-4ef1-a3c3-6f4592bb823d"]) == 0
    out = capsys.readouterr().out
    assert "ToolSearch" in out and "get_strategy" in out and "data/contract/compile_strategy_plan/" in out
    assert "includeInactive" in out and "6 KB" in out and "never" in out.lower()


def test_run_fails_the_v5_body_on_missing_exit_and_gate_refuses(tmp_path, capsys):
    sp, rp = _captures(tmp_path)
    body = tmp_path / "body.json"; body.write_text(json.dumps(V5), encoding="utf-8")
    out = tmp_path / "receipt.json"
    rc = cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                   "--now", "2026-09-04T09:00:00Z"])
    assert rc == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert receipt["verdict"] == "FAIL"
    paths = {f["path"] for f in receipt["findings"] if f["verdict"] == "FAIL"}
    assert "conditions[0].exit" in paths and "conditions[*].exit" in paths
    assert cli.main(["gate", str(out), "--body", str(body), "--now", "2026-09-04T09:01:00Z"]) == 1


def test_run_passes_once_exit_is_mirrored_and_gate_admits_then_expires(tmp_path, capsys):
    sp, rp = _captures(tmp_path)
    fixed = json.loads(json.dumps(V5))
    for c in fixed["request"]["conditions"]:
        c["exit"] = False
    body = tmp_path / "body.json"; body.write_text(json.dumps(fixed), encoding="utf-8")
    out = tmp_path / "receipt.json"
    rc = cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                   "--now", "2026-09-04T09:00:00Z"])
    printed = capsys.readouterr().out
    assert rc == 0 and "PREFLIGHT PASS" in printed and "runtime validator" in printed
    assert cli.main(["gate", str(out), "--body", str(body), "--now", "2026-09-04T09:30:00Z"]) == 0
    assert cli.main(["gate", str(out), "--body", str(body), "--now", "2026-09-04T11:00:00Z"]) == 1


def test_run_refuses_a_transcription_suspect_schema(tmp_path, capsys):
    sp, rp = _captures(tmp_path)
    doc = json.loads(sp.read_text(encoding="utf-8"))
    doc["response"]["parameters"]["properties"]["request"]["anyOf"][0]["properties"]["rules"]["items"]["properties"]["signalId"]["enum"].pop()
    sp.write_text(json.dumps(doc), encoding="utf-8")
    body = tmp_path / "body.json"; body.write_text(json.dumps(V5), encoding="utf-8")
    out = tmp_path / "receipt.json"
    assert cli.main(["run", str(body), "--schema", str(sp), "--readback", str(rp), "--out", str(out),
                     "--now", "2026-09-04T09:00:00Z"]) == 1
    receipt = json.loads(out.read_text(encoding="utf-8"))
    assert any(f["cls"] == "TRANSCRIPTION_SUSPECT" for f in receipt["findings"])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_preflight_cli.py -v`
Expected: FAIL with `FileNotFoundError` for `scripts/preflight.py`.

- [ ] **Step 3: Write the CLI**

```python
# scripts/preflight.py
"""Schema-drift preflight CLI (design: docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md).

  recipe <body.json> --reference <strategyId>
      Print the numbered, read-only session procedure for THIS body: which definition to
      load, which record to read back, exactly where to save each verbatim capture.
  run <body.json> --schema <capture> --readback <capture> [--previous-schema <capture>]
      [--expires-minutes 60] [--out data/audit/compile_preflight_<date>.json] [--now <ISO Z>]
      Diff the body against both captures; write the receipt; print the gate line.
      Exit 0 on PASS, 1 on FAIL.
  gate <receipt> --body <body.json> [--now <ISO Z>]
      Exit 0 only if the receipt is PASS, the body sha matches, it has not expired and
      it is not voided.

This script never calls the connector. The captures are agent transcriptions of read-only
calls; `run` checks their fidelity before it trusts them.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omega import preflight as P  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCHEMA_DIR = ROOT / "data" / "contract" / "compile_strategy_plan"
CAPTURE_READBACK_DIR = ROOT / "data" / "contract" / "get_strategy"
AUDIT_DIR = ROOT / "data" / "audit"
TOOL = "mcp__c330236a-7aee-4d07-ae11-e487c8cbc894__compile_strategy_plan"


def repo_signal_ids() -> set[str]:
    m = json.loads((ROOT / "data/derived/signal_module_map.json").read_text(encoding="utf-8"))["moduleSignals"]
    return {s for sigs in m.values() for s in sigs}


def repo_template_keys() -> set[str]:
    t = json.loads((ROOT / "data/contract/templates/platform/_all.json").read_text(encoding="utf-8"))["templates"]
    return {e["sectionKey"] for e in t}


def repo_timeframes() -> list[str]:
    return json.loads((ROOT / "data/contract/vocabulary/_shared.json").read_text(encoding="utf-8"))["absoluteTimeframes"]


def _load_body(path: str) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    return doc.get("request", doc) if isinstance(doc, dict) else doc


def _load_capture(path: str) -> tuple[dict, dict]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or "capturedAt" not in doc or "response" not in doc:
        raise SystemExit(f"{path}: not a capture (need capturedAt/how/request/response)")
    return doc, doc["response"]


def _now(arg: str | None) -> datetime:
    return P._parse_iso(arg) if arg else datetime.now(timezone.utc).replace(microsecond=0)


def cmd_recipe(a) -> int:
    body = _load_body(a.body)
    stamp = "<YYYYMMDDTHHMMSSZ, the UTC time of the fetch>"
    print(f"""Schema-drift preflight - read-only session procedure for {a.body}
(operation {body.get('operation', '?')}, {len(body.get('conditions', []))} conditions). Nothing below writes to the platform.

1. Load the compile definition (a definition load, NOT a call):
     ToolSearch  select:{TOOL}   max_results 1
   Save the returned definition VERBATIM to
     {CAPTURE_SCHEMA_DIR.relative_to(ROOT).as_posix()}/schema_{stamp}.json
   as {{"capturedAt": "<ISO Z>", "how": "ToolSearch select:<tool>", "request": null, "response": <the definition>}}.
   The definition is ~21 KB. If one Write fails or truncates, write it in <= 6 KB chunks and
   concatenate, and say so in "how". Never edit, reorder or repair the text.

2. Read back the reference record (read-only; quota-free per docs/10):
     get_strategy  {{"strategyId": "{a.reference}", "includeInactive": true}}
   Save the response VERBATIM to
     {CAPTURE_READBACK_DIR.relative_to(ROOT).as_posix()}/{a.reference}_{stamp}.json
   as {{"capturedAt": "<ISO Z>", "how": "get_strategy", "request": {{...the call...}}, "response": <the response>}}.

3. Run the diff:
     python scripts/preflight.py run {a.body} --schema <step 1 file> --readback <step 2 file>
   It checks the captures' fidelity first (signalId enum == 84 ids, 25 platform section keys,
   13 timeframes; record id, 84 signalRules), then diffs, writes the receipt under
   data/audit/, and prints the gate line.

4. On FAIL: stop. For each MISSING_* finding, mirror the record's value in omega in its own
   commit with tests; if no record carries the field, the user chooses and the receipt
   records it as user-chosen. Re-run step 3 (captures reusable within the expiry window).

5. On PASS: quote the printed gate line in the plan's authorization checkbox, then request
   the doc 20 section 5 authorization sentence from the user exactly as before. The preflight
   changes nothing about who authorizes the compile.""")
    return 0


def cmd_run(a) -> int:
    body = _load_body(a.body)
    schema_doc, definition = _load_capture(a.schema)
    readback_doc, record = _load_capture(a.readback)
    now = _now(a.now)
    operation = body.get("operation", "CREATE")
    arms, root = P.resolve_arms(definition)
    if operation not in arms:
        raise SystemExit(f"operation {operation!r} has no arm in the captured definition ({sorted(arms)})")
    arm = arms[operation]
    findings: list[P.Finding] = []
    findings += P.fingerprint_schema(arm, root, signal_ids=repo_signal_ids(),
                                     template_keys=repo_template_keys(), timeframes=repo_timeframes())
    strategy_id = (readback_doc.get("request") or {}).get("strategyId") or P.record_request_view(record).get("id")
    findings += P.fingerprint_readback(record, strategy_id)
    if not findings:
        findings += P.diff_schema(body, arm, root)
        findings += P.diff_record(body, record, arm, root)
        findings += P.mirror_findings(body, record)
        if a.previous_schema:
            _, prev_def = _load_capture(a.previous_schema)
            prev_arms, prev_root = P.resolve_arms(prev_def)
            if operation in prev_arms:
                findings += P.changelog(P.schema_index(prev_arms[operation], prev_root), P.schema_index(arm, root))
    rec = P.record_request_view(record)
    receipt = P.build_receipt(
        body=body, body_path=a.body, operation=operation,
        schema_meta={"path": a.schema, "capturedAt": schema_doc["capturedAt"],
                     "fingerprint": "ok" if not any(f.cls == "TRANSCRIPTION_SUSPECT" and f.path != "id" for f in findings) else "suspect"},
        readback_meta={"path": a.readback, "capturedAt": readback_doc["capturedAt"], "strategyId": strategy_id,
                       "revision": rec.get("revision"), "fingerprint": "ok" if not any(f.cls == "TRANSCRIPTION_SUSPECT" for f in findings) else "suspect"},
        findings=findings, now=now, expires_minutes=a.expires_minutes,
        unmeasured=["the runtime validator (only a compile observes it)",
                    "whether additionalProperties:false is enforced (schema-derived, not measured)",
                    "semantics of any field first seen in this capture"])
    out = Path(a.out) if a.out else AUDIT_DIR / f"compile_preflight_{now.strftime('%Y-%m-%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for f in findings:
        print(f"  [{f.verdict:4}] {f.cls:20} {f.path or '<root>'}: {f.detail}")
    print(f"receipt: {out}")
    if receipt["verdict"] == "PASS":
        print(P.gate_line(receipt, str(out)))
        print(f"note: {P.DISCLAIMER}")
        return 0
    print("PREFLIGHT FAIL - stop; mirror from a record, never invent (see the recipe, step 4)")
    return 1


def cmd_gate(a) -> int:
    receipt = json.loads(Path(a.receipt).read_text(encoding="utf-8"))
    ok, why = P.gate_check(receipt, _load_body(a.body), _now(a.now))
    print(P.gate_line(receipt, a.receipt) if ok else f"PREFLIGHT GATE REFUSED: {why}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("recipe"); r.add_argument("body"); r.add_argument("--reference", required=True)
    r.set_defaults(fn=cmd_recipe)
    u = sub.add_parser("run"); u.add_argument("body"); u.add_argument("--schema", required=True)
    u.add_argument("--readback", required=True); u.add_argument("--previous-schema")
    u.add_argument("--expires-minutes", type=int, default=60); u.add_argument("--out"); u.add_argument("--now")
    u.set_defaults(fn=cmd_run)
    g = sub.add_parser("gate"); g.add_argument("receipt"); g.add_argument("--body", required=True); g.add_argument("--now")
    g.set_defaults(fn=cmd_gate)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_preflight_cli.py -v`
Expected: 4 passed. If `test_run_passes_once_exit_is_mirrored...` fails on a walker finding from the v5 body (a real column shape the miniature does not model), extend the miniature's `columns.items.properties` with the missing key rather than loosening the walker, and re-run.

- [ ] **Step 5: Commit**

Run: `python -m pytest -q` — expected `959 passed`.

```bash
git add scripts/preflight.py tests/test_preflight_cli.py tests/fixtures/preflight/schema_walker_min.json
git commit -m "preflight: CLI recipe/run/gate, end-to-end in tmp_path (task 6)"
```

---

### Task 7: The gate in the authoring procedure

**Files:**
- Modify: `docs/20-the-authoring-procedure.md` (§5, before the "Compile dry-run" bullet at ~line 109)
- Modify: `docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md` (status line)

- [ ] **Step 1: Read §5 of docs/20** (`sed -n 100,132p docs/20-the-authoring-procedure.md`) and insert this paragraph immediately after the sentence ending "read them before running one." and before the "Compile dry-run" bullet:

```markdown
**Precondition for every compile (2026-09-04):** a same-session schema-drift preflight
receipt, PASS, bound to the exact body's sha256 and not expired — produced by the
read-only procedure `python scripts/preflight.py recipe <body> --reference <id>`
(design: `docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md`). The
authorization checkbox quotes the printed `PREFLIGHT PASS · …` line verbatim. The
receipt is a precondition of asking for authorization, not the authorization itself;
its disclaimer stands: it covers the published schema and the reference record only;
the runtime validator is not observed. A refusal after a PASS voids the receipt
(`voided` with the refusal verbatim and a `gate_missed` class) and the post-refusal
read-back becomes the next baseline.
```

- [ ] **Step 2: Update the spec's status line** to:
`**Status:** implemented 2026-09-xx (tasks 1–7 of docs/superpowers/plans/2026-09-04-schema-drift-preflight.md); first live run pending the user's ask (task 8).`

- [ ] **Step 3: Commit**

```bash
git add docs/20-the-authoring-procedure.md docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md
git commit -m "docs: the preflight receipt is a precondition of compile authorization (task 7)"
```

---

### Task 8: First live run (read-only; needs the user's ask naming the read)

**Files:**
- Create: `data/contract/compile_strategy_plan/schema_<stamp>.json` (verbatim capture)
- Create: `data/contract/get_strategy/b9438519-8223-4ef1-a3c3-6f4592bb823d_<stamp>.json` (verbatim capture)
- Create: `data/audit/compile_preflight_<date>.json` (receipt)
- Modify: `tests/test_write_surface.py` (one new test, pins vs the NAMED capture)

**Do not start this task without the user's explicit ask:** *"run the preflight for `<body>` against `b9438519-8223-4ef1-a3c3-6f4592bb823d`"*. Read-only calls need no write-path authorization, but the design says the ask names the read.

- [ ] **Step 1:** `python scripts/compile_dry_run.py > "<scratchpad>/body.json"` — the no-argument mode prints the current `wire()` CREATE body (the same builder the 08-30 compile used) as compact JSON. Use the session scratchpad, never `/tmp`.
- [ ] **Step 2:** `python scripts/preflight.py recipe "<scratchpad>/body.json" --reference b9438519-8223-4ef1-a3c3-6f4592bb823d` and follow its steps 1–2 in the session, saving both captures verbatim. Record in each capture's `how` whether one Write sufficed or chunks were needed — this is the unverified assumption the spec names.
- [ ] **Step 3:** `python scripts/preflight.py run "<scratchpad>/body.json" --schema <capture> --readback <capture>`. Expected: fingerprints pass (84 / 25 / 13; id, 84 signalRules), and the diff is a PASS with `CHANGELOG` absent (no previous capture yet) and `INFO` lines for the 16 execution defaults and `decisionInvalidationExitEnabled`. If it FAILs, that is a real drift instance #6: record it under `data/audit/` per the drift-instance convention and stop.
- [ ] **Step 4:** Add to `tests/test_write_surface.py`, pinned to the NAMED file, never a glob:

```python
SCHEMA_CAPTURE_2026_09_XX = ROOT / "data/contract/compile_strategy_plan/schema_<stamp>.json"


def test_api_pins_agree_with_the_named_schema_capture():
    """A green suite proves pin-vs-capture agreement for THIS dated capture, not platform
    agreement. The preflight's gate never reads a committed capture."""
    from omega import preflight as P
    definition = json.loads(SCHEMA_CAPTURE_2026_09_XX.read_text(encoding="utf-8"))["response"]
    arms, root = P.resolve_arms(definition)
    create = P.deref(arms["CREATE"], root)
    assert set(create["properties"]) == API_ACCEPTS
    assert set(create["required"]) == API_REQUIRES
```

- [ ] **Step 5:** Run `python -m pytest -q` (expected `960 passed`), commit the two captures, the receipt and the test:

```bash
git add data/contract/compile_strategy_plan data/contract/get_strategy data/audit/compile_preflight_*.json tests/test_write_surface.py
git commit -m "preflight: first live run - verbatim captures, receipt, pins tied to the named capture (task 8)"
```

---

## Self-review (done while writing)

- **Spec coverage:** components 1–3 → Tasks 6/1–5/6; receipt and gate line → Task 5; session procedure → `recipe` (Task 6) and Task 8; reference-by-role → recipe's `--reference` plus the spec text; staleness defence → expiry in Task 5, `gate` never reading committed captures (Task 6), the named-fixture pin test (Task 8); testing section → Tasks 1–6 (walker miniature labelled; replays of #4/#5 from real records in Task 3; fingerprints in Task 4; gate in Task 5); would-have-caught → replay tests; docs gate → Task 7. Not covered by code on purpose: `gate_missed` ledger entries are written by hand into the receipt's `voided` field after a refusal (spec step 8); no automation is specified for it.
- **Placeholders:** the only "<…>" tokens are file-name stamps chosen at capture time and the scratchpad path; none are TODOs.
- **Type consistency:** `resolve_arms` returns `(arms, root)` everywhere; `diff_schema(body, arm, root)`, `diff_record(body, record, arm, root)`, `mirror_findings(body, record)`, `fingerprint_schema(arm, root, *, signal_ids, template_keys, timeframes)`, `fingerprint_readback(record, strategy_id)`, `build_receipt(...)`, `gate_check(receipt, body, now)` are used with the same signatures in Tasks 5–6 as defined in 1–5. `P._parse_iso` is private but used by the CLI deliberately (same package family as `scripts/compile_dry_run.py` reaching into omega).
- **Test counts** assume no other test file changes; adjust the "expected N passed" lines to the live baseline at execution time rather than trusting these numbers.
