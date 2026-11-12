"""OMEGA v0.11.0: the 24 metric keys contract 146.0.0 added, re-extracted at 146.0.1 on 2026-11-02.

From 2026-11-01 (v0.10.2) they were served and known by name only - data/contract/metrics/_unmeasured_108.json, refused
offline as METRIC_UNMEASURED. On 2026-11-02 the v0.10.0 pipeline ran again at the served 146.0.1 (build a07740c0):
refresh_metric_contracts.py (326 hints), list_strategy_categories / list_strategy_vocabulary (eleven categories: `market`
added), build_corpus.py, the targeted subject / scope / applicability probe (scripts/probe_market_section_146.py, 97
probes) and two coverage sweeps, one per section subject. Everything below is a stored measurement of that day; nothing
here calls the platform. Record: docs/plans/2026-11-02-omega-reextraction-146.md.

The axis 146 introduced, measured here: a custom section's `marketScope` selects its SUBJECT, and each subject reads its
own metric domain (served, whole, in the refusal of a column it does not read). null = an evaluated-coin section, 312
metrics; a named scope = a MARKET section, the 13 MKT_*; PAR_DEV is read by neither.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.contract import CONTRACT_DIR, load, metric_subjects
from omega.fanout import outputs_for
from omega.types import Column, CustomSection, Report
from omega.validate import validate_column, validate_report, validate_section

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "data/audit"
COLUMNS = CONTRACT_DIR / "columns"


def _j(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


MOVES = _j(CONTRACT_DIR / "metrics" / "_moves_146.json")
SUBJECTS = _j(CONTRACT_DIR / "metrics" / "_subjects_146.json")
UNMEASURED = _j(CONTRACT_DIR / "metrics" / "_unmeasured_108.json")
PROBE = _j(AUDIT / "market_section_probe_146_2026-11-02.json")
SWEEP_COIN = _j(AUDIT / "coverage_sweep_2026-11-02.json")
SWEEP_MARKET = _j(AUDIT / "coverage_sweep_2026-11-02-market.json")
ZONES = _j(COLUMNS / "zone_vocabulary_146_2026-11-02.json")
MANIFEST = _j(CONTRACT_DIR / "_manifest.json")
COMPARE = _j(AUDIT / "contract_146_0_1_vocabulary_unchanged_2026-11-02.json")

MKT = {"MKT_UP", "MKT_DOWN", "MKT_NET", "MKT_AVG_CHG", "MKT_DISPERSION", "MKT_PPO_UP", "MKT_PPO_DOWN", "MKT_PPO_NET",
       "MKT_AVG_PPO", "MKT_VOL_NET", "MKT_STRETCH", "MKT_ABOVE_EMA", "MKT_UNIVERSE"}
CROWD_Z = {"CROWD_UP_LEAN_Z", "CROWD_UP_EXCESS_Z", "CROWD_CAPT_EXCESS_Z", "CROWD_ACC_EDGE_Z",
           "CROWD_UP_LEAN_Z_LIVE", "CROWD_UP_EXCESS_Z_LIVE", "CROWD_CAPT_EXCESS_Z_LIVE", "CROWD_ACC_EDGE_Z_LIVE"}
WARNINGS = {"REGIME_WARNING_CRASH", "REGIME_WARNING_DIVERGENCE"}
ADDED = MKT | CROWD_Z | WARNINGS | {"PAR_DEV"}
SUBJECT_REFUSAL = "REPORT_COLUMN_SUBJECT_METRIC_UNSUPPORTED"


@pytest.fixture(scope="module")
def contract():
    return load()


def _probe(name: str) -> dict:
    hits = [p for p in PROBE["probes"] if p["probe"] == name]
    assert len(hits) == 1, name
    return hits[0]


def _col(metric: str, transform: str = "value", **extra) -> Column:
    return Column.model_validate({"metric": metric, "transformId": transform, "timeframe": {"rel": "anchor"}, **extra})


def _errors(findings) -> list[str]:
    return [f.code for f in findings if f.severity == "error"]


def _headers(obj, out: set[str]) -> set[str]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "header" and isinstance(v, str):
                out.add(v)
            else:
                _headers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _headers(v, out)
    return out


# --- the roster moved as recorded -------------------------------------------------------------------------------------
def test_the_24_are_in_the_corpus_and_nothing_is_unmeasured(contract):
    assert MOVES["contractVersion"] == "146.0.1" and MOVES["buildSha"].startswith("a07740c0")
    assert set(MOVES["added"]) == ADDED and len(MOVES["added"]) == 24 and MOVES["retired"] == {}
    assert set(MOVES["added_detail"]) == ADDED
    # 326 until the 149.1.0 refresh; 532 at 149.1.0; 534 at 161.0.0 (2026-11-09: BB_TOUCH out, three in)
    # 2026-11-11, contract 168.3.0 (extraction 20261111): 581 - the 47 keys of _moves_168.json in, none out
    moves_168 = _j(CONTRACT_DIR / "metrics" / "_moves_168.json")
    assert (len(moves_168["added"]), moves_168["retired"], moves_168["metrics"]) == (47, [], {"at161": 534, "at168": 581})
    assert ADDED <= set(contract.metrics) and len(contract.metrics) == 534 + len(moves_168["added"]) == 581
    for key in sorted(ADDED):
        assert (CONTRACT_DIR / "metrics" / f"{key}.json").is_file(), key
    # since 2026-11-05 the record lists the 206 keys of the 148.1.0 capture by name (none of these 24)
    assert set(contract.unmeasured_metrics).isdisjoint(ADDED) and set(UNMEASURED["metrics"]).isdisjoint(ADDED)
    assert set(UNMEASURED["history146"]["formerlyUnmeasured"]) == ADDED
    assert (UNMEASURED["history146"]["listedOn"], UNMEASURED["history146"]["measuredOn"]) == ("2026-11-01", "2026-11-02")


def test_the_market_family_is_the_13_mkt_metrics(contract):
    assert set(MOVES["familiesAdded"]) == {"market"}
    assert {m for m in contract.metrics if contract.metric(m).family == "market"} == MKT
    categories = _j(CONTRACT_DIR / "categories.json")
    market = [c for c in categories["categories"] if c["category"] == "market"]
    # 2026-11-11, contract 168: fourteen categories (eleven until then) - the platform split channels, vwapProfile and
    # levels out of structure (_moves_168.json familiesMoved); `market` is untouched, still the 13 MKT_*
    assert len(categories["categories"]) == 14 and len(market) == 1 and market[0]["metricCount"] == 13
    at_161 = {c["category"] for c in _j(CONTRACT_DIR / "vocabulary" / "20261109T1622Z" / "_categories.json")["categories"]}
    assert len(at_161) == 11 and {c["category"] for c in categories["categories"]} - at_161 == {
        "channels", "vwapProfile", "levels"}
    assert not any("market" in move for move in _j(CONTRACT_DIR / "metrics" / "_moves_168.json")["familiesMoved"]["byMove"])
    # re-read 2026-11-05 at 148.1.0 (structure 156 -> 362, market unchanged) and 2026-11-07 at 149.1.0 (nothing moved);
    # the 146.0.1 read three `previous` down since the 161.0.0 re-read of 2026-11-09 (it was two before it); five down
    # since 2026-11-11, which read the categories twice (18:23Z at 168.2.0, 22:32Z at 168.3.0)
    assert categories["_refreshed"]["previous"]["previous"]["previous"]["previous"]["previous"]["contractVersion"] == "146.0.1"
    # a market metric spreads over market metrics only (the served spreadOperands of each of the ten that offer spread)
    for key in sorted(MKT):
        m = contract.metric(key)
        if "spread" in m.transforms:
            assert m.spread_operands and set(m.spread_operands) <= MKT - {key}, key
    assert {k for k in MKT if "spread" not in contract.metric(k).transforms} == {"MKT_STRETCH", "MKT_VOL_NET",
                                                                                   "MKT_UNIVERSE"}


def test_the_served_facts_of_the_crowd_z_and_the_warnings(contract):
    for key in sorted(CROWD_Z):
        m = contract.metric(key)
        assert m.is_timeless and set(m.transforms) == {"value", "rank"}, key
        assert set(m.rank_orderings) == {"hi", "lo", "far", "near"} and m.rank_scope == "report", key
    for key in sorted(WARNINGS):
        m = contract.metric(key)
        assert m.is_timeless and set(m.transforms) == {"value"}, key
        assert m.native_output["kind"] == "classification" and set(m.native_output["vocab"]) == {"raised", "clear"}, key
    # PAR_DEV: hint and vocabulary served, 12 transforms at 146.0.1, 17 since 149.1.0 (+ ema, rma, wma, rsi, cci); read
    # by no subject at 146 and on a pair section since 148 (test_par_dev_is_read_by_no_subject); 18 since 161.0.0
    # (2026-11-09: + roc)
    assert len(contract.metric("PAR_DEV").transforms) == 18 and not contract.metric("PAR_DEV").is_timeless


# --- section subjects: the axis 146 introduced -------------------------------------------------------------------------
def test_the_subject_domains_partition_the_served_enum(contract):
    coin, market = SUBJECTS["subjects"]["evaluated-coin"], SUBJECTS["subjects"]["market"]
    assert coin["marketScope"] is None and isinstance(market["marketScope"], str)
    assert (coin["metricCount"], market["metricCount"]) == (312, 13) and set(market["metrics"]) == MKT
    assert set(coin["metrics"]).isdisjoint(market["metrics"])
    # the 146 measurement covers the 326 it saw; the 206 the 148.1.0 capture added are subject-typed by their own
    # served subjectKinds (_moves_149.json)
    added_148 = set(_j(CONTRACT_DIR / "metrics" / "_moves_149.json")["added"])
    # 161.0.0 (2026-11-09): the three keys 161 added are outside that measurement, and BB_TOUCH (which it covered) is retired
    moves_161 = _j(CONTRACT_DIR / "metrics" / "_moves_161.json")
    # 2026-11-11, contract 168.3.0 (extraction 20261111): the 47 keys 168 added (_moves_168.json, none retired) are
    # outside that measurement too
    moves_168 = _j(CONTRACT_DIR / "metrics" / "_moves_168.json")
    assert len(moves_168["added"]) == 47 and moves_168["retired"] == []
    assert set(coin["metrics"]) | set(market["metrics"]) | set(SUBJECTS["noSubject"]) == (
        (set(contract.metrics) - added_148 - set(moves_161["added"]) - set(moves_168["added"]))
        | set(moves_161["retired"]))
    assert SUBJECTS["servedEnumCount"] == 326 and list(SUBJECTS["noSubject"]) == ["PAR_DEV"]
    assert "is not read on a evaluated-coin section's bars" in coin["refusal"]
    assert "is not read on a market section's bars" in market["refusal"]
    subjects = metric_subjects()
    assert subjects["MKT_UP"] == "market" and subjects["CLOSE"] == "evaluated-coin" and "PAR_DEV" not in subjects
    assert contract.metric("MKT_UP").subject == "market" and contract.metric("RSI14").subject == "evaluated-coin"
    # None at 146.0.1 (no subject read it); since 148 the served subjectKinds say `reference` - a pair section reads it
    assert contract.metric("PAR_DEV").subject == "reference" and contract.metric("PAR_DEV").subject_kinds == ("reference",)


def test_the_domains_were_served_by_the_two_refusals():
    """A.coinSection.domain sent MKT_UP on a null-scope section, A.marketSection.domain sent CLOSE on a crypto section;
    each refusal's allowedDomain.candidates is the whole domain that subject reads."""
    coin, market = _probe("A.coinSection.domain"), _probe("A.marketSection.domain")
    assert not coin["accepted"] and coin["refusal"]["authoringCode"] == SUBJECT_REFUSAL
    assert not market["accepted"] and market["refusal"]["authoringCode"] == SUBJECT_REFUSAL
    assert len(coin["candidates"]) == 312 and set(market["candidates"]) == MKT
    assert coin["sections"][0]["marketScope"] is None and market["sections"][0]["marketScope"] == "crypto"


@pytest.mark.parametrize("key", sorted(MKT))
def test_each_market_metric_renders_on_a_market_section_only(key):
    assert not _probe(f"B.{key}.coin")["accepted"]
    assert _probe(f"B.{key}.coin")["refusal"]["authoringCode"] == SUBJECT_REFUSAL
    assert _probe(f"B.{key}.market")["accepted"]


@pytest.mark.parametrize("key", sorted(CROWD_Z | WARNINGS))
def test_each_coin_metric_renders_on_a_coin_section_only(key):
    assert _probe(f"B.{key}.coin")["accepted"]
    assert not _probe(f"B.{key}.market")["accepted"]
    assert _probe(f"B.{key}.market")["refusal"]["authoringCode"] == SUBJECT_REFUSAL


def test_par_dev_is_read_by_no_subject(contract):
    for arm in ("coin", "market"):
        p = _probe(f"B.PAR_DEV.{arm}")
        assert not p["accepted"] and p["refusal"]["authoringCode"] == SUBJECT_REFUSAL, arm
    assert set(SUBJECTS["noSubject"]["PAR_DEV"]) == {"evaluated-coin", "market"}
    # offline since 148 / 149: the column is fine on its own (METRIC_NO_SUBJECT retired - it read on no section at 146),
    # and refused on a coin and a market section by the subject rule, as the 149.1.0 probe measured (G.coin.PAR_DEV,
    # G.market.PAR_DEV); it renders on a pair section (G.USDT_USD.pair)
    assert _errors(validate_column(_col("PAR_DEV"), contract=contract)) == []
    for scope in (None, "crypto"):
        assert _errors(validate_section(_section(scope, _col("PAR_DEV")), contract=contract)) == [
            "SECTION_SUBJECT_METRIC_UNSUPPORTED"]
    pair = CustomSection.model_validate({"kind": "custom", "title": "t", "benchmarkTicker": "USDT_USD",
                                         "marketScope": None, "columns": [_col("PAR_DEV").model_dump()]})
    assert _errors(validate_section(pair, contract=contract)) == []


def test_the_probe_record_counts():
    assert PROBE["contractVersion"] == "146.0.1" and PROBE["capturedAt"] == "2026-11-02T06:16:10Z"
    assert PROBE["counts"] == {"probes": 97, "accepted": 50, "refused": 47, "headersMinted": 44}
    assert len(PROBE["probes"]) == 97 and sum(p["accepted"] for p in PROBE["probes"]) == 50
    # the one malformed probe is recorded as such, not as a measurement of MKT_UP
    assert PROBE["_notes"] and "D.MKT_UP.value.higher" in PROBE["_notes"][0]


# --- what omega refuses offline, as the platform did live ---------------------------------------------------------------
def _section(scope, *columns: Column) -> CustomSection:
    return CustomSection(title="t", marketScope=scope, columns=list(columns))


def test_omega_refuses_a_column_on_the_wrong_subject(contract):
    coin_sec = _section(None, _col("MKT_UP"))
    assert _errors(validate_section(coin_sec, contract=contract)) == ["SECTION_SUBJECT_METRIC_UNSUPPORTED"]
    assert _errors(validate_section(_section("crypto", _col("CLOSE")), contract=contract)) == [
        "SECTION_SUBJECT_METRIC_UNSUPPORTED"]
    assert _errors(validate_section(_section("crypto", _col("MKT_UP")), contract=contract)) == []
    assert _errors(validate_section(_section(None, _col("CLOSE")), contract=contract)) == []
    # the finding names the column and quotes the platform's wording
    f = [f for f in validate_section(coin_sec, path="s", contract=contract) if f.severity == "error"][0]
    assert f.path == "s.columns[0].metric" and "evaluated-coin section" in f.message
    # through validate_report: one error per offending column, nothing else
    report = Report(anchor="1h", sections=[_section(None, _col("MKT_UP"), _col("MKT_DOWN"), _col("RSI14"))])
    assert _errors(validate_report(report, contract=contract).findings) == ["SECTION_SUBJECT_METRIC_UNSUPPORTED"] * 2


def test_the_applicability_probes_are_what_omega_models(contract):
    # a market metric takes no rank, no relativeTo, no distance - and omega offers none
    for name in ("D.MKT_UP.rank", "D.MKT_UP.relativeTo", "D.MKT_UP.distance"):
        assert not _probe(name)["accepted"], name
    assert {"rank", "relativeTo", "distance"}.isdisjoint(contract.metric("MKT_UP").transforms)
    # a market spread takes a market operand only
    assert not _probe("D.MKT_UP.spread.CROWD_ACC")["accepted"] and _probe("D.MKT_UP.spread.MKT_DOWN")["accepted"]
    assert "CROWD_ACC" not in contract.metric("MKT_UP").spread_operands
    assert _errors(validate_column(_col("MKT_UP", "spread", inputs=[{"metric": "CROWD_ACC"}]), contract=contract))
    assert _errors(validate_column(_col("MKT_UP", "spread", inputs=[{"metric": "MKT_DOWN"}]), contract=contract)) == []
    # a CROWD_*_Z rank takes no scope (rankScope report)
    assert not _probe("D.CROWD_UP_LEAN_Z.rank.scope")["accepted"] and _probe("D.CROWD_UP_LEAN_Z.rank.hi")["accepted"]
    assert _errors(validate_column(_col("CROWD_UP_LEAN_Z", "rank", ordering="hi", scope="crypto"), contract=contract))
    assert _errors(validate_column(_col("CROWD_UP_LEAN_Z", "rank", ordering="hi"), contract=contract)) == []
    # the warnings are value-only
    assert _probe("D.REGIME_WARNING_CRASH.value")["accepted"]
    assert not _probe("D.REGIME_WARNING_CRASH.trajectory")["accepted"]
    assert not _probe("D.REGIME_WARNING_DIVERGENCE.classifyZone")["accepted"]
    assert _errors(validate_column(_col("REGIME_WARNING_CRASH", "trajectory"), contract=contract))


# --- headers and zones --------------------------------------------------------------------------------------------------
def test_market_headers_carry_no_scope_token(contract):
    """mktUp on a crypto section and on an l1 section mint the same header (probe C: the nine scopes, each accepted)."""
    assert [o.header for o in outputs_for(_col("MKT_UP"), contract)] == ["mktUp"]
    assert [o.header for o in outputs_for(_col("MKT_ABOVE_EMA", "classifyZone"), contract)] == ["mktAboveEma_zone"]
    assert [o.header for o in outputs_for(_col("MKT_UP", "spread", inputs=[{"metric": "MKT_DOWN"}]), contract)] == [
        "mktUp_mktDown_spread"]
    scopes = [p for p in PROBE["probes"] if p["probe"].startswith("C.")]
    assert len(scopes) == 9 and all(p["accepted"] for p in scopes)
    assert {h for p in scopes for h in _headers(p["render"], set())} == {"mktUp"}


def test_the_zone_vocabularies_146_added(contract):
    assert ZONES["contractVersion"] == "146.0.1"
    assert ZONES["byMetric"]["MKT_ABOVE_EMA"] == ["risk-off", "neutral", "risk-on"]
    for key in ("CVD", "CUM_VOLUME_DELTA", "SPOT_CVD"):
        assert ZONES["byMetric"][key] == ["bullish", "bearish", "neutral"], key
        assert "classifyZone" in contract.metric(key).transforms, key
    assert "PAR_DEV" not in ZONES["byMetric"]
    zone = outputs_for(_col("MKT_ABOVE_EMA", "classifyZone"), contract)[0]
    assert zone.kind == "classification" and list(zone.vocabulary) == ["risk-off", "neutral", "risk-on"]
    assert list(outputs_for(_col("CVD", "classifyZone"), contract)[0].vocabulary) == ["bullish", "bearish", "neutral"]
    assert {o["header"] for o in ZONES["probe146"]["outputs"]} >= {"CVD_zone", "cumVolDelta_zone", "spotCVD_zone",
                                                                     "regState"}


# --- the two sweeps ----------------------------------------------------------------------------------------------------
def test_the_two_sweeps_rendered_everything_they_asked_for():
    # the coin sweep: the ten coin-subject metrics 146 added plus the three that gained classifyZone (CVD and kin)
    assert SWEEP_COIN["marketScope"] is None
    assert set(SWEEP_COIN["metricsRestrictedTo"]) == CROWD_Z | WARNINGS | {"CVD", "CUM_VOLUME_DELTA", "SPOT_CVD"}
    assert (SWEEP_COIN["shapesRequested"], SWEEP_COIN["headersMinted"]) == (200, 268)
    assert SWEEP_MARKET["marketScope"] == "crypto" and set(SWEEP_MARKET["metricsRestrictedTo"]) == MKT
    assert (SWEEP_MARKET["shapesRequested"], SWEEP_MARKET["headersMinted"]) == (1015, 1419)
    for rec in (SWEEP_COIN, SWEEP_MARKET):
        assert rec["refusalCount"] == 0 and rec["predictedButNotRenderedCount"] == 0
    coin = set(_j(COLUMNS / "_coverage_sweep_2026-11-02.json")["headers"])
    market = set(_j(COLUMNS / "_coverage_sweep_2026-11-02-market.json")["headers"])
    assert len(coin) == 268 and len(market) == 1419
    assert all(h.startswith("mkt") for h in market)
    assert {"upLeanZ_rank_lo", "upLeanZLive_rank_far", "CVD_cumVolDelta_spread"} <= coin


# --- the surface, the manifest, the version ----------------------------------------------------------------------------
def test_the_live_surface_compared_clean():
    assert COMPARE["compare"]["contractVersion"] == "146.0.1" and COMPARE["compare"]["liveToolCount"] == 151
    r = COMPARE["compare"]["results"]
    assert r["metrics"] == {"live": 326, "stored": 326, "liveNotStored": [], "storedNotLive": [],
                            "storedUnmeasured": []}
    assert r["sectionKeys"]["live"] == r["sectionKeys"]["stored"] == 22 and r["sectionKeys"]["storedUnmeasured"] == []


def test_the_manifest_chain_and_the_templates():
    # the 146.0.1 extraction is the one under `supersedes` since the 161.0.0 extraction (2026-11-09; test_v161.py)
    # 2026-11-11, contract 168.3.0 (extraction 20261111): the manifest's own block is the 168.3.0 extraction, the 161.0.0
    # one is its `supersedes` and the 146.0.1 one sits under that - two levels down, it was one
    # 2026-11-12: found by version, not depth (tests/manifest_chain.py); the chain on top of it then was
    # 171.0.0 -> 169.4.0 -> 168.3.0 -> 161.0.0 -> 146.0.1
    from tests.manifest_chain import extraction, surface, versions
    assert versions(MANIFEST)[:5] == ["171.0.0", "169.4.0", "168.3.0", "161.0.0", "146.0.1"]
    ext = extraction("146.0.1", MANIFEST)
    assert ext["servedContractVersion"] == "146.0.1" and ext["extractedOn"] == "2026-11-02"
    assert ext["supersedes"]["servedContractVersion"] == "144.0.0"
    assert ext["counts"]["metrics"] == 326 and ext["counts"]["families"] == 11
    # the write surface moved to the 148.1.0 capture on 2026-11-05 and to the 149.1.0 one on 2026-11-07; the 146.0.1
    # live check is two levels under `supersedes`; three since the 161.0.0 capture of 2026-11-09 (149.1.0 sits between);
    # four since the 168.3.0 capture of 2026-11-11 (168.3.0 -> 161.0.0 -> 149.1.0 -> 148.1.0 -> the 146.0.0 capture)
    v146_capture = surface("146.0.0", MANIFEST)
    assert v146_capture["servedContractVersion"] == "146.0.0"
    assert v146_capture["liveCheckedAt"]["contractVersion"] == "146.0.1"
    assert "derive_strategy_rule_view" not in MANIFEST["toolsUsed"]
    templates = _j(CONTRACT_DIR / "templates" / "platform" / "_all.json")
    by_key = {t["sectionKey"]: t for t in templates["templates"]}
    assert len(by_key) == 22 and "includeMarketBreadth" not in by_key
    regime = {(c["metric"], c["transformId"]) for c in by_key["includeRegimeContext"]["columns"]}
    assert {(k, "value") for k in WARNINGS} <= regime
    crowd = {(c["metric"], c["transformId"]) for c in by_key["includeCrowdIntelligence"]["columns"]}
    assert {(k, "value") for k in CROWD_Z} <= crowd
    # re-read 2026-11-05 at 148.1.0 (ema, conditionFrameReads 2048) and 2026-11-07 at 149.1.0; 146.0.1 two `previous` down
    # 161.0.0 (2026-11-09): three down, was two
    # 2026-11-11, contract 168: five down - the shared blocks were read twice that day (18:23Z at 168.2.0, 22:32Z at
    # 168.3.0), each read pushing the earlier ones one `previous` deeper
    shared = _j(CONTRACT_DIR / "vocabulary" / "_shared.json")["_refreshed"]
    assert (shared["contractVersion"], shared["previous"]["contractVersion"]) == ("168.3.0", "168.2.0")
    assert shared["previous"]["previous"]["previous"]["previous"]["previous"]["contractVersion"] == "146.0.1"


def test_the_version_moved_past_0_11_0():
    # 0.11.0 was this re-extraction's release; 0.12.0 since the cut at contract 161.0.0 (2026-11-10); 0.12.2 since
    # 2026-11-11 (the joint depth bound of a rolling-inner chain, tests/test_v0_12_2.py); 0.13.0 the same day (the
    # re-extraction at contract 168.3.0, tests/test_v168.py); 0.13.1 on 2026-11-12 (tests/test_v169.py); 0.14.0 the same
    # day (exit plans, tests/test_exit_plans_170.py); 0.14.1 the same day (the chain window limits, tests/test_v0_14_1.py;
    # the exit plan's runner, tests/test_exit_plan_runner_171.py)
    assert 'version = "0.14.1"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
