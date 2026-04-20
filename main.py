from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    from src.state_manager import StateManager
    from src.gui.app import App

    # Legacy: single project dir passed as argument
    if len(sys.argv) > 1:
        project_dir = Path(sys.argv[1])
        project_dir.mkdir(parents=True, exist_ok=True)
        state_manager = StateManager(project_dir)
        app = App(state_manager)
        app.mainloop()
        return

    from src.project_manager import ProjectManager

    base_dir = Path.home() / "thesis-projects"
    pm = ProjectManager(base_dir)
    projects = pm.list_projects()
    first_dir = pm.get_project_dir(projects[0].id)
    state_manager = StateManager(first_dir)
    app = App(state_manager, project_manager=pm, initial_project_id=projects[0].id)
    app.mainloop()


if __name__ == "__main__":
    main()
