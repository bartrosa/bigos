from __future__ import annotations

import math

import pytest

from bigos.eval.metrics import (
    char_error_rate,
    compute_text_diagnostic,
    normalize_text,
    normalized_edit_distance,
    teds,
)


def test_cer_identical() -> None:
    assert char_error_rate("hello", "hello") == 0.0


def test_cer_completely_different() -> None:
    assert math.isclose(char_error_rate("aaaa", "bbbb"), 1.0)


def test_cer_known_example() -> None:
    assert math.isclose(char_error_rate("kit", "kot"), 1.0 / 3.0)


def test_cer_empty_gt() -> None:
    assert char_error_rate("x", "") == 1.0
    assert char_error_rate("", "") == 0.0


def test_teds_identical_html() -> None:
    html = "<table><tr><td>a</td></tr></table>"
    assert teds(html, html) == pytest.approx(1.0)


def test_teds_different_structure() -> None:
    a = "<table><tr><td>a</td></tr></table>"
    b = "<table><tr><td></td><td></td></tr></table>"
    assert teds(a, b) < 1.0


def test_teds_empty_inputs() -> None:
    assert teds("", "") == 1.0
    assert teds("<p>x</p>", "") == 0.0


def test_ned_in_unit_interval() -> None:
    assert normalized_edit_distance("hello", "hello") == 0.0
    assert 0 <= normalized_edit_distance("a", "abcdefgh") <= 1.0
    assert 0 <= normalized_edit_distance("abcdefgh" * 100, "x") <= 1.0


def test_ned_symmetric_when_lengths_equal() -> None:
    a, b = "hello world", "world hello"
    assert abs(normalized_edit_distance(a, b) - normalized_edit_distance(b, a)) < 1e-9


def test_ned_vs_cer_on_long_pred() -> None:
    pred = "a" * 100
    gt = "a"
    cer_val = char_error_rate(pred, gt)
    ned_val = normalized_edit_distance(pred, gt)
    assert cer_val > 1.0
    assert 0 <= ned_val <= 1.0


def test_normalize_text_strips_headers() -> None:
    assert normalize_text("# Title\n\nBody") == "Title Body"


def test_normalize_text_strips_bold_italic() -> None:
    assert normalize_text("Hello **world** and *foo*") == "Hello world and foo"


def test_normalize_text_strips_table_pipes() -> None:
    md = "| a | b |\n|---|---|\n| 1 | 2 |"
    out = normalize_text(md)
    assert "|" not in out
    assert "---" not in out
    assert "a" in out and "b" in out and "1" in out and "2" in out


def test_normalize_text_preserves_polish_chars() -> None:
    s = "Zażółć gęślą jaźń"
    assert normalize_text(s) == "Zażółć gęślą jaźń"


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("a  \n\n\t  b") == "a b"


def test_compute_text_diagnostic_full() -> None:
    d = compute_text_diagnostic("# Hello\n\nWorld", "Hello World")
    assert d.len_pred == len("# Hello\n\nWorld")
    assert d.len_gt == len("Hello World")
    assert d.cer > 0
    assert d.cer_normalized < 0.05
    assert d.ned_normalized < 0.05
