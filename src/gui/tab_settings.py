"""Settings tab: API key, default model, prompt editor."""
from __future__ import annotations

import customtkinter as ctk

from ..models import AVAILABLE_MODELS


class SettingsTab(ctk.CTkFrame):
    def __init__(self, master, state_manager, ai_service_ref: list, **kwargs):
        super().__init__(master, **kwargs)
        self._sm = state_manager
        # ai_service_ref is a mutable list so we can swap the AIService object later
        self._ai_ref = ai_service_ref

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
        save_btn.grid(row=row, column=0, columnspan=2, pady=(8, 16))

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
