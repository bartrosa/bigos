from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from bigos.eval import omnidocbench as omni
from bigos.eval.omnidocbench import (
    CategoryMetrics,
    EvalReport,
    SampleResult,
    _gt_markdown_for_eval,
    _gt_text_from_layout,
    _gt_text_from_layout_legacy,
    gt_markdown_json2md,
    report_to_json_dict,
)
from bigos.schema import Document, Source


class _MockBackend:
    name = "mock"
    version = "0"

    async def run(self, source: Source) -> Document:
        return Document(source=source, blocks=[])


def test_evaluate_unknown_subset_raises() -> None:
    with pytest.raises(ValueError, match="subset must be one of"):
        asyncio.run(omni.evaluate(_MockBackend(), subset="nope", max_samples=1))


def test_evaluate_with_mock_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    png = tmp_path / "page.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00"
        b"\x00\x00\x04\x00\x01\x0c\x8c\x10\x0c\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    manifest = [
        {
            "page_info": {
                "page_no": 1,
                "page_attribute": {"subset": "table_hard", "data_source": "x"},
                "image_path": "page.png",
            },
            "layout_dets": [],
        },
        {
            "page_info": {
                "page_no": 2,
                "page_attribute": {"subset": "table_hard", "data_source": "x"},
                "image_path": "page.png",
            },
            "layout_dets": [],
        },
    ]

    def fake_hub_download(
        repo_id: str,
        filename: str,
        repo_type: str | None = None,
    ) -> str:
        if filename == omni._MANIFEST_NAME:
            p = tmp_path / omni._MANIFEST_NAME
            p.write_text(json.dumps(manifest), encoding="utf-8")
            return str(p)
        if filename.startswith("images/"):
            return str(png)
        raise AssertionError(f"unexpected filename: {filename}")

    monkeypatch.setattr(omni, "hf_hub_download", fake_hub_download)

    report = asyncio.run(omni.evaluate(_MockBackend(), subset="tables", max_samples=2))
    assert report.n_samples == 2
    assert len(report.results) == 2


@pytest.mark.slow
def test_evaluate_with_docling_smoke() -> None:
    pytest.importorskip("docling")
    from bigos.backends.docling import DoclingBackend

    report = asyncio.run(
        omni.evaluate(DoclingBackend(), subset="tables", max_samples=2),
    )
    assert report.n_samples <= 2


def test_gt_extraction_includes_table_html() -> None:
    layout_dets = [
        {
            "category_type": "table",
            "html": "<table><tr><td>a</td></tr></table>",
            "order": 1,
        },
    ]
    gt = _gt_text_from_layout(layout_dets)
    assert "<table>" in gt
    assert "a" in gt


def test_gt_extraction_includes_formula_latex() -> None:
    layout_dets = [
        {
            "category_type": "equation_isolated",
            "latex": r"\int_0^1 x\, dx",
            "order": 1,
        },
    ]
    gt = _gt_text_from_layout(layout_dets)
    assert r"\int_0^1" in gt


def test_gt_extraction_respects_reading_order() -> None:
    layout_dets = [
        {"category_type": "text_block", "text": "second", "order": 2},
        {"category_type": "text_block", "text": "first", "order": 1},
    ]
    gt = _gt_text_from_layout(layout_dets)
    assert gt.index("first") < gt.index("second")


def test_gt_extraction_page_number_included_like_json2md() -> None:
    """Official json2md writes any block with ``text`` via the text branch."""
    layout_dets = [
        {"category_type": "text_block", "text": "MAIN", "order": 1},
        {"category_type": "page_number", "text": "42", "order": 2},
    ]
    gt = _gt_text_from_layout(layout_dets)
    assert "MAIN" in gt
    assert "42" in gt


def test_legacy_extraction_still_works() -> None:
    layout_dets = [
        {"category_type": "table", "html": "<table>...</table>", "order": 1},
        {"category_type": "text_block", "text": "hello", "order": 2},
    ]
    legacy_gt = _gt_text_from_layout_legacy(layout_dets)
    new_gt = gt_markdown_json2md(
        {"layout_dets": layout_dets, "page_info": {"image_path": "x.png"}},
    )
    assert "hello" in legacy_gt
    assert "<table>" not in legacy_gt
    assert "<table>" in new_gt


def test_per_category_breakdown_structure() -> None:
    r = SampleResult(
        sample_id="s",
        subset="tables",
        per_category={
            "text_block": CategoryMetrics(
                category="text_block",
                n_blocks=2,
                text_ned=0.1,
            ),
        },
    )
    report = EvalReport(results=[r])
    bd = report.category_breakdown
    assert "text_block" in bd
    assert bd["text_block"]["total_blocks"] == 2
    assert bd["text_block"]["mean_text_ned"] == 0.1


def test_gt_markdown_for_eval_prefers_explicit_fields() -> None:
    row = {
        "markdown_gt": "FROM_ROW",
        "layout_dets": [{"category_type": "text_block", "text": "IGNORE", "order": 1}],
    }
    assert _gt_markdown_for_eval(row, "json2md") == "FROM_ROW"


def test_truncated_merge_joins_text() -> None:
    row = {
        "page_info": {"image_path": "p.png"},
        "layout_dets": [
            {"anno_id": "a", "category_type": "text_block", "text": "hel", "order": 1},
            {"anno_id": "b", "category_type": "text_block", "text": "lo", "order": 2},
        ],
        "extra": {
            "relation": [
                {"relation_type": "truncated", "source_anno_id": "a", "target_anno_id": "b"},
            ],
        },
    }
    assert "hello" in gt_markdown_json2md(row)


def test_eval_report_to_markdown_and_json_dict() -> None:
    r = SampleResult(
        sample_id="p1",
        subset="tables",
        cer=2.0,
        ned=0.8,
        ned_normalized=0.75,
        len_pred=200,
        len_gt=100,
        teds_avg=0.65,
        elapsed_s=1.5,
        per_category={
            "text_block": CategoryMetrics(
                category="text_block",
                n_blocks=2,
                text_ned=0.5,
                table_teds=0.9,
                formula_ned=None,
            ),
        },
    )
    report = EvalReport(
        benchmark="omnidocbench-v1.5",
        backend_name="docling",
        backend_version="9",
        subset="tables",
        n_samples=1,
        results=[r],
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:01:00Z",
    )
    md = report.to_markdown()
    assert "Per-category breakdown" in md
    assert "| text_block |" in md
    assert "p1" in md
    assert "longer than gt" in md

    payload = report_to_json_dict(report)
    assert payload["mean_ned"] == report.mean_ned
    assert "text_block" in payload["category_breakdown"]
