"""Background PhotoRec scan worker."""

from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal

from engines.photorec import PhotoRecAdapter, ScanResult


class PhotoRecScanWorker(QThread):
    output_line = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, engine: PhotoRecAdapter, image: str, destination: str) -> None:
        super().__init__()
        self.engine = engine
        self.image = image
        self.destination = destination
        self.cancel_event = threading.Event()

    def run(self) -> None:
        try:
            result: ScanResult = self.engine.scan(
                self.image, self.destination,
                cancel_event=self.cancel_event,
                on_output=self.output_line.emit,
            )
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    def cancel(self) -> None:
        self.cancel_event.set()
        self.engine.cancel()
