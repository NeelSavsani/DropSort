#!/usr/bin/env python3
"""DropSort — Intelligent File Organizer.

Usage:
  # Launch Desktop GUI:
  python main.py

  # Headless CLI Modes:
  python main.py --simulate --path "D:/Downloads"
  python main.py --run --path "D:/Downloads"
  python main.py --watch --path "D:/Downloads"
  python main.py --undo last
  python main.py --list-rules
"""

import sys

# Ensure UTF-8 output encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dropsort.cli import run_cli


def main() -> None:
    # Check if CLI commands were invoked
    handled_by_cli = run_cli(sys.argv[1:])
    if not handled_by_cli:
        # Launch PySide6 GUI
        from dropsort.gui.app import launch_gui
        launch_gui()


if __name__ == "__main__":
    main()
