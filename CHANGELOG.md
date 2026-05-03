# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Pydantic v2 schemas: Source, Block, Document (PR #2)
- Backend Protocol abstraction (PR #2)
- Markdown and JSON export for Document (PR #2)
- DoclingBackend wrapping docling.DocumentConverter (PR #3)
- CLI: `bigos parse <path>` with --format/--output (PR #3)
- Cross-platform device detection (CUDA/MPS/CPU) (PR #3)
- Generated test fixtures: simple text, table, Polish (PR #3)

## [0.0.1.dev0] - 2026-05-03

### Added

- Initial package layout (`src/bigos`), tooling (Ruff, Mypy, Pytest, Coverage), and GitHub Actions CI.
