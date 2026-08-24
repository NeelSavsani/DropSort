"""History and 1-Click Undo Management View."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dropsort.database import Database
from dropsort.gui.components.badges import Badge
from dropsort.models import MoveRecordStatus
from dropsort.organizer import undo_batch, undo_move_record


class HistoryView(QWidget):
    """History log viewer and 1-Click Undo management screen."""

    history_changed = Signal()

    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        self._init_ui()
        self.load_history()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        main_title = QLabel("History & Undo")
        main_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f3f4f6;")
        sub_title = QLabel("See all past file moves and restore any files back to their original places with 1 click.")
        sub_title.setStyleSheet("font-size: 13px; color: #9ca3af;")

        title_box.addWidget(main_title)
        title_box.addWidget(sub_title)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        refresh_btn = QPushButton("🔄 Refresh List")
        refresh_btn.setObjectName("subtleBtn")
        refresh_btn.setMinimumHeight(32)
        refresh_btn.clicked.connect(self.load_history)
        header_layout.addWidget(refresh_btn)

        main_layout.addLayout(header_layout)

        # Filter Bar
        filter_card = QFrame()
        filter_card.setStyleSheet("""
            QFrame {
                background-color: #18202c;
                border: 1px solid #283548;
                border-radius: 10px;
                padding: 8px 12px;
            }
        """)
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(8, 4, 8, 4)
        filter_layout.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter history by file name...")
        self.search_input.setMinimumHeight(32)
        self.search_input.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.search_input, stretch=3)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Moves", "Completed", "Undone", "Failed"])
        self.status_filter.setMinimumHeight(32)
        self.status_filter.currentIndexChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.status_filter, stretch=1)

        main_layout.addWidget(filter_card)

        # Tabs for Batch View vs All Moves View
        self.tabs = QTabWidget()

        # Tab 1: Organization Batches
        batch_tab = QWidget()
        b_layout = QVBoxLayout(batch_tab)
        b_layout.setContentsMargins(0, 8, 0, 0)

        self.batches_table = QTableWidget()
        self.batches_table.setColumnCount(6)
        self.batches_table.setHorizontalHeaderLabels([
            "Time",
            "Batch ID",
            "Folder",
            "Files Moved",
            "Status",
            "Action",
        ])
        self.batches_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.batches_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.batches_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.batches_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.batches_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.batches_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.batches_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.batches_table.setAlternatingRowColors(True)
        b_layout.addWidget(self.batches_table)
        self.tabs.addTab(batch_tab, "📦 Organization Batches")

        # Tab 2: Individual File Moves
        moves_tab = QWidget()
        m_layout = QVBoxLayout(moves_tab)
        m_layout.setContentsMargins(0, 8, 0, 0)

        self.moves_table = QTableWidget()
        self.moves_table.setColumnCount(6)
        self.moves_table.setHorizontalHeaderLabels([
            "Time",
            "Original File Name",
            "Moved To",
            "Rule Matched",
            "Status",
            "Action",
        ])
        self.moves_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.moves_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.moves_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.moves_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.moves_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.moves_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.moves_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.moves_table.setAlternatingRowColors(True)
        m_layout.addWidget(self.moves_table)
        self.tabs.addTab(moves_tab, "📄 Individual File Moves")

        main_layout.addWidget(self.tabs, stretch=1)

    def load_history(self) -> None:
        """Fetch records from database and update tables."""
        # Load Batches
        batches = self.database.get_batches(limit=50)
        self.batches_table.setRowCount(len(batches))

        for row, b in enumerate(batches):
            # Timestamp
            ts_str = b.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            ts_item = QTableWidgetItem(ts_str)
            self.batches_table.setItem(row, 0, ts_item)

            # Batch ID
            id_item = QTableWidgetItem(b.id[:8] + "...")
            id_item.setToolTip(b.id)
            self.batches_table.setItem(row, 1, id_item)

            # Folder
            folder_item = QTableWidgetItem(Path(b.target_folder).name)
            folder_item.setToolTip(b.target_folder)
            self.batches_table.setItem(row, 2, folder_item)

            # Count
            count_str = f"{b.total_moves} files"
            if b.undone_count > 0:
                count_str += f" ({b.undone_count} undone)"
            count_item = QTableWidgetItem(count_str)
            self.batches_table.setItem(row, 3, count_item)

            # Status
            status_variant = "success" if b.status == "completed" else "muted"
            status_badge = Badge(b.status.upper(), status_variant)
            s_widget = QWidget()
            s_layout = QHBoxLayout(s_widget)
            s_layout.addWidget(status_badge)
            s_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s_layout.setContentsMargins(0, 0, 0, 0)
            self.batches_table.setCellWidget(row, 4, s_widget)

            # Undo Batch Action Button
            undo_btn = QPushButton("↩️ Undo All")
            undo_btn.setObjectName("dangerBtn" if b.status == "completed" else "subtleBtn")
            undo_btn.setEnabled(b.status == "completed")
            undo_btn.setMinimumHeight(28)
            undo_btn.setMinimumWidth(100)
            undo_btn.clicked.connect(lambda _, bid=b.id: self._undo_batch_clicked(bid))

            a_widget = QWidget()
            a_layout = QHBoxLayout(a_widget)
            a_layout.addWidget(undo_btn)
            a_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            a_layout.setContentsMargins(0, 0, 0, 0)
            self.batches_table.setCellWidget(row, 5, a_widget)

        # Load Moves
        moves = self.database.get_history(limit=100)
        self.moves_table.setRowCount(len(moves))

        for row, m in enumerate(moves):
            # Timestamp
            ts_str = m.timestamp.strftime("%H:%M:%S")
            ts_item = QTableWidgetItem(ts_str)
            self.moves_table.setItem(row, 0, ts_item)

            # Original
            orig_item = QTableWidgetItem(Path(m.original_path).name)
            orig_item.setToolTip(m.original_path)
            self.moves_table.setItem(row, 1, orig_item)

            # Target
            target_item = QTableWidgetItem(f"→ {Path(m.target_path).parent.name}/{Path(m.target_path).name}")
            target_item.setToolTip(m.target_path)
            self.moves_table.setItem(row, 2, target_item)

            # Rule
            rule_item = QTableWidgetItem(m.rule_name)
            self.moves_table.setItem(row, 3, rule_item)

            # Status
            stat_str = m.status.value if isinstance(m.status, MoveRecordStatus) else str(m.status)
            variant = "success" if stat_str == "completed" else ("muted" if stat_str == "undone" else "danger")
            badge = Badge(stat_str.upper(), variant)
            b_widget = QWidget()
            b_layout = QHBoxLayout(b_widget)
            b_layout.addWidget(badge)
            b_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b_layout.setContentsMargins(0, 0, 0, 0)
            self.moves_table.setCellWidget(row, 4, b_widget)

            # Undo 1-Click Button
            undo_btn = QPushButton("↩️ Undo")
            undo_btn.setObjectName("dangerBtn" if stat_str == "completed" else "subtleBtn")
            undo_btn.setEnabled(stat_str == "completed")
            undo_btn.setMinimumHeight(28)
            undo_btn.setMinimumWidth(80)
            undo_btn.clicked.connect(lambda _, mid=m.id: self._undo_single_move(mid))

            a_widget = QWidget()
            a_layout = QHBoxLayout(a_widget)
            a_layout.addWidget(undo_btn)
            a_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            a_layout.setContentsMargins(0, 0, 0, 0)
            self.moves_table.setCellWidget(row, 5, a_widget)

    def _undo_batch_clicked(self, batch_id: str) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Batch Undo",
            f"Are you sure you want to reverse all file moves in batch:\n{batch_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            res = undo_batch(batch_id, self.database)
            if res["undone"] > 0:
                QMessageBox.information(self, "Undo Success", f"Successfully restored {res['undone']} files back to their original locations!")
            else:
                QMessageBox.warning(self, "Undo Warning", "No files could be restored (they may have been deleted or moved).")
            self.load_history()
            self.history_changed.emit()

    def _undo_single_move(self, move_id: str) -> None:
        success, msg = undo_move_record(move_id, self.database)
        if success:
            QMessageBox.information(self, "Undo Success", msg)
        else:
            QMessageBox.critical(self, "Undo Failed", msg)
        self.load_history()
        self.history_changed.emit()

    def _apply_filter(self) -> None:
        search_txt = self.search_input.text().lower().strip()
        status_filter = self.status_filter.currentText().lower()

        # Filter moves table
        for row in range(self.moves_table.rowCount()):
            orig = self.moves_table.item(row, 1).text().lower() if self.moves_table.item(row, 1) else ""
            target = self.moves_table.item(row, 2).text().lower() if self.moves_table.item(row, 2) else ""
            rule = self.moves_table.item(row, 3).text().lower() if self.moves_table.item(row, 3) else ""

            matches_search = not search_txt or (search_txt in orig or search_txt in target or search_txt in rule)
            
            matches_status = True
            if status_filter != "all moves":
                # Check status text
                badge_widget = self.moves_table.cellWidget(row, 4)
                if badge_widget:
                    b = badge_widget.findChild(Badge)
                    if b:
                        matches_status = (b.text().lower() == status_filter)

            self.moves_table.setRowHidden(row, not (matches_search and matches_status))
