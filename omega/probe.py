"""Request builders and verbatim ingesters for the two read-only column tools.

omega CANNOT CALL MCP TOOLS
---------------------------
This is the house rule (omega/performance.py:244, scripts/build_corpus.py). The
agent runs the connector tools and saves each response verbatim; this module builds
the payloads to hand over and reads the results back. No network client is imported
here, and tests/test_probe.py enforces that against the import graph.

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
`effectiveParameters` off the response rather than echoing what was sent.
"""
from __future__ import annotations

import json
from typing import Sequence

from .contract import CONTRACT_DIR
from .space import ColumnShape

COLUMNS_DIR = CONTRACT_DIR / "columns"

# Four shapes spanning the structurally distinct cases: a plain atom, a chained
# form, a bare fan-out, and one of the 10 shapes that can chain into rank. Each is
# checked against validate_column before a connector call is spent on it.
FIRST_CUT: tuple[ColumnShape, ...] = (
    ColumnShape("RSI14", "value"),                               # atom, 1 header
    ColumnShape("EMA5", "spread", "trajectory", "EMA13", None),  # chain + fan-out
    ColumnShape("CCI20", "trajectory"),                          # bare fan-out
    ColumnShape("VWAP", "distance", "rank", None, None),         # rank-chain
)

FETCH_RECIPE = """\
omega cannot call MCP tools itself. To capture column contracts and the first real
rendered values, run these read-only calls and save each response VERBATIM:

  1. for each shape in omega.probe.FIRST_CUT:
       get_strategy_column_contract(omega.probe.contract_request(shape))
     -> save to data/contract/columns/_contracts.json as
        {"capturedAt": "<ISO8601>", "cases": [{"request": ..., "response": ...}]}

  2. preview_strategy_report(omega.probe.render_request(FIRST_CUT, ["BTC","GOOGL"]))
     -> save to data/contract/columns/_renders.json as
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


# --- reading the captures ---------------------------------------------------

def _read(name: str) -> dict:
    p = COLUMNS_DIR / name
    if not p.exists():
        raise FileNotFoundError(
            f"{p} not captured yet - run the calls in omega.probe.FETCH_RECIPE")
    return json.loads(p.read_text(encoding="utf-8"))


def load_contracts() -> list[dict]:
    """Captured get_strategy_column_contract cases, verbatim.

    Each case is {"request": ..., "response": ...} - the exact payload sent and the
    exact result returned, so a reader can always see what was asked as well as
    what came back.
    """
    return _read("_contracts.json")["cases"]


def load_renders(name: str = "_renders.json") -> dict:
    """One captured preview_strategy_report payload, verbatim."""
    return _read(name)


def load_all_renders() -> list[dict]:
    """Every captured render, oldest file first.

    Renders accumulate one file per capture rather than being merged, so each keeps
    its own `capturedAt` and the request that produced it. A later capture never
    rewrites an earlier one.
    """
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(COLUMNS_DIR.glob("_renders*.json"))]


def effective_parameters(case: dict) -> dict:
    """The parameters the platform ACTUALLY applied - not the ones we sent.

    Defaults are not guessable and are not echoes of the request: `trajectory`
    resolves window to 4, `efficiency` to 21, a chained `rank` resolves ordering to
    "hi", and `bars` resolves to "all" - which includes the live forming bar, so a
    trajectory's `now` slot repeats its last closed observation until that bar
    closes. Always read this rather than assuming.
    """
    return case["response"]["contract"]["effectiveParameters"]


def headers(case: dict) -> list[str]:
    """Output header names, in the order the compiler returned them.

    Note the stem is the metric's `code`, not its key: CCI20 renders as CCI_t3,
    CCI_now, CCI_trend.
    """
    return [o["header"] for o in case["response"]["contract"]["outputs"]]
