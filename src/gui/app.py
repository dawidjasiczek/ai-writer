"""Main application window."""
from __future__ import annotations

from typing import Optional
import customtkinter as ctk

from ..state_manager import StateManager
from ..ai_service import AIService

from .tab_sources import SourcesTab
from .tab_extract import ExtractTab
from .tab_questions import QuestionsTab
from .tab_analyze import AnalyzeTab
from .tab_results import ResultsTab
from .tab_settings import SettingsTab
from .components import StatusBar


ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(
        self,
        state_manager: StateManager,
        project_manager=None,
        initial_project_id: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.title("Thesis Source Analyzer")
        self.geometry("1100x780")
        self.minsize(900, 600)

        self._sm = state_manager
        self._pm = project_manager
        self._current_project_id = initial_project_id

        # AIService held in a mutable list so Settings tab can swap it
        self._ai_ref: list[AIService] = [
            AIService(
                state_manager.state.openai_api_key,
                max_concurrent=state_manager.state.gpt_workers,
            )
        ]

        self._build()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)

        tab_view = ctk.CTkTabview(self)
        tab_view.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))

        tab_view.add("Źródła")
        tab_view.add("Ekstrakcja")
        tab_view.add("Pytania")
        tab_view.add("Analiza")
        tab_view.add("Wyniki")
        tab_view.add("Ustawienia")

        def make_tab(cls, tab_name, *args, **kwargs):
            frame = cls(tab_view.tab(tab_name), *args, **kwargs)
            frame.pack(fill="both", expand=True)
            return frame

        self._sources_tab = make_tab(SourcesTab, "Źródła", self._sm, self._refresh_all)
        self._extract_tab = make_tab(ExtractTab, "Ekstrakcja", self._sm, self._ai_ref)
        self._questions_tab = make_tab(QuestionsTab, "Pytania", self._sm)
        self._analyze_tab = make_tab(AnalyzeTab, "Analiza", self._sm, self._ai_ref)
        self._results_tab = make_tab(ResultsTab, "Wyniki", self._sm)
        self._settings_tab = make_tab(
            SettingsTab,
            "Ustawienia",
            self._sm,
            self._ai_ref,
            self._refresh_all,
            project_manager=self._pm,
            current_project_id=self._current_project_id,
            switch_project_callback=self.switch_project,
        )

        # Status bar
        self._status = StatusBar(self)
        self._status.grid(row=1, column=0, sticky="ew", padx=8, pady=(2, 4))

        # Pass status bar down to tabs that need it
        self._extract_tab.set_status_bar(self._status)
        self._analyze_tab.set_status_bar(self._status)

        # Refresh tabs on tab change
        tab_view.configure(command=self._on_tab_change)
        self._tab_view = tab_view

    def switch_project(self, project_id: str) -> None:
        """Tear down current tabs and reload everything for the given project."""
        if self._pm is None:
            return
        self._sm.save()
        new_dir = self._pm.get_project_dir(project_id)
        self._sm = StateManager(new_dir)
        self._current_project_id = project_id

        # Replace AIService with one configured for the new project
        old_ai = self._ai_ref[0]
        self._ai_ref[0] = AIService(
            self._sm.state.openai_api_key,
            max_concurrent=self._sm.state.gpt_workers,
        )
        old_ai.shutdown()

        self._tab_view.destroy()
        self._status.destroy()
        self._build()

    def _on_tab_change(self) -> None:
        name = self._tab_view.get()
        if name == "Ekstrakcja":
            self._extract_tab.refresh()
        elif name == "Analiza":
            self._analyze_tab.refresh()
        elif name == "Wyniki":
            self._results_tab.refresh()

    def _refresh_all(self) -> None:
        self._extract_tab.refresh()
        self._analyze_tab.refresh()
        self._results_tab.refresh()

    def destroy(self) -> None:
        self._ai_ref[0].shutdown()
        super().destroy()
