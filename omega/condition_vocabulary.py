"""The condition vocabulary at contract 108, DERIVED from the saved write schema - never typed.

Source: the file the manifest's `writeSurface.schema` names (since 2026-10-11
`data/contract/stage_strategy_draft/schema_20261010T215326Z.json`, contract 108.0.0, build 1076c4e7): the CONDITIONS
axis of `stage_strategy_draft`'s input schema, the same grammar under `preview_strategy_report`'s `source.conditions`,
the per-header fields `preview_strategy_report` serves for each condition column (`conditionOperators`,
`conditionHold`), and the REPORT column's `metric` / `transformId` / `chainedTransformId` enums.

`derive(doc)` walks that document and returns the inventory written to `data/derived/condition_vocabulary_108.json`:
every clause arm with its operators, operand fields and constraints, the hold, the column, the conditionRef and group
arms, the condition object, and the column enums - each entry with its JSON Pointer (RFC 6901) into the source file's
document. tests/test_condition_vocabulary_108.py re-derives it from the schema file and compares, so a later schema
swap shows up as a diff of this file rather than as a silent drift.

`gaps()` compares the inventory with what omega models (the builders' and validator's operators, the metric corpus,
the authorable transforms, the Column model's fields). It reads the schema, never the other way round: a rule that
lives only in a description (the README changelog, the vendor skill's prose) is not in this file.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .contract import CONTRACT_DIR, DERIVED_DIR, ROOT
from .preflight import union_key

OUT = DERIVED_DIR / "condition_vocabulary_108.json"
STAGE = "stage_strategy_draft"
PREVIEW = "preview_strategy_report"
# The keys every clause arm shares; what is left on an arm is its operand.
CLAUSE_FRAME = ("kind", "column", "op", "hold")
_POINTER_KEYS = ("pointer", "opPointer", "holdPointer", "itemsRef", "definitionPointer")


# --- JSON Pointer --------------------------------------------------------------------------------
def _esc(part: object) -> str:
    return str(part).replace("~", "~0").replace("/", "~1")


def pointer(parts: list) -> str:
    """RFC 6901: "" is the whole document, "/a/0/b" a node in it."""
    return "".join("/" + _esc(p) for p in parts)


def resolve(doc: Any, ptr: str) -> Any:
    """The node at JSON Pointer `ptr` in `doc`."""
    cur = doc
    if ptr == "":
        return cur
    for raw in ptr.split("/")[1:]:
        part = raw.replace("~1", "/").replace("~0", "~")
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def _ref_parts(base: list, ref: str) -> list:
    """A local `$ref` ('#/a/b') is relative to the tool's input (or output) schema, `base`."""
    if not ref.startswith("#/"):
        raise ValueError(f"non-local $ref {ref!r}")
    return base + [int(p) if p.isdigit() else p.replace("~1", "/").replace("~0", "~")
                   for p in ref[2:].split("/")]


def _deref(doc: dict, base: list, parts: list) -> tuple[list, Any]:
    """(parts, node) after following every `$ref` from `parts`."""
    node = resolve(doc, pointer(parts))
    for _ in range(32):
        if not (isinstance(node, dict) and "$ref" in node):
            return parts, node
        parts = _ref_parts(base, node["$ref"])
        node = resolve(doc, pointer(parts))
    raise ValueError(f"$ref chain too deep at {pointer(parts)}")


def _inline(doc: dict, base: list, parts: list) -> Any:
    """A leaf schema with its `$ref`s inlined (operands, column, hold and the condition fields do not recurse)."""
    parts, node = _deref(doc, base, parts)
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for k, v in node.items():
        if isinstance(v, dict):
            out[k] = _inline(doc, base, parts + [k])
        elif isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            out[k] = [_inline(doc, base, parts + [k, i]) for i in range(len(v))]
        else:
            out[k] = v
    return out


def _ops(node: dict) -> list[str]:
    return list(node["enum"]) if "enum" in node else [node["const"]]


def _flatten(doc: dict, base: list, parts: list) -> list[tuple[list, dict]]:
    """Every non-union arm under a (possibly nested) anyOf / oneOf, in schema order, as (pointer parts, node)."""
    parts, node = _deref(doc, base, parts)
    key = union_key(node)
    if key:
        out: list[tuple[list, dict]] = []
        for i in range(len(node[key])):
            out.extend(_flatten(doc, base, parts + [key, i]))
        return out
    return [(parts, node)]


# --- the grammar ---------------------------------------------------------------------------------
def _grammar(doc: dict, tool: str, items: list) -> dict:
    """The condition grammar under one tool's `conditions.items` (pointer parts `items`)."""
    base = [tool, "inputSchema"]
    _, cond = _deref(doc, base, items)
    clause_arms: list[dict] = []
    refs: list[dict] = []
    groups: list[dict] = []
    def_parts = items + ["properties", "definition"]
    column_parts = hold_parts = None
    for parts, arm in _flatten(doc, base, def_parts):
        props = arm["properties"]
        kind = props["kind"]["const"]
        if kind == "clause":
            op_parts, op_node = _deref(doc, base, parts + ["properties", "op"])
            if column_parts is None:
                column_parts = _deref(doc, base, parts + ["properties", "column"])[0]
                hold_parts = _deref(doc, base, parts + ["properties", "hold"])[0]
            clause_arms.append({
                "pointer": pointer(parts),
                "ops": _ops(op_node),
                "opPointer": pointer(op_parts),
                "operands": {k: {"pointer": pointer(parts + ["properties", k]),
                                 "schema": _inline(doc, base, parts + ["properties", k])}
                             for k in props if k not in CLAUSE_FRAME},
                "required": list(arm["required"]),
                "additionalProperties": arm.get("additionalProperties", True),
            })
        elif kind == "conditionRef":
            refs.append({"pointer": pointer(parts), "required": list(arm["required"]),
                         "additionalProperties": arm.get("additionalProperties", True),
                         "fields": {k: _inline(doc, base, parts + ["properties", k]) for k in props}})
        elif kind == "group":
            members = props["members"]
            groups.append({
                "pointer": pointer(parts),
                "ops": _ops(props["op"]),
                "opPointer": pointer(parts + ["properties", "op"]),
                "required": list(arm["required"]),
                "additionalProperties": arm.get("additionalProperties", True),
                # recursive: the members are definitions again, so the item is named by its target, not inlined
                "members": {"pointer": pointer(parts + ["properties", "members"]),
                            "minItems": members.get("minItems"), "maxItems": members.get("maxItems"),
                            "itemsRef": pointer(_ref_parts(base, members["items"]["$ref"]))},
                "n": {"pointer": pointer(parts + ["properties", "n"]),
                      "schema": _inline(doc, base, parts + ["properties", "n"])},
                "holdPointer": pointer(_deref(doc, base, parts + ["properties", "hold"])[0]),
            })
        else:
            raise ValueError(f"unknown definition kind {kind!r} at {pointer(parts)}")
    if len(refs) != 1 or len(groups) != 1 or column_parts is None:
        raise ValueError(f"expected clause arms, one conditionRef and one group arm; got "
                         f"{len(clause_arms)}, {len(refs)}, {len(groups)}")
    operators: dict[str, dict] = {}
    for i, arm in enumerate(clause_arms):
        for op in arm["ops"]:
            if op in operators:
                raise ValueError(f"operator {op!r} is declared by two clause arms")
            operators[op] = {"arm": i, "operands": sorted(arm["operands"]),
                             "sharesArmWith": [o for o in arm["ops"] if o != op]}
    return {
        "condition": {
            "pointer": pointer(items),
            "required": list(cond["required"]),
            "additionalProperties": cond.get("additionalProperties", True),
            "fields": {k: _inline(doc, base, items + ["properties", k])
                       for k in cond["properties"] if k != "definition"},
        },
        "definitionPointer": pointer(def_parts),
        "clauseArms": clause_arms,
        "operators": operators,
        "column": {"pointer": pointer(column_parts), "schema": _inline(doc, base, column_parts)},
        "hold": {"pointer": pointer(hold_parts), "schema": _inline(doc, base, hold_parts)},
        "conditionRef": refs[0],
        "group": groups[0],
    }


def strip_pointers(node: Any) -> Any:
    """The grammar with every pointer removed: what two tools' grammars must agree on."""
    if isinstance(node, dict):
        return {k: strip_pointers(v) for k, v in node.items() if k not in _POINTER_KEYS}
    if isinstance(node, list):
        return [strip_pointers(x) for x in node]
    return node


def _envelope(doc: dict) -> list:
    """The pointer parts of the stage tool's `request` envelope: `["properties", "request"]` in a capture from before
    contract v111, none since (README v111: "the draft tools take their arguments at the top level")."""
    return ["properties", "request"] if "request" in doc[STAGE]["inputSchema"].get("properties", {}) else []


def _custom_section(doc: dict) -> list:
    """Pointer parts of the REPORT axis's one custom-section arm (the arm that carries `columns`)."""
    base = [STAGE, "inputSchema"]
    sections = base + _envelope(doc) + ["properties", "axes", "properties", "REPORT", "properties",
                                        "sections", "items"]
    custom = [p for p, arm in _flatten(doc, base, sections) if "columns" in arm.get("properties", {})]
    if len(custom) != 1:
        raise ValueError(f"expected one custom-section arm on the REPORT axis, got {len(custom)}")
    return custom[0]


def _report_section(doc: dict) -> dict:
    """The custom section the REPORT axis admits: its fields, which are required, and the `columns` array bounds
    (v103 removed the fixed 64; 48.0.0 removed the section `timeframe` override)."""
    parts = _custom_section(doc)
    node = resolve(doc, pointer(parts))
    columns = node["properties"]["columns"]
    return {"pointer": pointer(parts), "fields": sorted(node["properties"]), "required": list(node["required"]),
            "additionalProperties": node.get("additionalProperties", True),
            "columns": {k: columns[k] for k in ("minItems", "maxItems") if k in columns}}


def _column_enums(doc: dict) -> dict:
    base = [STAGE, "inputSchema"]
    column = _custom_section(doc) + ["properties", "columns", "items"]
    _, node = _deref(doc, base, column)
    out: dict[str, Any] = {"pointer": pointer(column), "fields": sorted(node["properties"])}
    for name in ("metric", "transformId", "chainedTransformId"):
        p, n = _deref(doc, base, column + ["properties", name])
        out[name] = {"pointer": pointer(p), "count": len(n["enum"]), "enum": list(n["enum"])}
    # the integer fields' bounds: window/offset keep only their floors since v103; buffer is 0-500 (v100)
    out["bounds"] = {name: {k: spec[k] for k in ("minimum", "maximum") if k in spec}
                     for name, spec in sorted(node["properties"].items()) if spec.get("type") == "integer"}
    return out


def _served_per_header(doc: dict) -> dict:
    """What preview_strategy_report serves for each condition-column output: the operators that header admits on
    that strategy (`conditionOperators`) and its hold domain (`conditionHold`). Both are per header, per strategy -
    read live, never offline."""
    base = [PREVIEW, "outputSchema"]
    authoring = base + ["properties", "authoring"]
    arms = [p for p, arm in _flatten(doc, base, authoring) if "conditionColumns" in arm.get("properties", {})]
    if len(arms) != 1:
        raise ValueError(f"expected one authoring arm with conditionColumns, got {len(arms)}")
    outputs = arms[0] + ["properties", "conditionColumns", "items", "properties", "outputs", "items"]
    _, node = _deref(doc, base, outputs)
    ops_parts = outputs + ["properties", "conditionOperators", "items"]
    hold_parts = outputs + ["properties", "conditionHold"]
    _, hold = _deref(doc, base, hold_parts)
    refusal = [i for i, b in enumerate(hold["properties"]["refusal"]["anyOf"]) if "enum" in b]
    refusal_parts = hold_parts + ["properties", "refusal", "anyOf", refusal[0]]
    return {
        "pointer": pointer(outputs),
        "required": list(node["required"]),
        "conditionOperators": {"pointer": pointer(ops_parts),
                               "enum": list(resolve(doc, pointer(ops_parts))["enum"])},
        "conditionHold": {"pointer": pointer(hold_parts), "required": list(hold["required"]),
                          "refusal": {"pointer": pointer(refusal_parts),
                                      "enum": list(resolve(doc, pointer(refusal_parts))["enum"])}},
    }


def derive(doc: dict, *, source: str, source_sha256: str) -> dict:
    """The inventory of one saved write-schema document (the multi-tool capture keyed by tool)."""
    stage_items = [STAGE, "inputSchema", *_envelope(doc), "properties", "axes", "properties", "CONDITIONS",
                   "properties", "conditions", "items"]
    stage = _grammar(doc, STAGE, stage_items)
    conditions_array = resolve(doc, pointer(stage_items[:-1]))
    preview_source = [PREVIEW, "inputSchema", "properties", "source"]
    fields_arm = [p for p, arm in _flatten(doc, [PREVIEW, "inputSchema"], preview_source)
                  if "conditions" in arm.get("properties", {})]
    if len(fields_arm) != 1:
        raise ValueError(f"expected one preview source arm with conditions, got {len(fields_arm)}")
    preview_items = fields_arm[0] + ["properties", "conditions", "items"]
    preview = _grammar(doc, PREVIEW, preview_items)
    return {
        "_what": ("The condition vocabulary the saved write schema admits, derived by "
                  "omega.condition_vocabulary.derive; every entry carries its JSON Pointer (RFC 6901) into the "
                  "source document. Regenerate with `python scripts/derive_condition_vocabulary.py`; "
                  "tests/test_condition_vocabulary_108.py re-derives it and fails on any difference. Only what the "
                  "schema states is here: a rule that lives in a description (README changelog, vendor skill) is "
                  "not, and neither is which header admits which operator - that is served per header, per "
                  "strategy (servedPerHeader)."),
        "source": {"schema": source, "sha256": source_sha256, "contractVersion": doc["contractVersion"],
                   "buildSha": doc["buildSha"], "observedAt": doc["observedAt"]},
        "clauseOperators": [op for arm in stage["clauseArms"] for op in arm["ops"]],
        "groupOperators": stage["group"]["ops"],
        "conditionsArray": {"pointer": pointer(stage_items[:-1]),
                            "bounds": {k: conditions_array[k] for k in ("minItems", "maxItems")
                                       if k in conditions_array}},
        "grammar": stage,
        "previewConditions": {"pointer": pointer(preview_items),
                              "sameGrammarAsStage": strip_pointers(preview) == strip_pointers(stage)},
        "servedPerHeader": _served_per_header(doc),
        "reportSection": _report_section(doc),
        "reportColumn": _column_enums(doc),
    }


def sha256(path: Path) -> str:
    """The schema file's sha256 with line endings normalised to LF. git stores these JSON captures with LF and a Windows
    checkout (core.autocrlf) writes CRLF, so a byte hash named a different file per checkout (2026-10-14: the inventory
    derived in one worktree failed its own hash check on the main checkout)."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def schema_path() -> Path:
    """The write schema the manifest names (`writeSurface.schema`)."""
    manifest = json.loads((CONTRACT_DIR / "_manifest.json").read_text(encoding="utf-8"))
    return ROOT / manifest["writeSurface"]["schema"]


def derive_from_disk() -> dict:
    path = schema_path()
    doc = json.loads(path.read_text(encoding="utf-8"))
    return derive(doc, source=path.relative_to(ROOT).as_posix(), source_sha256=sha256(path))


def render(vocab: dict) -> str:
    return json.dumps(vocab, indent=1, ensure_ascii=False) + "\n"


@lru_cache(maxsize=1)
def vocabulary() -> dict:
    """The stored inventory (data/derived/condition_vocabulary_108.json)."""
    return json.loads(OUT.read_text(encoding="utf-8"))


def arm_for(op: str) -> dict | None:
    """The clause arm the schema declares for `op`, or None when the schema has no such operator."""
    grammar = vocabulary()["grammar"]
    entry = grammar["operators"].get(op)
    return None if entry is None else grammar["clauseArms"][entry["arm"]]


# --- what omega models, against the schema --------------------------------------------------------
def gaps() -> dict:
    """Set differences between the schema's vocabulary and omega's model of it, per kind: `schemaOnly` is what the
    schema admits and omega does not model, `omegaOnly` what omega models and the schema does not admit."""
    from .conditions import GROUP_OPS, MODELLED_CLAUSE_OPS
    from .contract import load
    from .types import Column, CustomSection
    v = vocabulary()
    c = load()
    col = v["reportColumn"]

    def diff(schema, omega) -> dict:
        return {"schemaOnly": sorted(set(schema) - set(omega)), "omegaOnly": sorted(set(omega) - set(schema))}

    return {
        "clauseOperators": diff(v["clauseOperators"], MODELLED_CLAUSE_OPS),
        "groupOperators": diff(v["groupOperators"], GROUP_OPS),
        # the measured corpus plus the names known only (data/contract/metrics/_unmeasured_108.json) ...
        "metrics": diff(col["metric"]["enum"], set(c.metrics) | set(c.unmeasured_metrics)),
        # ... and of those, the ones whose transform admissibility is unmeasured
        "metricsUnmeasured": sorted(c.unmeasured_metrics),
        "transforms": diff(col["transformId"]["enum"], c.transforms),
        "columnFields": diff(col["fields"], Column.model_fields),
        "sectionFields": diff(v["reportSection"]["fields"], CustomSection.model_fields),
    }
