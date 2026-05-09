"""OmniDocBench v1.5 evaluation (HuggingFace ``opendatalab/OmniDocBench``).

**Discovered schema (PR #5):**

- The dataset repo ships ``OmniDocBench.json`` at the root: a list (~1651) of page
  records with ``layout_dets``, ``page_info``, and optional ``extra``.
- Ground-truth markdown for eval can follow ``tools/json2md.py`` from OmniDocBench
  (see ``docs/eval/json2md-reference.md``) or the legacy text-only extraction.

User-facing subset names map to manifest filters:

- ``tables`` → ``page_attribute["subset"] == "table_hard"``
- ``academic_paper`` → ``page_attribute["data_source"] == "academic_literature"``
- ``note`` → ``page_attribute["data_source"] == "note"``
"""

from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from huggingface_hub import hf_hub_download

from bigos._hashing import sha256_file
from bigos.backend import Backend
from bigos.eval.metrics import (
    compute_text_diagnostic,
    normalized_edit_distance,
    teds,
)
from bigos.schema import Block, Document, Source

SUPPORTED_SUBSETS = ("tables", "academic_paper", "note")

_REPO_ID = "opendatalab/OmniDocBench"
_MANIFEST_NAME = "OmniDocBench.json"

_SAFE_DUMP_RE = re.compile(r"[^a-zA-Z0-9._-]+")

GTStrategy = Literal["legacy", "json2md"]

_LEGACY_TEXT_CATEGORIES = frozenset(
    {
        "header",
        "paragraph_title",
        "text",
        "abstract",
        "footer",
        "footnote",
        "reference",
        "list",
        "figure_caption",
        "table_caption",
    },
)

# Dummy SHA for building single-block markdown during metrics (valid hex len 64).
_DUMMY_SHA = "0" * 64


def _dummy_source() -> Source:
    return Source(uri="file:///dev/null", mime_type="text/plain", sha256=_DUMMY_SHA)


def _block_export_markdown(block: Block) -> str:
    return Document(source=_dummy_source(), blocks=[block]).export_markdown()


def _mean_optional(vals: list[float | None]) -> float | None:
    present = [v for v in vals if v is not None]
    return sum(present) / len(present) if present else None


# ----- json2md.py text normalization (verbatim regex intent) -----


def _replace_repeated_chars_json2md(input_str: str) -> str:
    input_str = re.sub(r"_{4,}", "____", input_str)
    input_str = re.sub(r" {4,}", "    ", input_str)
    return re.sub(r"([^a-zA-Z0-9])\1{10,}", r"\1\1\1\1", input_str)


def _text_norm_json2md(text: str) -> str:
    after_text = _replace_repeated_chars_json2md(text)
    return after_text.replace("/t", "\t").replace("/n", "\n")


def _page_stem_from_row(row: dict[str, Any]) -> str:
    pi = row.get("page_info")
    if not isinstance(pi, dict):
        return "page"
    ip = pi.get("image_path") or "page.png"
    return Path(str(ip)).stem


def _filter_annos_with_truthy_order(layout_dets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match json2md.py: ``if x.get('order'): annos.append(x)`` (excludes order 0)."""
    return [x for x in layout_dets if x.get("order")]


def _merge_truncated_json2md(
    annos: list[dict[str, Any]],
    extra: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Simplified merge for ``relation_type == 'truncated'`` (no langid dependency)."""
    if not extra:
        return sorted(annos, key=lambda x: int(x.get("order") or 0))
    relations = extra.get("relation")
    if not isinstance(relations, list):
        return annos

    truncated_all: dict[str, dict[str, Any]] = {}
    related_truncated: list[list[str]] = []
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        if relation.get("relation_type") != "truncated":
            continue
        sid = relation.get("source_anno_id")
        tid = relation.get("target_anno_id")
        if sid is not None:
            truncated_all[str(sid)] = {}
        if tid is not None:
            truncated_all[str(tid)] = {}
        pair = [str(sid), str(tid)]
        merged_into = False
        for ml in related_truncated:
            if pair[0] in ml or pair[1] in ml:
                if pair[0] not in ml:
                    ml.append(pair[0])
                if pair[1] not in ml:
                    ml.append(pair[1])
                merged_into = True
                break
        if not merged_into:
            related_truncated.append(pair)

    merged_annos: list[dict[str, Any]] = []
    for item in annos:
        aid = str(item.get("anno_id", ""))
        if aid not in truncated_all:
            merged_annos.append(item)
        else:
            truncated_all[aid] = item

    for merge_list in related_truncated:
        blocks = [v for k in merge_list if (v := truncated_all.get(k))]
        if not blocks:
            continue
        sorted_block = sorted(blocks, key=lambda x: int(x.get("order") or 0))
        text = "".join(str(b.get("text", "") or "") for b in sorted_block)
        merged_block = {
            "category_type": sorted_block[0].get("category_type"),
            "order": sorted_block[0].get("order"),
            "anno_id": sorted_block[0].get("anno_id"),
            "text": text,
        }
        merged_annos.append(merged_block)

    return sorted(merged_annos, key=lambda x: int(x.get("order") or 0))


def prepare_annos_json2md(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Prepare ``layout_dets`` the same way as ``tools/json2md.py`` before MD emission."""
    layout_dets = row.get("layout_dets")
    if not isinstance(layout_dets, list):
        return []
    raw = [d for d in layout_dets if isinstance(d, dict)]
    annos = _filter_annos_with_truthy_order(raw)
    extra = row.get("extra") if isinstance(row.get("extra"), dict) else None
    return _merge_truncated_json2md(annos, extra)


def _markdown_piece_from_anno(anno: dict[str, Any], page_stem: str) -> str | None:
    """Single block string as in json2md.py write loop (without trailing sep)."""
    table_format = "html"
    cat = str(anno.get("category_type") or "")

    if cat == "figure":
        aid = anno.get("anno_id", "fig")
        return f"![](./imgs/{page_stem}_{aid}.jpg)"

    if cat == "table":
        chunk = str(anno.get(table_format) or "")
        return chunk if chunk else None

    if anno.get("text"):
        raw = str(anno["text"])
        if cat == "title":
            return "# " + _text_norm_json2md(raw.strip("#").strip())
        return _text_norm_json2md(raw)

    if anno.get("html"):
        return str(anno["html"])

    if anno.get("latex"):
        return str(anno["latex"])

    return None


def gt_markdown_json2md(row: dict[str, Any]) -> str:
    """Rebuild GT markdown from ``layout_dets`` mirroring ``tools/json2md.py``."""
    annos = prepare_annos_json2md(row)
    stem = _page_stem_from_row(row)
    pieces: list[str] = []
    for anno in annos:
        p = _markdown_piece_from_anno(anno, stem)
        if p:
            pieces.append(p)
    return "\n\n".join(pieces)


def _gt_text_from_layout_legacy(layout_dets: list[dict[str, Any]]) -> str:
    """Pre-PR7b text-only GT (``text`` field subset + fallback)."""
    parts: list[str] = []
    for det in sorted(layout_dets, key=lambda d: int(d.get("order", 0) or 0)):
        cat = str(det.get("category_type", "")).lower()
        if cat in _LEGACY_TEXT_CATEGORIES or cat == "":
            t = str(det.get("text", "") or "").strip()
            if t:
                parts.append(t)
    if parts:
        return "\n\n".join(parts)
    fallback: list[str] = []
    for det in layout_dets:
        t = str(det.get("text", "") or "").strip()
        if t:
            fallback.append(t)
    return "\n\n".join(fallback)


def _gt_text_from_layout(layout_dets: list[dict[str, Any]]) -> str:
    """json2md-style GT from ``layout_dets`` only (synthetic page, no ``extra``)."""
    return gt_markdown_json2md(
        {"layout_dets": layout_dets, "page_info": {"image_path": "synthetic.png"}},
    )


@dataclass
class CategoryMetrics:
    """Metrics aggregated per OmniDocBench ``category_type`` within one sample."""

    category: str
    n_blocks: int = 0
    text_ned: float | None = None
    table_teds: float | None = None
    formula_ned: float | None = None


def _compute_per_category_metrics(
    row: dict[str, Any],
    doc: Document,
) -> dict[str, CategoryMetrics]:
    """Match GT json2md segments to pred blocks in reading order (simple zip per kind)."""
    annos = prepare_annos_json2md(row)
    stem = _page_stem_from_row(row)
    pred_tables = [b for b in doc.blocks if b.kind == "table"]
    pred_formulas = [b for b in doc.blocks if b.kind == "formula"]
    pred_text_blocks = [
        b for b in doc.blocks if b.kind in ("paragraph", "heading", "list_item", "caption", "code")
    ]

    ti = fi = xi = 0
    accum: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"ned": [], "teds": [], "fned": []},
    )
    counts: dict[str, int] = defaultdict(int)

    for anno in annos:
        cat_raw = str(anno.get("category_type") or "unknown")
        cat_l = cat_raw.lower()
        counts[cat_raw] += 1

        piece = _markdown_piece_from_anno(anno, stem)
        if piece is None:
            continue

        if cat_l == "figure":
            continue

        if cat_l == "table":
            gt_html = str(anno.get("html") or "")
            if ti < len(pred_tables) and gt_html:
                pb = pred_tables[ti]
                ti += 1
                pred_html = str(pb.extras.get("html", "") or "") if pb.extras else ""
                if pred_html:
                    accum[cat_raw]["teds"].append(teds(pred_html, gt_html))
            continue

        if anno.get("latex") and not anno.get("text"):
            gt_lx = str(anno["latex"])
            if fi < len(pred_formulas):
                pb = pred_formulas[fi]
                fi += 1
                pred_lx = str(pb.extras.get("latex", pb.text or "") if pb.extras else pb.text or "")
                if gt_lx and pred_lx:
                    accum[cat_raw]["fned"].append(normalized_edit_distance(pred_lx, gt_lx))
            continue

        if anno.get("text") or cat_l == "title":
            gt_txt = piece
            if xi < len(pred_text_blocks):
                pb = pred_text_blocks[xi]
                xi += 1
                pred_txt = _block_export_markdown(pb)
                accum[cat_raw]["ned"].append(normalized_edit_distance(pred_txt, gt_txt))
            continue

        if anno.get("html"):
            gt_html = piece
            if ti < len(pred_tables):
                pb = pred_tables[ti]
                ti += 1
                pred_html = str(pb.extras.get("html", "") or "") if pb.extras else ""
                if gt_html and pred_html:
                    accum[cat_raw]["teds"].append(teds(pred_html, gt_html))
            continue

        if anno.get("latex"):
            gt_lx = piece
            if fi < len(pred_formulas):
                pb = pred_formulas[fi]
                fi += 1
                pred_lx = str(pb.extras.get("latex", pb.text or "") if pb.extras else pb.text or "")
                if gt_lx and pred_lx:
                    accum[cat_raw]["fned"].append(normalized_edit_distance(pred_lx, gt_lx))

    out: dict[str, CategoryMetrics] = {}
    for cat, _ in counts.items():
        bucket = accum.get(cat, {})
        tn = _mean_optional([float(x) for x in bucket.get("ned", [])])
        tt = _mean_optional([float(x) for x in bucket.get("teds", [])])
        fn = _mean_optional([float(x) for x in bucket.get("fned", [])])
        out[cat] = CategoryMetrics(
            category=cat,
            n_blocks=counts[cat],
            text_ned=tn,
            table_teds=tt,
            formula_ned=fn,
        )
    return out


@dataclass
class SampleResult:
    sample_id: str
    subset: str
    cer: float | None = None
    ned: float | None = None
    cer_normalized: float | None = None
    ned_normalized: float | None = None
    len_pred: int | None = None
    len_gt: int | None = None
    teds_avg: float | None = None
    n_tables_pred: int = 0
    n_tables_gt: int = 0
    formula_edit_dist: float | None = None
    n_formulas_pred: int = 0
    n_formulas_gt: int = 0
    elapsed_s: float = 0.0
    error: str | None = None
    pred_preview: str | None = None
    gt_preview: str | None = None
    per_category: dict[str, CategoryMetrics] = field(default_factory=dict)


@dataclass
class EvalReport:
    benchmark: str = "omnidocbench-v1.5"
    backend_name: str = ""
    backend_version: str = ""
    subset: str = ""
    n_samples: int = 0
    results: list[SampleResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    @property
    def mean_cer(self) -> float | None:
        values = [r.cer for r in self.results if r.cer is not None]
        return sum(values) / len(values) if values else None

    @property
    def mean_ned(self) -> float | None:
        values = [r.ned for r in self.results if r.ned is not None]
        return sum(values) / len(values) if values else None

    @property
    def mean_ned_normalized(self) -> float | None:
        values = [r.ned_normalized for r in self.results if r.ned_normalized is not None]
        return sum(values) / len(values) if values else None

    @property
    def mean_len_ratio(self) -> float | None:
        ratios = [
            r.len_pred / r.len_gt
            for r in self.results
            if r.len_pred is not None and r.len_gt is not None and r.len_gt > 0
        ]
        return sum(ratios) / len(ratios) if ratios else None

    @property
    def mean_teds(self) -> float | None:
        values = [r.teds_avg for r in self.results if r.teds_avg is not None]
        return sum(values) / len(values) if values else None

    @property
    def category_breakdown(self) -> dict[str, dict[str, Any]]:
        """Aggregate per-category metrics across samples."""
        breakdown: dict[str, list[CategoryMetrics]] = defaultdict(list)
        for r in self.results:
            for _cat, m in r.per_category.items():
                breakdown[m.category].append(m)
        out: dict[str, dict[str, Any]] = {}
        for cat, mlist in breakdown.items():
            out[cat] = {
                "n_samples_with_category": len(mlist),
                "total_blocks": sum(m.n_blocks for m in mlist),
                "mean_text_ned": _mean_optional([m.text_ned for m in mlist]),
                "mean_table_teds": _mean_optional([m.table_teds for m in mlist]),
                "mean_formula_ned": _mean_optional([m.formula_ned for m in mlist]),
            }
        return out

    def _diagnostic_interpretation(self) -> str:
        msgs: list[str] = []

        if self.mean_cer is not None and self.mean_ned is not None:
            if self.mean_cer > 1.0:
                msgs.append(
                    "Mean CER > 1.0 indicates raw edit distance exceeds GT length. "
                    "This is normal when pred (markdown) is longer than gt (plain text). "
                    "Look at NED instead."
                )
            mn = self.mean_ned_normalized
            if self.mean_ned > 0.5 and mn is not None and mn < 0.2:
                msgs.append(
                    "NED is high but NED-on-stripped-markdown is low — most of the "
                    "apparent error is markdown formatting noise, not actual parsing errors."
                )
            if mn is not None and mn > 0.3:
                msgs.append(
                    "NED on stripped markdown > 0.3 — substantial content mismatch. "
                    "Inspect pred_preview vs gt_preview in JSON dumps."
                )

        if self.mean_len_ratio is not None:
            if self.mean_len_ratio > 1.5:
                msgs.append(
                    f"pred is on average {self.mean_len_ratio:.2f}x longer than gt — "
                    "Docling likely adds markdown structure vs plain GT."
                )
            elif self.mean_len_ratio < 0.7:
                msgs.append(
                    f"pred is on average {self.mean_len_ratio:.2f}x shorter than gt — "
                    "Docling may be missing content."
                )

        return "\n".join(f"- {m}" for m in msgs) if msgs else "- (no notable diagnostic flags)"

    def to_markdown(self) -> str:
        cer_agg = (
            f"- Mean CER (raw, can exceed 1.0): {self.mean_cer:.4f}"
            if self.mean_cer is not None
            else "- Mean CER: n/a"
        )
        ned_agg = (
            f"- Mean NED (normalized [0,1]): {self.mean_ned:.4f}"
            if self.mean_ned is not None
            else "- Mean NED: n/a"
        )
        ned_n_agg = (
            f"- Mean NED on stripped markdown: {self.mean_ned_normalized:.4f}"
            if self.mean_ned_normalized is not None
            else "- Mean NED stripped: n/a"
        )
        ratio_agg = (
            f"- Mean len(pred)/len(gt): {self.mean_len_ratio:.2f}"
            if self.mean_len_ratio is not None
            else "- len ratio: n/a"
        )
        teds_agg = (
            f"- Mean TEDS (S-TEDS): {self.mean_teds:.4f}"
            if self.mean_teds is not None
            else "- Mean TEDS: n/a"
        )
        lines = [
            f"# {self.benchmark} — {self.subset}",
            "",
            f"- Backend: `{self.backend_name}` v{self.backend_version}",
            f"- Samples: {self.n_samples}",
            f"- Started: {self.started_at}",
            f"- Finished: {self.finished_at}",
            "",
            "## Aggregate metrics",
            "",
            "### Text quality",
            "",
            cer_agg,
            ned_agg,
            ned_n_agg,
            ratio_agg,
            "",
            "### Structural",
            "",
            teds_agg,
            "",
            "## Diagnostic interpretation",
            "",
            self._diagnostic_interpretation(),
            "",
            "## Per-category breakdown",
            "",
            "| Category | samples | blocks | mean text NED | mean table TEDS | mean formula NED |",
            "|---|---:|---:|---:|---:|---:|",
        ]

        def _cell(v: float | None) -> str:
            return f"{v:.4f}" if v is not None else "n/a"

        for cat, ag in sorted(self.category_breakdown.items()):
            lines.append(
                f"| {cat} | {ag['n_samples_with_category']} | {ag['total_blocks']} | "
                f"{_cell(ag['mean_text_ned'])} | {_cell(ag['mean_table_teds'])} | "
                f"{_cell(ag['mean_formula_ned'])} |"
            )
        lines.extend(
            [
                "",
                "## Per-sample results",
                "",
                "| Sample | CER | NED | NED-norm | len_p/len_g | TEDS | Elapsed | Error |",
                "|---|---|---|---|---|---|---|---|",
            ]
        )
        for r in self.results:
            cer = f"{r.cer:.3f}" if r.cer is not None else "n/a"
            ned = f"{r.ned:.3f}" if r.ned is not None else "n/a"
            ned_n = f"{r.ned_normalized:.3f}" if r.ned_normalized is not None else "n/a"
            ratio = (
                f"{r.len_pred / r.len_gt:.2f}"
                if r.len_pred is not None and r.len_gt is not None and r.len_gt > 0
                else "n/a"
            )
            teds_str = f"{r.teds_avg:.3f}" if r.teds_avg is not None else "n/a"
            lines.append(
                f"| {r.sample_id} | {cer} | {ned} | {ned_n} | {ratio} | {teds_str} | "
                f"{r.elapsed_s:.1f}s | {r.error or ''} |"
            )
        return "\n".join(lines)


def _manifest_path() -> Path:
    p = hf_hub_download(repo_id=_REPO_ID, filename=_MANIFEST_NAME, repo_type="dataset")
    return Path(p)


def _load_manifest() -> list[dict[str, Any]]:
    path = _manifest_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        msg = f"expected list in {_MANIFEST_NAME}, got {type(data).__name__}"
        raise ValueError(msg)
    return data


def _matches_subset(page_attribute: dict[str, Any], subset: str) -> bool:
    if subset == "tables":
        return str(page_attribute.get("subset", "")).lower() == "table_hard"
    if subset == "academic_paper":
        return str(page_attribute.get("data_source", "")).lower() == "academic_literature"
    if subset == "note":
        return str(page_attribute.get("data_source", "")).lower() == "note"
    return False


def _image_rel(page_info: dict[str, Any]) -> str | None:
    for key in ("image_path", "img_path", "image"):
        v = page_info.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _gt_markdown_for_eval(row: dict[str, Any], strategy: GTStrategy) -> str:
    for key in ("markdown_gt", "text_gt", "gt_md", "gt_text"):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    layout_dets = row.get("layout_dets")
    if not isinstance(layout_dets, list):
        layout_dets = []
    if strategy == "legacy":
        return _gt_text_from_layout_legacy(layout_dets)
    return gt_markdown_json2md(row)


def _gt_tables_html(layout_dets: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for det in sorted(layout_dets, key=lambda d: int(d.get("order", 0) or 0)):
        if str(det.get("category_type", "")).lower() == "table":
            h = str(det.get("html", "") or "").strip()
            if h:
                out.append(h)
    return out


_FORMULA_CATEGORIES = frozenset({"equation_isolated", "equation_inline"})


def _gt_formulas_latex(layout_dets: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for det in sorted(layout_dets, key=lambda d: int(d.get("order", 0) or 0)):
        if str(det.get("category_type", "")).lower() in _FORMULA_CATEGORIES:
            lx = str(det.get("latex", "") or "").strip()
            if lx:
                out.append(lx)
    return out


def _append_error(result: SampleResult, msg: str) -> None:
    if result.error:
        result.error = f"{result.error}; {msg}"
    else:
        result.error = msg


def _safe_dump_stem(sample_id: str) -> str:
    s = _SAFE_DUMP_RE.sub("_", sample_id.strip())
    return (s[:180] if s else "sample").strip("_") or "sample"


async def evaluate(
    backend: Backend,
    subset: str,
    max_samples: int | None = None,
    dump_dir: Path | None = None,
    gt_strategy: GTStrategy = "json2md",
) -> EvalReport:
    """Run a backend on a subset of OmniDocBench and compute metrics.

    ``gt_strategy='legacy'`` uses pre-PR7b text-only GT; ``'json2md'`` mirrors official
    ``tools/json2md.py`` assembly (without writing figure crops to disk).
    """
    if subset not in SUPPORTED_SUBSETS:
        raise ValueError(f"subset must be one of {SUPPORTED_SUBSETS}")

    report = EvalReport(
        backend_name=backend.name,
        backend_version=backend.version,
        subset=subset,
        started_at=datetime.now(UTC).isoformat(),
    )

    if dump_dir is not None:
        dump_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest()
    taken = 0

    for idx, row in enumerate(manifest):
        if max_samples is not None and taken >= max_samples:
            break

        page_info = row.get("page_info")
        if not isinstance(page_info, dict):
            continue

        page_attr = page_info.get("page_attribute")
        if not isinstance(page_attr, dict):
            page_attr = {}

        if not _matches_subset(page_attr, subset):
            continue

        image_rel = _image_rel(page_info)
        if not image_rel:
            continue

        # ``page_no`` is the page number *within* a source PDF (1, 2, 3, ...) and
        # is NOT unique across manifest rows: every multi-page document starts at
        # page 1, so picking ``page_no`` first means every "first page" sample
        # collapses to ``sample_id == "1"``. Per-sample dump JSON files written to
        # ``dump_dir/{sample_id}.json`` then silently overwrite each other.
        # ``image_rel`` (the per-page image filename, e.g.
        # ``paper_2401.05459_page_001.png``) is unique per row and carries both
        # document and page info, so prefer it.
        sample_id = str(
            row.get("page_id") or image_rel or page_info.get("page_no") or f"row_{idx}",
        )
        result = SampleResult(sample_id=sample_id, subset=subset)

        layout_dets = row.get("layout_dets")
        if not isinstance(layout_dets, list):
            layout_dets = []

        t0 = time.perf_counter()
        try:
            img_local = Path(
                hf_hub_download(
                    repo_id=_REPO_ID,
                    filename=f"images/{image_rel}",
                    repo_type="dataset",
                )
            )
            sha = sha256_file(img_local)
            mime = "image/png"
            suf = img_local.suffix.lower()
            if suf in (".jpg", ".jpeg"):
                mime = "image/jpeg"
            elif suf == ".webp":
                mime = "image/webp"

            source = Source(uri=img_local.as_uri(), mime_type=mime, sha256=sha)
            doc = await backend.run(source)
            result.elapsed_s = time.perf_counter() - t0

            try:
                result.per_category = _compute_per_category_metrics(row, doc)
            except Exception as e:
                _append_error(result, f"per_category: {type(e).__name__}: {e}")

            gt_text = _gt_markdown_for_eval(row, gt_strategy)
            if gt_text.strip():
                try:
                    pred_text = doc.export_markdown()
                    diag = compute_text_diagnostic(pred_text, gt_text)
                    result.cer = diag.cer
                    result.ned = diag.ned
                    result.cer_normalized = diag.cer_normalized
                    result.ned_normalized = diag.ned_normalized
                    result.len_pred = diag.len_pred
                    result.len_gt = diag.len_gt
                    result.pred_preview = pred_text[:500]
                    result.gt_preview = gt_text[:500]
                except Exception as e:
                    _append_error(result, f"TextDiagnostic: {type(e).__name__}: {e}")

            gt_tables = _gt_tables_html(layout_dets)
            pred_tables = [b for b in doc.blocks if b.kind == "table"]
            result.n_tables_gt = len(gt_tables)
            result.n_tables_pred = len(pred_tables)
            if gt_tables:
                scores: list[float] = []
                try:
                    for gt_html, pred_block in zip(gt_tables, pred_tables, strict=False):
                        pred_html = ""
                        if pred_block.extras:
                            pred_html = str(pred_block.extras.get("html", "") or "")
                        if gt_html and pred_html:
                            scores.append(teds(pred_html, gt_html))
                    if scores:
                        result.teds_avg = sum(scores) / len(scores)
                except Exception as e:
                    _append_error(result, f"TEDS: {type(e).__name__}: {e}")

            gt_formulas = _gt_formulas_latex(layout_dets)
            pred_formulas = [
                str(b.extras.get("latex", b.text or "") if b.extras else b.text or "")
                for b in doc.blocks
                if b.kind == "formula"
            ]
            result.n_formulas_gt = len(gt_formulas)
            result.n_formulas_pred = len(pred_formulas)
            if gt_formulas:
                try:
                    dists: list[float] = []
                    for gt_latex, pred_latex in zip(gt_formulas, pred_formulas, strict=False):
                        if gt_latex and pred_latex:
                            dists.append(normalized_edit_distance(pred_latex, gt_latex))
                    if dists:
                        result.formula_edit_dist = sum(dists) / len(dists)
                except Exception as e:
                    _append_error(result, f"Formula: {type(e).__name__}: {e}")

        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
            result.elapsed_s = time.perf_counter() - t0

        if dump_dir is not None:
            stem = _safe_dump_stem(sample_id)
            dump_path = dump_dir / f"{stem}.json"
            dump_path.write_text(
                json.dumps(asdict(result), indent=2, default=str, ensure_ascii=False),
                encoding="utf-8",
            )

        report.results.append(result)
        taken += 1

    report.finished_at = datetime.now(UTC).isoformat()
    report.n_samples = len(report.results)
    return report


def report_to_json_dict(report: EvalReport) -> dict[str, Any]:
    """JSON-serializable dict (nested dataclasses → dicts)."""
    base = asdict(report)
    base["mean_cer"] = report.mean_cer
    base["mean_ned"] = report.mean_ned
    base["mean_ned_normalized"] = report.mean_ned_normalized
    base["mean_len_ratio"] = report.mean_len_ratio
    base["mean_teds"] = report.mean_teds
    base["category_breakdown"] = report.category_breakdown
    return base
