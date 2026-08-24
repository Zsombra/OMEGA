"""Close the loop: which signals actually earned their allocation.

Joins each signal evaluation (`get_signal_log` -> `allEvaluatedSignals`) to the trade it
produced (`pipeline.outcome`), then aggregates per signal: how often it fired, how often
those trades won, and what they returned.

**The discipline this module exists to enforce.** The platform's own
`get_agent_conviction_calibration` refuses to report a win rate below 20 closed trades:

    "below the minimum sample size a group carries INSUFFICIENT_DATA and a sampleSize
     and NO rate at all - there is deliberately no win rate to read off a sample too
     small to support one."

`omega.performance` mirrors that exactly. Below `MIN_SAMPLE` firings a signal reports
INSUFFICIENT_DATA and no rate, and `recommend_allocations` returns nothing for it. A
3-from-4 win rate is not a 75% edge, and a tool that renders it as one is worse than no
tool. Wilson intervals are reported for READY signals so the uncertainty stays visible
even once the sample is large enough to speak.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from .contract import ROOT

# The platform's own threshold, from get_agent_conviction_calibration.minSampleSize.
MIN_SAMPLE = 20
Z = 1.96  # 95% Wilson interval


def wilson_interval(wins: int, n: int, z: float = Z) -> tuple[float, float]:
    """Wilson score interval - honest about small samples where normal approx is not."""
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


@dataclass
class SignalEdge:
    signal_id: str
    fired: int = 0
    wins: int = 0
    losses: int = 0
    net_pnl: float = 0.0
    attribution_sum: float = 0.0
    not_fired_wins: int = 0
    not_fired_losses: int = 0

    @property
    def readiness(self) -> str:
        return "READY" if self.fired >= MIN_SAMPLE else "INSUFFICIENT_DATA"

    @property
    def win_rate(self) -> float | None:
        """None below MIN_SAMPLE - deliberately, not as a missing value."""
        if self.readiness != "READY" or self.fired == 0:
            return None
        return self.wins / self.fired

    @property
    def confidence_interval(self) -> tuple[float, float] | None:
        if self.readiness != "READY":
            return None
        return wilson_interval(self.wins, self.fired)

    @property
    def avg_net_pnl(self) -> float | None:
        if self.readiness != "READY" or self.fired == 0:
            return None
        return self.net_pnl / self.fired

    @property
    def avg_attribution(self) -> float | None:
        if self.fired == 0:
            return None
        return self.attribution_sum / self.fired

    @property
    def lift(self) -> float | None:
        """Win rate when it fired minus win rate when it did not.

        The signal-quality question is not "do trades win when this fires" - in a winning
        strategy everything looks good. It is whether trades win MORE when it fires.
        """
        if self.readiness != "READY":
            return None
        base_n = self.not_fired_wins + self.not_fired_losses
        if base_n < MIN_SAMPLE:
            return None
        return (self.wins / self.fired) - (self.not_fired_wins / base_n)

    def __str__(self) -> str:
        if self.readiness != "READY":
            return f"{self.signal_id:<32} INSUFFICIENT_DATA  fired={self.fired} (need {MIN_SAMPLE})"
        lo, hi = self.confidence_interval
        lift = f"{self.lift:+.0%}" if self.lift is not None else "n/a"
        return (f"{self.signal_id:<32} fired={self.fired:<4} "
                f"win={self.win_rate:.0%} [{lo:.0%}-{hi:.0%}]  "
                f"avgPnl={self.avg_net_pnl:+.3f}  lift={lift}")


@dataclass
class EdgeReport:
    agent_name: str
    observations: int
    with_outcome: int
    edges: dict[str, SignalEdge] = field(default_factory=dict)
    totals: dict = field(default_factory=dict)

    @property
    def ready(self) -> list[SignalEdge]:
        return sorted((e for e in self.edges.values() if e.readiness == "READY"),
                      key=lambda e: -(e.win_rate or 0))

    @property
    def insufficient(self) -> list[SignalEdge]:
        return sorted((e for e in self.edges.values() if e.readiness != "READY"),
                      key=lambda e: -e.fired)

    def trades_needed(self) -> dict:
        """How many more closed trades before anything can be concluded.

        A signal needs MIN_SAMPLE firings. If it fires in a fraction f of trades, that
        takes MIN_SAMPLE / f trades. Reported for the signals closest to readiness.
        """
        out = {}
        for e in self.edges.values():
            if e.readiness == "READY" or self.with_outcome == 0:
                continue
            rate = e.fired / self.with_outcome
            out[e.signal_id] = (round(MIN_SAMPLE / rate) if rate > 0 else None)
        return out

    def render(self) -> str:
        lines = [
            f"{self.agent_name}",
            f"observations {self.observations}  |  with a closed trade {self.with_outcome}"
            f"  |  minimum sample {MIN_SAMPLE}",
            "",
        ]
        if self.ready:
            lines.append(f"READY ({len(self.ready)}):")
            lines += [f"  {e}" for e in self.ready]
        else:
            lines.append("READY (0): no signal has fired often enough to support a rate.")
        lines.append("")
        top = self.insufficient[:8]
        if top:
            lines.append(f"INSUFFICIENT_DATA ({len(self.insufficient)}), most-fired first:")
            lines += [f"  {e}" for e in top]
        need = {k: v for k, v in self.trades_needed().items() if v}
        if need:
            best = sorted(need.items(), key=lambda kv: kv[1])[:3]
            lines += ["", "closest to a readable rate:"]
            lines += [f"  {k:<32} ~{v} closed trades at its current fire rate"
                      for k, v in best]
        return "\n".join(lines)


def analyse(observations: list[dict], *, agent_name: str = "agent",
            totals: dict | None = None) -> EdgeReport:
    """Aggregate per-signal edge from signal-log/outcome observations.

    Each observation: {signals: [{id, triggered, attributionPercent}], outcome: {...}|None}
    """
    report = EdgeReport(agent_name=agent_name, observations=len(observations),
                        with_outcome=0, totals=totals or {})
    for obs in observations:
        outcome = obs.get("outcome")
        if not outcome:
            continue
        won = outcome.get("tradeOutcome") == "WIN"
        pnl = float(outcome.get("netPnl") or 0.0)
        report.with_outcome += 1
        for s in obs.get("signals", []):
            edge = report.edges.setdefault(s["id"], SignalEdge(signal_id=s["id"]))
            if s.get("triggered"):
                edge.fired += 1
                edge.attribution_sum += float(s.get("attributionPercent") or 0)
                edge.net_pnl += pnl
                if won:
                    edge.wins += 1
                else:
                    edge.losses += 1
            elif won:
                edge.not_fired_wins += 1
            else:
                edge.not_fired_losses += 1
    return report


@dataclass(frozen=True)
class AllocationSuggestion:
    signal_id: str
    current: int
    suggested: int
    reason: str

    def __str__(self) -> str:
        arrow = "->" if self.current != self.suggested else "=="
        return f"{self.signal_id:<32} {self.current} {arrow} {self.suggested}   {self.reason}"


def recommend_allocations(report: EdgeReport, current: dict[str, int],
                          *, baseline_win_rate: float | None = None
                          ) -> list[AllocationSuggestion]:
    """Suggest allocation changes - ONLY for signals with a readable sample.

    Returns an empty list when nothing is READY. That is the correct answer to a small
    sample, not a failure to produce output.
    """
    out: list[AllocationSuggestion] = []
    base = baseline_win_rate
    if base is None:
        base = (report.totals or {}).get("winRate")
    for edge in report.ready:
        lo, hi = edge.confidence_interval
        cur = current.get(edge.signal_id, 0)
        if base is not None and lo > base:
            suggested = min(3, cur + 1)
            reason = (f"win rate {edge.win_rate:.0%}, and even the low end of its 95% "
                      f"interval ({lo:.0%}) beats the {base:.0%} baseline")
        elif base is not None and hi < base:
            suggested = max(0, cur - 1)
            reason = (f"win rate {edge.win_rate:.0%}, and even the high end ({hi:.0%}) "
                      f"trails the {base:.0%} baseline")
        else:
            suggested = cur
            reason = (f"win rate {edge.win_rate:.0%} but the interval "
                      f"[{lo:.0%}-{hi:.0%}] straddles the baseline - not separable yet")
        out.append(AllocationSuggestion(edge.signal_id, cur, suggested, reason))
    return out


# --- fetching -------------------------------------------------------------
FETCH_RECIPE = """\
omega cannot call MCP tools itself. To build an observation set, run these read-only
calls and save the result as JSON matching data/performance/dunkirk_sample.json:

  1. list_intelligence_agents()                 -> agent ids
  2. get_signal_performance({agentId})          -> agentTotals
  3. list_trade_outcomes({agentId, limit: 50})  -> trades, each with a signalLogId
  4. for each signalLogId:
       get_signal_log({agentId, logId})
       -> observation.signals   from log.scorecard.allEvaluatedSignals
                                 (+ attributionPercent from log.attributions)
       -> observation.outcome   from log.pipeline.outcome
  5. get_agent_conviction_calibration({agentId}) -> the platform's own readiness view

Every one of those is read-only. None of them consumes strategy or agent quota.
"""


def load_sample(path: str | Path | None = None) -> EdgeReport:
    p = Path(path) if path else ROOT / "data" / "performance" / "dunkirk_sample.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    return analyse(d["observations"], agent_name=d.get("agentName", "agent"),
                   totals=d.get("agentTotals", {}))
