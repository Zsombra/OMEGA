"""The manifest's history, found by contract version rather than by depth.

data/contract/_manifest.json keeps every earlier extraction under `supersedes` and every earlier write surface under
`writeSurface.supersedes`, one level deeper at each re-pin. A test that walked to a block by depth broke at every new
contract (2026-11-12: three re-pins in one morning); one that names the version it means does not.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest() -> dict:
    return json.loads((ROOT / "data/contract/_manifest.json").read_text(encoding="utf-8"))


def chain(top: dict) -> list[dict]:
    """`top` and every block under its `supersedes`, newest first."""
    out, node = [], top
    while node:
        out.append(node)
        node = node.get("supersedes")
    return out


def _find(top: dict, version: str, what: str) -> dict:
    found = [block for block in chain(top) if block.get("servedContractVersion") == version]
    if len(found) != 1:
        raise AssertionError(f"{len(found)} {what} blocks at {version} in the manifest: "
                             f"{[b.get('servedContractVersion') for b in chain(top)]}")
    return found[0]


def extraction(version: str, doc: dict | None = None) -> dict:
    """The extraction block of `version` (the manifest's own top block or one under `supersedes`)."""
    return _find(doc or manifest(), version, "extraction")


def surface(version: str, doc: dict | None = None) -> dict:
    """The write-surface block of `version` (`writeSurface` or one under its `supersedes`)."""
    return _find((doc or manifest())["writeSurface"], version, "write surface")


def versions(top: dict) -> list[str]:
    return [block.get("servedContractVersion") for block in chain(top)]
