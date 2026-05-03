"""Read 5 dumps from each subset and print key statistics + previews."""

from __future__ import annotations

import json
from pathlib import Path

DUMPS = [
    Path("eval/results/dumps/tables-v2"),
    Path("eval/results/dumps/academic-v2"),
]


def main() -> None:
    for dump_dir in DUMPS:
        print(f"\n{'=' * 70}")
        print(f"DUMP DIR: {dump_dir}")
        print("=" * 70)
        if not dump_dir.exists():
            print(f"(missing directory: {dump_dir})")
            continue
        files = sorted(dump_dir.glob("*.json"))[:5]
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            print(f"\n--- {f.name} ---")
            print(f"len_pred:  {data.get('len_pred')}")
            print(f"len_gt:    {data.get('len_gt')}")
            lp, lg = data.get("len_pred"), data.get("len_gt")
            ratio = (lp / lg) if lp is not None and lg else None
            print(f"ratio:     {ratio:.2f}" if ratio is not None else "ratio: n/a")
            ned = data.get("ned")
            nedn = data.get("ned_normalized")
            print(f"NED:       {ned:.4f}" if ned is not None else "NED:       n/a")
            print(f"NED-strip: {nedn:.4f}" if nedn is not None else "NED-strip: n/a")
            print("\nGT preview (first 500 chars):")
            print(repr(data.get("gt_preview", ""))[:600])
            print("\nPRED preview (first 500 chars):")
            print(repr(data.get("pred_preview", ""))[:600])


if __name__ == "__main__":
    main()
