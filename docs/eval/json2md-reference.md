# Reference: `tools/json2md.py` (OmniDocBench)

Plik źródłowy: `/tmp/omnidocbench-ref/tools/json2md.py` (repozytorium OmniDocBench).

## Cel skryptu

Konwersja pojedynczej próbki z `OmniDocBench*.json` na plik Markdown na dysku: przycinanie figur z obrazu strony, zapis cropów do `imgs/`, zapis treści jako `.md`.

## Kluczowy fragment — pętla wyjściowa

```python
sep = '\n\n'
if anno["category_type"] == 'table':
    f.write(item[table_format])   # domyślnie 'html'
    f.write(sep)
elif item.get('text'):
    if item["category_type"] == 'title':
        f.write('# ' + text_norm(item['text'].strip('#').strip()))
        f.write(sep)
    else:
        f.write(text_norm(item['text']))
        f.write(sep)
elif item.get('html'):
    f.write(item['html'])
    f.write(sep)
elif item.get('latex'):
    f.write(item['latex'])
    f.write(sep)
```

## Zasady wejścia (`layout_dets`)

1. **Filtrowanie:** do dalszego przetwarzania trafiają **tylko** detekcje z **prawdziwym `order`** (`if x.get('order'):`). W Pythonie **`order == 0` jest wykluczone** (wartość falsy).

2. **Sortowanie końcowe:** `sorted(merged_annos, key=lambda x: x['order'])`.

3. **Scalanie truncated:** z `sample["extra"]["relation"]` wybierane są relacje `relation_type == "truncated"`; bloki o podanych `anno_id` są scalane w jeden blok tekstowy (merge wg `order`), treść złożona z `block['text']` z heurystyką `langid` dla angielskiego (łączenie ze spacją vs łączenie bez myślnika). **Bez `extra`** ten krok jest pusty.

4. **Figura (`category_type == 'figure'`):** przed gałęzią table/text — zapis `![](./imgs/{stem}_{anno_id}.jpg)` + `sep`. **Nie** wchodzi w gałąź `elif text` w tej samej iteracji jako osobna ścieżka treści — najpierw crop i link.

5. **Tabela:** gałąź **`category_type == 'table'`** — zapis **`item[table_format]`** przy `table_format = 'html'` → pole **`html`**.

6. **Tekst:** gałąź **`elif item.get('text')`** — dla **`title`** prefiks `# ` + `text_norm(...)`; dla pozostałych **`text_norm(text)`**.

7. **Fallback:** **`elif item.get('html')`** / **`elif item.get('latex')`** — surowy HTML / LaTeX (bez dodatkowego owijania w kodzie referencyjnym).

8. **Normalizacja tekstu:** `text_norm` → `replace_repeated_chars` (regexy na powtórzenia podkreślników, spacji, symboli) oraz zamiana literalnych `/t`, `/n`.

## Tabela: kategoria → pole treści → format wyjścia

| Warunek w kodzie | Pole źródłowe | Wynik w MD |
|------------------|---------------|------------|
| `category_type == 'figure'` | crop z `poly` | `![](./imgs/{stem}_{anno_id}.jpg)` |
| `category_type == 'table'` | `html` (przez `item['html']` przy `table_format='html'`) | surowy HTML |
| `elif text` i `category_type == 'title'` | `text` | `# {text_norm(...)}` |
| `elif text` (inne) | `text` | `text_norm(text)` |
| `elif html` | `html` | surowy HTML |
| `elif latex` | `latex` | surowy LaTeX |

**Uwaga:** Kategorie nie są enumerowane explicite — każdy blok z tekstem przechodzi przez gałąź `text` (w tym np. `page_number`, `header`, jeśli mają `text` i `order`).

## Kategorie „wykluczone”

Brak jawnej listy **skip** po `category_type`. Wykluczenie następuje **pośrednio**:

- brak **truthy `order`** → blok nie trafia do `annos`;
- brak `figure`/`table`/`text`/`html`/`latex` w kolejności gałęzi → nic nie zapisano dla tego bloku (np. pusty blok).

## Separator między blokami

Stały **`sep = '\n\n'`** po każdym fragmencie treści (oprócz samego zapisu figury, po którym też używane jest `sep`).

## Implementacja w `bigos`

Skrypt referencyjny zapisuje na dysk i wymaga PIL oraz obrazu — w evalu **nie** kopiujemy cropów; dla figure generujemy **ten sam** wzorzec ścieżki Markdown co w `json2md.py`, bez walidacji istnienia pliku.
