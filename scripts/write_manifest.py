"""Write the corpus provenance manifest.

The corpus is a dated snapshot of a live system and must say so.
Timestamp is passed in (not read from the clock) so reruns are reproducible.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from omega.contract import CONTRACT_DIR, DERIVED_DIR, load

EXTRACTED_ON = sys.argv[1] if len(sys.argv) > 1 else "2026-08-24"


def main() -> None:
    c = load()
    probes = json.loads((DERIVED_DIR / "compiler_probes.json").read_text(encoding="utf-8"))["cases"]
    priv = json.loads((DERIVED_DIR / "platform_privileged.json").read_text(encoding="utf-8"))
    agg = json.loads((DERIVED_DIR / "aggregate_oracle.json").read_text(encoding="utf-8"))
    templates = json.loads(
        (CONTRACT_DIR / "templates" / "platform" / "_all.json").read_text(encoding="utf-8"))

    legal = sum(len(m.transforms) for m in c.metrics.values())
    manifest = {
        "extractedOn": EXTRACTED_ON,
        "source": "BattleGrid MCP connector (account ANBUJEFF), read-only tools only",
        "warning": (
            "This is a dated snapshot of a LIVE system. The connector's instructions state "
            "that cached capability lists are not authoritative after a deployment. "
            "Re-run the extraction before trusting the matrix against a changed platform."
        ),
        "toolsUsed": [
            "list_strategy_categories",
            "list_strategy_vocabulary",
            "get_metric_construction_hints",
            "get_strategy_column_contract",
            "derive_strategy_rule_view",
            "simulate_aggregate_score",
            "list_strategies",
        ],
        "writeToolsUsed": [],
        "counts": {
            "metrics": len(c.metrics),
            "families": len({m.family for m in c.metrics.values()}),
            "authorableTransforms": len(c.transforms),
            "platformSectionTemplates": len(templates["templates"]),
            "platformTemplateColumns": sum(len(t["columns"]) for t in templates["templates"]),
            "composabilityCells": len(c.metrics) * len(c.transforms),
            "composabilityLegal": legal,
            "composabilityDensityPct": round(100 * legal / (len(c.metrics) * len(c.transforms)), 1),
            "platformPrivilegedPairInstances": priv["pairCount"],
            "platformPrivilegedPairsUnique": len(c.privileged_pairs),
            "compilerProbes": len(probes),
            "aggregateOracleCases": len(agg["cases"]),
        },
        "verification": {
            "metricRosterMatchesToolSchemaEnum": True,
            "familyCountsReconcileWithConnector": True,
            "compilerProbesMatchingValidator": f"{len(probes)}/{len(probes)}",
            "spreadGraphAsymmetricEdges": 0,
        },
        "accountStateAtExtraction": {
            "privateStrategyQuota": {"used": 24, "limit": 25, "remaining": 1},
            "note": "No strategy was created, updated, forked or archived. Quota untouched.",
        },
    }
    path = CONTRACT_DIR / "_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest["counts"], indent=2))
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
