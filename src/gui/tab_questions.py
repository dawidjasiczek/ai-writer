"""Questions tab: CRUD list of questions with id/title/description."""
from __future__ import annotations

from tkinter import messagebox
from typing import Optional

import customtkinter as ctk

from ..state_manager import StateManager
from ..models import Question


class QuestionsTab(ctk.CTkFrame):
    def __init__(self, master, state_manager: StateManager, **kwargs):
        super().__init__(master, **kwargs)
        self._sm = state_manager
        self._selected_id: Optional[int] = None
        self._build()
        self._refresh()

    def _build(self) -> None:
        self.columnconfigure(0, weight=0, minsize=260)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Left: question list
        left = ctk.CTkFrame(self, width=260)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        ctk.CTkLabel(left, text="Pytania", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=(10, 4)
        )
        self._q_list = ctk.CTkScrollableFrame(left)
        self._q_list.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)

        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=4, pady=4)
        ctk.CTkButton(btn_row, text="+ Nowe pytanie", command=self._new_question, width=130).pack(
            side="left", padx=2
        )
        ctk.CTkButton(
            btn_row, text="Usuń", command=self._delete_question, width=80, fg_color="#c0392b"
        ).pack(side="left", padx=2)

        # Right: editor
        right = ctk.CTkFrame(self)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Edytor pytania", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 4)
        )

        ctk.CTkLabel(right, text="Tytuł / Zagadnienie:").grid(
            row=1, column=0, sticky="w", padx=12, pady=(6, 0)
        )
        self._title_entry = ctk.CTkEntry(right, placeholder_text="np. Definicja sztucznej inteligencji")
        self._title_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))

        ctk.CTkLabel(right, text="Opis (opcjonalny):").grid(
            row=3, column=0, sticky="w", padx=12, pady=(6, 0)
        )
        self._desc_text = ctk.CTkTextbox(right, height=120, wrap="word")
        self._desc_text.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))

        save_btn = ctk.CTkButton(right, text="Zapisz pytanie", command=self._save_question, width=140)
        save_btn.grid(row=5, column=0, pady=4)

        self._id_label = ctk.CTkLabel(right, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self._id_label.grid(row=6, column=0, pady=(0, 4))

    def _refresh(self) -> None:
        for w in self._q_list.winfo_children():
            w.destroy()
        for q in self._sm.state.questions:
            btn = ctk.CTkButton(
                self._q_list,
                text=f"#{q.id}  {q.title}",
                anchor="w",
                fg_color="transparent",
                text_color=("black", "white"),
                hover_color=("lightblue", "#2a5080"),
                command=lambda qid=q.id: self._select_question(qid),
            )
            btn.pack(fill="x", padx=2, pady=1)

    def _select_question(self, qid: int) -> None:
        self._selected_id = qid
        q = next((x for x in self._sm.state.questions if x.id == qid), None)
        if q is None:
            return
        self._title_entry.delete(0, "end")
        self._title_entry.insert(0, q.title)
        self._desc_text.delete("1.0", "end")
        self._desc_text.insert("1.0", q.description)
        self._id_label.configure(text=f"ID pytania: {q.id}")

    def _new_question(self) -> None:
        self._selected_id = None
        self._title_entry.delete(0, "end")
        self._desc_text.delete("1.0", "end")
        self._id_label.configure(text="Nowe pytanie")

    def _save_question(self) -> None:
        title = self._title_entry.get().strip()
        desc = self._desc_text.get("1.0", "end").strip()
        if not title:
            messagebox.showerror("Błąd", "Podaj tytuł pytania.")
            return
        if self._selected_id is not None:
            self._sm.update_question(self._selected_id, title=title, description=desc)
        else:
            q = self._sm.add_question(title, desc)
            self._selected_id = q.id
            self._id_label.configure(text=f"ID pytania: {q.id}")
        self._refresh()

    def _delete_question(self) -> None:
        if self._selected_id is None:
            messagebox.showinfo("Info", "Wybierz pytanie.")
            return
        if messagebox.askyesno("Potwierdź", "Usunąć to pytanie?"):
            self._sm.remove_question(self._selected_id)
            self._selected_id = None
            self._title_entry.delete(0, "end")
            self._desc_text.delete("1.0", "end")
            self._id_label.configure(text="")
            self._refresh()
