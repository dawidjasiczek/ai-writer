"""Extract tab: text extraction (step 5), graphic description (step 6), placeholder fill (step 7)."""
from __future__ import annotations

import re
import threading
from pathlib import Path
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from ..state_manager import StateManager
from ..pdf_service import extract_segment_text, render_page_to_image, fill_placeholders
from ..marker_service import (
    run_marker_extraction,
    split_marker_text_into_segment,
    normalize_marker_page_markers,
    find_image_refs_for_pages,
    replace_image_refs_with_descriptions,
    strip_remaining_image_refs,
    delete_marker_images,
    get_cached_models,
    get_device_label,
)
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

            # Group selection by source to run Marker once per source
            sources_selected: dict[str, list] = {}
            for src_id, seg_id in selection:
                sources_selected.setdefault(src_id, []).append(seg_id)

            for src_id, seg_ids in sources_selected.items():
                src = self._sm.get_source(src_id)
                if src is None:
                    continue
                pdf_path = self._sm.get_source_pdf_path(src_id)
                if pdf_path is None or not pdf_path.exists():
                    errors.append(f"{src.display_name}: brak pliku PDF")
                    continue

                # Collect the actual Segment objects
                all_segs = []
                for seg_id in seg_ids:
                    if seg_id is None:
                        all_segs.extend(src.segments)
                    else:
                        seg = self._sm.get_segment(src_id, seg_id)
                        if seg:
                            all_segs.append(seg)
                # Deduplicate while preserving order
                seen_seg_ids: set[str] = set()
                segs = []
                for s in all_segs:
                    if s.id not in seen_seg_ids:
                        seen_seg_ids.add(s.id)
                        segs.append(s)

                if src.extraction_method == "marker":
                    # --- MARKER path ---
                    marker_dir = self._sm.marker_output_dir(src_id)

                    # Load (or reuse cached) models — show device label
                    self._update_progress_label(
                        f"Ładowanie modeli Marker {get_device_label()}..."
                    )
                    get_cached_models()

                    for seg in segs:
                        try:
                            self._update_progress_label(
                                f"{src.display_name} / {seg.name} {get_device_label()}"
                            )
                            # IMPORTANT: process only the selected segment pages.
                            # Marker expects 0-based page ranges.
                            page_range = f"{seg.start_page - 1}-{seg.end_page - 1}"
                            workers_count = self._sm.state.marker_workers
                            markdown_text, _ = run_marker_extraction(
                                pdf_path,
                                marker_dir,
                                workers=workers_count,
                                page_range=page_range,
                            )
                            text = split_marker_text_into_segment(
                                markdown_text,
                                seg.start_page,
                                seg.end_page,
                            )
                            # Extra safety: normalize any marker pagination
                            # delimiters that may leak through.
                            text = normalize_marker_page_markers(text)
                            if src.single_segment:
                                text = re.sub(r"\n{0,3}=== \[PAGE \d+\] ===\n{0,3}", "\n\n", text).strip() + "\n"
                            out_path = self._sm.raw_text_path(src_id, seg.id)
                            out_path.write_text(text, encoding="utf-8")
                            done += 1
                        except Exception as e:
                            errors.append(f"{src.display_name}/{seg.name}: {e}")

                else:
                    # --- pdfplumber path (unchanged) ---
                    for seg in segs:
                        try:
                            self._update_progress_label(f"{src.display_name} / {seg.name}")
                            text = extract_segment_text(
                                pdf_path, seg.start_page, seg.end_page, src.graphic_pages
                            )
                            if src.single_segment:
                                text = re.sub(r"\n{0,3}=== \[PAGE \d+\] ===\n{0,3}", "\n\n", text).strip() + "\n"
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

        self._start_progress("Opisywanie stron graficznych...")
        model = self._sm.state.default_model
        prompt = self._sm.state.prompts.graphic_description
        ai = self._ai_ref[0]

        def worker():
            errors = []
            done = 0

            # Split selection by source and method
            sources_selected: dict[str, list] = {}
            for src_id, seg_id in selection:
                sources_selected.setdefault(src_id, []).append(seg_id)

            # --- MARKER path: describe individual extracted images ---
            # --- pdfplumber path: render full pages and describe them ---

            all_futures = []

            for src_id, seg_ids in sources_selected.items():
                src = self._sm.get_source(src_id)
                if src is None:
                    continue

                # Collect segments
                all_segs = []
                for seg_id in seg_ids:
                    if seg_id is None:
                        all_segs.extend(src.segments)
                    else:
                        seg = self._sm.get_segment(src_id, seg_id)
                        if seg:
                            all_segs.append(seg)
                seen_seg_ids: set[str] = set()
                segs = []
                for s in all_segs:
                    if s.id not in seen_seg_ids:
                        seen_seg_ids.add(s.id)
                        segs.append(s)

                if src.extraction_method == "marker":
                    # Collect all image filenames that appear in raw text for graphic pages
                    marker_dir = self._sm.marker_output_dir(src_id)
                    seen_images: set[str] = set()

                    for seg in segs:
                        raw_path = self._sm.raw_text_path(src_id, seg.id)
                        if not raw_path.exists():
                            continue
                        raw_text = raw_path.read_text(encoding="utf-8")
                        img_refs = find_image_refs_for_pages(raw_text, src.graphic_pages)

                        for img_filename, page_1based in img_refs:
                            if img_filename in seen_images:
                                continue
                            seen_images.add(img_filename)

                            img_path = marker_dir / img_filename
                            if not img_path.exists():
                                errors.append(
                                    f"{src.display_name} strona {page_1based}: "
                                    f"brak pliku obrazka {img_filename}"
                                )
                                continue

                            # Description saved per-image (reuse graphic_description_path pattern)
                            desc_path = marker_dir / (img_filename + "_description.txt")

                            def _cb(
                                result: str,
                                exc,
                                _desc_path=desc_path,
                                _img_filename=img_filename,
                                _page=page_1based,
                            ):
                                nonlocal done
                                if exc:
                                    errors.append(
                                        f"AI błąd {_img_filename}: {exc}"
                                    )
                                else:
                                    _desc_path.write_text(result, encoding="utf-8")
                                    done += 1
                                self._update_progress_label(f"Opisano {done} obrazków...")

                            future = ai.describe_extracted_image(img_path, model, prompt, on_done=_cb)
                            all_futures.append(future)

                else:
                    # pdfplumber path: render whole page
                    pdf_path = self._sm.get_source_pdf_path(src_id)
                    if pdf_path is None or not pdf_path.exists():
                        errors.append(f"Brak PDF: {src_id}")
                        continue

                    seen_pages: set[tuple[str, int]] = set()
                    for seg in segs:
                        for pg in src.graphic_pages:
                            if seg.start_page <= pg <= seg.end_page:
                                key = (src_id, pg)
                                if key in seen_pages:
                                    continue
                                seen_pages.add(key)

                                img_path = self._sm.graphic_image_path(src_id, pg)
                                desc_path = self._sm.graphic_description_path(src_id, pg)

                                try:
                                    render_page_to_image(pdf_path, pg, img_path)
                                except Exception as e:
                                    errors.append(f"Błąd renderowania strony {pg}: {e}")
                                    continue

                                def _cb(
                                    result: str,
                                    exc,
                                    _src_id=src_id,
                                    _pg=pg,
                                    _desc_path=desc_path,
                                ):
                                    nonlocal done
                                    if exc:
                                        errors.append(f"AI błąd strona {_pg}: {exc}")
                                    else:
                                        _desc_path.write_text(result, encoding="utf-8")
                                        done += 1
                                    self._update_progress_label(f"Opisano {done} stron...")

                                future = ai.describe_graphic_page(img_path, model, prompt, on_done=_cb)
                                all_futures.append(future)

            if not all_futures:
                def no_work():
                    self._stop_progress()
                    messagebox.showinfo("Info", "Brak stron graficznych / obrazków w wybranych segmentach.")
                self.after(0, no_work)
                return

            total = len(all_futures)
            self._update_progress_label(f"0/{total} opisanych...")

            for fut in all_futures:
                try:
                    fut.result()
                except Exception:
                    pass

            for src_id2, _ in selection:
                self._sm.mark_graphics_described(src_id2)

            def finish():
                self._stop_progress()
                if errors:
                    messagebox.showerror("Błędy", "\n".join(errors))
                else:
                    self._set_status(f"Opisano {done} obrazków/stron graficznych.")

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

            sources_selected: dict[str, list] = {}
            for src_id, seg_id in selection:
                sources_selected.setdefault(src_id, []).append(seg_id)

            for src_id, seg_ids in sources_selected.items():
                src = self._sm.get_source(src_id)
                if src is None:
                    continue

                all_segs = []
                for seg_id in seg_ids:
                    if seg_id is None:
                        all_segs.extend(src.segments)
                    else:
                        seg = self._sm.get_segment(src_id, seg_id)
                        if seg:
                            all_segs.append(seg)
                seen_seg_ids: set[str] = set()
                segs = []
                for s in all_segs:
                    if s.id not in seen_seg_ids:
                        seen_seg_ids.add(s.id)
                        segs.append(s)

                if src.extraction_method == "marker":
                    # --- MARKER path ---
                    marker_dir = self._sm.marker_output_dir(src_id)

                    for seg in segs:
                        raw_path = self._sm.raw_text_path(src_id, seg.id)
                        if not raw_path.exists():
                            errors.append(
                                f"{src.display_name}/{seg.name}: brak wyciągniętego tekstu (uruchom krok 1)"
                            )
                            continue
                        try:
                            raw_text = raw_path.read_text(encoding="utf-8")

                            # Build descriptions map: image_filename -> description
                            img_refs = find_image_refs_for_pages(raw_text, src.graphic_pages)
                            descriptions: dict[str, str] = {}
                            for img_filename, _ in img_refs:
                                desc_path = marker_dir / (img_filename + "_description.txt")
                                if desc_path.exists():
                                    descriptions[img_filename] = desc_path.read_text(encoding="utf-8")

                            # Replace described images, strip the rest
                            filled = replace_image_refs_with_descriptions(raw_text, descriptions)
                            filled = strip_remaining_image_refs(filled)

                            out_path = self._sm.full_text_path(src_id, seg.id)
                            out_path.write_text(filled, encoding="utf-8")
                            done += 1

                            # Clean up: delete all image files referenced in this segment
                            all_filenames = re.findall(
                                r"!\[\]\((_page_\d+_[^)]+\.jpe?g)\)", raw_text
                            )
                            delete_marker_images(marker_dir, all_filenames)

                        except Exception as e:
                            errors.append(f"{src.display_name}/{seg.name}: {e}")

                    self._sm.mark_placeholders_filled(src_id)

                else:
                    # --- pdfplumber path (unchanged) ---
                    descriptions_plumber: dict[int, str] = {}
                    for pg in src.graphic_pages:
                        desc_path = self._sm.graphic_description_path(src_id, pg)
                        if desc_path.exists():
                            descriptions_plumber[pg] = desc_path.read_text(encoding="utf-8")

                    for seg in segs:
                        raw_path = self._sm.raw_text_path(src_id, seg.id)
                        if not raw_path.exists():
                            errors.append(
                                f"{src.display_name}/{seg.name}: brak wyciągniętego tekstu (uruchom krok 1)"
                            )
                            continue
                        try:
                            raw_text = raw_path.read_text(encoding="utf-8")
                            filled = fill_placeholders(raw_text, descriptions_plumber)
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
