"""PhotoRec image-only command adapter using CGSecurity's scripted CLI."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineStatus:
    available: bool
    executable: Path | None
    version: str | None
    message: str


@dataclass(frozen=True)
class ScanResult:
    output_directory: Path
    recovered_files: tuple[Path, ...]
    return_code: int
    cancelled: bool


class PhotoRecAdapter:
    """Find PhotoRec and invoke it on a disk image, never a physical device."""

    CANDIDATES = ("photorec", "photorec_win", "photorec.exe", "photorec_win.exe")

    def __init__(self, executable: str | Path | None = None) -> None:
        self.executable = Path(executable) if executable else self._find_executable()
        self._process: subprocess.Popen[str] | None = None

    @classmethod
    def _find_executable(cls) -> Path | None:
        for candidate in cls.CANDIDATES:
            found = shutil.which(candidate)
            if found:
                return Path(found)
        return None

    def status(self) -> EngineStatus:
        if self.executable is None or not self.executable.is_file():
            return EngineStatus(False, None, None, "PhotoRec not found. Install TestDisk from cgsecurity.org.")
        try:
            result = subprocess.run(
                [str(self.executable), "/version"], capture_output=True, text=True,
                timeout=5, check=False, env=self._process_environment(),
            )
            output = (result.stdout + " " + result.stderr).strip()
            version = output[:160] if output else "Version unavailable"
            return EngineStatus(True, self.executable, version, "PhotoRec ready for disk-image scans.")
        except (OSError, subprocess.TimeoutExpired) as exc:
            return EngineStatus(True, self.executable, None, f"PhotoRec found; version check failed: {exc}")

    @staticmethod
    def _process_environment() -> dict[str, str]:
        environment = os.environ.copy()
        # CGSecurity documents this for image files: they do not need raw-device
        # privileges, and the compatibility layer avoids a needless UAC prompt.
        if os.name == "nt":
            environment["__COMPAT_LAYER"] = "RunAsInvoker"
        return environment

    @staticmethod
    def validate_inputs(image: Path, destination: Path) -> tuple[Path, Path]:
        image = image.expanduser().resolve(strict=True)
        destination = destination.expanduser().resolve(strict=True)
        if not image.is_file():
            raise ValueError("The source must be a disk image file.")
        if not destination.is_dir():
            raise ValueError("The recovery destination must be an existing folder.")
        if not os.access(image, os.R_OK):
            raise ValueError("The image is not readable.")
        if not os.access(destination, os.W_OK):
            raise ValueError("The recovery destination is not writable.")
        if image.stat().st_dev == destination.stat().st_dev:
            raise ValueError("Choose a recovery destination on a different storage device from the source image.")
        return image, destination

    def build_command(self, image: Path, destination: Path, run_directory: Path) -> list[str]:
        """Build the documented PhotoRec scripted-run command for an image."""
        if self.executable is None:
            raise RuntimeError("PhotoRec was not found. Install TestDisk first.")
        image, destination = self.validate_inputs(image, destination)
        run_directory = run_directory.expanduser().resolve(strict=False)
        if run_directory.parent != destination:
            raise ValueError("The scan output folder must be directly inside the selected destination.")
        if run_directory.exists():
            raise ValueError("The scan output folder already exists.")
        return [
            str(self.executable), "/log", "/logname", str(run_directory / "photorec.log"),
            "/d", str(run_directory), "/cmd", str(image),
            "partition_none,fileopt,everything,enable,search",
        ]

    def scan(
        self,
        image: Path,
        destination: Path,
        *,
        cancel_event: threading.Event | None = None,
        on_output: Callable[[str], None] | None = None,
    ) -> ScanResult:
        """Run PhotoRec and return files actually created by the engine."""
        if self.executable is None or not self.executable.is_file():
            raise RuntimeError("PhotoRec was not found. Install TestDisk first.")
        image, destination = self.validate_inputs(image, destination)
        run_name = datetime.now().strftime("RecoverX_%Y%m%d_%H%M%S_%f")
        run_directory = destination / run_name
        command = self.build_command(image, destination, run_directory)
        run_directory.mkdir(parents=False, exist_ok=False)
        cancelled = False
        log.info("Starting PhotoRec image scan: image=%s output=%s", image, run_directory)
        try:
            self._process = subprocess.Popen(
                command, cwd=run_directory, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                encoding="utf-8", errors="replace", bufsize=1,
                env=self._process_environment(),
            )
            assert self._process.stdout is not None
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                self._process.terminate()
            for line in self._process.stdout:
                line = line.rstrip()
                if line and on_output is not None:
                    on_output(line)
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    self._process.terminate()
                    break
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
            try:
                return_code = self._process.wait(timeout=5 if cancelled else None)
            except subprocess.TimeoutExpired:
                self._process.kill()
                return_code = self._process.wait()
        except OSError as exc:
            log.exception("Could not start PhotoRec")
            raise RuntimeError(f"Could not start PhotoRec: {exc}") from exc
        finally:
            self._process = None

        output_directories = sorted(
            path for path in destination.iterdir()
            if path.is_dir() and path.name.startswith(f"{run_name}.")
        )
        output_directory = output_directories[-1] if output_directories else run_directory
        recovered = tuple(sorted(
            path for path in output_directory.rglob("*")
            if path.is_file() and path.name.lower() not in {"photorec.log", "photorec.ses", "report.xml"}
        ))
        log.info("PhotoRec scan ended: return_code=%d cancelled=%s files=%d output=%s", return_code, cancelled, len(recovered), output_directory)
        return ScanResult(output_directory, recovered, return_code, cancelled)

    def cancel(self) -> None:
        """Stop a currently running scan, if one is active."""
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
