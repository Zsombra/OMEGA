"""Schema-drift preflight (design 2026-09-04). Pure functions; the fixtures are a
hand-built walker miniature and the REAL records named in the plan. The miniature is a
walker fixture only - never a regression oracle for wire()."""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

import pytest

from omega import preflight as P

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "preflight"
MINI = json.loads((FIX / "schema_walker_min.json").read_text(encoding="utf-8"))


def test_module_imports_no_network_client():
    """The house rule (omega/probe.py:3), enforced against the import graph."""
    tree = ast.parse(inspect.getsource(P))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"requests", "httpx", "urllib", "aiohttp", "socket", "http"}


def test_finding_is_frozen_and_has_the_four_fields():
    f = P.Finding("ENUM", "entry.trigger", "x", "FAIL")
    assert (f.cls, f.path, f.detail, f.verdict) == ("ENUM", "entry.trigger", "x", "FAIL")
    with pytest.raises(Exception):
        f.cls = "INFO"  # type: ignore[misc]


def test_resolve_arms_selects_by_operation_const_and_returns_root():
    arms, root = P.resolve_arms(MINI)
    assert set(arms) == {"CREATE", "UPDATE"}
    assert arms["CREATE"]["properties"]["operation"]["const"] == "CREATE"
    assert root is MINI["parameters"]


def test_deref_follows_local_refs_relative_to_parameters():
    arms, root = P.resolve_arms(MINI)
    tf = P.deref(arms["UPDATE"]["properties"]["timeframe"], root)
    assert tf["enum"] == ["1h", "4h"]
    # a ref inside a ref target
    entry = P.deref(arms["UPDATE"]["properties"]["entry"], root)
    assert P.deref(entry["properties"]["confirmTf"], root)["enum"] == ["1h", "4h"]


def test_deref_refuses_non_local_refs():
    with pytest.raises(P.UnsupportedSchema):
        P.deref({"$ref": "https://example.invalid/schema#/x"}, MINI["parameters"])
