# OMEGA v0.10.1: `compare_vocabulary` reads the metric enum through `$defs/metricKey`

**Status: DONE 2026-10-30.** A patch on v0.10.0 (a871e44): one script, three tests, no extraction moved. Served contract
at the time of the fix **144.2.0** (build `2012d43d`, acknowledged by the battlegrid-manager watch 2026-10-30T06:58Z;
144.0.0 -> 144.2.0 touched read tools only).

## Why

`scripts/compare_vocabulary.py` read the live metric vocabulary at `get_metric_construction_hints`
`properties.metric.enum`. Contract **v137.2** named the vocabulary once per schema instead: the property is
`{"$ref": "#/$defs/metricKey"}` and the enum sits under `$defs` (the v0.10.0 record noted the move for the stage
schema, where `omega.contract` already reads it; the comparison script was not changed). On every surface since
v137.2 the script therefore found no enum and raised "no enum found on the surface for: metrics".

battlegrid-manager loads that script by path for its pin-drift gate (`manager/authoring/preflight.py`). Measured on
2026-10-30 against production's stored 144.2.0 surface, every preset's gate build was `FAIL` with `SURFACE_UNREAD` -
the enum was unreadable, not moved - so `manager strategy status` could clear no plan while the watch, the schema checks
and the header probe all passed. The manager's own authoring tests pinned the 110.8.0 / 110.13.0 surfaces, where the
enum is inline, and so never saw it.

## Fix

`first_enum(node, prop, root=None)`: when the property named `prop` carries no `enum` but a `$ref`, the local JSON
pointer is resolved against `root` (the schema the search started in; `node` itself by default) **at the property
looked up and nowhere else**. The 144 stage schema's `$defs` holds `conditionNode`, which refers to itself; a reader
that expanded references while walking would not terminate. A pointer that resolves to nothing, or to a node without
`enum`, reads as no enum here and the search continues - `live_enums` still refuses such a surface ("an absent enum is
unreadable, not empty"), never reports every stored metric removed.

## Proof

- `tests/test_compare_vocabulary.py`: a v137.2-shaped hints schema (the shape read off the watch's stored 144.2.0
  surface) compares identical through the pointer; an unresolvable pointer leaves the surface unreadable; the saved
  144.0.0 stage capture, with its recursive `$defs`, reads both enums without looping, and its REPORT axis's `metric`
  column reads the 302-key enum only when the capture it came from is the root.
- The watch's stored 144.2.0 surface (151 tools, observed 2026-10-30T15:28:39Z), read-only from the manager's
  `system_state`: `metrics 302 / 302, sectionKeys 24 / 24`, nothing on either side, exit 0.
- Full suite: 1731 passed on main at v0.10.0; this branch adds three.

## What a consumer must change (battlegrid-manager)

Re-pin to v0.10.1. Nothing in the extraction, the presets or the write surface moved between v0.10.0 and v0.10.1; a
manager pinned to v0.10.0 (or any earlier tag) reads every surface since v137.2 as `SURFACE_UNREAD`.
