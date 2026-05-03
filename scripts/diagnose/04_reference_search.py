"""Search OmniDocBench reference repo for GT extraction logic."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REF_ROOT = Path("/tmp/omnidocbench-ref")
if not REF_ROOT.exists():
    print(f"Reference repo not found at {REF_ROOT}; skipping")
    sys.exit(0)

PATTERNS = [
    r"def\s+\w*gt\w*",
    r"def\s+\w*ground_?truth\w*",
    r"def\s+\w*build_md\w*",
    r"def\s+\w*to_markdown\w*",
    r"def\s+\w*get_text\w*",
    r"layout_dets",
    r'"category"',
    r'"category_type"',
    r"category_filter",
]

print("=== Files containing GT-related logic ===\n")
for py_file in sorted(REF_ROOT.rglob("*.py")):
    try:
        text = py_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    matches: list[tuple[int, str, str]] = []
    for pat in PATTERNS:
        for m in re.finditer(pat, text):
            line_no = text[: m.start()].count("\n") + 1
            matches.append((line_no, pat, m.group()))
    if matches:
        rel = py_file.relative_to(REF_ROOT)
        print(f"\n--- {rel} ---")
        for line_no, pat, hit in sorted(matches)[:15]:
            print(f"  L{line_no}: {hit}  (matched {pat})")

candidates = (
    list(REF_ROOT.rglob("*end*end*.py"))
    + list(REF_ROOT.rglob("*metric*.py"))
    + list(REF_ROOT.rglob("*eval*.py"))
)
print(f"\n\n=== Candidate evaluator files: {len(candidates)} ===")
for c in candidates[:5]:
    try:
        body = c.read_text(encoding="utf-8", errors="ignore")[:3000]
    except OSError:
        body = "(read error)"
    print(f"\n>>> {c.relative_to(REF_ROOT)}")
    print(body)
