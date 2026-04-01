"""Analyze tab: run quote extraction AI (step 9) with aggregation."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from ..state_manager import StateManager
from ..ai_service import AIService
from ..models import AVAILABLE_MODELS, SegmentAnalysisResult, FragmentResult, Quote
from .components import SegmentSelector, StatusBar


class AnalyzeTab(ctk.CTkFrame):
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

        # Left: controls
        left = ctk.CTkFrame(self, width=280)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Wybierz segmenty", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 2)
        )
        self._selector = SegmentSelector(left, self._sm, height=260)
        self._selector.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        btn_sel = ctk.CTkFrame(left, fg_color="transparent")
        btn_sel.grid(row=2, column=0, sticky="ew", padx=4)
        ctk.CTkButton(btn_sel, text="Wszystkie", command=self._selector.select_all, width=100).pack(
            side="left", padx=2, pady=4
        )
        ctk.CTkButton(btn_sel, text="Żadne", command=self._selector.deselect_all, width=80).pack(
            side="left", padx=2, pady=4
        )

        model_row = ctk.CTkFrame(left, fg_color="transparent")
        model_row.grid(row=3, column=0, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(model_row, text="Model:").pack(side="left", padx=(0, 6))
        self._model_var = ctk.StringVar(value=self._sm.state.default_model)
        self._model_combo = ctk.CTkComboBox(model_row, values=AVAILABLE_MODELS, variable=self._model_var, width=180)
        self._model_combo.pack(side="left")

        ctk.CTkButton(
            left, text="Uruchom analizę", command=self._run_analysis, height=40, font=ctk.CTkFont(weight="bold")
        ).grid(row=4, column=0, sticky="ew", padx=8, pady=8)

        self._progress = ctk.CTkProgressBar(left, mode="indeterminate")
        self._progress.grid(row=5, column=0, sticky="ew", padx=8, pady=4)
        self._progress_label = ctk.CTkLabel(left, text="", font=ctk.CTkFont(size=11), wraplength=250)
        self._progress_label.grid(row=6, column=0, padx=8, pady=2)

        # Right: log
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ctk.CTkLabel(right, text="Log operacji", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 4)
        )
        self._log = ctk.CTkTextbox(right, wrap="word", font=ctk.CTkFont(family="Courier", size=11), state="disabled")
        self._log.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

    def _log_line(self, msg: str) -> None:
        def _do():
            self._log.configure(state="normal")
            self._log.insert("end", msg + "\n")
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _do)

    def _run_analysis(self) -> None:
        if not self._sm.state.questions:
            messagebox.showinfo("Info", "Najpierw zdefiniuj pytania w zakładce 'Pytania'.")
            return
        if not self._sm.state.openai_api_key:
            messagebox.showinfo("Info", "Podaj klucz API w zakładce 'Ustawienia'.")
            return

        selection = self._selector.get_selection()
        if not selection:
            messagebox.showinfo("Info", "Wybierz co najmniej jeden segment.")
            return

        model = self._model_var.get()
        self._running = True
        self._progress.start()
        self._log_line(f"--- Rozpoczęcie analizy, model: {model} ---")

        def worker():
            errors = []
            done = 0
            total = len(selection)

            for src_id, seg_id in selection:
                src = self._sm.get_source(src_id)
                if src is None:
                    continue

                segs_to_process = (
                    src.segments if seg_id is None else [self._sm.get_segment(src_id, seg_id)]
                )
                segs_to_process = [s for s in segs_to_process if s is not None]

                for seg in segs_to_process:
                    # Prefer full text (with graphics) if available, else raw
                    full_path = self._sm.full_text_path(src_id, seg.id)
                    raw_path = self._sm.raw_text_path(src_id, seg.id)
                    if full_path.exists():
                        text_path = full_path
                    elif raw_path.exists():
                        text_path = raw_path
                    else:
                        errors.append(
                            f"{src.display_name}/{seg.name}: brak tekstu – uruchom ekstrakcję najpierw"
                        )
                        self._log_line(f"  SKIP {src.display_name}/{seg.name}: brak tekstu")
                        continue

                    segment_text = text_path.read_text(encoding="utf-8")

                    self._log_line(f"  Analizuję: {src.display_name} / {seg.name}...")
                    self.after(0, lambda s=f"{src.display_name}/{seg.name}": self._progress_label.configure(text=s))

                    result_holder = [None]
                    error_holder = [None]
                    event = threading.Event()

                    def _cb(res, exc, _event=event, _rh=result_holder, _eh=error_holder):
                        _rh[0] = res
                        _eh[0] = exc
                        _event.set()

                    self._ai_ref[0].extract_quotes(
                        segment_text=segment_text,
                        questions=self._sm.state.questions,
                        model=model,
                        system_prompt_template=self._sm.state.prompts.quote_extraction,
                        on_done=_cb,
                        on_progress=lambda msg: self._log_line(f"    {msg}"),
                    )
                    event.wait()

                    if error_holder[0]:
                        errors.append(f"{src.display_name}/{seg.name}: {error_holder[0]}")
                        self._log_line(f"  BŁĄD {src.display_name}/{seg.name}: {error_holder[0]}")
                        continue

                    raw_result = result_holder[0]
                    _save_segment_result(self._sm, src, seg, raw_result)
                    done += 1
                    self._log_line(f"  OK {src.display_name} / {seg.name}")

            # Aggregate all results
            self._log_line("Agregowanie wyników...")
            _aggregate_all(self._sm)

            def finish():
                self._running = False
                self._progress.stop()
                self._progress_label.configure(text="")
                if errors:
                    self._log_line("--- Zakończono z błędami ---")
                    messagebox.showerror("Błędy", "\n".join(errors))
                else:
                    self._log_line(f"--- Zakończono. Przeanalizowano {done} segmentów. ---")
                self._set_status(f"Analiza zakończona. {done}/{total} segmentów.")

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()


# ------------------------------------------------------------------
# Helpers for saving & aggregating results
# ------------------------------------------------------------------


def _save_segment_result(sm: StateManager, src, seg, raw_result: dict) -> None:
    """Save per-segment JSON and update source-level aggregation."""
    result = SegmentAnalysisResult(
        source_id=src.id,
        source_display_name=src.display_name,
        segment_id=seg.id,
        segment_name=seg.name,
        fragments=[
            FragmentResult(
                fragment_id=f["fragment_id"],
                fragment_title=f["fragment_title"],
                fragment_summary=f.get("fragment_summary", ""),
                quotes=[Quote(**q) for q in f.get("quotes", [])],
            )
            for f in raw_result.get("fragments", [])
        ],
    )
    # Per-segment file
    seg_path = sm.segment_analysis_path(src.id, seg.id)
    seg_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Source-level aggregation: reload all segments for this source
    all_frags: list[dict] = []
    for s in [x for x in sm.state.sources if x.id == src.id]:
        for sg in s.segments:
            p = sm.segment_analysis_path(src.id, sg.id)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                for frag in data.get("fragments", []):
                    frag_copy = dict(frag)
                    frag_copy["_segment_id"] = sg.id
                    frag_copy["_segment_name"] = sg.name
                    all_frags.append(frag_copy)

    source_agg = {
        "source_id": src.id,
        "source_display_name": src.display_name,
        "fragments": all_frags,
    }
    sm.source_quotes_path(src.id).write_text(
        json.dumps(source_agg, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _aggregate_all(sm: StateManager) -> None:
    """Build per-question aggregated JSON across all sources."""
    question_map: dict[int, dict] = {}

    for src in sm.state.sources:
        src_path = sm.source_quotes_path(src.id)
        if not src_path.exists():
            continue
        data = json.loads(src_path.read_text(encoding="utf-8"))
        for frag in data.get("fragments", []):
            fid = frag["fragment_id"]
            if fid not in question_map:
                question_map[fid] = {
                    "fragment_id": fid,
                    "fragment_title": frag.get("fragment_title", ""),
                    "results": [],
                }
            question_map[fid]["results"].append(
                {
                    "source_id": src.id,
                    "source_display_name": src.display_name,
                    "segment_id": frag.get("_segment_id", ""),
                    "segment_name": frag.get("_segment_name", ""),
                    "fragment_summary": frag.get("fragment_summary", ""),
                    "quotes": frag.get("quotes", []),
                }
            )

    for qid, agg in question_map.items():
        sm.question_aggregated_json_path(qid).write_text(
            json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
