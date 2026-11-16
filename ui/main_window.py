"""RecoverX MVP main window."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QPlainTextEdit,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.logging_config import configure_logging
from engines.photorec import PhotoRecAdapter, ScanResult
from services.recovery_copy import CopyReport
from services.image_service import validate_image
from ui.copy_worker import RecoveryCopyWorker
from ui.scan_worker import PhotoRecScanWorker

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        configure_logging()
        self.engine = PhotoRecAdapter()
        self.selected_image: Path | None = None
        self.selected_destination: Path | None = None
        self.scan_worker: PhotoRecScanWorker | None = None
        self.copy_worker: RecoveryCopyWorker | None = None
        self.last_scan: ScanResult | None = None
        self.close_when_workers_stop = False
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
        card_layout.addWidget(QLabel("RecoverX currently scans disk images only. Physical device scanning is not enabled.", objectName="muted"))
        row = QHBoxLayout()
        self.image_label = QLabel("No image selected")
        self.image_label.setObjectName("muted")
        row.addWidget(self.image_label, 1)
        self.image_button = QPushButton("Choose disk image")
        self.image_button.clicked.connect(self.choose_image)
        row.addWidget(self.image_button)
        card_layout.addLayout(row)
        self.destination_label = QLabel("Recovery destination: not selected")
        self.destination_label.setObjectName("muted")
        card_layout.addWidget(self.destination_label)
        controls = QHBoxLayout()
        self.destination_button = QPushButton("Choose destination")
        self.destination_button.clicked.connect(self.choose_destination)
        controls.addWidget(self.destination_button)
        self.scan_button = QPushButton("Start PhotoRec recovery", objectName="primary")
        self.scan_button.clicked.connect(self.start_recovery)
        controls.addWidget(self.scan_button)
        self.cancel_button = QPushButton("Cancel scan")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_recovery)
        controls.addWidget(self.cancel_button)
        card_layout.addLayout(controls)
        layout.addWidget(card)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        results_header = QHBoxLayout()
        results_header.addWidget(QLabel("Recovered files · select rows to copy"))
        results_header.addStretch()
        self.result_count = QLabel("0 files")
        self.result_count.setObjectName("muted")
        results_header.addWidget(self.result_count)
        layout.addLayout(results_header)

        self.results = QTableWidget(0, 5)
        self.results.setHorizontalHeaderLabels(["File", "Type", "Size", "Location", "Copy status"])
        self.results.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.results.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.results.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.results.itemSelectionChanged.connect(self.update_copy_button)
        layout.addWidget(self.results, 1)

        copy_controls = QHBoxLayout()
        self.copy_button = QPushButton("Copy selected files")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.choose_copy_destination)
        copy_controls.addWidget(self.copy_button)
        self.cancel_copy_button = QPushButton("Cancel copy")
        self.cancel_copy_button.setEnabled(False)
        self.cancel_copy_button.clicked.connect(self.cancel_copy)
        copy_controls.addWidget(self.cancel_copy_button)
        copy_controls.addStretch()
        layout.addLayout(copy_controls)

        info = QFrame(objectName="card")
        info_layout = QVBoxLayout(info)
        info_layout.addWidget(QLabel("Engine status"))
        info_layout.addWidget(QLabel(engine_status.message, objectName="muted"))
        info_layout.addWidget(QLabel("PhotoRec runs through its documented scripted interface. Scan percentage is not available; recovered files are listed from actual output.", objectName="muted"))
        self.engine_log = QPlainTextEdit()
        self.engine_log.setReadOnly(True)
        self.engine_log.setMaximumBlockCount(500)
        self.engine_log.setPlaceholderText("PhotoRec output will appear here.")
        self.engine_log.setMaximumHeight(120)
        info_layout.addWidget(self.engine_log)
        layout.addWidget(info)
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
        if self.copy_worker is not None and self.copy_worker.isRunning():
            return
        filename, _ = QFileDialog.getOpenFileName(self, "Select disk image", "", "Disk images (*.img *.dd *.raw *.dmg *.e01 *.001 *.iso);;All files (*)")
        if not filename:
            return
        try:
            self.selected_image = validate_image(Path(filename))
            self.image_label.setText(f"{self.selected_image.name} · {self.selected_image.stat().st_size:,} bytes")
            self.last_scan = None
            self.results.setRowCount(0)
            self.result_count.setText("0 files")
            self.update_copy_button()
            log.info("Selected disk image: %s", self.selected_image)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Invalid image", str(exc))

    def choose_destination(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a separate recovery destination")
        if folder:
            self.selected_destination = Path(folder).resolve()
            self.destination_label.setText(f"Recovery destination: {self.selected_destination}")

    def start_recovery(self) -> None:
        if self.scan_worker is not None and self.scan_worker.isRunning():
            return
        if self.selected_image is None or self.selected_destination is None:
            QMessageBox.warning(self, "Select recovery paths", "Choose a disk image and a destination folder first.")
            return
        try:
            PhotoRecAdapter.validate_inputs(self.selected_image, self.selected_destination)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Recovery path check", str(exc))
            return
        engine_status = self.engine.status()
        if not engine_status.available:
            QMessageBox.warning(self, "PhotoRec unavailable", engine_status.message)
            return

        self.results.setRowCount(0)
        self.result_count.setText("0 files")
        self.last_scan = None
        self.update_copy_button()
        self.engine_log.clear()
        self.progress.setRange(0, 0)
        self.progress.setFormat("PhotoRec scanning — percentage unavailable")
        self.scan_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.image_button.setEnabled(False)
        self.destination_button.setEnabled(False)
        log.info("User started image recovery: %s", self.selected_image)
        self.scan_worker = PhotoRecScanWorker(self.engine, str(self.selected_image), str(self.selected_destination))
        self.scan_worker.output_line.connect(self.engine_log.appendPlainText)
        self.scan_worker.completed.connect(self.recovery_completed)
        self.scan_worker.failed.connect(self.recovery_failed)
        self.scan_worker.finished.connect(self.scan_thread_finished)
        self.scan_worker.start()

    def cancel_recovery(self) -> None:
        if self.scan_worker is not None and self.scan_worker.isRunning():
            self.cancel_button.setEnabled(False)
            self.progress.setFormat("Stopping PhotoRec…")
            self.scan_worker.cancel()

    def recovery_completed(self, result: ScanResult) -> None:
        self.last_scan = result
        self.results.setRowCount(len(result.recovered_files))
        for row, recovered_file in enumerate(result.recovered_files):
            suffix = recovered_file.suffix.lstrip(".").upper() or "UNKNOWN"
            media_type = mimetypes.guess_type(recovered_file.name)[0]
            type_label = f"{suffix} · {media_type}" if media_type else suffix
            values = (
                recovered_file.name,
                type_label,
                self._format_size(recovered_file.stat().st_size),
                str(recovered_file),
                "Ready",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, str(recovered_file.resolve()))
                self.results.setItem(row, column, item)
        self.result_count.setText(f"{len(result.recovered_files)} files")
        self.update_copy_button()
        count = len(result.recovered_files)
        if result.cancelled:
            summary = f"Scan cancelled. {count} recovered file(s) found in {result.output_directory}."
        elif result.return_code == 0:
            summary = f"Scan complete. {count} recovered file(s) found in {result.output_directory}."
        else:
            summary = f"PhotoRec exited with code {result.return_code}. {count} output file(s) found in {result.output_directory}."
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.progress.setFormat(summary)
        log.info("%s", summary)

    def recovery_failed(self, message: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Recovery failed")
        log.error("PhotoRec recovery failed: %s", message)
        QMessageBox.critical(self, "Recovery failed", message)

    def scan_thread_finished(self) -> None:
        self.scan_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.image_button.setEnabled(True)
        self.destination_button.setEnabled(True)
        self.scan_worker = None
        self._close_when_workers_stop()

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
            value /= 1024
        return f"{size} B"

    def update_copy_button(self) -> None:
        selected = bool(self.results.selectionModel().selectedRows())
        can_copy = self.last_scan is not None and self.selected_image is not None
        self.copy_button.setEnabled(selected and can_copy and self.copy_worker is None)

    def choose_copy_destination(self) -> None:
        if self.last_scan is None or self.selected_image is None:
            QMessageBox.warning(self, "No recovery results", "Run a scan before copying recovered files.")
            return
        selected_rows = sorted({index.row() for index in self.results.selectionModel().selectedRows()})
        files = [Path(self.results.item(row, 0).data(Qt.ItemDataRole.UserRole)) for row in selected_rows]
        if not files:
            QMessageBox.warning(self, "Select files", "Select one or more recovered files first.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Choose a safe copy destination")
        if not folder:
            return
        self.start_copy(files, Path(folder))

    def start_copy(self, files: list[Path], destination: Path) -> None:
        if self.last_scan is None or self.selected_image is None:
            return
        self.copy_button.setEnabled(False)
        self.cancel_copy_button.setEnabled(True)
        self.results.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.image_button.setEnabled(False)
        self.destination_button.setEnabled(False)
        self.progress.setRange(0, len(files))
        self.progress.setValue(0)
        self.progress.setFormat("Preparing verified copies…")
        self.copy_worker = RecoveryCopyWorker(
            files, self.last_scan.output_directory, self.selected_image, destination,
        )
        self.copy_worker.progress.connect(self.copy_progress)
        self.copy_worker.completed.connect(self.copy_completed)
        self.copy_worker.failed.connect(self.copy_failed)
        self.copy_worker.finished.connect(self.copy_thread_finished)
        log.info("User requested verified recovery copies: count=%d destination=%s", len(files), destination)
        self.copy_worker.start()

    def copy_progress(self, current: int, total: int, filename: str) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(max(0, current - 1))
        self.progress.setFormat(f"Copying {filename} ({current} of {total})")

    def cancel_copy(self) -> None:
        if self.copy_worker is not None and self.copy_worker.isRunning():
            self.cancel_copy_button.setEnabled(False)
            self.progress.setFormat("Stopping after current file…")
            self.copy_worker.cancel()

    def copy_completed(self, report: CopyReport) -> None:
        rows_by_path = {
            Path(self.results.item(row, 0).data(Qt.ItemDataRole.UserRole)): row
            for row in range(self.results.rowCount())
        }
        for record in report.copied:
            row = rows_by_path.get(record.source)
            if row is not None:
                status = self.results.item(row, 4)
                status.setText("Copied · SHA-256 verified")
                status.setToolTip(f"{record.destination}\nSHA-256: {record.sha256}")
        for failure in report.failed:
            row = rows_by_path.get(failure.source)
            if row is not None:
                status = self.results.item(row, 4)
                status.setText("Copy failed")
                status.setToolTip(failure.message)
        total = len(report.copied) + len(report.failed)
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(total)
        summary = f"{len(report.copied)} copied and verified; {len(report.failed)} failed."
        if report.copied:
            summary += f" Destination: {report.copied[0].destination.parent}"
        if report.cancelled:
            summary = "Copy cancelled. " + summary
        self.progress.setFormat(summary)
        log.info("Verified copy batch finished: copied=%d failed=%d cancelled=%s", len(report.copied), len(report.failed), report.cancelled)
        if report.failed:
            details = "\n".join(f"{failure.source.name}: {failure.message}" for failure in report.failed[:5])
            QMessageBox.warning(self, "Some files were not copied", f"{summary}\n\n{details}")

    def copy_failed(self, message: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setFormat("Copy could not start")
        log.error("Could not start verified copy: %s", message)
        QMessageBox.warning(self, "Copy could not start", message)

    def copy_thread_finished(self) -> None:
        self.copy_worker = None
        self.cancel_copy_button.setEnabled(False)
        self.results.setEnabled(True)
        self.results.clearSelection()
        self.scan_button.setEnabled(True)
        self.image_button.setEnabled(True)
        self.destination_button.setEnabled(True)
        self.update_copy_button()
        self._close_when_workers_stop()

    def _close_when_workers_stop(self) -> None:
        scan_active = self.scan_worker is not None and self.scan_worker.isRunning()
        copy_active = self.copy_worker is not None and self.copy_worker.isRunning()
        if self.close_when_workers_stop and not scan_active and not copy_active:
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        scan_active = self.scan_worker is not None and self.scan_worker.isRunning()
        copy_active = self.copy_worker is not None and self.copy_worker.isRunning()
        if scan_active or copy_active:
            self.close_when_workers_stop = True
            self.cancel_recovery()
            self.cancel_copy()
            event.ignore()
            return
        event.accept()
