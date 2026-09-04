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
