from __future__ import annotations

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
