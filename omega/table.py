"""One command over the column loop: explore, explain, author.

    python -m omega.table explore --family volumeFlow --max-headers 1
    python -m omega.table explain EMA5 spread:EMA13 --chain trajectory --window 4
    python -m omega.table author  EMA5 spread:EMA13 --chain trajectory --out out/

Each verb is a thin shell. `explore` is omega.space, `explain` is omega.explain,
`author` is validate -> fanout -> emit. This module owns argument parsing and
printing; it holds no rules of its own.

NO SILENT CAPS
--------------
`explore` truncates long result sets, and always says how many it dropped. A
capped list that reads as a complete one is the same failure as a guessed number.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .contract import DERIVED_DIR, load
from .explain import explain, render_text
from .fanout import outputs_for
from .space import ColumnShape, header_cost, platform_used, query
from .types import Column, CustomSection, Operand, RelTimeframe, Report
from .validate import validate_report


def parse_spec(metric: str, transform: str, *, chain: str | None = None,
               window: int | None = None, offset: int | None = None,
               bars: str | None = None, ordering: str | None = None,
               side: str | None = None, rel: str = "anchor") -> Column:
    """Build a Column from the CLI's mini-language.

    `transform` may carry an operand after a colon: `spread:EMA13`.
    """
    contract = load()
    if metric not in contract.metrics:
        sys.exit(f"unknown metric {metric!r} - see `explore` for the {len(contract.metrics)} available")

    tid, _, operand = transform.partition(":")
    if tid not in contract.transforms:
        sys.exit(f"unknown transform {tid!r} - one of {', '.join(contract.transform_ids())}")

    return Column(
        metric=metric, transformId=tid, timeframe=RelTimeframe(rel=rel),
        chainedTransformId=chain, window=window, offset=offset, bars=bars,
        ordering=ordering, side=side,
        inputs=[Operand(metric=operand)] if operand else None,
    )


def _cmd_explore(a: argparse.Namespace) -> int:
    c = load()
    shapes = query(family=a.family, transform=a.transform, unit=a.unit,
                   chained=a.chained, max_headers=a.max_headers,
                   platform_uses=(False if a.unused else None), contract=c)
    total = len(shapes)
    banner = f"{total} shapes"
    if a.unused:
        banner += ", never used by a platform template"
    print(banner)
    print()
    shown = shapes[:a.limit]
    for s in shown:
        chain = f" -> {s.chained}" if s.chained else ""
        operand = f" ({s.operand})" if s.operand else ""
        cost = header_cost(s, contract=c)
        fam = c.metrics[s.metric].family
        print(f"  {s.metric:<20}{s.transform + chain + operand:<34}{fam:<13}{cost} header(s)")
    if total > len(shown):
        print()
        print(f"  showing {len(shown)} of {total} - raise --limit to see the rest")
    return 0


def _cmd_explain(a: argparse.Namespace) -> int:
    col = parse_spec(a.metric, a.transform, chain=a.chain, window=a.window,
                     offset=a.offset, bars=a.bars, ordering=a.ordering,
                     side=a.side, rel=a.rel)
    print(render_text(explain(col)))
    return 0


def _cmd_author(a: argparse.Namespace) -> int:
    col = parse_spec(a.metric, a.transform, chain=a.chain, window=a.window,
                     offset=a.offset, bars=a.bars, ordering=a.ordering,
                     side=a.side, rel=a.rel)
    section = CustomSection(kind="custom", title=a.title,
                            benchmarkTicker=None, columns=[col])
    report = Report(anchor=a.anchor, sections=[section])

    findings = validate_report(report).findings
    errors = [f for f in findings if f.severity == "error"]
    for f in findings:
        print(f"  {f}")
    if errors:
        print()
        print(f"REFUSED: {len(errors)} error(s). Nothing was written.")
        return 1

    outs = outputs_for(col)
    print(f"legal. {len(outs)} header(s): {', '.join(o.header for o in outs)}")
    if a.out:
        from .emit import emit
        path = emit(report, a.title.replace(" ", "-").lower(),
                    out_dir=Path(a.out), force=True)
        print(f"wrote {path}")
        print("This is a submit-ready payload. Submitting stays a separate, human act.")
    return 0


def _cmd_families(a: argparse.Namespace) -> int:
    """Browse the indicator census - what named families this platform can build.

    The census lives in data/derived/indicator_families.json and is checked by
    tests/test_indicator_families.py, which builds every buildable entry. So this
    is a report on verified constructions, not a wish list.
    """
    import json
    data = json.loads((DERIVED_DIR / "indicator_families.json").read_text(encoding="utf-8"))

    if a.blocked:
        rows = data["blocked"]
        if a.cause:
            rows = [f for f in rows if f["cause"] == a.cause]
        by_cause: dict[str, list] = {}
        for f in rows:
            by_cause.setdefault(f["cause"], []).append(f)
        print(f"{len(rows)} blocked families")
        for cause in ("operator-absent", "guard-refuses", "needs-state", "data-absent"):
            group = by_cause.get(cause)
            if not group:
                continue
            print()
            print(f"  {cause}  ({len(group)})")
            for f in group:
                needs = f" needs {f['needs']}" if f.get("needs") else ""
                print(f"    {f['name']}{needs}")
        return 0

    rows = data["buildable"]
    if a.domain:
        rows = [f for f in rows if f["domain"] == a.domain]
    if not rows:
        domains = sorted({f["domain"] for f in data["buildable"]})
        sys.exit(f"no families in domain {a.domain!r} - one of {', '.join(domains)}")

    print(f"{len(rows)} buildable families"
          + (f" in {a.domain}" if a.domain else ""))
    for f in rows:
        attr = f"  [{f['attribution']}]" if f.get("attribution") else ""
        print()
        print(f"  {f['name']}{attr}")
        for spec in f["columns"]:
            bits = [spec["metric"], spec["transformId"]]
            if spec.get("inputs"):
                bits.append("(" + ", ".join(i["metric"] for i in spec["inputs"]) + ")")
            if spec.get("chainedTransformId"):
                bits.append("-> " + spec["chainedTransformId"])
            for k in ("window", "offset", "ordering", "side", "bars"):
                if spec.get(k) is not None:
                    bits.append(f"{k}={spec[k]}")
            print("      " + " ".join(bits))
        if f.get("note"):
            print(f"      note: {f['note']}")
    return 0


def _add_column_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("metric")
    p.add_argument("transform", help="transformId, optionally transform:OPERAND")
    p.add_argument("--chain", help="chained transform id")
    p.add_argument("--window", type=int)
    p.add_argument("--offset", type=int)
    p.add_argument("--bars", choices=["closed", "all"])
    p.add_argument("--ordering", choices=["hi", "lo", "far", "near"])
    p.add_argument("--side", choices=["support", "resistance"])
    p.add_argument("--rel", choices=["anchor", "lower", "regime"], default="anchor")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omega.table", description="explore, explain and author BattleGrid columns")
    sub = parser.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("explore", help="browse the design space")
    e.add_argument("--family")
    e.add_argument("--transform")
    e.add_argument("--unit")
    e.add_argument("--chained", type=lambda v: v.lower() == "true")
    e.add_argument("--max-headers", type=int, dest="max_headers")
    e.add_argument("--unused", action="store_true",
                   help="only shapes no platform template uses")
    e.add_argument("--limit", type=int, default=40)
    e.set_defaults(fn=_cmd_explore)

    x = sub.add_parser("explain", help="what does this column compute, and what did it produce")
    _add_column_args(x)
    x.set_defaults(fn=_cmd_explain)

    w = sub.add_parser("author", help="validate a column and emit a submit-ready payload")
    _add_column_args(w)
    w.add_argument("--out", help="directory to write the payload into")
    w.add_argument("--title", default="omega column")
    w.add_argument("--anchor", default="1h",
                   choices=["5m", "15m", "1h", "4h"])
    w.set_defaults(fn=_cmd_author)

    f = sub.add_parser("families", help="browse the indicator census")
    f.add_argument("--domain", help="classical, oscillator, factor, microstructure, "
                                    "derivatives, statistical, structure, sentiment, institutional")
    f.add_argument("--blocked", action="store_true", help="show what cannot be built, and why")
    f.add_argument("--cause", choices=["operator-absent", "guard-refuses",
                                       "needs-state", "data-absent"])
    f.set_defaults(fn=_cmd_families)

    a = parser.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(main())
