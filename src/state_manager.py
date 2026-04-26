from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from .models import (
    ProjectState,
    Prompts,
    Question,
    Segment,
    Source,
    ProcessingStatus,
)


class StateManager:
    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.state_file = project_dir / "project_state.json"
        self.state = ProjectState()
        self._ensure_dirs()
        self.load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _ensure_dirs(self) -> None:
        (self.project_dir / "sources").mkdir(parents=True, exist_ok=True)
        (self.project_dir / "output" / "aggregated").mkdir(parents=True, exist_ok=True)

    def load(self) -> None:
        if self.state_file.exists():
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            self.state = ProjectState.from_dict(data)
        # Ensure segments are sorted by start_page after loading
        for src in self.state.sources:
            src.segments.sort(key=lambda s: s.start_page)

    def save(self) -> None:
        tmp = self.state_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state.to_dict(), f, ensure_ascii=False, indent=2)
        tmp.replace(self.state_file)

    # ------------------------------------------------------------------
    # Source operations
    # ------------------------------------------------------------------

    def add_source(self, filename: str, display_name: Optional[str] = None) -> Source:
        src_id = f"src_{uuid.uuid4().hex[:8]}"
        source = Source(
            id=src_id,
            filename=filename,
            display_name=display_name or filename,
        )
        self.state.sources.append(source)
        self._ensure_source_dirs(src_id)
        self.save()
        return source

    def remove_source(self, source_id: str) -> None:
        self.state.sources = [s for s in self.state.sources if s.id != source_id]
        self.save()

    def rename_source(self, source_id: str, display_name: str) -> None:
        src = self.get_source(source_id)
        if src:
            src.display_name = display_name
            self.save()

    def get_source(self, source_id: str) -> Optional[Source]:
        return next((s for s in self.state.sources if s.id == source_id), None)

    def get_source_pdf_path(self, source_id: str) -> Optional[Path]:
        src = self.get_source(source_id)
        if src is None:
            return None
        return self.project_dir / "sources" / src.filename

    # ------------------------------------------------------------------
    # Segment operations
    # ------------------------------------------------------------------

    def add_segment(
        self, source_id: str, name: str, start_page: int, end_page: int
    ) -> Optional[Segment]:
        src = self.get_source(source_id)
        if src is None:
            return None
        seg_id = f"seg_{uuid.uuid4().hex[:8]}"
        seg = Segment(id=seg_id, name=name, start_page=start_page, end_page=end_page)
        src.segments.append(seg)
        src.segments.sort(key=lambda s: s.start_page)
        self.save()
        return seg

    def update_segment(
        self,
        source_id: str,
        segment_id: str,
        name: Optional[str] = None,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
    ) -> None:
        src = self.get_source(source_id)
        if src is None:
            return
        seg = next((s for s in src.segments if s.id == segment_id), None)
        if seg is None:
            return
        if name is not None:
            seg.name = name
        if start_page is not None:
            seg.start_page = start_page
        if end_page is not None:
            seg.end_page = end_page
        src.segments.sort(key=lambda s: s.start_page)
        self.save()

    def remove_segment(self, source_id: str, segment_id: str) -> None:
        src = self.get_source(source_id)
        if src is None:
            return
        src.segments = [s for s in src.segments if s.id != segment_id]
        self.save()

    def get_segment(self, source_id: str, segment_id: str) -> Optional[Segment]:
        src = self.get_source(source_id)
        if src is None:
            return None
        return next((s for s in src.segments if s.id == segment_id), None)

    # ------------------------------------------------------------------
    # Graphic pages
    # ------------------------------------------------------------------

    def set_graphic_pages(self, source_id: str, pages: list[int]) -> None:
        src = self.get_source(source_id)
        if src:
            src.graphic_pages = sorted(set(pages))
            self.save()

    def set_extraction_method(self, source_id: str, method: str) -> None:
        """Set extraction method for a source: 'pdfplumber' or 'marker'."""
        src = self.get_source(source_id)
        if src:
            src.extraction_method = method
            self.save()

    def set_single_segment(self, source_id: str, value: bool) -> None:
        src = self.get_source(source_id)
        if src:
            src.single_segment = value
            self.save()

    def set_page_numbering_start_pdf_page(self, source_id: str, value: int) -> None:
        src = self.get_source(source_id)
        if src:
            src.page_numbering_start_pdf_page = max(1, value)
            self.save()

    # ------------------------------------------------------------------
    # Processing status
    # ------------------------------------------------------------------

    def mark_text_extracted(self, source_id: str) -> None:
        src = self.get_source(source_id)
        if src:
            src.processing_status.text_extracted = True
            self.save()

    def mark_graphics_described(self, source_id: str) -> None:
        src = self.get_source(source_id)
        if src:
            src.processing_status.graphics_described = True
            self.save()

    def mark_placeholders_filled(self, source_id: str) -> None:
        src = self.get_source(source_id)
        if src:
            src.processing_status.placeholders_filled = True
            self.save()

    # ------------------------------------------------------------------
    # Questions
    # ------------------------------------------------------------------

    def add_question(self, title: str, description: str = "") -> Question:
        next_id = max((q.id for q in self.state.questions), default=0) + 1
        q = Question(id=next_id, title=title, description=description)
        self.state.questions.append(q)
        self.save()
        return q

    def update_question(
        self,
        question_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        q = next((x for x in self.state.questions if x.id == question_id), None)
        if q is None:
            return
        if title is not None:
            q.title = title
        if description is not None:
            q.description = description
        self.save()

    def remove_question(self, question_id: int) -> None:
        self.state.questions = [q for q in self.state.questions if q.id != question_id]
        self.save()

    # ------------------------------------------------------------------
    # Settings / prompts
    # ------------------------------------------------------------------

    def set_api_key(self, key: str) -> None:
        self.state.openai_api_key = key
        self.save()

    def set_default_model(self, model: str) -> None:
        self.state.default_model = model
        self.save()

    def update_prompts(self, **kwargs: str) -> None:
        for k, v in kwargs.items():
            if hasattr(self.state.prompts, k):
                setattr(self.state.prompts, k, v)
        self.save()

    def set_marker_workers(self, workers: int) -> None:
        self.state.marker_workers = max(1, workers)
        self.save()

    def set_gpt_workers(self, workers: int) -> None:
        self.state.gpt_workers = max(1, workers)
        self.save()

    # ------------------------------------------------------------------
    # Output path helpers
    # ------------------------------------------------------------------

    def _ensure_source_dirs(self, source_id: str) -> None:
        base = self.project_dir / "output" / source_id
        (base / "segments").mkdir(parents=True, exist_ok=True)
        (base / "graphics").mkdir(parents=True, exist_ok=True)
        (base / "analysis").mkdir(parents=True, exist_ok=True)
        (base / "marker").mkdir(parents=True, exist_ok=True)

    def raw_text_path(self, source_id: str, segment_id: str) -> Path:
        self._ensure_source_dirs(source_id)
        return self.project_dir / "output" / source_id / "segments" / f"{segment_id}_raw.txt"

    def full_text_path(self, source_id: str, segment_id: str) -> Path:
        self._ensure_source_dirs(source_id)
        return self.project_dir / "output" / source_id / "segments" / f"{segment_id}_full.txt"

    def graphics_dir(self, source_id: str) -> Path:
        self._ensure_source_dirs(source_id)
        return self.project_dir / "output" / source_id / "graphics"

    def graphic_image_path(self, source_id: str, page_num: int) -> Path:
        return self.graphics_dir(source_id) / f"page_{page_num}.png"

    def graphic_description_path(self, source_id: str, page_num: int) -> Path:
        return self.graphics_dir(source_id) / f"page_{page_num}_description.txt"

    def segment_analysis_path(self, source_id: str, segment_id: str) -> Path:
        self._ensure_source_dirs(source_id)
        return self.project_dir / "output" / source_id / "analysis" / f"{segment_id}_quotes.json"

    def source_quotes_path(self, source_id: str) -> Path:
        return self.project_dir / "output" / source_id / "source_quotes.json"

    def marker_output_dir(self, source_id: str) -> Path:
        """Directory where Marker stores its extracted markdown and images."""
        self._ensure_source_dirs(source_id)
        return self.project_dir / "output" / source_id / "marker"

    def question_aggregated_json_path(self, question_id: int) -> Path:
        return self.project_dir / "output" / "aggregated" / f"question_{question_id}_all.json"

    def question_aggregated_txt_path(self, question_id: int) -> Path:
        return self.project_dir / "output" / "aggregated" / f"question_{question_id}_all.txt"
