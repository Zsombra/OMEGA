"""What does this column compute, and what did it actually produce?

THIS MODULE COMPUTES NOTHING
----------------------------
Every formula, effective parameter, header and value printed here was returned by
BattleGrid and stored verbatim. `explain` assembles three sources:

    1. the transform authoring contract   data/contract/transforms/_authoring.json
    2. the compiled column contract       data/contract/columns/_contracts.json
    3. rendered live values               data/contract/columns/_renders*.json

Sources 2 and 3 exist only for columns someone actually probed. Where a piece is
missing, `explain` says so. It never fills the gap - a plausible number is
indistinguishable from a measured one once it is rendered as text, which is the same
house rule `omega.scoring` follows when it returns `computable=False`.

WHY YOU CANNOT SKIP THE COMPILED CONTRACT
-----------------------------------------
The parameters that took effect are not the parameters you sent. A request carrying
neither `window` nor `bars` comes back with `window=4, bars="all"`, and `bars="all"`
includes the live forming bar (cookbook trap #1). `explain` reports the EFFECTIVE
values wherever it has them, and marks them absent where it does not.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .contract import Contract, load
from .fanout import outputs_for
from .probe import load_all_renders, load_contracts
from .space import ColumnShape
from .types import Column

_UNCAPTURED = ("not captured - run the calls in omega.probe.FETCH_RECIPE to "
               "compile this column against the live connector")


@dataclass(frozen=True)
class Explanation:
    """One column, explained from what was extracted - and what was not."""

    column: Column
    label: str
    formula: str | None                       # stage 1, from the authoring contract
    calculation_summary: str | None
    operand_order: list[str] | None
    null_behavior: str | None
    parameters: Mapping[str, Any]             # the transform's declared parameters
    chained_formula: str | None = None        # stage 2, when the column chains
    chained_label: str | None = None
    effective_parameters: Mapping[str, Any] | None = None   # None => never compiled
    headers: list[str] | None = None                        # None => never compiled
    predicted_headers: list[str] = field(default_factory=list)
    glossary: Mapping[str, str] | None = None
    contract_null_behavior: str | None = None
    values: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    defect_note: str | None = None

    @property
    def was_compiled(self) -> bool:
        return self.effective_parameters is not None

    @property
    def was_rendered(self) -> bool:
        return bool(self.values)


def _as_column(target: Column | ColumnShape) -> Column:
    return target.to_column() if isinstance(target, ColumnShape) else target


def _same_column(a: Mapping, b: Mapping) -> bool:
    """Two wire payloads describing the same column, ignoring key order."""
    return a == b


def _find_contract(col: Column) -> dict | None:
    wire = col.wire()
    for case in load_contracts():
        if _same_column(case["request"]["column"], wire):
            return case["response"]["contract"]
    return None


def _find_values(col: Column, headers: list[str]) -> dict[str, dict[str, str]]:
    """Rendered cells for these headers, keyed coin -> header -> cell."""
    wire = col.wire()
    out: dict[str, dict[str, str]] = {}
    for payload in load_all_renders():
        section = payload["request"]["sections"][0]
        if not any(_same_column(spec, wire) for spec in section["columns"]):
            continue
        text = payload["response"]["renderedSections"][0]["section"]["text"]
        lines = [ln for ln in text.splitlines() if ln.startswith("|")]
        if len(lines) < 3:
            continue
        names = [c.strip() for c in lines[0].strip("|").split("|")]
        for row in lines[2:]:
            cells = [c.strip() for c in row.strip("|").split("|")]
            if len(cells) != len(names):
                continue
            coin, by_name = cells[0], dict(zip(names, cells))
            picked = {h: by_name[h] for h in headers if h in by_name}
            if picked:
                out.setdefault(coin, {}).update(picked)
    return out


def _defect_note(col: Column, contract: Contract) -> str | None:
    """The platform's formula text is wrong for a chained spread->trajectory.

    Recorded in composition_rules.chaining.knownDocDefect and re-confirmed live.
    Surfaced beside the verbatim text rather than substituted for it.
    """
    if col.transformId == "spread" and col.chainedTransformId == "trajectory":
        return contract.rules["chaining"].get("knownDocDefect")
    return None


def explain(target: Column | ColumnShape, contract: Contract | None = None) -> Explanation:
    """Assemble everything known about one column. Computes nothing."""
    c = contract or load()
    col = _as_column(target)
    auth = c.transforms.get(col.transformId, {})
    chained = c.transforms.get(col.chainedTransformId or "", {})
    compiled = _find_contract(col)

    headers = ([o["header"] for o in compiled["outputs"]] if compiled else None)
    predicted = [o.header for o in outputs_for(col, c)]

    return Explanation(
        column=col,
        label=auth.get("label", col.transformId),
        formula=auth.get("formula"),
        calculation_summary=auth.get("calculationSummary"),
        operand_order=auth.get("operandOrder"),
        null_behavior=auth.get("nullBehavior"),
        parameters=auth.get("parameters", {}),
        chained_formula=chained.get("formula"),
        chained_label=chained.get("label"),
        effective_parameters=(compiled["effectiveParameters"] if compiled else None),
        headers=headers,
        predicted_headers=predicted,
        glossary=(compiled.get("glossary") if compiled else None),
        contract_null_behavior=(compiled.get("nullBehavior") if compiled else None),
        values=_find_values(col, headers or predicted),
        defect_note=_defect_note(col, c),
    )


def render_text(e: Explanation) -> str:
    """A plain-text account, naming its sources so a reader can check them."""
    col = e.column
    who = f"{col.metric} × {col.transformId}"
    if col.chainedTransformId:
        who += f" → {col.chainedTransformId}"
    if col.inputs:
        who += f"  (operand {', '.join(i.metric for i in col.inputs)})"

    L = [who, "=" * len(who), ""]

    L += ["THE MATH            source: data/contract/transforms/_authoring.json",
          f"  stage 1  {e.label}",
          f"           {e.calculation_summary or '—'}",
          f"           {e.formula or '—'}"]
    if e.chained_formula:
        L += [f"  stage 2  {e.chained_label}", f"           {e.chained_formula}"]
    if e.operand_order:
        L.append(f"  operands {' , '.join(e.operand_order)}")
    if e.null_behavior:
        L.append(f"  nulls    {e.null_behavior}")

    if e.defect_note:
        L += ["", "KNOWN DEFECT in the platform's own wording",
              f"  {e.defect_note}",
              "  The text above is stored exactly as BattleGrid returns it."]

    L += ["", "PARAMETERS          source: the same authoring contract"]
    for name, spec in (e.parameters or {}).items():
        default = spec.get("defaultValue", "—")
        req = "required" if spec.get("required") else f"default {default!r}"
        L.append(f"  {name:<10}{req}")
    if not e.parameters:
        L.append("  (none)")

    L += ["", "EFFECTIVE           source: data/contract/columns/_contracts.json"]
    if e.was_compiled:
        applied = {k: v for k, v in e.effective_parameters.items() if v not in (None, [])}
        L.append(f"  {applied}")
        L.append("  These are what the platform APPLIED, not what was requested.")
        L.append(f"  headers  {', '.join(e.headers or [])}")
    else:
        L.append(f"  {_UNCAPTURED}")
        L.append(f"  predicted headers (omega.fanout): {', '.join(e.predicted_headers)}")

    L += ["", "VALUES              source: data/contract/columns/_renders*.json"]
    if e.was_rendered:
        for coin, cells in e.values.items():
            rendered = "  ".join(f"{h}={v}" for h, v in cells.items())
            L.append(f"  {coin:<7}{rendered}")
    else:
        L.append(f"  {_UNCAPTURED}")

    return "\n".join(L)
