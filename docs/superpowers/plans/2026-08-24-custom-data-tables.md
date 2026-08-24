# Custom Data Tables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enumerate the BattleGrid custom-column design space as queryable objects, and land the repo's first real rendered column values — extracted from the platform, never computed locally.

**Architecture:** `omega/space.py` enumerates `ColumnShape` objects from the already-extracted contract corpus (pure local, no network). `omega/probe.py` builds the exact request payloads for two read-only connector tools and ingests their saved responses verbatim into `data/contract/columns/`. Neither module opens a socket — the agent runs the tools, `omega` prepares and consumes.

**Tech Stack:** Python 3.14, pydantic (already used in `omega/types.py`), pytest. No new dependencies.

## Global Constraints

- **Extract, never compute.** No task may implement a transform formula, derive a column value, or infer a default. Every formula and number comes from the platform verbatim.
- **`omega` cannot call MCP tools.** House rule stated at `omega/performance.py:244`. No task adds `requests`, `httpx`, `urllib`, or any network client. Pattern: agent runs tool → response saved verbatim → pure-local code reads it.
- **Read-only only.** The two connector tools used here are `get_strategy_column_contract` and `preview_strategy_report`. Neither writes. Strategy quota stays 24/25, agent slots 24/24. No task may call a write tool.
- **Store platform text verbatim; annotate corrections separately.** Never repair the platform's own formula text in place.
- **Existing suite is 305 tests and must stay green.** Run `python -m pytest -q` before every commit.
- **Working directory:** `C:\Users\rafae\Documents\GitHub\OMEGA`. Run pytest from the repo root.

### Verified counts these tasks must reproduce

| quantity | value |
|---|---|
| metrics | 86 |
| transforms | 16 |
| metric × transform pairs | 1376 |
| legal atoms (`legal == "yes"`) | 322 |
| atoms accepting a chained stage | 52 (42 with 3 successors, 10 with 4 including `rank`) |
| structural shapes (atoms + chained forms) | 488 |
| operand/ordering-expanded forms | 2200 |

### Existing APIs these tasks consume

```python
# omega/contract.py
ROOT: Path; CONTRACT_DIR: Path; DERIVED_DIR: Path
def load() -> Contract                      # lru_cached

@dataclass
class Contract:
    metrics: dict[str, Metric]
    transforms: dict[str, dict]
    privileged_pairs: set[tuple[str, str]]
    budgets: dict[str, int]
    rules: dict
    shared: dict
    platform_templates: dict[str, dict]
    def metric(self, name: str) -> Metric
    def transform_ids(self) -> list[str]
    def is_privileged(self, metric: str, transform_id: str) -> bool

@dataclass
class Metric:
    metric: str; label: str; code: str; family: str
    native_output: dict; output_kind: str; timeframe_mode: str
    transforms: dict[str, dict]          # transformId -> flags
    spread_operands: tuple[str, ...] = ()
    rank_orderings: tuple[str, ...] = ()
    @property
    def unit(self) -> str | None
    def offers(self, transform_id: str) -> bool

# omega/types.py  (pydantic BaseModel)
class Column(BaseModel):
    metric: str
    transformId: str
    timeframe: Timeframe                 # RelTimeframe(rel=...) | AbsTimeframe(abs=...)
    chainedTransformId: str | None = None
    window: int | None = None            # 1..64
    offset: int | None = None            # 0..64
    bars: Literal["closed","all"] | None = None
    ordering: Literal["hi","lo","far","near"] | None = None
    side: Literal["support","resistance"] | None = None
    inputs: list[Operand] | None = None  # max 4; Operand(metric=str)
    def wire(self) -> dict               # exclude_none JSON the connector expects

class RelTimeframe(BaseModel): rel: str
class Operand(BaseModel): metric: str

# omega/validate.py
def validate_column(column: Column, *, section_timeframe: str | None = None,
                    path: str = "column", contract: Contract | None = None) -> list[Finding]
@dataclass(frozen=True)
class Finding: ...                       # .level is "error" | "warning"

# omega/fanout.py
def outputs_for(column: Column, contract: Contract | None = None) -> list[Output]
@dataclass(frozen=True)
class Output:
    header: str; kind: str; vocabulary: tuple[str, ...] = ()
```

---

### Task 1: `ColumnShape` and shape enumeration

**Files:**
- Create: `omega/space.py`
- Test: `tests/test_space.py`

**Interfaces:**
- Consumes: `omega.contract.load`, `Contract`, `Metric`; `omega.types.Column`, `RelTimeframe`, `Operand`
- Produces:
  - `ColumnShape` frozen dataclass with fields `metric: str`, `transform: str`, `chained: str | None`, `operand: str | None`, `ordering: str | None`
  - `ColumnShape.to_column(timeframe_rel: str = "anchor") -> Column`
  - `enumerate_shapes(expand_operands: bool = False, contract: Contract | None = None) -> list[ColumnShape]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_space.py
"""The custom-column design space, enumerated from the extracted corpus.

The counts pinned here are the whole point: chaining is capped at two stages
(composition_rules.chaining.stages), which is what makes the space finite and
countable rather than open-ended.
"""
from __future__ import annotations

import csv
from pathlib import Path

from omega.contract import DERIVED_DIR
from omega.space import ColumnShape, enumerate_shapes

ROOT = Path(__file__).resolve().parents[1]


def _matrix_rows():
    with (DERIVED_DIR / "composability_matrix.csv").open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_matrix_is_the_full_metric_by_transform_grid():
    rows = _matrix_rows()
    assert len(rows) == 1376
    assert len({r["metric"] for r in rows}) == 86
    assert len({r["transform"] for r in rows}) == 16


def test_structural_shape_count_is_488():
    """322 legal atoms + 166 chained forms. Chaining stops at two stages."""
    shapes = enumerate_shapes()
    atoms = [s for s in shapes if s.chained is None]
    chained = [s for s in shapes if s.chained is not None]
    assert len(atoms) == 322
    assert len(chained) == 166
    assert len(shapes) == 488


def test_chain_successors_split_42_and_10():
    """42 atoms take the 3 general successors; 10 also take rank."""
    shapes = enumerate_shapes()
    by_atom: dict[tuple[str, str], set[str]] = {}
    for s in shapes:
        if s.chained:
            by_atom.setdefault((s.metric, s.transform), set()).add(s.chained)
    three = [k for k, v in by_atom.items() if v == {"trajectory", "aggregate", "efficiency"}]
    four = [k for k, v in by_atom.items()
            if v == {"trajectory", "aggregate", "efficiency", "rank"}]
    assert len(three) == 42
    assert len(four) == 10


def test_expanding_operands_and_orderings_gives_2200():
    assert len(enumerate_shapes(expand_operands=True)) == 2200


def test_chained_rank_expands_over_its_own_ordering_axis():
    """chainedRankOrderings is separate from the metric's own rankOrderings.

    Missing this axis undercounts the space by 78. The 10 rank-chain atoms carry
    [hi, lo, far, near] and expand to 104 forms once spread operands multiply in.
    """
    expanded = enumerate_shapes(expand_operands=True)
    rank_chains = [s for s in expanded if s.chained == "rank"]
    assert len(rank_chains) == 104
    assert {s.ordering for s in rank_chains} == {"hi", "lo", "far", "near"}


def test_expansion_produces_no_duplicate_rows():
    expanded = enumerate_shapes(expand_operands=True)
    assert len(expanded) == len(set(expanded))


def test_expansion_never_loses_a_shape():
    """Every structural shape must survive expansion under some operand/ordering."""
    plain = {(s.metric, s.transform, s.chained) for s in enumerate_shapes()}
    wide = {(s.metric, s.transform, s.chained)
            for s in enumerate_shapes(expand_operands=True)}
    assert plain == wide


def test_shape_converts_to_a_validatable_column():
    shape = ColumnShape(metric="EMA5", transform="spread",
                        chained="trajectory", operand="EMA13", ordering=None)
    col = shape.to_column()
    assert col.metric == "EMA5"
    assert col.transformId == "spread"
    assert col.chainedTransformId == "trajectory"
    assert col.inputs is not None and col.inputs[0].metric == "EMA13"
    assert col.timeframe.rel == "anchor"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_space.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'omega.space'`

- [ ] **Step 3: Write the implementation**

```python
# omega/space.py
"""The custom-column design space, enumerated from the extracted corpus.

WHY THIS IS FINITE
------------------
`composition_rules.chaining.stages` is 2. A column is one metric, one transform,
and at most one chained successor - so the structural space can be counted rather
than sampled:

    1376 metric x transform pairs
     322 legal atoms
     166 chained forms   (42 atoms x 3 general successors, 10 x 4 including rank)
     488 structural shapes

Expanding spread operands and rank orderings gives 2200 concrete forms.

PARAMETERS ARE NOT ENUMERATED, DELIBERATELY
-------------------------------------------
`window` is 1-64, `offset` 0-64, `bars` is one of two values and `inputs` takes up
to four metrics. Materialising that cross-product would produce millions of rows of
no value. Parameters are axes you vary on a shape you have already chosen; ask the
platform for their effective values via omega.probe.

Pure local computation - performs no network or MCP calls.
"""
from __future__ import annotations

from dataclasses import dataclass

from .contract import Contract, Metric, load
from .types import Column, Operand, RelTimeframe

# From composition_rules.chaining. Held here as the enumeration's own statement of
# the rule; test_space asserts it against the stored contract.
GENERAL_SUCCESSORS = ("trajectory", "aggregate", "efficiency")


@dataclass(frozen=True)
class ColumnShape:
    """One structural point in the space: metric x transform x optional chain."""

    metric: str
    transform: str
    chained: str | None = None
    operand: str | None = None
    ordering: str | None = None

    def to_column(self, timeframe_rel: str = "anchor") -> Column:
        """The authorable Column this shape denotes, with no parameters set."""
        return Column(
            metric=self.metric,
            transformId=self.transform,
            timeframe=RelTimeframe(rel=timeframe_rel),
            chainedTransformId=self.chained,
            ordering=self.ordering,
            inputs=[Operand(metric=self.operand)] if self.operand else None,
        )


def _variants(m: Metric, transform: str, expand: bool) -> list[tuple[str | None, str | None]]:
    """(operand, ordering) pairs for one atom. Exactly one entry when not expanding."""
    if not expand:
        return [(None, None)]
    if transform == "spread" and m.spread_operands:
        return [(o, None) for o in m.spread_operands]
    if transform == "rank" and m.rank_orderings:
        return [(None, o) for o in m.rank_orderings]
    return [(None, None)]


def enumerate_shapes(expand_operands: bool = False,
                     contract: Contract | None = None) -> list[ColumnShape]:
    """Every structural shape in the space.

    `expand_operands=False` gives the 488 structural shapes. `True` enumerates each
    spread operand and rank ordering separately, giving 2200.

    THREE ORDERING AXES, NOT ONE
    ----------------------------
    A `rank` ATOM varies over the metric's `rankOrderings`. A chained `rank` varies
    over the atom's own `chainedRankOrderings`, which the contract publishes
    separately - `EMA13 x distance` carries chainSuccessors [..., "rank"] AND
    chainedRankOrderings [hi, lo, far, near]. Dropping that second axis undercounts
    the space by 78 (2122 instead of 2200), so it is enumerated explicitly below.
    A shape has at most one rank stage, so a single `ordering` field serves both.
    """
    c = contract or load()
    out: list[ColumnShape] = []
    for name, m in c.metrics.items():
        for transform, flags in m.transforms.items():
            for operand, ordering in _variants(m, transform, expand_operands):
                out.append(ColumnShape(name, transform, None, operand, ordering))
                for succ in (flags.get("chainSuccessors") or ()):
                    if succ == "rank" and expand_operands:
                        for o in (flags.get("chainedRankOrderings") or (None,)):
                            out.append(ColumnShape(name, transform, succ, operand, o))
                    else:
                        out.append(ColumnShape(name, transform, succ, operand, ordering))
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_space.py -q`
Expected: PASS, 8 tests.

If a count is off, do **not** adjust the assertion. The assertions encode measured
facts. Print the discrepancy and investigate `data/contract/metrics/*.json` — a
mismatch means the enumeration logic disagrees with the corpus, which is the bug the
test exists to catch.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS, 313 tests (305 existing + 8 new).

- [ ] **Step 6: Commit**

```bash
git add omega/space.py tests/test_space.py
git commit -m "Enumerate the column design space: 488 shapes, 2200 expanded"
```

---

### Task 2: Query the space

**Files:**
- Modify: `omega/space.py`
- Modify: `tests/test_space.py`

**Interfaces:**
- Consumes: Task 1's `ColumnShape`, `enumerate_shapes`; `omega.fanout.outputs_for`
- Produces:
  - `header_cost(shape: ColumnShape, window: int = 4, contract: Contract | None = None) -> int`
  - `platform_used(contract: Contract | None = None) -> set[tuple[str, str]]`
  - `query(*, family: str | None = None, transform: str | None = None, unit: str | None = None, timeframe_mode: str | None = None, chained: bool | None = None, max_headers: int | None = None, platform_uses: bool | None = None, expand_operands: bool = False, contract: Contract | None = None) -> list[ColumnShape]`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_space.py
from omega.space import header_cost, platform_used, query


def test_only_trajectory_fans_out():
    """composition_rules.fanOut: every other transform emits exactly one header."""
    plain = ColumnShape(metric="RSI14", transform="value")
    traj = ColumnShape(metric="RSI14", transform="trajectory")
    assert header_cost(plain) == 1
    assert header_cost(traj, window=4) == 5      # 4 slots + _trend
    assert header_cost(traj, window=8) == 9


def test_platform_used_pairs_come_from_the_shipped_templates():
    used = platform_used()
    assert used, "platform templates must yield at least one (metric, transform) pair"
    assert all(isinstance(p, tuple) and len(p) == 2 for p in used)


def test_query_filters_by_family():
    got = query(family="volumeFlow")
    assert got
    assert {s.metric for s in got} <= {
        m for m, mm in __import__("omega.contract", fromlist=["load"]).load()
        .metrics.items() if mm.family == "volumeFlow"
    }


def test_query_by_max_headers_excludes_fan_out():
    cheap = query(max_headers=1)
    assert all(s.transform != "trajectory" and s.chained != "trajectory" for s in cheap)


def test_query_can_isolate_what_the_platform_never_uses():
    """The 'what haven't I thought of' question, answered against shipped templates."""
    unused = query(platform_uses=False)
    used = query(platform_uses=True)
    assert unused and used
    assert not ({(s.metric, s.transform) for s in used}
                & {(s.metric, s.transform) for s in unused})


def test_query_with_no_filters_is_the_whole_space():
    assert len(query()) == 488
    assert len(query(expand_operands=True)) == 2200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_space.py -q`
Expected: FAIL — `ImportError: cannot import name 'header_cost' from 'omega.space'`

- [ ] **Step 3: Write the implementation**

```python
# append to omega/space.py
from .fanout import outputs_for


def header_cost(shape: ColumnShape, window: int = 4,
                contract: Contract | None = None) -> int:
    """How many report headers this shape emits.

    Only `trajectory` fans out (composition_rules.fanOut); everything else is 1.
    `window` matters only when trajectory is present, and defaults to 4 because
    that is the platform's own default for the transform.
    """
    col = shape.to_column()
    if "trajectory" in (shape.transform, shape.chained):
        col = col.model_copy(update={"window": window})
    return len(outputs_for(col, contract))


def platform_used(contract: Contract | None = None) -> set[tuple[str, str]]:
    """(metric, transformId) pairs the platform's own shipped templates use."""
    c = contract or load()
    out: set[tuple[str, str]] = set()
    for template in c.platform_templates.values():
        for col in template.get("columns", []) or []:
            metric, transform = col.get("metric"), col.get("transformId")
            if metric and transform:
                out.add((metric, transform))
                if chained := col.get("chainedTransformId"):
                    out.add((metric, chained))
    return out


def query(*, family: str | None = None, transform: str | None = None,
          unit: str | None = None, timeframe_mode: str | None = None,
          chained: bool | None = None, max_headers: int | None = None,
          platform_uses: bool | None = None, expand_operands: bool = False,
          contract: Contract | None = None) -> list[ColumnShape]:
    """Filter the space. Every argument is optional; omitted means 'do not filter'."""
    c = contract or load()
    used = platform_used(c) if platform_uses is not None else set()
    out = []
    for s in enumerate_shapes(expand_operands, c):
        m = c.metrics[s.metric]
        if family is not None and m.family != family:
            continue
        if transform is not None and transform not in (s.transform, s.chained):
            continue
        if unit is not None and m.unit != unit:
            continue
        if timeframe_mode is not None and m.timeframe_mode != timeframe_mode:
            continue
        if chained is not None and (s.chained is not None) != chained:
            continue
        if max_headers is not None and header_cost(s, contract=c) > max_headers:
            continue
        if platform_uses is not None and ((s.metric, s.transform) in used) != platform_uses:
            continue
        out.append(s)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_space.py -q`
Expected: PASS, 14 tests.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS, 319 tests.

- [ ] **Step 6: Commit**

```bash
git add omega/space.py tests/test_space.py
git commit -m "Add a query surface over the column space, including platform-usage gaps"
```

---

### Task 3: Probe request builder

**Files:**
- Create: `omega/probe.py`
- Create: `data/contract/columns/.gitkeep`
- Test: `tests/test_probe.py`

**Interfaces:**
- Consumes: Task 1's `ColumnShape`; `omega.types.Column`
- Produces:
  - `FETCH_RECIPE: str`
  - `FIRST_CUT: tuple[ColumnShape, ...]` — the four shapes this plan probes
  - `contract_request(shape: ColumnShape, section_timeframe: str = "1h", window: int | None = None) -> dict`
  - `render_request(shapes: Sequence[ColumnShape], tickers: Sequence[str], timeframe: str = "1h", title: str = "omega probe") -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_probe.py
"""Request builders for the two read-only column tools.

omega cannot call MCP tools (see omega/performance.py:244). These build the exact
payloads the agent hands to the connector, and nothing here opens a socket.
"""
from __future__ import annotations

import inspect

from omega.probe import (
    FETCH_RECIPE, FIRST_CUT, contract_request, render_request,
)
from omega.space import ColumnShape
from omega.validate import validate_column


def test_module_opens_no_sockets():
    import omega.probe as probe
    src = inspect.getsource(probe)
    for banned in ("import requests", "import httpx", "urllib", "socket", "aiohttp"):
        assert banned not in src, f"probe.py must not use {banned}"


def test_first_cut_spans_the_interesting_cases():
    """An atom, a chain, a trajectory fan-out, and a rank-chain."""
    assert len(FIRST_CUT) == 4
    assert any(s.chained is None and s.transform != "trajectory" for s in FIRST_CUT)
    assert any(s.chained is not None for s in FIRST_CUT)
    assert any("trajectory" in (s.transform, s.chained) for s in FIRST_CUT)
    assert any(s.chained == "rank" for s in FIRST_CUT)


def test_every_first_cut_shape_is_legal_before_we_spend_a_call():
    for shape in FIRST_CUT:
        findings = validate_column(shape.to_column(), section_timeframe="1h")
        assert not [f for f in findings if f.level == "error"], f"{shape} -> {findings}"


def test_contract_request_is_the_wire_shape():
    shape = ColumnShape("EMA5", "spread", "trajectory", "EMA13", None)
    req = contract_request(shape, window=4)
    assert req["sectionTimeframe"] == "1h"
    col = req["column"]
    assert col["metric"] == "EMA5"
    assert col["transformId"] == "spread"
    assert col["chainedTransformId"] == "trajectory"
    assert col["window"] == 4
    assert col["inputs"] == [{"metric": "EMA13"}]
    assert "None" not in str(col), "wire payload must omit unset fields"


def test_render_request_wraps_columns_in_one_custom_section():
    req = render_request(FIRST_CUT, ["BTC", "GOOGL"])
    assert req["timeframe"] == "1h"
    assert req["coinSelection"] == {"mode": "explicit", "tickers": ["BTC", "GOOGL"]}
    assert len(req["sections"]) == 1
    section = req["sections"][0]
    assert section["kind"] == "custom"
    assert section["benchmarkTicker"] is None
    assert len(section["columns"]) == 4


def test_fetch_recipe_names_both_tools_and_the_read_only_guarantee():
    assert "get_strategy_column_contract" in FETCH_RECIPE
    assert "preview_strategy_report" in FETCH_RECIPE
    assert "read-only" in FETCH_RECIPE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_probe.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'omega.probe'`

- [ ] **Step 3: Write the implementation**

```python
# omega/probe.py
"""Request builders and verbatim ingesters for the two read-only column tools.

omega CANNOT CALL MCP TOOLS
---------------------------
This is the house rule (omega/performance.py:244, scripts/build_corpus.py). The
agent runs the connector tools and saves each response verbatim; this module builds
the payloads to hand over and reads the results back. Nothing here opens a socket.

WHY BOTH TOOLS ARE SAFE
-----------------------
`get_strategy_column_contract` compiles one column and reads no market values.
`preview_strategy_report` is documented as rendering "without saving or mutating
strategy state" - no write, no strategy slot, no quota consumed.

WHY WE ASK RATHER THAN COMPUTE
------------------------------
The platform's effective parameters are not guessable. A contract request passing
neither `window` nor `bars` comes back with window=4, bars="all" - and bars="all"
includes the live forming bar, which is trap #1 in the cookbook. Always read
`effectiveParameters` off the response rather than assuming the values sent.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from .contract import CONTRACT_DIR
from .space import ColumnShape

COLUMNS_DIR = CONTRACT_DIR / "columns"

# Four shapes spanning the structurally distinct cases: a plain atom, a chained
# form, a fan-out, and one of the 10 shapes that can chain into rank.
FIRST_CUT: tuple[ColumnShape, ...] = (
    ColumnShape("RSI14", "value"),                              # atom, 1 header
    ColumnShape("EMA5", "spread", "trajectory", "EMA13", None),  # chain + fan-out
    ColumnShape("CCI20", "trajectory"),                          # bare fan-out
    ColumnShape("VWAP", "distance", "rank", None, None),         # rank-chain
)

FETCH_RECIPE = """\
omega cannot call MCP tools itself. To capture column contracts and the first real
rendered values, run these read-only calls and save each response VERBATIM:

  1. for each shape in omega.probe.FIRST_CUT:
       get_strategy_column_contract(omega.probe.contract_request(shape))
     -> save the full result to data/contract/columns/_contracts.json as
        {"capturedAt": "<ISO8601>", "cases": [{"request": ..., "response": ...}]}

  2. preview_strategy_report(omega.probe.render_request(FIRST_CUT, ["BTC","GOOGL"]))
     -> save the full result to data/contract/columns/_renders.json as
        {"capturedAt": "<ISO8601>", "request": ..., "response": ...}

Both are read-only. get_strategy_column_contract reads no market values;
preview_strategy_report renders "without saving or mutating strategy state". Neither
consumes strategy or agent quota.

Store responses unmodified. Do not normalise, reorder, or repair them - including
the known defect in the platform's formula text for a chained spread->trajectory,
which must be preserved verbatim and annotated separately.
"""


def contract_request(shape: ColumnShape, section_timeframe: str = "1h",
                     window: int | None = None) -> dict:
    """The payload for get_strategy_column_contract."""
    col = shape.to_column()
    if window is not None:
        col = col.model_copy(update={"window": window})
    return {"column": col.wire(), "sectionTimeframe": section_timeframe}


def render_request(shapes: Sequence[ColumnShape], tickers: Sequence[str],
                   timeframe: str = "1h", title: str = "omega probe") -> dict:
    """The payload for preview_strategy_report: one custom section holding shapes."""
    return {
        "timeframe": timeframe,
        "coinSelection": {"mode": "explicit", "tickers": list(tickers)},
        "sections": [{
            "kind": "custom",
            "title": title,
            "benchmarkTicker": None,
            "columns": [s.to_column().wire() for s in shapes],
        }],
    }
```

- [ ] **Step 4: Create the capture directory**

```bash
mkdir -p data/contract/columns
printf '' > data/contract/columns/.gitkeep
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_probe.py -q`
Expected: PASS, 6 tests.

If `test_every_first_cut_shape_is_legal_before_we_spend_a_call` fails, the chosen
shape is not authorable — pick a different metric offering that transform, using
`omega.space.query(transform="rank", chained=True)` to find a legal `rank`-chain.
Do not weaken the test.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS, 325 tests.

- [ ] **Step 7: Commit**

```bash
git add omega/probe.py tests/test_probe.py data/contract/columns/.gitkeep
git commit -m "Add read-only probe request builders for column contracts and renders"
```

---

### Task 4: Capture the responses and ingest them

**Files:**
- Modify: `omega/probe.py`
- Create: `data/contract/columns/_contracts.json` (captured)
- Create: `data/contract/columns/_renders.json` (captured)
- Modify: `tests/test_probe.py`

**Interfaces:**
- Consumes: Task 3's `FIRST_CUT`, `contract_request`, `render_request`
- Produces:
  - `load_contracts() -> list[dict]` — each `{"request": ..., "response": ...}`
  - `load_renders() -> dict` — `{"request": ..., "response": ...}`
  - `effective_parameters(case: dict) -> dict`
  - `headers(case: dict) -> list[str]`

**This task is performed by the agent, not by code.** The four contract calls and one
render call are run through the MCP connector and their responses saved verbatim.

- [ ] **Step 1: Print the payloads to run**

```bash
python -c "
import json
from omega.probe import FIRST_CUT, contract_request, render_request
for s in FIRST_CUT:
    print(json.dumps(contract_request(s), indent=2))
print(json.dumps(render_request(FIRST_CUT, ['BTC','GOOGL']), indent=2))
"
```

- [ ] **Step 2: Run the five read-only calls**

Run each printed `contract_request` payload through `get_strategy_column_contract`,
and the `render_request` payload through `preview_strategy_report`. Save verbatim:

- `data/contract/columns/_contracts.json` as
  `{"capturedAt": "<ISO8601>", "cases": [{"request": ..., "response": ...}, ...]}`
- `data/contract/columns/_renders.json` as
  `{"capturedAt": "<ISO8601>", "request": ..., "response": ...}`

Do not edit, reorder, or repair any response.

- [ ] **Step 3: Write the failing ingester test**

```python
# append to tests/test_probe.py
import pytest

from omega.probe import (
    effective_parameters, headers, load_contracts, load_renders,
)


def test_every_first_cut_shape_was_captured():
    cases = load_contracts()
    assert len(cases) == len(FIRST_CUT)


def test_effective_parameters_are_read_not_assumed():
    """The platform fills in defaults we never sent. Trap #1 lives here."""
    for case in load_contracts():
        eff = effective_parameters(case)
        assert "bars" in eff, "every compiled column reports an effective bars value"


def test_trajectory_default_window_is_four_not_eight():
    """A guessed default would have been wrong; this pins the measured one."""
    case = next(c for c in load_contracts()
                if c["request"]["column"]["metric"] == "CCI20"
                and c["request"]["column"]["transformId"] == "trajectory"
                and "window" not in c["request"]["column"])
    assert effective_parameters(case)["window"] == 4


def test_fan_out_headers_are_window_plus_trend():
    case = next(c for c in load_contracts()
                if c["request"]["column"].get("chainedTransformId") == "trajectory")
    hs = headers(case)
    window = effective_parameters(case)["window"]
    assert len(hs) == window + 1
    assert hs[-1].endswith("_trend")


def test_the_known_formula_defect_is_stored_verbatim():
    """One-to-one means we keep the platform's wrong text, not a repaired one."""
    case = next(c for c in load_contracts()
                if c["request"]["column"].get("chainedTransformId") == "trajectory"
                and c["request"]["column"]["transformId"] == "spread")
    formula = case["response"]["contract"]["formula"]
    assert "non-null EMA5 values" in formula, (
        "the platform names the base series where the slots hold the spread series; "
        "storing a corrected string here would break the one-to-one guarantee")


def test_renders_carry_at_least_one_real_value():
    """The repo's first number produced by a custom column."""
    payload = load_renders()
    assert payload["response"], "render response must not be empty"
    assert json.dumps(payload["response"]) != "{}"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `python -m pytest tests/test_probe.py -q`
Expected: FAIL — `ImportError: cannot import name 'load_contracts' from 'omega.probe'`

- [ ] **Step 5: Write the ingesters**

```python
# append to omega/probe.py

def _read(name: str) -> dict:
    p = COLUMNS_DIR / name
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not captured yet - run the calls in omega.probe.FETCH_RECIPE")
    return json.loads(p.read_text(encoding="utf-8"))


def load_contracts() -> list[dict]:
    """Captured get_strategy_column_contract cases, verbatim."""
    return _read("_contracts.json")["cases"]


def load_renders() -> dict:
    """The captured preview_strategy_report payload, verbatim."""
    return _read("_renders.json")


def effective_parameters(case: dict) -> dict:
    """The parameters the platform ACTUALLY applied - not the ones we sent.

    Defaults are not guessable: trajectory window is 4, efficiency 21, bars "all".
    Always read this rather than echoing the request.
    """
    return case["response"]["contract"]["effectiveParameters"]


def headers(case: dict) -> list[str]:
    """Output header names, in the order the compiler returned them."""
    return [o["header"] for o in case["response"]["contract"]["outputs"]]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_probe.py -q`
Expected: PASS, 12 tests.

If `test_trajectory_default_window_is_four_not_eight` fails, the platform changed its
default. That is a real finding — record the new value and update the spec and doc 02,
rather than editing the assertion silently.

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS, 331 tests.

- [ ] **Step 8: Commit**

```bash
git add omega/probe.py tests/test_probe.py data/contract/columns/
git commit -m "Capture the first real rendered column values from BattleGrid"
```

---

### Task 5: Document the space

**Files:**
- Create: `docs/14-column-space.md`
- Modify: `README.md` (docs table, `docs/ 00-13` line, test counts)

**Interfaces:**
- Consumes: Tasks 1-4. No new code.

- [ ] **Step 1: Generate the real numbers for the doc**

```bash
python -c "
from omega.space import query, enumerate_shapes, platform_used
print('shapes           ', len(enumerate_shapes()))
print('expanded         ', len(enumerate_shapes(expand_operands=True)))
print('platform pairs   ', len(platform_used()))
print('never used       ', len(query(platform_uses=False)))
print('single-header    ', len(query(max_headers=1)))
"
```

- [ ] **Step 2: Write `docs/14-column-space.md`**

Cover, using the numbers printed in Step 1 — never invented ones:

1. Why the space is finite (chaining capped at 2 stages).
2. The counts table: 1376 pairs, 322 legal atoms, 488 shapes, 2200 expanded.
3. Why parameters are not enumerated, and that effective values come from the platform.
4. The measured defaults — trajectory window 4, efficiency 21, `bars` "all" — and that
   `bars: "all"` includes the live forming bar (cookbook trap #1).
5. The known formula defect, quoted verbatim from the captured contract, with the
   correction stated as an annotation beneath it.
6. What the platform's own 25 templates use, and what that leaves untouched.
7. A worked `explore → explain → author` example using the real captured render.

- [ ] **Step 3: Update the README**

Add to the docs table after the row for doc 13:

```markdown
| [14 · Column Space](docs/14-column-space.md) | every table you could build: 488 shapes, 2200 expanded, and what the platform leaves untouched |
```

Change `docs/              00–13` to `docs/              00–14`, and update both test
counts to the number `python -m pytest -q` actually reports.

- [ ] **Step 4: Verify the doc's claims**

```bash
python -m pytest -q
grep -n "00–14\|14 ·" README.md
```

Every number in the doc must match Step 1's output. Re-read the doc against that
output before committing.

- [ ] **Step 5: Commit**

```bash
git add docs/14-column-space.md README.md
git commit -m "Document the column space: 488 shapes and what the platform never uses"
```

---

## Self-Review

**Spec coverage:**

| spec section | task |
|---|---|
| `space.py` enumeration + query | 1, 2 |
| `probe.py` request builder + ingester | 3, 4 |
| Effective-parameters rule | 4 (`effective_parameters`, window-4 test) |
| Known-defect verbatim policy | 4 (`test_the_known_formula_defect_is_stored_verbatim`), 5 |
| The one real gap — rendered values | 4 |
| Platform-template coverage | 2 (`platform_used`, `query(platform_uses=...)`) |
| Enumeration/drift/honesty testing | 1, 2, 4 |
| First-cut scope: four shapes | 3 (`FIRST_CUT`) |
| `explain.py`, CLI | **deferred by the spec** — not in this plan |

`explain.py` and the CLI are explicitly out of the first cut per the spec's "Scope of the
first cut". They get their own plan once the round-trip is proven.

**Type consistency:** `ColumnShape(metric, transform, chained, operand, ordering)` is used
with that field order in Tasks 1-4. `to_column()` returns `Column`; `contract_request`
calls `.wire()`. `load_contracts()` returns cases shaped `{"request", "response"}`, which
is what `effective_parameters` and `headers` index into, and what Task 4 Step 2 saves.

**Placeholders:** none. Every code step carries runnable code; every test step carries real
assertions.

**One judgement call flagged:** Task 3's `FIRST_CUT` names `VWAP × distance → rank` as the
rank-chain case, taken from doc 03's worked example. Task 3 Step 5 says what to do if it
fails validation — find a legal replacement via `query`, never weaken the test.
