"""Print the current _gt_text_from_layout logic and a category histogram of layout_dets."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
OMNI_PATH = _ROOT / "src/bigos/eval/omnidocbench.py"


def _extract_gt_text_from_layout_source() -> str | None:
    text = OMNI_PATH.read_text(encoding="utf-8")
    m = re.search(
        r"(^def _gt_text_from_layout\(layout_dets:.*?\n)(?=^def |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    return m.group(1).rstrip() if m else None


src = _extract_gt_text_from_layout_source()
if src is None:
    print(f"⚠️ Could not extract _gt_text_from_layout from {OMNI_PATH}")
else:
    print("=== Current source of _gt_text_from_layout (from omnidocbench.py) ===\n")
    print(src)

hf_cache_candidates = [
    Path.home() / ".cache" / "huggingface" / "hub",
    Path.home() / ".cache" / "huggingface" / "datasets",
]
manifest_files: list[Path] = []
for c in hf_cache_candidates:
    if c.exists():
        manifest_files.extend(c.rglob("OmniDocBench.json"))

if not manifest_files:
    print("\n⚠️ OmniDocBench.json not found in HF cache; skipping category histogram")
else:
    mpath = manifest_files[0]
    print(f"\n=== Found manifest: {mpath} ===\n")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))

    print(f"Manifest type: {type(manifest).__name__}")
    if isinstance(manifest, list):
        print(f"Manifest entries: {len(manifest)}")

        first = manifest[0]
        if isinstance(first, dict):
            print(f"\nFirst entry keys: {list(first.keys())}")

        cat_counter: Counter[str] = Counter()
        cat_with_text: Counter[str] = Counter()
        cat_with_html: Counter[str] = Counter()
        cat_with_latex: Counter[str] = Counter()
        for entry in manifest[:100]:
            if not isinstance(entry, dict):
                continue
            for det in entry.get("layout_dets", []) or []:
                if not isinstance(det, dict):
                    continue
                cat = str(det.get("category_type") or det.get("category") or "unknown")
                cat_counter[cat] += 1
                if det.get("text"):
                    cat_with_text[cat] += 1
                if det.get("html"):
                    cat_with_html[cat] += 1
                if det.get("latex"):
                    cat_with_latex[cat] += 1

        print("\n=== Category histogram (first 100 entries) ===")
        print(
            f"{'Category':<30s}  {'Count':>8s}  {'has text':>10s}  "
            f"{'has html':>10s}  {'has latex':>10s}"
        )
        for cat, count in cat_counter.most_common():
            print(
                f"{cat:<30s}  {count:>8d}  {cat_with_text[cat]:>10d}  "
                f"{cat_with_html[cat]:>10d}  {cat_with_latex[cat]:>10d}"
            )

        print("\n=== Sample layout_det per category ===")
        seen: set[str] = set()
        for entry in manifest:
            if not isinstance(entry, dict):
                continue
            for det in entry.get("layout_dets", []) or []:
                if not isinstance(det, dict):
                    continue
                cat = str(det.get("category_type") or det.get("category") or "unknown")
                if cat not in seen:
                    seen.add(cat)
                    print(f"\n--- category: {cat} ---")
                    print(json.dumps(det, indent=2, ensure_ascii=False)[:800])
                    if len(seen) >= 10:
                        break
            if len(seen) >= 10:
                break
