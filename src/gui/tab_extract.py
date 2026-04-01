"""Extract tab: text extraction (step 5), graphic description (step 6), placeholder fill (step 7)."""
from __future__ import annotations

import threading
from pathlib import Path
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from ..state_manager import StateManager
from ..pdf_service import extract_segment_text, render_page_to_image, fill_placeholders
from ..ai_service import AIService
from .components import SegmentSelector, StatusBar


class ExtractTab(ctk.CTkFrame):
    def __init__(self, master, state_manager: StateManager, ai_service_ref: list, **kwargs):
        super().__init__(master, **kwargs)
        self._sm = state_manager
        self._ai_ref = ai_service_ref
        self._status_bar: Optional[StatusBar] = None
        self._running = False
        self._build()

    def set_status_bar(self, bar: StatusBar) -> None:
        self._status_bar = bar

    def _set_status(self, msg: str) -> None:
        if self._status_bar:
            self._status_bar.set(msg)

    def refresh(self) -> None:
        self._selector.refresh()

    def _build(self) -> None:
        self.columnconfigure(0, weight=0, minsize=280)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Left: selector
        left = ctk.CTkFrame(self, width=280)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Wybierz segmenty", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 2)
        )
        self._selector = SegmentSelector(left, self._sm, height=300)
        self._selector.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        btn_sel = ctk.CTkFrame(left, fg_color="transparent")
        btn_sel.grid(row=2, column=0, sticky="ew", padx=4)
        ctk.CTkButton(btn_sel, text="Wszystkie", command=self._selector.select_all, width=100).pack(
            side="left", padx=2, pady=4
        )
        ctk.CTkButton(btn_sel, text="Żadne", command=self._selector.deselect_all, width=80).pack(
            side="left", padx=2, pady=4
        )

        # Action buttons
        btns = ctk.CTkFrame(left, fg_color="transparent")
        btns.grid(row=3, column=0, sticky="ew", padx=4, pady=8)

        ctk.CTkButton(
            btns, text="1. Wyciągnij tekst", command=self._run_extract_text, height=36
        ).pack(fill="x", padx=4, pady=3)
        ctk.CTkButton(
            btns, text="2. Opisz strony graficzne", command=self._run_describe_graphics, height=36
        ).pack(fill="x", padx=4, pady=3)
        ctk.CTkButton(
            btns, text="3. Wypełnij placeholdery", command=self._run_fill_placeholders, height=36
        ).pack(fill="x", padx=4, pady=3)

        # Progress
        self._progress = ctk.CTkProgressBar(left, mode="indeterminate")
        self._progress.grid(row=4, column=0, sticky="ew", padx=8, pady=4)
        self._progress_label = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11))
        self._progress_label.grid(row=5, column=0, padx=8)

        # Right: preview
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        preview_header = ctk.CTkFrame(right, fg_color="transparent")
        preview_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        ctk.CTkLabel(preview_header, text="Podgląd:", font=ctk.CTkFont(weight="bold")).pack(
            side="left", padx=(0, 6)
        )

        self._preview_segment_combo = ctk.CTkComboBox(
            preview_header, values=["–"], command=self._load_preview, width=280
        )
        self._preview_segment_combo.pack(side="left", padx=4)

        self._preview_mode = ctk.CTkSegmentedButton(
            preview_header, values=["RAW", "FULL"], command=self._load_preview, width=120
        )
        self._preview_mode.set("RAW")
        self._preview_mode.pack(side="left", padx=4)

        ctk.CTkButton(preview_header, text="Odśwież", command=self._refresh_preview_list, width=80).pack(
            side="left", padx=4
        )

        self._preview_text = ctk.CTkTextbox(right, wrap="word", font=ctk.CTkFont(family="Courier", size=11))
        self._preview_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

    # ------------------------------------------------------------------
    # Step 1: Extract text
    # ------------------------------------------------------------------

    def _run_extract_text(self) -> None:
        selection = self._selector.get_selection()
        if not selection:
            messagebox.showinfo("Info", "Wybierz co najmniej jeden segment.")
            return
        self._start_progress("Wyciąganie tekstu...")

        def worker():
            errors = []
            done = 0
            for src_id, seg_id in selection:
                src = self._sm.get_source(src_id)
                if src is None:
                    continue
                pdf_path = self._sm.get_source_pdf_path(src_id)
                if pdf_path is None or not pdf_path.exists():
                    errors.append(f"{src.display_name}: brak pliku PDF")
                    continue

                segs = src.segments if seg_id is None else [self._sm.get_segment(src_id, seg_id)]
                segs = [s for s in segs if s is not None]

                for seg in segs:
                    try:
                        self._update_progress_label(f"{src.display_name} / {seg.name}")
                        text = extract_segment_text(
                            pdf_path, seg.start_page, seg.end_page, src.graphic_pages
                        )
                        out_path = self._sm.raw_text_path(src_id, seg.id)
                        out_path.write_text(text, encoding="utf-8")
                        done += 1
                    except Exception as e:
                        errors.append(f"{src.display_name}/{seg.name}: {e}")

            if any(s.processing_status.text_extracted is False for s in self._sm.state.sources):
                for src_id2, _ in selection:
                    self._sm.mark_text_extracted(src_id2)

            def finish():
                self._stop_progress()
                if errors:
                    messagebox.showerror("Błędy", "\n".join(errors))
                else:
                    self._set_status(f"Wyciągnięto tekst z {done} segmentów.")
                self._refresh_preview_list()

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Step 2: Describe graphic pages
    # ------------------------------------------------------------------

    def _run_describe_graphics(self) -> None:
        selection = self._selector.get_selection()
        if not selection:
            messagebox.showinfo("Info", "Wybierz co najmniej jeden segment / plik.")
            return

        # Collect unique (source_id, page_num) pairs
        pages_to_describe: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for src_id, seg_id in selection:
            src = self._sm.get_source(src_id)
            if src is None:
                continue
            segs = src.segments if seg_id is None else [self._sm.get_segment(src_id, seg_id)]
            segs = [s for s in segs if s is not None]
            for seg in segs:
                for pg in src.graphic_pages:
                    if seg.start_page <= pg <= seg.end_page:
                        key = (src_id, pg)
                        if key not in seen:
                            seen.add(key)
                            pages_to_describe.append(key)

        if not pages_to_describe:
            messagebox.showinfo("Info", "Brak stron graficznych w wybranych segmentach.")
            return

        self._start_progress("Opisywanie stron graficznych...")
        model = self._sm.state.default_model
        prompt = self._sm.state.prompts.graphic_description

        def worker():
            errors = []
            done = 0
            total = len(pages_to_describe)

            import concurrent.futures
            futures = []
            ai = self._ai_ref[0]

            for src_id, page_num in pages_to_describe:
                src = self._sm.get_source(src_id)
                pdf_path = self._sm.get_source_pdf_path(src_id)
                if pdf_path is None or not pdf_path.exists():
                    errors.append(f"Brak PDF: {src_id}")
                    continue

                img_path = self._sm.graphic_image_path(src_id, page_num)
                desc_path = self._sm.graphic_description_path(src_id, page_num)

                try:
                    render_page_to_image(pdf_path, page_num, img_path)
                except Exception as e:
                    errors.append(f"Błąd renderowania strony {page_num}: {e}")
                    continue

                def _cb(result: str, exc, _src_id=src_id, _pg=page_num, _desc_path=desc_path):
                    nonlocal done
                    if exc:
                        errors.append(f"AI błąd strona {_pg}: {exc}")
                    else:
                        _desc_path.write_text(result, encoding="utf-8")
                        done += 1
                    self._update_progress_label(f"{done}/{total} stron opisanych")

                future = ai.describe_graphic_page(img_path, model, prompt, on_done=_cb)
                futures.append(future)

            # Wait for all
            for fut in futures:
                try:
                    fut.result()
                except Exception:
                    pass

            # Mark status
            for src_id2, _ in selection:
                self._sm.mark_graphics_described(src_id2)

            def finish():
                self._stop_progress()
                if errors:
                    messagebox.showerror("Błędy", "\n".join(errors))
                else:
                    self._set_status(f"Opisano {done} stron graficznych.")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Step 3: Fill placeholders
    # ------------------------------------------------------------------

    def _run_fill_placeholders(self) -> None:
        selection = self._selector.get_selection()
        if not selection:
            messagebox.showinfo("Info", "Wybierz co najmniej jeden segment.")
            return
        self._start_progress("Wypełnianie placeholderów...")

        def worker():
            errors = []
            done = 0
            for src_id, seg_id in selection:
                src = self._sm.get_source(src_id)
                if src is None:
                    continue

                segs = src.segments if seg_id is None else [self._sm.get_segment(src_id, seg_id)]
                segs = [s for s in segs if s is not None]

                # Load descriptions for this source
                descriptions: dict[int, str] = {}
                for pg in src.graphic_pages:
                    desc_path = self._sm.graphic_description_path(src_id, pg)
                    if desc_path.exists():
                        descriptions[pg] = desc_path.read_text(encoding="utf-8")

                for seg in segs:
                    raw_path = self._sm.raw_text_path(src_id, seg.id)
                    if not raw_path.exists():
                        errors.append(
                            f"{src.display_name}/{seg.name}: brak wyciągniętego tekstu (uruchom krok 1)"
                        )
                        continue
                    try:
                        raw_text = raw_path.read_text(encoding="utf-8")
                        filled = fill_placeholders(raw_text, descriptions)
                        out_path = self._sm.full_text_path(src_id, seg.id)
                        out_path.write_text(filled, encoding="utf-8")
                        done += 1
                    except Exception as e:
                        errors.append(f"{src.display_name}/{seg.name}: {e}")

                self._sm.mark_placeholders_filled(src_id)

            def finish():
                self._stop_progress()
                if errors:
                    messagebox.showerror("Błędy", "\n".join(errors))
                else:
                    self._set_status(f"Wypełniono placeholdery w {done} segmentach.")
                self._refresh_preview_list()

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _refresh_preview_list(self) -> None:
        options = []
        for src in self._sm.state.sources:
            for seg in src.segments:
                raw = self._sm.raw_text_path(src.id, seg.id)
                full = self._sm.full_text_path(src.id, seg.id)
                if raw.exists() or full.exists():
                    options.append(f"{src.display_name} / {seg.name}")
        self._preview_segment_combo.configure(values=options if options else ["–"])
        if options:
            self._preview_segment_combo.set(options[0])
            self._load_preview(options[0])

    def _load_preview(self, value: str = None) -> None:
        value = value or self._preview_segment_combo.get()
        mode = self._preview_mode.get()
        if not value or value == "–":
            return
        parts = value.split(" / ", 1)
        if len(parts) != 2:
            return
        display_name, seg_name = parts
        for src in self._sm.state.sources:
            if src.display_name == display_name:
                for seg in src.segments:
                    if seg.name == seg_name:
                        if mode == "FULL":
                            path = self._sm.full_text_path(src.id, seg.id)
                            if not path.exists():
                                path = self._sm.raw_text_path(src.id, seg.id)
                        else:
                            path = self._sm.raw_text_path(src.id, seg.id)
                        if path.exists():
                            content = path.read_text(encoding="utf-8")
                            self._preview_text.delete("1.0", "end")
                            self._preview_text.insert("1.0", content)
                        return

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _start_progress(self, msg: str) -> None:
        self._running = True
        self._progress.start()
        self._update_progress_label(msg)
        self._set_status(msg)

    def _stop_progress(self) -> None:
        self._running = False
        self._progress.stop()
        self._progress_label.configure(text="")

    def _update_progress_label(self, msg: str) -> None:
        self.after(0, lambda: self._progress_label.configure(text=msg))
