from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import pdfplumber

# ---------------------------------------------------------------------------
# Table extraction helpers (adapted from EXAMPLE_PDF_PLUMBER_1.py)
# ---------------------------------------------------------------------------

TABLE_SETTINGS_CANDIDATES = [
    {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
    {"vertical_strategy": "lines_strict", "horizontal_strategy": "lines_strict"},
    {
        "vertical_strategy": "text",
        "horizontal_strategy": "text",
        "min_words_vertical": 4,
        "min_words_horizontal": 1,
        "text_x_tolerance": 3,
        "text_y_tolerance": 3,
    },
]


def _normalize_cell(value: str | None) -> str:
    return "" if value is None else " ".join(value.split())


def _table_is_usable(table: list[list[str | None]]) -> bool:
    cells = [_normalize_cell(c) for row in table for c in row if _normalize_cell(c)]
    if not cells:
        return False
    max_cols = max(len(row) for row in table)
    if max_cols > 12:
        return False
    one_char_ratio = sum(1 for c in cells if len(c) == 1) / len(cells)
    avg_len = sum(len(c) for c in cells) / len(cells)
    return one_char_ratio < 0.4 and avg_len >= 3


def _format_table(table: list[list[str | None]], table_idx: int) -> str:
    lines = [f"[TABLE {table_idx}]"]
    for row in table:
        lines.append(" | ".join(_normalize_cell(c) for c in row))
    return "\n".join(lines)


def _extract_page_content(page: pdfplumber.page.Page) -> str:
    text = (page.extract_text(layout=True) or "").strip()
    selected_tables: list[list[list[str | None]]] = []
    for settings in TABLE_SETTINGS_CANDIDATES:
        tables = page.extract_tables(settings)
        usable = [t for t in tables if t and _table_is_usable(t)]
        if usable:
            selected_tables = usable
            break

    blocks = []
    if text:
        blocks.append("[TEXT]")
        blocks.append(text)
    if selected_tables:
        blocks.append(
            "\n\n".join(
                _format_table(t, i) for i, t in enumerate(selected_tables, start=1)
            )
        )
    return "\n\n".join(blocks).strip() if blocks else ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

PAGE_SEPARATOR = "\n\n\n=== [PAGE {page}] ===\n\n\n"
# Note: 4 braces so that .format(page=N) produces the literal {{TRESCI_GRAFICZNE_STRONA_N}}
GRAPHIC_PLACEHOLDER = "{{{{TRESCI_GRAFICZNE_STRONA_{page}}}}}"


def extract_segment_text(
    pdf_path: Path,
    start_page: int,
    end_page: int,
    graphic_pages: list[int],
    page_numbering_start_pdf_page: int = 1,
) -> str:
    """
    Extract text from a page range.  Pages in `graphic_pages` become placeholder
    strings instead of real text.  Pages are separated by PAGE_SEPARATOR.
    """
    graphic_set = set(graphic_pages)
    page_shift = page_numbering_start_pdf_page - 1
    chunks: list[str] = []

    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        clipped_end = min(end_page, total)
        if start_page > total:
            raise ValueError(f"start_page {start_page} exceeds total pages {total}")

        for idx in range(start_page - 1, clipped_end):
            pdf_page_no = idx + 1
            logical_page_no = pdf_page_no - page_shift
            separator = PAGE_SEPARATOR.format(page=logical_page_no)
            if pdf_page_no in graphic_set:
                content = GRAPHIC_PLACEHOLDER.format(page=logical_page_no)
            else:
                content = _extract_page_content(pdf.pages[idx]).strip()
            chunks.append(f"{separator}[TEXT]\n{content}" if content else separator)

    return "\n".join(chunks).strip() + "\n"


def fill_placeholders(raw_text: str, descriptions: dict[int, str]) -> str:
    """
    Replace {{TRESCI_GRAFICZNE_STRONA_N}} placeholders with actual AI descriptions.
    `descriptions` is a mapping of page_number -> description string.
    """

    def replacer(match: re.Match) -> str:
        page = int(match.group(1))
        desc = descriptions.get(page, "")
        return f"[OPIS GRAFICZNY STRONY {page}]\n{desc}"

    return re.sub(r"\{\{TRESCI_GRAFICZNE_STRONA_(\d+)\}\}", replacer, raw_text)


def render_page_to_image(pdf_path: Path, page_num: int, output_path: Path, dpi: int = 200) -> Path:
    """
    Render a single PDF page to a PNG image using PyMuPDF.
    page_num is 1-based.
    Returns the path to the saved image.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    if page_num < 1 or page_num > len(doc):
        raise ValueError(f"page_num {page_num} out of range 1..{len(doc)}")

    page = doc[page_num - 1]
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(output_path))
    doc.close()
    return output_path


def get_pdf_page_count(pdf_path: Path) -> int:
    with pdfplumber.open(str(pdf_path)) as pdf:
        return len(pdf.pages)
