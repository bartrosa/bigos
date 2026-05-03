from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from html.parser import HTMLParser

from apted import APTED, Config
from rapidfuzz.distance import Levenshtein

# ===== TEXT METRICS =====


def char_error_rate(pred: str, gt: str) -> float:
    """Classic CER = edit_distance / len(gt). Can exceed 1.0 if pred >> gt.

    NOTE: For document parsing where pred (markdown) and gt (plain text) differ
    in length, prefer normalized_edit_distance() instead.
    """
    if not gt:
        return 1.0 if pred else 0.0
    return Levenshtein.distance(pred, gt) / len(gt)


def normalized_edit_distance(pred: str, gt: str) -> float:
    """NED = edit_distance / max(len(pred), len(gt)). Always in [0, 1].

    This is what OmniDocBench and most OCR benchmarks call "edit distance".
    """
    if not pred and not gt:
        return 0.0
    max_len = max(len(pred), len(gt))
    if max_len == 0:
        return 0.0
    return Levenshtein.distance(pred, gt) / max_len


# ===== TEXT NORMALIZATION =====

_MD_HEADER_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC_RE = re.compile(r"\*(.+?)\*|_(.+?)_")
_MD_CODE_INLINE_RE = re.compile(r"`(.+?)`")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_MD_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:|-]+\|?\s*$", re.MULTILINE)
_MD_TABLE_PIPE_RE = re.compile(r"\s*\|\s*")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(s: str, *, strip_markdown: bool = True, lowercase: bool = False) -> str:
    """Normalize text for fair comparison between predicted markdown and plain-text GT.

    Steps:
    1. Unicode NFKC normalization (handles fullwidth chars, ligatures, etc.)
    2. Optional markdown stripping (headers, bold, italic, code, links, tables)
    3. Whitespace collapse to single space
    4. Strip leading/trailing whitespace
    5. Optional lowercase
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)

    if strip_markdown:
        s = _MD_IMAGE_RE.sub("", s)
        s = _MD_LINK_RE.sub(r"\1", s)
        s = _MD_HEADER_RE.sub("", s)
        s = _MD_BOLD_RE.sub(r"\1", s)
        s = _MD_ITALIC_RE.sub(lambda m: m.group(1) or m.group(2) or "", s)
        s = _MD_CODE_INLINE_RE.sub(r"\1", s)
        s = _MD_TABLE_SEP_RE.sub("", s)
        s = _MD_TABLE_PIPE_RE.sub(" ", s)

    s = _WHITESPACE_RE.sub(" ", s).strip()
    if lowercase:
        s = s.lower()
    return s


@dataclass(frozen=True)
class TextDiagnostic:
    """Detailed diagnostic from comparing pred vs gt."""

    len_pred: int
    len_gt: int
    edit_distance: int
    cer: float  # classic, can exceed 1
    ned: float  # normalized, in [0,1]
    cer_normalized: float  # CER on markdown-stripped text
    ned_normalized: float  # NED on markdown-stripped text


def compute_text_diagnostic(pred: str, gt: str) -> TextDiagnostic:
    """Compute all four text metrics + length info in one shot."""
    distance = Levenshtein.distance(pred, gt)
    pred_norm = normalize_text(pred, strip_markdown=True)
    gt_norm = normalize_text(gt, strip_markdown=True)
    return TextDiagnostic(
        len_pred=len(pred),
        len_gt=len(gt),
        edit_distance=distance,
        cer=char_error_rate(pred, gt),
        ned=normalized_edit_distance(pred, gt),
        cer_normalized=char_error_rate(pred_norm, gt_norm),
        ned_normalized=normalized_edit_distance(pred_norm, gt_norm),
    )


edit_distance_normalized = normalized_edit_distance


# ===== TEDS (structure-only) =====


@dataclass
class HTMLTreeNode:
    """APTED Config.rename compares labels via ``node.name``."""

    tag: str
    children: list[HTMLTreeNode]

    @property
    def name(self) -> str:
        return self.tag


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.root = HTMLTreeNode("ROOT", [])
        self.stack: list[HTMLTreeNode] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HTMLTreeNode(tag, [])
        self.stack[-1].children.append(node)
        self.stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = HTMLTreeNode(tag, [])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        if len(self.stack) > 1:
            self.stack.pop()


def _count_nodes(n: HTMLTreeNode) -> int:
    return 1 + sum(_count_nodes(c) for c in n.children)


def teds(pred_html: str, gt_html: str) -> float:
    """Tree Edit Distance Similarity (S-TEDS, structure-only).

    Returns score in [0, 1]; 1 = identical structure.
    NOTE: This is structure-only TEDS (no cell content matching).
    Real TEDS in OmniDocBench is content-aware. Use this as a PoC approximation.
    """
    ps = pred_html.strip()
    gs = gt_html.strip()
    if not ps and not gs:
        return 1.0
    if not ps or not gs:
        return 0.0

    class _APTEDConfig(Config):  # type: ignore[misc]
        def rename(self, n1: HTMLTreeNode, n2: HTMLTreeNode) -> int:
            return 0 if n1.tag == n2.tag else 1

        def children(self, n: HTMLTreeNode) -> list[HTMLTreeNode]:
            return n.children

    p_builder = _TreeBuilder()
    p_builder.feed(pred_html)
    p_builder.close()
    g_builder = _TreeBuilder()
    g_builder.feed(gt_html)
    g_builder.close()

    max_size = max(_count_nodes(p_builder.root), _count_nodes(g_builder.root))
    if max_size <= 1:
        return 1.0
    apted = APTED(p_builder.root, g_builder.root, _APTEDConfig())
    dist = float(apted.compute_edit_distance())
    return 1.0 - dist / max_size
