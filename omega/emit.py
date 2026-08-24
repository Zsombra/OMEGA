"""Emit a validated, submit-ready payload to disk.

This module NEVER calls a BattleGrid write tool. It validates, costs, and writes
JSON to `out/`. Submitting it stays a separate, deliberate, human-initiated act.
"""
from __future__ import annotations

import json
from pathlib import Path

from .contract import ROOT, load
from .fanout import cost_report, outputs_for
from .types import CustomSection, Report
from .validate import validate_report

OUT_DIR = ROOT / "out"


class RefusedToEmit(RuntimeError):
    """Raised when a report has validation errors; emitting it would waste a submit."""


def emit(report: Report, name: str, *, out_dir: Path | None = None, force: bool = False) -> Path:
    """Validate, cost, and write the report payload. Returns the written path."""
    c = load()
    result = validate_report(report, contract=c)
    cost = cost_report(report, c)

    if not result.ok and not force:
        raise RefusedToEmit(
            f"{len(result.errors)} validation error(s); refusing to emit.\n{result.report()}"
        )

    target = (out_dir or OUT_DIR)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{name}.json"

    header_map = {}
    for i, section in enumerate(report.sections):
        if isinstance(section, CustomSection):
            for j, col in enumerate(section.columns):
                if col.metric in c.metrics:
                    header_map[f"sections[{i}].columns[{j}]"] = [
                        {"header": o.header, "kind": o.kind,
                         "conditionOperators": o.condition_operators,
                         "conditionVocabulary": list(o.vocabulary)}
                        for o in outputs_for(col, c)
                    ]

    payload = {
        "_generatedBy": "omega.emit - LOCAL ONLY, not submitted",
        "_status": "validated" if result.ok else "FORCED (has errors)",
        "anchor": report.anchor,
        "sections": report.wire(),
        "_predictedOutputs": header_map,
        "_cost": {
            "sections": cost.sections,
            "columns": cost.columns,
            "headers": cost.headers,
            "distinctTimeframes": cost.distinct_timeframes,
            "estimatedTokens": cost.estimated_tokens,
            "withinBudget": cost.ok,
        },
        "_findings": [
            {"severity": f.severity, "code": f.code, "path": f.path, "message": f.message}
            for f in result.findings
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
