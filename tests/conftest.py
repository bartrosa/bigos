from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _ensure_pdf_fixtures() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    needed = [
        FIXTURES_DIR / "simple_text.pdf",
        FIXTURES_DIR / "with_table.pdf",
        FIXTURES_DIR / "polish.pdf",
    ]
    if any(not p.exists() for p in needed):
        subprocess.run(
            [sys.executable, str(FIXTURES_DIR / "_generate.py")],
            check=True,
        )


@pytest.fixture(scope="session")
def simple_text_pdf() -> Path:
    p = FIXTURES_DIR / "simple_text.pdf"
    assert p.is_file()
    return p


@pytest.fixture(scope="session")
def with_table_pdf() -> Path:
    p = FIXTURES_DIR / "with_table.pdf"
    assert p.is_file()
    return p


@pytest.fixture(scope="session")
def polish_pdf() -> Path:
    p = FIXTURES_DIR / "polish.pdf"
    assert p.is_file()
    return p
