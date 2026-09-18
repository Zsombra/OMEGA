"""Write a platform-drift record from a schema-drift preflight receipt.

    python scripts/write_drift.py <receipt.json> <previous-schema-capture.json> <out.json>

A drift record states what MOVED between two dated compile-definition captures. Nothing
here is typed by hand: every list is parsed out of the receipt's own CHANGELOG findings
(`omega.preflight.changelog` over the two captures, formatted by the CLI's
`--previous-schema` run), and the contract versions are read out of the captures' own
`how` lines, the extraction manifest and the vendor package. The script cannot make the
record say anything the receipt does not.

Two prose blocks are the exceptions, and both name their source: what the preflight
refused BEFORE the fix (that run's receipts were not kept; the counts are the plan's
measured-facts table) and what this plan did not resolve.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Quoted from docs/superpowers/plans/2026-09-18-contract-61-authoring-surface.md, the first
# row of "Measured facts this plan relies on": `scripts/preflight.py run` at 08:40 UTC over
# the five `plan(PRESETS[...]).wire()` bodies, against the same captures this receipt names.
REFUSED_BEFORE_THE_FIX = {
    "_source": ("docs/superpowers/plans/2026-09-18-contract-61-authoring-surface.md, "
                "'Measured facts' row 1 - scripts/preflight.py run 2026-09-18T08:40Z over the "
                "five preset bodies; that run's receipts were not kept, these are its counts"),
    "verdict": "FAIL",
    "perBody": [
        "7 x FAIL UNDECLARED conditions[i].clock",
        "1 x FAIL ENUM entry.trigger 'AT_SIGNAL' not in the declared enum (3 values)",
        "3 x FAIL UNDECLARED entry keys: entry.confirmTf, entry.closes, entry.bandAtrMultiple",
        "1 x WARN MIRROR entry.trigger body 'AT_SIGNAL' vs record 'ON_CANDLE_CLOSE'",
        ("~93 x WARN UNSUPPORTED ... ['multipleOf'] (every closes, every rules[i].allocation, "
         "minAggregateScore, minRequiredCount, entry.levelOffsetAtrMultiple)"),
    ],
}

NOT_RESOLVED = [
    {
        "what": ("The metric/transform/vocabulary EXTRACTION (data/contract/_manifest.json) is still "
                 "the 2026-09-09 one at contract 54.1.0."),
        "whyItMatters": ("metricEnumAdded below shows the compile schema's metric enum has grown since "
                         "that extraction, so the repo's metric catalogue, the composability matrix and "
                         "every count derived from them (docs 00/01/03/14/18, README) under-report the "
                         "served platform. This plan changed the authoring surface only; it did not "
                         "re-extract, and it did not measure what the added keys mean."),
        "owner": "a re-extraction session (read-only, the 2026-09-09 recipe), not this plan",
    },
    {
        "what": ("The TPO branch claude/tpo-strategy-brainstorm-796f15 pins the pre-60 entry: "
                 "tests/test_tpo_suite_wire.py asserts builder.ENTRY_MIRROR carries confirmTf."),
        "whyItMatters": ("that test fails against the three-key entry on this branch; the branch must be "
                         "brought to {trigger, levelOffsetAtrMultiple, validForBars} when it is merged "
                         "(a Phase 4 prerequisite)."),
        "owner": "whoever merges the TPO branch",
    },
]

_ENUM = re.compile(r"^enum added (\[.*\]) removed (\[.*\])$")
_REQUIRED = re.compile(r"^required (\[.*\]) -> (\[.*\])$")
_PROPERTIES = re.compile(r"^properties added (\[.*\]) removed (\[.*\])$")
_BOUNDS = re.compile(r"^bounds (\{.*\}) -> (\{.*\})$")
_VERSION = re.compile(r"contract (\d+\.\d+\.\d+)")
_BUILD = re.compile(r"build ([0-9a-f]{6,40})")


def parse_changelog(receipt: dict) -> dict:
    """Group the receipt's CHANGELOG findings by the kind of move each records.

    The detail strings are the ones `omega.preflight.changelog` formats, so their payloads
    are Python literals and are read back with ast.literal_eval - never re-typed. An
    unrecognised detail stops the script rather than being dropped silently."""
    moves: dict[str, object] = {"schemaPathsRemoved": [], "schemaPathsAdded": [], "enumsChanged": {},
                                "requiredListsChanged": {}, "propertiesChanged": {}, "boundsChanged": {}}
    for f in receipt["findings"]:
        if f["cls"] != "CHANGELOG":
            continue
        path, detail = f["path"], f["detail"]
        if detail == "removed from the current schema":
            moves["schemaPathsRemoved"].append(path)
        elif detail == "new in the current schema":
            moves["schemaPathsAdded"].append(path)
        elif m := _ENUM.match(detail):
            moves["enumsChanged"][path] = {"added": ast.literal_eval(m.group(1)),
                                           "removed": ast.literal_eval(m.group(2))}
        elif m := _REQUIRED.match(detail):
            moves["requiredListsChanged"][path] = {"previous": ast.literal_eval(m.group(1)),
                                                   "current": ast.literal_eval(m.group(2))}
        elif m := _PROPERTIES.match(detail):
            moves["propertiesChanged"][path] = {"added": ast.literal_eval(m.group(1)),
                                                "removed": ast.literal_eval(m.group(2))}
        elif m := _BOUNDS.match(detail):
            moves["boundsChanged"][path] = {"previous": ast.literal_eval(m.group(1)),
                                            "current": ast.literal_eval(m.group(2))}
        else:
            raise SystemExit(f"unparsed CHANGELOG detail at {path!r}: {detail!r}")
    return moves


def capture_version(path: str) -> dict:
    """What a capture states about itself: when it was taken and which contract served it."""
    doc = json.loads((ROOT / path).read_text(encoding="utf-8"))
    how = doc["how"]
    v, b = _VERSION.search(how), _BUILD.search(how)
    return {"capture": path, "capturedAt": doc["capturedAt"],
            "contractVersion": v.group(1) if v else None,
            "buildSha": b.group(1) if b else None, "how": how}


def main() -> None:
    receipt_path, previous_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    receipt = json.loads((ROOT / receipt_path).read_text(encoding="utf-8"))
    moves = parse_changelog(receipt)
    current = capture_version(receipt["captures"]["schema"]["path"])
    previous = capture_version(previous_path)
    manifest = json.loads((ROOT / "data/contract/_manifest.json").read_text(encoding="utf-8"))
    package = json.loads((ROOT / ".agents/skills/battlegrid/package.json").read_text(encoding="utf-8"))
    export = json.loads((ROOT / ".agents/skills/battlegrid/skills/EXPORT.json").read_text(encoding="utf-8"))

    # The 2026-09-09 capture's `how` line states the contract version but not the build sha. The
    # extraction manifest records the same GET /mcp/version read, at the capture's own second, and
    # states it - taken only when both the second and the version agree, never assumed.
    if (previous["buildSha"] is None
            and previous["capturedAt"] in manifest["contractVersionSource"]
            and manifest["servedContractVersion"] == previous["contractVersion"]):
        if b := _BUILD.search(manifest["contractVersionSource"]):
            previous["buildSha"] = b.group(1)
            previous["buildShaSource"] = ("data/contract/_manifest.json contractVersionSource - the same "
                                          "GET /mcp/version read, at the capture's own second")

    # The named axes, each one a slice of the parsed moves - not a second, hand-typed copy.
    conditions_props = moves["propertiesChanged"].get("conditions[]", {})
    conditions_required = moves["requiredListsChanged"].get("conditions[]", {})
    entry_props = moves["propertiesChanged"].get("entry", {})
    entry_required = moves["requiredListsChanged"].get("entry", {})
    trigger_enum = moves["enumsChanged"].get("entry.trigger", {})
    metric_enums = {p: v for p, v in moves["enumsChanged"].items() if p.endswith(".metric")}
    metric_added = sorted({k for v in metric_enums.values() for k in v["added"]})
    metric_removed = sorted({k for v in metric_enums.values() for k in v["removed"]})

    record = {
        "_what": (
            f"Measured drift on the COMPILE DEFINITION between {previous['capturedAt']} (contract "
            f"{previous['contractVersion']}, build {previous['buildSha']}) and {current['capturedAt']} "
            f"(contract {current['contractVersion']}, build {current['buildSha']}). Every list below is "
            f"parsed by scripts/write_drift.py out of the CHANGELOG findings of the preflight receipt "
            f"named under evidence.receipt - none was typed by hand, and the record can say nothing the "
            f"receipt does not. Read-only throughout: omega never calls BattleGrid, and the two captures "
            f"were taken by the manager's watch and by get_strategy. This record covers the AUTHORING "
            f"SURFACE only; see notResolved for what it does not cover."),
        "measuredAt": receipt["when"],
        "evidence": {
            "receipt": receipt.get("receiptPath") or receipt_path,
            "receiptVerdict": receipt["verdict"],
            "gateLine": receipt["gateLine"],
            "body": receipt["body"],
            "schemaCurrent": current,
            "schemaPrevious": previous,
            "readback": receipt["captures"]["readback"],
            "readbackOfTheMigratedRecord": (
                "data/contract/get_strategy/824f4343-e51f-4e5a-87b1-6b44d0bc547f_20260918T084500Z.json "
                "- created 2026-09-03 with entry.trigger AT_SIGNAL and six entry keys, revision still 1: "
                "what it reads back now is the platform's own migration, not an authoring choice"),
            "captureAge": (
                "The captures are the ones committed with the plan at 21b4bbd (08:33:59Z and 08:35:00Z) "
                "and were NOT re-taken for this run, so the receipt was produced with "
                "--expires-minutes 1440 instead of the default 60. The gate line's expiry is measured "
                "from the schema capture, and a compile authorization must re-capture."),
            "vendorPackage": (f".agents/skills/battlegrid ({package['name']} {package['version']}; "
                              f"skills/EXPORT.json contractVersion {export['contractVersion']})"),
            "writer": "scripts/write_drift.py",
        },
        "contractVersion": {
            "previous": {"contractVersion": previous["contractVersion"], "buildSha": previous["buildSha"],
                         "statedBy": previous["capture"],
                         "buildShaSource": previous.get("buildShaSource")},
            "current": {"contractVersion": current["contractVersion"], "buildSha": current["buildSha"],
                        "statedBy": current["capture"]},
            "extractionManifest": {"extractedOn": manifest["extractedOn"],
                                   "servedContractVersion": manifest["servedContractVersion"],
                                   "contractVersionSource": manifest["contractVersionSource"]},
        },
        "conditions": {
            "keysRemoved": conditions_props.get("removed", []),
            "keysAdded": conditions_props.get("added", []),
            "requiredPrevious": conditions_required.get("previous", []),
            "requiredCurrent": conditions_required.get("current", []),
        },
        "entry": {
            "keysRemoved": entry_props.get("removed", []),
            "keysAdded": entry_props.get("added", []),
            "requiredPrevious": entry_required.get("previous", []),
            "requiredCurrent": entry_required.get("current", []),
            "triggerEnumRemoved": trigger_enum.get("removed", []),
            "triggerEnumAdded": trigger_enum.get("added", []),
        },
        "boundsMoved": moves["boundsChanged"],
        "metricEnumAdded": {
            "keys": metric_added,
            "removed": metric_removed,
            "paths": sorted(metric_enums),
            "_note": (
                f"{len(metric_added)} keys across {len(metric_enums)} column paths"
                + ("; the same list on each" if len({tuple(v["added"]) for v in metric_enums.values()}) == 1
                   else "; the paths differ - see schemaMoves.enumsChanged")
                + f". The plan's measured-facts table FIRST named only nine TPO keys of this list, read off "
                  f"a truncated changelog line; it was corrected in commit 48efdee to the {len(metric_added)} "
                  f"the changelog actually carries, which is the list above. What any of them MEANS is "
                  f"unmeasured here - see notResolved."),
        },
        "schemaMoves": moves,
        "refusedBeforeTheFix": REFUSED_BEFORE_THE_FIX,
        "notResolved": NOT_RESOLVED,
    }
    out = ROOT / out_path
    out.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out_path}: {len(moves['schemaPathsRemoved'])} paths removed, "
          f"{len(moves['boundsChanged'])} bounds moved, {len(metric_added)} metric keys added")


if __name__ == "__main__":
    main()
