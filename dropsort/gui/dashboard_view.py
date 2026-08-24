"""Dashboard view containing folder selection, live monitoring toggle, KPI cards, and activity feed."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from dropsort.database import Database
from dropsort.gui.components.badges import Badge
from dropsort.gui.components.cards import StatCard
from dropsort.gui.components.drop_zone import DropZone


class DashboardView(QWidget):
    """Main Dashboard overview tab."""

    scan_requested = Signal(str)
    organize_now_requested = Signal(str)
    undo_last_requested = Signal()
    watcher_toggle_requested = Signal(bool, str)

    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        self.current_folder: str = ""
        self.is_watching = False

        self._init_ui()
        self.refresh_stats()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(20)

        # Header Section
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        main_title = QLabel("Dashboard")
        main_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f3f4f6;")
        sub_title = QLabel("Organize your files cleanly into folders in 3 easy steps.")
        sub_title.setStyleSheet("font-size: 13px; color: #9ca3af;")

        title_box.addWidget(main_title)
        title_box.addWidget(sub_title)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Watcher Status Banner & Toggle
        self.watcher_card = QFrame()
        self.watcher_card.setStyleSheet("""
            QFrame {
                background-color: #18202c;
                border: 1px solid #283548;
                border-radius: 10px;
                padding: 6px 12px;
            }
        """)
        watcher_layout = QHBoxLayout(self.watcher_card)
        watcher_layout.setContentsMargins(10, 6, 10, 6)
        watcher_layout.setSpacing(12)

        self.watch_status_badge = Badge("AUTO-WATCH OFF", "muted")
        watcher_layout.addWidget(self.watch_status_badge)

        self.toggle_watch_btn = QPushButton("Turn On Auto-Watch")
        self.toggle_watch_btn.setObjectName("primaryBtn")
        self.toggle_watch_btn.setMinimumHeight(32)
        self.toggle_watch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_watch_btn.clicked.connect(self._toggle_watcher)
        watcher_layout.addWidget(self.toggle_watch_btn)

        header_layout.addWidget(self.watcher_card)
        main_layout.addLayout(header_layout)

        # KPI Stat Cards Row
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(14)

        self.card_scanned = StatCard("Files Found", "0", "In selected folder", icon="📁", accent_color="#6366f1")
        self.card_organized = StatCard("Files Moved Today", "0", "Organized cleanly", icon="✨", accent_color="#10b981")
        self.card_rules = StatCard("Sorting Rules", "9", "Active filters", icon="⚙️", accent_color="#38bdf8")
        self.card_undone = StatCard("Undo Sessions", "0", "1-click undo ready", icon="↩️", accent_color="#f59e0b")

        kpi_layout.addWidget(self.card_scanned)
        kpi_layout.addWidget(self.card_organized)
        kpi_layout.addWidget(self.card_rules)
        kpi_layout.addWidget(self.card_undone)

        main_layout.addLayout(kpi_layout)

        # Step 1 & 2 Workflow Banner / Path Selector
        workflow_card = QFrame()
        workflow_card.setObjectName("workflowCard")
        workflow_card.setStyleSheet("""
            QFrame#workflowCard {
                background-color: #18202c;
                border: 1px solid #283548;
                border-radius: 12px;
                padding: 14px 18px;
            }
        """)
        wf_layout = QVBoxLayout(workflow_card)
        wf_layout.setContentsMargins(12, 12, 12, 12)
        wf_layout.setSpacing(10)

        wf_title_row = QHBoxLayout()
        wf_step_lbl = QLabel("1️⃣ Step 1: Choose a Folder    ➔    2️⃣ Step 2: Click 'Search' to Test Safely")
        wf_step_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #818cf8; background: transparent;")
        wf_title_row.addWidget(wf_step_lbl)
        wf_title_row.addStretch()
        wf_layout.addLayout(wf_title_row)

        path_selector_row = QHBoxLayout()
        path_selector_row.setSpacing(10)

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Choose a folder to organize (e.g. Downloads, Documents)...")
        self.path_input.setMinimumHeight(38)
        self.path_input.textChanged.connect(self._on_path_input_changed)
        path_selector_row.addWidget(self.path_input, stretch=4)

        self.browse_btn = QPushButton("📁 Choose Folder...")
        self.browse_btn.setObjectName("subtleBtn")
        self.browse_btn.setMinimumHeight(38)
        self.browse_btn.setMinimumWidth(140)
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.clicked.connect(self._open_browse_dialog)
        path_selector_row.addWidget(self.browse_btn)

        self.search_btn = QPushButton("🔍 Search and Preview")
        self.search_btn.setObjectName("primaryBtn")
        self.search_btn.setMinimumHeight(38)
        self.search_btn.setMinimumWidth(180)
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.clicked.connect(self._on_preview_clicked)
        path_selector_row.addWidget(self.search_btn)

        wf_layout.addLayout(path_selector_row)
        main_layout.addWidget(workflow_card)

        # Middle Row: DropZone and Quick Action Panel
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(16)

        # Drop Zone (Folder selection)
        self.drop_zone = DropZone()
        self.drop_zone.folder_selected.connect(self.set_folder)
        middle_layout.addWidget(self.drop_zone, stretch=3)

        # Quick Actions Card
        actions_card = QFrame()
        actions_card.setObjectName("actionsCard")
        actions_card.setStyleSheet("""
            QFrame#actionsCard {
                background-color: #18202c;
                border: 1px solid #283548;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        act_layout = QVBoxLayout(actions_card)
        act_layout.setContentsMargins(14, 14, 14, 14)
        act_layout.setSpacing(12)

        act_title = QLabel("Quick Actions")
        act_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f3f4f6; background: transparent;")
        act_layout.addWidget(act_title)

        self.preview_btn = QPushButton("🔍 Search and Preview")
        self.preview_btn.setObjectName("primaryBtn")
        self.preview_btn.setMinimumHeight(38)
        self.preview_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.preview_btn.clicked.connect(self._on_preview_clicked)
        act_layout.addWidget(self.preview_btn)

        self.organize_btn = QPushButton("⚡ Move Files Now")
        self.organize_btn.setObjectName("successBtn")
        self.organize_btn.setMinimumHeight(38)
        self.organize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.organize_btn.clicked.connect(self._on_organize_clicked)
        act_layout.addWidget(self.organize_btn)

        self.undo_btn = QPushButton("↩️ Put Files Back (Undo)")
        self.undo_btn.setObjectName("subtleBtn")
        self.undo_btn.setMinimumHeight(38)
        self.undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.clicked.connect(self._on_undo_clicked)
        act_layout.addWidget(self.undo_btn)

        act_layout.addStretch()
        middle_layout.addWidget(actions_card, stretch=2)

        main_layout.addLayout(middle_layout)

        # Bottom Section: Activity Feed
        feed_box = QFrame()
        feed_box.setStyleSheet("""
            QFrame {
                background-color: #18202c;
                border: 1px solid #283548;
                border-radius: 12px;
                padding: 14px;
            }
        """)
        feed_layout = QVBoxLayout(feed_box)
        feed_layout.setContentsMargins(12, 12, 12, 12)
        feed_layout.setSpacing(8)

        feed_header = QHBoxLayout()
        feed_title = QLabel("Live Activity Stream")
        feed_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #f3f4f6; background: transparent;")
        feed_header.addWidget(feed_title)
        feed_header.addStretch()

        clear_feed_btn = QPushButton("Clear Log")
        clear_feed_btn.setObjectName("subtleBtn")
        clear_feed_btn.setMinimumHeight(30)
        clear_feed_btn.setMinimumWidth(90)
        clear_feed_btn.clicked.connect(self._clear_activity)
        feed_header.addWidget(clear_feed_btn)

        feed_layout.addLayout(feed_header)

        self.activity_list = QListWidget()
        self.activity_list.setStyleSheet("""
            QListWidget {
                background-color: #131b26;
                border: 1px solid #283548;
                border-radius: 8px;
                padding: 6px;
                color: #e5e7eb;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #1e293b;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #1e293b;
            }
        """)
        feed_layout.addWidget(self.activity_list)

        main_layout.addWidget(feed_box, stretch=2)

        # Initial message
        self.log_activity("DropSort initialized. Select a folder to begin organizing.", "info")

    def _open_browse_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Target Folder to Organize")
        if folder:
            self.set_folder(folder)

    def _on_path_input_changed(self, text: str) -> None:
        if getattr(self, "_is_updating_path", False):
            return
        p = Path(text.strip())
        if p.exists() and p.is_dir():
            self._is_updating_path = True
            try:
                self.current_folder = str(p.resolve())
                self.drop_zone.set_folder(self.current_folder)
            finally:
                self._is_updating_path = False

    def set_folder(self, folder: str) -> None:
        if getattr(self, "_is_updating_path", False):
            return
        self._is_updating_path = True
        try:
            self.current_folder = folder
            if self.path_input.text() != folder:
                self.path_input.setText(folder)
            self.drop_zone.set_folder(folder)
            self.log_activity(f"Selected target folder: {folder}", "info")
        finally:
            self._is_updating_path = False

    def _toggle_watcher(self) -> None:
        if not self.current_folder:
            self.log_activity("Please select a target folder first before starting watcher.", "warning")
            return

        self.is_watching = not self.is_watching
        if self.is_watching:
            self.watch_status_badge.set_badge("WATCHING ACTIVE", "success")
            self.toggle_watch_btn.setText("Stop Live Watch")
            self.toggle_watch_btn.setObjectName("dangerBtn")
            self.toggle_watch_btn.setStyle(self.toggle_watch_btn.style())
            self.log_activity(f"Live folder watching started on: {self.current_folder}", "success")
        else:
            self.watch_status_badge.set_badge("IDLE", "muted")
            self.toggle_watch_btn.setText("Start Live Watch")
            self.toggle_watch_btn.setObjectName("primaryBtn")
            self.toggle_watch_btn.setStyle(self.toggle_watch_btn.style())
            self.log_activity("Live folder watching stopped.", "info")

        self.watcher_toggle_requested.emit(self.is_watching, self.current_folder)

    def _on_preview_clicked(self) -> None:
        if not self.current_folder:
            self.log_activity("Please select a folder to scan.", "warning")
            return
        self.scan_requested.emit(self.current_folder)

    def _on_organize_clicked(self) -> None:
        if not self.current_folder:
            self.log_activity("Please select a folder to organize.", "warning")
            return
        self.organize_now_requested.emit(self.current_folder)

    def _on_undo_clicked(self) -> None:
        self.undo_last_requested.emit()

    def log_activity(self, message: str, level: str = "info") -> None:
        t = time.strftime("%H:%M:%S")
        prefix = {
            "info": "ℹ️",
            "success": "✨",
            "warning": "⚠️",
            "error": "❌",
        }.get(level, "•")

        item_text = f"[{t}] {prefix} {message}"
        item = QListWidgetItem(item_text)
        if level == "success":
            item.setForeground(Qt.GlobalColor.green)
        elif level == "warning":
            item.setForeground(Qt.GlobalColor.yellow)
        elif level == "error":
            item.setForeground(Qt.GlobalColor.red)
        
        self.activity_list.insertItem(0, item)

    def _clear_activity(self) -> None:
        self.activity_list.clear()

    def refresh_stats(self) -> None:
        """Update KPI stats from SQLite DB."""
        stats = self.database.get_stats_today()
        self.card_organized.set_value(stats["organized_today"])
        self.card_undone.set_value(stats["batches_today"])
