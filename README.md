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

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
