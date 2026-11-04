"""Set-compare a live tool surface's authoring enums against this repo's extraction.

    python scripts/compare_vocabulary.py <surface.json>

`<surface.json>` is a stored tool surface: an object with `contractVersion`, `buildSha`,
`observedAt` and `tools` (a list of `{name, inputSchema, ...}`). The battlegrid-manager
keeps the live one in `system_state["surface_tools"]`, so a drift check makes no platform
call:

    docker exec battlegrid-manager-postgres-1 psql -U manager -d manager -At \\
        -c "SELECT value::text FROM system_state WHERE key = 'surface_tools';" > surface.json

It prints the `results` block of a `data/audit/contract_<N>_vocabulary_*.json` record and
exits 0 when both enums are identical in both directions, 1 when either moved. Nothing
is typed by hand: each live enum is read from the schema the platform serves, and each
stored enum from the extraction this repo authors against.
- metric: `get_metric_construction_hints` `properties.metric.enum` - since contract v137.2 the
  property is `{"$ref": "#/$defs/metricKey"}` and the enum is read through that pointer
  (`first_enum`; measured on the watch's stored 144.2.0 surface on 2026-10-30, where the
  inline read had left the manager's gate `SURFACE_UNREAD`) - against the
  `data/contract/metrics/<METRIC>.json` files;
- sectionKey: the `sectionKey` enum on `stage_strategy_draft`'s REPORT axis, against the
  same enum in the newest `data/contract/stage_strategy_draft/schema_*.json` capture.

Contract 85.0.0 removed compile_strategy_plan and update_strategy_signal_rule with no
alias (README "Contract history - v85": "a signal rule is a row of the draft's SIGNAL_RULES
axis"), so both enums are read off the stage tool's axes now; the compile captures are
retired (data/contract/_manifest.json). The 2026-09-26..10-02 records under data/audit/
were made by the compile-era form of this script, which is in the repository history.

Contract 108.0.0 (2026-10-11) removed the SIGNAL_RULES axis ("stage_strategy_draft refuses the SIGNAL_RULES and
SETUP_GATES axes as unrecognized keys", README "Contract history - v108"): the platform serves no signalId enum to
compare, so the `signals` kind is retired. Reading it would raise on every 108 surface ("an absent enum is
unreadable"); the v91 form of this script is in the repository history.

2026-10-11 (plan docs/plans/2026-10-11-omega-condition-vocabulary-108.md): the stored `metrics` are the measured corpus
(`data/contract/metrics/<METRIC>.json`, 156) PLUS the metrics known by name only
(`data/contract/metrics/_unmeasured_108.json`, 15 - served by the 108 write schema, transform admissibility
unmeasured). A served metric omega knows by name is therefore not `liveNotStored`; `compare(..., unmeasured=...)`
lists the served ones under `storedUnmeasured` so the difference stays visible. omega never emits one
(omega.validate METRIC_UNMEASURED).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omega.preflight import resolve_axes  # noqa: E402

CONTRACT = ROOT / "data" / "contract"
STAGE_TOOL = "stage_strategy_draft"


def _pointer(root, ref):
    """The node a local JSON pointer (`#/$defs/metricKey`) names in `root`, or None when any step is missing or the
    reference is not local. `~1` and `~0` unescape as RFC 6901 says."""
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    node = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return None
    return node


def first_enum(node, prop: str, root=None) -> list | None:
    """Depth-first: the `enum` of the first property named `prop` that carries one, else None.

    Since contract v137.2 the platform names the metric vocabulary once per schema: the property is
    `{"$ref": "#/$defs/metricKey"}` and the enum sits under `$defs` (measured on the 144.2.0 surface, 2026-10-30).
    Such a pointer is followed against `root` - the schema the search started in, by default `node` itself - at the
    property looked up and nowhere else, so a self-referential `$defs` entry (conditionNode refers to conditionNode)
    is never expanded while walking. A pointer that resolves to nothing, or to a node without `enum`, reads as no
    enum here and the search goes on."""
    if root is None:
        root = node
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and isinstance(props.get(prop), dict):
            target = props[prop]
            if "enum" not in target and "$ref" in target:
                target = _pointer(root, target["$ref"])
            if isinstance(target, dict) and "enum" in target:
                return target["enum"]
        for value in node.values():
            found = first_enum(value, prop, root)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = first_enum(value, prop, root)
            if found is not None:
                return found
    return None


def _input_schema(tools: dict, name: str) -> dict:
    if name not in tools:
        raise KeyError(f"the surface has no tool {name!r}; it cannot be compared")
    return tools[name].get("inputSchema") or {}


def _axes(definition: dict) -> dict[str, dict]:
    axes, _root = resolve_axes(definition)
    return axes


def live_enums(surface: dict) -> dict[str, set[str]]:
    tools = {t["name"]: t for t in surface["tools"]}
    _input_schema(tools, STAGE_TOOL)                    # refuses a surface without the tool
    axes = _axes(tools[STAGE_TOOL])
    found = {
        "metrics": first_enum(_input_schema(tools, "get_metric_construction_hints"), "metric"),
        "sectionKeys": first_enum(axes.get("REPORT", {}), "sectionKey"),
    }
    missing = [k for k, v in found.items() if not v]
    if missing:
        # An absent enum is unreadable, not empty: comparing it would report every stored value as removed.
        raise ValueError(f"no enum found on the surface for: {', '.join(missing)}")
    return {k: set(v) for k, v in found.items()}


def newest_stage_capture(contract: Path = CONTRACT) -> Path:
    captures = sorted((contract / STAGE_TOOL).glob("schema_*.json"))
    if not captures:
        raise FileNotFoundError(f"no {STAGE_TOOL}/schema_*.json capture in the extraction")
    return captures[-1]


def stored_unmeasured(contract: Path = CONTRACT) -> dict[str, set[str]]:
    """Per kind, the stored values known by name only (their admissibility is unmeasured): metrics only."""
    path = contract / "metrics" / "_unmeasured_108.json"
    names = set(json.loads(path.read_text(encoding="utf-8"))["metrics"]) if path.exists() else set()
    return {"metrics": names, "sectionKeys": set()}


def stored_enums(contract: Path = CONTRACT) -> dict[str, set[str]]:
    doc = json.loads(newest_stage_capture(contract).read_text(encoding="utf-8"))
    # a session capture is an envelope ({capturedAt, how, request, response}); the saved
    # manager-surface file is keyed by tool - resolve_axes reads either
    capture = doc["response"] if isinstance(doc.get("response"), dict) else doc
    return {
        "metrics": {p.stem for p in (contract / "metrics").glob("*.json") if not p.name.startswith("_")}
        | stored_unmeasured(contract)["metrics"],
        "sectionKeys": set(first_enum(_axes(capture).get("REPORT", {}), "sectionKey") or []),
    }


def compare(live: dict[str, set[str]], stored: dict[str, set[str]],
            unmeasured: dict[str, set[str]] | None = None) -> dict:
    """Per kind: counts, `liveNotStored`, `storedNotLive`, and `storedUnmeasured` - the served values that are stored
    by name only (empty unless `unmeasured` is given). A caller that reads only the first two is unaffected."""
    unmeasured = unmeasured or {}
    return {k: {"live": len(live[k]), "stored": len(stored[k]),
                "liveNotStored": sorted(live[k] - stored[k]), "storedNotLive": sorted(stored[k] - live[k]),
                "storedUnmeasured": sorted(live[k] & unmeasured.get(k, set()))}
            for k in ("metrics", "sectionKeys")}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    surface = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    results = compare(live_enums(surface), stored_enums(), stored_unmeasured())
    print(json.dumps({"contractVersion": surface.get("contractVersion"), "buildSha": surface.get("buildSha"),
                      "observedAt": surface.get("observedAt"), "liveToolCount": len(surface["tools"]),
                      "storedStageCapture": newest_stage_capture().relative_to(ROOT).as_posix(),
                      "results": results}, indent=1))
    moved = any(r["liveNotStored"] or r["storedNotLive"] for r in results.values())
    return 1 if moved else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
