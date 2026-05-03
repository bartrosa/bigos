"""OmniDocBench v1.5 evaluation (HuggingFace ``opendatalab/OmniDocBench``).

**Discovered schema (PR #5):**

- The dataset repo ships ``OmniDocBench.json`` at the root: a list (~1651) of page
  records with ``layout_dets``, ``page_info``, and optional ``extra``.
- ``page_info.page_attribute`` includes ``data_source`` (e.g. ``academic_literature``,
  ``note``), ``subset`` (e.g. ``v1.5``, ``table_hard``, ``equation_hard``), and
  ``layout``.
- ``page_info.image_path`` names files under the repo folder ``images/``.
- The HuggingFace ``datasets`` table row exposes ``image`` (PIL) only — **no**
  embedded markdown/table/formula GT. We therefore join manifest rows from
  ``OmniDocBench.json`` for ground truth and download ``images/<path>`` via
  ``hf_hub_download``.

User-facing subset names map to manifest filters:

- ``tables`` → ``page_attribute["subset"] == "table_hard"``
- ``academic_paper`` → ``page_attribute["data_source"] == "academic_literature"``
- ``note`` → ``page_attribute["data_source"] == "note"``
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download

from bigos._hashing import sha256_file
from bigos.backend import Backend
from bigos.eval.metrics import char_error_rate, edit_distance_normalized, teds
from bigos.schema import Source

SUPPORTED_SUBSETS = ("tables", "academic_paper", "note")

_REPO_ID = "opendatalab/OmniDocBench"
_MANIFEST_NAME = "OmniDocBench.json"


@dataclass
class SampleResult:
    sample_id: str
    subset: str
    cer: float | None = None
    teds_avg: float | None = None
    formula_edit_dist: float | None = None
    elapsed_s: float = 0.0
    error: str | None = None


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
    def mean_teds(self) -> float | None:
        values = [r.teds_avg for r in self.results if r.teds_avg is not None]
        return sum(values) / len(values) if values else None

    def to_markdown(self) -> str:
        cer_line = (
            f"- Mean CER: {self.mean_cer:.4f}" if self.mean_cer is not None else "- Mean CER: n/a"
        )
        teds_line = (
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
            cer_line,
            teds_line,
            "",
            "## Per-sample results",
            "",
            "| Sample | CER | TEDS | Formula edit | Elapsed (s) | Error |",
            "|---|---|---|---|---|---|",
        ]
        for r in self.results:
            cer = f"{r.cer:.3f}" if r.cer is not None else "n/a"
            teds_str = f"{r.teds_avg:.3f}" if r.teds_avg is not None else "n/a"
            formula = f"{r.formula_edit_dist:.3f}" if r.formula_edit_dist is not None else "n/a"
            lines.append(
                f"| {r.sample_id} | {cer} | {teds_str} | {formula} | {r.elapsed_s:.1f} | "
                f"{r.error or ''} |"
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


_TEXT_CATEGORIES = frozenset(
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
    }
)


def _gt_text_from_layout(layout_dets: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for det in sorted(layout_dets, key=lambda d: int(d.get("order", 0) or 0)):
        cat = str(det.get("category_type", "")).lower()
        if cat in _TEXT_CATEGORIES or cat == "":
            t = str(det.get("text", "") or "").strip()
            if t:
                parts.append(t)
    if parts:
        return "\n\n".join(parts)
    # Fallback: any non-empty text field
    fallback: list[str] = []
    for det in layout_dets:
        t = str(det.get("text", "") or "").strip()
        if t:
            fallback.append(t)
    return "\n\n".join(fallback)


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


async def evaluate(
    backend: Backend,
    subset: str,
    max_samples: int | None = None,
) -> EvalReport:
    """Run a backend on a subset of OmniDocBench and compute metrics."""
    if subset not in SUPPORTED_SUBSETS:
        raise ValueError(f"subset must be one of {SUPPORTED_SUBSETS}")

    report = EvalReport(
        backend_name=backend.name,
        backend_version=backend.version,
        subset=subset,
        started_at=datetime.now(UTC).isoformat(),
    )

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

        sample_id = str(
            page_info.get("page_no") or row.get("page_id") or image_rel or f"row_{idx}",
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

            gt_text = _gt_text_from_layout(layout_dets)
            if gt_text.strip():
                pred_text = doc.export_markdown()
                result.cer = char_error_rate(pred_text, gt_text)

            gt_tables = _gt_tables_html(layout_dets)
            if gt_tables:
                pred_tables = [b for b in doc.blocks if b.kind == "table"]
                scores: list[float] = []
                for gt_html, pred_block in zip(gt_tables, pred_tables, strict=False):
                    pred_html = ""
                    if pred_block.extras:
                        pred_html = str(pred_block.extras.get("html", "") or "")
                    if gt_html and pred_html:
                        scores.append(teds(pred_html, gt_html))
                if scores:
                    result.teds_avg = sum(scores) / len(scores)

            gt_formulas = _gt_formulas_latex(layout_dets)
            if gt_formulas:
                pred_formulas = [
                    str(b.extras.get("latex", b.text or "") if b.extras else b.text or "")
                    for b in doc.blocks
                    if b.kind == "formula"
                ]
                dists: list[float] = []
                for gt_latex, pred_latex in zip(gt_formulas, pred_formulas, strict=False):
                    if gt_latex and pred_latex:
                        dists.append(edit_distance_normalized(pred_latex, gt_latex))
                if dists:
                    result.formula_edit_dist = sum(dists) / len(dists)

        except Exception as e:
            result.error = f"{type(e).__name__}: {e}"
            result.elapsed_s = time.perf_counter() - t0

        report.results.append(result)
        taken += 1

    report.finished_at = datetime.now(UTC).isoformat()
    report.n_samples = len(report.results)
    return report


def report_to_json_dict(report: EvalReport) -> dict[str, Any]:
    """JSON-serializable dict (nested dataclasses → dicts)."""
    base = asdict(report)
    base["mean_cer"] = report.mean_cer
    base["mean_teds"] = report.mean_teds
    return base
