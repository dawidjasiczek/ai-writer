"""Results tab: browse results, aggregate, export (step 10)."""
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
        self._build()

    def refresh(self) -> None:
        self._reload_questions()

    def _build(self) -> None:
        self.columnconfigure(0, weight=0, minsize=260)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Left: filters
        left = ctk.CTkFrame(self, width=260)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.columnconfigure(0, weight=1)
        left.rowconfigure(3, weight=1)

        ctk.CTkLabel(left, text="Filtry", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )

        ctk.CTkLabel(left, text="Pytanie:").grid(row=1, column=0, sticky="w", padx=10, pady=(4, 0))
        self._q_combo = ctk.CTkComboBox(left, values=["–"], command=self._on_question_change, width=230)
        self._q_combo.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 6))

        ctk.CTkLabel(left, text="Źródła / segmenty:", font=ctk.CTkFont(weight="bold")).grid(
            row=3, column=0, sticky="nw", padx=10, pady=(6, 2)
        )

        self._filter_frame = ctk.CTkScrollableFrame(left, height=300)
        self._filter_frame.grid(row=4, column=0, sticky="nsew", padx=4, pady=4)

        filter_btns = ctk.CTkFrame(left, fg_color="transparent")
        filter_btns.grid(row=5, column=0, sticky="ew", padx=4, pady=4)
        ctk.CTkButton(filter_btns, text="Wszystkie", command=self._select_all_filters, width=100).pack(
            side="left", padx=2
        )
        ctk.CTkButton(filter_btns, text="Żadne", command=self._deselect_all_filters, width=80).pack(
            side="left", padx=2
        )

        ctk.CTkButton(left, text="Wyświetl wyniki", command=self._show_results, height=36).grid(
            row=6, column=0, sticky="ew", padx=8, pady=6
        )
        ctk.CTkButton(
            left,
            text="Eksportuj do .txt",
            command=self._export_txt,
            height=36,
            fg_color="#27ae60",
        ).grid(row=7, column=0, sticky="ew", padx=8, pady=(0, 8))

        # Right: results display
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ctk.CTkLabel(right, text="Wyniki", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 4)
        )
        self._results_text = ctk.CTkTextbox(right, wrap="word", font=ctk.CTkFont(size=12))
        self._results_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        # Internal state
        self._filter_vars: dict[str, "ctk.BooleanVar"] = {}
        self._current_question_id: Optional[int] = None

    # ------------------------------------------------------------------
    # Questions dropdown
    # ------------------------------------------------------------------

    def _reload_questions(self) -> None:
        options = []
        for q in self._sm.state.questions:
            options.append(f"#{q.id} – {q.title}")
        self._q_combo.configure(values=options if options else ["–"])
        if options:
            self._q_combo.set(options[0])
            self._on_question_change(options[0])
        else:
            self._q_combo.set("–")
            self._current_question_id = None

    def _on_question_change(self, value: str) -> None:
        if value.startswith("#") and "–" in value:
            try:
                qid = int(value.split("–")[0].strip().lstrip("#"))
                self._current_question_id = qid
            except ValueError:
                self._current_question_id = None
        else:
            self._current_question_id = None
        self._reload_filter_checkboxes()

    # ------------------------------------------------------------------
    # Filter checkboxes (source / segment)
    # ------------------------------------------------------------------

    def _reload_filter_checkboxes(self) -> None:
        for w in self._filter_frame.winfo_children():
            w.destroy()
        self._filter_vars.clear()

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

    def _select_all_filters(self) -> None:
        for v in self._filter_vars.values():
            v.set(True)

    def _deselect_all_filters(self) -> None:
        for v in self._filter_vars.values():
            v.set(False)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _show_results(self) -> None:
        if self._current_question_id is None:
            messagebox.showinfo("Info", "Wybierz pytanie.")
            return

        content = self._build_display_text()
        self._results_text.delete("1.0", "end")
        self._results_text.insert("1.0", content)

    def _build_display_text(self) -> str:
        if self._current_question_id is None:
            return ""

        agg_path = self._sm.question_aggregated_json_path(self._current_question_id)
        if not agg_path.exists():
            return "Brak wyników. Uruchom analizę dla wybranych segmentów."

        data = json.loads(agg_path.read_text(encoding="utf-8"))
        lines = []
        title = data.get("fragment_title", f"Pytanie #{self._current_question_id}")
        lines.append(f"{'='*70}")
        lines.append(f"PYTANIE: {title}")
        lines.append(f"{'='*70}\n")

        selected_keys = {k for k, v in self._filter_vars.items() if v.get()}

        for entry in data.get("results", []):
            key = f"{entry['source_id']}::{entry['segment_id']}"
            if self._filter_vars and key not in selected_keys:
                continue

            lines.append(f"--- {entry['source_display_name']} / {entry['segment_name']} ---")
            summary = entry.get("fragment_summary", "").strip()
            if summary:
                lines.append(f"\nPodsumowanie:\n{summary}\n")
            quotes = entry.get("quotes", [])
            if quotes:
                lines.append("Cytaty:")
                for q in quotes:
                    lines.append(f'  [s. {q.get("page", "?")}] "{q.get("text", "")}"')
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_txt(self) -> None:
        if self._current_question_id is None:
            messagebox.showinfo("Info", "Wybierz pytanie.")
            return

        content = self._build_display_text()
        if not content.strip():
            messagebox.showinfo("Info", "Brak wyników do eksportu.")
            return

        q = next(
            (x for x in self._sm.state.questions if x.id == self._current_question_id), None
        )
        default_name = f"pytanie_{self._current_question_id}.txt"
        if q:
            safe = "".join(c for c in q.title if c.isalnum() or c in " _-").strip()
            default_name = f"pytanie_{self._current_question_id}_{safe[:40]}.txt"

        path = filedialog.asksaveasfilename(
            title="Zapisz wyniki",
            defaultextension=".txt",
            filetypes=[("Pliki tekstowe", "*.txt"), ("Wszystkie", "*.*")],
            initialfile=default_name,
            initialdir=str(self._sm.project_dir / "output" / "aggregated"),
        )
        if path:
            Path(path).write_text(content, encoding="utf-8")
            # Also save to standard aggregated path
            self._sm.question_aggregated_txt_path(self._current_question_id).write_text(
                content, encoding="utf-8"
            )
            messagebox.showinfo("Sukces", f"Zapisano do:\n{path}")
