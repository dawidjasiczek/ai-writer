"""Manages multiple thesis projects stored under a shared base directory."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional


class ProjectEntry:
    def __init__(self, project_id: str, name: str, folder: str) -> None:
        self.id = project_id
        self.name = name
        self.folder = folder

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "folder": self.folder}

    @classmethod
    def from_dict(cls, d: dict) -> "ProjectEntry":
        return cls(d["id"], d["name"], d["folder"])


class ProjectManager:
    """Stores project metadata in <base_dir>/projects.json.

    Each project lives in its own subdirectory under base_dir.
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._file = base_dir / "projects.json"
        self._projects: list[ProjectEntry] = []
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._file.exists():
            with open(self._file, encoding="utf-8") as f:
                data = json.load(f)
            self._projects = [ProjectEntry.from_dict(p) for p in data.get("projects", [])]
        if not self._projects:
            self._create_entry("Domyślny projekt", "default")

    def _save(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"projects": [p.to_dict() for p in self._projects]}, f, ensure_ascii=False, indent=2)
        tmp.replace(self._file)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_projects(self) -> list[ProjectEntry]:
        return list(self._projects)

    def get_project(self, project_id: str) -> Optional[ProjectEntry]:
        return next((p for p in self._projects if p.id == project_id), None)

    def get_project_dir(self, project_id: str) -> Path:
        p = self.get_project(project_id)
        if p is None:
            raise ValueError(f"Project {project_id!r} not found")
        d = self.base_dir / p.folder
        d.mkdir(parents=True, exist_ok=True)
        return d

    def add_project(self, name: str) -> ProjectEntry:
        name = name.strip() or "Nowy projekt"
        return self._create_entry(name, f"proj_{uuid.uuid4().hex[:8]}")

    def rename_project(self, project_id: str, new_name: str) -> None:
        p = self.get_project(project_id)
        if p:
            p.name = new_name.strip() or p.name
            self._save()

    def delete_project(self, project_id: str) -> None:
        if len(self._projects) <= 1:
            raise ValueError("Nie można usunąć jedynego projektu.")
        self._projects = [p for p in self._projects if p.id != project_id]
        self._save()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _create_entry(self, name: str, folder: str) -> ProjectEntry:
        entry = ProjectEntry(project_id=folder, name=name, folder=folder)
        (self.base_dir / folder).mkdir(parents=True, exist_ok=True)
        self._projects.append(entry)
        self._save()
        return entry
