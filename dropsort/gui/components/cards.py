"""Custom Card and KPI Metric widgets for PySide6 GUI."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class StatCard(QFrame):
    """Visual KPI Card displaying key statistics."""

    def __init__(
        self,
        title: str,
        value: str = "0",
        subtitle: str = "",
        icon: str = "📊",
        accent_color: str = "#6366f1",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("statCard")
        self.accent_color = accent_color
        self.setStyleSheet(f"""
            QFrame#statCard {{
                background-color: #18202c;
                border: 1px solid #283548;
                border-left: 4px solid {accent_color};
                border-radius: 12px;
                padding: 12px 16px;
            }}
            QFrame#statCard:hover {{
                border-color: #3b4d66;
                border-left-color: {accent_color};
                background-color: #1c2534;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Header with icon and title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        self.icon_label = QLabel(icon)
        self.icon_label.setStyleSheet("font-size: 18px; background: transparent;")
        header_layout.addWidget(self.icon_label)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 600; text-transform: uppercase; background: transparent;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Main big value
        self.val_label = QLabel(value)
        self.val_label.setStyleSheet(f"color: #f3f4f6; font-size: 26px; font-weight: 700; background: transparent;")
        layout.addWidget(self.val_label)

        # Subtitle / description
        self.sub_label = QLabel(subtitle)
        self.sub_label.setStyleSheet("color: #6b7280; font-size: 11px; background: transparent;")
        layout.addWidget(self.sub_label)

    def set_value(self, val: str | int) -> None:
        self.val_label.setText(str(val))

    def set_subtitle(self, sub: str) -> None:
        self.sub_label.setText(sub)
