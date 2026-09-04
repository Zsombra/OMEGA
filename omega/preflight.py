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


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


_NUM = (int, float)

_KNOWN_TYPES = ("object", "array", "string", "boolean", "null", "number", "integer")

# Keywords the walker models directly, plus keywords that are annotative/harmless
# (description, title, default, examples, $comment) and never worth a finding.
# Anything outside this set is reported as UNSUPPORTED per the Global Constraint.
_MODELED_KEYWORDS = frozenset({
    "type", "properties", "required", "additionalProperties", "enum", "const",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "minLength", "maxLength", "minItems", "maxItems", "items", "anyOf", "$ref",
    "pattern", "description", "title", "default", "examples", "$comment",
})


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
    unknown = set(schema) - _MODELED_KEYWORDS
    if unknown:
        out.append(Finding("UNSUPPORTED", path,
                            f"schema keyword(s) not modelled by the walker: {sorted(unknown)}", "WARN"))
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
    if isinstance(t, list):
        out.append(Finding("UNSUPPORTED", path, "type as a list", "WARN"))
    elif isinstance(t, str) and t not in _KNOWN_TYPES:
        out.append(Finding("UNSUPPORTED", path, f"unknown type name {t!r}", "WARN"))
    elif isinstance(t, str) and not _type_ok(t, value):
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
            items_schema = schema["items"]
            if isinstance(items_schema, list):
                out.append(Finding("UNSUPPORTED", path,
                                   "tuple-form items (a list) not modelled by the walker", "WARN"))
            else:
                for i, v in enumerate(value):
                    _walk(v, items_schema, root, f"{path}[{i}]", out)
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

# A record key/element field whose value is null on every record element carries nothing to
# mirror - the platform's not-set default (e.g. the optional section-level `timeframe`,
# omega/validate.py section_timeframe). INFO, not FAIL; no drift instance to date (#3/#4/#5)
# was null-valued.
_NULL_INFO_DETAIL = "platform null default on the record; nothing to mirror"


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
    elements sharing a `kind` (custom sections vs custom sections). A record key whose
    value is None on every record element is INFO (nothing to mirror), not FAIL."""
    if kinds:
        body_elems = [e for e in body_elems if isinstance(e, dict) and e.get("kind") in kinds]
        rec_elems = [e for e in rec_elems if isinstance(e, dict) and e.get("kind") in kinds]
    exemplar = _intersection_keys(rec_elems)
    body_dicts = [e for e in body_elems if isinstance(e, dict)]
    rec_dicts = [e for e in rec_elems if isinstance(e, dict)]
    if not exemplar or not body_dicts:
        return
    for key in sorted(exemplar):
        delta_key = f"{path}[].{key}"
        if delta_key in KNOWN_DELTAS:
            continue
        missing = sum(1 for e in body_dicts if key not in e)
        if missing:
            agg_path = f"{path}[*].{key}"
            if rec_dicts and all(e.get(key) is None for e in rec_dicts):
                out.append(Finding("INFO", agg_path, _NULL_INFO_DETAIL, "INFO"))
            else:
                out.append(Finding("MISSING_VS_RECORD", agg_path,
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
        if isinstance(rv, dict) and bk in NESTED_REQUEST_OBJECTS:
            out.append(Finding("MISSING_VS_RECORD", bk, "the record carries this object; the body omits it "
                               "entirely (a human decides whether to mirror it)", "WARN"))
        elif bk in required:
            continue                       # already MISSING_REQUIRED from diff_schema
        elif bk in props:
            out.append(Finding("INFO", bk, "declared optional; the record carries a value the body omits "
                               "(platform default or deliberate omission)", "INFO"))
        else:
            out.append(Finding("INFO", bk, "server-derived key on the record, not part of the request", "INFO"))
    for name in NESTED_REQUEST_OBJECTS:
        if isinstance(body.get(name), dict) and isinstance(rec.get(name), dict):
            for key in sorted(set(rec[name]) - set(body[name])):
                if rec[name][key] is None:
                    out.append(Finding("INFO", _join(name, key), _NULL_INFO_DETAIL, "INFO"))
                else:
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
