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


@lru_cache(maxsize=1)
def stage_schema() -> dict:
    """The input schemas of the six strategy-draft tools at the contract the manifest's
    `writeSurface` names (108.0.0 since 2026-10-11, input AND output schemas: stage/get/commit/
    list strategy drafts, preview_strategy_report and get_strategy; 91.0.0 before, kept as the
    writeSurface's `supersedes`). The path is read from the manifest, never
    hard-coded here, so a re-capture moves one pointer. compile_strategy_plan/ and the
    pre-v84 get_strategy/ records are `retired` in the same manifest - history, not the
    write surface (plan 2026-10-06, Work step 1)."""
    manifest = _load(CONTRACT_DIR / "_manifest.json")
    return _load(ROOT / manifest["writeSurface"]["schema"])


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
    anchor: str | None = None
    """The one ABSOLUTE timeframe this metric accepts, when the platform declares one.

    Published by get_metric_construction_hints from contract 54.1.0 on PDH, PDL and the
    seven pivots (all "1d"). Measured 2026-09-09 on PIVOT_P: relative references
    (rel anchor/lower/regime) are accepted, {abs: "1d"} is accepted, and {abs: "4h"} is
    refused with "metric 'pivotP' is anchored to '1d' - it accepts only that absolute
    timeframe reference". See data/audit/metric_anchor_rule_2026-09-09.json.
    """

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
    # Served at contract 108 and known by NAME only (data/contract/metrics/_unmeasured_108.json): never in `metrics`,
    # so nothing that enumerates the corpus can select one; validate_column refuses them (METRIC_UNMEASURED).
    unmeasured_metrics: dict[str, dict] = field(default_factory=dict)
    # Retired by the platform (data/contract/metrics/_moves_110.json: MACD, PPO, KC_MID at contract 110): never in
    # `metrics`; validate_column refuses one naming what to author instead (METRIC_RETIRED).
    retired_metrics: dict[str, dict] = field(default_factory=dict)
    # Both DERIVED from the write schema's column `transformId` enum (data/derived/condition_vocabulary_108.json),
    # never typed. Retired: extracted at 61.2.0 and no longer served (v100 retired `bandTouch`) - dropped from every
    # Metric.transforms, so omega.space never enumerates one; `transforms` above keeps the extraction's catalogue as
    # extracted. Unmeasured: served, never extracted, and not a platform-privileged transform (v100's
    # `levelInteraction`) - which metrics it composes is unmeasured offline.
    retired_transforms: dict[str, dict] = field(default_factory=dict)
    unmeasured_transforms: dict[str, dict] = field(default_factory=dict)

    # -- lookups -------------------------------------------------------------
    def metric(self, name: str) -> Metric:
        try:
            return self.metrics[name]
        except KeyError:
            raise KeyError(f"unknown metric {name!r}") from None

    def transform_ids(self) -> list[str]:
        return list(self.transforms)

    def _requires(self, transform_id: str, parameter: str) -> bool:
        params = (self.transforms.get(transform_id) or {}).get("parameters") or {}
        return bool((params.get(parameter) or {}).get("required"))

    def requires_operand(self, transform_id: str) -> bool:
        """`authoring.parameters.inputs.required` - where v103 says to read what `operandRequired` restated (that
        flag left the served transform entry; it agrees with this on every 61.2.0 cell)."""
        return self._requires(transform_id, "inputs")

    def requires_side(self, transform_id: str) -> bool:
        """`authoring.parameters.side.required` - where v103 says to read what `sideRequired` restated."""
        return self._requires(transform_id, "side")

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
    privileged_pairs = {(p["metric"], p["transform"]) for p in privileged["pairs"]}
    retired, unmeasured_transforms = _transform_drift(authoring["transforms"], privileged_pairs)

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
            transforms={t["id"]: t for t in rec["transforms"] if t["id"] not in retired},
            spread_operands=tuple(rec.get("spreadOperands", ())),
            rank_orderings=tuple(rec.get("rankOrderings", ())),
            anchor=rec.get("anchor"),
        )

    # The roster size is the platform's to choose, not ours to pin: it went 86 (2026-08-24)
    # -> 135 (09-05) -> 144 (09-09, contract 54.1.0). A literal here made the loader raise
    # the moment the corpus was refreshed. Check the corpus against its OWN index instead,
    # which still catches a half-written or partially-committed refresh.
    expected = _load(CONTRACT_DIR / "metrics" / "_index.json")["metricCount"]
    if len(metrics) != expected:
        raise RuntimeError(
            f"corpus incomplete: {len(metrics)} metric files, _index.json says {expected}")

    unmeasured_path = CONTRACT_DIR / "metrics" / "_unmeasured_108.json"
    unmeasured = _load(unmeasured_path)["metrics"] if unmeasured_path.exists() else {}
    overlap = set(unmeasured) & set(metrics)
    if overlap:
        raise RuntimeError(f"measured AND listed unmeasured: {sorted(overlap)} - drop them from {unmeasured_path.name}")
    moves_path = CONTRACT_DIR / "metrics" / "_moves_110.json"
    moves = _load(moves_path) if moves_path.exists() else {}
    retired_metrics = {name: rec | {"retiredAt": moves["contractVersion"]} for name, rec in moves.get("retired", {}).items()}
    if set(retired_metrics) & set(metrics):
        raise RuntimeError(f"retired AND in the corpus: {sorted(set(retired_metrics) & set(metrics))} - a half-done refresh")
    # v123 renamed eighteen header codes (data/contract/metrics/_moves_123.json). A metric file still carrying its
    # `before` code - a half-applied rename, or a re-extraction that disagrees with the changelog - must not load:
    # every header omega predicts and every clause it derives from those headers would be refused at stage.
    stale = {key: (metrics[key].code, move["since"]) for key, move in header_code_moves().items()
             if key in metrics and metrics[key].code != move["since"]}
    if stale:
        raise RuntimeError(f"v123 header codes not applied (key: corpus code, v123 code): {stale}")

    return Contract(
        metrics=metrics,
        transforms=authoring["transforms"],
        privileged_pairs=privileged_pairs,
        budgets=shared["budgets"],
        rules=rules,
        shared=shared,
        platform_templates={t["sectionKey"]: t for t in templates["templates"]},
        unmeasured_metrics=unmeasured,
        retired_metrics=retired_metrics,
        retired_transforms=retired,
        unmeasured_transforms=unmeasured_transforms,
    )


@lru_cache(maxsize=1)
def header_code_moves() -> dict[str, dict[str, str]]:
    """metric key -> {"before", "since"}: the header codes contract v123 renamed, verbatim from the vendor changelog
    (battlegrid-mcp README "Contract history - v123", recorded in data/contract/metrics/_moves_123.json). Keys do not
    move; only the code a header is built from does."""
    path = CONTRACT_DIR / "metrics" / "_moves_123.json"
    if not path.exists():
        return {}
    return {k: v for k, v in _load(path)["headerCodes"].items() if not k.startswith("_")}


def header_since_123(header: str) -> str:
    """A header rendered before v123, under the codes served since: `CCI_now` -> `CCI20_now`, `dist_donchianHi_4h` ->
    `dist_donchianHi20_4h`, `buyPres_pctB_spread` -> `buyPres_pctB20_spread`. README v123: "Every suffix and prefix
    is kept". A header is `_`-separated tokens and no renamed code holds a `_`, so a code is replaced only as a whole
    token (`donchianHiPrior` never matches `donchianHi`). A header that names no renamed code is returned unchanged.

    For replaying a record captured before 2026-10-20 (a live render, a stored body) - the rename is the changelog's
    rule applied, not a re-measurement."""
    codes = {m["before"]: m["since"] for m in header_code_moves().values()}
    return "_".join(codes.get(token, token) for token in header.split("_"))


def _transform_drift(extracted: dict, privileged_pairs: set[tuple[str, str]]) -> tuple[dict, dict]:
    """(retired, unmeasured) transform ids: the extraction's catalogue against the write schema's served enum, read
    from the derived inventory (omega.condition_vocabulary). With no inventory on disk, neither."""
    path = DERIVED_DIR / "condition_vocabulary_108.json"
    if not path.exists():
        return {}, {}
    vocab = _load(path)
    served = vocab["reportColumn"]["transformId"]
    at = {"servedAt": vocab["source"]["contractVersion"], "enumPointer": served["pointer"],
          "schema": vocab["source"]["schema"]}
    privileged = {t for _, t in privileged_pairs}
    retired = {t: dict(at) for t in extracted if t not in served["enum"]}
    unmeasured = {t: dict(at) for t in served["enum"] if t not in extracted and t not in privileged}
    return retired, unmeasured
