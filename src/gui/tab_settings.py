"""Settings tab: API key, default model, prompt editor, data reset."""
from __future__ import annotations

import shutil
from typing import Callable, Optional

import customtkinter as ctk
from tkinter import messagebox

from ..models import AVAILABLE_MODELS


class SettingsTab(ctk.CTkFrame):
    def __init__(
        self,
        master,
        state_manager,
        ai_service_ref: list,
        refresh_callback: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self._sm = state_manager
        self._ai_ref = ai_service_ref
        self._refresh_cb = refresh_callback

        self._build()
        self._load()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)

        row = 0
        ctk.CTkLabel(self, text="Ustawienia", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 8)
        )

        row += 1
        ctk.CTkLabel(self, text="Klucz OpenAI API:").grid(
            row=row, column=0, sticky="e", padx=(16, 8), pady=6
        )
        self._api_key_entry = ctk.CTkEntry(
            self, width=360, show="*", placeholder_text="sk-..."
        )
        self._api_key_entry.grid(row=row, column=1, sticky="ew", padx=(0, 16), pady=6)

        row += 1
        ctk.CTkLabel(self, text="Domyślny model:").grid(
            row=row, column=0, sticky="e", padx=(16, 8), pady=6
        )
        self._model_var = ctk.StringVar()
        self._model_combo = ctk.CTkComboBox(
            self, values=AVAILABLE_MODELS, variable=self._model_var, width=220
        )
        self._model_combo.grid(row=row, column=1, sticky="w", padx=(0, 16), pady=6)

        row += 1
        ctk.CTkLabel(
            self,
            text="Prompt – opis graficzny stron:",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(14, 2))

        row += 1
        self._graphic_prompt = ctk.CTkTextbox(self, height=120, wrap="word")
        self._graphic_prompt.grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8)
        )

        row += 1
        ctk.CTkLabel(
            self,
            text="Prompt – ekstrakcja cytatów (użyj {questions_block} jako placeholder):",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(8, 2))

        row += 1
        self._quote_prompt = ctk.CTkTextbox(self, height=200, wrap="word")
        self._quote_prompt.grid(
            row=row, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 8)
        )

        row += 1
        save_btn = ctk.CTkButton(self, text="Zapisz ustawienia", command=self._save)
        save_btn.grid(row=row, column=0, columnspan=2, pady=(8, 8))

        row += 1
        ctk.CTkLabel(
            self,
            text="Strefa niebezpieczna",
            font=ctk.CTkFont(weight="bold"),
            text_color=("#c0392b", "#e74c3c"),
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=16, pady=(16, 2))

        row += 1
        ctk.CTkButton(
            self,
            text="Wyczyść dane projektu (usuń output, resetuj źródła)",
            command=self._clear_data,
            fg_color="#c0392b",
            hover_color="#922b21",
        ).grid(row=row, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))

    def _load(self) -> None:
        s = self._sm.state
        self._api_key_entry.delete(0, "end")
        self._api_key_entry.insert(0, s.openai_api_key)
        self._model_var.set(s.default_model)

        self._graphic_prompt.delete("1.0", "end")
        self._graphic_prompt.insert("1.0", s.prompts.graphic_description)

        self._quote_prompt.delete("1.0", "end")
        self._quote_prompt.insert("1.0", s.prompts.quote_extraction)

    def _save(self) -> None:
        api_key = self._api_key_entry.get().strip()
        model = self._model_var.get()
        graphic = self._graphic_prompt.get("1.0", "end").strip()
        quote = self._quote_prompt.get("1.0", "end").strip()

        self._sm.set_api_key(api_key)
        self._sm.set_default_model(model)
        self._sm.update_prompts(graphic_description=graphic, quote_extraction=quote)

        # Update the live AIService with new API key
        if self._ai_ref:
            self._ai_ref[0].update_api_key(api_key)

    def _clear_data(self) -> None:
        dialog = _ConfirmClearDialog(self)
        self.wait_window(dialog)
        if not dialog.confirmed:
            return

        # Delete output folder contents
        output_dir = self._sm.project_dir / "output"
        if output_dir.exists():
            shutil.rmtree(output_dir)

        # Reset state: keep API key and prompts, wipe sources and questions
        api_key = self._sm.state.openai_api_key
        model = self._sm.state.default_model
        prompts_dict = self._sm.state.prompts.to_dict()

        self._sm.state.sources.clear()
        self._sm.state.questions.clear()
        self._sm.save()
        self._sm._ensure_dirs()

        messagebox.showinfo("Gotowe", "Dane projektu zostały wyczyszczone.")
        if self._refresh_cb:
            self._refresh_cb()


class _ConfirmClearDialog(ctk.CTkToplevel):
    """Asks the user to type 'tak, na pewno' before clearing data.

    Widgets are created in after(50) to work around the CTkToplevel blank-
    window rendering bug on Windows.
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("Potwierdź wyczyszczenie danych")
        self.resizable(False, False)
        self.geometry("440x200")
        self.confirmed = False
        self._entry: Optional[ctk.CTkEntry] = None
        # Build content after the window is visible to avoid blank rendering
        self.after(50, self._build_content)
        self.grab_set()

    def _build_content(self) -> None:
        ctk.CTkLabel(
            self,
            text="Ta operacja usunie wszystkie wyciągnięte teksty i wyniki AI.\nŹródła PDF pozostaną na dysku.",
            wraplength=400,
        ).pack(pady=(16, 6), padx=16)
        ctk.CTkLabel(
            self,
            text='Wpisz "tak, na pewno" aby potwierdzić:',
            font=ctk.CTkFont(weight="bold"),
        ).pack(padx=16)

        self._entry = ctk.CTkEntry(self, width=280)
        self._entry.pack(pady=8)
        self._entry.focus_set()

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=(0, 12))
        ctk.CTkButton(
            btn_row, text="Usuń dane", command=self._on_confirm, fg_color="#c0392b"
        ).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Anuluj", command=self.destroy).pack(side="left", padx=8)

    def _on_confirm(self) -> None:
        if self._entry is None:
            return
        if self._entry.get().strip().lower() == "tak, na pewno":
            self.confirmed = True
            self.grab_release()
            self.destroy()
        else:
            self._entry.delete(0, "end")
            self._entry.configure(placeholder_text="Wpisz dokładnie: tak, na pewno")
