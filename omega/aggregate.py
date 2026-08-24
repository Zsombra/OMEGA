"""The strategy scorecard aggregation math.

Reverse-engineered from `simulate_aggregate_score` and confirmed by probe:
signals {score 1 @ alloc 3, score 0 @ alloc 1} -> aggregate 0.75 = (1*3 + 0*1) / (3 + 1).

    aggregate     = SUM(score_i * alloc_i) / SUM(alloc_i)
    attribution_i = (score_i * alloc_i) / SUM(score_j * alloc_j)
    wouldRoute    = aggregate >= gate

Allocation tier 0 carries ZERO weight - it is informational, not a light vote.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    label: str
    score: float          # [0, 1]
    allocation: int       # 0..3

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"{self.label}: score {self.score} outside [0,1]")
        if self.allocation not in (0, 1, 2, 3):
            raise ValueError(f"{self.label}: allocation {self.allocation} outside 0..3")


@dataclass(frozen=True)
class Attribution:
    label: str
    score: float
    allocation: int
    attribution_percent: int


@dataclass(frozen=True)
class AggregateResult:
    aggregate_score: float
    aggregate_score_percent: int
    gate: float
    gate_percent: int
    would_route: bool
    attributions: list[Attribution]

    def render(self) -> str:
        verdict = "ROUTES" if self.would_route else "held"
        lines = [f"aggregate {self.aggregate_score_percent}%  vs gate {self.gate_percent}%  -> {verdict}"]
        for a in sorted(self.attributions, key=lambda x: -x.attribution_percent):
            bar = "#" * round(a.attribution_percent / 4)
            lines.append(f"  {a.label:<28} a{a.allocation} score {a.score:>5.2f}  "
                         f"{a.attribution_percent:>3}% {bar}")
        return "\n".join(lines)


# `simulate_aggregate_score` accepts at most 20 signals per call. That is an API
# limit, NOT a property of the maths or of strategies: EL_ALAMEIN carries 32 non-zero
# allocations. So a full production scorecard cannot be checked with that tool in one
# call, and local aggregation is the only way to evaluate one.
SIMULATE_TOOL_MAX_SIGNALS = 20


def aggregate(signals: list[Signal], gate: float) -> AggregateResult:
    """Allocation-weighted mean of signal scores, compared against the routing gate.

    Accepts any number of signals. See SIMULATE_TOOL_MAX_SIGNALS for why the
    connector's own what-if tool cannot always be used to check the result.
    """
    if not signals:
        raise ValueError("expected at least one signal")
    if not 0.0 <= gate <= 1.0:
        raise ValueError(f"gate {gate} outside [0,1]")

    weight_total = sum(s.allocation for s in signals)
    contributions = [s.score * s.allocation for s in signals]
    contribution_total = sum(contributions)

    score = (contribution_total / weight_total) if weight_total else 0.0

    attributions = [
        Attribution(
            label=s.label,
            score=s.score,
            allocation=s.allocation,
            attribution_percent=(
                round(100 * contrib / contribution_total) if contribution_total else 0
            ),
        )
        for s, contrib in zip(signals, contributions)
    ]

    return AggregateResult(
        aggregate_score=score,
        aggregate_score_percent=round(100 * score),
        gate=gate,
        gate_percent=round(100 * gate),
        would_route=score >= gate,
        attributions=attributions,
    )


def minimum_score_to_route(signals: list[Signal], gate: float, label: str) -> float | None:
    """What `label` would have to score, holding the others fixed, to clear the gate.

    Returns None when the signal cannot move the outcome (allocation 0, or the gate
    is unreachable/already cleared regardless of this signal).
    """
    target = next((s for s in signals if s.label == label), None)
    if target is None:
        raise KeyError(f"no signal named {label!r}")
    if target.allocation == 0:
        return None

    weight_total = sum(s.allocation for s in signals)
    others = sum(s.score * s.allocation for s in signals if s.label != label)
    needed = (gate * weight_total - others) / target.allocation
    if needed <= 0:
        return 0.0
    if needed > 1:
        return None
    return needed
