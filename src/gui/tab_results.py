"""Results tab: browse results, aggregate, export (step 10).

Two view modes:
- Po pytaniu  : pick a question, filter source/segment checkboxes
- Po segmencie: pick source + segment, shows all questions answered for it
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Optional

import customtkinter as ctk

from ..state_manager import StateManager


class ResultsTab(ctk.CTkFrame):
    def __init__(self, master, state_manager: StateManager, **kwargs):
        super().__init__(master, **kwargs)
        self._sm = state_manager
        self._current_question_id: Optional[int] = None
        self._filter_vars: dict[str, ctk.BooleanVar] = {}
        self._skip_empty_var = ctk.BooleanVar(value=True)
        self._split_segments_var = ctk.BooleanVar(value=False)
        self._build()

    def refresh(self) -> None:
        self._reload_questions_combo()
        self._reload_segment_combos()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build(self) -> None:
        self.columnconfigure(0, weight=0, minsize=270)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Left: controls
        left = ctk.CTkFrame(self, width=270)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(5, weight=1)

        # View mode switch
        ctk.CTkLabel(left, text="Widok:", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 2)
        )
        self._view_mode = ctk.CTkSegmentedButton(
            left,
            values=["Po pytaniu", "Po segmencie"],
            command=self._on_view_mode_change,
        )
        self._view_mode.set("Po pytaniu")
        self._view_mode.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        # ---- "Po pytaniu" controls ----
        self._by_q_frame = ctk.CTkFrame(left, fg_color="transparent")
        self._by_q_frame.columnconfigure(0, weight=1)
        self._by_q_frame.rowconfigure(1, weight=1)
        self._by_q_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)

        ctk.CTkLabel(self._by_q_frame, text="Pytanie:").grid(
            row=0, column=0, sticky="w", padx=10, pady=(0, 2)
        )
        self._q_combo = ctk.CTkComboBox(
            self._by_q_frame, values=["–"], command=self._on_question_change, width=240
        )
        self._q_combo.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))

        self._skip_empty_cb = ctk.CTkCheckBox(
            self._by_q_frame,
            text="Pomiń puste wyniki",
            variable=self._skip_empty_var,
            command=self._on_question_options_change,
        )
        self._skip_empty_cb.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 2))
        self._split_segments_cb = ctk.CTkCheckBox(
            self._by_q_frame,
            text="Rozdzielaj na segmenty",
            variable=self._split_segments_var,
            command=self._on_question_options_change,
        )
        self._split_segments_cb.grid(row=3, column=0, sticky="w", padx=10, pady=(0, 4))

        ctk.CTkLabel(
            self._by_q_frame, text="Źródła / segmenty:", font=ctk.CTkFont(weight="bold")
        ).grid(row=4, column=0, sticky="w", padx=10, pady=(6, 2))

        self._filter_frame = ctk.CTkScrollableFrame(self._by_q_frame, height=220)
        self._filter_frame.grid(row=5, column=0, sticky="nsew", padx=4, pady=4)
        self._by_q_frame.rowconfigure(5, weight=1)

        filter_btns = ctk.CTkFrame(self._by_q_frame, fg_color="transparent")
        filter_btns.grid(row=6, column=0, sticky="ew", padx=4, pady=2)
        ctk.CTkButton(filter_btns, text="Wszystkie", command=self._select_all_filters, width=100).pack(
            side="left", padx=2
        )
        ctk.CTkButton(filter_btns, text="Żadne", command=self._deselect_all_filters, width=80).pack(
            side="left", padx=2
        )

        # ---- "Po segmencie" controls ----
        self._by_seg_frame = ctk.CTkFrame(left, fg_color="transparent")
        self._by_seg_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(self._by_seg_frame, text="Źródło:").grid(
            row=0, column=0, sticky="w", padx=10, pady=(0, 2)
        )
        self._src_combo = ctk.CTkComboBox(
            self._by_seg_frame, values=["–"], command=self._on_src_change, width=240
        )
        self._src_combo.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 6))

        ctk.CTkLabel(self._by_seg_frame, text="Segment:").grid(
            row=2, column=0, sticky="w", padx=10, pady=(0, 2)
        )
        self._seg_combo = ctk.CTkComboBox(
            self._by_seg_frame, values=["–"], command=lambda _: None, width=240
        )
        self._seg_combo.grid(row=3, column=0, sticky="ew", padx=8, pady=(0, 4))

        # Shared action buttons (below whichever frame is shown)
        btn_frame = ctk.CTkFrame(left, fg_color="transparent")
        btn_frame.grid(row=6, column=0, sticky="ew", padx=4, pady=(4, 4))
        ctk.CTkButton(btn_frame, text="Wyświetl wyniki", command=self._show_results, height=36).pack(
            fill="x", padx=4, pady=2
        )
        ctk.CTkButton(
            btn_frame,
            text="Eksportuj do .txt",
            command=self._export_txt,
            height=36,
            fg_color="#27ae60",
        ).pack(fill="x", padx=4, pady=2)
        self._export_all_btn = ctk.CTkButton(
            btn_frame,
            text="Eksportuj wszystkie pytania do folderu",
            command=self._export_all_questions_to_folder,
            height=34,
            fg_color="#2d7ff9",
        )
        self._export_all_btn.pack(fill="x", padx=4, pady=2)

        # Right: results text
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ctk.CTkLabel(right, text="Wyniki", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 4)
        )
        self._results_text = ctk.CTkTextbox(right, wrap="word", font=ctk.CTkFont(size=12))
        self._results_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Start with "Po pytaniu" visible
        self._on_view_mode_change("Po pytaniu")

    # ------------------------------------------------------------------
    # View mode switching
    # ------------------------------------------------------------------

    def _on_view_mode_change(self, mode: str) -> None:
        if mode == "Po pytaniu":
            self._by_seg_frame.grid_remove()
            self._by_q_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
            self._reload_questions_combo()
        else:
            self._by_q_frame.grid_remove()
            self._by_seg_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=0)
            self._reload_segment_combos()

    # ------------------------------------------------------------------
    # "Po pytaniu" logic
    # ------------------------------------------------------------------

    def _reload_questions_combo(self) -> None:
        options = [f"#{q.id} – {q.title}" for q in self._sm.state.questions]
        self._q_combo.configure(values=options if options else ["–"])
        if options:
            self._q_combo.set(options[0])
            self._on_question_change(options[0])
        else:
            self._q_combo.set("–")
            self._current_question_id = None
            self._clear_filter_frame()

    def _on_question_change(self, value: str) -> None:
        try:
            qid = int(value.split("–")[0].strip().lstrip("#"))
            self._current_question_id = qid
        except (ValueError, IndexError):
            self._current_question_id = None
        self._reload_filter_checkboxes()

    def _reload_filter_checkboxes(self) -> None:
        self._clear_filter_frame()
        if self._current_question_id is None:
            return
        agg_path = self._sm.question_aggregated_json_path(self._current_question_id)
        if not agg_path.exists():
            ctk.CTkLabel(self._filter_frame, text="Brak wyników – uruchom analizę.").pack(pady=8)
            return
        data = json.loads(agg_path.read_text(encoding="utf-8"))
        if self._split_segments_var.get():
            for entry in data.get("results", []):
                if self._skip_empty_var.get() and self._is_empty_entry(entry):
                    continue
                key = f"{entry['source_id']}::{entry['segment_id']}"
                label = f"{entry['source_display_name']} / {entry['segment_name']}"
                var = ctk.BooleanVar(value=True)
                self._filter_vars[key] = var
                ctk.CTkCheckBox(self._filter_frame, text=label, variable=var).pack(
                    anchor="w", padx=4, pady=2
                )
            if not self._filter_vars:
                ctk.CTkLabel(self._filter_frame, text="Brak wyników dla wybranych opcji.").pack(pady=8)
            return

        by_source: dict[str, dict] = {}
        for entry in data.get("results", []):
            src_id = entry.get("source_id", "")
            bucket = by_source.setdefault(
                src_id,
                {
                    "source_display_name": entry.get("source_display_name", src_id),
                    "has_non_empty": False,
                },
            )
            if not self._is_empty_entry(entry):
                bucket["has_non_empty"] = True

        for src_id, bucket in by_source.items():
            if self._skip_empty_var.get() and not bucket["has_non_empty"]:
                continue
            label = str(bucket["source_display_name"])
            var = ctk.BooleanVar(value=True)
            self._filter_vars[src_id] = var
            ctk.CTkCheckBox(self._filter_frame, text=label, variable=var).pack(
                anchor="w", padx=4, pady=2
            )
        if not self._filter_vars:
            ctk.CTkLabel(self._filter_frame, text="Brak wyników dla wybranych opcji.").pack(pady=8)

    def _clear_filter_frame(self) -> None:
        for w in self._filter_frame.winfo_children():
            w.destroy()
        self._filter_vars.clear()

    def _select_all_filters(self) -> None:
        for v in self._filter_vars.values():
            v.set(True)

    def _deselect_all_filters(self) -> None:
        for v in self._filter_vars.values():
            v.set(False)

    def _on_question_options_change(self) -> None:
        self._reload_filter_checkboxes()
        if self._view_mode.get() == "Po pytaniu":
            self._show_results()

    # ------------------------------------------------------------------
    # "Po segmencie" logic
    # ------------------------------------------------------------------

    def _reload_segment_combos(self) -> None:
        src_options = [src.display_name for src in self._sm.state.sources]
        self._src_combo.configure(values=src_options if src_options else ["–"])
        if src_options:
            self._src_combo.set(src_options[0])
            self._on_src_change(src_options[0])
        else:
            self._src_combo.set("–")
            self._seg_combo.configure(values=["–"])
            self._seg_combo.set("–")

    def _on_src_change(self, src_name: str) -> None:
        src = next((s for s in self._sm.state.sources if s.display_name == src_name), None)
        if src is None:
            self._seg_combo.configure(values=["–"])
            self._seg_combo.set("–")
            return
        seg_options = [seg.name for seg in src.segments]
        self._seg_combo.configure(values=seg_options if seg_options else ["–"])
        self._seg_combo.set(seg_options[0] if seg_options else "–")

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _show_results(self) -> None:
        mode = self._view_mode.get()
        content = self._build_by_question() if mode == "Po pytaniu" else self._build_by_segment()
        self._results_text.delete("1.0", "end")
        self._results_text.insert("1.0", content)

    def _build_by_question(self) -> str:
        if self._current_question_id is None:
            return "Wybierz pytanie."
        selected_keys = {k for k, v in self._filter_vars.items() if v.get()}
        return self._build_question_text(self._current_question_id, selected_keys)

    def _is_no_data_summary(self, summary: str) -> bool:
        normalized = re.sub(r"[\s.]+", " ", summary.strip().lower())
        return normalized in {"no relevant data found", "brak istotnych danych"}

    def _is_empty_entry(self, entry: dict) -> bool:
        quotes = entry.get("quotes", []) or []
        summary = str(entry.get("fragment_summary", "")).strip()
        if quotes:
            return False
        return not summary or self._is_no_data_summary(summary)

    def _format_quotes(self, lines: list[str], quotes: list[dict]) -> None:
        if not quotes:
            return
        lines.append("Cytaty:")
        for q in quotes:
            pg = q.get("page", "?")
            pg_end = q.get("page_end")
            pg_str = f"{pg}–{pg_end}" if pg_end and pg_end != pg else str(pg)
            lines.append(f'  [s. {pg_str}] "{q.get("text", "")}"')

    def _safe_filename(self, text: str, max_len: int = 40) -> str:
        safe = "".join(c for c in text if c.isalnum() or c in " _-").strip()
        return safe[:max_len] or "wyniki"

    def _build_question_text(
        self, question_id: int, selected_keys: Optional[set[str]] = None
    ) -> str:
        agg_path = self._sm.question_aggregated_json_path(question_id)
        if not agg_path.exists():
            return "Brak wyników. Uruchom analizę dla wybranych segmentów."

        data = json.loads(agg_path.read_text(encoding="utf-8"))
        lines = []
        title = data.get("fragment_title", f"Pytanie #{question_id}")
        lines.append("=" * 70)
        lines.append(f"PYTANIE #{question_id}: {title}")
        lines.append("=" * 70)
        lines.append("")

        skip_empty = self._skip_empty_var.get()
        split_segments = self._split_segments_var.get()
        any_shown = False

        if split_segments:
            for entry in data.get("results", []):
                key = f"{entry['source_id']}::{entry['segment_id']}"
                if selected_keys is not None and self._filter_vars and key not in selected_keys:
                    continue
                if skip_empty and self._is_empty_entry(entry):
                    continue
                any_shown = True
                lines.append(f"--- {entry['source_display_name']} / {entry['segment_name']} ---")
                summary = str(entry.get("fragment_summary", "")).strip()
                if summary:
                    lines.append(f"\nPodsumowanie:\n{summary}\n")
                self._format_quotes(lines, entry.get("quotes", []))
                lines.append("")
        else:
            by_source: dict[str, dict] = {}
            for entry in data.get("results", []):
                src_id = entry.get("source_id", "")
                if selected_keys is not None and self._filter_vars and src_id not in selected_keys:
                    continue
                bucket = by_source.setdefault(
                    src_id,
                    {
                        "source_display_name": entry.get("source_display_name", src_id),
                        "summaries": [],
                        "quotes": [],
                        "seen_quote_keys": set(),
                    },
                )
                summary = str(entry.get("fragment_summary", "")).strip()
                if summary and not self._is_no_data_summary(summary):
                    bucket["summaries"].append(summary)
                for q in entry.get("quotes", []):
                    q_key = (q.get("text", ""), q.get("page"), q.get("page_end"))
                    if q_key in bucket["seen_quote_keys"]:
                        continue
                    bucket["seen_quote_keys"].add(q_key)
                    bucket["quotes"].append(q)

            for bucket in by_source.values():
                bucket["quotes"].sort(
                    key=lambda q: (
                        q.get("page") if isinstance(q.get("page"), int) else 10**9,
                        q.get("page_end") if isinstance(q.get("page_end"), int) else 10**9,
                        str(q.get("text", "")),
                    )
                )

            for src_id, bucket in by_source.items():
                has_content = bool(bucket["summaries"] or bucket["quotes"])
                if skip_empty and not has_content:
                    continue
                any_shown = True
                lines.append(f"--- {bucket['source_display_name']} ---")
                if bucket["summaries"]:
                    merged_summary = "\n\n".join(bucket["summaries"])
                    lines.append(f"\nPodsumowanie:\n{merged_summary}\n")
                elif not skip_empty:
                    lines.append("\nPodsumowanie:\nNo relevant data found.\n")
                self._format_quotes(lines, bucket["quotes"])
                lines.append("")

        if not any_shown:
            lines.append("Brak wyników dla wybranych filtrów.")
        return "\n".join(lines)

    def _build_by_segment(self) -> str:
        src_name = self._src_combo.get()
        seg_name = self._seg_combo.get()
        if src_name == "–" or seg_name == "–":
            return "Wybierz źródło i segment."

        src = next((s for s in self._sm.state.sources if s.display_name == src_name), None)
        if src is None:
            return "Nieznane źródło."
        seg = next((s for s in src.segments if s.name == seg_name), None)
        if seg is None:
            return "Nieznany segment."

        analysis_path = self._sm.segment_analysis_path(src.id, seg.id)
        if not analysis_path.exists():
            return f"Brak wyników analizy dla: {src_name} / {seg_name}\nUruchom analizę AI."

        data = json.loads(analysis_path.read_text(encoding="utf-8"))
        lines = []
        lines.append("=" * 70)
        lines.append(f"SEGMENT: {src_name} / {seg_name}")
        lines.append("=" * 70)
        lines.append("")

        # Build question title lookup
        q_titles = {q.id: q.title for q in self._sm.state.questions}

        for frag in data.get("fragments", []):
            fid = frag.get("fragment_id")
            ftitle = frag.get("fragment_title") or q_titles.get(fid, f"Pytanie #{fid}")
            lines.append(f"=== #{fid}: {ftitle} ===")
            summary = frag.get("fragment_summary", "").strip()
            if summary:
                lines.append(f"\nPodsumowanie:\n{summary}\n")
            quotes = frag.get("quotes", [])
            if quotes:
                lines.append("Cytaty:")
                for q in quotes:
                    pg = q.get("page", "?")
                    pg_end = q.get("page_end")
                    pg_str = f"{pg}–{pg_end}" if pg_end and pg_end != pg else str(pg)
                    lines.append(f'  [s. {pg_str}] "{q.get("text", "")}"')
            else:
                lines.append("  (brak cytatów dla tego zagadnienia)")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_txt(self) -> None:
        mode = self._view_mode.get()
        content = self._build_by_question() if mode == "Po pytaniu" else self._build_by_segment()
        if not content.strip():
            messagebox.showinfo("Info", "Brak wyników do eksportu.")
            return

        if mode == "Po pytaniu" and self._current_question_id is not None:
            q = next((x for x in self._sm.state.questions if x.id == self._current_question_id), None)
            default_name = f"pytanie_{self._current_question_id}.txt"
            if q:
                default_name = f"pytanie_{self._current_question_id}_{self._safe_filename(q.title)}.txt"
        else:
            src_name = self._src_combo.get()
            seg_name = self._seg_combo.get()
            safe_src = self._safe_filename(src_name, max_len=30)
            safe_seg = self._safe_filename(seg_name, max_len=30)
            default_name = f"segment_{safe_src}_{safe_seg}.txt"

        path = filedialog.asksaveasfilename(
            title="Zapisz wyniki",
            defaultextension=".txt",
            filetypes=[("Pliki tekstowe", "*.txt"), ("Wszystkie", "*.*")],
            initialfile=default_name,
            initialdir=str(self._sm.project_dir / "output" / "aggregated"),
        )
        if path:
            Path(path).write_text(content, encoding="utf-8")
            if mode == "Po pytaniu" and self._current_question_id is not None:
                self._sm.question_aggregated_txt_path(self._current_question_id).write_text(
                    content, encoding="utf-8"
                )
            messagebox.showinfo("Sukces", f"Zapisano do:\n{path}")

    def _export_all_questions_to_folder(self) -> None:
        if self._view_mode.get() != "Po pytaniu":
            messagebox.showinfo("Info", "Eksport wszystkich pytań działa w widoku 'Po pytaniu'.")
            return
        if not self._sm.state.questions:
            messagebox.showinfo("Info", "Brak pytań do eksportu.")
            return

        folder = filedialog.askdirectory(
            title="Wybierz folder na eksport wszystkich pytań",
            initialdir=str(self._sm.project_dir / "output" / "aggregated"),
            mustexist=True,
        )
        if not folder:
            return

        saved = 0
        for q in self._sm.state.questions:
            content = self._build_question_text(q.id, selected_keys=None)
            filename = f"pytanie_{q.id}_{self._safe_filename(q.title)}.txt"
            out_path = Path(folder) / filename
            out_path.write_text(content, encoding="utf-8")
            saved += 1

        messagebox.showinfo(
            "Sukces",
            f"Zapisano {saved} plików w folderze:\n{folder}",
        )
