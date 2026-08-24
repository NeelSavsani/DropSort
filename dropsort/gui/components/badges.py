"""Visual badge pill widgets for categories, status tags, and duplicate actions."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget


class Badge(QLabel):
    """Pill-style badge label with curated color schemes."""

    COLORS = {
        "primary": ("#6366f1", "rgba(99, 102, 241, 0.15)"),
        "success": ("#10b981", "rgba(16, 185, 129, 0.15)"),
        "warning": ("#f59e0b", "rgba(245, 158, 11, 0.15)"),
        "danger": ("#ef4444", "rgba(239, 68, 68, 0.15)"),
        "info": ("#06b6d4", "rgba(6, 182, 212, 0.15)"),
        "muted": ("#9ca3af", "rgba(156, 163, 175, 0.12)"),
    }

    def __init__(
        self,
        text: str,
        variant: str = "primary",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.variant = variant
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.update_style()

    def update_style(self) -> None:
        fg, bg = self.COLORS.get(self.variant, self.COLORS["primary"])
        self.setStyleSheet(f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                border: 1px solid {fg};
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
            }}
        """)

    def set_badge(self, text: str, variant: str) -> None:
        self.setText(text)
        self.variant = variant
        self.update_style()
