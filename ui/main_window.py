"""RecoverX MVP main window."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from core.logging_config import configure_logging
from engines.photorec import PhotoRecAdapter
from services.image_service import validate_image

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        configure_logging()
        self.engine = PhotoRecAdapter()
        self.selected_image: Path | None = None
        self.setWindowTitle("RecoverX — Intelligent Data Recovery")
        self.resize(1120, 740)
        self.setMinimumSize(840, 580)
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #0c1220; color: #e7edf7; font-family: 'Segoe UI'; }
            QLabel#muted { color: #91a0b8; }
            QLabel#title { font-size: 28px; font-weight: 700; }
            QLabel#metric { font-size: 25px; font-weight: 700; color: #62d6b0; }
            QFrame#card { background: #141e30; border: 1px solid #26334a; border-radius: 12px; }
            QPushButton { background: #1c2a40; border: 1px solid #34445f; border-radius: 8px; padding: 11px 16px; text-align: left; }
            QPushButton:hover { background: #263b57; }
            QPushButton#primary { background: #157b69; border: 0; font-weight: 700; }
            QPushButton#primary:hover { background: #19947e; }
        """)

        shell = QWidget()
        outer = QHBoxLayout(shell)
        outer.setContentsMargins(0, 0, 0, 0)
        nav = QFrame()
        nav.setFixedWidth(220)
        nav.setStyleSheet("background:#101827; border-right:1px solid #26334a")
        nav_layout = QVBoxLayout(nav)
        brand = QLabel("◈  RecoverX")
        brand.setStyleSheet("font-size:22px;font-weight:700;padding:16px;color:#72dfbd")
        nav_layout.addWidget(brand)
        for name in ("Dashboard", "Data Recovery", "Device Manager", "Disk Imaging", "Advanced Scan", "Diagnostics", "Recovery History", "Reports", "Settings", "About RecoverX"):
            item = QPushButton(name)
            item.setFlat(True)
            nav_layout.addWidget(item)
        nav_layout.addStretch()
        nav_layout.addWidget(QLabel("  Local processing · No account", objectName="muted"))
        outer.addWidget(nav)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 28, 34, 28)
        heading = QLabel("Recovery dashboard", objectName="title")
        layout.addWidget(heading)
        layout.addWidget(QLabel("Select a disk image to begin a safe recovery workflow.", objectName="muted"))

        metrics = QHBoxLayout()
        self._add_metric(metrics, "Connected devices", "0", "Image-only MVP")
        engine_status = self.engine.status()
        self._add_metric(metrics, "Recovery engines", "1" if engine_status.available else "0", "PhotoRec detected" if engine_status.available else "PhotoRec not installed")
        self._add_metric(metrics, "Recent sessions", "0", "No scans run yet")
        layout.addLayout(metrics)

        card = QFrame(objectName="card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        label = QLabel("Start a recovery")
        label.setStyleSheet("font-size:19px;font-weight:700")
        card_layout.addWidget(label)
        card_layout.addWidget(QLabel("RecoverX currently accepts disk image files only. Physical device scanning is not enabled.", objectName="muted"))
        row = QHBoxLayout()
        self.image_label = QLabel("No image selected")
        self.image_label.setObjectName("muted")
        row.addWidget(self.image_label, 1)
        choose = QPushButton("Choose disk image")
        choose.clicked.connect(self.choose_image)
        row.addWidget(choose)
        card_layout.addLayout(row)
        self.destination_label = QLabel("Recovery destination: not selected")
        self.destination_label.setObjectName("muted")
        card_layout.addWidget(self.destination_label)
        controls = QHBoxLayout()
        dest_button = QPushButton("Choose destination")
        dest_button.clicked.connect(self.choose_destination)
        controls.addWidget(dest_button)
        self.scan_button = QPushButton("Start PhotoRec recovery", objectName="primary")
        self.scan_button.clicked.connect(self.start_recovery)
        controls.addWidget(self.scan_button)
        card_layout.addLayout(controls)
        layout.addWidget(card)

        info = QFrame(objectName="card")
        info_layout = QVBoxLayout(info)
        info_layout.addWidget(QLabel("Engine status"))
        info_layout.addWidget(QLabel(engine_status.message, objectName="muted"))
        info_layout.addWidget(QLabel("Scans are not yet enabled because a verified, noninteractive Windows PhotoRec CLI workflow is not available. RecoverX will not report fabricated progress or results.", objectName="muted"))
        layout.addWidget(info)
        layout.addStretch()
        outer.addWidget(content, 1)
        self.setCentralWidget(shell)

    @staticmethod
    def _add_metric(layout: QHBoxLayout, title: str, value: str, subtitle: str) -> None:
        card = QFrame(objectName="card")
        box = QVBoxLayout(card)
        box.addWidget(QLabel(title, objectName="muted"))
        box.addWidget(QLabel(value, objectName="metric"))
        box.addWidget(QLabel(subtitle, objectName="muted"))
        layout.addWidget(card)

    def choose_image(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Select disk image", "", "Disk images (*.img *.dd *.raw *.dmg *.e01 *.001 *.iso);;All files (*)")
        if not filename:
            return
        try:
            self.selected_image = validate_image(Path(filename))
            self.image_label.setText(f"{self.selected_image.name} · {self.selected_image.stat().st_size:,} bytes")
            log.info("Selected disk image: %s", self.selected_image)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid image", str(exc))

    def choose_destination(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a separate recovery destination")
        if folder:
            self.destination_label.setText(f"Recovery destination: {Path(folder)}")

    def start_recovery(self) -> None:
        QMessageBox.information(self, "PhotoRec integration status", "No scan was started. Automated scanning is disabled until the installed PhotoRec CLI and safe read-only invocation are verified.")
