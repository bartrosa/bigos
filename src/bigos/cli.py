from __future__ import annotations

import asyncio
import mimetypes
import time
from pathlib import Path
from typing import Annotated

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
    backend = _BACKENDS[backend_name](cache=cache)
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
