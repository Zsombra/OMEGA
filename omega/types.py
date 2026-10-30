"""Pydantic models mirroring the BattleGrid MCP JSON Schemas for report authoring.

Field names and enums are kept identical to the wire format so that
`Column.model_dump(exclude_none=True)` is directly submittable.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ABS_TIMEFRAMES = Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "3d", "1w"]
# MEASURED complete, 2026-08-28: the strategy-write schema's timeframe enum carries 13
# values, but the server refuses every anchor outside these four with
# REPORT_TIMEFRAME_NOT_AUTHORABLE, allowedDomain ['5m','15m','1h','4h']
# (anchor_sweep_2026-08-28.json). Column abs timeframes above are a separate,
# read-surface axis and keep all 13.
ANCHOR_TIMEFRAMES = Literal["5m", "15m", "1h", "4h"]
REL = Literal["anchor", "lower", "regime"]
ORDERING = Literal["hi", "lo", "far", "near"]
SIDE = Literal["support", "resistance"]
BARS = Literal["closed", "all"]
# v136 (README "Contract history - v136"): the category scope of an exchange-wide `rank`; the enum is the 144.0.0
# stage schema's (data/contract/stage_strategy_draft/schema_20261029T152942Z.json, columns.items.properties.scope).
SCOPE = Literal["all", "crypto", "l1", "memes", "defi", "tradfi", "stocks", "indices", "commodities"]


class RelTimeframe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rel: REL


class AbsTimeframe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    abs: ABS_TIMEFRAMES


Timeframe = RelTimeframe | AbsTimeframe


class Operand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metric: str


class Column(BaseModel):
    """One custom report column: (metric, transform, timeframe) plus parameters."""
    model_config = ConfigDict(extra="forbid")

    metric: str
    transformId: str = Field(min_length=1, max_length=40)
    timeframe: Timeframe
    chainedTransformId: str | None = Field(default=None, min_length=1, max_length=40)
    # Integer floors only: v103 "The fixed `64` maximums leave strategy authoring ... `window` and `offset` keep their
    # integer floors" - the served budget `columnLookback` judges them (omega.validate).
    window: Annotated[int, Field(ge=1)] | None = None
    offset: Annotated[int, Field(ge=0)] | None = None
    bars: BARS | None = None
    ordering: ORDERING | None = None
    side: SIDE | None = None
    inputs: list[Operand] | None = Field(default=None, max_length=4)
    # v100: "whole basis points of the level, 0-500, default 0 ... declared by levelInteraction only"; the bounds are
    # the 108 schema's (data/derived/condition_vocabulary_108.json reportColumn.bounds.buffer).
    buffer: Annotated[int, Field(ge=0, le=500)] | None = None
    # v142.3: the roster instrument a `relativeTo` column reads its metric against, `BTC` when omitted; the shape is
    # the 144.0.0 stage schema's (minLength 1, maxLength 20, pattern ^[A-Za-z0-9][A-Za-z0-9._:-]*$, "case-insensitive").
    # Refused on every other transform (measured 2026-10-30: "transform 'value' does not accept params.instrument",
    # data/audit/relative_to_probe_144_2026-10-30.json).
    instrument: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    # v136: a `rank` column's category scope, `all` when omitted. Refused off rank ("transform 'value' does not accept
    # params.scope") and on a rank of the report's own coins (measured 2026-10-30 on CROWD_UPBIAS).
    scope: SCOPE | None = None

    def wire(self) -> dict:
        """The exact JSON the connector expects."""
        return self.model_dump(exclude_none=True)


class CustomSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["custom"] = "custom"
    title: str = Field(min_length=1, max_length=60)
    # The 108 schema's coin symbol (v103 holds get_strategy_column_contract's ticker to the same charset).
    benchmarkTicker: str | None = Field(default=None, min_length=1, max_length=20,
                                        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    # No fixed ceiling since v103; the served `sectionColumns` budget judges the count (omega.validate).
    columns: list[Column] = Field(min_length=1)
    # RETIRED at contract 48.0.0 (`remove-section-anchor-override`): "no section can be overridden", and the 108
    # custom-section arm has no `timeframe` (additionalProperties false). Kept so a record written before 48 still
    # loads; omega.validate refuses it (SECTION_TIMEFRAME_RETIRED).
    timeframe: ABS_TIMEFRAMES | None = None
    sectionKey: str | None = None
    # Required by the compile schema since the 2026-08-29 condition-clock deployment
    # (published 2026-08-30): string 1-400 chars or null. The generator always fills
    # a provenance string; null is schema-legal but its acceptance is unmeasured.
    notes: str | None = Field(default=None, min_length=1, max_length=400)

    def wire(self) -> dict:
        d = self.model_dump(exclude_none=True)
        d["columns"] = [c.wire() for c in self.columns]
        # benchmarkTicker and notes are required by the schema even when null
        d.setdefault("benchmarkTicker", None)
        d.setdefault("notes", None)
        return d


class PlatformSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["platform"] = "platform"
    sectionKey: str

    def wire(self) -> dict:
        return self.model_dump()


Section = CustomSection | PlatformSection


class Rule(BaseModel):
    """One signal in the strategy scorecard."""
    model_config = ConfigDict(extra="forbid")

    signalId: str
    allocation: Annotated[int, Field(ge=0, le=3)]
    required: bool
    params: dict | None = None


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor: ANCHOR_TIMEFRAMES = "1h"
    # The 108 REPORT axis bounds no `sections` array; the served `sections` budget judges it (omega.validate).
    sections: list[Section] = Field(default_factory=list)

    def wire(self) -> list[dict]:
        return [s.wire() for s in self.sections]
