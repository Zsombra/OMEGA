"""Compose a complete, validated strategy from a thesis.

Everything below composes the rest of the toolkit: columns come from recipes that are
legal by construction (validate.py), sections respect the timeframe-inert rule
(04), allocations only go to signals the report can actually feed (membership.py),
and the gate is checked against the aggregation math (aggregate.py).

Shape mirrors real strategies read back from the connector (EL_ALAMEIN, MATH-C3):
a dense 84-entry scorecard where unused signals sit at allocation 0, and
`minAggregateScore` as the routing gate.

Emits to disk. Never submits.
"""
from __future__ import annotations

import copy
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

import uuid

from .aggregate import Signal, aggregate
from .conditions import (
    all_of, ambient_headers, close_on, condition, crowd_leaning_down, crowd_leaning_up, is_,
    market_read_text, n_of, num, ref, stables_at_par, tape_bearish, tape_bullish,
    entry_gates, validate_conditions, validate_entry_gate, validate_market_read,
)
from .contract import DERIVED_DIR, load
from .fanout import cost_report, outputs_for
from .membership import (RUNG_REL, _map, _signal_data, analyse, check_allocations,
                         predicted_diagnostics, shown_data, signals_for)
from .types import Column, CustomSection, Report, Rule
from .validate import validate_report

# The v91 REPORT axis: a custom section's optional `sectionKey` must match this pattern
# (schema_20261005T194629Z.json, REPORT.sections.items.anyOf[1].properties.sectionKey). A
# clause's `column.sectionKey` is any string of 1..120 characters or null - no enum - so the
# platform keys the server derives ("reference-pairs", "market-breadth", ...) and the minted
# "custom:<uuid>" keys are all admissible there.
CUSTOM_SECTION_KEY = re.compile(r"^custom:[0-9a-fA-F-]{36}$")
CLAUSE_SECTION_KEY_MAX_LENGTH = 120
# What makes two wire columns "the same column" for carrying a section key: the Column
# docstring's identity triple plus the chained transform. The parameters (window, offset,
# bars, ordering, side, inputs) may move without the header changing section.
_COLUMN_IDENTITY = ("metric", "transformId", "chainedTransformId", "timeframe")

# --- column recipes -------------------------------------------------------
# One entry per signal module: the columns that both FEED the module and give the
# agent something worth reading. Every column here is validated in tests.
MODULE_RECIPES: dict[str, list[dict]] = {
    "RSI": [
        {"metric": "RSI14", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4, "bars": "closed"},
        {"metric": "RSI14", "transformId": "classifyZone", "timeframe": {"rel": "anchor"}},
    ],
    "MACD": [
        {"metric": "MACD", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4, "bars": "closed"},
        {"metric": "MACD", "transformId": "crossDetect", "timeframe": {"rel": "anchor"}},
    ],
    "STOCHASTIC": [
        {"metric": "STOCH_K", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 3, "bars": "closed"},
        {"metric": "STOCH_K", "transformId": "classifyZone", "timeframe": {"rel": "anchor"}},
        {"metric": "STOCH_D", "transformId": "value", "timeframe": {"rel": "anchor"}},
    ],
    "VOLUME": [
        {"metric": "RVOL", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4, "bars": "closed"},
        {"metric": "OBV", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4, "bars": "closed"},
    ],
    "VOLATILITY": [
        {"metric": "ATR_PCT", "transformId": "value", "timeframe": {"rel": "anchor"}},
        {"metric": "ATR", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4, "bars": "closed"},
    ],
    "BOLLINGER": [
        {"metric": "BB_PCT_B", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4, "bars": "closed"},
        {"metric": "BB_WIDTH_PCT", "transformId": "value", "timeframe": {"rel": "anchor"}},
        {"metric": "BB_TOUCH", "transformId": "value", "timeframe": {"rel": "anchor"}},
    ],
    "MOVING_AVERAGES": [
        {"metric": "MA_ALIGN", "transformId": "value", "timeframe": {"rel": "anchor"}},
        {"metric": "EMA5", "transformId": "spread", "chainedTransformId": "trajectory",
         "timeframe": {"rel": "anchor"}, "inputs": [{"metric": "EMA13"}], "window": 4},
        {"metric": "SMA200", "transformId": "distance", "timeframe": {"rel": "anchor"}},
    ],
    "TREND_STRENGTH": [
        {"metric": "ADX", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4, "bars": "closed"},
    ],
    "MFI": [
        {"metric": "MFI14", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4, "bars": "closed"},
        {"metric": "MFI14", "transformId": "classifyZone", "timeframe": {"rel": "anchor"}},
    ],
    "RELATIVE_STRENGTH": [
        {"metric": "PPO", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4, "bars": "closed"},
        {"metric": "ROC12", "transformId": "crossDetect", "timeframe": {"rel": "anchor"}},
    ],
    "SUPPORT_RESISTANCE": [
        # 2026-09-09 (rename landed at contract 53.0.0, found in the 54.1.0 sweep):
        # SWING_HIGH/SWING_LOW were RENAMED to DONCHIAN_UPPER/DONCHIAN_LOWER - identical
        # nativeOutput, timeframeMode and transform set, header stems swingHi->donchianHi
        # and swingLo->donchianLo. It always was a 20-bar Donchian channel; the old names
        # answer to nothing now.
        {"metric": "DONCHIAN_UPPER", "transformId": "distance", "timeframe": {"rel": "anchor"}},
        {"metric": "DONCHIAN_LOWER", "transformId": "distance", "timeframe": {"rel": "anchor"}},
        {"metric": "PRICE_ZONE", "transformId": "value", "timeframe": {"rel": "anchor"}},
    ],
    "PRICE_STRUCTURE": [
        {"metric": "STRUCT_ZONES", "transformId": "nearestZoneDist", "timeframe": {"rel": "anchor"}, "side": "support"},
        {"metric": "STRUCT_ZONES", "transformId": "nearestZoneDist", "timeframe": {"rel": "anchor"}, "side": "resistance"},
        {"metric": "STRUCT_ZONES", "transformId": "count", "timeframe": {"rel": "anchor"}},
    ],
    "CVD": [
        {"metric": "CVD", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4, "bars": "closed"},
        {"metric": "BUY_PRESSURE", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 3, "bars": "closed"},
    ],
    # --- timeframe-inert modules: these force their section to carry no override ---
    "FUNDING": [
        {"metric": "FUNDING_RATE", "transformId": "value", "timeframe": {"rel": "anchor"}},
        {"metric": "FUNDING_RATE", "transformId": "aggregate", "timeframe": {"rel": "anchor"}, "window": 24},
        {"metric": "FUNDING_LABEL", "transformId": "value", "timeframe": {"rel": "anchor"}},
    ],
    "OPEN_INTEREST": [
        {"metric": "OI", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4},
        {"metric": "OI_CHG", "transformId": "value", "timeframe": {"rel": "anchor"}},
        {"metric": "OI_PX_REGIME", "transformId": "value", "timeframe": {"rel": "anchor"}},
    ],
    "REGIME": [
        {"metric": "REGIME_TREND", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 3},
        {"metric": "REGIME_VOL", "transformId": "value", "timeframe": {"rel": "anchor"}},
        {"metric": "REGIME_MOM", "transformId": "value", "timeframe": {"rel": "anchor"}},
    ],
    "FLOW_DIVERGENCE": [
        {"metric": "SPOT_CVD", "transformId": "trajectory", "timeframe": {"rel": "anchor"}, "window": 4},
        {"metric": "PERP_SPOT_FLOW", "transformId": "value", "timeframe": {"rel": "anchor"}},
    ],
}

# Directional reads per module, expressed over headers the recipes above produce.
# `up` / `down` are clause factories; `filter` is non-directional.
# Every one of these is type-checked against predicted headers in the tests.
MODULE_CLAUSES: dict[str, dict] = {
    # `up`/`down` are the ALIGN (trend) reading; `fade_up`/`fade_down` the contrarian
    # one. Without this split a reversion thesis would buy strength and a breakout
    # thesis would buy the lower band - both legal, both backwards.
    "RSI":               {"up": lambda: num("RSI14_now", "gt", 50),
                          "down": lambda: num("RSI14_now", "lt", 50),
                          "fade_up": lambda: num("RSI14_now", "lt", 35),
                          "fade_down": lambda: num("RSI14_now", "gt", 65)},
    "MACD":              {"up": lambda: is_("MACD_trend", "rising"),
                          "down": lambda: is_("MACD_trend", "falling")},
    "MOVING_AVERAGES":   {"up": lambda: is_("MAalign", "bullish"),
                          "down": lambda: is_("MAalign", "bearish")},
    "TREND_STRENGTH":    {"filter": lambda: num("ADX_now", "gte", 25)},
    "BOLLINGER":         {"up": lambda: num("pctB_now", "gt", 0.95),
                          "down": lambda: num("pctB_now", "lt", 0.05),
                          "fade_up": lambda: num("pctB_now", "lt", 0.05),
                          "fade_down": lambda: num("pctB_now", "gt", 0.95)},
    "CVD":               {"up": lambda: is_("CVD_trend", "rising"),
                          "down": lambda: is_("CVD_trend", "falling")},
    "VOLUME":            {"up": lambda: is_("OBV_trend", "rising"),
                          "down": lambda: is_("OBV_trend", "falling")},
    "VOLATILITY":        {"filter": lambda: is_("ATR_trend", "rising")},
    "MFI":               {"up": lambda: is_("MFI14_zone", "overbought"),
                          "down": lambda: is_("MFI14_zone", "oversold"),
                          "fade_up": lambda: is_("MFI14_zone", "oversold"),
                          "fade_down": lambda: is_("MFI14_zone", "overbought")},
    "STOCHASTIC":        {"up": lambda: is_("K_zone", "overbought"),
                          "down": lambda: is_("K_zone", "oversold"),
                          "fade_up": lambda: is_("K_zone", "oversold"),
                          "fade_down": lambda: is_("K_zone", "overbought")},
    "RELATIVE_STRENGTH": {"up": lambda: is_("PPO_trend", "rising"),
                          "down": lambda: is_("PPO_trend", "falling")},
    "SUPPORT_RESISTANCE": {"up": lambda: is_("zone", "near low"),
                           "down": lambda: is_("zone", "near high")},
    "PRICE_STRUCTURE":   {"up": lambda: num("zones_support_dist", "lt", 1.0),
                          # `resist`, not `resistance` - verified against a live render
                          "down": lambda: num("zones_resist_dist", "gt", -1.0)},
    "FUNDING":           {"up": lambda: num("rate", "lt", 0),
                          "down": lambda: num("rate", "gt", 0)},
    "OPEN_INTEREST":     {"up": lambda: is_("OI_trend", "rising"),
                          "down": lambda: is_("OI_trend", "falling")},
    "REGIME":            {"up": lambda: is_("regTrend_now", "trending up"),
                          "down": lambda: is_("regTrend_now", "trending down")},
    "FLOW_DIVERGENCE":   {"up": lambda: is_("perpSpotFlow", "spot_led_accumulation"),
                          "down": lambda: is_("perpSpotFlow", "perp_led_fragile")},
}

# Modules whose oscillators substantially agree. Taking more than two is paying
# token cost for one piece of evidence - and, if weighted, counting it twice.
CORRELATED_OSCILLATORS = {"RSI", "STOCHASTIC", "MFI", "BOLLINGER"}

# Server-derived cadence and regime timeframe per anchor - every value MEASURED
# against the server as of 2026-08-28 (anchor_sweep_2026-08-28.json + the 1h/4h
# probes), and these four anchors are the platform's COMPLETE authorable set: the 1m
# and 1d sweep probes were refused with REPORT_TIMEFRAME_NOT_AUTHORABLE, allowedDomain
# enum ['5m','15m','1h','4h'] - below the published schema's 13-value enum. Two
# guessed values died to measurement here: 4h cadence (guessed INTRADAY, measured
# SWING) and 5m regime (guessed 1h, measured 15m).
CADENCE_FOR_ANCHOR = {"5m": "SCALPER", "15m": "SCALPER", "1h": "INTRADAY", "4h": "SWING"}
REGIME_TF_FOR_ANCHOR = {"5m": "15m", "15m": "1h", "1h": "4h", "4h": "1d"}

# Modules whose columns are null outside crypto. FLOW_DIVERGENCE measured directly
# (doc 12: "Perp/spot flow data unavailable" on GOOGL/GOLD); CVD via trap 21 (its
# metrics are daily-00:00-UTC accumulators, absent off-crypto, and null reads FALSE).
# FUNDING and OPEN_INTEREST are deliberately NOT here - synthetic perps carry both.
CRYPTO_ONLY_MODULES = {"CVD", "FLOW_DIVERGENCE"}

# Measured 2026-08-28 (cap_boundary_2026-08-28.json): the largest ranked selection
# whose compile preview fits BG-14's 256,000-byte cap, FOR THE TREND-CONTINUATION
# REPORT SHAPE OF THAT DAY (11 custom columns; since 2026-10-10 the preset renders 14
# columns and the same 34 headers) - exact adjacent-pair bracket: 4 viable, 5 refused
# at 258,883 bytes; CRYPTO also viable at 4. Report-relative: a wider report refuses
# earlier. The compile is the authority; this number only steers defaults and
# warnings. The byte curve is concave, so this is nowhere near cap/coins-at-30.
RANKED_LIMIT_MEASURED_MAX = 4


@dataclass
class Thesis:
    """What the strategy believes, expressed as modules and weights.

    2026-10-11, contract 108 ("signal rules, the aggregate-score gate and the required-count gate
    are removed", README "Contract history - v108"): two fields are RETIRED, removed rather than
    aliased, because nothing in omega reads them and the platform has no field to receive them:
      `gate`     (was SETUP_GATES.minAggregateScore, after the `stance` slot: float, default 0.65)
      `required` (was the signalIds counted into SETUP_GATES.minRequiredCount and sent as
                  `required: true` SIGNAL_RULES rows; list[str])
    A caller passing either gets a TypeError. The entry gate is now the conditions omega builds
    from `weights` and `stance` (omega.conditions.entry_gates)."""
    name: str
    tagline: str = ""
    description: str = ""
    anchor: str = "1h"
    # module -> tier (0-3). The KEYS choose the modules whose recipe columns the REPORT shows
    # (the agent's model reads the report) and whose readings the condition checklist reads
    # (directional modules: MODULE_CLAUSES "up"/"down"; filters: "filter"). Until contract 108
    # the tier was also the allocation of every signal in the module; at 108 the tier has no
    # platform meaning - it is validated 0..3 and rendered, nothing more.
    weights: dict[str, int] = field(default_factory=dict)
    # ALIGN: the tape should agree with the direction (trend theses).
    # FADE:  the crowd should be leaning the OTHER way (contrarian theses).
    stance: str = "ALIGN"
    # Modules included as reading material, weighted 0. BattleGrid lists each of their signals
    # whose data the report then shows as REPORT_DATA_SIGNAL_OFF and the module as
    # MODULE_IN_REPORT_SCORES_NOTHING (measured 2026-10-09/10 on REGIME: 4 + 1); the critique
    # predicts both. No preset carries one since 2026-10-10.
    context: list[str] = field(default_factory=list)
    # Show every (metric, rung) a weighted signal scores on that the module recipes do not:
    # one `value` column (STRUCT_ZONES: `count`) per missing pair at the rung's rel
    # (omega.membership.RUNG_REL). BattleGrid's ACTIVE_SIGNAL_DATA_NOT_IN_REPORT, measured
    # 12 times on the trend-continuation create of 2026-10-09 (data/contract/
    # stage_strategy_draft/diagnostics_action60_create_20261009T2310Z.json). False gives the
    # pre-2026-10-10 report, the shape committed as strategy 7534b2ee.
    show_scoring_data: bool = True
    # API coinSelection object; None means "derive one from the modules"
    coin_selection: dict | None = None
    # Explicit execution-parameter overrides (API field names); None/empty means the
    # MEASURED platform defaults (Decision 1a, 2026-08-28) - since v85 sent whole on their
    # axes, see omega/execution.py.
    execution: dict | None = None
    # Condition ROLES (EXIT_ROLES: "UP", "CORE_DOWN", ...) whose entry condition is also an
    # exit: each gains the v88 split, an exit rule CLOSE_ON_<key> closing the side its
    # verdict opposes (omega.conditions.close_on). Empty: every condition is an entry
    # condition, exitSide null - what every pre-v88 generated condition (exit: false) was.
    exits: list[str] = field(default_factory=list)

    @property
    def modules(self) -> list[str]:
        return list(self.weights) + [m for m in self.context if m not in self.weights]

    def resolved_coin_selection(self) -> dict:
        """Explicit selection wins; otherwise class-aware ranked, capped to the
        measured BG-14 boundary - a limit-30 default could never compile (measured
        2026-08-28; the old limit is preserved in git history)."""
        if self.coin_selection is not None:
            return self.coin_selection
        cat = "CRYPTO" if CRYPTO_ONLY_MODULES & set(self.modules) else "ALL"
        return {"mode": "ranked", "category": cat,
                "limit": min(30, RANKED_LIMIT_MEASURED_MAX)}


# --- preset theses --------------------------------------------------------
# Until 2026-10-10 every preset carried context=["REGIME"]: three columns the agent read and
# no signal scored (REPORT_DATA_SIGNAL_OFF x4 + MODULE_IN_REPORT_SCORES_NOTHING on every live
# stage). No preset's thesis weights REGIME, so the columns went rather than the weights.
PRESETS: dict[str, Thesis] = {
    "mean-reversion": Thesis(
        name="Mean Reversion at Extremes",
        tagline="Fade the stretch, only with flow agreeing",
        description="Oscillator extreme plus band breach, confirmed by flow and paid for by funding.",
        stance="FADE",
        weights={"BOLLINGER": 3, "RSI": 2, "CVD": 2, "FUNDING": 1, "VOLATILITY": 1},
    ),
    "trend-continuation": Thesis(
        name="Trend Continuation",
        tagline="Never fight an aligned stack",
        description="Full MA alignment with trend strength, entered on momentum resumption.",
        stance="ALIGN",
        weights={"MOVING_AVERAGES": 3, "TREND_STRENGTH": 2, "MACD": 2, "VOLUME": 1},
    ),
    "squeeze-breakout": Thesis(
        name="Squeeze Breakout",
        tagline="Coiled, then released",
        description="Volatility contraction into expansion, validated by participation and OI.",
        stance="ALIGN",
        weights={"BOLLINGER": 3, "VOLATILITY": 3, "VOLUME": 2, "OPEN_INTEREST": 1},
    ),
    "flow-divergence": Thesis(
        name="Spot-Led Accumulation",
        tagline="Organic demand ahead of leverage",
        description="Spot CVD outpacing perp flow while funding stays unexcited.",
        stance="FADE",
        weights={"FLOW_DIVERGENCE": 3, "CVD": 2, "FUNDING": 2, "OPEN_INTEREST": 1},
    ),
    "structure-reversal": Thesis(
        name="Structure Reversal",
        tagline="Turn at a level that means something",
        description="Price arriving at a structural zone with momentum divergence and flow confirmation.",
        stance="FADE",
        weights={"PRICE_STRUCTURE": 3, "SUPPORT_RESISTANCE": 2, "RSI": 2, "CVD": 1},
    ),
}

# The ENTRY axis, contract 85.0.0+. ON_CANDLE_CLOSE takes the entry AT the qualifying close, at market (the
# trigger every stored record was migrated to at 60.0.0, data/contract/get_strategy/824f4343-..._20260918T084500Z.json).
# v85 made `entry` "a union discriminated by trigger: { trigger: 'ON_CANDLE_CLOSE' } alone ... ON_CANDLE_CLOSE
# naming either dial is refused, which the retired compile accepted; the server stamps the seed values"
# (README "Contract history - v85"; the v91 schema's first ENTRY arm is additionalProperties:false over
# `trigger` only). The 61.0.1 three-key form {.., levelOffsetAtrMultiple: 0, validForBars: 4} is in git history.
# The level triggers rest orders omega has not measured.
ENTRY_MIRROR: dict = {"trigger": "ON_CANDLE_CLOSE"}

# The eight axes of stage_strategy_draft at 108.0.0, in the order its description lists them, each written WHOLE
# (data/contract/stage_strategy_draft/schema_20261010T215326Z.json). v108 refuses SIGNAL_RULES and SETUP_GATES "as
# unrecognized keys"; SETUP_GATES' minAtrPct moved onto TRADE_LEVEL_POLICY. The ten axes of 91.0.0 are AXES_91.
AXES = ("IDENTITY", "TIMEFRAME_PROFILE", "REPORT", "MARKET_READ", "CONDITIONS", "ENTRY",
        "TRADE_LEVEL_POLICY", "POSITION_MANAGEMENT")
AXES_91 = ("IDENTITY", "TIMEFRAME_PROFILE", "REPORT", "MARKET_READ", "CONDITIONS", "ENTRY",
           "SETUP_GATES", "TRADE_LEVEL_POLICY", "POSITION_MANAGEMENT", "SIGNAL_RULES")
# What a `current` read before v108 may still hold: accepted by axes_update and never staged.
RETIRED_AXES = ("SETUP_GATES", "SIGNAL_RULES")

# The seven roles _build_conditions emits (key = <prefix>_<role>); Thesis.exits names some of them.
EXIT_ROLES = ("RISK_ON", "CTX_UP", "CTX_DOWN", "CORE_UP", "CORE_DOWN", "UP", "DOWN")


@dataclass
class StrategyPlan:
    thesis: Thesis
    report: Report
    rules: list[Rule]
    conditions: list[dict] = field(default_factory=list)
    market_read_text: str = ""

    def condition_findings(self):
        out = validate_conditions(self.report, self.conditions)
        out += validate_market_read(self.market_read_text, self.conditions, self.report)
        out += validate_entry_gate(self.conditions)         # contract 108: the only entry gate
        return out

    def entry_gates(self) -> list[str]:
        """The conditionKeys that gate entry (omega.conditions.entry_gates); empty = NO_ENTRY_CONDITION."""
        return entry_gates(self.conditions)

    # -- analysis ---------------------------------------------------------
    def validation(self):
        return validate_report(self.report)

    def cost(self):
        return cost_report(self.report)

    def membership(self):
        return analyse(self.report)

    def allocation_findings(self):
        return check_allocations(self.report, [r for r in self.rules if r.allocation > 0])

    def simulate(self, score: float = 0.75, *, gate: float):
        """RETIRED at contract 108 (2026-10-11): what the aggregate would have been if every
        weighted signal scored `score`, against a minAggregateScore `gate`. The platform has no
        aggregate and no gate since 108 (simulate_aggregate_score was removed with no alias);
        kept as history of omega.aggregate's model, called by nothing on the generation path."""
        weighted = [r for r in self.rules if r.allocation > 0]
        if not weighted:
            return None
        return aggregate([Signal(r.signalId, score, r.allocation) for r in weighted], gate)

    def critique(self) -> list[str]:
        out: list[str] = []
        v, mem = self.validation(), self.membership()
        out += [f"invalid column: {f}" for f in v.errors]
        for f in self.allocation_findings():
            if f.severity == "error":
                out.append(f"wasted allocation: {f}")
        if mem.dead_metrics:
            out.append(f"context-only metrics (feed no signal): {', '.join(sorted(mem.dead_metrics))}")

        for f in self.condition_findings():
            out.append(f"condition {f.severity}: {f}")

        osc = CORRELATED_OSCILLATORS & set(self.thesis.weights)
        if len(osc) > 2:
            out.append(f"correlated oscillators weighted together: {', '.join(sorted(osc))} - "
                       f"largely one piece of evidence counted {len(osc)} times")

        c = self.cost()
        if c.breaches:
            out += [f"budget breach: {b}" for b in c.breaches]
        out.append(f"estimated agent tokens: ~{c.estimated_tokens} (what the agent reads; no platform token "
                   f"cap since contract 92 - the preview is capped at "
                   f"{load().shared['previewExecutionLimits']['maxResultChars']} result characters)")

        predicted = predicted_diagnostics(self.report, self.rules)
        out += [f"scoring {f.severity}: {f}" for f in predicted["mismatches"] + predicted["warnings"]]

        from .execution import PLATFORM_EXECUTION_DEFAULTS, validate_execution
        ov = self.thesis.execution or {}
        out += [f"execution {f.severity}: {f}" for f in validate_execution(ov)]
        eff = {**PLATFORM_EXECUTION_DEFAULTS, **ov}
        out.append(
            f"execution: {'platform defaults' if not ov else f'{len(ov)} override(s)'}"
            f" - R:R {eff['minRiskRewardRatio']}, ATR gate {eff['minAtrPct']}%, stop "
            f"{eff['minStopLossAtrMultiple']}-{eff['maxStopLossAtrMultiple']}xATR, "
            f"trailing {'on' if eff['trailingEnabled'] else 'off'}, break-even "
            f"{'on' if eff['breakEvenEnabled'] else 'off'} at {eff['breakEvenTriggerR']}R, "
            f"time decay {'on' if eff['timeDecayEnabled'] else 'off'}")

        sel = self.thesis.resolved_coin_selection()
        if sel.get("mode") == "ranked" and sel.get("limit", 0) > RANKED_LIMIT_MEASURED_MAX:
            out.append(
                f"coinSelection warning: ranked limit {sel['limit']} exceeds the measured "
                f"compile-preview boundary {RANKED_LIMIT_MEASURED_MAX} (BG-14) - expect a "
                f"byte-cap refusal (measured for the trend-continuation report shape; "
                f"wider reports refuse earlier)")
        return out

    # -- output -----------------------------------------------------------
    def _assumptions(self) -> list[str]:
        """What this plan assumes, for render() only. The compile's `assumptions` and
        `intentSummary` went with compile_strategy_plan at v85 ("the draft is the intent"),
        so nothing here reaches the platform."""
        sel = self.thesis.resolved_coin_selection()
        how = ("explicit thesis override" if self.thesis.coin_selection is not None else
               "default - class-aware: CRYPTO when the thesis weights a crypto-only "
               "module (CVD, FLOW_DIVERGENCE), else ALL")
        execution = (f"execution overrides set: {sorted(self.thesis.execution)}"
                     if self.thesis.execution else
                     "no execution overrides - the 08-28 MEASURED platform defaults are "
                     "sent whole on their axes (see omega/execution.py; M1 is owed)")
        return [
            f"preview coinSelection {sel} ({how})",
            "signal params are the platform defaults captured in the signal map",
            execution,
            "local only: never staged into a draft, never committed",
        ]

    def _sections(self) -> list[dict]:
        # Measured 2026-08-28: a CREATE refused ANY client-supplied custom sectionKey
        # (REPORT_CUSTOM_SECTION_NOT_OWNED, allowedDomain enum []) - the server mints them.
        # The v91 REPORT axis still declares sectionKey optional on a custom section; a
        # create draft's acceptance of one is unmeasured, so a CREATE keeps not sending it.
        # Our deterministic keys stay on the local Report; platform sections keep theirs,
        # which IS the section's identity. An UPDATE puts the strategy's LIVE custom keys
        # back on (axes_update -> _carry_section_keys, 2026-10-10).
        return [
            {k: v for k, v in s.items() if not (s.get("kind") == "custom" and k == "sectionKey")}
            for s in self.report.wire()
        ]

    def _rules(self) -> list[dict]:
        """The dense 84-row scorecard. `allocation` is an INTEGER 0..3 and required on the
        v91 SIGNAL_RULES axis, as is `required`; unallocated signals ride at 0."""
        m = _map()
        defaults = m["defaultParams"]
        allocated = {r.signalId: r for r in self.rules}
        all_signals = sorted({s for v in m["moduleSignals"].values() for s in v})
        return [
            {
                "signalId": s,
                "allocation": int(allocated[s].allocation) if s in allocated else 0,
                "required": bool(allocated[s].required) if s in allocated else False,
                "params": defaults.get(s, {}),
            }
            for s in all_signals
        ]

    def axes(self) -> dict:
        """The `axes` of a CREATE stage_strategy_draft request (no strategyId,
        draftVersion 0): all eight axes, each WHOLE, keyed and shaped by the 108 schema
        (data/contract/stage_strategy_draft/schema_20261010T215326Z.json). TRADE_LEVEL_POLICY
        carries minAtrPct beside the stop-loss multiples and the risk-reward minimum (v108).
        The ten-axis v91 form (SETUP_GATES, SIGNAL_RULES) and the flat compile body before
        it are in git history."""
        from .execution import (PLATFORM_EXECUTION_DEFAULTS, POSITION_MANAGEMENT_DIALS,
                                POSITION_MANAGEMENT_MIRROR, TRADE_LEVEL_DIALS)
        t = self.thesis
        # validated in critique(); keys are the API's own field names
        eff = {**PLATFORM_EXECUTION_DEFAULTS, **POSITION_MANAGEMENT_MIRROR, **(t.execution or {})}
        return {
            "IDENTITY": {"name": t.name, "description": t.description, "tagline": t.tagline},
            "TIMEFRAME_PROFILE": {"timeframe": t.anchor},
            "REPORT": {"sections": self._sections()},
            "MARKET_READ": {"marketReadText": self.market_read_text},
            "CONDITIONS": {"conditions": self.conditions},
            "ENTRY": {"entry": dict(ENTRY_MIRROR)},
            "TRADE_LEVEL_POLICY": {k: eff[k] for k in TRADE_LEVEL_DIALS},
            "POSITION_MANAGEMENT": {k: eff[k] for k in POSITION_MANAGEMENT_DIALS},
        }

    def axes_update(self, current: dict | None) -> dict:
        """The axes for staging this thesis into an EXISTING strategy's draft. Never ENTRY
        (the old UPDATE rule: never touch an existing strategy's entry axis; an axis omitted
        from a stage keeps the value the draft has, v85). strategyId and draftVersion belong
        to the stage request, not to the axes.

        `current` is the strategy's axes as get_strategy_draft reads them (the held draft,
        or the committed values when none is held). The 2026-08-29 UPDATE sent a dial only
        when `thesis.execution` named it, so a tuned strategy kept its dials; an axis is
        staged WHOLE, so sending axes()'s 08-28 defaults would reset them (the review of
        2026-10-06). So TRADE_LEVEL_POLICY and POSITION_MANAGEMENT are staged only when the
        thesis names one of their dials, the rest of the axis read from `current`. A dial
        found in neither raises: omega never invents the value of a live strategy's dial.

        Contract 108 (2026-10-11): SETUP_GATES and SIGNAL_RULES are gone, so nothing forces a
        dial axis onto an update any more (SETUP_GATES was always staged because it carried the
        thesis's gate). minAtrPct is a TRADE_LEVEL_POLICY dial; a `current` read before v108
        that still holds SETUP_GATES / SIGNAL_RULES is accepted, those two axes are never
        staged, and when current TRADE_LEVEL_POLICY lacks minAtrPct it is taken from the old
        SETUP_GATES.

        Section keys are carried forward from `current` (2026-10-10). A CREATE sends no key -
        the server mints a custom section's `sectionKey` and derives a clause's
        `column.sectionKey` at commit - so re-staging a strategy omega created showed 14
        changes of no substance on the first live UPDATE (2 sections "custom:…" -> null,
        12 clauses "reference-pairs" / "market-breadth" / the strategy's own custom key ->
        null; manager action 62, 2026-10-10 06:34Z). The commit kept every live key, so the
        diff was cosmetic, but the manager's card binds that diff. Here:

        * REPORT: each generated custom section takes the `sectionKey` of the current custom
          section with the same `title` (omega writes titles deterministically); when no
          title matches, the counts are equal and the titles unique on both sides, by
          position; a partial title match carries only what matched. A current custom
          section this thesis no longer generates is simply not carried - the platform drops
          it at commit. A key not matching the schema's ^custom:[0-9a-fA-F-]{36}$ is never
          sent.
        * CONDITIONS: a generated clause whose `column.sectionKey` is null takes the key the
          current clause with the same `conditionKey` and the same `header` carries, when
          that key names where this plan's report resolves the header: an ambient or
          platform section's own key, or - for a custom key - the live key of the section
          carried above, whose current columns must hold a column with the same identity
          (metric, transformId, chainedTransformId, timeframe) as the generated column that
          emits the header. A header two sections emit, a key the schema refuses (empty or
          over 120 characters), a differing or missing key: left null, as a CREATE sends it.

        Never invents a key. Whether the server honours a key sent back on an UPDATE, rather
        than re-deriving it, is unmeasured: the 2026-08-29 compile-path UPDATE re-minted
        custom keys sent byte-identical (LOCKSTEP_REMINT); the v91 commit of 2026-10-10
        kept them through nulls."""
        from .execution import POSITION_MANAGEMENT_DIALS, TRADE_LEVEL_DIALS
        out = self.axes()
        del out["ENTRY"]
        # axes() hands out self.conditions itself; the carry below must not leak live keys
        # into a later CREATE, so the two axes it rewrites are copied first.
        out["REPORT"] = copy.deepcopy(out["REPORT"])
        out["CONDITIONS"] = copy.deepcopy(out["CONDITIONS"])
        named = self.thesis.execution or {}
        current = current or {}
        self._carry_section_keys(out, current)

        def complete(axis: str, dials: tuple[str, ...]) -> dict:
            have = current.get(axis) or {}
            missing = [d for d in dials if d not in named and d not in have]
            if missing:
                raise ValueError(
                    f"{axis}: {missing} named neither by the thesis nor by the strategy's "
                    f"current axes - read them with get_strategy_draft and pass them as "
                    f"`current`; omega never invents a live strategy's dial")
            return {d: named[d] if d in named else have[d] for d in dials}

        # a pre-v108 read: minAtrPct still sits on SETUP_GATES (RETIRED_AXES are never staged)
        legacy_atr = (current.get("SETUP_GATES") or {}).get("minAtrPct")
        tlp = current.get("TRADE_LEVEL_POLICY") or {}
        if "minAtrPct" not in tlp and legacy_atr is not None:
            current = {**current, "TRADE_LEVEL_POLICY": {**tlp, "minAtrPct": legacy_atr}}
        for axis, dials in (("TRADE_LEVEL_POLICY", TRADE_LEVEL_DIALS),
                            ("POSITION_MANAGEMENT", POSITION_MANAGEMENT_DIALS)):
            if named.keys() & set(dials):
                out[axis] = complete(axis, dials)
            else:
                del out[axis]
        return out

    def _carry_section_keys(self, out: dict, current: dict) -> None:
        """Copy the current strategy's section keys onto `out`'s REPORT custom sections and
        CONDITIONS clauses under the rules axes_update() documents. Mutates `out` only."""
        cur_sections = (current.get("REPORT") or {}).get("sections") or []
        cur_conditions = (current.get("CONDITIONS") or {}).get("conditions") or []
        sections = out["REPORT"]["sections"]

        # omega's local deterministic key -> (the live key carried, the current section)
        live_of_local: dict[str, tuple[str, dict]] = {}
        for i, cur in _match_custom_sections(sections, cur_sections).items():
            key = cur.get("sectionKey")
            if not (isinstance(key, str) and CUSTOM_SECTION_KEY.match(key)):
                continue
            sections[i] = {**sections[i], "sectionKey": key}
            live_of_local[self.report.sections[i].sectionKey] = (key, cur)

        if not cur_conditions:
            return
        emitters = self._header_emitters()

        def resolves(header: str, key: str) -> bool:
            places = emitters.get(header) or []
            if len(places) != 1:            # emitted nowhere or in two sections: the server resolves
                return False
            local_key, column = places[0]
            if column is None:              # ambient / platform section: its key is the identity
                return key == local_key
            live = live_of_local.get(local_key)
            if live is None or live[0] != key:
                return False
            wanted = _column_identity(column)
            return any(_column_identity(c) == wanted for c in live[1].get("columns") or [])

        cur_by_key = {c.get("conditionKey"): c for c in cur_conditions}
        for cond in out["CONDITIONS"]["conditions"]:
            cur = cur_by_key.get(cond["conditionKey"])
            if cur is None:
                continue
            keys_by_header: dict[str, set[str]] = {}
            for clause in _clauses_of(cur.get("definition")):
                col = clause.get("column") or {}
                key = col.get("sectionKey")
                if isinstance(key, str) and 1 <= len(key) <= CLAUSE_SECTION_KEY_MAX_LENGTH:
                    keys_by_header.setdefault(col.get("header"), set()).add(key)
            for clause in _clauses_of(cond["definition"]):
                col = clause["column"]
                if col.get("sectionKey") is not None:
                    continue
                keys = keys_by_header.get(col["header"]) or set()
                if len(keys) == 1 and resolves(col["header"], next(iter(keys))):
                    clause["column"] = {**col, "sectionKey": next(iter(keys))}

    def _header_emitters(self) -> dict[str, list[tuple[str, dict | None]]]:
        """header -> every (sectionKey, column) in this plan's report that emits it: a custom
        section's local key with the emitting column's wire dict; a platform section's key,
        or an ambient section's, with None (their key is the identity)."""
        c = load()
        out: dict[str, list[tuple[str, dict | None]]] = {
            h: [(spec["sectionKey"], None)] for h, spec in ambient_headers().items()}
        for section in self.report.sections:
            if isinstance(section, CustomSection):
                for column in section.columns:
                    if column.metric not in c.metrics:
                        continue
                    for o in outputs_for(column, c):
                        out.setdefault(o.header, []).append((section.sectionKey, column.wire()))
            else:
                tmpl = c.platform_templates.get(section.sectionKey) or {}
                for spec in tmpl.get("columns", []):
                    try:
                        for o in outputs_for(Column.model_validate(spec), c):
                            out.setdefault(o.header, []).append((section.sectionKey, None))
                    except Exception:
                        continue
        return out

    def preview_request(self) -> dict:
        """The read-only dry run: a preview_strategy_report body with a FIELDS source
        (v85). It judges the report and the conditions with the v84/v88 grammar - NOT
        signal rules, gates or dials; only a stage does, and a stage is a write.
        coinSelection lives here only since v85: it is no part of a strategy."""
        return {
            "coinSelection": self.thesis.resolved_coin_selection(),
            "source": {
                "kind": "FIELDS",
                "timeframe": self.thesis.anchor,
                "sections": self._sections(),
                "conditions": self.conditions,
                "marketReadText": self.market_read_text,
            },
        }

    def render(self) -> str:
        c, mem = self.cost(), self.membership()
        weighted = [r for r in self.rules if r.allocation > 0]
        lines = [
            f"{self.thesis.name}  --  {self.thesis.tagline}",
            f"anchor {self.thesis.anchor} | stance {self.thesis.stance} | "
            f"{len(self.report.sections)} sections | {c.columns} columns | {c.headers} headers",
            "",
            f"weighted signals  {len(weighted):>3} of {len(mem.signals_in)} in report",
        ]
        by_tier: dict[int, list[str]] = {}
        for r in weighted:
            by_tier.setdefault(r.allocation, []).append(r.signalId)
        for tier in sorted(by_tier, reverse=True):
            lines.append(f"  tier {tier}  ({len(by_tier[tier])})  {', '.join(sorted(by_tier[tier])[:4])}"
                         + (" ..." if len(by_tier[tier]) > 4 else ""))
        gates = self.entry_gates()
        lines += ["", "entry gate: " + (", ".join(gates) if gates else "NONE (NO_ENTRY_CONDITION)")]
        if self.conditions:
            lines += ["", f"conditions        {len(self.conditions):>3}"]
            for cond in self.conditions:
                v = cond.get("verdict") or "-"
                if cond.get("exitSide"):
                    v = f"x{cond['exitSide']}"       # an exit rule: the side it closes
                lines.append(f"  {cond['conditionKey']:<16} {v:<8} {cond['name']}")
        lines += ["", "assumptions:"] + [f"  - {x}" for x in self._assumptions()]
        lines += ["", "critique:"] + [f"  - {x}" for x in self.critique()]
        return "\n".join(lines)


def _section_key(title: str) -> str:
    """Deterministic custom sectionKey so conditions can reference the section."""
    return f"custom:{uuid.uuid5(uuid.NAMESPACE_URL, f'omega/{title}')}"


def _match_custom_sections(generated: list[dict], current: list[dict]) -> dict[int, dict]:
    """Index of a generated custom section -> the current custom section it continues.

    By `title` first (omega writes titles deterministically), which needs the current titles
    to be unique; when NO title matches, by position - only when the counts are equal and
    the titles are unique on both sides. A partial title match carries only what matched.
    A current section no generated one matches is not in the result: the platform drops it."""
    gen = [(i, s) for i, s in enumerate(generated) if s.get("kind") == "custom"]
    cur = [s for s in current if s.get("kind") == "custom"]
    cur_titles = [s.get("title") for s in cur]
    gen_titles = [s.get("title") for _, s in gen]
    matched: dict[int, dict] = {}
    if len(set(cur_titles)) == len(cur_titles):
        by_title = {s.get("title"): s for s in cur}
        matched = {i: by_title[s["title"]] for i, s in gen if s.get("title") in by_title}
        if not matched and len(gen) == len(cur) and len(set(gen_titles)) == len(gen_titles):
            matched = {i: c for (i, _), c in zip(gen, cur)}
    return matched


def _clauses_of(defn: object) -> Iterator[dict]:
    """Every clause node under a condition definition, in order (groups recursed, refs
    skipped). Yields the live dicts so a caller may rewrite a clause's column."""
    if not isinstance(defn, dict):
        return
    if defn.get("kind") == "clause":
        yield defn
        return
    for member in defn.get("members") or []:
        yield from _clauses_of(member)
    if "member" in defn:
        yield from _clauses_of(defn["member"])


def _column_identity(column: dict) -> tuple[str, ...]:
    return tuple(json.dumps(column.get(k), sort_keys=True) for k in _COLUMN_IDENTITY)


def _split_by_timeframe_mode(modules: list[str]) -> tuple[list[dict], list[dict]]:
    """Candle-backed columns and timeframe-inert columns, kept apart.

    A section carrying a `timeframe` override cannot hold inert metrics, so they get
    their own section. This keeps the candle section free to be pinned later.
    """
    c = load()
    candle, inert = [], []
    for module in modules:
        for spec in MODULE_RECIPES.get(module, []):
            (inert if c.metric(spec["metric"]).is_timeless else candle).append(spec)
    return candle, inert


def _plainest_transform(metric: str) -> str:
    """`value` when the metric offers it; else its first listed transform (STRUCT_ZONES, an
    entitySet, lists count first) - the metric file's own list, data/contract/metrics/."""
    transforms = load().metric(metric).transforms
    return "value" if "value" in transforms else next(iter(transforms))


def _scoring_data_columns(rules: list[Rule], recipe: list[dict]) -> list[dict]:
    """One column per (metric, rung) a weighted signal scores on that the recipe columns do not
    show: the metric at the rung's rel (RUNG_REL), plainest transform, in rule order. What
    BattleGrid lists as ACTIVE_SIGNAL_DATA_NOT_IN_REPORT (membership.scoring_gaps)."""
    shown = shown_data(Report(sections=[CustomSection(
        title="recipe", benchmarkTicker=None,
        columns=[Column.model_validate(c) for c in recipe])])) if recipe else set()
    data = _signal_data()
    out: list[dict] = []
    for r in rules:
        for d in data.get(r.signalId, []):
            key = (d["metric"], RUNG_REL[d["rung"]])
            if key in shown:
                continue
            shown.add(key)
            out.append({"metric": key[0], "transformId": _plainest_transform(key[0]),
                        "timeframe": {"rel": key[1]}})
    return out


def plan(thesis: Thesis) -> StrategyPlan:
    """Turn a thesis into a validated report plus allocations."""
    m = _map()
    c = load()
    candle, inert = _split_by_timeframe_mode(thesis.modules)

    # allocate only what the report can actually feed (membership is module-level, so the
    # scoring-data columns below never widen it: every metric they add belongs to a module
    # the thesis already weights)
    feedable = signals_for({s["metric"] for s in candle + inert})
    rules: list[Rule] = []
    for module, tier in thesis.weights.items():
        for sid in m["moduleSignals"].get(module, []):
            if sid in feedable and tier > 0:
                rules.append(Rule(signalId=sid, allocation=tier, required=False))
    if thesis.show_scoring_data:
        for spec in _scoring_data_columns(rules, candle + inert):
            (inert if c.metric(spec["metric"]).is_timeless else candle).append(spec)

    # sections[].notes is REQUIRED by the compile schema (published 2026-08-30,
    # string 1-400 or null). Emit a provenance string - null is schema-legal but
    # its acceptance is unmeasured (plan decision, 2026-08-29).
    notes = (f"Generated by omega.generate from the {thesis.name!r} thesis "
             f"(stance {thesis.stance}, anchor {thesis.anchor}).")[:400]
    sections: list[CustomSection] = []
    if candle:
        title = f"{thesis.name[:44]} Signals"[:60]
        sections.append(CustomSection(
            title=title, sectionKey=_section_key(title), benchmarkTicker=None,
            notes=notes, columns=[Column.model_validate(s) for s in candle]))
    if inert:
        title = f"{thesis.name[:40]} Context"[:60]
        sections.append(CustomSection(
            title=title, sectionKey=_section_key(title), benchmarkTicker=None,
            notes=notes, columns=[Column.model_validate(s) for s in inert]))

    report = Report(anchor=thesis.anchor, sections=sections)
    conditions = _build_conditions(thesis)
    verdicts = [c for c in conditions if c.get("verdict") in ("UP", "DOWN")]
    text = market_read_text(
        f"{thesis.name}. {thesis.description}".strip(), verdicts) if verdicts else ""
    return StrategyPlan(thesis=thesis, report=report, rules=rules,
                        conditions=conditions, market_read_text=text)


def _clause_for(module: str, side: str, fade: bool) -> dict:
    """Pick the reading that matches the thesis stance."""
    spec = MODULE_CLAUSES[module]
    if fade and f"fade_{side}" in spec:
        return spec[f"fade_{side}"]()
    return spec[side]()


def _build_conditions(thesis: Thesis) -> list[dict]:
    """A layered condition DAG, not one flat checklist.

    Building blocks carry verdict=None and are composed by conditionRef into the two
    verdict-bearing conditions. Context comes from the AMBIENT sections, which cost
    nothing against the column or token budget:

        {P}_RISK_ON    stablecoin pairs at par            (ambient, free)
        {P}_CTX_UP     tape / crowd context for longs     (ambient, free)
        {P}_CTX_DOWN   tape / crowd context for shorts    (ambient, free)
        {P}_CORE_UP    N_OF checklist over the modules    (your columns)
        {P}_CORE_DOWN  ...
        {P}_UP         ALL(CORE_UP, CTX_UP, RISK_ON)      -> verdict UP
        {P}_DOWN       ALL(CORE_DOWN, CTX_DOWN, RISK_ON)  -> verdict DOWN

    Every clause and group holds one read, {1,1}: what `closes: 1` meant before v84, and
    a hold above it is unmeasured for these readings. Every one of the seven is an entry
    condition (exitSide null); each role named in thesis.exits then gains its v88 split,
    CLOSE_ON_{P}_{role}, appended after the seven (omega.conditions.close_on).
    """
    directional = [m for m in thesis.weights if "up" in MODULE_CLAUSES.get(m, {})]
    filters = [m for m in thesis.weights if "filter" in MODULE_CLAUSES.get(m, {})]
    if len(directional) < 2:
        return []

    prefix = "".join(w[0] for w in thesis.name.split()[:2]).upper() or "SETUP"
    n = max(2, (len(directional) * 2) // 3)          # two-thirds of the checklist
    fade = thesis.stance == "FADE"

    out = [
        condition(f"{prefix}_RISK_ON", "Stablecoin pairs at par",
                  stables_at_par(), verdict=None),
        condition(f"{prefix}_CTX_UP",
                  "Crowd leaning down - room to fade up" if fade else "Broad tape up",
                  crowd_leaning_down() if fade else tape_bullish(),
                  verdict=None),
        condition(f"{prefix}_CTX_DOWN",
                  "Crowd leaning up - room to fade down" if fade else "Broad tape down",
                  crowd_leaning_up() if fade else tape_bearish(),
                  verdict=None),
    ]
    for side, verdict in (("up", "UP"), ("down", "DOWN")):
        checklist = n_of(n, *[_clause_for(m, side, fade) for m in directional])
        core = (all_of(checklist, *[MODULE_CLAUSES[m]["filter"]() for m in filters])
                if filters else checklist)
        out.append(condition(f"{prefix}_CORE_{verdict}",
                             f"{n} of {len(directional)} filters agree - {side}",
                             core, verdict=None))
    for verdict in ("UP", "DOWN"):
        out.append(condition(
            f"{prefix}_{verdict}",
            f"Setup confirmed - {verdict.lower()}",
            all_of(ref(f"{prefix}_CORE_{verdict}"),
                   ref(f"{prefix}_CTX_{verdict}"),
                   ref(f"{prefix}_RISK_ON")),
            verdict=verdict))
    by_role = {c["conditionKey"][len(prefix) + 1:]: c for c in out}
    for role in thesis.exits:
        if role not in by_role:
            raise ValueError(f"exit role {role!r} is not one of {EXIT_ROLES}")
        out.append(close_on(by_role[role]))
    return out


def plan_for_signals(signal_ids: list[str], *, name: str = "Ad-hoc", tier: int = 2,
                     anchor: str = "1h") -> StrategyPlan:
    """Work backwards: given signals you want to weight, build the report that feeds them."""
    m = _map()
    modules, unreachable = [], []
    for sid in signal_ids:
        module = next((k for k, v in m["moduleSignals"].items() if sid in v), None)
        if module is None or not m["moduleSatisfiedBy"].get(module):
            unreachable.append(sid)
        elif module not in modules:
            modules.append(module)
    thesis = Thesis(name=name, tagline="built from target signals", anchor=anchor,
                    weights={mod: tier for mod in modules})
    result = plan(thesis)
    if unreachable:
        result.thesis.description = (
            f"unreachable and therefore unallocated: {', '.join(unreachable)}")
    return result


def emit_plan(plan_obj: StrategyPlan, name: str, *, out_dir=None) -> str:
    from .contract import ROOT
    target = out_dir or (ROOT / "out")
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{name}.strategy.json"
    # The request of a CREATE stage_strategy_draft (v85: no strategyId opens a new create
    # draft; draftVersion 0 when there is no draft), plus local metadata.
    payload: dict = {"draftVersion": 0, "axes": plan_obj.axes()}
    payload["_generatedBy"] = "omega.generate - LOCAL ONLY, not submitted"
    payload["_critique"] = plan_obj.critique()
    payload["_assumptions"] = plan_obj._assumptions()
    payload["_previewRequest"] = plan_obj.preview_request()
    # cadence/regimeTimeframe have no field on any axis; keep them as local metadata.
    # Underscore keys never go to the API - strip every "_"-prefixed key before any
    # submission.
    payload["_cadence"] = CADENCE_FOR_ANCHOR[plan_obj.thesis.anchor]
    payload["_regimeTimeframe"] = REGIME_TF_FOR_ANCHOR[plan_obj.thesis.anchor]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)
