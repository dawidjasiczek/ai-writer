"""Results tab: browse results, aggregate, export (step 10).

Two view modes:
- Po pytaniu  : pick a question, filter source/segment checkboxes
- Po segmencie: pick source + segment, shows all questions answered for it
"""
from __future__ import annotations

import json
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

        ctk.CTkLabel(
            self._by_q_frame, text="Źródła / segmenty:", font=ctk.CTkFont(weight="bold")
        ).grid(row=2, column=0, sticky="w", padx=10, pady=(6, 2))

        self._filter_frame = ctk.CTkScrollableFrame(self._by_q_frame, height=220)
        self._filter_frame.grid(row=3, column=0, sticky="nsew", padx=4, pady=4)
        self._by_q_frame.rowconfigure(3, weight=1)

        filter_btns = ctk.CTkFrame(self._by_q_frame, fg_color="transparent")
        filter_btns.grid(row=4, column=0, sticky="ew", padx=4, pady=2)
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
        for entry in data.get("results", []):
            key = f"{entry['source_id']}::{entry['segment_id']}"
            label = f"{entry['source_display_name']} / {entry['segment_name']}"
            var = ctk.BooleanVar(value=True)
            self._filter_vars[key] = var
            ctk.CTkCheckBox(self._filter_frame, text=label, variable=var).pack(
                anchor="w", padx=4, pady=2
            )

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
        agg_path = self._sm.question_aggregated_json_path(self._current_question_id)
        if not agg_path.exists():
            return "Brak wyników. Uruchom analizę dla wybranych segmentów."
        data = json.loads(agg_path.read_text(encoding="utf-8"))
        lines = []
        title = data.get("fragment_title", f"Pytanie #{self._current_question_id}")
        lines.append("=" * 70)
        lines.append(f"PYTANIE #{self._current_question_id}: {title}")
        lines.append("=" * 70)
        lines.append("")
        selected_keys = {k for k, v in self._filter_vars.items() if v.get()}
        any_shown = False
        for entry in data.get("results", []):
            key = f"{entry['source_id']}::{entry['segment_id']}"
            if self._filter_vars and key not in selected_keys:
                continue
            any_shown = True
            lines.append(f"--- {entry['source_display_name']} / {entry['segment_name']} ---")
            summary = entry.get("fragment_summary", "").strip()
            if summary:
                lines.append(f"\nPodsumowanie:\n{summary}\n")
            quotes = entry.get("quotes", [])
            if quotes:
                lines.append("Cytaty:")
                for q in quotes:
                    pg = q.get("page", "?")
                    pg_end = q.get("page_end")
                    pg_str = f"{pg}–{pg_end}" if pg_end and pg_end != pg else str(pg)
                    lines.append(f'  [s. {pg_str}] "{q.get("text", "")}"')
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
                safe = "".join(c for c in q.title if c.isalnum() or c in " _-").strip()
                default_name = f"pytanie_{self._current_question_id}_{safe[:40]}.txt"
        else:
            src_name = self._src_combo.get()
            seg_name = self._seg_combo.get()
            safe_src = "".join(c for c in src_name if c.isalnum() or c in " _-").strip()[:30]
            safe_seg = "".join(c for c in seg_name if c.isalnum() or c in " _-").strip()[:30]
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
