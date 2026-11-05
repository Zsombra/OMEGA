"""Merge extracted metric batches into the canonical corpus and derive classification artifacts.

Reads   : data/contract/metrics/_batch*.json, vocabulary/_shared.json,
          transforms/_authoring.json, templates/platform/_all.json, categories.json
Writes  : data/contract/metrics/<METRIC>.json      (one file per metric)
          data/contract/metrics/_index.json
          data/derived/composability_matrix.csv
          data/derived/spread_operand_graph.json
          data/derived/platform_privileged.json
          data/derived/type_system.json

Pure local computation - performs no network or MCP calls.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "data" / "contract"
DERIVED = ROOT / "data" / "derived"

# The authoritative 144-metric roster, taken verbatim from the `metric` enum in the live
# compile_strategy_plan JSON Schema (contract 54.1.0, 2026-09-09) and cross-checked against
# list_strategy_vocabulary across all ten categories - the two agree exactly. Was 86 on
# 2026-08-24 and 135 on 2026-09-05; SWING_HIGH/SWING_LOW were RENAMED to
# DONCHIAN_UPPER/DONCHIAN_LOWER at contract 53.0.0 and nine TPO (market-profile) metrics
# plus the two Donchian edges arrived by 54.1.0.
# The platform-order roster: the write schema column metric enum, derived (data/derived/condition_vocabulary_108.json
# from the manifest writeSurface) - no longer a typed list (156 names, typed 2026-09-20; 171 since contract 104).
METRIC_ENUM = json.loads((Path(__file__).resolve().parents[1] / "data" / "derived" / "condition_vocabulary_108.json")
                         .read_text(encoding="utf-8"))["reportColumn"]["metric"]["enum"]
# Served and known by NAME only (data/contract/metrics/_unmeasured_108.json `metrics`; 206 at 148.1.0 on 2026-11-05,
# before the hint step reached them): no batch record exists for them, so the measured roster is the served one minus
# these. Without this the script stopped at "roster mismatch" whenever the write surface moved ahead of the corpus,
# and no derived artefact could be regenerated in between.
_UNMEASURED_PATH = CONTRACT / "metrics" / "_unmeasured_108.json"
UNMEASURED = (set(json.loads(_UNMEASURED_PATH.read_text(encoding="utf-8")).get("metrics") or {})
              if _UNMEASURED_PATH.exists() else set())
MEASURED = [name for name in METRIC_ENUM if name not in UNMEASURED]

# nativeOutput.kind -> the condition operators the compiler exposes for that output.
# Sourced from observed get_strategy_column_contract responses.
CONDITION_OPERATORS = {
    "numeric": ["lt", "lte", "gte", "gt", "between"],
    "direction": ["is", "in"],
    "classification": ["is", "in"],
    "event": ["is", "in"],
    "boolean": ["is"],
    "date": ["lt", "lte", "gte", "gt", "between"],
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def merge_metrics() -> dict:
    records: dict[str, dict] = {}
    for batch in sorted((CONTRACT / "metrics").glob("_batch*.json")):
        for rec in load_json(batch):
            name = rec["metric"]
            if name in records:
                raise SystemExit(f"duplicate metric record: {name} (in {batch.name})")
            records[name] = rec
    return records


def verify(records: dict, categories: dict, unmeasured: set[str] | None = None) -> None:
    """The batches hold exactly the served roster minus the metrics known by name only, and the connector's family
    counts reconcile: exactly when nothing is unmeasured; otherwise no family holds more than declared and the
    families' shortfall is exactly the unmeasured count (an unmeasured key's family is not measured)."""
    unmeasured = UNMEASURED if unmeasured is None else unmeasured
    if unmeasured - set(METRIC_ENUM):
        raise SystemExit(f"listed unmeasured but not served: {sorted(unmeasured - set(METRIC_ENUM))}")
    got, want = set(records), set(METRIC_ENUM) - unmeasured
    if got & unmeasured:
        raise SystemExit(f"measured AND listed unmeasured: {sorted(got & unmeasured)} - drop them from "
                         f"{_UNMEASURED_PATH.name}")
    if got != want:
        raise SystemExit(
            f"roster mismatch\n  missing: {sorted(want - got)}\n  extra: {sorted(got - want)}"
        )

    declared = {c["category"]: c["metricCount"] for c in categories["categories"]}
    actual: dict[str, int] = defaultdict(int)
    for rec in records.values():
        actual[rec["family"]] += 1
    shortfall = {}
    for fam in sorted(set(declared) | set(actual)):
        count = declared.get(fam, 0)
        if actual[fam] > count or (actual[fam] < count and not unmeasured):
            raise SystemExit(
                f"family '{fam}': connector declares {count}, corpus holds {actual[fam]}"
            )
        if actual[fam] < count:
            shortfall[fam] = count - actual[fam]
    if sum(shortfall.values()) != len(unmeasured):
        raise SystemExit(f"families short of the connector's counts by {shortfall} (total {sum(shortfall.values())}), "
                         f"but {len(unmeasured)} metrics are listed unmeasured")
    print(f"OK  {len(records)}/{len(METRIC_ENUM)} metrics measured"
          + (f" ({len(unmeasured)} known by name only)" if unmeasured else "")
          + f"; all {len(categories['categories'])} family counts reconcile with the connector"
          + (f" (short by {shortfall}: the unmeasured)" if shortfall else ""))


def _required(authoring: dict, tid: str, parameter: str) -> bool:
    """v103: `operandRequired` / `sideRequired` left the served transform entry; read
    `authoring.parameters.{inputs,side}.required` instead (equal on every 61.2.0 cell -
    tests/test_v103_transform_entry.py). A corpus extracted before v103 still carries the flags."""
    params = (authoring.get(tid) or {}).get("parameters") or {}
    return bool((params.get(parameter) or {}).get("required"))


def build_composability(records: dict, shared: dict) -> list[dict]:
    authoring = load_json(CONTRACT / "transforms" / "_authoring.json")["transforms"]
    # The served catalogue (vocabulary/_shared.json) can be ahead of the extraction: `ema` is served at 148.1.0 and
    # no metric record measured it yet. A matrix column for it would read "no" on every metric - a false refusal - so
    # only the transforms the extraction's catalogue holds get a column (omega.contract reads the rest as unmeasured).
    transform_ids = [t["id"] for t in shared["transforms"] if t["id"] in authoring]
    rows = []
    for name in MEASURED:
        rec = records[name]
        offered = {t["id"]: t for t in rec["transforms"]}
        for tid in transform_ids:
            t = offered.get(tid)
            rows.append({
                "metric": name,
                "family": rec["family"],
                "nativeKind": rec["nativeOutput"]["kind"],
                "unit": rec["nativeOutput"].get("unit", ""),
                "timeframeMode": rec["timeframeMode"],
                "transform": tid,
                "legal": "yes" if t else "no",
                "operandRequired": "yes" if t and (t.get("operandRequired") or _required(authoring, tid, "inputs")) else "",
                "sideRequired": "yes" if t and (t.get("sideRequired") or _required(authoring, tid, "side")) else "",
                "chainSuccessors": "|".join(t.get("chainSuccessors", [])) if t else "",
                "chainedRankOrderings": "|".join(t.get("chainedRankOrderings", [])) if t else "",
                "rankableSpreadOperands": "|".join(t.get("rankableSpreadOperands", [])) if t else "",
                "rankOrderings": "|".join(rec.get("rankOrderings", [])) if t and tid == "rank" else "",
                "spreadOperandCount": len(rec.get("spreadOperands", [])) if t and tid == "spread" else "",
            })
    return rows


def build_privileged(records: dict, templates: dict) -> dict:
    """(metric, transform) pairs the platform's own templates use that authors cannot."""
    findings = []
    for section in templates["templates"]:
        for col in section["columns"]:
            m, tid = col["metric"], col["transformId"]
            offered = {t["id"] for t in records[m]["transforms"]}
            if tid not in offered:
                findings.append({
                    "metric": m,
                    "transform": tid,
                    "usedBySection": section["sectionKey"],
                    "sectionTitle": section["title"],
                    "authorableAlternatives": sorted(offered),
                })
    return {
        "_note": (
            "Pairs referenced by platform section templates that are ABSENT from the "
            "metric's authorable transform whitelist. Custom columns using these are "
            "rejected with REPORT_COLUMN_PAIR_UNSUPPORTED."
        ),
        "pairCount": len(findings),
        "pairs": findings,
    }


def build_spread_graph(records: dict) -> dict:
    by_unit: dict[str, list[str]] = defaultdict(list)
    edges = {}
    asymmetric = []
    for name in MEASURED:
        rec = records[name]
        ops = rec.get("spreadOperands")
        if ops is not None:
            edges[name] = ops
            by_unit[rec["nativeOutput"].get("unit", "?")].append(name)
    for a, ops in edges.items():
        for b in ops:
            if b in edges and a not in edges[b]:
                asymmetric.append({"from": a, "to": b, "reciprocal": False})
    return {
        "_note": (
            "spread operand whitelists. Pools are scoped by nativeOutput.unit - a metric "
            "may only spread against operands sharing its unit class, and never against itself."
        ),
        "unitPools": {u: sorted(m) for u, m in sorted(by_unit.items())},
        "edges": edges,
        "asymmetricEdges": asymmetric,
        "metricsWithoutSpread": sorted(
            m for m in MEASURED if records[m].get("spreadOperands") is None
        ),
    }


def build_type_system(records: dict) -> dict:
    kinds: dict[str, dict] = {}
    for name in MEASURED:
        no = records[name]["nativeOutput"]
        k = no["kind"]
        entry = kinds.setdefault(k, {
            "conditionOperators": CONDITION_OPERATORS.get(k, []),
            "units": set(),
            "metrics": [],
            "vocabularies": {},
        })
        entry["metrics"].append(name)
        if "unit" in no:
            entry["units"].add(no["unit"])
        if "vocab" in no:
            entry["vocabularies"][name] = no["vocab"]
    for entry in kinds.values():
        entry["units"] = sorted(entry["units"])
        entry["metricCount"] = len(entry["metrics"])
    return {
        "_note": (
            "nativeOutput.kind drives which condition operators a compiled output header "
            "accepts. Every trajectory column also emits one synthetic '_trend' output of "
            "kind 'direction' with vocabulary [rising, falling, flat]."
        ),
        "kinds": kinds,
        "syntheticOutputKinds": {
            "direction": {
                "conditionOperators": ["is", "in"],
                "vocabulary": ["rising", "falling", "flat"],
                "producedBy": "trajectory transform (the _trend output)",
            }
        },
    }


def main() -> None:
    categories = load_json(CONTRACT / "categories.json")
    shared = load_json(CONTRACT / "vocabulary" / "_shared.json")
    templates = load_json(CONTRACT / "templates" / "platform" / "_all.json")

    records = merge_metrics()
    verify(records, categories)

    # one canonical file per metric
    for name, rec in records.items():
        (CONTRACT / "metrics" / f"{name}.json").write_text(
            json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    (CONTRACT / "metrics" / "_index.json").write_text(
        json.dumps(
            {
                "metricCount": len(records),
                "byFamily": {
                    fam: sorted(m for m, r in records.items() if r["family"] == fam)
                    for fam in sorted({r["family"] for r in records.values()})
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    DERIVED.mkdir(parents=True, exist_ok=True)

    rows = build_composability(records, shared)
    with (DERIVED / "composability_matrix.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    privileged = build_privileged(records, templates)
    (DERIVED / "platform_privileged.json").write_text(
        json.dumps(privileged, indent=2, ensure_ascii=False), encoding="utf-8")

    (DERIVED / "spread_operand_graph.json").write_text(
        json.dumps(build_spread_graph(records), indent=2, ensure_ascii=False), encoding="utf-8")

    (DERIVED / "type_system.json").write_text(
        json.dumps(build_type_system(records), indent=2, ensure_ascii=False), encoding="utf-8")

    legal = sum(1 for r in rows if r["legal"] == "yes")
    print(f"OK  composability matrix: {legal}/{len(rows)} cells legal "
          f"({100*legal/len(rows):.1f}% density)")
    print(f"OK  platform-privileged pairs found: {privileged['pairCount']}")
    for p in privileged["pairs"]:
        print(f"      {p['metric']} x {p['transform']}  (used by {p['usedBySection']})")


if __name__ == "__main__":
    main()
