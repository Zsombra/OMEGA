"""Would this strategy route, and which signals are holding it back?

THE DENOMINATOR IS THE FIRED SET
--------------------------------
The aggregate is a weighted mean over the signals that ACTUALLY FIRED. Signals that
did not fire are excluded entirely - from the numerator and the denominator both:

    aggregate = SUM(score_i x alloc_i) / SUM(alloc_i)     over fired signals only

This project previously assumed the denominator carried every non-zero allocation,
which made unfired signals look like dead weight dragging the score down. That was
wrong, and it inverted the advice that followed from it. Four confirmations:

    Dunkirk log     aggregateScore 0.68; numerator 14.2810 / fired alloc 21 = 0.680
                                                           / all   alloc 119 = 0.120
    BTC preview     46%;  sum of fired scores / 14 fired = 45.7%   (/84 = 7.6%)
    SOL preview     52%;  / 9 fired  = 52.0%
    ETH preview     56%;  / 19 fired = 55.8%

`simulate_aggregate_score` agrees: it computes over exactly the signal set you hand
it. The live engine hands it the fired set.

WHAT FOLLOWS
------------
1. Unfired signals are FREE. A signal with no feeding column, or one that simply
   never triggers, costs nothing. There is no allocation-dilution penalty and no
   structural ceiling - the maximum aggregate is 1.0 for any scorecard.

2. The real enemy is a signal that FIRES with a LOW score. Because the aggregate
   is a mean, any fired signal scoring below the current aggregate pulls it down.
   That is the exact condition:

       a fired signal helps  <=>  its score > the current aggregate

3. Allocating both directions of a pair guarantees dilution. In any given market one
   side fires meaningfully and the other fires weakly, and the weak side drags the
   mean toward the middle.

The only genuine unreachability left is a `required` signal that no column feeds -
see blocking_requirements().

None of this measures whether a strategy is PROFITABLE. It measures whether it
routes. omega.performance owns profitability, and refuses to answer below 20 closed
trades.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

__all__ = [
    "Observation", "CoinResult", "Sweep", "simulate",
    "Leverage", "leverage", "drag_ranking", "blocking_requirements",
    "load_observations", "load_rules", "FETCH_RECIPE",
]

_ROOT = Path(__file__).resolve().parents[1]

FETCH_RECIPE = """\
Read-only. Consumes no strategy or agent quota, writes nothing.

  1. get_coin_signal_preview({ticker, interval})     # per coin in your sample
       -> allEvaluatedSignals[] : {id, score, triggered, effectiveAllocation: 1}
       Omit agentId: you want the UNWEIGHTED scores so you can apply your own
       allocations. Passing agentId overlays an existing agent's weighting instead.

  2. Observation.from_preview(payload, interval)

  3. simulate(rules, gate, observations)   -> would it route, per coin?
     drag_ranking(rules, observations)     -> which fired signals pull the mean down?
     blocking_requirements(rules, in_report) -> any required signal with no column?

Keep one interval per sweep: readings from different timeframes are different bars.
"""


# --- inputs -----------------------------------------------------------------

def _weights(rules: Iterable) -> dict[str, int]:
    """Accept omega.types.Rule, plain dicts, or (signal_id, allocation) pairs."""
    out: dict[str, int] = {}
    for r in rules:
        if hasattr(r, "signalId"):
            sid, alloc = r.signalId, r.allocation
        elif isinstance(r, Mapping):
            sid, alloc = r["signalId"], r["allocation"]
        else:
            sid, alloc = r
        if alloc:                      # tier 0 is weightless: never in either sum
            out[sid] = alloc
    return out


@dataclass(frozen=True)
class Observation:
    """One coin's unweighted scorecard from get_coin_signal_preview."""

    ticker: str
    interval: str
    scores: Mapping[str, float]

    @classmethod
    def from_preview(cls, payload: Mapping, interval: str = "") -> "Observation":
        # Store only non-zero scores: an absent signal did not fire, and the
        # fired-set semantics make "absent" and "scored 0" the same thing.
        return cls(
            ticker=payload["coinTicker"],
            interval=interval,
            scores={s["id"]: float(s["score"])
                    for s in payload["allEvaluatedSignals"] if s["score"]},
        )


def _aggregate(scores: Mapping[str, float], w: Mapping[str, int]) -> tuple[float, int, int]:
    """The engine's aggregate: a weighted mean over FIRED signals only."""
    num = den = 0.0
    fired = 0
    for sid, alloc in w.items():
        s = scores.get(sid, 0.0)
        if s <= 0.0:                   # did not fire -> excluded from both sums
            continue
        num += s * alloc
        den += alloc
        fired += 1
    return (num / den if den else 0.0), fired, int(den)


# --- the sweep --------------------------------------------------------------

@dataclass(frozen=True)
class CoinResult:
    ticker: str
    aggregate: float
    routes: bool
    fired: int
    fired_weight: int
    top: list[tuple[str, int]]


@dataclass(frozen=True)
class Sweep:
    gate: float
    results: list[CoinResult]
    never_fired: list[str]

    @property
    def routed(self) -> int:
        return sum(1 for r in self.results if r.routes)

    @property
    def best(self) -> float:
        return max((r.aggregate for r in self.results), default=0.0)

    def render(self) -> str:
        n = len(self.results)
        lines = [
            f"gate {self.gate * 100:.1f}%   {self.routed}/{n} coins would route   "
            f"best observed {self.best * 100:.1f}%",
            "",
        ]
        for r in sorted(self.results, key=lambda x: -x.aggregate):
            mark = "ROUTES" if r.routes else "  held"
            carry = ", ".join(f"{s} {p}%" for s, p in r.top[:3])
            lines.append(f"  {mark}  {r.ticker:<6} {r.aggregate * 100:>5.1f}%  "
                         f"{r.fired:>2} fired (weight {r.fired_weight:>2})   {carry}")
        if self.never_fired:
            lines += ["", f"  allocated but never fired across {n} coins - COSTLESS, "
                          "not dead weight:"]
            lines.append(f"    {len(self.never_fired)} signals; they enter neither sum")
        lines += ["", "  A snapshot of one moment's tape - routing frequency, "
                      "NOT profitability."]
        return "\n".join(lines)


def simulate(rules: Iterable, gate: float,
             observations: Sequence[Observation]) -> Sweep:
    """Apply a hypothetical allocation vector to real unweighted scorecards."""
    w = _weights(rules)
    results: list[CoinResult] = []
    fired_anywhere: set[str] = set()

    for obs in observations:
        agg, fired, weight = _aggregate(obs.scores, w)
        fired_anywhere |= {s for s in w if obs.scores.get(s, 0.0) > 0}
        num = sum(obs.scores.get(s, 0.0) * a for s, a in w.items())
        top = sorted(
            ((s, round(obs.scores.get(s, 0.0) * a / num * 100))
             for s, a in w.items() if obs.scores.get(s, 0.0) > 0),
            key=lambda kv: -kv[1]) if num else []
        results.append(CoinResult(obs.ticker, agg, agg >= gate, fired, weight, top))

    return Sweep(gate, results, sorted(s for s in w if s not in fired_anywhere))


# --- leverage: what each fired signal does to the mean -----------------------

@dataclass(frozen=True)
class Leverage:
    signal_id: str
    score: float
    allocation: int
    aggregate_without: float
    delta_pp: float          # percentage points the aggregate MOVES if removed

    @property
    def is_drag(self) -> bool:
        """True when removing this signal would RAISE the aggregate."""
        return self.delta_pp > 0


def leverage(rules: Iterable, observation: Observation) -> list[Leverage]:
    """Per-signal marginal effect on one coin's aggregate.

    A fired signal helps exactly when its score exceeds the aggregate, because the
    aggregate is a weighted mean. Everything below the mean is pulling it down.
    """
    w = _weights(rules)
    base, _, _ = _aggregate(observation.scores, w)
    out: list[Leverage] = []
    for sid, alloc in w.items():
        s = observation.scores.get(sid, 0.0)
        if s <= 0.0:
            continue                   # unfired signals have no leverage either way
        without = {k: v for k, v in observation.scores.items() if k != sid}
        agg_without, _, _ = _aggregate(without, w)
        out.append(Leverage(sid, s, alloc, agg_without, (agg_without - base) * 100))
    return sorted(out, key=lambda l: -l.delta_pp)


def drag_ranking(rules: Iterable, observations: Sequence[Observation],
                 min_coverage: float = 0.5) -> str:
    """Which fired signals cost you the most aggregate, across the sample.

    Split by COVERAGE, not just magnitude. A signal that fired on one coin out of
    five has a mean computed from a single observation - that is noise wearing a
    decimal point, and ranking it beside a signal that fired on all five invites
    exactly the wrong conclusion. `min_coverage` is the fraction of the sample a
    signal must fire on to be reported as consistent evidence.
    """
    n = len(observations)
    totals: dict[str, list[float]] = {}
    for obs in observations:
        for lv in leverage(rules, obs):
            totals.setdefault(lv.signal_id, []).append(lv.delta_pp)

    need = max(2, round(n * min_coverage))
    rows = sorted(((sum(v) / len(v), len(v), sid) for sid, v in totals.items()),
                  key=lambda r: -r[0])
    consistent = [r for r in rows if r[1] >= need]
    occasional = [r for r in rows if r[1] < need]

    def fmt(r):
        mean_pp, fired_on, sid = r
        tag = "DRAG   " if mean_pp > 0 else "carries"
        return f"  {tag} {sid:<34} {mean_pp:+6.2f}pp   fired on {fired_on}/{n}"

    lines = [f"leverage across {n} coins (positive = removing it RAISES the aggregate)", ""]
    lines.append(f"CONSISTENT - fired on at least {need} of {n}:")
    lines += [fmt(r) for r in consistent] or ["  (none)"]
    if occasional:
        lines += ["", f"OCCASIONAL - fired on fewer than {need}; too few observations to "
                      "rank against the above:"]
        lines += [fmt(r) for r in occasional]
    lines += ["", "  Removing a drag signal raises the mean on every coin where it fires "
                  "below the aggregate,", "  and cannot lower it anywhere - an unfired "
                  "signal is costless."]
    return "\n".join(lines)


# --- the one genuine unreachability -----------------------------------------

def blocking_requirements(rules: Iterable, in_report: set[str]) -> list[str]:
    """Signals marked `required` that no column feeds - the strategy never routes.

    This is the only structural block left once the fired-set semantics are correct.
    A required signal that cannot fire is an unsatisfiable precondition.
    """
    blocked = []
    for r in rules:
        required = getattr(r, "required", None)
        if required is None and isinstance(r, Mapping):
            required = r.get("required")
        sid = getattr(r, "signalId", None) or (r["signalId"] if isinstance(r, Mapping) else None)
        if required and sid and sid not in in_report:
            blocked.append(sid)
    return blocked


# --- captured fixtures ------------------------------------------------------

def load_observations(interval: str | None = None) -> list[Observation]:
    """Live scorecards captured in data/performance/coin_observations.json."""
    raw = json.loads((_ROOT / "data" / "performance" / "coin_observations.json")
                     .read_text(encoding="utf-8"))
    out = [Observation(o["ticker"], o["interval"], o["scores"])
           for o in raw["observations"]]
    return [o for o in out if interval is None or o.interval == interval]


def load_rules(name: str) -> tuple[dict[str, int], float]:
    """A real captured scorecard: returns (allocations, minAggregateScore)."""
    raw = json.loads((_ROOT / "data" / "performance" / "strategy_rules_sample.json")
                     .read_text(encoding="utf-8"))
    s = raw["strategies"][name]
    return s["allocations"], s["minAggregateScore"]
