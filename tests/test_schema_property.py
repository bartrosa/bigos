from __future__ import annotations

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

from bigos.schema import Block, BlockKind, Document, Source

sha256_hex = st.text(alphabet="0123456789abcdef", min_size=64, max_size=64)

_TEXT_KINDS_NEEDING_NONEMPTY_TEXT: frozenset[str] = frozenset(
    {"paragraph", "heading", "list_item", "caption", "code"}
)

json_scalars = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(-10_000, 10_000),
    st.floats(min_value=-1e9, max_value=1e9, allow_nan=False, allow_infinity=False),
    st.text(max_size=200),
)
extras_dict = st.dictionaries(
    keys=st.text(min_size=1),
    values=json_scalars,
    max_size=8,
)

block_kinds = st.sampled_from(
    [
        "paragraph",
        "heading",
        "list_item",
        "table",
        "figure",
        "formula",
        "caption",
        "code",
        "page_break",
    ]
)


@composite
def blocks(draw) -> Block:
    kind: BlockKind = draw(block_kinds)
    if kind in _TEXT_KINDS_NEEDING_NONEMPTY_TEXT:
        text = draw(st.text(min_size=1, max_size=200))
    else:
        text = draw(st.none() | st.text(max_size=200))
    extras = draw(extras_dict)
    page = draw(st.none() | st.integers(min_value=1, max_value=10_000))
    return Block(kind=kind, text=text, page=page, extras=extras)


@composite
def sources(draw) -> Source:
    uri = draw(st.text(min_size=1, max_size=120))
    mime_simple = st.sampled_from(["application/pdf", "text/plain"])
    mime_fallback = st.text(min_size=1, max_size=80)
    mime_type = draw(mime_simple | mime_fallback)
    sha = draw(sha256_hex)
    return Source(uri=uri, mime_type=mime_type, sha256=sha)


@composite
def documents(draw) -> Document:
    source = draw(sources())
    block_list = draw(st.lists(blocks(), min_size=0, max_size=12))
    language = draw(st.none() | st.sampled_from(["en", "pl", "de", "fr"]))
    raw_strategy = (
        st.none()
        | st.integers()
        | st.text()
        | st.binary(max_size=32)
        | st.lists(st.integers(), max_size=3)
    )
    raw: Any = draw(raw_strategy)
    return Document(source=source, blocks=block_list, language=language, raw=raw)


def assert_document_equal_modulo_raw(a: Document, b: Document) -> None:
    da = a.model_dump(mode="python", exclude={"raw"})
    db = b.model_dump(mode="python", exclude={"raw"})
    assert da == db


@given(documents())
@settings(max_examples=100)
def test_document_json_roundtrip_property(doc: Document) -> None:
    roundtrip = Document.model_validate_json(doc.export_json())
    assert_document_equal_modulo_raw(roundtrip, doc)


@given(documents())
@settings(max_examples=100)
def test_export_markdown_is_deterministic(doc: Document) -> None:
    m1 = doc.export_markdown()
    m2 = doc.export_markdown()
    assert m1 == m2
