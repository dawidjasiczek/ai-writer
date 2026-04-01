from __future__ import annotations

import pdfplumber


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


def normalize_cell(value: str | None) -> str:
    return "" if value is None else " ".join(value.split())


def table_is_usable(table: list[list[str | None]]) -> bool:
    cells = [normalize_cell(cell) for row in table for cell in row if normalize_cell(cell)]
    if not cells:
        return False
    max_cols = max(len(row) for row in table)
    if max_cols > 12:
        return False
    one_char_ratio = sum(1 for cell in cells if len(cell) == 1) / len(cells)
    avg_len = sum(len(cell) for cell in cells) / len(cells)
    return one_char_ratio < 0.4 and avg_len >= 3


def _format_table(table: list[list[str | None]], table_idx: int) -> str:
    lines = [f"[TABLE {table_idx}]"]
    for row in table:
        lines.append(" | ".join(normalize_cell(cell) for cell in row))
    return "\n".join(lines)


def extract_page_content(page: pdfplumber.page.Page) -> str:
    text = (page.extract_text(layout=True) or "").strip()
    selected_tables: list[list[list[str | None]]] = []
    for settings in TABLE_SETTINGS_CANDIDATES:
        tables = page.extract_tables(settings)
        usable_tables = [table for table in tables if table and table_is_usable(table)]
        if usable_tables:
            selected_tables = usable_tables
            break

    blocks = []
    if text:
        blocks.append("[TEXT]")
        blocks.append(text)
    if selected_tables:
        table_blocks = [
            _format_table(table=table, table_idx=index)
            for index, table in enumerate(selected_tables, start=1)
        ]
        blocks.append("\n\n".join(table_blocks))
    if not blocks:
        return ""
    return "\n\n".join(blocks).strip()


def extract_pdf_range(pdf_path: str, start_page: int, end_page: int) -> str:
    chunks: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        if start_page > total_pages:
            raise ValueError(f"start_page {start_page} is > total pages {total_pages}")
        clipped_end = min(end_page, total_pages)

        for page_idx in range(start_page - 1, clipped_end):
            page_no = page_idx + 1
            content = extract_page_content(pdf.pages[page_idx]).strip()
            chunks.append(f"[PAGE {page_no}]\n{content}".strip())
    return "\n\n---\n\n".join(chunks).strip() + "\n"


def extract_pdf_full(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
    return extract_pdf_range(pdf_path=pdf_path, start_page=1, end_page=total_pages)
