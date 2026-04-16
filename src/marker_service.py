"""Marker-based PDF extraction service.

Runs Marker (marker-pdf) to convert PDFs to paginated markdown + extracted
images.  Provides utilities for splitting the output by page range and
handling image references for graphic pages.
"""
from __future__ import annotations

import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Marker page delimiter format (--paginate_output):
#   \n\n{0-based page number}\n{48 dashes}\n\n
# ---------------------------------------------------------------------------
_PAGE_DELIM_RE = re.compile(
    r"\n\n\{?(\d+)\}?\n-{48}\n\n"
)
_PAGE_DELIM_FALLBACK_RE = re.compile(
    r"(?:^|\n\n)\{?(\d+)\}?\n?-{48}\n\n"
)

# Matches: optionally a <span id="page-N-M"></span> before the image
# and the ![](image.jpeg) itself.
_IMG_REF_RE = re.compile(
    r"(?:<span[^>]*></span>\s*)?!\[\]\((_page_(\d+)_[^)]+\.jpe?g)\)"
)


def run_marker_extraction(
    pdf_path: Path,
    output_dir: Path,
    workers: int = 4,
    page_range: str | None = None,
) -> tuple[str, dict[str, "PIL.Image.Image"]]:
    """
    Run Marker on a single PDF and return (markdown_text, images_dict).

    markdown_text  -- paginated markdown (0-based page delimiters)
    images_dict    -- {filename: PIL.Image} for all extracted images

    Images are also saved to output_dir on disk.
    output_dir is created if it doesn't exist.
    """
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.config.parser import ConfigParser
    from marker.output import text_from_rendered

    output_dir.mkdir(parents=True, exist_ok=True)

    config_parser = ConfigParser({
        "output_format": "markdown",
        "paginate_output": True,
        "workers": workers,
        **({"page_range": page_range} if page_range else {}),
    })
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
    )
    rendered = converter(str(pdf_path))
    text, _, images = text_from_rendered(rendered)

    # Save images to disk
    for filename, img in images.items():
        img_path = output_dir / filename
        img.save(str(img_path))

    # Save full markdown alongside images for debugging / re-use
    (output_dir / "_full_marker.md").write_text(text, encoding="utf-8")

    return text, images


def split_marker_text_into_segment(
    markdown_text: str,
    start_page: int,  # 1-based, inclusive
    end_page: int,    # 1-based, inclusive
) -> str:
    """
    Slice the paginated Marker markdown to only include pages in [start_page, end_page].
    Marker uses 0-based page indices in delimiters; we convert to 1-based.
    Returns the extracted text with our standard PAGE_SEPARATOR format.
    """
    # Split into (page_idx_0based, content) pairs.
    # Content before the first delimiter belongs to page 0.
    parts: list[tuple[int, str]] = []

    matches = list(_PAGE_DELIM_RE.finditer(markdown_text))

    if not matches:
        # No pagination markers — treat whole text as page 1
        parts = [(0, markdown_text.strip())]
    else:
        # Content before first delimiter belongs to page 0
        first_content = markdown_text[: matches[0].start()].strip()
        if first_content:
            parts.append((0, first_content))

        for i, m in enumerate(matches):
            page_idx = int(m.group(1))  # 0-based
            content_start = m.end()
            content_end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)
            content = markdown_text[content_start:content_end].strip()
            parts.append((page_idx, content))

    # Filter to requested range (convert 1-based to 0-based)
    start_0 = start_page - 1
    end_0 = end_page - 1

    # When marker is called with page_range, some backends may emit paginated
    # indices relative to the extracted subset (0..N-1) instead of original PDF
    # indices. If that pattern is detected, shift indices to absolute pages.
    if parts:
        max_page_idx = max(p for p, _ in parts)
        if max_page_idx < start_0 and start_0 > 0:
            parts = [(p + start_0, content) for p, content in parts]

    chunks: list[str] = []
    for page_idx, content in parts:
        if start_0 <= page_idx <= end_0:
            page_1based = page_idx + 1
            sep = f"\n\n\n=== [PAGE {page_1based}] ===\n\n\n"
            chunks.append(f"{sep}{content}" if content else sep)

    return "\n".join(chunks).strip() + "\n" if chunks else ""


def normalize_marker_page_markers(text: str) -> str:
    """
    Replace marker pagination delimiters with app page separators:
    {0} + dashed line -> === [PAGE 1] ===
    """
    def repl(match: re.Match) -> str:
        page_0 = int(match.group(1))
        page_1 = page_0 + 1
        return f"\n\n\n=== [PAGE {page_1}] ===\n\n\n"

    return _PAGE_DELIM_FALLBACK_RE.sub(repl, text)


def find_image_refs_for_pages(
    segment_text: str,
    graphic_pages: list[int],  # 1-based page numbers
) -> list[tuple[str, int]]:
    """
    Return list of (image_filename, 1-based-page) for every image reference
    in segment_text whose page falls in graphic_pages.

    Marker filenames use 0-based page indices, so _page_4_... = page 5 (1-based).
    """
    graphic_set = set(graphic_pages)
    results: list[tuple[str, int]] = []
    seen: set[str] = set()

    for m in _IMG_REF_RE.finditer(segment_text):
        filename = m.group(1)
        page_0based = int(m.group(2))
        page_1based = page_0based + 1
        if page_1based in graphic_set and filename not in seen:
            seen.add(filename)
            results.append((filename, page_1based))

    return results


def replace_image_refs_with_descriptions(
    text: str,
    descriptions: dict[str, str],  # image_filename -> description
) -> str:
    """
    Replace ![](_page_N_Figure_X.jpeg) (and any preceding <span> anchor)
    with the AI-generated description for that image.
    Only images that appear in `descriptions` are replaced.
    """
    def replacer(m: re.Match) -> str:
        filename = m.group(1)
        if filename in descriptions:
            desc = descriptions[filename].strip()
            return f"[OPIS GRAFICZNY: {filename}]\n{desc}"
        return m.group(0)  # leave unchanged

    return _IMG_REF_RE.sub(replacer, text)


def strip_remaining_image_refs(text: str) -> str:
    """
    Remove all remaining Marker image references (![](_page_*)) that were not
    replaced by descriptions (i.e., from non-graphic pages or unprocessed images).
    Also removes orphaned <span id="page-..."></span> anchors.
    """
    # Remove image refs (with optional preceding span anchor already consumed by _IMG_REF_RE)
    text = _IMG_REF_RE.sub("", text)
    # Remove any remaining standalone span anchors that marker inserts
    text = re.sub(r"<span\s+id=\"page-[\d-]+\"\s*></span>\s*", "", text)
    # Collapse multiple blank lines introduced by removals
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def delete_marker_images(output_dir: Path, image_filenames: list[str]) -> None:
    """Delete specific extracted image files from the marker output directory."""
    for fname in image_filenames:
        img_path = output_dir / fname
        if img_path.exists():
            img_path.unlink()
