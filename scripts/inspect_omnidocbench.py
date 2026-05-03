"""Inspect actual OmniDocBench schema to verify our field assumptions.

Run: uv run python scripts/inspect_omnidocbench.py
"""

from __future__ import annotations

from collections import Counter

from datasets import load_dataset


def summarize_value(v: object, max_len: int = 200) -> str:
    """Return a short string summary of a value, useful for debugging."""
    if v is None:
        return "None"
    if isinstance(v, (str, int, float, bool)):
        s = str(v)
        return s if len(s) <= max_len else s[:max_len] + "..."
    if isinstance(v, dict):
        return f"dict(keys={list(v.keys())[:10]})"
    if isinstance(v, list):
        if not v:
            return "[]"
        return f"list(len={len(v)}, first={summarize_value(v[0], 80)})"
    return f"{type(v).__name__}"


def _load_streaming() -> tuple[object, str]:
    last_err: Exception | None = None
    for split in ("test", "train"):
        try:
            ds = load_dataset("opendatalab/OmniDocBench", split=split, streaming=True)
            return ds, split
        except Exception as e:
            last_err = e
            continue
    msg = f"Could not load opendatalab/OmniDocBench with split test or train: {last_err!r}"
    raise RuntimeError(msg) from last_err


def _page_attribute_dict(sample: dict) -> dict:
    pa = sample.get("page_attribute")
    if isinstance(pa, dict):
        return pa
    pi = sample.get("page_info", {})
    if isinstance(pi, dict):
        inner = pi.get("page_attribute")
        if isinstance(inner, dict):
            return inner
    return {}


def main() -> None:
    print("Loading OmniDocBench (streaming)...")
    ds, split_used = _load_streaming()
    print(f"(using split={split_used!r})")

    print("\n=== FIRST 3 SAMPLES (top-level structure) ===\n")
    samples_seen: list[dict] = []
    for i, sample in enumerate(ds):
        if i >= 3:
            break
        if not isinstance(sample, dict):
            print(f"--- Sample {i} --- (not a dict: {type(sample)})")
            continue
        print(f"--- Sample {i} ---")
        print(f"Top-level keys: {list(sample.keys())}")
        for k, v in sample.items():
            print(f"  {k}: {summarize_value(v)}")
        samples_seen.append(sample)
        print()

    if not samples_seen or not isinstance(samples_seen[0], dict):
        print("No dict samples to deep-dive.")
        return

    print("\n=== DEEP DIVE on sample 0 ===\n")
    s = samples_seen[0]
    for k, v in s.items():
        print(f"\n## {k}")
        print(f"   type: {type(v).__name__}")
        if isinstance(v, dict):
            for subk, subv in v.items():
                print(f"   {subk}: {summarize_value(subv, 150)}")
        elif isinstance(v, list) and v:
            print(f"   length: {len(v)}")
            print(f"   first item: {summarize_value(v[0], 200)}")
            if isinstance(v[0], dict):
                for subk, subv in v[0].items():
                    print(f"     {subk}: {summarize_value(subv, 100)}")

    print(f"\n=== SUBSET DISTRIBUTION (first 100 samples, split={split_used!r}) ===\n")
    ds2, _ = _load_streaming()
    subsets: Counter[str] = Counter()
    for i, sample in enumerate(ds2):
        if i >= 100:
            break
        if not isinstance(sample, dict):
            continue
        pa = _page_attribute_dict(sample)
        ds_name = str(pa.get("data_source", "unknown"))
        subsets[ds_name] += 1
    for name, count in subsets.most_common():
        print(f"  {name}: {count}")

    print("\n=== GROUND TRUTH FIELD CANDIDATES ===\n")
    s = samples_seen[0]
    candidates = ["markdown_gt", "text_gt", "gt_md", "gt_text", "html_gt", "gt"]
    for c in candidates:
        if c in s:
            print(f"  ✓ '{c}' EXISTS, type={type(s[c]).__name__}")
        else:
            print(f"  ✗ '{c}' missing")

    print("\n=== KEYS CONTAINING 'gt' or 'ground' (recursive) ===\n")

    def find_gt_keys(obj: object, path: str = "") -> list[str]:
        results: list[str] = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                full = f"{path}.{k}" if path else k
                lk = k.lower()
                if "gt" in lk or "ground" in lk or "label" in lk:
                    results.append(f"{full} ({type(v).__name__})")
                results.extend(find_gt_keys(v, full))
        elif isinstance(obj, list) and obj:
            results.extend(find_gt_keys(obj[0], f"{path}[0]"))
        return results

    for key in find_gt_keys(samples_seen[0]):
        print(f"  {key}")

    print(
        "\nNote: Full-page GT for OmniDocBench is in manifest ``OmniDocBench.json`` "
        "(``layout_dets``), not in the HuggingFace table row. See "
        "``src/bigos/eval/omnidocbench.py``.\n"
    )
    print("Done. Now adapt src/bigos/eval/omnidocbench.py to use the actual field names.")


if __name__ == "__main__":
    main()
