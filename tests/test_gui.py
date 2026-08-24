"""Headless integration tests for PySide6 GUI views and MainWindow."""

import os
from pathlib import Path
import tempfile
import pytest

# Use offscreen platform for headless Qt testing
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from dropsort.database import Database
from dropsort.gui.app import MainWindow
from dropsort.gui.dashboard_view import DashboardView
from dropsort.gui.history_view import HistoryView
from dropsort.gui.preview_view import PreviewView
from dropsort.gui.rule_editor_view import RuleEditorView
from dropsort.gui.settings_view import SettingsView


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_init(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_path = Path(tmpdir) / "rules.json"
        db_path = Path(tmpdir) / "test.db"

        window = MainWindow(str(rules_path))
        assert window.windowTitle() == "DropSort — Intelligent File Organizer"
        assert window.view_stack.count() == 5
        assert isinstance(window.dashboard_view, DashboardView)
        assert isinstance(window.preview_view, PreviewView)
        assert isinstance(window.rule_editor_view, RuleEditorView)
        assert isinstance(window.history_view, HistoryView)
        assert isinstance(window.settings_view, SettingsView)

        # Test tab navigation
        window._navigate_to(1)
        assert window.view_stack.currentIndex() == 1

        window._navigate_to(2)
        assert window.view_stack.currentIndex() == 2

        window._navigate_to(0)
        assert window.view_stack.currentIndex() == 0

        # Test toast notification
        window.show_toast("Test Toast", "success")


def test_rule_editor_sandbox_interaction(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_path = Path(tmpdir) / "rules.json"
        window = MainWindow(str(rules_path))
        editor = window.rule_editor_view

        # Set sandbox input
        editor.test_filename_input.setText("invoice_august_2026.pdf")
        assert "Invoices & Receipts" in editor.sandbox_result_lbl.text()

        editor.test_filename_input.setText("IMG_1234.jpg")
        assert "Photos by Year" in editor.sandbox_result_lbl.text()

        editor.test_filename_input.setText("setup_v1.0.exe")
        assert "Applications" in editor.sandbox_result_lbl.text()


def test_dashboard_browse_and_set_folder(qapp):
    with tempfile.TemporaryDirectory() as tmpdir:
        rules_path = Path(tmpdir) / "rules.json"
        target_dir = Path(tmpdir) / "sample_folder"
        target_dir.mkdir()
        (target_dir / "invoice_1.pdf").write_text("dummy")

        window = MainWindow(str(rules_path))
        dashboard = window.dashboard_view

        # Set folder programmatically
        dashboard.set_folder(str(target_dir))
        assert dashboard.current_folder == str(target_dir)
        assert dashboard.path_input.text() == str(target_dir)

        # Trigger search & dry run
        dashboard.search_btn.click()
        assert window.view_stack.currentIndex() == 1  # Switched to Preview tab
        assert window.preview_view.current_plan is not None
        assert len(window.preview_view.current_plan.items) == 1
