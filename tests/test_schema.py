import json

import pytest
from pydantic import ValidationError

from bigos.schema import Block, Document, Source

_VALID_SHA = "a" * 64


def test_source_valid_sha256() -> None:
    s = Source(
        uri="file:///tmp/x.pdf",
        mime_type="application/pdf",
        sha256="A" * 64,
    )
    assert s.sha256 == "a" * 64


def test_source_invalid_sha256() -> None:
    with pytest.raises(ValidationError):
        Source(
            uri="file:///x",
            mime_type="application/pdf",
            sha256="ab" * 20,
        )


def test_source_invalid_sha256_chars() -> None:
    with pytest.raises(ValidationError):
        Source(
            uri="file:///x",
            mime_type="application/pdf",
            sha256="g" * 64,
        )


def test_block_text_required_for_text_kinds() -> None:
    with pytest.raises(ValidationError):
        Block(kind="paragraph", text=None)


def test_block_text_optional_for_visual_kinds() -> None:
    b = Block(kind="figure", text=None)
    assert b.text is None
    assert b.kind == "figure"


def test_document_construction() -> None:
    src = Source(
        uri="file:///a",
        mime_type="application/pdf",
        sha256=_VALID_SHA,
    )
    doc = Document(
        source=src,
        blocks=[
            Block(kind="paragraph", text="a"),
            Block(kind="heading", text="b", extras={"level": 2}),
            Block(kind="page_break"),
        ],
    )
    assert len(doc.blocks) == 3


def test_heading_invalid_level_defaults_to_one() -> None:
    src = Source(
        uri="file:///a",
        mime_type="application/pdf",
        sha256=_VALID_SHA,
    )
    doc = Document(
        source=src,
        blocks=[
            Block(kind="heading", text="Title", extras={"level": "not-a-number"}),
        ],
    )
    assert doc.export_markdown() == "# Title"


def test_document_export_markdown_heading() -> None:
    src = Source(
        uri="file:///a",
        mime_type="application/pdf",
        sha256=_VALID_SHA,
    )
    doc = Document(
        source=src,
        blocks=[
            Block(kind="heading", text="Title", extras={"level": 1}),
            Block(kind="paragraph", text="Body"),
        ],
    )
    assert doc.export_markdown() == "# Title\n\nBody"


def test_document_export_markdown_with_table() -> None:
    src = Source(
        uri="file:///a",
        mime_type="application/pdf",
        sha256=_VALID_SHA,
    )
    html = "<table><tr><td>cell</td></tr></table>"
    doc = Document(
        source=src,
        blocks=[
            Block(kind="table", text="ignored", extras={"html": html}),
        ],
    )
    out = doc.export_markdown()
    assert html in out
    assert out == html


def test_document_export_markdown_with_formula() -> None:
    src = Source(
        uri="file:///a",
        mime_type="application/pdf",
        sha256=_VALID_SHA,
    )
    doc = Document(
        source=src,
        blocks=[
            Block(kind="formula", text=None, extras={"latex": "x^2"}),
        ],
    )
    assert doc.export_markdown() == "$$x^2$$"


def test_document_json_excludes_raw() -> None:
    src = Source(
        uri="file:///a",
        mime_type="application/pdf",
        sha256=_VALID_SHA,
    )
    doc = Document(
        source=src,
        blocks=[],
        raw={"secret": 1},
    )
    payload = json.loads(doc.export_json())
    assert "raw" not in payload


def test_export_markdown_covers_all_block_kinds() -> None:
    """Exercise every branch in `_block_to_markdown` for coverage."""
    src = Source(
        uri="file:///a",
        mime_type="application/pdf",
        sha256=_VALID_SHA,
    )
    blocks = [
        Block(kind="paragraph", text="p"),
        Block(kind="heading", text="h", extras={"level": 2}),
        Block(kind="list_item", text="li"),
        Block(kind="table", extras={"html": "<table></table>"}),
        Block(kind="table", text="t"),
        Block(kind="table"),
        Block(kind="formula", extras={"latex": "y"}),
        Block(kind="figure", extras={"image_b64": "AAA"}),
        Block(kind="figure"),
        Block(kind="code", text="print()"),
        Block(kind="caption", text="cap"),
        Block(kind="page_break"),
    ]
    doc = Document(source=src, blocks=blocks)
    md = doc.export_markdown()
    assert "<table></table>" in md
    assert "$$y$$" in md
    assert "data:image/png;base64,AAA" in md
    assert "\n---\n" in md


def test_document_json_roundtrip() -> None:
    src = Source(
        uri="file:///a",
        mime_type="application/pdf",
        sha256=_VALID_SHA,
    )
    doc = Document(
        source=src,
        blocks=[Block(kind="paragraph", text="hi")],
        language="en",
    )
    doc2 = Document.model_validate_json(doc.export_json())
    assert doc2 == doc

    with_raw = Document(
        source=src,
        blocks=[],
        raw=object(),
    )
    back = Document.model_validate_json(with_raw.export_json())
    assert back.model_dump(exclude={"raw"}) == with_raw.model_dump(exclude={"raw"})
