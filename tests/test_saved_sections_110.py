"""A player's saved report sections are never platform vocabulary.

Since contract 110.x (observed by 110.8.0, 2026-10-15) `list_strategy_vocabulary` lists "the platform's templates,
then the player's own saved sections as `kind: "saved"` (the live library, which `vocabularyDigest` does not cover)",
and `save_report_section` / `remove_saved_report_section` write that library. A saved section is account state: it
changes whenever the player saves one and differs per account, so omega must never extract it as if the platform
served it. The 2026-10-15 read held none (the account had saved nothing); this keeps it that way for every snapshot.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOCABULARY = ROOT / "data" / "contract" / "vocabulary"
PLATFORM_TEMPLATES = ROOT / "data" / "contract" / "templates" / "platform" / "_all.json"


def _snapshot_templates():
    for path in sorted(VOCABULARY.glob("*/*.json")):
        if path.name.startswith("_"):
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for template in doc.get("templates") or []:
            yield path, template


def test_no_stored_vocabulary_snapshot_holds_a_saved_section():
    kinds = {}
    for path, template in _snapshot_templates():
        kinds.setdefault(template.get("kind"), []).append(path.parent.name)
    assert "saved" not in kinds, f"a player's saved section was stored as vocabulary: {sorted(set(kinds['saved']))}"
    assert set(kinds) <= {"platform", "custom"}


def test_the_platform_templates_are_platform_only():
    templates = json.loads(PLATFORM_TEMPLATES.read_text(encoding="utf-8"))["templates"]
    assert templates and all(t.get("kind", "platform") == "platform" for t in templates)
    assert not any("savedSectionId" in t for t in templates)
