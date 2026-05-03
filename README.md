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
# Heavy mathematics PDFs / OmniDocBench academic_paper with Granite-Docling VLM:
# uv run bigos eval --benchmark=omnidocbench --subset=academic_paper --vlm ...
# Compare against older baselines that used text-only GT:
# uv run bigos eval ... --gt-strategy=legacy
```

Inspect individual samples:

```bash
cat eval/results/dumps/tables/SAMPLE_ID.json | jq .
```

**OmniDocBench academic_paper (subset, 20 próbek, json2md GT):**

| | v3 (standard Docling) | v4 (`--vlm`) |
|--|--:|--:|
| Mean NED | 0.783 | 0.524 |
| Mean len(pred)/len(gt) | 0.26 | 1.02 |
| Σ pred / Σ GT formuł | 0 / 248 | 98 / 248 (~40%) |

Szczegóły: `eval/results/comparison-v3-vs-v4-academic.md`, baseline `baseline-omnidocbench-academic_paper-v4.{md,json}`.

Baseline results (current GT = json2md-aligned): `eval/results/baseline-*-v3.md` (tables + starsze subsety); academic z VLM: **v4** powyżej. Starsze baseline (legacy GT): `baseline-*-v2.md`. See `docs/eval/metrics-explained.md`,
`docs/eval/omnidocbench.md`, `docs/eval/docling-vlm-api.md`, and `docs/eval/json2md-reference.md`.

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
