from __future__ import annotations

import asyncio
import importlib.metadata
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    VlmConvertOptions,
    VlmPipelineOptions,
)
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
    PdfFormatOption,
)
from docling.pipeline.vlm_pipeline import VlmPipeline
from docling_core.types.doc.document import (
    CodeItem,
    DocItem,
    DoclingDocument,
    FormulaItem,
    ListItem,
    PictureItem,
    SectionHeaderItem,
    TableItem,
    TextItem,
    TitleItem,
)
from docling_core.types.doc.labels import DocItemLabel

from bigos._device import Device, detect_device
from bigos.cache import Cache, make_cache_key
from bigos.schema import Block, Document, Source

_DL_VERSION = importlib.metadata.version("docling")
_NAME = "docling"

# VLM / markup heuristics: some pipelines emit LaTeX in TextItem instead of FormulaItem.
_LATEXISH_TEXTITEM = re.compile(
    r"(^\s*\$\$)|(\\(?:frac|int|sum|prod|sqrt|infty|cdot|times|partial|alpha|beta|gamma|delta|left|right|bigcup|bigcap|mathbb|mathrm)\b)|(\\begin\{)",
)


def _device_to_accelerator_str(device: Device) -> str:
    return str(device)


def uri_to_path(uri: str) -> Path:
    """Resolve a file URI or plain path to a local Path."""
    u = uri.strip()
    if not u.lower().startswith("file:"):
        return Path(u)
    parsed = urlparse(u)
    path = unquote(parsed.path or "")
    if sys.platform == "win32" and path.startswith("/") and len(path) >= 3 and path[2] == ":":
        path = path[1:]
    return Path(path)


def _page_1_indexed_from_item(item: Any) -> int | None:
    """Return the (1-indexed) page number of a DocItem, or None if unknown.

    Docling's ``ProvenanceItem.page_no`` is already 1-indexed: it matches the
    keys of ``DoclingDocument.pages`` (e.g. ``doc.pages[prov.page_no]``), so we
    must NOT add +1 on top — doing so would shift every block's ``page`` by one
    and cause RAG citations to point at the wrong page.
    """
    prov = getattr(item, "prov", None) or []
    if not prov:
        return None
    p0 = prov[0]
    page_no = getattr(p0, "page_no", None)
    if page_no is None:
        return None
    try:
        n = int(page_no)
    except (TypeError, ValueError):
        return None
    if n < 1:
        return None
    return n


def _safe_model_dict(obj: Any) -> Any:
    if obj is None:
        return None
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            return dump()
        except Exception:
            return None
    dct = getattr(obj, "dict", None)
    if callable(dct):
        try:
            return dct()
        except Exception:
            return None
    return None


def _strip_nonempty(text: str | None) -> str | None:
    if text is None:
        return None
    s = text.strip()
    return s if s else None


def _map_item_to_block(item: Any, d: DoclingDocument) -> Block | None:
    page = _page_1_indexed_from_item(item)

    if isinstance(item, CodeItem):
        text = _strip_nonempty(getattr(item, "text", None))
        if text is None:
            return None
        lang = getattr(item, "code_language", None)
        if lang is not None and hasattr(lang, "value"):
            lang = lang.value
        return Block(
            kind="code",
            text=text,
            page=page,
            extras={"lang": lang},
        )

    if isinstance(item, FormulaItem):
        latex = _strip_nonempty(getattr(item, "text", None))
        if latex is None:
            return None
        return Block(
            kind="formula",
            text=latex,
            page=page,
            extras={"latex": latex},
        )

    if isinstance(item, TableItem):
        html: str | None = None
        export_html = getattr(item, "export_to_html", None)
        if callable(export_html):
            try:
                html = export_html(d)
            except Exception:
                html = None
        md: str | None = None
        export_md = getattr(item, "export_to_markdown", None)
        if callable(export_md):
            try:
                md = export_md(d)
            except Exception:
                md = None
        data = getattr(item, "data", None)
        num_rows = getattr(data, "num_rows", None) if data is not None else None
        num_cols = getattr(data, "num_cols", None) if data is not None else None
        text_val = _strip_nonempty(md)
        extras: dict[str, Any] = {}
        if html is not None:
            extras["html"] = html
        if num_rows is not None:
            extras["rows"] = num_rows
        if num_cols is not None:
            extras["cols"] = num_cols
        return Block(kind="table", text=text_val, page=page, extras=extras)

    if isinstance(item, PictureItem):
        cap_fn = getattr(item, "caption_text", None)
        caption = ""
        if callable(cap_fn):
            try:
                caption = cap_fn(d)
            except Exception:
                caption = ""
        caption_clean = _strip_nonempty(caption)
        prov = getattr(item, "prov", None) or []
        bbox_dict: Any = None
        if prov:
            bbox = getattr(prov[0], "bbox", None)
            bbox_dict = _safe_model_dict(bbox)
        return Block(
            kind="figure",
            text=caption_clean,
            page=page,
            extras={"bbox": bbox_dict},
        )

    if isinstance(item, ListItem):
        text = _strip_nonempty(getattr(item, "text", None))
        if text is None:
            return None
        marker = getattr(item, "marker", None)
        enumerated = bool(getattr(item, "enumerated", False))
        return Block(
            kind="list_item",
            text=text,
            page=page,
            extras={"marker": marker, "enumerated": enumerated},
        )

    if isinstance(item, SectionHeaderItem):
        text = _strip_nonempty(getattr(item, "text", None))
        if text is None:
            return None
        level_raw = getattr(item, "level", 1)
        try:
            level = int(level_raw)
        except (TypeError, ValueError):
            level = 1
        return Block(
            kind="heading",
            text=text,
            page=page,
            extras={"level": level},
        )

    if isinstance(item, TitleItem):
        text = _strip_nonempty(getattr(item, "text", None))
        if text is None:
            return None
        return Block(
            kind="heading",
            text=text,
            page=page,
            extras={"level": 1},
        )

    if isinstance(item, TextItem):
        label = getattr(item, "label", None)
        text = _strip_nonempty(getattr(item, "text", None))

        if label == DocItemLabel.CAPTION:
            if text is None:
                return None
            return Block(kind="caption", text=text, page=page, extras={})

        if label == DocItemLabel.FORMULA and text is not None:
            return Block(
                kind="formula",
                text=text,
                page=page,
                extras={"latex": text},
            )

        if text is not None and _LATEXISH_TEXTITEM.search(text):
            return Block(
                kind="formula",
                text=text,
                page=page,
                extras={"latex": text},
            )

        if label in (
            DocItemLabel.PARAGRAPH,
            DocItemLabel.TEXT,
            DocItemLabel.REFERENCE,
            DocItemLabel.FOOTNOTE,
            DocItemLabel.HANDWRITTEN_TEXT,
            DocItemLabel.FIELD_KEY,
            DocItemLabel.FIELD_HINT,
            DocItemLabel.MARKER,
            DocItemLabel.PAGE_HEADER,
            DocItemLabel.PAGE_FOOTER,
            DocItemLabel.EMPTY_VALUE,
            DocItemLabel.CHECKBOX_SELECTED,
            DocItemLabel.CHECKBOX_UNSELECTED,
        ):
            if text is None:
                return None
            return Block(
                kind="paragraph",
                text=text,
                page=page,
                extras={"docling_label": str(label)},
            )

    return None


def _map_docling_to_bigos(d: DoclingDocument, source: Source) -> Document:
    blocks: list[Block] = []
    try:
        iterator = d.iterate_items()
    except Exception:
        return Document(source=source, blocks=[], language=None, raw=None)

    for pair in iterator:
        try:
            item = pair[0] if isinstance(pair, tuple) and len(pair) > 0 else pair
            if not isinstance(item, DocItem):
                continue
            block = _map_item_to_block(item, d)
            if block is not None:
                blocks.append(block)
        except Exception:
            continue

    return Document(source=source, blocks=blocks, language=None, raw=None)


class DoclingBackend:
    """Wraps Docling `DocumentConverter` and maps output to `bigos.Document`.

    Optional disk cache stores parsed documents keyed by file SHA-256 and backend
    version. Cached hits return a ``Document`` **without** ``raw`` (the Docling
    ``DoclingDocument`` is not JSON-serializable and is never persisted).

    Set ``enable_vlm=True`` to use Docling's ``VlmPipeline`` with the
    ``granite_docling`` preset (Granite-Docling VLM). This is slower but can emit
    formula items / LaTeX for STEM PDFs and page images.
    """

    name = _NAME

    def __init__(
        self,
        device: Device | None = None,
        cache: Cache | None = None,
        *,
        enable_vlm: bool = False,
    ) -> None:
        self._device: Device = device if device is not None else detect_device()
        self._converter: DocumentConverter | None = None
        self._cache: Cache | None = cache
        self.enable_vlm = enable_vlm
        base_ver = importlib.metadata.version("docling")
        self.version = f"{base_ver}+vlm" if enable_vlm else base_ver

    def _make_converter(self) -> DocumentConverter:
        accel = AcceleratorOptions(device=_device_to_accelerator_str(self._device))
        if self.enable_vlm:
            vlm_opts = VlmPipelineOptions(
                accelerator_options=accel,
                enable_remote_services=False,
            )
            vlm_opts.vlm_options = VlmConvertOptions.from_preset("granite_docling")
            pdf_fmt = PdfFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=vlm_opts,
            )
            img_fmt = ImageFormatOption(
                pipeline_cls=VlmPipeline,
                pipeline_options=vlm_opts,
            )
            return DocumentConverter(
                format_options={
                    InputFormat.PDF: pdf_fmt,
                    InputFormat.IMAGE: img_fmt,
                },
            )
        pdf_opts = PdfPipelineOptions(accelerator_options=accel)
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_opts),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pdf_opts),
            },
        )

    async def run(self, source: Source) -> Document:
        cache = self._cache
        cache_key: str | None = None
        if cache is not None:
            cache_key = make_cache_key(source.sha256, self.name, self.version)
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        path = uri_to_path(source.uri)
        if self._converter is None:
            self._converter = self._make_converter()
        converter = self._converter
        assert converter is not None

        def _convert() -> Any:
            return converter.convert(path)

        conv = await asyncio.to_thread(_convert)
        d = conv.document
        doc = _map_docling_to_bigos(d, source)
        out = doc.model_copy(update={"raw": d})
        if cache is not None and cache_key is not None:
            cache.set(cache_key, out)
        return out
