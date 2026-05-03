"""Compute length distribution statistics across all dumps."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import TypedDict


class _Sample(TypedDict):
    id: str
    len_pred: int
    len_gt: int
    ratio: float
    ned: float | None
    ned_strip: float | None


def main() -> None:
    for dump_dir in [
        Path("eval/results/dumps/tables-v2"),
        Path("eval/results/dumps/academic-v2"),
    ]:
        print(f"\n=== {dump_dir} ===")
        if not dump_dir.exists():
            print("(directory missing)")
            continue
        samples: list[_Sample] = []
        for f in sorted(dump_dir.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            lp, lg = data.get("len_pred"), data.get("len_gt")
            if lp is not None and lg is not None and lg > 0:
                lip = int(lp)
                lig = int(lg)
                ned_raw = data.get("ned")
                ned_strip_raw = data.get("ned_normalized")
                samples.append(
                    _Sample(
                        id=f.stem,
                        len_pred=lip,
                        len_gt=lig,
                        ratio=float(lip) / float(lig),
                        ned=float(ned_raw) if ned_raw is not None else None,
                        ned_strip=float(ned_strip_raw) if ned_strip_raw is not None else None,
                    )
                )

        if not samples:
            print("(no samples)")
            continue

        print(f"N samples: {len(samples)}")
        stat_rows = [
            ("len_pred", [float(s["len_pred"]) for s in samples]),
            ("len_gt", [float(s["len_gt"]) for s in samples]),
            ("ratio", [float(s["ratio"]) for s in samples]),
        ]
        for field, vals in stat_rows:
            print(
                f"  {field:10s}  min={min(vals):>8.0f}  med={statistics.median(vals):>8.0f}  "
                f"mean={statistics.mean(vals):>8.0f}  max={max(vals):>8.0f}"
            )

        print("\n  Per-sample ratio vs NED:")
        for s in sorted(samples, key=lambda x: x["ratio"]):
            ned = s["ned"]
            ned_s = f"{float(ned):.3f}" if ned is not None else "n/a"
            print(
                f"    {str(s['id'])[:30]:30s}  ratio={float(s['ratio']):>6.1f}  ned={ned_s}  "
                f"len_gt={int(s['len_gt']):>5d}  len_pred={int(s['len_pred']):>6d}"
            )

        # Median ratio sample (closest to median)
        ratios = [float(s["ratio"]) for s in samples]
        med = statistics.median(ratios)
        closest = min(samples, key=lambda s: abs(float(s["ratio"]) - med))
        print(f"\n  >>> Median ratio ≈ {med:.2f}; closest sample: {closest['id']}")


if __name__ == "__main__":
    main()
