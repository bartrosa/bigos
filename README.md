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

## Evaluation

Install optional dependencies including eval extras (see `pyproject.toml`), then run OmniDocBench with optional per-sample dumps:

```bash
uv sync --all-extras
uv run bigos eval --benchmark=omnidocbench --subset=tables \
  --max-samples=20 --dump-dir=eval/results/dumps/tables/
# Compare against older baselines that used text-only GT:
# uv run bigos eval ... --gt-strategy=legacy
```

Inspect individual samples:

```bash
cat eval/results/dumps/tables/SAMPLE_ID.json | jq .
```

Baseline results (current GT = json2md-aligned): see `eval/results/baseline-*-v3.md`.
Older runs (legacy GT): `baseline-*-v2.md`. See `docs/eval/metrics-explained.md`,
`docs/eval/omnidocbench.md`, and `docs/eval/json2md-reference.md`.

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
