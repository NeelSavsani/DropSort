"""Visual Rule Editor with priority ordering, condition builder, variable tokens, and live sandbox tester."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from dropsort.config import get_default_rules, load_rules_from_file, save_rules_to_file
from dropsort.gui.components.badges import Badge
from dropsort.models import (
    Action,
    Condition,
    ConditionField,
    ConditionGroup,
    ConditionOp,
    DuplicateAction,
    FileActionType,
    FileCategory,
    FileMetadata,
    LogicalOp,
    Rule,
)
from dropsort.rule_engine import RuleEngine


class ConditionRowWidget(QWidget):
    """Row widget for editing a single condition."""

    deleted = Signal(object)

    def __init__(self, condition: Optional[Condition] = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.condition = condition or Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "pdf")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)

        # Field
        self.field_combo = QComboBox()
        self.field_combo.addItems([
            "extension",
            "filename",
            "filename_regex",
            "filename_glob",
            "file_type",
            "size_bytes",
            "date_modified",
        ])
        curr_field = self.condition.field.value if isinstance(self.condition.field, ConditionField) else str(self.condition.field)
        self.field_combo.setCurrentText(curr_field)
        self.field_combo.currentTextChanged.connect(self._on_field_changed)
        layout.addWidget(self.field_combo, stretch=2)

        # Operator
        self.op_combo = QComboBox()
        self._populate_operators(self.field_combo.currentText())
        curr_op = self.condition.operator.value if isinstance(self.condition.operator, ConditionOp) else str(self.condition.operator)
        self.op_combo.setCurrentText(curr_op)
        layout.addWidget(self.op_combo, stretch=2)

        # Value input
        self.val_input = QLineEdit()
        val_str = ", ".join(self.condition.value) if isinstance(self.condition.value, list) else str(self.condition.value)
        self.val_input.setText(val_str)
        layout.addWidget(self.val_input, stretch=3)

        # Delete button
        del_btn = QPushButton("✕")
        del_btn.setObjectName("dangerBtn")
        del_btn.setFixedSize(28, 28)
        del_btn.clicked.connect(lambda: self.deleted.emit(self))
        layout.addWidget(del_btn)

    def _populate_operators(self, field_name: str) -> None:
        self.op_combo.clear()
        if field_name == "extension":
            self.op_combo.addItems(["equals", "not_equals", "in_list", "not_in_list"])
        elif field_name == "filename":
            self.op_combo.addItems(["contains", "not_contains", "starts_with", "ends_with", "equals", "matches_regex", "matches_glob"])
        elif field_name in ("filename_regex", "filename_glob"):
            self.op_combo.addItems(["matches_regex" if field_name == "filename_regex" else "matches_glob"])
        elif field_name == "file_type":
            self.op_combo.addItems(["equals", "not_equals", "in_list"])
        elif field_name == "size_bytes":
            self.op_combo.addItems(["greater_than", "less_than", "equals"])
        elif field_name in ("date_modified", "date_created"):
            self.op_combo.addItems(["within_days", "before_date", "after_date", "equals"])

    def _on_field_changed(self, field_name: str) -> None:
        self._populate_operators(field_name)

    def get_condition(self) -> Condition:
        field_str = self.field_combo.currentText()
        op_str = self.op_combo.currentText()
        val_str = self.val_input.text().strip()

        if op_str in ("in_list", "not_in_list"):
            val: Any = [x.strip() for x in val_str.split(",") if x.strip()]
        else:
            val = val_str

        return Condition(
            field=ConditionField(field_str) if field_str in ConditionField.__members__.values() else field_str,
            operator=ConditionOp(op_str) if op_str in ConditionOp.__members__.values() else op_str,
            value=val,
        )


class RuleEditorView(QWidget):
    """Rule Management View with Visual Builder and Live Tester."""

    rules_updated = Signal()

    def __init__(self, rules: Optional[List[Rule]] = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rules: List[Rule] = rules if rules is not None else get_default_rules()
        self.selected_rule_index: int = 0
        self.condition_rows: List[ConditionRowWidget] = []

        self._init_ui()
        self._load_rule_list()
        if self.rules:
            self._display_rule(0)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        main_title = QLabel("Rule Engine & Logic Builder")
        main_title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f3f4f6;")
        sub_title = QLabel("Construct multi-condition rules, rearrange priorities, and test patterns live")
        sub_title.setStyleSheet("font-size: 13px; color: #9ca3af;")

        title_box.addWidget(main_title)
        title_box.addWidget(sub_title)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Import / Export
        import_btn = QPushButton("📂 Import Rules")
        import_btn.setObjectName("subtleBtn")
        import_btn.clicked.connect(self._import_rules)
        header_layout.addWidget(import_btn)

        export_btn = QPushButton("💾 Export Rules")
        export_btn.setObjectName("subtleBtn")
        export_btn.clicked.connect(self._export_rules)
        header_layout.addWidget(export_btn)

        main_layout.addLayout(header_layout)

        # Splitter Layout (Left: Rules List, Right: Rule Details / Builder)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Column: Rules List
        left_panel = QFrame()
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #18202c;
                border: 1px solid #283548;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)

        left_header = QHBoxLayout()
        rules_lbl = QLabel("Active Rules (Priority Order)")
        rules_lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #f3f4f6; background: transparent;")
        left_header.addWidget(rules_lbl)
        left_header.addStretch()

        add_rule_btn = QPushButton("+ New")
        add_rule_btn.setObjectName("primaryBtn")
        add_rule_btn.setFixedHeight(26)
        add_rule_btn.clicked.connect(self._add_new_rule)
        left_header.addWidget(add_rule_btn)

        left_layout.addLayout(left_header)

        self.rule_list_widget = QListWidget()
        self.rule_list_widget.currentRowChanged.connect(self._on_rule_selected)
        left_layout.addWidget(self.rule_list_widget)

        # Priority Reorder buttons
        reorder_layout = QHBoxLayout()
        self.move_up_btn = QPushButton("▲ Move Up")
        self.move_up_btn.setObjectName("subtleBtn")
        self.move_up_btn.clicked.connect(self._move_rule_up)
        reorder_layout.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("▼ Move Down")
        self.move_down_btn.setObjectName("subtleBtn")
        self.move_down_btn.clicked.connect(self._move_rule_down)
        reorder_layout.addWidget(self.move_down_btn)

        self.delete_rule_btn = QPushButton("🗑 Delete")
        self.delete_rule_btn.setObjectName("dangerBtn")
        self.delete_rule_btn.clicked.connect(self._delete_current_rule)
        reorder_layout.addWidget(self.delete_rule_btn)

        left_layout.addLayout(reorder_layout)
        splitter.addWidget(left_panel)

        # Right Column: Visual Builder & Sandbox
        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #18202c;
                border: 1px solid #283548;
                border-radius: 12px;
                padding: 14px;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(14, 14, 14, 14)
        right_layout.setSpacing(12)

        # Scroll Area for Rule Details
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        builder_container = QWidget()
        self.builder_layout = QVBoxLayout(builder_container)
        self.builder_layout.setContentsMargins(0, 0, 0, 0)
        self.builder_layout.setSpacing(12)

        # Basic Info Row
        info_group = QGroupBox("Rule Information")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(8)

        name_row = QHBoxLayout()
        name_lbl = QLabel("Rule Name:")
        name_lbl.setFixedWidth(80)
        self.rule_name_input = QLineEdit()
        self.rule_name_input.textChanged.connect(self._on_rule_edited)
        name_row.addWidget(name_lbl)
        name_row.addWidget(self.rule_name_input)

        self.rule_enabled_chk = QPushButton("Enabled")
        self.rule_enabled_chk.setCheckable(True)
        self.rule_enabled_chk.setChecked(True)
        self.rule_enabled_chk.setObjectName("successBtn")
        self.rule_enabled_chk.toggled.connect(self._on_rule_edited)
        name_row.addWidget(self.rule_enabled_chk)

        info_layout.addLayout(name_row)

        desc_row = QHBoxLayout()
        desc_lbl = QLabel("Description:")
        desc_lbl.setFixedWidth(80)
        self.rule_desc_input = QLineEdit()
        self.rule_desc_input.textChanged.connect(self._on_rule_edited)
        desc_row.addWidget(desc_lbl)
        desc_row.addWidget(self.rule_desc_input)
        info_layout.addLayout(desc_row)

        self.builder_layout.addWidget(info_group)

        # Conditions Group
        self.cond_group = QGroupBox("Match Conditions (WHEN)")
        self.cond_layout = QVBoxLayout(self.cond_group)
        self.cond_layout.setSpacing(8)

        cond_header = QHBoxLayout()
        cond_logic_lbl = QLabel("Combine conditions using:")
        self.logic_combo = QComboBox()
        self.logic_combo.addItems(["ALL conditions must match (AND)", "ANY condition can match (OR)"])
        self.logic_combo.currentIndexChanged.connect(self._on_rule_edited)
        cond_header.addWidget(cond_logic_lbl)
        cond_header.addWidget(self.logic_combo)
        cond_header.addStretch()

        add_cond_btn = QPushButton("+ Add Condition")
        add_cond_btn.setObjectName("primaryBtn")
        add_cond_btn.setFixedHeight(26)
        add_cond_btn.clicked.connect(self._add_condition_row)
        cond_header.addWidget(add_cond_btn)

        self.cond_layout.addLayout(cond_header)

        self.cond_rows_container = QVBoxLayout()
        self.cond_rows_container.setSpacing(4)
        self.cond_layout.addLayout(self.cond_rows_container)

        self.builder_layout.addWidget(self.cond_group)

        # Action / Destination Group
        action_group = QGroupBox("Destination & Behavior (THEN)")
        action_layout = QVBoxLayout(action_group)
        action_layout.setSpacing(8)

        dest_row = QHBoxLayout()
        dest_lbl = QLabel("Destination:")
        dest_lbl.setFixedWidth(80)
        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("e.g. Documents/Invoices/{year}/")
        self.dest_input.textChanged.connect(self._on_rule_edited)
        dest_row.addWidget(dest_lbl)
        dest_row.addWidget(self.dest_input)
        action_layout.addLayout(dest_row)

        # Variable Token Chips
        tokens_layout = QHBoxLayout()
        tokens_layout.setSpacing(6)
        token_lbl = QLabel("Insert Token:")
        token_lbl.setStyleSheet("color: #9ca3af; font-size: 11px;")
        tokens_layout.addWidget(token_lbl)

        tokens = ["{year}", "{month}", "{ext}", "{category}", "{date}", "{base_name}"]
        for tok in tokens:
            chip_btn = QPushButton(tok)
            chip_btn.setObjectName("subtleBtn")
            chip_btn.setFixedHeight(24)
            chip_btn.setStyleSheet("font-size: 11px; padding: 2px 6px;")
            chip_btn.clicked.connect(lambda _, t=tok: self._insert_token(t))
            tokens_layout.addWidget(chip_btn)

        tokens_layout.addStretch()
        action_layout.addLayout(tokens_layout)

        # Duplicate handling & action type
        options_row = QHBoxLayout()
        dup_lbl = QLabel("On Duplicate:")
        self.dup_combo = QComboBox()
        self.dup_combo.addItems(["Rename (auto-increment)", "Replace (overwrite)", "Skip"])
        self.dup_combo.currentIndexChanged.connect(self._on_rule_edited)
        options_row.addWidget(dup_lbl)
        options_row.addWidget(self.dup_combo)

        act_type_lbl = QLabel("Operation:")
        self.act_type_combo = QComboBox()
        self.act_type_combo.addItems(["Move File", "Copy File"])
        self.act_type_combo.currentIndexChanged.connect(self._on_rule_edited)
        options_row.addWidget(act_type_lbl)
        options_row.addWidget(self.act_type_combo)

        action_layout.addLayout(options_row)
        self.builder_layout.addWidget(action_group)

        # Save Button
        save_bar = QHBoxLayout()
        save_bar.addStretch()
        self.save_rule_btn = QPushButton("💾 Save Changes to Rule")
        self.save_rule_btn.setObjectName("primaryBtn")
        self.save_rule_btn.setFixedHeight(34)
        self.save_rule_btn.clicked.connect(self._save_current_rule)
        save_bar.addWidget(self.save_rule_btn)
        self.builder_layout.addLayout(save_bar)

        scroll_area.setWidget(builder_container)
        right_layout.addWidget(scroll_area, stretch=1)

        # Rule Sandbox Tester at Bottom
        sandbox_group = QGroupBox("🧪 Live Rule Sandbox Tester")
        sandbox_layout = QVBoxLayout(sandbox_group)
        sandbox_layout.setSpacing(8)

        test_row = QHBoxLayout()
        self.test_filename_input = QLineEdit()
        self.test_filename_input.setPlaceholderText("Type a sample filename e.g. invoice_august_2026.pdf, IMG_1234.jpg...")
        self.test_filename_input.textChanged.connect(self._run_sandbox_test)
        test_row.addWidget(self.test_filename_input)
        sandbox_layout.addLayout(test_row)

        self.sandbox_result_lbl = QLabel("Enter a filename above to test rule matching in real-time.")
        self.sandbox_result_lbl.setStyleSheet("color: #9ca3af; font-size: 12px; padding: 4px;")
        sandbox_layout.addWidget(self.sandbox_result_lbl)

        right_layout.addWidget(sandbox_group)

        splitter.addWidget(right_panel)
        splitter.setSizes([260, 600])

        main_layout.addWidget(splitter, stretch=1)

    def _load_rule_list(self) -> None:
        self.rule_list_widget.clear()
        self.rules.sort(key=lambda r: r.priority)
        for idx, rule in enumerate(self.rules, start=1):
            rule.priority = idx * 10
            status_dot = "🟢" if rule.enabled else "⚪"
            item_text = f"{idx}. {status_dot} {rule.name}"
            item = QListWidgetItem(item_text)
            self.rule_list_widget.addItem(item)

        if self.rules:
            self.rule_list_widget.setCurrentRow(0)

    def _display_rule(self, index: int) -> None:
        if index < 0 or index >= len(self.rules):
            return
        self.selected_rule_index = index
        rule = self.rules[index]

        self.rule_name_input.setText(rule.name)
        self.rule_desc_input.setText(rule.description)
        self.rule_enabled_chk.setChecked(rule.enabled)
        self.rule_enabled_chk.setText("Enabled" if rule.enabled else "Disabled")

        # Logic
        log_op = (
            rule.conditions.logical_operator.value
            if isinstance(rule.conditions.logical_operator, LogicalOp)
            else str(rule.conditions.logical_operator)
        )
        self.logic_combo.setCurrentIndex(0 if log_op == "AND" else 1)

        # Clear condition rows
        for row_widget in self.condition_rows:
            self.cond_rows_container.removeWidget(row_widget)
            row_widget.deleteLater()
        self.condition_rows.clear()

        # Add condition rows
        for cond in rule.conditions.conditions:
            if isinstance(cond, Condition):
                self._add_condition_row(cond)

        # Destination
        self.dest_input.setText(rule.action.destination)

        # Duplicate
        dup_val = (
            rule.action.on_duplicate.value
            if isinstance(rule.action.on_duplicate, DuplicateAction)
            else str(rule.action.on_duplicate).lower()
        )
        dup_map = {"rename": 0, "replace": 1, "skip": 2}
        self.dup_combo.setCurrentIndex(dup_map.get(dup_val, 0))

        # Action type
        act_val = (
            rule.action.action_type.value
            if isinstance(rule.action.action_type, FileActionType)
            else str(rule.action.action_type).lower()
        )
        self.act_type_combo.setCurrentIndex(0 if act_val == "move" else 1)

        self._run_sandbox_test()

    def _add_condition_row(self, condition: Optional[Condition] = None) -> None:
        row_widget = ConditionRowWidget(condition)
        row_widget.deleted.connect(self._remove_condition_row)
        self.condition_rows.append(row_widget)
        self.cond_rows_container.addWidget(row_widget)

    def _remove_condition_row(self, row_widget: ConditionRowWidget) -> None:
        if row_widget in self.condition_rows:
            self.condition_rows.remove(row_widget)
            self.cond_rows_container.removeWidget(row_widget)
            row_widget.deleteLater()
            self._on_rule_edited()

    def _insert_token(self, token: str) -> None:
        self.dest_input.insert(token)
        self.dest_input.setFocus()

    def _on_rule_selected(self, row: int) -> None:
        if row >= 0 and row < len(self.rules):
            self._display_rule(row)

    def _on_rule_edited(self) -> None:
        self._run_sandbox_test()

    def _save_current_rule(self) -> None:
        if self.selected_rule_index < 0 or self.selected_rule_index >= len(self.rules):
            return

        name = self.rule_name_input.text().strip() or "Untitled Rule"
        desc = self.rule_desc_input.text().strip()
        enabled = self.rule_enabled_chk.isChecked()
        log_op = LogicalOp.AND if self.logic_combo.currentIndex() == 0 else LogicalOp.OR

        conditions = [row.get_condition() for row in self.condition_rows]
        cond_group = ConditionGroup(logical_operator=log_op, conditions=conditions)

        dest = self.dest_input.text().strip() or "Organized/"
        dup_opts = [DuplicateAction.RENAME, DuplicateAction.REPLACE, DuplicateAction.SKIP]
        dup_action = dup_opts[self.dup_combo.currentIndex()]

        act_type = FileActionType.MOVE if self.act_type_combo.currentIndex() == 0 else FileActionType.COPY

        rule = self.rules[self.selected_rule_index]
        rule.name = name
        rule.description = desc
        rule.enabled = enabled
        rule.conditions = cond_group
        rule.action = Action(
            destination=dest,
            action_type=act_type,
            on_duplicate=dup_action,
        )

        curr_row = self.selected_rule_index
        self._load_rule_list()
        self.rule_list_widget.setCurrentRow(curr_row)
        self.rules_updated.emit()
        self._run_sandbox_test()

    def _add_new_rule(self) -> None:
        new_rule = Rule(
            name=f"Custom Rule {len(self.rules) + 1}",
            priority=(len(self.rules) + 1) * 10,
            conditions=ConditionGroup(
                logical_operator=LogicalOp.AND,
                conditions=[Condition(ConditionField.EXTENSION, ConditionOp.EQUALS, "pdf")],
            ),
            action=Action(destination="Documents/"),
        )
        self.rules.append(new_rule)
        self._load_rule_list()
        self.rule_list_widget.setCurrentRow(len(self.rules) - 1)
        self.rules_updated.emit()

    def _delete_current_rule(self) -> None:
        if not self.rules:
            return
        idx = self.selected_rule_index
        del self.rules[idx]
        if not self.rules:
            self._add_new_rule()
        else:
            new_idx = min(idx, len(self.rules) - 1)
            self._load_rule_list()
            self.rule_list_widget.setCurrentRow(new_idx)
        self.rules_updated.emit()

    def _move_rule_up(self) -> None:
        idx = self.selected_rule_index
        if idx > 0:
            self.rules[idx], self.rules[idx - 1] = self.rules[idx - 1], self.rules[idx]
            self._load_rule_list()
            self.rule_list_widget.setCurrentRow(idx - 1)
            self.rules_updated.emit()

    def _move_rule_down(self) -> None:
        idx = self.selected_rule_index
        if idx < len(self.rules) - 1:
            self.rules[idx], self.rules[idx + 1] = self.rules[idx + 1], self.rules[idx]
            self._load_rule_list()
            self.rule_list_widget.setCurrentRow(idx + 1)
            self.rules_updated.emit()

    def _run_sandbox_test(self) -> None:
        test_str = self.test_filename_input.text().strip()
        if not test_str:
            self.sandbox_result_lbl.setText("Enter a filename above to test rule matching in real-time.")
            self.sandbox_result_lbl.setStyleSheet("color: #9ca3af; font-size: 12px;")
            return

        # Create mock FileMetadata
        test_path = Path(test_str)
        ext = test_path.suffix.lower().lstrip(".")
        cat = FileCategory.OTHER
        from dropsort.models import CATEGORY_EXTENSIONS
        for c, s in CATEGORY_EXTENSIONS.items():
            if ext in s:
                cat = c
                break

        meta = FileMetadata(
            path=test_path,
            name=test_path.name,
            base_name=test_path.stem,
            extension=ext,
            size_bytes=1024 * 1024 * 2,  # Mock 2MB
            created_at=datetime.now(),
            modified_at=datetime.now(),
            category=cat,
        )

        engine = RuleEngine(self.rules)
        res = engine.plan_file(meta, Path.cwd())

        if res:
            rule, dest = res
            self.sandbox_result_lbl.setText(
                f"✔ Matched Rule: <b style='color:#10b981;'>{rule.name}</b> (Priority {rule.priority})<br>"
                f"→ Destination: <b style='color:#6366f1;'>{dest.name}</b> in <code>{dest.parent.name}/</code>"
            )
            self.sandbox_result_lbl.setStyleSheet("color: #f3f4f6; font-size: 12px;")
        else:
            self.sandbox_result_lbl.setText(
                f"✖ No active rule matched <b style='color:#ef4444;'>'{test_str}'</b>. File will remain in place."
            )
            self.sandbox_result_lbl.setStyleSheet("color: #ef4444; font-size: 12px;")

    def _import_rules(self) -> None:
        fpath, _ = QFileDialog.getOpenFileName(self, "Import Rules", "", "JSON Rules (*.json);;YAML Rules (*.yaml *.yml)")
        if fpath:
            try:
                self.rules = load_rules_from_file(fpath)
                self._load_rule_list()
                self.rules_updated.emit()
                QMessageBox.information(self, "Success", f"Successfully imported {len(self.rules)} rules!")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import rules: {e}")

    def _export_rules(self) -> None:
        fpath, _ = QFileDialog.getSaveFileName(self, "Export Rules", "rules.json", "JSON Rules (*.json);;YAML Rules (*.yaml)")
        if fpath:
            try:
                save_rules_to_file(self.rules, fpath)
                QMessageBox.information(self, "Success", f"Rules exported successfully to:\n{fpath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export rules: {e}")
