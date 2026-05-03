# OmniDocBench evaluation in `bigos`

## What is OmniDocBench

OmniDocBench v1.5 is a comprehensive benchmark for document parsing,
covering 9 document types (~1651 docs total). Source:
https://github.com/opendatalab/OmniDocBench (CVPR 2025).

## What we measure in PoC

We run a SUBSET (`tables` and `academic_paper`) with `max_samples=20`
each, computing:

- Text CER (Character Error Rate) via rapidfuzz Levenshtein
- Table S-TEDS (structure-only Tree Edit Distance Similarity) via apted
- Formula normalized edit distance

Ground truth is read from `OmniDocBench.json` in the HuggingFace dataset
repository (layout annotations), not from the table-only `datasets` rows.

## Caveat: S-TEDS vs. real TEDS

Our `teds()` is structure-only — it compares HTML tag trees, not cell
contents. Real TEDS in OmniDocBench is content-aware. Use our numbers
as a relative signal between backends, not as comparable to published
OmniDocBench leaderboard scores.

For full validation, run the official OmniDocBench evaluator on outputs
exported via `bigos parse`.

## Subset mapping

CLI names map to manifest filters in `page_info.page_attribute`:

| CLI subset        | Filter |
|-------------------|--------|
| `tables`          | `subset == "table_hard"` |
| `academic_paper`  | `data_source == "academic_literature"` |
| `note`            | `data_source == "note"` |

## Baseline results

See `eval/results/baseline-omnidocbench-*.md`.
