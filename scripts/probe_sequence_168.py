"""OMEGA read-only probe of the `SEQUENCE` condition group contract 168 added (2026-11-12).

The stage and the preview share one condition grammar (data/derived/condition_vocabulary_108.json
`previewConditions.sameGrammarAsStage`), so the preview measures it with no draft: the trend-continuation preset's
preview request with ONE probe condition added (`SEQ_PROBE`), every other condition as generated. Each probe records
what the preview answers - accepted or the refusal - and, when accepted, the probe condition's outcome per coin
(`authoring.conditionOutcomes`, its `sequence` evidence: within, timeframe, steps with the bar each matched) and the
trade register's row for it (`tradeConditions.register`).

What it asks: does SEQUENCE take one member, does it take `n`, what `within` defaults to and its bounds, whether
`within` is refused on another op, whether a SEQUENCE nests in ALL and holds a conditionRef, and whether it carries a
verdict.

Read-only: preview_strategy_report over mcporter (battlegrid-anbu), probe_authoring_148's call / classify / version
rules. Writes data/audit/sequence_probe_<MAJOR>_<PROBE_DATE>.json. One run per PROBE_DATE (PROBE_OVERWRITE=1 replaces).

    EXTRACTION_TRANSPORT=runtime MCPORTER_DIST=<...> PROBE_CONTRACT=169.4.0 PROBE_DATE=2026-11-12 \
        python -m scripts.probe_sequence_168
"""
from __future__ import annotations

import copy
import json
import os
import sys
import time

from scripts import probe_authoring_148 as P

TICKERS = ["BTC", "ETH", "SOL"]
RECORD_OUT = f"data/audit/sequence_probe_{P.MAJOR}_{P.PROBE_DATE}.json"
HOLD = {"atLeast": 1, "of": 1}


def base_request() -> tuple[dict, list[dict]]:
    """The preset's preview request (explicit tickers) and two clauses of its own conditions to sequence."""
    from omega.generate import PRESETS, plan
    req = plan(PRESETS["trend-continuation"]).preview_request()
    req["coinSelection"] = {"mode": "explicit", "tickers": TICKERS}
    req["detail"] = "detailed"
    clauses = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("kind") == "clause":
                clauses.append(node)
            for member in node.get("members") or []:
                walk(member)

    for condition in req["source"]["conditions"]:
        walk(condition["definition"])
    # the per-coin clauses only: the Market Tape (mktBreadth) and Stablecoin Par (parDev) sections read the market and
    # a reference pair, not the coin's own bars, which is what a sequence steps through
    context = {col_header for section in req["source"]["sections"]
               if section.get("kind") == "custom" and (section.get("marketScope") or section.get("benchmarkTicker"))
               for col_header in _headers(section)}
    distinct = []
    for clause in clauses:
        header = clause["column"]["header"]
        if header not in context and header not in {c["column"]["header"] for c in distinct}:
            distinct.append(clause)
    return req, distinct


def _headers(section) -> set[str]:
    """The headers a context section's columns emit, as omega.fanout predicts them."""
    from omega.contract import load
    from omega.fanout import outputs_for
    from omega.types import Column
    return {o.header for col in section.get("columns") or [] for o in outputs_for(Column(**col), load())}


def group(op, members, **extra):
    return {"kind": "group", "op": op, "hold": dict(HOLD), "members": members, **extra}


def condition(definition, **extra):
    return {"conditionKey": "SEQ_PROBE", "name": "sequence probe", "definition": definition, "verdict": None,
            "required": False, "exitSide": None, **extra}


def probes(clauses):
    a, b, c = (copy.deepcopy(clauses[i]) for i in range(3))
    ref = {"kind": "conditionRef", "conditionKey": "TC_RISK_ON"}
    return [
        ("X.seq2", condition(group("SEQUENCE", [a, b]))),
        ("X.seq2.within2", condition(group("SEQUENCE", [a, b], within=2))),
        ("X.seq2.within5", condition(group("SEQUENCE", [a, b], within=5))),
        ("X.seq2.within1", condition(group("SEQUENCE", [a, b], within=1))),
        ("X.seq2.within64", condition(group("SEQUENCE", [a, b], within=64))),
        ("X.seq2.within1000", condition(group("SEQUENCE", [a, b], within=1000))),
        ("X.seq3.within10", condition(group("SEQUENCE", [a, b, c], within=10))),
        ("X.seq1", condition(group("SEQUENCE", [a]))),
        ("X.seq2.n1", condition(group("SEQUENCE", [a, b], n=1))),
        ("X.all.within5", condition(group("ALL", [a, b], within=5))),
        ("X.nof.within5", condition(group("N_OF", [a, b], n=1, within=5))),
        ("X.seq.in.all", condition(group("ALL", [group("SEQUENCE", [a, b], within=5), c]))),
        ("X.seq.with.ref", condition(group("SEQUENCE", [ref, a], within=5))),
        ("X.seq.hold2of3", condition({**group("SEQUENCE", [a, b], within=5), "hold": {"atLeast": 2, "of": 3}})),
        ("X.seq.verdict.long", condition(group("SEQUENCE", [a, b], within=5), verdict="LONG")),
        ("X.seq.required", condition(group("SEQUENCE", [a, b], within=5), required=True)),
        ("X.seq.of.groups", condition(group("SEQUENCE", [group("ALL", [a]), group("ANY", [b, c])], within=5))),
    ]


def probes_round2(clauses):
    """The second round (SEQ_ROUND=2), after the first answered: three of its probes were confounded - one member and
    `n` were sent without the `within` every sequence requires, and the verdict was sent as LONG (the enum is UP / DOWN
    / NEITHER) - and the window's upper edge was not asked."""
    a, b, c = (copy.deepcopy(clauses[i]) for i in range(3))
    return [
        ("X2.seq1.within5", condition(group("SEQUENCE", [a], within=5))),
        ("X2.seq2.n1.within5", condition(group("SEQUENCE", [a, b], n=1, within=5))),
        ("X2.seq.verdict.up", condition(group("SEQUENCE", [a, b], within=5), verdict="UP")),
        ("X2.seq.verdict.neither", condition(group("SEQUENCE", [a, b], within=5), verdict="NEITHER")),
        ("X2.seq.exit", condition(group("SEQUENCE", [a, b], within=5), verdict="UP", exitSide="DOWN")),
        ("X2.seq.in.seq", condition(group("SEQUENCE", [group("SEQUENCE", [a, b], within=3), c], within=6))),
        ("X2.not.within5", condition(group("NOT", [a], within=5))),
        ("X2.seq.within2436", condition(group("SEQUENCE", [a, b], within=2436))),
        ("X2.seq.within2500", condition(group("SEQUENCE", [a, b], within=2500))),
        ("X2.seq.within100000", condition(group("SEQUENCE", [a, b], within=100000))),
        ("X2.seq64.members", condition(group("SEQUENCE", [copy.deepcopy(a) for _ in range(64)], within=100))),
    ]


def probes_round3(clauses):
    """The third round (SEQ_ROUND=3): the exit rule (verdict null, exitSide set - round 2 sent exitSide DOWN, outside
    the LONG / SHORT / BOTH enum), the platform's own remedy for a nested sequence (its own condition, referenced), and
    how the condition frame reads are counted - every count probe is sized past the 5048 cap so the refusal states the
    count: within x steps (round 2: 2 x 100000 + 11, 64 x 100 + 11), a step's own hold, a prior-bar step, a group step,
    and a plain group's hold over its members."""
    a, b, c = (copy.deepcopy(clauses[i]) for i in range(3))

    def held(clause, at_least, of):
        return {**copy.deepcopy(clause), "hold": {"atLeast": at_least, "of": of}}

    enters = {"kind": "clause", "column": copy.deepcopy(a["column"]), "op": "enters", "label": a.get("label"),
              "hold": dict(HOLD)}
    seq = condition(group("SEQUENCE", [a, b], within=5))
    ref = {"kind": "conditionRef", "conditionKey": "SEQ_PROBE"}
    return [
        ("X3.exit.short", condition(group("SEQUENCE", [a, b], within=5), exitSide="SHORT")),
        ("X3.exit.both", condition(group("SEQUENCE", [a, b], within=5), exitSide="BOTH")),
        ("X3.exit.verdict.up", condition(group("SEQUENCE", [a, b], within=5), verdict="UP", exitSide="SHORT")),
        ("X3.ref.from.group", [seq, {**condition(group("ALL", [ref, c])), "conditionKey": "SEQ_USER"}]),
        ("X3.ref.from.exit", [seq, {**condition(ref, exitSide="LONG"), "conditionKey": "CLOSE_ON_SEQ_PROBE"}]),
        ("X3.reads.seq3.w2449", condition(group("SEQUENCE", [a, b, c], within=2449))),
        ("X3.reads.step.hold2of3", condition(group("SEQUENCE", [held(a, 2, 3), b, c], within=2449))),
        ("X3.reads.step.hold3of3", condition(group("SEQUENCE", [held(a, 3, 3), b, c], within=2449))),
        ("X3.reads.step.prior", condition(group("SEQUENCE", [enters, b, c], within=2449))),
        ("X3.reads.step.group", condition(group("SEQUENCE", [group("ALL", [a, b]), c, held(c, 1, 1)], within=2449))),
        ("X3.reads.step.grouphold", condition(group("SEQUENCE", [{**group("ALL", [a, b]), "hold": {"atLeast": 2,
                                                                                                    "of": 3}},
                                                                  c, held(c, 1, 1)], within=2449))),
        ("X3.reads.group.hold", condition({**group("ALL", [a, b]), "hold": {"atLeast": 1, "of": 3000}})),
        ("X3.reads.clause.hold", condition(group("ALL", [held(a, 1, 5100), b]))),
    ]


def probes_round4(clauses):
    """The fourth round (SEQ_ROUND=4): round 3 counted a group hold over plain clauses (of x clauses) and a prior-bar
    step (within + 1), which a product and a span both fit. Sized so both are refused and the count tells them apart:
    a held clause under a held group (product 3 x 2400 + 2400 + 2400, span 2402 + 2400 + 2400), a prior-bar clause
    under a held group (product 2 x 2400 + ..., span 2401 + ...), and what a conditionRef step costs in a sequence."""
    a, b, c = (copy.deepcopy(clauses[i]) for i in range(3))
    enters = {"kind": "clause", "column": copy.deepcopy(a["column"]), "op": "enters", "label": a.get("label"),
              "hold": dict(HOLD)}
    ref = {"kind": "conditionRef", "conditionKey": "TC_RISK_ON"}
    return [
        ("X4.reads.nested.hold", condition({**group("ALL", [{**a, "hold": {"atLeast": 1, "of": 3}}, b, c]),
                                             "hold": {"atLeast": 1, "of": 2400}})),
        ("X4.reads.nested.prior", condition({**group("ALL", [enters, b, c]), "hold": {"atLeast": 1, "of": 2400}})),
        ("X4.reads.seq.ref.step", condition(group("SEQUENCE", [ref, a, b, c], within=2449))),
    ]


def probes_round5(clauses):
    """SEQ_ROUND=5: round 4's conditionRef step pointed at a one-clause condition (TC_RISK_ON), so a flat step and the
    referenced condition's clauses expanded counted the same. TC_CORE_UP holds four clauses: flat 3 x 2449 + 11, expanded
    (4 + 2) x 2449 + 11."""
    a, b = (copy.deepcopy(clauses[i]) for i in range(2))
    ref = {"kind": "conditionRef", "conditionKey": "TC_CORE_UP"}
    return [("X5.reads.seq.ref4.step", condition(group("SEQUENCE", [ref, a, b], within=2449)))]


def probes_round6(clauses):
    """SEQ_ROUND=6: round 5 answered with the served step rule ("each a clause, a group of clauses, or a reference to a
    condition that reads one bar - every step and row held Once"); round 1 measured ALL and ANY steps. Asked here: an
    N_OF and a NOT step, a conditionRef inside a group step, and a reference to a condition that holds a row 3 closes."""
    a, b, c = (copy.deepcopy(clauses[i]) for i in range(3))
    ref = {"kind": "conditionRef", "conditionKey": "TC_RISK_ON"}
    held = {**condition({**copy.deepcopy(c), "hold": {"atLeast": 1, "of": 3}}), "conditionKey": "SEQ_HELD"}
    return [
        ("X6.step.nof", condition(group("SEQUENCE", [group("N_OF", [a, b], n=1), c], within=5))),
        ("X6.step.not", condition(group("SEQUENCE", [group("NOT", [a]), c], within=5))),
        ("X6.step.group.with.ref", condition(group("SEQUENCE", [group("ALL", [ref, a]), c], within=5))),
        ("X6.step.ref.held", [held, condition(group("SEQUENCE", [{"kind": "conditionRef", "conditionKey": "SEQ_HELD"},
                                                                 a], within=5))]),
    ]


def probes_round7(clauses):
    """SEQ_ROUND=7: rounds 3 - 4 fit "each clause counts the largest `of` on its path" and also "the outermost hold
    above 1 wins". Three clauses held 2400 under a group held 3: the largest gives 3 x 2400 + 11 (refused, the count
    shown), the outermost 3 x 3 + 11 (accepted), a product 3 x 7200 + 11."""
    a, b, c = (copy.deepcopy(clauses[i]) for i in range(3))
    rows = [{**x, "hold": {"atLeast": 1, "of": 2400}} for x in (a, b, c)]
    return [("X7.reads.inner.over.outer", condition({**group("ALL", rows), "hold": {"atLeast": 1, "of": 3}}))]


def outcome_rows(d, key="SEQ_PROBE"):
    rows = []
    for coin in ((d.get("authoring") or {}).get("conditionOutcomes") or []):
        for o in coin.get("outcomes") or []:
            if o.get("conditionKey") == key:
                rows.append({"ticker": coin.get("ticker"), "outcome": o.get("outcome"), "evidence": o.get("evidence")})
    register = (d.get("tradeConditions") or {}).get("register") or {}
    reg = [c for c in (register.get("conditions") or []) if c.get("key") == key]
    return rows, {"coin": register.get("coin"), "verdict": register.get("verdict"), "row": reg[0] if reg else None}


def main() -> int:
    if os.path.exists(RECORD_OUT) and os.environ.get("PROBE_OVERWRITE") != "1":
        sys.exit(f"{RECORD_OUT} exists: give this run its own PROBE_DATE, or PROBE_OVERWRITE=1")
    v0 = P.read_version_safely(P.version)
    if "error" in v0 or v0.get("contractVersion") != P.CONTRACT:
        sys.exit(f"served contract {v0} is not {P.CONTRACT}: stop before the first preview")
    req0, clauses = base_request()
    if len(clauses) < 3:
        sys.exit(f"the preset offers {len(clauses)} distinct clauses; three are needed")
    record = {"_what": __doc__.strip().splitlines()[0], "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "tickers": TICKERS, "timeframe": req0["source"]["timeframe"],
              "clauses": [{"header": c["column"]["header"], "op": c["op"]} for c in clauses[:3]], "probes": []}
    # the control: the preset's request as generated, so a refusal below is the probe condition's alone
    rounds = {"2": probes_round2, "3": probes_round3, "4": probes_round4, "5": probes_round5, "6": probes_round6,
              "7": probes_round7}
    chosen = rounds.get(os.environ.get("SEQ_ROUND", ""), probes)(clauses)
    record["round"] = int(os.environ.get("SEQ_ROUND") or 1)
    for name, extra in [("X.control", None)] + chosen:
        req = copy.deepcopy(req0)
        if extra is not None:
            # a probe is one condition, or (round 3) a list of them: a sequence and the condition that references it
            req["source"]["conditions"].extend(extra if isinstance(extra, list) else [extra])
        d = P.call("preview_strategy_report", req)
        kind = P.classify(d)
        entry = {"probe": name, "condition": extra, "accepted": kind == "render"}
        if kind == "render":
            rows, register = outcome_rows(d)
            entry.update(outcomes=rows, register=register)
            summary = ", ".join(f"{r['ticker']}={r['outcome']}" for r in rows) or "no outcome row"
        else:
            entry["refusal"] = P.refusal(d) if isinstance(d, dict) else {"raw": str(d)[:400]}
            entry["answerKind"] = kind
            summary = f"{kind}: {str((entry['refusal'] or {}).get('message'))[:200]}"
        record["probes"].append(entry)
        print(f"  {name}: {'OK ' if entry['accepted'] else 'REFUSED '}{summary}", flush=True)
        time.sleep(0.5)
    v1 = P.read_version_safely(P.version, P.RETRY_PAUSE)
    record.update(P.contract_fields(v0, v1))
    record["capturedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    os.makedirs(os.path.dirname(RECORD_OUT), exist_ok=True)
    with open(RECORD_OUT, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"wrote {RECORD_OUT}; contract {record['contractVersion']} -> {record['versionAtEnd']}")
    return 0 if record.get("contractMoved") is False else 2


if __name__ == "__main__":
    raise SystemExit(main())
