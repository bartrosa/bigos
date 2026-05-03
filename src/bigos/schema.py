from __future__ import annotations

import re
from typing import Any, Literal, Self, assert_never

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

BlockKind = Literal[
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

_TEXT_REQUIRED_KINDS: frozenset[str] = frozenset(
    {"paragraph", "heading", "list_item", "caption", "code"}
)


class Source(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    uri: str
    mime_type: str
    sha256: str

    @field_validator("sha256")
    @classmethod
    def sha256_hex_len64(cls, v: str) -> str:
        if len(v) != 64:
            msg = "sha256 must be 64 hex characters"
            raise ValueError(msg)
        if not re.fullmatch(r"[0-9a-fA-F]+", v):
            msg = "sha256 must contain only hexadecimal characters"
            raise ValueError(msg)
        return v.lower()


class Block(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: BlockKind
    text: str | None = None
    page: int | None = None
    extras: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def text_required_for_text_kinds(self) -> Self:
        if self.kind in _TEXT_REQUIRED_KINDS and (self.text is None or self.text == ""):
            msg = f"text is required and must be non-empty for kind {self.kind!r}"
            raise ValueError(msg)
        return self


class Document(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    source: Source
    blocks: list[Block] = Field(default_factory=list)
    language: str | None = None
    raw: Any = None

    def export_markdown(self) -> str:
        parts: list[str] = []
        for block in self.blocks:
            parts.append(_block_to_markdown(block))
        return "\n\n".join(parts)

    def export_json(self) -> str:
        return self.model_dump_json(exclude={"raw"}, indent=2)


def _block_to_markdown(block: Block) -> str:
    text = block.text
    x = block.extras

    match block.kind:
        case "heading":
            level_raw = x.get("level", 1)
            try:
                level = int(level_raw)
            except (TypeError, ValueError):
                level = 1
            level = max(1, min(level, 6))
            hashes = "#" * level
            return f"{hashes} {text or ''}"
        case "paragraph":
            return text or ""
        case "list_item":
            return f"- {text or ''}"
        case "table":
            if html := x.get("html"):
                return str(html)
            if text is not None:
                return text
            return "[TABLE]"
        case "formula":
            latex = x.get("latex", text or "")
            return f"$${latex}$$"
        case "figure":
            b64 = x.get("image_b64")
            if b64:
                alt = text or "figure"
                return f"![{alt}](data:image/png;base64,{b64})"
            return "[FIGURE: " + (text or "no caption") + "]"
        case "code":
            body = text or ""
            return f"```{body}```"
        case "caption":
            return f"_Caption: {text or ''}_"
        case "page_break":
            return "\n---\n"
        case _ as k:  # pragma: no cover -- impossible if `BlockKind` stays in sync with branches
            assert_never(k)
