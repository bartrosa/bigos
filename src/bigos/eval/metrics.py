from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser

from apted import APTED, Config
from rapidfuzz.distance import Levenshtein


def char_error_rate(pred: str, gt: str) -> float:
    """CER = edit_distance(pred, gt) / max(len(gt), 1)."""
    if not gt:
        return 1.0 if pred else 0.0
    return Levenshtein.distance(pred, gt) / len(gt)


def edit_distance_normalized(pred: str, gt: str) -> float:
    """Normalized to [0, 1]. 0 = identical, 1 = completely different."""
    if not pred and not gt:
        return 0.0
    max_len = max(len(pred), len(gt))
    return Levenshtein.distance(pred, gt) / max_len if max_len else 0.0


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
    distance = float(apted.compute_edit_distance())
    return 1.0 - distance / max_size
