"""Set-compare a live tool surface's authoring enums against this repo's extraction.

    python scripts/compare_vocabulary.py <surface.json>

`<surface.json>` is a stored tool surface: an object with `contractVersion`, `buildSha`,
`observedAt` and `tools` (a list of `{name, inputSchema, ...}`). The battlegrid-manager
keeps the live one in `system_state["surface_tools"]`, so a drift check makes no platform
call:

    docker exec battlegrid-manager-postgres-1 psql -U manager -d manager -At \\
        -c "SELECT value::text FROM system_state WHERE key = 'surface_tools';" > surface.json

It prints the `results` block of a `data/audit/contract_<N>_vocabulary_*.json` record and
exits 0 when all three enums are identical in both directions, 1 when any moved. Nothing
is typed by hand: each live enum is read from the schema the platform serves, and each
stored enum from the extraction this repo authors against.
- metric: `get_metric_construction_hints` `properties.metric.enum`, against the
  `data/contract/metrics/<METRIC>.json` files;
- signalId: the first `signalId` enum in `update_strategy_signal_rule`, against the keys
  of `data/contract/signals/_scoring.json["signals"]`;
- sectionKey: the first `sectionKey` enum in `compile_strategy_plan`, against the same
  enum in the newest `data/contract/compile_strategy_plan/schema_*.json` capture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data" / "contract"


def first_enum(node, prop: str) -> list | None:
    """Depth-first: the `enum` of the first property named `prop` that carries one, else None."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict) and isinstance(props.get(prop), dict) and "enum" in props[prop]:
            return props[prop]["enum"]
        for value in node.values():
            found = first_enum(value, prop)
            if found is not None:
                return found
    elif isinstance(node, list):
        for value in node:
            found = first_enum(value, prop)
            if found is not None:
                return found
    return None


def _input_schema(tools: dict, name: str) -> dict:
    if name not in tools:
        raise KeyError(f"the surface has no tool {name!r}; it cannot be compared")
    return tools[name].get("inputSchema") or {}


def live_enums(surface: dict) -> dict[str, set[str]]:
    tools = {t["name"]: t for t in surface["tools"]}
    found = {
        "metrics": first_enum(_input_schema(tools, "get_metric_construction_hints"), "metric"),
        "signals": first_enum(_input_schema(tools, "update_strategy_signal_rule"), "signalId"),
        "sectionKeys": first_enum(_input_schema(tools, "compile_strategy_plan"), "sectionKey"),
    }
    missing = [k for k, v in found.items() if not v]
    if missing:
        # An absent enum is unreadable, not empty: comparing it would report every stored value as removed.
        raise ValueError(f"no enum found on the surface for: {', '.join(missing)}")
    return {k: set(v) for k, v in found.items()}


def newest_compile_capture(contract: Path = CONTRACT) -> Path:
    captures = sorted((contract / "compile_strategy_plan").glob("schema_*.json"))
    if not captures:
        raise FileNotFoundError("no compile_strategy_plan/schema_*.json capture in the extraction")
    return captures[-1]


def stored_enums(contract: Path = CONTRACT) -> dict[str, set[str]]:
    capture = json.loads(newest_compile_capture(contract).read_text(encoding="utf-8"))
    scoring = json.loads((contract / "signals" / "_scoring.json").read_text(encoding="utf-8"))
    return {
        "metrics": {p.stem for p in (contract / "metrics").glob("*.json") if not p.name.startswith("_")},
        "signals": set(scoring["signals"]),
        "sectionKeys": set(first_enum(capture, "sectionKey") or []),
    }


def compare(live: dict[str, set[str]], stored: dict[str, set[str]]) -> dict:
    return {k: {"live": len(live[k]), "stored": len(stored[k]),
                "liveNotStored": sorted(live[k] - stored[k]), "storedNotLive": sorted(stored[k] - live[k])}
            for k in ("metrics", "signals", "sectionKeys")}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    surface = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    results = compare(live_enums(surface), stored_enums())
    print(json.dumps({"contractVersion": surface.get("contractVersion"), "buildSha": surface.get("buildSha"),
                      "observedAt": surface.get("observedAt"), "liveToolCount": len(surface["tools"]),
                      "storedCompileCapture": newest_compile_capture().relative_to(ROOT).as_posix(),
                      "results": results}, indent=1))
    moved = any(r["liveNotStored"] or r["storedNotLive"] for r in results.values())
    return 1 if moved else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
