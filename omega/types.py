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
# Contract 146.0.0 (2026-11-01, undocumented in the vendor README): a custom section's `marketScope`, REQUIRED (null
# allowed); the enum is the 146.0.0 stage schema's (data/contract/stage_strategy_draft/schema_20261101T061733Z.json,
# axes.REPORT.sections.items.oneOf[1].properties.marketScope) - the same nine category names as SCOPE.
MARKET_SCOPE = Literal["all", "crypto", "l1", "memes", "defi", "tradfi", "stocks", "indices", "commodities"]


# The column fields that are a METRIC's knobs (served per metric in the hint's `parameters`), as opposed to the
# transform's own (`window`, `offset`, `bars`, ...). The 148.1.0 six and the 149.0.0 thirteen.
KNOBS = ("leftBars", "rightBars", "swingLength", "confluenceFilter", "equalBars", "equalThreshold", "period", "fast",
         "slow", "signal", "kSmoothing", "dSmoothing", "rsiPeriod", "atrPeriod", "stdDev", "multiplier",
         "accelerationStart", "accelerationIncrement", "accelerationMaximum",
         # 161.0.0 (2026-11-09, undocumented): Ichimoku's four lengths, served on the five ICHI_* metrics
         "conversionPeriod", "basePeriod", "spanBPeriod", "displacement",
         # 168 (2026-11-11, undocumented; extraction 20261111 at 168.3.0): the prior-session supply / demand zones' two
         # settings (24 PRIOR_*_DEMAND_* / PRIOR_*_SUPPLY_* levels) and the structure zones' flag (STRUCT_ZONES, ZONE_*)
         "supplyDemandThreshold", "supplyDemandResolution", "usedUpOnClose")


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


# A number knob is a finite float: NaN passed every bound comparison and crashed the step check, and `wire()` would send
# `nan`, which is not JSON; inf predicted the header `sdinf` (review 2026-11-08).
Finite = Annotated[float, Field(allow_inf_nan=False)]


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
    # 161.0.0 (2026-11-09, undocumented; measured data/audit/authoring_probe_161_2026-11-09.json): the touch distance
    # as a multiple of ATR, levelInteraction's alternative to `buffer` - "accepts params.buffer or params.touchAtr,
    # never both"; served minimum 0.1 and step 0.1, the maximum per metric (on a chained levelInteraction the served
    # chain-outer one; both 2, measured 2026-11-11). Header token `_a<value>` (bbUpper20_lvl_a0.5).
    # The schema's own column `buffer` maximum rose to 2^53-1 at 161, but levelInteraction still serves 0 - 500 and
    # refuses 501 (measured), so the bound above stays.
    touchAtr: Finite | None = None
    # 161.0.0: the OUTER window of a chain whose inner is a rolling transform (aggregate / ema / rma / wma / rsi / cci /
    # roc), which keeps `window` for itself - the served chainedOuters.<outer>.windowParameter names which field the
    # outer reads ("window" after spread / distance / relativeTo, "chainedWindow" after a rolling inner); refused on any
    # other chain ("transform 'spread' -> 'ema' does not accept params.chainedWindow", measured).
    chainedWindow: Annotated[int, Field(ge=1)] | None = None
    # v142.3: the roster instrument a `relativeTo` column reads its metric against, `BTC` when omitted; the shape is
    # the 144.0.0 stage schema's (minLength 1, maxLength 20, pattern ^[A-Za-z0-9][A-Za-z0-9._:-]*$, "case-insensitive").
    # Refused on every other transform (measured 2026-10-30: "transform 'value' does not accept params.instrument",
    # data/audit/relative_to_probe_144_2026-10-30.json).
    instrument: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    # v136: a `rank` column's category scope, `all` when omitted. Refused off rank ("transform 'value' does not accept
    # params.scope") and on a rank of the report's own coins (measured 2026-10-30 on CROWD_UPBIAS).
    scope: SCOPE | None = None
    # The nineteen per-metric knobs of contract 148.1.0 (v146.5 / .8: the swing, structure and equal-pivot six) and
    # 149.0.0 (the thirteen indicator settings). The stage schema bounds the integer ones at >= 1 (`$defs/barCount`)
    # and the number ones not at all; each metric serves its own knobs with their default, minimum, maximum, step and
    # bound (get_metric_construction_hints `parameters`, data/contract/metrics/<METRIC>.json), and omega.validate
    # judges a column against that. Types are the schema's (data/derived/condition_vocabulary_108.json reportColumn.types);
    # a non-integer bar count is a schema VALIDATION_ERROR on the platform ("expected int, received number", measured
    # 2026-11-07 at 149.1.0) and a pydantic error here.
    leftBars: Annotated[int, Field(ge=1)] | None = None
    rightBars: Annotated[int, Field(ge=1)] | None = None
    swingLength: Annotated[int, Field(ge=1)] | None = None
    confluenceFilter: bool | None = None
    equalBars: Annotated[int, Field(ge=1)] | None = None
    equalThreshold: Finite | None = None
    period: Annotated[int, Field(ge=1)] | None = None
    fast: Annotated[int, Field(ge=1)] | None = None
    slow: Annotated[int, Field(ge=1)] | None = None
    signal: Annotated[int, Field(ge=1)] | None = None
    kSmoothing: Annotated[int, Field(ge=1)] | None = None
    dSmoothing: Annotated[int, Field(ge=1)] | None = None
    rsiPeriod: Annotated[int, Field(ge=1)] | None = None
    atrPeriod: Annotated[int, Field(ge=1)] | None = None
    stdDev: Finite | None = None
    multiplier: Finite | None = None
    accelerationStart: Finite | None = None
    accelerationIncrement: Finite | None = None
    accelerationMaximum: Finite | None = None
    conversionPeriod: Annotated[int, Field(ge=1)] | None = None
    basePeriod: Annotated[int, Field(ge=1)] | None = None
    spanBPeriod: Annotated[int, Field(ge=1)] | None = None
    displacement: Annotated[int, Field(ge=1)] | None = None
    # 168: the write schema types the first two `number` (no bound of its own) and the third `boolean`; each metric
    # serves the range (threshold 0 - 100 step 0.5, resolution 2 - 500 step 1) and omega.validate judges against that.
    # Their header spelling was rendered the same day (omega.fanout KNOB_JOINED, KNOB_SINGLE: _vt10.5, _res51, _close).
    supplyDemandThreshold: Finite | None = None
    supplyDemandResolution: Finite | None = None
    usedUpOnClose: bool | None = None

    def knobs(self) -> dict:
        """The metric knobs this column sets (explicit defaults included), in field order."""
        return {k: getattr(self, k) for k in KNOBS if getattr(self, k) is not None}

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
    # REQUIRED by the 146.0.0 stage schema (2026-11-01; `'marketScope' is a required property` without it, so every
    # plan failed battlegrid-manager's preflight from 06:12Z). null = a PER-COIN section, the shape every section
    # OMEGA builds has always had (probed live 2026-11-01T07:58Z with the manager's panel request: accepted, one
    # rendered section). A named scope makes a MARKET section, which refuses per-coin metrics - the live refusal:
    # "a market section cannot carry this column — metric 'PRIOR_TPO_POC' is not read on a market section's bars" -
    # so a named scope is only for a section built from the v146 market metrics (MKT_*, CROWD_*_Z), none of which
    # OMEGA has extracted yet. wire() always emits the key.
    marketScope: MARKET_SCOPE | None = None
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
        # benchmarkTicker, marketScope (146.0.0) and notes are required by the schema even when null
        d.setdefault("benchmarkTicker", None)
        d.setdefault("marketScope", None)
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
