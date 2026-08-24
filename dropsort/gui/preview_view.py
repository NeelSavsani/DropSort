"""Live Preview View displaying proposed actions with selective checkboxes and execution controls."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dropsort.gui.components.badges import Badge
from dropsort.models import PlanItem, PlanItemStatus, PreviewPlan


class PreviewView(QWidget):
    """Interactive Live Preview Screen before applying any file moves."""

    apply_requested = Signal()
    rescan_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.current_plan: Optional[PreviewPlan] = None
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header Title
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        main_title = QLabel("Live Preview & Staging")
        main_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f3f4f6;")
        sub_title = QLabel("Review exactly where each file will be moved before any disk changes occur")
        sub_title.setStyleSheet("font-size: 13px; color: #9ca3af;")

        title_box.addWidget(main_title)
        title_box.addWidget(sub_title)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        self.rescan_btn = QPushButton("🔄 Rescan Folder")
        self.rescan_btn.setObjectName("subtleBtn")
        self.rescan_btn.clicked.connect(self.rescan_requested.emit)
        header_layout.addWidget(self.rescan_btn)

        main_layout.addLayout(header_layout)

        # Filter & Search Bar
        filter_card = QFrame()
        filter_card.setStyleSheet("""
            QFrame {
                background-color: #18202c;
                border: 1px solid #283548;
                border-radius: 10px;
                padding: 6px 12px;
            }
        """)
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(8, 4, 8, 4)
        filter_layout.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Search by filename or path...")
        self.search_input.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.search_input, stretch=3)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Statuses", "Ready to Move", "Duplicate / Replace", "Skipped"])
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        filter_layout.addWidget(self.status_filter, stretch=1)

        # Selection shortcuts
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setObjectName("subtleBtn")
        self.select_all_btn.setFixedHeight(28)
        self.select_all_btn.clicked.connect(lambda: self._set_all_selection(True))
        filter_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setObjectName("subtleBtn")
        self.deselect_all_btn.setFixedHeight(28)
        self.deselect_all_btn.clicked.connect(lambda: self._set_all_selection(False))
        filter_layout.addWidget(self.deselect_all_btn)

        main_layout.addWidget(filter_card)

        # Table Widget
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Select",
            "File Name",
            "Target Destination",
            "Matched Rule",
            "Size",
            "Action / Status",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)

        main_layout.addWidget(self.table, stretch=1)

        # Bottom Action Bar
        action_bar = QFrame()
        action_bar.setStyleSheet("""
            QFrame {
                background-color: #18202c;
                border: 1px solid #283548;
                border-radius: 12px;
                padding: 12px 18px;
            }
        """)
        action_layout = QHBoxLayout(action_bar)
        action_layout.setContentsMargins(10, 8, 10, 8)
        action_layout.setSpacing(16)

        # Progress / Stats
        stat_box = QVBoxLayout()
        stat_box.setSpacing(4)
        self.summary_label = QLabel("No folder scanned yet.")
        self.summary_label.setStyleSheet("color: #9ca3af; font-size: 13px; background: transparent;")
        stat_box.addWidget(self.summary_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        stat_box.addWidget(self.progress_bar)

        action_layout.addLayout(stat_box, stretch=1)

        self.apply_btn = QPushButton("🚀 Apply Selected Changes")
        self.apply_btn.setObjectName("successBtn")
        self.apply_btn.setFixedHeight(40)
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.clicked.connect(self._on_apply_clicked)
        action_layout.addWidget(self.apply_btn)

        main_layout.addWidget(action_bar)

    def load_plan(self, plan: PreviewPlan) -> None:
        """Populate table with plan items."""
        self.current_plan = plan
        self._populate_table()

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        if not self.current_plan or not self.current_plan.items:
            self.summary_label.setText("No actionable files found.")
            return

        items = self.current_plan.items
        self.table.setRowCount(len(items))

        for row, item in enumerate(items):
            # Checkbox
            chk = QCheckBox()
            chk.setChecked(item.selected)
            chk.setEnabled(item.status != PlanItemStatus.SKIPPED)
            chk.stateChanged.connect(lambda state, i=item: self._on_item_check_changed(i, state))

            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.addWidget(chk)
            chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 0, chk_widget)

            # Name
            name_item = QTableWidgetItem(item.file_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, name_item)

            # Target Destination
            try:
                rel_dst = item.target_path.relative_to(self.current_plan.base_folder)
            except ValueError:
                rel_dst = item.target_path

            dest_str = f"→ {rel_dst}"
            dest_item = QTableWidgetItem(dest_str)
            dest_item.setToolTip(str(item.target_path))
            dest_item.setFlags(dest_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, dest_item)

            # Rule Name
            rule_item = QTableWidgetItem(item.rule_name)
            rule_item.setFlags(rule_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, rule_item)

            # Size
            size_item = QTableWidgetItem(item.file_size_human)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            size_item.setFlags(size_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, size_item)

            # Status Badge
            badge_variant = "success"
            status_text = "Ready"
            if item.status == PlanItemStatus.CONFLICT:
                badge_variant = "warning"
                status_text = "Replace"
            elif item.status == PlanItemStatus.SKIPPED:
                badge_variant = "muted"
                status_text = "Skipped"

            badge = Badge(status_text, badge_variant)
            badge.setToolTip(item.reason)
            badge_container = QWidget()
            b_layout = QHBoxLayout(badge_container)
            b_layout.addWidget(badge)
            b_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            b_layout.setContentsMargins(0, 0, 0, 0)
            self.table.setCellWidget(row, 5, badge_container)

        self._update_summary()

    def _on_item_check_changed(self, item: PlanItem, state: int) -> None:
        item.selected = (state == Qt.CheckState.Checked.value)
        self._update_summary()

    def _set_all_selection(self, selected: bool) -> None:
        if not self.current_plan:
            return
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget:
                chk = widget.findChild(QCheckBox)
                if chk and chk.isEnabled():
                    chk.setChecked(selected)
        for item in self.current_plan.items:
            if item.status != PlanItemStatus.SKIPPED:
                item.selected = selected
        self._update_summary()

    def _apply_filters(self) -> None:
        search_txt = self.search_input.text().lower().strip()
        status_choice = self.status_filter.currentText()

        for row in range(self.table.rowCount()):
            name_cell = self.table.item(row, 1)
            dest_cell = self.table.item(row, 2)
            rule_cell = self.table.item(row, 3)

            name = name_cell.text().lower() if name_cell else ""
            dest = dest_cell.text().lower() if dest_cell else ""
            rule = rule_cell.text().lower() if rule_cell else ""

            # Check search
            matches_search = not search_txt or (search_txt in name or search_txt in dest or search_txt in rule)

            # Check status filter
            item = self.current_plan.items[row] if self.current_plan and row < len(self.current_plan.items) else None
            matches_status = True
            if item:
                if status_filter := status_choice:
                    if status_filter == "Ready to Move":
                        matches_status = (item.status == PlanItemStatus.READY)
                    elif status_filter == "Duplicate / Replace":
                        matches_status = (item.status == PlanItemStatus.CONFLICT)
                    elif status_filter == "Skipped":
                        matches_status = (item.status == PlanItemStatus.SKIPPED)

            self.table.setRowHidden(row, not (matches_search and matches_status))

    def _update_summary(self) -> None:
        if not self.current_plan:
            return
        actionable = [it for it in self.current_plan.items if it.selected and it.status != PlanItemStatus.SKIPPED]
        total = len(self.current_plan.items)
        self.summary_label.setText(
            f"Selected <b style='color:#10b981;'>{len(actionable)}</b> of {total} files ready to organize."
        )

    def _on_apply_clicked(self) -> None:
        self.apply_requested.emit()

    def show_progress(self, current: int, total: int) -> None:
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.summary_label.setText(f"Processing: {current}/{total} files moved...")

    def hide_progress(self) -> None:
        self.progress_bar.setVisible(False)
