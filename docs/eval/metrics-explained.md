# Evaluation metrics in `bigos`

## CER vs NED

- **CER (character error rate)** here means `Levenshtein(pred, gt) / len(gt)` when
  `len(gt) > 0`. It is **not** bounded above by 1.0: if the model outputs much
  more text than the reference (e.g. markdown with headings and pipes), the
  edit distance can exceed the length of the ground-truth string.

- **NED (normalized edit distance)** is
  `Levenshtein(pred, gt) / max(len(pred), len(gt))`, so it always lies in
  **[0, 1]**. This matches the usual “normalized edit distance” / NED used in
  many OCR and document-benchmark writeups (including OmniDocBench-style
  reporting).

**When to use which:** use **NED** (and **NED on stripped markdown**, see below)
for headline numbers and cross-run comparison. Use **CER** only if you
explicitly want a classical rate with respect to GT length and you understand
it can exceed 1.0 when `pred` is much longer than `gt`.

## Why we report multiple text metrics

Predictions are **markdown** (from `export_markdown()`), while OmniDocBench
ground truth from `layout_dets` is **plain text** blocks. That mismatch alone
inflates raw edit distance (headers, `**bold**`, table pipes, etc.).

We therefore also report:

- **NED on stripped markdown** — same NED after `normalize_text()` (NFKC,
  optional markdown stripping, collapsed whitespace). When **raw NED is high**
  but **stripped NED is low**, most of the gap is **formatting noise**, not
  wrong content. When **stripped NED is high**, there is a real **content**
  mismatch worth inspecting (use `--dump-dir` and `pred_preview` / `gt_preview`).

## How to read the “Diagnostic interpretation” block

The markdown report includes a short heuristic section. It flags patterns such
as:

- mean CER > 1.0 (expected when markdown is much longer than plain GT);
- high NED but low NED-stripped (formatting vs content);
- high NED-stripped (real extraction errors);
- mean `len(pred)/len(gt)` far from 1.0 (systematic over- or under-generation).

It is **guidance**, not a formal test; always confirm on individual samples.

## S-TEDS vs full TEDS

**S-TEDS** in this repo compares **HTML tag trees** only (via APTED). **Full
TEDS** in OmniDocBench is **content-aware** (cell text). Do not compare our
S-TEDS numbers to published OmniDocBench table scores directly; use them for
**relative** comparison between backends or settings in the same harness.
