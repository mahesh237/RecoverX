"""Background worker for copying and verifying selected recovery results."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from services.recovery_copy import CopyReport, copy_recovered_files


class RecoveryCopyWorker(QThread):
    progress = Signal(int, int, str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, files: list[Path], recovery_root: Path, source_image: Path, destination: Path) -> None:
        super().__init__()
        self.files = files
        self.recovery_root = recovery_root
        self.source_image = source_image
        self.destination = destination
        self.cancel_event = threading.Event()

    def run(self) -> None:
        try:
            report: CopyReport = copy_recovered_files(
                self.files,
                recovery_root=self.recovery_root,
                source_image=self.source_image,
                destination=self.destination,
                cancel_event=self.cancel_event,
                on_progress=lambda current, total, path: self.progress.emit(current, total, path.name),
            )
            self.completed.emit(report)
        except Exception as exc:
            self.failed.emit(str(exc))

    def cancel(self) -> None:
        self.cancel_event.set()
