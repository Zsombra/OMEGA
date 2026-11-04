"""Generate the metric- and transform-layer reference docs directly from the corpus.

Anything derivable is generated, so the tables cannot drift from the extracted data.
Conceptual docs (00, 03, 04, 05, 06) are hand-written.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from omega.contract import CONTRACT_DIR, DERIVED_DIR, ROOT, load

DOCS = ROOT / "docs"
TRANSFORM_ORDER = [
    "value", "trajectory", "distance", "spread", "relativeTo", "efficiency", "aggregate",
    "zscore", "stddev", "linregSlope", "pctl", "rollingMin", "rollingMax", "maxShare", "rank", "classifyZone", "crossDetect", "levelInteraction", "bandTouch",
    "count", "nearestZoneType", "nearestZoneRange", "nearestZoneDist", "nearestZoneAge",
]
FAMILY_ORDER = ["price", "momentum", "trend", "volatility", "volumeFlow",
                "derivatives", "structure", "regime", "crowd", "derived"]


def metric_layer(c) -> str:
    cats = {x["category"]: x for x in
            json.loads((CONTRACT_DIR / "categories.json").read_text(encoding="utf-8"))["categories"]}
    by_family: dict[str, list] = defaultdict(list)
    for m in c.metrics.values():
        by_family[m.family].append(m)

    out = [
        "# 01 · The Metric Layer",
        "",
        "*Generated from `data/contract/metrics/` — do not hand-edit.*",
        "",
        f"{len(c.metrics)} metrics across {len({m.family for m in c.metrics.values()})} families. "
        "A metric is a **named quantity the platform already",
        "computes**; you never define the maths, you select the quantity and then choose how",
        "to read it. Four fields govern everything you can do with one:",
        "",
        "| Field | What it decides |",
        "|---|---|",
        "| `nativeOutput.kind` | which condition operators the compiled column accepts |",
        "| `nativeOutput.unit` | which other metrics it may `spread` against |",
        "| `timeframeMode` | whether it resolves on the candle grid (`candle`) or is a bundle read (`timeless`) |",
        "| `transforms[]` | the *only* transforms the engine can execute for it |",
        "",
    ]
    for fam in FAMILY_ORDER:
        cat = cats[fam]
        metrics = sorted(by_family[fam], key=lambda m: m.metric)
        out += [
            f"## {cat['label']} — `{fam}` ({len(metrics)})",
            "",
            f"> {cat['purpose']}",
            "",
            "**Common misuses (platform's own words):**",
            "",
        ]
        out += [f"- {x}" for x in cat["commonMisuses"]]
        out += [
            "",
            "| Metric | `code` | Kind / unit | TF mode | Transforms |",
            "|---|---|---|---|---|",
        ]
        for m in metrics:
            kind = m.native_output["kind"]
            unit = m.unit or ""
            rng = m.native_output.get("range")
            if rng:
                lo, hi = rng.get("min", ""), rng.get("max", "")
                unit += f" [{lo}–{hi}]" if hi != "" else f" [≥{lo}]"
            vocab = m.vocab
            if vocab:
                unit = "·".join(vocab[:3]) + ("…" if len(vocab) > 3 else "")
            tfs = ", ".join(t for t in TRANSFORM_ORDER if m.offers(t))
            out.append(f"| `{m.metric}` | `{m.code}` | {kind} / {unit} | {m.timeframe_mode} | {tfs} |")
        out.append("")
    return "\n".join(out)


def _extracted_offers(tid: str):
    """The metric records of the extraction that list `tid` (a retired transform leaves Metric.transforms)."""
    for path in sorted((CONTRACT_DIR / "metrics").glob("*.json")):
        if path.name.startswith("_"):
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        if any(t["id"] == tid for t in rec["transforms"]):
            yield rec["metric"]


def transform_layer(c) -> str:
    graph = json.loads((DERIVED_DIR / "spread_operand_graph.json").read_text(encoding="utf-8"))
    priv = json.loads((DERIVED_DIR / "platform_privileged.json").read_text(encoding="utf-8"))

    support: dict[str, list[str]] = defaultdict(list)
    for m in c.metrics.values():
        for tid in m.transforms:
            support[tid].append(m.metric)

    live = [tid for tid in TRANSFORM_ORDER if tid not in c.retired_transforms]
    cells = sum(len(v) for v in support.values())
    out = [
        "# 02 · The Transform Layer",
        "",
        "*Generated from `data/contract/transforms/_authoring.json` — do not hand-edit.*",
        "",
        f"A transform is **how you read** a metric. There are {len(live)} authorable transforms omega has extracted.",
        "Crucially the metric×transform matrix is a **sparse partial function**, not a grid:",
        f"only **{cells} of {len(c.metrics)}×{len(live)} = {len(c.metrics)*len(live)}** cells are legal",
        f"(**{100*cells/(len(c.metrics)*len(live)):.1f}%** density).",
        "",
    ]
    if c.retired_transforms or c.unmeasured_transforms:
        rec = next(iter({**c.retired_transforms, **c.unmeasured_transforms}.values()))
        out += [
            f"Against the column `transformId` enum the contract {rec['servedAt']} write schema serves "
            f"(`{rec['schema']}`):",
            "",
        ]
        for tid in c.retired_transforms:
            out.append(f"- **`{tid}` is retired** — extracted, no longer served; it is dropped from every metric's transforms in doc 01 and "
                       f"here, and `omega.validate` refuses it (`TRANSFORM_RETIRED`). Its reference entry is kept "
                       f"as history.")
        for tid in c.unmeasured_transforms:
            out.append(f"- **`{tid}` is served and unmeasured** — never extracted, so it has no entry here; "
                       f"`omega.validate` refuses it (`TRANSFORM_UNMEASURED`) until its column contract is read.")
        out.append("")
    out += [
        "## Reference",
        "",
    ]
    for tid in TRANSFORM_ORDER:
        t = c.transforms[tid]
        retired = tid in c.retired_transforms
        out += [
            f"### `{tid}` — {t['label']}" + (" (RETIRED)" if retired else ""),
            "",
            f"{t['calculationSummary']}",
            "",
            "```",
            f"{t['formula']}",
            "```",
            "",
            (f"- **Retired** at contract {c.retired_transforms[tid]['servedAt']}: not in the served enum; the "
             f"61.2.0 extraction offered it on {sum(1 for r in _extracted_offers(tid))} metric(s)"
             if retired else f"- **Supported on:** {len(support[tid])} metric(s)"),
            f"- **Emits:** {t['emits']}" + (f" — {t['emitsNote']}" if "emitsNote" in t else ""),
            f"- **Null behaviour:** {t['nullBehavior']}",
        ]
        params = t.get("parameters") or {}
        if params:
            out.append("- **Parameters:**")
            for pname, p in params.items():
                req = "required" if p.get("required") else f"optional, default `{p.get('defaultValue')}`"
                out.append(f"  - `{pname}` ({req}) — {p['description']}")
        else:
            out.append("- **Parameters:** none")
        if "chainSuccessorsWhenCandle" in t:
            out.append(f"- **Chains into:** {t['chainSuccessorsWhenCandle']} (candle-backed metrics only)")
        if "note" in t:
            out.append(f"- **Note:** {t['note']}")
        if "range" in t:
            out.append(f"- **Output range:** {t['range']}")
        out.append("")

    out += [
        "## Spread operand pools",
        "",
        "`spread` is unit-typed. A metric may only spread against operands sharing its",
        "`nativeOutput.unit`, and never against itself. Every pool is fully symmetric",
        f"({len(graph['asymmetricEdges'])} asymmetric edges across the whole graph).",
        "",
        "| Unit | Size | Members |",
        "|---|---|---|",
    ]
    for unit, members in graph["unitPools"].items():
        out.append(f"| `{unit}` | {len(members)} | {', '.join(f'`{m}`' for m in members)} |")
    out += [
        "",
        f"`RVOL` (unit `ratio`) is the lone numeric metric with **no** spread transform at all —",
        "its pool would have exactly one member.",
        "",
        f"{len(graph['metricsWithoutSpread'])} metrics offer no `spread`: mostly classifications,",
        "booleans, events and the entity set.",
        "",
        "## Platform-privileged pairs",
        "",
        "The platform's own section templates use pairs that **authors cannot**. Requesting one",
        "returns `REPORT_COLUMN_PAIR_UNSUPPORTED`.",
        "",
        "| Metric | Transform | Used by | Authorable substitute |",
        "|---|---|---|---|",
    ]
    seen = set()
    for p in priv["pairs"]:
        key = (p["metric"], p["transform"])
        if key in seen:
            continue
        seen.add(key)
        sub = "`classifyZone`" if "classifyZone" in p["authorableAlternatives"] else "—"
        out.append(f"| `{p['metric']}` | `{p['transform']}` | `{p['usedBySection']}` | {sub} |")
    out += [
        "",
        "`CCI20 × classifyZone` is the subtle one: `classifyZone` classifies a *bounded*",
        "oscillator, and `CCI20`'s `nativeOutput` carries no `range`. No canonical bounds,",
        "no zone policy exposed to authors — though the platform reserves one for itself.",
        "",
        "`bandTouch` is the mirror case: fully authorable, used by **zero** platform templates.",
        "",
    ]
    return "\n".join(out)


def main() -> None:
    c = load()
    DOCS.mkdir(exist_ok=True)
    (DOCS / "01-metric-layer.md").write_text(metric_layer(c), encoding="utf-8")
    (DOCS / "02-transform-layer.md").write_text(transform_layer(c), encoding="utf-8")
    print("wrote docs/01-metric-layer.md")
    print("wrote docs/02-transform-layer.md")


if __name__ == "__main__":
    main()
