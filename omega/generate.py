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

import json
from dataclasses import dataclass, field

import uuid

from .aggregate import Signal, aggregate
from .conditions import (
    all_of, condition, crowd_leaning_down, crowd_leaning_up, is_, market_read_text,
    n_of, num, ref, stables_at_par, tape_bearish, tape_bullish, validate_conditions,
    validate_market_read,
)
from .contract import DERIVED_DIR, load
from .fanout import cost_report, outputs_for
from .membership import _map, analyse, check_allocations, scoring_gaps, signals_for
from .types import Column, CustomSection, Report, Rule
from .validate import validate_report

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
        {"metric": "SWING_HIGH", "transformId": "distance", "timeframe": {"rel": "anchor"}},
        {"metric": "SWING_LOW", "transformId": "distance", "timeframe": {"rel": "anchor"}},
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
# REPORT SHAPE (11 custom columns) - exact adjacent-pair bracket: 4 viable, 5 refused
# at 258,883 bytes; CRYPTO also viable at 4. Report-relative: a wider report refuses
# earlier. The compile is the authority; this number only steers defaults and
# warnings. The byte curve is concave, so this is nowhere near cap/coins-at-30.
RANKED_LIMIT_MEASURED_MAX = 4


@dataclass
class Thesis:
    """What the strategy believes, expressed as modules and weights."""
    name: str
    tagline: str = ""
    description: str = ""
    anchor: str = "1h"
    gate: float = 0.65
    # module -> allocation tier (0-3) applied to every signal in that module
    weights: dict[str, int] = field(default_factory=dict)
    # ALIGN: the tape should agree with the direction (trend theses).
    # FADE:  the crowd should be leaning the OTHER way (contrarian theses).
    stance: str = "ALIGN"
    required: list[str] = field(default_factory=list)   # signalIds treated as vetoes
    context: list[str] = field(default_factory=list)    # modules included but weighted 0
    # API coinSelection object; None means "derive one from the modules"
    coin_selection: dict | None = None
    # Explicit execution-parameter overrides (API field names); None/empty means emit
    # nothing and run on the MEASURED platform defaults (Decision 1a, 2026-08-28).
    execution: dict | None = None

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
PRESETS: dict[str, Thesis] = {
    "mean-reversion": Thesis(
        name="Mean Reversion at Extremes",
        tagline="Fade the stretch, only with flow agreeing",
        description="Oscillator extreme plus band breach, confirmed by flow and paid for by funding.",
        stance="FADE",
        gate=0.65,
        weights={"BOLLINGER": 3, "RSI": 2, "CVD": 2, "FUNDING": 1, "VOLATILITY": 1},
        context=["REGIME"],
    ),
    "trend-continuation": Thesis(
        name="Trend Continuation",
        tagline="Never fight an aligned stack",
        description="Full MA alignment with trend strength, entered on momentum resumption.",
        stance="ALIGN",
        gate=0.60,
        weights={"MOVING_AVERAGES": 3, "TREND_STRENGTH": 2, "MACD": 2, "VOLUME": 1},
        context=["REGIME"],
    ),
    "squeeze-breakout": Thesis(
        name="Squeeze Breakout",
        tagline="Coiled, then released",
        description="Volatility contraction into expansion, validated by participation and OI.",
        stance="ALIGN",
        gate=0.55,
        weights={"BOLLINGER": 3, "VOLATILITY": 3, "VOLUME": 2, "OPEN_INTEREST": 1},
        context=["REGIME"],
    ),
    "flow-divergence": Thesis(
        name="Spot-Led Accumulation",
        tagline="Organic demand ahead of leverage",
        description="Spot CVD outpacing perp flow while funding stays unexcited.",
        stance="FADE",
        gate=0.60,
        weights={"FLOW_DIVERGENCE": 3, "CVD": 2, "FUNDING": 2, "OPEN_INTEREST": 1},
        context=["REGIME"],
    ),
    "structure-reversal": Thesis(
        name="Structure Reversal",
        tagline="Turn at a level that means something",
        description="Price arriving at a structural zone with momentum divergence and flow confirmation.",
        stance="FADE",
        gate=0.65,
        weights={"PRICE_STRUCTURE": 3, "SUPPORT_RESISTANCE": 2, "RSI": 2, "CVD": 1},
        context=["REGIME"],
    ),
}


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
        return out

    # -- analysis ---------------------------------------------------------
    def validation(self):
        return validate_report(self.report)

    def cost(self):
        return cost_report(self.report)

    def membership(self):
        return analyse(self.report)

    def allocation_findings(self):
        return check_allocations(self.report, [r for r in self.rules if r.allocation > 0])

    def simulate(self, score: float = 0.75):
        """What the aggregate would be if every weighted signal scored `score`."""
        weighted = [r for r in self.rules if r.allocation > 0]
        if not weighted:
            return None
        return aggregate([Signal(r.signalId, score, r.allocation) for r in weighted],
                         self.thesis.gate)

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
        headroom = c.budgets["estimatedTokens"] - c.estimated_tokens
        out.append(f"token headroom: ~{headroom} of {c.budgets['estimatedTokens']}")

        sim = self.simulate()
        if sim and not sim.would_route:
            out.append(f"even at 0.75 across the board the aggregate is "
                       f"{sim.aggregate_score_percent}% - below the {sim.gate_percent}% gate")

        out += [f"scoring {f.severity}: {f}" for f in scoring_gaps(self.report, self.rules)]

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
        """The API's required `assumptions` array: each string <=500 chars, list <=20."""
        sel = self.thesis.resolved_coin_selection()
        how = ("explicit thesis override" if self.thesis.coin_selection is not None else
               "default - class-aware: CRYPTO when the thesis weights a crypto-only "
               "module (CVD, FLOW_DIVERGENCE), else ALL")
        execution = (f"execution overrides set: {sorted(self.thesis.execution)}"
                     if self.thesis.execution else
                     "no execution parameters set - the MEASURED platform defaults "
                     "apply (see omega/execution.py)")
        return [
            f"coinSelection {sel} ({how})",
            "signal params are the platform defaults captured in the signal map",
            execution,
            "dry-run: compiled for viability only, never applied",
        ]

    def wire(self) -> dict:
        """The exact compile_strategy_plan CREATE request body, dense 84-entry scorecard
        included. Shape verified against the live schema on 2026-08-28."""
        m = _map()
        defaults = m["defaultParams"]
        allocated = {r.signalId: r for r in self.rules}
        all_signals = sorted({s for v in m["moduleSignals"].values() for s in v})
        # Measured 2026-08-28: CREATE refuses ANY client-supplied custom sectionKey
        # (REPORT_CUSTOM_SECTION_NOT_OWNED, allowedDomain enum []) - the server mints
        # them. Our deterministic keys stay on the local Report; platform sections keep
        # theirs, which IS the section's identity.
        sections = [
            {k: v for k, v in s.items() if not (s.get("kind") == "custom" and k == "sectionKey")}
            for s in self.report.wire()
        ]
        out = {
            "operation": "CREATE",
            "intentSummary": (f"{self.thesis.name}: {self.thesis.description} "
                              f"Stance {self.thesis.stance}, gate {self.thesis.gate}. "
                              f"Generated by omega.generate; compile dry-run only.")[:2000],
            "assumptions": self._assumptions(),
            "coinSelection": self.thesis.resolved_coin_selection(),
            "name": self.thesis.name,
            "tagline": self.thesis.tagline,
            "description": self.thesis.description,
            "timeframe": self.thesis.anchor,
            "sections": sections,
            "conditions": self.conditions,
            "marketReadText": self.market_read_text,
            "rules": [
                {
                    "signalId": s,
                    "allocation": allocated[s].allocation if s in allocated else 0,
                    "required": bool(allocated[s].required) if s in allocated else False,
                    "params": defaults.get(s, {}),
                }
                for s in all_signals
            ],
            "minAggregateScore": self.thesis.gate,
            "minRequiredCount": sum(1 for r in self.rules if r.required),
        }
        if self.thesis.execution:
            out.update(self.thesis.execution)   # validated in critique(); keys are API fields
        return out

    def wire_update(self, strategy_id: str, expected_revision: int) -> dict:
        """The exact compile_strategy_plan UPDATE request body: the full CREATE body
        re-targeted at an existing strategy (design 2026-08-29 - the Thesis is the
        single source of truth; the server computes the diff)."""
        if expected_revision < 1:
            raise ValueError(f"expectedRevision must be >= 1, got {expected_revision}")
        out = self.wire()
        out["operation"] = "UPDATE"
        out["strategyId"] = strategy_id
        out["expectedRevision"] = expected_revision
        return out

    def render(self) -> str:
        c, mem, sim = self.cost(), self.membership(), self.simulate()
        weighted = [r for r in self.rules if r.allocation > 0]
        lines = [
            f"{self.thesis.name}  --  {self.thesis.tagline}",
            f"anchor {self.thesis.anchor} | gate {self.thesis.gate:.2f} | "
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
        if self.conditions:
            lines += ["", f"conditions        {len(self.conditions):>3}"]
            for cond in self.conditions:
                v = cond.get("verdict") or "-"
                lines.append(f"  {cond['conditionKey']:<16} {v:<8} {cond['name']}")
        if sim:
            lines += ["", f"all-signals-at-0.75 -> aggregate {sim.aggregate_score_percent}% "
                          f"vs gate {sim.gate_percent}% -> "
                          f"{'ROUTES' if sim.would_route else 'held'}"]
        lines += ["", "critique:"] + [f"  - {x}" for x in self.critique()]
        return "\n".join(lines)


def _section_key(title: str) -> str:
    """Deterministic custom sectionKey so conditions can reference the section."""
    return f"custom:{uuid.uuid5(uuid.NAMESPACE_URL, f'omega/{title}')}"


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


def plan(thesis: Thesis) -> StrategyPlan:
    """Turn a thesis into a validated report plus allocations."""
    m = _map()
    candle, inert = _split_by_timeframe_mode(thesis.modules)

    sections: list[CustomSection] = []
    if candle:
        title = f"{thesis.name[:44]} Signals"[:60]
        sections.append(CustomSection(
            title=title, sectionKey=_section_key(title), benchmarkTicker=None,
            columns=[Column.model_validate(s) for s in candle]))
    if inert:
        title = f"{thesis.name[:40]} Context"[:60]
        sections.append(CustomSection(
            title=title, sectionKey=_section_key(title), benchmarkTicker=None,
            columns=[Column.model_validate(s) for s in inert]))

    report = Report(anchor=thesis.anchor, sections=sections)

    # allocate only what the report can actually feed
    feedable = signals_for({s["metric"] for s in candle + inert})
    rules: list[Rule] = []
    for module, tier in thesis.weights.items():
        for sid in m["moduleSignals"].get(module, []):
            if sid in feedable and tier > 0:
                rules.append(Rule(signalId=sid, allocation=tier,
                                  required=sid in thesis.required))
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
                  crowd_leaning_down() if fade else tape_bullish(), verdict=None),
        condition(f"{prefix}_CTX_DOWN",
                  "Crowd leaning up - room to fade down" if fade else "Broad tape down",
                  crowd_leaning_up() if fade else tape_bearish(), verdict=None),
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
    return out


def plan_for_signals(signal_ids: list[str], *, name: str = "Ad-hoc", tier: int = 2,
                     gate: float = 0.65, anchor: str = "1h") -> StrategyPlan:
    """Work backwards: given signals you want to weight, build the report that feeds them."""
    m = _map()
    modules, unreachable = [], []
    for sid in signal_ids:
        module = next((k for k, v in m["moduleSignals"].items() if sid in v), None)
        if module is None or not m["moduleSatisfiedBy"].get(module):
            unreachable.append(sid)
        elif module not in modules:
            modules.append(module)
    thesis = Thesis(name=name, tagline="built from target signals", anchor=anchor, gate=gate,
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
    payload = plan_obj.wire()
    payload["_generatedBy"] = "omega.generate - LOCAL ONLY, not submitted"
    payload["_critique"] = plan_obj.critique()
    # cadence/regimeTimeframe have no field in the CREATE request; keep them as local
    # metadata. Underscore keys never go to the API - strip every "_"-prefixed key
    # before any submission.
    payload["_cadence"] = CADENCE_FOR_ANCHOR[plan_obj.thesis.anchor]
    payload["_regimeTimeframe"] = REGIME_TF_FOR_ANCHOR[plan_obj.thesis.anchor]
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)
