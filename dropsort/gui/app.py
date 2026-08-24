"""Main Application Window with sidebar navigation, view stack, and system coordination."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, QThread, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from dropsort.config import (
    get_default_rules,
    get_resource_path,
    get_user_rules_path,
    load_rules_from_file,
    load_settings,
    save_rules_to_file,
)
from dropsort.database import Database
from dropsort.gui.components.toasts import ToastNotification
from dropsort.gui.dashboard_view import DashboardView
from dropsort.gui.history_view import HistoryView
from dropsort.gui.preview_view import PreviewView
from dropsort.gui.rule_editor_view import RuleEditorView
from dropsort.gui.settings_view import SettingsView
from dropsort.gui.styles import MAIN_STYLESHEET
from dropsort.models import AppSettings, FileMetadata, PreviewPlan, Rule
from dropsort.organizer import create_preview, execute_plan, scan_folder, undo_batch
from dropsort.rule_engine import RuleEngine
from dropsort.watcher import FolderWatcher


class WatcherWorker(QObject):
    """Worker object for bridging watchdog events to Qt signals."""

    file_landed = Signal(str)

    def on_file(self, path: Path) -> None:
        self.file_landed.emit(str(path))


class MainWindow(QMainWindow):
    """Main window for DropSort."""

    def __init__(self, rules_file: Optional[str] = None) -> None:
        super().__init__()
        self.setWindowTitle("DropSort — Intelligent File Organizer")
        self.resize(1180, 760)
        self.setMinimumSize(960, 620)

        # Locate logo path (works in dev and PyInstaller exe)
        self.logo_path = get_resource_path("DropSort_logo.png")
        if not self.logo_path.exists():
            self.logo_path = get_resource_path("DropSort_logo.ico")

        if self.logo_path.exists():
            self.setWindowIcon(QIcon(str(self.logo_path)))

        # Initialize core managers
        self.database = Database()
        self.settings: AppSettings = load_settings()
        self.rules_file = rules_file or str(get_user_rules_path())
        self.rules: List[Rule] = load_rules_from_file(self.rules_file)
        self.rule_engine = RuleEngine(self.rules)

        self.current_plan: Optional[PreviewPlan] = None
        self.active_watcher: Optional[FolderWatcher] = None
        self.watcher_worker = WatcherWorker()
        self.watcher_worker.file_landed.connect(self._on_watcher_file_landed)

        self._init_ui()
        self.setStyleSheet(MAIN_STYLESHEET)

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Sidebar Navigation
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(12, 16, 12, 16)
        side_layout.setSpacing(6)

        # App Brand Header
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(10)

        if self.logo_path.exists():
            brand_icon = QLabel()
            pixmap = QPixmap(str(self.logo_path)).scaled(
                36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            brand_icon.setPixmap(pixmap)
            brand_icon.setStyleSheet("background: transparent;")
        else:
            brand_icon = QLabel("📂")
            brand_icon.setStyleSheet("font-size: 26px; background: transparent;")

        brand_layout.addWidget(brand_icon)

        brand_text_box = QVBoxLayout()
        brand_text_box.setSpacing(0)
        brand_title = QLabel("DropSort")
        brand_title.setStyleSheet("font-size: 17px; font-weight: 800; color: #f3f4f6; background: transparent;")
        brand_sub = QLabel("Smart File Organizer")
        brand_sub.setStyleSheet("font-size: 11px; color: #6366f1; font-weight: 600; background: transparent;")
        brand_text_box.addWidget(brand_title)
        brand_text_box.addWidget(brand_sub)
        brand_layout.addLayout(brand_text_box)
        brand_layout.addStretch()

        side_layout.addLayout(brand_layout)
        side_layout.addSpacing(16)

        # Nav Buttons Group
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_btns: List[QPushButton] = []

        nav_items = [
            ("🏠  Dashboard", 0),
            ("👀  Preview Changes", 1),
            ("⚙️  Sorting Rules", 2),
            ("↩️  Undo History", 3),
            ("🔧  Settings", 4),
        ]

        for text, index in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setMinimumHeight(38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if index == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda _, i=index: self._navigate_to(i))
            self.nav_group.addButton(btn, index)
            self.nav_btns.append(btn)
            side_layout.addWidget(btn)

        side_layout.addStretch()

        # Sidebar footer
        footer_lbl = QLabel("DropSort v1.0.0\nLocal & Private")
        footer_lbl.setStyleSheet("color: #4b5563; font-size: 11px; text-align: center; background: transparent;")
        side_layout.addWidget(footer_lbl)

        main_layout.addWidget(sidebar)

        # 2. Main Content Stack
        content_container = QWidget()
        content_container.setObjectName("contentArea")
        self.content_layout = QVBoxLayout(content_container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        # Toast notification container
        self.toast_container = QVBoxLayout()
        self.toast_container.setContentsMargins(20, 10, 20, 0)
        self.content_layout.addLayout(self.toast_container)

        # View Stack
        self.view_stack = QStackedWidget()

        # Views
        self.dashboard_view = DashboardView(self.database)
        self.preview_view = PreviewView()
        self.rule_editor_view = RuleEditorView(self.rules)
        self.history_view = HistoryView(self.database)
        self.settings_view = SettingsView()

        self.view_stack.addWidget(self.dashboard_view)
        self.view_stack.addWidget(self.preview_view)
        self.view_stack.addWidget(self.rule_editor_view)
        self.view_stack.addWidget(self.history_view)
        self.view_stack.addWidget(self.settings_view)

        self.content_layout.addWidget(self.view_stack, stretch=1)
        main_layout.addWidget(content_container, stretch=1)

        # Connect signals
        self._wire_signals()

    def _wire_signals(self) -> None:
        # Dashboard signals
        self.dashboard_view.scan_requested.connect(self._on_dashboard_scan)
        self.dashboard_view.organize_now_requested.connect(self._on_dashboard_organize_now)
        self.dashboard_view.undo_last_requested.connect(self._on_dashboard_undo_last)
        self.dashboard_view.watcher_toggle_requested.connect(self._on_watcher_toggle)

        # Preview signals
        self.preview_view.apply_requested.connect(self._on_preview_apply)
        self.preview_view.rescan_requested.connect(self._on_preview_rescan)

        # Rule Editor signals
        self.rule_editor_view.rules_updated.connect(self._on_rules_updated)

        # History signals
        self.history_view.history_changed.connect(self._on_history_changed)

        # Settings signals
        self.settings_view.settings_saved.connect(self._on_settings_saved)

    def _navigate_to(self, index: int) -> None:
        self.view_stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_btns):
            btn.setChecked(i == index)

    def show_toast(self, message: str, variant: str = "success") -> None:
        toast = ToastNotification(message, variant=variant, parent=self)
        self.toast_container.addWidget(toast)

    # --- Actions & Coordination ---

    def _on_dashboard_scan(self, folder_path: str) -> None:
        folder = Path(folder_path)
        if not folder.exists():
            self.show_toast(f"Folder does not exist: {folder_path}", "error")
            return

        self.dashboard_view.log_activity(f"Scanning folder: {folder_path}...", "info")
        files, ignored = scan_folder(
            folder,
            recursive=self.settings.recursive_scan,
            ignored_patterns=self.settings.ignored_patterns,
        )
        self.dashboard_view.card_scanned.set_value(len(files))

        self.current_plan = create_preview(
            files,
            self.rule_engine,
            folder,
            default_strategy=self.settings.default_on_duplicate,
        )

        self.preview_view.load_plan(self.current_plan)
        self.dashboard_view.log_activity(
            f"Scan complete. {self.current_plan.ready_count} files ready to organize.", "success"
        )
        self.show_toast(f"Found {len(files)} files ({self.current_plan.ready_count} ready to organize)", "info")
        self._navigate_to(1)  # Switch to Preview tab

    def _on_preview_rescan(self) -> None:
        if self.dashboard_view.current_folder:
            self._on_dashboard_scan(self.dashboard_view.current_folder)

    def _on_dashboard_organize_now(self, folder_path: str) -> None:
        folder = Path(folder_path)
        if not folder.exists():
            self.show_toast("Target folder not found.", "error")
            return

        files, _ = scan_folder(
            folder,
            recursive=self.settings.recursive_scan,
            ignored_patterns=self.settings.ignored_patterns,
        )
        plan = create_preview(
            files,
            self.rule_engine,
            folder,
            default_strategy=self.settings.default_on_duplicate,
        )

        if not plan.actionable_items:
            self.show_toast("No files needed organization.", "warning")
            self.dashboard_view.log_activity("No files matched organization rules.", "warning")
            return

        res = execute_plan(plan, self.database)
        if res["executed"] > 0:
            msg = f"Organized {res['executed']} files successfully!"
            self.show_toast(msg, "success")
            self.dashboard_view.log_activity(msg, "success")
            self.dashboard_view.refresh_stats()
            self.history_view.load_history()
        else:
            self.show_toast("Organization completed with 0 moves.", "warning")

    def _on_preview_apply(self) -> None:
        if not self.current_plan or not self.current_plan.actionable_items:
            self.show_toast("No files selected to organize.", "warning")
            return

        total = len(self.current_plan.actionable_items)

        def progress(cur: int, tot: int, item, success: bool, err: str) -> None:
            self.preview_view.show_progress(cur, tot)
            QApplication.processEvents()

        res = execute_plan(self.current_plan, self.database, progress_callback=progress)
        self.preview_view.hide_progress()

        if res["executed"] > 0:
            msg = f"Successfully organized {res['executed']} files!"
            self.show_toast(msg, "success")
            self.dashboard_view.log_activity(f"Organized batch {res['batch_id'][:8]}: {res['executed']} files moved.", "success")
            self.dashboard_view.refresh_stats()
            self.history_view.load_history()

            # Show completed modal with quick undo option
            reply = QMessageBox.information(
                self,
                "Changes Applied Successfully",
                f"✅ Organization Complete!\n\n"
                f"• Files Organized: {res['executed']}\n"
                f"• Batch ID: {res['batch_id']}\n\n"
                f"Would you like to keep these changes, or undo immediately?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Reset,
            )
            if reply == QMessageBox.StandardButton.Reset:
                self._on_dashboard_undo_last()
            else:
                self._on_preview_rescan()
        else:
            self.show_toast("Failed to move selected files.", "error")

    def _on_dashboard_undo_last(self) -> None:
        latest = self.database.get_latest_batch()
        if not latest or latest.status == "undone":
            self.show_toast("No active batch to undo.", "warning")
            self.dashboard_view.log_activity("No completed batch available to undo.", "warning")
            return

        res = undo_batch(latest.id, self.database, clean_empty_parents=self.settings.clean_empty_folders)
        if res["undone"] > 0:
            msg = f"Undone batch: Restored {res['undone']} files."
            self.show_toast(msg, "success")
            self.dashboard_view.log_activity(msg, "info")
            self.dashboard_view.refresh_stats()
            self.history_view.load_history()
        else:
            self.show_toast("Could not restore files (files may have been deleted).", "warning")

    def _on_watcher_toggle(self, is_active: bool, folder_path: str) -> None:
        if is_active:
            if self.active_watcher:
                self.active_watcher.stop()

            self.active_watcher = FolderWatcher(
                folder_path=Path(folder_path),
                on_file_detected=self.watcher_worker.on_file,
                debounce_seconds=self.settings.debounce_seconds,
                recursive=self.settings.recursive_scan,
                ignored_patterns=self.settings.ignored_patterns,
            )
            self.active_watcher.start()
            self.show_toast(f"Live monitoring active on {Path(folder_path).name}", "success")
        else:
            if self.active_watcher:
                self.active_watcher.stop()
                self.active_watcher = None
            self.show_toast("Live folder monitoring stopped.", "info")

    def _on_watcher_file_landed(self, file_path_str: str) -> None:
        p = Path(file_path_str)
        if not p.exists():
            return

        try:
            meta = FileMetadata.from_path(p)
            base_folder = Path(self.dashboard_view.current_folder)
            plan = create_preview([meta], self.rule_engine, base_folder, default_strategy=self.settings.default_on_duplicate)
            if plan.actionable_items:
                res = execute_plan(plan, self.database)
                if res["executed"] > 0:
                    item = plan.actionable_items[0]
                    msg = f"Auto-organized: {meta.name} → {item.target_path.parent.name}/{item.target_path.name}"
                    self.dashboard_view.log_activity(msg, "success")
                    self.dashboard_view.refresh_stats()
                    self.history_view.load_history()
                    self.show_toast(f"Auto-sorted: {meta.name}", "info")
        except Exception as e:
            self.dashboard_view.log_activity(f"Watcher error on {p.name}: {e}", "error")

    def _on_rules_updated(self) -> None:
        self.rules = self.rule_editor_view.rules
        self.rule_engine.set_rules(self.rules)
        save_rules_to_file(self.rules, self.rules_file)
        self.dashboard_view.card_rules.set_value(len(self.rules))
        self.show_toast("Rules updated and saved.", "info")

    def _on_history_changed(self) -> None:
        self.dashboard_view.refresh_stats()

    def _on_settings_saved(self) -> None:
        self.settings = self.settings_view.settings
        self.show_toast("Preferences applied successfully.", "success")

    def closeEvent(self, event) -> None:
        if self.active_watcher:
            self.active_watcher.stop()
        event.accept()


def launch_gui(rules_file: Optional[str] = None) -> None:
    """Entry point for launching the PySide6 desktop GUI."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow(rules_file)
    window.show()
    sys.exit(app.exec())
