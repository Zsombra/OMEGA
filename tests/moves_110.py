"""Contract 110 for the history tests: a body or record captured before 2026-10-14, as the server now holds it.

README v110: "Strategies, agents and drafts already stored are rewritten by the server; only what you send changes."
data/contract/metrics/_moves_110.json says what moved. A same-series retired metric becomes its replacement (MACD ->
MACD_HIST, PPO -> PPO_HIST: "the same histograms") and a header naming the old code names the new one (`MACD_trend`
-> `MACDhist_trend`). KC_MID -> EMA20 is a different metric and is not rewritten here: a stored KC_MID column has no
same-series successor to become.
"""
from __future__ import annotations

import json
from pathlib import Path

MOVES = json.loads((Path(__file__).resolve().parents[1] / "data/contract/metrics/_moves_110.json")
                   .read_text(encoding="utf-8"))
SAME_SERIES = {old: rec["author"] for old, rec in MOVES["retired"].items() if rec.get("sameSeries")}
CODES = {MOVES["headerCodes"]["before"][old]: MOVES["headerCodes"]["since"][new] for old, new in SAME_SERIES.items()}


def rewritten_at_110(obj):
    def walk(x, key=None):
        if isinstance(x, dict):
            return {k: walk(v, k) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        if isinstance(x, str):
            if key == "metric":
                return SAME_SERIES.get(x, x)
            for old, new in CODES.items():
                if x.startswith(old + "_"):
                    return new + x[len(old):]
        return x
    return walk(obj)
