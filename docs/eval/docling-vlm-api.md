# Docling 2.92.x: VLM pipeline (Granite-Docling)

## Faktyczne API w tej wersji

Odkryte skryptem `scripts/discover/01_docling_vlm_api.py` (wynik: `eval/results/discovery/01_docling_vlm_api.txt`).

- **`VlmPipeline`**: `docling.pipeline.vlm_pipeline.VlmPipeline` — konstruktor
  `(pipeline_options: VlmPipelineOptions)`.
- **`VlmPipelineOptions`**: `docling.datamodel.pipeline_options.VlmPipelineOptions` — m.in.
  `accelerator_options`, `enable_remote_services`, `vlm_options` (typ `VlmConvertOptions` |
  legacy `InlineVlmOptions` / `ApiVlmOptions`), `generate_page_images` (domyślnie włączone
  pod VLM), `force_backend_text`.
- **Presety VLM**: `VlmConvertOptions.from_preset(name)` — ten sam mechanizm co w oficjalnym
  CLI (`docling convert --pipeline vlm --vlm-model ...`). Preset domyślny w CLI:
  `granite_docling` (Granite-Docling VLM, ~256M).
- **DocumentConverter**: `FormatOption` w `docling.document_converter` ma pole
  `pipeline_cls: Type[BasePipeline]`. Dla VLM oficjalny wzorzec (z
  `docling/cli/main.py`, gałąź `ProcessingPipeline.VLM`):

```python
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import VlmConvertOptions, VlmPipelineOptions
from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
from docling.pipeline.vlm_pipeline import VlmPipeline

pipeline_options = VlmPipelineOptions(enable_remote_services=False)
pipeline_options.vlm_options = VlmConvertOptions.from_preset("granite_docling")

pdf_format_option = PdfFormatOption(
    pipeline_cls=VlmPipeline,
    pipeline_options=pipeline_options,
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: pdf_format_option,
        InputFormat.IMAGE: ImageFormatOption(
            pipeline_cls=VlmPipeline,
            pipeline_options=pipeline_options,
        ),
    },
)
```

(`ImageFormatOption` + `ImageDocumentBackend` jest wymagane dla `InputFormat.IMAGE`; sam
`PdfFormatOption` na obrazkach jest przestarzały i wywołuje ostrzeżenie.)

W `bigos` do `VlmPipelineOptions` przekazywane jest także `accelerator_options` (urządzenie
z `detect_device()`), spójnie ze ścieżką standardową.

## Różnice względem `StandardPdfPipeline`

- **Standard** (`PdfFormatOption` bez nadpisania `pipeline_cls`): `StandardPdfPipeline` +
  layout, OCR, tabele, opcjonalne enrich (w tym `do_formula_enrichment` — inna ścieżka niż
  pełny VLM).
- **VLM**: jedna ścieżka wizyjno-językowa na obrazach stron; formuły mogą pojawić się jako
  `FormulaItem`, `TextItem` z etykietą `FORMULA`, lub LaTeX w `TextItem` (stąd heurystyka w
  `DoclingBackend`).

## Jeśli Docling zmieni API

1. Uruchom ponownie `uv run python scripts/discover/01_docling_vlm_api.py`.
2. Sprawdź **upstream** `docling/cli/main.py` — gałąź `pipeline == ProcessingPipeline.VLM`.
3. Dostosuj `_make_converter` w `src/bigos/backends/docling.py` oraz ten dokument.

Oficjalna dokumentacja pakietu: [Docling](https://docling-project.github.io/docling/)
(oraz release notes dla Twojej wersji na PyPI).
