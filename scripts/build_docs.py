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
    "value", "trajectory", "distance", "spread", "efficiency", "aggregate",
    "maxShare", "rank", "classifyZone", "crossDetect", "bandTouch",
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
        "86 metrics across 10 families. A metric is a **named quantity the platform already",
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


def transform_layer(c) -> str:
    graph = json.loads((DERIVED_DIR / "spread_operand_graph.json").read_text(encoding="utf-8"))
    priv = json.loads((DERIVED_DIR / "platform_privileged.json").read_text(encoding="utf-8"))

    support: dict[str, list[str]] = defaultdict(list)
    for m in c.metrics.values():
        for tid in m.transforms:
            support[tid].append(m.metric)

    out = [
        "# 02 · The Transform Layer",
        "",
        "*Generated from `data/contract/transforms/_authoring.json` — do not hand-edit.*",
        "",
        "A transform is **how you read** a metric. There are 16 authorable transforms.",
        "Crucially the metric×transform matrix is a **sparse partial function**, not a grid:",
        f"only **{sum(len(v) for v in support.values())} of {len(c.metrics)}×16 = {len(c.metrics)*16}** cells are legal",
        f"(**{100*sum(len(v) for v in support.values())/(len(c.metrics)*16):.1f}%** density).",
        "",
        "## Reference",
        "",
    ]
    for tid in TRANSFORM_ORDER:
        t = c.transforms[tid]
        out += [
            f"### `{tid}` — {t['label']}",
            "",
            f"{t['calculationSummary']}",
            "",
            "```",
            f"{t['formula']}",
            "```",
            "",
            f"- **Supported on:** {len(support[tid])} metric(s)",
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
