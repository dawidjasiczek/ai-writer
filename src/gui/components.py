"""Reusable GUI components."""
from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from ..models import Source


class SegmentSelector(ctk.CTkScrollableFrame):
    """
    Tree of checkboxes: Source -> Segments.
    Returns selected (source_id, segment_id or None-for-whole-source) tuples.
    """

    def __init__(self, master, state_manager, **kwargs):
        super().__init__(master, **kwargs)
        self._sm = state_manager
        self._source_vars: dict[str, tk.BooleanVar] = {}
        self._seg_vars: dict[tuple[str, str], tk.BooleanVar] = {}
        self._source_frames: dict[str, ctk.CTkFrame] = {}
        self.refresh()

    def refresh(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self._source_vars.clear()
        self._seg_vars.clear()
        self._source_frames.clear()

        for src in self._sm.state.sources:
            src_var = tk.BooleanVar(value=False)
            self._source_vars[src.id] = src_var

            src_frame = ctk.CTkFrame(self, fg_color="transparent")
            src_frame.pack(fill="x", padx=4, pady=(4, 0))
            self._source_frames[src.id] = src_frame

            src_cb = ctk.CTkCheckBox(
                src_frame,
                text=f"  {src.display_name}",
                variable=src_var,
                font=ctk.CTkFont(weight="bold"),
                command=lambda s=src, v=src_var: self._on_source_toggle(s, v),
            )
            src_cb.pack(anchor="w", padx=4)

            for seg in src.segments:
                seg_var = tk.BooleanVar(value=False)
                self._seg_vars[(src.id, seg.id)] = seg_var
                seg_cb = ctk.CTkCheckBox(
                    src_frame,
                    text=f"      {seg.name}  (s. {seg.start_page}–{seg.end_page})",
                    variable=seg_var,
                    font=ctk.CTkFont(size=12),
                )
                seg_cb.pack(anchor="w", padx=16)

    def _on_source_toggle(self, src: Source, var: tk.BooleanVar) -> None:
        state = var.get()
        for seg in src.segments:
            key = (src.id, seg.id)
            if key in self._seg_vars:
                self._seg_vars[key].set(state)

    def get_selection(self) -> list[tuple[str, Optional[str]]]:
        """
        Returns list of (source_id, segment_id).
        If a whole source checkbox is checked (but no segments), returns (source_id, None).
        If individual segments are checked, returns one entry per segment.
        """
        result: list[tuple[str, Optional[str]]] = []
        for src in self._sm.state.sources:
            seg_keys = [(src.id, seg.id) for seg in src.segments]
            selected_segs = [
                seg.id
                for seg in src.segments
                if self._seg_vars.get((src.id, seg.id), tk.BooleanVar()).get()
            ]
            src_checked = self._source_vars.get(src.id, tk.BooleanVar()).get()

            if src_checked and not src.segments:
                result.append((src.id, None))
            elif selected_segs:
                for seg_id in selected_segs:
                    result.append((src.id, seg_id))
            elif src_checked and src.segments:
                for seg in src.segments:
                    result.append((src.id, seg.id))
        return result

    def select_all(self) -> None:
        for var in self._source_vars.values():
            var.set(True)
        for var in self._seg_vars.values():
            var.set(True)

    def deselect_all(self) -> None:
        for var in self._source_vars.values():
            var.set(False)
        for var in self._seg_vars.values():
            var.set(False)


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, height=28, **kwargs)
        self._label = ctk.CTkLabel(self, text="Gotowy.", anchor="w", font=ctk.CTkFont(size=12))
        self._label.pack(fill="x", padx=8)

    def set(self, text: str) -> None:
        self._label.configure(text=text)


class ProgressDialog(ctk.CTkToplevel):
    def __init__(self, master, title: str = "Przetwarzanie..."):
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.geometry("380x120")
        self.grab_set()

        self._label = ctk.CTkLabel(self, text="Proszę czekać...", wraplength=340)
        self._label.pack(pady=(20, 8), padx=20)

        self._bar = ctk.CTkProgressBar(self, mode="indeterminate")
        self._bar.pack(fill="x", padx=20, pady=4)
        self._bar.start()

        self._cancel_cb: Optional[Callable] = None
        self._cancel_btn = ctk.CTkButton(self, text="Anuluj", width=80, command=self._on_cancel)
        self._cancel_btn.pack(pady=8)

    def set_message(self, msg: str) -> None:
        self._label.configure(text=msg)

    def set_cancel_callback(self, cb: Callable) -> None:
        self._cancel_cb = cb

    def _on_cancel(self) -> None:
        if self._cancel_cb:
            self._cancel_cb()
        self.close()

    def close(self) -> None:
        self._bar.stop()
        self.grab_release()
        self.destroy()


def make_label(master, text: str, **kwargs) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text=text, **kwargs)


def make_entry(master, placeholder: str = "", width: int = 200, **kwargs) -> ctk.CTkEntry:
    return ctk.CTkEntry(master, placeholder_text=placeholder, width=width, **kwargs)


def make_button(master, text: str, command: Callable, **kwargs) -> ctk.CTkButton:
    return ctk.CTkButton(master, text=text, command=command, **kwargs)
