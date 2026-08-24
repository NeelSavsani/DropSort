"""Application Settings & Configuration Preferences View."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from dropsort.config import load_settings, save_settings
from dropsort.models import AppSettings, DuplicateAction


class SettingsView(QWidget):
    """Configuration and Preferences Screen."""

    settings_saved = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings: AppSettings = load_settings()
        self._init_ui()
        self._load_values()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        main_title = QLabel("Settings & Preferences")
        main_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f3f4f6;")
        sub_title = QLabel("Configure folder watching behavior, duplicate resolution, and ignore lists")
        sub_title.setStyleSheet("font-size: 13px; color: #9ca3af;")

        title_box.addWidget(main_title)
        title_box.addWidget(sub_title)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        save_btn = QPushButton("💾 Save Preferences")
        save_btn.setObjectName("primaryBtn")
        save_btn.setFixedHeight(34)
        save_btn.clicked.connect(self._save_values)
        header_layout.addWidget(save_btn)

        main_layout.addLayout(header_layout)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        form_layout = QVBoxLayout(container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(16)

        # Group 1: General & Duplicate Behavior
        general_group = QGroupBox("General Organization Behavior")
        g_layout = QVBoxLayout(general_group)
        g_layout.setSpacing(10)

        dup_row = QHBoxLayout()
        dup_lbl = QLabel("Default Duplicate Action:")
        dup_lbl.setFixedWidth(200)
        self.dup_combo = QComboBox()
        self.dup_combo.addItems(["Rename (auto-increment)", "Replace (overwrite)", "Skip"])
        dup_row.addWidget(dup_lbl)
        dup_row.addWidget(self.dup_combo)
        dup_row.addStretch()
        g_layout.addLayout(dup_row)

        self.clean_empty_chk = QCheckBox("Automatically remove empty directories created after undo/organization")
        g_layout.addWidget(self.clean_empty_chk)

        self.recursive_chk = QCheckBox("Scan subdirectories recursively by default")
        g_layout.addWidget(self.recursive_chk)

        form_layout.addWidget(general_group)

        # Group 2: Folder Watcher & Debounce
        watcher_group = QGroupBox("Folder Monitoring & Debouncing")
        w_layout = QVBoxLayout(watcher_group)
        w_layout.setSpacing(10)

        debounce_row = QHBoxLayout()
        debounce_lbl = QLabel("Write-Lock Debounce Delay (seconds):")
        debounce_lbl.setFixedWidth(260)
        self.debounce_spin = QDoubleSpinBox()
        self.debounce_spin.setRange(0.2, 30.0)
        self.debounce_spin.setSingleStep(0.5)
        debounce_row.addWidget(debounce_lbl)
        debounce_row.addWidget(self.debounce_spin)
        debounce_row.addStretch()
        w_layout.addLayout(debounce_row)

        debounce_desc = QLabel("Waits until a file has finished downloading or writing before organizing.")
        debounce_desc.setStyleSheet("color: #9ca3af; font-size: 11px;")
        w_layout.addWidget(debounce_desc)

        form_layout.addWidget(watcher_group)

        # Group 3: Ignored File Patterns
        ignore_group = QGroupBox("Ignored File & Directory Patterns")
        i_layout = QVBoxLayout(ignore_group)
        i_layout.setSpacing(10)

        add_pat_row = QHBoxLayout()
        self.new_pat_input = QLineEdit()
        self.new_pat_input.setPlaceholderText("e.g. *.tmp, *.crdownload, .git, Thumbs.db")
        add_pat_row.addWidget(self.new_pat_input)

        add_pat_btn = QPushButton("+ Add Pattern")
        add_pat_btn.setObjectName("primaryBtn")
        add_pat_btn.clicked.connect(self._add_pattern)
        add_pat_row.addWidget(add_pat_btn)
        i_layout.addLayout(add_pat_row)

        self.pattern_list = QListWidget()
        self.pattern_list.setMaximumHeight(160)
        i_layout.addWidget(self.pattern_list)

        del_pat_btn = QPushButton("Remove Selected Pattern")
        del_pat_btn.setObjectName("dangerBtn")
        del_pat_btn.clicked.connect(self._remove_pattern)
        i_layout.addWidget(del_pat_btn)

        form_layout.addWidget(ignore_group)

        form_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll, stretch=1)

    def _load_values(self) -> None:
        dup_val = self.settings.default_on_duplicate
        if isinstance(dup_val, DuplicateAction):
            dup_str = dup_val.value
        else:
            dup_str = str(dup_val).lower()

        dup_map = {"rename": 0, "replace": 1, "skip": 2}
        self.dup_combo.setCurrentIndex(dup_map.get(dup_str, 0))

        self.clean_empty_chk.setChecked(self.settings.clean_empty_folders)
        self.recursive_chk.setChecked(self.settings.recursive_scan)
        self.debounce_spin.setValue(self.settings.debounce_seconds)

        self.pattern_list.clear()
        for pat in self.settings.ignored_patterns:
            self.pattern_list.addItem(QListWidgetItem(pat))

    def _add_pattern(self) -> None:
        pat = self.new_pat_input.text().strip()
        if pat:
            self.pattern_list.addItem(QListWidgetItem(pat))
            self.new_pat_input.clear()

    def _remove_pattern(self) -> None:
        row = self.pattern_list.currentRow()
        if row >= 0:
            item = self.pattern_list.takeItem(row)
            del item

    def _save_values(self) -> None:
        dup_opts = [DuplicateAction.RENAME, DuplicateAction.REPLACE, DuplicateAction.SKIP]
        self.settings.default_on_duplicate = dup_opts[self.dup_combo.currentIndex()]
        self.settings.clean_empty_folders = self.clean_empty_chk.isChecked()
        self.settings.recursive_scan = self.recursive_chk.isChecked()
        self.settings.debounce_seconds = self.debounce_spin.value()

        patterns: list[str] = []
        for r in range(self.pattern_list.count()):
            patterns.append(self.pattern_list.item(r).text())
        self.settings.ignored_patterns = patterns

        save_settings(self.settings)
        self.settings_saved.emit()
        QMessageBox.information(self, "Settings Saved", "Your configuration preferences have been saved successfully!")
