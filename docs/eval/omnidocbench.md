# OmniDocBench evaluation in `bigos`

## What is OmniDocBench

OmniDocBench v1.5 is a comprehensive benchmark for document parsing,
covering 9 document types (~1651 docs total). Source:
https://github.com/opendatalab/OmniDocBench (CVPR 2025).

## What we measure in PoC

We run a SUBSET (`tables` and `academic_paper`) with `max_samples=20`
each, computing:

- Text: **CER** (unbounded), **NED** in [0,1], and **NED on stripped markdown**
  (see `docs/eval/metrics-explained.md`)
- Table S-TEDS (structure-only Tree Edit Distance Similarity) via apted
- Formula normalized edit distance (same normalization as NED per character)

Ground truth is read from `OmniDocBench.json` in the HuggingFace dataset
repository (layout annotations), not from the table-only `datasets` rows.

## GT extraction strategy (`legacy` vs `json2md`)

Full-page markdown GT for scoring is assembled from each manifest row’s
`layout_dets` (and optional `extra.relation` for truncated merges):

| Strategy | Behaviour |
|----------|-----------|
| **`json2md`** (default) | Mirrors OmniDocBench `tools/json2md.py`: truthy `order` filter, sort by `order`, truncated merge when `extra` is present, branch order figure → table (`html`) → `text` (`title` → `# …`) → raw `html` / `latex`, `text_norm`, blocks joined with `\n\n`. Figure crops are **not** written; figure blocks become `![](./imgs/{stem}_{anno_id}.jpg)` placeholders. See **`docs/eval/json2md-reference.md`**. |
| **`legacy`** | Pre-PR7b text-only extraction from a subset of categories (`text` field only). Omits table HTML and equation LaTeX — useful only for backward comparison with older baselines (`*-v2`). |

CLI: `--gt-strategy=legacy|json2md` (default `json2md`).

## Per-category metrics

Beyond global NED / TEDS / formula distance, each sample records **`per_category`**:
per OmniDocBench `category_type`, block counts and mean **text NED** (text-like
blocks), mean **table TEDS** (HTML tables), mean **formula NED** (LaTeX), where
applicable. Aggregated **`category_breakdown`** appears in JSON reports and in the
Markdown summary section **Per-category breakdown**.

## Schema discovered (HF `datasets` rows)

Run `uv run python scripts/inspect_omnidocbench.py` for a live dump. Typical
observations:

- The Hub table often exposes only **`image`** (PIL) at the top level—**no**
  `markdown_gt` / `text_gt` on the row.
- **`page_attribute`** may appear under **`page_info`** rather than at the
  top level; the inspection script checks both.
- The **`test`** split may be absent; we fall back to **`train`** for streaming
  probes.

Full-page text/table/formula GT used by `bigos eval` comes from the manifest
JSON (`layout_dets`), with optional fallback keys on each row if present:
`markdown_gt`, `text_gt`, `gt_md`, `gt_text`.

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

## How to inspect failures

Per-sample JSON dumps (previews + all metrics):

```bash
uv sync --all-extras
uv run bigos eval --benchmark=omnidocbench --subset=tables \
  --max-samples=20 --dump-dir=eval/results/dumps/tables/
```

Inspect one sample:

```bash
cat eval/results/dumps/tables/page-XXXX.json | jq .
```

Compare `pred_preview` and `gt_preview`; check `ned` vs `ned_normalized`.

## Baseline results

- v1 (legacy CER-focused reports): `eval/results/baseline-omnidocbench-*.md`
  (without `-v2`/`-v3`).
- v2 (NED + diagnostics, **legacy GT**): `eval/results/baseline-omnidocbench-*-v2.md`.
- v3 (**json2md-aligned GT**, current): `eval/results/baseline-omnidocbench-*-v3.md`
  (and `.json`). Comparison v2→v3: `eval/results/comparison-v2-vs-v3.md`.

See also `docs/eval/metrics-explained.md` and `docs/eval/json2md-reference.md`.
