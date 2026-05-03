"""Deep-dive into one sample: full pred, full gt, side-by-side comparison."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Sample closest to median len_ratio for tables-v2 (from 02_length_stats.py output).
SAMPLE_ID = "page-28c45f5f-7e0d-464a-89ec-8de3a4abb927.png"
DUMP_PATH = Path("eval/results/dumps/tables-v2") / f"{SAMPLE_ID}.json"


def main() -> None:
    if not DUMP_PATH.exists():
        print(f"Not found: {DUMP_PATH}", file=sys.stderr)
        print("Available samples:", file=sys.stderr)
        for f in sorted(Path("eval/results/dumps/tables-v2").glob("*.json"))[:10]:
            print(f"  {f.stem}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DUMP_PATH.read_text(encoding="utf-8"))

    print("=" * 70)
    print(f"FULL DUMP for sample: {SAMPLE_ID}")
    print("=" * 70)
    for k, v in data.items():
        if k in ("pred_preview", "gt_preview"):
            continue
        print(f"{k}: {v}")

    print("\n" + "=" * 70)
    print("FULL GT")
    print("=" * 70)
    print(data.get("gt_preview", "(no gt)"))
    print(
        f"\n[GT preview length in dump: {len(data.get('gt_preview', '') or '')}; "
        f"full len_gt: {data.get('len_gt')}]"
    )

    print("\n" + "=" * 70)
    print("FULL PRED (first 3000 chars)")
    print("=" * 70)
    pred = data.get("pred_preview", "(no pred)")
    print(str(pred)[:3000])
    print(f"\n[Preview is {len(str(pred))} chars; full len_pred: {data.get('len_pred')}]")


if __name__ == "__main__":
    main()
