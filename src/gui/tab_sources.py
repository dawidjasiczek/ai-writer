"""Sources tab: manage source files, rename, segments, graphic pages."""
from __future__ import annotations

import shutil
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable, Optional

import customtkinter as ctk

try:
    import fitz  # PyMuPDF
    from PIL import Image, ImageTk
    _PDF_PREVIEW_AVAILABLE = True
except ImportError:
    _PDF_PREVIEW_AVAILABLE = False

from ..models import Source, Segment
from ..state_manager import StateManager
from ..pdf_service import get_pdf_page_count


class SourcesTab(ctk.CTkFrame):
    def __init__(self, master, state_manager: StateManager, refresh_callback: Callable, **kwargs):
        super().__init__(master, **kwargs)
        self._sm = state_manager
        self._refresh_cb = refresh_callback
        self._selected_source_id: Optional[str] = None
        self._selected_seg_id: Optional[str] = None
        self._build()
        self._refresh_source_list()

    # ------------------------------------------------------------------
    # Build layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.columnconfigure(0, weight=0, minsize=220)
        self.columnconfigure(1, weight=1, minsize=340)
        self.columnconfigure(2, weight=2, minsize=300)
        self.rowconfigure(0, weight=1)

        # ── col 0: source list ───────────────────────────────────────
        left = ctk.CTkFrame(self, width=220)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Pliki źródłowe", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4)
        )

        self._source_list = ctk.CTkScrollableFrame(left)
        self._source_list.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=4, pady=4)

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=4, pady=4)
        ctk.CTkButton(btn_row, text="Dodaj PDF", command=self._add_pdf, width=110).pack(
            side="left", padx=2
        )
        ctk.CTkButton(
            btn_row, text="Usuń", command=self._remove_source, width=80, fg_color="#c0392b"
        ).pack(side="left", padx=2)

        # ── col 1: details panel ─────────────────────────────────────
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 4), pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(5, weight=1)

        self._detail_frame = right
        ctk.CTkLabel(right, text="Szczegóły pliku", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 4)
        )

        # Rename row
        rename_row = ctk.CTkFrame(right, fg_color="transparent")
        rename_row.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(rename_row, text="Nazwa wyświetlana:").pack(side="left", padx=(0, 6))
        self._display_name_entry = ctk.CTkEntry(rename_row, width=220)
        self._display_name_entry.pack(side="left", padx=4)
        ctk.CTkButton(rename_row, text="Zapisz nazwę", command=self._save_display_name, width=110).pack(
            side="left", padx=4
        )

        # Graphic pages row
        graphic_row = ctk.CTkFrame(right, fg_color="transparent")
        graphic_row.grid(row=2, column=0, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(graphic_row, text="Strony graficzne (np. 3,7,15):").pack(
            side="left", padx=(0, 6)
        )
        self._graphic_pages_entry = ctk.CTkEntry(graphic_row, width=160)
        self._graphic_pages_entry.pack(side="left", padx=4)
        ctk.CTkButton(
            graphic_row, text="Zapisz", command=self._save_graphic_pages, width=80
        ).pack(side="left", padx=4)

        # Page numbering start row
        page_num_row = ctk.CTkFrame(right, fg_color="transparent")
        page_num_row.grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(page_num_row, text="Numeracja stron od strony PDF:").pack(
            side="left", padx=(0, 6)
        )
        self._page_numbering_start_entry = ctk.CTkEntry(page_num_row, width=90)
        self._page_numbering_start_entry.pack(side="left", padx=4)
        ctk.CTkButton(
            page_num_row, text="Zapisz", command=self._save_page_numbering_start, width=80
        ).pack(side="left", padx=4)

        # Extraction method row
        method_row = ctk.CTkFrame(right, fg_color="transparent")
        method_row.grid(row=4, column=0, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(method_row, text="Metoda ekstrakcji:").pack(side="left", padx=(0, 6))
        self._extraction_method_btn = ctk.CTkSegmentedButton(
            method_row,
            values=["pdfplumber", "marker"],
            command=self._save_extraction_method,
            width=200,
        )
        self._extraction_method_btn.set("pdfplumber")
        self._extraction_method_btn.pack(side="left", padx=4)
        ctk.CTkLabel(
            method_row,
            text="(marker = lepsza jakość + wyciąga obrazki)",
            text_color=("gray50", "gray60"),
            font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=6)

        single_seg_row = ctk.CTkFrame(right, fg_color="transparent")
        single_seg_row.grid(row=5, column=0, sticky="ew", padx=8, pady=2)
        self._single_segment_var = ctk.BooleanVar(value=False)
        self._single_segment_chk = ctk.CTkCheckBox(
            single_seg_row,
            text="Całe źródło jako jeden segment (bez podziału na strony)",
            variable=self._single_segment_var,
            command=self._on_single_segment_toggle,
        )
        self._single_segment_chk.pack(side="left", padx=(0, 4))

        # Segments section
        seg_frame = ctk.CTkFrame(right)
        seg_frame.grid(row=6, column=0, sticky="nsew", padx=8, pady=(4, 8))
        seg_frame.columnconfigure(0, weight=1)
        seg_frame.rowconfigure(1, weight=1)

        seg_header = ctk.CTkFrame(seg_frame, fg_color="transparent")
        seg_header.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ctk.CTkLabel(seg_header, text="Segmenty", font=ctk.CTkFont(weight="bold")).pack(
            side="left"
        )
        self._add_seg_btn = ctk.CTkButton(
            seg_header, text="+ Dodaj segment", command=self._add_segment, width=130
        )
        self._add_seg_btn.pack(
            side="right"
        )

        self._seg_list = ctk.CTkScrollableFrame(seg_frame, height=200)
        self._seg_list.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        # Segment editor
        self._seg_editor = SegmentEditor(seg_frame, on_save=self._save_segment, on_delete=self._delete_segment)
        self._seg_editor.grid(row=2, column=0, sticky="ew", padx=4, pady=4)

        # ── col 2: PDF viewer ────────────────────────────────────────
        self._pdf_viewer = PDFViewer(self)
        self._pdf_viewer.grid(row=0, column=2, sticky="nsew", padx=(4, 8), pady=8)

    # ------------------------------------------------------------------
    # Source list management
    # ------------------------------------------------------------------

    def _refresh_source_list(self) -> None:
        for w in self._source_list.winfo_children():
            w.destroy()
        for src in self._sm.state.sources:
            btn = ctk.CTkButton(
                self._source_list,
                text=src.display_name,
                anchor="w",
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("lightblue", "#2a5080"),
                command=lambda s=src: self._select_source(s.id),
            )
            btn.pack(fill="x", padx=2, pady=1)

    def _add_pdf(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Wybierz pliki PDF",
            filetypes=[("PDF", "*.pdf"), ("Wszystkie", "*.*")],
        )
        for path_str in paths:
            src_path = Path(path_str)
            dest = self._sm.project_dir / "sources" / src_path.name
            if not dest.exists():
                shutil.copy2(src_path, dest)
            # Don't add duplicate filename
            if not any(s.filename == src_path.name for s in self._sm.state.sources):
                self._sm.add_source(src_path.name, src_path.stem)
        self._refresh_source_list()
        self._refresh_cb()

    def _remove_source(self) -> None:
        if not self._selected_source_id:
            messagebox.showinfo("Info", "Wybierz najpierw źródło.")
            return
        if messagebox.askyesno("Potwierdź", "Usunąć to źródło?"):
            self._sm.remove_source(self._selected_source_id)
            self._selected_source_id = None
            self._refresh_source_list()
            self._clear_details()
            self._refresh_cb()

    def _select_source(self, source_id: str) -> None:
        self._selected_source_id = source_id
        self._selected_seg_id = None
        src = self._sm.get_source(source_id)
        if src is None:
            return
        self._display_name_entry.delete(0, "end")
        self._display_name_entry.insert(0, src.display_name)
        self._graphic_pages_entry.delete(0, "end")
        self._graphic_pages_entry.insert(0, ", ".join(str(p) for p in src.graphic_pages))
        self._page_numbering_start_entry.delete(0, "end")
        self._page_numbering_start_entry.insert(0, str(src.page_numbering_start_pdf_page))
        self._extraction_method_btn.set(src.extraction_method)
        self._single_segment_var.set(src.single_segment)
        self._set_single_segment_ui_state(src.single_segment)
        self._seg_editor.clear()
        self._refresh_seg_list(src)
        # Load PDF in viewer
        pdf_path = self._sm.project_dir / "sources" / src.filename
        if pdf_path.exists():
            self._pdf_viewer.load_pdf(pdf_path)
        else:
            self._pdf_viewer.clear()

    def _clear_details(self) -> None:
        self._display_name_entry.delete(0, "end")
        self._graphic_pages_entry.delete(0, "end")
        self._page_numbering_start_entry.delete(0, "end")
        self._page_numbering_start_entry.insert(0, "1")
        self._extraction_method_btn.set("pdfplumber")
        self._single_segment_var.set(False)
        self._set_single_segment_ui_state(False)
        for w in self._seg_list.winfo_children():
            w.destroy()
        self._seg_editor.clear()

    def _save_display_name(self) -> None:
        if not self._selected_source_id:
            return
        name = self._display_name_entry.get().strip()
        if name:
            self._sm.rename_source(self._selected_source_id, name)
            self._refresh_source_list()
            self._refresh_cb()

    def _save_extraction_method(self, method: str) -> None:
        if not self._selected_source_id:
            return
        self._sm.set_extraction_method(self._selected_source_id, method)

    def _save_graphic_pages(self) -> None:
        if not self._selected_source_id:
            return
        raw = self._graphic_pages_entry.get().strip()
        pages: list[int] = []
        if raw:
            try:
                pages = [int(x.strip()) for x in raw.replace(";", ",").split(",") if x.strip()]
            except ValueError:
                messagebox.showerror("Błąd", "Podaj numery stron oddzielone przecinkami.")
                return
        self._sm.set_graphic_pages(self._selected_source_id, pages)

    def _save_page_numbering_start(self) -> None:
        if not self._selected_source_id:
            return
        raw = self._page_numbering_start_entry.get().strip()
        try:
            value = int(raw) if raw else 1
        except ValueError:
            messagebox.showerror("Błąd", "Podaj liczbę całkowitą >= 1.")
            return
        if value < 1:
            messagebox.showerror("Błąd", "Wartość musi być >= 1.")
            return
        self._sm.set_page_numbering_start_pdf_page(self._selected_source_id, value)

    def _set_single_segment_ui_state(self, enabled: bool) -> None:
        state = "disabled" if enabled else "normal"
        self._add_seg_btn.configure(state=state)
        self._seg_editor.set_enabled(not enabled)

    def _on_single_segment_toggle(self) -> None:
        if not self._selected_source_id:
            return
        src = self._sm.get_source(self._selected_source_id)
        if src is None:
            return

        enabled = bool(self._single_segment_var.get())

        if enabled:
            pdf_path = self._sm.get_source_pdf_path(src.id)
            if pdf_path is None or not pdf_path.exists():
                messagebox.showerror("Błąd", "Brak pliku PDF dla wybranego źródła.")
                self._single_segment_var.set(False)
                self._set_single_segment_ui_state(False)
                return
            try:
                total_pages = get_pdf_page_count(pdf_path)
            except Exception as e:
                messagebox.showerror("Błąd", f"Nie udało się odczytać liczby stron PDF: {e}")
                self._single_segment_var.set(False)
                self._set_single_segment_ui_state(False)
                return
            if total_pages <= 0:
                messagebox.showerror("Błąd", "PDF nie zawiera żadnych stron.")
                self._single_segment_var.set(False)
                self._set_single_segment_ui_state(False)
                return

            src.segments = []
            self._sm.add_segment(src.id, "Całe źródło", 1, total_pages)
            self._sm.set_single_segment(src.id, True)
            src = self._sm.get_source(src.id) or src
            self._selected_seg_id = None
            self._seg_editor.clear()
            self._refresh_seg_list(src)
            self._refresh_cb()
        else:
            self._sm.set_single_segment(src.id, False)
            self._refresh_cb()

        self._set_single_segment_ui_state(enabled)

    # ------------------------------------------------------------------
    # Segment management
    # ------------------------------------------------------------------

    def _refresh_seg_list(self, src: Source) -> None:
        for w in self._seg_list.winfo_children():
            w.destroy()
        for seg in src.segments:
            row = ctk.CTkFrame(self._seg_list, fg_color="transparent")
            row.pack(fill="x", padx=2, pady=1)
            ctk.CTkButton(
                row,
                text=f"{seg.name}  (s. {seg.start_page}–{seg.end_page})",
                anchor="w",
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("lightblue", "#2a5080"),
                command=lambda s=seg: self._select_segment(s.id),
            ).pack(fill="x")

    def _add_segment(self) -> None:
        if not self._selected_source_id:
            messagebox.showinfo("Info", "Wybierz najpierw źródło.")
            return
        self._selected_seg_id = None
        self._seg_editor.edit(segment=None)

    def _select_segment(self, seg_id: str) -> None:
        self._selected_seg_id = seg_id
        if not self._selected_source_id:
            return
        seg = self._sm.get_segment(self._selected_source_id, seg_id)
        if seg:
            self._seg_editor.edit(segment=seg)
            self._pdf_viewer.goto_page(seg.start_page)

    def _save_segment(self, name: str, start: int, end: int) -> None:
        if not self._selected_source_id:
            return
        if self._selected_seg_id:
            self._sm.update_segment(self._selected_source_id, self._selected_seg_id, name, start, end)
        else:
            self._sm.add_segment(self._selected_source_id, name, start, end)
        # Always reset to "new segment" mode after saving
        self._selected_seg_id = None
        self._seg_editor.edit(segment=None)
        src = self._sm.get_source(self._selected_source_id)
        if src:
            self._refresh_seg_list(src)
        self._refresh_cb()

    def _delete_segment(self) -> None:
        if not self._selected_source_id or not self._selected_seg_id:
            return
        if messagebox.askyesno("Potwierdź", "Usunąć ten segment?"):
            self._sm.remove_segment(self._selected_source_id, self._selected_seg_id)
            self._selected_seg_id = None
            self._seg_editor.clear()
            src = self._sm.get_source(self._selected_source_id)
            if src:
                self._refresh_seg_list(src)
            self._refresh_cb()


class PDFViewer(ctk.CTkFrame):
    """Renders PDF pages one at a time using PyMuPDF."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._doc: "fitz.Document | None" = None
        self._page_idx: int = 0  # 0-based
        self._total_pages: int = 0
        self._photo = None  # keep reference to avoid GC
        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Controls strip
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))

        self._prev_btn = ctk.CTkButton(ctrl, text="◀", width=32, command=self._prev)
        self._prev_btn.pack(side="left", padx=2)

        self._page_label = ctk.CTkLabel(ctrl, text="–", width=90)
        self._page_label.pack(side="left", padx=4)

        self._next_btn = ctk.CTkButton(ctrl, text="▶", width=32, command=self._next)
        self._next_btn.pack(side="left", padx=2)

        self._page_entry = ctk.CTkEntry(ctrl, width=56, placeholder_text="str.")
        self._page_entry.pack(side="left", padx=(10, 2))
        self._page_entry.bind("<Return>", self._jump_to_entered)

        # Canvas + scrollbar
        canvas_frame = ctk.CTkFrame(self, fg_color="transparent")
        canvas_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 4))
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        self._canvas = tk.Canvas(canvas_frame, bg="#1a1a2e", highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self._canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.bind("<Configure>", lambda _: self._render())

        self._placeholder_label = ctk.CTkLabel(
            self._canvas,
            text="Wybierz źródło,\naby zobaczyć podgląd PDF",
            text_color=("gray60", "gray50"),
        )
        self._canvas.create_window(0, 0, window=self._placeholder_label, anchor="nw", tags="placeholder")

        self._set_controls_state("disabled")

    def load_pdf(self, pdf_path: Path) -> None:
        if not _PDF_PREVIEW_AVAILABLE:
            return
        if self._doc is not None:
            self._doc.close()
            self._doc = None
        self._doc = fitz.open(str(pdf_path))
        self._total_pages = len(self._doc)
        self._page_idx = 0
        self._set_controls_state("normal")
        self._render()

    def goto_page(self, page_num: int) -> None:
        """Jump to a 1-based page number."""
        if self._doc is None:
            return
        idx = max(0, min(page_num - 1, self._total_pages - 1))
        self._page_idx = idx
        self._render()

    def clear(self) -> None:
        if self._doc is not None:
            self._doc.close()
            self._doc = None
        self._total_pages = 0
        self._page_idx = 0
        self._photo = None
        self._canvas.delete("page")
        self._set_controls_state("disabled")
        self._page_label.configure(text="–")
        # Show placeholder
        self._canvas.itemconfigure("placeholder", state="normal")

    def _render(self) -> None:
        if not _PDF_PREVIEW_AVAILABLE or self._doc is None:
            return
        self._canvas.itemconfigure("placeholder", state="hidden")
        w = self._canvas.winfo_width()
        if w < 10:
            w = 400

        page = self._doc[self._page_idx]
        zoom = w / page.rect.width
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self._photo = ImageTk.PhotoImage(img)

        self._canvas.delete("page")
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo, tags="page")
        self._canvas.configure(scrollregion=(0, 0, pix.width, pix.height))
        self._canvas.yview_moveto(0)

        self._page_label.configure(text=f"{self._page_idx + 1} / {self._total_pages}")

    def _prev(self) -> None:
        if self._doc is None or self._page_idx <= 0:
            return
        self._page_idx -= 1
        self._render()

    def _next(self) -> None:
        if self._doc is None or self._page_idx >= self._total_pages - 1:
            return
        self._page_idx += 1
        self._render()

    def _jump_to_entered(self, _event=None) -> None:
        try:
            num = int(self._page_entry.get().strip())
        except ValueError:
            return
        self._page_entry.delete(0, "end")
        self.goto_page(num)

    def _set_controls_state(self, state: str) -> None:
        self._prev_btn.configure(state=state)
        self._next_btn.configure(state=state)
        self._page_entry.configure(state=state)


class SegmentEditor(ctk.CTkFrame):
    """Inline editor for a single segment."""

    def __init__(self, master, on_save: Callable, on_delete: Callable, **kwargs):
        super().__init__(master, **kwargs)
        self._on_save = on_save
        self._on_delete = on_delete
        self._build()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="Nazwa segmentu:").grid(
            row=0, column=0, sticky="e", padx=(6, 4), pady=4
        )
        self._name = ctk.CTkEntry(self, placeholder_text="np. Rozdział 1 – Wstęp")
        self._name.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(0, 6), pady=4)

        ctk.CTkLabel(self, text="Strona od:").grid(row=1, column=0, sticky="e", padx=(6, 4), pady=4)
        self._start = ctk.CTkEntry(self, width=70)
        self._start.grid(row=1, column=1, sticky="w", padx=(0, 8), pady=4)

        ctk.CTkLabel(self, text="do:").grid(row=1, column=2, sticky="e", padx=(0, 4), pady=4)
        self._end = ctk.CTkEntry(self, width=70)
        self._end.grid(row=1, column=3, sticky="w", padx=(0, 6), pady=4)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=4, pady=4)
        self._save_btn = ctk.CTkButton(btn_row, text="Zapisz segment", command=self._save, width=130)
        self._save_btn.pack(side="left", padx=4)
        self._del_btn = ctk.CTkButton(
            btn_row, text="Usuń", command=self._on_delete, width=80, fg_color="#c0392b"
        )
        self._del_btn.pack(side="left", padx=4)

    def edit(self, segment: Optional[Segment]) -> None:
        self._name.delete(0, "end")
        self._start.delete(0, "end")
        self._end.delete(0, "end")
        if segment:
            self._name.insert(0, segment.name)
            self._start.insert(0, str(segment.start_page))
            self._end.insert(0, str(segment.end_page))
            self._del_btn.configure(state="normal")
        else:
            self._del_btn.configure(state="disabled")

    def clear(self) -> None:
        self._name.delete(0, "end")
        self._start.delete(0, "end")
        self._end.delete(0, "end")
        self._del_btn.configure(state="disabled")

    def set_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        self._name.configure(state=state)
        self._start.configure(state=state)
        self._end.configure(state=state)
        self._save_btn.configure(state=state)
        if not enabled:
            self._del_btn.configure(state="disabled")
        elif self._name.get().strip():
            self._del_btn.configure(state="normal")

    def _save(self) -> None:
        name = self._name.get().strip()
        try:
            start = int(self._start.get().strip())
            end = int(self._end.get().strip())
        except ValueError:
            messagebox.showerror("Błąd", "Strony muszą być liczbami.")
            return
        if not name:
            messagebox.showerror("Błąd", "Podaj nazwę segmentu.")
            return
        if start > end:
            messagebox.showerror("Błąd", "Strona od musi być <= strona do.")
            return
        self._on_save(name, start, end)
