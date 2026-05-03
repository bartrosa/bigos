"""Discover the actual VLM pipeline API in installed Docling version."""

from __future__ import annotations

import importlib
import importlib.metadata
import inspect
from pathlib import Path

OUTPUT = Path("eval/results/discovery/01_docling_vlm_api.txt")

lines: list[str] = []


def log(msg: str) -> None:
    print(msg)
    lines.append(msg)


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    try:
        dver = importlib.metadata.version("docling")
    except importlib.metadata.PackageNotFoundError:
        dver = "unknown"
    log(f"=== docling version (importlib.metadata): {dver}")

    import docling as docling_pkg

    log("\n=== docling submodules ===")
    for name in sorted(dir(docling_pkg)):
        if not name.startswith("_"):
            log(f"  docling.{name}")

    candidates_modules = [
        "docling.document_converter",
        "docling.datamodel.pipeline_options",
        "docling.datamodel.base_models",
        "docling.pipeline.vlm_pipeline",
        "docling.pipeline.standard_pdf_pipeline",
        "docling.models.vlm_models",
        "docling.models.granite_docling_vlm",
    ]

    for mod_name in candidates_modules:
        try:
            mod = importlib.import_module(mod_name)
            log(f"\n=== {mod_name} ===")
            members = [
                (name, obj)
                for name, obj in inspect.getmembers(mod)
                if not name.startswith("_") and (inspect.isclass(obj) or inspect.isfunction(obj))
            ]
            for name, obj in members:
                log(f"  {name}: {obj.__class__.__name__}")
                if inspect.isclass(obj):
                    try:
                        sig = inspect.signature(obj.__init__)
                        log(f"    __init__{sig}")
                    except (ValueError, TypeError):
                        pass
        except ImportError as e:
            log(f"\n=== {mod_name}: NOT IMPORTABLE ({e})")

    log("\n=== Grepping docling package for vlm/granite/formula ===")

    docling_path = Path(docling_pkg.__file__).parent
    for py_file in sorted(docling_path.rglob("*.py")):
        rel = py_file.relative_to(docling_path)
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        matches: list[str] = []
        for pattern in [
            "VlmPipeline",
            "VlmPipelineOptions",
            "GraniteDocling",
            "do_formula",
            "formula_enrichment",
            "VlmOptions",
        ]:
            if pattern in text:
                matches.append(pattern)
        if matches:
            log(f"  {rel}: {matches}")

    log("\n=== Trying common VLM-related imports ===")
    attempts = [
        ("docling.document_converter", "DocumentConverter"),
        ("docling.document_converter", "PdfFormatOption"),
        ("docling.datamodel.base_models", "InputFormat"),
        ("docling.datamodel.pipeline_options", "PdfPipelineOptions"),
        ("docling.datamodel.pipeline_options", "VlmPipelineOptions"),
        ("docling.datamodel.pipeline_options", "smoldocling_vlm_conversion_options"),
        ("docling.pipeline.vlm_pipeline", "VlmPipeline"),
    ]
    for mod_name, cls_name in attempts:
        try:
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, cls_name)
            log(f"  ✓ {mod_name}.{cls_name}")
            if hasattr(cls, "__init__"):
                try:
                    sig = inspect.signature(cls.__init__)
                    log(f"     signature: {sig}")
                except (ValueError, TypeError):
                    pass
            if cls.__doc__:
                doc = cls.__doc__.strip().split("\n")[0]
                log(f"     doc: {doc[:120]}")
        except (ImportError, AttributeError) as e:
            log(f"  ✗ {mod_name}.{cls_name} — {e}")

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    log(f"\nWritten to {OUTPUT}")


if __name__ == "__main__":
    main()
