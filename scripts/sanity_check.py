"""Run DoclingBackend on every PDF in a given directory, print stats per file.

Usage: uv run python scripts/sanity_check.py path/to/docs/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import time
from collections import Counter
from pathlib import Path

from bigos._hashing import sha256_file
from bigos.backends.docling import DoclingBackend
from bigos.cache import DEFAULT_CACHE_DIR, DiskCache
from bigos.schema import Document, Source


async def process(backend: DoclingBackend, path: Path) -> tuple[dict[str, object], Document]:
    source = Source(
        uri=path.resolve().as_uri(),
        mime_type=mimetypes.guess_type(path)[0] or "application/octet-stream",
        sha256=sha256_file(path),
    )
    t0 = time.perf_counter()
    doc = await backend.run(source)
    elapsed = time.perf_counter() - t0
    kinds = Counter(b.kind for b in doc.blocks)
    stats: dict[str, object] = {
        "file": str(path),
        "elapsed_s": round(elapsed, 2),
        "n_blocks": len(doc.blocks),
        "block_kinds": dict(kinds),
        "has_tables": kinds.get("table", 0) > 0,
        "has_formulas": kinds.get("formula", 0) > 0,
        "language": doc.language,
    }
    return stats, doc


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--output-md-dir", type=Path, default=None)
    args = parser.parse_args()

    cache = None if args.no_cache else DiskCache(cache_dir=args.cache_dir)
    backend = DoclingBackend(cache=cache)

    pdfs = sorted(args.directory.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {args.directory}")
        return

    results: list[dict[str, object]] = []
    for pdf in pdfs:
        print(f"Processing {pdf.name}...", flush=True)
        result, doc = await process(backend, pdf)
        results.append(result)
        print(json.dumps(result, indent=2))

        if args.output_md_dir:
            args.output_md_dir.mkdir(parents=True, exist_ok=True)
            md_path = args.output_md_dir / f"{pdf.stem}.md"
            md_path.write_text(doc.export_markdown(), encoding="utf-8")
            print(f"  -> wrote {md_path}")

    print("\n=== SUMMARY ===")
    print(f"Total files: {len(results)}")
    total_elapsed = sum(float(r["elapsed_s"]) for r in results)
    print(f"Total time: {total_elapsed:.1f}s")
    print(f"Files with tables: {sum(1 for r in results if r['has_tables'])}")
    print(f"Files with formulas: {sum(1 for r in results if r['has_formulas'])}")


if __name__ == "__main__":
    asyncio.run(main())
