"""Does the generator produce plans that survive what the verification found?

This is the bridge test between the two halves of the project. The extraction side now
knows a great deal that the generation side may or may not act on:

  - a timeless metric takes the literal {"rel":"anchor"} and nothing else
  - a spread chained into a series transform needs a candle-backed operand
  - CLOSE_CHANGE x rank offers only ['far','near'], not the default 'hi'
  - 8 CROWD x rank shapes validate and return INTERNAL_ERROR on render
  - two columns compiling to the same header silently drop the whole section
    from conditionColumns, so the agent can read it and no condition can address it
  - ROC12 renders a FRACTION while its label says percent (BG-11), so a threshold
    written as if it were a percent is off by 100x
  - a gate on a label that has never been observed reads FALSE forever, and a NOT
    around it fires ALWAYS
  - for a single-signed metric, rank_lo and rank_near are the SAME column under two
    names, so authoring both spends two of the 32 section slots on one measurement

A plan can pass omega.validate and still be quietly broken by the last four. Validation
answers "will the platform accept this". This answers "is it worth accepting".

    python -m scripts.audit_generated_plans
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from omega import contract as C
from omega.fanout import outputs_for
from omega.generate import PRESETS, plan
from omega.validate import validate_report

ROOT = Path(__file__).resolve().parents[1]

# Non-negative metrics: rank_lo IS rank_near. Non-positive: rank_lo IS rank_far.
# Measured live 2026-08-26 - BTC OI_rank_lo and OI_rank_near both 78/78, lowDev_rank_lo
# and lowDev_rank_far both 38/78. See data/contract/columns/_coverage_sweep_2026-08-26.json.
NON_NEGATIVE = {"OI", "OI_CHG", "RVOL", "VOLUME", "VOL_SMA20", "TRADES", "BUY_TRADES",
                "SELL_TRADES", "BUY_VOLUME", "SELL_VOLUME", "ATR", "ATR_PCT",
                "BB_WIDTH", "BB_WIDTH_PCT", "HIGH_DEV", "ADX", "MFI14", "RSI14",
                "RSI7", "STOCH_K", "STOCH_D"}
NON_POSITIVE = {"LOW_DEV"}


def unobserved_labels() -> set[tuple[str, str]]:
    rec = json.loads((ROOT / "data/audit/tier_c_coherence.json").read_text(
        encoding="utf-8"))["unobservedLabels"]
    return {(m, l) for m, v in rec.items() if not m.startswith("_") for l in v["unseen"]}


def audit(name: str, contract):
    p = plan(PRESETS[name])
    findings: list[str] = []

    # 1. does the platform accept it at all?
    result = validate_report(p.report, contract=contract)
    errors = [f for f in result.findings if f.severity == "error"]
    findings += [f"VALIDATION {f.code}: {f.message}" for f in errors]

    columns = [c for s in p.report.sections
               if getattr(s, "kind", None) == "custom" for c in s.columns]

    # 2. ordering aliases - two slots, one measurement
    seen_rank: dict[str, set[str]] = {}
    for c in columns:
        if "rank" in (c.transformId, c.chainedTransformId or ""):
            seen_rank.setdefault(c.metric, set()).add(c.ordering or "hi")
    for metric, orders in seen_rank.items():
        if metric in NON_NEGATIVE and {"lo", "near"} <= orders:
            findings.append(f"ALIAS {metric}: rank_lo and rank_near are the same column")
        if metric in NON_NEGATIVE and {"hi", "far"} <= orders:
            findings.append(f"ALIAS {metric}: rank_hi and rank_far are the same column")
        if metric in NON_POSITIVE and {"lo", "far"} <= orders:
            findings.append(f"ALIAS {metric}: rank_lo and rank_far are the same column")

    # 3. BG-11 - ROC12 renders a fraction, its label says percent
    if any(c.metric == "ROC12" for c in columns):
        findings.append("BG-11 ROC12 is present: it renders a FRACTION while labelled "
                        "'(%)'. Any threshold written as a percent is 100x wrong.")

    # 4. inert gates - a condition naming a label never observed
    unseen = unobserved_labels()
    by_header = {}
    for s in p.report.sections:
        if getattr(s, "kind", None) != "custom":
            continue
        for c in s.columns:
            for o in outputs_for(c, contract):
                by_header[o.header] = c.metric
    for cond in p.conditions:
        for label, metric, ctx in _labels_in(cond, by_header):
            if (metric, label) in unseen:
                findings.append(
                    f"INERT CLAUSE {metric} is {label!r} never observed "
                    f"({cond['conditionKey']}): {_effect(ctx)}")

    # 5. duplicate headers inside one section
    for s in p.report.sections:
        if getattr(s, "kind", None) != "custom":
            continue
        hs = [o.header for c in s.columns for o in outputs_for(c, contract)]
        dupes = [h for h, n in Counter(hs).items() if n > 1]
        if dupes:
            findings.append(f"DUPLICATE HEADER in {s.title!r}: {dupes} - the platform "
                            f"renders both and drops the SECTION from conditionColumns")

    return p, columns, findings


def _effect(ctx):
    """What a permanently-FALSE clause actually does, given where it sits.

    The first version of this script got this wrong. It reported every unobserved label
    as "reads FALSE forever", which is only true for a bare clause or one under ALL.
    Inside an N_OF the condition still works - what silently moves is the THRESHOLD, and
    the strategy ends up stricter than its author declared. Under a NOT the clause is
    permanently TRUE, which is the opposite failure. Same input, three different bugs.
    """
    op, total, n = ctx
    if op == "NOT":
        return "it sits under NOT, so that clause fires ALWAYS - the opposite of inert"
    if op == "N_OF":
        return (f"1 of {total} members of an N_OF needing {n}, so the gate is really "
                f"{n}-of-{total - 1}, tighter than the {n}-of-{total} declared")
    if op == "ANY":
        return f"1 of {total} ANY members, leaving {total - 1} live"
    if op == "ALL":
        return "an ALL member, so the whole condition can NEVER be true"
    return "a bare clause, so the condition can NEVER be true"


def _labels_in(node, by_header, ctx=(None, 0, 0)):
    """Yield (label, metric, ctx) for every is/in clause, carrying its parent group."""
    if not isinstance(node, dict):
        return
    if node.get("kind") == "clause" and node.get("op") in ("is", "in"):
        header = (node.get("column") or {}).get("header")
        metric = by_header.get(header)
        if metric:
            for lbl in ([node["label"]] if node.get("op") == "is" else node.get("labels", [])):
                yield lbl, metric, ctx
    if node.get("kind") == "group":
        members = node.get("members") or []
        child_ctx = (node.get("op"), len(members), node.get("n") or 0)
        for child in members:
            yield from _labels_in(child, by_header, child_ctx)
    if node.get("definition"):
        yield from _labels_in(node["definition"], by_header, ctx)


def main() -> int:
    c = C.load()
    total = 0
    print(f"auditing {len(PRESETS)} preset theses against the verified traps\n")
    for name in PRESETS:
        p, columns, findings = audit(name, c)
        headers = sum(len(outputs_for(col, c)) for col in columns)
        status = "CLEAN" if not findings else f"{len(findings)} finding(s)"
        print(f"{name:22s} {len(columns):>3} columns, {headers:>3} headers, "
              f"{len(p.conditions):>2} conditions  ->  {status}")
        for f in findings:
            print(f"      - {f}")
        total += len(findings)
    print(f"\n{total} finding(s) across {len(PRESETS)} presets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
