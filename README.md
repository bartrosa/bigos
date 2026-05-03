# bigos

High-level data ingestion library for RAG pipelines.

## Status

Early PoC — APIs unstable.

## Quickstart

```bash
uv sync && uv run pytest
```

## Quick example

```bash
uv pip install -e ".[docling]"
bigos parse contract.pdf --format=md
```

## Supported formats

Currently PDF via Docling. More backends planned.

## Sanity-checking on your own documents

Drop PDFs in `data/`, then:

```bash
uv run python scripts/sanity_check.py data/ --output-md-dir=data/_parsed/
```

This parses every PDF, prints per-file stats, and writes markdowns to `data/_parsed/`. Open them in VS Code to visually verify quality.

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
