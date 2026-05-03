from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from bigos.eval import omnidocbench as omni
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
