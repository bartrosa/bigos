# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- (eval) Ground-truth markdown rebuilt to mirror OmniDocBench `tools/json2md.py` (PR #7b).

### Added

- (docling) `enable_vlm` on `DoclingBackend` — `VlmPipeline` + preset `granite_docling` for formula-friendly parsing (opt-in, PR #8).
- CLI `bigos parse --vlm` / `bigos eval --vlm` (Docling only, PR #8).
- `docs/eval/docling-vlm-api.md` — how VLM is wired in Docling 2.92.x (PR #8).
- OmniDocBench baseline **academic_paper v4** (`baseline-omnidocbench-academic_paper-v4.{md,json}`) with VLM; v1–v3 unchanged (PR #8).

### Changed

- Backend version string includes `+vlm` when VLM is enabled so disk cache keys stay disjoint from standard Docling runs (PR #8).

- (eval) Per-category metric breakdown on `EvalReport` and in markdown output (PR #7b).
- CLI `--gt-strategy` (`legacy` | `json2md`, default `json2md`) for OmniDocBench GT assembly (PR #7b).
- `docs/eval/json2md-reference.md` — reference behaviour from official `json2md.py` (PR #7b).
- OmniDocBench baselines **v3** (`baseline-*-v3.{md,json}`); v1/v2 retained for comparison (PR #7b).

- Pydantic v2 schemas: Source, Block, Document (PR #2)
- Backend Protocol abstraction (PR #2)
- Markdown and JSON export for Document (PR #2)
- DoclingBackend wrapping docling.DocumentConverter (PR #3)
- CLI: `bigos parse <path>` with --format/--output (PR #3)
- Cross-platform device detection (CUDA/MPS/CPU) (PR #3)
- Generated test fixtures: simple text, table, Polish (PR #3)
- DiskCache for parsed Documents (PR #4)
- CLI flags --no-cache, --cache-dir (PR #4)
- scripts/sanity_check.py for batch testing on user docs (PR #4)
- Eval harness: char_error_rate, teds (S-TEDS), edit_distance metrics (PR #5)
- OmniDocBench v1.5 integration via HuggingFace dataset repo + manifest JSON (PR #5)
- CLI: `bigos eval --benchmark=omnidocbench` (PR #5)
- Baseline results for `tables` and `academic_paper` subsets (PR #5)
- NED (normalized edit distance) metric (PR #6)
- Text normalization (markdown stripping, NFKC, whitespace) (PR #6)
- `compute_text_diagnostic()` with full per-sample diagnostic fields (PR #6)
- `--dump-dir` flag for per-sample debugging JSON (PR #6)
- Schema inspection script `scripts/inspect_omnidocbench.py` (PR #6)
- Re-baseline with corrected metrics (`baseline-*-v2`) (PR #6)
- `sanity_check.py`: previews, `_summary.md`, `_polish_check.json` (PR #6)

## [0.0.1.dev0] - 2026-05-03

### Added

- Initial package layout (`src/bigos`), tooling (Ruff, Mypy, Pytest, Coverage), and GitHub Actions CI.
