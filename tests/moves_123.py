"""Contract v123 for the history tests: a header or body captured before 2026-10-20, under the codes served since.

README v123: "A metric's code now ends with its indicator's single length ... Every suffix and prefix is kept
(`ADX14_state`, `dist_donchianLo20`, `RVOL20_rank_hi`) ... Stored strategies, agents, drafts and open positions are
rewritten on the server." data/contract/metrics/_moves_123.json names the eighteen codes. A live render recorded before
v123 printed `CCI_now`; the same column renders `CCI20_now` now - the measurement still pins the header's SHAPE, so a
history test replays it under the codes of today (omega.contract.header_since_123) instead of being re-measured.
"""
from __future__ import annotations

from omega.contract import header_since_123 as header_at_123


def rewritten_at_123(obj):
    """Every `header` string in a stored body, as the server rewrote it at v123. Metric keys do not move."""
    def walk(x, key=None):
        if isinstance(x, dict):
            return {k: walk(v, k) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v, key) for v in x]
        if isinstance(x, str) and key == "header":
            return header_at_123(x)
        return x
    return walk(obj)


__all__ = ["header_at_123", "rewritten_at_123"]
