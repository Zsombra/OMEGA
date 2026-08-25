"""Load the extracted BattleGrid contract corpus.

The corpus is a dated snapshot of a live system. Everything here is read-only:
nothing in this package ever calls a BattleGrid write tool.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DIR = ROOT / "data" / "contract"
DERIVED_DIR = ROOT / "data" / "derived"


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Metric:
    """One metric's authoring contract."""
    metric: str
    label: str
    code: str
    family: str
    native_output: dict
    output_kind: str
    timeframe_mode: str
    transforms: dict[str, dict]          # transformId -> flags (operandRequired, chainSuccessors, ...)
    spread_operands: tuple[str, ...] = ()
    rank_orderings: tuple[str, ...] = ()

    @property
    def is_timeless(self) -> bool:
        return self.timeframe_mode == "timeless"

    @property
    def unit(self) -> str | None:
        return self.native_output.get("unit")

    @property
    def vocab(self) -> list[str] | None:
        """The labels an `is` / `in` condition may name.

        A boolean-native metric carries no `vocab` in the metric contract - the kind is
        the whole declaration - but the platform's rendered conditionColumns publishes
        `conditionVocabulary: ["true", "false"]` for it, and those two strings are what a
        condition must actually name. Returning None here answered "nothing to gate on"
        for CAPTAIN_CONF and PERP_SPOT_CONFIRMS, both of which are gateable. Confirmed
        live 2026-08-26 in the label sweep.
        """
        if self.native_output.get("kind") == "boolean":
            return list(self.native_output.get("vocab") or ("true", "false"))
        return self.native_output.get("vocab")

    def offers(self, transform_id: str) -> bool:
        return transform_id in self.transforms


@dataclass(frozen=True)
class Contract:
    metrics: dict[str, Metric]
    transforms: dict[str, dict]
    privileged_pairs: set[tuple[str, str]]
    budgets: dict[str, int]
    rules: dict
    shared: dict
    platform_templates: dict[str, dict] = field(default_factory=dict)

    # -- lookups -------------------------------------------------------------
    def metric(self, name: str) -> Metric:
        try:
            return self.metrics[name]
        except KeyError:
            raise KeyError(f"unknown metric {name!r}") from None

    def transform_ids(self) -> list[str]:
        return list(self.transforms)

    def is_privileged(self, metric: str, transform_id: str) -> bool:
        """True when the platform's own templates use this pair but authors cannot."""
        return (metric, transform_id) in self.privileged_pairs

    def resolve_timeframe(self, rel: str, anchor: str) -> str | None:
        return self.rules["timeframeResolution"]["rel"][rel][anchor]


@lru_cache(maxsize=1)
def load() -> Contract:
    """Load and cache the corpus."""
    shared = _load(CONTRACT_DIR / "vocabulary" / "_shared.json")
    authoring = _load(CONTRACT_DIR / "transforms" / "_authoring.json")
    rules = _load(DERIVED_DIR / "composition_rules.json")
    privileged = _load(DERIVED_DIR / "platform_privileged.json")
    templates = _load(CONTRACT_DIR / "templates" / "platform" / "_all.json")

    metrics: dict[str, Metric] = {}
    for path in sorted((CONTRACT_DIR / "metrics").glob("*.json")):
        if path.name.startswith("_"):
            continue
        rec = _load(path)
        metrics[rec["metric"]] = Metric(
            metric=rec["metric"],
            label=rec["label"],
            code=rec["code"],
            family=rec["family"],
            native_output=rec["nativeOutput"],
            output_kind=rec["outputKind"],
            timeframe_mode=rec["timeframeMode"],
            transforms={t["id"]: t for t in rec["transforms"]},
            spread_operands=tuple(rec.get("spreadOperands", ())),
            rank_orderings=tuple(rec.get("rankOrderings", ())),
        )

    if len(metrics) != 86:
        raise RuntimeError(f"corpus incomplete: {len(metrics)} metrics, expected 86")

    return Contract(
        metrics=metrics,
        transforms=authoring["transforms"],
        privileged_pairs={(p["metric"], p["transform"]) for p in privileged["pairs"]},
        budgets=shared["budgets"],
        rules=rules,
        shared=shared,
        platform_templates={t["sectionKey"]: t for t in templates["templates"]},
    )
