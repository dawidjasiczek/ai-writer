# Thesis Source Analyzer

Aplikacja desktopowa do analizy źródeł PDF na potrzeby pracy magisterskiej.
Umożliwia wyciąganie tekstu, opisywanie stron graficznych przez AI Vision,
a następnie ekstrakcję cytatów i podsumowań do zadanych zagadnień tematycznych.

---

## Wymagania

- **Python 3.10 - 3.13** (zalecane **Python 3.12**, pobierz z https://python.org)
- Klucz API OpenAI (https://platform.openai.com/api-keys)
- **Linux/Ubuntu**: wymagany pakiet systemowy `python3-tk` (GUI):
  ```bash
  sudo apt install python3-tk
  ```
  Na Windows i macOS tkinter jest wbudowany w standardową instalację Pythona.

### GPU (NVIDIA) / PyTorch na Windows

Jeśli chcesz używać Markera na GPU (CUDA), PyTorch musi wspierać architekturę Twojej karty.
Przy bardzo nowych kartach (np. Blackwell, `sm_120`) stabilne buildy mogą jeszcze nie działać
i wtedy potrzebny jest nightly build.

Instalacja nightly PyTorch (CUDA 12.8):

```bash
pip uninstall -y torch torchvision torchaudio
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
```

Weryfikacja:

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.get_device_name(0)); print(torch.cuda.get_device_capability(0)); print(torch.cuda.get_arch_list())"
python -c "import torch; x=torch.randn(1024,1024,device='cuda'); y=torch.randn(1024,1024,device='cuda'); print((x@y).mean().item())"
```

Jeśli `torch.cuda.get_arch_list()` zawiera architekturę Twojej karty (np. `sm_120`) i drugi test
działa bez błędu, GPU jest poprawnie skonfigurowane.

---

## Uruchomienie na Windows (szybki start)

1. Zainstaluj Python **3.10 - 3.13** (najlepiej **3.12**) i zaznacz opcję **"Add Python to PATH"** podczas instalacji.
2. Pobierz / skopiuj cały folder projektu na dysk, np. `C:\thesis-writer`.
3. Kliknij dwukrotnie plik **`run.bat`**.
   - Przy pierwszym uruchomieniu automatycznie stworzy środowisko wirtualne (`venv`)
     i zainstaluje wszystkie zależności.
   - Przy kolejnych uruchomieniach tylko uruchamia aplikację.
   - Skrypt zatrzyma się z czytelnym błędem, jeśli wykryje Python 3.14+.
   - Skrypt zapyta o profil zależności:
     - `C` = CUDA/GPU (domyślny, plik `requirements-cuda-windows.txt`)
     - `Z` = zwykły CPU (plik `requirements.txt`)
   - Gdy wybierzesz profil CUDA, skrypt wykona sanity check (`torch.cuda.is_available()` + test mnożenia macierzy na GPU).
     Jeśli test nie przejdzie, automatycznie odinstaluje pakiety `torch/torchvision/torchaudio`
     i zrobi fallback do profilu CPU (`requirements.txt`).

> Uwaga (Windows): Python 3.14 jest obecnie problematyczny dla części zależności
> (`Pillow`, `regex`, zależności Markera) i może wymuszać kompilację z C/C++.
> Użyj Python 3.12 lub 3.13.

---

## Uruchomienie ręczne (Linux / macOS / Windows bez .bat)

```bash
# 1. Utwórz środowisko wirtualne (tylko raz)
python3 -m venv venv

# 2. Aktywuj środowisko
# Windows:
venv\Scripts\activate
# Linux / macOS:
source venv/bin/activate

# 3. Zainstaluj zależności (tylko raz lub po aktualizacji)
pip3 install -r requirements.txt

# 4. Uruchom aplikację
python3 main.py
```

Opcjonalnie możesz przekazać ścieżkę do własnego folderu projektu:

```bash
python main.py "C:/Users/ja/moja-praca-magisterska"
```

Jeżeli argument nie zostanie podany, aplikacja tworzy i używa folderu
`~/thesis-projects/default`.

---

## Struktura projektu (pliki użytkownika)

```
<folder-projektu>/
  project_state.json        ← centralny stan projektu
  sources/                  ← tutaj wrzucasz pliki PDF
  output/
    <source_id>/
      segments/
        <seg_id>_raw.txt    ← wyciągnięty tekst (krok 5)
        <seg_id>_full.txt   ← tekst z wypełnionymi opisami grafik (krok 7)
      graphics/
        page_N.png          ← renderowana strona
        page_N_description.txt  ← opis AI (krok 6)
      analysis/
        <seg_id>_quotes.json    ← wyniki analizy segmentu (krok 9)
      source_quotes.json    ← agregacja dla całego źródła
    aggregated/
      question_N_all.json   ← wszystkie cytaty dla pytania N
      question_N_all.txt    ← eksport do .txt
```

---

## Instrukcja obsługi

### 1. Zakładka „Źródła"
- Kliknij **Dodaj PDF** – wybierz jeden lub więcej plików PDF.
  Pliki zostaną skopiowane do folderu `sources/`.
- Nadaj każdemu plikowi czytelną **nazwę wyświetlaną**.
- Dodaj **segmenty** (zakresy stron tematycznych).
- Wpisz numery **stron graficznych** (zawierające wykresy/rysunki), oddzielone przecinkami.

### 2. Zakładka „Ekstrakcja"
- Zaznacz segmenty do przetworzenia.
- **Krok 1 – Wyciągnij tekst**: extrahuje tekst za pomocą pdfplumber;
  strony graficzne zastępuje placeholderami `{{TRESCI_GRAFICZNE_STRONA_N}}`.
- **Krok 2 – Opisz strony graficzne**: renderuje strony z grafikami do PNG,
  wysyła do OpenAI Vision, zapisuje opisy.
- **Krok 3 – Wypełnij placeholdery**: tworzy nowy plik z wstawionymi opisami.
- Podgląd wyciągniętej treści dostępny po prawej stronie.

### 3. Zakładka „Pytania"
- Definiuj zagadnienia tematyczne (pytania) z opcjonalnym opisem.
- Każde pytanie dostaje unikalny ID (od 1 wzwyż).

### 4. Zakładka „Analiza"
- Zaznacz segmenty i wybierz model GPT.
- Kliknij **Uruchom analizę** – AI wyciągnie cytaty i podsumowania
  dla każdego pytania z każdego segmentu.
- Wyniki zapisywane są w `output/<source_id>/analysis/` oraz agregowane.
- Maksymalnie 4 zadania AI działają równocześnie.
- Bardzo długie segmenty są automatycznie dzielone na chunki.

### 5. Zakładka „Wyniki"
- Wybierz pytanie z listy.
- Odfiltruj źródła / segmenty checkboxami.
- Kliknij **Wyświetl wyniki** – zobaczysz cytaty i podsumowania.
- Kliknij **Eksportuj do .txt** – zapisuje czytelny plik tekstowy.

### 6. Zakładka „Ustawienia"
- Wpisz klucz OpenAI API.
- Wybierz domyślny model (`gpt-5.4-mini` / `gpt-5.4-nano` / `gpt-5.4`).
- Edytuj prompty systemowe używane przez AI.

---

## Zależności

| Pakiet | Zastosowanie |
|--------|-------------|
| `customtkinter` | GUI |
| `openai` | OpenAI Responses API |
| `pdfplumber` | Ekstrakcja tekstu z PDF |
| `PyMuPDF` | Renderowanie stron PDF do obrazów |
| `Pillow` | Obsługa obrazów |

---

## Uwagi

- Klucz API jest zapisywany w `project_state.json` w folderze projektu.
  Nie udostępniaj tego pliku publicznie.
- Model `gpt-5.4-nano` jest najtańszy; `gpt-5.4` najdokładniejszy.
- Wyniki analizy są persystowane – możesz wznawiać pracę w dowolnym momencie.
