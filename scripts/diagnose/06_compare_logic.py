"""Compare legacy GT extraction with json2md-style GT from one manifest entry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from bigos.eval.omnidocbench import (  # noqa: E402
    _gt_text_from_layout_legacy,
    gt_markdown_json2md,
    prepare_annos_json2md,
)


def _find_manifest() -> Path:
    candidates = list(Path.home().glob(".cache/huggingface/**/OmniDocBench.json"))
    if not candidates:
        msg = "OmniDocBench.json not found under ~/.cache/huggingface"
        raise FileNotFoundError(msg)
    return candidates[0]


def main() -> None:
    path = _find_manifest()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, list) or not manifest:
        print("Empty manifest", file=sys.stderr)
        sys.exit(1)
    sample_entry = manifest[0]
    layout = sample_entry.get("layout_dets")
    if not isinstance(layout, list):
        layout = []

    our_legacy = _gt_text_from_layout_legacy(layout)
    our_json2md = gt_markdown_json2md(sample_entry)
    annos = prepare_annos_json2md(sample_entry)

    print("=== OUR GT (legacy text-only) ===")
    print(repr(our_legacy[:500]))
    print(f"Length: {len(our_legacy)}")

    print("\n=== OUR GT (json2md mirror) ===")
    print(repr(our_json2md[:500]))
    print(f"Length: {len(our_json2md)}")

    print(f"\n=== prepare_annos_json2md: {len(annos)} annos after filter/merge ===")

    ratio = len(our_json2md) / len(our_legacy) if our_legacy else float("inf")
    print(f"\n=== Length ratio (json2md / legacy) ===\n{ratio:.2f}x")


if __name__ == "__main__":
    main()
