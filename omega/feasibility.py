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
    captured_at: str = ""

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


def load_captures(interval: str | None = None) -> list[Observation]:
    """Every capture file, flattened - each Observation stamped with its capture.

    `load_observations` reads one file and is the single-instant view. This reads
    all of them, so the same (ticker, interval) pair appears once per timepoint.
    Anything ranking over the result must therefore separate the two axes: five
    coins at one instant and one coin at five instants both give you n=5, and they
    support completely different conclusions.
    """
    out: list[Observation] = []
    for f in sorted((_ROOT / "data" / "performance").glob("coin_observations*.json")):
        raw = json.loads(f.read_text(encoding="utf-8"))
        stamp = raw.get("_capturedAt", f.stem)
        out += [Observation(o["ticker"], o["interval"], o["scores"],
                            o.get("capturedAt", stamp))
                for o in raw["observations"]]
    return [o for o in out if interval is None or o.interval == interval]


def stability(observations: Sequence[Observation]) -> dict[str, tuple[int, int]]:
    """For each signal: (distinct coins it fired on, distinct timepoints it fired at)."""
    coins: dict[str, set[str]] = {}
    times: dict[str, set[str]] = {}
    for o in observations:
        for sid in o.scores:
            coins.setdefault(sid, set()).add(f"{o.ticker}/{o.interval}")
            times.setdefault(sid, set()).add(o.captured_at)
    return {sid: (len(coins[sid]), len(times[sid])) for sid in coins}


def temporal_estimates(rules: Iterable, observations: Sequence[Observation]
                       ) -> dict[str, "TemporalEstimate"]:
    """Per signal: a coin-averaged leverage estimate plus both coverage axes.

    THE ESTIMATE AVERAGES WITHIN COIN FIRST
    ---------------------------------------
    Pooling every observation into one list treats a second look at BTC as
    independent evidence about coins. It is not - it is a second look at BTC.
    So each coin is collapsed to its own mean across the timepoints where the
    signal fired, and the reported estimate is the mean OF THOSE COIN MEANS.
    A coin captured twice therefore carries exactly the weight of a coin
    captured once, which is the only thing that makes `coins` a real n.

    THE NOISE FLOOR IS MEASURED, NOT ASSUMED
    ----------------------------------------
    Wherever a signal fired on the same coin at two different timepoints, the
    gap between those two readings is drift the market handed us for free -
    same coin, same rules, only the clock changed. Averaging the half-gap over
    such coins gives that signal its own noise floor. An estimate smaller than
    its own noise floor has no direction worth reporting, however many coins it
    fired on - which is a different question from whether it fired widely.
    """
    per: dict[str, dict[str, dict[str, float]]] = {}
    for obs in observations:
        coin = f"{obs.ticker}/{obs.interval}"
        for lv in leverage(rules, obs):
            per.setdefault(lv.signal_id, {}).setdefault(coin, {})[obs.captured_at] = lv.delta_pp

    out: dict[str, TemporalEstimate] = {}
    for sid, by_coin in per.items():
        coin_means = [sum(t.values()) / len(t) for t in by_coin.values()]
        estimate = sum(coin_means) / len(coin_means)
        # half-range per coin, over coins that saw this signal fire more than once
        gaps = [(max(t.values()) - min(t.values())) / 2
                for t in by_coin.values() if len(t) > 1]
        out[sid] = TemporalEstimate(
            signal_id=sid,
            estimate_pp=estimate,
            coins=len(by_coin),
            times=len({stamp for t in by_coin.values() for stamp in t}),
            noise_pp=(sum(gaps) / len(gaps)) if gaps else None,
        )
    return out


@dataclass(frozen=True)
class TemporalEstimate:
    """One signal's leverage, with the evidence behind it kept visible."""

    signal_id: str
    estimate_pp: float
    coins: int          # distinct (ticker, interval) pairs it fired on
    times: int          # distinct capture stamps it fired at
    noise_pp: float | None   # None when no coin saw it fire twice

    @property
    def resolved(self) -> bool:
        """Is the sign of this estimate bigger than the drift behind it?"""
        return self.noise_pp is not None and abs(self.estimate_pp) > self.noise_pp

    @property
    def verdict(self) -> str:
        if not self.resolved:
            return "?      "
        return "DRAG   " if self.estimate_pp > 0 else "carries"


def temporal_drag_ranking(rules: Iterable, observations: Sequence[Observation],
                          min_coins: int = 3) -> str:
    """Rank drag/carry across BOTH axes: how many coins, and how many timepoints.

    `drag_ranking` pools every observation into one flat list, so its "fired on
    n/5" collapses the two axes into one number. Feed it two captures and 3 coins
    x 2 times becomes indistinguishable from 6 coins x 1 time - the
    pseudoreplication trap.

    Measured on the first two captures (~42 minutes apart, apex-imported rules):

        fired on   signals   mean |shift|   max |shift|
          1/5           19        0.99pp        3.97pp
          2/5            8        0.65pp        2.68pp
          3/5            9        0.69pp        2.22pp
          4/5            2        0.18pp        0.33pp

    Coverage predicts how far the MAGNITUDE moves. It does not predict SIGN
    stability - `ma_ema_aligned_bull` fired on 3 coins and still crossed zero
    (+0.63 -> -0.68) because its magnitude sits inside its own drift. The two
    failure modes are gated separately here: `min_coins` promotes on breadth,
    the measured noise floor decides whether a direction is claimed at all.
    """
    est = temporal_estimates(rules, observations)
    n_coins = len({f"{o.ticker}/{o.interval}" for o in observations})
    n_times = len({o.captured_at for o in observations})
    need = min(min_coins, n_coins)

    rows = sorted(est.values(), key=lambda e: -e.estimate_pp)
    consistent = [e for e in rows if e.coins >= need]
    occasional = [e for e in rows if e.coins < need]

    def fmt(e: TemporalEstimate) -> str:
        cover = f"{e.coins} coin{'s' if e.coins != 1 else ' '} x {e.times} time{'s' if e.times != 1 else ' '}"
        why = ""
        if not e.resolved:
            why = ("   unresolved: no single coin fired it at both timepoints"
                   if e.noise_pp is None
                   else f"   unresolved: |{e.estimate_pp:+.2f}| within drift {e.noise_pp:.2f}pp")
        return f"  {e.verdict} {e.signal_id:<32}{e.estimate_pp:+6.2f}pp   {cover}{why}"

    lines = [f"leverage across {n_coins} coins x {n_times} timepoints "
             f"(positive = removing it RAISES the aggregate)",
             "  each coin is averaged across time before coins are averaged together,",
             "  so a coin captured twice still counts once", ""]
    lines.append(f"CONSISTENT - fired on at least {need} of {n_coins} coins:")
    lines += [fmt(e) for e in consistent] or ["  (none)"]
    if occasional:
        lines += ["", f"OCCASIONAL - fired on fewer than {need} coins; too few coins "
                      "to rank against the above:"]
        lines += [fmt(e) for e in occasional]
    lines += ["", "  A '?' means the estimate is smaller than the drift measured on the "
                  "same coin", "  across timepoints - it fired, but this sample cannot "
                  "say in which direction."]
    return chr(10).join(lines)


def load_rules(name: str) -> tuple[dict[str, int], float]:
    """A real captured scorecard: returns (allocations, minAggregateScore)."""
    raw = json.loads((_ROOT / "data" / "performance" / "strategy_rules_sample.json")
                     .read_text(encoding="utf-8"))
    s = raw["strategies"][name]
    return s["allocations"], s["minAggregateScore"]
