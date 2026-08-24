"""Drag and Drop target zone for folder selection."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class DropZone(QFrame):
    """Drag-and-drop zone widget for directory selection."""

    folder_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.current_folder: str = ""

        self.setObjectName("dropZone")
        self._set_idle_style()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(10)

        # Icon
        self.icon_label = QLabel("📁")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setStyleSheet("font-size: 32px; background: transparent;")
        layout.addWidget(self.icon_label)

        # Title / prompt
        self.title_label = QLabel("Drag and Drop a Folder Here")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #f3f4f6; background: transparent;")
        layout.addWidget(self.title_label)

        # Subtitle
        self.sub_label = QLabel("or click below to choose a directory to organize")
        self.sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub_label.setStyleSheet("font-size: 12px; color: #9ca3af; background: transparent;")
        layout.addWidget(self.sub_label)

        # Browse button
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.browse_btn = QPushButton("📁 Browse Folder")
        self.browse_btn.setObjectName("primaryBtn")
        self.browse_btn.setMinimumHeight(38)
        self.browse_btn.setMinimumWidth(160)
        self.browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_btn.clicked.connect(self._open_file_dialog)
        btn_layout.addWidget(self.browse_btn)

        layout.addLayout(btn_layout)

    def _set_idle_style(self) -> None:
        self.setStyleSheet("""
            QFrame#dropZone {
                background-color: #141b24;
                border: 2px dashed #2e3d52;
                border-radius: 12px;
            }
            QFrame#dropZone:hover {
                border-color: #6366f1;
                background-color: #18202c;
            }
        """)

    def _set_active_style(self) -> None:
        self.setStyleSheet("""
            QFrame#dropZone {
                background-color: rgba(99, 102, 241, 0.1);
                border: 2px dashed #6366f1;
                border-radius: 12px;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and Path(urls[0].toLocalFile()).is_dir():
                event.acceptProposedAction()
                self._set_active_style()
                return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_idle_style()
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_idle_style()
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_dir():
                self.set_folder(path)
                self.folder_selected.emit(path)
                event.acceptProposedAction()

    def _open_file_dialog(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Organize")
        if folder:
            self.set_folder(folder)
            self.folder_selected.emit(folder)

    def set_folder(self, folder_path: str) -> None:
        self.current_folder = folder_path
        self.title_label.setText(f"Target: {Path(folder_path).name}")
        self.sub_label.setText(folder_path)
