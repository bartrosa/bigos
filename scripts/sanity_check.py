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

POLISH_CHARS = "ąęćłńóśźżĄĘĆŁŃÓŚŹŻ"

_PREVIEW_CHARS = 2000


def check_polish(text: str) -> dict[str, object]:
    found = sorted({c for c in text if c in POLISH_CHARS})
    sample = ""
    for c in found[:3]:
        idx = text.find(c)
        if idx >= 0:
            start = max(0, idx - 30)
            end = min(len(text), idx + 30)
            sample = text[start:end]
            break
    return {
        "has_polish_chars": bool(found),
        "polish_chars_found": found,
        "sample_with_polish": sample,
    }


def _preview_md(doc: Document, path: Path) -> str:
    md = doc.export_markdown()
    kinds = Counter(b.kind for b in doc.blocks)
    lines = [
        f"Document: {path.name}",
        "",
        "Blocks summary",
        "",
    ]
    for kind, n in sorted(kinds.items()):
        lines.append(f"{kind}: {n}")
    lines.extend(
        [
            "",
            f"First {_PREVIEW_CHARS} chars of markdown:",
            "",
            md[:_PREVIEW_CHARS],
            "",
        ]
    )
    return "\n".join(lines)


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
    md = doc.export_markdown()
    stats: dict[str, object] = {
        "file": path.name,
        "elapsed_s": round(elapsed, 2),
        "n_blocks": len(doc.blocks),
        "block_kinds": dict(kinds),
        "has_tables": kinds.get("table", 0) > 0,
        "has_formulas": kinds.get("formula", 0) > 0,
        "language": doc.language,
        "parse_status": "ok",
    }
    stats["polish"] = check_polish(md)
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
    polish_report: dict[str, object] = {}
    out_dir = args.output_md_dir
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    for pdf in pdfs:
        print(f"Processing {pdf.name}...", flush=True)
        try:
            result, doc = await process(backend, pdf)
        except Exception as e:
            result = {
                "file": pdf.name,
                "parse_status": f"{type(e).__name__}: {e}",
                "elapsed_s": None,
                "n_blocks": 0,
                "block_kinds": {},
                "has_tables": False,
                "has_formulas": False,
                "language": None,
                "polish": check_polish(""),
            }
            results.append(result)
            polish_report[pdf.name] = result["polish"]
            print(json.dumps(result, indent=2))
            continue

        results.append(result)
        polish_report[str(result["file"])] = result["polish"]
        print(json.dumps(result, indent=2))

        if out_dir is not None:
            md_path = out_dir / f"{pdf.stem}.md"
            md_path.write_text(doc.export_markdown(), encoding="utf-8")
            print(f"  -> wrote {md_path}")

            preview_path = out_dir / f"{pdf.stem}.preview.txt"
            preview_path.write_text(_preview_md(doc, pdf), encoding="utf-8")
            print(f"  -> wrote {preview_path}")

    if out_dir is not None:
        summary_lines = [
            "| file | n_blocks | kinds | has_tables | has_formulas | "
            "language | elapsed_s | parse_status |",
            "|---|---:|---|:---:|:---:|:---|---:|---|",
        ]
        for r in results:
            kinds = r.get("block_kinds")
            kinds_s = json.dumps(kinds, sort_keys=True) if isinstance(kinds, dict) else ""
            summary_lines.append(
                "| "
                + " | ".join(
                    [
                        str(r.get("file", "")),
                        str(r.get("n_blocks", "")),
                        kinds_s.replace("|", "\\|")[:80],
                        str(r.get("has_tables", "")),
                        str(r.get("has_formulas", "")),
                        str(r.get("language", "")),
                        str(r.get("elapsed_s", "")),
                        str(r.get("parse_status", "")).replace("|", "\\|"),
                    ]
                )
                + " |"
            )
        (out_dir / "_summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
        print(f"  -> wrote {out_dir / '_summary.md'}")

        (out_dir / "_polish_check.json").write_text(
            json.dumps(polish_report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  -> wrote {out_dir / '_polish_check.json'}")

    print("\n=== SUMMARY ===")
    print(f"Total files: {len(results)}")
    ok_results = [r for r in results if r.get("parse_status") == "ok"]
    total_elapsed = sum(float(r["elapsed_s"]) for r in ok_results if r.get("elapsed_s") is not None)
    print(f"Total time (successful): {total_elapsed:.1f}s")
    print(f"Files with tables: {sum(1 for r in results if r.get('has_tables'))}")
    print(f"Files with formulas: {sum(1 for r in results if r.get('has_formulas'))}")


if __name__ == "__main__":
    asyncio.run(main())
