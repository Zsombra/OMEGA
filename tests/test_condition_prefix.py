"""The condition-key prefix (v0.8.2): every key the generator emits matches the platform's
^[A-Z][A-Z0-9_]{1,39}$, whatever the strategy is called.

Found by the strategist's first Hermes-path proof (2026-10-17): names led by a timeframe
("4h Moving Average ...", "1h Breakout ...") gave keys like `4M_UP` and `1B_CORE_UP`, which the
platform refuses. The rule pinned here: the legacy prefix (first character of each of the first
two words, uppercased) whenever the platform accepts it; otherwise the first ASCII letter of each
of the name's first two words that have one, uppercased; "SETUP" when no word has a letter."""
from __future__ import annotations

import random
import string
from dataclasses import replace

import pytest

from omega.conditions import CONDITION_KEY
from omega.generate import (CONDITION_PREFIX_FALLBACK, EXIT_ROLES, PRESETS, Thesis,
                            condition_prefix, plan)

TWO_DIRECTIONAL = {"RSI": 2, "MACD": 2, "MOVING_AVERAGES": 1}


def _keys(name: str, *, exits: tuple[str, ...] = EXIT_ROLES) -> list[str]:
    t = Thesis(name=name, weights=TWO_DIRECTIONAL, exits=list(exits))
    return [c["conditionKey"] for c in plan(t).conditions]


@pytest.mark.parametrize("name, prefix", [
    # digit-led: the digit word still has a letter, and that letter is its initial
    ("4h Low-Vol Fade", "HL"),
    ("4h Moving Average Cross", "HM"),
    ("1h Breakout Retest", "HB"),
    ("15m Scalp", "MS"),
    # punctuation-only words are skipped; punctuation-led words give their first letter
    ("-- Fade --", "F"),
    ("*** !!! ???", CONDITION_PREFIX_FALLBACK),
    ("(Trend) [Follow]", "TF"),
    # empty and whitespace-only
    ("", CONDITION_PREFIX_FALLBACK),
    ("   ", CONDITION_PREFIX_FALLBACK),
    ("2024 365", CONDITION_PREFIX_FALLBACK),
    # non-ASCII letters are not [A-Z]; the first ASCII letter of the word is used
    ("Élan Vital", "LV"),
    ("Ünïcode Straße", "NS"),
    ("日本 Momentum", "M"),
    # one word
    ("Fade", "F"),
    # a legacy prefix the platform accepts is kept, digit and all
    ("PVM 15m", "P1"),
    ("Fade 2x", "F2"),
])
def test_the_prefix_rule(name, prefix):
    assert condition_prefix(name) == prefix


@pytest.mark.parametrize("name", ["4h Low-Vol Fade", "", "*** !!!", "Élan Vital", "1h Breakout"])
def test_every_emitted_key_matches_the_platform_pattern(name):
    keys = _keys(name)
    assert len(keys) == len(EXIT_ROLES) * 2          # seven entry conditions + seven CLOSE_ON_ splits
    bad = [k for k in keys if not CONDITION_KEY.match(k)]
    assert not bad, bad


def test_a_name_the_platform_already_accepted_keeps_its_prefix():
    """No stored key moves: wherever the pre-0.8.2 prefix (the first character of each of the
    first two words) was legal - every name whose first two words start with ASCII letters, and
    a letter-led name whose second word starts with a digit - it is still the prefix."""
    def before(name: str) -> str:
        return "".join(w[0] for w in name.split()[:2]).upper() or "SETUP"
    names = [t.name for t in PRESETS.values()] + [
        "Deep Tail Fade", "momentum ignition", "Fade", "A B C D", "Spot-Led Accumulation",
        "EMA20 Flip", "ESC Alpha", "PVM 15m", "Fork B", "OMEGA-TEST sandbox", "Fade 2x", "Trend_ follow"]
    for name in names:
        assert condition_prefix(name) == before(name), name


def test_preset_keys_are_pinned():
    assert {k: condition_prefix(t.name) for k, t in PRESETS.items()} == {
        "mean-reversion": "MR", "trend-continuation": "TC", "squeeze-breakout": "SB",
        "flow-divergence": "SA", "structure-reversal": "SR"}


@pytest.mark.parametrize("preset", sorted(PRESETS))
def test_a_revision_of_an_existing_strategy_keeps_its_keys(preset):
    """The UPDATE path (axes_update) re-stages CONDITIONS from the thesis; the keys it sends
    must be the keys the strategy already holds."""
    p = plan(replace(PRESETS[preset], exits=list(EXIT_ROLES)))
    current = p.axes()
    held = [c["conditionKey"] for c in current["CONDITIONS"]["conditions"]]
    staged = [c["conditionKey"] for c in p.axes_update(current)["CONDITIONS"]["conditions"]]
    assert staged == held


def _synthetic_names(n: int = 20) -> list[str]:
    rng = random.Random(20261017)
    alphabet = string.ascii_letters + string.digits + string.punctuation + "éüßÆ日本 "
    fixed = ["4h", "1h Breakout", "", "   ", "99 Problems", "#1 Setup", "__init__", "x",
             "ÄÖÜ äöü", "a" * 200]
    rand = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30)))
            for _ in range(n - len(fixed))]
    return fixed + rand


def test_sweep_presets_and_synthetic_names():
    names = [t.name for t in PRESETS.values()] + _synthetic_names()
    assert len(names) == len(PRESETS) + 20
    for name in names:
        prefix = condition_prefix(name)
        assert CONDITION_KEY.match(f"{prefix}_UP"), (name, prefix)
        longest = f"CLOSE_ON_{prefix}_CORE_DOWN"
        assert len(longest) <= 40 and CONDITION_KEY.match(longest), (name, longest)
        for key in _keys(name):
            assert CONDITION_KEY.match(key), (name, key)
