"""Toast notification banners for in-app alerts and execution feedback."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class ToastNotification(QFrame):
    """Floating notification toast banner."""

    def __init__(
        self,
        message: str,
        variant: str = "success",
        duration_ms: int = 3500,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.duration_ms = duration_ms

        color_map = {
            "success": ("#10b981", "#052e16"),
            "error": ("#ef4444", "#450a0a"),
            "info": ("#6366f1", "#1e1b4b"),
            "warning": ("#f59e0b", "#451a03"),
        }
        border_col, bg_col = color_map.get(variant, color_map["info"])

        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 8px;
                padding: 6px 12px;
            }}
            QLabel {{
                color: #f3f4f6;
                font-size: 13px;
                font-weight: 500;
                background: transparent;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        icon_map = {
            "success": "✔",
            "error": "✖",
            "info": "ℹ",
            "warning": "⚠",
        }
        icon_lbl = QLabel(icon_map.get(variant, "ℹ"))
        icon_lbl.setStyleSheet(f"color: {border_col}; font-weight: bold; background: transparent;")
        layout.addWidget(icon_lbl)

        self.msg_lbl = QLabel(message)
        layout.addWidget(self.msg_lbl)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #9ca3af;
                font-size: 12px;
                padding: 0;
            }
            QPushButton:hover {
                color: #ffffff;
            }
        """)
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self.close)
