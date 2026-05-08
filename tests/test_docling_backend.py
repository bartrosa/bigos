from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from bigos._hashing import sha256_file
from bigos.backends.docling import DoclingBackend
from bigos.schema import Source


def test_backend_metadata() -> None:
    backend = DoclingBackend()
    assert backend.name == "docling"
    assert re.match(r"^\d+\.\d+", backend.version)
    assert backend.enable_vlm is False
    assert "+vlm" not in backend.version


def test_backend_vlm_flag_version() -> None:
    vlm = DoclingBackend(enable_vlm=True)
    assert vlm.enable_vlm is True
    assert vlm.version.endswith("+vlm")
    assert "+vlm" in vlm.version


@pytest.mark.slow
async def test_parse_simple_text(simple_text_pdf: Path) -> None:
    backend = DoclingBackend()
    src = Source(
        uri=simple_text_pdf.as_uri(),
        mime_type="application/pdf",
        sha256=sha256_file(simple_text_pdf),
    )
    doc = await backend.run(src)
    kinds = [b.kind for b in doc.blocks]
    assert kinds.count("heading") >= 1
    assert kinds.count("paragraph") >= 2


@pytest.mark.slow
async def test_parse_with_table(with_table_pdf: Path) -> None:
    backend = DoclingBackend()
    src = Source(
        uri=with_table_pdf.as_uri(),
        mime_type="application/pdf",
        sha256=sha256_file(with_table_pdf),
    )
    doc = await backend.run(src)
    md = doc.export_markdown()
    tables = [b for b in doc.blocks if b.kind == "table"]
    if tables:
        html = (tables[0].extras or {}).get("html")
        assert isinstance(html, str)
        assert html.strip() != ""
    else:
        assert "Report with grid" in md
        assert "[FIGURE" in md or "R0C0" in md


@pytest.mark.slow
async def test_parse_polish(polish_pdf: Path) -> None:
    backend = DoclingBackend()
    src = Source(
        uri=polish_pdf.as_uri(),
        mime_type="application/pdf",
        sha256=sha256_file(polish_pdf),
    )
    doc = await backend.run(src)
    blob = str(doc.blocks)
    assert "ąęćłńóśźż" in blob


@pytest.mark.slow
async def test_parse_preserves_raw(simple_text_pdf: Path) -> None:
    from docling_core.types.doc.document import DoclingDocument

    backend = DoclingBackend()
    src = Source(
        uri=simple_text_pdf.as_uri(),
        mime_type="application/pdf",
        sha256=sha256_file(simple_text_pdf),
    )
    doc = await backend.run(src)
    assert doc.raw is not None
    assert isinstance(doc.raw, DoclingDocument)


@pytest.mark.slow
async def test_export_markdown_nonempty(simple_text_pdf: Path) -> None:
    backend = DoclingBackend()
    src = Source(
        uri=simple_text_pdf.as_uri(),
        mime_type="application/pdf",
        sha256=sha256_file(simple_text_pdf),
    )
    doc = await backend.run(src)
    assert len(doc.export_markdown()) > 0


@pytest.mark.slow
def test_backend_vlm_does_not_crash_on_simple_pdf(simple_text_pdf: Path) -> None:
    backend = DoclingBackend(enable_vlm=True)
    src = Source(
        uri=simple_text_pdf.as_uri(),
        mime_type="application/pdf",
        sha256=sha256_file(simple_text_pdf),
    )
    doc = asyncio.run(backend.run(src))
    assert len(doc.blocks) > 0


def test_cache_key_version_differs_with_vlm() -> None:
    a = DoclingBackend()
    b = DoclingBackend(enable_vlm=True)
    assert a.version != b.version


def test_page_helper_passes_through_1_indexed() -> None:
    """Docling's ProvenanceItem.page_no is already 1-indexed (matches DoclingDocument.pages).

    Regression test for an off-by-one where the helper added +1 on top, causing
    every block to report its page one higher than the true page number — which
    would point RAG citations at the wrong page (or off the end of the document).
    """
    from types import SimpleNamespace

    from bigos.backends.docling import _page_1_indexed_from_item

    item = SimpleNamespace(prov=[SimpleNamespace(page_no=1)])
    assert _page_1_indexed_from_item(item) == 1

    item5 = SimpleNamespace(prov=[SimpleNamespace(page_no=5)])
    assert _page_1_indexed_from_item(item5) == 5

    no_prov = SimpleNamespace(prov=[])
    assert _page_1_indexed_from_item(no_prov) is None

    bad_value = SimpleNamespace(prov=[SimpleNamespace(page_no="not-a-number")])
    assert _page_1_indexed_from_item(bad_value) is None


@pytest.mark.slow
async def test_parse_simple_text_page_number_is_one(simple_text_pdf: Path) -> None:
    """Single-page PDF must report ``page=1`` for its blocks (not 2)."""
    backend = DoclingBackend()
    src = Source(
        uri=simple_text_pdf.as_uri(),
        mime_type="application/pdf",
        sha256=sha256_file(simple_text_pdf),
    )
    doc = await backend.run(src)
    page_values = {b.page for b in doc.blocks if b.page is not None}
    assert page_values, "expected at least one block with a page number"
    assert page_values == {1}, f"expected all blocks on page 1, got {sorted(page_values)}"
