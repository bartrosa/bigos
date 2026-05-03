from __future__ import annotations

import time
from pathlib import Path

import pytest

from bigos._hashing import sha256_file
from bigos.backends.docling import DoclingBackend
from bigos.cache import DiskCache, make_cache_key
from bigos.schema import Block, Document, Source


def _sample_document() -> Document:
    sha = "a" * 64
    src = Source(
        uri="file:///tmp/sample.pdf",
        mime_type="application/pdf",
        sha256=sha,
    )
    return Document(
        source=src,
        blocks=[Block(kind="paragraph", text="hello")],
        language="en",
        raw={"x": 1},
    )


def test_disk_cache_set_get_roundtrip(tmp_path: Path) -> None:
    c = DiskCache(cache_dir=tmp_path / "c")
    doc = _sample_document()
    c.set("k1", doc)
    got = c.get("k1")
    assert got is not None
    assert got.model_dump(exclude={"raw"}) == doc.model_dump(exclude={"raw"})


def test_disk_cache_miss_returns_none(tmp_path: Path) -> None:
    c = DiskCache(cache_dir=tmp_path / "c")
    assert c.get("missing") is None


def test_disk_cache_clear(tmp_path: Path) -> None:
    c = DiskCache(cache_dir=tmp_path / "c")
    c.set("k", _sample_document())
    c.clear()
    assert c.get("k") is None


def test_make_cache_key_deterministic() -> None:
    k1 = make_cache_key("a" * 64, "docling", "2.0.0")
    k2 = make_cache_key("a" * 64, "docling", "2.0.0")
    assert k1 == k2


def test_make_cache_key_differs_on_version() -> None:
    k1 = make_cache_key("b" * 64, "docling", "2.0.0")
    k2 = make_cache_key("b" * 64, "docling", "2.1.0")
    assert k1 != k2


@pytest.mark.slow
async def test_docling_backend_with_cache_speedup(tmp_path: Path, simple_text_pdf: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache = DiskCache(cache_dir=cache_dir)
    backend = DoclingBackend(cache=cache)
    src = Source(
        uri=simple_text_pdf.resolve().as_uri(),
        mime_type="application/pdf",
        sha256=sha256_file(simple_text_pdf),
    )
    t0 = time.perf_counter()
    await backend.run(src)
    first = time.perf_counter() - t0
    t1 = time.perf_counter()
    await backend.run(src)
    second = time.perf_counter() - t1
    assert first > 0
    assert second < 0.1 * first


@pytest.mark.slow
async def test_docling_backend_no_cache_no_speedup(tmp_path: Path, simple_text_pdf: Path) -> None:
    src = Source(
        uri=simple_text_pdf.resolve().as_uri(),
        mime_type="application/pdf",
        sha256=sha256_file(simple_text_pdf),
    )
    backend = DoclingBackend(cache=None)
    t0 = time.perf_counter()
    await backend.run(src)
    first = time.perf_counter() - t0
    t1 = time.perf_counter()
    await backend.run(src)
    second = time.perf_counter() - t1
    assert first > 0
    assert second > 0.15 * first
