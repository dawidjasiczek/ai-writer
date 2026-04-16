from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Segment:
    id: str
    name: str
    start_page: int
    end_page: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "start_page": self.start_page,
            "end_page": self.end_page,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Segment":
        return cls(
            id=d["id"],
            name=d["name"],
            start_page=d["start_page"],
            end_page=d["end_page"],
        )


@dataclass
class ProcessingStatus:
    text_extracted: bool = False
    graphics_described: bool = False
    placeholders_filled: bool = False

    def to_dict(self) -> dict:
        return {
            "text_extracted": self.text_extracted,
            "graphics_described": self.graphics_described,
            "placeholders_filled": self.placeholders_filled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProcessingStatus":
        return cls(
            text_extracted=d.get("text_extracted", False),
            graphics_described=d.get("graphics_described", False),
            placeholders_filled=d.get("placeholders_filled", False),
        )


@dataclass
class Source:
    id: str
    filename: str
    display_name: str
    segments: list[Segment] = field(default_factory=list)
    graphic_pages: list[int] = field(default_factory=list)
    processing_status: ProcessingStatus = field(default_factory=ProcessingStatus)
    extraction_method: str = "pdfplumber"  # "pdfplumber" | "marker"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "display_name": self.display_name,
            "segments": [s.to_dict() for s in self.segments],
            "graphic_pages": self.graphic_pages,
            "processing_status": self.processing_status.to_dict(),
            "extraction_method": self.extraction_method,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Source":
        return cls(
            id=d["id"],
            filename=d["filename"],
            display_name=d.get("display_name", d["filename"]),
            segments=[Segment.from_dict(s) for s in d.get("segments", [])],
            graphic_pages=d.get("graphic_pages", []),
            processing_status=ProcessingStatus.from_dict(
                d.get("processing_status", {})
            ),
            extraction_method=d.get("extraction_method", "pdfplumber"),
        )


@dataclass
class Question:
    id: int
    title: str
    description: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "description": self.description}

    @classmethod
    def from_dict(cls, d: dict) -> "Question":
        return cls(
            id=d["id"],
            title=d["title"],
            description=d.get("description", ""),
        )


@dataclass
class Prompts:
    graphic_description: str = (
        "Jesteś asystentem analizującym strony dokumentów PDF. "
        "Opisz szczegółowo i dokładnie zawartość graficzną tej strony: "
        "wszystkie wykresy, tabele, diagramy, zdjęcia, rysunki i inne elementy wizualne. "
        "Podaj liczby, etykiety, legendy i wszelkie informacje zawarte w elementach graficznych. "
        "Odpowiedz po polsku."
    )
    quote_extraction: str = (
        "Jesteś asystentem naukowym pomagającym w pisaniu pracy magisterskiej. "
        "Otrzymasz fragment źródła akademickiego. Twoim zadaniem jest:\n"
        "1. Dla każdego zagadnienia z listy poniżej: wyciągnąć dokładne cytaty (dosłowne fragmenty tekstu) "
        "dotyczące tego zagadnienia jeśli się pojawiają, oraz napisać krótkie podsumowanie co ten fragment mówi na ten temat.\n"
        "2. Jeśli zagadnienie nie pojawia się w tekście, zwróć pustą listę cytatów i puste podsumowanie dla tego zagadnienia.\n"
        "3. Cytaty muszą być dosłowne, nie parafrazowane. "
        "Dla każdego cytatu podaj numer strony (page). Jeśli cytat rozciąga się na kilka stron, podaj też page_end (ostatnia strona cytatu); jeśli cytat mieści się na jednej stronie, ustaw page_end na null.\n"
        "4. WAŻNE: fragment_id w odpowiedzi JSON MUSI być dokładnie tym samym numerem ID co na liście zagadnień poniżej. "
        "Nie twórz własnych identyfikatorów. Każde zagadnienie z listy musi mieć swój wpis w 'fragments'.\n\n"
        "ZAGADNIENIA DO ANALIZY (format: ID. Tytuł):\n{questions_block}\n\n"
        "Odpowiedz w formacie JSON zgodnym ze schematem. "
        "Tablica 'fragments' musi zawierać dokładnie tyle elementów ile jest zagadnień na liście, "
        "każdy z poprawnym fragment_id równym ID zagadnienia."
    )

    def to_dict(self) -> dict:
        return {
            "graphic_description": self.graphic_description,
            "quote_extraction": self.quote_extraction,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Prompts":
        obj = cls()
        if "graphic_description" in d:
            obj.graphic_description = d["graphic_description"]
        if "quote_extraction" in d:
            obj.quote_extraction = d["quote_extraction"]
        return obj


@dataclass
class ProjectState:
    openai_api_key: str = ""
    default_model: str = "gpt-5.4-mini"
    sources: list[Source] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    prompts: Prompts = field(default_factory=Prompts)
    marker_workers: int = 4

    def to_dict(self) -> dict:
        return {
            "openai_api_key": self.openai_api_key,
            "default_model": self.default_model,
            "sources": [s.to_dict() for s in self.sources],
            "questions": [q.to_dict() for q in self.questions],
            "prompts": self.prompts.to_dict(),
            "marker_workers": self.marker_workers,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectState":
        return cls(
            openai_api_key=d.get("openai_api_key", ""),
            default_model=d.get("default_model", "gpt-5.4-mini"),
            sources=[Source.from_dict(s) for s in d.get("sources", [])],
            questions=[Question.from_dict(q) for q in d.get("questions", [])],
            prompts=Prompts.from_dict(d.get("prompts", {})),
            marker_workers=d.get("marker_workers", 4),
        )


# Quote extraction result models (for AI response parsing)

@dataclass
class Quote:
    text: str
    page: int
    page_end: Optional[int] = None  # set when the quote spans multiple pages

    def to_dict(self) -> dict:
        d: dict = {"text": self.text, "page": self.page}
        if self.page_end is not None:
            d["page_end"] = self.page_end
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Quote":
        return cls(
            text=d["text"],
            page=d["page"],
            page_end=d.get("page_end"),
        )


@dataclass
class FragmentResult:
    fragment_id: int
    fragment_title: str
    fragment_summary: str
    quotes: list[Quote] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "fragment_id": self.fragment_id,
            "fragment_title": self.fragment_title,
            "fragment_summary": self.fragment_summary,
            "quotes": [q.to_dict() for q in self.quotes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FragmentResult":
        return cls(
            fragment_id=d["fragment_id"],
            fragment_title=d["fragment_title"],
            fragment_summary=d.get("fragment_summary", ""),
            quotes=[Quote.from_dict(q) for q in d.get("quotes", [])],
        )


@dataclass
class SegmentAnalysisResult:
    """Stored in output/{source_id}/analysis/{seg_id}_quotes.json"""
    source_id: str
    source_display_name: str
    segment_id: str
    segment_name: str
    fragments: list[FragmentResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_display_name": self.source_display_name,
            "segment_id": self.segment_id,
            "segment_name": self.segment_name,
            "fragments": [f.to_dict() for f in self.fragments],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SegmentAnalysisResult":
        return cls(
            source_id=d["source_id"],
            source_display_name=d.get("source_display_name", ""),
            segment_id=d["segment_id"],
            segment_name=d.get("segment_name", ""),
            fragments=[FragmentResult.from_dict(f) for f in d.get("fragments", [])],
        )


AVAILABLE_MODELS = ["gpt-5.4-mini", "gpt-5.4-nano", "gpt-5.4"]
