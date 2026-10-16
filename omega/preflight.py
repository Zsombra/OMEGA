"""Schema-drift preflight (design: docs/superpowers/specs/2026-09-04-schema-drift-preflight-design.md).

omega CANNOT CALL MCP TOOLS (omega/probe.py:3). The session saves a verbatim capture of
the stage_strategy_draft tool definition (a ToolSearch definition load, not a call) and
hands it here as a dict. This module walks a stage request - each axis against its own
schema - and returns findings; scripts/preflight.py does the file I/O and prints the
receipt. Nothing here decides a value for a missing field: a FAIL names the field and a
human mirrors it from a record, exactly as was done for drift instances #3, #4 and #5.

Contract 85.0.0 removed compile_strategy_plan: the body is now the `axes` of a stage
(plan 2026-10-06, Work step 4). resolve_arms, diff_record and fingerprint_readback stay for
the RETIRED compile captures and pre-v84 read-backs (data/contract/_manifest.json
`retired`); the read-back mirror is retired until a v91 read-back is captured, because a
pre-v84 record carries `closes` and `exit`, which no v91 body may.

Contract 108.0.0 (2026-10-11, plan docs/plans/2026-10-11-omega-v108-conditions-only.md): the stage takes EIGHT
axes - SIGNAL_RULES and SETUP_GATES are refused as unrecognized keys, minAtrPct is required on TRADE_LEVEL_POLICY.
The walk is unchanged (it reads whatever axes the capture declares); fingerprint_axes checks the eight and no longer
checks a signalId enum, because there is none: with signal rules gone there is no signal parameter or signal id
to check a body against. AXES_91 stays as history.

The walker covers only the JSON-Schema subset the definitions use: properties /
required / additionalProperties:false / enum / const / type / minimum / maximum /
exclusiveMinimum / exclusiveMaximum / multipleOf / minLength / maxLength / minItems /
maxItems / items / anyOf (discriminated by a const on operation|kind|mode, else by type) /
local $ref.
Anything else is reported as UNSUPPORTED, never silently skipped.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

CLASSES = ("UNDECLARED", "MISSING_REQUIRED", "MISSING_VS_RECORD", "ENUM", "BOUNDS",
           "UNSUPPORTED", "MIRROR", "CHANGELOG", "TRANSCRIPTION_SUSPECT", "INFO")
VERDICTS = ("FAIL", "WARN", "INFO")
DISCLAIMER = ("covers the published schema only (the read-back mirror is retired until a read-back at "
              "the write surface's contract, 108.0.0, is captured); the builder's diagnostics - among them "
              "the NO_ENTRY_CONDITION warning - and the runtime validator are "
              "not observed by this check")


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


STAGE_TOOL = "stage_strategy_draft"


def _input_root(definition: dict) -> dict:
    """The input schema every local $ref of a tool definition is relative to. Three
    capture shapes are read: a ToolSearch definition ({..., "parameters": schema}), a
    battlegrid-manager surface entry ({..., "inputSchema": schema}), and the saved
    multi-tool file (data/contract/stage_strategy_draft/schema_*.json, keyed by tool)."""
    if STAGE_TOOL in definition and isinstance(definition[STAGE_TOOL], dict):
        definition = definition[STAGE_TOOL]
    for key in ("parameters", "inputSchema"):
        if isinstance(definition.get(key), dict):
            return definition[key]
    raise UnsupportedSchema("definition carries neither `parameters` nor `inputSchema`")


def resolve_request(definition: dict) -> tuple[dict, dict]:
    """The `request` object schema of a stage_strategy_draft definition, plus its root. Since contract v111 (served
    as 110.13.0, 2026-10-16; README "Contract history - v111: the draft tools take their arguments at the top level")
    the draft tools carry no `request` envelope - the input root IS the request object; a capture from before keeps
    its envelope and is read through it."""
    root = _input_root(definition)
    props = root.get("properties", {})
    if "request" in props:
        return deref(props["request"], root), root
    return root, root


def resolve_axes(definition: dict) -> tuple[dict[str, dict], dict]:
    """The axis schemas of a stage_strategy_draft definition, keyed by axis name (ten at
    91.0.0, eight at 108.0.0), plus the root every local $ref is relative to. This replaces resolve_arms:
    v85 split the flat CREATE/UPDATE body into axes, each staged WHOLE."""
    request, root = resolve_request(definition)
    axes = deref(request.get("properties", {}).get("axes", {}), root)
    props = axes.get("properties")
    if not isinstance(props, dict) or not props:
        raise UnsupportedSchema("stage request without an axes object")
    return {name: deref(node, root) for name, node in props.items()}, root


def diff_axes(axes: dict, axis_schemas: dict[str, dict], root: dict) -> list[Finding]:
    """Walk each staged axis against its own schema (paths `axes.<AXIS>...`). An axis the
    definition does not declare is UNDECLARED (the axes object is additionalProperties:false
    at 91.0.0 and 108.0.0 - a SIGNAL_RULES or SETUP_GATES axis is UNDECLARED against a 108 capture); an axis the
    body omits is not a finding - "axes you omit keep their values"."""
    out: list[Finding] = []
    for name, value in axes.items():
        path = f"axes.{name}"
        if name not in axis_schemas:
            out.append(Finding("UNDECLARED", path, "not an axis of the published stage schema "
                               f"({sorted(axis_schemas)})", "FAIL"))
            continue
        _walk(value, axis_schemas[name], root, path, out)
    return out


def resolve_arms(definition: dict) -> tuple[dict[str, dict], dict]:
    """The operation arms of a RETIRED compile_strategy_plan definition, keyed by the
    `operation` const, plus the root every local $ref is relative to. Read only for the
    compile captures kept as history; a v91 body is walked with resolve_axes."""
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
    "multipleOf",
    "pattern", "format", "description", "title", "default", "examples", "$comment",
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


def _fits(value: dict, b: dict, root: dict, relaxed: bool = False) -> bool:
    """True when `value` satisfies branch `b` at its own level: a matching discriminator
    const, every required key, no undeclared key under additionalProperties:false, and
    every top-level enum/const property it carries. A branch that is itself an anyOf fits
    when one of its branches does.

    Needed at 91.0.0: the CONDITIONS clause union is FOUR arms sharing kind "clause"
    (told apart by `op`), and the ENTRY union is told apart by the `trigger` enum - the
    first-const / first-required rules below would walk an `is` clause against the
    numeric arm, or a level trigger against the ON_CANDLE_CLOSE arm.

    `relaxed` drops only the required-key test and keeps the undeclared-key and const/enum
    ones:
    the branch a value MEANS (an `is` clause that forgot its hold is still an `is`
    clause), so the walk reports the missing key there rather than a pile of noise
    against the first arm sharing its kind."""
    if "anyOf" in b and "properties" not in b:
        return _pick_branch(value, b["anyOf"], root, strict=True, relaxed=relaxed) is not None
    if b.get("type", "object") != "object":
        return False
    props = b.get("properties", {})
    if not relaxed and not all(k in value for k in b.get("required", [])):
        return False
    if b.get("additionalProperties") is False and any(k not in props for k in value):
        return False
    for k, v in value.items():
        if k in props:
            s = deref(props[k], root)
            if ("const" in s and v != s["const"]) or ("enum" in s and v not in s["enum"]):
                return False
    return True


def _pick_branch(value: object, branches: list, root: dict, strict: bool = False,
                 relaxed: bool = False) -> dict | None:
    cands = [deref(b, root) for b in branches]
    if isinstance(value, dict):
        for b in cands:                                   # the first branch the value fits
            if _fits(value, b, root, relaxed):
                return b
        if strict:
            return None
        for b in cands:                                   # the branch it means (consts/enums)
            if _fits(value, b, root, relaxed=True):
                return b
        # No exact fit: fall back to the discriminator, then the required keys, so the walk
        # still descends and names the specific finding rather than one opaque mismatch.
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
        t = b.get("type")
        if isinstance(t, str) and t in _KNOWN_TYPES and _type_ok(t, value) and "enum" not in b and "const" not in b:
            return b
    return None


def _check_unknown_keywords(schema: dict, path: str, out: list[Finding]) -> None:
    """Keywords the walker does not model, per the Global Constraint (never a silent
    skip). Called once on the anyOf-holder schema and again on whichever branch
    `_pick_branch` selects - a keyword scoped to one arm of an anyOf is otherwise never
    examined."""
    unknown = set(schema) - _MODELED_KEYWORDS
    if unknown:
        out.append(Finding("UNSUPPORTED", path,
                            f"schema keyword(s) not modelled by the walker: {sorted(unknown)}", "WARN"))


def _walk(value: object, schema: dict, root: dict, path: str, out: list[Finding]) -> None:
    schema = deref(schema, root)
    _check_unknown_keywords(schema, path, out)
    # A loop, not an `if`: the 91.0.0 condition definition nests anyOf three deep (group |
    # (ref | (four clause arms))). Taking one level and walking the inner anyOf as a plain
    # object left every clause unvalidated with no finding at all - a silent skip.
    while "anyOf" in schema:
        branch = _pick_branch(value, schema["anyOf"], root)
        if branch is None:
            # RULING: an unmatched anyOf branch leaves the subtree unvalidated - FAIL, not
            # WARN, unlike the WARN-and-keep-walking UNSUPPORTED cases below.
            out.append(Finding("UNSUPPORTED", path, "no anyOf branch matches the value", "FAIL"))
            return
        schema = deref(branch, root)
        _check_unknown_keywords(schema, path, out)
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
        if "multipleOf" in schema:
            # Contract 61.0.1 (capture schema_20260918T083359Z.json) declares multipleOf on
            # 18 numeric fields - entry.levelOffsetAtrMultiple 0.1, conditions[].closes 1,
            # rules[].allocation 1, minAggregateScore 0.05, minRequiredCount 1 and the
            # execution knobs. Unmodelled, it produced ~93 UNSUPPORTED warnings per preset
            # body on 2026-09-18. The remainder is taken on the QUOTIENT, not with `%`:
            # 0.3 % 0.1 == 0.0999... in binary floating point while 0.3 / 0.1 rounds to 3
            # within 1.5e-16, so a tolerance on the quotient is what makes a legal value pass.
            m = schema["multipleOf"]
            if not _is_num(m) or m <= 0:
                # JSON Schema requires a positive number; anything else is a shape the
                # walker does not model, and dividing by it would raise inside the check.
                out.append(Finding("UNSUPPORTED", path,
                                   f"multipleOf {m!r} is not a positive number", "WARN"))
            else:
                q = v / m
                if abs(round(q) - q) > 1e-9:
                    out.append(Finding("BOUNDS", path, f"{v} is not a multiple of {m}", "FAIL"))
    elif isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            out.append(Finding("BOUNDS", path, f"length {len(value)} < minLength {schema['minLength']}", "FAIL"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            out.append(Finding("BOUNDS", path, f"length {len(value)} > maxLength {schema['maxLength']}", "FAIL"))
        if "pattern" in schema:
            out.append(Finding("INFO", path, f"pattern-unchecked: {schema['pattern']!r} (no regex engine "
                                             "for \\p classes; validated by the platform, not here)", "INFO"))
        if "format" in schema:
            out.append(Finding("INFO", path, f"format-unchecked: {schema['format']!r} (declared, not "
                                             "modelled; validated by the platform, not here)", "INFO"))


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
    # measured for CUSTOM sections only (custom:<uuid>, minted on CREATE, never sent -
    # measured 2026-08-28). The key is kind-aware ("[custom]", not the bare "[]" array
    # marker) because _missing_in_elements compares platform sections under their own
    # "[platform]" label - a bare "sections[].sectionKey" key would have matched both
    # kinds' delta lookup and silently suppressed a real platform-side sectionKey drift.
    "sections[custom].sectionKey": "server-minted on CREATE (custom:<uuid>), never sent - measured 2026-08-28",
}
# Request-shaped nested objects: a record key the body lacks here is a FAIL whether or not
# the schema declares it - drift #3 and #4 were exactly undeclared-but-present-in-the-record.
NESTED_REQUEST_OBJECTS = ("entry",)
NESTED_REQUEST_ARRAYS = ("conditions", "sections", "rules")

# A record key/element field whose value is null on every record element carries nothing to
# mirror - the platform's not-set default (e.g. the section-level `timeframe` a pre-48.0.0 record
# carries as null; the override was removed at 48.0.0). INFO, not FAIL; no drift instance to date (#3/#4/#5)
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
                         kinds: tuple[str, ...] | None = None, label: str | None = None) -> None:
    """One finding per record key absent from body elements, aggregated as
    '<path>[*].<key>' with a 'missing in k/n' count. `kinds` restricts the comparison to
    elements sharing a `kind` (custom sections vs platform sections). `label` disambiguates
    the KNOWN_DELTAS lookup key (and the reported path) for a same-`path` call made under a
    different `kinds` filter - e.g. platform sections vs custom sections - so an allowlist
    entry measured for one kind cannot silently suppress the same-named key drifting on the
    other. A record key whose value is None on every record element is INFO (nothing to
    mirror), not FAIL."""
    if kinds:
        body_elems = [e for e in body_elems if isinstance(e, dict) and e.get("kind") in kinds]
        rec_elems = [e for e in rec_elems if isinstance(e, dict) and e.get("kind") in kinds]
    exemplar = _intersection_keys(rec_elems)
    body_dicts = [e for e in body_elems if isinstance(e, dict)]
    rec_dicts = [e for e in rec_elems if isinstance(e, dict)]
    if not exemplar or not body_dicts:
        return
    prefix = f"{path}[{label}]" if label else path
    for key in sorted(exemplar):
        # the label already names the kind ("sections[custom]"), so the KNOWN_DELTAS
        # lookup key drops the generic "[]" array marker in that case - only the
        # unlabeled form (conditions, rules, ...) still uses "[]" as the marker.
        delta_key = f"{prefix}.{key}" if label else f"{prefix}[].{key}"
        if delta_key in KNOWN_DELTAS:
            continue
        missing = sum(1 for e in body_dicts if key not in e)
        if missing:
            agg_path = f"{prefix}[*].{key}"
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
            _missing_in_elements(body_cols, rec_cols, f"{prefix}[].columns", out)


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
        if isinstance(rv, dict):
            # any dict-valued record key the body lacks entirely is a WARN, not just the
            # ones named in NESTED_REQUEST_OBJECTS - the arm may not even declare it, and
            # "server-derived, not part of the request" is an assertion the code cannot
            # make about an object it has never modelled
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
            _missing_in_elements(b, r, name, out, kinds=("custom",), label="custom")
            _missing_in_elements(b, r, name, out, kinds=("platform",), label="platform")
        else:
            _missing_in_elements(b, r, name, out)
    return out


# Values omega hardcodes as platform mirrors. sections[].notes is excluded: omega sends a
# provenance string on purpose while null acceptance is unmeasured.
# Each name here left the list when the platform stopped carrying the field, never because
# omega stopped caring about it - a field the schema no longer declares has no platform
# value to mirror, and a record written before the removal still carrying it is history:
#   `levelSource`  - removed from `entry` by contract 54.1.0 (captured 2026-09-09).
#   `confirmTf`, `closes`, `bandAtrMultiple` - removed from `entry` by contract 60.0.0
#     (captured 2026-09-18, schema_20260918T083359Z.json: `entry` publishes exactly
#     trigger / levelOffsetAtrMultiple / validForBars, all three required). `confirmTf`
#     had in any case been excluded since the Step 0 amendment of 2026-08-30 as the thesis
#     anchor omega chooses rather than mirrors.
#   `clock` - retired from `conditions[]` by contract 61.0.0 and REFUSED on input
#     (captured 2026-09-18; the seven-key condition shape).
#   `closes` - removed from `conditions[]` by contract 84.0.0; the hold is now `hold` on
#     each clause and group, compared node by node below (`_holds`).
#   `exit` - removed from `conditions[]` by contract 88.0.0 for `exitSide`.
# The levelOffsetAtrMultiple / validForBars pair stays named: a level trigger carries both
# (v85), and the entry mirror compares only keys present on both sides.
MIRROR_ENTRY_FIELDS = ("trigger", "levelOffsetAtrMultiple", "validForBars")
MIRROR_CONDITION_FIELDS = ("exitSide",)


def _holds(defn: object, path: str) -> list[tuple[str, dict]]:
    """(path, hold) for every clause and group in a definition; refs carry none."""
    if not isinstance(defn, dict):
        return []
    out: list[tuple[str, dict]] = []
    if defn.get("kind") in ("clause", "group") and isinstance(defn.get("hold"), dict):
        out.append((f"{path}.hold", defn["hold"]))
    for i, member in enumerate(defn.get("members") or []):
        out.extend(_holds(member, f"{path}.members[{i}]"))
    return out


def mirror_findings(body: dict, record: dict) -> list[Finding]:
    """WARN when a hardcoded mirror differs from what the reference record carries.

    `body` is a stage request or its `axes` (the ENTRY and CONDITIONS axes are read), or a
    flat body with top-level `entry` / `conditions`. RETIRED from the CLI until a v91
    read-back is captured: no record on disk carries `exitSide` or a per-node `hold`, so
    against one of them this reports nothing for the conditions, by construction."""
    rec = record_request_view(record)
    axes = body.get("axes", body)
    out: list[Finding] = []
    be = (axes.get("ENTRY") or {}).get("entry") if "ENTRY" in axes else body.get("entry")
    re_ = rec.get("entry")
    if isinstance(be, dict) and isinstance(re_, dict):
        for k in MIRROR_ENTRY_FIELDS:
            if k in be and k in re_ and be[k] != re_[k]:
                out.append(Finding("MIRROR", _join("entry", k),
                                   f"body {be[k]!r} vs record {re_[k]!r} - the user decides whether to re-mirror", "WARN"))
    bconds = ((axes.get("CONDITIONS") or {}).get("conditions") if "CONDITIONS" in axes
              else body.get("conditions")) or []
    rconds = [c for c in rec.get("conditions", []) if isinstance(c, dict)]
    for k in MIRROR_CONDITION_FIELDS:
        seen = {c[k] if not isinstance(c.get(k), (list, dict)) else None for c in rconds if k in c}
        if not seen:
            continue
        for i, c in enumerate(bconds):
            # compare by value, not set membership: c[k] may be a list/dict and thus
            # unhashable, which `c[k] not in seen` (a set) would raise TypeError on
            if isinstance(c, dict) and k in c and not any(c[k] == s for s in seen):
                out.append(Finding("MIRROR", f"conditions[{i}].{k}",
                                   f"body {c[k]!r}; the record's conditions carry {sorted(map(repr, seen))}", "WARN"))
    # the per-node hold check: every hold the body sends should be one the record carries
    rec_holds = [h for c in rconds for _, h in _holds(c.get("definition"), "")]
    if rec_holds:
        for i, c in enumerate(bconds):
            if not isinstance(c, dict):
                continue
            for path, h in _holds(c.get("definition"), f"conditions[{i}].definition"):
                if not any(h == r for r in rec_holds):
                    out.append(Finding("MIRROR", path,
                                       f"body hold {h!r}; the record's nodes carry "
                                       f"{sorted({repr(r) for r in rec_holds})}", "WARN"))
    return out


_BOUND_KEYS = ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
               "minLength", "maxLength", "minItems", "maxItems")


def schema_index(arm: dict, root: dict) -> dict[str, dict]:
    """Flatten an arm to {path: {enum, required, properties, bounds}} for changelog diffs.
    Recursion is cut on a schema node already on the current path."""
    out: dict[str, dict] = {}

    def visit(node: dict, path: str, stack: tuple[int, ...]) -> None:
        node = deref(node, root)
        entry = out.setdefault(path, {"enum": None, "required": [], "properties": [], "bounds": {}})
        if id(node) in stack:
            return
        stack = stack + (id(node),)
        if "anyOf" in node:
            for i, b in enumerate(node["anyOf"]):
                visit(b, f"{path}|{i}" if path else f"|{i}", stack)
            return
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
                               f"missing {sorted(set(want) - set(got))[:5]} extra {sorted(set(got) - set(want))[:5]}; "
                               "either mistranscribed, or the platform's set grew/shrank since the repo data "
                               "was captured - verify with a second read-back before refreshing data/derived "
                               "or data/contract", "FAIL"))
    if not deref(arm, root).get("required"):
        out.append(Finding("TRANSCRIPTION_SUSPECT", "", "arm has no required list", "FAIL"))
    return out


# History: the ten axes of 91.0.0 (data/contract/stage_strategy_draft/schema_20261005T194629Z.json).
AXES_91 = ("IDENTITY", "TIMEFRAME_PROFILE", "REPORT", "MARKET_READ", "CONDITIONS", "ENTRY",
           "SETUP_GATES", "TRADE_LEVEL_POLICY", "POSITION_MANAGEMENT", "SIGNAL_RULES")
# The eight axes of 108.0.0 (data/contract/stage_strategy_draft/schema_20261010T215326Z.json; README "Contract
# history - v108": "stage_strategy_draft refuses the SIGNAL_RULES and SETUP_GATES axes as unrecognized keys").
AXES_108 = tuple(a for a in AXES_91 if a not in ("SETUP_GATES", "SIGNAL_RULES"))


def fingerprint_axes(axis_schemas: dict[str, dict], root: dict, *,
                     template_keys: set[str], timeframes: list[str]) -> list[Finding]:
    """Fidelity of a transcribed stage_strategy_draft capture against data the repo holds
    independently - the fingerprint_schema checks at their homes on the axes (REPORT,
    TIMEFRAME_PROFILE) - plus the eight axes the 108.0.0 schema declares.

    Contract 108 (2026-10-11): the SIGNAL_RULES signalId check is retired with the axis - the
    stage serves no signal id, and no signal definition exists to check a parameter against."""
    out: list[Finding] = []
    if set(axis_schemas) != set(AXES_108):
        out.append(Finding("TRANSCRIPTION_SUSPECT", "axes",
                           f"axes {sorted(axis_schemas)} are not the eight of 108.0.0; either "
                           "mistranscribed, or the platform's axis set moved - read the "
                           "changelog and re-capture before trusting the walk", "FAIL"))
    checks = (
        ("axes.REPORT.sections[].platform.sectionKey",
         _enum_at(axis_schemas.get("REPORT", {}), root, "sections", "[]", "anyOf:platform", "sectionKey"),
         template_keys),
        ("axes.TIMEFRAME_PROFILE.timeframe",
         _enum_at(axis_schemas.get("TIMEFRAME_PROFILE", {}), root, "timeframe"), set(timeframes)),
    )
    for path, got, want in checks:
        if got is None:
            out.append(Finding("TRANSCRIPTION_SUSPECT", path, "enum not found in the capture", "FAIL"))
        elif set(got) != set(want) or len(got) != len(set(got)):
            out.append(Finding("TRANSCRIPTION_SUSPECT", path,
                               f"enum has {len(got)} values, repo data has {len(want)}; "
                               f"missing {sorted(set(want) - set(got))[:5]} extra {sorted(set(got) - set(want))[:5]}; "
                               "either mistranscribed, or the platform's set grew/shrank since the repo data "
                               "was captured - verify with a second read-back before refreshing data/derived "
                               "or data/contract", "FAIL"))
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
                           f"{len(rules) if isinstance(rules, list) else type(rules).__name__}; "
                           "either mistranscribed, or the platform's set grew/shrank since the repo data "
                           "was captured - verify with a second read-back before refreshing data/derived "
                           "or data/contract", "FAIL"))
    conds = rec.get("conditions")
    if not isinstance(conds, list) or not conds:
        out.append(Finding("TRANSCRIPTION_SUSPECT", "conditions", "expected a non-empty conditions list", "FAIL"))
    return out


GATE_LINE_PREFIX = "PREFLIGHT PASS"
_ISO = "%Y-%m-%dT%H:%M:%SZ"


def body_sha256(body: dict) -> str:
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def verdict(findings: list[Finding]) -> str:
    return "FAIL" if any(f.verdict == "FAIL" for f in findings) else "PASS"


def parse_iso(s: str) -> datetime:
    """Parse `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` or the same with a `+HH:MM`/`+00:00` offset,
    returning an aware UTC datetime. Platform timestamps carry milliseconds
    (2026-08-28T13:48:33.561Z); the original strict `%Y-%m-%dT%H:%M:%SZ` format rejected
    both that and the `+00:00` spelling."""
    if not isinstance(s, str):
        raise ValueError(f"not a string: {s!r}")
    txt = s.strip()
    if len(txt) > 10 and txt[10] != "T":
        # fromisoformat also takes a space (and any one character); the documented form - and every stored
        # capturedAt / expiresAt - uses the T
        raise ValueError(f"unparsable ISO-8601 timestamp (date and time must be joined by 'T'): {s!r}")
    if txt.endswith("Z") or txt.endswith("z"):
        txt = txt[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError as exc:
        raise ValueError(f"unparsable ISO-8601 timestamp: {s!r}") from exc
    if dt.tzinfo is None:
        raise ValueError(f"timestamp has no timezone/Z suffix: {s!r}")
    return dt.astimezone(timezone.utc)


_parse_iso = parse_iso  # kept for existing internal callers


def build_receipt(*, body: dict, body_path: str, operation: str, schema_meta: dict,
                  readback_meta: dict | None, findings: list[Finding], now: datetime,
                  expires_minutes: int = 60, unmeasured: list[str] | None = None,
                  receipt_path: str = "<receipt>") -> dict:
    """`readback_meta` is None since v85: the read-back mirror is retired until a v91
    read-back is captured, and the expiry then runs from the schema capture alone."""
    captured = [_parse_iso(schema_meta["capturedAt"])]
    if readback_meta is not None:
        captured.append(_parse_iso(readback_meta["capturedAt"]))
    oldest = min(captured)
    receipt = {
        "_what": "Schema-drift preflight receipt: the body walked against a fresh tool "
                 "definition capture (since v85 the stage_strategy_draft axes; the read-back "
                 "mirror is retired until a 108 read-back exists). A PASS is a precondition of "
                 "the authorization, not the authorization. Nothing here was interpreted.",
        "when": now.strftime(_ISO),
        "body": {"path": body_path, "sha256": body_sha256(body), "operation": operation},
        "captures": {"schema": dict(schema_meta),
                     "readback": dict(readback_meta) if readback_meta is not None else None},
        "findings": [f.__dict__ for f in findings],
        "verdict": verdict(findings),
        "expiresAt": (oldest + timedelta(minutes=expires_minutes)).strftime(_ISO),
        "disclaimer": DISCLAIMER,
        "unmeasured": list(unmeasured or []),
        "voided": None,
    }
    receipt["gateLine"] = gate_line(receipt, receipt_path) if receipt["verdict"] == "PASS" else None
    return receipt


def gate_line(receipt: dict, receipt_path: str = "<receipt>") -> str:
    rb = receipt["captures"]["readback"]
    ref = f"ref {rb['strategyId']} rev {rb['revision']}" if rb else "ref none (read-back retired)"
    return (f"{GATE_LINE_PREFIX} · {receipt_path} · body {receipt['body']['sha256'][:8]} · "
            f"schema {receipt['captures']['schema']['capturedAt']} · {ref} · "
            f"expires {receipt['expiresAt']}")


def gate_check(receipt: dict, body: dict, now: datetime) -> tuple[bool, str]:
    if receipt.get("voided"):
        return False, f"receipt voided: {receipt['voided']}"
    if receipt.get("verdict") != "PASS":
        return False, f"receipt verdict is {receipt.get('verdict')!r}"
    try:
        receipt_sha = receipt["body"]["sha256"]
    except (KeyError, TypeError) as exc:
        return False, f"receipt malformed: {exc!r}"
    if receipt_sha != body_sha256(body):
        return False, "body sha256 does not match the receipt (the body changed after the preflight)"
    if now.tzinfo is None or now.utcoffset() is None:
        return False, "now must be timezone-aware UTC; refusing to compare against expiresAt"
    try:
        expires_at = _parse_iso(receipt["expiresAt"])
    except (KeyError, TypeError, ValueError) as exc:
        return False, f"receipt malformed: {exc!r}"
    if now >= expires_at:
        return False, f"receipt expired at {receipt['expiresAt']}; re-run the preflight"
    return True, "PASS"
