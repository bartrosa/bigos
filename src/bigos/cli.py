from __future__ import annotations

import asyncio
import json
import mimetypes
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

import typer

from bigos._hashing import sha256_file
from bigos.backends.docling import DoclingBackend
from bigos.cache import DEFAULT_CACHE_DIR, DiskCache
from bigos.schema import Source

app = typer.Typer(name="bigos", help="Document ingestion for RAG pipelines.")

_BACKENDS: dict[str, type[DoclingBackend]] = {"docling": DoclingBackend}


@app.callback()
def _main() -> None:
    """Document ingestion for RAG pipelines."""


@app.command("parse")
def parse(
    path: Annotated[
        Path,
        typer.Argument(..., exists=True, dir_okay=False, readable=True),
    ],
    output_format: Annotated[
        str,
        typer.Option("--format", "-f", help="md or json"),
    ] = "md",
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o"),
    ] = None,
    backend_name: Annotated[
        str,
        typer.Option("--backend", "-b"),
    ] = "docling",
    no_cache: Annotated[
        bool,
        typer.Option("--no-cache", help="Disable disk cache for this run."),
    ] = False,
    cache_dir: Annotated[
        Path,
        typer.Option("--cache-dir", help="Directory for parsed-document disk cache."),
    ] = DEFAULT_CACHE_DIR,
    enable_vlm: Annotated[
        bool,
        typer.Option(
            "--vlm/--no-vlm",
            help="Use Granite-Docling VLM pipeline (formula-friendly; slower). Docling only.",
        ),
    ] = False,
) -> None:
    if backend_name not in _BACKENDS:
        typer.echo(f"Unknown backend: {backend_name}", err=True)
        raise typer.Exit(code=1)
    if output_format not in ("md", "json"):
        typer.echo(f"Unknown format: {output_format}", err=True)
        raise typer.Exit(code=1)
    cache = None
    if not no_cache:
        try:
            cache = DiskCache(cache_dir=cache_dir)
        except ImportError:
            typer.echo(
                "diskcache is not installed; parsing without cache. "
                "Install optional dependency: pip install 'bigos[cache]'",
                err=True,
            )
    backend = (
        _BACKENDS[backend_name](cache=cache, enable_vlm=enable_vlm)
        if backend_name == "docling"
        else _BACKENDS[backend_name](cache=cache)
    )
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    source = Source(uri=path.as_uri(), mime_type=mime, sha256=sha256_file(path))
    t0 = time.perf_counter()
    doc = asyncio.run(backend.run(source))
    elapsed = time.perf_counter() - t0
    text = doc.export_markdown() if output_format == "md" else doc.export_json()
    if output:
        output.write_text(text, encoding="utf-8")
        typer.echo(f"Wrote {output}", err=True)
    else:
        print(text)
    cached_hint = cache is not None and elapsed < 0.5
    suffix = " (cached)" if cached_hint else ""
    typer.echo(f"Parsed {len(doc.blocks)} blocks in {elapsed:.2f}s{suffix}", err=True)


@app.command("eval")
def eval_cmd(
    benchmark: Annotated[str, typer.Option("--benchmark", "-B")] = "omnidocbench",
    subset: Annotated[str, typer.Option("--subset", "-s")] = "tables",
    max_samples: Annotated[int, typer.Option("--max-samples", "-n")] = 20,
    backend_name: Annotated[str, typer.Option("--backend", "-b")] = "docling",
    output_dir: Annotated[Path, typer.Option("--output-dir", "-o")] = Path("eval/results"),
    dump_dir: Annotated[
        Path | None,
        typer.Option("--dump-dir", help="Per-sample diagnostic JSON dumps."),
    ] = None,
    gt_strategy: Annotated[
        Literal["legacy", "json2md"],
        typer.Option("--gt-strategy", help="Ground-truth assembly: legacy | json2md."),
    ] = "json2md",
    enable_vlm: Annotated[
        bool,
        typer.Option(
            "--vlm/--no-vlm",
            help="Granite-Docling VLM pipeline for OmniDocBench (Docling only).",
        ),
    ] = False,
) -> None:
    if benchmark != "omnidocbench":
        typer.echo("Only 'omnidocbench' supported in PoC", err=True)
        raise typer.Exit(code=1)
    if backend_name not in _BACKENDS:
        typer.echo(f"Unknown backend: {backend_name}", err=True)
        raise typer.Exit(code=1)
    if gt_strategy not in ("legacy", "json2md"):
        typer.echo("--gt-strategy must be 'legacy' or 'json2md'", err=True)
        raise typer.Exit(code=1)

    from bigos.eval.omnidocbench import evaluate, report_to_json_dict

    backend = (
        _BACKENDS[backend_name](enable_vlm=enable_vlm)
        if backend_name == "docling"
        else _BACKENDS[backend_name]()
    )
    report = asyncio.run(
        evaluate(
            backend,
            subset=subset,
            max_samples=max_samples,
            dump_dir=dump_dir,
            gt_strategy=gt_strategy,
        ),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.now(UTC).strftime("%Y-%m-%d-%H%M")
    md_path = output_dir / f"{date}-{benchmark}-{subset}.md"
    md_path.write_text(report.to_markdown(), encoding="utf-8")
    json_path = output_dir / f"{date}-{benchmark}-{subset}.json"
    json_path.write_text(json.dumps(report_to_json_dict(report), indent=2), encoding="utf-8")
    typer.echo(f"Wrote {md_path}")
    typer.echo(f"Wrote {json_path}")
    typer.echo(f"\nMean CER (raw): {report.mean_cer}")
    typer.echo(f"Mean NED: {report.mean_ned}")
    typer.echo(f"Mean NED (stripped MD): {report.mean_ned_normalized}")
    typer.echo(f"Mean len(pred)/len(gt): {report.mean_len_ratio}")
    typer.echo(f"Mean TEDS (S-TEDS): {report.mean_teds}")
