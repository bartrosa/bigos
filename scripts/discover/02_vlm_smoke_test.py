"""Smoke test VLM pipeline on one local PDF (downloads Granite-Docling on first run)."""

from __future__ import annotations

import json
import time
from pathlib import Path

from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
    PdfFormatOption,
)
from docling.pipeline.vlm_pipeline import VlmPipeline

ROOT = Path(__file__).resolve().parents[2]


def _pick_academic_dump_image() -> Path | None:
    dumps = ROOT / "eval/results/dumps/academic-v3"
    if not dumps.is_dir():
        return None
    for p in sorted(dumps.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except OSError:
            continue
        if int(data.get("n_formulas_gt") or 0) >= 3:
            sid = str(data.get("sample_id") or "")
            if sid.endswith(".png"):
                cache_root = Path.home() / ".cache/huggingface/hub"
                matches = list(cache_root.glob(f"**/datasets--*/**/images/{sid}"))
                if matches:
                    return matches[0]
    return None


def main() -> None:
    sample_image = _pick_academic_dump_image()
    sample_pdf = ROOT / "tests/fixtures/simple_text.pdf"
    input_path = sample_image if sample_image and sample_image.is_file() else sample_pdf

    pipeline_options = VlmPipelineOptions(
        accelerator_options=AcceleratorOptions(device="auto"),
        enable_remote_services=False,
    )
    pipeline_options.vlm_options = VlmConvertOptions.from_preset("granite_docling")

    pdf_opt = PdfFormatOption(
        pipeline_cls=VlmPipeline,
        pipeline_options=pipeline_options,
    )
    img_opt = ImageFormatOption(
        pipeline_cls=VlmPipeline,
        pipeline_options=pipeline_options,
    )
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: pdf_opt,
            InputFormat.IMAGE: img_opt,
        },
    )

    print("Building VLM converter (granite_docling preset)...")
    print(f"Converting {input_path} ...")
    t0 = time.perf_counter()
    result = converter.convert(input_path)
    elapsed = time.perf_counter() - t0
    print(f"Done in {elapsed:.1f}s")

    doc = result.document
    formulas: list[dict[str, str]] = []
    for item, _level in doc.iterate_items():
        cls_name = type(item).__name__
        if "Formula" in cls_name or "Math" in cls_name or "Equation" in cls_name:
            formulas.append(
                {
                    "class": cls_name,
                    "text": (getattr(item, "text", "") or "")[:200],
                },
            )

    print(f"\nDetected {len(formulas)} formula-like items:")
    for f in formulas[:8]:
        print(f"  {f['class']}: {f['text']!r}")

    md = doc.export_to_markdown()
    print(f"\nMarkdown length: {len(md)}")
    print("Markdown preview (first 2000 chars):")
    print(md[:2000])

    out = ROOT / "eval/results/discovery/02_vlm_smoke_output.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"\nFull markdown written to {out}")


if __name__ == "__main__":
    main()
