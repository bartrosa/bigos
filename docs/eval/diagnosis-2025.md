# Diagnostyka len_ratio i NED w eval OmniDocBench

## TL;DR

Na podstawie dumpów JSON, statystyk długości oraz histogramu `layout_dets` z manifestu **OmniDocBench.json** (pierwsze 100 wpisów): **tekst referencyjny używany w evalu składa się głównie z pól `text` w detekcjach**, podczas gdy w danych oficjalnych **tabele żyją w polu `html`**, a **izolowane równania w polu `latex`** (bez `text`). W efekcie GT jest **celowo krótki** względem pełnej treści strony, którą Docling składa w markdown (w tym duże tabele HTML). To tłumaczy **średni stosunek `len(pred)/len(gt)` rzędu 34× (tables)** i **NED ~0,93** przy prawie identycznym NED „stripped” — problem nie jest wyłącznie nagłówkami Markdown. **Hipoteza z PR #6 jest potwierdzona:** `_gt_text_from_layout` **nie reprezentuje pełnej treści strony** w sensie porównywalnym z `export_markdown()`. Proponowany następny krok to **PR-B**: rozszerzyć budowę GT o `html` (tabele), `latex` (formuły), dopasować nazwy kategorii do schematu (`text_block`, `title`, …) oraz ewentualnie ścieżkę jak w `tools/json2md.py` z repozytorium OmniDocBench.

## Obserwacje surowe

### 1. Statystyki długości

Źródło: `eval/results/diagnosis/02_length_stats.txt` (20 próbek na subset).

**Subset `tables-v2`:**

| Pole      | min | mediana | średnia | max |
|-----------|-----|---------|---------|-----|
| len_pred  | 596 | 1490    | 1746    | 5761 |
| len_gt    | 17  | 47      | 110     | 620 |
| ratio     | 2   | 29      | 34      | 110 |

**Subset `academic-v2`:**

| Pole      | min | mediana | średnia | max |
|-----------|-----|---------|---------|-----|
| len_pred  | 161 | 850     | 1084    | 3668 |
| len_gt    | 12  | 290     | 789     | 3404 |
| ratio     | 0   | 2       | 20      | 97 |

Uwaga: dla części stron academic GT zawiera długi blok LaTeX w polu `text` (dowód), wtedy `len_gt > len_pred` i ratio &lt; 1 — stąd szeroki rozstrzał ratio na tym subsecie.

### 2. Per-sample ratio vs NED (tables — 5 najwyższych ratio)

Z pełnej listy posortowanej rosnąco po `ratio`, **najwyższe** wartości to m.in.:

| ID (skrót) | ratio | len_gt | len_pred | NED |
|------------|-------|--------|----------|-----|
| …b527edec… | 109.6 | 17 | 1863 | ~0.994 |
| …c7792da7… | 67.7 | 25 | 1693 | ~0.989 |
| …9edf7687… | 57.5 | 19 | 1092 | ~0.986 |
| …3c690b07… | 51.0 | 34 | 1733 | ~0.991 |
| …9477c155… | 46.1 | 23 | 1061 | ~0.987 |

Im krótszy `len_gt`, tym częściej ekstremalny ratio przy normalnej długości predykcji OCR.

### 3. Side-by-side — głęboki sample (medianowy ratio, tables)

**Sample:** `page-28c45f5f-7e0d-464a-89ec-8de3a4abb927.png` (najbliższy medianie ratio ≈ 29,2; źródło: `03_deep_dive.txt`).

**GT (pierwsze ~300 znaków, zapis w dumpie = pełny „tekstowy” GT dla metryki):**

> `J. Cardiovasc. Dev. Dis. 2025, 12, 13`  
> `Table 1. Classification of congenital coronary abnormalities.`

**PRED (początek preview 500 znaków — reszta strony to dalszy artykuł + struktura):**

> `recommendations ofthe Cardiological Organizational CommitteeforSportsEligibility (COCIS) [1,2].`  
> `# Background`  
> `Theprevalence of CAAsremainsunclear...`

W dumpie: `len_gt=100`, `len_pred=2944`, `n_tables_gt=1`, `n_tables_pred=1`, **TEDS (S-TEDS) ~0,14** — struktura tabeli mocno się różni. **GT nie zawiera treści tabeli jako tekstu** (w manifestcie jest w `html`, nie w polu sklejanym do `_gt_text_from_layout`).

### 4. Kategorie `layout_dets` w manifeście

Źródło: `eval/results/diagnosis/05_our_logic.txt`, histogram po **pierwszych 100 wpisach** manifestu:

- **`equation_isolated`**: 888 detekcji, **0 z `text`**, **888 z `latex`**.
- **`text_block`**: 847 / 847 z `text`.
- **`table`**: 2 detekcje, **0 z `text`**, **2 z `html`**.
- **`title`**, **`header`**, **`page_number`**, **`figure_caption`**, **`code_txt`**, itd.

Wniosek: **znacząca część sygnału GT (LaTeX, HTML tabel) nie wchodzi do łańcucha złożonego wyłącznie z `det["text"]`.**

### 5. Obecna logika `_gt_text_from_layout`

Źródło: wycinek z `src/bigos/eval/omnidocbench.py` w `05_our_logic.txt`:

- Najpierw zbierane są detekcje z `category_type` ∈ `_TEXT_CATEGORIES` (m.in. `text`, `paragraph_title`, … — **nie** `text_block` ani `title` w tej nazwie) **albo** pusty typ.
- Jeśli nic — **fallback**: każdy blok z niepustym `text`.

**Co jest pomijane w praktyce:** bloki **bez** `text`, a z **`html`** lub **`latex`** (tabele, typowe równania `equation_isolated`). To dokładnie pokrywa się z histogramem.

Dodatkowo schemat OmniDocBench używa nazwy **`text_block`**, podczas gdy kod oczekuje m.in. **`text`** — pierwsza ścieżka często nie trafia; **fallback ratuje zwykły tekst** z `text_block`, ale **nie ratuje** treści z `html`/`latex`.

### 6. Logika OmniDocBench (reference repo)

Repozytorium sklonowane do `/tmp/omnidocbench-ref` (sieć OK).

W **`tools/json2md.py`** (fragment konceptualny — jak buduje się „pełniejszy” MD z JSON):

- Dla `category_type == 'table'`: zapis **`item[table_format]`** (domyślnie `html`).
- Dla bloków z `text`: normalizacja i zapis tekstu (np. `title` → nagłówek `#`).
- W gałęzi `elif item.get('html')` / `elif item.get('latex')`: zapis **`html`** lub **`latex`**.

Oficjalny **end-to-end** (`src/dataset/end2end_dataset.py`) ocenia osobno bloki (tekst, formuły, tabele, reading order) — **nie** redukuje całej strony do jednego łańcucha z samych pól `text`.

Szczegóły dopasowań: `src/core/matching/match*.py`, metryki: `src/metrics/cal_metric.py`, `table_metric.py` (TEDS z treścią komórek), itd. — pełna lista trafień w `eval/results/diagnosis/04_reference.txt`.

## Diagnoza

**Opcja A — GT jest niepełne względem tego, co user porównuje z pred (najbardziej uzasadniona):**

- **Dowód ilościowy:** histogram pokazuje masowe **`latex` bez `text`** oraz **`html` bez `text`**.
- **Dowód jakościowy:** sample medianowy — GT to dwie linijki nagłówka/tabeli, pred to długi artykuł + tabela HTML w markdown; **niedopasowanie długości jest oczekiwane**, jeśli GT nie zawiera treści tabeli ani akapitów z `text_block` w jednym spójnym „full page string” albo jeśli chunk GT jest tylko legendą tabeli.

**Opcja B — pred zbyt obszerne:** częściowo (Docling produkuje pełny OCR strony), ale **to nie wyjaśnia** samego braku treści tabeli w GT tekstowym; **page breaków `---`** w preview nie dominuje jako główna przyczyna ratio 34×.

**Opcja C (inne):** Kodowanie / język — **wtórne**; dla academic część GT to już długi LaTeX w `text`, wtedy ratio spada — zgodne z obserwacją dwóch reżimów na jednym benchu.

**Wybór:** **Opcja A** jako główna, z elementami **B** (pred naturalnie dłuższy od „samej legendy”).

## Proponowany fix (na przyszły PR — nie wykonany w tej diagnostyce)

1. **Zsynchronizować nazwy kategorii** z manifestem: `text_block`, `title`, `header`, `figure_caption`, `code_txt`, `page_number`, … (mapowanie 1:1 zamiast `text` / `paragraph_title`).
2. **Dla `table`:** do łańcucha GT dodać **tekst wyekstrahowany z `html`** (np. strip tagów + normalizacja spacji) albo surowy HTML — zgodnie z tym, co ma być porównywane z pred (uwaga: wtedy porównanie z MD Doclinga może wymagać tej samej normalizacji co w `normalize_text`).
3. **Dla `equation_isolated` / `equation_inline`:** dodać **`latex`** (po oczyszczeniu delimiterów) do GT tekstowego **albo** wyłączyć te bloki z „jednego stringa” i oceniać osobno (jak OmniDocBench).
4. **Sortowanie:** kontynuować po `order`; obsłużyć `order is None` (jak w próbkach `equation_semantic`).
5. **Opcjonalnie:** scalanie **truncated** z `extra["relation"]` jak w `json2md.py` — jeśli brakuje kontekstu w prostym konkatenacji.

## Spodziewany efekt po fixie

- **`len_ratio`** na subsetcie **tables** powinien **spaść wyraźnie** (z ~34 średnio w stronę **~1,5–4** jako luźny zakres — zależnie od tego, czy HTML tabeli jest liczony jako znaki vs markdown Doclinga); dokładna wartość zależy od normalizacji.
- **NED** powinno **spaść**, jeśli GT i pred pokrywają ten sam zbiór semantyczny; jeśli po fixie NED pozostaje **wysokie**, kolejny podejrzany to **jakość OCR / kolejność czytania**, nie sama długość GT.

## Następne kroki

1. **Diagnoza jest wystarczająco pewna na PR-B** — implementacja rozszerzonego GT + test regresji na kilku dumpach (porównanie `len_gt` przed/po).
2. Jeśli po PR-B NED nadal ~0,8+ na tables: **diagnostyka OCR** (fragmenty vs pełna strona) lub **alignment** z oficjalnym pipeline (oddzielne metryki tekst/tabela/formuła).
3. Jeśli zespół chce **ściśle** odwzorować leaderboard: rozważyć **eksport pred do Markdown per strona** i uruchomienie **oficjalnego evaluatora** OmniDocBench zamiast jednego stringa textowej edycji.

---

## Załączniki (wygenerowane komendami)

| Plik | Opis |
|------|------|
| `eval/results/diagnosis/01_dumps_inspection.txt` | 5 dumpów × 2 subsety |
| `eval/results/diagnosis/02_length_stats.txt` | Rozkłady + medianowy sample |
| `eval/results/diagnosis/03_deep_dive.txt` | Pełny deep-dive medianowego sample (tables) |
| `eval/results/diagnosis/04_reference.txt` | Przeszukanie `/tmp/omnidocbench-ref` |
| `eval/results/diagnosis/05_our_logic.txt` | Kod `_gt_text_from_layout` + histogram |

Skrypty: `scripts/diagnose/01_read_dumps.py` … `05_our_gt_logic.py`.
