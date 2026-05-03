from __future__ import annotations

import math

import pytest

from bigos.eval.metrics import char_error_rate, teds


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
