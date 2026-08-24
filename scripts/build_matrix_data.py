"""Emit a compact JSON payload for the interactive composability matrix artifact."""
from __future__ import annotations

import json
from pathlib import Path

from omega.contract import CONTRACT_DIR, DERIVED_DIR, ROOT, load

TRANSFORM_ORDER = [
    "value", "trajectory", "distance", "spread", "efficiency", "aggregate",
    "maxShare", "rank", "classifyZone", "crossDetect", "bandTouch",
    "count", "nearestZoneType", "nearestZoneRange", "nearestZoneDist", "nearestZoneAge",
]
FAMILY_ORDER = ["price", "momentum", "trend", "volatility", "volumeFlow",
                "derivatives", "structure", "regime", "crowd", "derived"]
SHORT = {
    "value": "val", "trajectory": "traj", "distance": "dist", "spread": "sprd",
    "efficiency": "eff", "aggregate": "agg", "maxShare": "mxSh", "rank": "rank",
    "classifyZone": "zone", "crossDetect": "xdet", "bandTouch": "band",
    "count": "cnt", "nearestZoneType": "nzTy", "nearestZoneRange": "nzRg",
    "nearestZoneDist": "nzDs", "nearestZoneAge": "nzAg",
}


def main() -> None:
    c = load()
    cats = {x["category"]: x for x in json.loads(
        (CONTRACT_DIR / "categories.json").read_text(encoding="utf-8"))["categories"]}
    graph = json.loads((DERIVED_DIR / "spread_operand_graph.json").read_text(encoding="utf-8"))
    priv = json.loads((DERIVED_DIR / "platform_privileged.json").read_text(encoding="utf-8"))
    templates = json.loads(
        (CONTRACT_DIR / "templates" / "platform" / "_all.json").read_text(encoding="utf-8"))

    # which (metric, transform) pairs the platform's own templates actually use
    used_by_platform: dict[str, set[str]] = {}
    for section in templates["templates"]:
        for col in section["columns"]:
            used_by_platform.setdefault(col["metric"], set()).add(col["transformId"])

    priv_pairs = {}
    for p in priv["pairs"]:
        priv_pairs.setdefault(p["metric"], {})[p["transform"]] = p["usedBySection"]

    transforms = []
    for tid in TRANSFORM_ORDER:
        t = c.transforms[tid]
        supported = sum(1 for m in c.metrics.values() if m.offers(tid))
        transforms.append({
            "id": tid, "short": SHORT[tid], "label": t["label"],
            "summary": t["calculationSummary"], "formula": t["formula"],
            "emits": str(t["emits"]), "nullBehavior": t["nullBehavior"],
            "params": [
                {"name": k, "required": bool(v.get("required")),
                 "default": v.get("defaultValue"), "desc": v["description"]}
                for k, v in (t.get("parameters") or {}).items()
            ],
            "supported": supported,
            "note": t.get("note"),
        })

    metrics = []
    for fam in FAMILY_ORDER:
        for m in sorted((x for x in c.metrics.values() if x.family == fam),
                        key=lambda x: x.metric):
            cells = {}
            for tid in TRANSFORM_ORDER:
                if m.offers(tid):
                    spec = m.transforms[tid]
                    cell = {"s": "legal"}
                    if spec.get("operandRequired"):
                        cell["op"] = True
                    if spec.get("sideRequired"):
                        cell["side"] = True
                    if spec.get("chainSuccessors"):
                        cell["chain"] = spec["chainSuccessors"]
                    if spec.get("chainedRankOrderings"):
                        cell["cro"] = spec["chainedRankOrderings"]
                    if spec.get("rankableSpreadOperands"):
                        cell["rso"] = spec["rankableSpreadOperands"]
                    if tid == "rank":
                        cell["ord"] = list(m.rank_orderings)
                    if tid == "spread":
                        cell["ops"] = list(m.spread_operands)
                    if tid in used_by_platform.get(m.metric, set()):
                        cell["pf"] = True
                    cells[tid] = cell
                elif tid in priv_pairs.get(m.metric, {}):
                    cells[tid] = {"s": "priv", "sec": priv_pairs[m.metric][tid]}
            metrics.append({
                "k": m.metric, "code": m.code, "label": m.label, "fam": m.family,
                "kind": m.native_output["kind"], "unit": m.unit,
                "tf": m.timeframe_mode,
                "range": m.native_output.get("range"),
                "vocab": m.vocab,
                "cells": cells,
                "n": len(m.transforms),
            })

    # classifyState is a 17th transform that exists in the engine but is absent from
    # every metric's authorable whitelist. Carried separately so the 86x16 density
    # figure stays honest, but the privilege story stays visible.
    reserved = {
        "id": "classifyState", "short": "cSta", "label": "State label",
        "summary": "Platform-only. Classify a metric into its canonical state vocabulary.",
        "usedOn": sorted({p["metric"] for p in priv["pairs"]
                          if p["transform"] == "classifyState"}),
        "usedBy": sorted({p["usedBySection"] for p in priv["pairs"]
                          if p["transform"] == "classifyState"}),
    }

    legal = sum(m["n"] for m in metrics)
    payload = {
        "reserved": reserved,
        "transforms": transforms,
        "metrics": metrics,
        "families": [
            {"id": f, "label": cats[f]["label"], "purpose": cats[f]["purpose"],
             "count": sum(1 for m in metrics if m["fam"] == f)}
            for f in FAMILY_ORDER
        ],
        "pools": graph["unitPools"],
        "noSpread": graph["metricsWithoutSpread"],
        "stats": {
            "metrics": len(metrics), "transforms": len(TRANSFORM_ORDER),
            "cells": len(metrics) * len(TRANSFORM_ORDER), "legal": legal,
            "density": round(100 * legal / (len(metrics) * len(TRANSFORM_ORDER)), 1),
            "privilegedPairs": len(set((p["metric"],p["transform"]) for p in priv["pairs"])),
            "privInGrid": sum(1 for m in metrics
                              for v in m["cells"].values() if v["s"] == "priv"),
            "pools": len(graph["unitPools"]),
        },
        "extractedOn": json.loads(
            (CONTRACT_DIR / "_manifest.json").read_text(encoding="utf-8"))["extractedOn"],
    }

    out = ROOT / "scratch_matrix.json"
    out.write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
                   encoding="utf-8")
    print(f"{out}  {out.stat().st_size/1024:.1f} KB")
    print(json.dumps(payload["stats"], indent=2))


if __name__ == "__main__":
    main()
