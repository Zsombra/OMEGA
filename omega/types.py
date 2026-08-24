"""Pydantic models mirroring the BattleGrid MCP JSON Schemas for report authoring.

Field names and enums are kept identical to the wire format so that
`Column.model_dump(exclude_none=True)` is directly submittable.
"""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

ABS_TIMEFRAMES = Literal["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "8h", "12h", "1d", "3d", "1w"]
ANCHOR_TIMEFRAMES = Literal["5m", "15m", "1h", "4h"]
REL = Literal["anchor", "lower", "regime"]
ORDERING = Literal["hi", "lo", "far", "near"]
SIDE = Literal["support", "resistance"]
BARS = Literal["closed", "all"]


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
    window: Annotated[int, Field(ge=1, le=64)] | None = None
    offset: Annotated[int, Field(ge=0, le=64)] | None = None
    bars: BARS | None = None
    ordering: ORDERING | None = None
    side: SIDE | None = None
    inputs: list[Operand] | None = Field(default=None, max_length=4)

    def wire(self) -> dict:
        """The exact JSON the connector expects."""
        return self.model_dump(exclude_none=True)


class CustomSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["custom"] = "custom"
    title: str = Field(min_length=1, max_length=60)
    benchmarkTicker: str | None = None
    columns: list[Column] = Field(min_length=1, max_length=64)
    timeframe: ABS_TIMEFRAMES | None = None
    sectionKey: str | None = None

    def wire(self) -> dict:
        d = self.model_dump(exclude_none=True)
        d["columns"] = [c.wire() for c in self.columns]
        # benchmarkTicker is required by the schema even when null
        d.setdefault("benchmarkTicker", None)
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
    sections: list[Section] = Field(default_factory=list, max_length=64)

    def wire(self) -> list[dict]:
        return [s.wire() for s in self.sections]
