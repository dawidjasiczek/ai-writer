from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    # Allow passing a project directory as argument; default to ~/thesis-projects/default
    if len(sys.argv) > 1:
        project_dir = Path(sys.argv[1])
    else:
        project_dir = Path.home() / "thesis-projects" / "default"

    project_dir.mkdir(parents=True, exist_ok=True)

    from src.state_manager import StateManager
    from src.gui.app import App

    state_manager = StateManager(project_dir)
    app = App(state_manager)
    app.mainloop()


if __name__ == "__main__":
    main()
