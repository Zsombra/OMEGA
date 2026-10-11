"""Write data/derived/condition_vocabulary_108.json from the write schema the manifest names.

    python scripts/derive_condition_vocabulary.py          # rewrite the file
    python scripts/derive_condition_vocabulary.py --check  # exit 1 when the stored file differs

Offline: it reads one saved schema file (data/contract/_manifest.json `writeSurface.schema`) and makes no platform call.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omega.condition_vocabulary import OUT, derive_from_disk, render  # noqa: E402


def main(argv: list[str]) -> int:
    text = render(derive_from_disk())
    if "--check" in argv:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("identical" if same else f"{OUT.relative_to(ROOT).as_posix()} differs from the schema's derivation")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
