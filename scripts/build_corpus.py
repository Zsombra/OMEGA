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

# The authoritative 86-metric roster, taken verbatim from the `metric` enum in the
# get_metric_construction_hints JSON Schema published by the connector.
METRIC_ENUM = [
    "OPEN", "HIGH", "LOW", "CLOSE", "LAST", "MARK", "ORACLE", "SPOT_CLOSE_CB",
    "SPOT_CLOSE_BN", "BAR_FORMING", "RSI14", "RSI7", "MACD", "STOCH_K", "STOCH_D",
    "MFI14", "PPO", "ROC12", "CCI20", "CLOSE_CHANGE", "CHG_5M", "CHG_15M", "CHG_1H",
    "CHG_4H", "CHG_24H", "ADX", "SMA20", "SMA50", "SMA200", "EMA5", "EMA13", "EMA20",
    "EMA_CROSS", "MA_ALIGN", "ATR", "ATR_PCT", "BB_WIDTH", "BB_WIDTH_PCT", "HIGH_DEV",
    "LOW_DEV", "BB_PCT_B", "SWING_HIGH", "SWING_LOW", "VWAP", "PRICE_ZONE", "BB_TOUCH",
    "STRUCT_ZONES", "VOLUME", "VOL_SMA20", "TRADES", "BUY_VOLUME", "SELL_VOLUME",
    "NOTIONAL_VOLUME_1D", "RVOL", "OBV", "CVD", "SPOT_CVD", "BUY_PRESSURE", "BUY_TRADES",
    "SELL_TRADES", "FUNDING_RATE", "FUNDING_ANN", "FUNDING_LABEL", "OI", "OI_CHG",
    "OI_VELOCITY", "OI_PX_REGIME", "REGIME_TREND", "REGIME_VOL", "REGIME_MOM",
    "CROWD_PICK", "CROWD_UPBIAS", "CROWD_ACC", "CROWD_CAPT", "CROWD_PICK_LIVE",
    "CROWD_UPBIAS_LIVE", "CROWD_ACC_LIVE", "CROWD_CAPT_LIVE", "SETTLED_AT", "FLOW_ALIGN",
    "SMART_RETAIL", "CAPTAIN_CONF", "CONFIDENCE", "PERP_SPOT_FLOW", "PERP_SPOT_STRENGTH",
    "PERP_SPOT_CONFIRMS",
]

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


def verify(records: dict, categories: dict) -> None:
    got, want = set(records), set(METRIC_ENUM)
    if got != want:
        raise SystemExit(
            f"roster mismatch\n  missing: {sorted(want - got)}\n  extra: {sorted(got - want)}"
        )

    declared = {c["category"]: c["metricCount"] for c in categories["categories"]}
    actual: dict[str, int] = defaultdict(int)
    for rec in records.values():
        actual[rec["family"]] += 1
    for fam, count in declared.items():
        if actual[fam] != count:
            raise SystemExit(
                f"family '{fam}': connector declares {count}, corpus holds {actual[fam]}"
            )
    print(f"OK  86/86 metrics; all 10 family counts reconcile with the connector")


def build_composability(records: dict, shared: dict) -> list[dict]:
    transform_ids = [t["id"] for t in shared["transforms"]]
    rows = []
    for name in METRIC_ENUM:
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
                "operandRequired": "yes" if t and t.get("operandRequired") else "",
                "sideRequired": "yes" if t and t.get("sideRequired") else "",
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
    for name in METRIC_ENUM:
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
            m for m in METRIC_ENUM if records[m].get("spreadOperands") is None
        ),
    }


def build_type_system(records: dict) -> dict:
    kinds: dict[str, dict] = {}
    for name in METRIC_ENUM:
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
