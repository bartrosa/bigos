from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bigos.cli import app
from bigos.schema import Document

runner = CliRunner()


def _minimal_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "stub.pdf"
    p.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    return p


def test_cli_unknown_backend(tmp_path: Path) -> None:
    pdf = _minimal_pdf(tmp_path)
    result = runner.invoke(app, ["parse", str(pdf), "--backend=nonexistent"])
    assert result.exit_code == 1
    assert "Unknown backend" in result.stderr


def test_cli_unknown_format(tmp_path: Path) -> None:
    pdf = _minimal_pdf(tmp_path)
    result = runner.invoke(app, ["parse", str(pdf), "--format=xml"])
    assert result.exit_code == 1
    assert "Unknown format" in result.stderr


def test_cli_relative_path_does_not_crash_with_value_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: ``bigos parse some/relative.pdf`` previously raised
    ``ValueError: relative path can't be expressed as a file URI`` because the
    CLI passed a non-resolved Path straight to ``Path.as_uri()``."""
    from bigos import cli as cli_mod
    from bigos.schema import Block, Document, Source

    pdf = _minimal_pdf(tmp_path)
    monkeypatch.chdir(tmp_path)
    rel = Path(pdf.name)
    assert not rel.is_absolute()

    captured: dict[str, Source] = {}

    class _StubBackend:
        name = "stub"
        version = "0"

        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def run(self, source: Source) -> Document:
            captured["source"] = source
            return Document(
                source=source, blocks=[Block(kind="paragraph", text="ok")]
            )

    monkeypatch.setitem(cli_mod._BACKENDS, "stub", _StubBackend)  # type: ignore[arg-type]

    result = runner.invoke(
        app,
        ["parse", str(rel), "--no-cache", "--backend=stub", "--format=md"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "ok" in result.stdout
    src = captured["source"]
    assert src.uri.startswith("file://")
    assert os.path.isabs(src.uri.removeprefix("file://"))


@pytest.mark.slow
def test_cli_parse_md(simple_text_pdf: Path) -> None:
    result = runner.invoke(app, ["parse", str(simple_text_pdf), "--format=md"])
    assert result.exit_code == 0
    assert "#" in result.stdout


@pytest.mark.slow
def test_cli_parse_json(simple_text_pdf: Path) -> None:
    result = runner.invoke(app, ["parse", str(simple_text_pdf), "--format=json"])
    assert result.exit_code == 0
    Document.model_validate_json(result.stdout)


@pytest.mark.slow
def test_cli_output_to_file(simple_text_pdf: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.md"
    result = runner.invoke(
        app,
        ["parse", str(simple_text_pdf), "--format=md", "--output", str(out)],
    )
    assert result.exit_code == 0
    assert out.is_file()
    assert len(out.read_text(encoding="utf-8")) > 0
